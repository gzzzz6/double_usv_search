from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    path = Path(r"F:\pythonprojects\baseline_GP\results\_temp_run_scripts\directory_page_consistency_xmlonly.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    print("COUNTS", data["counts"])
    for label, key in [
        ("主目录", "main_toc"),
        ("图目录", "figure_directory"),
        ("表目录", "table_directory"),
    ]:
        bad = [item for item in data[key] if item["status"] != "ok"]
        print()
        print(label, len(bad))
        for item in bad:
            print(
                f"{item.get('title')} | 目录={item.get('listed_page')} "
                f"实际={item.get('actual_page')} 状态={item.get('status')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
