from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import win32com.client


WD_SECTION_BREAK_CONTINUOUS = 3
WD_HEADER_FOOTER_PRIMARY = 1
WD_HEADER_FOOTER_FIRST_PAGE = 2
WD_HEADER_FOOTER_EVEN_PAGES = 3
WD_ALIGN_PARAGRAPH_LEFT = 0
WD_ALIGN_PARAGRAPH_CENTER = 1
WD_ALIGN_TAB_RIGHT = 2
WD_TAB_LEADER_SPACES = 0
WD_BORDER_BOTTOM = -3
WD_LINE_STYLE_NONE = 0
WD_LINE_STYLE_SINGLE = 1
WD_LINE_WIDTH_050PT = 4
WD_FIELD_PAGE = 33
WD_PAGE_NUMBER_STYLE_ARABIC = 0
WD_PAGE_NUMBER_STYLE_LOWERCASE_ROMAN = 2

HF_TYPES = (
    WD_HEADER_FOOTER_PRIMARY,
    WD_HEADER_FOOTER_FIRST_PAGE,
    WD_HEADER_FOOTER_EVEN_PAGES,
)


def clean(text: str) -> str:
    return (text or "").replace("\r", "").replace("\x07", "").strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", clean(text))


def paragraph_text(paragraph) -> str:
    return clean(paragraph.Range.Text)


def paragraph_compact(paragraph) -> str:
    return compact(paragraph_text(paragraph))


def find_paragraph(doc, predicate, *, start: int = 1):
    for i in range(start, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        if predicate(paragraph_text(p), paragraph_compact(p)):
            return i, p
    raise RuntimeError("未找到目标段落")


def section_for_range(doc, rng) -> object:
    pos = rng.Start
    for i in range(1, doc.Sections.Count + 1):
        sec = doc.Sections(i)
        if sec.Range.Start <= pos < sec.Range.End:
            return sec
    raise RuntimeError("未能定位段落所在节")


def section_label(sec) -> str:
    text = clean(sec.Range.Text)
    return text[:80]


def insert_continuous_section_before(paragraph) -> None:
    rng = paragraph.Range.Document.Range(paragraph.Range.Start, paragraph.Range.Start)
    rng.InsertBreak(WD_SECTION_BREAK_CONTINUOUS)


def clear_header(header) -> None:
    header.LinkToPrevious = False
    header.Range.Text = ""
    try:
        border = header.Range.Paragraphs(1).Borders(WD_BORDER_BOTTOM)
        border.LineStyle = WD_LINE_STYLE_NONE
    except Exception:
        pass


def clear_footer(footer) -> None:
    footer.LinkToPrevious = False
    footer.Range.Text = ""
    try:
        footer.Range.ParagraphFormat.Alignment = WD_ALIGN_PARAGRAPH_CENTER
        footer.Range.Font.Name = "宋体"
        footer.Range.Font.NameFarEast = "宋体"
        footer.Range.Font.Size = 10.5
    except Exception:
        pass


def apply_header(section, title: str) -> None:
    section.PageSetup.DifferentFirstPageHeaderFooter = False
    width = float(section.PageSetup.PageWidth - section.PageSetup.LeftMargin - section.PageSetup.RightMargin)
    for typ in HF_TYPES:
        header = section.Headers(typ)
        header.LinkToPrevious = False
        rng = header.Range
        rng.Text = f"兰州大学本科毕业论文（设计）\t{title}"
        rng.Font.Name = "宋体"
        rng.Font.NameFarEast = "宋体"
        rng.Font.Size = 9
        rng.Font.Bold = False
        para = rng.Paragraphs(1)
        para.Alignment = WD_ALIGN_PARAGRAPH_LEFT
        para.Range.Font.Name = "宋体"
        para.Range.Font.NameFarEast = "宋体"
        para.Range.Font.Size = 9
        para.Range.Font.Bold = False
        tabs = para.TabStops
        tabs.ClearAll()
        tabs.Add(Position=width, Alignment=WD_ALIGN_TAB_RIGHT, Leader=WD_TAB_LEADER_SPACES)
        border = para.Borders(WD_BORDER_BOTTOM)
        border.LineStyle = WD_LINE_STYLE_SINGLE
        border.LineWidth = WD_LINE_WIDTH_050PT


def apply_page_footer(section, *, number_style: int) -> None:
    section.PageSetup.DifferentFirstPageHeaderFooter = False
    footer = section.Footers(WD_HEADER_FOOTER_PRIMARY)
    footer.LinkToPrevious = False
    footer.Range.Text = ""
    footer.Range.ParagraphFormat.Alignment = WD_ALIGN_PARAGRAPH_CENTER
    footer.Range.Font.Name = "宋体"
    footer.Range.Font.NameFarEast = "宋体"
    footer.Range.Font.Size = 10.5
    footer.Range.Font.Bold = False
    footer.PageNumbers.RestartNumberingAtSection = True
    footer.PageNumbers.StartingNumber = 1
    footer.PageNumbers.NumberStyle = number_style
    footer.PageNumbers.ShowFirstPageNumber = True

    field_range = footer.Range
    field_range.Collapse(1)
    field = footer.Range.Fields.Add(Range=field_range, Type=WD_FIELD_PAGE)
    field.Result.Font.Name = "宋体"
    field.Result.Font.NameFarEast = "宋体"
    field.Result.Font.Size = 10.5
    field.Result.Font.Bold = False
    footer.Range.Paragraphs(1).Alignment = WD_ALIGN_PARAGRAPH_CENTER
    footer.Range.Paragraphs(1).Range.Font.Name = "宋体"
    footer.Range.Paragraphs(1).Range.Font.NameFarEast = "宋体"
    footer.Range.Paragraphs(1).Range.Font.Size = 10.5

    for typ in (WD_HEADER_FOOTER_FIRST_PAGE, WD_HEADER_FOOTER_EVEN_PAGES):
        other = section.Footers(typ)
        other.LinkToPrevious = False
        other.Range.Text = ""


def clear_all_footers(section) -> None:
    section.PageSetup.DifferentFirstPageHeaderFooter = False
    for typ in HF_TYPES:
        clear_footer(section.Footers(typ))


def clear_all_headers(section) -> None:
    section.PageSetup.DifferentFirstPageHeaderFooter = False
    for typ in HF_TYPES:
        clear_header(section.Headers(typ))


def main() -> int:
    docx_path = Path(sys.argv[1]).resolve()
    out_path = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\fix_header_footer_pagenum_report.json")
    )
    if not docx_path.exists():
        raise FileNotFoundError(docx_path)

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(
            str(docx_path),
            ReadOnly=False,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Visible=False,
        )
        doc.Repaginate()

        chinese_abstract_idx, chinese_abstract = find_paragraph(doc, lambda text, c: c == "中文摘要")
        title_para = doc.Paragraphs(chinese_abstract_idx - 1)
        title = paragraph_text(title_para)
        if not title:
            raise RuntimeError("未能从中文摘要前一段读取论文题目")

        _, toc_para = find_paragraph(doc, lambda text, c: c == "目录")
        _, appendix_para = find_paragraph(doc, lambda text, c: c == "附录")

        insert_continuous_section_before(toc_para)
        # Locate again after the first insertion because paragraph indices/ranges may be invalidated.
        _, appendix_para = find_paragraph(doc, lambda text, c: c == "附录")
        insert_continuous_section_before(appendix_para)
        doc.Repaginate()

        _, chinese_abstract = find_paragraph(doc, lambda text, c: c == "中文摘要")
        _, toc_para = find_paragraph(doc, lambda text, c: c == "目录")
        _, body_para = find_paragraph(doc, lambda text, c: c == "1绪论")
        _, appendix_para = find_paragraph(doc, lambda text, c: c == "附录")

        cover_section = doc.Sections(1)
        abstract_section = section_for_range(doc, chinese_abstract.Range)
        catalog_section = section_for_range(doc, toc_para.Range)
        body_section = section_for_range(doc, body_para.Range)
        appendix_section = section_for_range(doc, appendix_para.Range)

        clear_all_headers(cover_section)
        clear_all_footers(cover_section)

        for sec in (abstract_section, catalog_section, body_section, appendix_section):
            apply_header(sec, title)

        apply_page_footer(abstract_section, number_style=WD_PAGE_NUMBER_STYLE_LOWERCASE_ROMAN)
        clear_all_footers(catalog_section)
        apply_page_footer(body_section, number_style=WD_PAGE_NUMBER_STYLE_ARABIC)
        clear_all_footers(appendix_section)

        doc.Fields.Update()
        doc.Repaginate()
        doc.Save()

        report = {
            "docx": str(docx_path),
            "title_used_in_header": title,
            "section_count": doc.Sections.Count,
            "sections": {
                "cover": cover_section.Index,
                "abstract_roman": abstract_section.Index,
                "catalog_no_page": catalog_section.Index,
                "body_arabic": body_section.Index,
                "appendix_no_page": appendix_section.Index,
            },
            "section_labels": {
                "cover": section_label(cover_section),
                "abstract_roman": section_label(abstract_section),
                "catalog_no_page": section_label(catalog_section),
                "body_arabic": section_label(body_section),
                "appendix_no_page": section_label(appendix_section),
            },
        }
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(out_path)
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
