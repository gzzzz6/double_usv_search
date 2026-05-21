from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def slide_number(name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 10**9


def extract_texts(pptx_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with ZipFile(pptx_path) as zf:
        slide_names = sorted(
            [
                name
                for name in zf.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ],
            key=slide_number,
        )
        for idx, name in enumerate(slide_names, start=1):
            root = ET.fromstring(zf.read(name))
            texts: list[str] = []
            for t in root.findall(".//a:t", NS):
                if t.text:
                    text = t.text.strip()
                    if text:
                        texts.append(text)
            rows.append(
                {
                    "slide_index": idx,
                    "xml_name": name,
                    "texts": texts,
                    "text_count": len(texts),
                }
            )
    return rows


def export_previews(pptx_path: Path, output_dir: Path, max_slides: int = 5) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        print(f"COM_IMPORT_FAILED: {exc}", file=sys.stderr)
        return exported

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
        count = min(int(max_slides), int(presentation.Slides.Count))
        for idx in range(1, count + 1):
            out_path = output_dir / f"slide_{idx:02d}.png"
            presentation.Slides(idx).Export(str(out_path), "PNG", 1920, 1080)
            exported.append(str(out_path))
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()
    return exported


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: inspect_pptx_progress.py <pptx_path> [output_dir] [max_slides]")
    pptx_path = Path(sys.argv[1])
    if not pptx_path.exists():
        raise FileNotFoundError(str(pptx_path))

    output_dir = (
        Path(sys.argv[2])
        if len(sys.argv) >= 3
        else Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\ppt_progress_preview")
    )
    max_slides = int(sys.argv[3]) if len(sys.argv) >= 4 else 5

    slides = extract_texts(pptx_path)
    exported = export_previews(pptx_path, output_dir, max_slides=max_slides)
    report = {
        "pptx_path": str(pptx_path),
        "slide_count": len(slides),
        "preview_dir": str(output_dir),
        "exported_previews": exported,
        "slides": slides,
    }
    report_path = output_dir / "ppt_progress_report.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
