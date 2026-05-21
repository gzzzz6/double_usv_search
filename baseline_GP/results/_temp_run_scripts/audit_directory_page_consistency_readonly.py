from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree
import win32com.client


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1


def qn(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def clean(text: str) -> str:
    return (text or "").replace("\r", "").replace("\x07", "").strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", clean(text))


def paragraph_text_xml(p: etree._Element) -> str:
    parts: list[str] = []
    for elem in p.iter():
        if elem.tag == qn("t"):
            parts.append(elem.text or "")
        elif elem.tag == qn("tab"):
            parts.append("\t")
        elif elem.tag == qn("br"):
            parts.append("\n")
    return "".join(parts).strip()


def style_id_xml(p: etree._Element) -> str | None:
    node = p.find("./w:pPr/w:pStyle", namespaces=NS)
    return node.get(qn("val")) if node is not None else None


def extract_listed_entry(text: str) -> tuple[str, int | None]:
    if "\t" in text:
        title, page = text.rsplit("\t", 1)
    else:
        m = re.match(r"^(.*?)(\d+)$", text)
        if not m:
            return text.strip(), None
        title, page = m.group(1), m.group(2)
    title = title.strip()
    page = page.strip()
    if page.isdigit():
        return title, int(page)
    return title, None


def is_main_toc_entry(text: str, style: str | None) -> bool:
    return bool(style in {"TOC1", "TOC2", "TOC3"} and "\t" in text)


def extract_directory_entries(docx_path: Path) -> dict:
    with zipfile.ZipFile(docx_path, "r") as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    paras = root.findall(".//w:body/w:p", namespaces=NS)

    markers: dict[str, int] = {}
    for idx, p in enumerate(paras):
        c = compact(paragraph_text_xml(p))
        if c in {"目录", "图目录", "表目录"} and c not in markers:
            markers[c] = idx
    for required in ("目录", "图目录", "表目录"):
        if required not in markers:
            raise RuntimeError(f"未找到 {required}")

    toc_entries = []
    fig_entries = []
    table_entries = []
    body_start_idx = None
    for idx, p in enumerate(paras):
        if compact(paragraph_text_xml(p)) == "1绪论" and style_id_xml(p) != "TOC1":
            body_start_idx = idx
            break
    if body_start_idx is None:
        body_start_idx = len(paras)

    for idx in range(markers["目录"] + 1, markers["图目录"]):
        text = paragraph_text_xml(paras[idx])
        style = style_id_xml(paras[idx])
        if is_main_toc_entry(text, style):
            title, page = extract_listed_entry(text)
            toc_entries.append({"index": idx, "style": style, "title": title, "key": compact(title), "listed_page": page})

    for idx in range(markers["图目录"] + 1, markers["表目录"]):
        text = paragraph_text_xml(paras[idx])
        if compact(text).startswith("图"):
            title, page = extract_listed_entry(text)
            fig_entries.append({"index": idx, "title": title, "key": compact(title), "listed_page": page})

    for idx in range(markers["表目录"] + 1, body_start_idx):
        text = paragraph_text_xml(paras[idx])
        if compact(text).startswith("表"):
            title, page = extract_listed_entry(text)
            table_entries.append({"index": idx, "title": title, "key": compact(title), "listed_page": page})

    return {
        "markers": markers,
        "body_start_idx": body_start_idx,
        "toc_entries": toc_entries,
        "fig_entries": fig_entries,
        "table_entries": table_entries,
    }


def actual_pages_from_word(docx_path: Path) -> dict:
    heading_pat = re.compile(r"^(?:\d+\s+.+|\d+(?:\.\d+){1,2}\s+.+)$")
    fig_pat = re.compile(r"^图\s*\d+[-.．]\d+(?:\s+|$)")
    table_pat = re.compile(r"^表\s*\d+[-.．]\d+(?:\s*续)?(?:\s+|$)")

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(
            str(docx_path),
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Visible=False,
        )
        doc.Repaginate()

        in_body = False
        after_references = False
        heading_pages: dict[str, list[dict]] = {}
        fig_pages: dict[str, list[dict]] = {}
        table_pages: dict[str, list[dict]] = {}

        for i in range(1, doc.Paragraphs.Count + 1):
            para = doc.Paragraphs(i)
            text = clean(para.Range.Text)
            if not text:
                continue
            c = compact(text)
            has_tab = "\t" in text
            style = ""
            try:
                style = str(para.Style.NameLocal)
            except Exception:
                style = ""

            if not in_body and c == "1绪论" and not has_tab:
                in_body = True
            if not in_body:
                continue

            page = int(para.Range.Information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER))

            # Main TOC entries: numbered headings plus back matter headings that may appear in the main TOC.
            if not has_tab and (heading_pat.match(text) or c in {"参考文献", "致谢", "附录"}):
                heading_pages.setdefault(c, []).append(
                    {"paragraph_index": i, "text": text, "page": page, "style": style}
                )
                if c == "参考文献":
                    after_references = True

            # Figure and table directories should correspond to main body captions, not appendix duplicates.
            if not after_references and not has_tab and fig_pat.match(text):
                fig_pages.setdefault(c, []).append(
                    {"paragraph_index": i, "text": text, "page": page, "style": style}
                )
            if not after_references and not has_tab and table_pat.match(text):
                table_pages.setdefault(c, []).append(
                    {"paragraph_index": i, "text": text, "page": page, "style": style}
                )
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()

    return {
        "heading_pages": heading_pages,
        "fig_pages": fig_pages,
        "table_pages": table_pages,
    }


def compare_entries(entries: list[dict], actual_map: dict[str, list[dict]]) -> list[dict]:
    out = []
    for entry in entries:
        matches = actual_map.get(entry["key"], [])
        if not matches:
            out.append({**entry, "actual_page": None, "status": "missing_actual"})
            continue
        actual_page = matches[0]["page"]
        status = "ok" if entry["listed_page"] == actual_page else "mismatch"
        out.append(
            {
                **entry,
                "actual_page": actual_page,
                "status": status,
                "actual_text": matches[0]["text"],
                "actual_paragraph_index": matches[0]["paragraph_index"],
            }
        )
    return out


def main() -> int:
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\pythonprojects\my_report.docx")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\directory_page_consistency_audit.json")
    )

    listed = extract_directory_entries(docx_path)
    actual = actual_pages_from_word(docx_path)

    main_compare = compare_entries(listed["toc_entries"], actual["heading_pages"])
    fig_compare = compare_entries(listed["fig_entries"], actual["fig_pages"])
    table_compare = compare_entries(listed["table_entries"], actual["table_pages"])

    out = {
        "docx": str(docx_path),
        "counts": {
            "main_toc_entries": len(main_compare),
            "figure_dir_entries": len(fig_compare),
            "table_dir_entries": len(table_compare),
            "main_mismatches": sum(1 for x in main_compare if x["status"] != "ok"),
            "figure_mismatches": sum(1 for x in fig_compare if x["status"] != "ok"),
            "table_mismatches": sum(1 for x in table_compare if x["status"] != "ok"),
        },
        "markers": listed["markers"],
        "main_toc": main_compare,
        "figure_directory": fig_compare,
        "table_directory": table_compare,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
