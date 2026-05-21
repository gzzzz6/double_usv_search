from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    path = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\docx_sections_audit_after_table_dir_regen.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    marker = data["markers"]["表目录"]
    print(
        json.dumps(
            {
                "table_dir_title": {
                    "text": marker["text"],
                    "pFormat": marker["pFormat"],
                    "runs": marker["runs"],
                },
                "figure_table_toc": data["figure_table_toc"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
