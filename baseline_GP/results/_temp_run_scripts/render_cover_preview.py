from __future__ import annotations

from pathlib import Path

import win32com.client as win32


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "信息科学与工程学院_320220938891_郭一泽.docx"
PDF_PATH = ROOT / "baseline_GP" / "results" / "_temp_run_scripts" / "cover_preview.pdf"
PNG_PATH = ROOT / "baseline_GP" / "results" / "_temp_run_scripts" / "cover_preview_page1.png"


def main() -> None:
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(str(DOCX_PATH), ReadOnly=True, AddToRecentFiles=False)
        doc.ExportAsFixedFormat(str(PDF_PATH), 17)
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()

    import fitz

    pdf = fitz.open(str(PDF_PATH))
    try:
        page = pdf[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pix.save(str(PNG_PATH))
    finally:
        pdf.close()
    print(PNG_PATH)


if __name__ == "__main__":
    main()
