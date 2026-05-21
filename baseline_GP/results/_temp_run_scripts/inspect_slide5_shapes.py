from __future__ import annotations

import json
from pathlib import Path

import win32com.client  # type: ignore


PPTX = Path(r"E:\毕设PPT\USV_PPT.pptx")
OUT = Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\ppt_progress_preview\slide5_shapes.json")


def shape_text(shape) -> str:
    try:
        if shape.HasTextFrame and shape.TextFrame.HasText:
            return str(shape.TextFrame.TextRange.Text).replace("\r", "\\r")
    except Exception:
        return ""
    return ""


def main() -> None:
    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = 1
    pres = app.Presentations.Open(str(PPTX), ReadOnly=1, Untitled=0, WithWindow=0)
    try:
        slide = pres.Slides(5)
        rows = []
        for idx, shape in enumerate(slide.Shapes, start=1):
            rows.append(
                {
                    "idx": idx,
                    "name": str(shape.Name),
                    "type": int(shape.Type),
                    "left": float(shape.Left),
                    "top": float(shape.Top),
                    "width": float(shape.Width),
                    "height": float(shape.Height),
                    "text": shape_text(shape),
                }
            )
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    finally:
        pres.Close()
        app.Quit()


if __name__ == "__main__":
    main()
