from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W_NS, "r": R_NS, "rel": REL_NS}


def qn(ns_name: str) -> str:
    prefix, name = ns_name.split(":")
    ns = {"w": W_NS, "r": R_NS, "rel": REL_NS}[prefix]
    return f"{{{ns}}}{name}"


def local(tag: str) -> str:
    return etree.QName(tag).localname


def text_of(el: etree._Element | None) -> str:
    if el is None:
        return ""
    parts: list[str] = []
    for e in el.iter():
        if e.tag == qn("w:t"):
            parts.append(e.text or "")
        elif e.tag == qn("w:tab"):
            parts.append("\t")
        elif e.tag == qn("w:br"):
            parts.append("\n")
        elif e.tag == qn("w:fldChar"):
            fld = e.get(qn("w:fldCharType"))
            if fld:
                parts.append(f"<fldChar:{fld}>")
        elif e.tag == qn("w:instrText"):
            parts.append(f"<instr:{e.text or ''}>")
    return "".join(parts).strip()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for e in p.iter():
        if e.tag == qn("w:t"):
            parts.append(e.text or "")
        elif e.tag == qn("w:tab"):
            parts.append("\t")
        elif e.tag == qn("w:br"):
            parts.append("\n")
    return "".join(parts).strip()


def style_id(p: etree._Element) -> str | None:
    n = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return n.get(qn("w:val")) if n is not None else None


def font_dict(rpr: etree._Element | None) -> dict[str, str]:
    if rpr is None:
        return {}
    node = rpr.find("./w:rFonts", namespaces=NS)
    if node is None:
        return {}
    out: dict[str, str] = {}
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        val = node.get(qn(f"w:{key}"))
        if val:
            out[key] = val
    return out


def run_summary(r: etree._Element) -> dict:
    rpr = r.find("./w:rPr", namespaces=NS)
    sz = rpr.find("./w:sz", namespaces=NS) if rpr is not None else None
    b = rpr.find("./w:b", namespaces=NS) if rpr is not None else None
    return {
        "text": text_of(r),
        "fonts": font_dict(rpr),
        "sizePt": int(sz.get(qn("w:val"))) / 2 if sz is not None and sz.get(qn("w:val")) else None,
        "bold": None if b is None else b.get(qn("w:val"), "1"),
    }


def paragraph_summary(p: etree._Element) -> dict:
    ppr = p.find("./w:pPr", namespaces=NS)
    jc = ppr.find("./w:jc", namespaces=NS) if ppr is not None else None
    p_bdr = ppr.find("./w:pBdr/w:bottom", namespaces=NS) if ppr is not None else None
    tabs = []
    if ppr is not None:
        for tab in ppr.findall("./w:tabs/w:tab", namespaces=NS):
            tabs.append(
                {
                    "val": tab.get(qn("w:val")),
                    "leader": tab.get(qn("w:leader")),
                    "pos": tab.get(qn("w:pos")),
                }
            )
    return {
        "style": style_id(p),
        "text": text_of(p),
        "jc": jc.get(qn("w:val")) if jc is not None else None,
        "bottomBorder": {
            "val": p_bdr.get(qn("w:val")),
            "sz": p_bdr.get(qn("w:sz")),
            "space": p_bdr.get(qn("w:space")),
            "color": p_bdr.get(qn("w:color")),
        }
        if p_bdr is not None
        else None,
        "tabs": tabs,
        "runs": [run_summary(r) for r in p.findall("./w:r", namespaces=NS)],
    }


def load_xml(zf: zipfile.ZipFile, name: str) -> etree._Element | None:
    try:
        return etree.fromstring(zf.read(name))
    except KeyError:
        return None


def rels_map(zf: zipfile.ZipFile) -> dict[str, str]:
    root = load_xml(zf, "word/_rels/document.xml.rels")
    if root is None:
        return {}
    out: dict[str, str] = {}
    for rel in root.findall("./rel:Relationship", namespaces=NS):
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            out[rid] = target if target.startswith("word/") else f"word/{target}"
    return out


def section_refs(sect_pr: etree._Element) -> dict:
    headers = []
    footers = []
    for ref in sect_pr.findall("./w:headerReference", namespaces=NS):
        headers.append({"type": ref.get(qn("w:type")), "rId": ref.get(qn("r:id"))})
    for ref in sect_pr.findall("./w:footerReference", namespaces=NS):
        footers.append({"type": ref.get(qn("w:type")), "rId": ref.get(qn("r:id"))})
    pg_num = sect_pr.find("./w:pgNumType", namespaces=NS)
    title_pg = sect_pr.find("./w:titlePg", namespaces=NS)
    return {
        "headers": headers,
        "footers": footers,
        "pgNumType": {
            "fmt": pg_num.get(qn("w:fmt")),
            "start": pg_num.get(qn("w:start")),
        }
        if pg_num is not None
        else None,
        "titlePg": title_pg is not None,
    }


def main() -> int:
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\header_footer_pagenum_audit.json")
    )
    with zipfile.ZipFile(docx_path, "r") as zf:
        document = etree.fromstring(zf.read("word/document.xml"))
        rels = rels_map(zf)
        paragraphs = document.findall(".//w:body/w:p", namespaces=NS)

        parts: dict[str, dict] = {}
        for rid, part in sorted(rels.items()):
            if "/header" in part or "/footer" in part:
                root = load_xml(zf, part)
                if root is None:
                    continue
                paras = root.findall("./w:p", namespaces=NS)
                parts[part] = {
                    "text": text_of(root),
                    "paragraphs": [paragraph_summary(p) for p in paras],
                }

    markers: dict[str, int] = {}
    for idx, p in enumerate(paragraphs):
        compact = re.sub(r"\s+", "", paragraph_text(p))
        for key in ("中文摘要", "Abstract", "目录", "图目录", "表目录", "1绪论", "6总结与展望", "参考文献", "附录", "致谢"):
            if key not in markers and compact.startswith(key):
                markers[key] = idx

    sections = []
    section_start = 0
    section_idx = 1
    for idx, p in enumerate(paragraphs):
        sect_pr = p.find("./w:pPr/w:sectPr", namespaces=NS)
        if sect_pr is None:
            continue
        end_text = paragraph_text(p)
        sections.append(
            {
                "section": section_idx,
                "startParagraph": section_start,
                "endParagraph": idx,
                "endText": end_text[:120],
                **section_refs(sect_pr),
            }
        )
        section_idx += 1
        section_start = idx + 1
    body = document.find(".//w:body", namespaces=NS)
    final_sect = body.find("./w:sectPr", namespaces=NS) if body is not None else None
    if final_sect is not None:
        sections.append(
            {
                "section": section_idx,
                "startParagraph": section_start,
                "endParagraph": len(paragraphs) - 1,
                "endText": paragraph_text(paragraphs[-1])[:120] if paragraphs else "",
                **section_refs(final_sect),
            }
        )

    for section in sections:
        for ref in section["headers"] + section["footers"]:
            rid = ref.get("rId")
            ref["part"] = rels.get(rid)

    out = {
        "docx": str(docx_path),
        "markers": markers,
        "sections": sections,
        "header_footer_parts": parts,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
