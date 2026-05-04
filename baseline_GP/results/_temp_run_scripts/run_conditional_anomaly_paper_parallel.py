from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from baseline_GP.marine_knownmap_runtime import (
    _json_safe,
    run_episode_single_usv_search_knownmap,
)
from baseline_GP.marine_knownmap_runtime_2usv import (
    run_episode_two_usv_search_knownmap,
)


CONDITIONAL_MODE = "ucb_anomaly_conditional"
GROUPS = {
    "single_usv_static": ("single", "static"),
    "single_usv_random_walk": ("single", "random_walk"),
    "two_usv_static": ("two", "static"),
    "two_usv_random_walk": ("two", "random_walk"),
}
KEEP_FIELDS = (
    "system_name",
    "episode_seed",
    "map_kind",
    "target_motion_mode",
    "assignment_mode",
    "clue_acquisition_mode",
    "success_all_found",
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length",
    "path_length_total",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "reservation_wait_fallback_count",
    "anomaly_conditional_alpha_final",
    "anomaly_conditional_triggered_final",
    "anomaly_gate_reason_final",
    "anomaly_conditional_alpha_mean",
    "anomaly_conditional_trigger_rate",
)
SUMMARY_METRICS = (
    "success_all_found",
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length",
    "path_length_total",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "reservation_wait_fallback_count",
    "anomaly_conditional_alpha_mean",
    "anomaly_conditional_trigger_rate",
)


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(payload), f, indent=2, ensure_ascii=False)


def _write_csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fields = tuple(keys)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in fields} for row in rows])


def _compact_result(result: dict, *, system_name: str, episode_seed: int, map_kind: str) -> dict:
    compact = {key: result.get(key) for key in KEEP_FIELDS}
    compact["system_name"] = system_name
    compact["episode_seed"] = int(episode_seed)
    compact["map_kind"] = str(map_kind)
    return compact


def _metric_mean(rows: list[dict[str, object]], metric: str) -> float | None:
    values: list[float] = []
    for row in rows:
        value = row.get(metric)
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            values.append(1.0 if value else 0.0)
        else:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
    return mean(values) if values else None


def _summary_rows(results: list[dict[str, object]], map_kinds: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for map_kind in ["ALL", *map_kinds]:
        subset = results if map_kind == "ALL" else [row for row in results if row["map_kind"] == map_kind]
        row: dict[str, object] = {
            "map_kind": map_kind,
            "clue_acquisition_mode": CONDITIONAL_MODE,
            "episode_count": len(subset),
        }
        for metric in SUMMARY_METRICS:
            row[f"{metric}_mean"] = _metric_mean(subset, metric)
        rows.append(row)
    return rows


def _load_old_rows(old_group_dir: Path) -> list[dict[str, object]]:
    fp = old_group_dir / "episode_results.csv"
    if not fp.exists():
        return []
    with fp.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _join_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("map_kind")),
        str(row.get("episode_seed")),
        str(row.get("clue_acquisition_mode")),
    )


def _compare_against_old(
    *,
    old_group_dir: Path,
    conditional_results: list[dict[str, object]],
    output_dir: Path,
) -> None:
    old_rows = _load_old_rows(old_group_dir)
    old_by_key = {_join_key(row): row for row in old_rows}
    for baseline_mode in ("ucb", "anomaly_upper_tail"):
        comparison_rows: list[dict[str, object]] = []
        for current in conditional_results:
            old = old_by_key.get(
                (str(current["map_kind"]), str(current["episode_seed"]), baseline_mode)
            )
            if old is None:
                continue
            row: dict[str, object] = {
                "map_kind": current["map_kind"],
                "episode_seed": current["episode_seed"],
                "baseline_mode": baseline_mode,
                "challenger_mode": CONDITIONAL_MODE,
            }
            for metric in SUMMARY_METRICS:
                curr_value = current.get(metric)
                old_value = old.get(metric)
                try:
                    row[f"{metric}_baseline"] = float(old_value)
                    row[f"{metric}_conditional"] = float(curr_value)
                    row[f"delta_{metric}"] = float(curr_value) - float(old_value)
                except (TypeError, ValueError):
                    row[f"{metric}_baseline"] = old_value
                    row[f"{metric}_conditional"] = curr_value
                    row[f"delta_{metric}"] = None
            comparison_rows.append(row)
        _write_csv(
            output_dir / f"delta_conditional_vs_{baseline_mode}.csv",
            comparison_rows,
        )


def run_group(*, old_root: Path, output_root: Path, group_name: str) -> Path:
    if group_name not in GROUPS:
        raise ValueError(f"Unknown group_name={group_name!r}; expected one of {sorted(GROUPS)}")
    system_kind, motion_mode = GROUPS[group_name]
    old_group_dir = old_root / group_name
    config = _read_json(old_group_dir / "config_snapshot.json")
    output_dir = output_root / group_name
    raw_dir = output_dir / "raw_results" / CONDITIONAL_MODE
    map_kinds = [str(item) for item in config["map_kinds"]]
    episode_seeds = [int(item) for item in config["episode_seeds"]]
    max_iters = int(config["max_iters"])
    base_kwargs = dict(config["base_episode_kwargs"])
    safe_nav_kwargs = dict(config["safe_nav_config"])
    episode_kwargs = {**base_kwargs, **safe_nav_kwargs}
    results: list[dict[str, object]] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    conditional_config = dict(config)
    conditional_config["clue_acquisition_modes"] = [CONDITIONAL_MODE]
    conditional_config["source_config_snapshot"] = str(old_group_dir / "config_snapshot.json")
    _write_json(output_dir / "config_snapshot.json", conditional_config)
    _write_json(raw_dir / "config_snapshot.json", conditional_config)

    for map_kind in map_kinds:
        map_results: list[dict[str, object]] = []
        for episode_seed in episode_seeds:
            print(
                f"conditional_run | group={group_name} | map={map_kind} | "
                f"seed={episode_seed} | motion={motion_mode}",
                flush=True,
            )
            if system_kind == "single":
                result = dict(
                    run_episode_single_usv_search_knownmap(
                        episode_seed=episode_seed,
                        max_iters=max_iters,
                        policy_name="marine_knownmap_path_v2_infosampled",
                        map_kind=map_kind,
                        target_motion_mode=motion_mode,
                        clue_acquisition_mode=CONDITIONAL_MODE,
                        **episode_kwargs,
                    )
                )
                system_name = "single_usv"
            else:
                result = dict(
                    run_episode_two_usv_search_knownmap(
                        episode_seed=episode_seed,
                        max_iters=max_iters,
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode=str(config.get("assignment_mode", "coordinated")),
                        map_kind=map_kind,
                        target_motion_mode=motion_mode,
                        clue_acquisition_mode=CONDITIONAL_MODE,
                        **episode_kwargs,
                    )
                )
                system_name = "two_usv_coordinated"
            compact = _compact_result(
                result,
                system_name=system_name,
                episode_seed=episode_seed,
                map_kind=map_kind,
            )
            results.append(compact)
            map_results.append(compact)
        map_dir = raw_dir / map_kind
        _write_json(map_dir / "episode_results.json", map_results)
        _write_json(map_dir / "policy_summary.json", _summary_rows(map_results, [map_kind]))

    summary_rows = _summary_rows(results, map_kinds)
    _write_csv(output_dir / "episode_results.csv", results, KEEP_FIELDS)
    _write_csv(output_dir / "main_results_by_map.csv", summary_rows)
    _write_json(
        output_dir / "summary_by_clue_mode.json",
        {CONDITIONAL_MODE: summary_rows},
    )
    _write_json(
        output_dir / "suite_summary.json",
        {
            "group_name": group_name,
            "output_dir": str(output_dir),
            "source_old_group_dir": str(old_group_dir),
            "clue_acquisition_mode": CONDITIONAL_MODE,
            "summary_rows": summary_rows,
        },
    )
    _compare_against_old(
        old_group_dir=old_group_dir,
        conditional_results=results,
        output_dir=output_dir,
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old_root", required=True)
    parser.add_argument("--output_root", required=True)
    parser.add_argument("--group", required=True, choices=tuple(GROUPS.keys()))
    args = parser.parse_args()
    output_dir = run_group(
        old_root=Path(args.old_root),
        output_root=Path(args.output_root),
        group_name=str(args.group),
    )
    print(f"conditional_output_dir={output_dir}", flush=True)


if __name__ == "__main__":
    main()
