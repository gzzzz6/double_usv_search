from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import win32com.client as win32


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "my_report1.docx"
OUT_REPORT = (
    ROOT
    / "baseline_GP"
    / "results"
    / "_temp_run_scripts"
    / "fig_table_directory_link_rebuild_report.json"
)

WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1
WD_UNDERLINE_NONE = 0
WD_COLOR_AUTOMATIC = -16777216


def clean_text(text: str) -> str:
    return text.replace("\r", "").replace("\x07", "").strip()


def normalize_key(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("－", "-").replace("—", "-").replace("–", "-")
    return text


def extract_caption_id(text: str, prefix: str) -> str | None:
    text = clean_text(text).lstrip("/")
    pattern = rf"^{prefix}\s*([0-9]+(?:[-.－—–][0-9]+)*)"
    m = re.match(pattern, text)
    if not m:
        return None
    return m.group(1).replace(".", "-").replace("－", "-").replace("—", "-").replace("–", "-")


def looks_like_dir_entry(text: str, prefix: str) -> bool:
    return extract_caption_id(text, prefix) is not None and re.search(r"\d+\s*$", text) is not None


def page_of_range(rng) -> int:
    return int(rng.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))


def text_range(para):
    rng = para.Range.Duplicate
    if rng.End > rng.Start:
        rng.End -= 1
    return rng


def bookmark_name(prefix: str, cid: str) -> str:
    return f"{prefix}_{cid.replace('-', '_').replace('.', '_')}"


def target_display_text(caption_text: str, prefix: str) -> str:
    text = clean_text(caption_text).lstrip("/")
    text = text.replace("－", "-").replace("—", "-").replace("–", "-")
    pattern = rf"^({prefix})\s*([0-9]+(?:[-.][0-9]+)*)\s*"
    return re.sub(pattern, lambda m: f"{m.group(1)}{m.group(2)} ", text)


def collect_paragraphs(doc):
    rows = []
    for idx, para in enumerate(doc.Paragraphs, start=1):
        text = clean_text(para.Range.Text)
        if not text:
            continue
        rows.append(
            {
                "idx": idx,
                "para": para,
                "text": text,
                "start": text_range(para).Start,
                "end": text_range(para).End,
                "page": page_of_range(para.Range),
            }
        )
    return rows


def build_operations(doc):
    paragraphs = collect_paragraphs(doc)
    fig_dir_title_idx = next((p["idx"] for p in paragraphs if normalize_key(p["text"]) == "图目录"), None)
    tab_dir_title_idx = next((p["idx"] for p in paragraphs if normalize_key(p["text"]) == "表目录"), None)
    first_chapter_idx = next((p["idx"] for p in paragraphs if re.match(r"^第一章", p["text"])), None)
    if fig_dir_title_idx is None or tab_dir_title_idx is None or first_chapter_idx is None:
        raise RuntimeError(
            f"Cannot locate anchors: fig={fig_dir_title_idx}, tab={tab_dir_title_idx}, chapter={first_chapter_idx}"
        )

    fig_dir_entries = [
        p
        for p in paragraphs
        if fig_dir_title_idx < p["idx"] < tab_dir_title_idx and looks_like_dir_entry(p["text"], "图")
    ]
    tab_dir_entries = [
        p
        for p in paragraphs
        if tab_dir_title_idx < p["idx"] < first_chapter_idx and looks_like_dir_entry(p["text"], "表")
    ]
    body_figs = [
        p
        for p in paragraphs
        if p["idx"] > first_chapter_idx and extract_caption_id(p["text"], "图") is not None
    ]
    body_tabs = [
        p
        for p in paragraphs
        if p["idx"] > first_chapter_idx and extract_caption_id(p["text"], "表") is not None
    ]

    def by_id(rows, prefix):
        result = {}
        for row in rows:
            result.setdefault(extract_caption_id(row["text"], prefix), []).append(row)
        return result

    fig_by_id = by_id(body_figs, "图")
    tab_by_id = by_id(body_tabs, "表")

    operations = []
    skipped = []

    for prefix, bm_prefix, entries, captions in [
        ("图", "fig", fig_dir_entries, fig_by_id),
        ("表", "tab", tab_dir_entries, tab_by_id),
    ]:
        for entry in entries:
            cid = extract_caption_id(entry["text"], prefix)
            matches = captions.get(cid, [])
            if len(matches) != 1:
                skipped.append(
                    {
                        "id": cid,
                        "prefix": prefix,
                        "reason": f"matched_caption_count={len(matches)}",
                        "directory_text": entry["text"],
                    }
                )
                continue
            caption = matches[0]
            bm_name = bookmark_name(bm_prefix, cid)
            if doc.Bookmarks.Exists(bm_name):
                doc.Bookmarks(bm_name).Delete()
            doc.Bookmarks.Add(bm_name, doc.Range(caption["start"], caption["end"]))
            display = target_display_text(caption["text"], prefix)
            page = page_of_range(caption["para"].Range)
            visible = f"{display}\t{page}"
            operations.append(
                {
                    "id": cid,
                    "prefix": prefix,
                    "bookmark": bm_name,
                    "start": entry["start"],
                    "end": entry["end"],
                    "old_text": entry["text"],
                    "new_text": visible,
                    "caption_text": caption["text"],
                    "page": page,
                }
            )
    return operations, skipped


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ROOT / f"my_report1_backup_before_rebuild_fig_table_dir_links_{timestamp}.docx"
    shutil.copy2(DOCX_PATH, backup_path)

    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(str(DOCX_PATH), ReadOnly=False, AddToRecentFiles=False)
        doc.Repaginate()
        operations, skipped = build_operations(doc)

        for op in sorted(operations, key=lambda item: item["start"], reverse=True):
            rng = doc.Range(op["start"], op["end"])
            rng.Text = op["new_text"]
            link_rng = doc.Range(op["start"], op["start"] + len(op["new_text"]))
            doc.Hyperlinks.Add(
                Anchor=link_rng,
                Address="",
                SubAddress=op["bookmark"],
                TextToDisplay=op["new_text"],
            )
            link_rng = doc.Range(op["start"], op["start"] + len(op["new_text"]))
            link_rng.Font.Color = WD_COLOR_AUTOMATIC
            link_rng.Font.Underline = WD_UNDERLINE_NONE

        doc.Repaginate()
        doc.Save()

        report = {
            "docx_path": str(DOCX_PATH),
            "backup_path": str(backup_path),
            "operations": operations,
            "skipped": skipped,
            "summary": {
                "linked": len(operations),
                "skipped": skipped,
                "fig_linked": sum(1 for op in operations if op["prefix"] == "图"),
                "table_linked": sum(1 for op in operations if op["prefix"] == "表"),
            },
        }
        OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"backup: {backup_path}")
        print(f"report: {OUT_REPORT}")
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()


if __name__ == "__main__":
    main()
