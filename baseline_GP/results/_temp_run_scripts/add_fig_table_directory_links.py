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
    / "fig_table_directory_link_update_report.json"
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


def bookmark_name(prefix: str, cid: str) -> str:
    safe = cid.replace("-", "_").replace(".", "_")
    return f"{prefix}_{safe}"


def target_display_text(caption_text: str, prefix: str) -> str:
    text = clean_text(caption_text).lstrip("/")
    if prefix == "图":
        text = re.sub(r"^(图\s*[0-9]+(?:[-.－—–][0-9]+)*)\s*", lambda m: m.group(1).replace(" ", "") + " ", text)
    elif prefix == "表":
        text = re.sub(r"^(表\s*[0-9]+(?:[-.－—–][0-9]+)*)\s*", lambda m: m.group(1).replace(" ", "") + " ", text)
    text = text.replace("－", "-").replace("—", "-").replace("–", "-")
    return text


def paragraph_text_range(para):
    rng = para.Range.Duplicate
    if rng.End > rng.Start:
        rng.End -= 1
    return rng


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
                "page": page_of_range(para.Range),
                "style": str(para.Range.Style),
            }
        )
    return rows


def build_index(doc):
    paragraphs = collect_paragraphs(doc)
    fig_dir_title_idx = next((p["idx"] for p in paragraphs if normalize_key(p["text"]) == "图目录"), None)
    tab_dir_title_idx = next((p["idx"] for p in paragraphs if normalize_key(p["text"]) == "表目录"), None)
    first_chapter_idx = next((p["idx"] for p in paragraphs if re.match(r"^第一章", p["text"])), None)

    if fig_dir_title_idx is None or tab_dir_title_idx is None or first_chapter_idx is None:
        raise RuntimeError(
            f"Cannot locate anchors: fig_dir={fig_dir_title_idx}, "
            f"tab_dir={tab_dir_title_idx}, first_chapter={first_chapter_idx}"
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

    body_fig_captions = [
        p
        for p in paragraphs
        if p["idx"] > first_chapter_idx and extract_caption_id(p["text"], "图") is not None
    ]
    body_tab_captions = [
        p
        for p in paragraphs
        if p["idx"] > first_chapter_idx and extract_caption_id(p["text"], "表") is not None
    ]

    def by_id(items, prefix):
        result = {}
        for item in items:
            cid = extract_caption_id(item["text"], prefix)
            result.setdefault(cid, []).append(item)
        return result

    return {
        "fig_dir_entries": fig_dir_entries,
        "tab_dir_entries": tab_dir_entries,
        "fig_caption_by_id": by_id(body_fig_captions, "图"),
        "tab_caption_by_id": by_id(body_tab_captions, "表"),
    }


def add_or_replace_bookmark(doc, name: str, para) -> None:
    if doc.Bookmarks.Exists(name):
        doc.Bookmarks(name).Delete()
    rng = paragraph_text_range(para)
    doc.Bookmarks.Add(name, rng)


def replace_directory_entry_with_link(doc, entry_para, display_text: str, page: int, bm_name: str) -> None:
    visible = f"{display_text}\t{page}"
    anchor = paragraph_text_range(entry_para)
    doc.Hyperlinks.Add(Anchor=anchor, Address="", SubAddress=bm_name, TextToDisplay=visible)

    # Keep the directory visually consistent with the original black TOC-style text.
    rng = paragraph_text_range(entry_para)
    rng.Font.Color = WD_COLOR_AUTOMATIC
    rng.Font.Underline = WD_UNDERLINE_NONE


def process_entries(doc, entries, caption_by_id, prefix: str, bm_prefix: str):
    rows = []
    for entry in entries:
        cid = extract_caption_id(entry["text"], prefix)
        matches = caption_by_id.get(cid, [])
        if len(matches) != 1:
            rows.append(
                {
                    "id": cid,
                    "status": "skipped",
                    "reason": f"matched_caption_count={len(matches)}",
                    "directory_text": entry["text"],
                }
            )
            continue

        caption = matches[0]
        bm_name = bookmark_name(bm_prefix, cid)
        add_or_replace_bookmark(doc, bm_name, caption["para"])
        display = target_display_text(caption["text"], prefix)
        page = page_of_range(caption["para"].Range)
        old_text = entry["text"]
        replace_directory_entry_with_link(doc, entry["para"], display, page, bm_name)
        rows.append(
            {
                "id": cid,
                "status": "linked",
                "bookmark": bm_name,
                "page": page,
                "old_directory_text": old_text,
                "new_directory_text": f"{display}\t{page}",
                "caption_text": caption["text"],
            }
        )
    return rows


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ROOT / f"my_report1_backup_before_fig_table_dir_links_{timestamp}.docx"
    shutil.copy2(DOCX_PATH, backup_path)

    word = win32.Dispatch("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(str(DOCX_PATH), ReadOnly=False, AddToRecentFiles=False)
        doc.Repaginate()
        index = build_index(doc)

        fig_results = process_entries(
            doc,
            index["fig_dir_entries"],
            index["fig_caption_by_id"],
            "图",
            "fig",
        )
        tab_results = process_entries(
            doc,
            index["tab_dir_entries"],
            index["tab_caption_by_id"],
            "表",
            "tab",
        )

        doc.Repaginate()
        doc.Save()

        report = {
            "docx_path": str(DOCX_PATH),
            "backup_path": str(backup_path),
            "fig_results": fig_results,
            "table_results": tab_results,
            "summary": {
                "fig_linked": sum(1 for r in fig_results if r["status"] == "linked"),
                "fig_skipped": [r for r in fig_results if r["status"] != "linked"],
                "table_linked": sum(1 for r in tab_results if r["status"] == "linked"),
                "table_skipped": [r for r in tab_results if r["status"] != "linked"],
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
