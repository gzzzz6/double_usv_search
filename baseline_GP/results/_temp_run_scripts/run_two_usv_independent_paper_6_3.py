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

from baseline_GP.marine_knownmap_runtime import _json_safe
from baseline_GP.marine_knownmap_runtime_2usv import run_episode_two_usv_search_knownmap


CLUE_MODES = ("ucb", "anomaly_upper_tail")
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
    "time_to_next_detection",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length_total",
    "path_length_by_usv",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "reservation_wait_fallback_count",
    "reservation_near_neighbor_step_ratio_mean",
    "reservation_same_cell_violation_count",
    "reservation_swap_violation_count",
    "wait_count_total",
    "wait_count_by_usv",
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
)
SUMMARY_METRICS = (
    "success_all_found",
    "time_to_first_detection",
    "time_to_all_found",
    "time_to_next_detection",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length_total",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "reservation_wait_fallback_count",
    "reservation_near_neighbor_step_ratio_mean",
    "reservation_same_cell_violation_count",
    "reservation_swap_violation_count",
    "wait_count_total",
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
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
            for key in row:
                if key not in keys:
                    keys.append(key)
        fields = tuple(keys)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_mean(rows: list[dict[str, object]], metric: str) -> float | None:
    values = [_to_float(row.get(metric)) for row in rows]
    finite_values = [float(value) for value in values if value is not None]
    return mean(finite_values) if finite_values else None


def _summary_rows(
    results: list[dict[str, object]],
    *,
    map_kinds: list[str],
    clue_modes: tuple[str, ...] = CLUE_MODES,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for clue_mode in clue_modes:
        clue_subset = [row for row in results if row["clue_acquisition_mode"] == clue_mode]
        for map_kind in ["ALL", *map_kinds]:
            subset = (
                clue_subset
                if map_kind == "ALL"
                else [row for row in clue_subset if row["map_kind"] == map_kind]
            )
            row: dict[str, object] = {
                "map_kind": map_kind,
                "assignment_mode": "independent",
                "clue_acquisition_mode": clue_mode,
                "episode_count": len(subset),
            }
            for metric in SUMMARY_METRICS:
                row[f"{metric}_mean"] = _metric_mean(subset, metric)
            rows.append(row)
    return rows


def _compact_result(
    result: dict,
    *,
    episode_seed: int,
    map_kind: str,
    clue_acquisition_mode: str,
    motion_mode: str,
) -> dict[str, object]:
    compact = {key: result.get(key) for key in KEEP_FIELDS}
    compact["system_name"] = "two_usv_independent"
    compact["episode_seed"] = int(episode_seed)
    compact["map_kind"] = str(map_kind)
    compact["target_motion_mode"] = str(motion_mode)
    compact["assignment_mode"] = "independent"
    compact["clue_acquisition_mode"] = str(clue_acquisition_mode)
    return compact


def _read_old_coordinated_rows(old_group_dir: Path) -> list[dict[str, object]]:
    fp = old_group_dir / "episode_results.csv"
    if not fp.exists():
        return []
    with fp.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _comparison_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("map_kind")),
        str(row.get("episode_seed")),
        str(row.get("clue_acquisition_mode")),
    )


def _write_coordinated_delta_tables(
    *,
    old_group_dir: Path,
    independent_results: list[dict[str, object]],
    output_dir: Path,
) -> None:
    old_rows = _read_old_coordinated_rows(old_group_dir)
    old_by_key = {_comparison_key(row): row for row in old_rows}
    for clue_mode in CLUE_MODES:
        rows: list[dict[str, object]] = []
        for independent in independent_results:
            if independent["clue_acquisition_mode"] != clue_mode:
                continue
            coordinated = old_by_key.get(
                (str(independent["map_kind"]), str(independent["episode_seed"]), clue_mode)
            )
            if coordinated is None:
                continue
            row: dict[str, object] = {
                "map_kind": independent["map_kind"],
                "episode_seed": independent["episode_seed"],
                "clue_acquisition_mode": clue_mode,
                "baseline_assignment_mode": "independent",
                "challenger_assignment_mode": "coordinated",
            }
            for metric in SUMMARY_METRICS:
                independent_value = _to_float(independent.get(metric))
                coordinated_value = _to_float(coordinated.get(metric))
                row[f"{metric}_independent"] = independent.get(metric)
                row[f"{metric}_coordinated"] = coordinated.get(metric)
                row[f"delta_coordinated_minus_independent_{metric}"] = (
                    None
                    if independent_value is None or coordinated_value is None
                    else coordinated_value - independent_value
                )
            rows.append(row)
        _write_csv(output_dir / f"delta_coordinated_vs_independent_{clue_mode}.csv", rows)


def run_independent_group(
    *,
    old_root: Path,
    output_root: Path,
    motion_mode: str,
) -> Path:
    if motion_mode not in {"static", "random_walk"}:
        raise ValueError("motion_mode must be 'static' or 'random_walk'")
    old_group_dir = old_root / f"two_usv_{motion_mode}"
    config = _read_json(old_group_dir / "config_snapshot.json")
    output_dir = output_root / f"two_usv_independent_{motion_mode}"
    raw_dir = output_dir / "raw_results"
    map_kinds = [str(item) for item in config["map_kinds"]]
    episode_seeds = [int(item) for item in config["episode_seeds"]]
    max_iters = int(config["max_iters"])
    base_kwargs = dict(config["base_episode_kwargs"])
    safe_nav_kwargs = dict(config["safe_nav_config"])
    episode_kwargs = {**base_kwargs, **safe_nav_kwargs}
    results: list[dict[str, object]] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    run_config = dict(config)
    run_config["source_config_snapshot"] = str(old_group_dir / "config_snapshot.json")
    run_config["assignment_mode"] = "independent"
    run_config["clue_acquisition_modes"] = list(CLUE_MODES)
    _write_json(output_dir / "config_snapshot.json", run_config)

    for clue_mode in CLUE_MODES:
        clue_results: list[dict[str, object]] = []
        clue_dir = raw_dir / clue_mode
        _write_json(clue_dir / "config_snapshot.json", run_config)
        for map_kind in map_kinds:
            map_results: list[dict[str, object]] = []
            for episode_seed in episode_seeds:
                print(
                    f"two_usv_independent_6_3 | motion={motion_mode} | "
                    f"clue={clue_mode} | map={map_kind} | seed={episode_seed}",
                    flush=True,
                )
                result = dict(
                    run_episode_two_usv_search_knownmap(
                        episode_seed=episode_seed,
                        max_iters=max_iters,
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode="independent",
                        map_kind=map_kind,
                        target_motion_mode=motion_mode,
                        clue_acquisition_mode=clue_mode,
                        **episode_kwargs,
                    )
                )
                compact = _compact_result(
                    result,
                    episode_seed=episode_seed,
                    map_kind=map_kind,
                    clue_acquisition_mode=clue_mode,
                    motion_mode=motion_mode,
                )
                results.append(compact)
                clue_results.append(compact)
                map_results.append(compact)
            map_dir = clue_dir / map_kind
            _write_json(map_dir / "episode_results.json", map_results)
            _write_json(
                map_dir / "policy_summary.json",
                _summary_rows(map_results, map_kinds=[map_kind], clue_modes=(clue_mode,)),
            )
        _write_json(
            clue_dir / "policy_summary.json",
            _summary_rows(clue_results, map_kinds=map_kinds, clue_modes=(clue_mode,)),
        )

    summary_rows = _summary_rows(results, map_kinds=map_kinds)
    summary_by_clue_mode = {
        clue_mode: _summary_rows(
            [row for row in results if row["clue_acquisition_mode"] == clue_mode],
            map_kinds=map_kinds,
            clue_modes=(clue_mode,),
        )
        for clue_mode in CLUE_MODES
    }
    _write_csv(output_dir / "episode_results.csv", results, KEEP_FIELDS)
    _write_csv(output_dir / "main_results_by_map.csv", summary_rows)
    _write_json(output_dir / "summary_by_clue_mode.json", summary_by_clue_mode)
    _write_coordinated_delta_tables(
        old_group_dir=old_group_dir,
        independent_results=results,
        output_dir=output_dir,
    )
    _write_json(
        output_dir / "suite_summary.json",
        {
            "output_dir": str(output_dir),
            "source_old_group_dir": str(old_group_dir),
            "assignment_mode": "independent",
            "clue_acquisition_modes": list(CLUE_MODES),
            "summary_rows": summary_rows,
        },
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run only the missing 2-USV independent UCB/anomaly results for paper section 6.3."
    )
    parser.add_argument("--old_root", required=True)
    parser.add_argument("--output_root", required=True)
    parser.add_argument(
        "--motion_mode",
        required=True,
        choices=("static", "random_walk"),
    )
    args = parser.parse_args()
    output_dir = run_independent_group(
        old_root=Path(args.old_root),
        output_root=Path(args.output_root),
        motion_mode=str(args.motion_mode),
    )
    print(f"two_usv_independent_6_3_output_dir={output_dir}", flush=True)


if __name__ == "__main__":
    main()
