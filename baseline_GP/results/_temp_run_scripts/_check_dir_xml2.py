"""Check children XML of TOC and directory entries."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

DOC = r"F:\pythonprojects\my_report2.docx"
doc = Document(DOC)

def _show_children(para, label):
    print(f"\n=== {label} ===")
    print(f"  Style: {para.style.name if para.style else 'None'}")
    print(f"  Text: {para.text[:120]}")
    print(f"  Children:")
    for child in para._element:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'pPr':
            print(f"    <pPr> (paragraph properties)")
            continue
        # Print the child element without full namespace declarations
        child_str = etree.tostring(child, pretty_print=True, encoding="unicode")
        # Only show first 600 chars of each child
        if len(child_str) > 600:
            child_str = child_str[:600] + "\n    ..."
        # Indent
        for line in child_str.split('\n'):
            print(f"    {line}")

# Find TOC entry with hyperlink
print("=" * 60)
for para in doc.paragraphs:
    text = para.text.strip()
    style = para.style.name if para.style else ""
    if "toc 1" in style:
        hl = para._element.findall(qn('w:hyperlink'))
        if hl:
            _show_children(para, "TOC ENTRY (toc 1 with hyperlink)")
            break

# Find 图目录 first entry
for para in doc.paragraphs:
    text = para.text.strip()
    if text.startswith("图2-1") and "toc 1" in (para.style.name if para.style else ""):
        _show_children(para, "图目录 ENTRY (图2-1)")
        break

# Find 表目录 first entry
for para in doc.paragraphs:
    text = para.text.strip()
    if text.startswith("表5-1") and "toc 1" in (para.style.name if para.style else ""):
        _show_children(para, "表目录 ENTRY (表5-1)")
        break

# Find body caption 图目录项
for para in doc.paragraphs:
    style = para.style.name if para.style else ""
    text = para.text.strip()
    if style == "图目录项" and "图2-1" in text:
        _show_children(para, "BODY 图目录项 (图2-1)")
        break

# Find body caption 表目录项
for para in doc.paragraphs:
    style = para.style.name if para.style else ""
    text = para.text.strip()
    if style == "表目录项" and "表5-1" in text:
        _show_children(para, "BODY 表目录项 (表5-1)")
        break
