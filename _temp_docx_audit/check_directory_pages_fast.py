from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import win32com.client  # type: ignore


WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1
WD_STATISTIC_PAGES = 2
WD_FIND_STOP = 0


def clean(text: str) -> str:
    return text.replace("\r", "").replace("\x07", "").replace("\u000b", "").strip()


def norm(text: str) -> str:
    return re.sub(r"\s+", "", clean(text)).replace("．", ".").replace("－", "-")


def adjusted_page(rng) -> int | None:
    try:
        return int(rng.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))
    except Exception:
        return None


@dataclass
class Entry:
    source: str
    text: str
    displayed_page: int
    start: int
    end: int


def parse_entry(text: str) -> tuple[str, int] | None:
    text = clean(text)
    if not text:
        return None
    m = re.search(r"^(.*?)(?:[\t .·。．…_]+)(\d+)\s*$", text)
    if not m:
        return None
    title = clean(m.group(1))
    if not title:
        return None
    return title, int(m.group(2))


def find_text(doc, text: str, start: int = 0, end: int | None = None):
    if end is None:
        end = int(doc.Content.End)
    rng = doc.Range(Start=int(start), End=int(end))
    f = rng.Find
    f.ClearFormatting()
    f.Text = text
    f.Forward = True
    f.Wrap = WD_FIND_STOP
    f.MatchCase = False
    f.MatchWholeWord = False
    f.MatchWildcards = False
    ok = f.Execute()
    if ok:
        return rng
    return None


def find_by_candidates(doc, candidates: list[str], start: int, end: int | None = None):
    best = None
    for text in candidates:
        if not text:
            continue
        rng = find_text(doc, text, start=start, end=end)
        if rng is not None and (best is None or int(rng.Start) < int(best.Start)):
            best = rng
    return best


def collect_toc_entries(doc) -> tuple[list[Entry], int]:
    entries: list[Entry] = []
    max_end = 0
    for i in range(1, doc.TablesOfContents.Count + 1):
        toc = doc.TablesOfContents.Item(i)
        rng = toc.Range
        max_end = max(max_end, int(rng.End))
        for j in range(1, rng.Paragraphs.Count + 1):
            p = rng.Paragraphs.Item(j).Range
            parsed = parse_entry(p.Text)
            if parsed is None:
                continue
            title, page = parsed
            entries.append(Entry(f"title_toc#{i}", title, page, int(p.Start), int(p.End)))
    return entries, max_end


def collect_manual_entries_between(doc, start: int, end: int, source: str, label: str) -> list[Entry]:
    rng = doc.Range(Start=int(start), End=int(end))
    entries: list[Entry] = []
    for i in range(1, rng.Paragraphs.Count + 1):
        p = rng.Paragraphs.Item(i).Range
        parsed = parse_entry(p.Text)
        if parsed is None:
            continue
        title, page = parsed
        if not re.match(rf"^{label}\s*\d", title):
            continue
        entries.append(Entry(source, title, page, int(p.Start), int(p.End)))
    return entries


def get_directory_sections(doc, toc_end: int) -> dict:
    fig_heading = find_text(doc, "图目录", start=toc_end)
    tab_heading = find_text(doc, "表目录", start=toc_end)
    first_body = find_text(doc, "1 绪", start=toc_end)
    if first_body is None:
        first_body = find_text(doc, "1绪", start=toc_end)
    return {
        "figure_heading": None if fig_heading is None else {"start": int(fig_heading.Start), "end": int(fig_heading.End), "page": adjusted_page(fig_heading), "text": clean(fig_heading.Text)},
        "table_heading": None if tab_heading is None else {"start": int(tab_heading.Start), "end": int(tab_heading.End), "page": adjusted_page(tab_heading), "text": clean(tab_heading.Text)},
        "first_body": None if first_body is None else {"start": int(first_body.Start), "end": int(first_body.End), "page": adjusted_page(first_body), "text": clean(first_body.Text)},
    }


def title_candidates(title: str) -> list[str]:
    c = [title]
    # Word Find is literal. Try variants with/without spaces after numbering.
    m = re.match(r"^(\d+(?:\.\d+)*)(.+)$", title)
    if m:
        num, rest = m.group(1), m.group(2).strip()
        c.append(f"{num} {rest}")
        c.append(f"{num}{rest}")
        c.append(rest)
        c.append(re.sub(r"\s+", "", rest))
        c.append(re.sub(r"\s+", " ", rest))
    return list(dict.fromkeys(c))


def caption_prefix(title: str, label: str) -> str:
    m = re.match(rf"^({label}\s*\d+(?:[-－.]\d+)*)", title)
    return m.group(1) if m else title[:20]


def match_entry(doc, entry: Entry, kind: str, body_start: int):
    if kind == "title":
        rng = find_by_candidates(doc, title_candidates(entry.text), start=body_start)
    else:
        label = "图" if kind == "figure" else "表"
        prefix = caption_prefix(entry.text, label)
        candidates = [entry.text, prefix, prefix.replace(" ", ""), re.sub(r"^([图表])", r"\1 ", prefix)]
        rng = find_by_candidates(doc, list(dict.fromkeys(candidates)), start=body_start)
    return {
        "entry": asdict(entry),
        "matched_text": None if rng is None else clean(rng.Paragraphs.Item(1).Range.Text),
        "match_start": None if rng is None else int(rng.Start),
        "actual_page": None if rng is None else adjusted_page(rng),
        "status": "unmatched" if rng is None else ("ok" if adjusted_page(rng) == entry.displayed_page else "mismatch"),
    }


def resolve_body_start(doc, toc_end: int, table_heading_end: int | None) -> int:
    start = table_heading_end if table_heading_end is not None else toc_end
    first_subheading = find_by_candidates(
        doc,
        ["1.1 研究背景及意义", "1.1研究背景及意义", "研究背景及意义"],
        start=start,
    )
    if first_subheading is not None:
        return int(first_subheading.Start)
    first_chapter = find_by_candidates(
        doc,
        ["绪 论", "绪论", "1 绪 论", "1绪论"],
        start=start,
    )
    if first_chapter is not None:
        return int(first_chapter.Start)
    return int(start)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_directory_pages_fast.py input.docx output_dir", file=sys.stderr)
        return 2
    docx = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
        total_pages = int(doc.ComputeStatistics(WD_STATISTIC_PAGES))
        title_entries, toc_end = collect_toc_entries(doc)
        sections = get_directory_sections(doc, toc_end)
        doc_end = int(doc.Content.End)
        fig_entries: list[Entry] = []
        table_entries: list[Entry] = []

        fig_h = sections["figure_heading"]
        tab_h = sections["table_heading"]
        body_h = sections["first_body"]
        if fig_h and tab_h:
            fig_entries = collect_manual_entries_between(doc, fig_h["end"], tab_h["start"], "figure_dir", "图")
        if tab_h and body_h:
            table_entries = collect_manual_entries_between(doc, tab_h["end"], body_h["start"], "table_dir", "表")
        elif tab_h:
            table_entries = collect_manual_entries_between(doc, tab_h["end"], min(tab_h["end"] + 5000, doc_end), "table_dir", "表")

        body_start = resolve_body_start(doc, toc_end, tab_h["end"] if tab_h else None)
        title_search_start = tab_h["end"] if tab_h else toc_end
        comparisons = {
            "title_toc": [match_entry(doc, e, "title", title_search_start) for e in title_entries],
            "figure_toc": [match_entry(doc, e, "figure", body_start) for e in fig_entries],
            "table_toc": [match_entry(doc, e, "table", body_start) for e in table_entries],
        }
        payload = {
            "docx": str(docx),
            "total_pages": total_pages,
            "toc_end": toc_end,
            "sections": sections,
            "body_start": body_start,
            "title_search_start": title_search_start,
            "counts": {
                "title_toc": len(title_entries),
                "figure_toc": len(fig_entries),
                "table_toc": len(table_entries),
            },
            "comparisons": comparisons,
        }
        (out_dir / "directory_page_audit_fast.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = [f"docx\t{docx}", f"total_pages\t{total_pages}", f"counts\t{payload['counts']}", ""]
        for key, rows in comparisons.items():
            lines.append(f"## {key}")
            for row in rows:
                e = row["entry"]
                lines.append(
                    f"{row['status']}\tshown={e['displayed_page']}\tactual={row['actual_page']}\t{e['text']}\tmatch={row['matched_text']}"
                )
            lines.append("")
        (out_dir / "directory_page_audit_fast.tsv").write_text("\n".join(lines), encoding="utf-8")
        print(json.dumps({
            "docx": str(docx),
            "total_pages": total_pages,
            "counts": payload["counts"],
            "sections": sections,
            "out_dir": str(out_dir),
        }, ensure_ascii=False, indent=2))
    finally:
        if doc is not None:
            doc.Close(False)
        app.Quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
