from __future__ import annotations

import json
import sys
from pathlib import Path


def iter_shape_text(shape) -> list[str]:
    texts: list[str] = []
    try:
        # msoGroup = 6
        if int(shape.Type) == 6:
            for idx in range(1, int(shape.GroupItems.Count) + 1):
                texts.extend(iter_shape_text(shape.GroupItems(idx)))
            return texts
    except Exception:
        pass

    try:
        if shape.HasTextFrame and shape.TextFrame.HasText:
            value = shape.TextFrame.TextRange.Text
            if value:
                for line in str(value).replace("\r", "\n").split("\n"):
                    line = line.strip()
                    if line:
                        texts.append(line)
    except Exception:
        pass

    try:
        if shape.HasTable:
            table = shape.Table
            for row in range(1, int(table.Rows.Count) + 1):
                for col in range(1, int(table.Columns.Count) + 1):
                    cell_text = table.Cell(row, col).Shape.TextFrame.TextRange.Text
                    if cell_text:
                        for line in str(cell_text).replace("\r", "\n").split("\n"):
                            line = line.strip()
                            if line:
                                texts.append(line)
    except Exception:
        pass

    return texts


def inspect_pptx(pptx_path: Path, out_dir: Path, max_slides: int = 5) -> dict:
    import win32com.client  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=True)
    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = 1
        presentation = app.Presentations.Open(
            str(pptx_path),
            ReadOnly=1,
            Untitled=0,
            WithWindow=0,
        )
        slide_count = int(presentation.Slides.Count)
        slide_width = float(presentation.PageSetup.SlideWidth)
        slide_height = float(presentation.PageSetup.SlideHeight)

        slides: list[dict] = []
        for idx in range(1, min(max_slides, slide_count) + 1):
            slide = presentation.Slides(idx)
            preview = out_dir / f"slide_{idx:02d}.png"
            slide.Export(str(preview), "PNG", 1920, 1080)

            texts: list[str] = []
            shape_summaries: list[dict] = []
            for sidx in range(1, int(slide.Shapes.Count) + 1):
                shape = slide.Shapes(sidx)
                shape_texts = iter_shape_text(shape)
                texts.extend(shape_texts)
                try:
                    shape_summaries.append(
                        {
                            "index": sidx,
                            "name": str(shape.Name),
                            "type": int(shape.Type),
                            "left": round(float(shape.Left), 2),
                            "top": round(float(shape.Top), 2),
                            "width": round(float(shape.Width), 2),
                            "height": round(float(shape.Height), 2),
                            "texts": shape_texts[:8],
                        }
                    )
                except Exception:
                    shape_summaries.append(
                        {
                            "index": sidx,
                            "name": "unreadable",
                            "type": None,
                            "texts": shape_texts[:8],
                        }
                    )

            slides.append(
                {
                    "slide_index": idx,
                    "preview": str(preview),
                    "shape_count": int(slide.Shapes.Count),
                    "texts": texts,
                    "shapes": shape_summaries,
                }
            )

        report = {
            "pptx_path": str(pptx_path),
            "slide_count": slide_count,
            "slide_width": slide_width,
            "slide_height": slide_height,
            "preview_dir": str(out_dir),
            "slides": slides,
        }
        report_path = out_dir / "first5_readonly_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: inspect_pptx_first5_readonly.py <pptx_path> [out_dir] [max_slides]")
    pptx_path = Path(sys.argv[1])
    out_dir = (
        Path(sys.argv[2])
        if len(sys.argv) >= 3
        else Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\readonly_first5")
    )
    max_slides = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
    report = inspect_pptx(pptx_path, out_dir, max_slides)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
