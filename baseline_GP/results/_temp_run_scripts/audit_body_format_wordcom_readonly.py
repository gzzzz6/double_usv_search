from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import win32com.client


def compact_text(s: str) -> str:
    return re.sub(r"[\s\u00a0　\r\a]+", "", s)


def clean_text(s: str) -> str:
    return s.replace("\r", "").replace("\a", "").strip()


def fval(v):
    try:
        if abs(float(v) - 9999999) < 1:
            return None
        return round(float(v), 2)
    except Exception:
        return None


def sval(v):
    try:
        if v is None:
            return None
        s = str(v)
        return s if s else None
    except Exception:
        return None


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_body_format_wordcom_readonly.py input.docx output.json")
    docx_path = str(Path(sys.argv[1]).resolve())
    out_path = Path(sys.argv[2])

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(
            FileName=docx_path,
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Revert=False,
        )
        records = []
        start_i = None
        end_i = None
        for i, p in enumerate(doc.Paragraphs, start=1):
            text = clean_text(p.Range.Text)
            ct = compact_text(text)
            style_name = sval(p.Range.Style.NameLocal) if hasattr(p.Range.Style, "NameLocal") else sval(p.Range.Style)
            is_toc = "PAGEREF" in text or "_Toc" in text or "\\h" in text
            is_toc = is_toc or bool(style_name and style_name.startswith("TOC"))
            if start_i is None:
                if ct in {"1绪论", "1绪論"}:
                    start_i = i
            elif ct in {"参考文献", "致谢", "附录"}:
                end_i = i
                break
        if start_i is None:
            start_i = 1
        if end_i is None:
            end_i = doc.Paragraphs.Count + 1

        for i, p in enumerate(doc.Paragraphs, start=1):
            if i < start_i or i >= end_i:
                continue
            text = clean_text(p.Range.Text)
            if not text:
                continue
            rng = p.Range
            pf = rng.ParagraphFormat
            font = rng.Font
            rec = {
                "para_index": i,
                "text": text[:160],
                "style": sval(rng.Style.NameLocal) if hasattr(rng.Style, "NameLocal") else sval(rng.Style),
                "font": {
                    "name": sval(font.Name),
                    "nameFarEast": sval(font.NameFarEast),
                    "nameAscii": sval(font.NameAscii),
                    "size": fval(font.Size),
                    "bold": None if fval(font.Bold) is None else int(font.Bold),
                },
                "paragraph": {
                    "alignment": int(pf.Alignment),
                    "lineSpacingRule": int(pf.LineSpacingRule),
                    "lineSpacing": fval(pf.LineSpacing),
                    "spaceBefore": fval(pf.SpaceBefore),
                    "spaceAfter": fval(pf.SpaceAfter),
                    "firstLineIndent": fval(pf.FirstLineIndent),
                    "characterUnitFirstLineIndent": fval(pf.CharacterUnitFirstLineIndent),
                    "leftIndent": fval(pf.LeftIndent),
                },
            }
            records.append(rec)

        out = {
            "docx": docx_path,
            "main_region_paragraph_index": {"start": start_i, "end_exclusive": end_i},
            "records": records,
            "notes": [
                "Word COM read-only audit. Document is opened read-only and closed without saving.",
                "Alignment: 0 left, 1 center, 2 right, 3 justify in common Word constants.",
                "LineSpacingRule: 0 single, 3 at least, 4 exactly in common Word constants.",
            ],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(out_path)
    finally:
        if doc is not None:
            doc.Close(SaveChanges=0)
        word.Quit()


if __name__ == "__main__":
    main()
