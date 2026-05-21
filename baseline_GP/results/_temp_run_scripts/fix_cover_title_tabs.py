from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import win32com.client as win32


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "信息科学与工程学院_320220938891_郭一泽.docx"
REPORT_PATH = (
    ROOT
    / "baseline_GP"
    / "results"
    / "_temp_run_scripts"
    / "fix_cover_title_tabs_report.json"
)

WD_UNDERLINE_SINGLE = 1
WD_UNDERLINE_NONE = 0
WD_TAB_ALIGNMENT_LEFT = 0
WD_TAB_LEADER_SPACES = 0
WD_ALIGN_PARAGRAPH_LEFT = 0
WD_LINE_SPACE_SINGLE = 0


CN_LABEL = "论文题目（中文）"
EN_LABEL = "论文题目（英文）"
CN_TITLE = "面向海上可疑目标搜索任务的多USV\v决策优化方法研究"
EN_TITLE = (
    "Research on Human-Machine\v"
    "Collaborative Decision-Making Optimization\v"
    "for Multi-USV in Maritime Suspicious\v"
    "Target Search Missions"
)


def clean_text(text: str) -> str:
    return text.replace("\r", "").replace("\x07", "").strip()


def normalize(text: str) -> str:
    text = clean_text(text)
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text


def find_paragraph(doc, label: str):
    label_norm = normalize(label)
    for idx, para in enumerate(doc.Paragraphs, start=1):
        text = clean_text(para.Range.Text)
        if label_norm in normalize(text):
            return idx, para, text
    return None, None, None


def set_cover_title_paragraph(word, para, label: str, title: str, tab_cm: float) -> dict[str, object]:
    visible = f"{label}\t{title}"
    rng = para.Range
    if rng.End > rng.Start:
        rng.End -= 1
    rng.Text = visible

    # Re-fetch range after text replacement.
    rng = para.Range
    if rng.End > rng.Start:
        rng.End -= 1

    pf = para.Range.ParagraphFormat
    tab_pt = tab_cm * 28.3464567
    pf.Alignment = WD_ALIGN_PARAGRAPH_LEFT
    pf.LeftIndent = tab_pt
    pf.FirstLineIndent = -tab_pt
    pf.LineSpacingRule = WD_LINE_SPACE_SINGLE
    pf.TabStops.ClearAll()
    pf.TabStops.Add(Position=tab_pt, Alignment=WD_TAB_ALIGNMENT_LEFT, Leader=WD_TAB_LEADER_SPACES)

    # Keep the label not underlined, and underline only the title text.
    rng.Font.Underline = WD_UNDERLINE_NONE
    title_start = para.Range.Start + len(label) + 1
    title_end = title_start + len(title)
    title_rng = para.Range.Document.Range(title_start, title_end)
    title_rng.Font.Underline = WD_UNDERLINE_SINGLE

    return {
        "label": label,
        "new_text": visible,
        "tab_cm": tab_cm,
        "left_indent_pt": float(pf.LeftIndent),
        "first_line_indent_pt": float(pf.FirstLineIndent),
    }


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ROOT / f"信息科学与工程学院_320220938891_郭一泽_backup_before_cover_title_tabs_{timestamp}.docx"
    shutil.copy2(DOCX_PATH, backup_path)

    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(str(DOCX_PATH), ReadOnly=False, AddToRecentFiles=False)

        cn_idx, cn_para, cn_old = find_paragraph(doc, CN_LABEL)
        en_idx, en_para, en_old = find_paragraph(doc, EN_LABEL)
        if cn_para is None or en_para is None:
            raise RuntimeError(
                f"Cannot find cover title paragraphs: cn_idx={cn_idx}, en_idx={en_idx}"
            )

        operations = []
        operations.append(set_cover_title_paragraph(word, cn_para, CN_LABEL, CN_TITLE, 4.2))
        operations[-1]["paragraph_idx"] = cn_idx
        operations[-1]["old_text"] = cn_old
        operations.append(set_cover_title_paragraph(word, en_para, EN_LABEL, EN_TITLE, 4.2))
        operations[-1]["paragraph_idx"] = en_idx
        operations[-1]["old_text"] = en_old

        doc.Save()

        report = {
            "docx_path": str(DOCX_PATH),
            "backup_path": str(backup_path),
            "operations": operations,
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()


if __name__ == "__main__":
    main()
