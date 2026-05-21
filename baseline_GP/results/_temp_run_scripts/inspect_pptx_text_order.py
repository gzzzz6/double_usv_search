from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: inspect_pptx_text_order.py <pptx_path>")
    pptx_path = Path(sys.argv[1])
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    slide_re = re.compile(r"ppt/slides/slide(\d+)\.xml$")
    with ZipFile(pptx_path) as zf:
        slides = []
        for name in zf.namelist():
            match = slide_re.match(name)
            if match:
                slides.append((int(match.group(1)), name))
        slides.sort()
        print("SLIDE_COUNT", len(slides))
        for idx, name in slides:
            root = ET.fromstring(zf.read(name))
            texts: list[str] = []
            for node in root.findall(".//a:t", ns):
                if node.text and node.text.strip():
                    texts.append(node.text.strip())
            preview = " | ".join(texts[:12])
            print(f"{idx:02d}: {preview[:220]}")


if __name__ == "__main__":
    main()
