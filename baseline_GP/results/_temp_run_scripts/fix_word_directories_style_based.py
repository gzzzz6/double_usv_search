# -*- coding: utf-8 -*-
"""Make equation/figure/table directories style-based and refreshable in Word."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.shared import Pt


REPORT_PATH = Path(r"F:\pythonprojects\my_report.docx")

FORMULA_STYLE = "公式目录项"
FIGURE_STYLE = "图目录项"
TABLE_STYLE = "表目录项"


def ensure_paragraph_style(doc: Document, name: str) -> None:
    try:
        style = doc.styles[name]
    except KeyError:
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = doc.styles["Normal"]
    font = style.font
    font.name = "宋体"
    font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def is_actual_figure_caption(text: str) -> bool:
    if "\t" in text:
        return False
    if not re.match(r"^图\d+[-.]\d+\s+", text):
        return False
    # Exclude body sentences that start with "图x-x 给出/展示..."
    if "给出" in text or "展示" in text or "可以看到" in text:
        return False
    return len(text) <= 80


def is_actual_table_caption(text: str) -> bool:
    if "\t" in text:
        return False
    if not re.match(r"^表\d+[-.]\d+\s+", text):
        return False
    return len(text) <= 90


def is_formula_number(text: str) -> bool:
    return bool(re.match(r"^（\d+）$", text))


def apply_directory_styles(doc: Document) -> tuple[int, int, int]:
    formula_count = 0
    figure_count = 0
    table_count = 0

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if is_formula_number(text):
            paragraph.style = doc.styles[FORMULA_STYLE]
            formula_count += 1
        elif is_actual_figure_caption(text):
            paragraph.style = doc.styles[FIGURE_STYLE]
            figure_count += 1
        elif is_actual_table_caption(text):
            paragraph.style = doc.styles[TABLE_STYLE]
            table_count += 1

    return formula_count, figure_count, table_count


def update_directory_field_codes(doc: Document) -> int:
    replacements = {
        r"\f E": rf'TOC \h \z \t "{FORMULA_STYLE},1"',
        r"\f F": rf'TOC \h \z \t "{FIGURE_STYLE},1"',
        r"\f T": rf'TOC \h \z \t "{TABLE_STYLE},1"',
    }
    updated = 0
    for instr in doc.element.xpath(".//w:instrText"):
        text = instr.text or ""
        if "TOC" not in text:
            continue
        for marker, new_instruction in replacements.items():
            if marker in text:
                instr.text = f" {new_instruction} "
                updated += 1
                break
    return updated


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_PATH.with_name(
        f"my_report_backup_before_style_directories_{stamp}.docx"
    )
    shutil.copy2(REPORT_PATH, backup)

    doc = Document(REPORT_PATH)
    for style_name in (FORMULA_STYLE, FIGURE_STYLE, TABLE_STYLE):
        ensure_paragraph_style(doc, style_name)

    formula_count, figure_count, table_count = apply_directory_styles(doc)
    updated_fields = update_directory_field_codes(doc)
    doc.save(REPORT_PATH)

    print(f"backup={backup}")
    print(f"updated={REPORT_PATH}")
    print(f"formula_style_count={formula_count}")
    print(f"figure_style_count={figure_count}")
    print(f"table_style_count={table_count}")
    print(f"updated_toc_fields={updated_fields}")


if __name__ == "__main__":
    main()
