from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"F:\pythonprojects")

from baseline_GP.marine_knownmap_runtime import _json_safe, _write_csv
from baseline_GP.marine_knownmap_runtime_2usv import (
    PHASE7_SYSTEM_TWO_USV_COORDINATED,
    PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
    _phase7_system_summary,
    _summarize_phase7_pairwise_results,
    load_knownmap_experiment_contract_2usv,
    run_episode_two_usv_search_knownmap,
)


SUITE_OUTPUT_DIR = Path(
    r"F:\pythonprojects\baseline_GP\results\two_usv_post_avoidance_assignment_comparison\formal_20260422_seeds0_9"
)
MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
EPISODE_SEEDS = tuple(range(10))
MOTION_MODES = ("static", "random_walk")
CLUE_ACQUISITION_MODE = "ucb"
POLICY_NAME = "marine_knownmap_path_v2_infosampled_2usv"
SYSTEM_ASSIGNMENTS = (
    (PHASE7_SYSTEM_TWO_USV_INDEPENDENT, "independent"),
    (PHASE7_SYSTEM_TWO_USV_COORDINATED, "coordinated"),
)
SAFE_NAV_KWARGS = {
    "path_safety_mode": "soft_clearance_astar_v1",
    "safe_nav_inflation_radius_cells": 0,
    "safe_nav_soft_clearance_radius_cells": 1,
    "safe_nav_lambda_clearance": 1.0,
    "team_path_avoidance_mode": "reservation_v1",
    "team_reservation_safety_distance_cells": 1.5,
    "team_reservation_lambda": 1.0,
}
SUMMARY_METRICS = (
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
)
RESULT_KEEP_KEYS = (
    "episode_seed",
    "map_kind",
    "system_name",
    "assignment_mode",
    "policy_name",
    "target_motion_mode",
    "clue_acquisition_mode",
    "path_safety_mode",
    "team_path_avoidance_mode",
    "safe_nav_lambda_clearance",
    "team_reservation_lambda",
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
    "wait_count_by_usv",
    "reservation_wait_fallback_count",
    "reservation_near_neighbor_step_ratio_mean",
    "reservation_same_cell_violation_count",
    "reservation_swap_violation_count",
)


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(np.asarray(values, dtype=float)))


def _std_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.std(np.asarray(values, dtype=float), ddof=0))


def _metric_values(results: list[dict[str, object]], metric_name: str) -> list[float]:
    return [
        float(result[metric_name])
        for result in results
        if result.get(metric_name) is not None
    ]


def _raw_motion_output_dir(motion_mode: str) -> Path:
    return SUITE_OUTPUT_DIR / "raw_results" / motion_mode


def _write_raw_group(
    *,
    raw_motion_dir: Path,
    config_snapshot: dict[str, object],
    system_name: str,
    map_kind: str,
    motion_mode: str,
    map_results: list[dict[str, object]],
) -> None:
    raw_motion_dir.mkdir(parents=True, exist_ok=True)
    with (raw_motion_dir / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)
    system_output_dir = raw_motion_dir / system_name
    system_output_dir.mkdir(parents=True, exist_ok=True)
    with (system_output_dir / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)
    map_output_dir = system_output_dir / map_kind
    map_output_dir.mkdir(parents=True, exist_ok=True)
    slim_results = [
        {key: result.get(key) for key in RESULT_KEEP_KEYS}
        for result in map_results
    ]
    with (map_output_dir / "episode_results.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(slim_results), f, indent=2, ensure_ascii=False)
    with (map_output_dir / "policy_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            _json_safe(
                {
                    "system_name": system_name,
                    "target_motion_mode": motion_mode,
                    "clue_acquisition_mode": CLUE_ACQUISITION_MODE,
                    "summary": _phase7_system_summary(slim_results),
                }
            ),
            f,
            indent=2,
            ensure_ascii=False,
        )


def _load_existing_results(
    *,
    motion_modes: tuple[str, ...],
    map_kinds: tuple[str, ...],
) -> dict[str, dict[str, dict[str, list[dict[str, object]]]]]:
    results_by_motion: dict[str, dict[str, dict[str, list[dict[str, object]]]]] = {
        motion_mode: {
            system_name: {map_kind: [] for map_kind in map_kinds}
            for system_name, _ in SYSTEM_ASSIGNMENTS
        }
        for motion_mode in motion_modes
    }
    for motion_mode in motion_modes:
        raw_motion_dir = _raw_motion_output_dir(motion_mode)
        if not raw_motion_dir.exists():
            continue
        for system_name, _ in SYSTEM_ASSIGNMENTS:
            for map_kind in map_kinds:
                fp = raw_motion_dir / system_name / map_kind / "episode_results.json"
                if not fp.exists():
                    continue
                loaded = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    results_by_motion[motion_mode][system_name][map_kind] = list(loaded)
    return results_by_motion


def _summary_row(
    *,
    map_kind: str,
    motion_mode: str,
    system_name: str,
    assignment_mode: str,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": system_name,
        "assignment_mode": assignment_mode,
        "target_motion_mode": motion_mode,
        "clue_acquisition_mode": CLUE_ACQUISITION_MODE,
        "path_safety_mode": SAFE_NAV_KWARGS["path_safety_mode"],
        "team_path_avoidance_mode": SAFE_NAV_KWARGS["team_path_avoidance_mode"],
    }
    for metric_name in SUMMARY_METRICS:
        values = _metric_values(results, metric_name)
        row[f"{metric_name}_mean"] = _mean_or_none(values)
        row[f"{metric_name}_std"] = _std_or_none(values)
    return row


def _episode_row(result: dict[str, object]) -> dict[str, object]:
    return {key: result.get(key) for key in RESULT_KEEP_KEYS}


def _write_motion_outputs(
    *,
    motion_mode: str,
    results_by_system: dict[str, dict[str, list[dict[str, object]]]],
) -> dict[str, str]:
    main_rows: list[dict[str, object]] = []
    episode_rows: list[dict[str, object]] = []
    for system_name, assignment_mode in SYSTEM_ASSIGNMENTS:
        flattened_results = [
            result
            for map_kind in MAP_KINDS
            for result in results_by_system[system_name][map_kind]
        ]
        main_rows.append(
            _summary_row(
                map_kind="ALL",
                motion_mode=motion_mode,
                system_name=system_name,
                assignment_mode=assignment_mode,
                results=flattened_results,
            )
        )
        for map_kind in MAP_KINDS:
            map_results = results_by_system[system_name][map_kind]
            main_rows.append(
                _summary_row(
                    map_kind=map_kind,
                    motion_mode=motion_mode,
                    system_name=system_name,
                    assignment_mode=assignment_mode,
                    results=map_results,
                )
            )
            episode_rows.extend(_episode_row(result) for result in map_results)

    pairwise = _summarize_phase7_pairwise_results(
        [
            result
            for map_kind in MAP_KINDS
            for result in results_by_system[PHASE7_SYSTEM_TWO_USV_INDEPENDENT][map_kind]
        ],
        [
            result
            for map_kind in MAP_KINDS
            for result in results_by_system[PHASE7_SYSTEM_TWO_USV_COORDINATED][map_kind]
        ],
        baseline_system_name=PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
        challenger_system_name=PHASE7_SYSTEM_TWO_USV_COORDINATED,
    )
    delta_rows: list[dict[str, object]] = []
    for map_kind in ("ALL",) + MAP_KINDS:
        delta_means = (
            pairwise["summary"]["delta_means"]
            if map_kind == "ALL"
            else pairwise["mapwise"][map_kind]["delta_means"]
        )
        row: dict[str, object] = {
            "map_kind": map_kind,
            "baseline_system_name": PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
            "challenger_system_name": PHASE7_SYSTEM_TWO_USV_COORDINATED,
            "baseline_assignment_mode": "independent",
            "challenger_assignment_mode": "coordinated",
            "target_motion_mode": motion_mode,
            "clue_acquisition_mode": CLUE_ACQUISITION_MODE,
            "path_safety_mode": SAFE_NAV_KWARGS["path_safety_mode"],
            "team_path_avoidance_mode": SAFE_NAV_KWARGS["team_path_avoidance_mode"],
        }
        row.update(delta_means)
        delta_rows.append(row)

    main_path = _write_csv(SUITE_OUTPUT_DIR / f"{motion_mode}_main_results_by_map.csv", main_rows)
    episode_path = _write_csv(SUITE_OUTPUT_DIR / f"{motion_mode}_episode_results.csv", episode_rows)
    delta_path = _write_csv(
        SUITE_OUTPUT_DIR / f"{motion_mode}_delta_coordinated_vs_independent.csv",
        delta_rows,
    )
    with (SUITE_OUTPUT_DIR / f"{motion_mode}_coordinated_vs_independent.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(_json_safe(pairwise), f, indent=2, ensure_ascii=False)
    return {
        f"{motion_mode}_main_results_by_map.csv": str(main_path),
        f"{motion_mode}_episode_results.csv": str(episode_path),
        f"{motion_mode}_delta_coordinated_vs_independent.csv": str(delta_path),
        f"{motion_mode}_coordinated_vs_independent.json": str(
            SUITE_OUTPUT_DIR / f"{motion_mode}_coordinated_vs_independent.json"
        ),
    }


def _aggregate_all_outputs(
    *,
    results_by_motion: dict[str, dict[str, dict[str, list[dict[str, object]]]]],
) -> dict[str, str]:
    output_files: dict[str, str] = {}
    for motion_mode in MOTION_MODES:
        output_files.update(
            _write_motion_outputs(
                motion_mode=motion_mode,
                results_by_system=results_by_motion[motion_mode],
            )
        )
    with (SUITE_OUTPUT_DIR / "suite_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            _json_safe(
                {
                    "output_dir": str(SUITE_OUTPUT_DIR),
                    "config_snapshot": json.loads(
                        (SUITE_OUTPUT_DIR / "config_snapshot.json").read_text(encoding="utf-8")
                    ),
                    "output_files": output_files,
                }
            ),
            f,
            indent=2,
            ensure_ascii=False,
        )
    return output_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run or aggregate 2-USV post-avoidance coordinated vs independent comparison."
    )
    parser.add_argument("--motion_mode", choices=MOTION_MODES, default=None)
    parser.add_argument(
        "--system_name",
        choices=(PHASE7_SYSTEM_TWO_USV_INDEPENDENT, PHASE7_SYSTEM_TWO_USV_COORDINATED),
        default=None,
    )
    parser.add_argument("--aggregate_only", action="store_true")
    args = parser.parse_args()

    contract = load_knownmap_experiment_contract_2usv()
    frozen_config = dict(contract["frozen_config"])
    resolved_max_iters = int(frozen_config["max_iters"])

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

    config_snapshot = {
        "map_kinds": list(MAP_KINDS),
        "episode_seeds": list(EPISODE_SEEDS),
        "motion_modes": list(MOTION_MODES),
        "max_iters": resolved_max_iters,
        "policy_name": POLICY_NAME,
        "clue_acquisition_mode": CLUE_ACQUISITION_MODE,
        "safe_nav_config": dict(SAFE_NAV_KWARGS),
        "assignment_modes": {
            PHASE7_SYSTEM_TWO_USV_INDEPENDENT: "independent",
            PHASE7_SYSTEM_TWO_USV_COORDINATED: "coordinated",
        },
        "two_usv_contract_revision_id": contract["baseline_revision_id"],
        "two_usv_contract_schema_version": contract["schema_version"],
        "base_episode_kwargs": _json_safe(base_episode_kwargs),
    }

    SUITE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (SUITE_OUTPUT_DIR / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)

    results_by_motion = _load_existing_results(motion_modes=MOTION_MODES, map_kinds=MAP_KINDS)

    if args.aggregate_only:
        output_files = _aggregate_all_outputs(results_by_motion=results_by_motion)
        print(
            f"two_usv_post_avoidance_assignment_output_dir={SUITE_OUTPUT_DIR}",
            flush=True,
        )
        print(
            f"two_usv_post_avoidance_assignment_output_files={json.dumps(output_files, ensure_ascii=False)}",
            flush=True,
        )
        return

    selected_motion_modes = (args.motion_mode,) if args.motion_mode is not None else MOTION_MODES
    selected_system_assignments = tuple(
        (system_name, assignment_mode)
        for system_name, assignment_mode in SYSTEM_ASSIGNMENTS
        if args.system_name is None or system_name == args.system_name
    )

    for motion_mode in selected_motion_modes:
        raw_motion_dir = _raw_motion_output_dir(motion_mode)
        for system_name, assignment_mode in selected_system_assignments:
            for map_kind in MAP_KINDS:
                completed_seeds = {
                    int(result["episode_seed"])
                    for result in results_by_motion[motion_mode][system_name][map_kind]
                    if result.get("episode_seed") is not None
                }
                for episode_seed in EPISODE_SEEDS:
                    if int(episode_seed) in completed_seeds:
                        continue
                    print(
                        "2-USV post-avoidance assignment comparison | "
                        f"motion={motion_mode} | system={system_name} | "
                        f"map={map_kind} | seed={episode_seed} | max_iters={resolved_max_iters}",
                        flush=True,
                    )
                    result = dict(
                        run_episode_two_usv_search_knownmap(
                            episode_seed=episode_seed,
                            max_iters=resolved_max_iters,
                            policy_name=POLICY_NAME,
                            assignment_mode=assignment_mode,
                            map_kind=map_kind,
                            target_motion_mode=motion_mode,
                            clue_acquisition_mode=CLUE_ACQUISITION_MODE,
                            **base_episode_kwargs,
                            **SAFE_NAV_KWARGS,
                        )
                    )
                    result["episode_seed"] = int(episode_seed)
                    result["map_kind"] = map_kind
                    result["system_name"] = system_name
                    result["assignment_mode"] = assignment_mode
                    results_by_motion[motion_mode][system_name][map_kind].append(result)
                    completed_seeds.add(int(episode_seed))
                    _write_raw_group(
                        raw_motion_dir=raw_motion_dir,
                        config_snapshot=config_snapshot,
                        system_name=system_name,
                        map_kind=map_kind,
                        motion_mode=motion_mode,
                        map_results=results_by_motion[motion_mode][system_name][map_kind],
                    )

    if args.motion_mode is None and args.system_name is None:
        output_files = _aggregate_all_outputs(results_by_motion=results_by_motion)
        print(
            f"two_usv_post_avoidance_assignment_output_dir={SUITE_OUTPUT_DIR}",
            flush=True,
        )
        print(
            f"two_usv_post_avoidance_assignment_output_files={json.dumps(output_files, ensure_ascii=False)}",
            flush=True,
        )


if __name__ == "__main__":
    main()
