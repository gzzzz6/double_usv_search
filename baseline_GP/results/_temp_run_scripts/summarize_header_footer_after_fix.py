from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    xml_path = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\header_footer_pagenum_audit_after_fix.json")
    word_path = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\header_footer_word_audit_after_fix.json")
    xml = json.loads(xml_path.read_text(encoding="utf-8"))
    word = json.loads(word_path.read_text(encoding="utf-8"))

    section_summary = []
    for sec in word["sections"]:
        primary_header = sec["headers"]["primary"]
        primary_footer = sec["footers"]["primary"]
        pnums = sec["footerPageNumbers"]["primary"]
        section_summary.append(
            {
                "section": sec["section"],
                "adjusted_pages": [sec["startAdjustedPage"], sec["endAdjustedPage"]],
                "physical_pages": [sec["startPhysicalPage"], sec["endPhysicalPage"]],
                "header_text": primary_header["text"],
                "header_font": {
                    "name": primary_header["paragraph"].get("fontName"),
                    "farEast": primary_header["paragraph"].get("fontNameFarEast"),
                    "size": primary_header["paragraph"].get("fontSize"),
                    "bottomBorderLineStyle": primary_header["paragraph"].get("bottomBorderLineStyle"),
                },
                "footer_text": primary_footer["text"],
                "footer_font": {
                    "name": primary_footer["paragraph"].get("fontName"),
                    "farEast": primary_footer["paragraph"].get("fontNameFarEast"),
                    "size": primary_footer["paragraph"].get("fontSize"),
                    "alignment": primary_footer["paragraph"].get("alignment"),
                },
                "page_number": pnums,
                "footer_fields": primary_footer["fields"],
            }
        )

    print(
        json.dumps(
            {
                "xml_section_count": len(xml["sections"]),
                "xml_sections": xml["sections"],
                "word_section_summary": section_summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
