from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

sys.path.insert(0, r"F:\pythonprojects")

from baseline_GP.marine_knownmap_runtime_2usv import run_episode_two_usv_search_knownmap


POLICY_NAME = "marine_knownmap_path_v2_infosampled_2usv"
ASSIGNMENT_MODE = "coordinated"
MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
EPISODE_SEEDS = tuple(range(10))
TARGET_MOTION_MODES = ("static", "random_walk")
PLANNER_ADAPTATION_MODES = ("adaptive", "no_kappa")
MAX_ITERS = 240

OUTPUT_DIR = (
    Path("baseline_GP")
    / "results"
    / "kappa_ablation_two_usv_anomaly"
    / f"kappa_ablation_2usv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
)

SUMMARY_METRICS = (
    "time_to_first_detection_censored",
    "time_to_all_found_censored",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "planning_time_ms_mean",
    "path_length_total",
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


def _censored_time(value: object) -> int:
    if value is None:
        return MAX_ITERS + 1
    return int(value)


def _mean_or_none(values: list[float]) -> float | None:
    return float(mean(values)) if values else None


def _std_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    return float(pstdev(values))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _episode_row(
    *,
    planner_adaptation_mode: str,
    target_motion_mode: str,
    map_kind: str,
    seed: int,
    result: dict,
) -> dict:
    path_length_by_usv = list(result.get("path_length_by_usv", []))
    wait_count_by_usv = list(result.get("wait_count_by_usv", []))
    return {
        "planner_adaptation_mode": planner_adaptation_mode,
        "target_motion_mode": target_motion_mode,
        "map_kind": map_kind,
        "episode_seed": seed,
        "policy_name": result.get("policy_name"),
        "assignment_mode": result.get("assignment_mode"),
        "clue_acquisition_mode": result.get("clue_acquisition_mode"),
        "path_safety_mode": result.get("path_safety_mode"),
        "team_path_avoidance_mode": result.get("team_path_avoidance_mode"),
        "success_all_found": bool(result.get("success_all_found", False)),
        "time_to_first_detection": result.get("time_to_first_detection"),
        "time_to_first_detection_censored": _censored_time(
            result.get("time_to_first_detection")
        ),
        "time_to_all_found": result.get("time_to_all_found"),
        "time_to_all_found_censored": _censored_time(result.get("time_to_all_found")),
        "detection_rate": float(result.get("detection_rate", 0.0)),
        "found_count": int(result.get("found_count", 0)),
        "known_free_observation_ratio_final": float(
            result.get("known_free_observation_ratio_final", 0.0)
        ),
        "planning_time_ms_mean": float(result.get("planning_time_ms_mean", 0.0)),
        "path_length_total": int(result.get("path_length_total", 0)),
        "path_length_u0": int(path_length_by_usv[0]) if len(path_length_by_usv) > 0 else 0,
        "path_length_u1": int(path_length_by_usv[1]) if len(path_length_by_usv) > 1 else 0,
        "duplicate_viewpoint_ratio": float(result.get("duplicate_viewpoint_ratio", 0.0)),
        "cross_region_assignment_ratio": float(
            result.get("cross_region_assignment_ratio", 0.0)
        ),
        "conflict_intervention_count": int(result.get("conflict_intervention_count", 0)),
        "wait_count_total": int(result.get("wait_count_total", 0)),
        "wait_count_u0": int(wait_count_by_usv[0]) if len(wait_count_by_usv) > 0 else 0,
        "wait_count_u1": int(wait_count_by_usv[1]) if len(wait_count_by_usv) > 1 else 0,
        "reservation_wait_fallback_count": int(
            result.get("reservation_wait_fallback_count", 0)
        ),
        "reservation_near_neighbor_step_ratio_mean": float(
            result.get("reservation_near_neighbor_step_ratio_mean", 0.0)
        ),
        "reservation_same_cell_violation_count": int(
            result.get("reservation_same_cell_violation_count", 0)
        ),
        "reservation_swap_violation_count": int(
            result.get("reservation_swap_violation_count", 0)
        ),
        "anomaly_top_band_selection_ratio_pre_first_detection": float(
            result.get("anomaly_top_band_selection_ratio_pre_first_detection", 0.0)
        ),
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": float(
            result.get(
                "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
                0.0,
            )
        ),
    }


def _summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        key = (
            str(row["target_motion_mode"]),
            str(row["map_kind"]),
            str(row["planner_adaptation_mode"]),
        )
        groups.setdefault(key, []).append(row)

    summary_rows: list[dict] = []
    for (motion_mode, map_kind, planner_mode), group_rows in sorted(groups.items()):
        out = {
            "target_motion_mode": motion_mode,
            "map_kind": map_kind,
            "planner_adaptation_mode": planner_mode,
            "n_episodes": len(group_rows),
            "success_all_found_rate": _mean_or_none(
                [1.0 if row["success_all_found"] else 0.0 for row in group_rows]
            ),
        }
        for metric in SUMMARY_METRICS:
            values = [float(row.get(metric, 0.0)) for row in group_rows]
            out[f"{metric}_mean"] = _mean_or_none(values)
            out[f"{metric}_std"] = _std_or_none(values)
        summary_rows.append(out)
    return summary_rows


def _delta_rows(summary_rows: list[dict]) -> list[dict]:
    by_key = {
        (
            str(row["target_motion_mode"]),
            str(row["map_kind"]),
            str(row["planner_adaptation_mode"]),
        ): row
        for row in summary_rows
    }
    deltas: list[dict] = []
    for motion_mode in TARGET_MOTION_MODES:
        for map_kind in MAP_KINDS:
            adaptive = by_key.get((motion_mode, map_kind, "adaptive"))
            no_kappa = by_key.get((motion_mode, map_kind, "no_kappa"))
            if adaptive is None or no_kappa is None:
                continue
            row = {
                "target_motion_mode": motion_mode,
                "map_kind": map_kind,
                "delta_direction": "no_kappa_minus_adaptive",
                "success_all_found_rate_delta": float(
                    no_kappa["success_all_found_rate"] or 0.0
                )
                - float(adaptive["success_all_found_rate"] or 0.0),
            }
            for metric in SUMMARY_METRICS:
                key = f"{metric}_mean"
                row[f"{metric}_delta"] = float(no_kappa[key] or 0.0) - float(
                    adaptive[key] or 0.0
                )
            deltas.append(row)
    return deltas


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config_snapshot = {
        "experiment": "kappa_ablation_two_usv_anomaly",
        "policy_name": POLICY_NAME,
        "assignment_mode": ASSIGNMENT_MODE,
        "planner_adaptation_modes": list(PLANNER_ADAPTATION_MODES),
        "target_motion_modes": list(TARGET_MOTION_MODES),
        "map_kinds": list(MAP_KINDS),
        "episode_seeds": list(EPISODE_SEEDS),
        "max_iters": MAX_ITERS,
        "map_height_cells": 60,
        "map_width_cells": 80,
        "n_targets": 3,
        "target_count_upper_bound": 3,
        "clue_acquisition_mode": "anomaly_upper_tail",
        "anomaly_tail_quantile": 0.90,
        "anomaly_weight_lambda": 1.0,
        "clue_sigma_m": 15.0,
        "path_safety_mode": "soft_clearance_astar_v1",
        "safe_nav_inflation_radius_cells": 0,
        "safe_nav_soft_clearance_radius_cells": 1,
        "safe_nav_lambda_clearance": 1.0,
        "team_path_avoidance_mode": "reservation_v1",
        "team_reservation_safety_distance_cells": 1.5,
        "team_reservation_lambda": 1.0,
        "score_weights": {
            "search_info_gain_norm": 6.5,
            "recency_bias_norm": 2.0,
            "exec_cost_norm": -0.35,
        },
    }
    with (OUTPUT_DIR / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(config_snapshot, f, indent=2, ensure_ascii=False)

    rows: list[dict] = []
    total = (
        len(PLANNER_ADAPTATION_MODES)
        * len(TARGET_MOTION_MODES)
        * len(MAP_KINDS)
        * len(EPISODE_SEEDS)
    )
    done = 0

    for planner_mode in PLANNER_ADAPTATION_MODES:
        for motion_mode in TARGET_MOTION_MODES:
            for map_kind in MAP_KINDS:
                for seed in EPISODE_SEEDS:
                    done += 1
                    print(
                        f"[{done}/{total}] planner={planner_mode} "
                        f"motion={motion_mode} map={map_kind} seed={seed}",
                        flush=True,
                    )
                    result = run_episode_two_usv_search_knownmap(
                        episode_seed=int(seed),
                        max_iters=MAX_ITERS,
                        policy_name=POLICY_NAME,
                        assignment_mode=ASSIGNMENT_MODE,
                        n_targets=3,
                        map_kind=str(map_kind),
                        map_height_cells=60,
                        map_width_cells=80,
                        target_motion_mode=str(motion_mode),
                        target_count_mode="upper_bound",
                        target_count_upper_bound=3,
                        resolution_m=5.0,
                        sensor_range_m=25.0,
                        min_target_separation_m=30.0,
                        min_start_distance_m=40.0,
                        gp_length_scale_m=20.0,
                        gp_noise_std=0.03,
                        gp_prior_mean=0.0,
                        gp_beta=0.5,
                        gp_fit_every=5,
                        gp_optimize_hyperparams=False,
                        gp_max_points=400,
                        clue_samples_per_step=24,
                        clue_sigma_m=15.0,
                        clue_amplitude=2.0,
                        clue_noise_std=0.03,
                        search_info_clue_weight=0.5,
                        search_info_intensity_weight=0.5,
                        clue_acquisition_mode="anomaly_upper_tail",
                        anomaly_tail_quantile=0.90,
                        anomaly_weight_lambda=1.0,
                        constraint_mode="hard",
                        lambda_u_turn=2.0,
                        gamma=0.95,
                        search_commit_window=4,
                        search_commit_max_window=10,
                        search_commit_path_divisor=2,
                        segment_horizon=8,
                        top_k_anchors=6,
                        viewpoints_per_anchor=6,
                        infosampled_inspected_limit_multiplier=3.0,
                        infosampled_inspected_limit_floor=4,
                        path_safety_mode="soft_clearance_astar_v1",
                        safe_nav_inflation_radius_cells=0,
                        safe_nav_soft_clearance_radius_cells=1,
                        safe_nav_lambda_clearance=1.0,
                        team_path_avoidance_mode="reservation_v1",
                        team_reservation_safety_distance_cells=1.5,
                        team_reservation_lambda=1.0,
                        planner_adaptation_mode=str(planner_mode),
                        r_hit=1,
                        render=False,
                        show_true_targets_in_viz=False,
                    )
                    rows.append(
                        _episode_row(
                            planner_adaptation_mode=str(planner_mode),
                            target_motion_mode=str(motion_mode),
                            map_kind=str(map_kind),
                            seed=int(seed),
                            result=result,
                        )
                    )
                    _write_csv(OUTPUT_DIR / "kappa_ablation_episode_results.csv", rows)

    summary_rows = _summarize(rows)
    delta_rows = _delta_rows(summary_rows)
    _write_csv(OUTPUT_DIR / "kappa_ablation_summary_by_mode_map.csv", summary_rows)
    _write_csv(OUTPUT_DIR / "kappa_ablation_delta_no_kappa_vs_adaptive.csv", delta_rows)

    with (OUTPUT_DIR / "kappa_ablation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "output_dir": str(OUTPUT_DIR),
                "n_episode_rows": len(rows),
                "n_summary_rows": len(summary_rows),
                "n_delta_rows": len(delta_rows),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Done. Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
