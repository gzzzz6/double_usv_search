from __future__ import annotations

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
    docx_path = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    with zipfile.ZipFile(docx_path, "r") as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    paragraphs = root.findall(".//w:body/w:p", namespaces=NS)
    for idx in range(max(0, start), min(len(paragraphs), end + 1)):
        text = paragraph_text(paragraphs[idx]).strip()
        if text:
            print(f"{idx}\t{style_id(paragraphs[idx])}\t{text[:240]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
