from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def export_slides(pptx_path: Path, out_dir: Path) -> list[Path]:
    import win32com.client  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=True)
    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = 1
    pres = app.Presentations.Open(str(pptx_path), ReadOnly=1, Untitled=0, WithWindow=0)
    paths: list[Path] = []
    try:
        for i in range(1, pres.Slides.Count + 1):
            out_path = out_dir / f"slide_{i:02d}.png"
            pres.Slides(i).Export(str(out_path), "PNG", 480, 270)
            paths.append(out_path)
        return paths
    finally:
        pres.Close()
        app.Quit()


def make_contact_sheet(image_paths: list[Path], out_path: Path, columns: int = 5) -> None:
    thumbs = [Image.open(path).convert("RGB") for path in image_paths]
    if not thumbs:
        raise RuntimeError("No images exported")
    tw, th = thumbs[0].size
    label_h = 24
    gap = 14
    rows = math.ceil(len(thumbs) / columns)
    sheet_w = columns * tw + (columns + 1) * gap
    sheet_h = rows * (th + label_h) + (rows + 1) * gap
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    for idx, img in enumerate(thumbs):
        row = idx // columns
        col = idx % columns
        x = gap + col * (tw + gap)
        y = gap + row * (th + label_h + gap)
        draw.text((x, y), f"{idx + 1:02d}", fill=(40, 40, 40), font=font)
        sheet.paste(img, (x, y + label_h))
    sheet.save(out_path)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: export_pptx_contact_sheet.py <pptx_path> <out_dir>")
    pptx_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    slide_dir = out_dir / "slides"
    image_paths = export_slides(pptx_path, slide_dir)
    contact_sheet = out_dir / "contact_sheet.png"
    make_contact_sheet(image_paths, contact_sheet)
    print(f"SLIDES={len(image_paths)}")
    print(f"CONTACT_SHEET={contact_sheet}")


if __name__ == "__main__":
    main()
