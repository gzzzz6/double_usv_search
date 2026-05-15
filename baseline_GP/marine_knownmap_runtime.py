"""
Known-static-map single-USV marine suspicious target search runtime.

This is the V2 mainline. The legacy unknown-map baseline remains in
``marine_search_runtime.py`` for historical comparison.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:
    from .core_anomaly_acquisition import (
        SUPPORTED_CLUE_ACQUISITION_MODES,
        build_knownmap_anomaly_acquisition_maps,
    )
    from .core_clue_field import build_clue_field_map, make_target_induced_clue_field, sample_clue_field
    from .core_execution import execute_next_step
    from .core_gp_field import GPSuspicionField, default_kernel
    from .core_gp_measurement import make_grid_xy
    from .core_intensity import (
        apply_known_occupancy_constraints,
        hit_update_intensity,
        init_intensity_map,
        miss_update_intensity,
        peak_intensity_ratio,
        predict_intensity,
        remaining_intensity_mass,
    )
    from .core_map import FREE, OCCUPIED, create_world, find_free_start, sensor_cells
    from .core_safe_nav import (
        build_clearance_cost_map,
        build_obstacle_distance_map,
        inflate_occupancy_map,
    )
    from .core_search_policy import (
        DEFAULT_VIEWPOINT_GENERATION_MODE,
        KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M,
        KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N,
        KNOWNMAP_SIDE_BRANCH_TREE_SECOND_LAYER_TOP_N,
        SUPPORTED_KNOWNMAP_POLICIES,
        SUPPORTED_PATH_SAFETY_MODES,
        SUPPORTED_VIEWPOINT_GENERATION_MODES,
        _knownmap_precompute_viewpoint_geometry_cache,
        _knownmap_visible_free_cells,
        select_knownmap_path_segment_policy,
    )
    from .core_staleness import (
        build_staleness_map,
        init_last_seen,
        known_free_observation_ratio,
        refresh_last_seen,
    )
    from .core_switch_penalty import move_direction
    from .core_targets import (
        PlacementInfeasibleError,
        detect_targets,
        remove_found_targets,
        sample_targets,
        step_targets,
        summarize_detection_times,
        update_found_mask,
    )
    from .viz_search import plot_search_state, save_heatmap_snapshot, save_search_snapshot
except ImportError:
    from core_anomaly_acquisition import (
        SUPPORTED_CLUE_ACQUISITION_MODES,
        build_knownmap_anomaly_acquisition_maps,
    )
    from core_clue_field import build_clue_field_map, make_target_induced_clue_field, sample_clue_field
    from core_execution import execute_next_step
    from core_gp_field import GPSuspicionField, default_kernel
    from core_gp_measurement import make_grid_xy
    from core_intensity import (
        apply_known_occupancy_constraints,
        hit_update_intensity,
        init_intensity_map,
        miss_update_intensity,
        peak_intensity_ratio,
        predict_intensity,
        remaining_intensity_mass,
    )
    from core_map import FREE, OCCUPIED, create_world, find_free_start, sensor_cells
    from core_safe_nav import (
        build_clearance_cost_map,
        build_obstacle_distance_map,
        inflate_occupancy_map,
    )
    from core_search_policy import (
        DEFAULT_VIEWPOINT_GENERATION_MODE,
        KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M,
        KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N,
        KNOWNMAP_SIDE_BRANCH_TREE_SECOND_LAYER_TOP_N,
        SUPPORTED_KNOWNMAP_POLICIES,
        SUPPORTED_PATH_SAFETY_MODES,
        SUPPORTED_VIEWPOINT_GENERATION_MODES,
        _knownmap_precompute_viewpoint_geometry_cache,
        _knownmap_visible_free_cells,
        select_knownmap_path_segment_policy,
    )
    from core_staleness import (
        build_staleness_map,
        init_last_seen,
        known_free_observation_ratio,
        refresh_last_seen,
    )
    from core_switch_penalty import move_direction
    from core_targets import (
        PlacementInfeasibleError,
        detect_targets,
        remove_found_targets,
        sample_targets,
        step_targets,
        summarize_detection_times,
        update_found_mask,
    )
    from viz_search import plot_search_state, save_heatmap_snapshot, save_search_snapshot


SEARCH_MODE = "SEARCH"
KNOWNMAP_EXPERIMENT_CONTRACT_FILENAME = "knownmap_experiment_contract.json"
KNOWNMAP_EXPERIMENT_CONTRACT_PATH = Path(__file__).with_name(KNOWNMAP_EXPERIMENT_CONTRACT_FILENAME)
# Deprecated compatibility modes. Both choices are currently accepted but ignored:
# kappa_commit is restricted to a non-decision trace field.
SUPPORTED_PLANNER_ADAPTATION_MODES = ("adaptive", "no_kappa")


def _spawn_rngs(episode_seed: int) -> dict[str, np.random.Generator]:
    seed_seq = np.random.SeedSequence(episode_seed)
    scenario_seq, detection_seq, observation_seq = seed_seq.spawn(3)
    return {
        "scenario_rng": np.random.default_rng(scenario_seq),
        "detection_rng": np.random.default_rng(detection_seq),
        "observation_rng": np.random.default_rng(observation_seq),
    }


def _sensor_range_cells(sensor_range_m: float, resolution_m: float) -> int:
    return max(1, int(round(sensor_range_m / resolution_m)))


def _distance_cells(distance_m: float, resolution_m: float) -> float:
    return float(distance_m) / float(resolution_m)


def _distance_maybe_to_m(distance_cells: float | None, resolution_m: float) -> float | None:
    if distance_cells is None:
        return None
    return float(distance_cells) * float(resolution_m)


def _write_csv(output_path: Path, rows: list[dict]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return output_path
    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            fieldnames.append(key)
            seen.add(key)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def _json_safe(value):
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if np.isnan(value):
            return None
        return value
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _make_output_dir(output_dir: str | None, default_leaf: str = "search_eval_knownmap") -> Path:
    if output_dir:
        path = Path(output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path("baseline_GP") / "results" / default_leaf / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _knownmap_contract_path(contract_path: str | None = None) -> Path:
    return Path(contract_path) if contract_path is not None else KNOWNMAP_EXPERIMENT_CONTRACT_PATH


def _assert_contract_mapping_keys(mapping: dict, required_keys: list[str], label: str) -> None:
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        raise ValueError(f"{label} missing frozen contract keys: {missing}")


def _validate_knownmap_contract_manifest(contract: dict, contract_path: Path) -> None:
    required_top_keys = [
        "baseline_revision_id",
        "schema_version",
        "frozen_policy_set",
        "frozen_config",
        "frozen_summary_keys",
        "frozen_policy_summary_keys",
        "frozen_trace_keys",
        "frozen_paired_comparison_keys",
        "initialization_semantics",
    ]
    _assert_contract_mapping_keys(contract, required_top_keys, f"known-map contract '{contract_path}'")

    frozen_policy_set = tuple(str(policy_name) for policy_name in contract["frozen_policy_set"])
    unsupported_frozen_policies = [
        policy_name for policy_name in frozen_policy_set if policy_name not in SUPPORTED_KNOWNMAP_POLICIES
    ]
    if unsupported_frozen_policies:
        raise ValueError(
            "Known-map contract frozen_policy_set contains unsupported known-map policies: "
            f"{unsupported_frozen_policies}"
        )

    frozen_config = contract["frozen_config"]
    if not isinstance(frozen_config, dict):
        raise ValueError("Known-map contract frozen_config must be a JSON object")
    _assert_contract_mapping_keys(
        frozen_config,
        [
            "map_kind",
            "episode_seeds",
            "max_iters",
            "n_targets",
            "target_motion_mode",
            "target_count_upper_bound",
            "clue_samples_per_step",
            "gp_max_points",
            "resolution_m",
            "sensor_range_m",
            "staleness_tau_steps",
            "gp_length_scale_m",
            "gp_noise_std",
            "gp_prior_mean",
            "gp_beta",
            "gp_optimize_hyperparams",
            "clue_sigma_m",
            "clue_amplitude",
            "clue_noise_std",
            "search_commit_window",
            "search_commit_max_window",
            "search_commit_path_divisor",
            "segment_horizon",
            "top_k_anchors",
            "viewpoints_per_anchor",
            "r_hit",
        ],
        f"known-map contract '{contract_path}' frozen_config",
    )
    if not isinstance(frozen_config.get("episode_seeds"), list) or not frozen_config["episode_seeds"]:
        raise ValueError("Known-map contract frozen_config.episode_seeds must be a non-empty list")
    map_height_cells = frozen_config.get("map_height_cells")
    map_width_cells = frozen_config.get("map_width_cells")
    if (map_height_cells is None) ^ (map_width_cells is None):
        raise ValueError(
            "Known-map contract frozen_config must specify both map_height_cells and map_width_cells together"
        )
    if map_height_cells is not None:
        if int(map_height_cells) < 3 or int(map_width_cells) < 3:
            raise ValueError(
                "Known-map contract frozen_config map_height_cells/map_width_cells must be >= 3"
            )

    for key_name in (
        "frozen_summary_keys",
        "frozen_policy_summary_keys",
        "frozen_trace_keys",
        "frozen_paired_comparison_keys",
    ):
        key_values = contract[key_name]
        if not isinstance(key_values, list) or not key_values:
            raise ValueError(f"Known-map contract {key_name} must be a non-empty list")
        if len(set(str(value) for value in key_values)) != len(key_values):
            raise ValueError(f"Known-map contract {key_name} contains duplicate entries")


def load_knownmap_experiment_contract(contract_path: str | None = None) -> dict[str, object]:
    resolved_path = _knownmap_contract_path(contract_path)
    with resolved_path.open("r", encoding="utf-8") as f:
        contract = json.load(f)
    _validate_knownmap_contract_manifest(contract, resolved_path)
    return contract


def _validate_knownmap_result_contract(
    result: dict,
    contract: dict | None = None,
) -> None:
    active_contract = load_knownmap_experiment_contract() if contract is None else contract
    required_summary_keys = [str(key) for key in active_contract["frozen_summary_keys"]]
    required_trace_keys = [str(key) for key in active_contract["frozen_trace_keys"]]
    _assert_contract_mapping_keys(result, required_summary_keys, "known-map result")
    for idx, row in enumerate(result.get("trace_rows", [])):
        _assert_contract_mapping_keys(row, required_trace_keys, f"known-map trace_rows[{idx}]")


def _validate_knownmap_policy_summary_contract(
    policy_summary: dict,
    contract: dict | None = None,
) -> None:
    active_contract = load_knownmap_experiment_contract() if contract is None else contract
    required_policy_summary_keys = [str(key) for key in active_contract["frozen_policy_summary_keys"]]
    _assert_contract_mapping_keys(policy_summary, required_policy_summary_keys, "known-map policy summary")


def _validate_knownmap_pairwise_contract(
    comparison_summary: dict[str, object],
    contract: dict | None = None,
) -> None:
    active_contract = load_knownmap_experiment_contract() if contract is None else contract
    required_delta_keys = [str(key) for key in active_contract["frozen_paired_comparison_keys"]]
    for idx, row in enumerate(comparison_summary.get("paired_episode_rows", [])):
        _assert_contract_mapping_keys(row, required_delta_keys, f"known-map paired_episode_rows[{idx}]")


def _resolve_knownmap_eval_contract(
    *,
    contract_path: str | None,
    n_episodes: int | None,
    max_iters: int | None,
    policy_names: tuple[str, ...] | list[str] | None,
    episode_seeds: tuple[int, ...] | list[int] | None,
    episode_kwargs: dict,
) -> tuple[dict[str, object], tuple[str, ...], tuple[int, ...], int, dict[str, object], list[str]]:
    contract = load_knownmap_experiment_contract(contract_path)
    frozen_config = dict(contract["frozen_config"])
    frozen_policy_set = tuple(str(policy_name) for policy_name in contract["frozen_policy_set"])
    frozen_episode_seeds = tuple(int(seed) for seed in frozen_config.pop("episode_seeds"))
    frozen_max_iters = int(frozen_config.pop("max_iters"))

    if policy_names is None:
        resolved_policy_names = frozen_policy_set
    else:
        resolved_policy_names = tuple(str(policy_name) for policy_name in policy_names)
        invalid_policy_names = [
            policy_name for policy_name in resolved_policy_names if policy_name not in SUPPORTED_KNOWNMAP_POLICIES
        ]
        if invalid_policy_names:
            raise ValueError(
                "Known-map evaluation policy_names must be drawn from SUPPORTED_KNOWNMAP_POLICIES: "
                f"{invalid_policy_names}"
            )

    if episode_seeds is None:
        if n_episodes is None:
            resolved_episode_seeds = frozen_episode_seeds
        elif int(n_episodes) == len(frozen_episode_seeds):
            resolved_episode_seeds = frozen_episode_seeds
        else:
            raise ValueError(
                "Known-map contract freezes an explicit episode_seeds list. "
                "Pass episode_seeds explicitly to override the contract seed list."
            )
    else:
        resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
        if n_episodes is not None and int(n_episodes) != len(resolved_episode_seeds):
            raise ValueError("n_episodes must equal len(episode_seeds) when episode_seeds is provided")

    resolved_max_iters = frozen_max_iters if max_iters is None else int(max_iters)
    effective_episode_kwargs = dict(frozen_config)
    effective_episode_kwargs.update(episode_kwargs)
    override_keys = sorted(key for key in episode_kwargs.keys() if key in frozen_config)
    if max_iters is not None and int(max_iters) != frozen_max_iters:
        override_keys.append("max_iters")
    if episode_seeds is not None and tuple(int(seed) for seed in episode_seeds) != frozen_episode_seeds:
        override_keys.append("episode_seeds")
    if policy_names is not None and tuple(str(name) for name in policy_names) != frozen_policy_set:
        override_keys.append("policy_names")
    return (
        contract,
        resolved_policy_names,
        resolved_episode_seeds,
        resolved_max_iters,
        effective_episode_kwargs,
        sorted(set(override_keys)),
    )


def _clue_field_from_state(state: dict):
    remaining = remove_found_targets(state["target_positions"], state["found_mask"])
    return make_target_induced_clue_field(
        state["true_map"],
        remaining,
        clue_sigma_cells=state["clue_sigma_cells"],
        clue_amplitude=state["clue_amplitude"],
    )


def _update_clue_truth_map(state: dict) -> None:
    state["clue_field_fn"] = _clue_field_from_state(state)
    state["clue_true_map"] = build_clue_field_map(state["clue_field_fn"], state["true_map"])


def _refresh_gp_state(
    state: dict,
    optimize_hyperparams: bool,
) -> None:
    if state["gp_field"] is None:
        return

    if optimize_hyperparams:
        state["gp_field"].refit_full()
    else:
        state["gp_field"].refit_fast()

    mu_map, var_map, acq_map = state["gp_field"].build_maps(
        state["grid_xy"],
        beta=state["gp_beta"],
    )
    occ_mask = state["nav_map_prior"] == OCCUPIED
    mu_map[occ_mask] = 0.0
    var_map[occ_mask] = 0.0
    acq_map[occ_mask] = 0.0
    state["gp_mu_map"] = mu_map
    state["gp_var_map"] = var_map
    state["gp_acq_map"] = acq_map
    state.update(
        build_knownmap_anomaly_acquisition_maps(
            gp_mu_map=mu_map,
            gp_var_map=var_map,
            gp_acq_map=acq_map,
            nav_map_prior=state["nav_map_prior"],
            clue_acquisition_mode=str(state.get("clue_acquisition_mode", "ucb")),
            anomaly_tail_quantile=float(state.get("anomaly_tail_quantile", 0.90)),
            anomaly_weight_lambda=float(state.get("anomaly_weight_lambda", 1.0)),
            step=int(state.get("current_step", state.get("completed_steps", 0))),
            gp_num_points=int(getattr(state.get("gp_field"), "n_obs", 0)),
            found_count=int(np.count_nonzero(state.get("found_mask", []))),
            prev_anomaly_top_mask=state.get("anomaly_conditional_top_mask"),
            anomaly_warmup_steps=int(state.get("anomaly_warmup_steps", 20)),
            anomaly_min_gp_points=int(state.get("anomaly_min_gp_points", 64)),
            anomaly_top_quantile=float(state.get("anomaly_top_quantile", 0.90)),
            anomaly_top_mass_min=float(state.get("anomaly_top_mass_min", 0.18)),
            anomaly_entropy_max=float(state.get("anomaly_entropy_max", 0.85)),
            anomaly_stability_min=float(state.get("anomaly_stability_min", 0.30)),
            anomaly_alpha_max=float(state.get("anomaly_alpha_max", 0.40)),
            anomaly_pre_first_alpha_cap=float(state.get("anomaly_pre_first_alpha_cap", 0.15)),
        )
    )


def _clue_heatmap_title(clue_acquisition_mode: str | None) -> str:
    if clue_acquisition_mode == "anomaly_upper_tail":
        return "GP Anomaly-Aware Clue"
    if clue_acquisition_mode == "ucb_anomaly_conditional":
        return "GP Conditional Anomaly Clue"
    return "GP Clue UCB"


def _fixed_clue_heatmap_limits(state: dict) -> tuple[float, float]:
    """Return a display-only fixed absolute scale for the clue heatmap."""
    return (0.0, 4.0)


def _remaining_target_intensity_mass(state: dict) -> float:
    """Treat intensity as a spatial belief over the exact remaining target count."""
    found_mask = np.asarray(state.get("found_mask", []), dtype=bool)
    return float(max(int(found_mask.size) - int(np.count_nonzero(found_mask)), 0))


def _segment_visible_cells(
    segment_path: list[tuple[int, int]],
    nav_map_prior: np.ndarray,
    sensor_range: int,
) -> set[tuple[int, int]]:
    visible: set[tuple[int, int]] = set()
    for cell in segment_path:
        visible.update(_knownmap_visible_free_cells(cell, nav_map_prior, sensor_range))
    return visible


def _map_value_for_cell(
    score_map: np.ndarray | None,
    cell: tuple[int, int] | None,
) -> float:
    if score_map is None or cell is None:
        return 0.0
    try:
        return float(np.asarray(score_map, dtype=float)[tuple(int(v) for v in cell)])
    except Exception:  # noqa: BLE001
        return 0.0


def _mean_map_on_cells(
    score_map: np.ndarray | None,
    cells: set[tuple[int, int]] | list[tuple[int, int]],
) -> float:
    if score_map is None or not cells:
        return 0.0
    values = [
        float(np.asarray(score_map, dtype=float)[tuple(int(v) for v in cell)])
        for cell in cells
    ]
    return _mean_or_default(values)


def _unfound_target_neighborhood_anomaly_mass_ratio(
    *,
    anomaly_map: np.ndarray | None,
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    nav_map_prior: np.ndarray,
    radius: int,
) -> float:
    if anomaly_map is None:
        return 0.0
    free_mask = nav_map_prior == FREE
    total_mass = float(np.sum(np.asarray(anomaly_map, dtype=float)[free_mask]))
    if total_mass <= 1e-9:
        return 0.0
    neighborhood_mask = np.zeros_like(nav_map_prior, dtype=bool)
    for idx, target in enumerate(np.asarray(target_positions)):
        if bool(found_mask[idx]):
            continue
        center = tuple(int(v) for v in target)
        for cell in sensor_cells(center, nav_map_prior.shape, radius):
            if nav_map_prior[cell] == FREE:
                neighborhood_mask[cell] = True
    if not np.any(neighborhood_mask):
        return 0.0
    anomaly_values = np.asarray(anomaly_map, dtype=float)
    return float(np.sum(anomaly_values[neighborhood_mask])) / total_mass


def _append_anomaly_target_neighborhood_metric(state: dict, step: int) -> None:
    state["anomaly_target_neighborhood_mass_ratio_rows"].append(
        {
            "step": int(step),
            "value": _unfound_target_neighborhood_anomaly_mass_ratio(
                anomaly_map=state.get("gp_anomaly_acq_map"),
                target_positions=state["target_positions"],
                found_mask=state["found_mask"],
                nav_map_prior=state["nav_map_prior"],
                radius=max(1, int(round(float(state.get("clue_sigma_cells", 1.0))))),
            ),
        }
    )


def _pre_first_detection_step_limit(find_times: list[int | None]) -> int | None:
    found_steps = [int(step) for step in find_times if step is not None]
    if not found_steps:
        return None
    return int(min(found_steps))


def _pre_first_detection_trace_rows(
    trace_rows: list[dict[str, object]],
    *,
    step_key: str,
    find_times: list[int | None],
) -> list[dict[str, object]]:
    step_limit = _pre_first_detection_step_limit(find_times)
    if step_limit is None:
        return list(trace_rows)
    return [
        row
        for row in trace_rows
        if int(row.get(step_key, -1)) <= int(step_limit)
    ]


def _pre_first_detection_curve_mean(
    rows: list[dict[str, object]],
    *,
    find_times: list[int | None],
) -> float:
    step_limit = _pre_first_detection_step_limit(find_times)
    filtered_rows = (
        list(rows)
        if step_limit is None
        else [row for row in rows if int(row.get("step", -1)) <= int(step_limit)]
    )
    return _mean_or_default([float(row.get("value", 0.0)) for row in filtered_rows])


def _augment_plan_details_with_anomaly(
    *,
    state: dict,
    plan_details: dict[str, object],
    segment_path: list[tuple[int, int]],
) -> dict[str, object]:
    details = dict(plan_details)
    viewpoint_cell = details.get("viewpoint_cell")
    visible_cells = _segment_visible_cells(
        list(segment_path),
        state["nav_map_prior"],
        state["sensor_range_cells"],
    )
    anomaly_prob_map = state.get("gp_anomaly_prob_map")
    anomaly_weight_map = state.get("gp_anomaly_weight_map")
    anomaly_acq_map = state.get("gp_anomaly_acq_map")
    anomaly_top_band_threshold = float(state.get("anomaly_top_band_threshold", 0.0))
    anomaly_viewpoint_prob = _map_value_for_cell(anomaly_prob_map, viewpoint_cell)
    details.update(
        {
            "clue_acquisition_mode": str(state.get("clue_acquisition_mode", "ucb")),
            "anomaly_conditional_alpha": float(state.get("anomaly_conditional_alpha", 0.0)),
            "anomaly_conditional_triggered": bool(
                state.get("anomaly_conditional_triggered", False)
            ),
            "anomaly_gate_reason": str(
                state.get("anomaly_gate_reason", "mode_not_conditional")
            ),
            "anomaly_top_mass_ratio": float(state.get("anomaly_top_mass_ratio", 0.0)),
            "anomaly_entropy_norm": float(state.get("anomaly_entropy_norm", 0.0)),
            "anomaly_hotspot_stability": float(
                state.get("anomaly_hotspot_stability", 1.0)
            ),
            "anomaly_pre_first_alpha_capped": bool(
                state.get("anomaly_pre_first_alpha_capped", False)
            ),
            "anomaly_viewpoint_prob": float(anomaly_viewpoint_prob),
            "anomaly_viewpoint_weight": _map_value_for_cell(anomaly_weight_map, viewpoint_cell),
            "anomaly_viewpoint_acq": _map_value_for_cell(anomaly_acq_map, viewpoint_cell),
            "anomaly_visible_mean": _mean_map_on_cells(anomaly_prob_map, visible_cells),
            "selected_in_anomaly_top_band": bool(
                anomaly_viewpoint_prob >= anomaly_top_band_threshold - 1e-9
            ),
        }
    )
    return details


def _safe_nav_wait_plan_details(state: dict) -> dict[str, object]:
    robot_pos = tuple(int(v) for v in state["robot_pos"])
    anchor_cell = state.get("committed_anchor") or robot_pos
    anchor_centroid_cell = state.get("committed_anchor_centroid") or robot_pos
    return {
        "path_safety_mode": str(state.get("path_safety_mode", "off")),
        "safe_nav_lambda_clearance": float(state.get("safe_nav_lambda_clearance", 0.0)),
        "anchor_cell": anchor_cell,
        "anchor_source": state.get("last_anchor_source") or "fallback_local",
        "anchor_centroid_cell": anchor_centroid_cell,
        "viewpoint_cell": robot_pos,
        "viewpoint_rule": "safe_nav_wait_fallback",
        "segment_endpoint_cell": robot_pos,
        "segment_path_length": 0,
        "planned_viewpoint_path_length": 0,
        "candidate_count": 0,
        "selected_by_final_score": False,
    }


def _normalize_knownmap_signal_map(
    score_map: np.ndarray | None,
    nav_map_prior: np.ndarray,
    clip_quantile: float = 0.98,
) -> np.ndarray:
    normalized = np.zeros_like(nav_map_prior, dtype=float)
    if score_map is None:
        return normalized
    free_mask = nav_map_prior == FREE
    if not np.any(free_mask):
        return normalized
    raw_map = np.asarray(score_map, dtype=float)
    active_values = raw_map[free_mask & np.isfinite(raw_map)]
    if active_values.size == 0:
        return normalized
    lower = float(np.min(active_values))
    upper = float(np.quantile(active_values, clip_quantile))
    if upper <= lower + 1e-9:
        upper = float(np.max(active_values))
    if upper <= lower + 1e-9:
        return normalized
    clipped = np.clip(raw_map, lower, upper)
    normalized[free_mask] = (clipped[free_mask] - lower) / (upper - lower)
    normalized[nav_map_prior == OCCUPIED] = 0.0
    normalized[~np.isfinite(normalized)] = 0.0
    return normalized


def _build_search_info_maps(
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    nav_map_prior: np.ndarray,
    clue_weight: float,
    intensity_weight: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    clue_component = _normalize_knownmap_signal_map(clue_map, nav_map_prior)
    intensity_component = _normalize_knownmap_signal_map(intensity_map, nav_map_prior)
    total_weight = float(max(0.0, clue_weight)) + float(max(0.0, intensity_weight))
    if total_weight <= 1e-9:
        clue_mix = 0.5
        intensity_mix = 0.5
    else:
        clue_mix = float(max(0.0, clue_weight)) / total_weight
        intensity_mix = float(max(0.0, intensity_weight)) / total_weight
    weighted_clue = clue_mix * clue_component
    weighted_intensity = intensity_mix * intensity_component
    search_info_map = weighted_clue + weighted_intensity
    search_info_map[nav_map_prior == OCCUPIED] = 0.0
    return search_info_map, weighted_clue, weighted_intensity


def _search_info_stats(
    search_info_map: np.ndarray,
    nav_map_prior: np.ndarray,
) -> tuple[float, float]:
    free_values = np.asarray(search_info_map, dtype=float)[nav_map_prior == FREE]
    if free_values.size == 0:
        return 0.0, 0.0
    return float(np.max(free_values)), float(np.mean(free_values))


def _update_search_info_state(
    state: dict,
    intensity_map: np.ndarray,
) -> None:
    search_info_map, clue_component, intensity_component = _build_search_info_maps(
        state.get("gp_clue_planner_map", state.get("gp_acq_map")),
        intensity_map,
        state["nav_map_prior"],
        clue_weight=state["search_info_clue_weight"],
        intensity_weight=state["search_info_intensity_weight"],
    )
    peak_value, mean_value = _search_info_stats(search_info_map, state["nav_map_prior"])
    state["search_info_map"] = search_info_map
    state["search_info_clue_component_map"] = clue_component
    state["search_info_intensity_component_map"] = intensity_component
    state["search_info_map_peak"] = float(peak_value)
    state["search_info_map_mean"] = float(mean_value)


def _sample_and_update_gp(
    state: dict,
    step: int,
    gp_fit_every: int,
) -> None:
    _update_clue_truth_map(state)
    X_new, y_new = sample_clue_field(
        state["clue_field_fn"],
        state["robot_pos"],
        state["sensor_range_cells"],
        state["observation_rng"],
        n_samples=state["clue_samples_per_step"],
        noise_std=state["clue_noise_std"],
        resolution=state["resolution_m"],
        map_shape=state["true_map"].shape,
    )
    if len(X_new) > 0:
        state["gp_field"].add_observations(X_new, y_new, t=float(step))
    if state["gp_max_points"] is not None:
        state["gp_field"].prune_observations(
            current_time=float(step),
            max_points=state["gp_max_points"],
        )
    optimize_now = (
        state["gp_optimize_hyperparams"]
        and gp_fit_every > 0
        and step % gp_fit_every == 0
    )
    state["current_step"] = int(step)
    _refresh_gp_state(state, optimize_hyperparams=optimize_now)


def _cells_distance(a: tuple[int, int] | None, b: tuple[int, int] | None) -> float:
    if a is None or b is None:
        return float("inf")
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _clip01(value: float) -> float:
    return float(np.clip(float(value), 0.0, 1.0))


def _append_trimmed(history: list[float], value: float, max_len: int) -> None:
    history.append(float(value))
    if len(history) > int(max_len):
        del history[: len(history) - int(max_len)]


def _mean_or_default(values: list[float], default: float = 0.0) -> float:
    return float(np.mean(values)) if values else float(default)


def _label_counts(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        raw_value = row.get(key)
        label = "None" if raw_value is None else str(raw_value)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _merge_count_dicts(count_dicts: list[dict[str, int]]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for count_dict in count_dicts:
        for label, count in count_dict.items():
            merged[label] = merged.get(label, 0) + int(count)
    return dict(sorted(merged.items(), key=lambda item: (-item[1], item[0])))


def _semantic_anchor_source(anchor_source: str | None) -> bool:
    return anchor_source in {"staleness", "clue", "intensity", "search_info"}


def _focus_anchor_source(anchor_source: str | None) -> bool:
    return anchor_source in {"clue", "intensity", "search_info"}


def _same_anchor_cluster_state(
    previous_anchor_source: str | None,
    previous_anchor_centroid: tuple[int, int] | None,
    current_anchor_source: str | None,
    current_anchor_centroid: tuple[int, int] | None,
    sensor_range: int,
) -> bool:
    if (
        not _semantic_anchor_source(previous_anchor_source)
        or not _semantic_anchor_source(current_anchor_source)
        or previous_anchor_source != current_anchor_source
        or previous_anchor_centroid is None
        or current_anchor_centroid is None
    ):
        return False
    anchor_match_radius = max(2, int(sensor_range) // 2)
    return _cells_distance(previous_anchor_centroid, current_anchor_centroid) <= float(anchor_match_radius)


def _compute_kappa_commit(state: dict) -> float:
    same_anchor_execution_ratio = _clip01(float(state["same_anchor_steps"]) / 10.0)
    path_execution_ratio = _clip01(
        float(state["steps_since_replan"]) / float(max(int(state["last_planned_segment_length"]), 1))
    )
    viewpoint_stability = (
        _clip01(1.0 - float(np.mean(state["recent_viewpoint_drifts"])))
        if state["recent_viewpoint_drifts"]
        else 0.0
    )
    segment_flip_rate = (
        float(np.mean(state["recent_segment_flips"]))
        if state["recent_segment_flips"]
        else 0.0
    )
    invalidation_pressure = (
        float(np.mean(state["recent_path_invalidations"]))
        if state["recent_path_invalidations"]
        else 0.0
    )
    kappa_commit = (
        0.35 * same_anchor_execution_ratio
        + 0.30 * path_execution_ratio
        + 0.25 * viewpoint_stability
        - 0.20 * segment_flip_rate
        - 0.15 * invalidation_pressure
    )
    return _clip01(kappa_commit)


def _policy_commit_window(
    policy_name: str,
    planned_segment_length: int,
    search_commit_window: int,
    search_commit_max_window: int,
    search_commit_path_divisor: int,
    kappa_commit: float,
) -> tuple[int, str]:
    min_window = int(search_commit_window)
    max_window = max(min_window, int(search_commit_max_window))
    divisor = max(1, int(search_commit_path_divisor))
    path_base = max(min_window, int(planned_segment_length) // divisor)
    # kappa_commit is deprecated and retained only for API/schema compatibility.
    kappa_term = 0
    if policy_name == "known_map_greedy_viewpoint":
        commit_steps = min(max_window, max(min_window, path_base))
        return int(commit_steps), "adaptive_knownmap_greedy"
    commit_steps = min(max_window, max(min_window, path_base + kappa_term))
    return int(commit_steps), "adaptive_knownmap_soft"


def _observation_progress_terms(state: dict) -> tuple[float, float, int]:
    visible_free = [
        cell
        for cell in sensor_cells(state["robot_pos"], state["nav_map_prior"].shape, state["sensor_range_cells"])
        if state["nav_map_prior"][cell] == FREE
    ]
    total = len(visible_free)
    if total == 0:
        return 0.0, 0.0, 0

    stale_refresh_count = 0
    newly_observed_count = 0
    for cell in visible_free:
        if state["last_seen_step"][cell] < 0:
            newly_observed_count += 1
        elif float(state["staleness_map"][cell]) >= 0.5:
            stale_refresh_count += 1

    effective_gain_ratio = float(newly_observed_count + stale_refresh_count) / float(total)
    stale_refresh_ratio = float(stale_refresh_count) / float(total)
    return effective_gain_ratio, stale_refresh_ratio, newly_observed_count


def _trace_row(
    step: int,
    state: dict,
    policy_name: str,
    replanned_this_step: bool,
    replan_reason: str | None,
    commit_remaining: int,
    path_length_current: int,
    fraction_before_replan: float,
    plan_details: dict,
    detected_count_this_step: int,
    collision_this_step: bool,
    collision_cell: tuple[int, int] | None,
    effective_observation_gain: float,
    stale_refresh_ratio: float,
) -> dict:
    return {
        "step": int(step),
        "policy_name": policy_name,
        "clue_acquisition_mode": str(state.get("clue_acquisition_mode", "ucb")),
        "anomaly_conditional_alpha": float(plan_details.get("anomaly_conditional_alpha", 0.0)),
        "anomaly_conditional_triggered": bool(
            plan_details.get("anomaly_conditional_triggered", False)
        ),
        "anomaly_gate_reason": str(
            plan_details.get("anomaly_gate_reason", "mode_not_conditional")
        ),
        "anomaly_top_mass_ratio": float(plan_details.get("anomaly_top_mass_ratio", 0.0)),
        "anomaly_entropy_norm": float(plan_details.get("anomaly_entropy_norm", 0.0)),
        "anomaly_hotspot_stability": float(
            plan_details.get("anomaly_hotspot_stability", 1.0)
        ),
        "anomaly_pre_first_alpha_capped": bool(
            plan_details.get("anomaly_pre_first_alpha_capped", False)
        ),
        "mode": SEARCH_MODE,
        "robot_cell": tuple(int(v) for v in state["robot_pos"]),
        "viewpoint_cell": plan_details.get("viewpoint_cell"),
        "segment_endpoint_cell": plan_details.get("segment_endpoint_cell"),
        "anchor_cell": plan_details.get("anchor_cell"),
        "anchor_source": plan_details.get("anchor_source"),
        "anchor_centroid_cell": plan_details.get("anchor_centroid_cell"),
        "anchor_cluster_size": int(plan_details.get("anchor_cluster_size", 0)),
        "anchor_cluster_peak": float(plan_details.get("anchor_cluster_peak", 0.0)),
        "anchor_cluster_mean": float(plan_details.get("anchor_cluster_mean", 0.0)),
        "viewpoint_rule": plan_details.get("viewpoint_rule"),
        "replanned_this_step": bool(replanned_this_step),
        "replan_reason": replan_reason,
        "commit_remaining": int(commit_remaining),
        "planned_commit_window": int(state.get("last_planned_commit_window", 0)),
        "commit_policy": state.get("last_commit_policy", "unknown"),
        "path_length_current": int(path_length_current),
        "planned_segment_length": int(state.get("last_planned_segment_length", 0)),
        "planned_viewpoint_path_length": int(plan_details.get("planned_viewpoint_path_length", 0)),
        "segment_path_length": int(plan_details.get("segment_path_length", 0)),
        "fraction_of_path_executed_before_replan": float(fraction_before_replan),
        "switch_count": int(state["switch_count"]),
        "explore_utility_raw": float(plan_details.get("explore_utility_raw", 0.0)),
        "explore_utility_norm": float(plan_details.get("explore_utility_norm", 0.0)),
        "focus_utility_raw": float(plan_details.get("focus_utility_raw", 0.0)),
        "focus_utility_norm": float(plan_details.get("focus_utility_norm", 0.0)),
        "recency_utility_raw": float(plan_details.get("recency_utility_raw", 0.0)),
        "recency_utility_norm": float(plan_details.get("recency_utility_norm", 0.0)),
        "search_info_gain_raw": float(plan_details.get("search_info_gain_raw", 0.0)),
        "search_info_gain_norm": float(plan_details.get("search_info_gain_norm", 0.0)),
        "recency_bias_raw": float(plan_details.get("recency_bias_raw", 0.0)),
        "recency_bias_norm": float(plan_details.get("recency_bias_norm", 0.0)),
        "exec_cost_raw": float(plan_details.get("exec_cost_raw", 0.0)),
        "exec_cost_norm": float(plan_details.get("exec_cost_norm", 0.0)),
        "clearance_penalty_raw": float(plan_details.get("clearance_penalty_raw", 0.0)),
        "segment_min_clearance_cells": float(
            plan_details.get("segment_min_clearance_cells", 0.0)
        ),
        "segment_mean_clearance_cells": float(
            plan_details.get("segment_mean_clearance_cells", 0.0)
        ),
        "near_obstacle_step_flag": bool(plan_details.get("near_obstacle_step_flag", False)),
        "near_obstacle_step_ratio": float(plan_details.get("near_obstacle_step_ratio", 0.0)),
        "path_safety_mode": str(plan_details.get("path_safety_mode", "off")),
        "planner_adaptation_mode": str(state.get("planner_adaptation_mode", "adaptive")),
        "safe_nav_lambda_clearance": float(plan_details.get("safe_nav_lambda_clearance", 0.0)),
        "marginal_information_gain_raw": float(
            plan_details.get("marginal_information_gain_raw", 0.0)
        ),
        "marginal_information_gain_norm": float(
            plan_details.get("marginal_information_gain_norm", 0.0)
        ),
        "execution_cost_raw": float(plan_details.get("execution_cost_raw", 0.0)),
        "execution_cost_norm": float(plan_details.get("execution_cost_norm", 0.0)),
        "continuity_bonus_raw": float(plan_details.get("continuity_bonus_raw", 0.0)),
        "continuity_bonus_anchor_raw": float(
            plan_details.get("continuity_bonus_anchor_raw", 0.0)
        ),
        "continuity_bonus_viewpoint_raw": float(
            plan_details.get("continuity_bonus_viewpoint_raw", 0.0)
        ),
        "marginal_information_gain_score_term": float(
            plan_details.get("marginal_information_gain_score_term", 0.0)
        ),
        "recency_bias_score_term": float(plan_details.get("recency_bias_score_term", 0.0)),
        "execution_cost_score_term": float(plan_details.get("execution_cost_score_term", 0.0)),
        "continuity_bonus_score_term": float(
            plan_details.get("continuity_bonus_score_term", 0.0)
        ),
        "maneuver_penalty_raw": float(plan_details.get("maneuver_penalty_raw", 0.0)),
        "maneuver_penalty_score_term": float(
            plan_details.get("maneuver_penalty_score_term", 0.0)
        ),
        "segment_turn_count": int(plan_details.get("segment_turn_count", 0)),
        "alpha_focus": float(plan_details.get("alpha_focus", 0.0)),
        "kappa_commit": float(plan_details.get("kappa_commit", 0.0)),
        "same_anchor_cluster": bool(plan_details.get("same_anchor_cluster", False)),
        "viewpoint_drift_norm": float(plan_details.get("viewpoint_drift_norm", 0.0)),
        "anchor_retention_bonus": float(plan_details.get("anchor_retention_bonus", 0.0)),
        "viewpoint_retention_bonus": float(plan_details.get("viewpoint_retention_bonus", 0.0)),
        "anchor_info_clue_share": float(plan_details.get("anchor_info_clue_share", 0.0)),
        "anchor_info_intensity_share": float(plan_details.get("anchor_info_intensity_share", 0.0)),
        "candidate_pool_size": int(plan_details.get("candidate_pool_size", 0)),
        "reachable_pool_size": int(plan_details.get("reachable_pool_size", 0)),
        "a_star_checked_pool_size": int(plan_details.get("a_star_checked_pool_size", 0)),
        "selected_viewpoint_rank": int(plan_details.get("selected_viewpoint_rank", 0)),
        "sampling_priority_raw": float(plan_details.get("sampling_priority_raw", 0.0)),
        "sampling_priority_norm": float(plan_details.get("sampling_priority_norm", 0.0)),
        "viewpoint_sampling_mode": plan_details.get("viewpoint_sampling_mode"),
        "selected_by_final_score": bool(plan_details.get("selected_by_final_score", False)),
        "sssp_build_time_ms": float(plan_details.get("sssp_build_time_ms", 0.0)),
        "path_reconstruct_time_ms": float(plan_details.get("path_reconstruct_time_ms", 0.0)),
        "sampling_pool_build_time_ms": float(plan_details.get("sampling_pool_build_time_ms", 0.0)),
        "priority_feature_time_ms": float(plan_details.get("priority_feature_time_ms", 0.0)),
        "tree_depth": int(plan_details.get("tree_depth", 1)),
        "tree_first_layer_top_m": int(plan_details.get("tree_first_layer_top_m", 0)),
        "tree_second_layer_top_n": int(plan_details.get("tree_second_layer_top_n", 0)),
        "tree_discount_gamma": float(plan_details.get("tree_discount_gamma", 0.0)),
        "tree_root_rank": int(plan_details.get("tree_root_rank", 0)),
        "tree_child_rank": int(plan_details.get("tree_child_rank", 0)),
        "tree_root_score_raw": float(plan_details.get("tree_root_score_raw", 0.0)),
        "tree_child_score_raw": float(plan_details.get("tree_child_score_raw", 0.0)),
        "tree_total_score": float(plan_details.get("tree_total_score", 0.0)),
        "tree_conditional_gain_lvl2": float(plan_details.get("tree_conditional_gain_lvl2", 0.0)),
        "tree_redundant_visible_ratio_lvl2": float(
            plan_details.get("tree_redundant_visible_ratio_lvl2", 0.0)
        ),
        "tree_unique_visible_count_lvl1": int(plan_details.get("tree_unique_visible_count_lvl1", 0)),
        "tree_unique_visible_count_lvl2": int(plan_details.get("tree_unique_visible_count_lvl2", 0)),
        "tree_expansion_count": int(plan_details.get("tree_expansion_count", 0)),
        "tree_planning_time_ms": float(plan_details.get("tree_planning_time_ms", 0.0)),
        "tree_child_oracle_score_raw": float(plan_details.get("tree_child_oracle_score_raw", 0.0)),
        "tree_child_budget_score_raw": float(plan_details.get("tree_child_budget_score_raw", 0.0)),
        "tree_child_oracle_gap_raw": float(plan_details.get("tree_child_oracle_gap_raw", 0.0)),
        "tree_child_oracle_rank_of_budgeted": int(
            plan_details.get("tree_child_oracle_rank_of_budgeted", 0)
        ),
        "tree_child_budget_matches_oracle": bool(
            plan_details.get("tree_child_budget_matches_oracle", False)
        ),
        "tree_child_oracle_viewpoint_cell": plan_details.get("tree_child_oracle_viewpoint_cell"),
        "tree_child_budget_viewpoint_cell": plan_details.get("tree_child_budget_viewpoint_cell"),
        "tree_child_full_candidate_count": int(plan_details.get("tree_child_full_candidate_count", 0)),
        "u_turn_penalty_term": float(plan_details.get("u_turn_penalty_term", 0.0)),
        "u_turn_penalty_applied": bool(plan_details.get("u_turn_penalty_applied", False)),
        "planned_first_move_dir": plan_details.get("first_move_dir"),
        "current_viewpoint_score": float(plan_details.get("current_viewpoint_score", 0.0)),
        "best_alternative_score": float(plan_details.get("best_alternative_score", 0.0)),
        "total_score": float(plan_details.get("total_score", 0.0)),
        "anchor_switch_count": int(state.get("anchor_switch_count", 0)),
        "focus_anchor_active": bool(_focus_anchor_source(plan_details.get("anchor_source"))),
        "focus_on_anchor_cluster_steps": int(state["focus_on_anchor_cluster_steps"]),
        "time_since_last_detection": int(state.get("time_since_last_detection", 0)),
        "remaining_intensity_mass": float(state["remaining_intensity_mass_curve"][-1]),
        "peak_intensity_ratio": float(state["peak_intensity_ratio_curve"][-1]),
        "known_free_observation_ratio": float(state["known_free_observation_ratio_curve"][-1]),
        "search_info_map_peak": float(state.get("search_info_map_peak", 0.0)),
        "search_info_map_mean": float(state.get("search_info_map_mean", 0.0)),
        "anomaly_viewpoint_prob": float(plan_details.get("anomaly_viewpoint_prob", 0.0)),
        "anomaly_viewpoint_weight": float(plan_details.get("anomaly_viewpoint_weight", 0.0)),
        "anomaly_viewpoint_acq": float(plan_details.get("anomaly_viewpoint_acq", 0.0)),
        "anomaly_visible_mean": float(plan_details.get("anomaly_visible_mean", 0.0)),
        "selected_in_anomaly_top_band": bool(
            plan_details.get("selected_in_anomaly_top_band", False)
        ),
        "effective_observation_gain": float(effective_observation_gain),
        "stale_refresh_ratio": float(stale_refresh_ratio),
        "detected_count_this_step": int(detected_count_this_step),
        "collision_this_step": bool(collision_this_step),
        "collision_cell": None if collision_cell is None else tuple(int(v) for v in collision_cell),
        "path_invalidations_per_episode": int(state["path_invalidations_per_episode"]),
    }


def _placement_infeasible_result(
    policy_name: str,
    n_targets: int,
    constraint_mode: str,
    map_kind: str,
    map_height_cells: int,
    map_width_cells: int,
    clue_acquisition_mode: str = "ucb",
    anomaly_tail_quantile: float = 0.90,
    anomaly_weight_lambda: float = 1.0,
) -> dict:
    result = {
        "policy_name": policy_name,
        "clue_acquisition_mode": str(clue_acquisition_mode),
        "anomaly_tail_quantile": float(anomaly_tail_quantile),
        "anomaly_weight_lambda": float(anomaly_weight_lambda),
        "anomaly_conditional_alpha_final": 0.0,
        "anomaly_conditional_triggered_final": False,
        "anomaly_gate_reason_final": "placement_infeasible",
        "anomaly_conditional_alpha_mean": 0.0,
        "anomaly_conditional_trigger_rate": 0.0,
        "anomaly_gate_reason_counts": {},
        "map_prior_mode": "known_static",
        "success_all_found": False,
        "found_count": 0,
        "miss_count": int(n_targets),
        "found_count_at_budget": 0,
        "detection_rate": 0.0,
        "find_times": [None] * int(n_targets),
        "found_count_curve": [0],
        "time_to_first_detection": None,
        "time_to_all_found": None,
        "time_to_next_detection": None,
        "completed_steps": 0,
        "path_length": 0,
        "map_kind": map_kind,
        "map_height_cells": int(map_height_cells),
        "map_width_cells": int(map_width_cells),
        "planning_time_ms": [],
        "planning_time_ms_total": 0.0,
        "planning_time_ms_mean": 0.0,
        "replan_count": 0,
        "switch_count": 0,
        "anchor_switch_count": 0,
        "terminated_reason": "placement_infeasible",
        "constraint_mode": constraint_mode,
        "placement_status": "infeasible",
        "actual_min_target_separation_cells": None,
        "actual_min_target_separation_m": None,
        "actual_min_start_distance_cells": None,
        "actual_min_start_distance_m": None,
        "known_free_observation_ratio_final": 0.0,
        "known_free_observation_ratio_curve": [0.0],
        "remaining_intensity_mass_curve": [0.0],
        "peak_intensity_ratio_curve": [0.0],
        "search_info_map_peak_final": 0.0,
        "search_info_map_mean_final": 0.0,
        "search_info_gain_mean": 0.0,
        "recency_bias_mean": 0.0,
        "candidate_pool_size_mean": 0.0,
        "reachable_pool_size_mean": 0.0,
        "a_star_checked_pool_size_mean": 0.0,
        "selected_viewpoint_rank_mean": 0.0,
        "sampling_priority_mean": 0.0,
        "sssp_build_time_ms_mean": 0.0,
        "path_reconstruct_time_ms_mean": 0.0,
        "sampling_pool_build_time_ms_mean": 0.0,
        "priority_feature_time_ms_mean": 0.0,
        "tree_total_score_mean": 0.0,
        "tree_conditional_gain_lvl2_mean": 0.0,
        "tree_redundant_visible_ratio_lvl2_mean": 0.0,
        "tree_expansion_count_mean": 0.0,
        "tree_unique_visible_count_lvl1_mean": 0.0,
        "tree_unique_visible_count_lvl2_mean": 0.0,
        "tree_planning_time_ms_mean": 0.0,
        "tree_child_oracle_gap_mean": 0.0,
        "tree_child_oracle_rank_of_budgeted_mean": 0.0,
        "tree_child_budget_matches_oracle_rate": 0.0,
        "tree_child_full_candidate_count_mean": 0.0,
        "search_info_fusion_weights": {"clue": 0.5, "intensity": 0.5},
        "anomaly_top_band_selection_ratio_pre_first_detection": 0.0,
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": 0.0,
        "alpha_focus_curve": [],
        "kappa_commit_curve": [],
        "trace_rows": [],
        "mode_history": [],
        "stale_region_refresh_rate": 0.0,
        "focus_on_anchor_cluster_duration": 0,
        "same_anchor_segment_ratio": 0.0,
        "viewpoint_drift_under_same_anchor": 0.0,
        "path_invalidations_per_episode": 0,
        "gp_n_obs": None,
        "eval_mean_gp_uncertainty": None,
        "eval_mean_gp_reward": None,
    }
    _validate_knownmap_result_contract(result)
    return result


def _result_replan_rows(result: dict) -> list[dict]:
    return [
        row
        for row in result.get("trace_rows", [])
        if bool(row.get("replanned_this_step", False))
    ]


def _mean_detection_gap(find_times: list[int | None]) -> float | None:
    found_steps = sorted(int(step) for step in find_times if step is not None)
    if len(found_steps) <= 1:
        return None
    gaps = [float(curr - prev) for prev, curr in zip(found_steps, found_steps[1:])]
    return float(np.mean(gaps)) if gaps else None


def _result_trace_metrics(result: dict) -> dict[str, object]:
    trace_rows = list(result.get("trace_rows", []))
    replan_rows = _result_replan_rows(result)
    same_anchor_rows = [row for row in replan_rows if bool(row.get("same_anchor_cluster", False))]
    # Under the current known-static-map baseline this hook should usually stay
    # near zero. It is retained for future dynamic-obstacle / map-mismatch /
    # execution-noise extensions, not as a primary behavior metric.
    return {
        "alpha_focus_mean": _mean_or_default(
            [float(row.get("alpha_focus", 0.0)) for row in trace_rows]
        ),
        "kappa_commit_mean": _mean_or_default(
            [float(row.get("kappa_commit", 0.0)) for row in trace_rows]
        ),
        "search_info_gain_mean": _mean_or_default(
            [float(row.get("search_info_gain_raw", 0.0)) for row in trace_rows]
        ),
        "recency_bias_mean": _mean_or_default(
            [float(row.get("recency_bias_raw", 0.0)) for row in trace_rows]
        ),
        "candidate_pool_size_mean": _mean_or_default(
            [float(row.get("candidate_pool_size", 0.0)) for row in replan_rows]
        ),
        "reachable_pool_size_mean": _mean_or_default(
            [float(row.get("reachable_pool_size", 0.0)) for row in replan_rows]
        ),
        "a_star_checked_pool_size_mean": _mean_or_default(
            [float(row.get("a_star_checked_pool_size", 0.0)) for row in replan_rows]
        ),
        "selected_viewpoint_rank_mean": _mean_or_default(
            [float(row.get("selected_viewpoint_rank", 0.0)) for row in replan_rows]
        ),
        "sampling_priority_mean": _mean_or_default(
            [float(row.get("sampling_priority_raw", 0.0)) for row in replan_rows]
        ),
        "sssp_build_time_ms_mean": _mean_or_default(
            [float(row.get("sssp_build_time_ms", 0.0)) for row in replan_rows]
        ),
        "path_reconstruct_time_ms_mean": _mean_or_default(
            [float(row.get("path_reconstruct_time_ms", 0.0)) for row in replan_rows]
        ),
        "sampling_pool_build_time_ms_mean": _mean_or_default(
            [float(row.get("sampling_pool_build_time_ms", 0.0)) for row in replan_rows]
        ),
        "priority_feature_time_ms_mean": _mean_or_default(
            [float(row.get("priority_feature_time_ms", 0.0)) for row in replan_rows]
        ),
        "tree_total_score_mean": _mean_or_default(
            [float(row.get("tree_total_score", 0.0)) for row in replan_rows]
        ),
        "tree_conditional_gain_lvl2_mean": _mean_or_default(
            [float(row.get("tree_conditional_gain_lvl2", 0.0)) for row in replan_rows]
        ),
        "tree_redundant_visible_ratio_lvl2_mean": _mean_or_default(
            [float(row.get("tree_redundant_visible_ratio_lvl2", 0.0)) for row in replan_rows]
        ),
        "tree_expansion_count_mean": _mean_or_default(
            [float(row.get("tree_expansion_count", 0.0)) for row in replan_rows]
        ),
        "tree_unique_visible_count_lvl1_mean": _mean_or_default(
            [float(row.get("tree_unique_visible_count_lvl1", 0.0)) for row in replan_rows]
        ),
        "tree_unique_visible_count_lvl2_mean": _mean_or_default(
            [float(row.get("tree_unique_visible_count_lvl2", 0.0)) for row in replan_rows]
        ),
        "tree_planning_time_ms_mean": _mean_or_default(
            [float(row.get("tree_planning_time_ms", 0.0)) for row in replan_rows]
        ),
        "tree_child_oracle_gap_mean": _mean_or_default(
            [float(row.get("tree_child_oracle_gap_raw", 0.0)) for row in replan_rows]
        ),
        "tree_child_oracle_rank_of_budgeted_mean": _mean_or_default(
            [float(row.get("tree_child_oracle_rank_of_budgeted", 0.0)) for row in replan_rows]
        ),
        "tree_child_budget_matches_oracle_rate": _mean_or_default(
            [1.0 if row.get("tree_child_budget_matches_oracle") else 0.0 for row in replan_rows]
        ),
        "tree_child_full_candidate_count_mean": _mean_or_default(
            [float(row.get("tree_child_full_candidate_count", 0.0)) for row in replan_rows]
        ),
        "fraction_of_path_executed_before_replan_mean": _mean_or_default(
            [float(row.get("fraction_of_path_executed_before_replan", 0.0)) for row in replan_rows]
        ),
        "planned_commit_window_mean": _mean_or_default(
            [float(row.get("planned_commit_window", 0.0)) for row in replan_rows]
        ),
        "same_anchor_segment_ratio": _mean_or_default(
            [1.0 if row.get("same_anchor_cluster") else 0.0 for row in replan_rows]
        ),
        "viewpoint_drift_under_same_anchor": _mean_or_default(
            [float(row.get("viewpoint_drift_norm", 0.0)) for row in same_anchor_rows]
        ),
        "stale_region_refresh_rate": _mean_or_default(
            [float(row.get("stale_refresh_ratio", 0.0)) for row in trace_rows]
        ),
        "focus_on_anchor_cluster_duration": int(
            sum(1 for row in trace_rows if bool(row.get("focus_anchor_active", False)))
        ),
        # Under the current known-static baseline this is mainly a reserved
        # hook for future map-mismatch / dynamic-obstacle extensions.
        "path_invalidations_per_episode": int(
            max(
                [int(row.get("path_invalidations_per_episode", 0)) for row in trace_rows],
                default=0,
            )
        ),
        "clearance_penalty_raw_mean": _mean_or_default(
            [float(row.get("clearance_penalty_raw", 0.0)) for row in trace_rows]
        ),
        "near_obstacle_step_ratio": _mean_or_default(
            [float(row.get("near_obstacle_step_ratio", 0.0)) for row in trace_rows]
        ),
        "min_clearance_cells_mean": _mean_or_default(
            [float(row.get("segment_min_clearance_cells", 0.0)) for row in trace_rows]
        ),
        "segment_mean_clearance_cells_mean": _mean_or_default(
            [float(row.get("segment_mean_clearance_cells", 0.0)) for row in trace_rows]
        ),
        "viewpoint_rule_counts": _label_counts(replan_rows, "viewpoint_rule"),
        "anchor_source_counts": _label_counts(replan_rows, "anchor_source"),
        "anomaly_visible_mean_mean": _mean_or_default(
            [float(row.get("anomaly_visible_mean", 0.0)) for row in trace_rows]
        ),
        "anomaly_top_band_selection_ratio": _mean_or_default(
            [1.0 if row.get("selected_in_anomaly_top_band") else 0.0 for row in trace_rows]
        ),
        "anomaly_conditional_alpha_mean": _mean_or_default(
            [float(row.get("anomaly_conditional_alpha", 0.0)) for row in trace_rows]
        ),
        "anomaly_conditional_trigger_rate": _mean_or_default(
            [1.0 if row.get("anomaly_conditional_triggered") else 0.0 for row in trace_rows]
        ),
        "anomaly_gate_reason_counts": _label_counts(trace_rows, "anomaly_gate_reason"),
    }


def _summarize_result(state: dict, policy_name: str) -> dict:
    summary = summarize_detection_times(state["find_times"])
    found_count = summary["found_count"]
    miss_count = summary["miss_count"]
    total_targets = len(state["target_ids"])
    planning_time_ms = [float(value) for value in state["planning_time_ms"]]
    trace_metrics = _result_trace_metrics({"trace_rows": state["trace_rows"]})
    pre_first_trace_rows = _pre_first_detection_trace_rows(
        list(state["trace_rows"]),
        step_key="step",
        find_times=state["find_times"],
    )
    anomaly_top_band_selection_ratio_pre_first_detection = _mean_or_default(
        [
            1.0 if row.get("selected_in_anomaly_top_band") else 0.0
            for row in pre_first_trace_rows
        ]
    )
    unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection = _pre_first_detection_curve_mean(
        list(state.get("anomaly_target_neighborhood_mass_ratio_rows", [])),
        find_times=state["find_times"],
    )
    result = {
        "policy_name": policy_name,
        "clue_acquisition_mode": str(state.get("clue_acquisition_mode", "ucb")),
        "anomaly_tail_quantile": float(state.get("anomaly_tail_quantile", 0.90)),
        "anomaly_weight_lambda": float(state.get("anomaly_weight_lambda", 1.0)),
        "anomaly_conditional_alpha_final": float(
            state.get("anomaly_conditional_alpha", 0.0)
        ),
        "anomaly_conditional_triggered_final": bool(
            state.get("anomaly_conditional_triggered", False)
        ),
        "anomaly_gate_reason_final": str(
            state.get("anomaly_gate_reason", "mode_not_conditional")
        ),
        "anomaly_conditional_alpha_mean": float(
            trace_metrics["anomaly_conditional_alpha_mean"]
        ),
        "anomaly_conditional_trigger_rate": float(
            trace_metrics["anomaly_conditional_trigger_rate"]
        ),
        "anomaly_gate_reason_counts": dict(trace_metrics["anomaly_gate_reason_counts"]),
        "map_prior_mode": "known_static",
        "success_all_found": miss_count == 0,
        "found_count": found_count,
        "miss_count": miss_count,
        "found_count_at_budget": found_count,
        "detection_rate": found_count / total_targets if total_targets > 0 else 0.0,
        "find_times": list(state["find_times"]),
        "found_count_curve": list(state["found_count_curve"]),
        "time_to_first_detection": summary["time_to_first_detection"],
        "time_to_all_found": summary["time_to_all_found"],
        "time_to_next_detection": _mean_detection_gap(state["find_times"]),
        "completed_steps": state["completed_steps"],
        "path_length": state["path_length"],
        "map_kind": state["map_kind"],
        "map_height_cells": int(state["map_height_cells"]),
        "map_width_cells": int(state["map_width_cells"]),
        "planning_time_ms": planning_time_ms,
        "planning_time_ms_total": float(np.sum(planning_time_ms)) if planning_time_ms else 0.0,
        "planning_time_ms_mean": float(np.mean(planning_time_ms)) if planning_time_ms else 0.0,
        "replan_count": state["replan_count"],
        "switch_count": state["switch_count"],
        "anchor_switch_count": state["anchor_switch_count"],
        "terminated_reason": state["terminated_reason"],
        "constraint_mode": state["constraint_mode"],
        "placement_status": state["placement_status"],
        "actual_min_target_separation_cells": state["actual_min_target_separation_cells"],
        "actual_min_target_separation_m": _distance_maybe_to_m(
            state["actual_min_target_separation_cells"],
            state["resolution_m"],
        ),
        "actual_min_start_distance_cells": state["actual_min_start_distance_cells"],
        "actual_min_start_distance_m": _distance_maybe_to_m(
            state["actual_min_start_distance_cells"],
            state["resolution_m"],
        ),
        "known_free_observation_ratio_final": float(state["known_free_observation_ratio_curve"][-1]),
        "known_free_observation_ratio_curve": list(state["known_free_observation_ratio_curve"]),
        "mode_history": list(state["mode_history"]),
        "remaining_intensity_mass_curve": list(state["remaining_intensity_mass_curve"]),
        "peak_intensity_ratio_curve": list(state["peak_intensity_ratio_curve"]),
        "search_info_map_peak_final": float(state.get("search_info_map_peak", 0.0)),
        "search_info_map_mean_final": float(state.get("search_info_map_mean", 0.0)),
        "path_safety_mode": str(state.get("path_safety_mode", "off")),
        "viewpoint_generation_mode": str(
            state.get("viewpoint_generation_mode", DEFAULT_VIEWPOINT_GENERATION_MODE)
        ),
        "planner_adaptation_mode": str(state.get("planner_adaptation_mode", "adaptive")),
        "safe_nav_inflation_radius_cells": int(state.get("safe_nav_inflation_radius_cells", 0)),
        "safe_nav_soft_clearance_radius_cells": int(
            state.get("safe_nav_soft_clearance_radius_cells", 0)
        ),
        "safe_nav_lambda_clearance": float(state.get("safe_nav_lambda_clearance", 0.0)),
        "anomaly_top_band_selection_ratio_pre_first_detection": float(
            anomaly_top_band_selection_ratio_pre_first_detection
        ),
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": float(
            unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection
        ),
        "search_info_fusion_weights": {
            "clue": float(state.get("search_info_clue_weight", 0.5)),
            "intensity": float(state.get("search_info_intensity_weight", 0.5)),
        },
        "alpha_focus_curve": list(state["alpha_focus_curve"]),
        "kappa_commit_curve": list(state["kappa_commit_curve"]),
        "trace_rows": list(state["trace_rows"]),
        "stale_region_refresh_rate": float(trace_metrics["stale_region_refresh_rate"]),
        "focus_on_anchor_cluster_duration": int(trace_metrics["focus_on_anchor_cluster_duration"]),
        "same_anchor_segment_ratio": float(trace_metrics["same_anchor_segment_ratio"]),
        "viewpoint_drift_under_same_anchor": float(trace_metrics["viewpoint_drift_under_same_anchor"]),
        "path_invalidations_per_episode": int(trace_metrics["path_invalidations_per_episode"]),
        "clearance_penalty_raw_mean": float(trace_metrics["clearance_penalty_raw_mean"]),
        "near_obstacle_step_ratio": float(trace_metrics["near_obstacle_step_ratio"]),
        "min_clearance_cells_mean": float(trace_metrics["min_clearance_cells_mean"]),
        "segment_mean_clearance_cells_mean": float(
            trace_metrics["segment_mean_clearance_cells_mean"]
        ),
        "search_info_gain_mean": float(trace_metrics["search_info_gain_mean"]),
        "recency_bias_mean": float(trace_metrics["recency_bias_mean"]),
        "candidate_pool_size_mean": float(trace_metrics["candidate_pool_size_mean"]),
        "reachable_pool_size_mean": float(trace_metrics["reachable_pool_size_mean"]),
        "a_star_checked_pool_size_mean": float(trace_metrics["a_star_checked_pool_size_mean"]),
        "selected_viewpoint_rank_mean": float(trace_metrics["selected_viewpoint_rank_mean"]),
        "sampling_priority_mean": float(trace_metrics["sampling_priority_mean"]),
        "sssp_build_time_ms_mean": float(trace_metrics["sssp_build_time_ms_mean"]),
        "path_reconstruct_time_ms_mean": float(trace_metrics["path_reconstruct_time_ms_mean"]),
        "sampling_pool_build_time_ms_mean": float(trace_metrics["sampling_pool_build_time_ms_mean"]),
        "priority_feature_time_ms_mean": float(trace_metrics["priority_feature_time_ms_mean"]),
        "tree_total_score_mean": float(trace_metrics["tree_total_score_mean"]),
        "tree_conditional_gain_lvl2_mean": float(trace_metrics["tree_conditional_gain_lvl2_mean"]),
        "tree_redundant_visible_ratio_lvl2_mean": float(
            trace_metrics["tree_redundant_visible_ratio_lvl2_mean"]
        ),
        "tree_expansion_count_mean": float(trace_metrics["tree_expansion_count_mean"]),
        "tree_unique_visible_count_lvl1_mean": float(trace_metrics["tree_unique_visible_count_lvl1_mean"]),
        "tree_unique_visible_count_lvl2_mean": float(trace_metrics["tree_unique_visible_count_lvl2_mean"]),
        "tree_planning_time_ms_mean": float(trace_metrics["tree_planning_time_ms_mean"]),
        "tree_child_oracle_gap_mean": float(trace_metrics["tree_child_oracle_gap_mean"]),
        "tree_child_oracle_rank_of_budgeted_mean": float(
            trace_metrics["tree_child_oracle_rank_of_budgeted_mean"]
        ),
        "tree_child_budget_matches_oracle_rate": float(
            trace_metrics["tree_child_budget_matches_oracle_rate"]
        ),
        "tree_child_full_candidate_count_mean": float(
            trace_metrics["tree_child_full_candidate_count_mean"]
        ),
        "target_motion_mode": state["target_motion_mode"],
        "target_count_upper_bound": state["target_count_upper_bound"],
    }
    free_mask = state["true_map"] == FREE
    sigma_map = np.sqrt(np.clip(state["gp_var_map"], 0.0, None))
    result["gp_n_obs"] = state["gp_field"].n_obs
    result["eval_mean_gp_uncertainty"] = float(np.mean(sigma_map[free_mask])) if free_mask.any() else 0.0
    result["eval_mean_gp_reward"] = float(np.mean(state["gp_acq_map"][free_mask])) if free_mask.any() else 0.0
    _validate_knownmap_result_contract(result)
    return result


def _policy_summary_rows(policy_results: list[dict]) -> dict:
    success_mean = float(np.mean([r["success_all_found"] for r in policy_results]))
    found_mean = float(np.mean([r["found_count"] for r in policy_results]))
    miss_mean = float(np.mean([r["miss_count"] for r in policy_results]))
    detection_rate_mean = float(np.mean([r["detection_rate"] for r in policy_results]))
    path_mean = float(np.mean([r["path_length"] for r in policy_results]))
    known_free_observation_ratio_final_mean = float(
        np.mean([r["known_free_observation_ratio_final"] for r in policy_results])
    )
    planning_ms_mean = float(np.mean([r["planning_time_ms_mean"] for r in policy_results]))
    switch_mean = float(np.mean([r["switch_count"] for r in policy_results]))
    anchor_switch_mean = float(np.mean([r.get("anchor_switch_count", 0) for r in policy_results]))
    replan_mean = float(np.mean([r["replan_count"] for r in policy_results]))
    first_detection_values = [
        r["time_to_first_detection"]
        for r in policy_results
        if r["time_to_first_detection"] is not None
    ]
    all_found_values = [
        r["time_to_all_found"]
        for r in policy_results
        if r["time_to_all_found"] is not None
    ]
    next_detection_values = [
        float(r["time_to_next_detection"])
        for r in policy_results
        if r["time_to_next_detection"] is not None
    ]
    first_mean = float(np.mean(first_detection_values)) if first_detection_values else float("nan")
    all_mean = float(np.mean(all_found_values)) if all_found_values else float("nan")
    next_mean = float(np.mean(next_detection_values)) if next_detection_values else float("nan")
    trace_metrics = [_result_trace_metrics(result) for result in policy_results]
    summary_row = {
        "success_all_found_mean": success_mean,
        "found_count_mean": found_mean,
        "miss_count_mean": miss_mean,
        "detection_rate_mean": detection_rate_mean,
        "time_to_first_detection_mean": first_mean,
        "time_to_all_found_mean": all_mean,
        "time_to_next_detection_mean": next_mean,
        "path_length_mean": path_mean,
        "known_free_observation_ratio_final_mean": known_free_observation_ratio_final_mean,
        "planning_time_ms_mean": planning_ms_mean,
        "switch_count_mean": switch_mean,
        "anchor_switch_count_mean": anchor_switch_mean,
        "replan_count_mean": replan_mean,
        "stale_region_refresh_rate_mean": _mean_or_default(
            [float(item["stale_region_refresh_rate"]) for item in trace_metrics]
        ),
        "focus_on_anchor_cluster_duration_mean": _mean_or_default(
            [float(item["focus_on_anchor_cluster_duration"]) for item in trace_metrics]
        ),
        "same_anchor_segment_ratio_mean": _mean_or_default(
            [float(item["same_anchor_segment_ratio"]) for item in trace_metrics]
        ),
        "viewpoint_drift_under_same_anchor_mean": _mean_or_default(
            [float(item["viewpoint_drift_under_same_anchor"]) for item in trace_metrics]
        ),
        "path_invalidations_per_episode_mean": _mean_or_default(
            [float(item["path_invalidations_per_episode"]) for item in trace_metrics]
        ),
        "clearance_penalty_raw_mean": _mean_or_default(
            [float(item["clearance_penalty_raw_mean"]) for item in trace_metrics]
        ),
        "near_obstacle_step_ratio_mean": _mean_or_default(
            [float(item["near_obstacle_step_ratio"]) for item in trace_metrics]
        ),
        "min_clearance_cells_mean": _mean_or_default(
            [float(item["min_clearance_cells_mean"]) for item in trace_metrics]
        ),
        "alpha_focus_mean": _mean_or_default(
            [float(item["alpha_focus_mean"]) for item in trace_metrics]
        ),
        "kappa_commit_mean": _mean_or_default(
            [float(item["kappa_commit_mean"]) for item in trace_metrics]
        ),
        "fraction_of_path_executed_before_replan_mean": _mean_or_default(
            [
                float(item["fraction_of_path_executed_before_replan_mean"])
                for item in trace_metrics
            ]
        ),
        "planned_commit_window_mean": _mean_or_default(
            [float(item["planned_commit_window_mean"]) for item in trace_metrics]
        ),
        "search_info_gain_mean": _mean_or_default(
            [float(item["search_info_gain_mean"]) for item in trace_metrics]
        ),
        "recency_bias_mean": _mean_or_default(
            [float(item["recency_bias_mean"]) for item in trace_metrics]
        ),
        "candidate_pool_size_mean": _mean_or_default(
            [float(item["candidate_pool_size_mean"]) for item in trace_metrics]
        ),
        "reachable_pool_size_mean": _mean_or_default(
            [float(item["reachable_pool_size_mean"]) for item in trace_metrics]
        ),
        "a_star_checked_pool_size_mean": _mean_or_default(
            [float(item["a_star_checked_pool_size_mean"]) for item in trace_metrics]
        ),
        "selected_viewpoint_rank_mean": _mean_or_default(
            [float(item["selected_viewpoint_rank_mean"]) for item in trace_metrics]
        ),
        "sampling_priority_mean": _mean_or_default(
            [float(item["sampling_priority_mean"]) for item in trace_metrics]
        ),
        "sssp_build_time_ms_mean": _mean_or_default(
            [float(item["sssp_build_time_ms_mean"]) for item in trace_metrics]
        ),
        "path_reconstruct_time_ms_mean": _mean_or_default(
            [float(item["path_reconstruct_time_ms_mean"]) for item in trace_metrics]
        ),
        "sampling_pool_build_time_ms_mean": _mean_or_default(
            [float(item["sampling_pool_build_time_ms_mean"]) for item in trace_metrics]
        ),
        "priority_feature_time_ms_mean": _mean_or_default(
            [float(item["priority_feature_time_ms_mean"]) for item in trace_metrics]
        ),
        "tree_total_score_mean": _mean_or_default(
            [float(item["tree_total_score_mean"]) for item in trace_metrics]
        ),
        "tree_conditional_gain_lvl2_mean": _mean_or_default(
            [float(item["tree_conditional_gain_lvl2_mean"]) for item in trace_metrics]
        ),
        "tree_redundant_visible_ratio_lvl2_mean": _mean_or_default(
            [float(item["tree_redundant_visible_ratio_lvl2_mean"]) for item in trace_metrics]
        ),
        "tree_expansion_count_mean": _mean_or_default(
            [float(item["tree_expansion_count_mean"]) for item in trace_metrics]
        ),
        "tree_unique_visible_count_lvl1_mean": _mean_or_default(
            [float(item["tree_unique_visible_count_lvl1_mean"]) for item in trace_metrics]
        ),
        "tree_unique_visible_count_lvl2_mean": _mean_or_default(
            [float(item["tree_unique_visible_count_lvl2_mean"]) for item in trace_metrics]
        ),
        "tree_planning_time_ms_mean": _mean_or_default(
            [float(item["tree_planning_time_ms_mean"]) for item in trace_metrics]
        ),
        "tree_child_oracle_gap_mean": _mean_or_default(
            [float(item["tree_child_oracle_gap_mean"]) for item in trace_metrics]
        ),
        "tree_child_oracle_rank_of_budgeted_mean": _mean_or_default(
            [float(item["tree_child_oracle_rank_of_budgeted_mean"]) for item in trace_metrics]
        ),
        "tree_child_budget_matches_oracle_rate": _mean_or_default(
            [float(item["tree_child_budget_matches_oracle_rate"]) for item in trace_metrics]
        ),
        "tree_child_full_candidate_count_mean": _mean_or_default(
            [float(item["tree_child_full_candidate_count_mean"]) for item in trace_metrics]
        ),
        "search_info_map_peak_final_mean": _mean_or_default(
            [float(result.get("search_info_map_peak_final", 0.0)) for result in policy_results]
        ),
        "search_info_map_mean_final_mean": _mean_or_default(
            [float(result.get("search_info_map_mean_final", 0.0)) for result in policy_results]
        ),
        "clue_acquisition_modes": sorted(
            {
                str(result["clue_acquisition_mode"])
                for result in policy_results
                if result.get("clue_acquisition_mode") is not None
            }
        ),
        "path_safety_modes": sorted(
            {
                str(result.get("path_safety_mode", "off"))
                for result in policy_results
                if result.get("path_safety_mode") is not None
            }
        ),
        "viewpoint_generation_modes": sorted(
            {
                str(result.get("viewpoint_generation_mode", DEFAULT_VIEWPOINT_GENERATION_MODE))
                for result in policy_results
                if result.get("viewpoint_generation_mode") is not None
            }
        ),
        "anomaly_top_band_selection_ratio_pre_first_detection_mean": _mean_or_default(
            [
                float(result.get("anomaly_top_band_selection_ratio_pre_first_detection", 0.0))
                for result in policy_results
            ]
        ),
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection_mean": _mean_or_default(
            [
                float(
                    result.get(
                        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
                        0.0,
                    )
                )
                for result in policy_results
            ]
        ),
        "viewpoint_rule_counts": _merge_count_dicts(
            [item["viewpoint_rule_counts"] for item in trace_metrics]
        ),
        "anchor_source_counts": _merge_count_dicts(
            [item["anchor_source_counts"] for item in trace_metrics]
        ),
    }
    _validate_knownmap_policy_summary_contract(summary_row)
    return summary_row


def _paired_outcome_rows(
    results_by_policy: dict[str, list[dict]],
    episode_seeds: list[int] | tuple[int, ...],
) -> list[dict]:
    rows = []
    policy_names = list(results_by_policy.keys())
    for row_idx, episode_seed in enumerate(episode_seeds):
        row = {"episode_seed": episode_seed}
        for policy_name in policy_names:
            result = results_by_policy[policy_name][row_idx]
            trace_metrics = _result_trace_metrics(result)
            prefix = f"{policy_name}__"
            row[prefix + "success_all_found"] = result["success_all_found"]
            row[prefix + "found_count"] = result["found_count"]
            row[prefix + "miss_count"] = result["miss_count"]
            row[prefix + "time_to_first_detection"] = result["time_to_first_detection"]
            row[prefix + "time_to_all_found"] = result["time_to_all_found"]
            row[prefix + "time_to_next_detection"] = result["time_to_next_detection"]
            row[prefix + "known_free_observation_ratio_final"] = result["known_free_observation_ratio_final"]
            row[prefix + "path_length"] = result["path_length"]
            row[prefix + "switch_count"] = result["switch_count"]
            row[prefix + "anchor_switch_count"] = result.get("anchor_switch_count", 0)
            row[prefix + "replan_count"] = result["replan_count"]
            row[prefix + "stale_region_refresh_rate"] = trace_metrics["stale_region_refresh_rate"]
            row[prefix + "focus_on_anchor_cluster_duration"] = trace_metrics["focus_on_anchor_cluster_duration"]
            row[prefix + "same_anchor_segment_ratio"] = trace_metrics["same_anchor_segment_ratio"]
            row[prefix + "viewpoint_drift_under_same_anchor"] = trace_metrics["viewpoint_drift_under_same_anchor"]
            row[prefix + "path_invalidations_per_episode"] = trace_metrics["path_invalidations_per_episode"]
            row[prefix + "alpha_focus_mean"] = trace_metrics["alpha_focus_mean"]
            row[prefix + "kappa_commit_mean"] = trace_metrics["kappa_commit_mean"]
            row[prefix + "search_info_gain_mean"] = trace_metrics["search_info_gain_mean"]
            row[prefix + "recency_bias_mean"] = trace_metrics["recency_bias_mean"]
            row[prefix + "candidate_pool_size_mean"] = trace_metrics["candidate_pool_size_mean"]
            row[prefix + "reachable_pool_size_mean"] = trace_metrics["reachable_pool_size_mean"]
            row[prefix + "a_star_checked_pool_size_mean"] = trace_metrics["a_star_checked_pool_size_mean"]
            row[prefix + "selected_viewpoint_rank_mean"] = trace_metrics["selected_viewpoint_rank_mean"]
            row[prefix + "sampling_priority_mean"] = trace_metrics["sampling_priority_mean"]
            row[prefix + "sssp_build_time_ms_mean"] = trace_metrics["sssp_build_time_ms_mean"]
            row[prefix + "path_reconstruct_time_ms_mean"] = trace_metrics["path_reconstruct_time_ms_mean"]
            row[prefix + "sampling_pool_build_time_ms_mean"] = trace_metrics["sampling_pool_build_time_ms_mean"]
            row[prefix + "priority_feature_time_ms_mean"] = trace_metrics["priority_feature_time_ms_mean"]
            row[prefix + "tree_total_score_mean"] = trace_metrics["tree_total_score_mean"]
            row[prefix + "tree_conditional_gain_lvl2_mean"] = trace_metrics["tree_conditional_gain_lvl2_mean"]
            row[prefix + "tree_redundant_visible_ratio_lvl2_mean"] = (
                trace_metrics["tree_redundant_visible_ratio_lvl2_mean"]
            )
            row[prefix + "tree_expansion_count_mean"] = trace_metrics["tree_expansion_count_mean"]
            row[prefix + "tree_unique_visible_count_lvl1_mean"] = (
                trace_metrics["tree_unique_visible_count_lvl1_mean"]
            )
            row[prefix + "tree_unique_visible_count_lvl2_mean"] = (
                trace_metrics["tree_unique_visible_count_lvl2_mean"]
            )
            row[prefix + "tree_planning_time_ms_mean"] = trace_metrics["tree_planning_time_ms_mean"]
            row[prefix + "tree_child_oracle_gap_mean"] = trace_metrics["tree_child_oracle_gap_mean"]
            row[prefix + "tree_child_oracle_rank_of_budgeted_mean"] = (
                trace_metrics["tree_child_oracle_rank_of_budgeted_mean"]
            )
            row[prefix + "tree_child_budget_matches_oracle_rate"] = (
                trace_metrics["tree_child_budget_matches_oracle_rate"]
            )
            row[prefix + "tree_child_full_candidate_count_mean"] = (
                trace_metrics["tree_child_full_candidate_count_mean"]
            )
            row[prefix + "search_info_map_peak_final"] = result.get("search_info_map_peak_final", 0.0)
            row[prefix + "search_info_map_mean_final"] = result.get("search_info_map_mean_final", 0.0)
            row[prefix + "fraction_of_path_executed_before_replan_mean"] = (
                trace_metrics["fraction_of_path_executed_before_replan_mean"]
            )
            row[prefix + "planned_commit_window_mean"] = trace_metrics["planned_commit_window_mean"]
            row[prefix + "terminated_reason"] = result["terminated_reason"]
        rows.append(row)
    return rows


def summarize_knownmap_policy_comparison(
    results_by_policy: dict[str, list[dict]],
    baseline_policy: str = "known_map_greedy_viewpoint",
    challenger_policy: str = "marine_knownmap_path_v2",
    episode_seeds: list[int] | tuple[int, ...] | None = None,
) -> dict[str, object]:
    if baseline_policy not in results_by_policy:
        raise ValueError(f"Missing baseline_policy='{baseline_policy}' in results_by_policy")
    if challenger_policy not in results_by_policy:
        raise ValueError(f"Missing challenger_policy='{challenger_policy}' in results_by_policy")
    baseline_results = results_by_policy[baseline_policy]
    challenger_results = results_by_policy[challenger_policy]
    if len(baseline_results) != len(challenger_results):
        raise ValueError("Baseline and challenger result counts must match")

    resolved_episode_seeds = (
        [int(seed) for seed in episode_seeds]
        if episode_seeds is not None
        else list(range(len(baseline_results)))
    )
    if len(resolved_episode_seeds) != len(baseline_results):
        raise ValueError("episode_seeds length must match the baseline/challenger result counts")

    paired_rows: list[dict[str, object]] = []
    for episode_seed, baseline_result, challenger_result in zip(
        resolved_episode_seeds,
        baseline_results,
        challenger_results,
    ):
        baseline_trace = _result_trace_metrics(baseline_result)
        challenger_trace = _result_trace_metrics(challenger_result)
        row = {
            "episode_seed": episode_seed,
            "switch_count_delta": int(challenger_result["switch_count"] - baseline_result["switch_count"]),
            "anchor_switch_count_delta": int(
                challenger_result.get("anchor_switch_count", 0)
                - baseline_result.get("anchor_switch_count", 0)
            ),
            "replan_count_delta": int(challenger_result["replan_count"] - baseline_result["replan_count"]),
            "found_count_delta": int(challenger_result["found_count"] - baseline_result["found_count"]),
            "known_free_observation_ratio_final_delta": float(
                challenger_result["known_free_observation_ratio_final"]
                - baseline_result["known_free_observation_ratio_final"]
            ),
            "stale_region_refresh_rate_delta": float(
                challenger_trace["stale_region_refresh_rate"]
                - baseline_trace["stale_region_refresh_rate"]
            ),
            "same_anchor_segment_ratio_delta": float(
                challenger_trace["same_anchor_segment_ratio"]
                - baseline_trace["same_anchor_segment_ratio"]
            ),
            "viewpoint_drift_under_same_anchor_delta": float(
                challenger_trace["viewpoint_drift_under_same_anchor"]
                - baseline_trace["viewpoint_drift_under_same_anchor"]
            ),
            "path_invalidations_per_episode_delta": int(
                challenger_trace["path_invalidations_per_episode"]
                - baseline_trace["path_invalidations_per_episode"]
            ),
            "search_info_gain_delta": float(
                challenger_trace["search_info_gain_mean"] - baseline_trace["search_info_gain_mean"]
            ),
            "recency_bias_delta": float(
                challenger_trace["recency_bias_mean"] - baseline_trace["recency_bias_mean"]
            ),
            "candidate_pool_size_delta": float(
                challenger_trace["candidate_pool_size_mean"]
                - baseline_trace["candidate_pool_size_mean"]
            ),
            "reachable_pool_size_delta": float(
                challenger_trace["reachable_pool_size_mean"]
                - baseline_trace["reachable_pool_size_mean"]
            ),
            "a_star_checked_pool_size_delta": float(
                challenger_trace["a_star_checked_pool_size_mean"]
                - baseline_trace["a_star_checked_pool_size_mean"]
            ),
            "selected_viewpoint_rank_delta": float(
                challenger_trace["selected_viewpoint_rank_mean"]
                - baseline_trace["selected_viewpoint_rank_mean"]
            ),
            "sampling_priority_delta": float(
                challenger_trace["sampling_priority_mean"]
                - baseline_trace["sampling_priority_mean"]
            ),
            "fraction_of_path_executed_before_replan_delta": float(
                challenger_trace["fraction_of_path_executed_before_replan_mean"]
                - baseline_trace["fraction_of_path_executed_before_replan_mean"]
            ),
        }
        baseline_first = baseline_result.get("time_to_first_detection")
        challenger_first = challenger_result.get("time_to_first_detection")
        if baseline_first is not None and challenger_first is not None:
            row["time_to_first_detection_delta"] = int(challenger_first - baseline_first)
        else:
            row["time_to_first_detection_delta"] = None
        paired_rows.append(row)

    comparable_first_deltas = [
        float(row["time_to_first_detection_delta"])
        for row in paired_rows
        if row["time_to_first_detection_delta"] is not None
    ]
    comparison_summary = {
        "baseline_policy": baseline_policy,
        "challenger_policy": challenger_policy,
        "n_episodes": len(paired_rows),
        "baseline_summary": _policy_summary_rows(baseline_results),
        "challenger_summary": _policy_summary_rows(challenger_results),
        "paired_delta_summary": {
            "switch_count_delta_mean": _mean_or_default(
                [float(row["switch_count_delta"]) for row in paired_rows]
            ),
            "anchor_switch_count_delta_mean": _mean_or_default(
                [float(row["anchor_switch_count_delta"]) for row in paired_rows]
            ),
            "replan_count_delta_mean": _mean_or_default(
                [float(row["replan_count_delta"]) for row in paired_rows]
            ),
            "found_count_delta_mean": _mean_or_default(
                [float(row["found_count_delta"]) for row in paired_rows]
            ),
            "known_free_observation_ratio_final_delta_mean": _mean_or_default(
                [float(row["known_free_observation_ratio_final_delta"]) for row in paired_rows]
            ),
            "stale_region_refresh_rate_delta_mean": _mean_or_default(
                [float(row["stale_region_refresh_rate_delta"]) for row in paired_rows]
            ),
            "same_anchor_segment_ratio_delta_mean": _mean_or_default(
                [float(row["same_anchor_segment_ratio_delta"]) for row in paired_rows]
            ),
            "viewpoint_drift_under_same_anchor_delta_mean": _mean_or_default(
                [float(row["viewpoint_drift_under_same_anchor_delta"]) for row in paired_rows]
            ),
            "path_invalidations_per_episode_delta_mean": _mean_or_default(
                [float(row["path_invalidations_per_episode_delta"]) for row in paired_rows]
            ),
            "search_info_gain_delta_mean": _mean_or_default(
                [float(row["search_info_gain_delta"]) for row in paired_rows]
            ),
            "recency_bias_delta_mean": _mean_or_default(
                [float(row["recency_bias_delta"]) for row in paired_rows]
            ),
            "candidate_pool_size_delta_mean": _mean_or_default(
                [float(row["candidate_pool_size_delta"]) for row in paired_rows]
            ),
            "reachable_pool_size_delta_mean": _mean_or_default(
                [float(row["reachable_pool_size_delta"]) for row in paired_rows]
            ),
            "a_star_checked_pool_size_delta_mean": _mean_or_default(
                [float(row["a_star_checked_pool_size_delta"]) for row in paired_rows]
            ),
            "selected_viewpoint_rank_delta_mean": _mean_or_default(
                [float(row["selected_viewpoint_rank_delta"]) for row in paired_rows]
            ),
            "sampling_priority_delta_mean": _mean_or_default(
                [float(row["sampling_priority_delta"]) for row in paired_rows]
            ),
            "fraction_of_path_executed_before_replan_delta_mean": _mean_or_default(
                [float(row["fraction_of_path_executed_before_replan_delta"]) for row in paired_rows]
            ),
            "time_to_first_detection_delta_mean": (
                float(np.mean(comparable_first_deltas))
                if comparable_first_deltas
                else float("nan")
            ),
        },
        "paired_episode_rows": paired_rows,
    }
    _validate_knownmap_pairwise_contract(comparison_summary)
    return comparison_summary


def summarize_knownmap_policy_comparison_matrix(
    results_by_policy: dict[str, list[dict]],
    policy_names: tuple[str, ...] | list[str] | None = None,
    episode_seeds: list[int] | tuple[int, ...] | None = None,
    contract_path: str | None = None,
) -> dict[str, object]:
    contract = load_knownmap_experiment_contract(contract_path)
    frozen_policy_set = tuple(str(policy_name) for policy_name in contract["frozen_policy_set"])
    resolved_policy_names = (
        tuple(str(policy_name) for policy_name in policy_names)
        if policy_names is not None
        else frozen_policy_set
    )
    missing_policies = [
        policy_name for policy_name in resolved_policy_names if policy_name not in results_by_policy
    ]
    if missing_policies:
        raise ValueError(f"Missing policy results for known-map comparison matrix: {missing_policies}")

    pair_labels: list[str] = []
    pairwise_comparisons: dict[str, dict[str, object]] = {}
    for baseline_policy, challenger_policy in combinations(resolved_policy_names, 2):
        pair_label = f"{baseline_policy}__vs__{challenger_policy}"
        pair_labels.append(pair_label)
        pairwise_comparisons[pair_label] = summarize_knownmap_policy_comparison(
            results_by_policy,
            baseline_policy=baseline_policy,
            challenger_policy=challenger_policy,
            episode_seeds=episode_seeds,
        )

    return {
        "schema_version": contract["schema_version"],
        "baseline_revision_id": contract["baseline_revision_id"],
        "policy_names": list(resolved_policy_names),
        "pair_labels": pair_labels,
        "pairwise_comparisons": pairwise_comparisons,
    }


def _save_episode_artifacts(
    output_dir: Path,
    episode_seed: int,
    state: dict,
    result: dict,
    policy_name: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / f"trace_seed_{episode_seed:03d}.csv", result["trace_rows"])
    clue_heatmap_limits = state.get("clue_heatmap_limits")
    clue_vmin = float(clue_heatmap_limits[0]) if clue_heatmap_limits is not None else None
    clue_vmax = float(clue_heatmap_limits[1]) if clue_heatmap_limits is not None else None

    save_search_snapshot(
        output_dir / f"episode_{policy_name}_seed_{episode_seed:03d}.png",
        known_map=state["nav_map_prior"],
        robot_pos=state["robot_pos"],
        target_positions=state["target_positions"],
        found_mask=state["found_mask"],
        trajectory=state["trajectory"],
        path=state["committed_segment"],
        goal=state["committed_viewpoint"],
        anchor=state["committed_anchor"],
        step=state["completed_steps"],
        policy_name=policy_name,
        clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
        clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
        clue_heatmap_limits=clue_heatmap_limits,
        search_info_map=state.get("search_info_map"),
        intensity_map=state["intensity_map"],
        staleness_map=state["staleness_map"],
        plan_details=state["current_plan_details"],
        show_true_targets=False,
    )

    save_heatmap_snapshot(
        output_dir / f"staleness_snapshot_seed_{episode_seed:03d}.png",
        known_map=state["nav_map_prior"],
        heatmap=state["staleness_map"],
        title="Recency Bias Map",
        robot_pos=state["robot_pos"],
        goal=state["committed_viewpoint"],
        anchor=state["committed_anchor"],
    )
    save_heatmap_snapshot(
        output_dir / f"search_info_snapshot_seed_{episode_seed:03d}.png",
        known_map=state["nav_map_prior"],
        heatmap=state["search_info_map"],
        title="Search Info Map",
        robot_pos=state["robot_pos"],
        goal=state["committed_viewpoint"],
        anchor=state["committed_anchor"],
    )
    save_heatmap_snapshot(
        output_dir / f"clue_snapshot_seed_{episode_seed:03d}.png",
        known_map=state["nav_map_prior"],
        heatmap=state.get("gp_clue_planner_map", state["gp_acq_map"]),
        title=f"{_clue_heatmap_title(state.get('clue_acquisition_mode'))} Map",
        robot_pos=state["robot_pos"],
        goal=state["committed_viewpoint"],
        anchor=state["committed_anchor"],
        vmin=clue_vmin,
        vmax=clue_vmax,
    )
    save_heatmap_snapshot(
        output_dir / f"intensity_snapshot_seed_{episode_seed:03d}.png",
        known_map=state["nav_map_prior"],
        heatmap=state["intensity_map"],
        title="Intensity Map",
        robot_pos=state["robot_pos"],
        goal=state["committed_viewpoint"],
        anchor=state["committed_anchor"],
    )


def _init_knownmap_state(
    episode_seed: int,
    policy_name: str,
    n_targets: int,
    map_kind: str,
    target_motion_mode: str,
    target_count_upper_bound: int,
    staleness_tau_steps: int,
    resolution_m: float,
    sensor_range_m: float,
    min_target_separation_m: float,
    min_start_distance_m: float,
    gp_length_scale_m: float,
    gp_noise_std: float,
    gp_prior_mean: float,
    gp_beta: float,
    gp_optimize_hyperparams: bool,
    clue_sigma_m: float,
    clue_amplitude: float,
    clue_noise_std: float,
    map_height_cells: int = 40,
    map_width_cells: int = 60,
    search_info_clue_weight: float = 0.5,
    search_info_intensity_weight: float = 0.5,
    clue_acquisition_mode: str = "ucb",
    anomaly_tail_quantile: float = 0.90,
    anomaly_weight_lambda: float = 1.0,
    anomaly_warmup_steps: int = 20,
    anomaly_min_gp_points: int = 64,
    anomaly_top_quantile: float = 0.90,
    anomaly_top_mass_min: float = 0.18,
    anomaly_entropy_max: float = 0.85,
    anomaly_stability_min: float = 0.30,
    anomaly_alpha_max: float = 0.40,
    anomaly_pre_first_alpha_cap: float = 0.15,
    constraint_mode: str = "hard",
    r_hit: int = 1,
    clue_samples_per_step: int | None = None,
    path_safety_mode: str = "off",
    safe_nav_inflation_radius_cells: int = 0,
    safe_nav_soft_clearance_radius_cells: int = 1,
    safe_nav_lambda_clearance: float = 1.0,
    viewpoint_generation_mode: str = DEFAULT_VIEWPOINT_GENERATION_MODE,
    planner_adaptation_mode: str = "adaptive",
) -> dict:
    if target_motion_mode not in {"static", "random_walk"}:
        raise ValueError(f"Unsupported target_motion_mode='{target_motion_mode}'")
    map_height_cells = int(map_height_cells)
    map_width_cells = int(map_width_cells)
    if map_height_cells < 3 or map_width_cells < 3:
        raise ValueError(
            f"map_height_cells/map_width_cells must be >= 3, got {map_height_cells}x{map_width_cells}"
        )
    if clue_acquisition_mode not in SUPPORTED_CLUE_ACQUISITION_MODES:
        raise ValueError(
            "clue_acquisition_mode must be one of "
            f"{SUPPORTED_CLUE_ACQUISITION_MODES}, got '{clue_acquisition_mode}'"
        )
    if path_safety_mode not in SUPPORTED_PATH_SAFETY_MODES:
        raise ValueError(
            "path_safety_mode must be one of "
            f"{SUPPORTED_PATH_SAFETY_MODES}, got '{path_safety_mode}'"
        )
    if viewpoint_generation_mode not in SUPPORTED_VIEWPOINT_GENERATION_MODES:
        raise ValueError(
            "viewpoint_generation_mode must be one of "
            f"{SUPPORTED_VIEWPOINT_GENERATION_MODES}, got '{viewpoint_generation_mode}'"
        )
    if planner_adaptation_mode not in SUPPORTED_PLANNER_ADAPTATION_MODES:
        raise ValueError(
            "planner_adaptation_mode must be one of "
            f"{SUPPORTED_PLANNER_ADAPTATION_MODES}, got '{planner_adaptation_mode}'"
        )

    rngs = _spawn_rngs(episode_seed)
    true_map = create_world(
        h=map_height_cells,
        w=map_width_cells,
        map_kind=map_kind,
    )
    nav_map_prior = np.array(true_map, copy=True)
    robot_pos = find_free_start(nav_map_prior)
    sensor_range_cells = _sensor_range_cells(sensor_range_m, resolution_m)
    min_target_separation_cells = _distance_cells(min_target_separation_m, resolution_m)
    min_start_distance_cells = _distance_cells(min_start_distance_m, resolution_m)
    clue_sigma_cells = _distance_cells(clue_sigma_m, resolution_m)

    target_positions, target_ids, placement_info = sample_targets(
        true_map,
        n_targets=n_targets,
        rng=rngs["scenario_rng"],
        start_pos=robot_pos,
        min_target_separation_cells=min_target_separation_cells,
        min_start_distance_cells=min_start_distance_cells,
        constraint_mode=constraint_mode,
    )
    found_mask = np.zeros(n_targets, dtype=bool)
    find_times: list[int | None] = [None] * n_targets
    last_seen_step = init_last_seen(nav_map_prior)
    refresh_last_seen(last_seen_step, nav_map_prior, robot_pos, sensor_range_cells, step=0)

    initial_detected = detect_targets(
        robot_pos,
        target_positions,
        found_mask,
        sensor_range_cells,
        rngs["detection_rng"],
    )
    initial_found_indices = update_found_mask(found_mask, initial_detected, find_times, step=0)

    h, w = true_map.shape
    grid_xy = make_grid_xy(h, w, resolution=resolution_m)
    max_map_extent = float(max(h, w)) * resolution_m
    kernel = default_kernel(
        length_scale=gp_length_scale_m,
        noise_level=gp_noise_std**2,
        length_scale_bounds=(resolution_m, 5.0 * max_map_extent),
    )
    gp_field = GPSuspicionField(
        kernel_cfg=kernel,
        prior_mean=gp_prior_mean,
    )

    safe_nav_inflation_radius_cells = max(0, int(safe_nav_inflation_radius_cells))
    safe_nav_soft_clearance_radius_cells = max(0, int(safe_nav_soft_clearance_radius_cells))
    obstacle_distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated_nav_map = None
    clearance_cost_map = None
    if path_safety_mode == "soft_clearance_astar_v1":
        inflated_nav_map = inflate_occupancy_map(
            nav_map_prior,
            inflation_radius_cells=safe_nav_inflation_radius_cells,
            obstacle_distance_map=obstacle_distance_map,
        )
        clearance_cost_map = build_clearance_cost_map(
            nav_map_prior,
            inflation_radius_cells=safe_nav_inflation_radius_cells,
            soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
            obstacle_distance_map=obstacle_distance_map,
            inflated_nav_map=inflated_nav_map,
        )

    state = {
        "true_map": true_map,
        "nav_map_prior": nav_map_prior,
        "knownmap_geometry_cache": _knownmap_precompute_viewpoint_geometry_cache(
            nav_map_prior,
            sensor_range_cells,
        ),
        "path_safety_mode": str(path_safety_mode),
        "viewpoint_generation_mode": str(viewpoint_generation_mode),
        "planner_adaptation_mode": str(planner_adaptation_mode),
        "safe_nav_inflation_radius_cells": int(safe_nav_inflation_radius_cells),
        "safe_nav_soft_clearance_radius_cells": int(safe_nav_soft_clearance_radius_cells),
        "safe_nav_lambda_clearance": float(safe_nav_lambda_clearance),
        "safe_nav_obstacle_distance_map": obstacle_distance_map,
        "safe_nav_inflated_nav_map": inflated_nav_map,
        "safe_nav_clearance_cost_map": clearance_cost_map,
        "robot_pos": robot_pos,
        "target_positions": target_positions,
        "target_ids": target_ids,
        "found_mask": found_mask,
        "find_times": find_times,
        "last_seen_step": last_seen_step,
        "staleness_map": build_staleness_map(
            last_seen_step,
            nav_map_prior,
            current_step=0,
            tau_stale=staleness_tau_steps,
        ),
        "committed_viewpoint": None,
        "committed_anchor": None,
        "committed_anchor_centroid": None,
        "committed_segment": [],
        "current_plan_details": {},
        "trajectory": [robot_pos],
        "path_length": 0,
        "replan_count": 0,
        "switch_count": 0,
        "anchor_switch_count": 0,
        "completed_steps": 0,
        "current_step": 0,
        "terminated_reason": "max_iters",
        "resolution_m": float(resolution_m),
        "map_kind": map_kind,
        "map_height_cells": int(h),
        "map_width_cells": int(w),
        "sensor_range_m": float(sensor_range_m),
        "sensor_range_cells": sensor_range_cells,
        "min_target_separation_m": float(min_target_separation_m),
        "min_target_separation_cells": float(min_target_separation_cells),
        "min_start_distance_m": float(min_start_distance_m),
        "min_start_distance_cells": float(min_start_distance_cells),
        "constraint_mode": placement_info["constraint_mode"],
        "placement_status": placement_info["placement_status"],
        "actual_min_target_separation_cells": placement_info["actual_min_target_separation_cells"],
        "actual_min_start_distance_cells": placement_info["actual_min_start_distance_cells"],
        "gp_beta": float(gp_beta),
        "gp_optimize_hyperparams": bool(gp_optimize_hyperparams),
        "gp_length_scale_m": float(gp_length_scale_m),
        "gp_noise_std": float(gp_noise_std),
        "gp_prior_mean": float(gp_prior_mean),
        "clue_acquisition_mode": str(clue_acquisition_mode),
        "anomaly_tail_quantile": float(anomaly_tail_quantile),
        "anomaly_weight_lambda": float(anomaly_weight_lambda),
        "anomaly_warmup_steps": int(anomaly_warmup_steps),
        "anomaly_min_gp_points": int(anomaly_min_gp_points),
        "anomaly_top_quantile": float(anomaly_top_quantile),
        "anomaly_top_mass_min": float(anomaly_top_mass_min),
        "anomaly_entropy_max": float(anomaly_entropy_max),
        "anomaly_stability_min": float(anomaly_stability_min),
        "anomaly_alpha_max": float(anomaly_alpha_max),
        "anomaly_pre_first_alpha_cap": float(anomaly_pre_first_alpha_cap),
        "anomaly_conditional_alpha": 0.0,
        "anomaly_conditional_triggered": False,
        "anomaly_gate_reason": "mode_not_conditional",
        "anomaly_top_mass_ratio": 0.0,
        "anomaly_entropy_norm": 0.0,
        "anomaly_hotspot_stability": 1.0,
        "anomaly_pre_first_alpha_capped": False,
        "clue_sigma_m": float(clue_sigma_m),
        "clue_sigma_cells": float(clue_sigma_cells),
        "clue_amplitude": float(clue_amplitude),
        "clue_noise_std": float(clue_noise_std),
        "search_info_clue_weight": float(search_info_clue_weight),
        "search_info_intensity_weight": float(search_info_intensity_weight),
        "gp_field": gp_field,
        "gp_mu_map": np.zeros_like(true_map, dtype=float),
        "gp_var_map": np.zeros_like(true_map, dtype=float),
        "gp_acq_map": np.zeros_like(true_map, dtype=float),
        "gp_anomaly_prob_map": np.zeros_like(true_map, dtype=float),
        "gp_anomaly_weight_map": np.zeros_like(true_map, dtype=float),
        "gp_anomaly_acq_map": np.zeros_like(true_map, dtype=float),
        "gp_clue_planner_map": np.zeros_like(true_map, dtype=float),
        "anomaly_conditional_top_mask": np.zeros_like(true_map, dtype=bool),
        "anomaly_tail_threshold": 0.0,
        "anomaly_top_band_threshold": 0.0,
        "search_info_map": np.zeros_like(true_map, dtype=float),
        "search_info_clue_component_map": np.zeros_like(true_map, dtype=float),
        "search_info_intensity_component_map": np.zeros_like(true_map, dtype=float),
        "search_info_map_peak": 0.0,
        "search_info_map_mean": 0.0,
        "clue_field_fn": None,
        "clue_true_map": None,
        "grid_xy": grid_xy,
        "scenario_rng": rngs["scenario_rng"],
        "detection_rng": rngs["detection_rng"],
        "observation_rng": rngs["observation_rng"],
        "planning_time_ms": [],
        "found_count_curve": [int(found_mask.sum())],
        "trace_rows": [],
        "mode_history": [],
        "anomaly_target_neighborhood_mass_ratio_rows": [],
        "target_motion_mode": target_motion_mode,
        "target_count_upper_bound": int(target_count_upper_bound),
        "staleness_tau_steps": int(staleness_tau_steps),
        "alpha_focus": 0.0,
        "kappa_commit": 0.0,
        "alpha_focus_curve": [],
        "kappa_commit_curve": [],
        "last_planned_segment_length": 0,
        "last_planned_commit_window": 0,
        "last_commit_policy": "unplanned",
        "last_anchor_source": None,
        "steps_since_replan": 0,
        "same_anchor_steps": 0,
        "recent_viewpoint_drifts": [],
        "recent_segment_flips": [],
        "recent_effective_observation_gains": [],
        "recent_path_invalidations": [],
        "time_since_last_detection": 0 if initial_found_indices else 20,
        # Reserved hook for future mismatch/dynamic-obstacle extensions.
        "path_invalidations_per_episode": 0,
        "focus_on_anchor_cluster_steps": 0,
        "r_hit": int(r_hit),
        "last_move_dir": None,
        "clue_samples_per_step": clue_samples_per_step,
    }

    state["intensity_map"] = init_intensity_map(nav_map_prior, total_mass=float(found_mask.size))
    if initial_found_indices:
        hit_positions = [
            tuple(int(v) for v in state["target_positions"][idx])
            for idx in initial_found_indices
        ]
        state["intensity_map"] = hit_update_intensity(
            state["intensity_map"],
            hit_positions=hit_positions,
            hit_count=len(initial_found_indices),
            r_hit=r_hit,
            known_map=state["nav_map_prior"],
            target_total_mass=_remaining_target_intensity_mass(state),
        )
    else:
        state["intensity_map"] = miss_update_intensity(
            state["intensity_map"],
            state["robot_pos"],
            state["sensor_range_cells"],
            known_map=state["nav_map_prior"],
            preserve_total_mass=True,
            target_total_mass=_remaining_target_intensity_mass(state),
        )
    state["remaining_intensity_mass_curve"] = [remaining_intensity_mass(state["intensity_map"])]
    state["peak_intensity_ratio_curve"] = [
        peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
    ]
    state["known_free_observation_ratio_curve"] = [
        known_free_observation_ratio(state["last_seen_step"], state["nav_map_prior"])
    ]

    _update_clue_truth_map(state)
    X_init, y_init = sample_clue_field(
        state["clue_field_fn"],
        state["robot_pos"],
        state["sensor_range_cells"],
        state["observation_rng"],
        n_samples=clue_samples_per_step,
        noise_std=state["clue_noise_std"],
        resolution=state["resolution_m"],
        map_shape=state["true_map"].shape,
    )
    if len(X_init) > 0:
        state["gp_field"].add_observations(X_init, y_init, t=0.0)
    _refresh_gp_state(state, optimize_hyperparams=gp_optimize_hyperparams)
    _update_search_info_state(state, state["intensity_map"])
    _append_anomaly_target_neighborhood_metric(state, step=0)
    state["clue_heatmap_limits"] = _fixed_clue_heatmap_limits(state)
    return state


def run_episode_single_usv_search_knownmap(
    episode_seed: int = 0,
    max_iters: int = 300,
    policy_name: str = "marine_search_soft_knownmap",
    n_targets: int = 3,
    map_kind: str = "obstacle_field",
    map_height_cells: int = 40,
    map_width_cells: int = 60,
    target_motion_mode: str = "static",
    target_count_mode: str = "upper_bound",
    target_count_upper_bound: int | None = None,
    staleness_tau_steps: int = 12,
    resolution_m: float = 5.0,
    sensor_range_m: float = 25.0,
    min_target_separation_m: float = 30.0,
    min_start_distance_m: float = 40.0,
    gp_length_scale_m: float = 20.0,
    gp_noise_std: float = 0.03,
    gp_prior_mean: float = 0.0,
    gp_beta: float = 0.5,
    gp_fit_every: int = 5,
    gp_optimize_hyperparams: bool = False,
    gp_max_points: int = 400,
    clue_samples_per_step: int | None = 24,
    clue_sigma_m: float = 20.0,
    clue_amplitude: float = 2.0,
    clue_noise_std: float = 0.03,
    search_info_clue_weight: float = 0.5,
    search_info_intensity_weight: float = 0.5,
    clue_acquisition_mode: str = "ucb",
    anomaly_tail_quantile: float = 0.90,
    anomaly_weight_lambda: float = 1.0,
    anomaly_warmup_steps: int = 20,
    anomaly_min_gp_points: int = 64,
    anomaly_top_quantile: float = 0.90,
    anomaly_top_mass_min: float = 0.18,
    anomaly_entropy_max: float = 0.85,
    anomaly_stability_min: float = 0.30,
    anomaly_alpha_max: float = 0.40,
    anomaly_pre_first_alpha_cap: float = 0.15,
    constraint_mode: str = "hard",
    lambda_u_turn: float = 2.0,
    gamma: float = 0.95,
    search_commit_window: int = 4,
    search_commit_max_window: int = 10,
    search_commit_path_divisor: int = 2,
    segment_horizon: int = 8,
    top_k_anchors: int = 6,
    viewpoints_per_anchor: int = 6,
    infosampled_inspected_limit_multiplier: float = 3.0,
    infosampled_inspected_limit_floor: int = 4,
    tree_first_layer_top_m: int = KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M,
    tree_second_layer_top_n: int = KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N,
    tree_discount_gamma: float = 0.85,
    tree_enable_diminishing_returns: bool = True,
    tree_enable_child_oracle_diagnostics: bool = True,
    path_safety_mode: str = "off",
    safe_nav_inflation_radius_cells: int = 0,
    safe_nav_soft_clearance_radius_cells: int = 1,
    safe_nav_lambda_clearance: float = 1.0,
    viewpoint_generation_mode: str = DEFAULT_VIEWPOINT_GENERATION_MODE,
    planner_adaptation_mode: str = "adaptive",
    r_hit: int = 1,
    render: bool = False,
    show_true_targets_in_viz: bool = False,
    output_dir: str | None = None,
    save_artifacts: bool = False,
) -> dict:
    if policy_name not in SUPPORTED_KNOWNMAP_POLICIES:
        raise ValueError(f"Unsupported policy_name='{policy_name}'")
    if target_count_mode != "upper_bound":
        raise ValueError(f"Unsupported target_count_mode='{target_count_mode}'")
    if target_count_upper_bound is None:
        target_count_upper_bound = int(n_targets)
    if target_count_upper_bound < n_targets:
        raise ValueError("target_count_upper_bound must be >= n_targets")
    if planner_adaptation_mode not in SUPPORTED_PLANNER_ADAPTATION_MODES:
        raise ValueError(
            "planner_adaptation_mode must be one of "
            f"{SUPPORTED_PLANNER_ADAPTATION_MODES}, got '{planner_adaptation_mode}'"
        )
    if viewpoint_generation_mode not in SUPPORTED_VIEWPOINT_GENERATION_MODES:
        raise ValueError(
            "viewpoint_generation_mode must be one of "
            f"{SUPPORTED_VIEWPOINT_GENERATION_MODES}, got '{viewpoint_generation_mode}'"
        )

    try:
        state = _init_knownmap_state(
            episode_seed=episode_seed,
            policy_name=policy_name,
            n_targets=n_targets,
            map_kind=map_kind,
            map_height_cells=map_height_cells,
            map_width_cells=map_width_cells,
            target_motion_mode=target_motion_mode,
            target_count_upper_bound=target_count_upper_bound,
            staleness_tau_steps=staleness_tau_steps,
            resolution_m=resolution_m,
            sensor_range_m=sensor_range_m,
            min_target_separation_m=min_target_separation_m,
            min_start_distance_m=min_start_distance_m,
            gp_length_scale_m=gp_length_scale_m,
            gp_noise_std=gp_noise_std,
            gp_prior_mean=gp_prior_mean,
            gp_beta=gp_beta,
            gp_optimize_hyperparams=gp_optimize_hyperparams,
            clue_sigma_m=clue_sigma_m,
            clue_amplitude=clue_amplitude,
            clue_noise_std=clue_noise_std,
            search_info_clue_weight=search_info_clue_weight,
            search_info_intensity_weight=search_info_intensity_weight,
            clue_acquisition_mode=clue_acquisition_mode,
            anomaly_tail_quantile=anomaly_tail_quantile,
            anomaly_weight_lambda=anomaly_weight_lambda,
            anomaly_warmup_steps=anomaly_warmup_steps,
            anomaly_min_gp_points=anomaly_min_gp_points,
            anomaly_top_quantile=anomaly_top_quantile,
            anomaly_top_mass_min=anomaly_top_mass_min,
            anomaly_entropy_max=anomaly_entropy_max,
            anomaly_stability_min=anomaly_stability_min,
            anomaly_alpha_max=anomaly_alpha_max,
            anomaly_pre_first_alpha_cap=anomaly_pre_first_alpha_cap,
            constraint_mode=constraint_mode,
            r_hit=r_hit,
            clue_samples_per_step=clue_samples_per_step,
            path_safety_mode=path_safety_mode,
            safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
            safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            viewpoint_generation_mode=viewpoint_generation_mode,
            planner_adaptation_mode=planner_adaptation_mode,
        )
    except PlacementInfeasibleError:
        result = _placement_infeasible_result(
            policy_name=policy_name,
            n_targets=n_targets,
            constraint_mode=constraint_mode,
            map_kind=map_kind,
            map_height_cells=map_height_cells,
            map_width_cells=map_width_cells,
            clue_acquisition_mode=clue_acquisition_mode,
            anomaly_tail_quantile=anomaly_tail_quantile,
            anomaly_weight_lambda=anomaly_weight_lambda,
        )
        result["planner_adaptation_mode"] = str(planner_adaptation_mode)
        return result

    state["gp_max_points"] = gp_max_points

    if render:
        plt.figure(figsize=(7, 6))
        plot_search_state(
            state["nav_map_prior"],
            state["robot_pos"],
            state["target_positions"],
            state["found_mask"],
            trajectory=state["trajectory"],
            path=state["committed_segment"],
            goal=state["committed_viewpoint"],
            anchor=state["committed_anchor"],
            step=0,
            policy_name=policy_name,
            clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
            clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
            clue_heatmap_limits=state.get("clue_heatmap_limits"),
            search_info_map=state["search_info_map"],
            intensity_map=state["intensity_map"],
            staleness_map=state["staleness_map"],
            plan_details=state["current_plan_details"],
            show_true_targets=show_true_targets_in_viz,
        )

    if np.all(state["found_mask"]):
        state["terminated_reason"] = "all_found"
        result = _summarize_result(state, policy_name)
        if save_artifacts and output_dir is not None:
            _save_episode_artifacts(Path(output_dir), episode_seed, state, result, policy_name)
        return result

    commit_remaining = 0

    for step in range(1, max_iters + 1):
        state["target_positions"] = step_targets(
            state["target_positions"],
            motion_mode=target_motion_mode,
            occ_grid=state["true_map"],
            rng=state["scenario_rng"],
            found_mask=state["found_mask"],
        )

        predicted_intensity = predict_intensity(
            state["intensity_map"],
            state["nav_map_prior"],
            motion_mode=target_motion_mode,
        )
        _update_search_info_state(state, predicted_intensity)

        state["alpha_focus"] = 0.0
        # Deprecated compatibility field: planner_adaptation_mode is still
        # accepted, but kappa_commit no longer changes planning decisions.
        state["kappa_commit"] = 0.0

        path_invalidated = (
            len(state["committed_segment"]) > 1
            and state["nav_map_prior"][state["committed_segment"][1]] != FREE
        )
        replan_reasons = []
        if state["committed_viewpoint"] is None:
            replan_reasons.append("initial_plan")
        if commit_remaining <= 0:
            replan_reasons.append("commit_expired")
        if len(state["committed_segment"]) <= 1:
            replan_reasons.append("segment_empty")
        if path_invalidated:
            replan_reasons.append("path_invalidated")
            state["path_invalidations_per_episode"] += 1

        need_replan = bool(replan_reasons)
        replanned_this_step = False
        replan_reason = None
        path_length_current = max(len(state["committed_segment"]) - 1, 0)
        previous_viewpoint = state["committed_viewpoint"]
        previous_anchor_source = state.get("last_anchor_source")
        previous_anchor_centroid = state.get("committed_anchor_centroid")
        prev_plan_length = int(state["last_planned_segment_length"])
        fraction_before_replan = (
            float(state["steps_since_replan"]) / float(prev_plan_length)
            if prev_plan_length > 0
            else 0.0
        )

        if need_replan:
            replanned_this_step = True
            replan_reason = "|".join(dict.fromkeys(replan_reasons))
            state["replan_count"] += 1
            t0 = time.perf_counter()
            segment_path, plan_details = select_knownmap_path_segment_policy(
                policy_name=policy_name,
                nav_map_prior=state["nav_map_prior"],
                robot_pos=state["robot_pos"],
                sensor_range=state["sensor_range_cells"],
                last_seen_step=state["last_seen_step"],
                staleness_map=state["staleness_map"],
                clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
                intensity_map=predicted_intensity,
                search_info_map=state["search_info_map"],
                search_info_clue_component=state["search_info_clue_component_map"],
                search_info_intensity_component=state["search_info_intensity_component_map"],
                current_viewpoint=state["committed_viewpoint"],
                current_anchor=state["committed_anchor"],
                current_anchor_source=state.get("last_anchor_source"),
                current_anchor_centroid=state.get("committed_anchor_centroid"),
                current_segment_endpoint=(
                    tuple(int(v) for v in state["committed_segment"][-1])
                    if state.get("committed_segment")
                    else None
                ),
                prev_move_dir=state["last_move_dir"],
                kappa_commit=state["kappa_commit"],
                lambda_u_turn=lambda_u_turn,
                segment_horizon=segment_horizon,
                top_k_anchors=top_k_anchors,
                viewpoints_per_anchor=viewpoints_per_anchor,
                gamma=gamma,
                sampling_seed_base=int(episode_seed) * 1000003 + int(step) * 9176,
                infosampled_inspected_limit_multiplier=infosampled_inspected_limit_multiplier,
                infosampled_inspected_limit_floor=infosampled_inspected_limit_floor,
                viewpoint_generation_mode=state["viewpoint_generation_mode"],
                geometry_cache=state["knownmap_geometry_cache"],
                tree_first_layer_top_m=tree_first_layer_top_m,
                tree_second_layer_top_n=tree_second_layer_top_n,
                tree_discount_gamma=tree_discount_gamma,
                tree_enable_diminishing_returns=tree_enable_diminishing_returns,
                tree_enable_child_oracle_diagnostics=tree_enable_child_oracle_diagnostics,
                path_safety_mode=state["path_safety_mode"],
                inflated_nav_map=state.get("safe_nav_inflated_nav_map"),
                obstacle_distance_map=state.get("safe_nav_obstacle_distance_map"),
                clearance_cost_map=state.get("safe_nav_clearance_cost_map"),
                safe_nav_lambda_clearance=state["safe_nav_lambda_clearance"],
                safe_nav_inflation_radius_cells=state["safe_nav_inflation_radius_cells"],
                safe_nav_soft_clearance_radius_cells=state["safe_nav_soft_clearance_radius_cells"],
            )
            state["planning_time_ms"].append((time.perf_counter() - t0) * 1000.0)

            if segment_path is None:
                if state["path_safety_mode"] == "soft_clearance_astar_v1":
                    segment_path = [tuple(int(v) for v in state["robot_pos"])]
                    plan_details = {
                        **state["current_plan_details"],
                        **_safe_nav_wait_plan_details(state),
                    }
                else:
                    state["completed_steps"] = step - 1
                    state["terminated_reason"] = "no_segment"
                    break
            plan_details = _augment_plan_details_with_anomaly(
                state=state,
                plan_details=plan_details,
                segment_path=list(segment_path),
            )

            new_viewpoint = plan_details.get("viewpoint_cell")
            if new_viewpoint != previous_viewpoint:
                state["switch_count"] += 1

            planned_segment_length = max(len(segment_path) - 1, 0)
            if (
                state["path_safety_mode"] == "soft_clearance_astar_v1"
                and planned_segment_length <= 0
            ):
                commit_remaining, commit_policy = 0, "safe_nav_wait"
            else:
                commit_remaining, commit_policy = _policy_commit_window(
                    policy_name=policy_name,
                    planned_segment_length=planned_segment_length,
                    search_commit_window=search_commit_window,
                    search_commit_max_window=search_commit_max_window,
                    search_commit_path_divisor=search_commit_path_divisor,
                    kappa_commit=state["kappa_commit"],
                )
            state["committed_viewpoint"] = new_viewpoint
            state["committed_anchor"] = plan_details.get("anchor_cell")
            state["committed_anchor_centroid"] = plan_details.get("anchor_centroid_cell")
            state["committed_segment"] = list(segment_path)
            state["current_plan_details"] = dict(plan_details)
            state["last_planned_segment_length"] = planned_segment_length
            state["last_planned_commit_window"] = int(commit_remaining)
            state["last_commit_policy"] = commit_policy
            state["last_anchor_source"] = plan_details.get("anchor_source")
            state["steps_since_replan"] = 0
            path_length_current = planned_segment_length

            segment_flip_flag = (
                1.0 if previous_viewpoint is not None and new_viewpoint != previous_viewpoint else 0.0
            )
            _append_trimmed(state["recent_segment_flips"], segment_flip_flag, max_len=6)
            _append_trimmed(
                state["recent_viewpoint_drifts"],
                float(plan_details.get("viewpoint_drift_norm", 0.0)),
                max_len=6,
            )

            same_anchor_cluster_now = _same_anchor_cluster_state(
                previous_anchor_source,
                previous_anchor_centroid,
                state.get("last_anchor_source"),
                state.get("committed_anchor_centroid"),
                state["sensor_range_cells"],
            )
            if (
                previous_anchor_centroid is not None
                and state.get("committed_anchor_centroid") is not None
                and not same_anchor_cluster_now
            ):
                state["anchor_switch_count"] += 1
            if _semantic_anchor_source(state.get("last_anchor_source")):
                state["same_anchor_steps"] = state["same_anchor_steps"] + 1 if same_anchor_cluster_now else 1
            else:
                state["same_anchor_steps"] = 0
        else:
            plan_details = dict(state["current_plan_details"])
            commit_remaining -= 1

        if render:
            plot_search_state(
                state["nav_map_prior"],
                state["robot_pos"],
                state["target_positions"],
                state["found_mask"],
                trajectory=state["trajectory"],
                path=state["committed_segment"],
                goal=state["committed_viewpoint"],
                anchor=state["committed_anchor"],
                step=step - 1,
                policy_name=policy_name,
                clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
                clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
                clue_heatmap_limits=state.get("clue_heatmap_limits"),
                search_info_map=state["search_info_map"],
                intensity_map=predicted_intensity,
                staleness_map=state["staleness_map"],
                plan_details=state["current_plan_details"],
                show_true_targets=show_true_targets_in_viz,
            )

        exec_result = execute_next_step(
            state["true_map"],
            state["nav_map_prior"],
            state["robot_pos"],
            state["committed_segment"],
        )
        collision_this_step = bool(exec_result.collision)
        collision_cell = exec_result.collision_cell
        invalidation_flag = 0.0
        if exec_result.move_success:
            prev_pos = state["robot_pos"]
            state["robot_pos"] = exec_result.new_robot_pos
            state["committed_segment"] = state["committed_segment"][1:]
            state["path_length"] += 1
            state["trajectory"].append(state["robot_pos"])
            state["steps_since_replan"] += 1
            state["last_move_dir"] = move_direction(prev_pos, state["robot_pos"])
            if _semantic_anchor_source(state.get("last_anchor_source")):
                state["same_anchor_steps"] += 1
            else:
                state["same_anchor_steps"] = 0
        elif len(state["committed_segment"]) > 1:
            state["committed_segment"] = [state["robot_pos"]]
            commit_remaining = 0
            state["path_invalidations_per_episode"] += 1
            invalidation_flag = 1.0
        _append_trimmed(state["recent_path_invalidations"], invalidation_flag, max_len=6)

        effective_observation_gain, stale_refresh_ratio, _new_obs = _observation_progress_terms(state)
        refresh_last_seen(
            state["last_seen_step"],
            state["nav_map_prior"],
            state["robot_pos"],
            state["sensor_range_cells"],
            step=step,
        )
        state["staleness_map"] = build_staleness_map(
            state["last_seen_step"],
            state["nav_map_prior"],
            current_step=step,
            tau_stale=staleness_tau_steps,
        )
        _append_trimmed(
            state["recent_effective_observation_gains"],
            effective_observation_gain,
            max_len=10,
        )

        predicted_intensity = apply_known_occupancy_constraints(
            predicted_intensity,
            state["nav_map_prior"],
            preserve_mass=True,
        )

        remaining_target_mass_before = _remaining_target_intensity_mass(state)
        detected_mask = detect_targets(
            state["robot_pos"],
            state["target_positions"],
            state["found_mask"],
            state["sensor_range_cells"],
            state["detection_rng"],
        )
        new_indices = update_found_mask(state["found_mask"], detected_mask, state["find_times"], step)
        detected_count_this_step = len(new_indices)
        if detected_count_this_step > 0:
            state["time_since_last_detection"] = 0
        else:
            state["time_since_last_detection"] += 1

        if detected_count_this_step > 0:
            hit_positions = [
                tuple(int(v) for v in state["target_positions"][idx])
                for idx in new_indices
            ]
            state["intensity_map"] = hit_update_intensity(
                predicted_intensity,
                hit_positions=hit_positions,
                hit_count=detected_count_this_step,
                r_hit=state["r_hit"],
                known_map=state["nav_map_prior"],
                target_total_mass=_remaining_target_intensity_mass(state),
            )
        else:
            state["intensity_map"] = miss_update_intensity(
                predicted_intensity,
                state["robot_pos"],
                state["sensor_range_cells"],
                known_map=state["nav_map_prior"],
                preserve_total_mass=True,
                target_total_mass=remaining_target_mass_before,
            )

        _sample_and_update_gp(state, step=step, gp_fit_every=gp_fit_every)
        _update_search_info_state(state, state["intensity_map"])
        _append_anomaly_target_neighborhood_metric(state, step=step)

        state["found_count_curve"].append(int(state["found_mask"].sum()))
        state["remaining_intensity_mass_curve"].append(remaining_intensity_mass(state["intensity_map"]))
        state["peak_intensity_ratio_curve"].append(
            peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
        )
        state["known_free_observation_ratio_curve"].append(
            known_free_observation_ratio(state["last_seen_step"], state["nav_map_prior"])
        )
        state["alpha_focus_curve"].append(float(state["alpha_focus"]))
        state["kappa_commit_curve"].append(float(state["kappa_commit"]))
        state["completed_steps"] = step
        state["mode_history"].append(SEARCH_MODE)
        if _focus_anchor_source(state["last_anchor_source"]):
            state["focus_on_anchor_cluster_steps"] += 1
        state["trace_rows"].append(
            _trace_row(
                step=step,
                state=state,
                policy_name=policy_name,
                replanned_this_step=replanned_this_step,
                replan_reason=replan_reason,
                commit_remaining=commit_remaining,
                path_length_current=path_length_current,
                fraction_before_replan=fraction_before_replan,
                plan_details=state["current_plan_details"],
                detected_count_this_step=detected_count_this_step,
                collision_this_step=collision_this_step,
                collision_cell=collision_cell,
                effective_observation_gain=effective_observation_gain,
                stale_refresh_ratio=stale_refresh_ratio,
            )
        )

        if np.all(state["found_mask"]):
            state["terminated_reason"] = "all_found"
            if render:
                plot_search_state(
                    state["nav_map_prior"],
                    state["robot_pos"],
                    state["target_positions"],
                    state["found_mask"],
                    trajectory=state["trajectory"],
                    path=state["committed_segment"],
                    goal=state["committed_viewpoint"],
                    anchor=state["committed_anchor"],
                    step=step,
                    policy_name=policy_name,
                    clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
                    clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
                    clue_heatmap_limits=state.get("clue_heatmap_limits"),
                    search_info_map=state["search_info_map"],
                    intensity_map=state["intensity_map"],
                    staleness_map=state["staleness_map"],
                    plan_details=state["current_plan_details"],
                    show_true_targets=show_true_targets_in_viz,
                )
                plt.show()
            result = _summarize_result(state, policy_name)
            if save_artifacts and output_dir is not None:
                _save_episode_artifacts(Path(output_dir), episode_seed, state, result, policy_name)
            return result
    else:
        state["completed_steps"] = max_iters

    if render:
        plot_search_state(
            state["nav_map_prior"],
            state["robot_pos"],
            state["target_positions"],
            state["found_mask"],
            trajectory=state["trajectory"],
            path=state["committed_segment"],
            goal=state["committed_viewpoint"],
            anchor=state["committed_anchor"],
            step=state["completed_steps"],
            policy_name=policy_name,
            clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
            clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
            clue_heatmap_limits=state.get("clue_heatmap_limits"),
            search_info_map=state["search_info_map"],
            intensity_map=state["intensity_map"],
            staleness_map=state["staleness_map"],
            plan_details=state["current_plan_details"],
            show_true_targets=show_true_targets_in_viz,
        )
        plt.show()

    result = _summarize_result(state, policy_name)
    if save_artifacts and output_dir is not None:
        _save_episode_artifacts(Path(output_dir), episode_seed, state, result, policy_name)
    return result


def run_visual_single_usv_search_knownmap(
    episode_seed: int = 0,
    max_iters: int = 300,
    policy_name: str = "marine_search_soft_knownmap",
    show_true_targets_in_viz: bool = True,
    **kwargs,
) -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=episode_seed,
        max_iters=max_iters,
        policy_name=policy_name,
        render=True,
        show_true_targets_in_viz=show_true_targets_in_viz,
        **kwargs,
    )
    placement_suffix = (
        f" | placement={result['placement_status']}"
        if result["placement_status"] != "satisfied"
        else ""
    )
    print(
        f"\nSingle-USV known-map search result | policy={policy_name} | "
        f"success_all_found={result['success_all_found']} | "
        f"found_count={result['found_count']} | miss_count={result['miss_count']} | "
        f"path_length={result['path_length']} | steps={result['completed_steps']}"
        f"{placement_suffix}"
    )


def run_evaluation_single_usv_search_knownmap(
    n_episodes: int | None = None,
    max_iters: int | None = None,
    policy_names: tuple[str, ...] | list[str] | None = None,
    output_dir: str | None = None,
    save_artifacts: bool = False,
    episode_seeds: tuple[int, ...] | list[int] | None = None,
    contract_path: str | None = None,
    **episode_kwargs,
) -> dict[str, list[dict]]:
    (
        contract,
        resolved_policy_names,
        resolved_episode_seeds,
        resolved_max_iters,
        effective_episode_kwargs,
        override_keys,
    ) = _resolve_knownmap_eval_contract(
        contract_path=contract_path,
        n_episodes=n_episodes,
        max_iters=max_iters,
        policy_names=policy_names,
        episode_seeds=episode_seeds,
        episode_kwargs=episode_kwargs,
    )

    results_by_policy: dict[str, list[dict]] = {}
    eval_output_dir = _make_output_dir(output_dir) if save_artifacts else None

    for policy_name in resolved_policy_names:
        if policy_name not in SUPPORTED_KNOWNMAP_POLICIES:
            raise ValueError(f"Unsupported policy_name='{policy_name}'")

        policy_results: list[dict] = []
        policy_output_dir = eval_output_dir / policy_name if eval_output_dir is not None else None
        print(
            f"Evaluate single-USV known-map suspicious search | policy={policy_name} | "
            f"episodes={len(resolved_episode_seeds)} | max_iters={resolved_max_iters}"
        )
        for episode_idx, episode_seed in enumerate(resolved_episode_seeds):
            result = run_episode_single_usv_search_knownmap(
                episode_seed=episode_seed,
                max_iters=resolved_max_iters,
                policy_name=policy_name,
                render=False,
                output_dir=None if policy_output_dir is None else str(policy_output_dir),
                save_artifacts=save_artifacts,
                **effective_episode_kwargs,
            )
            policy_results.append(result)
            placement_suffix = (
                f" placement={result['placement_status']}"
                if result["placement_status"] != "satisfied"
                else ""
            )
            print(
                f"  [{episode_idx + 1:3d}/{len(resolved_episode_seeds)} | seed={episode_seed}] "
                f"success={result['success_all_found']} "
                f"found={result['found_count']} "
                f"miss={result['miss_count']} "
                f"first={result['time_to_first_detection']} "
                f"all={result['time_to_all_found']} "
                f"known_free_obs={result['known_free_observation_ratio_final']:.2f} "
                f"path={result['path_length']}"
                f"{placement_suffix}"
            )
        summary = _policy_summary_rows(policy_results)
        print(
            f"Summary | policy={policy_name} | "
            f"success_all_found={summary['success_all_found_mean']:.2f} | "
            f"found_count={summary['found_count_mean']:.2f} | "
            f"miss_count={summary['miss_count_mean']:.2f} | "
            f"detection_rate={summary['detection_rate_mean']:.2f} | "
            f"time_to_first={summary['time_to_first_detection_mean']:.1f} | "
            f"known_free_obs={summary['known_free_observation_ratio_final_mean']:.2f} | "
            f"stale_refresh={summary['stale_region_refresh_rate_mean']:.2f} | "
            f"same_anchor_segment={summary['same_anchor_segment_ratio_mean']:.2f} | "
            f"path_length={summary['path_length_mean']:.1f}"
        )
        results_by_policy[policy_name] = policy_results

    if eval_output_dir is not None:
        comparison_summary = None
        if (
            "known_map_greedy_viewpoint" in results_by_policy
            and "marine_knownmap_path_v2" in results_by_policy
        ):
            comparison_summary = summarize_knownmap_policy_comparison(
                results_by_policy,
                baseline_policy="known_map_greedy_viewpoint",
                challenger_policy="marine_knownmap_path_v2",
                episode_seeds=resolved_episode_seeds,
            )

        comparison_matrix = summarize_knownmap_policy_comparison_matrix(
            results_by_policy,
            policy_names=resolved_policy_names,
            episode_seeds=resolved_episode_seeds,
            contract_path=contract_path,
        )

        _write_csv(
            eval_output_dir / "paired_outcomes.csv",
            _paired_outcome_rows(results_by_policy, resolved_episode_seeds),
        )
        with (eval_output_dir / "knownmap_experiment_contract.json").open("w", encoding="utf-8") as f:
            json.dump(contract, f, indent=2, ensure_ascii=False)
        with (eval_output_dir / "comparison_matrix.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(comparison_matrix), f, indent=2, ensure_ascii=False)
        summary_payload = {
            "created_at": datetime.now().isoformat(),
            "n_episodes": len(resolved_episode_seeds),
            "max_iters": resolved_max_iters,
            "policy_names": list(resolved_policy_names),
            "episode_seeds": list(resolved_episode_seeds),
            "episode_kwargs": _json_safe(effective_episode_kwargs),
            "knownmap_contract_path": str(_knownmap_contract_path(contract_path)),
            "knownmap_contract_schema_version": contract["schema_version"],
            "knownmap_contract_baseline_revision_id": contract["baseline_revision_id"],
            "knownmap_contract_override_keys": override_keys,
            "knownmap_experiment_contract": _json_safe(contract),
            "policy_summary": {
                policy_name: _policy_summary_rows(results)
                for policy_name, results in results_by_policy.items()
            },
            "knownmap_policy_comparison": _json_safe(comparison_summary),
            "knownmap_policy_comparison_matrix": _json_safe(comparison_matrix),
        }
        with (eval_output_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    return results_by_policy


def run_knownmap_tree_budget_oracle_validation(
    *,
    output_dir: str | None = None,
    save_artifacts: bool = True,
    map_kinds: tuple[str, ...] | list[str] = ("open_water", "obstacle_field", "peninsula_passage"),
    episode_seeds: tuple[int, ...] | list[int] = (0, 1, 2, 3, 4),
    max_iters: int = 220,
    n_targets: int = 3,
    target_motion_mode: str = "random_walk",
    target_count_upper_bound: int = 4,
    clue_samples_per_step: int = 12,
    gp_max_points: int = 128,
    infosampled_inspected_limit_multiplier: float = 2.0,
    infosampled_inspected_limit_floor: int = 4,
    tree_discount_gamma: float = 0.85,
    tree_enable_diminishing_returns: bool = True,
) -> dict[str, object]:
    contract = load_knownmap_experiment_contract()
    base_episode_kwargs = dict(contract["frozen_config"])
    base_episode_kwargs.pop("episode_seeds", None)
    base_episode_kwargs.pop("max_iters", None)

    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
    strategy_specs = (
        {
            "strategy_label": "infosampled_ref",
            "policy_name": "marine_knownmap_path_v2_infosampled",
        },
        {
            "strategy_label": "tree_m2_n1",
            "policy_name": "marine_knownmap_path_v2_infosampled_tree_d2",
            "tree_first_layer_top_m": KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M,
            "tree_second_layer_top_n": KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N,
        },
        {
            "strategy_label": "tree_m2_n3",
            "policy_name": "marine_knownmap_path_v2_infosampled_tree_d2",
            "tree_first_layer_top_m": KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M,
            "tree_second_layer_top_n": KNOWNMAP_SIDE_BRANCH_TREE_SECOND_LAYER_TOP_N,
        },
    )

    output_path = _make_output_dir(output_dir, default_leaf="phase3x_child_oracle_validation")
    results_by_map_and_label: dict[tuple[str, str], list[dict]] = {}
    per_map_summary_rows: list[dict[str, object]] = []
    oracle_summary_rows: list[dict[str, object]] = []
    per_episode_rows: list[dict[str, object]] = []

    for map_kind in resolved_map_kinds:
        for spec in strategy_specs:
            policy_name = str(spec["policy_name"])
            strategy_label = str(spec["strategy_label"])
            eval_kwargs = dict(base_episode_kwargs)
            eval_kwargs.update(
                {
                    "map_kind": map_kind,
                    "n_targets": int(n_targets),
                    "target_motion_mode": target_motion_mode,
                    "target_count_upper_bound": int(target_count_upper_bound),
                    "clue_samples_per_step": int(clue_samples_per_step),
                    "gp_max_points": int(gp_max_points),
                    "infosampled_inspected_limit_multiplier": float(infosampled_inspected_limit_multiplier),
                    "infosampled_inspected_limit_floor": int(infosampled_inspected_limit_floor),
                    "tree_discount_gamma": float(tree_discount_gamma),
                    "tree_enable_diminishing_returns": bool(tree_enable_diminishing_returns),
                }
            )
            if "tree_first_layer_top_m" in spec:
                eval_kwargs["tree_first_layer_top_m"] = int(spec["tree_first_layer_top_m"])
            if "tree_second_layer_top_n" in spec:
                eval_kwargs["tree_second_layer_top_n"] = int(spec["tree_second_layer_top_n"])

            results = run_evaluation_single_usv_search_knownmap(
                max_iters=int(max_iters),
                policy_names=(policy_name,),
                output_dir=None,
                save_artifacts=False,
                episode_seeds=resolved_episode_seeds,
                **eval_kwargs,
            )
            policy_results = list(results[policy_name])
            results_by_map_and_label[(map_kind, strategy_label)] = policy_results

            summary_row = {
                "map_kind": map_kind,
                "strategy_label": strategy_label,
                "policy_name": policy_name,
                "tree_first_layer_top_m": int(spec.get("tree_first_layer_top_m", 0)),
                "tree_second_layer_top_n": int(spec.get("tree_second_layer_top_n", 0)),
                **_policy_summary_rows(policy_results),
            }
            per_map_summary_rows.append(summary_row)

            if strategy_label.startswith("tree_"):
                oracle_summary_rows.append(
                    {
                        "map_kind": map_kind,
                        "strategy_label": strategy_label,
                        "policy_name": policy_name,
                        "tree_first_layer_top_m": int(spec.get("tree_first_layer_top_m", 0)),
                        "tree_second_layer_top_n": int(spec.get("tree_second_layer_top_n", 0)),
                        "tree_child_oracle_gap_mean": float(summary_row["tree_child_oracle_gap_mean"]),
                        "tree_child_oracle_rank_of_budgeted_mean": float(
                            summary_row["tree_child_oracle_rank_of_budgeted_mean"]
                        ),
                        "tree_child_budget_matches_oracle_rate": float(
                            summary_row["tree_child_budget_matches_oracle_rate"]
                        ),
                        "tree_child_full_candidate_count_mean": float(
                            summary_row["tree_child_full_candidate_count_mean"]
                        ),
                        "tree_redundant_visible_ratio_lvl2_mean": float(
                            summary_row["tree_redundant_visible_ratio_lvl2_mean"]
                        ),
                        "tree_expansion_count_mean": float(summary_row["tree_expansion_count_mean"]),
                        "tree_planning_time_ms_mean": float(summary_row["tree_planning_time_ms_mean"]),
                    }
                )

            for episode_seed, result in zip(resolved_episode_seeds, policy_results):
                trace_metrics = _result_trace_metrics(result)
                per_episode_rows.append(
                    {
                        "map_kind": map_kind,
                        "strategy_label": strategy_label,
                        "policy_name": policy_name,
                        "episode_seed": int(episode_seed),
                        "tree_first_layer_top_m": int(spec.get("tree_first_layer_top_m", 0)),
                        "tree_second_layer_top_n": int(spec.get("tree_second_layer_top_n", 0)),
                        "success_all_found": bool(result["success_all_found"]),
                        "found_count": int(result["found_count"]),
                        "detection_rate": float(result["detection_rate"]),
                        "time_to_first_detection": result["time_to_first_detection"],
                        "time_to_all_found": result["time_to_all_found"],
                        "time_to_next_detection": result["time_to_next_detection"],
                        "path_length": float(result["path_length"]),
                        "planning_time_ms_mean": float(result["planning_time_ms_mean"]),
                        "same_anchor_segment_ratio": float(trace_metrics["same_anchor_segment_ratio"]),
                        "viewpoint_drift_under_same_anchor": float(
                            trace_metrics["viewpoint_drift_under_same_anchor"]
                        ),
                        "tree_total_score_mean": float(trace_metrics["tree_total_score_mean"]),
                        "tree_conditional_gain_lvl2_mean": float(
                            trace_metrics["tree_conditional_gain_lvl2_mean"]
                        ),
                        "tree_redundant_visible_ratio_lvl2_mean": float(
                            trace_metrics["tree_redundant_visible_ratio_lvl2_mean"]
                        ),
                        "tree_expansion_count_mean": float(trace_metrics["tree_expansion_count_mean"]),
                        "tree_child_oracle_gap_mean": float(trace_metrics["tree_child_oracle_gap_mean"]),
                        "tree_child_oracle_rank_of_budgeted_mean": float(
                            trace_metrics["tree_child_oracle_rank_of_budgeted_mean"]
                        ),
                        "tree_child_budget_matches_oracle_rate": float(
                            trace_metrics["tree_child_budget_matches_oracle_rate"]
                        ),
                        "tree_child_full_candidate_count_mean": float(
                            trace_metrics["tree_child_full_candidate_count_mean"]
                        ),
                    }
                )

    cross_map_summary_rows: list[dict[str, object]] = []
    for spec in strategy_specs:
        strategy_label = str(spec["strategy_label"])
        policy_name = str(spec["policy_name"])
        combined_results: list[dict] = []
        for map_kind in resolved_map_kinds:
            combined_results.extend(results_by_map_and_label[(map_kind, strategy_label)])
        cross_map_summary_rows.append(
            {
                "map_kind": "ALL",
                "strategy_label": strategy_label,
                "policy_name": policy_name,
                "n_maps": int(len(resolved_map_kinds)),
                "n_episodes_total": int(len(combined_results)),
                "tree_first_layer_top_m": int(spec.get("tree_first_layer_top_m", 0)),
                "tree_second_layer_top_n": int(spec.get("tree_second_layer_top_n", 0)),
                **_policy_summary_rows(combined_results),
            }
        )

    def _is_behavior_advantage(delta_row: dict[str, float]) -> bool:
        return bool(
            delta_row["found_count_mean_delta"] >= 0.2
            or delta_row["detection_rate_mean_delta"] >= 0.05
            or delta_row["time_to_next_detection_mean_delta"] <= -5.0
        )

    def _is_oracle_mismatch(summary_row: dict[str, object]) -> bool:
        return bool(
            float(summary_row["tree_child_oracle_gap_mean"]) >= 0.5
            and (
                float(summary_row["tree_child_budget_matches_oracle_rate"]) <= 0.75
                or float(summary_row["tree_child_oracle_rank_of_budgeted_mean"]) >= 1.5
            )
        )

    per_map_by_label = {
        (str(row["map_kind"]), str(row["strategy_label"])): row
        for row in per_map_summary_rows
    }
    keep_drop_rows: list[dict[str, object]] = []
    behavior_advantage_map_count = 0
    oracle_mismatch_map_count = 0
    for map_kind in resolved_map_kinds:
        m2_n1 = per_map_by_label[(map_kind, "tree_m2_n1")]
        m2_n3 = per_map_by_label[(map_kind, "tree_m2_n3")]
        delta_row = {
            "map_kind": map_kind,
            "found_count_mean_delta": float(m2_n3["found_count_mean"]) - float(m2_n1["found_count_mean"]),
            "detection_rate_mean_delta": float(m2_n3["detection_rate_mean"])
            - float(m2_n1["detection_rate_mean"]),
            "time_to_next_detection_mean_delta": float(m2_n3["time_to_next_detection_mean"])
            - float(m2_n1["time_to_next_detection_mean"]),
            "planning_time_ms_mean_delta": float(m2_n3["planning_time_ms_mean"])
            - float(m2_n1["planning_time_ms_mean"]),
            "tree_child_oracle_gap_mean": float(m2_n3["tree_child_oracle_gap_mean"]),
            "tree_child_budget_matches_oracle_rate": float(
                m2_n3["tree_child_budget_matches_oracle_rate"]
            ),
            "tree_child_oracle_rank_of_budgeted_mean": float(
                m2_n3["tree_child_oracle_rank_of_budgeted_mean"]
            ),
        }
        delta_row["behavior_advantage_vs_m2_n1"] = _is_behavior_advantage(delta_row)
        delta_row["oracle_proxy_mismatch_likely"] = _is_oracle_mismatch(m2_n3)
        behavior_advantage_map_count += int(delta_row["behavior_advantage_vs_m2_n1"])
        oracle_mismatch_map_count += int(delta_row["oracle_proxy_mismatch_likely"])
        keep_drop_rows.append(delta_row)

    decision_report = {
        "map_kinds": list(resolved_map_kinds),
        "episode_seeds": list(resolved_episode_seeds),
        "reference_strategy": "infosampled_ref",
        "tree_budget_candidates": ["tree_m2_n1", "tree_m2_n3"],
        "active_tree_line_defaults": {
            "tree_first_layer_top_m": int(KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M),
            "tree_second_layer_top_n": int(KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N),
            "strategy_label": "tree_m2_n1",
        },
        "side_branch_tree_budget": {
            "tree_first_layer_top_m": int(KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M),
            "tree_second_layer_top_n": int(KNOWNMAP_SIDE_BRANCH_TREE_SECOND_LAYER_TOP_N),
            "strategy_label": "tree_m2_n3",
        },
        "decision_thresholds": {
            "behavior_advantage": {
                "found_count_mean_delta_gte": 0.2,
                "detection_rate_mean_delta_gte": 0.05,
                "time_to_next_detection_mean_delta_lte": -5.0,
                "required_maps": 2,
            },
            "oracle_proxy_mismatch": {
                "tree_child_oracle_gap_mean_gte": 0.5,
                "tree_child_budget_matches_oracle_rate_lte": 0.75,
                "tree_child_oracle_rank_of_budgeted_mean_gte": 1.5,
                "required_maps": 2,
            },
        },
        "per_map_rows": _json_safe(keep_drop_rows),
        "behavior_advantage_map_count": int(behavior_advantage_map_count),
        "oracle_mismatch_map_count": int(oracle_mismatch_map_count),
        "keep_m2_n3": bool(
            behavior_advantage_map_count >= 2 and oracle_mismatch_map_count >= 2
        ),
        "recommended_active_tree_line": (
            "tree_m2_n3"
            if behavior_advantage_map_count >= 2 and oracle_mismatch_map_count >= 2
            else "tree_m2_n1"
        ),
        "m2_n3_status": (
            "keep_active_line"
            if behavior_advantage_map_count >= 2 and oracle_mismatch_map_count >= 2
            else "downgrade_to_side_branch"
        ),
    }

    if save_artifacts:
        _write_csv(output_path / "cross_map_summary.csv", cross_map_summary_rows)
        _write_csv(output_path / "per_map_summary.csv", per_map_summary_rows)
        _write_csv(output_path / "episode_rows.csv", per_episode_rows)
        _write_csv(output_path / "oracle_diagnostic_summary.csv", oracle_summary_rows)
        _write_csv(output_path / "m2_n3_keep_drop_report.csv", keep_drop_rows)
        with (output_path / "cross_map_summary.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(cross_map_summary_rows), f, indent=2, ensure_ascii=False)
        with (output_path / "per_map_summary.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(per_map_summary_rows), f, indent=2, ensure_ascii=False)
        with (output_path / "oracle_diagnostic_summary.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(oracle_summary_rows), f, indent=2, ensure_ascii=False)
        with (output_path / "decision_report.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(decision_report), f, indent=2, ensure_ascii=False)

    return {
        "output_dir": str(output_path),
        "cross_map_summary_rows": cross_map_summary_rows,
        "per_map_summary_rows": per_map_summary_rows,
        "oracle_summary_rows": oracle_summary_rows,
        "episode_rows": per_episode_rows,
        "decision_report": decision_report,
    }
