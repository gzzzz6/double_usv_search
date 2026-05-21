from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    path = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\references_audit.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    for occ in data["citation_summary"]["citation_occurrences_sample"]:
        n = occ["number"]
        if n in seen:
            continue
        seen.add(n)
        if n >= 24:
            print(f"[{n}] p{occ['paragraph_index']}: {occ['context']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
