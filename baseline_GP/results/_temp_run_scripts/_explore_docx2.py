"""Explore body captions and directory structure in my_report2.docx."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from docx import Document
from docx.oxml.ns import qn

DOC = r"F:\pythonprojects\my_report2.docx"
doc = Document(DOC)

# ============================================================
# 1. Find all figure/table captions in body
# ============================================================
print("=== BODY CAPTIONS (containing 图/表) ===\n")
body_captions = []
for i, para in enumerate(doc.paragraphs):
    text = para.text.strip()
    style = para.style.name if para.style else "None"
    # Skip TOC/directory areas (paragraphs before chapter 1)
    # Look for captions: 图X-X or 表X-X
    if not text:
        continue

    # Check for figure/table caption pattern
    is_fig = any(text.startswith(p) for p in ["图", "Figure", "Fig"])
    is_tbl = any(text.startswith(p) for p in ["表", "Table"])
    if is_fig or is_tbl:
        # Check for bookmarks
        bms = para._element.findall(qn('w:bookmarkStart'))
        bm_names = [b.get(qn('w:name')) for b in bms]
        print(f"  P{i:04d} [{style}] bm={bm_names}: {text[:120]}")
        body_captions.append((i, text, style, bm_names, "fig" if is_fig else "tbl"))

print(f"\n  Total figure captions: {sum(1 for c in body_captions if c[4]=='fig')}")
print(f"  Total table captions: {sum(1 for c in body_captions if c[4]=='tbl')}")

# ============================================================
# 2. Detail of directory paragraphs
# ============================================================
print("\n=== 图目录 DETAIL ===\n")
in_fig_dir = False
in_tbl_dir = False
fig_entries = []
tbl_entries = []
for i, para in enumerate(doc.paragraphs):
    text = para.text.strip()
    if text == "图目录":
        in_fig_dir = True
        print(f"  P{i:04d}: [START 图目录] style={para.style.name}")
        continue
    if text == "表目录":
        in_fig_dir = False
        in_tbl_dir = True
        print(f"  P{i:04d}: [START 表目录] style={para.style.name}")
        continue
    if in_fig_dir and text:
        # Check XML for hyperlinks, fldSimple, etc.
        hl = para._element.findall(qn('w:hyperlink'))
        fs = para._element.findall(qn('w:fldSimple'))
        print(f"  P{i:04d}: hl={len(hl)} fs={len(fs)} style={para.style.name} | {text[:120]}")
        fig_entries.append((i, text))
    if in_tbl_dir and text:
        hl = para._element.findall(qn('w:hyperlink'))
        fs = para._element.findall(qn('w:fldSimple'))
        print(f"  P{i:04d}: hl={len(hl)} fs={len(fs)} style={para.style.name} | {text[:120]}")
        tbl_entries.append((i, text))
    # Stop at next section
    if (in_fig_dir or in_tbl_dir) and text.startswith("第") and "章" in text:
        break

# ============================================================
# 3. Check TOC entry XML structure for comparison
# ============================================================
print("\n=== TOC ENTRY XML SAMPLE (one working hyperlink) ===\n")
for para in doc.paragraphs:
    text = para.text.strip()
    if "3.2.1" in text and "静态地图建模" in text:
        xml_str = para._element.xml
        print(xml_str[:800])
        break

# ============================================================
# 4. Check if any bookmarks exist in the document
# ============================================================
print("\n=== BOOKMARKS (first 20) ===\n")
bm_count = 0
for para in doc.paragraphs:
    for bm in para._element.findall(qn('w:bookmarkStart')):
        name = bm.get(qn('w:name'))
        if bm_count < 20:
            print(f"  bookmark: '{name}' at paragraph starting: {para.text[:60]}")
        bm_count += 1
print(f"  Total bookmarks: {bm_count}")
