"""
Ad hoc smoke benchmark for the 2-USV safe-nav V1 prototype.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from .marine_knownmap_runtime_2usv import (
        load_knownmap_experiment_contract_2usv,
        run_episode_two_usv_search_knownmap,
    )
except ImportError:
    from marine_knownmap_runtime_2usv import (
        load_knownmap_experiment_contract_2usv,
        run_episode_two_usv_search_knownmap,
    )


SAFE_NAV_V1_ASSIGNMENT_MODES = ("coordinated", "independent")
SAFE_NAV_V1_AVOIDANCE_GROUPS = {
    "execution_only": {
        "path_safety_mode": "off",
        "team_path_avoidance_mode": "off",
        "safe_nav_lambda_clearance": 1.0,
        "team_reservation_lambda": 1.0,
    },
    "obstacle_only": {
        "path_safety_mode": "soft_clearance_astar_v1",
        "team_path_avoidance_mode": "off",
        "safe_nav_lambda_clearance": 1.0,
        "team_reservation_lambda": 1.0,
    },
    "full_dual_avoidance_v1": {
        "path_safety_mode": "soft_clearance_astar_v1",
        "team_path_avoidance_mode": "reservation_v1",
        "safe_nav_lambda_clearance": 1.0,
        "team_reservation_lambda": 1.0,
    },
}
SAFE_NAV_V1_MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_safe(value) for key, value in row.items()})


def _mean(rows: list[dict[str, object]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return float(np.mean(np.asarray(values, dtype=float)))


def _summarize_group(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "n_episodes": int(len(rows)),
        "time_to_first_detection_mean": _mean(rows, "time_to_first_detection"),
        "time_to_all_found_mean": _mean(rows, "time_to_all_found"),
        "detection_rate_mean": _mean(rows, "detection_rate"),
        "known_free_observation_ratio_final_mean": _mean(
            rows,
            "known_free_observation_ratio_final",
        ),
        "planning_time_ms_mean": _mean(rows, "planning_time_ms_mean"),
        "conflict_intervention_count_mean": _mean(rows, "conflict_intervention_count"),
        "wait_count_total_mean": _mean(rows, "wait_count_total"),
        "reservation_wait_fallback_count_mean": _mean(
            rows,
            "reservation_wait_fallback_count",
        ),
        "reservation_near_neighbor_step_ratio_mean": _mean(
            rows,
            "reservation_near_neighbor_step_ratio_mean",
        ),
        "reservation_same_cell_violation_count_mean": _mean(
            rows,
            "reservation_same_cell_violation_count",
        ),
        "reservation_swap_violation_count_mean": _mean(
            rows,
            "reservation_swap_violation_count",
        ),
    }


def _acceptance_delta(
    baseline_rows: list[dict[str, object]],
    challenger_rows: list[dict[str, object]],
) -> dict[str, object]:
    baseline_summary = _summarize_group(baseline_rows)
    challenger_summary = _summarize_group(challenger_rows)
    conflict_baseline = baseline_summary["conflict_intervention_count_mean"]
    conflict_challenger = challenger_summary["conflict_intervention_count_mean"]
    wait_baseline = baseline_summary["wait_count_total_mean"]
    wait_challenger = challenger_summary["wait_count_total_mean"]
    planning_baseline = baseline_summary["planning_time_ms_mean"]
    planning_challenger = challenger_summary["planning_time_ms_mean"]
    return {
        "baseline_summary": baseline_summary,
        "challenger_summary": challenger_summary,
        "conflict_intervention_count_delta_mean": (
            None
            if conflict_baseline is None or conflict_challenger is None
            else float(conflict_challenger) - float(conflict_baseline)
        ),
        "wait_count_total_delta_mean": (
            None
            if wait_baseline is None or wait_challenger is None
            else float(wait_challenger) - float(wait_baseline)
        ),
        "reservation_same_cell_violation_count_mean": challenger_summary[
            "reservation_same_cell_violation_count_mean"
        ],
        "reservation_swap_violation_count_mean": challenger_summary[
            "reservation_swap_violation_count_mean"
        ],
        "planning_time_ratio_vs_execution_only": (
            None
            if planning_baseline in {None, 0.0} or planning_challenger is None
            else float(planning_challenger) / float(planning_baseline)
        ),
    }


def run_two_usv_safe_nav_v1_smoke_benchmark(
    *,
    episode_seeds: tuple[int, ...] | list[int] = (0, 1, 2, 3, 4),
    map_kinds: tuple[str, ...] | list[str] = SAFE_NAV_V1_MAP_KINDS,
    assignment_modes: tuple[str, ...] | list[str] = SAFE_NAV_V1_ASSIGNMENT_MODES,
    max_iters: int | None = None,
    output_dir: str | None = None,
    save_artifacts: bool = True,
) -> dict[str, object]:
    contract = load_knownmap_experiment_contract_2usv()
    frozen_config = dict(contract["frozen_config"])
    resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_assignment_modes = tuple(str(mode) for mode in assignment_modes)
    resolved_max_iters = (
        int(max_iters)
        if max_iters is not None
        else int(frozen_config.get("max_iters", 240))
    )
    base_episode_kwargs = dict(frozen_config)
    for key in (
        "episode_seeds",
        "max_iters",
        "map_kind",
        "n_usvs",
        "fixed_launch_positions",
        "target_motion_mode",
    ):
        base_episode_kwargs.pop(key, None)
    base_episode_kwargs["map_height_cells"] = 60
    base_episode_kwargs["map_width_cells"] = 80
    base_episode_kwargs["clue_sigma_m"] = 15.0

    results: list[dict[str, object]] = []
    for assignment_mode in resolved_assignment_modes:
        for avoidance_group, group_kwargs in SAFE_NAV_V1_AVOIDANCE_GROUPS.items():
            for map_kind in resolved_map_kinds:
                for episode_seed in resolved_episode_seeds:
                    print(
                        "Safe-nav V1 smoke | "
                        f"assignment={assignment_mode} | group={avoidance_group} | "
                        f"map={map_kind} | seed={episode_seed} | max_iters={resolved_max_iters}"
                    )
                    result = dict(
                        run_episode_two_usv_search_knownmap(
                            episode_seed=episode_seed,
                            max_iters=resolved_max_iters,
                            policy_name="marine_knownmap_path_v2_infosampled_2usv",
                            assignment_mode=assignment_mode,
                            map_kind=map_kind,
                            target_motion_mode="static",
                            **base_episode_kwargs,
                            **group_kwargs,
                        )
                    )
                    result["avoidance_group"] = avoidance_group
                    result["map_kind"] = map_kind
                    result["episode_seed"] = int(episode_seed)
                    results.append(result)

    summary_by_group_assignment: dict[str, dict[str, object]] = {}
    episode_rows: list[dict[str, object]] = []
    for assignment_mode in resolved_assignment_modes:
        for avoidance_group in SAFE_NAV_V1_AVOIDANCE_GROUPS:
            key = f"{assignment_mode}__{avoidance_group}"
            group_rows = [
                row
                for row in results
                if row["assignment_mode"] == assignment_mode
                and row["avoidance_group"] == avoidance_group
            ]
            summary_by_group_assignment[key] = _summarize_group(group_rows)
            summary_by_group_assignment[key]["assignment_mode"] = assignment_mode
            summary_by_group_assignment[key]["avoidance_group"] = avoidance_group
            for map_kind in resolved_map_kinds:
                map_rows = [row for row in group_rows if row["map_kind"] == map_kind]
                summary_by_group_assignment[key][f"{map_kind}_summary"] = _summarize_group(map_rows)

    acceptance_report = {}
    for assignment_mode in resolved_assignment_modes:
        baseline_rows = [
            row
            for row in results
            if row["assignment_mode"] == assignment_mode
            and row["avoidance_group"] == "execution_only"
        ]
        challenger_rows = [
            row
            for row in results
            if row["assignment_mode"] == assignment_mode
            and row["avoidance_group"] == "full_dual_avoidance_v1"
        ]
        acceptance_report[f"{assignment_mode}__full_dual_avoidance_v1_vs_execution_only"] = (
            _acceptance_delta(baseline_rows, challenger_rows)
        )

    for row in results:
        episode_rows.append(
            {
                "assignment_mode": row["assignment_mode"],
                "avoidance_group": row["avoidance_group"],
                "map_kind": row["map_kind"],
                "episode_seed": row["episode_seed"],
                "path_safety_mode": row.get("path_safety_mode"),
                "team_path_avoidance_mode": row.get("team_path_avoidance_mode"),
                "safe_nav_lambda_clearance": row.get("safe_nav_lambda_clearance"),
                "team_reservation_lambda": row.get("team_reservation_lambda"),
                "time_to_first_detection": row.get("time_to_first_detection"),
                "time_to_all_found": row.get("time_to_all_found"),
                "detection_rate": row.get("detection_rate"),
                "known_free_observation_ratio_final": row.get(
                    "known_free_observation_ratio_final"
                ),
                "planning_time_ms_mean": row.get("planning_time_ms_mean"),
                "conflict_intervention_count": row.get("conflict_intervention_count"),
                "wait_count_total": row.get("wait_count_total"),
                "reservation_wait_fallback_count": row.get(
                    "reservation_wait_fallback_count"
                ),
                "reservation_near_neighbor_step_ratio_mean": row.get(
                    "reservation_near_neighbor_step_ratio_mean"
                ),
                "reservation_same_cell_violation_count": row.get(
                    "reservation_same_cell_violation_count"
                ),
                "reservation_swap_violation_count": row.get(
                    "reservation_swap_violation_count"
                ),
            }
        )

    payload = {
        "created_at": datetime.now().isoformat(),
        "config_snapshot": {
            "episode_seeds": list(resolved_episode_seeds),
            "map_kinds": list(resolved_map_kinds),
            "assignment_modes": list(resolved_assignment_modes),
            "avoidance_groups": _json_safe(SAFE_NAV_V1_AVOIDANCE_GROUPS),
            "max_iters": int(resolved_max_iters),
            "base_episode_kwargs": _json_safe(base_episode_kwargs),
        },
        "summary_by_group_assignment": summary_by_group_assignment,
        "acceptance_report": acceptance_report,
    }

    if save_artifacts:
        if output_dir is None:
            output_path = Path(__file__).with_name("results") / "two_usv_safe_nav_v1_smoke" / (
                "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            )
        else:
            output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        _write_csv(output_path / "episode_results.csv", episode_rows)
        _write_csv(
            output_path / "summary_by_group_assignment.csv",
            list(summary_by_group_assignment.values()),
        )
        with (output_path / "config_snapshot.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(payload["config_snapshot"]), f, indent=2, ensure_ascii=False)
        with (output_path / "summary_by_group_assignment.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(summary_by_group_assignment), f, indent=2, ensure_ascii=False)
        with (output_path / "acceptance_report.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(acceptance_report), f, indent=2, ensure_ascii=False)
        payload["output_dir"] = str(output_path)

    return payload


if __name__ == "__main__":
    run_two_usv_safe_nav_v1_smoke_benchmark()
