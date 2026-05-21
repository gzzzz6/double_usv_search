"""
Fix 图目录 and 表目录 in my_report2.docx: add Ctrl+click hyperlinks.

Approach:
- Wrap existing w:r runs in each directory entry in a w:hyperlink
- Each hyperlink points to the bookmark on the corresponding body caption
- Add bookmarks to body captions that lack them
- Preserve all formatting, tab leaders, and page numbers
"""
from __future__ import annotations

import re
import copy
import shutil
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

DOC = Path(r"F:\pythonprojects\my_report2.docx")
BACKUP = Path(r"F:\pythonprojects\my_report2_backup.docx")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_id(text: str) -> str | None:
    """Extract canonical figure/table ID, e.g. '图2-1' or '表5-1'."""
    m = re.match(r'(图|表)\s*(\d+)[-.](\d+)', text)
    return f"{m.group(1)}{m.group(2)}-{m.group(3)}" if m else None


def _add_bookmark(para, name: str):
    """Add bookmarkStart/End around the paragraph content."""
    bm_id = abs(hash(name)) % 100000
    bm_s = OxmlElement("w:bookmarkStart")
    bm_s.set(qn("w:id"), str(bm_id))
    bm_s.set(qn("w:name"), name)
    bm_e = OxmlElement("w:bookmarkEnd")
    bm_e.set(qn("w:id"), str(bm_id))
    para._element.insert(0, bm_s)
    para._element.append(bm_e)


def _wrap_runs_in_hyperlink(para, anchor: str):
    """Wrap all w:r children of para in a w:hyperlink pointing to anchor."""
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    runs = para._element.findall(qn('w:r'))
    if not runs:
        return False

    hl = OxmlElement("w:hyperlink")
    hl.set(qn("w:anchor"), anchor)
    hl.set(qn("w:history"), "1")

    for run in runs:
        para._element.remove(run)
        hl.append(run)

    # Insert after pPr
    pPr = para._element.find(qn('w:pPr'))
    children = list(para._element)
    if pPr is not None and pPr in children:
        idx = children.index(pPr)
        para._element.insert(idx + 1, hl)
    else:
        para._element.insert(0, hl)

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Backup
    if not BACKUP.exists():
        shutil.copy2(DOC, BACKUP)
        print(f"Backup: {BACKUP}")
    else:
        print(f"Backup already exists: {BACKUP}")

    doc = Document(str(DOC))

    # ================================================================
    # Collect body captions with bookmarks
    # ================================================================
    body: dict[str, dict] = {}  # fig_id -> {para_idx, text, bookmarks, prefix}

    for i, para in enumerate(doc.paragraphs):
        style = para.style.name if para.style else ""
        if style not in ("图目录项", "表目录项"):
            continue
        fid = _extract_id(para.text)
        if not fid:
            continue
        bms = para._element.findall(qn('w:bookmarkStart'))
        bm_names = [b.get(qn('w:name')) for b in bms]
        prefix = "图" if style == "图目录项" else "表"
        body[fid] = {"para_idx": i, "text": para.text.strip(), "bookmarks": bm_names, "prefix": prefix}

    print(f"Body captions found: {len(body)}")

    # Add bookmarks to body captions that lack them
    new_bm_count = 0
    for fid, info in body.items():
        if not info["bookmarks"]:
            new_bm_count += 1
            bm_name = f"_FigTabFix_{fid.replace('-', '_')}"
            _add_bookmark(doc.paragraphs[info["para_idx"]], bm_name)
            info["bookmarks"].append(bm_name)
            print(f"  +bookmark '{bm_name}' on {fid}")
    print(f"Bookmarks added: {new_bm_count}")

    # ================================================================
    # Locate directory entries
    # ================================================================
    in_fig = False
    in_tbl = False
    fig_entries = []  # (para_idx, fig_id)
    tbl_entries = []

    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text == "图目录":
            in_fig = True
            continue
        if text == "表目录":
            in_fig = False
            in_tbl = True
            continue
        if (in_fig or in_tbl) and text and re.match(r'第[一二三四五六七八九十\d]+章', text):
            break
        fid = _extract_id(text) if text else None
        if in_fig and fid:
            fig_entries.append((i, fid))
        if in_tbl and fid:
            tbl_entries.append((i, fid))

    print(f"\n图目录 entries: {len(fig_entries)}")
    print(f"表目录 entries: {len(tbl_entries)}")

    # ================================================================
    # Wrap runs in hyperlinks
    # ================================================================
    linked = 0
    mismatches = []

    for dir_label, entries in [("图目录", fig_entries), ("表目录", tbl_entries)]:
        for para_idx, fid in entries:
            para = doc.paragraphs[para_idx]

            if fid not in body:
                mismatches.append(f"{dir_label} '{fid}': no matching body caption")
                continue
            if not body[fid]["bookmarks"]:
                mismatches.append(f"{dir_label} '{fid}': body caption has no bookmark")
                continue

            anchor = body[fid]["bookmarks"][0]
            ok = _wrap_runs_in_hyperlink(para, anchor)
            if ok:
                linked += 1

    print(f"\nLinked: {linked}")

    # ================================================================
    # Verify: count hyperlinks in directory entries
    # ================================================================
    # Re-check
    hl_count = 0
    for para_idx, _ in fig_entries + tbl_entries:
        para = doc.paragraphs[para_idx]
        hls = para._element.findall(qn('w:hyperlink'))
        hl_count += len(hls)
    print(f"Total hyperlinks in directories: {hl_count}")

    # ================================================================
    # Report mismatches
    # ================================================================
    print(f"\nMismatches: {len(mismatches)}")
    for m in mismatches:
        print(f"  ! {m}")

    # Also list directory entries that were linked vs not
    unlinked = []
    for dir_label, entries in [("图目录", fig_entries), ("表目录", tbl_entries)]:
        for para_idx, fid in entries:
            para = doc.paragraphs[para_idx]
            hls = para._element.findall(qn('w:hyperlink'))
            if not hls:
                unlinked.append(f"{dir_label} '{fid}': NOT LINKED")
    if unlinked:
        print(f"\nUnlinked entries: {len(unlinked)}")
        for u in unlinked:
            print(f"  ! {u}")
    else:
        print("\nAll directory entries have hyperlinks.")

    # ================================================================
    # Save
    # ================================================================
    doc.save(str(DOC))
    print(f"\nSaved: {DOC}")
    print(f"Backup: {BACKUP}")


if __name__ == "__main__":
    main()
