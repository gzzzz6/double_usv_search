from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def qn(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def twips_to_pt(value: str | None) -> float | None:
    return int(value) / 20.0 if value is not None else None


def half_points_to_pt(value: str | None) -> float | None:
    return int(value) / 2.0 if value is not None else None


def line_to_pt(value: str | None) -> float | None:
    return int(value) / 20.0 if value is not None else None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("tab"):
            parts.append("\t")
        elif elem.tag == qn("br"):
            parts.append("\n")
    return "".join(parts).strip()


def p_style_id(p: etree._Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return node.get(qn("val")) if node is not None else None


def attr(node: etree._Element | None, name: str) -> str | None:
    return node.get(qn(name)) if node is not None else None


def bool_prop(rpr: etree._Element | None, tag: str) -> bool | None:
    if rpr is None:
        return None
    node = rpr.find(f"./w:{tag}", namespaces=NS)
    if node is None:
        return None
    val = node.get(qn("val"))
    return val not in {"0", "false", "False"}


def font_dict(rpr: etree._Element | None) -> dict[str, str]:
    if rpr is None:
        return {}
    node = rpr.find("./w:rFonts", namespaces=NS)
    if node is None:
        return {}
    out = {}
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        val = node.get(qn(key))
        if val:
            out[key] = val
    return out


def read_styles(docx_path: Path) -> tuple[dict, dict]:
    with zipfile.ZipFile(docx_path) as zf:
        root = etree.fromstring(zf.read("word/styles.xml"))
    styles: dict[str, dict] = {}
    defaults: dict = {
        "line": None,
        "lineRule": None,
        "beforePt": None,
        "afterPt": None,
        "jc": None,
        "fonts": {},
        "sizePt": None,
        "bold": None,
    }
    doc_defaults = root.find("./w:docDefaults", namespaces=NS)
    if doc_defaults is not None:
        ppr = doc_defaults.find("./w:pPrDefault/w:pPr", namespaces=NS)
        if ppr is not None:
            spacing = ppr.find("./w:spacing", namespaces=NS)
            if spacing is not None:
                defaults["line"] = attr(spacing, "line")
                defaults["lineRule"] = attr(spacing, "lineRule")
                defaults["beforePt"] = twips_to_pt(attr(spacing, "before"))
                defaults["afterPt"] = twips_to_pt(attr(spacing, "after"))
        rpr = doc_defaults.find("./w:rPrDefault/w:rPr", namespaces=NS)
        if rpr is not None:
            sz = rpr.find("./w:sz", namespaces=NS)
            defaults["fonts"] = font_dict(rpr)
            defaults["sizePt"] = half_points_to_pt(attr(sz, "val"))
            defaults["bold"] = bool_prop(rpr, "b")

    for st in root.findall("./w:style", namespaces=NS):
        sid = st.get(qn("styleId"))
        if not sid:
            continue
        based_on = st.find("./w:basedOn", namespaces=NS)
        ppr = st.find("./w:pPr", namespaces=NS)
        rpr = st.find("./w:rPr", namespaces=NS)
        item = {
            "basedOn": attr(based_on, "val"),
            "line": None,
            "lineRule": None,
            "beforePt": None,
            "afterPt": None,
            "jc": None,
            "fonts": {},
            "sizePt": None,
            "bold": None,
        }
        if ppr is not None:
            spacing = ppr.find("./w:spacing", namespaces=NS)
            if spacing is not None:
                item["line"] = attr(spacing, "line")
                item["lineRule"] = attr(spacing, "lineRule")
                item["beforePt"] = twips_to_pt(attr(spacing, "before"))
                item["afterPt"] = twips_to_pt(attr(spacing, "after"))
            jc = ppr.find("./w:jc", namespaces=NS)
            item["jc"] = attr(jc, "val")
        if rpr is not None:
            sz = rpr.find("./w:sz", namespaces=NS)
            item["fonts"] = font_dict(rpr)
            item["sizePt"] = half_points_to_pt(attr(sz, "val"))
            item["bold"] = bool_prop(rpr, "b")
        styles[sid] = item
    return styles, defaults


def resolve_style(styles: dict, defaults: dict, sid: str | None, key: str):
    current = sid
    visited = set()
    while current and current not in visited:
        visited.add(current)
        item = styles.get(current, {})
        val = item.get(key)
        if key == "fonts":
            if val:
                return val
        elif val is not None:
            return val
        current = item.get("basedOn")
    return defaults.get(key)


def paragraph_format(p: etree._Element, styles: dict, defaults: dict) -> dict:
    sid = p_style_id(p)
    ppr = p.find("./w:pPr", namespaces=NS)
    direct = {}
    if ppr is not None:
        spacing = ppr.find("./w:spacing", namespaces=NS)
        if spacing is not None:
            direct["line"] = attr(spacing, "line")
            direct["lineRule"] = attr(spacing, "lineRule")
            direct["beforePt"] = twips_to_pt(attr(spacing, "before"))
            direct["afterPt"] = twips_to_pt(attr(spacing, "after"))
        jc = ppr.find("./w:jc", namespaces=NS)
        if jc is not None:
            direct["jc"] = attr(jc, "val")
    out = {"style": sid}
    for key in ("line", "lineRule", "beforePt", "afterPt", "jc"):
        out[key] = direct[key] if key in direct and direct[key] is not None else resolve_style(styles, defaults, sid, key)
    out["linePt"] = line_to_pt(out.get("line"))
    return out


def run_format(r: etree._Element, p_style: str | None, styles: dict, defaults: dict) -> dict:
    rpr = r.find("./w:rPr", namespaces=NS)
    sz = rpr.find("./w:sz", namespaces=NS) if rpr is not None else None
    fonts = font_dict(rpr)
    b = bool_prop(rpr, "b")
    return {
        "text": paragraph_text(r),
        "fonts": fonts if fonts else resolve_style(styles, defaults, p_style, "fonts"),
        "sizePt": half_points_to_pt(attr(sz, "val")) if sz is not None else resolve_style(styles, defaults, p_style, "sizePt"),
        "bold": b if b is not None else resolve_style(styles, defaults, p_style, "bold"),
    }


def paragraph_runs(p: etree._Element, styles: dict, defaults: dict) -> list[dict]:
    sid = p_style_id(p)
    return [run_format(r, sid, styles, defaults) for r in p.findall("./w:r", namespaces=NS)]


def load_document(docx_path: Path) -> etree._Element:
    with zipfile.ZipFile(docx_path) as zf:
        return etree.fromstring(zf.read("word/document.xml"))


def body_children(root: etree._Element) -> list[etree._Element]:
    body = root.find("./w:body", namespaces=NS)
    if body is None:
        raise RuntimeError("word/document.xml missing w:body")
    return list(body)


def iter_paragraphs_in_element(el: etree._Element) -> list[etree._Element]:
    if el.tag == qn("p"):
        return [el]
    return el.findall(".//w:p", namespaces=NS)


def find_body_child_index_by_compact(children: list[etree._Element], target: str) -> int:
    for idx, child in enumerate(children):
        if child.tag == qn("p") and compact_text(paragraph_text(child)) == target:
            return idx
    raise RuntimeError(f"未找到 {target}")


def title_spacing_check(text: str) -> dict:
    m = re.match(r"^附([ \u3000]*)录$", text)
    if not m:
        return {"matches_appendix_title_pattern": False, "space_chars": None, "fullwidth_spaces": None}
    spaces = m.group(1)
    return {
        "matches_appendix_title_pattern": True,
        "space_chars": len(spaces),
        "fullwidth_spaces": spaces.count("\u3000"),
        "ascii_spaces": spaces.count(" "),
        "raw_between": spaces,
    }


def caption_kind(text: str) -> str | None:
    c = compact_text(text)
    if re.match(r"^图\d+", c):
        return "figure"
    if re.match(r"^表\d+", c):
        return "table"
    if re.match(r"^(式)?[（(]\d+[）)]", c):
        return "formula"
    if re.match(r"^文献[\[［]\d+[\]］]", c):
        return "reference"
    return None


def appendix_numbering_issue(text: str, kind: str) -> str | None:
    c = compact_text(text)
    if kind == "figure":
        if re.match(r"^图\d+[-.．]\d+", c):
            return "附录图编号仍使用正文式章节编号，未另行编为图1、图2等。"
    if kind == "table":
        if re.match(r"^表\d+[-.．]\d+", c):
            return "附录表编号仍使用正文式章节编号，未另行编为表1、表2等。"
    if kind == "formula":
        # 附录公式允许式（1），此处只报告章节式编号。
        if re.match(r"^(式)?[（(]\d+[-.．]\d+[）)]", c):
            return "附录公式疑似仍使用正文式章节编号，未另行编为式（1）等。"
    return None


def content_format_issues(record: dict) -> list[str]:
    text = record["text"]
    if not text:
        return []
    issues = []
    fmt = record["format"]
    runs = record["runs"]
    first_run = next((r for r in runs if clean_text(r.get("text", ""))), runs[0] if runs else {})
    fonts = first_run.get("fonts", {})
    size = first_run.get("sizePt")
    if size != 10.5:
        issues.append(f"字号不是五号10.5pt，检测为 {size}pt。")
    if has_cjk(text):
        if fonts.get("eastAsia") != "宋体":
            issues.append(f"中文字体不是宋体，检测为 {fonts}。")
    else:
        if fonts.get("ascii") != "Times New Roman" and fonts.get("hAnsi") != "Times New Roman":
            issues.append(f"英文字体不是 Times New Roman，检测为 {fonts}。")
    if fmt.get("lineRule") != "exact" or fmt.get("linePt") != 20.0:
        issues.append(f"行距不是固定值20磅，lineRule={fmt.get('lineRule')}, linePt={fmt.get('linePt')}。")
    return issues


def main() -> int:
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\appendix_audit.json")
    )
    styles, defaults = read_styles(docx_path)
    root = load_document(docx_path)
    children = body_children(root)
    appendix_child_idx = find_body_child_index_by_compact(children, "附录")

    appendix_title = children[appendix_child_idx]
    title_info = {
        "body_child_index": appendix_child_idx,
        "text": paragraph_text(appendix_title),
        "compact": compact_text(paragraph_text(appendix_title)),
        "spacing_check": title_spacing_check(paragraph_text(appendix_title)),
        "format": paragraph_format(appendix_title, styles, defaults),
        "runs": paragraph_runs(appendix_title, styles, defaults),
    }

    appendix_records = []
    for child_idx in range(appendix_child_idx + 1, len(children)):
        child = children[child_idx]
        if child.tag == qn("sectPr"):
            continue
        container = "table" if child.tag == qn("tbl") else "body"
        for local_p_idx, p in enumerate(iter_paragraphs_in_element(child)):
            text = clean_text(paragraph_text(p))
            if not text:
                continue
            kind = caption_kind(text)
            record = {
                "body_child_index": child_idx,
                "container": container,
                "local_paragraph_index": local_p_idx,
                "text": text,
                "compact": compact_text(text),
                "style": p_style_id(p),
                "format": paragraph_format(p, styles, defaults),
                "runs": paragraph_runs(p, styles, defaults),
                "caption_kind": kind,
            }
            record["content_format_issues"] = content_format_issues(record)
            if kind:
                record["numbering_issue"] = appendix_numbering_issue(text, kind)
            appendix_records.append(record)

    caption_records = [r for r in appendix_records if r["caption_kind"]]
    numbering_issues = [
        {
            "body_child_index": r["body_child_index"],
            "text": r["text"],
            "caption_kind": r["caption_kind"],
            "issue": r.get("numbering_issue"),
        }
        for r in caption_records
        if r.get("numbering_issue")
    ]

    title_findings = []
    title_run = title_info["runs"][0] if title_info["runs"] else {}
    title_fonts = title_run.get("fonts", {})
    title_fmt = title_info["format"]
    spacing = title_info["spacing_check"]
    if not spacing.get("matches_appendix_title_pattern"):
        title_findings.append("附录标题不是“附  录”形式。")
    else:
        # 两个汉字间隙在 Word 中可能表现为 2 个全角空格或 4 个半角空格。
        if not (spacing.get("fullwidth_spaces") == 2 or spacing.get("ascii_spaces") == 4):
            title_findings.append(
                f"附录两字间距疑似不等于2个汉字间隙，检测到半角空格 {spacing.get('ascii_spaces')} 个、全角空格 {spacing.get('fullwidth_spaces')} 个。"
            )
    if title_fonts.get("eastAsia") != "黑体":
        title_findings.append(f"附录标题字体不是黑体，检测为 {title_fonts}。")
    if title_run.get("sizePt") != 16.0:
        title_findings.append(f"附录标题字号不是三号16pt，检测为 {title_run.get('sizePt')}pt。")
    if title_run.get("bold") is not True:
        title_findings.append("附录标题未检测为加粗。")
    if title_fmt.get("jc") != "center":
        title_findings.append("附录标题未检测为居中。")
    if title_fmt.get("lineRule") != "auto":
        title_findings.append(f"附录标题不是单倍行距，lineRule={title_fmt.get('lineRule')}。")
    if title_fmt.get("beforePt") != 24.0 or title_fmt.get("afterPt") != 18.0:
        title_findings.append(f"附录标题段前/段后不是24/18pt，检测为 {title_fmt.get('beforePt')}/{title_fmt.get('afterPt')}pt。")

    content_issues = [
        {
            "body_child_index": r["body_child_index"],
            "container": r["container"],
            "text": r["text"][:220],
            "issues": r["content_format_issues"],
        }
        for r in appendix_records
        if r["content_format_issues"]
    ]

    out = {
        "docx": str(docx_path),
        "appendix_title": title_info,
        "appendix_content_count": len(appendix_records),
        "caption_count": len(caption_records),
        "captions": [
            {
                "body_child_index": r["body_child_index"],
                "container": r["container"],
                "caption_kind": r["caption_kind"],
                "text": r["text"],
                "numbering_issue": r.get("numbering_issue"),
            }
            for r in caption_records
        ],
        "title_findings": title_findings,
        "numbering_issues": numbering_issues,
        "content_format_issue_count": len(content_issues),
        "content_format_issues_sample": content_issues[:120],
        "notes": [
            "本报告只读取docx XML，不修改文档。",
            "表格单元格内段落已纳入附录内容格式检查。",
            "附录标题两字间距按2个全角空格或4个半角空格视为可能符合。"
        ],
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
