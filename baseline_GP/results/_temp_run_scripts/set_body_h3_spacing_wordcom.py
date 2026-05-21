from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import win32com.client


CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百\d]+章")
H3_RE = re.compile(r"^\d+\.\d+\.\d+(?:\s+|　+).+")


def clean_text(text: str) -> str:
    return text.replace("\r", "").replace("\a", "").strip()


def compact_text(text: str) -> str:
    return re.sub(r"[\s\u00a0　\r\a]+", "", text)


def style_name_of(paragraph) -> str:
    try:
        return str(paragraph.Range.Style.NameLocal)
    except Exception:
        try:
            return str(paragraph.Range.Style)
        except Exception:
            return ""


def find_body_region(doc) -> tuple[int, int]:
    start = None
    end = None
    for idx, para in enumerate(doc.Paragraphs, start=1):
        text = clean_text(para.Range.Text)
        style = style_name_of(para)
        if style.startswith("TOC"):
            continue
        if start is None and CHAPTER_RE.match(text):
            start = idx
            continue
        if start is not None and compact_text(text) in {"参考文献", "致谢", "附录"}:
            end = idx
            break
    if start is None:
        raise RuntimeError("Could not locate the first body chapter heading.")
    if end is None:
        end = doc.Paragraphs.Count + 1
    return start, end


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: set_body_h3_spacing_wordcom.py input.docx report.json")

    docx_path = str(Path(sys.argv[1]).resolve())
    report_path = Path(sys.argv[2])

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    changed = []
    skipped_toc = []
    try:
        doc = word.Documents.Open(
            FileName=docx_path,
            ReadOnly=False,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Revert=False,
        )
        if doc.ReadOnly:
            raise RuntimeError("Document was opened read-only. Close Word or unlock the file before editing.")

        start, end = find_body_region(doc)
        for idx, para in enumerate(doc.Paragraphs, start=1):
            text = clean_text(para.Range.Text)
            if not text:
                continue
            style = style_name_of(para)
            if style.startswith("TOC"):
                if H3_RE.match(text):
                    skipped_toc.append({"paragraph_index": idx, "text": text, "style": style})
                continue
            if not (start <= idx < end):
                continue
            if not H3_RE.match(text):
                continue

            before_old = float(para.Range.ParagraphFormat.SpaceBefore)
            para.Range.ParagraphFormat.SpaceBefore = 12
            before_new = float(para.Range.ParagraphFormat.SpaceBefore)
            changed.append({
                "paragraph_index": idx,
                "text": text,
                "style": style,
                "before_old": before_old,
                "before_new": before_new,
            })

        doc.Save()
        report = {
            "docx": docx_path,
            "body_region_paragraph_index": {"start": start, "end_exclusive": end},
            "changed_count": len(changed),
            "changed": changed,
            "skipped_toc_count": len(skipped_toc),
            "skipped_toc_sample": skipped_toc[:20],
            "notes": [
                "Only body paragraphs matching x.x.x headings were edited.",
                "TOC style paragraphs were skipped.",
                "Only SpaceBefore was changed to 12 pt.",
            ],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(report_path)
    finally:
        if doc is not None:
            doc.Close(SaveChanges=0)
        word.Quit()


if __name__ == "__main__":
    main()
