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


def run_direct_format(r: etree._Element, p_style: str | None, styles: dict, defaults: dict) -> dict:
    rpr = r.find("./w:rPr", namespaces=NS)
    sz = rpr.find("./w:sz", namespaces=NS) if rpr is not None else None
    fonts = font_dict(rpr)
    return {
        "text": paragraph_text(r),
        "fonts": fonts if fonts else resolve_style(styles, defaults, p_style, "fonts"),
        "sizePt": half_points_to_pt(attr(sz, "val")) if sz is not None else resolve_style(styles, defaults, p_style, "sizePt"),
        "bold": bool_prop(rpr, "b") if bool_prop(rpr, "b") is not None else resolve_style(styles, defaults, p_style, "bold"),
    }


def paragraph_runs(p: etree._Element, styles: dict, defaults: dict) -> list[dict]:
    sid = p_style_id(p)
    return [run_direct_format(r, sid, styles, defaults) for r in p.findall("./w:r", namespaces=NS)]


def load_paragraphs(docx_path: Path) -> list[etree._Element]:
    with zipfile.ZipFile(docx_path) as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    return root.findall(".//w:body/w:p", namespaces=NS)


def find_reference_region(paragraphs: list[etree._Element]) -> tuple[int, int]:
    ref_idx = None
    end_idx = len(paragraphs)
    for idx, p in enumerate(paragraphs):
        if compact_text(paragraph_text(p)) == "参考文献":
            ref_idx = idx
            break
    if ref_idx is None:
        raise RuntimeError("未找到参考文献标题")
    for idx in range(ref_idx + 1, len(paragraphs)):
        c = compact_text(paragraph_text(paragraphs[idx]))
        if c in {"致谢", "附录", "参考书目"}:
            end_idx = idx
            break
    return ref_idx, end_idx


def extract_ref_number(text: str) -> int | None:
    m = re.match(r"^[\[\［]\s*(\d+)\s*[\]\］]", text)
    if m:
        return int(m.group(1))
    return None


def reference_item_checks(text: str) -> dict:
    number = extract_ref_number(text)
    bracket_ok = number is not None
    gap_ok = bool(re.match(r"^[\[\［]\s*\d+\s*[\]\］]\s+", text))
    ends_period = text.endswith(".") or text.endswith("．")
    has_type = bool(re.search(r"[\[\［][A-Z]{1,4}(?:/[A-Z]{1,4})?[\]\］]", text))
    comma_cn = "，" in text
    semicolon_cn = "；" in text
    has_interval_dot = "." in text or "．" in text
    authors_prefix = re.split(r"[.．]", text, maxsplit=1)[0]
    author_count_hint = len(re.split(r"\s*,\s*|，", authors_prefix))
    too_many_authors_without_et_al = author_count_hint > 4 and not re.search(r"\b(et al\.?|等)\b", authors_prefix, re.I)
    return {
        "number": number,
        "bracket_number_ok": bracket_ok,
        "gap_after_number_ok": gap_ok,
        "ends_with_period": ends_period,
        "has_literature_type": has_type,
        "has_interval_dot": has_interval_dot,
        "contains_chinese_comma": comma_cn,
        "contains_chinese_semicolon": semicolon_cn,
        "author_count_hint": author_count_hint,
        "too_many_authors_without_et_al_or_deng": too_many_authors_without_et_al,
    }


def extract_citation_numbers(text: str) -> list[int]:
    nums: list[int] = []
    for match in re.finditer(r"[\[\［]([0-9,\-－—~～\s]+)[\]\］]", text):
        raw = match.group(1)
        parts = re.split(r"[,，\s]+", raw)
        for part in parts:
            if not part:
                continue
            range_match = re.match(r"^(\d+)\s*[-－—~～]\s*(\d+)$", part)
            if range_match:
                a, b = int(range_match.group(1)), int(range_match.group(2))
                if a <= b:
                    nums.extend(range(a, b + 1))
                else:
                    nums.extend(range(b, a + 1))
            elif part.isdigit():
                nums.append(int(part))
    return nums


def main() -> int:
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\references_audit.json")
    )
    styles, defaults = read_styles(docx_path)
    paragraphs = load_paragraphs(docx_path)
    ref_idx, ref_end = find_reference_region(paragraphs)

    title_p = paragraphs[ref_idx]
    title_info = {
        "index": ref_idx,
        "text": paragraph_text(title_p),
        "format": paragraph_format(title_p, styles, defaults),
        "runs": paragraph_runs(title_p, styles, defaults),
    }

    ref_items = []
    for idx in range(ref_idx + 1, ref_end):
        text = clean_text(paragraph_text(paragraphs[idx]))
        if not text:
            continue
        p_format = paragraph_format(paragraphs[idx], styles, defaults)
        runs = paragraph_runs(paragraphs[idx], styles, defaults)
        language = "zh" if has_cjk(text) else "en"
        ref_items.append(
            {
                "index": idx,
                "text": text,
                "language_guess": language,
                "format": p_format,
                "runs": runs,
                "checks": reference_item_checks(text),
            }
        )

    ref_numbers = [item["checks"]["number"] for item in ref_items]
    numbered_refs = [n for n in ref_numbers if n is not None]
    expected_numbers = list(range(1, len(ref_items) + 1))
    numbering_summary = {
        "item_count": len(ref_items),
        "numbered_count": len(numbered_refs),
        "numbers": ref_numbers,
        "expected_numbers": expected_numbers,
        "continuous_from_1": numbered_refs == expected_numbers,
        "missing_bracket_number_count": sum(1 for n in ref_numbers if n is None),
    }

    # Scan正文、图题、表题至参考文献标题前。目录区也会含数字方括号风险较低；这里记录首次出现位置，后续人工可结合上下文判断。
    cited_sequence: list[int] = []
    citation_occurrences: list[dict] = []
    for idx in range(0, ref_idx):
        text = paragraph_text(paragraphs[idx])
        nums = extract_citation_numbers(text)
        if not nums:
            continue
        for n in nums:
            cited_sequence.append(n)
            citation_occurrences.append({"paragraph_index": idx, "number": n, "context": clean_text(text)[:240]})

    first_order: list[int] = []
    seen = set()
    for n in cited_sequence:
        if n not in seen:
            seen.add(n)
            first_order.append(n)
    citation_summary = {
        "occurrence_count": len(citation_occurrences),
        "unique_cited_numbers_in_first_appearance_order": first_order,
        "unique_cited_count": len(first_order),
        "cited_set_sorted": sorted(seen),
        "citation_occurrences_sample": citation_occurrences[:80],
        "first_appearance_matches_1_to_n": first_order == list(range(1, len(first_order) + 1)),
        "uncited_reference_numbers": [n for n in numbered_refs if n not in seen],
        "cited_numbers_without_reference": [n for n in sorted(seen) if n not in numbered_refs],
    }

    format_findings = []
    tf = title_info["format"]
    title_run = title_info["runs"][0] if title_info["runs"] else {}
    title_fonts = title_run.get("fonts", {})
    if title_fonts.get("eastAsia") != "黑体":
        format_findings.append("参考文献标题字体不是黑体或未检测到黑体。")
    if title_run.get("sizePt") != 16.0:
        format_findings.append(f"参考文献标题字号不是三号16pt，检测为 {title_run.get('sizePt')}pt。")
    if title_run.get("bold") is not True:
        format_findings.append("参考文献标题未检测为加粗。")
    if tf.get("jc") != "center":
        format_findings.append("参考文献标题未检测为居中。")
    if tf.get("lineRule") != "auto":
        format_findings.append(f"参考文献标题不是单倍行距，lineRule={tf.get('lineRule')}。")
    if tf.get("beforePt") != 24.0 or tf.get("afterPt") != 18.0:
        format_findings.append(f"参考文献标题段前/段后不是24/18pt，检测为 {tf.get('beforePt')}/{tf.get('afterPt')}pt。")

    item_findings = []
    for item in ref_items:
        text = item["text"]
        checks = item["checks"]
        if not checks["bracket_number_ok"]:
            item_findings.append({"index": item["index"], "issue": "未按［序号］或[序号]开头", "text": text})
        if checks["bracket_number_ok"] and not checks["gap_after_number_ok"]:
            item_findings.append({"index": item["index"], "issue": "序号后未检测到空1个字符间隙", "text": text})
        if not checks["ends_with_period"]:
            item_findings.append({"index": item["index"], "issue": "文献末尾未以句点结束", "text": text})
        if not checks["has_literature_type"]:
            item_findings.append({"index": item["index"], "issue": "未检测到文献类型标识如[J]/[M]/[C]/[EB/OL]", "text": text})
        if checks["too_many_authors_without_et_al_or_deng"]:
            item_findings.append({"index": item["index"], "issue": "作者数疑似超过三位但未使用等/et al.", "text": text})

        p_format = item["format"]
        runs = item["runs"]
        first_run = next((r for r in runs if clean_text(r.get("text", ""))), runs[0] if runs else {})
        fonts = first_run.get("fonts", {})
        size = first_run.get("sizePt")
        if size != 10.5:
            item_findings.append({"index": item["index"], "issue": f"参考文献字号不是五号10.5pt，检测为 {size}pt", "text": text})
        if p_format.get("lineRule") != "exact" or p_format.get("linePt") != 16.0:
            item_findings.append(
                {
                    "index": item["index"],
                    "issue": f"行间距不是固定值16磅，lineRule={p_format.get('lineRule')}, linePt={p_format.get('linePt')}",
                    "text": text,
                }
            )
        if item["language_guess"] == "zh":
            if fonts.get("eastAsia") != "宋体":
                item_findings.append({"index": item["index"], "issue": f"中文文献字体不是宋体，检测为 {fonts}", "text": text})
        else:
            if fonts.get("ascii") != "Times New Roman" and fonts.get("hAnsi") != "Times New Roman":
                item_findings.append({"index": item["index"], "issue": f"英文文献字体不是Times New Roman，检测为 {fonts}", "text": text})

    out = {
        "docx": str(docx_path),
        "reference_region": {"title_index": ref_idx, "end_index": ref_end},
        "title": title_info,
        "references": ref_items,
        "numbering_summary": numbering_summary,
        "citation_summary": citation_summary,
        "format_findings": format_findings,
        "item_findings": item_findings,
        "notes": [
            "本报告只读取docx XML，不修改文档。",
            "英文题名大小写、标点全角/半角和作者三位以上规则只能由脚本初筛，最终仍需人工确认。",
        ],
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
