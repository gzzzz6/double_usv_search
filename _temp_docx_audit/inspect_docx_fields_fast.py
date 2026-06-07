from __future__ import annotations

import json
from pathlib import Path
import sys

import win32com.client  # type: ignore

WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1
WD_STATISTIC_PAGES = 2


def clean(text: str) -> str:
    return text.replace("\r", "\n").replace("\x07", "").strip()


def page(rng) -> int | None:
    try:
        return int(rng.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))
    except Exception:
        return None


def main() -> int:
    docx = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    app = win32com.client.DispatchEx("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    doc = None
    try:
        doc = app.Documents.Open(
            FileName=str(docx),
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Revert=True,
        )
        doc.Repaginate()
        payload = {
            "pages": int(doc.ComputeStatistics(WD_STATISTIC_PAGES)),
            "toc_count": int(doc.TablesOfContents.Count),
            "tof_count": int(doc.TablesOfFigures.Count),
            "tocs": [],
            "tofs": [],
        }
        for i in range(1, doc.TablesOfContents.Count + 1):
            rng = doc.TablesOfContents.Item(i).Range
            paras = []
            for j in range(1, min(rng.Paragraphs.Count, 20) + 1):
                p = rng.Paragraphs.Item(j).Range
                paras.append({"text": clean(p.Text), "page": page(p), "start": int(p.Start), "end": int(p.End)})
            payload["tocs"].append({"index": i, "page": page(rng), "start": int(rng.Start), "end": int(rng.End), "paras": paras})
        for i in range(1, doc.TablesOfFigures.Count + 1):
            tof = doc.TablesOfFigures.Item(i)
            rng = tof.Range
            paras = []
            for j in range(1, min(rng.Paragraphs.Count, 30) + 1):
                p = rng.Paragraphs.Item(j).Range
                paras.append({"text": clean(p.Text), "page": page(p), "start": int(p.Start), "end": int(p.End)})
            caption = ""
            try:
                caption = str(tof.Caption)
            except Exception:
                pass
            payload["tofs"].append({"index": i, "caption": caption, "page": page(rng), "start": int(rng.Start), "end": int(rng.End), "paras": paras})
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:5000])
    finally:
        if doc is not None:
            doc.Close(False)
        app.Quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
