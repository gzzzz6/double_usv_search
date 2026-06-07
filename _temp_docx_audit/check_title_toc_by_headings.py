import json
import re
import sys
from pathlib import Path

import win32com.client


WD_ACTIVE_END_PAGE_NUMBER = 1
WD_FIELD_TOC = 13
WD_COLLAPSE_START = 1


def norm_text(s):
    s = (s or "").replace("\r", "").replace("\x07", "")
    s = re.sub(r"\s+", "", s)
    return s


def strip_prefix(s):
    s = norm_text(s)
    s = re.sub(r"^第?[一二三四五六七八九十]+章", "", s)
    s = re.sub(r"^\d+(?:\.\d+)*", "", s)
    return s


def page_of_range(rng):
    return int(rng.Information(WD_ACTIVE_END_PAGE_NUMBER))


def parse_toc_entries(doc):
    if doc.TablesOfContents.Count < 1:
        return []
    toc = doc.TablesOfContents(1)
    text = toc.Range.Text
    entries = []
    for raw in text.split("\r"):
        line = raw.replace("\x07", "").strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) < 2:
            continue
        try:
            page = int(parts[-1])
        except ValueError:
            continue
        title = " ".join(parts[:-1]).strip()
        entries.append({"text": title, "displayed_page": page})
    return entries


def extract_headings(doc, start_after):
    headings = []
    for p in doc.Paragraphs:
        try:
            level = int(p.OutlineLevel)
            if not (1 <= level <= 9):
                continue
            if int(p.Range.Start) < start_after:
                continue
            text = p.Range.Text.replace("\r", "").replace("\x07", "").strip()
            if not text:
                continue
            # Exclude directory headings themselves if any remain after the TOC range.
            if text in {"图目录", "表目录", "目 录", "目录"}:
                continue
            headings.append(
                {
                    "text": text,
                    "page": page_of_range(p.Range),
                    "level": level,
                    "start": int(p.Range.Start),
                    "norm": norm_text(text),
                    "tail": strip_prefix(text),
                }
            )
        except Exception:
            continue
    return headings


def match_entry(entry, headings, used):
    e_norm = norm_text(entry["text"])
    e_tail = strip_prefix(entry["text"])

    best = None
    for i, h in enumerate(headings):
        if i in used:
            continue
        h_norm = h["norm"]
        h_tail = h["tail"]
        score = 0
        if e_norm == h_norm:
            score = 100
        elif e_tail and e_tail == h_tail:
            score = 90
        elif e_tail and (e_tail in h_norm or h_tail in e_norm):
            score = 75
        elif e_norm in h_norm or h_norm in e_norm:
            score = 70
        if score and (best is None or score > best[0]):
            best = (score, i, h)

    if best is None:
        return {"entry": entry, "status": "unmatched", "actual_page": None, "matched_heading": None}

    used.add(best[1])
    h = best[2]
    status = "ok" if int(entry["displayed_page"]) == int(h["page"]) else "mismatch"
    return {
        "entry": entry,
        "status": status,
        "actual_page": h["page"],
        "matched_heading": h["text"],
        "heading_level": h["level"],
        "match_score": best[0],
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_title_toc_by_headings.py DOCX OUT_JSON")
    docx = str(Path(sys.argv[1]).resolve())
    out_json = Path(sys.argv[2]).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    app = win32com.client.DispatchEx("Word.Application")
    app.Visible = False
    doc = None
    try:
        doc = app.Documents.Open(docx, ReadOnly=True, AddToRecentFiles=False)
        doc.Repaginate()
        toc_entries = parse_toc_entries(doc)
        toc_end = int(doc.TablesOfContents(1).Range.End) if doc.TablesOfContents.Count >= 1 else 0
        headings = extract_headings(doc, toc_end)
        used = set()
        comparisons = [match_entry(e, headings, used) for e in toc_entries]
        status_counts = {}
        for c in comparisons:
            status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
        payload = {
            "docx": docx,
            "total_pages": int(doc.ComputeStatistics(2)),
            "toc_entries": len(toc_entries),
            "heading_candidates": len(headings),
            "status_counts": status_counts,
            "comparisons": comparisons,
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: payload[k] for k in ["total_pages", "toc_entries", "heading_candidates", "status_counts"]}, ensure_ascii=False, indent=2))
    finally:
        if doc is not None:
            doc.Close(SaveChanges=False)
        app.Quit()


if __name__ == "__main__":
    main()
