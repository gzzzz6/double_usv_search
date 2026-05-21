from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import win32com.client


WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1


def clean_text(text: str) -> str:
    return (text or "").replace("\r", "").replace("\x07", "").strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def main() -> int:
    docx_path = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()
    if not docx_path.exists():
        raise FileNotFoundError(docx_path)

    caption_pattern = re.compile(r"^表\s*\d+[-.．]\d+(?:\s*续)?(?:\s+|$)")
    records: list[dict] = []

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
        for i in range(1, doc.Paragraphs.Count + 1):
            para = doc.Paragraphs(i)
            text = clean_text(para.Range.Text)
            compact = compact_text(text)
            if not text:
                continue
            if not in_body and compact == "1绪论":
                in_body = True
            if in_body and compact in {"参考文献", "附录"}:
                break
            if in_body and caption_pattern.match(text):
                records.append(
                    {
                        "paragraph_index": i,
                        "caption": text,
                        "page": int(para.Range.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER)),
                    }
                )
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()

    out = {
        "docx": str(docx_path),
        "count": len(records),
        "records": records,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
