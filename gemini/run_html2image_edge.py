import os
from html2image import Html2Image

output_dir = r"F:\pythonprojects\gemini"
html_path = os.path.join(output_dir, "slide_mockup.html")
img_name = "beautiful_slide.png"
img_path = os.path.join(output_dir, img_name)

# Try with Microsoft Edge which is native to Windows
edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(edge_path):
    edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

try:
    hti = Html2Image(
        browser_executable=edge_path if os.path.exists(edge_path) else None,
        output_path=output_dir, 
        custom_flags=['--default-background-color=00000000', '--hide-scrollbars']
    )
    hti.screenshot(html_file=html_path, save_as=img_name, size=(1280, 720))
    print(f"Successfully generated: {img_path}")
except Exception as e:
    print(f"Error during image generation: {e}")
