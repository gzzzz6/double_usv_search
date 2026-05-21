from __future__ import annotations

import json
import subprocess
from pathlib import Path

import win32com.client as win32


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "信息科学与工程学院_320220938891_郭一泽.docx"
OUT_DIR = ROOT / "baseline_GP" / "results" / "_temp_run_scripts" / "pdf_crop_audit"
PDF_PATH = OUT_DIR / "信息科学与工程学院_320220938891_郭一泽_margin_crop_audit.pdf"
REPORT_PATH = OUT_DIR / "margin_crop_audit_report.json"

PT_PER_CM = 28.3464567
TARGETS_CM = {
    "top": 2.5,
    "bottom": 2.5,
    "left": 2.5,
    "right": 2.0,
    "header": 1.5,
    "footer": 1.5,
}


def pt_to_cm(value: float) -> float:
    return float(value) / PT_PER_CM


def cm_close(a: float, b: float, tol: float = 0.03) -> bool:
    return abs(a - b) <= tol


def audit_word_layout() -> dict:
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(str(DOCX_PATH), ReadOnly=True, AddToRecentFiles=False)
        doc.Repaginate()
        sections = []
        for i in range(1, doc.Sections.Count + 1):
            sec = doc.Sections(i)
            ps = sec.PageSetup
            values = {
                "top": pt_to_cm(ps.TopMargin),
                "bottom": pt_to_cm(ps.BottomMargin),
                "left": pt_to_cm(ps.LeftMargin),
                "right": pt_to_cm(ps.RightMargin),
                "header": pt_to_cm(ps.HeaderDistance),
                "footer": pt_to_cm(ps.FooterDistance),
                "page_width": pt_to_cm(ps.PageWidth),
                "page_height": pt_to_cm(ps.PageHeight),
                "orientation": int(ps.Orientation),
            }
            checks = {
                key: cm_close(values[key], target)
                for key, target in TARGETS_CM.items()
            }
            sections.append({"section": i, "values_cm": values, "checks": checks})

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        doc.ExportAsFixedFormat(str(PDF_PATH), 17)
        return {
            "section_count": int(doc.Sections.Count),
            "page_count_word": int(doc.ComputeStatistics(2)),
            "sections": sections,
            "pdf_exported": str(PDF_PATH),
        }
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()


def render_pdf_pages() -> list[Path]:
    prefix = OUT_DIR / "page"
    cmd = [
        "pdftoppm",
        "-png",
        "-r",
        "120",
        str(PDF_PATH),
        str(prefix),
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    return sorted(OUT_DIR.glob("page-*.png"))


def audit_png_edges(paths: list[Path]) -> dict:
    from PIL import Image

    edge_rows = []
    risky = []
    border_px = 4
    near_px = 24
    threshold = 245

    def is_nonwhite(pixel) -> bool:
        if isinstance(pixel, int):
            return pixel < threshold
        return any(channel < threshold for channel in pixel[:3])

    for page_index, path in enumerate(paths, start=1):
        im = Image.open(path).convert("RGB")
        w, h = im.size
        pix = im.load()

        def count_region(x0: int, y0: int, x1: int, y1: int) -> int:
            count = 0
            for y in range(max(0, y0), min(h, y1)):
                for x in range(max(0, x0), min(w, x1)):
                    if is_nonwhite(pix[x, y]):
                        count += 1
            return count

        border_counts = {
            "top": count_region(0, 0, w, border_px),
            "bottom": count_region(0, h - border_px, w, h),
            "left": count_region(0, 0, border_px, h),
            "right": count_region(w - border_px, 0, w, h),
        }
        near_counts = {
            "top": count_region(0, 0, w, near_px),
            "bottom": count_region(0, h - near_px, w, h),
            "left": count_region(0, 0, near_px, h),
            "right": count_region(w - near_px, 0, w, h),
        }
        row = {
            "page": page_index,
            "image": str(path),
            "size_px": [w, h],
            "border_nonwhite_px": border_counts,
            "near_edge_nonwhite_px": near_counts,
            "touches_outer_border": any(value > 0 for value in border_counts.values()),
        }
        edge_rows.append(row)
        if row["touches_outer_border"]:
            risky.append(row)

    return {
        "rendered_pages": len(paths),
        "edge_scan_border_px": border_px,
        "edge_scan_near_px": near_px,
        "pages_touching_outer_border": risky,
        "pages": edge_rows,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    word_report = audit_word_layout()
    png_paths = render_pdf_pages()
    edge_report = audit_png_edges(png_paths)
    report = {
        "docx_path": str(DOCX_PATH),
        "targets_cm": TARGETS_CM,
        "word_layout": word_report,
        "pdf_edge_audit": edge_report,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "section_count": word_report["section_count"],
        "page_count_word": word_report["page_count_word"],
        "all_margin_checks_pass": all(
            all(sec["checks"].values()) for sec in word_report["sections"]
        ),
        "pdf_rendered_pages": edge_report["rendered_pages"],
        "pages_touching_outer_border_count": len(edge_report["pages_touching_outer_border"]),
        "report_path": str(REPORT_PATH),
        "pdf_path": str(PDF_PATH),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
