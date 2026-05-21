from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def qn(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("tab"):
            parts.append("\t")
        elif elem.tag == qn("br"):
            parts.append("\n")
    return "".join(parts)


def style_id(p: etree._Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return node.get(qn("val")) if node is not None else None


def main() -> int:
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\table_caption_candidates.json")
    )

    with zipfile.ZipFile(docx_path, "r") as zf:
        root = etree.fromstring(zf.read("word/document.xml"))

    paragraphs = root.findall(".//w:body/w:p", namespaces=NS)
    pattern = re.compile(r"^表\s*\d+[-.．]\d+(?:\s*续)?(?:\s+|$)")

    records = []
    markers = {}
    for idx, p in enumerate(paragraphs):
        text = paragraph_text(p).strip()
        compact = re.sub(r"\s+", "", text)
        if compact in {"目录", "图目录", "表目录"}:
            markers[compact] = idx
        if pattern.match(text):
            records.append(
                {
                    "index": idx,
                    "style": style_id(p),
                    "text": text,
                }
            )

    out = {
        "docx": str(docx_path),
        "markers": markers,
        "count": len(records),
        "records": records,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
