from __future__ import annotations

import csv
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

# 按你的 Windows 工程路径
sys.path.insert(0, r"F:\pythonprojects")

import baseline_GP.core_search_policy as csp
from baseline_GP.marine_knownmap_runtime import run_episode_single_usv_search_knownmap


POLICY_NAME = "marine_knownmap_path_v2_infosampled"

MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
EPISODE_SEEDS = tuple(range(5))

MAX_ITERS = 240

# 仍然把原始经验权重标记为 current，便于后续比较。
CURRENT_WEIGHTS = (6.5, 3.0, -0.35)

OUTPUT_DIR = (
    Path("baseline_GP")
    / "results"
    / "weight_sweep_stage2_ws_wr"
    / f"stage2_ws_wr_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
)


def build_stage2_weight_configs():
    """Return the local ws-wr grid configs for stage 2.

    Stage 2 validates local combinations around the best stage-1 region:
      w_s in {4.5, 5.5, 6.5}
      w_r in {2.0, 3.0, 4.0}
      w_e fixed at -0.35
    """
    ws_values = (4.5, 5.5, 6.5)
    wr_values = (2.0, 3.0, 4.0)
    fixed_we = -0.35

    configs = []
    for ws in ws_values:
        for wr in wr_values:
            configs.append(
                {
                    "stage": "stage2_ws_wr_grid",
                    "w_s": float(ws),
                    "w_r": float(wr),
                    "w_e": float(fixed_we),
                }
            )
    return configs


@contextmanager
def patched_knownmap_weights(w_s: float, w_r: float, w_e: float):
    """Temporarily override infosampled/infofused known-map scorer weights.

    This avoids editing core_search_policy.py and keeps the frozen default intact.
    """
    original_fn = csp._knownmap_segment_weights

    def _patched_segment_weights(policy_name: str) -> dict[str, float]:
        if policy_name in {
            "marine_knownmap_path_v2_infofused",
            "marine_knownmap_path_v2_infosampled",
            "marine_knownmap_path_v2_infosampled_tree_d2",
        }:
            return {
                "search_info_gain_norm": float(w_s),
                "recency_bias_norm": float(w_r),
                "exec_cost_norm": float(w_e),
            }
        return original_fn(policy_name)

    csp._knownmap_segment_weights = _patched_segment_weights
    try:
        yield
    finally:
        csp._knownmap_segment_weights = original_fn


def censored_time_to_all_found(result: dict) -> int:
    value = result.get("time_to_all_found")
    if value is None:
        return MAX_ITERS + 1
    return int(value)


def censored_time_to_first_detection(result: dict) -> int:
    value = result.get("time_to_first_detection")
    if value is None:
        return MAX_ITERS + 1
    return int(value)


def episode_row(cfg: dict, map_kind: str, seed: int, result: dict) -> dict:
    return {
        "stage": cfg["stage"],
        "w_s": cfg["w_s"],
        "w_r": cfg["w_r"],
        "w_e": cfg["w_e"],
        "map_kind": map_kind,
        "episode_seed": seed,
        "policy_name": result.get("policy_name"),
        "target_motion_mode": result.get("target_motion_mode"),
        "clue_acquisition_mode": result.get("clue_acquisition_mode"),
        "path_safety_mode": result.get("path_safety_mode"),
        "success_all_found": bool(result.get("success_all_found", False)),
        "time_to_first_detection": result.get("time_to_first_detection"),
        "time_to_first_detection_censored": censored_time_to_first_detection(result),
        "time_to_all_found": result.get("time_to_all_found"),
        "time_to_all_found_censored": censored_time_to_all_found(result),
        "detection_rate": float(result.get("detection_rate", 0.0)),
        "found_count": int(result.get("found_count", 0)),
        "known_free_observation_ratio_final": float(
            result.get("known_free_observation_ratio_final", 0.0)
        ),
        "planning_time_ms_mean": float(result.get("planning_time_ms_mean", 0.0)),
        "path_length": int(result.get("path_length", 0)),
        "switch_count": int(result.get("switch_count", 0)),
        "anchor_switch_count": int(result.get("anchor_switch_count", 0)),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_mean(values: list[float]) -> float | None:
    return float(mean(values)) if values else None


def safe_std(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    return float(pstdev(values))


def summarize_by_config(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[float, float, float], list[dict]] = {}
    stage_by_key: dict[tuple[float, float, float], str] = {}

    for row in rows:
        key = (float(row["w_s"]), float(row["w_r"]), float(row["w_e"]))
        groups.setdefault(key, []).append(row)
        stage_by_key[key] = str(row["stage"])

    summary_rows = []
    for key, group_rows in groups.items():
        w_s, w_r, w_e = key
        n = len(group_rows)
        success_values = [1.0 if r["success_all_found"] else 0.0 for r in group_rows]

        summary_rows.append(
            {
                "stage": stage_by_key[key],
                "w_s": w_s,
                "w_r": w_r,
                "w_e": w_e,
                "n_episodes": n,
                "success_all_found_rate": safe_mean(success_values),
                "time_to_all_found_censored_mean": safe_mean(
                    [float(r["time_to_all_found_censored"]) for r in group_rows]
                ),
                "time_to_all_found_censored_std": safe_std(
                    [float(r["time_to_all_found_censored"]) for r in group_rows]
                ),
                "detection_rate_mean": safe_mean(
                    [float(r["detection_rate"]) for r in group_rows]
                ),
                "found_count_mean": safe_mean(
                    [float(r["found_count"]) for r in group_rows]
                ),
                "time_to_first_detection_censored_mean": safe_mean(
                    [float(r["time_to_first_detection_censored"]) for r in group_rows]
                ),
                "known_free_observation_ratio_final_mean": safe_mean(
                    [float(r["known_free_observation_ratio_final"]) for r in group_rows]
                ),
                "planning_time_ms_mean": safe_mean(
                    [float(r["planning_time_ms_mean"]) for r in group_rows]
                ),
                "path_length_mean": safe_mean(
                    [float(r["path_length"]) for r in group_rows]
                ),
                "switch_count_mean": safe_mean(
                    [float(r["switch_count"]) for r in group_rows]
                ),
                "anchor_switch_count_mean": safe_mean(
                    [float(r["anchor_switch_count"]) for r in group_rows]
                ),
            }
        )

    # Lexicographic ranking:
    # 1 success_all_found_rate desc
    # 2 time_to_all_found_censored_mean asc
    # 3 detection_rate_mean desc
    # 4 time_to_first_detection_censored_mean asc
    # 5 planning_time_ms_mean asc
    summary_rows.sort(
        key=lambda r: (
            -float(r["success_all_found_rate"] or 0.0),
            float(r["time_to_all_found_censored_mean"] or 1e9),
            -float(r["detection_rate_mean"] or 0.0),
            float(r["time_to_first_detection_censored_mean"] or 1e9),
            float(r["planning_time_ms_mean"] or 1e9),
        )
    )

    for idx, row in enumerate(summary_rows, start=1):
        row["rank_overall"] = idx
        row["is_current_weight"] = (
            abs(float(row["w_s"]) - CURRENT_WEIGHTS[0]) < 1e-9
            and abs(float(row["w_r"]) - CURRENT_WEIGHTS[1]) < 1e-9
            and abs(float(row["w_e"]) - CURRENT_WEIGHTS[2]) < 1e-9
        )

    return summary_rows


def summarize_marginal(rows: list[dict]) -> list[dict]:
    out = []

    for param_name in ("w_s", "w_r", "w_e"):
        values = sorted({float(row[param_name]) for row in rows})
        for value in values:
            subset = [row for row in rows if abs(float(row[param_name]) - value) < 1e-9]
            success_values = [1.0 if r["success_all_found"] else 0.0 for r in subset]
            out.append(
                {
                    "param_name": param_name,
                    "param_value": value,
                    "n_episodes": len(subset),
                    "success_all_found_rate": safe_mean(success_values),
                    "time_to_all_found_censored_mean": safe_mean(
                        [float(r["time_to_all_found_censored"]) for r in subset]
                    ),
                    "detection_rate_mean": safe_mean(
                        [float(r["detection_rate"]) for r in subset]
                    ),
                    "time_to_first_detection_censored_mean": safe_mean(
                        [float(r["time_to_first_detection_censored"]) for r in subset]
                    ),
                    "planning_time_ms_mean": safe_mean(
                        [float(r["planning_time_ms_mean"]) for r in subset]
                    ),
                }
            )

    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    weight_configs = build_stage2_weight_configs()

    config_snapshot = {
        "stage": "stage2_ws_wr_grid",
        "policy_name": POLICY_NAME,
        "map_height_cells": 40,
        "map_width_cells": 60,
        "map_kinds": list(MAP_KINDS),
        "episode_seeds": list(EPISODE_SEEDS),
        "max_iters": MAX_ITERS,
        "target_motion_mode": "static",
        "clue_acquisition_mode": "ucb",
        "path_safety_mode": "soft_clearance_astar_v1",
        "safe_nav_inflation_radius_cells": 0,
        "safe_nav_soft_clearance_radius_cells": 1,
        "safe_nav_lambda_clearance": 1.0,
        "target_count_upper_bound": 3,
        "clue_sigma_m": 15.0,
        "current_weights": {
            "w_s": CURRENT_WEIGHTS[0],
            "w_r": CURRENT_WEIGHTS[1],
            "w_e": CURRENT_WEIGHTS[2],
        },
        "weight_configs": weight_configs,
        "selection_rule": [
            "success_all_found_rate desc",
            "time_to_all_found_censored_mean asc",
            "detection_rate_mean desc",
            "time_to_first_detection_censored_mean asc",
            "planning_time_ms_mean asc",
        ],
    }

    with (OUTPUT_DIR / "weight_sweep_config_snapshot.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(config_snapshot, f, indent=2, ensure_ascii=False)

    rows = []

    total = len(weight_configs) * len(MAP_KINDS) * len(EPISODE_SEEDS)
    done = 0

    for cfg in weight_configs:
        w_s = float(cfg["w_s"])
        w_r = float(cfg["w_r"])
        w_e = float(cfg["w_e"])

        with patched_knownmap_weights(w_s, w_r, w_e):
            for map_kind in MAP_KINDS:
                for seed in EPISODE_SEEDS:
                    done += 1
                    print(
                        f"[{done}/{total}] "
                        f"stage={cfg['stage']} "
                        f"w=({w_s},{w_r},{w_e}) "
                        f"map={map_kind} seed={seed}",
                        flush=True,
                    )

                    result = run_episode_single_usv_search_knownmap(
                        episode_seed=int(seed),
                        max_iters=MAX_ITERS,
                        policy_name=POLICY_NAME,
                        n_targets=3,
                        map_kind=str(map_kind),
                        map_height_cells=40,
                        map_width_cells=60,
                        target_motion_mode="static",
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
                        gp_max_points=128,
                        clue_samples_per_step=12,
                        clue_sigma_m=15.0,
                        clue_amplitude=2.0,
                        clue_noise_std=0.03,
                        search_info_clue_weight=0.5,
                        search_info_intensity_weight=0.5,
                        clue_acquisition_mode="ucb",
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
                        planner_adaptation_mode="adaptive",
                        r_hit=1,
                        render=False,
                        show_true_targets_in_viz=False,
                        save_artifacts=False,
                    )

                    rows.append(episode_row(cfg, map_kind, int(seed), result))

                    # 每个 episode 后都落一次，避免中断丢结果。
                    write_csv(OUTPUT_DIR / "weight_sweep_episode_results.csv", rows)

    summary_rows = summarize_by_config(rows)
    marginal_rows = summarize_marginal(rows)

    write_csv(OUTPUT_DIR / "weight_sweep_summary_by_config.csv", summary_rows)
    write_csv(OUTPUT_DIR / "weight_sweep_marginal_summary.csv", marginal_rows)

    with (OUTPUT_DIR / "stage2_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "output_dir": str(OUTPUT_DIR),
                "best_config": summary_rows[0] if summary_rows else None,
                "current_config": next(
                    (row for row in summary_rows if row.get("is_current_weight")),
                    None,
                ),
                "n_episode_rows": len(rows),
                "n_weight_configs": len(weight_configs),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Done. Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()