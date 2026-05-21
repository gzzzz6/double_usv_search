from __future__ import annotations

import json
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def qn(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def text(p: etree._Element) -> str:
    out = []
    for e in p.iter():
        if e.tag == qn("t"):
            out.append(e.text or "")
        elif e.tag == qn("tab"):
            out.append("\t")
    return "".join(out).strip()


def style(p: etree._Element) -> str | None:
    n = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return n.get(qn("val")) if n is not None else None


def run_summary(p: etree._Element) -> list[dict]:
    items = []
    for r in p.findall("./w:r", namespaces=NS):
        r_text = text(r)
        rpr = r.find("./w:rPr", namespaces=NS)
        fonts = rpr.find("./w:rFonts", namespaces=NS) if rpr is not None else None
        sz = rpr.find("./w:sz", namespaces=NS) if rpr is not None else None
        b = rpr.find("./w:b", namespaces=NS) if rpr is not None else None
        items.append(
            {
                "text": r_text,
                "font_eastAsia": fonts.get(qn("eastAsia")) if fonts is not None else None,
                "font_ascii": fonts.get(qn("ascii")) if fonts is not None else None,
                "size_pt": int(sz.get(qn("val"))) / 2 if sz is not None else None,
                "bold_val": b.get(qn("val")) if b is not None else None,
            }
        )
    return items


def main() -> int:
    docx = Path(r"F:\pythonprojects\my_report.docx")
    with zipfile.ZipFile(docx) as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    paras = root.findall(".//w:body/w:p", namespaces=NS)
    entries = []
    table_title = None
    for idx, p in enumerate(paras):
        p_text = text(p)
        if p_text == "表目录":
            table_title = {"index": idx, "text": p_text, "runs": run_summary(p)}
        if 159 <= idx <= 171:
            entries.append({"index": idx, "style": style(p), "text": p_text, "runs": run_summary(p)})
    print(json.dumps({"table_title": table_title, "entry_count": len(entries), "entries": entries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
