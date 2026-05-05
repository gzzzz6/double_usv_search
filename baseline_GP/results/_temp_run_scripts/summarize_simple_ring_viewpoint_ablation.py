"""Summarize the already-run simple_ring_v1 viewpoint ablation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, pstdev


BASE_RESULTS_DIR = Path(
    r"F:\pythonprojects\baseline_GP\results\paper_parallel_run_20260501_190059"
)
OUTPUT_DIR = BASE_RESULTS_DIR / "viewpoint_simple_ring_ablation"
MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
MOTION_MODES = ("static", "random_walk")
METRICS = (
    "time_to_first_detection",
    "time_to_all_found",
    "success_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length",
    "planning_time_ms_mean",
    "candidate_pool_size_mean",
    "reachable_pool_size_mean",
    "a_star_checked_pool_size_mean",
    "selected_viewpoint_rank_mean",
)


def load_simple_rows() -> list[dict[str, object]]:
    with (OUTPUT_DIR / "simple_ring_episode_results.csv").open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_baseline_rows() -> list[dict[str, object]]:
    rows = []
    for motion_mode in MOTION_MODES:
        for map_kind in MAP_KINDS:
            fp = (
                BASE_RESULTS_DIR
                / f"single_usv_{motion_mode}"
                / "raw_results"
                / "ucb"
                / map_kind
                / "episode_results.json"
            )
            for row in json.loads(fp.read_text(encoding="utf-8")):
                rows.append({**row, "target_motion_mode": motion_mode})
    return rows


def value(row: dict[str, object], key: str) -> float | None:
    raw = row.get(key)
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if raw in ("True", "true"):
        return 1.0
    if raw in ("False", "false"):
        return 0.0
    return float(raw)


def group(rows: list[dict[str, object]], keys: tuple[str, ...]) -> dict[tuple[object, ...], list[dict[str, object]]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(tuple(row.get(key) for key in keys), []).append(row)
    return groups


def metric_mean(rows: list[dict[str, object]], metric: str) -> float | None:
    values = [value(row, metric) for row in rows]
    clean = [float(item) for item in values if item is not None]
    return mean(clean) if clean else None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def comparison_rows(group_keys: tuple[str, ...]) -> list[dict[str, object]]:
    simple_groups = group(load_simple_rows(), group_keys)
    baseline_groups = group(load_baseline_rows(), group_keys)
    rows = []
    for key in sorted(simple_groups, key=lambda item: tuple(str(v) for v in item)):
        simple = simple_groups[key]
        baseline = baseline_groups[key]
        row = {group_key: value for group_key, value in zip(group_keys, key)}
        row["n"] = len(simple)
        for metric in METRICS:
            base_mean = metric_mean(baseline, metric)
            simple_mean = metric_mean(simple, metric)
            row[f"{metric}_baseline_mean"] = base_mean
            row[f"{metric}_simple_ring_mean"] = simple_mean
            row[f"{metric}_delta"] = (
                None if base_mean is None or simple_mean is None else simple_mean - base_mean
            )
        rows.append(row)
    return rows


def main() -> None:
    write_csv(
        OUTPUT_DIR / "comparison_summary_by_motion.csv",
        comparison_rows(("target_motion_mode",)),
    )
    write_csv(
        OUTPUT_DIR / "comparison_summary_by_motion_map.csv",
        comparison_rows(("target_motion_mode", "map_kind")),
    )
    print("wrote comparison summaries")


if __name__ == "__main__":
    main()
