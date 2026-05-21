import sys
from pptx import Presentation

prs = Presentation(r"E:\毕设PPT\USV_PPT_gemini.pptx")
with open(r"F:\pythonprojects\gemini\check_slides_6_9.txt", "w", encoding="utf-8") as f:
    f.write(f"Total slides: {len(prs.slides)}\n\n")
    # let's inspect slides 5, 6, 7, 8, 9, 10
    for idx in range(4, 11):
        if idx < len(prs.slides):
            f.write(f"=== Slide {idx+1} ===\n")
            slide = prs.slides[idx]
            for shape in slide.shapes:
                txt = shape.text.strip() if hasattr(shape, 'text') else ""
                if txt:
                    f.write(f"[{shape.name}] {txt[:60]}\n")
            f.write("\n")
print("Done")
