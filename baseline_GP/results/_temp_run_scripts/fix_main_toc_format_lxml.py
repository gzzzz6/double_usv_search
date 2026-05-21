from __future__ import annotations

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


def qn(tag: str) -> str:
    prefix, name = tag.split(":")
    if prefix != "w":
        raise ValueError(tag)
    return f"{{{W_NS}}}{name}"


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("w:t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("w:tab"):
            parts.append("\t")
        elif elem.tag == qn("w:br"):
            parts.append("\n")
    return "".join(parts)


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def p_style_id(p: etree._Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return node.get(qn("w:val")) if node is not None else None


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


def ensure_ppr(p: etree._Element) -> etree._Element:
    ppr = p.find("./w:pPr", namespaces=NS)
    if ppr is not None:
        return ppr
    ppr = etree.Element(qn("w:pPr"))
    p.insert(0, ppr)
    return ppr


def ensure_rpr(r: etree._Element) -> etree._Element:
    rpr = r.find("./w:rPr", namespaces=NS)
    if rpr is not None:
        return rpr
    rpr = etree.Element(qn("w:rPr"))
    r.insert(0, rpr)
    return rpr


def remove_children(parent: etree._Element, tag: str) -> None:
    for child in list(parent):
        if child.tag == qn(tag):
            parent.remove(child)


def set_paragraph_spacing(
    p: etree._Element,
    *,
    before_twips: str,
    after_twips: str,
    line: str,
    line_rule: str,
) -> None:
    ppr = ensure_ppr(p)
    spacing = ensure_child(ppr, "w:spacing")
    spacing.set(qn("w:before"), before_twips)
    spacing.set(qn("w:after"), after_twips)
    spacing.set(qn("w:line"), line)
    spacing.set(qn("w:lineRule"), line_rule)


def set_paragraph_centered(p: etree._Element) -> None:
    ppr = ensure_ppr(p)
    jc = ensure_child(ppr, "w:jc")
    jc.set(qn("w:val"), "center")


def set_paragraph_indent_zero(p: etree._Element) -> None:
    ppr = ensure_ppr(p)
    remove_children(ppr, "w:ind")
    ind = ensure_child(ppr, "w:ind")
    for key in ("w:left", "w:right", "w:firstLine", "w:hanging", "w:firstLineChars", "w:hangingChars"):
        ind.set(qn(key), "0")


def set_run_format(r: etree._Element, *, font: str, size_half_points: str, bold: bool) -> None:
    rpr = ensure_rpr(r)

    rfonts = ensure_child(rpr, "w:rFonts", 0)
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(key), font)

    b = ensure_child(rpr, "w:b")
    bcs = ensure_child(rpr, "w:bCs")
    if bold:
        b.attrib.pop(qn("w:val"), None)
        bcs.attrib.pop(qn("w:val"), None)
    else:
        b.set(qn("w:val"), "0")
        bcs.set(qn("w:val"), "0")

    sz = ensure_child(rpr, "w:sz")
    szcs = ensure_child(rpr, "w:szCs")
    sz.set(qn("w:val"), size_half_points)
    szcs.set(qn("w:val"), size_half_points)


def replace_paragraph_text(
    p: etree._Element,
    text: str,
    *,
    font: str,
    size_half_points: str,
    bold: bool,
) -> None:
    ppr = p.find("./w:pPr", namespaces=NS)
    for child in list(p):
        if child is not ppr:
            p.remove(child)
    r = etree.SubElement(p, qn("w:r"))
    set_run_format(r, font=font, size_half_points=size_half_points, bold=bold)
    t = etree.SubElement(r, qn("w:t"))
    t.text = text


def write_docx_with_replaced_part(src: Path, dst: Path, replacements: dict[str, bytes]) -> None:
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            data = replacements.get(info.filename)
            if data is None:
                data = zin.read(info.filename)
            zout.writestr(info, data)


def main() -> int:
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    if not docx_path.exists():
        raise FileNotFoundError(docx_path)

    with zipfile.ZipFile(docx_path, "r") as zf:
        document_xml = zf.read("word/document.xml")

    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    root = etree.fromstring(document_xml, parser=parser)
    body = root.find("./w:body", namespaces=NS)
    if body is None:
        raise RuntimeError("word/document.xml missing w:body")

    paragraphs = body.findall("./w:p", namespaces=NS)
    toc_title_idx: int | None = None
    figure_dir_idx: int | None = None

    for idx, p in enumerate(paragraphs):
        compact = compact_text(paragraph_text(p))
        if toc_title_idx is None and compact == "目录":
            toc_title_idx = idx
            continue
        if toc_title_idx is not None and compact in {"图目录", "图表目录", "插图目录"}:
            figure_dir_idx = idx
            break

    if toc_title_idx is None:
        raise RuntimeError("未找到主目录标题")
    if figure_dir_idx is None:
        figure_dir_idx = len(paragraphs)

    toc_title = paragraphs[toc_title_idx]
    set_paragraph_centered(toc_title)
    set_paragraph_spacing(toc_title, before_twips="480", after_twips="360", line="240", line_rule="auto")
    set_paragraph_indent_zero(toc_title)
    replace_paragraph_text(toc_title, "目 录", font="黑体", size_half_points="32", bold=True)

    target_styles = {
        "TOC1": {"font": "宋体", "size_half_points": "28", "bold": True},
        "TOC2": {"font": "宋体", "size_half_points": "28", "bold": False},
        "TOC3": {"font": "宋体", "size_half_points": "24", "bold": False},
    }
    changed_counts = {"TOC1": 0, "TOC2": 0, "TOC3": 0, "other_toc_levels": {}}

    for p in paragraphs[toc_title_idx + 1 : figure_dir_idx]:
        style = p_style_id(p)
        if style in target_styles:
            spec = target_styles[style]
            for r in p.iter(qn("w:r")):
                set_run_format(
                    r,
                    font=spec["font"],
                    size_half_points=spec["size_half_points"],
                    bold=spec["bold"],
                )
            changed_counts[style] += 1
        elif style and re.fullmatch(r"TOC\d+", style):
            changed_counts["other_toc_levels"][style] = changed_counts["other_toc_levels"].get(style, 0) + 1

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
        "toc_title_index": toc_title_idx,
        "main_toc_end_index": figure_dir_idx,
        "changed_counts": changed_counts,
        "scope": "Only the main table of contents before the figure directory was modified.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
