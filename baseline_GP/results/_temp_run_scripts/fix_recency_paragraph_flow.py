# -*- coding: utf-8 -*-
"""Fix paragraph flow after adding recency references."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from docx import Document


REPORT_PATH = Path(r"F:\pythonprojects\my_report.docx")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_PATH.with_name(
        f"my_report_backup_before_recency_flow_fix_{stamp}.docx"
    )
    shutil.copy2(REPORT_PATH, backup)

    doc = Document(REPORT_PATH)
    for paragraph in doc.paragraphs:
        text = paragraph.text
        if "与persistent surveillance中常用的重访时间思想类似" in text:
            for run in paragraph.runs:
                if "与persistent surveillance中常用的重访时间思想类似" in run.text:
                    run.text = ""
        if "持续监视问题通常将重访时间或观测间隔作为衡量监视质量的重要因素" in text:
            for run in paragraph.runs:
                if "持续监视问题通常将重访时间或观测间隔作为衡量监视质量的重要因素" in run.text:
                    run.text = (
                        "持续监视问题通常将重访时间或观测间隔作为衡量监视质量的重要因素[12]，"
                        "本文的观测时效性场则将这一思想转化为路径规划阶段可使用的局部刷新收益。"
                    )
    doc.save(REPORT_PATH)
    print(f"backup={backup}")
    print(f"updated={REPORT_PATH}")


if __name__ == "__main__":
    main()
