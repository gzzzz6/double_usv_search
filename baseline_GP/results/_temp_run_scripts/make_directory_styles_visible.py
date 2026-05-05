# -*- coding: utf-8 -*-
"""Expose directory source styles in Word's quick style gallery."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


REPORT_PATH = Path(r"F:\pythonprojects\my_report.docx")
STYLE_NAMES = ("公式目录项", "图目录项", "表目录项")


def set_quick_style(style) -> None:
    element = style._element
    for tag in ("w:semiHidden", "w:unhideWhenUsed"):
        child = element.find(qn(tag))
        if child is not None:
            element.remove(child)
    if element.find(qn("w:qFormat")) is None:
        element.append(OxmlElement("w:qFormat"))
    priority = element.find(qn("w:uiPriority"))
    if priority is None:
        priority = OxmlElement("w:uiPriority")
        element.append(priority)
    priority.set(qn("w:val"), "20")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_PATH.with_name(
        f"my_report_backup_before_visible_directory_styles_{stamp}.docx"
    )
    shutil.copy2(REPORT_PATH, backup)

    doc = Document(REPORT_PATH)
    found = []
    for name in STYLE_NAMES:
        style = doc.styles[name]
        set_quick_style(style)
        found.append(name)
    doc.save(REPORT_PATH)

    print(f"backup={backup}")
    print(f"updated={REPORT_PATH}")
    print("visible_styles=" + ",".join(found))


if __name__ == "__main__":
    main()
