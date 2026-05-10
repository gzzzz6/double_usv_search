"""
Formal post-avoidance anomaly comparison for single-USV episodes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from .marine_knownmap_runtime import (
        _json_safe,
        _make_output_dir,
        _write_csv,
        load_knownmap_experiment_contract,
        run_episode_single_usv_search_knownmap,
        SUPPORTED_PLANNER_ADAPTATION_MODES,
    )
except ImportError:
    from marine_knownmap_runtime import (
        _json_safe,
        _make_output_dir,
        _write_csv,
        load_knownmap_experiment_contract,
        run_episode_single_usv_search_knownmap,
        SUPPORTED_PLANNER_ADAPTATION_MODES,
    )


POST_AVOIDANCE_MAP_KINDS = ("open_water", "benchmark", "peninsula_passage")
POST_AVOIDANCE_EPISODE_SEEDS = tuple(range(10))
POST_AVOIDANCE_CLUE_MODES = ("ucb", "anomaly_upper_tail")
POST_AVOIDANCE_MAP_HEIGHT_CELLS = 40
POST_AVOIDANCE_MAP_WIDTH_CELLS = 60
POST_AVOIDANCE_CLUE_SIGMA_M = 15.0
POST_AVOIDANCE_ANOMALY_TAIL_QUANTILE = 0.90
POST_AVOIDANCE_ANOMALY_WEIGHT_LAMBDA = 1.25
DEFAULT_POST_AVOIDANCE_MOTION_MODE = "static"
POST_AVOIDANCE_POLICY_NAME = "marine_knownmap_path_v2_infosampled"
POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE = "simple_ring_v1"
POST_AVOIDANCE_SAFE_NAV_KWARGS = {
    "path_safety_mode": "soft_clearance_astar_v1",
    "safe_nav_inflation_radius_cells": 0,
    "safe_nav_soft_clearance_radius_cells": 1,
    "safe_nav_lambda_clearance": 1.0,
}
SUMMARY_METRICS = (
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
)
AUX_METRICS = (
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
)
PAIRWISE_METRICS = SUMMARY_METRICS + AUX_METRICS
PAIRWISE_INT_METRICS = {
    "time_to_first_detection",
    "time_to_all_found",
    "found_count",
    "path_invalidations_per_episode",
}


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
    planner_adaptation_mode: str,
    anomaly_tail_quantile: float,
    anomaly_weight_lambda: float,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": "single_usv_infosampled",
        "target_motion_mode": str(target_motion_mode),
        "clue_acquisition_mode": clue_acquisition_mode,
        "planner_adaptation_mode": str(planner_adaptation_mode),
        "policy_name": POST_AVOIDANCE_POLICY_NAME,
        "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
        "path_safety_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["path_safety_mode"],
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
    planner_adaptation_mode: str,
    anomaly_tail_quantile: float,
    anomaly_weight_lambda: float,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": "single_usv_infosampled",
        "target_motion_mode": str(target_motion_mode),
        "clue_acquisition_mode": clue_acquisition_mode,
        "planner_adaptation_mode": str(planner_adaptation_mode),
        "policy_name": POST_AVOIDANCE_POLICY_NAME,
        "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
        "path_safety_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["path_safety_mode"],
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
        "system_name": "single_usv_infosampled",
        "target_motion_mode": result.get("target_motion_mode"),
        "clue_acquisition_mode": result.get("clue_acquisition_mode"),
        "planner_adaptation_mode": result.get("planner_adaptation_mode"),
        "policy_name": result.get("policy_name"),
        "viewpoint_generation_mode": result.get("viewpoint_generation_mode"),
        "path_safety_mode": result.get("path_safety_mode"),
        "anomaly_tail_quantile": result.get("anomaly_tail_quantile"),
        "anomaly_weight_lambda": result.get("anomaly_weight_lambda"),
        "safe_nav_lambda_clearance": result.get("safe_nav_lambda_clearance"),
    }
    for metric_name in PAIRWISE_METRICS:
        row[metric_name] = result.get(metric_name)
    return row


def _result_identity(result: dict[str, object]) -> tuple[str, int]:
    return str(result.get("map_kind", "")), int(result["episode_seed"])


def _metric_delta(
    metric_name: str,
    *,
    baseline_result: dict[str, object],
    challenger_result: dict[str, object],
) -> int | float | None:
    baseline_value = baseline_result.get(metric_name)
    challenger_value = challenger_result.get(metric_name)
    if baseline_value is None or challenger_value is None:
        return None
    if metric_name in PAIRWISE_INT_METRICS:
        return int(challenger_value) - int(baseline_value)
    return float(challenger_value) - float(baseline_value)


def _delta_means(paired_rows: list[dict[str, object]]) -> dict[str, float | None]:
    return {
        f"{metric_name}_delta_mean": _mean_or_none(
            [
                float(row[f"{metric_name}_delta"])
                for row in paired_rows
                if row.get(f"{metric_name}_delta") is not None
            ]
        )
        for metric_name in PAIRWISE_METRICS
    }


def _summary_payload(results: list[dict[str, object]]) -> dict[str, object]:
    payload = {
        "n_episodes": int(len(results)),
        "policy_names": sorted(
            {
                str(result["policy_name"])
                for result in results
                if result.get("policy_name") is not None
            }
        ),
        "clue_acquisition_modes": sorted(
            {
                str(result["clue_acquisition_mode"])
                for result in results
                if result.get("clue_acquisition_mode") is not None
            }
        ),
        "path_safety_modes": sorted(
            {
                str(result["path_safety_mode"])
                for result in results
                if result.get("path_safety_mode") is not None
            }
        ),
        "planner_adaptation_modes": sorted(
            {
                str(result["planner_adaptation_mode"])
                for result in results
                if result.get("planner_adaptation_mode") is not None
            }
        ),
        "viewpoint_generation_modes": sorted(
            {
                str(result["viewpoint_generation_mode"])
                for result in results
                if result.get("viewpoint_generation_mode") is not None
            }
        ),
    }
    for metric_name in PAIRWISE_METRICS:
        payload[f"{metric_name}_mean"] = _mean_or_none(_metric_values(results, metric_name))
    return payload


def _summarize_pairwise_results(
    baseline_results: list[dict[str, object]],
    challenger_results: list[dict[str, object]],
) -> dict[str, object]:
    baseline_by_key = {_result_identity(result): result for result in baseline_results}
    challenger_by_key = {_result_identity(result): result for result in challenger_results}
    baseline_keys = set(baseline_by_key.keys())
    challenger_keys = set(challenger_by_key.keys())
    if baseline_keys != challenger_keys:
        raise ValueError(
            "Single-USV paired comparison requires identical (map_kind, episode_seed) support. "
            f"missing_from_challenger={sorted(baseline_keys - challenger_keys)}, "
            f"missing_from_baseline={sorted(challenger_keys - baseline_keys)}"
        )
    paired_rows: list[dict[str, object]] = []
    for map_kind, episode_seed in sorted(baseline_keys, key=lambda item: (item[0], item[1])):
        baseline_result = baseline_by_key[(map_kind, episode_seed)]
        challenger_result = challenger_by_key[(map_kind, episode_seed)]
        row: dict[str, object] = {
            "map_kind": map_kind,
            "episode_seed": int(episode_seed),
        }
        for metric_name in PAIRWISE_METRICS:
            row[f"{metric_name}_delta"] = _metric_delta(
                metric_name,
                baseline_result=baseline_result,
                challenger_result=challenger_result,
            )
        paired_rows.append(row)

    mapwise: dict[str, dict[str, object]] = {}
    for map_kind in sorted({str(result.get("map_kind", "")) for result in baseline_results}):
        map_baseline = [
            result for result in baseline_results if str(result.get("map_kind", "")) == map_kind
        ]
        map_challenger = [
            result for result in challenger_results if str(result.get("map_kind", "")) == map_kind
        ]
        map_rows = [row for row in paired_rows if str(row.get("map_kind", "")) == map_kind]
        mapwise[map_kind] = {
            "n_episodes": int(len(map_rows)),
            "baseline_summary": _summary_payload(map_baseline),
            "challenger_summary": _summary_payload(map_challenger),
            "delta_means": _delta_means(map_rows),
        }
    return {
        "paired_episode_rows": paired_rows,
        "summary": {
            "n_episodes": int(len(paired_rows)),
            "baseline_summary": _summary_payload(baseline_results),
            "challenger_summary": _summary_payload(challenger_results),
            "delta_means": _delta_means(paired_rows),
        },
        "mapwise": mapwise,
    }


def _delta_rows(
    *,
    ucb_results_by_map: dict[str, list[dict[str, object]]],
    anomaly_results_by_map: dict[str, list[dict[str, object]]],
    map_kinds: tuple[str, ...],
    target_motion_mode: str,
    planner_adaptation_mode: str,
) -> list[dict[str, object]]:
    pairwise = _summarize_pairwise_results(
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
    )
    rows: list[dict[str, object]] = []
    for map_kind in ("ALL",) + map_kinds:
        delta_means = (
            pairwise["summary"]["delta_means"]
            if map_kind == "ALL"
            else pairwise["mapwise"][map_kind]["delta_means"]
        )
        row: dict[str, object] = {
            "map_kind": map_kind,
            "baseline_clue_acquisition_mode": "ucb",
            "challenger_clue_acquisition_mode": "anomaly_upper_tail",
            "target_motion_mode": str(target_motion_mode),
            "planner_adaptation_mode": str(planner_adaptation_mode),
            "policy_name": POST_AVOIDANCE_POLICY_NAME,
            "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
            "path_safety_mode": POST_AVOIDANCE_SAFE_NAV_KWARGS["path_safety_mode"],
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
    planner_adaptation_mode: str,
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
                            "system_name": "single_usv_infosampled",
                            "target_motion_mode": str(target_motion_mode),
                            "clue_acquisition_mode": clue_acquisition_mode,
                            "planner_adaptation_mode": str(planner_adaptation_mode),
                            "policy_name": POST_AVOIDANCE_POLICY_NAME,
                            "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
                            "map_kind": map_kind,
                            "summary": _summary_payload(map_results),
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
    planner_adaptation_mode: str,
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
                    "system_name": "single_usv_infosampled",
                    "target_motion_mode": str(target_motion_mode),
                    "clue_acquisition_mode": clue_acquisition_mode,
                    "planner_adaptation_mode": str(planner_adaptation_mode),
                    "policy_name": POST_AVOIDANCE_POLICY_NAME,
                    "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
                    "map_kind": map_kind,
                    "summary": _summary_payload(map_results),
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
    clue_modes: tuple[str, ...],
) -> dict[str, dict[str, list[dict[str, object]]]]:
    results_by_clue_mode: dict[str, dict[str, list[dict[str, object]]]] = {
        clue_mode: {map_kind: [] for map_kind in map_kinds}
        for clue_mode in clue_modes
    }
    if not raw_output_dir.exists():
        return results_by_clue_mode
    for clue_acquisition_mode in clue_modes:
        for map_kind in map_kinds:
            fp = raw_output_dir / clue_acquisition_mode / map_kind / "episode_results.json"
            if not fp.exists():
                continue
            loaded = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                results_by_clue_mode[clue_acquisition_mode][map_kind] = list(loaded)
    return results_by_clue_mode


def run_single_usv_post_avoidance_anomaly_comparison(
    *,
    map_kinds: tuple[str, ...] | list[str] = POST_AVOIDANCE_MAP_KINDS,
    episode_seeds: tuple[int, ...] | list[int] = POST_AVOIDANCE_EPISODE_SEEDS,
    clue_modes: tuple[str, ...] | list[str] = POST_AVOIDANCE_CLUE_MODES,
    max_iters: int | None = None,
    motion_mode: str = DEFAULT_POST_AVOIDANCE_MOTION_MODE,
    planner_adaptation_mode: str = "adaptive",
    anomaly_tail_quantile: float = POST_AVOIDANCE_ANOMALY_TAIL_QUANTILE,
    anomaly_weight_lambda: float = POST_AVOIDANCE_ANOMALY_WEIGHT_LAMBDA,
    output_dir: str | None = None,
    save_artifacts: bool = True,
    resume_if_available: bool = True,
) -> dict[str, object]:
    contract = load_knownmap_experiment_contract()
    frozen_config = dict(contract["frozen_config"])
    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
    resolved_clue_modes = tuple(str(clue_mode) for clue_mode in clue_modes)
    invalid_map_kinds = sorted(set(resolved_map_kinds) - set(POST_AVOIDANCE_MAP_KINDS))
    if invalid_map_kinds:
        raise ValueError(
            "map_kinds must be drawn from "
            f"{POST_AVOIDANCE_MAP_KINDS}, got invalid values {invalid_map_kinds}"
        )
    invalid_clue_modes = sorted(set(resolved_clue_modes) - set(POST_AVOIDANCE_CLUE_MODES))
    if invalid_clue_modes:
        raise ValueError(
            "clue_modes must be drawn from "
            f"{POST_AVOIDANCE_CLUE_MODES}, got invalid values {invalid_clue_modes}"
        )
    if not resolved_map_kinds:
        raise ValueError("map_kinds must contain at least one map")
    if not resolved_episode_seeds:
        raise ValueError("episode_seeds must contain at least one seed")
    if not resolved_clue_modes:
        raise ValueError("clue_modes must contain at least one clue acquisition mode")
    resolved_max_iters = int(max_iters) if max_iters is not None else 240
    resolved_motion_mode = str(motion_mode)
    if resolved_motion_mode not in {"static", "random_walk"}:
        raise ValueError(
            "motion_mode must be one of {'static', 'random_walk'}, "
            f"got '{resolved_motion_mode}'"
        )
    resolved_planner_adaptation_mode = str(planner_adaptation_mode)
    if resolved_planner_adaptation_mode not in SUPPORTED_PLANNER_ADAPTATION_MODES:
        raise ValueError(
            "planner_adaptation_mode must be one of "
            f"{SUPPORTED_PLANNER_ADAPTATION_MODES}, got '{resolved_planner_adaptation_mode}'"
        )

    base_episode_kwargs = dict(frozen_config)
    for key in (
        "episode_seeds",
        "max_iters",
        "map_kind",
        "target_motion_mode",
    ):
        base_episode_kwargs.pop(key, None)
    base_episode_kwargs["map_height_cells"] = POST_AVOIDANCE_MAP_HEIGHT_CELLS
    base_episode_kwargs["map_width_cells"] = POST_AVOIDANCE_MAP_WIDTH_CELLS
    base_episode_kwargs["clue_sigma_m"] = POST_AVOIDANCE_CLUE_SIGMA_M
    base_episode_kwargs["resolution_m"] = 5.0
    base_episode_kwargs["anomaly_tail_quantile"] = float(anomaly_tail_quantile)
    base_episode_kwargs["anomaly_weight_lambda"] = float(anomaly_weight_lambda)
    base_episode_kwargs["viewpoint_generation_mode"] = POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE

    config_snapshot = {
        "map_kinds": list(resolved_map_kinds),
        "episode_seeds": list(resolved_episode_seeds),
        "max_iters": int(resolved_max_iters),
        "map_height_cells": POST_AVOIDANCE_MAP_HEIGHT_CELLS,
        "map_width_cells": POST_AVOIDANCE_MAP_WIDTH_CELLS,
        "clue_sigma_m": POST_AVOIDANCE_CLUE_SIGMA_M,
        "target_motion_mode": resolved_motion_mode,
        "planner_adaptation_mode": resolved_planner_adaptation_mode,
        "clue_acquisition_modes": list(resolved_clue_modes),
        "anomaly_upper_tail_config": {
            "anomaly_tail_quantile": float(anomaly_tail_quantile),
            "anomaly_weight_lambda": float(anomaly_weight_lambda),
            "selection_note": (
                "lambda=1.25 is the thesis formal setting selected from "
                "post-avoidance lambda sensitivity experiments; UCB ignores "
                "this anomaly weighting parameter."
            ),
        },
        "policy_name": POST_AVOIDANCE_POLICY_NAME,
        "viewpoint_generation_mode": POST_AVOIDANCE_VIEWPOINT_GENERATION_MODE,
        "safe_nav_config": dict(POST_AVOIDANCE_SAFE_NAV_KWARGS),
        "single_contract_revision_id": contract["baseline_revision_id"],
        "single_contract_schema_version": contract["schema_version"],
        "base_episode_kwargs": _json_safe(base_episode_kwargs),
    }

    default_leaf = f"single_usv_post_avoidance_anomaly_{resolved_motion_mode}"
    if (
        resolved_map_kinds != POST_AVOIDANCE_MAP_KINDS
        or resolved_clue_modes != POST_AVOIDANCE_CLUE_MODES
    ):
        map_tag = "-".join(resolved_map_kinds)
        clue_tag = "-".join(resolved_clue_modes)
        default_leaf = f"{default_leaf}_{map_tag}_{clue_tag}"
    if resolved_planner_adaptation_mode != "adaptive":
        default_leaf = f"{default_leaf}_{resolved_planner_adaptation_mode}"
    output_path = (
        _make_output_dir(
            output_dir,
            default_leaf=default_leaf,
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
                clue_modes=resolved_clue_modes,
            )
        else:
            results_by_clue_mode = {
                clue_mode: {map_kind: [] for map_kind in resolved_map_kinds}
                for clue_mode in resolved_clue_modes
            }
    else:
        results_by_clue_mode = {
            clue_mode: {map_kind: [] for map_kind in resolved_map_kinds}
            for clue_mode in resolved_clue_modes
        }

    for clue_acquisition_mode in resolved_clue_modes:
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
                    "Single post-avoidance anomaly comparison | "
                    "system=single_usv_infosampled | "
                    f"motion={resolved_motion_mode} | "
                    f"clue={clue_acquisition_mode} | "
                    f"map={map_kind} | seed={episode_seed} | max_iters={resolved_max_iters}"
                )
                result = dict(
                    run_episode_single_usv_search_knownmap(
                        episode_seed=episode_seed,
                        max_iters=resolved_max_iters,
                        policy_name=POST_AVOIDANCE_POLICY_NAME,
                        map_kind=map_kind,
                        target_motion_mode=resolved_motion_mode,
                        clue_acquisition_mode=clue_acquisition_mode,
                        planner_adaptation_mode=resolved_planner_adaptation_mode,
                        **base_episode_kwargs,
                        **POST_AVOIDANCE_SAFE_NAV_KWARGS,
                    )
                )
                result["episode_seed"] = int(episode_seed)
                result["map_kind"] = map_kind
                result["system_name"] = "single_usv_infosampled"
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
                        planner_adaptation_mode=resolved_planner_adaptation_mode,
                    )

    if output_path is not None:
        _write_raw_results(
            raw_output_dir=raw_output_dir,
            config_snapshot=config_snapshot,
            results_by_clue_mode=results_by_clue_mode,
            target_motion_mode=resolved_motion_mode,
            planner_adaptation_mode=resolved_planner_adaptation_mode,
        )

    episode_rows: list[dict[str, object]] = []
    main_rows: list[dict[str, object]] = []
    aux_rows: list[dict[str, object]] = []
    summary_by_clue_mode: dict[str, dict[str, object]] = {}
    for clue_acquisition_mode in resolved_clue_modes:
        flattened_results = [
            result
            for map_kind in resolved_map_kinds
            for result in results_by_clue_mode[clue_acquisition_mode][map_kind]
        ]
        summary_by_clue_mode[clue_acquisition_mode] = {
            "overall": _summary_payload(flattened_results),
            "mapwise": {
                map_kind: _summary_payload(results_by_clue_mode[clue_acquisition_mode][map_kind])
                for map_kind in resolved_map_kinds
            },
        }
        main_rows.append(
            _summary_row(
                map_kind="ALL",
                target_motion_mode=resolved_motion_mode,
                clue_acquisition_mode=clue_acquisition_mode,
                planner_adaptation_mode=resolved_planner_adaptation_mode,
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
                planner_adaptation_mode=resolved_planner_adaptation_mode,
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
                    planner_adaptation_mode=resolved_planner_adaptation_mode,
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
                    planner_adaptation_mode=resolved_planner_adaptation_mode,
                    anomaly_tail_quantile=float(anomaly_tail_quantile),
                    anomaly_weight_lambda=float(anomaly_weight_lambda),
                    results=map_results,
                )
            )
            episode_rows.extend(_episode_result_row(result) for result in map_results)

    if {"ucb", "anomaly_upper_tail"}.issubset(set(resolved_clue_modes)):
        delta_rows = _delta_rows(
            ucb_results_by_map=results_by_clue_mode["ucb"],
            anomaly_results_by_map=results_by_clue_mode["anomaly_upper_tail"],
            map_kinds=resolved_map_kinds,
            target_motion_mode=resolved_motion_mode,
            planner_adaptation_mode=resolved_planner_adaptation_mode,
        )
    else:
        delta_rows = []

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
        description="Run single-USV post-avoidance anomaly comparison."
    )
    parser.add_argument("--output_dir", type=str, default=None)
    parser.add_argument("--max_iters", type=int, default=None)
    parser.add_argument(
        "--map_kinds",
        type=str,
        nargs="+",
        default=None,
        choices=POST_AVOIDANCE_MAP_KINDS,
        help="Map kinds to run. Defaults to all post-avoidance thesis maps.",
    )
    parser.add_argument(
        "--episode_seeds",
        type=int,
        nargs="+",
        default=None,
        help="Episode seeds to run. Defaults to 0..9.",
    )
    parser.add_argument(
        "--clue_modes",
        type=str,
        nargs="+",
        default=None,
        choices=POST_AVOIDANCE_CLUE_MODES,
        help="Clue acquisition modes to run. Defaults to ucb and anomaly_upper_tail.",
    )
    parser.add_argument(
        "--motion_mode",
        type=str,
        default=DEFAULT_POST_AVOIDANCE_MOTION_MODE,
        choices=("static", "random_walk"),
    )
    parser.add_argument(
        "--planner_adaptation_mode",
        type=str,
        default="adaptive",
        choices=SUPPORTED_PLANNER_ADAPTATION_MODES,
        help=(
            "Deprecated compatibility switch. Both choices are accepted, "
            "but kappa_commit is currently ignored and fixed to 0."
        ),
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
    result = run_single_usv_post_avoidance_anomaly_comparison(
        output_dir=args.output_dir,
        max_iters=args.max_iters,
        map_kinds=tuple(args.map_kinds) if args.map_kinds is not None else POST_AVOIDANCE_MAP_KINDS,
        episode_seeds=(
            tuple(args.episode_seeds)
            if args.episode_seeds is not None
            else POST_AVOIDANCE_EPISODE_SEEDS
        ),
        clue_modes=tuple(args.clue_modes) if args.clue_modes is not None else POST_AVOIDANCE_CLUE_MODES,
        motion_mode=args.motion_mode,
        planner_adaptation_mode=args.planner_adaptation_mode,
        anomaly_tail_quantile=args.anomaly_tail_quantile,
        anomaly_weight_lambda=args.anomaly_weight_lambda,
        resume_if_available=not bool(args.no_resume),
    )
    print(f"single_post_avoidance_output_dir={result.get('output_dir')}")
