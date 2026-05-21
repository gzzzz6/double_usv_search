from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def qn(tag: str) -> str:
    prefix, name = tag.split(":")
    return f"{{{NS[prefix]}}}{name}"


def twips_to_pt(value: str | None) -> float | None:
    if value is None:
        return None
    return int(value) / 20.0


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


def load_xml(docx_path: Path, part: str) -> ET.Element:
    with zipfile.ZipFile(docx_path) as zf:
        return ET.fromstring(zf.read(part))


def paragraph_text(p: ET.Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("w:t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("w:tab"):
            parts.append("\t")
        elif elem.tag == qn("w:br"):
            parts.append("\n")
    return "".join(parts)


def run_text(r: ET.Element) -> str:
    parts: list[str] = []
    for elem in r.iter():
        if elem.tag == qn("w:t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("w:tab"):
            parts.append("\t")
    return "".join(parts)


def p_style_id(p: ET.Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", NS)
    return node.get(qn("w:val")) if node is not None else None


def attr(node: ET.Element | None, name: str) -> str | None:
    return node.get(qn(name)) if node is not None else None


def bool_prop(rpr: ET.Element | None, tag: str) -> bool | None:
    if rpr is None:
        return None
    node = rpr.find(f"./w:{tag}", NS)
    if node is None:
        return None
    val = node.get(qn("w:val"))
    return val not in {"0", "false", "False"}


def font_dict(rpr: ET.Element | None) -> dict[str, str]:
    if rpr is None:
        return {}
    node = rpr.find("./w:rFonts", NS)
    if node is None:
        return {}
    out = {}
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        val = node.get(qn(f"w:{key}"))
        if val:
            out[key] = val
    return out


def read_styles(docx_path: Path) -> tuple[dict, dict, dict]:
    root = load_xml(docx_path, "word/styles.xml")
    styles: dict[str, dict] = {}
    defaults: dict = {
        "line": None,
        "lineRule": None,
        "beforePt": None,
        "afterPt": None,
        "jc": None,
        "ind": {},
        "tabs": [],
        "fonts": {},
        "sizePt": None,
        "bold": None,
    }
    default_style_by_type: dict[str, str] = {}

    doc_defaults = root.find("./w:docDefaults", NS)
    if doc_defaults is not None:
        ppr = doc_defaults.find("./w:pPrDefault/w:pPr", NS)
        if ppr is not None:
            spacing = ppr.find("./w:spacing", NS)
            if spacing is not None:
                defaults["line"] = attr(spacing, "w:line")
                defaults["lineRule"] = attr(spacing, "w:lineRule")
                defaults["beforePt"] = twips_to_pt(attr(spacing, "w:before"))
                defaults["afterPt"] = twips_to_pt(attr(spacing, "w:after"))
        rpr = doc_defaults.find("./w:rPrDefault/w:rPr", NS)
        if rpr is not None:
            sz = rpr.find("./w:sz", NS)
            defaults["sizePt"] = half_points_to_pt(attr(sz, "w:val"))
            defaults["fonts"] = font_dict(rpr)
            defaults["bold"] = bool_prop(rpr, "b")

    for st in root.findall("./w:style", NS):
        sid = st.get(qn("w:styleId"))
        if not sid:
            continue
        stype = st.get(qn("w:type"))
        if stype and st.get(qn("w:default")) == "1":
            default_style_by_type[stype] = sid
        based_on = st.find("./w:basedOn", NS)
        ppr = st.find("./w:pPr", NS)
        rpr = st.find("./w:rPr", NS)
        item = {
            "basedOn": attr(based_on, "w:val"),
            "line": None,
            "lineRule": None,
            "beforePt": None,
            "afterPt": None,
            "jc": None,
            "ind": {},
            "tabs": [],
            "fonts": {},
            "sizePt": None,
            "bold": None,
        }
        if ppr is not None:
            spacing = ppr.find("./w:spacing", NS)
            if spacing is not None:
                item["line"] = attr(spacing, "w:line")
                item["lineRule"] = attr(spacing, "w:lineRule")
                item["beforePt"] = twips_to_pt(attr(spacing, "w:before"))
                item["afterPt"] = twips_to_pt(attr(spacing, "w:after"))
            jc = ppr.find("./w:jc", NS)
            item["jc"] = attr(jc, "w:val")
            ind = ppr.find("./w:ind", NS)
            if ind is not None:
                item["ind"] = {
                    key: attr(ind, f"w:{key}")
                    for key in ("left", "right", "firstLine", "hanging", "firstLineChars", "hangingChars")
                    if attr(ind, f"w:{key}") is not None
                }
            tabs = []
            for tab in ppr.findall("./w:tabs/w:tab", NS):
                tabs.append(
                    {
                        "val": attr(tab, "w:val"),
                        "leader": attr(tab, "w:leader"),
                        "pos": attr(tab, "w:pos"),
                    }
                )
            item["tabs"] = tabs
        if rpr is not None:
            sz = rpr.find("./w:sz", NS)
            item["sizePt"] = half_points_to_pt(attr(sz, "w:val"))
            item["fonts"] = font_dict(rpr)
            item["bold"] = bool_prop(rpr, "b")
        styles[sid] = item
    return styles, defaults, default_style_by_type


def resolve(styles: dict, defaults: dict, default_style_by_type: dict, sid: str | None, key: str):
    current = sid or default_style_by_type.get("paragraph")
    visited = set()
    while current and current not in visited:
        visited.add(current)
        item = styles.get(current, {})
        val = item.get(key)
        if key in {"fonts", "ind", "tabs"}:
            if val:
                return val
        elif val is not None:
            return val
        current = item.get("basedOn")
    return defaults.get(key)


def direct_p_format(p: ET.Element) -> dict:
    ppr = p.find("./w:pPr", NS)
    out = {
        "line": None,
        "lineRule": None,
        "beforePt": None,
        "afterPt": None,
        "jc": None,
        "ind": {},
        "tabs": [],
    }
    if ppr is None:
        return out
    spacing = ppr.find("./w:spacing", NS)
    if spacing is not None:
        out["line"] = attr(spacing, "w:line")
        out["lineRule"] = attr(spacing, "w:lineRule")
        out["beforePt"] = twips_to_pt(attr(spacing, "w:before"))
        out["afterPt"] = twips_to_pt(attr(spacing, "w:after"))
    jc = ppr.find("./w:jc", NS)
    out["jc"] = attr(jc, "w:val")
    ind = ppr.find("./w:ind", NS)
    if ind is not None:
        out["ind"] = {
            key: attr(ind, f"w:{key}")
            for key in ("left", "right", "firstLine", "hanging", "firstLineChars", "hangingChars")
            if attr(ind, f"w:{key}") is not None
        }
    tabs = []
    for tab in ppr.findall("./w:tabs/w:tab", NS):
        tabs.append({"val": attr(tab, "w:val"), "leader": attr(tab, "w:leader"), "pos": attr(tab, "w:pos")})
    out["tabs"] = tabs
    return out


def effective_p_format(p: ET.Element, styles: dict, defaults: dict, default_style_by_type: dict) -> dict:
    sid = p_style_id(p)
    direct = direct_p_format(p)
    out = {"style": sid}
    for key in ("line", "lineRule", "beforePt", "afterPt", "jc", "ind", "tabs"):
        if key in {"ind", "tabs"}:
            out[key] = direct[key] if direct[key] else resolve(styles, defaults, default_style_by_type, sid, key)
        else:
            out[key] = direct[key] if direct[key] is not None else resolve(
                styles, defaults, default_style_by_type, sid, key
            )
    out["linePt"] = line_to_pt(out["line"]) if out.get("line") is not None else None
    return out


def direct_run_format(r: ET.Element) -> dict:
    rpr = r.find("./w:rPr", NS)
    sz = rpr.find("./w:sz", NS) if rpr is not None else None
    return {
        "fonts": font_dict(rpr),
        "sizePt": half_points_to_pt(attr(sz, "w:val")),
        "bold": bool_prop(rpr, "b"),
    }


def effective_run_format(
    r: ET.Element,
    p: ET.Element,
    styles: dict,
    defaults: dict,
    default_style_by_type: dict,
) -> dict:
    sid = p_style_id(p)
    direct = direct_run_format(r)
    return {
        "fonts": direct["fonts"] or resolve(styles, defaults, default_style_by_type, sid, "fonts") or {},
        "sizePt": direct["sizePt"]
        if direct["sizePt"] is not None
        else resolve(styles, defaults, default_style_by_type, sid, "sizePt"),
        "bold": direct["bold"]
        if direct["bold"] is not None
        else resolve(styles, defaults, default_style_by_type, sid, "bold"),
    }


def paragraph_record(index: int, p: ET.Element, styles: dict, defaults: dict, default_style_by_type: dict) -> dict:
    text = paragraph_text(p)
    runs = []
    for r in p.findall(".//w:r", NS):
        rt = run_text(r)
        if not clean_text(rt) and "\t" not in rt:
            continue
        fmt = effective_run_format(r, p, styles, defaults, default_style_by_type)
        runs.append({"text": rt, **fmt})
    return {
        "index": index,
        "style": p_style_id(p),
        "text": text,
        "cleanText": clean_text(text),
        "noSpaceLen": len(re.sub(r"\s+", "", text)),
        "pFormat": effective_p_format(p, styles, defaults, default_style_by_type),
        "runs": runs,
    }


def find_index(records: list[dict], pattern: str) -> int | None:
    for i, rec in enumerate(records):
        if rec["cleanText"] == pattern:
            return i
    return None


def find_contains(records: list[dict], pattern: str) -> int | None:
    for i, rec in enumerate(records):
        if pattern in rec["cleanText"]:
            return i
    return None


def nonempty_between(records: list[dict], start: int, end: int | None) -> list[dict]:
    upto = len(records) if end is None else end
    return [r for r in records[start:upto] if r["cleanText"]]


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?", text))


def split_keywords(text: str) -> list[str]:
    text = re.sub(r"^(关键词|Keywords|Key words)\s*[:：]\s*", "", text, flags=re.I)
    parts = re.split(r"[;；,，]\s*", text)
    return [p.strip() for p in parts if p.strip()]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: audit_docx_sections_readonly.py input.docx output.json", file=sys.stderr)
        return 2
    docx_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    doc_root = load_xml(docx_path, "word/document.xml")
    styles, defaults, default_style_by_type = read_styles(docx_path)
    paragraphs = doc_root.findall(".//w:body//w:p", NS)
    records = [paragraph_record(i, p, styles, defaults, default_style_by_type) for i, p in enumerate(paragraphs, 1)]
    nonempty = [r for r in records if r["cleanText"]]

    idx_cn_abs = find_index(records, "中文摘要")
    idx_abs = find_index(records, "Abstract")
    idx_kw_cn = find_contains(records, "关键词")
    idx_kw_en = find_contains(records, "Keywords")
    if idx_kw_en is None:
        idx_kw_en = find_contains(records, "Key words")
    idx_toc = find_contains(records, "目 录")
    idx_figtoc = find_contains(records, "图目录")
    if idx_figtoc is None:
        idx_figtoc = find_contains(records, "图 目 录")
    idx_tabtoc = find_contains(records, "表目录")
    if idx_tabtoc is None:
        idx_tabtoc = find_contains(records, "表 目 录")

    cn_body = []
    if idx_cn_abs is not None and idx_kw_cn is not None:
        cn_body = nonempty_between(records, idx_cn_abs + 1, idx_kw_cn)
    en_body = []
    if idx_abs is not None and idx_kw_en is not None:
        en_body = nonempty_between(records, idx_abs + 1, idx_kw_en)

    toc_entries = []
    if idx_toc is not None:
        for r in records[idx_toc + 1 :]:
            if not r["cleanText"]:
                continue
            if r["cleanText"] in {"图目录", "图 目 录", "表目录", "表 目 录"}:
                break
            if str(r["style"] or "").upper().startswith("TOC"):
                toc_entries.append(r)
            elif toc_entries:
                break

    fig_entries = []
    if idx_figtoc is not None:
        end = idx_tabtoc if idx_tabtoc is not None and idx_tabtoc > idx_figtoc else None
        for r in records[idx_figtoc + 1 : end]:
            if r["cleanText"]:
                fig_entries.append(r)
    tab_entries = []
    if idx_tabtoc is not None:
        end = None
        for j, r in enumerate(records[idx_tabtoc + 1 :], start=idx_tabtoc + 1):
            if re.match(r"^第\s*\d+\s*章|^\d+\s+", r["cleanText"]):
                end = j
                break
        for r in records[idx_tabtoc + 1 : end]:
            if r["cleanText"]:
                tab_entries.append(r)

    body_fig_captions = [
        r for r in nonempty if re.match(r"^图\s*\d", r["cleanText"]) and r not in fig_entries
    ]
    body_tab_captions = [
        r for r in nonempty if re.match(r"^表\s*\d", r["cleanText"]) and r not in tab_entries
    ]

    result = {
        "docx": str(docx_path),
        "markers": {
            "中文摘要": records[idx_cn_abs] if idx_cn_abs is not None else None,
            "Abstract": records[idx_abs] if idx_abs is not None else None,
            "关键词": records[idx_kw_cn] if idx_kw_cn is not None else None,
            "Keywords_or_Key_words": records[idx_kw_en] if idx_kw_en is not None else None,
            "目录": records[idx_toc] if idx_toc is not None else None,
            "图目录": records[idx_figtoc] if idx_figtoc is not None else None,
            "表目录": records[idx_tabtoc] if idx_tabtoc is not None else None,
        },
        "abstracts": {
            "cn_body_paragraphs": cn_body,
            "cn_char_count_no_space": sum(r["noSpaceLen"] for r in cn_body),
            "en_body_paragraphs": en_body,
            "en_word_count": word_count(" ".join(r["cleanText"] for r in en_body)),
        },
        "keywords": {
            "cn": split_keywords(records[idx_kw_cn]["cleanText"]) if idx_kw_cn is not None else [],
            "en": split_keywords(records[idx_kw_en]["cleanText"]) if idx_kw_en is not None else [],
        },
        "toc": {
            "entries_count": len(toc_entries),
            "styles": sorted(set(str(r["style"]) for r in toc_entries)),
            "entries_sample": toc_entries[:80],
            "entries_level_gt3": [
                r for r in toc_entries if re.match(r"TOC[4-9]", str(r["style"] or ""), flags=re.I)
            ],
        },
        "figure_table_toc": {
            "fig_entries_count": len(fig_entries),
            "tab_entries_count": len(tab_entries),
            "fig_entries_sample": fig_entries[:80],
            "tab_entries_sample": tab_entries[:80],
            "body_fig_caption_count": len(body_fig_captions),
            "body_tab_caption_count": len(body_tab_captions),
            "body_fig_caption_sample": body_fig_captions[:80],
            "body_tab_caption_sample": body_tab_captions[:80],
        },
        "first_nonempty": nonempty[:80],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
