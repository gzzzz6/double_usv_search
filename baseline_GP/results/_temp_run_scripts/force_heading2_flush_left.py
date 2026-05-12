from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt


ROOT = Path(r"F:\pythonprojects")
DOCX_PATH = ROOT / "my_report.docx"
OUT_JSON = (
    ROOT
    / "baseline_GP"
    / "results"
    / "_temp_run_scripts"
    / "force_heading2_flush_left_report.json"
)


def ensure_ppr(element):
    ppr = element.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        element.insert(0, ppr)
    return ppr


def ensure_ind(element):
    ppr = ensure_ppr(element)
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        ppr.append(ind)
    return ind


def force_no_indent(element) -> None:
    """Force paragraph/style indentation to true flush-left.

    Setting only w:firstLine=0 is not enough when a base style carries
    w:firstLineChars=200. Word may still render the inherited character-based
    first-line indent. Therefore explicitly zero both twip-based and
    character-based indent attributes.
    """
    ind = ensure_ind(element)
    for attr in (
        "left",
        "leftChars",
        "right",
        "rightChars",
        "firstLine",
        "firstLineChars",
        "hanging",
        "hangingChars",
    ):
        qattr = qn(f"w:{attr}")
        if qattr in ind.attrib:
            del ind.attrib[qattr]
    ind.set(qn("w:left"), "0")
    ind.set(qn("w:leftChars"), "0")
    ind.set(qn("w:firstLine"), "0")
    ind.set(qn("w:firstLineChars"), "0")


def force_third_level_indent(element) -> None:
    ind = ensure_ind(element)
    for attr in (
        "left",
        "leftChars",
        "right",
        "rightChars",
        "firstLine",
        "firstLineChars",
        "hanging",
        "hangingChars",
    ):
        qattr = qn(f"w:{attr}")
        if qattr in ind.attrib:
            del ind.attrib[qattr]
    ind.set(qn("w:left"), "0")
    ind.set(qn("w:leftChars"), "0")
    ind.set(qn("w:firstLineChars"), "200")


def ind_xml(element) -> dict[str, str]:
    ppr = element.find(qn("w:pPr"))
    if ppr is None:
        return {}
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        return {}
    out = {}
    for attr in (
        "left",
        "leftChars",
        "firstLine",
        "firstLineChars",
        "hanging",
        "hangingChars",
    ):
        value = ind.get(qn(f"w:{attr}"))
        if value is not None:
            out[attr] = value
    return out


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ROOT / f"my_report_backup_before_force_heading2_flush_left_{timestamp}.docx"
    shutil.copy2(DOCX_PATH, backup_path)

    doc = Document(DOCX_PATH)

    touched_styles = {}
    # Body keeps two-character first-line indent. Headings explicitly override it.
    for name in ("一级标题", "二级标题", "Heading 1", "Heading 2", "标题 1", "标题 2"):
        try:
            style = doc.styles[name]
        except Exception:
            continue
        before = ind_xml(style.element)
        force_no_indent(style.element)
        style.paragraph_format.alignment = (
            WD_ALIGN_PARAGRAPH.CENTER
            if name in {"一级标题", "Heading 1", "标题 1"}
            else WD_ALIGN_PARAGRAPH.LEFT
        )
        touched_styles[name] = {"before": before, "after": ind_xml(style.element)}

    for name in ("三级标题", "Heading 3", "标题 3"):
        try:
            style = doc.styles[name]
        except Exception:
            continue
        before = ind_xml(style.element)
        force_third_level_indent(style.element)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        touched_styles[name] = {"before": before, "after": ind_xml(style.element)}

    level1_pat = re.compile(r"^[1-6]\s+")
    level2_pat = re.compile(r"^[1-6]\.[1-9][0-9]*\s+")
    level3_pat = re.compile(r"^[1-6]\.[1-9][0-9]*\.[1-9][0-9]*\s+")
    touched_paragraphs = []

    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = paragraph.style.name

        # Important: test level3 before level2 because 5.4.1 also matches
        # the loose level2 prefix otherwise.
        if style_name in {"三级标题", "Heading 3", "标题 3"} or level3_pat.match(text):
            before = ind_xml(paragraph._p)
            force_third_level_indent(paragraph._p)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            touched_paragraphs.append(
                {"index": idx, "style": style_name, "text": text[:120], "before": before, "after": ind_xml(paragraph._p)}
            )
        elif style_name in {"二级标题", "Heading 2", "标题 2"} or level2_pat.match(text):
            before = ind_xml(paragraph._p)
            force_no_indent(paragraph._p)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            touched_paragraphs.append(
                {"index": idx, "style": style_name, "text": text[:120], "before": before, "after": ind_xml(paragraph._p)}
            )
        elif style_name in {"一级标题", "Heading 1", "标题 1"} or level1_pat.match(text):
            before = ind_xml(paragraph._p)
            force_no_indent(paragraph._p)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            touched_paragraphs.append(
                {"index": idx, "style": style_name, "text": text[:120], "before": before, "after": ind_xml(paragraph._p)}
            )

    doc.save(DOCX_PATH)

    reopened = Document(DOCX_PATH)
    samples = []
    for idx, paragraph in enumerate(reopened.paragraphs):
        text = paragraph.text.strip()
        if text.startswith(("5.3", "5.4", "5.5", "6.1")) or paragraph.style.name in {"二级标题", "三级标题"}:
            samples.append(
                {
                    "index": idx,
                    "style": paragraph.style.name,
                    "text": text[:100],
                    "direct_indent": ind_xml(paragraph._p),
                    "style_indent": ind_xml(paragraph.style.element),
                    "alignment": str(paragraph.paragraph_format.alignment),
                }
            )
            if len(samples) >= 80:
                break

    result = {
        "docx": str(DOCX_PATH),
        "backup": str(backup_path),
        "touched_styles": touched_styles,
        "touched_paragraph_count": len(touched_paragraphs),
        "samples": samples,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "docx": str(DOCX_PATH),
                "backup": str(backup_path),
                "touched_style_count": len(touched_styles),
                "touched_paragraph_count": len(touched_paragraphs),
                "out_json": str(OUT_JSON),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
