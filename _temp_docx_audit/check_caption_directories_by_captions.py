import json
import re
import sys
from pathlib import Path

import win32com.client


WD_ACTIVE_END_PAGE_NUMBER = 1
WD_COLLAPSE_START = 1


def clean(s):
    return (s or "").replace("\r", "").replace("\x07", "").strip()


def norm(s):
    return re.sub(r"\s+", "", clean(s))


def page_of_range(rng):
    return int(rng.Information(WD_ACTIVE_END_PAGE_NUMBER))


def find_text(doc, text, start=0, end=None):
    if end is None:
        end = doc.Content.End
    rng = doc.Range(Start=start, End=end)
    f = rng.Find
    f.ClearFormatting()
    f.Text = text
    f.Forward = True
    f.Wrap = 0
    if f.Execute():
        return {"start": int(rng.Start), "end": int(rng.End), "page": page_of_range(rng), "text": clean(rng.Text)}
    return None


def parse_lines_in_range(doc, start, end, source):
    rng = doc.Range(Start=start, End=end)
    entries = []
    for raw in rng.Text.split("\r"):
        line = clean(raw)
        if not line:
            continue
        m = re.match(r"^(图|表)\s*(\d+[-－]\d+)\s+(.+?)\s+(\d+)$", line)
        if not m:
            continue
        prefix, num, title, page = m.groups()
        entries.append(
            {
                "source": source,
                "kind": "figure" if prefix == "图" else "table",
                "label": f"{prefix}{num.replace('－', '-')}",
                "text": f"{prefix}{num.replace('－', '-')} {title.strip()}",
                "displayed_page": int(page),
            }
        )
    return entries


def extract_captions(doc, body_start):
    captions = []
    for p in doc.Paragraphs:
        try:
            if int(p.Range.Start) < body_start:
                continue
            text = clean(p.Range.Text)
            if not text:
                continue
            m = re.match(r"^(图|表)\s*(\d+[-－]\d+)\s+(.+)$", text)
            if not m:
                continue
            prefix, num, title = m.groups()
            captions.append(
                {
                    "kind": "figure" if prefix == "图" else "table",
                    "label": f"{prefix}{num.replace('－', '-')}",
                    "text": f"{prefix}{num.replace('－', '-')} {title.strip()}",
                    "page": page_of_range(p.Range),
                    "start": int(p.Range.Start),
                    "norm": norm(f"{prefix}{num.replace('－', '-')} {title.strip()}"),
                }
            )
        except Exception:
            continue
    return captions


def compare(entries, captions, kind):
    out = []
    by_label = {}
    for c in captions:
        if c["kind"] == kind:
            by_label.setdefault(c["label"], []).append(c)
    for e in [x for x in entries if x["kind"] == kind]:
        candidates = by_label.get(e["label"], [])
        exact = [c for c in candidates if c["norm"] == norm(e["text"])]
        c = exact[0] if exact else (candidates[0] if candidates else None)
        if c is None:
            out.append({"entry": e, "status": "unmatched", "actual_page": None, "matched_caption": None})
            continue
        status = "ok" if e["displayed_page"] == c["page"] else "mismatch"
        out.append({"entry": e, "status": status, "actual_page": c["page"], "matched_caption": c["text"]})
    return out


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_caption_directories_by_captions.py DOCX OUT_JSON")
    docx = str(Path(sys.argv[1]).resolve())
    out_json = Path(sys.argv[2]).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    app = win32com.client.DispatchEx("Word.Application")
    app.Visible = False
    doc = None
    try:
        doc = app.Documents.Open(docx, ReadOnly=True, AddToRecentFiles=False)
        doc.Repaginate()

        toc_end = int(doc.TablesOfContents(1).Range.End) if doc.TablesOfContents.Count >= 1 else 0
        figure_heading = find_text(doc, "图目录", toc_end)
        table_heading = find_text(doc, "表目录", figure_heading["end"] if figure_heading else toc_end)
        body_heading = find_text(doc, "第一章", table_heading["end"] if table_heading else toc_end)
        if body_heading is None:
            body_heading = find_text(doc, "1.1 研究背景及意义", table_heading["end"] if table_heading else toc_end)
        body_start = body_heading["start"] if body_heading else toc_end

        entries = []
        if figure_heading and table_heading:
            entries.extend(parse_lines_in_range(doc, figure_heading["end"], table_heading["start"], "figure_toc"))
        if table_heading and body_heading:
            entries.extend(parse_lines_in_range(doc, table_heading["end"], body_heading["start"], "table_toc"))

        captions = extract_captions(doc, body_start)
        comparisons = {
            "figure_toc": compare(entries, captions, "figure"),
            "table_toc": compare(entries, captions, "table"),
        }
        status_counts = {}
        for key, rows in comparisons.items():
            status_counts[key] = {}
            for r in rows:
                status_counts[key][r["status"]] = status_counts[key].get(r["status"], 0) + 1

        payload = {
            "docx": docx,
            "total_pages": int(doc.ComputeStatistics(2)),
            "body_start": body_start,
            "entry_count": len(entries),
            "caption_count": len(captions),
            "status_counts": status_counts,
            "comparisons": comparisons,
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: payload[k] for k in ["total_pages", "entry_count", "caption_count", "status_counts"]}, ensure_ascii=False, indent=2))
    finally:
        if doc is not None:
            doc.Close(SaveChanges=False)
        app.Quit()


if __name__ == "__main__":
    main()
