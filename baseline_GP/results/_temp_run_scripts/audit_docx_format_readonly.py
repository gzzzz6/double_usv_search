from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def qn(tag: str) -> str:
    prefix, name = tag.split(":")
    return f"{{{NS[prefix]}}}{name}"


def twips_to_cm(value: str | None) -> float | None:
    if value is None:
        return None
    return int(value) / 1440.0 * 2.54


def half_points_to_pt(value: str | None) -> float | None:
    if value is None:
        return None
    return int(value) / 2.0


def line_to_pt(value: str | None) -> float | None:
    if value is None:
        return None
    return int(value) / 20.0


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def get_text(elem: ET.Element) -> str:
    parts: list[str] = []
    for node in elem.iter(qn("w:t")):
        parts.append(node.text or "")
    return "".join(parts)


def p_style_id(p: ET.Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", NS)
    return node.get(qn("w:val")) if node is not None else None


def p_direct_spacing(p: ET.Element) -> tuple[str | None, str | None]:
    node = p.find("./w:pPr/w:spacing", NS)
    if node is None:
        return None, None
    return node.get(qn("w:line")), node.get(qn("w:lineRule"))


def run_font_size_pt(r: ET.Element) -> float | None:
    node = r.find("./w:rPr/w:sz", NS)
    return half_points_to_pt(node.get(qn("w:val"))) if node is not None else None


def run_fonts(r: ET.Element) -> dict[str, str]:
    node = r.find("./w:rPr/w:rFonts", NS)
    if node is None:
        return {}
    out = {}
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        val = node.get(qn(f"w:{key}"))
        if val:
            out[key] = val
    return out


def load_xml_from_docx(docx_path: Path, part: str) -> ET.Element:
    with zipfile.ZipFile(docx_path) as zf:
        data = zf.read(part)
    return ET.fromstring(data)


def load_style_maps(docx_path: Path) -> tuple[dict, dict, dict]:
    root = load_xml_from_docx(docx_path, "word/styles.xml")
    styles: dict[str, dict] = {}
    defaults: dict = {}

    doc_defaults = root.find("./w:docDefaults", NS)
    if doc_defaults is not None:
        p_spacing = doc_defaults.find("./w:pPrDefault/w:pPr/w:spacing", NS)
        rpr = doc_defaults.find("./w:rPrDefault/w:rPr", NS)
        defaults["line"] = p_spacing.get(qn("w:line")) if p_spacing is not None else None
        defaults["lineRule"] = p_spacing.get(qn("w:lineRule")) if p_spacing is not None else None
        defaults["size"] = None
        defaults["fonts"] = {}
        if rpr is not None:
            sz = rpr.find("./w:sz", NS)
            defaults["size"] = half_points_to_pt(sz.get(qn("w:val"))) if sz is not None else None
            fonts = rpr.find("./w:rFonts", NS)
            if fonts is not None:
                defaults["fonts"] = {
                    key: fonts.get(qn(f"w:{key}"))
                    for key in ("ascii", "hAnsi", "eastAsia", "cs")
                    if fonts.get(qn(f"w:{key}"))
                }

    default_style_by_type: dict[str, str] = {}
    for style in root.findall("./w:style", NS):
        sid = style.get(qn("w:styleId"))
        stype = style.get(qn("w:type"))
        if not sid:
            continue
        if style.get(qn("w:default")) == "1" and stype:
            default_style_by_type[stype] = sid
        based_on = style.find("./w:basedOn", NS)
        spacing = style.find("./w:pPr/w:spacing", NS)
        rpr = style.find("./w:rPr", NS)
        fonts: dict[str, str] = {}
        size = None
        if rpr is not None:
            sz = rpr.find("./w:sz", NS)
            size = half_points_to_pt(sz.get(qn("w:val"))) if sz is not None else None
            fnode = rpr.find("./w:rFonts", NS)
            if fnode is not None:
                fonts = {
                    key: fnode.get(qn(f"w:{key}"))
                    for key in ("ascii", "hAnsi", "eastAsia", "cs")
                    if fnode.get(qn(f"w:{key}"))
                }
        styles[sid] = {
            "basedOn": based_on.get(qn("w:val")) if based_on is not None else None,
            "line": spacing.get(qn("w:line")) if spacing is not None else None,
            "lineRule": spacing.get(qn("w:lineRule")) if spacing is not None else None,
            "size": size,
            "fonts": fonts,
        }
    return styles, defaults, default_style_by_type


def resolve_style_value(
    styles: dict,
    defaults: dict,
    style_id: str | None,
    key: str,
    default_style_by_type: dict,
) -> object:
    current = style_id or default_style_by_type.get("paragraph")
    visited = set()
    while current and current not in visited:
        visited.add(current)
        entry = styles.get(current, {})
        val = entry.get(key)
        if key == "fonts":
            if val:
                return val
        elif val is not None:
            return val
        current = entry.get("basedOn")
    return defaults.get(key)


def effective_spacing(p: ET.Element, styles: dict, defaults: dict, default_style_by_type: dict) -> dict:
    direct_line, direct_rule = p_direct_spacing(p)
    sid = p_style_id(p)
    line = direct_line if direct_line is not None else resolve_style_value(
        styles, defaults, sid, "line", default_style_by_type
    )
    rule = direct_rule if direct_rule is not None else resolve_style_value(
        styles, defaults, sid, "lineRule", default_style_by_type
    )
    return {
        "style": sid,
        "line": line,
        "lineRule": rule,
        "linePt": line_to_pt(line) if line is not None else None,
        "source": "direct" if direct_line is not None or direct_rule is not None else "style/default",
    }


def effective_run_format(
    r: ET.Element,
    p: ET.Element,
    styles: dict,
    defaults: dict,
    default_style_by_type: dict,
) -> dict:
    sid = p_style_id(p)
    size = run_font_size_pt(r)
    fonts = run_fonts(r)
    if size is None:
        size = resolve_style_value(styles, defaults, sid, "size", default_style_by_type)
    if not fonts:
        fonts = resolve_style_value(styles, defaults, sid, "fonts", default_style_by_type) or {}
    return {
        "sizePt": size,
        "fonts": fonts,
    }


def audit(docx_path: Path) -> dict:
    doc_root = load_xml_from_docx(docx_path, "word/document.xml")
    styles, defaults, default_style_by_type = load_style_maps(docx_path)

    sects = doc_root.findall(".//w:sectPr", NS)
    sections = []
    for idx, sect in enumerate(sects, start=1):
        mar = sect.find("./w:pgMar", NS)
        item = {"index": idx}
        if mar is not None:
            for key in ("top", "bottom", "left", "right", "header", "footer"):
                raw = mar.get(qn(f"w:{key}"))
                item[key] = {
                    "twips": int(raw) if raw is not None else None,
                    "cm": round(twips_to_cm(raw), 3) if raw is not None else None,
                }
        sections.append(item)

    body = doc_root.find("./w:body", NS)
    paragraphs = body.findall(".//w:p", NS) if body is not None else []
    line_counter = Counter()
    bad_line_examples = []
    nonempty_count = 0
    for idx, p in enumerate(paragraphs, start=1):
        text = clean_text(get_text(p))
        if not text:
            continue
        nonempty_count += 1
        sp = effective_spacing(p, styles, defaults, default_style_by_type)
        key = (sp["line"], sp["lineRule"], sp["linePt"])
        line_counter[key] += 1
        ok = sp["line"] == "400" and sp["lineRule"] == "exact"
        if not ok and len(bad_line_examples) < 80:
            bad_line_examples.append(
                {
                    "paragraph_index": idx,
                    "style": sp["style"],
                    "line": sp["line"],
                    "lineRule": sp["lineRule"],
                    "linePt": sp["linePt"],
                    "source": sp["source"],
                    "text": text[:120],
                }
            )

    first_nonempty = []
    for idx, p in enumerate(paragraphs, start=1):
        text = clean_text(get_text(p))
        if not text:
            continue
        runs = []
        for r in p.findall("./w:r", NS):
            rtext = clean_text(get_text(r))
            if not rtext:
                continue
            fmt = effective_run_format(r, p, styles, defaults, default_style_by_type)
            runs.append(
                {
                    "text": rtext[:80],
                    "fonts": fmt["fonts"],
                    "sizePt": fmt["sizePt"],
                }
            )
        sp = effective_spacing(p, styles, defaults, default_style_by_type)
        first_nonempty.append(
            {
                "paragraph_index": idx,
                "style": p_style_id(p),
                "text": text[:200],
                "char_count_no_space": len(re.sub(r"\s+", "", text)),
                "spacing": sp,
                "runs": runs[:10],
            }
        )
        if len(first_nonempty) >= 45:
            break

    return {
        "docx_path": str(docx_path),
        "sections": sections,
        "paragraph_count": len(paragraphs),
        "nonempty_paragraph_count": nonempty_count,
        "line_spacing_distribution": [
            {
                "line": k[0],
                "lineRule": k[1],
                "linePt": k[2],
                "count": v,
            }
            for k, v in line_counter.most_common()
        ],
        "bad_line_examples": bad_line_examples,
        "first_nonempty_paragraphs": first_nonempty,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: audit_docx_format_readonly.py input.docx output.json", file=sys.stderr)
        return 2
    docx_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    result = audit(docx_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
