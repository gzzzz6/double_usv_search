# -*- coding: utf-8 -*-
"""Run anomaly_weight_lambda sweep without changing formal runners."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_DIR = Path(__file__).resolve().parents[2]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from marine_knownmap_runtime import (  # noqa: E402
    _json_safe,
    _write_csv,
    load_knownmap_experiment_contract,
    run_episode_single_usv_search_knownmap,
)
from marine_knownmap_runtime_2usv import (  # noqa: E402
    load_knownmap_experiment_contract_2usv,
    run_episode_two_usv_search_knownmap,
)


MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
EPISODE_SEEDS = tuple(range(10))
LAMBDAS = (0.50, 0.75, 1.25)
MAX_ITERS = 240
ANOMALY_TAIL_QUANTILE = 0.90
CLUE_MODE = "anomaly_upper_tail"

SINGLE_POLICY = "marine_knownmap_path_v2_infosampled"
TWO_POLICY = "marine_knownmap_path_v2_infosampled_2usv"
TWO_ASSIGNMENT_MODE = "coordinated"

SINGLE_SAFE_NAV_KWARGS = {
    "path_safety_mode": "soft_clearance_astar_v1",
    "safe_nav_inflation_radius_cells": 0,
    "safe_nav_soft_clearance_radius_cells": 1,
    "safe_nav_lambda_clearance": 1.0,
}
TWO_SAFE_NAV_KWARGS = {
    **SINGLE_SAFE_NAV_KWARGS,
    "team_path_avoidance_mode": "reservation_v1",
    "team_reservation_safety_distance_cells": 1.5,
    "team_reservation_lambda": 1.0,
}

SINGLE_SUMMARY_METRICS = (
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "planning_time_ms_mean",
    "path_length",
    "clearance_penalty_raw_mean",
    "near_obstacle_step_ratio",
    "min_clearance_cells_mean",
    "path_invalidations_per_episode",
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
)
TWO_SUMMARY_METRICS = (
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "planning_time_ms_mean",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "conflict_intervention_count",
    "wait_count_total",
    "reservation_wait_fallback_count",
    "reservation_near_neighbor_step_ratio_mean",
    "reservation_same_cell_violation_count",
    "reservation_swap_violation_count",
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
)


def _mean(values: list[float]) -> float | None:
    return float(np.mean(np.asarray(values, dtype=float))) if values else None


def _std(values: list[float]) -> float | None:
    return float(np.std(np.asarray(values, dtype=float), ddof=0)) if values else None


def _metric_values(results: list[dict[str, Any]], metric: str) -> list[float]:
    return [
        float(result[metric])
        for result in results
        if result.get(metric) is not None and np.isfinite(float(result[metric]))
    ]


def _lambda_label(lam: float) -> str:
    return f"lambda{int(round(float(lam) * 100)):03d}"


def _load_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    return []


def _save_results(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(results), f, indent=2, ensure_ascii=False)


def _base_kwargs(system: str) -> dict[str, Any]:
    if system == "single":
        contract = load_knownmap_experiment_contract()
        frozen_config = dict(contract["frozen_config"])
        for key in ("episode_seeds", "max_iters", "map_kind", "target_motion_mode"):
            frozen_config.pop(key, None)
        frozen_config["map_height_cells"] = 40
        frozen_config["map_width_cells"] = 60
        frozen_config["clue_sigma_m"] = 15.0
        frozen_config["resolution_m"] = 5.0
        return frozen_config

    contract = load_knownmap_experiment_contract_2usv()
    frozen_config = dict(contract["frozen_config"])
    for key in (
        "episode_seeds",
        "max_iters",
        "map_kind",
        "n_usvs",
        "fixed_launch_positions",
        "target_motion_mode",
    ):
        frozen_config.pop(key, None)
    frozen_config["map_height_cells"] = 60
    frozen_config["map_width_cells"] = 80
    frozen_config["clue_sigma_m"] = 15.0
    return frozen_config


def _run_episode(
    *,
    system: str,
    seed: int,
    map_kind: str,
    motion_mode: str,
    lam: float,
    base_kwargs: dict[str, Any],
) -> dict[str, Any]:
    common = {
        "episode_seed": int(seed),
        "max_iters": MAX_ITERS,
        "map_kind": map_kind,
        "target_motion_mode": motion_mode,
        "clue_acquisition_mode": CLUE_MODE,
        "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
        "anomaly_weight_lambda": float(lam),
        **base_kwargs,
    }
    if system == "single":
        result = dict(
            run_episode_single_usv_search_knownmap(
                policy_name=SINGLE_POLICY,
                planner_adaptation_mode="adaptive",
                **common,
                **SINGLE_SAFE_NAV_KWARGS,
            )
        )
        result["system_name"] = "single_usv_infosampled"
        result["policy_name"] = SINGLE_POLICY
        result["planner_adaptation_mode"] = "adaptive"
    else:
        result = dict(
            run_episode_two_usv_search_knownmap(
                policy_name=TWO_POLICY,
                assignment_mode=TWO_ASSIGNMENT_MODE,
                planner_adaptation_mode="adaptive",
                **common,
                **TWO_SAFE_NAV_KWARGS,
            )
        )
        result["system_name"] = "two_usv_coordinated"
        result["policy_name"] = TWO_POLICY
        result["assignment_mode"] = TWO_ASSIGNMENT_MODE
    result["episode_seed"] = int(seed)
    result["map_kind"] = map_kind
    result["target_motion_mode"] = motion_mode
    result["clue_acquisition_mode"] = CLUE_MODE
    result["anomaly_tail_quantile"] = ANOMALY_TAIL_QUANTILE
    result["anomaly_weight_lambda"] = float(lam)
    return result


def _summary_rows(
    *,
    system: str,
    motion_mode: str,
    results_by_lam_map: dict[float, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metrics = SINGLE_SUMMARY_METRICS if system == "single" else TWO_SUMMARY_METRICS
    by_map_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    for lam in sorted(results_by_lam_map):
        all_results: list[dict[str, Any]] = []
        for map_kind in MAP_KINDS:
            results = results_by_lam_map[lam].get(map_kind, [])
            all_results.extend(results)
            row: dict[str, Any] = {
                "system": system,
                "target_motion_mode": motion_mode,
                "map_kind": map_kind,
                "clue_acquisition_mode": CLUE_MODE,
                "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
                "anomaly_weight_lambda": float(lam),
                "n": len(results),
            }
            for metric in metrics:
                values = _metric_values(results, metric)
                row[f"{metric}_mean"] = _mean(values)
                row[f"{metric}_std"] = _std(values)
            by_map_rows.append(row)
        overall: dict[str, Any] = {
            "system": system,
            "target_motion_mode": motion_mode,
            "map_kind": "ALL",
            "clue_acquisition_mode": CLUE_MODE,
            "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
            "anomaly_weight_lambda": float(lam),
            "n": len(all_results),
        }
        for metric in metrics:
            values = _metric_values(all_results, metric)
            overall[f"{metric}_mean"] = _mean(values)
            overall[f"{metric}_std"] = _std(values)
        overall_rows.append(overall)
    return by_map_rows, overall_rows


def run_group(*, system: str, motion_mode: str, output_root: Path, resume: bool) -> Path:
    group_name = f"{system}_usv_{motion_mode}" if system == "single" else f"two_usv_coordinated_{motion_mode}"
    output_dir = output_root / group_name
    raw_dir = output_dir / "raw_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    base_kwargs = _base_kwargs(system)
    config = {
        "system": system,
        "target_motion_mode": motion_mode,
        "map_kinds": list(MAP_KINDS),
        "episode_seeds": list(EPISODE_SEEDS),
        "max_iters": MAX_ITERS,
        "clue_acquisition_mode": CLUE_MODE,
        "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
        "anomaly_weight_lambdas": list(LAMBDAS),
        "base_episode_kwargs": _json_safe(base_kwargs),
        "safe_nav_kwargs": SINGLE_SAFE_NAV_KWARGS if system == "single" else TWO_SAFE_NAV_KWARGS,
    }
    with (output_dir / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config), f, indent=2, ensure_ascii=False)

    results_by_lam_map: dict[float, dict[str, list[dict[str, Any]]]] = {
        lam: {map_kind: [] for map_kind in MAP_KINDS} for lam in LAMBDAS
    }
    for lam in LAMBDAS:
        for map_kind in MAP_KINDS:
            result_path = raw_dir / _lambda_label(lam) / map_kind / "episode_results.json"
            existing = _load_results(result_path) if resume else []
            results_by_lam_map[lam][map_kind] = existing
            completed = {int(item["episode_seed"]) for item in existing if item.get("episode_seed") is not None}
            for seed in EPISODE_SEEDS:
                if seed in completed:
                    continue
                print(
                    "anomaly lambda sweep | "
                    f"system={system} | motion={motion_mode} | lambda={lam:.2f} | "
                    f"map={map_kind} | seed={seed} | max_iters={MAX_ITERS}",
                    flush=True,
                )
                result = _run_episode(
                    system=system,
                    seed=seed,
                    map_kind=map_kind,
                    motion_mode=motion_mode,
                    lam=lam,
                    base_kwargs=base_kwargs,
                )
                results_by_lam_map[lam][map_kind].append(result)
                _save_results(result_path, results_by_lam_map[lam][map_kind])

    episode_rows: list[dict[str, Any]] = []
    for lam in LAMBDAS:
        for map_kind in MAP_KINDS:
            episode_rows.extend(results_by_lam_map[lam][map_kind])
    by_map_rows, overall_rows = _summary_rows(
        system=system,
        motion_mode=motion_mode,
        results_by_lam_map=results_by_lam_map,
    )
    _write_csv(output_dir / "episode_results.csv", episode_rows)
    _write_csv(output_dir / "summary_by_lambda_and_map.csv", by_map_rows)
    _write_csv(output_dir / "summary_by_lambda.csv", overall_rows)
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True, choices=("single", "two"))
    parser.add_argument("--motion_mode", required=True, choices=("static", "random_walk"))
    parser.add_argument("--output_root", required=True)
    parser.add_argument("--no_resume", action="store_true")
    args = parser.parse_args()
    out = run_group(
        system=args.system,
        motion_mode=args.motion_mode,
        output_root=Path(args.output_root),
        resume=not bool(args.no_resume),
    )
    print(f"lambda_sweep_output_dir={out}", flush=True)


if __name__ == "__main__":
    main()
