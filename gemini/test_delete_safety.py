import sys
from pptx import Presentation

sys.stdout.reconfigure(encoding='utf-8')
prs = Presentation(r"E:\毕设PPT\USV_PPT_gemini.pptx")

print("=== Shape check before delete ===")
for idx in [5, 6, 7, 8]:
    slide = prs.slides[idx]
    print(f"Slide {idx+1}: total shapes = {len(slide.shapes)}")
    # Print shapes from 15 onwards
    if len(slide.shapes) > 15:
        print(f"  Shape 15: name='{slide.shapes[15].name}', type={slide.shapes[15].shape_type}")
    else:
        print("  Fewer than 16 shapes!")
