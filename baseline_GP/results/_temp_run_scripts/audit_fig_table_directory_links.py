from __future__ import annotations

import json
import re
from pathlib import Path

import win32com.client as win32


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "my_report1.docx"
OUT_PATH = (
    ROOT
    / "baseline_GP"
    / "results"
    / "_temp_run_scripts"
    / "fig_table_directory_link_audit.json"
)

WD_ACTIVE_END_PAGE_NUMBER = 3
WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1


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


def main() -> None:
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(str(DOCX_PATH), ReadOnly=True, AddToRecentFiles=False)
        doc.Repaginate()

        paragraphs = []
        for idx, para in enumerate(doc.Paragraphs, start=1):
            text = clean_text(para.Range.Text)
            if not text:
                continue
            paragraphs.append(
                {
                    "idx": idx,
                    "text": text,
                    "page": page_of_range(para.Range),
                    "style": str(para.Range.Style),
                }
            )

        fig_dir_title_idx = next(
            (p["idx"] for p in paragraphs if normalize_key(p["text"]) == "图目录"), None
        )
        tab_dir_title_idx = next(
            (p["idx"] for p in paragraphs if normalize_key(p["text"]) == "表目录"), None
        )
        first_chapter_idx = next(
            (p["idx"] for p in paragraphs if re.match(r"^第一章", p["text"])), None
        )

        if fig_dir_title_idx is None or tab_dir_title_idx is None or first_chapter_idx is None:
            raise RuntimeError(
                f"Cannot locate required anchors: fig_dir={fig_dir_title_idx}, "
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

        fig_caption_by_id = {}
        for p in body_fig_captions:
            cid = extract_caption_id(p["text"], "图")
            fig_caption_by_id.setdefault(cid, []).append(p)

        tab_caption_by_id = {}
        for p in body_tab_captions:
            cid = extract_caption_id(p["text"], "表")
            tab_caption_by_id.setdefault(cid, []).append(p)

        def audit_entries(entries, caption_by_id, prefix):
            rows = []
            for entry in entries:
                cid = extract_caption_id(entry["text"], prefix)
                listed_page_m = re.search(r"(\d+)\s*$", entry["text"])
                listed_page = int(listed_page_m.group(1)) if listed_page_m else None
                matches = caption_by_id.get(cid, [])
                actual_pages = [int(m["page"]) for m in matches]
                rows.append(
                    {
                        "id": cid,
                        "directory_paragraph_idx": entry["idx"],
                        "directory_text": entry["text"],
                        "directory_listed_page": listed_page,
                        "matched_caption_count": len(matches),
                        "caption_pages": actual_pages,
                        "page_match": listed_page in actual_pages if listed_page is not None else False,
                        "caption_texts": [m["text"] for m in matches],
                    }
                )
            return rows

        report = {
            "docx_path": str(DOCX_PATH),
            "anchors": {
                "fig_dir_title_idx": fig_dir_title_idx,
                "tab_dir_title_idx": tab_dir_title_idx,
                "first_chapter_idx": first_chapter_idx,
            },
            "counts": {
                "fig_dir_entries": len(fig_dir_entries),
                "tab_dir_entries": len(tab_dir_entries),
                "body_fig_captions": len(body_fig_captions),
                "body_tab_captions": len(body_tab_captions),
            },
            "fig_directory_audit": audit_entries(fig_dir_entries, fig_caption_by_id, "图"),
            "table_directory_audit": audit_entries(tab_dir_entries, tab_caption_by_id, "表"),
        }
        report["summary"] = {
            "fig_unmatched": [
                r["id"] for r in report["fig_directory_audit"] if r["matched_caption_count"] != 1
            ],
            "table_unmatched": [
                r["id"] for r in report["table_directory_audit"] if r["matched_caption_count"] != 1
            ],
            "fig_page_mismatches": [
                {
                    "id": r["id"],
                    "listed": r["directory_listed_page"],
                    "actual": r["caption_pages"],
                }
                for r in report["fig_directory_audit"]
                if not r["page_match"]
            ],
            "table_page_mismatches": [
                {
                    "id": r["id"],
                    "listed": r["directory_listed_page"],
                    "actual": r["caption_pages"],
                }
                for r in report["table_directory_audit"]
                if not r["page_match"]
            ],
        }

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"wrote: {OUT_PATH}")
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()


if __name__ == "__main__":
    main()
