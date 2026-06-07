from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import win32com.client  # type: ignore


WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1
WD_STATISTIC_PAGES = 2


@dataclass
class ParaInfo:
    index: int
    text: str
    style: str
    outline_level: int | None
    page: int | None
    start: int
    end: int


@dataclass
class TocEntry:
    source: str
    text: str
    displayed_page: int | None
    range_page: int | None
    start: int
    end: int


def clean_text(text: str) -> str:
    return (
        text.replace("\r", "")
        .replace("\x07", "")
        .replace("\u000b", "")
        .strip()
    )


def normalize_title(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("．", ".").replace("－", "-")
    return text


def parse_toc_entry(raw: str) -> tuple[str, int | None] | None:
    text = clean_text(raw)
    if not text:
        return None
    # TOC entries usually end in a displayed page number after tabs/dot leaders.
    m = re.search(r"^(.*?)(?:[\t .·。．…_]+)(\d+)\s*$", text)
    if not m:
        return None
    title = clean_text(m.group(1))
    if not title:
        return None
    return title, int(m.group(2))


def adjusted_page(range_obj) -> int | None:
    try:
        value = int(range_obj.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))
        return value
    except Exception:
        return None


def iter_paragraph_infos(doc) -> list[ParaInfo]:
    infos: list[ParaInfo] = []
    paragraphs = doc.Paragraphs
    for i in range(1, paragraphs.Count + 1):
        p = paragraphs.Item(i)
        rng = p.Range
        text = clean_text(rng.Text)
        try:
            style = str(p.Style.NameLocal)
        except Exception:
            style = str(p.Style)
        try:
            outline_level = int(p.OutlineLevel)
        except Exception:
            outline_level = None
        infos.append(
            ParaInfo(
                index=i,
                text=text,
                style=style,
                outline_level=outline_level,
                page=adjusted_page(rng),
                start=int(rng.Start),
                end=int(rng.End),
            )
        )
    return infos


def collect_field_ranges(doc) -> list[dict]:
    rows: list[dict] = []
    try:
        for i in range(1, doc.TablesOfContents.Count + 1):
            obj = doc.TablesOfContents.Item(i)
            rng = obj.Range
            rows.append(
                {
                    "kind": "TablesOfContents",
                    "index": i,
                    "page": adjusted_page(rng),
                    "start": int(rng.Start),
                    "end": int(rng.End),
                    "text_preview": clean_text(rng.Text)[:800],
                }
            )
    except Exception as exc:
        rows.append({"kind": "TablesOfContents", "error": repr(exc)})
    try:
        for i in range(1, doc.TablesOfFigures.Count + 1):
            obj = doc.TablesOfFigures.Item(i)
            rng = obj.Range
            caption = ""
            try:
                caption = str(obj.Caption)
            except Exception:
                pass
            rows.append(
                {
                    "kind": "TablesOfFigures",
                    "index": i,
                    "caption": caption,
                    "page": adjusted_page(rng),
                    "start": int(rng.Start),
                    "end": int(rng.End),
                    "text_preview": clean_text(rng.Text)[:800],
                }
            )
    except Exception as exc:
        rows.append({"kind": "TablesOfFigures", "error": repr(exc)})
    return rows


def collect_entries_from_range(doc, rng, source: str) -> list[TocEntry]:
    entries: list[TocEntry] = []
    for i in range(1, rng.Paragraphs.Count + 1):
        p = rng.Paragraphs.Item(i)
        parsed = parse_toc_entry(p.Range.Text)
        if parsed is None:
            continue
        title, page = parsed
        entries.append(
            TocEntry(
                source=source,
                text=title,
                displayed_page=page,
                range_page=adjusted_page(p.Range),
                start=int(p.Range.Start),
                end=int(p.Range.End),
            )
        )
    return entries


def collect_directory_entries(doc, field_ranges: list[dict], paras: list[ParaInfo]) -> dict[str, list[TocEntry]]:
    grouped: dict[str, list[TocEntry]] = {"title_toc": [], "figure_toc": [], "table_toc": []}

    for item in field_ranges:
        if "start" not in item or "end" not in item:
            continue
        rng = doc.Range(Start=int(item["start"]), End=int(item["end"]))
        entries = collect_entries_from_range(doc, rng, f"{item.get('kind')}#{item.get('index')}")
        preview = item.get("text_preview", "")
        if item.get("kind") == "TablesOfContents":
            grouped["title_toc"].extend(entries)
        elif item.get("kind") == "TablesOfFigures":
            # Infer figure/table from visible entries. Chinese Word labels often show as text even
            # when the COM Caption property is blank.
            sample = "\n".join(e.text for e in entries[:8]) + "\n" + preview
            if re.search(r"表\s*\d", sample):
                grouped["table_toc"].extend(entries)
            elif re.search(r"图\s*\d", sample):
                grouped["figure_toc"].extend(entries)

    # Fallback for manually-created lists or when TablesOfFigures is not exposed.
    if not grouped["figure_toc"] or not grouped["table_toc"]:
        heading_positions: dict[str, int] = {}
        for p in paras:
            nt = normalize_title(p.text)
            if nt in {"目录", "图目录", "表目录"}:
                heading_positions[nt] = p.index
        sorted_heads = sorted((idx, name) for name, idx in heading_positions.items())
        for idx, name in sorted_heads:
            next_idx = min((j for j, _ in sorted_heads if j > idx), default=min(idx + 80, len(paras) + 1))
            if name not in {"图目录", "表目录"}:
                continue
            target_key = "figure_toc" if name == "图目录" else "table_toc"
            if grouped[target_key]:
                continue
            for p in paras[idx: next_idx - 1]:
                parsed = parse_toc_entry(p.text)
                if parsed is None:
                    continue
                title, page = parsed
                if name == "图目录" and not re.search(r"图\s*\d", title):
                    continue
                if name == "表目录" and not re.search(r"表\s*\d", title):
                    continue
                grouped[target_key].append(
                    TocEntry(
                        source=f"manual_after_{name}",
                        text=title,
                        displayed_page=page,
                        range_page=p.page,
                        start=p.start,
                        end=p.end,
                    )
                )

    return grouped


def candidate_heading(paras: list[ParaInfo], entry: TocEntry) -> ParaInfo | None:
    norm_entry = normalize_title(entry.text)
    # Remove a few common non-heading directory entries if present.
    candidates = []
    for p in paras:
        if not p.text:
            continue
        norm_p = normalize_title(p.text)
        if norm_p == norm_entry:
            candidates.append(p)
    if candidates:
        # Prefer actual body headings/captions after the directory range, not the TOC entry itself.
        body = [p for p in candidates if p.start > entry.end]
        if body:
            return body[0]
        return candidates[0]

    # Some TOC text may include extra spaces or line wrapping; use prefix match cautiously.
    if len(norm_entry) >= 6:
        for p in paras:
            norm_p = normalize_title(p.text)
            if p.start > entry.end and (norm_p.startswith(norm_entry) or norm_entry.startswith(norm_p)):
                return p
    return None


def candidate_caption(paras: list[ParaInfo], entry: TocEntry, label: str) -> ParaInfo | None:
    norm_entry = normalize_title(entry.text)
    # Match by full caption first.
    matches = [
        p for p in paras
        if p.start > entry.end and normalize_title(p.text) == norm_entry
    ]
    if matches:
        return matches[0]

    # Then match by "图 5-3" / "表5-1" label prefix.
    label_match = re.match(rf"({label}\s*\d+(?:[-－.]\d+)*)", entry.text)
    if label_match:
        prefix = normalize_title(label_match.group(1))
        for p in paras:
            if p.start <= entry.end:
                continue
            norm_p = normalize_title(p.text)
            if norm_p.startswith(prefix):
                return p
    return candidate_heading(paras, entry)


def compare_entries(paras: list[ParaInfo], entries: list[TocEntry], kind: str) -> list[dict]:
    rows = []
    for e in entries:
        if kind == "figure":
            target = candidate_caption(paras, e, "图")
        elif kind == "table":
            target = candidate_caption(paras, e, "表")
        else:
            target = candidate_heading(paras, e)
        actual = target.page if target is not None else None
        rows.append(
            {
                "entry": asdict(e),
                "matched_text": target.text if target is not None else None,
                "matched_para_index": target.index if target is not None else None,
                "actual_page": actual,
                "status": (
                    "unmatched"
                    if target is None
                    else "ok"
                    if actual == e.displayed_page
                    else "mismatch"
                ),
            }
        )
    return rows


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_directory_pages.py input.docx output_dir", file=sys.stderr)
        return 2
    docx_path = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    app = win32com.client.DispatchEx("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    doc = None
    try:
        doc = app.Documents.Open(
            FileName=str(docx_path),
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Revert=True,
        )
        doc.Repaginate()
        total_pages = int(doc.ComputeStatistics(WD_STATISTIC_PAGES))
        paras = iter_paragraph_infos(doc)
        field_ranges = collect_field_ranges(doc)
        grouped = collect_directory_entries(doc, field_ranges, paras)

        comparisons = {
            "title_toc": compare_entries(paras, grouped["title_toc"], "heading"),
            "figure_toc": compare_entries(paras, grouped["figure_toc"], "figure"),
            "table_toc": compare_entries(paras, grouped["table_toc"], "table"),
        }
        payload = {
            "docx": str(docx_path),
            "total_pages": total_pages,
            "field_ranges": field_ranges,
            "directory_counts": {k: len(v) for k, v in grouped.items()},
            "comparisons": comparisons,
            "paragraph_samples": [asdict(p) for p in paras[:80]],
        }
        (out_dir / "directory_page_audit.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary_lines = [
            f"docx: {docx_path}",
            f"total_pages: {total_pages}",
            f"counts: {payload['directory_counts']}",
            "",
        ]
        for key, rows in comparisons.items():
            summary_lines.append(f"## {key}")
            for row in rows:
                e = row["entry"]
                marker = row["status"].upper()
                summary_lines.append(
                    f"{marker}\tshown={e['displayed_page']}\tactual={row['actual_page']}\t"
                    f"{e['text']}\tmatch={row['matched_text']}"
                )
            summary_lines.append("")
        (out_dir / "directory_page_audit.tsv").write_text(
            "\n".join(summary_lines),
            encoding="utf-8",
        )
        print(json.dumps({
            "docx": str(docx_path),
            "total_pages": total_pages,
            "directory_counts": payload["directory_counts"],
            "out_dir": str(out_dir),
        }, ensure_ascii=False, indent=2))
    finally:
        if doc is not None:
            doc.Close(False)
        app.Quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
