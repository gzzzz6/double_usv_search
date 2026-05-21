from __future__ import annotations

import json
import sys
from pathlib import Path

import win32com.client


WD_ACTIVE_END_PAGE_NUMBER = 3
WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1
WD_HEADER_FOOTER_PRIMARY = 1
WD_HEADER_FOOTER_FIRST_PAGE = 2
WD_HEADER_FOOTER_EVEN_PAGES = 3
WD_BORDER_BOTTOM = -3
WD_FIELD_PAGE = 33


HF_TYPES = {
    "primary": WD_HEADER_FOOTER_PRIMARY,
    "first": WD_HEADER_FOOTER_FIRST_PAGE,
    "even": WD_HEADER_FOOTER_EVEN_PAGES,
}


ALIGN_MAP = {
    0: "left",
    1: "center",
    2: "right",
    3: "justify",
}


NUMBER_STYLE_MAP = {
    0: "arabic",
    1: "upperRoman",
    2: "lowerRoman",
    3: "upperLetter",
    4: "lowerLetter",
}


def clean(text: str) -> str:
    return (text or "").replace("\r", "").replace("\x07", "").strip()


def paragraph_info(range_obj) -> dict:
    try:
        p = range_obj.Paragraphs(1)
    except Exception:
        return {}
    rng = p.Range
    font = rng.Font
    border = p.Borders(WD_BORDER_BOTTOM)
    return {
        "text": clean(rng.Text),
        "alignment": ALIGN_MAP.get(int(p.Alignment), int(p.Alignment)),
        "fontName": font.Name,
        "fontNameFarEast": font.NameFarEast,
        "fontSize": float(font.Size) if font.Size is not None else None,
        "bold": int(font.Bold) if font.Bold is not None else None,
        "bottomBorderLineStyle": int(border.LineStyle),
        "bottomBorderLineWidth": int(border.LineWidth),
    }


def header_footer_info(hf) -> dict:
    rng = hf.Range
    page_fields = []
    for i in range(1, rng.Fields.Count + 1):
        field = rng.Fields(i)
        page_fields.append(
            {
                "type": int(field.Type),
                "code": clean(field.Code.Text),
                "result": clean(field.Result.Text),
                "isPage": int(field.Type) == WD_FIELD_PAGE,
            }
        )
    return {
        "exists": bool(hf.Exists),
        "linkToPrevious": bool(hf.LinkToPrevious),
        "text": clean(rng.Text),
        "paragraph": paragraph_info(rng),
        "fields": page_fields,
    }


def page_numbers_info(footer) -> dict:
    pns = footer.PageNumbers
    return {
        "count": int(pns.Count),
        "restartNumberingAtSection": bool(pns.RestartNumberingAtSection),
        "startingNumber": int(pns.StartingNumber),
        "numberStyle": NUMBER_STYLE_MAP.get(int(pns.NumberStyle), int(pns.NumberStyle)),
        "showFirstPageNumber": bool(pns.ShowFirstPageNumber),
    }


def main() -> int:
    docx_path = Path(sys.argv[1]).resolve()
    out_path = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\header_footer_word_audit.json")
    )

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(
            str(docx_path),
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Visible=False,
        )
        doc.Repaginate()

        sections = []
        for i in range(1, doc.Sections.Count + 1):
            section = doc.Sections(i)
            sec_range = section.Range
            start_range = doc.Range(sec_range.Start, sec_range.Start)
            end_pos = max(sec_range.Start, sec_range.End - 1)
            end_range = doc.Range(end_pos, end_pos)
            start_page = int(start_range.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))
            end_page = int(end_range.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))
            start_physical = int(start_range.Information(WD_ACTIVE_END_PAGE_NUMBER))
            end_physical = int(end_range.Information(WD_ACTIVE_END_PAGE_NUMBER))

            headers = {}
            footers = {}
            footer_page_numbers = {}
            for name, typ in HF_TYPES.items():
                headers[name] = header_footer_info(section.Headers(typ))
                footer = section.Footers(typ)
                footers[name] = header_footer_info(footer)
                footer_page_numbers[name] = page_numbers_info(footer)

            sections.append(
                {
                    "section": i,
                    "startAdjustedPage": start_page,
                    "endAdjustedPage": end_page,
                    "startPhysicalPage": start_physical,
                    "endPhysicalPage": end_physical,
                    "differentFirstPageHeaderFooter": bool(section.PageSetup.DifferentFirstPageHeaderFooter),
                    "headers": headers,
                    "footers": footers,
                    "footerPageNumbers": footer_page_numbers,
                }
            )
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()

    out = {"docx": str(docx_path), "sections": sections}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
