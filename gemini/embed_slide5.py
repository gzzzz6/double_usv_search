"""
Embed the captured slide5 image into PPT Slide 5 as a full-page image.
Keeps the nav-bar template elements (shapes 0-12 from slide 7 style) stripped,
and places our image as the sole full-bleed content on slide 5.
"""
import copy
import shutil
from pptx import Presentation
from pptx.util import Emu

SRC_PPT  = r"E:\毕设PPT\USV_PPT.pptx"
BAK_PPT  = r"E:\毕设PPT\USV_PPT_slide5_bak2.pptx"
IMG_PATH = r"F:\pythonprojects\gemini\slide5_capture.png"

prs = Presentation(SRC_PPT)

# Slide dimensions
slide_w = prs.slide_width   # EMU
slide_h = prs.slide_height  # EMU
print(f"Slide size: {slide_w} x {slide_h} EMU  ({slide_w/914400:.2f}\" x {slide_h/914400:.2f}\")")

# Backup
shutil.copy2(SRC_PPT, BAK_PPT)
print(f"Backup saved to {BAK_PPT}")

# Target slide (index 4 = slide 5)
slide = prs.slides[4]

# --- Remove ALL existing shapes ---
spTree = slide.shapes._spTree
for sp in list(spTree):
    # Keep the drawing namespace root elements (sp, pic, grpSp, etc.) but remove them
    tag = sp.tag.split('}')[-1] if '}' in sp.tag else sp.tag
    if tag not in ('grpSpPr', 'sp', 'pic', 'grpSp', 'graphicFrame', 'cxnSp', 'txBody'):
        continue  # leave structural XML alone
spTree_children = list(spTree)
for child in spTree_children:
    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
    if tag in ('sp', 'pic', 'grpSp', 'graphicFrame', 'cxnSp'):
        spTree.remove(child)

remaining = [s.name for s in slide.shapes]
print(f"Shapes remaining after clear: {remaining}")

# --- Add full-bleed image ---
slide.shapes.add_picture(IMG_PATH, left=0, top=0, width=slide_w, height=slide_h)
print("Full-bleed image added to slide 5.")

# --- Save ---
prs.save(SRC_PPT)
print(f"Saved to {SRC_PPT}")
