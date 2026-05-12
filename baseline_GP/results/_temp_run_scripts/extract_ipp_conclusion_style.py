from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(r"E:\论文\海上搜索\IPP")
OUT = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\ipp_conclusion_style_snippets.json")


def get_reader(path: Path):
    try:
        from pypdf import PdfReader  # type: ignore
        return PdfReader(str(path))
    except Exception:
        from PyPDF2 import PdfReader  # type: ignore
        return PdfReader(str(path))


def norm(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def find_relevant(text: str) -> list[str]:
    low = text.lower()
    markers = [
        "conclusion",
        "conclusions",
        "future work",
        "discussion",
        "summary",
    ]
    chunks: list[str] = []
    for marker in markers:
        idx = low.find(marker)
        if idx >= 0:
            chunks.append(text[max(0, idx - 400): idx + 1800])
    return chunks[:3]


def main() -> None:
    pdfs = sorted(ROOT.glob("*.pdf"))
    results = []
    for path in pdfs:
        try:
            reader = get_reader(path)
            n = len(reader.pages)
            # Conclusions are usually in the final pages.
            text = "\n".join(
                (reader.pages[i].extract_text() or "")
                for i in range(max(0, n - 4), n)
            )
            text = norm(text)
            chunks = find_relevant(text)
            if chunks:
                results.append(
                    {
                        "name": path.name,
                        "pages": n,
                        "snippets": [norm(c)[:1800] for c in chunks],
                    }
                )
        except Exception as exc:
            results.append({"name": path.name, "error": repr(exc)})
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pdf_count": len(pdfs), "with_snippets": sum("snippets" in r for r in results), "out": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
