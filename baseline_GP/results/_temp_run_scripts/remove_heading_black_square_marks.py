from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "my_report.docx"
OUT_JSON = (
    ROOT
    / "baseline_GP"
    / "results"
    / "_temp_run_scripts"
    / "remove_heading_black_square_marks_report.json"
)


PAGINATION_TAGS = {
    "keepNext",
    "keepLines",
    "pageBreakBefore",
    "suppressLineNumbers",
}


def remove_pagination_marks_from_ppr(ppr) -> list[str]:
    if ppr is None:
        return []
    removed = []
    for child in list(ppr):
        local = child.tag.split("}")[-1]
        if local in PAGINATION_TAGS:
            ppr.remove(child)
            removed.append(local)
    return removed


def remove_from_style(style) -> list[str]:
    ppr = style.element.find(qn("w:pPr"))
    removed = remove_pagination_marks_from_ppr(ppr)
    if style.base_style is not None:
        base_ppr = style.base_style.element.find(qn("w:pPr"))
        removed += [f"base:{x}" for x in remove_pagination_marks_from_ppr(base_ppr)]
    return removed


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ROOT / f"my_report_backup_before_remove_heading_black_square_marks_{timestamp}.docx"
    shutil.copy2(DOCX_PATH, backup_path)

    doc = Document(DOCX_PATH)

    touched_styles = {}
    for name in ("一级标题", "二级标题", "三级标题", "Heading 1", "Heading 2", "Heading 3", "标题 1", "标题 2", "标题 3"):
        try:
            style = doc.styles[name]
        except Exception:
            continue
        removed = remove_from_style(style)
        if removed:
            touched_styles[name] = removed

    heading_pat = re.compile(r"^[1-6](?:\.[1-9][0-9]*){0,2}\s+")
    touched_paragraphs = []
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style.name in {"一级标题", "二级标题", "三级标题", "Heading 1", "Heading 2", "Heading 3"} or heading_pat.match(text):
            ppr = paragraph._p.find(qn("w:pPr"))
            removed = remove_pagination_marks_from_ppr(ppr)
            if removed:
                touched_paragraphs.append(
                    {
                        "index": idx,
                        "style": paragraph.style.name,
                        "text": text[:120],
                        "removed": removed,
                    }
                )

    doc.save(DOCX_PATH)

    result = {
        "docx": str(DOCX_PATH),
        "backup": str(backup_path),
        "touched_styles": touched_styles,
        "touched_paragraph_count": len(touched_paragraphs),
        "touched_paragraphs": touched_paragraphs[:80],
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "touched_paragraphs"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
