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


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("tab"):
            parts.append("\t")
    return "".join(parts).strip()


def p_style_id(p: etree._Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return node.get(qn("val")) if node is not None else None


def p_sect_pr(p: etree._Element) -> etree._Element | None:
    return p.find("./w:pPr/w:sectPr", namespaces=NS)


def body_sect_pr(root: etree._Element) -> etree._Element | None:
    body = root.find("./w:body", namespaces=NS)
    return body.find("./w:sectPr", namespaces=NS) if body is not None else None


def page_num_type(sect_pr: etree._Element | None) -> dict:
    if sect_pr is None:
        return {"fmt": None, "start": None}
    node = sect_pr.find("./w:pgNumType", namespaces=NS)
    if node is None:
        return {"fmt": None, "start": None}
    return {
        "fmt": node.get(qn("fmt")),
        "start": int(node.get(qn("start"))) if node.get(qn("start")) and node.get(qn("start")).isdigit() else None,
    }


def paragraph_render_pages(paragraphs: list[etree._Element]) -> list[int]:
    pages: list[int] = []
    current_page = 1
    for p in paragraphs:
        page_for_text = current_page
        saw_text = False
        for elem in p.iter():
            if elem.tag == qn("lastRenderedPageBreak"):
                current_page += 1
                if not saw_text:
                    page_for_text = current_page
            elif elem.tag == qn("t") and (elem.text or "").strip():
                if not saw_text:
                    page_for_text = current_page
                    saw_text = True
        pages.append(page_for_text)
    return pages


def section_ranges(root: etree._Element, paragraphs: list[etree._Element], physical_pages: list[int]) -> list[dict]:
    ranges = []
    start_idx = 0
    sect_num = 1
    for idx, p in enumerate(paragraphs):
        sect = p_sect_pr(p)
        if sect is None:
            continue
        ranges.append(
            {
                "section": sect_num,
                "start_idx": start_idx,
                "end_idx": idx,
                "start_physical_page": physical_pages[start_idx],
                "end_physical_page": physical_pages[idx],
                "pg": page_num_type(sect),
                "end_text": paragraph_text(p),
            }
        )
        start_idx = idx + 1
        sect_num += 1
    final = body_sect_pr(root)
    if final is not None and start_idx < len(paragraphs):
        ranges.append(
            {
                "section": sect_num,
                "start_idx": start_idx,
                "end_idx": len(paragraphs) - 1,
                "start_physical_page": physical_pages[start_idx],
                "end_physical_page": physical_pages[-1],
                "pg": page_num_type(final),
                "end_text": paragraph_text(paragraphs[-1]),
            }
        )
    return ranges


def section_for_idx(sections: list[dict], idx: int) -> dict:
    for sec in sections:
        if sec["start_idx"] <= idx <= sec["end_idx"]:
            return sec
    return sections[-1]


def adjusted_page(idx: int, physical_pages: list[int], sections: list[dict]) -> int:
    sec = section_for_idx(sections, idx)
    start_num = sec["pg"].get("start")
    if start_num is None:
        # Continue physical numbering when no explicit page-number restart exists.
        return physical_pages[idx]
    return start_num + (physical_pages[idx] - sec["start_physical_page"])


def extract_entry(text: str) -> tuple[str, int | None]:
    if "\t" in text:
        title, page = text.rsplit("\t", 1)
    else:
        m = re.match(r"^(.*?)(\d+)$", text)
        if not m:
            return text.strip(), None
        title, page = m.group(1), m.group(2)
    title = title.strip()
    page = page.strip()
    return title, int(page) if page.isdigit() else None


def compare(entries: list[dict], actual_map: dict[str, list[dict]]) -> list[dict]:
    out = []
    for entry in entries:
        matches = actual_map.get(entry["key"], [])
        if not matches:
            out.append({**entry, "actual_page": None, "status": "missing_actual"})
            continue
        actual = matches[0]
        status = "ok" if entry["listed_page"] == actual["actual_page"] else "mismatch"
        out.append({**entry, **actual, "status": status})
    return out


def main() -> int:
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\directory_page_consistency_xmlonly.json")
    )
    with zipfile.ZipFile(docx, "r") as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    paragraphs = root.findall(".//w:body/w:p", namespaces=NS)
    physical_pages = paragraph_render_pages(paragraphs)
    sections = section_ranges(root, paragraphs, physical_pages)

    markers: dict[str, int] = {}
    for idx, p in enumerate(paragraphs):
        c = compact(paragraph_text(p))
        if c in {"目录", "图目录", "表目录"} and c not in markers:
            markers[c] = idx
    body_idx = next(
        idx for idx, p in enumerate(paragraphs) if compact(paragraph_text(p)) == "1绪论" and p_style_id(p) != "TOC1"
    )

    main_entries = []
    fig_entries = []
    table_entries = []
    for idx in range(markers["目录"] + 1, markers["图目录"]):
        text = paragraph_text(paragraphs[idx])
        if p_style_id(paragraphs[idx]) in {"TOC1", "TOC2", "TOC3"} and "\t" in text:
            title, page = extract_entry(text)
            main_entries.append({"dir_index": idx, "title": title, "key": compact(title), "listed_page": page})
    for idx in range(markers["图目录"] + 1, markers["表目录"]):
        text = paragraph_text(paragraphs[idx])
        if compact(text).startswith("图"):
            title, page = extract_entry(text)
            fig_entries.append({"dir_index": idx, "title": title, "key": compact(title), "listed_page": page})
    for idx in range(markers["表目录"] + 1, body_idx):
        text = paragraph_text(paragraphs[idx])
        if compact(text).startswith("表"):
            title, page = extract_entry(text)
            table_entries.append({"dir_index": idx, "title": title, "key": compact(title), "listed_page": page})

    heading_pat = re.compile(r"^(?:\d+\s+.+|\d+(?:\.\d+){1,2}\s+.+)$")
    fig_pat = re.compile(r"^图\s*\d+[-.．]\d+(?:\s+|$)")
    table_pat = re.compile(r"^表\s*\d+[-.．]\d+(?:\s*续)?(?:\s+|$)")
    headings: dict[str, list[dict]] = {}
    figs: dict[str, list[dict]] = {}
    tables: dict[str, list[dict]] = {}

    after_references = False
    for idx in range(body_idx, len(paragraphs)):
        text = paragraph_text(paragraphs[idx])
        if not text or "\t" in text:
            continue
        c = compact(text)
        actual = {
            "actual_index": idx,
            "actual_text": text,
            "actual_page": adjusted_page(idx, physical_pages, sections),
            "physical_page": physical_pages[idx],
            "section": section_for_idx(sections, idx)["section"],
        }
        if heading_pat.match(text) or c in {"参考文献", "致谢", "附录"}:
            headings.setdefault(c, []).append(actual)
            if c == "参考文献":
                after_references = True
        if not after_references and fig_pat.match(text):
            figs.setdefault(c, []).append(actual)
        if not after_references and table_pat.match(text):
            tables.setdefault(c, []).append(actual)

    main_compare = compare(main_entries, headings)
    fig_compare = compare(fig_entries, figs)
    table_compare = compare(table_entries, tables)
    out = {
        "docx": str(docx),
        "method": "XML lastRenderedPageBreak based read-only audit; no document modification.",
        "markers": markers,
        "body_index": body_idx,
        "sections": sections,
        "counts": {
            "main_entries": len(main_compare),
            "figure_entries": len(fig_compare),
            "table_entries": len(table_compare),
            "main_non_ok": sum(1 for x in main_compare if x["status"] != "ok"),
            "figure_non_ok": sum(1 for x in fig_compare if x["status"] != "ok"),
            "table_non_ok": sum(1 for x in table_compare if x["status"] != "ok"),
        },
        "main_toc": main_compare,
        "figure_directory": fig_compare,
        "table_directory": table_compare,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
