from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import win32com.client


WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1


def clean(text: str) -> str:
    return (text or "").replace("\r", "").replace("\x07", "").strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def main() -> int:
    docx_path = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()

    heading_pat = re.compile(r"^(?:\d+\s+.+|\d+(?:\.\d+){1,2}\s+.+)$")
    fig_pat = re.compile(r"^图\s*\d+[-.．]\d+(?:\s+|$)")
    table_pat = re.compile(r"^表\s*\d+[-.．]\d+(?:\s*续)?(?:\s+|$)")

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

        in_body = False
        headings: list[dict] = []
        figures: list[dict] = []
        tables: list[dict] = []

        for i in range(1, doc.Paragraphs.Count + 1):
            para = doc.Paragraphs(i)
            text = clean(para.Range.Text)
            c = compact(text)
            if not text:
                continue
            if not in_body and c == "1绪论":
                in_body = True
            if not in_body:
                continue
            if c == "参考文献":
                break
            if "\t" in text:
                continue
            page = int(para.Range.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))
            if heading_pat.match(text):
                headings.append({"paragraph_index": i, "text": text, "key": compact(text), "page": page})
            if fig_pat.match(text):
                figures.append({"paragraph_index": i, "text": text, "key": compact(text), "page": page})
            if table_pat.match(text):
                tables.append({"paragraph_index": i, "text": text, "key": compact(text), "page": page})
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()

    out = {
        "docx": str(docx_path),
        "headings_count": len(headings),
        "figures_count": len(figures),
        "tables_count": len(tables),
        "headings": headings,
        "figures": figures,
        "tables": tables,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
