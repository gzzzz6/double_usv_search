from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: make_image_contact_sheet.py <image_dir> <out_path>")
    image_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    files = [
        p
        for p in sorted(image_dir.iterdir(), key=lambda x: x.name)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    thumb_w, thumb_h = 300, 170
    label_h = 46
    gap = 14
    cols = 4
    rows = math.ceil(len(files) / cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap, rows * (thumb_h + label_h) + (rows + 1) * gap), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
        small = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    for idx, path in enumerate(files):
        row, col = divmod(idx, cols)
        x = gap + col * (thumb_w + gap)
        y = gap + row * (thumb_h + label_h + gap)
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((thumb_w, thumb_h))
            canvas = Image.new("RGB", (thumb_w, thumb_h), (245, 248, 252))
            ox = (thumb_w - im.width) // 2
            oy = (thumb_h - im.height) // 2
            canvas.paste(im, (ox, oy))
            sheet.paste(canvas, (x, y + label_h))
        label = f"{idx + 1:02d}. {path.name}"
        draw.text((x, y), label[:46], fill=(20, 42, 70), font=font)
        draw.text((x, y + 20), f"{path.stat().st_size // 1024} KB", fill=(80, 90, 105), font=small)
    sheet.save(out_path)
    print(out_path)


if __name__ == "__main__":
    main()
