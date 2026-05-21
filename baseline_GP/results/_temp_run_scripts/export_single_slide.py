from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("Usage: export_single_slide.py <pptx_path> <slide_index> <out_png>")
    pptx_path = Path(sys.argv[1])
    slide_index = int(sys.argv[2])
    out_png = Path(sys.argv[3])
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if out_png.exists():
        out_png.unlink()

    import win32com.client  # type: ignore

    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = 1
        presentation = app.Presentations.Open(str(pptx_path), ReadOnly=1, Untitled=0, WithWindow=0)
        presentation.Slides(slide_index).Export(str(out_png), "PNG", 1920, 1080)
        print(str(out_png))
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()


if __name__ == "__main__":
    main()
