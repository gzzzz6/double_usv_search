"""
Formal post-avoidance anomaly comparison for 2-USV coordinated episodes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from .marine_knownmap_runtime import _json_safe, _make_output_dir, _write_csv
    from .marine_knownmap_runtime_2usv import (
        PHASE7_SYSTEM_TWO_USV_COORDINATED,
        _phase7_system_summary,
        _summarize_phase7_pairwise_results,
        load_knownmap_experiment_contract_2usv,
        run_episode_two_usv_search_knownmap,
    )
except ImportError:
    from marine_knownmap_runtime import _json_safe, _make_output_dir, _write_csv
    from marine_knownmap_runtime_2usv import (
        PHASE7_SYSTEM_TWO_USV_COORDINATED,
        _phase7_system_summary,
        _summarize_phase7_pairwise_results,
        load_knownmap_experiment_contract_2usv,
        run_episode_two_usv_search_knownmap,
    )


POST_AVOIDANCE_MAP_KINDS = ("open_water", "benchmark", "peninsula_passage")
POST_AVOIDANCE_EPISODE_SEEDS = tuple(range(10))
POST_AVOIDANCE_CLUE_MODES = ("ucb", "anomaly_upper_tail")
POST_AVOIDANCE_ANOMALY_TAIL_QUANTILE = 0.90
POST_AVOIDANCE_ANOMALY_WEIGHT_LAMBDA = 1.25
DEFAULT_POST_AVOIDANCE_MOTION_MODE = "static"
POST_AVOIDANCE_ASSIGNMENT_MODE = "coordinated"
POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE = "simple_ring_v1"
POST_AVOIDANCE_SAFE_NAV_KWARGS = {
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
AUX_METRICS = (
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
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


def _summary_row(
    *,
    map_kind: str,
    target_motion_mode: str,
    clue_acquisition_mode: str,
    anomaly_tail_quantile: float,
    anomaly_weight_lambda: float,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": PHASE7_SYSTEM_TWO_USV_COORDINATED,
        "assignment_mode": POST_AVOIDANCE_ASSIGNMENT_MODE,
        "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
        "target_motion_mode": str(target_motion_mode),
        "clue_acquisition_mode": clue_acquisition_mode,
        "anomaly_tail_quantile": (
            float(anomaly_tail_quantile)
            if clue_acquisition_mode == "anomaly_upper_tail"
            else None
        ),
        "anomaly_weight_lambda": (
            float(anomaly_weight_lambda)
            if clue_acquisition_mode == "anomaly_upper_tail"
            else None
        ),
        "path_safety_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["path_safety_mode"],
        "team_path_avoidance_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["team_path_avoidance_mode"],
    }
    for metric_name in SUMMARY_METRICS:
        values = _metric_values(results, metric_name)
        row[f"{metric_name}_mean"] = _mean_or_none(values)
        row[f"{metric_name}_std"] = _std_or_none(values)
    return row


def _aux_row(
    *,
    map_kind: str,
    target_motion_mode: str,
    clue_acquisition_mode: str,
    anomaly_tail_quantile: float,
    anomaly_weight_lambda: float,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": PHASE7_SYSTEM_TWO_USV_COORDINATED,
        "assignment_mode": POST_AVOIDANCE_ASSIGNMENT_MODE,
        "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
        "target_motion_mode": str(target_motion_mode),
        "clue_acquisition_mode": clue_acquisition_mode,
        "anomaly_tail_quantile": (
            float(anomaly_tail_quantile)
            if clue_acquisition_mode == "anomaly_upper_tail"
            else None
        ),
        "anomaly_weight_lambda": (
            float(anomaly_weight_lambda)
            if clue_acquisition_mode == "anomaly_upper_tail"
            else None
        ),
        "path_safety_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["path_safety_mode"],
        "team_path_avoidance_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["team_path_avoidance_mode"],
    }
    for metric_name in AUX_METRICS:
        values = _metric_values(results, metric_name)
        row[f"{metric_name}_mean"] = _mean_or_none(values)
        row[f"{metric_name}_std"] = _std_or_none(values)
    return row


def _episode_result_row(result: dict[str, object]) -> dict[str, object]:
    row = {
        "episode_seed": result.get("episode_seed"),
        "map_kind": result.get("map_kind"),
        "system_name": PHASE7_SYSTEM_TWO_USV_COORDINATED,
        "assignment_mode": result.get("assignment_mode"),
        "viewpoint_generation_mode": result.get("viewpoint_generation_mode"),
        "target_motion_mode": result.get("target_motion_mode"),
        "clue_acquisition_mode": result.get("clue_acquisition_mode"),
        "anomaly_tail_quantile": result.get("anomaly_tail_quantile"),
        "anomaly_weight_lambda": result.get("anomaly_weight_lambda"),
        "path_safety_mode": result.get("path_safety_mode"),
        "team_path_avoidance_mode": result.get("team_path_avoidance_mode"),
        "safe_nav_lambda_clearance": result.get("safe_nav_lambda_clearance"),
        "team_reservation_lambda": result.get("team_reservation_lambda"),
    }
    for metric_name in SUMMARY_METRICS + AUX_METRICS:
        row[metric_name] = result.get(metric_name)
    return row


def _delta_rows(
    *,
    ucb_results_by_map: dict[str, list[dict[str, object]]],
    anomaly_results_by_map: dict[str, list[dict[str, object]]],
    map_kinds: tuple[str, ...],
    target_motion_mode: str,
) -> list[dict[str, object]]:
    pairwise = _summarize_phase7_pairwise_results(
        [
            result
            for map_kind in map_kinds
            for result in ucb_results_by_map.get(map_kind, [])
        ],
        [
            result
            for map_kind in map_kinds
            for result in anomaly_results_by_map.get(map_kind, [])
        ],
        baseline_system_name="two_usv_coordinated_ucb_post_avoidance",
        challenger_system_name="two_usv_coordinated_anomaly_upper_tail_post_avoidance",
    )
    rows: list[dict[str, object]] = []
    for map_kind in ("ALL",) + map_kinds:
        if map_kind == "ALL":
            delta_means = pairwise["summary"]["delta_means"]
        else:
            delta_means = pairwise["mapwise"][map_kind]["delta_means"]
        row: dict[str, object] = {
            "map_kind": map_kind,
            "baseline_clue_acquisition_mode": "ucb",
            "challenger_clue_acquisition_mode": "anomaly_upper_tail",
            "assignment_mode": POST_AVOIDANCE_ASSIGNMENT_MODE,
            "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
            "target_motion_mode": str(target_motion_mode),
            "path_safety_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["path_safety_mode"],
            "team_path_avoidance_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["team_path_avoidance_mode"],
        }
        row.update(delta_means)
        rows.append(row)
    return rows


def _write_raw_results(
    *,
    raw_output_dir: Path,
    config_snapshot: dict[str, object],
    results_by_clue_mode: dict[str, dict[str, list[dict[str, object]]]],
    target_motion_mode: str,
) -> None:
    for clue_acquisition_mode, results_by_map in results_by_clue_mode.items():
        clue_output_dir = raw_output_dir / clue_acquisition_mode
        clue_output_dir.mkdir(parents=True, exist_ok=True)
        with (clue_output_dir / "config_snapshot.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)
        for map_kind, map_results in results_by_map.items():
            map_output_dir = clue_output_dir / map_kind
            map_output_dir.mkdir(parents=True, exist_ok=True)
            with (map_output_dir / "episode_results.json").open("w", encoding="utf-8") as f:
                json.dump(_json_safe(map_results), f, indent=2, ensure_ascii=False)
            with (map_output_dir / "policy_summary.json").open("w", encoding="utf-8") as f:
                json.dump(
                    _json_safe(
                        {
                            "system_name": PHASE7_SYSTEM_TWO_USV_COORDINATED,
                            "assignment_mode": POST_AVOIDANCE_ASSIGNMENT_MODE,
                            "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
                            "target_motion_mode": str(target_motion_mode),
                            "clue_acquisition_mode": clue_acquisition_mode,
                            "map_kind": map_kind,
                            "summary": _phase7_system_summary(map_results),
                        }
                    ),
                    f,
                    indent=2,
                    ensure_ascii=False,
                )


def _write_raw_result_group(
    *,
    raw_output_dir: Path,
    config_snapshot: dict[str, object],
    clue_acquisition_mode: str,
    map_kind: str,
    map_results: list[dict[str, object]],
    target_motion_mode: str,
) -> None:
    clue_output_dir = raw_output_dir / clue_acquisition_mode
    clue_output_dir.mkdir(parents=True, exist_ok=True)
    with (clue_output_dir / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)
    map_output_dir = clue_output_dir / map_kind
    map_output_dir.mkdir(parents=True, exist_ok=True)
    with (map_output_dir / "episode_results.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(map_results), f, indent=2, ensure_ascii=False)
    with (map_output_dir / "policy_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            _json_safe(
                {
                    "system_name": PHASE7_SYSTEM_TWO_USV_COORDINATED,
                    "assignment_mode": POST_AVOIDANCE_ASSIGNMENT_MODE,
                    "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
                    "target_motion_mode": str(target_motion_mode),
                    "clue_acquisition_mode": clue_acquisition_mode,
                    "map_kind": map_kind,
                    "summary": _phase7_system_summary(map_results),
                }
            ),
            f,
            indent=2,
            ensure_ascii=False,
        )


def _load_existing_results(
    *,
    raw_output_dir: Path,
    map_kinds: tuple[str, ...],
) -> dict[str, dict[str, list[dict[str, object]]]]:
    results_by_clue_mode: dict[str, dict[str, list[dict[str, object]]]] = {
        clue_mode: {map_kind: [] for map_kind in map_kinds}
        for clue_mode in POST_AVOIDANCE_CLUE_MODES
    }
    if not raw_output_dir.exists():
        return results_by_clue_mode
    for clue_acquisition_mode in POST_AVOIDANCE_CLUE_MODES:
        for map_kind in map_kinds:
            fp = raw_output_dir / clue_acquisition_mode / map_kind / "episode_results.json"
            if not fp.exists():
                continue
            loaded = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                results_by_clue_mode[clue_acquisition_mode][map_kind] = list(loaded)
    return results_by_clue_mode


def run_two_usv_coordinated_post_avoidance_anomaly_comparison(
    *,
    map_kinds: tuple[str, ...] | list[str] = POST_AVOIDANCE_MAP_KINDS,
    episode_seeds: tuple[int, ...] | list[int] = POST_AVOIDANCE_EPISODE_SEEDS,
    max_iters: int | None = None,
    motion_mode: str = DEFAULT_POST_AVOIDANCE_MOTION_MODE,
    anomaly_tail_quantile: float = POST_AVOIDANCE_ANOMALY_TAIL_QUANTILE,
    anomaly_weight_lambda: float = POST_AVOIDANCE_ANOMALY_WEIGHT_LAMBDA,
    output_dir: str | None = None,
    save_artifacts: bool = True,
    resume_if_available: bool = True,
) -> dict[str, object]:
    contract = load_knownmap_experiment_contract_2usv()
    frozen_config = dict(contract["frozen_config"])
    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
    resolved_max_iters = (
        int(max_iters) if max_iters is not None else int(frozen_config["max_iters"])
    )
    resolved_motion_mode = str(motion_mode)
    if resolved_motion_mode not in {"static", "random_walk"}:
        raise ValueError(
            "motion_mode must be one of {'static', 'random_walk'}, "
            f"got '{resolved_motion_mode}'"
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
    base_episode_kwargs["anomaly_tail_quantile"] = float(anomaly_tail_quantile)
    base_episode_kwargs["anomaly_weight_lambda"] = float(anomaly_weight_lambda)
    base_episode_kwargs["viewpoint_generation_mode"] = POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE

    config_snapshot = {
        "map_kinds": list(resolved_map_kinds),
        "episode_seeds": list(resolved_episode_seeds),
        "max_iters": int(resolved_max_iters),
        "assignment_mode": POST_AVOIDANCE_ASSIGNMENT_MODE,
        "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
        "target_motion_mode": resolved_motion_mode,
        "clue_acquisition_modes": list(POST_AVOIDANCE_CLUE_MODES),
        "anomaly_upper_tail_config": {
            "anomaly_tail_quantile": float(anomaly_tail_quantile),
            "anomaly_weight_lambda": float(anomaly_weight_lambda),
            "selection_note": (
                "lambda=1.25 is the thesis formal setting selected from "
                "post-avoidance lambda sensitivity experiments; UCB ignores "
                "this anomaly weighting parameter."
            ),
        },
        "safe_nav_config": dict(POST_AVOIDANCE_SAFE_NAV_KWARGS),
        "two_usv_contract_revision_id": contract["baseline_revision_id"],
        "two_usv_contract_schema_version": contract["schema_version"],
        "base_episode_kwargs": _json_safe(base_episode_kwargs),
    }

    output_path = (
        _make_output_dir(
            output_dir,
            default_leaf=f"two_usv_coordinated_post_avoidance_anomaly_{resolved_motion_mode}",
        )
        if save_artifacts
        else None
    )
    if output_path is not None:
        raw_output_dir = output_path / "raw_results"
        raw_output_dir.mkdir(parents=True, exist_ok=True)
        with (output_path / "config_snapshot.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)
        if resume_if_available:
            results_by_clue_mode = _load_existing_results(
                raw_output_dir=raw_output_dir,
                map_kinds=resolved_map_kinds,
            )
        else:
            results_by_clue_mode = {
                clue_mode: {map_kind: [] for map_kind in resolved_map_kinds}
                for clue_mode in POST_AVOIDANCE_CLUE_MODES
            }
    else:
        results_by_clue_mode = {
            clue_mode: {map_kind: [] for map_kind in resolved_map_kinds}
            for clue_mode in POST_AVOIDANCE_CLUE_MODES
        }

    for clue_acquisition_mode in POST_AVOIDANCE_CLUE_MODES:
        for map_kind in resolved_map_kinds:
            completed_seeds = {
                int(result["episode_seed"])
                for result in results_by_clue_mode[clue_acquisition_mode][map_kind]
                if result.get("episode_seed") is not None
            }
            for episode_seed in resolved_episode_seeds:
                if int(episode_seed) in completed_seeds:
                    continue
                print(
                    "Post-avoidance anomaly comparison | "
                    f"system={PHASE7_SYSTEM_TWO_USV_COORDINATED} | "
                    f"motion={resolved_motion_mode} | "
                    f"clue={clue_acquisition_mode} | "
                    f"map={map_kind} | seed={episode_seed} | max_iters={resolved_max_iters}"
                )
                result = dict(
                    run_episode_two_usv_search_knownmap(
                        episode_seed=episode_seed,
                        max_iters=resolved_max_iters,
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode=POST_AVOIDANCE_ASSIGNMENT_MODE,
                        map_kind=map_kind,
                        target_motion_mode=resolved_motion_mode,
                        clue_acquisition_mode=clue_acquisition_mode,
                        **base_episode_kwargs,
                        **POST_AVOIDANCE_SAFE_NAV_KWARGS,
                    )
                )
                result["episode_seed"] = int(episode_seed)
                result["map_kind"] = map_kind
                result["assignment_mode"] = POST_AVOIDANCE_ASSIGNMENT_MODE
                result["system_name"] = PHASE7_SYSTEM_TWO_USV_COORDINATED
                results_by_clue_mode[clue_acquisition_mode][map_kind].append(result)
                completed_seeds.add(int(episode_seed))

                if output_path is not None:
                    _write_raw_result_group(
                    raw_output_dir=raw_output_dir,
                        config_snapshot=config_snapshot,
                        clue_acquisition_mode=clue_acquisition_mode,
                        map_kind=map_kind,
                        map_results=results_by_clue_mode[clue_acquisition_mode][map_kind],
                        target_motion_mode=resolved_motion_mode,
                    )

    if output_path is not None:
        _write_raw_results(
            raw_output_dir=raw_output_dir,
            config_snapshot=config_snapshot,
            results_by_clue_mode=results_by_clue_mode,
            target_motion_mode=resolved_motion_mode,
        )

    episode_rows: list[dict[str, object]] = []
    main_rows: list[dict[str, object]] = []
    aux_rows: list[dict[str, object]] = []
    summary_by_clue_mode: dict[str, dict[str, object]] = {}
    for clue_acquisition_mode in POST_AVOIDANCE_CLUE_MODES:
        flattened_results = [
            result
            for map_kind in resolved_map_kinds
            for result in results_by_clue_mode[clue_acquisition_mode][map_kind]
        ]
        summary_by_clue_mode[clue_acquisition_mode] = {
            "overall": _phase7_system_summary(flattened_results),
            "mapwise": {
                map_kind: _phase7_system_summary(
                    results_by_clue_mode[clue_acquisition_mode][map_kind]
                )
                for map_kind in resolved_map_kinds
            },
        }
        main_rows.append(
                _summary_row(
                    map_kind="ALL",
                    target_motion_mode=resolved_motion_mode,
                    clue_acquisition_mode=clue_acquisition_mode,
                    anomaly_tail_quantile=float(anomaly_tail_quantile),
                    anomaly_weight_lambda=float(anomaly_weight_lambda),
                    results=flattened_results,
                )
        )
        aux_rows.append(
                _aux_row(
                    map_kind="ALL",
                    target_motion_mode=resolved_motion_mode,
                    clue_acquisition_mode=clue_acquisition_mode,
                    anomaly_tail_quantile=float(anomaly_tail_quantile),
                    anomaly_weight_lambda=float(anomaly_weight_lambda),
                    results=flattened_results,
                )
        )
        for map_kind in resolved_map_kinds:
            map_results = results_by_clue_mode[clue_acquisition_mode][map_kind]
            main_rows.append(
                _summary_row(
                    map_kind=map_kind,
                    target_motion_mode=resolved_motion_mode,
                    clue_acquisition_mode=clue_acquisition_mode,
                    anomaly_tail_quantile=float(anomaly_tail_quantile),
                    anomaly_weight_lambda=float(anomaly_weight_lambda),
                    results=map_results,
                )
            )
            aux_rows.append(
                _aux_row(
                    map_kind=map_kind,
                    target_motion_mode=resolved_motion_mode,
                    clue_acquisition_mode=clue_acquisition_mode,
                    anomaly_tail_quantile=float(anomaly_tail_quantile),
                    anomaly_weight_lambda=float(anomaly_weight_lambda),
                    results=map_results,
                )
            )
            episode_rows.extend(_episode_result_row(result) for result in map_results)

    delta_rows = _delta_rows(
        ucb_results_by_map=results_by_clue_mode["ucb"],
        anomaly_results_by_map=results_by_clue_mode["anomaly_upper_tail"],
        map_kinds=resolved_map_kinds,
        target_motion_mode=resolved_motion_mode,
    )

    payload = {
        "created_at": datetime.now().isoformat(),
        "config_snapshot": config_snapshot,
        "summary_by_clue_mode": summary_by_clue_mode,
        "delta_anomaly_vs_ucb": delta_rows,
    }

    if output_path is not None:
        _write_csv(output_path / "episode_results.csv", episode_rows)
        _write_csv(output_path / "main_results_by_map.csv", main_rows)
        _write_csv(output_path / "anomaly_aux_metrics_by_map.csv", aux_rows)
        _write_csv(output_path / "delta_anomaly_vs_ucb.csv", delta_rows)
        with (output_path / "summary_by_clue_mode.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(summary_by_clue_mode), f, indent=2, ensure_ascii=False)
        with (output_path / "suite_summary.json").open("w", encoding="utf-8") as f:
            json.dump(
                _json_safe(
                    {
                        "output_dir": str(output_path),
                        "config_snapshot": config_snapshot,
                        "output_files": {
                            "episode_results.csv": str(output_path / "episode_results.csv"),
                            "main_results_by_map.csv": str(output_path / "main_results_by_map.csv"),
                            "anomaly_aux_metrics_by_map.csv": str(
                                output_path / "anomaly_aux_metrics_by_map.csv"
                            ),
                            "delta_anomaly_vs_ucb.csv": str(output_path / "delta_anomaly_vs_ucb.csv"),
                            "summary_by_clue_mode.json": str(
                                output_path / "summary_by_clue_mode.json"
                            ),
                            "config_snapshot.json": str(output_path / "config_snapshot.json"),
                        },
                    }
                ),
                f,
                indent=2,
                ensure_ascii=False,
            )
        payload["output_dir"] = str(output_path)

    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run 2-USV coordinated post-avoidance anomaly comparison."
    )
    parser.add_argument("--output_dir", type=str, default=None)
    parser.add_argument("--max_iters", type=int, default=None)
    parser.add_argument(
        "--motion_mode",
        type=str,
        default=DEFAULT_POST_AVOIDANCE_MOTION_MODE,
        choices=("static", "random_walk"),
    )
    parser.add_argument(
        "--anomaly_tail_quantile",
        type=float,
        default=POST_AVOIDANCE_ANOMALY_TAIL_QUANTILE,
        help="Upper-tail quantile for anomaly_upper_tail. Defaults to thesis formal q=0.90.",
    )
    parser.add_argument(
        "--anomaly_weight_lambda",
        type=float,
        default=POST_AVOIDANCE_ANOMALY_WEIGHT_LAMBDA,
        help=(
            "Weight lambda for anomaly_upper_tail. Defaults to thesis formal "
            "lambda=1.25 selected by sensitivity experiments."
        ),
    )
    parser.add_argument(
        "--no_resume",
        action="store_true",
        help="Disable resume_if_available and rerun from scratch inside the target output_dir.",
    )
    args = parser.parse_args()
    result = run_two_usv_coordinated_post_avoidance_anomaly_comparison(
        output_dir=args.output_dir,
        max_iters=args.max_iters,
        motion_mode=args.motion_mode,
        anomaly_tail_quantile=args.anomaly_tail_quantile,
        anomaly_weight_lambda=args.anomaly_weight_lambda,
        resume_if_available=not bool(args.no_resume),
    )
    print(f"post_avoidance_output_dir={result.get('output_dir')}")
