from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    path = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\references_audit.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    print("REFERENCE REGION", data["reference_region"])
    print("TITLE TEXT", data["title"]["text"])
    print("TITLE FORMAT", data["title"]["format"])
    print("TITLE RUNS", data["title"]["runs"][:2])
    print("NUMBERING", data["numbering_summary"])
    print("CITATION SUMMARY")
    for key, value in data["citation_summary"].items():
        if key != "citation_occurrences_sample":
            print(key, value)
    print("FORMAT FINDINGS")
    for item in data["format_findings"]:
        print("-", item)
    print("ITEM FINDINGS COUNT", len(data["item_findings"]))
    for item in data["item_findings"][:120]:
        print(f"- p{item['index']}: {item['issue']} | {item['text'][:180]}")
    print("REFERENCES SAMPLE")
    for item in data["references"][:40]:
        print(f"- p{item['index']} num={item['checks']['number']} lang={item['language_guess']} text={item['text'][:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
