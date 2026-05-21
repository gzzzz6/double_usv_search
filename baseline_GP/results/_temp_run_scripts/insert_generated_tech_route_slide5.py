from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

import win32com.client  # type: ignore


PP_LAYOUT_BLANK = 12
MSO_FALSE = 0
MSO_TRUE = -1


def export_preview(pres, out_dir: Path, slide_indices: list[int]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx in slide_indices:
        slide = pres.Slides(idx)
        out_path = out_dir / f"slide_{idx:02d}.png"
        slide.Export(str(out_path), "PNG", 1920, 1080)


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: python insert_generated_tech_route_slide5.py "
            "<pptx_path> <image_path> <preview_dir>",
            file=sys.stderr,
        )
        return 2

    pptx_path = Path(sys.argv[1]).resolve()
    image_path = Path(sys.argv[2]).resolve()
    preview_dir = Path(sys.argv[3]).resolve()

    if not pptx_path.exists():
        raise FileNotFoundError(pptx_path)
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = pptx_path.with_name(
        f"{pptx_path.stem}_backup_before_insert_slide5_{timestamp}{pptx_path.suffix}"
    )
    shutil.copy2(pptx_path, backup_path)

    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = True
    pres = None
    try:
        pres = app.Presentations.Open(str(pptx_path), WithWindow=False)
        before_count = pres.Slides.Count
        slide_width = pres.PageSetup.SlideWidth
        slide_height = pres.PageSetup.SlideHeight

        slide = pres.Slides.Add(5, PP_LAYOUT_BLANK)
        slide.FollowMasterBackground = False
        slide.Background.Fill.ForeColor.RGB = 0xFFFFFF

        picture = slide.Shapes.AddPicture(
            str(image_path),
            MSO_FALSE,
            MSO_TRUE,
            0,
            0,
            slide_width,
            slide_height,
        )
        picture.LockAspectRatio = MSO_FALSE
        picture.Left = 0
        picture.Top = 0
        picture.Width = slide_width
        picture.Height = slide_height

        after_count = pres.Slides.Count
        pres.Save()
        export_preview(pres, preview_dir, [5, 6, 7, 8])

        print(f"pptx: {pptx_path}")
        print(f"image: {image_path}")
        print(f"backup: {backup_path}")
        print(f"slides_before: {before_count}")
        print(f"slides_after: {after_count}")
        print(f"preview_dir: {preview_dir}")
        return 0
    finally:
        if pres is not None:
            pres.Close()
        app.Quit()


if __name__ == "__main__":
    raise SystemExit(main())
