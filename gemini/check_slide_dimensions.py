from pptx import Presentation
prs = Presentation(r"E:\毕设PPT\USV_PPT_gemini.pptx")
print(f"Slide width: {prs.slide_width} EMUs ({prs.slide_width/914400} inches)")
print(f"Slide height: {prs.slide_height} EMUs ({prs.slide_height/914400} inches)")
