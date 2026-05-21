from __future__ import annotations

import copy
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def qn(name: str) -> str:
    if name.startswith("w:"):
        name = name.split(":", 1)[1]
    return f"{{{W_NS}}}{name}"


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("tab"):
            parts.append("\t")
        elif elem.tag == qn("br"):
            parts.append("\n")
    return "".join(parts)


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def ensure_child(parent: etree._Element, tag: str, insert_at: int | None = None) -> etree._Element:
    child = parent.find(f"./{tag}", namespaces=NS)
    if child is not None:
        return child
    child = etree.Element(qn(tag))
    if insert_at is None:
        parent.append(child)
    else:
        parent.insert(insert_at, child)
    return child


def remove_children(parent: etree._Element, tag: str) -> None:
    for child in list(parent):
        if child.tag == qn(tag):
            parent.remove(child)


def ensure_ppr(p: etree._Element) -> etree._Element:
    ppr = p.find("./w:pPr", namespaces=NS)
    if ppr is not None:
        return ppr
    ppr = etree.Element(qn("pPr"))
    p.insert(0, ppr)
    return ppr


def ensure_rpr(r: etree._Element) -> etree._Element:
    rpr = r.find("./w:rPr", namespaces=NS)
    if rpr is not None:
        return rpr
    rpr = etree.Element(qn("rPr"))
    r.insert(0, rpr)
    return rpr


def set_run_format(r: etree._Element, *, font: str, size_half_points: str, bold: bool | None) -> None:
    rpr = ensure_rpr(r)
    rfonts = ensure_child(rpr, "w:rFonts", 0)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(key), font)

    if bold is not None:
        b = ensure_child(rpr, "w:b")
        bcs = ensure_child(rpr, "w:bCs")
        if bold:
            b.attrib.pop(qn("val"), None)
            bcs.attrib.pop(qn("val"), None)
        else:
            b.set(qn("val"), "0")
            bcs.set(qn("val"), "0")

    sz = ensure_child(rpr, "w:sz")
    szcs = ensure_child(rpr, "w:szCs")
    sz.set(qn("val"), size_half_points)
    szcs.set(qn("val"), size_half_points)


def format_table_dir_title(p: etree._Element) -> None:
    ppr = ensure_ppr(p)
    jc = ensure_child(ppr, "w:jc")
    jc.set(qn("val"), "center")

    spacing = ensure_child(ppr, "w:spacing")
    spacing.set(qn("line"), "400")
    spacing.set(qn("lineRule"), "exact")

    remove_children(ppr, "w:ind")
    ind = ensure_child(ppr, "w:ind")
    for key in ("left", "right", "firstLine", "hanging", "firstLineChars", "hangingChars"):
        ind.set(qn(key), "0")

    for r in p.iter(qn("r")):
        set_run_format(r, font="黑体", size_half_points="32", bold=False)


def new_entry_paragraph(caption: str, page: int, template: etree._Element | None = None) -> etree._Element:
    p = copy.deepcopy(template) if template is not None else etree.Element(qn("p"))
    for child in list(p):
        p.remove(child)

    ppr = etree.SubElement(p, qn("pPr"))
    pstyle = etree.SubElement(ppr, qn("pStyle"))
    pstyle.set(qn("val"), "TOC1")

    tabs = etree.SubElement(ppr, qn("tabs"))
    tab = etree.SubElement(tabs, qn("tab"))
    tab.set(qn("val"), "right")
    tab.set(qn("leader"), "dot")
    tab.set(qn("pos"), "8948")

    spacing = etree.SubElement(ppr, qn("spacing"))
    spacing.set(qn("line"), "400")
    spacing.set(qn("lineRule"), "exact")

    ind = etree.SubElement(ppr, qn("ind"))
    ind.set(qn("left"), "0")
    ind.set(qn("right"), "0")
    ind.set(qn("firstLine"), "0")
    ind.set(qn("firstLineChars"), "0")

    jc = etree.SubElement(ppr, qn("jc"))
    jc.set(qn("val"), "both")

    for value, is_tab in ((caption, False), ("", True), (str(page), False)):
        r = etree.SubElement(p, qn("r"))
        set_run_format(r, font="宋体", size_half_points="28", bold=False)
        if is_tab:
            etree.SubElement(r, qn("tab"))
        else:
            t = etree.SubElement(r, qn("t"))
            t.text = value

    return p


def write_docx_with_replaced_part(src: Path, dst: Path, replacements: dict[str, bytes]) -> None:
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            data = replacements.get(info.filename)
            if data is None:
                data = zin.read(info.filename)
            zout.writestr(info, data)


def main() -> int:
    docx_path = Path(sys.argv[1]).resolve()
    pages_json = Path(sys.argv[2]).resolve()
    report_path = (
        Path(sys.argv[3]).resolve()
        if len(sys.argv) > 3
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\regenerate_table_directory_report.json")
    )
    pages = json.loads(pages_json.read_text(encoding="utf-8"))
    records = pages.get("records", [])
    if len(records) != 13:
        raise RuntimeError(f"期望正文表题 13 条，但页码文件中有 {len(records)} 条")

    with zipfile.ZipFile(docx_path, "r") as zf:
        document_xml = zf.read("word/document.xml")

    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    root = etree.fromstring(document_xml, parser=parser)
    body = root.find("./w:body", namespaces=NS)
    if body is None:
        raise RuntimeError("word/document.xml missing w:body")
    paragraphs = body.findall("./w:p", namespaces=NS)

    table_dir_idx: int | None = None
    body_start_idx: int | None = None
    for idx, p in enumerate(paragraphs):
        compact = compact_text(paragraph_text(p))
        if table_dir_idx is None and compact == "表目录":
            table_dir_idx = idx
            continue
        if table_dir_idx is not None and compact.startswith("1绪论"):
            body_start_idx = idx
            break
    if table_dir_idx is None or body_start_idx is None:
        raise RuntimeError("未能定位表目录或正文起点")

    title_p = paragraphs[table_dir_idx]
    format_table_dir_title(title_p)
    first_old_entry = paragraphs[table_dir_idx + 1] if body_start_idx > table_dir_idx + 1 else None

    # Preserve the final blank/section paragraph immediately before the body when it exists.
    delete_start = table_dir_idx + 1
    delete_end = body_start_idx
    preserved_tail = None
    if delete_end > delete_start:
        tail_candidate = paragraphs[delete_end - 1]
        if not paragraph_text(tail_candidate).strip():
            preserved_tail = tail_candidate
            delete_end -= 1

    for p in paragraphs[delete_start:delete_end]:
        body.remove(p)

    insert_after = title_p
    insert_pos = list(body).index(insert_after) + 1
    for offset, record in enumerate(records):
        caption = record["caption"]
        page = int(record["page"])
        body.insert(insert_pos + offset, new_entry_paragraph(caption, page, first_old_entry))

    updated_xml = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=None)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_docx_with_replaced_part(docx_path, tmp_path, {"word/document.xml": updated_xml})
        shutil.move(str(tmp_path), str(docx_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    report = {
        "docx": str(docx_path),
        "table_dir_index": table_dir_idx,
        "body_start_index_before": body_start_idx,
        "old_entry_count_removed": delete_end - delete_start,
        "new_entry_count": len(records),
        "preserved_blank_or_section_paragraph": preserved_tail is not None,
        "records": records,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
