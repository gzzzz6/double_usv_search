"""
Capture the HTML slide at 1920x1080 using Edge/Selenium and embed into PPT Slide 5.
"""
import time
import shutil
from pathlib import Path

# ---- Try selenium with Edge ----
try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options as EdgeOptions

    html_path = r"F:\pythonprojects\gemini\slide5_design.html"
    out_img = r"F:\pythonprojects\gemini\slide5_capture.png"

    options = EdgeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--hide-scrollbars")

    driver = webdriver.Edge(options=options)
    driver.set_window_size(1920, 1080)
    driver.get(f"file:///{html_path}")
    time.sleep(2)  # Let fonts load

    driver.save_screenshot(out_img)
    driver.quit()
    print(f"Screenshot saved to {out_img}")

except Exception as e:
    print(f"Selenium failed: {e}")
    print("Trying alternative...")
    raise
