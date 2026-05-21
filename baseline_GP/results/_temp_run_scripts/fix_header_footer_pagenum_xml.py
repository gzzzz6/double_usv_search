from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


DOCX = Path(r"F:\pythonprojects\my_report.docx")
REPORT = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\fix_header_footer_pagenum_xml_report.json")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {"w": W_NS, "r": R_NS, "rel": REL_NS, "ct": CT_NS}


def qn(tag: str) -> str:
    prefix, name = tag.split(":")
    ns = {"w": W_NS, "r": R_NS, "rel": REL_NS, "ct": CT_NS}[prefix]
    return f"{{{ns}}}{name}"


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("w:t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("w:tab"):
            parts.append("\t")
    return "".join(parts).strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def find_paragraph_index(paragraphs: list[etree._Element], target_compact: str) -> int:
    for idx, p in enumerate(paragraphs):
        if compact_text(paragraph_text(p)) == target_compact:
            return idx
    raise RuntimeError(f"未找到段落: {target_compact}")


def ensure_ppr(p: etree._Element) -> etree._Element:
    ppr = p.find("./w:pPr", namespaces=NS)
    if ppr is not None:
        return ppr
    ppr = etree.Element(qn("w:pPr"))
    p.insert(0, ppr)
    return ppr


def remove_children(parent: etree._Element, local_names: set[str]) -> None:
    for child in list(parent):
        if etree.QName(child).localname in local_names:
            parent.remove(child)


def strip_section_refs(sect_pr: etree._Element) -> None:
    remove_children(
        sect_pr,
        {
            "headerReference",
            "footerReference",
            "type",
            "pgNumType",
            "titlePg",
        },
    )


def add_ref(sect_pr: etree._Element, tag: str, rid: str, ref_type: str = "default") -> None:
    node = etree.Element(qn(f"w:{tag}"))
    node.set(qn("w:type"), ref_type)
    node.set(qn("r:id"), rid)
    sect_pr.insert(0, node)


def add_section_type(sect_pr: etree._Element, val: str) -> None:
    node = etree.Element(qn("w:type"))
    node.set(qn("w:val"), val)
    # After header/footer references.
    insert_at = 0
    for i, child in enumerate(list(sect_pr)):
        if etree.QName(child).localname in {"headerReference", "footerReference"}:
            insert_at = i + 1
    sect_pr.insert(insert_at, node)


def add_page_number_type(sect_pr: etree._Element, *, start: str, fmt: str | None = None) -> None:
    node = etree.Element(qn("w:pgNumType"))
    node.set(qn("w:start"), start)
    if fmt:
        node.set(qn("w:fmt"), fmt)

    insert_at = len(sect_pr)
    for i, child in enumerate(list(sect_pr)):
        if etree.QName(child).localname == "cols":
            insert_at = i
            break
        if etree.QName(child).localname == "docGrid":
            insert_at = i
            break
    sect_pr.insert(insert_at, node)


def make_section(
    base: etree._Element,
    *,
    header_rid: str | None,
    footer_rid: str | None,
    page_start: str | None = None,
    page_fmt: str | None = None,
    continuous: bool = False,
) -> etree._Element:
    sect_pr = copy.deepcopy(base)
    strip_section_refs(sect_pr)
    if header_rid:
        add_ref(sect_pr, "headerReference", header_rid)
    if footer_rid:
        add_ref(sect_pr, "footerReference", footer_rid)
    if continuous:
        add_section_type(sect_pr, "continuous")
    if page_start is not None:
        add_page_number_type(sect_pr, start=page_start, fmt=page_fmt)
    return sect_pr


def set_paragraph_section(p: etree._Element, sect_pr: etree._Element) -> None:
    ppr = ensure_ppr(p)
    remove_children(ppr, {"sectPr"})
    ppr.append(sect_pr)


def rpr(font: str, size_half_points: str) -> etree._Element:
    node = etree.Element(qn("w:rPr"))
    fonts = etree.SubElement(node, qn("w:rFonts"))
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), font)
    sz = etree.SubElement(node, qn("w:sz"))
    sz.set(qn("w:val"), size_half_points)
    szcs = etree.SubElement(node, qn("w:szCs"))
    szcs.set(qn("w:val"), size_half_points)
    b = etree.SubElement(node, qn("w:b"))
    b.set(qn("w:val"), "0")
    bcs = etree.SubElement(node, qn("w:bCs"))
    bcs.set(qn("w:val"), "0")
    return node


def add_text_run(p: etree._Element, text: str, *, font: str, size_half_points: str) -> None:
    run = etree.SubElement(p, qn("w:r"))
    run.append(rpr(font, size_half_points))
    t = etree.SubElement(run, qn("w:t"))
    t.text = text


def add_tab_run(p: etree._Element, *, font: str, size_half_points: str) -> None:
    run = etree.SubElement(p, qn("w:r"))
    run.append(rpr(font, size_half_points))
    etree.SubElement(run, qn("w:tab"))


def make_header_xml(title: str, right_tab_pos: str) -> bytes:
    hdr = etree.Element(qn("w:hdr"), nsmap={"w": W_NS, "r": R_NS})
    p = etree.SubElement(hdr, qn("w:p"))
    ppr = etree.SubElement(p, qn("w:pPr"))
    tabs = etree.SubElement(ppr, qn("w:tabs"))
    tab = etree.SubElement(tabs, qn("w:tab"))
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), right_tab_pos)
    p_bdr = etree.SubElement(ppr, qn("w:pBdr"))
    bottom = etree.SubElement(p_bdr, qn("w:bottom"))
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "auto")
    jc = etree.SubElement(ppr, qn("w:jc"))
    jc.set(qn("w:val"), "left")
    ppr.append(rpr("宋体", "18"))
    add_text_run(p, "兰州大学本科毕业论文（设计）", font="宋体", size_half_points="18")
    add_tab_run(p, font="宋体", size_half_points="18")
    add_text_run(p, title, font="宋体", size_half_points="18")
    return etree.tostring(hdr, encoding="UTF-8", xml_declaration=True, standalone="yes")


def make_footer_xml(result_text: str) -> bytes:
    ftr = etree.Element(qn("w:ftr"), nsmap={"w": W_NS, "r": R_NS})
    p = etree.SubElement(ftr, qn("w:p"))
    ppr = etree.SubElement(p, qn("w:pPr"))
    jc = etree.SubElement(ppr, qn("w:jc"))
    jc.set(qn("w:val"), "center")
    ppr.append(rpr("宋体", "21"))

    run_begin = etree.SubElement(p, qn("w:r"))
    run_begin.append(rpr("宋体", "21"))
    fld_begin = etree.SubElement(run_begin, qn("w:fldChar"))
    fld_begin.set(qn("w:fldCharType"), "begin")

    run_instr = etree.SubElement(p, qn("w:r"))
    run_instr.append(rpr("宋体", "21"))
    instr = etree.SubElement(run_instr, qn("w:instrText"))
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = " PAGE "

    run_sep = etree.SubElement(p, qn("w:r"))
    run_sep.append(rpr("宋体", "21"))
    fld_sep = etree.SubElement(run_sep, qn("w:fldChar"))
    fld_sep.set(qn("w:fldCharType"), "separate")

    add_text_run(p, result_text, font="宋体", size_half_points="21")

    run_end = etree.SubElement(p, qn("w:r"))
    run_end.append(rpr("宋体", "21"))
    fld_end = etree.SubElement(run_end, qn("w:fldChar"))
    fld_end.set(qn("w:fldCharType"), "end")
    return etree.tostring(ftr, encoding="UTF-8", xml_declaration=True, standalone="yes")


def make_blank_footer_xml() -> bytes:
    ftr = etree.Element(qn("w:ftr"), nsmap={"w": W_NS, "r": R_NS})
    p = etree.SubElement(ftr, qn("w:p"))
    ppr = etree.SubElement(p, qn("w:pPr"))
    jc = etree.SubElement(ppr, qn("w:jc"))
    jc.set(qn("w:val"), "center")
    ppr.append(rpr("宋体", "21"))
    return etree.tostring(ftr, encoding="UTF-8", xml_declaration=True, standalone="yes")


def next_part_name(zf: zipfile.ZipFile, prefix: str, suffix: str) -> str:
    nums = []
    pattern = re.compile(rf"word/{re.escape(prefix)}(\d+){re.escape(suffix)}$")
    for name in zf.namelist():
        m = pattern.match(name)
        if m:
            nums.append(int(m.group(1)))
    return f"word/{prefix}{max(nums, default=0) + 1}{suffix}"


def next_rid(rels_root: etree._Element) -> str:
    nums = []
    for rel in rels_root.findall("./rel:Relationship", namespaces=NS):
        rid = rel.get("Id") or ""
        if rid.startswith("rId") and rid[3:].isdigit():
            nums.append(int(rid[3:]))
    return f"rId{max(nums, default=0) + 1}"


def add_relationship(rels_root: etree._Element, *, rid: str, rel_type: str, target: str) -> None:
    rel = etree.SubElement(rels_root, qn("rel:Relationship"))
    rel.set("Id", rid)
    rel.set("Type", rel_type)
    rel.set("Target", target)


def add_override(ct_root: etree._Element, *, part_name: str, content_type: str) -> None:
    normalized = "/" + part_name.replace("\\", "/").lstrip("/")
    for item in ct_root.findall("./ct:Override", namespaces=NS):
        if item.get("PartName") == normalized:
            return
    node = etree.SubElement(ct_root, qn("ct:Override"))
    node.set("PartName", normalized)
    node.set("ContentType", content_type)


def write_docx(src: Path, replacements: dict[str, bytes], additions: dict[str, bytes]) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(tmp_path, "w") as zout:
            written = set()
            for info in zin.infolist():
                data = replacements.get(info.filename)
                if data is None:
                    data = zin.read(info.filename)
                zout.writestr(info, data)
                written.add(info.filename)
            for name, data in additions.items():
                if name not in written:
                    zout.writestr(name, data)
        shutil.move(str(tmp_path), str(src))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    with zipfile.ZipFile(DOCX, "r") as zf:
        parser = etree.XMLParser(remove_blank_text=False, recover=False)
        document = etree.fromstring(zf.read("word/document.xml"), parser=parser)
        rels_root = etree.fromstring(zf.read("word/_rels/document.xml.rels"), parser=parser)
        ct_root = etree.fromstring(zf.read("[Content_Types].xml"), parser=parser)

        header_part = next_part_name(zf, "header", ".xml")
        footer_roman_part = next_part_name(zf, "footer", ".xml")
        # Account for the footer part we are about to add.
        footer_body_num = int(re.search(r"footer(\d+)\.xml$", footer_roman_part).group(1)) + 1
        footer_body_part = f"word/footer{footer_body_num}.xml"
        footer_blank_part = f"word/footer{footer_body_num + 1}.xml"

    body = document.find("./w:body", namespaces=NS)
    if body is None:
        raise RuntimeError("word/document.xml missing body")
    paragraphs = body.findall("./w:p", namespaces=NS)

    abstract_title_idx = find_paragraph_index(paragraphs, "中文摘要")
    title = paragraph_text(paragraphs[abstract_title_idx - 1])
    toc_idx = find_paragraph_index(paragraphs, "目录")
    body_idx = find_paragraph_index(paragraphs, "1绪论")
    appendix_idx = find_paragraph_index(paragraphs, "附录")

    # Existing section properties: cover, pre-body section, final body section.
    existing_sects = document.findall(".//w:sectPr", namespaces=NS)
    if len(existing_sects) < 3:
        raise RuntimeError(f"当前文档分节数量异常: {len(existing_sects)}")
    cover_base = existing_sects[0]
    front_base = existing_sects[1]
    body_base = existing_sects[-1]

    right_tab_pos = str(
        int(front_base.find("./w:pgSz", namespaces=NS).get(qn("w:w")))
        - int(front_base.find("./w:pgMar", namespaces=NS).get(qn("w:left")))
        - int(front_base.find("./w:pgMar", namespaces=NS).get(qn("w:right")))
    )

    header_rid = next_rid(rels_root)
    add_relationship(
        rels_root,
        rid=header_rid,
        rel_type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header",
        target=header_part.replace("word/", ""),
    )
    footer_roman_rid = next_rid(rels_root)
    add_relationship(
        rels_root,
        rid=footer_roman_rid,
        rel_type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer",
        target=footer_roman_part.replace("word/", ""),
    )
    footer_body_rid = next_rid(rels_root)
    add_relationship(
        rels_root,
        rid=footer_body_rid,
        rel_type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer",
        target=footer_body_part.replace("word/", ""),
    )
    footer_blank_rid = next_rid(rels_root)
    add_relationship(
        rels_root,
        rid=footer_blank_rid,
        rel_type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer",
        target=footer_blank_part.replace("word/", ""),
    )

    # Section 1: cover/declaration, no header/footer/page number.
    strip_section_refs(cover_base)

    # Section 2: Chinese/English abstracts, lower Roman page number from i.
    abstract_sect = make_section(
        front_base,
        header_rid=header_rid,
        footer_rid=footer_roman_rid,
        page_start="1",
        page_fmt="lowerRoman",
        continuous=True,
    )
    set_paragraph_section(paragraphs[toc_idx - 1], abstract_sect)

    # Section 3: main/catalog/list-of-figures/list-of-tables, header but no page number.
    catalog_sect = make_section(
        front_base,
        header_rid=header_rid,
        footer_rid=footer_blank_rid,
        continuous=False,
    )
    set_paragraph_section(paragraphs[body_idx - 1], catalog_sect)

    # Section 4: body/references/acknowledgement, Arabic page number from 1.
    body_sect = make_section(
        body_base,
        header_rid=header_rid,
        footer_rid=footer_body_rid,
        page_start="1",
        page_fmt="decimal",
        continuous=True,
    )
    set_paragraph_section(paragraphs[appendix_idx - 1], body_sect)

    # Section 5: appendix, header but no page number.
    appendix_sect = make_section(
        body_base,
        header_rid=header_rid,
        footer_rid=footer_blank_rid,
        continuous=False,
    )
    final_sect = body.find("./w:sectPr", namespaces=NS)
    if final_sect is None:
        body.append(appendix_sect)
    else:
        body.replace(final_sect, appendix_sect)

    add_override(
        ct_root,
        part_name=header_part,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
    )
    add_override(
        ct_root,
        part_name=footer_roman_part,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
    )
    add_override(
        ct_root,
        part_name=footer_body_part,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
    )
    add_override(
        ct_root,
        part_name=footer_blank_part,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
    )

    replacements = {
        "word/document.xml": etree.tostring(document, encoding="UTF-8", xml_declaration=True, standalone=None),
        "word/_rels/document.xml.rels": etree.tostring(rels_root, encoding="UTF-8", xml_declaration=True, standalone=None),
        "[Content_Types].xml": etree.tostring(ct_root, encoding="UTF-8", xml_declaration=True, standalone=None),
    }
    additions = {
        header_part: make_header_xml(title, right_tab_pos),
        footer_roman_part: make_footer_xml("i"),
        footer_body_part: make_footer_xml("1"),
        footer_blank_part: make_blank_footer_xml(),
    }
    write_docx(DOCX, replacements, additions)

    report = {
        "docx": str(DOCX),
        "title_used_in_header": title,
        "inserted_parts": {
            "header": header_part,
            "footer_roman": footer_roman_part,
            "footer_body": footer_body_part,
            "footer_blank": footer_blank_part,
        },
        "relationships": {
            "header": header_rid,
            "footer_roman": footer_roman_rid,
            "footer_body": footer_body_rid,
            "footer_blank": footer_blank_rid,
        },
        "paragraph_boundaries": {
            "abstract_title_index": abstract_title_idx,
            "toc_index": toc_idx,
            "body_index": body_idx,
            "appendix_index": appendix_idx,
        },
        "right_tab_pos_twips": right_tab_pos,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
