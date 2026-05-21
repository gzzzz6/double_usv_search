from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from lxml import etree


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}
W = "{%s}" % NS["w"]
M = "{%s}" % NS["m"]


CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百\d]+章(?:\s+.+)?$")
H2_RE = re.compile(r"^(\d+)(?:\s+|　+)(.+)$")
H3_RE = re.compile(r"^(\d+\.\d+)(?:\s+|　+)(.+)$")
H4_RE = re.compile(r"^(\d+\.\d+\.\d+)(?:\s+|　+)(.+)$")
FIG_CAPTION_RE = re.compile(r"^图\s*\d+(?:[-.]\d+)?(?:续)?\s*")
TABLE_CAPTION_RE = re.compile(r"^表\s*\d+(?:[-.]\d+)?(?:续)?\s*")
FORMULA_NUM_RE = re.compile(r"[（(]\s*\d+\s*[）)]")


def wval(el: etree._Element | None, attr: str = "val") -> str | None:
    if el is None:
        return None
    return el.get(W + attr)


def text_of(el: etree._Element) -> str:
    parts: list[str] = []
    for t in el.xpath(".//w:t | .//w:instrText | .//w:delText", namespaces=NS):
        if t.text:
            parts.append(t.text)
    return "".join(parts).strip()


def compact_text(s: str) -> str:
    return re.sub(r"[\s\u00a0　]+", "", s)


def has_text_run(el: etree._Element) -> bool:
    return bool(el.xpath(".//w:t[normalize-space(.)!='']", namespaces=NS))


def twips_to_pt(v: str | None) -> float | None:
    if v is None:
        return None
    try:
        return round(int(v) / 20.0, 2)
    except Exception:
        return None


def halfpt_to_pt(v: str | None) -> float | None:
    if v is None:
        return None
    try:
        return round(int(v) / 2.0, 2)
    except Exception:
        return None


def line_to_pt(v: str | None, rule: str | None) -> float | None:
    if v is None:
        return None
    try:
        n = int(v)
    except Exception:
        return None
    if rule in {"exact", "atLeast"}:
        return round(n / 20.0, 2)
    return round(n / 20.0, 2)


def load_xml(docx_path: Path, name: str) -> etree._Element:
    with zipfile.ZipFile(docx_path) as zf:
        return etree.fromstring(zf.read(name))


def merge_props(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if v is not None:
            out[k] = v
    return out


def rpr_to_dict(rpr: etree._Element | None) -> dict[str, Any]:
    if rpr is None:
        return {}
    rfonts = rpr.find("w:rFonts", NS)
    return {
        "ascii": rfonts.get(W + "ascii") if rfonts is not None else None,
        "hAnsi": rfonts.get(W + "hAnsi") if rfonts is not None else None,
        "eastAsia": rfonts.get(W + "eastAsia") if rfonts is not None else None,
        "sizePt": halfpt_to_pt(wval(rpr.find("w:sz", NS))),
        "bold": rpr.find("w:b", NS) is not None,
    }


def ppr_to_dict(ppr: etree._Element | None) -> dict[str, Any]:
    if ppr is None:
        return {}
    spacing = ppr.find("w:spacing", NS)
    ind = ppr.find("w:ind", NS)
    jc = ppr.find("w:jc", NS)
    out = {
        "jc": wval(jc),
        "beforePt": twips_to_pt(spacing.get(W + "before") if spacing is not None else None),
        "afterPt": twips_to_pt(spacing.get(W + "after") if spacing is not None else None),
        "lineRule": spacing.get(W + "lineRule") if spacing is not None else None,
        "linePt": line_to_pt(spacing.get(W + "line") if spacing is not None else None,
                             spacing.get(W + "lineRule") if spacing is not None else None),
        "firstLineTwips": ind.get(W + "firstLine") if ind is not None else None,
        "firstLineChars": ind.get(W + "firstLineChars") if ind is not None else None,
        "leftTwips": ind.get(W + "left") if ind is not None else None,
        "leftChars": ind.get(W + "leftChars") if ind is not None else None,
    }
    return out


def read_styles(styles_root: etree._Element) -> dict[str, dict[str, Any]]:
    raw: dict[str, dict[str, Any]] = {}
    for st in styles_root.xpath("//w:style", namespaces=NS):
        sid = st.get(W + "styleId")
        if not sid:
            continue
        raw[sid] = {
            "basedOn": wval(st.find("w:basedOn", NS)),
            "name": wval(st.find("w:name", NS)),
            "pPr": ppr_to_dict(st.find("w:pPr", NS)),
            "rPr": rpr_to_dict(st.find("w:rPr", NS)),
        }

    memo: dict[str, dict[str, Any]] = {}

    def resolve(sid: str | None) -> dict[str, Any]:
        if not sid or sid not in raw:
            return {"pPr": {}, "rPr": {}, "name": sid}
        if sid in memo:
            return memo[sid]
        base = resolve(raw[sid].get("basedOn"))
        merged = {
            "name": raw[sid].get("name"),
            "pPr": merge_props(base.get("pPr", {}), raw[sid].get("pPr", {})),
            "rPr": merge_props(base.get("rPr", {}), raw[sid].get("rPr", {})),
        }
        memo[sid] = merged
        return merged

    for sid in list(raw):
        resolve(sid)
    return memo


def p_style_id(p: etree._Element) -> str | None:
    pstyle = p.find("w:pPr/w:pStyle", NS)
    return wval(pstyle)


def para_effective_format(p: etree._Element, styles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sid = p_style_id(p)
    st = styles.get(sid or "", {"pPr": {}, "rPr": {}, "name": sid})
    p_fmt = merge_props(st.get("pPr", {}), ppr_to_dict(p.find("w:pPr", NS)))

    r_fmt = dict(st.get("rPr", {}))
    # Use the first run containing visible text, then fall back to the first run.
    runs = p.xpath("./w:r", namespaces=NS)
    chosen = None
    for r in runs:
        if text_of(r):
            chosen = r
            break
    if chosen is None and runs:
        chosen = runs[0]
    if chosen is not None:
        r_fmt = merge_props(r_fmt, rpr_to_dict(chosen.find("w:rPr", NS)))
    return {
        "styleId": sid,
        "styleName": st.get("name"),
        "pPr": p_fmt,
        "rPr": r_fmt,
    }


def is_chinese_font_song(rpr: dict[str, Any]) -> bool:
    ea = rpr.get("eastAsia")
    # Some paragraphs only store ascii/hAnsi. Treat that as suspicious, not a hard pass.
    return ea == "宋体"


def ascii_font_ok(rpr: dict[str, Any], expected: str) -> bool:
    vals = [rpr.get("ascii"), rpr.get("hAnsi")]
    return all((v is None or v == expected) for v in vals) and any(v == expected for v in vals)


def font_contains(rpr: dict[str, Any], expected: str) -> bool:
    return expected in {rpr.get("ascii"), rpr.get("hAnsi"), rpr.get("eastAsia")}


def is_exact_20(ppr: dict[str, Any]) -> bool:
    return ppr.get("lineRule") == "exact" and abs((ppr.get("linePt") or -1) - 20.0) < 0.01


def is_single_spacing(ppr: dict[str, Any]) -> bool:
    return ppr.get("lineRule") in {None, "auto"} and ppr.get("linePt") in {None, 12.0}


def is_zero_spacing(ppr: dict[str, Any]) -> bool:
    return (ppr.get("beforePt") in {None, 0.0}) and (ppr.get("afterPt") in {None, 0.0})


def check_heading(kind: str, text: str, fmt: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ppr = fmt["pPr"]
    rpr = fmt["rPr"]
    if kind == "chapter":
        if ppr.get("jc") != "center":
            issues.append(f"章标题未居中，jc={ppr.get('jc')}")
        if not font_contains(rpr, "黑体"):
            issues.append(f"章标题字体不是黑体，检测为 {rpr}")
        if rpr.get("sizePt") != 16.0:
            issues.append(f"章标题字号不是三号16pt，检测为 {rpr.get('sizePt')}pt")
        if not rpr.get("bold"):
            issues.append("章标题未加粗")
        if not is_single_spacing(ppr):
            issues.append(f"章标题不是单倍行距，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
        if ppr.get("beforePt") != 24.0 or ppr.get("afterPt") != 18.0:
            issues.append(f"章标题段前/段后不是24/18磅，检测为 {ppr.get('beforePt')}/{ppr.get('afterPt')}")
    elif kind == "h2":
        if ppr.get("jc") not in {None, "left"}:
            issues.append(f"二级标题未顶左，jc={ppr.get('jc')}")
        if not font_contains(rpr, "黑体"):
            issues.append(f"二级标题字体不是黑体，检测为 {rpr}")
        if rpr.get("sizePt") != 14.0:
            issues.append(f"二级标题字号不是四号14pt，检测为 {rpr.get('sizePt')}pt")
        if not is_single_spacing(ppr):
            issues.append(f"二级标题不是单倍行距，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
        if ppr.get("beforePt") != 24.0 or ppr.get("afterPt") != 6.0:
            issues.append(f"二级标题段前/段后不是24/6磅，检测为 {ppr.get('beforePt')}/{ppr.get('afterPt')}")
        if not re.match(r"^\d+(?:\s|　)", text):
            issues.append("二级标题编号与标题之间不是空格分隔")
    elif kind == "h3":
        if ppr.get("jc") not in {None, "left"}:
            issues.append(f"三级标题未左对齐，jc={ppr.get('jc')}")
        if not font_contains(rpr, "黑体"):
            issues.append(f"三级标题字体不是黑体，检测为 {rpr}")
        if rpr.get("sizePt") != 12.0:
            issues.append(f"三级标题字号不是小四12pt，检测为 {rpr.get('sizePt')}pt")
        if not is_single_spacing(ppr):
            issues.append(f"三级标题不是单倍行距，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
        if ppr.get("beforePt") != 12.0 or ppr.get("afterPt") != 6.0:
            issues.append(f"三级标题段前/段后不是12/6磅，检测为 {ppr.get('beforePt')}/{ppr.get('afterPt')}")
        first = ppr.get("firstLineChars") or ppr.get("firstLineTwips")
        if first is None:
            issues.append("三级标题未检测到首行缩进2个汉字符")
        if not re.match(r"^\d+\.\d+(?:\s|　)", text):
            issues.append("三级标题编号与标题之间不是空格分隔")
    elif kind == "h4":
        # The user gave explicit rules up to 1.1.1 as third-level heading.
        if ppr.get("jc") not in {None, "left"}:
            issues.append(f"1.1.1级标题未左对齐，jc={ppr.get('jc')}")
        if not font_contains(rpr, "黑体"):
            issues.append(f"1.1.1级标题字体不是黑体，检测为 {rpr}")
        if rpr.get("sizePt") != 12.0:
            issues.append(f"1.1.1级标题字号不是小四12pt，检测为 {rpr.get('sizePt')}pt")
        if not is_single_spacing(ppr):
            issues.append(f"1.1.1级标题不是单倍行距，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
        if ppr.get("beforePt") != 12.0 or ppr.get("afterPt") != 6.0:
            issues.append(f"1.1.1级标题段前/段后不是12/6磅，检测为 {ppr.get('beforePt')}/{ppr.get('afterPt')}")
        first = ppr.get("firstLineChars") or ppr.get("firstLineTwips")
        if first is None:
            issues.append("1.1.1级标题未检测到首行缩进2个汉字符")
        if not re.match(r"^\d+\.\d+\.\d+(?:\s|　)", text):
            issues.append("1.1.1级标题编号与标题之间不是空格分隔")
    return issues


def check_body_para(text: str, fmt: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ppr = fmt["pPr"]
    rpr = fmt["rPr"]
    if rpr.get("sizePt") != 12.0:
        issues.append(f"正文字号不是小四12pt，检测为 {rpr.get('sizePt')}pt")
    if not is_chinese_font_song(rpr):
        # This is intentionally strict because the requirement names east Asian font.
        issues.append(f"正文中文字体未明确为宋体，检测为 {rpr}")
    if not ascii_font_ok(rpr, "Times New Roman"):
        # Many Chinese paragraphs use only宋体; report as warning-like issue.
        issues.append(f"正文英文字体未明确为Times New Roman，检测为 {rpr}")
    if ppr.get("jc") != "both":
        issues.append(f"正文未设置两端对齐，jc={ppr.get('jc')}")
    if not is_exact_20(ppr):
        issues.append(f"正文行距不是固定值20磅，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
    if not is_zero_spacing(ppr):
        issues.append(f"正文段前/段后不是0/0磅，检测为 {ppr.get('beforePt')}/{ppr.get('afterPt')}")
    if ppr.get("firstLineChars") not in {"200", "220"} and ppr.get("firstLineTwips") is None:
        issues.append(f"正文未检测到首行缩进2个汉字符，firstLineChars={ppr.get('firstLineChars')}, firstLineTwips={ppr.get('firstLineTwips')}")
    return issues


def check_caption(kind: str, text: str, fmt: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ppr = fmt["pPr"]
    rpr = fmt["rPr"]
    if rpr.get("sizePt") != 10.5:
        issues.append(f"{kind}题字号不是五号10.5pt，检测为 {rpr.get('sizePt')}pt")
    if not is_chinese_font_song(rpr):
        issues.append(f"{kind}题中文字体未明确为宋体，检测为 {rpr}")
    if not ascii_font_ok(rpr, "Times New Roman"):
        issues.append(f"{kind}题英文字体未明确为Times New Roman，检测为 {rpr}")
    if ppr.get("jc") != "center":
        issues.append(f"{kind}题未居中，jc={ppr.get('jc')}")
    if not is_single_spacing(ppr):
        issues.append(f"{kind}题不是单倍行距，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
    expected_after = 12.0 if kind == "图" else 6.0
    if ppr.get("beforePt") != 6.0 or ppr.get("afterPt") != expected_after:
        issues.append(f"{kind}题段前/段后不是6/{expected_after:g}磅，检测为 {ppr.get('beforePt')}/{ppr.get('afterPt')}")
    if kind == "图" and not re.match(r"^图\s*\d+(?:[-.]\d+)?(?:续)?(?:\s|　)", text):
        issues.append("图序与图名之间未检测到空格")
    if kind == "表" and not re.match(r"^表\s*\d+(?:[-.]\d+)?(?:续)?(?:\s|　)", text):
        issues.append("表序与表名之间未检测到空格")
    return issues


def check_formula(text: str, p: etree._Element, fmt: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ppr = fmt["pPr"]
    rpr = fmt["rPr"]
    if p.find(".//m:oMath", NS) is None and p.find(".//m:oMathPara", NS) is None:
        issues.append("疑似公式编号段落未检测到OMML公式对象")
    if not FORMULA_NUM_RE.search(text):
        issues.append("公式未检测到括号编号，如（1）")
    if rpr.get("sizePt") not in {None, 10.5, 12.0}:
        issues.append(f"公式编号字号异常，检测为 {rpr.get('sizePt')}pt")
    if rpr.get("sizePt") == 12.0:
        issues.append("公式编号看起来为小四12pt，不是要求的五号10.5pt")
    if ppr.get("jc") == "both":
        issues.append("公式段落为两端对齐，建议另起一行并缩格/居中处理")
    return issues


def child_kind(child: etree._Element) -> str:
    if child.tag == W + "p":
        return "p"
    if child.tag == W + "tbl":
        return "tbl"
    if child.tag == W + "sectPr":
        return "sectPr"
    return child.tag


def table_paragraphs(tbl: etree._Element) -> list[etree._Element]:
    return tbl.xpath(".//w:p", namespaces=NS)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_body_fig_table_formula_readonly.py input.docx output.json")
    docx_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    document = load_xml(docx_path, "word/document.xml")
    styles_root = load_xml(docx_path, "word/styles.xml")
    styles = read_styles(styles_root)
    body = document.find("w:body", NS)
    children = list(body)

    items: list[dict[str, Any]] = []
    for idx, child in enumerate(children):
        kind = child_kind(child)
        if kind == "p":
            txt = text_of(child)
            fmt = para_effective_format(child, styles)
            items.append({
                "idx": idx,
                "kind": "p",
                "text": txt,
                "fmt": fmt,
                "hasDrawing": bool(child.xpath(".//w:drawing | .//w:pict", namespaces=NS)),
                "hasMath": bool(child.xpath(".//m:oMath | .//m:oMathPara", namespaces=NS)),
                "el": child,
            })
        elif kind == "tbl":
            items.append({"idx": idx, "kind": "tbl", "text": "", "el": child})
        else:
            items.append({"idx": idx, "kind": kind, "text": "", "el": child})

    # Define main text region: start at the real first body heading, not the TOC.
    # TOC entries contain PAGEREF/_Toc field codes, so exclude them explicitly.
    start_idx = None
    end_idx = None
    for it in items:
        if it["kind"] == "p" and start_idx is None:
            t = it["text"]
            ct = compact_text(t)
            is_toc_field = "PAGEREF" in t or "_Toc" in t or "\\h" in t
            looks_like_first_heading = (
                CHAPTER_RE.match(t) is not None
                or (not is_toc_field and re.match(r"^1(?:\s+|　+).{1,20}$", t) is not None)
                or ct in {"1绪论", "1绪論"}
            )
            if looks_like_first_heading and not is_toc_field:
                start_idx = it["idx"]
        if it["kind"] == "p" and compact_text(it["text"]) in {"参考文献", "致谢", "附录"}:
            if start_idx is not None and it["idx"] > start_idx:
                end_idx = it["idx"]
                break
    if start_idx is None:
        start_idx = 0
    if end_idx is None:
        end_idx = len(children)

    main_items = [it for it in items if start_idx <= it["idx"] < end_idx]

    headings: list[dict[str, Any]] = []
    heading_issues: list[dict[str, Any]] = []
    body_para_issues: list[dict[str, Any]] = []
    captions: list[dict[str, Any]] = []
    caption_issues: list[dict[str, Any]] = []
    formula_items: list[dict[str, Any]] = []
    formula_issues: list[dict[str, Any]] = []
    position_issues: list[dict[str, Any]] = []

    prev_num_by_level: dict[int, tuple[int, ...]] = {}
    seen_numbers: set[str] = set()

    for pos, it in enumerate(main_items):
        if it["kind"] != "p":
            continue
        text = it["text"]
        if not text:
            continue
        fmt = it["fmt"]
        h_kind = None
        level = None
        num_tuple = None
        if CHAPTER_RE.match(text):
            h_kind = "chapter"
            level = 1
        elif H4_RE.match(text):
            h_kind = "h4"
            level = 4
            num_tuple = tuple(map(int, H4_RE.match(text).group(1).split(".")))
        elif H3_RE.match(text):
            h_kind = "h3"
            level = 3
            num_tuple = tuple(map(int, H3_RE.match(text).group(1).split(".")))
        elif H2_RE.match(text):
            h_kind = "h2"
            level = 2
            num_tuple = (int(H2_RE.match(text).group(1)),)

        if h_kind:
            issues = check_heading(h_kind, text, fmt)
            if num_tuple:
                num_str = ".".join(map(str, num_tuple))
                if num_str in seen_numbers:
                    issues.append(f"标题编号重复：{num_str}")
                seen_numbers.add(num_str)
                prev = prev_num_by_level.get(level)
                if prev is not None and len(prev) == len(num_tuple):
                    expected = prev[:-1] + (prev[-1] + 1,)
                    # Only check strict continuity for siblings under same parent.
                    if prev[:-1] == num_tuple[:-1] and num_tuple != expected:
                        issues.append(f"同级标题编号可能不连续，上一项为 {'.'.join(map(str, prev))}")
                prev_num_by_level[level] = num_tuple
            headings.append({
                "idx": it["idx"],
                "level": level,
                "kind": h_kind,
                "text": text,
                "styleId": fmt.get("styleId"),
                "styleName": fmt.get("styleName"),
                "pPr": fmt["pPr"],
                "rPr": fmt["rPr"],
            })
            if issues:
                heading_issues.append({"idx": it["idx"], "text": text, "kind": h_kind, "issues": issues})
            continue

        if FIG_CAPTION_RE.match(text) or TABLE_CAPTION_RE.match(text):
            kind = "图" if FIG_CAPTION_RE.match(text) else "表"
            issues = check_caption(kind, text, fmt)
            captions.append({"idx": it["idx"], "kind": kind, "text": text, "pPr": fmt["pPr"], "rPr": fmt["rPr"]})
            if issues:
                caption_issues.append({"idx": it["idx"], "text": text, "kind": kind, "issues": issues})
            # Position check relative to neighboring body items.
            if kind == "图":
                prev_has_drawing = any(
                    mi.get("kind") == "p" and mi.get("hasDrawing")
                    for mi in main_items[max(0, pos - 3):pos]
                )
                if not prev_has_drawing:
                    position_issues.append({"idx": it["idx"], "text": text, "issue": "图题前3个主体元素内未检测到图片对象，需人工确认图题是否在图下方。"})
            else:
                next_is_table = any(mi.get("kind") == "tbl" for mi in main_items[pos + 1:pos + 4])
                if not next_is_table:
                    position_issues.append({"idx": it["idx"], "text": text, "issue": "表题后3个主体元素内未检测到表格对象，需人工确认表题是否在表上方。"})
            continue

        if it.get("hasMath") or FORMULA_NUM_RE.search(text):
            issues = check_formula(text, it["el"], fmt)
            formula_items.append({"idx": it["idx"], "text": text, "hasMath": it.get("hasMath"), "pPr": fmt["pPr"], "rPr": fmt["rPr"]})
            if issues:
                formula_issues.append({"idx": it["idx"], "text": text, "issues": issues})
            continue

        # Normal body paragraphs: skip very short blank-like lines and captions handled above.
        if len(text) >= 8 and not it.get("hasDrawing"):
            issues = check_body_para(text, fmt)
            if issues:
                body_para_issues.append({"idx": it["idx"], "text": text[:120], "issues": issues, "pPr": fmt["pPr"], "rPr": fmt["rPr"]})

    # Table internal text format: only sample because there can be many cells.
    table_text_issues: list[dict[str, Any]] = []
    table_count = 0
    for it in main_items:
        if it["kind"] != "tbl":
            continue
        table_count += 1
        for p in table_paragraphs(it["el"]):
            txt = text_of(p)
            if not txt:
                continue
            fmt = para_effective_format(p, styles)
            issues = []
            rpr = fmt["rPr"]
            ppr = fmt["pPr"]
            if rpr.get("sizePt") not in {10.5, 12.0}:
                issues.append(f"表格内文字字号异常，检测为 {rpr.get('sizePt')}pt")
            if not is_chinese_font_song(rpr):
                issues.append(f"表格内中文字体未明确为宋体，检测为 {rpr}")
            if not is_single_spacing(ppr) and not is_exact_20(ppr):
                issues.append(f"表格内行距异常，lineRule={ppr.get('lineRule')}, linePt={ppr.get('linePt')}")
            if issues:
                table_text_issues.append({"idx": it["idx"], "text": txt[:80], "issues": issues})
                if len(table_text_issues) >= 80:
                    break
        if len(table_text_issues) >= 80:
            break

    # Number order for figure/table captions.
    number_order_issues: list[dict[str, Any]] = []
    by_kind: dict[str, list[tuple[int, str, str]]] = {"图": [], "表": []}
    for c in captions:
        m = re.match(r"^[图表]\s*(\d+(?:[-.]\d+)?)(?:续)?", c["text"])
        if m:
            by_kind[c["kind"]].append((c["idx"], m.group(1), c["text"]))
    for kind, vals in by_kind.items():
        prev = None
        for idx, num, text in vals:
            if prev is not None:
                # Only flag duplicate exact non-continuation or decrease;章内编号 may skip if no figure/table in a section.
                def key(s: str) -> tuple[int, ...]:
                    return tuple(map(int, re.split(r"[-.]", s)))
                if key(num) < key(prev):
                    number_order_issues.append({"idx": idx, "kind": kind, "text": text, "issue": f"{kind}编号小于上一编号 {prev}"})
            prev = num

    issue_counter = Counter()
    for coll in (heading_issues, body_para_issues, caption_issues, formula_issues, position_issues, table_text_issues, number_order_issues):
        for row in coll:
            for issue in row.get("issues", [row.get("issue", "")]):
                issue_counter[issue] += 1

    report = {
        "docx": str(docx_path),
        "main_region": {"start_body_child_index": start_idx, "end_body_child_index": end_idx},
        "counts": {
            "headings": len(headings),
            "heading_issues": len(heading_issues),
            "body_para_issues": len(body_para_issues),
            "captions": len(captions),
            "caption_issues": len(caption_issues),
            "position_issues": len(position_issues),
            "formulas_or_numbered_formula_paras": len(formula_items),
            "formula_issues": len(formula_issues),
            "tables": table_count,
            "table_text_issue_sample_count": len(table_text_issues),
            "number_order_issues": len(number_order_issues),
        },
        "heading_outline": headings,
        "heading_issues": heading_issues,
        "body_para_issues_sample": body_para_issues[:80],
        "captions": captions,
        "caption_issues": caption_issues,
        "position_issues": position_issues,
        "formula_items": formula_items,
        "formula_issues": formula_issues,
        "table_text_issues_sample": table_text_issues,
        "number_order_issues": number_order_issues,
        "issue_summary": [{"count": c, "issue": k} for k, c in issue_counter.most_common(80)],
        "notes": [
            "本报告只读取docx XML，不修改文档。",
            "正文区域按真实第一个正文标题开始，到参考文献/致谢/附录之前结束；目录PAGEREF域已排除。",
            "图题位置通过图题前3个主体元素是否存在图片对象作辅助判断；复杂浮动图需人工复核。",
            "表题位置通过表题后3个主体元素是否存在表格对象作辅助判断。",
            "字体检查依赖XML中显式字体设置；若Word界面显示正确但XML缺少eastAsia字段，会被报告为需确认。",
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
