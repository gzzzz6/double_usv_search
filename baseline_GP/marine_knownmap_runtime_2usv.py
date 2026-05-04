"""
Two-USV known-static-map suspicious target search runtime.

Phase 1 + Phase 2 baseline:
- centralized shared team state
- synchronous one-step execution
- fused clue / detection / recency / intensity updates
- minimal centralized joint assignment via residual search-info gain
"""

from __future__ import annotations

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
    from .core_map import FREE, OCCUPIED, create_world, sensor_cells
    from .core_safe_nav import (
        build_clearance_cost_map,
        build_obstacle_distance_map,
        build_reservation_table,
        evaluate_path_against_reservation,
        inflate_occupancy_map,
    )
    from .core_search_policy import (
        SUPPORTED_KNOWNMAP_POLICIES,
        SUPPORTED_PATH_SAFETY_MODES,
        _knownmap_precompute_viewpoint_geometry_cache,
        _knownmap_single_source_shortest_path_tree,
        _knownmap_visible_free_cells,
        rebuild_knownmap_segment_to_fixed_viewpoint,
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
    from .marine_knownmap_runtime import (
        _append_anomaly_target_neighborhood_metric,
        _append_trimmed,
        _augment_plan_details_with_anomaly,
        _build_search_info_maps,
        _clue_heatmap_title,
        _distance_cells,
        _distance_maybe_to_m,
        _fixed_clue_heatmap_limits,
        _json_safe,
        _label_counts,
        _make_output_dir,
        _mean_or_default,
        _policy_commit_window,
        _pre_first_detection_curve_mean,
        _pre_first_detection_trace_rows,
        _remaining_target_intensity_mass,
        _same_anchor_cluster_state,
        _search_info_stats,
        _semantic_anchor_source,
        _sensor_range_cells,
        _spawn_rngs,
        _write_csv,
        run_episode_single_usv_search_knownmap,
    )
    from .viz_search import plot_team_search_state
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
    from core_map import FREE, OCCUPIED, create_world, sensor_cells
    from core_safe_nav import (
        build_clearance_cost_map,
        build_obstacle_distance_map,
        build_reservation_table,
        evaluate_path_against_reservation,
        inflate_occupancy_map,
    )
    from core_search_policy import (
        SUPPORTED_KNOWNMAP_POLICIES,
        SUPPORTED_PATH_SAFETY_MODES,
        _knownmap_precompute_viewpoint_geometry_cache,
        _knownmap_single_source_shortest_path_tree,
        _knownmap_visible_free_cells,
        rebuild_knownmap_segment_to_fixed_viewpoint,
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
    from marine_knownmap_runtime import (
        _append_anomaly_target_neighborhood_metric,
        _append_trimmed,
        _augment_plan_details_with_anomaly,
        _build_search_info_maps,
        _clue_heatmap_title,
        _distance_cells,
        _distance_maybe_to_m,
        _fixed_clue_heatmap_limits,
        _json_safe,
        _label_counts,
        _make_output_dir,
        _mean_or_default,
        _policy_commit_window,
        _pre_first_detection_curve_mean,
        _pre_first_detection_trace_rows,
        _remaining_target_intensity_mass,
        _same_anchor_cluster_state,
        _search_info_stats,
        _semantic_anchor_source,
        _sensor_range_cells,
        _spawn_rngs,
        _write_csv,
        run_episode_single_usv_search_knownmap,
    )
    from viz_search import plot_team_search_state


TWO_USV_POLICY_TO_SINGLE: dict[str, str] = {
    "known_map_greedy_viewpoint_2usv": "known_map_greedy_viewpoint",
    "marine_search_soft_knownmap_2usv": "marine_search_soft_knownmap",
    "marine_knownmap_path_v2_infofused_2usv": "marine_knownmap_path_v2_infofused",
    "marine_knownmap_path_v2_infosampled_2usv": "marine_knownmap_path_v2_infosampled",
}
SUPPORTED_TWO_USV_KNOWNMAP_POLICIES = tuple(TWO_USV_POLICY_TO_SINGLE.keys())
TWO_USV_FIXED_START_POSITIONS = ((25, 2), (35, 2))
# Deprecated compatibility modes. Both choices are currently accepted but ignored:
# kappa_commit is restricted to a non-decision trace field.
SUPPORTED_TWO_USV_PLANNER_ADAPTATION_MODES = ("adaptive", "no_kappa")
KNOWNMAP_EXPERIMENT_2USV_CONTRACT_FILENAME = "knownmap_experiment_contract_2usv_v1.json"
KNOWNMAP_EXPERIMENT_2USV_CONTRACT_PATH = Path(__file__).with_name(
    KNOWNMAP_EXPERIMENT_2USV_CONTRACT_FILENAME
)
RESPONSIBILITY_BUFFER_BAND_CELLS = 4
SUPPORTED_TWO_USV_ASSIGNMENT_MODES = ("coordinated", "independent")
SUPPORTED_TEAM_PATH_AVOIDANCE_MODES = ("off", "reservation_v1")
PHASE7_SYSTEM_SINGLE = "single_usv_infosampled"
PHASE7_SYSTEM_TWO_USV_INDEPENDENT = "two_usv_independent"
PHASE7_SYSTEM_TWO_USV_COORDINATED = "two_usv_coordinated"
PHASE7_DEFAULT_MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
PHASE7_SHARED_METRICS = (
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "planning_time_ms_mean",
)
PHASE7_AUXILIARY_METRICS = (
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
)
PHASE7_TWO_USV_ONLY_METRICS = (
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "conflict_intervention_count",
    "wait_count_total",
)
PHASE7_PAIRWISE_METRICS = PHASE7_SHARED_METRICS + PHASE7_AUXILIARY_METRICS + PHASE7_TWO_USV_ONLY_METRICS
PHASE7_INT_DELTA_METRICS = {
    "time_to_first_detection",
    "time_to_all_found",
    "found_count",
    "conflict_intervention_count",
    "wait_count_total",
}


def _team_underlying_policy(policy_name: str) -> str:
    if policy_name not in TWO_USV_POLICY_TO_SINGLE:
        raise ValueError(f"Unsupported 2-USV known-map policy_name='{policy_name}'")
    single_policy_name = TWO_USV_POLICY_TO_SINGLE[policy_name]
    if single_policy_name not in SUPPORTED_KNOWNMAP_POLICIES:
        raise ValueError(f"Underlying single-USV policy is unsupported: '{single_policy_name}'")
    return single_policy_name


def load_knownmap_experiment_contract_2usv(contract_path: str | None = None) -> dict[str, object]:
    resolved_path = (
        Path(contract_path)
        if contract_path is not None
        else KNOWNMAP_EXPERIMENT_2USV_CONTRACT_PATH
    )
    with resolved_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _select_two_usv_start_positions(
    nav_map_prior: np.ndarray,
) -> list[tuple[int, int]]:
    h, w = nav_map_prior.shape
    launch_positions = [tuple(int(v) for v in pos) for pos in TWO_USV_FIXED_START_POSITIONS]
    for pos in launch_positions:
        if not (0 <= pos[0] < h and 0 <= pos[1] < w):
            raise ValueError(
                f"Fixed 2-USV launch position {pos} is outside map shape {(h, w)}"
            )
        if nav_map_prior[pos] != FREE:
            raise ValueError(
                f"Fixed 2-USV launch position {pos} is not FREE on the current map"
            )
    return launch_positions


def _build_responsibility_maps(
    nav_map_prior: np.ndarray,
    robot_positions: list[tuple[int, int]],
    *,
    sensor_range_cells: int,
    buffer_band_width_cells: int = RESPONSIBILITY_BUFFER_BAND_CELLS,
) -> dict[str, object]:
    if len(robot_positions) != 2:
        raise ValueError("Responsibility map construction currently expects exactly 2 USVs.")

    distance_maps: list[np.ndarray] = []
    for robot_pos in robot_positions:
        tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
        distance_maps.append(np.asarray(tree["distance_map"], dtype=float))

    d0 = np.asarray(distance_maps[0], dtype=float)
    d1 = np.asarray(distance_maps[1], dtype=float)
    h, w = nav_map_prior.shape
    responsibility_owner_map = np.full((h, w), -1, dtype=int)
    buffer_band_mask = np.zeros((h, w), dtype=bool)
    responsibility_score_map_0 = np.zeros((h, w), dtype=float)

    free_mask = nav_map_prior == FREE
    reachable_mask = free_mask & np.isfinite(d0) & np.isfinite(d1)
    if np.any(reachable_mask):
        diff = np.zeros((h, w), dtype=float)
        diff[reachable_mask] = d1[reachable_mask] - d0[reachable_mask]
        responsibility_owner_map[reachable_mask] = np.where(
            d0[reachable_mask] <= d1[reachable_mask],
            0,
            1,
        )
        buffer_band_mask[reachable_mask] = (
            np.abs(diff[reachable_mask]) <= float(buffer_band_width_cells)
        )
        scale = max(1.0, float(sensor_range_cells))
        responsibility_score_map_0[reachable_mask] = np.clip(
            diff[reachable_mask] / scale,
            -1.0,
            1.0,
        )
        responsibility_score_map_0[buffer_band_mask] = 0.0

    responsibility_score_map_1 = -np.asarray(responsibility_score_map_0, dtype=float)
    responsibility_score_map_1[buffer_band_mask] = 0.0
    responsibility_score_map_0[~reachable_mask] = 0.0
    responsibility_score_map_1[~reachable_mask] = 0.0

    return {
        "responsibility_owner_map": responsibility_owner_map,
        "responsibility_score_map": [
            responsibility_score_map_0,
            responsibility_score_map_1,
        ],
        "buffer_band_mask": buffer_band_mask,
        "responsibility_distance_maps": [d0, d1],
    }


def _responsibility_owner_for_cell(
    owner_map: np.ndarray | None,
    cell: tuple[int, int] | None,
) -> int | None:
    if owner_map is None or cell is None:
        return None
    cell_tuple = tuple(int(v) for v in cell)
    owner = int(owner_map[cell_tuple])
    return owner if owner >= 0 else None


def _mask_contains_cell(
    mask: np.ndarray | None,
    cell: tuple[int, int] | None,
) -> bool:
    if mask is None or cell is None:
        return False
    return bool(mask[tuple(int(v) for v in cell)])


def _responsibility_score_for_cell(
    score_map: np.ndarray | None,
    cell: tuple[int, int] | None,
) -> float:
    if score_map is None or cell is None:
        return 0.0
    return float(score_map[tuple(int(v) for v in cell)])


def _responsibility_score_visible_mean(
    score_map: np.ndarray | None,
    visible_cells: set[tuple[int, int]],
) -> float:
    if score_map is None or not visible_cells:
        return 0.0
    return float(
        np.mean([float(score_map[tuple(int(v) for v in cell)]) for cell in visible_cells])
    )


def _make_usv_local_state(usv_id: int, robot_pos: tuple[int, int]) -> dict[str, object]:
    return {
        "usv_id": int(usv_id),
        "robot_pos": tuple(int(v) for v in robot_pos),
        "trajectory": [tuple(int(v) for v in robot_pos)],
        "committed_viewpoint": None,
        "committed_anchor": None,
        "committed_anchor_centroid": None,
        "committed_segment": [tuple(int(v) for v in robot_pos)],
        "current_plan_details": {},
        "path_length": 0,
        "replan_count": 0,
        "switch_count": 0,
        "anchor_switch_count": 0,
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
        "last_move_dir": None,
        "commit_remaining": 0,
        "wait_count": 0,
    }


def _team_clue_field_from_state(state: dict) -> object:
    remaining = remove_found_targets(state["target_positions"], state["found_mask"])
    return make_target_induced_clue_field(
        state["true_map"],
        remaining,
        clue_sigma_cells=state["clue_sigma_cells"],
        clue_amplitude=state["clue_amplitude"],
    )


def _update_team_clue_truth_map(state: dict) -> None:
    state["clue_field_fn"] = _team_clue_field_from_state(state)
    state["clue_true_map"] = build_clue_field_map(state["clue_field_fn"], state["true_map"])


def _refresh_team_gp_state(
    state: dict,
    optimize_hyperparams: bool,
) -> None:
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


def _update_team_search_info_state(state: dict, intensity_map: np.ndarray) -> None:
    search_info_map, clue_component, intensity_component = _build_search_info_maps(
        state.get("gp_clue_planner_map", state.get("gp_acq_map")),
        intensity_map,
        state["nav_map_prior"],
        clue_weight=state["search_info_clue_weight"],
        intensity_weight=state["search_info_intensity_weight"],
    )
    state["search_info_map"] = search_info_map
    state["search_info_clue_component_map"] = clue_component
    state["search_info_intensity_component_map"] = intensity_component
    peak_value, mean_value = _search_info_stats(search_info_map, state["nav_map_prior"])
    state["search_info_map_peak"] = float(peak_value)
    state["search_info_map_mean"] = float(mean_value)


def _apply_team_miss_updates(
    intensity_map: np.ndarray,
    robot_positions: list[tuple[int, int]],
    sensor_range_cells: int,
    known_map: np.ndarray,
    target_total_mass: float,
) -> np.ndarray:
    updated = np.asarray(intensity_map, dtype=float)
    for robot_pos in robot_positions:
        updated = miss_update_intensity(
            updated,
            robot_pos,
            sensor_range_cells,
            known_map=known_map,
            preserve_total_mass=True,
            target_total_mass=target_total_mass,
        )
    return updated


def _sample_and_update_team_gp(
    state: dict,
    step: int,
    gp_fit_every: int,
) -> None:
    _update_team_clue_truth_map(state)
    x_batches: list[np.ndarray] = []
    y_batches: list[np.ndarray] = []
    for local in state["usv_states"]:
        x_new, y_new = sample_clue_field(
            state["clue_field_fn"],
            local["robot_pos"],
            state["sensor_range_cells"],
            state["observation_rng"],
            n_samples=state["clue_samples_per_step"],
            noise_std=state["clue_noise_std"],
            resolution=state["resolution_m"],
            map_shape=state["true_map"].shape,
        )
        if len(x_new) > 0:
            x_batches.append(x_new)
            y_batches.append(y_new)
    if x_batches:
        state["gp_field"].add_observations(
            np.concatenate(x_batches, axis=0),
            np.concatenate(y_batches, axis=0),
            t=float(step),
        )
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
    _refresh_team_gp_state(state, optimize_hyperparams=optimize_now)


def _observation_progress_for_robot(state: dict, robot_pos: tuple[int, int]) -> tuple[float, float]:
    visible_free = [
        cell
        for cell in sensor_cells(robot_pos, state["nav_map_prior"].shape, state["sensor_range_cells"])
        if state["nav_map_prior"][cell] == FREE
    ]
    total = len(visible_free)
    if total == 0:
        return 0.0, 0.0
    stale_refresh_count = 0
    newly_observed_count = 0
    for cell in visible_free:
        if state["last_seen_step"][cell] < 0:
            newly_observed_count += 1
        elif float(state["staleness_map"][cell]) >= 0.5:
            stale_refresh_count += 1
    effective_gain_ratio = float(newly_observed_count + stale_refresh_count) / float(total)
    stale_refresh_ratio = float(stale_refresh_count) / float(total)
    return effective_gain_ratio, stale_refresh_ratio


def _local_planner_terms(
    state: dict,
    local: dict,
) -> float:
    # Deprecated compatibility hook: per-USV kappa_commit is no longer allowed
    # to affect scoring or commit-window decisions.
    return 0.0


def _segment_visible_cells(
    segment_path: list[tuple[int, int]],
    nav_map_prior: np.ndarray,
    sensor_range: int,
) -> set[tuple[int, int]]:
    visible: set[tuple[int, int]] = set()
    for cell in segment_path:
        visible.update(_knownmap_visible_free_cells(cell, nav_map_prior, sensor_range))
    return visible


def _zero_assignment_details(
    robot_pos: tuple[int, int],
    *,
    kappa_commit: float,
) -> dict[str, object]:
    return {
        "viewpoint_cell": tuple(int(v) for v in robot_pos),
        "segment_endpoint_cell": tuple(int(v) for v in robot_pos),
        "anchor_cell": None,
        "anchor_source": None,
        "anchor_centroid_cell": None,
        "anchor_cluster_size": 0,
        "anchor_cluster_peak": 0.0,
        "anchor_cluster_mean": 0.0,
        "viewpoint_rule": "hold_position",
        "sampling_priority_raw": 0.0,
        "candidate_pool_size": 0,
        "reachable_pool_size": 0,
        "a_star_checked_pool_size": 0,
        "selected_viewpoint_rank": 0,
        "search_info_gain_raw": 0.0,
        "recency_bias_raw": 0.0,
        "exec_cost_raw": 0.0,
        "clearance_penalty_raw": 0.0,
        "reservation_soft_penalty_raw": 0.0,
        "reservation_same_cell_violation": False,
        "reservation_swap_violation": False,
        "reservation_near_neighbor_step_ratio": 0.0,
        "segment_min_clearance_cells": 0.0,
        "segment_mean_clearance_cells": 0.0,
        "near_obstacle_step_flag": False,
        "near_obstacle_step_ratio": 0.0,
        "segment_turn_count": 0,
        "path_safety_mode": "off",
        "safe_nav_lambda_clearance": 0.0,
        "team_reservation_lambda": 0.0,
        "search_info_gain_norm": 0.0,
        "recency_bias_norm": 0.0,
        "exec_cost_norm": 0.0,
        "alpha_focus": 0.0,
        "kappa_commit": 0.0,
        "same_anchor_cluster": False,
        "viewpoint_drift_norm": 0.0,
        "anchor_retention_bonus": 0.0,
        "viewpoint_retention_bonus": 0.0,
        "u_turn_penalty_term": 0.0,
        "u_turn_penalty_applied": False,
        "total_score": 0.0,
        "marginal_information_gain_raw": 0.0,
        "marginal_information_gain_norm": 0.0,
        "execution_cost_raw": 0.0,
        "execution_cost_norm": 0.0,
        "continuity_bonus_raw": 0.0,
        "continuity_bonus_anchor_raw": 0.0,
        "continuity_bonus_viewpoint_raw": 0.0,
        "marginal_information_gain_score_term": 0.0,
        "recency_bias_score_term": 0.0,
        "execution_cost_score_term": 0.0,
        "continuity_bonus_score_term": 0.0,
        "clue_acquisition_mode": "ucb",
        "anomaly_viewpoint_prob": 0.0,
        "anomaly_viewpoint_weight": 0.0,
        "anomaly_viewpoint_acq": 0.0,
        "anomaly_visible_mean": 0.0,
        "selected_in_anomaly_top_band": False,
        "maneuver_penalty_raw": 0.0,
        "maneuver_penalty_score_term": 0.0,
        "segment_path_length": 0,
        "planned_viewpoint_path_length": 0,
        "sampled_viewpoint_pool_cells": [],
        "responsibility_owner_robot": None,
        "responsibility_owner_viewpoint": None,
        "responsibility_score_viewpoint": 0.0,
        "responsibility_score_visible_mean": 0.0,
        "responsibility_regularizer_term": 0.0,
        "selected_in_buffer_band": False,
        "cross_region_selected": False,
        "team_path_avoidance_mode": "off",
        "reservation_priority_rank": -1,
        "fixed_viewpoint_reroute_applied": False,
    }


def _reservation_wait_plan_details(
    team_state: dict,
    robot_pos: tuple[int, int],
    *,
    kappa_commit: float,
    viewpoint_rule: str,
    fixed_viewpoint_reroute_applied: bool = False,
) -> dict[str, object]:
    details = _zero_assignment_details(
        robot_pos,
        kappa_commit=kappa_commit,
    )
    details.update(
        {
            "viewpoint_rule": str(viewpoint_rule),
            "path_safety_mode": str(team_state.get("path_safety_mode", "off")),
            "safe_nav_lambda_clearance": float(team_state.get("safe_nav_lambda_clearance", 0.0)),
            "team_path_avoidance_mode": str(team_state.get("team_path_avoidance_mode", "off")),
            "team_reservation_lambda": float(team_state.get("team_reservation_lambda", 0.0)),
            "fixed_viewpoint_reroute_applied": bool(fixed_viewpoint_reroute_applied),
        }
    )
    return details


def _plan_for_usv(
    *,
    team_state: dict,
    local: dict,
    predicted_intensity: np.ndarray,
    search_info_map: np.ndarray,
    policy_name: str,
    step: int,
    use_responsibility_prior: bool = True,
    reservation_table: dict[str, object] | None = None,
    fixed_viewpoint_cell: tuple[int, int] | None = None,
    fixed_viewpoint_details: dict[str, object] | None = None,
    fixed_viewpoint_reroute_applied: bool = False,
) -> tuple[list[tuple[int, int]], dict[str, object], set[tuple[int, int]]]:
    kappa_commit = _local_planner_terms(team_state, local)
    planner_search_info_map = (
        None if search_info_map is None else np.asarray(search_info_map, dtype=float)
    )
    responsibility_score_maps = team_state.get("responsibility_score_map")
    if (
        use_responsibility_prior
        and planner_search_info_map is not None
        and responsibility_score_maps is not None
    ):
        planner_search_info_map = planner_search_info_map * (
            1.0 + 0.25 * np.asarray(responsibility_score_maps[int(local["usv_id"])], dtype=float)
        )
        planner_search_info_map[team_state["nav_map_prior"] == OCCUPIED] = 0.0
    planner_kwargs = {
        "policy_name": policy_name,
        "nav_map_prior": team_state["nav_map_prior"],
        "robot_pos": local["robot_pos"],
        "sensor_range": team_state["sensor_range_cells"],
        "last_seen_step": team_state["last_seen_step"],
        "staleness_map": team_state["staleness_map"],
        "clue_map": team_state.get("gp_clue_planner_map", team_state["gp_acq_map"]),
        "intensity_map": predicted_intensity,
        "search_info_map": planner_search_info_map,
        "current_viewpoint": local["committed_viewpoint"],
        "current_anchor_source": local["last_anchor_source"],
        "current_anchor_centroid": local["committed_anchor_centroid"],
        "prev_move_dir": local["last_move_dir"],
        "kappa_commit": kappa_commit,
        "lambda_u_turn": team_state["lambda_u_turn"],
        "gamma": team_state["gamma"],
        "segment_horizon": team_state["segment_horizon"],
        "geometry_cache": team_state["knownmap_geometry_cache"],
        "path_safety_mode": team_state["path_safety_mode"],
        "inflated_nav_map": team_state.get("safe_nav_inflated_nav_map"),
        "obstacle_distance_map": team_state.get("safe_nav_obstacle_distance_map"),
        "clearance_cost_map": team_state.get("safe_nav_clearance_cost_map"),
        "safe_nav_lambda_clearance": team_state["safe_nav_lambda_clearance"],
        "safe_nav_inflation_radius_cells": team_state["safe_nav_inflation_radius_cells"],
        "safe_nav_soft_clearance_radius_cells": team_state[
            "safe_nav_soft_clearance_radius_cells"
        ],
        "reservation_table": reservation_table,
        "team_reservation_lambda": team_state.get("team_reservation_lambda", 1.0),
    }
    if fixed_viewpoint_cell is None:
        segment_path, plan_details = select_knownmap_path_segment_policy(
            search_info_clue_component=team_state["search_info_clue_component_map"],
            search_info_intensity_component=team_state["search_info_intensity_component_map"],
            current_anchor=local["committed_anchor"],
            current_segment_endpoint=(
                tuple(int(v) for v in local["committed_segment"][-1])
                if local["committed_segment"]
                else None
            ),
            top_k_anchors=team_state["top_k_anchors"],
            viewpoints_per_anchor=team_state["viewpoints_per_anchor"],
            sampling_seed_base=(
                int(team_state["episode_seed"]) * 1000003
                + int(step) * 9176
                + int(local["usv_id"]) * 31
            ),
            infosampled_inspected_limit_multiplier=team_state[
                "infosampled_inspected_limit_multiplier"
            ],
            infosampled_inspected_limit_floor=team_state["infosampled_inspected_limit_floor"],
            **planner_kwargs,
        )
    else:
        original_details = dict(fixed_viewpoint_details or {})
        segment_path, plan_details = rebuild_knownmap_segment_to_fixed_viewpoint(
            fixed_viewpoint_cell=tuple(int(v) for v in fixed_viewpoint_cell),
            anchor_cell=original_details.get("anchor_cell"),
            anchor_source=original_details.get("anchor_source"),
            anchor_centroid_cell=original_details.get("anchor_centroid_cell"),
            candidate_metadata={
                "candidate_pool_size": int(original_details.get("candidate_pool_size", 0)),
                "reachable_pool_size": int(original_details.get("reachable_pool_size", 0)),
                "a_star_checked_pool_size": int(
                    original_details.get("a_star_checked_pool_size", 0)
                ),
                "selected_viewpoint_rank": int(
                    original_details.get("selected_viewpoint_rank", 0)
                ),
                "sampling_priority_raw": float(
                    original_details.get("sampling_priority_raw", 0.0)
                ),
                "sampling_priority_norm": float(
                    original_details.get("sampling_priority_norm", 0.0)
                ),
                "viewpoint_sampling_mode": original_details.get("viewpoint_sampling_mode"),
                "sampled_viewpoint_pool_cells": list(
                    original_details.get("sampled_viewpoint_pool_cells", [])
                ),
            },
            viewpoint_rule="fixed_viewpoint_reroute",
            **planner_kwargs,
        )
    if segment_path is None:
        wait_segment = [tuple(int(v) for v in local["robot_pos"])]
        wait_rule = (
            "fixed_viewpoint_wait_fallback"
            if fixed_viewpoint_cell is not None
            else (
                "team_reservation_wait_fallback"
                if reservation_table is not None
                else "hold_position"
            )
        )
        wait_details = _reservation_wait_plan_details(
            team_state,
            tuple(int(v) for v in local["robot_pos"]),
            kappa_commit=kappa_commit,
            viewpoint_rule=wait_rule,
            fixed_viewpoint_reroute_applied=fixed_viewpoint_reroute_applied,
        )
        return wait_segment, wait_details, set()
    visible_cells = _segment_visible_cells(
        list(segment_path),
        team_state["nav_map_prior"],
        team_state["sensor_range_cells"],
    )
    details = _augment_plan_details_with_anomaly(
        state=team_state,
        plan_details=plan_details,
        segment_path=list(segment_path),
    )
    details["alpha_focus"] = 0.0
    details["kappa_commit"] = float(kappa_commit)
    details["team_path_avoidance_mode"] = str(team_state.get("team_path_avoidance_mode", "off"))
    details["fixed_viewpoint_reroute_applied"] = bool(fixed_viewpoint_reroute_applied)
    return list(segment_path), details, visible_cells


def _annotate_assignment_details(
    *,
    team_state: dict,
    local: dict,
    details: dict[str, object],
    visible_cells: set[tuple[int, int]],
    reservation_priority_rank: int,
    fixed_viewpoint_reroute_applied: bool,
    responsibility_regularizer_term: float,
) -> dict[str, object]:
    responsibility_owner_map = team_state.get("responsibility_owner_map")
    responsibility_score_maps = team_state.get("responsibility_score_map")
    buffer_band_mask = team_state.get("buffer_band_mask")
    usv_id = int(local["usv_id"])
    score_map = (
        np.asarray(responsibility_score_maps[usv_id], dtype=float)
        if responsibility_score_maps is not None
        else None
    )
    viewpoint_cell = details.get("viewpoint_cell")
    responsibility_owner_robot = _responsibility_owner_for_cell(
        responsibility_owner_map,
        local["robot_pos"],
    )
    responsibility_owner_viewpoint = _responsibility_owner_for_cell(
        responsibility_owner_map,
        viewpoint_cell,
    )
    selected_in_buffer_band = _mask_contains_cell(buffer_band_mask, viewpoint_cell)
    responsibility_score_viewpoint = _responsibility_score_for_cell(score_map, viewpoint_cell)
    responsibility_visible_mean = _responsibility_score_visible_mean(score_map, visible_cells)
    cross_region_selected = bool(
        responsibility_owner_viewpoint is not None
        and int(responsibility_owner_viewpoint) != int(usv_id)
        and not selected_in_buffer_band
    )
    annotated = dict(details)
    annotated.update(
        {
            "responsibility_owner_robot": responsibility_owner_robot,
            "responsibility_owner_viewpoint": responsibility_owner_viewpoint,
            "responsibility_score_viewpoint": float(responsibility_score_viewpoint),
            "responsibility_score_visible_mean": float(responsibility_visible_mean),
            "responsibility_regularizer_term": float(responsibility_regularizer_term),
            "selected_in_buffer_band": bool(selected_in_buffer_band),
            "cross_region_selected": bool(cross_region_selected),
            "team_path_avoidance_mode": str(
                team_state.get("team_path_avoidance_mode", "off")
            ),
            "reservation_priority_rank": int(reservation_priority_rank),
            "fixed_viewpoint_reroute_applied": bool(fixed_viewpoint_reroute_applied),
        }
    )
    return {
        "details": annotated,
        "responsibility_visible_mean": float(responsibility_visible_mean),
        "cross_region_selected": bool(cross_region_selected),
        "selected_in_buffer_band": bool(selected_in_buffer_band),
    }


def _joint_assign_two_usv_segments(
    *,
    team_state: dict,
    policy_name: str,
    predicted_intensity: np.ndarray,
    step: int,
    lambda_overlap: float = 1.5,
) -> tuple[dict[int, dict[str, object]], dict[str, object]]:
    best_assignment: dict[int, dict[str, object]] | None = None
    best_summary: dict[str, object] | None = None
    underlying_policy = _team_underlying_policy(policy_name)
    team_path_avoidance_mode = str(team_state.get("team_path_avoidance_mode", "off"))

    for ordering in ((0, 1), (1, 0)):
        residual_map = np.array(team_state["search_info_map"], copy=True)
        accumulated_visible: set[tuple[int, int]] = set()
        assignment: dict[int, dict[str, object]] = {}
        total_score = 0.0
        total_overlap_penalty = 0.0

        for order_rank, usv_id in enumerate(ordering):
            local = team_state["usv_states"][usv_id]
            reservation_table = None
            if team_path_avoidance_mode == "reservation_v1" and order_rank > 0:
                reservation_table = build_reservation_table(
                    assignment[ordering[0]]["segment_path"],
                    safety_distance_cells=float(
                        team_state.get("team_reservation_safety_distance_cells", 1.5)
                    ),
                )
            segment_path, details, visible_cells = _plan_for_usv(
                team_state=team_state,
                local=local,
                predicted_intensity=predicted_intensity,
                search_info_map=residual_map,
                policy_name=underlying_policy,
                step=step,
                reservation_table=reservation_table,
            )
            overlap_ratio = (
                float(len(visible_cells & accumulated_visible)) / float(max(1, len(visible_cells)))
                if visible_cells
                else 0.0
            )
            overlap_penalty = float(lambda_overlap) * float(overlap_ratio)
            responsibility_visible_mean = _responsibility_score_visible_mean(
                np.asarray(team_state["responsibility_score_map"][usv_id], dtype=float),
                visible_cells,
            )
            # Responsibility remains a local planner ranking bias only. Keep
            # the regularizer field for trace compatibility, but do not let it
            # affect team assignment scores.
            responsibility_regularizer = 0.0
            annotation = _annotate_assignment_details(
                team_state=team_state,
                local=local,
                details=details,
                visible_cells=visible_cells,
                reservation_priority_rank=order_rank,
                fixed_viewpoint_reroute_applied=False,
                responsibility_regularizer_term=responsibility_regularizer,
            )
            details = dict(annotation["details"])
            adjusted_score = float(details.get("total_score", 0.0)) - overlap_penalty
            for cell in visible_cells:
                residual_map[cell] = 0.0
            accumulated_visible.update(visible_cells)
            assignment[usv_id] = {
                "segment_path": segment_path,
                "plan_details": details,
                "visible_cells": visible_cells,
                "overlap_ratio": float(overlap_ratio),
                "overlap_penalty": float(overlap_penalty),
                "adjusted_total_score": float(adjusted_score),
                "responsibility_visible_mean": float(annotation["responsibility_visible_mean"]),
                "responsibility_regularizer": float(responsibility_regularizer),
                "cross_region_selected": bool(annotation["cross_region_selected"]),
                "selected_in_buffer_band": bool(annotation["selected_in_buffer_band"]),
                "order_rank": int(order_rank),
            }
            total_score += adjusted_score
            total_overlap_penalty += overlap_penalty

        same_viewpoint = (
            assignment[0]["plan_details"].get("viewpoint_cell")
            == assignment[1]["plan_details"].get("viewpoint_cell")
        )
        if same_viewpoint:
            total_score -= 2.0
            total_overlap_penalty += 2.0

        summary = {
            "joint_assignment_score": float(total_score),
            "joint_overlap_penalty": float(total_overlap_penalty),
            "assignment_order": tuple(int(v) for v in ordering),
            "assignment_mode": "coordinated",
            "same_viewpoint_selected": bool(same_viewpoint),
            "cross_region_selected_0": bool(assignment[0]["cross_region_selected"]),
            "cross_region_selected_1": bool(assignment[1]["cross_region_selected"]),
            "cross_region_count": int(
                int(bool(assignment[0]["cross_region_selected"]))
                + int(bool(assignment[1]["cross_region_selected"]))
            ),
            "responsibility_regularizer_0": float(assignment[0]["responsibility_regularizer"]),
            "responsibility_regularizer_1": float(assignment[1]["responsibility_regularizer"]),
            "team_path_avoidance_mode": team_path_avoidance_mode,
            "reservation_priority_order": (
                tuple(int(v) for v in ordering)
                if team_path_avoidance_mode == "reservation_v1"
                else None
            ),
            "reservation_wait_fallback_count": int(
                sum(
                    1
                    for item in assignment.values()
                    if item["plan_details"].get("viewpoint_rule")
                    in {"team_reservation_wait_fallback", "fixed_viewpoint_wait_fallback"}
                )
            ),
            "reservation_same_cell_violation_any": bool(
                any(
                    item["plan_details"].get("reservation_same_cell_violation", False)
                    for item in assignment.values()
                )
            ),
            "reservation_swap_violation_any": bool(
                any(
                    item["plan_details"].get("reservation_swap_violation", False)
                    for item in assignment.values()
                )
            ),
            "reservation_near_neighbor_step_ratio_team": float(
                np.mean(
                    [
                        float(
                            item["plan_details"].get(
                                "reservation_near_neighbor_step_ratio",
                                0.0,
                            )
                        )
                        for item in assignment.values()
                    ]
                )
            ),
        }
        if best_summary is None or float(summary["joint_assignment_score"]) > float(
            best_summary["joint_assignment_score"]
        ):
            best_assignment = assignment
            best_summary = summary

    assert best_assignment is not None
    assert best_summary is not None
    if team_path_avoidance_mode == "reservation_v1":
        priority_order = tuple(
            sorted(
                (0, 1),
                key=lambda usv_id: _priority_tuple(
                    team_state["usv_states"][usv_id],
                    float(best_assignment[usv_id]["adjusted_total_score"]),
                ),
                reverse=True,
            )
        )
        if tuple(int(v) for v in best_summary.get("assignment_order", ())) == tuple(
            int(v) for v in priority_order
        ):
            best_summary = {
                **best_summary,
                "reservation_priority_order": tuple(int(v) for v in priority_order),
            }
            return best_assignment, best_summary
        refined_assignment: dict[int, dict[str, object]] = {}
        residual_map = np.array(team_state["search_info_map"], copy=True)
        accumulated_visible: set[tuple[int, int]] = set()
        total_score = 0.0
        total_overlap_penalty = 0.0

        for priority_rank, usv_id in enumerate(priority_order):
            local = team_state["usv_states"][usv_id]
            base_item = best_assignment[usv_id]
            reservation_table = None
            if priority_rank > 0:
                lead_usv = priority_order[0]
                reservation_table = build_reservation_table(
                    refined_assignment[lead_usv]["segment_path"],
                    safety_distance_cells=float(
                        team_state.get("team_reservation_safety_distance_cells", 1.5)
                    ),
                )
            segment_path, details, visible_cells = _plan_for_usv(
                team_state=team_state,
                local=local,
                predicted_intensity=predicted_intensity,
                search_info_map=residual_map,
                policy_name=underlying_policy,
                step=step,
                reservation_table=reservation_table,
                fixed_viewpoint_cell=base_item["plan_details"].get("viewpoint_cell"),
                fixed_viewpoint_details=base_item["plan_details"],
                fixed_viewpoint_reroute_applied=False,
            )
            overlap_ratio = (
                float(len(visible_cells & accumulated_visible)) / float(max(1, len(visible_cells)))
                if visible_cells
                else 0.0
            )
            overlap_penalty = float(lambda_overlap) * float(overlap_ratio)
            responsibility_visible_mean = _responsibility_score_visible_mean(
                np.asarray(team_state["responsibility_score_map"][usv_id], dtype=float),
                visible_cells,
            )
            # Responsibility remains a local planner ranking bias only. Keep
            # the regularizer field for trace compatibility, but do not let it
            # affect team assignment scores.
            responsibility_regularizer = 0.0
            annotation = _annotate_assignment_details(
                team_state=team_state,
                local=local,
                details=details,
                visible_cells=visible_cells,
                reservation_priority_rank=priority_rank,
                fixed_viewpoint_reroute_applied=False,
                responsibility_regularizer_term=responsibility_regularizer,
            )
            details = dict(annotation["details"])
            adjusted_score = float(details.get("total_score", 0.0)) - overlap_penalty
            for cell in visible_cells:
                residual_map[cell] = 0.0
            accumulated_visible.update(visible_cells)
            refined_assignment[usv_id] = {
                "segment_path": segment_path,
                "plan_details": details,
                "visible_cells": visible_cells,
                "overlap_ratio": float(overlap_ratio),
                "overlap_penalty": float(overlap_penalty),
                "adjusted_total_score": float(adjusted_score),
                "responsibility_visible_mean": float(
                    annotation["responsibility_visible_mean"]
                ),
                "responsibility_regularizer": float(responsibility_regularizer),
                "cross_region_selected": bool(annotation["cross_region_selected"]),
                "selected_in_buffer_band": bool(annotation["selected_in_buffer_band"]),
                "order_rank": int(priority_rank),
            }
            total_score += adjusted_score
            total_overlap_penalty += overlap_penalty

        same_viewpoint = (
            refined_assignment[0]["plan_details"].get("viewpoint_cell")
            == refined_assignment[1]["plan_details"].get("viewpoint_cell")
        )
        if same_viewpoint:
            total_score -= 2.0
            total_overlap_penalty += 2.0
        best_assignment = refined_assignment
        best_summary = {
            **best_summary,
            "joint_assignment_score": float(total_score),
            "joint_overlap_penalty": float(total_overlap_penalty),
            "same_viewpoint_selected": bool(same_viewpoint),
            "cross_region_selected_0": bool(best_assignment[0]["cross_region_selected"]),
            "cross_region_selected_1": bool(best_assignment[1]["cross_region_selected"]),
            "cross_region_count": int(
                int(bool(best_assignment[0]["cross_region_selected"]))
                + int(bool(best_assignment[1]["cross_region_selected"]))
            ),
            "responsibility_regularizer_0": float(
                best_assignment[0]["responsibility_regularizer"]
            ),
            "responsibility_regularizer_1": float(
                best_assignment[1]["responsibility_regularizer"]
            ),
            "reservation_priority_order": tuple(int(v) for v in priority_order),
            "reservation_wait_fallback_count": int(
                sum(
                    1
                    for item in best_assignment.values()
                    if item["plan_details"].get("viewpoint_rule")
                    in {"team_reservation_wait_fallback", "fixed_viewpoint_wait_fallback"}
                )
            ),
            "reservation_same_cell_violation_any": bool(
                any(
                    item["plan_details"].get("reservation_same_cell_violation", False)
                    for item in best_assignment.values()
                )
            ),
            "reservation_swap_violation_any": bool(
                any(
                    item["plan_details"].get("reservation_swap_violation", False)
                    for item in best_assignment.values()
                )
            ),
            "reservation_near_neighbor_step_ratio_team": float(
                np.mean(
                    [
                        float(
                            item["plan_details"].get(
                                "reservation_near_neighbor_step_ratio",
                                0.0,
                            )
                        )
                        for item in best_assignment.values()
                    ]
                )
            ),
        }
    return best_assignment, best_summary


def _assign_two_usv_segments_independent(
    *,
    team_state: dict,
    policy_name: str,
    predicted_intensity: np.ndarray,
    step: int,
) -> tuple[dict[int, dict[str, object]], dict[str, object]]:
    underlying_policy = _team_underlying_policy(policy_name)
    base_search_info_map = np.asarray(team_state["search_info_map"], dtype=float)
    base_assignment: dict[int, dict[str, object]] = {}

    for usv_id in (0, 1):
        local = team_state["usv_states"][usv_id]
        segment_path, details, visible_cells = _plan_for_usv(
            team_state=team_state,
            local=local,
            predicted_intensity=predicted_intensity,
            search_info_map=base_search_info_map,
            policy_name=underlying_policy,
            step=step,
            use_responsibility_prior=False,
        )
        annotation = _annotate_assignment_details(
            team_state=team_state,
            local=local,
            details=details,
            visible_cells=visible_cells,
            reservation_priority_rank=-1,
            fixed_viewpoint_reroute_applied=False,
            responsibility_regularizer_term=0.0,
        )
        details = dict(annotation["details"])
        adjusted_score = float(details.get("total_score", 0.0))
        base_assignment[usv_id] = {
            "segment_path": segment_path,
            "plan_details": details,
            "visible_cells": visible_cells,
            "overlap_ratio": 0.0,
            "overlap_penalty": 0.0,
            "adjusted_total_score": adjusted_score,
            "responsibility_visible_mean": float(annotation["responsibility_visible_mean"]),
            "responsibility_regularizer": 0.0,
            "cross_region_selected": bool(annotation["cross_region_selected"]),
            "selected_in_buffer_band": bool(annotation["selected_in_buffer_band"]),
            "order_rank": int(usv_id),
        }

    assignment: dict[int, dict[str, object]] = {
        usv_id: {
            **item,
            "plan_details": dict(item["plan_details"]),
        }
        for usv_id, item in base_assignment.items()
    }
    team_path_avoidance_mode = str(team_state.get("team_path_avoidance_mode", "off"))
    reservation_priority_order = None
    if team_path_avoidance_mode == "reservation_v1":
        priority_order = tuple(
            sorted(
                (0, 1),
                key=lambda usv_id: _priority_tuple(
                    team_state["usv_states"][usv_id],
                    float(base_assignment[usv_id]["adjusted_total_score"]),
                ),
                reverse=True,
            )
        )
        reservation_priority_order = tuple(int(v) for v in priority_order)
        priority_lead = int(priority_order[0])
        priority_follow = int(priority_order[1])
        lead_local = team_state["usv_states"][priority_lead]
        lead_annotation = _annotate_assignment_details(
            team_state=team_state,
            local=lead_local,
            details=assignment[priority_lead]["plan_details"],
            visible_cells=assignment[priority_lead]["visible_cells"],
            reservation_priority_rank=0,
            fixed_viewpoint_reroute_applied=False,
            responsibility_regularizer_term=0.0,
        )
        assignment[priority_lead]["plan_details"] = dict(lead_annotation["details"])
        reservation_table = build_reservation_table(
            assignment[priority_lead]["segment_path"],
            safety_distance_cells=float(
                team_state.get("team_reservation_safety_distance_cells", 1.5)
            ),
        )
        follow_local = team_state["usv_states"][priority_follow]
        base_follow_diagnostics = evaluate_path_against_reservation(
            assignment[priority_follow]["segment_path"],
            reservation_table,
        )
        if (
            not base_follow_diagnostics["same_cell_violation"]
            and not base_follow_diagnostics["swap_violation"]
            and float(base_follow_diagnostics["reservation_soft_penalty_raw"]) <= 1e-12
            and float(base_follow_diagnostics["near_neighbor_step_ratio"]) <= 1e-12
        ):
            follow_details = dict(assignment[priority_follow]["plan_details"])
            follow_details.update(
                {
                    "reservation_soft_penalty_raw": float(
                        base_follow_diagnostics["reservation_soft_penalty_raw"]
                    ),
                    "reservation_same_cell_violation": bool(
                        base_follow_diagnostics["same_cell_violation"]
                    ),
                    "reservation_swap_violation": bool(
                        base_follow_diagnostics["swap_violation"]
                    ),
                    "reservation_near_neighbor_step_ratio": float(
                        base_follow_diagnostics["near_neighbor_step_ratio"]
                    ),
                }
            )
            follow_annotation = _annotate_assignment_details(
                team_state=team_state,
                local=follow_local,
                details=follow_details,
                visible_cells=assignment[priority_follow]["visible_cells"],
                reservation_priority_rank=1,
                fixed_viewpoint_reroute_applied=False,
                responsibility_regularizer_term=0.0,
            )
            assignment[priority_follow] = {
                **assignment[priority_follow],
                "plan_details": dict(follow_annotation["details"]),
                "responsibility_visible_mean": float(
                    follow_annotation["responsibility_visible_mean"]
                ),
                "cross_region_selected": bool(follow_annotation["cross_region_selected"]),
                "selected_in_buffer_band": bool(follow_annotation["selected_in_buffer_band"]),
                "order_rank": 1,
            }
        else:
            reroute_segment_path, reroute_details, reroute_visible_cells = _plan_for_usv(
                team_state=team_state,
                local=follow_local,
                predicted_intensity=predicted_intensity,
                search_info_map=base_search_info_map,
                policy_name=underlying_policy,
                step=step,
                use_responsibility_prior=False,
                reservation_table=reservation_table,
                fixed_viewpoint_cell=assignment[priority_follow]["plan_details"].get("viewpoint_cell"),
                fixed_viewpoint_details=assignment[priority_follow]["plan_details"],
                fixed_viewpoint_reroute_applied=True,
            )
            follow_annotation = _annotate_assignment_details(
                team_state=team_state,
                local=follow_local,
                details=reroute_details,
                visible_cells=reroute_visible_cells,
                reservation_priority_rank=1,
                fixed_viewpoint_reroute_applied=True,
                responsibility_regularizer_term=0.0,
            )
            assignment[priority_follow] = {
                "segment_path": reroute_segment_path,
                "plan_details": dict(follow_annotation["details"]),
                "visible_cells": reroute_visible_cells,
                "overlap_ratio": 0.0,
                "overlap_penalty": 0.0,
                "adjusted_total_score": float(reroute_details.get("total_score", 0.0)),
                "responsibility_visible_mean": float(
                    follow_annotation["responsibility_visible_mean"]
                ),
                "responsibility_regularizer": 0.0,
                "cross_region_selected": bool(follow_annotation["cross_region_selected"]),
                "selected_in_buffer_band": bool(follow_annotation["selected_in_buffer_band"]),
                "order_rank": 1,
            }

    total_score = sum(float(item["adjusted_total_score"]) for item in assignment.values())
    same_viewpoint = (
        assignment[0]["plan_details"].get("viewpoint_cell")
        == assignment[1]["plan_details"].get("viewpoint_cell")
    )
    summary = {
        "joint_assignment_score": float(total_score),
        "joint_overlap_penalty": 0.0,
        "assignment_order": None,
        "assignment_mode": "independent",
        "same_viewpoint_selected": bool(same_viewpoint),
        "cross_region_selected_0": bool(assignment[0]["cross_region_selected"]),
        "cross_region_selected_1": bool(assignment[1]["cross_region_selected"]),
        "cross_region_count": int(
            int(bool(assignment[0]["cross_region_selected"]))
            + int(bool(assignment[1]["cross_region_selected"]))
        ),
        "responsibility_regularizer_0": 0.0,
        "responsibility_regularizer_1": 0.0,
        "team_path_avoidance_mode": team_path_avoidance_mode,
        "reservation_priority_order": reservation_priority_order,
        "reservation_wait_fallback_count": int(
            sum(
                1
                for item in assignment.values()
                if item["plan_details"].get("viewpoint_rule")
                in {"team_reservation_wait_fallback", "fixed_viewpoint_wait_fallback"}
            )
        ),
        "reservation_same_cell_violation_any": bool(
            any(
                item["plan_details"].get("reservation_same_cell_violation", False)
                for item in assignment.values()
            )
        ),
        "reservation_swap_violation_any": bool(
            any(
                item["plan_details"].get("reservation_swap_violation", False)
                for item in assignment.values()
            )
        ),
        "reservation_near_neighbor_step_ratio_team": float(
            np.mean(
                [
                    float(
                        item["plan_details"].get(
                            "reservation_near_neighbor_step_ratio",
                            0.0,
                        )
                    )
                    for item in assignment.values()
                ]
            )
        ),
    }
    return assignment, summary


def _priority_tuple(local: dict, assigned_total_score: float) -> tuple[float, float, int]:
    return (
        float(local.get("commit_remaining", 0)),
        float(assigned_total_score),
        -int(local["usv_id"]),
    )


def _resolve_execution_conflict(
    team_state: dict,
    assignments: dict[int, dict[str, object]],
    safety_distance_cells: float = 1.5,
) -> tuple[dict[int, bool], str | None, float]:
    next_cells: dict[int, tuple[int, int]] = {}
    moving: dict[int, bool] = {}
    for usv_id, assignment in assignments.items():
        segment_path = assignment["segment_path"]
        local = team_state["usv_states"][usv_id]
        moving[usv_id] = len(segment_path) > 1
        next_cells[usv_id] = (
            tuple(int(v) for v in segment_path[1])
            if len(segment_path) > 1
            else tuple(int(v) for v in local["robot_pos"])
        )

    wait_applied = {0: False, 1: False}
    conflict_type: str | None = None
    conflict_penalty = 0.0

    if moving[0] and moving[1] and next_cells[0] == next_cells[1]:
        conflict_type = "same_cell"
    elif moving[0] and moving[1]:
        pos0 = tuple(int(v) for v in team_state["usv_states"][0]["robot_pos"])
        pos1 = tuple(int(v) for v in team_state["usv_states"][1]["robot_pos"])
        if next_cells[0] == pos1 and next_cells[1] == pos0:
            conflict_type = "swap"

    if conflict_type is None and moving[0] and moving[1]:
        dist = float(np.hypot(next_cells[0][0] - next_cells[1][0], next_cells[0][1] - next_cells[1][1]))
        if dist < float(safety_distance_cells):
            conflict_type = "near_neighbor"

    if conflict_type == "swap":
        wait_applied[0] = True
        wait_applied[1] = True
        conflict_penalty = 2.0
        return wait_applied, conflict_type, float(conflict_penalty)

    if conflict_type in {"same_cell", "near_neighbor"}:
        priority0 = _priority_tuple(team_state["usv_states"][0], float(assignments[0]["adjusted_total_score"]))
        priority1 = _priority_tuple(team_state["usv_states"][1], float(assignments[1]["adjusted_total_score"]))
        losing_usv = 1 if priority0 >= priority1 else 0
        wait_applied[losing_usv] = True
        conflict_penalty = 1.0
    return wait_applied, conflict_type, float(conflict_penalty)


def _apply_joint_assignment_to_locals(
    team_state: dict,
    policy_name: str,
    assignments: dict[int, dict[str, object]],
    *,
    search_commit_window: int,
    search_commit_max_window: int,
    search_commit_path_divisor: int,
) -> None:
    underlying_policy = _team_underlying_policy(policy_name)
    for usv_id, assignment in assignments.items():
        local = team_state["usv_states"][usv_id]
        details = dict(assignment["plan_details"])
        segment_path = list(assignment["segment_path"])
        previous_viewpoint = local["committed_viewpoint"]
        previous_anchor_source = local["last_anchor_source"]
        previous_anchor_centroid = local["committed_anchor_centroid"]

        planned_segment_length = max(len(segment_path) - 1, 0)
        commit_remaining, commit_policy = _policy_commit_window(
            policy_name=underlying_policy,
            planned_segment_length=planned_segment_length,
            search_commit_window=search_commit_window,
            search_commit_max_window=search_commit_max_window,
            search_commit_path_divisor=search_commit_path_divisor,
            kappa_commit=float(details.get("kappa_commit", 0.0)),
        )
        if previous_viewpoint is not None and details.get("viewpoint_cell") != previous_viewpoint:
            local["switch_count"] += 1

        segment_flip_flag = (
            1.0
            if previous_viewpoint is not None and details.get("viewpoint_cell") != previous_viewpoint
            else 0.0
        )
        _append_trimmed(local["recent_segment_flips"], segment_flip_flag, max_len=6)
        _append_trimmed(
            local["recent_viewpoint_drifts"],
            float(details.get("viewpoint_drift_norm", 0.0)),
            max_len=6,
        )
        same_anchor_cluster_now = _same_anchor_cluster_state(
            previous_anchor_source,
            previous_anchor_centroid,
            details.get("anchor_source"),
            details.get("anchor_centroid_cell"),
            team_state["sensor_range_cells"],
        )
        if (
            previous_anchor_centroid is not None
            and details.get("anchor_centroid_cell") is not None
            and not same_anchor_cluster_now
        ):
            local["anchor_switch_count"] += 1
        if _semantic_anchor_source(details.get("anchor_source")):
            local["same_anchor_steps"] = local["same_anchor_steps"] + 1 if same_anchor_cluster_now else 1
        else:
            local["same_anchor_steps"] = 0

        local["replan_count"] += 1
        local["committed_viewpoint"] = details.get("viewpoint_cell")
        local["committed_anchor"] = details.get("anchor_cell")
        local["committed_anchor_centroid"] = details.get("anchor_centroid_cell")
        local["committed_segment"] = segment_path
        local["current_plan_details"] = details
        local["last_planned_segment_length"] = planned_segment_length
        local["last_planned_commit_window"] = int(commit_remaining)
        local["last_commit_policy"] = commit_policy
        local["last_anchor_source"] = details.get("anchor_source")
        local["steps_since_replan"] = 0
        local["commit_remaining"] = int(commit_remaining)
        assignment["planned_commit_window"] = int(commit_remaining)
        assignment["commit_policy"] = commit_policy


def _update_local_after_execution(
    local: dict,
    wait_applied: bool,
    exec_result,
) -> None:
    invalidation_flag = 0.0
    if wait_applied:
        local["wait_count"] += 1
        local["commit_remaining"] = max(int(local["commit_remaining"]) - 1, 0)
        local["steps_since_replan"] += 1
        local["last_move_dir"] = None
    elif exec_result is not None and exec_result.move_success:
        prev_pos = tuple(int(v) for v in local["robot_pos"])
        local["robot_pos"] = tuple(int(v) for v in exec_result.new_robot_pos)
        local["committed_segment"] = list(local["committed_segment"][1:])
        local["path_length"] += 1
        local["trajectory"].append(local["robot_pos"])
        local["steps_since_replan"] += 1
        local["commit_remaining"] = max(int(local["commit_remaining"]) - 1, 0)
        local["last_move_dir"] = move_direction(prev_pos, local["robot_pos"])
        if _semantic_anchor_source(local["last_anchor_source"]):
            local["same_anchor_steps"] += 1
        else:
            local["same_anchor_steps"] = 0
    elif len(local["committed_segment"]) > 1:
        local["committed_segment"] = [tuple(int(v) for v in local["robot_pos"])]
        local["commit_remaining"] = 0
        invalidation_flag = 1.0
    _append_trimmed(local["recent_path_invalidations"], invalidation_flag, max_len=6)


def _local_trace_row(
    *,
    team_step: int,
    usv_id: int,
    local: dict,
    clue_acquisition_mode: str,
    responsibility_owner_map: np.ndarray | None,
    assignment: dict[str, object],
    wait_applied: bool,
    conflict_type: str | None,
    conflict_penalty: float,
    detected_count_this_step: int,
    effective_observation_gain: float,
    stale_refresh_ratio: float,
    joint_assignment_score: float,
) -> dict[str, object]:
    details = assignment["plan_details"]
    robot_cell = tuple(int(v) for v in local["robot_pos"])
    return {
        "team_step": int(team_step),
        "usv_id": int(usv_id),
        "clue_acquisition_mode": str(clue_acquisition_mode),
        "anomaly_conditional_alpha": float(details.get("anomaly_conditional_alpha", 0.0)),
        "anomaly_conditional_triggered": bool(
            details.get("anomaly_conditional_triggered", False)
        ),
        "anomaly_gate_reason": str(details.get("anomaly_gate_reason", "mode_not_conditional")),
        "anomaly_top_mass_ratio": float(details.get("anomaly_top_mass_ratio", 0.0)),
        "anomaly_entropy_norm": float(details.get("anomaly_entropy_norm", 0.0)),
        "anomaly_hotspot_stability": float(details.get("anomaly_hotspot_stability", 1.0)),
        "anomaly_pre_first_alpha_capped": bool(
            details.get("anomaly_pre_first_alpha_capped", False)
        ),
        "robot_cell": robot_cell,
        "viewpoint_cell": details.get("viewpoint_cell"),
        "viewpoint_rule": details.get("viewpoint_rule"),
        "segment_endpoint_cell": details.get("segment_endpoint_cell"),
        "anchor_cell": details.get("anchor_cell"),
        "anchor_source": details.get("anchor_source"),
        "replanned_this_step": True,
        "replan_reason": "joint_assignment",
        "planned_commit_window": int(assignment.get("planned_commit_window", 0)),
        "commit_remaining": int(local.get("commit_remaining", 0)),
        "segment_path_length": int(max(len(assignment["segment_path"]) - 1, 0)),
        "search_info_gain_raw": float(details.get("search_info_gain_raw", 0.0)),
        "recency_bias_raw": float(details.get("recency_bias_raw", 0.0)),
        "exec_cost_raw": float(details.get("exec_cost_raw", 0.0)),
        "marginal_information_gain_raw": float(details.get("marginal_information_gain_raw", 0.0)),
        "execution_cost_raw": float(details.get("execution_cost_raw", 0.0)),
        "continuity_bonus_raw": float(details.get("continuity_bonus_raw", 0.0)),
        "total_score": float(details.get("total_score", 0.0)),
        "joint_assignment_score": float(joint_assignment_score),
        "overlap_penalty": float(assignment.get("overlap_penalty", 0.0)),
        "overlap_ratio": float(assignment.get("overlap_ratio", 0.0)),
        "conflict_penalty": float(conflict_penalty),
        "wait_applied": bool(wait_applied),
        "conflict_type": conflict_type,
        "detected_count_this_step": int(detected_count_this_step),
        "same_anchor_cluster": bool(details.get("same_anchor_cluster", False)),
        "viewpoint_drift_norm": float(details.get("viewpoint_drift_norm", 0.0)),
        "anchor_retention_bonus": float(details.get("anchor_retention_bonus", 0.0)),
        "viewpoint_retention_bonus": float(details.get("viewpoint_retention_bonus", 0.0)),
        "sampling_priority_raw": float(details.get("sampling_priority_raw", 0.0)),
        "path_safety_mode": str(details.get("path_safety_mode", "off")),
        "team_path_avoidance_mode": str(details.get("team_path_avoidance_mode", "off")),
        "reservation_priority_rank": int(details.get("reservation_priority_rank", -1)),
        "fixed_viewpoint_reroute_applied": bool(
            details.get("fixed_viewpoint_reroute_applied", False)
        ),
        "reservation_soft_penalty_raw": float(
            details.get("reservation_soft_penalty_raw", 0.0)
        ),
        "reservation_near_neighbor_step_ratio": float(
            details.get("reservation_near_neighbor_step_ratio", 0.0)
        ),
        "reservation_same_cell_violation": bool(
            details.get("reservation_same_cell_violation", False)
        ),
        "reservation_swap_violation": bool(
            details.get("reservation_swap_violation", False)
        ),
        "anomaly_viewpoint_prob": float(details.get("anomaly_viewpoint_prob", 0.0)),
        "anomaly_viewpoint_weight": float(details.get("anomaly_viewpoint_weight", 0.0)),
        "anomaly_viewpoint_acq": float(details.get("anomaly_viewpoint_acq", 0.0)),
        "anomaly_visible_mean": float(details.get("anomaly_visible_mean", 0.0)),
        "selected_in_anomaly_top_band": bool(
            details.get("selected_in_anomaly_top_band", False)
        ),
        "responsibility_owner_robot": _responsibility_owner_for_cell(
            responsibility_owner_map,
            robot_cell,
        ),
        "responsibility_owner_viewpoint": details.get("responsibility_owner_viewpoint"),
        "responsibility_score_viewpoint": float(details.get("responsibility_score_viewpoint", 0.0)),
        "responsibility_score_visible_mean": float(
            details.get("responsibility_score_visible_mean", 0.0)
        ),
        "responsibility_regularizer_term": float(
            details.get("responsibility_regularizer_term", 0.0)
        ),
        "selected_in_buffer_band": bool(details.get("selected_in_buffer_band", False)),
        "cross_region_selected": bool(details.get("cross_region_selected", False)),
        "effective_observation_gain": float(effective_observation_gain),
        "stale_refresh_ratio": float(stale_refresh_ratio),
    }


def _team_trace_row(
    *,
    team_step: int,
    assignments: dict[int, dict[str, object]],
    joint_summary: dict[str, object],
    conflict_type: str | None,
    conflict_penalty: float,
    wait_applied_map: dict[int, bool],
    team_detected_count: int,
) -> dict[str, object]:
    assignment_order = joint_summary.get("assignment_order")
    return {
        "team_step": int(team_step),
        "clue_acquisition_mode": str(joint_summary.get("clue_acquisition_mode", "ucb")),
        "anomaly_conditional_alpha": float(
            joint_summary.get("anomaly_conditional_alpha", 0.0)
        ),
        "anomaly_conditional_triggered": bool(
            joint_summary.get("anomaly_conditional_triggered", False)
        ),
        "anomaly_gate_reason": str(
            joint_summary.get("anomaly_gate_reason", "mode_not_conditional")
        ),
        "anomaly_top_mass_ratio": float(joint_summary.get("anomaly_top_mass_ratio", 0.0)),
        "anomaly_entropy_norm": float(joint_summary.get("anomaly_entropy_norm", 0.0)),
        "anomaly_hotspot_stability": float(
            joint_summary.get("anomaly_hotspot_stability", 1.0)
        ),
        "anomaly_pre_first_alpha_capped": bool(
            joint_summary.get("anomaly_pre_first_alpha_capped", False)
        ),
        "assignment_mode": str(joint_summary.get("assignment_mode", "coordinated")),
        "joint_assignment_score": float(joint_summary["joint_assignment_score"]),
        "joint_overlap_penalty": float(joint_summary["joint_overlap_penalty"]),
        "assignment_order": (
            None
            if assignment_order is None
            else tuple(int(v) for v in assignment_order)
        ),
        "same_viewpoint_selected": bool(joint_summary["same_viewpoint_selected"]),
        "selected_viewpoint_0": assignments[0]["plan_details"].get("viewpoint_cell"),
        "selected_viewpoint_1": assignments[1]["plan_details"].get("viewpoint_cell"),
        "cross_region_selected_0": bool(joint_summary.get("cross_region_selected_0", False)),
        "cross_region_selected_1": bool(joint_summary.get("cross_region_selected_1", False)),
        "cross_region_count": int(joint_summary.get("cross_region_count", 0)),
        "responsibility_regularizer_0": float(
            joint_summary.get("responsibility_regularizer_0", 0.0)
        ),
        "responsibility_regularizer_1": float(
            joint_summary.get("responsibility_regularizer_1", 0.0)
        ),
        "team_path_avoidance_mode": str(
            joint_summary.get("team_path_avoidance_mode", "off")
        ),
        "reservation_priority_order": joint_summary.get("reservation_priority_order"),
        "reservation_wait_fallback_count": int(
            joint_summary.get("reservation_wait_fallback_count", 0)
        ),
        "reservation_same_cell_violation_any": bool(
            joint_summary.get("reservation_same_cell_violation_any", False)
        ),
        "reservation_swap_violation_any": bool(
            joint_summary.get("reservation_swap_violation_any", False)
        ),
        "reservation_near_neighbor_step_ratio_team": float(
            joint_summary.get("reservation_near_neighbor_step_ratio_team", 0.0)
        ),
        "wait_applied_any": bool(wait_applied_map[0] or wait_applied_map[1]),
        "wait_applied_0": bool(wait_applied_map[0]),
        "wait_applied_1": bool(wait_applied_map[1]),
        "conflict_type": conflict_type,
        "conflict_penalty": float(conflict_penalty),
        "team_detected_count_this_step": int(team_detected_count),
    }


def _init_two_usv_knownmap_state(
    episode_seed: int,
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
    map_height_cells: int = 60,
    map_width_cells: int = 80,
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
    path_safety_mode: str = "off",
    safe_nav_inflation_radius_cells: int = 0,
    safe_nav_soft_clearance_radius_cells: int = 1,
    safe_nav_lambda_clearance: float = 1.0,
    team_path_avoidance_mode: str = "off",
    team_reservation_safety_distance_cells: float = 1.5,
    team_reservation_lambda: float = 1.0,
    constraint_mode: str = "hard",
    r_hit: int = 1,
    clue_samples_per_step: int | None = None,
) -> dict:
    if target_motion_mode not in {"static", "random_walk"}:
        raise ValueError(f"Unsupported target_motion_mode='{target_motion_mode}'")
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
    if team_path_avoidance_mode not in SUPPORTED_TEAM_PATH_AVOIDANCE_MODES:
        raise ValueError(
            "team_path_avoidance_mode must be one of "
            f"{SUPPORTED_TEAM_PATH_AVOIDANCE_MODES}, got '{team_path_avoidance_mode}'"
        )

    rngs = _spawn_rngs(episode_seed)
    true_map = create_world(
        h=int(map_height_cells),
        w=int(map_width_cells),
        map_kind=map_kind,
    )
    nav_map_prior = np.array(true_map, copy=True)
    robot_positions = _select_two_usv_start_positions(nav_map_prior)
    sensor_range_cells = _sensor_range_cells(sensor_range_m, resolution_m)
    min_target_separation_cells = _distance_cells(min_target_separation_m, resolution_m)
    min_start_distance_cells = _distance_cells(min_start_distance_m, resolution_m)
    clue_sigma_cells = _distance_cells(clue_sigma_m, resolution_m)
    responsibility_maps = _build_responsibility_maps(
        nav_map_prior,
        robot_positions,
        sensor_range_cells=sensor_range_cells,
    )

    target_positions, target_ids, placement_info = sample_targets(
        true_map,
        n_targets=n_targets,
        rng=rngs["scenario_rng"],
        start_pos=robot_positions,
        min_target_separation_cells=min_target_separation_cells,
        min_start_distance_cells=min_start_distance_cells,
        constraint_mode=constraint_mode,
    )
    found_mask = np.zeros(n_targets, dtype=bool)
    find_times: list[int | None] = [None] * n_targets
    last_seen_step = init_last_seen(nav_map_prior)
    for robot_pos in robot_positions:
        refresh_last_seen(last_seen_step, nav_map_prior, robot_pos, sensor_range_cells, step=0)

    team_detected_mask = np.zeros_like(found_mask, dtype=bool)
    for robot_pos in robot_positions:
        detected_mask = detect_targets(
            robot_pos,
            target_positions,
            found_mask,
            sensor_range_cells,
            rngs["detection_rng"],
        )
        team_detected_mask |= detected_mask
    initial_found_indices = update_found_mask(found_mask, team_detected_mask, find_times, step=0)

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
        "episode_seed": int(episode_seed),
        "true_map": true_map,
        "nav_map_prior": nav_map_prior,
        "knownmap_geometry_cache": _knownmap_precompute_viewpoint_geometry_cache(
            nav_map_prior,
            sensor_range_cells,
        ),
        "responsibility_owner_map": responsibility_maps["responsibility_owner_map"],
        "responsibility_score_map": responsibility_maps["responsibility_score_map"],
        "buffer_band_mask": responsibility_maps["buffer_band_mask"],
        "responsibility_distance_maps": responsibility_maps["responsibility_distance_maps"],
        "path_safety_mode": str(path_safety_mode),
        "safe_nav_inflation_radius_cells": int(safe_nav_inflation_radius_cells),
        "safe_nav_soft_clearance_radius_cells": int(safe_nav_soft_clearance_radius_cells),
        "safe_nav_lambda_clearance": float(safe_nav_lambda_clearance),
        "safe_nav_obstacle_distance_map": obstacle_distance_map,
        "safe_nav_inflated_nav_map": inflated_nav_map,
        "safe_nav_clearance_cost_map": clearance_cost_map,
        "team_path_avoidance_mode": str(team_path_avoidance_mode),
        "team_reservation_safety_distance_cells": float(team_reservation_safety_distance_cells),
        "team_reservation_lambda": float(team_reservation_lambda),
        "usv_states": [_make_usv_local_state(idx, robot_pos) for idx, robot_pos in enumerate(robot_positions)],
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
        "resolution_m": float(resolution_m),
        "map_kind": map_kind,
        "map_height_cells": int(h),
        "map_width_cells": int(w),
        "sensor_range_m": float(sensor_range_m),
        "sensor_range_cells": sensor_range_cells,
        "constraint_mode": placement_info["constraint_mode"],
        "placement_status": placement_info["placement_status"],
        "actual_min_target_separation_cells": placement_info["actual_min_target_separation_cells"],
        "actual_min_start_distance_cells": placement_info["actual_min_start_distance_cells"],
        "gp_beta": float(gp_beta),
        "gp_optimize_hyperparams": bool(gp_optimize_hyperparams),
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
        "gp_max_points": None,
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
        "team_trace_rows": [],
        "trace_rows": [],
        "anomaly_target_neighborhood_mass_ratio_rows": [],
        "target_motion_mode": target_motion_mode,
        "target_count_upper_bound": int(target_count_upper_bound),
        "staleness_tau_steps": int(staleness_tau_steps),
        "time_since_last_detection": 0 if initial_found_indices else 20,
        "r_hit": int(r_hit),
        "clue_samples_per_step": clue_samples_per_step,
        "clue_sigma_cells": float(clue_sigma_cells),
        "clue_amplitude": float(clue_amplitude),
        "clue_noise_std": float(clue_noise_std),
        "search_info_clue_weight": float(search_info_clue_weight),
        "search_info_intensity_weight": float(search_info_intensity_weight),
        "terminated_reason": "max_iters",
        "completed_steps": 0,
        "current_step": 0,
        "known_free_observation_ratio_curve": [
            known_free_observation_ratio(last_seen_step, nav_map_prior)
        ],
    }

    state["intensity_map"] = init_intensity_map(nav_map_prior, total_mass=float(found_mask.size))
    state["intensity_map"] = _apply_team_miss_updates(
        state["intensity_map"],
        [local["robot_pos"] for local in state["usv_states"]],
        state["sensor_range_cells"],
        known_map=state["nav_map_prior"],
        target_total_mass=_remaining_target_intensity_mass(state),
    )
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

    state["remaining_intensity_mass_curve"] = [remaining_intensity_mass(state["intensity_map"])]
    state["peak_intensity_ratio_curve"] = [
        peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
    ]

    _sample_and_update_team_gp(state, step=0, gp_fit_every=1)
    _update_team_search_info_state(state, state["intensity_map"])
    _append_anomaly_target_neighborhood_metric(state, step=0)
    state["clue_heatmap_limits"] = _fixed_clue_heatmap_limits(state)
    return state


def _placement_infeasible_two_usv_result(
    episode_seed: int,
    policy_name: str,
    assignment_mode: str,
    n_targets: int,
    constraint_mode: str,
    map_kind: str,
    map_height_cells: int,
    map_width_cells: int,
    clue_acquisition_mode: str = "ucb",
    anomaly_tail_quantile: float = 0.90,
    anomaly_weight_lambda: float = 1.0,
    path_safety_mode: str = "off",
    team_path_avoidance_mode: str = "off",
) -> dict[str, object]:
    return {
        "episode_seed": int(episode_seed),
        "policy_name": policy_name,
        "assignment_mode": str(assignment_mode),
        "clue_acquisition_mode": str(clue_acquisition_mode),
        "path_safety_mode": str(path_safety_mode),
        "team_path_avoidance_mode": str(team_path_avoidance_mode),
        "safe_nav_inflation_radius_cells": 0,
        "safe_nav_soft_clearance_radius_cells": 1,
        "safe_nav_lambda_clearance": 1.0,
        "team_reservation_safety_distance_cells": 1.5,
        "team_reservation_lambda": 1.0,
        "anomaly_tail_quantile": float(anomaly_tail_quantile),
        "anomaly_weight_lambda": float(anomaly_weight_lambda),
        "anomaly_conditional_alpha_final": 0.0,
        "anomaly_conditional_triggered_final": False,
        "anomaly_gate_reason_final": "placement_infeasible",
        "anomaly_conditional_alpha_mean": 0.0,
        "anomaly_conditional_trigger_rate": 0.0,
        "anomaly_gate_reason_counts": {},
        "map_prior_mode": "known_static",
        "n_usvs": 2,
        "success_all_found": False,
        "found_count": 0,
        "miss_count": int(n_targets),
        "detection_rate": 0.0,
        "find_times": [None] * int(n_targets),
        "time_to_first_detection": None,
        "time_to_all_found": None,
        "time_to_next_detection": None,
        "completed_steps": 0,
        "map_kind": map_kind,
        "map_height_cells": int(map_height_cells),
        "map_width_cells": int(map_width_cells),
        "constraint_mode": constraint_mode,
        "placement_status": "infeasible",
        "terminated_reason": "placement_infeasible",
        "team_trace_rows": [],
        "trace_rows": [],
        "planning_time_ms": [],
        "planning_time_ms_mean": 0.0,
        "known_free_observation_ratio_final": 0.0,
        "conflict_intervention_count": 0,
        "duplicate_viewpoint_ratio": 0.0,
        "cross_region_assignment_ratio": 0.0,
        "reservation_wait_fallback_count": 0,
        "reservation_near_neighbor_step_ratio_mean": 0.0,
        "reservation_same_cell_violation_count": 0,
        "reservation_swap_violation_count": 0,
        "anomaly_top_band_selection_ratio_pre_first_detection": 0.0,
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": 0.0,
        "wait_count_total": 0,
        "wait_count_by_usv": [0, 0],
    }


def _summarize_two_usv_result(state: dict, policy_name: str) -> dict[str, object]:
    summary = summarize_detection_times(state["find_times"])
    found_count = int(summary["found_count"])
    miss_count = int(summary["miss_count"])
    planning_time_ms = [float(value) for value in state["planning_time_ms"]]
    team_trace_rows = list(state["team_trace_rows"])
    trace_rows = list(state["trace_rows"])
    duplicate_viewpoint_ratio = _mean_or_default(
        [1.0 if row.get("same_viewpoint_selected") else 0.0 for row in team_trace_rows]
    )
    conflict_intervention_count = int(
        sum(1 for row in team_trace_rows if row.get("conflict_type") is not None)
    )
    path_length_by_usv = [int(local["path_length"]) for local in state["usv_states"]]
    wait_count_by_usv = [int(local.get("wait_count", 0)) for local in state["usv_states"]]
    cross_region_assignment_ratio = _mean_or_default(
        [1.0 if row.get("cross_region_selected") else 0.0 for row in trace_rows]
    )
    reservation_wait_fallback_count = int(
        sum(int(row.get("reservation_wait_fallback_count", 0)) for row in team_trace_rows)
    )
    reservation_near_neighbor_step_ratio_mean = _mean_or_default(
        [
            float(row.get("reservation_near_neighbor_step_ratio", 0.0))
            for row in trace_rows
        ]
    )
    reservation_same_cell_violation_count = int(
        sum(1 for row in trace_rows if row.get("reservation_same_cell_violation"))
    )
    reservation_swap_violation_count = int(
        sum(1 for row in trace_rows if row.get("reservation_swap_violation"))
    )
    anomaly_conditional_alpha_mean = _mean_or_default(
        [float(row.get("anomaly_conditional_alpha", 0.0)) for row in team_trace_rows]
    )
    anomaly_conditional_trigger_rate = _mean_or_default(
        [1.0 if row.get("anomaly_conditional_triggered") else 0.0 for row in team_trace_rows]
    )
    pre_first_trace_rows = _pre_first_detection_trace_rows(
        trace_rows,
        step_key="team_step",
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
    return {
        "episode_seed": int(state["episode_seed"]),
        "policy_name": policy_name,
        "assignment_mode": str(state.get("assignment_mode", "coordinated")),
        "planner_adaptation_mode": str(state.get("planner_adaptation_mode", "adaptive")),
        "clue_acquisition_mode": str(state.get("clue_acquisition_mode", "ucb")),
        "path_safety_mode": str(state.get("path_safety_mode", "off")),
        "team_path_avoidance_mode": str(state.get("team_path_avoidance_mode", "off")),
        "safe_nav_inflation_radius_cells": int(state.get("safe_nav_inflation_radius_cells", 0)),
        "safe_nav_soft_clearance_radius_cells": int(
            state.get("safe_nav_soft_clearance_radius_cells", 0)
        ),
        "safe_nav_lambda_clearance": float(state.get("safe_nav_lambda_clearance", 0.0)),
        "team_reservation_safety_distance_cells": float(
            state.get("team_reservation_safety_distance_cells", 1.5)
        ),
        "team_reservation_lambda": float(state.get("team_reservation_lambda", 0.0)),
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
        "anomaly_conditional_alpha_mean": float(anomaly_conditional_alpha_mean),
        "anomaly_conditional_trigger_rate": float(anomaly_conditional_trigger_rate),
        "anomaly_gate_reason_counts": _label_counts(team_trace_rows, "anomaly_gate_reason"),
        "map_prior_mode": "known_static",
        "n_usvs": 2,
        "success_all_found": miss_count == 0,
        "found_count": found_count,
        "miss_count": miss_count,
        "detection_rate": float(found_count) / float(len(state["target_ids"])) if len(state["target_ids"]) > 0 else 0.0,
        "find_times": list(state["find_times"]),
        "time_to_first_detection": summary["time_to_first_detection"],
        "time_to_all_found": summary["time_to_all_found"],
        "time_to_next_detection": (
            None
            if sum(step is not None for step in state["find_times"]) <= 1
            else float(
                np.mean(
                    np.diff(
                        np.asarray(
                            sorted(int(step) for step in state["find_times"] if step is not None),
                            dtype=float,
                        )
                    )
                )
            )
        ),
        "completed_steps": int(state["completed_steps"]),
        "terminated_reason": state["terminated_reason"],
        "map_kind": state["map_kind"],
        "map_height_cells": int(state["map_height_cells"]),
        "map_width_cells": int(state["map_width_cells"]),
        "constraint_mode": state["constraint_mode"],
        "placement_status": state["placement_status"],
        "path_length_total": int(sum(path_length_by_usv)),
        "path_length_by_usv": path_length_by_usv,
        "robot_positions_final": [tuple(int(v) for v in local["robot_pos"]) for local in state["usv_states"]],
        "robot_start_positions": [tuple(int(v) for v in local["trajectory"][0]) for local in state["usv_states"]],
        "planning_time_ms": planning_time_ms,
        "planning_time_ms_mean": float(np.mean(planning_time_ms)) if planning_time_ms else 0.0,
        "known_free_observation_ratio_final": float(state["known_free_observation_ratio_curve"][-1]),
        "found_count_curve": list(state["found_count_curve"]),
        "remaining_intensity_mass_curve": list(state["remaining_intensity_mass_curve"]),
        "peak_intensity_ratio_curve": list(state["peak_intensity_ratio_curve"]),
        "known_free_observation_ratio_curve": list(state["known_free_observation_ratio_curve"]),
        "search_info_map_peak_final": float(state["search_info_map_peak"]),
        "search_info_map_mean_final": float(state["search_info_map_mean"]),
        "duplicate_viewpoint_ratio": float(duplicate_viewpoint_ratio),
        "cross_region_assignment_ratio": float(cross_region_assignment_ratio),
        "reservation_wait_fallback_count": int(reservation_wait_fallback_count),
        "reservation_near_neighbor_step_ratio_mean": float(
            reservation_near_neighbor_step_ratio_mean
        ),
        "reservation_same_cell_violation_count": int(
            reservation_same_cell_violation_count
        ),
        "reservation_swap_violation_count": int(reservation_swap_violation_count),
        "anomaly_top_band_selection_ratio_pre_first_detection": float(
            anomaly_top_band_selection_ratio_pre_first_detection
        ),
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": float(
            unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection
        ),
        "conflict_intervention_count": int(conflict_intervention_count),
        "wait_count_total": int(sum(wait_count_by_usv)),
        "wait_count_by_usv": wait_count_by_usv,
        "team_trace_rows": team_trace_rows,
        "trace_rows": trace_rows,
        "target_motion_mode": state["target_motion_mode"],
        "target_count_upper_bound": state["target_count_upper_bound"],
        "gp_n_obs": state["gp_field"].n_obs,
        "eval_mean_gp_reward": float(
            np.mean(state["gp_acq_map"][state["nav_map_prior"] == FREE])
        )
        if np.any(state["nav_map_prior"] == FREE)
        else 0.0,
    }


def _two_usv_policy_summary_rows(policy_results: list[dict[str, object]]) -> dict[str, object]:
    return {
        "success_all_found_mean": _mean_or_default([float(r["success_all_found"]) for r in policy_results]),
        "found_count_mean": _mean_or_default([float(r["found_count"]) for r in policy_results]),
        "detection_rate_mean": _mean_or_default([float(r["detection_rate"]) for r in policy_results]),
        "time_to_first_detection_mean": _mean_or_default(
            [float(r["time_to_first_detection"]) for r in policy_results if r["time_to_first_detection"] is not None],
            default=float("nan"),
        ),
        "time_to_all_found_mean": _mean_or_default(
            [float(r["time_to_all_found"]) for r in policy_results if r["time_to_all_found"] is not None],
            default=float("nan"),
        ),
        "planning_time_ms_mean": _mean_or_default([float(r["planning_time_ms_mean"]) for r in policy_results]),
        "known_free_observation_ratio_final_mean": _mean_or_default(
            [float(r["known_free_observation_ratio_final"]) for r in policy_results]
        ),
        "path_safety_modes": sorted(
            {
                str(result.get("path_safety_mode", "off"))
                for result in policy_results
                if result.get("path_safety_mode") is not None
            }
        ),
        "team_path_avoidance_modes": sorted(
            {
                str(result.get("team_path_avoidance_mode", "off"))
                for result in policy_results
                if result.get("team_path_avoidance_mode") is not None
            }
        ),
        "duplicate_viewpoint_ratio_mean": _mean_or_default(
            [float(r["duplicate_viewpoint_ratio"]) for r in policy_results]
        ),
        "cross_region_assignment_ratio_mean": _mean_or_default(
            [float(r["cross_region_assignment_ratio"]) for r in policy_results]
        ),
        "reservation_wait_fallback_count_mean": _mean_or_default(
            [float(r.get("reservation_wait_fallback_count", 0.0)) for r in policy_results]
        ),
        "reservation_near_neighbor_step_ratio_mean": _mean_or_default(
            [
                float(r.get("reservation_near_neighbor_step_ratio_mean", 0.0))
                for r in policy_results
            ]
        ),
        "reservation_same_cell_violation_count_mean": _mean_or_default(
            [
                float(r.get("reservation_same_cell_violation_count", 0.0))
                for r in policy_results
            ]
        ),
        "reservation_swap_violation_count_mean": _mean_or_default(
            [
                float(r.get("reservation_swap_violation_count", 0.0))
                for r in policy_results
            ]
        ),
        "clue_acquisition_modes": sorted(
            {
                str(result["clue_acquisition_mode"])
                for result in policy_results
                if result.get("clue_acquisition_mode") is not None
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
        "conflict_intervention_count_mean": _mean_or_default(
            [float(r["conflict_intervention_count"]) for r in policy_results]
        ),
        "wait_count_total_mean": _mean_or_default([float(r["wait_count_total"]) for r in policy_results]),
    }


def _phase7_result_identity(result: dict[str, object]) -> tuple[str, int]:
    map_kind = str(result.get("map_kind", ""))
    if "episode_seed" not in result:
        raise ValueError("Phase 7 comparison requires every result to include episode_seed.")
    return map_kind, int(result["episode_seed"])


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(np.asarray(values, dtype=float)))


def _phase7_metric_delta(
    metric_name: str,
    *,
    baseline_result: dict[str, object],
    challenger_result: dict[str, object],
) -> int | float | None:
    baseline_value = baseline_result.get(metric_name)
    challenger_value = challenger_result.get(metric_name)
    if baseline_value is None or challenger_value is None:
        return None
    if metric_name in PHASE7_INT_DELTA_METRICS:
        return int(challenger_value) - int(baseline_value)
    return float(challenger_value) - float(baseline_value)


def _phase7_delta_means(paired_rows: list[dict[str, object]]) -> dict[str, float | None]:
    return {
        f"{metric_name}_delta_mean": _mean_or_none(
            [
                float(row[f"{metric_name}_delta"])
                for row in paired_rows
                if row.get(f"{metric_name}_delta") is not None
            ]
        )
        for metric_name in PHASE7_PAIRWISE_METRICS
    }


def _phase7_system_summary(results: list[dict[str, object]]) -> dict[str, object]:
    summary = {
        "n_episodes": int(len(results)),
        "success_all_found_mean": _mean_or_none(
            [float(result["success_all_found"]) for result in results if result.get("success_all_found") is not None]
        ),
        "assignment_modes": sorted(
            {
                str(result["assignment_mode"])
                for result in results
                if result.get("assignment_mode") is not None
            }
        ),
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
    }
    for metric_name in PHASE7_SHARED_METRICS + PHASE7_AUXILIARY_METRICS + PHASE7_TWO_USV_ONLY_METRICS:
        summary[f"{metric_name}_mean"] = _mean_or_none(
            [
                float(result[metric_name])
                for result in results
                if result.get(metric_name) is not None
            ]
        )

    wait_vectors = [
        [float(value) for value in result["wait_count_by_usv"]]
        for result in results
        if result.get("wait_count_by_usv") is not None
    ]
    if wait_vectors:
        n_usvs = max(len(values) for values in wait_vectors)
        summary["wait_count_by_usv_mean"] = [
            _mean_or_none(
                [values[usv_id] for values in wait_vectors if len(values) > usv_id]
            )
            for usv_id in range(n_usvs)
        ]
    else:
        summary["wait_count_by_usv_mean"] = None
    return summary


def _align_phase7_results(
    baseline_results: list[dict[str, object]],
    challenger_results: list[dict[str, object]],
) -> list[tuple[tuple[str, int], dict[str, object], dict[str, object]]]:
    baseline_by_key: dict[tuple[str, int], dict[str, object]] = {}
    challenger_by_key: dict[tuple[str, int], dict[str, object]] = {}
    for result in baseline_results:
        identity = _phase7_result_identity(result)
        if identity in baseline_by_key:
            raise ValueError(f"Duplicate baseline Phase 7 result identity: {identity}")
        baseline_by_key[identity] = result
    for result in challenger_results:
        identity = _phase7_result_identity(result)
        if identity in challenger_by_key:
            raise ValueError(f"Duplicate challenger Phase 7 result identity: {identity}")
        challenger_by_key[identity] = result

    baseline_keys = set(baseline_by_key.keys())
    challenger_keys = set(challenger_by_key.keys())
    if baseline_keys != challenger_keys:
        missing_from_challenger = sorted(baseline_keys - challenger_keys)
        missing_from_baseline = sorted(challenger_keys - baseline_keys)
        raise ValueError(
            "Phase 7 paired comparison requires identical (map_kind, episode_seed) support. "
            f"missing_from_challenger={missing_from_challenger}, "
            f"missing_from_baseline={missing_from_baseline}"
        )

    return [
        (identity, baseline_by_key[identity], challenger_by_key[identity])
        for identity in sorted(baseline_keys, key=lambda item: (item[0], item[1]))
    ]


def _summarize_phase7_pairwise_results(
    baseline_results: list[dict[str, object]],
    challenger_results: list[dict[str, object]],
    *,
    baseline_system_name: str,
    challenger_system_name: str,
) -> dict[str, object]:
    paired_rows: list[dict[str, object]] = []
    aligned_results = _align_phase7_results(baseline_results, challenger_results)
    for (map_kind, episode_seed), baseline_result, challenger_result in aligned_results:
        row: dict[str, object] = {
            "map_kind": map_kind,
            "episode_seed": int(episode_seed),
        }
        for metric_name in PHASE7_PAIRWISE_METRICS:
            row[f"{metric_name}_delta"] = _phase7_metric_delta(
                metric_name,
                baseline_result=baseline_result,
                challenger_result=challenger_result,
            )
        paired_rows.append(row)

    mapwise: dict[str, dict[str, object]] = {}
    map_kinds = sorted({str(result.get("map_kind", "")) for result in baseline_results + challenger_results})
    for map_kind in map_kinds:
        map_baseline_results = [
            result for result in baseline_results if str(result.get("map_kind", "")) == map_kind
        ]
        map_challenger_results = [
            result for result in challenger_results if str(result.get("map_kind", "")) == map_kind
        ]
        map_pairs = _align_phase7_results(map_baseline_results, map_challenger_results)
        map_rows = [
            row for row in paired_rows if str(row.get("map_kind", "")) == map_kind
        ]
        mapwise[map_kind] = {
            "n_episodes": int(len(map_pairs)),
            "baseline_summary": _phase7_system_summary(map_baseline_results),
            "challenger_summary": _phase7_system_summary(map_challenger_results),
            "delta_means": _phase7_delta_means(map_rows),
        }

    return {
        "baseline_system_name": baseline_system_name,
        "challenger_system_name": challenger_system_name,
        "paired_episode_rows": paired_rows,
        "summary": {
            "n_episodes": int(len(paired_rows)),
            "baseline_summary": _phase7_system_summary(baseline_results),
            "challenger_summary": _phase7_system_summary(challenger_results),
            "delta_means": _phase7_delta_means(paired_rows),
        },
        "mapwise": mapwise,
    }


def summarize_two_usv_knownmap_policy_comparison(
    baseline_results: list[dict],
    challenger_results: list[dict],
    *,
    baseline_policy_name: str,
    challenger_policy_name: str,
) -> dict[str, object]:
    if len(baseline_results) != len(challenger_results):
        raise ValueError("Baseline and challenger result counts must match")

    paired_rows: list[dict[str, object]] = []
    baseline_episode_seeds = [result.get("episode_seed", idx) for idx, result in enumerate(baseline_results)]
    challenger_episode_seeds = [result.get("episode_seed", idx) for idx, result in enumerate(challenger_results)]
    if baseline_episode_seeds != challenger_episode_seeds:
        raise ValueError("2-USV policy comparison requires baseline and challenger episode seeds to align.")

    for baseline_result, challenger_result, episode_seed in zip(
        baseline_results,
        challenger_results,
        baseline_episode_seeds,
    ):
        row: dict[str, object] = {
            "episode_seed": int(episode_seed),
        }
        if baseline_result.get("map_kind") is not None:
            row["map_kind"] = str(baseline_result["map_kind"])
        for metric_name in (
            "time_to_first_detection",
            "time_to_all_found",
            "detection_rate",
            "found_count",
            "known_free_observation_ratio_final",
            "duplicate_viewpoint_ratio",
            "cross_region_assignment_ratio",
            "conflict_intervention_count",
            "wait_count_total",
        ):
            row[f"{metric_name}_delta"] = _phase7_metric_delta(
                metric_name,
                baseline_result=baseline_result,
                challenger_result=challenger_result,
            )
        paired_rows.append(row)

    return {
        "baseline_policy_name": baseline_policy_name,
        "challenger_policy_name": challenger_policy_name,
        "paired_episode_rows": paired_rows,
        "summary": {
            "n_episodes": int(len(paired_rows)),
            "baseline_summary": _two_usv_policy_summary_rows(baseline_results),
            "challenger_summary": _two_usv_policy_summary_rows(challenger_results),
            "delta_means": {
                f"{metric_name}_delta_mean": _mean_or_none(
                    [
                        float(row[f"{metric_name}_delta"])
                        for row in paired_rows
                        if row.get(f"{metric_name}_delta") is not None
                    ]
                )
                for metric_name in (
                    "time_to_first_detection",
                    "time_to_all_found",
                    "detection_rate",
                    "found_count",
                    "known_free_observation_ratio_final",
                    "duplicate_viewpoint_ratio",
                    "cross_region_assignment_ratio",
                    "conflict_intervention_count",
                    "wait_count_total",
                )
            },
        },
    }


def summarize_two_usv_knownmap_policy_comparison_matrix(
    results_by_policy: dict[str, list[dict]],
    policy_names: tuple[str, ...] | list[str] | None = None,
) -> dict[str, object]:
    resolved_policy_names = (
        [str(policy_name) for policy_name in policy_names]
        if policy_names is not None
        else list(results_by_policy.keys())
    )
    missing_policy_names = [
        policy_name for policy_name in resolved_policy_names if policy_name not in results_by_policy
    ]
    if missing_policy_names:
        raise ValueError(
            f"Missing policy results for 2-USV known-map comparison matrix: {missing_policy_names}"
        )

    pair_labels: list[str] = []
    pairwise_comparisons: dict[str, dict[str, object]] = {}
    for baseline_policy_name, challenger_policy_name in combinations(resolved_policy_names, 2):
        pair_label = f"{baseline_policy_name}__vs__{challenger_policy_name}"
        pair_labels.append(pair_label)
        pairwise_comparisons[pair_label] = summarize_two_usv_knownmap_policy_comparison(
            results_by_policy[baseline_policy_name],
            results_by_policy[challenger_policy_name],
            baseline_policy_name=baseline_policy_name,
            challenger_policy_name=challenger_policy_name,
        )

    return {
        "policy_names": list(resolved_policy_names),
        "pair_labels": pair_labels,
        "pairwise_comparisons": pairwise_comparisons,
    }


def _phase7_config_snapshot(
    *,
    map_kinds: tuple[str, ...],
    episode_seeds: tuple[int, ...],
    max_iters: int,
    contract: dict[str, object],
    target_motion_mode: str,
    clue_acquisition_mode: str,
    anomaly_tail_quantile: float,
    anomaly_weight_lambda: float,
) -> dict[str, object]:
    return {
        "map_kinds": list(map_kinds),
        "episode_seeds": list(episode_seeds),
        "max_iters": int(max_iters),
        "map_height_cells": 60,
        "map_width_cells": 80,
        "clue_sigma_m": 15.0,
        "single_usv_policy_name": "marine_knownmap_path_v2_infosampled",
        "two_usv_independent_policy_name": "marine_knownmap_path_v2_infosampled_2usv",
        "two_usv_coordinated_policy_name": "marine_knownmap_path_v2_infosampled_2usv",
        "two_usv_independent_assignment_mode": "independent",
        "two_usv_coordinated_assignment_mode": "coordinated",
        "target_motion_mode": str(target_motion_mode),
        "clue_acquisition_mode": str(clue_acquisition_mode),
        "anomaly_tail_quantile": float(anomaly_tail_quantile),
        "anomaly_weight_lambda": float(anomaly_weight_lambda),
        "two_usv_contract_revision_id": contract["baseline_revision_id"],
        "two_usv_contract_schema_version": contract["schema_version"],
        "knownmap_contract_path_2usv": str(KNOWNMAP_EXPERIMENT_2USV_CONTRACT_PATH),
    }


def _phase7_overall_scorecard(
    pairwise_summary: dict[str, object],
) -> dict[str, object]:
    coordinated_vs_independent = pairwise_summary.get(
        f"{PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{PHASE7_SYSTEM_TWO_USV_INDEPENDENT}",
        {},
    )
    delta_means = coordinated_vs_independent.get("summary", {}).get("delta_means", {})
    time_to_first_delta = delta_means.get("time_to_first_detection_delta_mean")
    time_to_all_delta = delta_means.get("time_to_all_found_delta_mean")
    known_free_delta = delta_means.get("known_free_observation_ratio_final_delta_mean")
    duplicate_delta = delta_means.get("duplicate_viewpoint_ratio_delta_mean")
    detection_time_improved = None
    if time_to_first_delta is not None or time_to_all_delta is not None:
        detection_time_improved = bool(
            (time_to_first_delta is not None and float(time_to_first_delta) < 0.0)
            or (time_to_all_delta is not None and float(time_to_all_delta) < 0.0)
        )
    return {
        "coordinated_vs_independent": {
            "duplicate_viewpoint_ratio_improved": (
                None if duplicate_delta is None else bool(float(duplicate_delta) < 0.0)
            ),
            "detection_time_improved": detection_time_improved,
            "known_free_observation_ratio_improved": (
                None if known_free_delta is None else bool(float(known_free_delta) > 0.0)
            ),
        }
    }


def run_episode_two_usv_search_knownmap(
    episode_seed: int = 0,
    max_iters: int = 240,
    policy_name: str = "marine_knownmap_path_v2_infosampled_2usv",
    assignment_mode: str = "coordinated",
    n_targets: int = 3,
    map_kind: str = "harbor_cove",
    map_height_cells: int = 60,
    map_width_cells: int = 80,
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
    clue_sigma_m: float = 15.0,
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
    path_safety_mode: str = "off",
    safe_nav_inflation_radius_cells: int = 0,
    safe_nav_soft_clearance_radius_cells: int = 1,
    safe_nav_lambda_clearance: float = 1.0,
    team_path_avoidance_mode: str = "off",
    team_reservation_safety_distance_cells: float = 1.5,
    team_reservation_lambda: float = 1.0,
    planner_adaptation_mode: str = "adaptive",
    r_hit: int = 1,
    render: bool = False,
    show_true_targets_in_viz: bool = False,
) -> dict[str, object]:
    _team_underlying_policy(policy_name)
    if assignment_mode not in SUPPORTED_TWO_USV_ASSIGNMENT_MODES:
        raise ValueError(
            "assignment_mode must be one of "
            f"{SUPPORTED_TWO_USV_ASSIGNMENT_MODES}, got '{assignment_mode}'"
        )
    if target_count_mode != "upper_bound":
        raise ValueError(f"Unsupported target_count_mode='{target_count_mode}'")
    if target_count_upper_bound is None:
        target_count_upper_bound = int(n_targets)
    if target_count_upper_bound < n_targets:
        raise ValueError("target_count_upper_bound must be >= n_targets")
    if path_safety_mode not in SUPPORTED_PATH_SAFETY_MODES:
        raise ValueError(
            "path_safety_mode must be one of "
            f"{SUPPORTED_PATH_SAFETY_MODES}, got '{path_safety_mode}'"
        )
    if team_path_avoidance_mode not in SUPPORTED_TEAM_PATH_AVOIDANCE_MODES:
        raise ValueError(
            "team_path_avoidance_mode must be one of "
            f"{SUPPORTED_TEAM_PATH_AVOIDANCE_MODES}, got '{team_path_avoidance_mode}'"
        )
    if planner_adaptation_mode not in SUPPORTED_TWO_USV_PLANNER_ADAPTATION_MODES:
        raise ValueError(
            "planner_adaptation_mode must be one of "
            f"{SUPPORTED_TWO_USV_PLANNER_ADAPTATION_MODES}, got '{planner_adaptation_mode}'"
        )

    try:
        state = _init_two_usv_knownmap_state(
            episode_seed=episode_seed,
            n_targets=n_targets,
            map_kind=map_kind,
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
            map_height_cells=map_height_cells,
            map_width_cells=map_width_cells,
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
            path_safety_mode=path_safety_mode,
            safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
            safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            team_path_avoidance_mode=team_path_avoidance_mode,
            team_reservation_safety_distance_cells=team_reservation_safety_distance_cells,
            team_reservation_lambda=team_reservation_lambda,
            constraint_mode=constraint_mode,
            r_hit=r_hit,
            clue_samples_per_step=clue_samples_per_step,
        )
    except PlacementInfeasibleError:
        return _placement_infeasible_two_usv_result(
            episode_seed=episode_seed,
            policy_name=policy_name,
            assignment_mode=assignment_mode,
            n_targets=n_targets,
            constraint_mode=constraint_mode,
            map_kind=map_kind,
            map_height_cells=map_height_cells,
            map_width_cells=map_width_cells,
            clue_acquisition_mode=clue_acquisition_mode,
            anomaly_tail_quantile=anomaly_tail_quantile,
            anomaly_weight_lambda=anomaly_weight_lambda,
            path_safety_mode=path_safety_mode,
            team_path_avoidance_mode=team_path_avoidance_mode,
        )

    state["gp_max_points"] = gp_max_points
    state["lambda_u_turn"] = float(lambda_u_turn)
    state["gamma"] = float(gamma)
    state["segment_horizon"] = int(segment_horizon)
    state["top_k_anchors"] = int(top_k_anchors)
    state["viewpoints_per_anchor"] = int(viewpoints_per_anchor)
    state["infosampled_inspected_limit_multiplier"] = float(infosampled_inspected_limit_multiplier)
    state["infosampled_inspected_limit_floor"] = int(infosampled_inspected_limit_floor)
    state["assignment_mode"] = str(assignment_mode)
    state["planner_adaptation_mode"] = str(planner_adaptation_mode)

    if render:
        plt.figure(figsize=(15, 9))
        plot_team_search_state(
            state["nav_map_prior"],
            state["usv_states"],
            state["target_positions"],
            state["found_mask"],
            step=0,
            policy_name=policy_name,
            clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
            clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
            clue_heatmap_limits=state.get("clue_heatmap_limits"),
            search_info_map=state["search_info_map"],
            intensity_map=state["intensity_map"],
            staleness_map=state["staleness_map"],
            wait_applied_map=None,
            conflict_type=None,
            joint_summary=None,
            responsibility_owner_map=state["responsibility_owner_map"],
            buffer_band_mask=state["buffer_band_mask"],
            show_true_targets=show_true_targets_in_viz,
        )

    if np.all(state["found_mask"]):
        state["terminated_reason"] = "all_found"
        return _summarize_two_usv_result(state, policy_name)

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

        t0 = time.perf_counter()
        if assignment_mode == "coordinated":
            assignments, joint_summary = _joint_assign_two_usv_segments(
                team_state=state,
                policy_name=policy_name,
                predicted_intensity=predicted_intensity,
                step=step,
            )
        elif assignment_mode == "independent":
            assignments, joint_summary = _assign_two_usv_segments_independent(
                team_state=state,
                policy_name=policy_name,
                predicted_intensity=predicted_intensity,
                step=step,
            )
        else:
            raise ValueError(
                "assignment_mode must be one of "
                f"{SUPPORTED_TWO_USV_ASSIGNMENT_MODES}, got '{assignment_mode}'"
            )
        joint_summary["clue_acquisition_mode"] = str(state.get("clue_acquisition_mode", "ucb"))
        anomaly_conditional_diag = {
            "anomaly_conditional_alpha": float(
                state.get("anomaly_conditional_alpha", 0.0)
            ),
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
        }
        joint_summary.update(anomaly_conditional_diag)
        for assignment in assignments.values():
            assignment["plan_details"].update(anomaly_conditional_diag)
        _apply_joint_assignment_to_locals(
            state,
            policy_name,
            assignments,
            search_commit_window=search_commit_window,
            search_commit_max_window=search_commit_max_window,
            search_commit_path_divisor=search_commit_path_divisor,
        )
        state["planning_time_ms"].append((time.perf_counter() - t0) * 1000.0)

        wait_applied_map, conflict_type, conflict_penalty = _resolve_execution_conflict(
            state,
            assignments,
            safety_distance_cells=float(
                state.get("team_reservation_safety_distance_cells", 1.5)
            ),
        )

        if render:
            plot_team_search_state(
                state["nav_map_prior"],
                state["usv_states"],
                state["target_positions"],
                state["found_mask"],
                step=step,
                policy_name=policy_name,
                clue_map=state.get("gp_clue_planner_map", state["gp_acq_map"]),
                clue_title=_clue_heatmap_title(state.get("clue_acquisition_mode")),
                clue_heatmap_limits=state.get("clue_heatmap_limits"),
                search_info_map=state["search_info_map"],
                intensity_map=predicted_intensity,
                staleness_map=state["staleness_map"],
                wait_applied_map=wait_applied_map,
                conflict_type=conflict_type,
                joint_summary=joint_summary,
                responsibility_owner_map=state["responsibility_owner_map"],
                buffer_band_mask=state["buffer_band_mask"],
                show_true_targets=show_true_targets_in_viz,
            )

        exec_results = {}
        local_observation_terms: dict[int, tuple[float, float]] = {}
        for usv_id, local in enumerate(state["usv_states"]):
            local_observation_terms[usv_id] = _observation_progress_for_robot(state, local["robot_pos"])
            if wait_applied_map[usv_id]:
                exec_results[usv_id] = None
            else:
                exec_results[usv_id] = execute_next_step(
                    state["true_map"],
                    state["nav_map_prior"],
                    local["robot_pos"],
                    local["committed_segment"],
                )

        for usv_id, local in enumerate(state["usv_states"]):
            _update_local_after_execution(
                local,
                wait_applied_map[usv_id],
                exec_results[usv_id],
            )

        for local in state["usv_states"]:
            refresh_last_seen(
                state["last_seen_step"],
                state["nav_map_prior"],
                local["robot_pos"],
                state["sensor_range_cells"],
                step=step,
            )
        state["staleness_map"] = build_staleness_map(
            state["last_seen_step"],
            state["nav_map_prior"],
            current_step=step,
            tau_stale=staleness_tau_steps,
        )

        predicted_intensity = apply_known_occupancy_constraints(
            predicted_intensity,
            state["nav_map_prior"],
            preserve_mass=True,
        )
        remaining_target_mass_before = _remaining_target_intensity_mass(state)
        team_detected_mask = np.zeros_like(state["found_mask"], dtype=bool)
        detected_by_usv = {0: 0, 1: 0}
        for usv_id, local in enumerate(state["usv_states"]):
            detected_mask = detect_targets(
                local["robot_pos"],
                state["target_positions"],
                state["found_mask"],
                state["sensor_range_cells"],
                state["detection_rng"],
            )
            detected_by_usv[usv_id] = int(np.sum(detected_mask))
            team_detected_mask |= detected_mask
        new_indices = update_found_mask(state["found_mask"], team_detected_mask, state["find_times"], step)
        team_detected_count = len(new_indices)
        if team_detected_count > 0:
            state["time_since_last_detection"] = 0
        else:
            state["time_since_last_detection"] += 1

        updated_intensity = _apply_team_miss_updates(
            predicted_intensity,
            [tuple(int(v) for v in local["robot_pos"]) for local in state["usv_states"]],
            state["sensor_range_cells"],
            known_map=state["nav_map_prior"],
            target_total_mass=remaining_target_mass_before,
        )
        if team_detected_count > 0:
            hit_positions = [
                tuple(int(v) for v in state["target_positions"][idx])
                for idx in new_indices
            ]
            updated_intensity = hit_update_intensity(
                updated_intensity,
                hit_positions=hit_positions,
                hit_count=team_detected_count,
                r_hit=state["r_hit"],
                known_map=state["nav_map_prior"],
                target_total_mass=_remaining_target_intensity_mass(state),
            )
        state["intensity_map"] = updated_intensity
        _sample_and_update_team_gp(state, step=step, gp_fit_every=gp_fit_every)
        _update_team_search_info_state(state, state["intensity_map"])
        _append_anomaly_target_neighborhood_metric(state, step=step)

        state["found_count_curve"].append(int(state["found_mask"].sum()))
        state["remaining_intensity_mass_curve"].append(remaining_intensity_mass(state["intensity_map"]))
        state["peak_intensity_ratio_curve"].append(
            peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
        )
        state["known_free_observation_ratio_curve"].append(
            known_free_observation_ratio(state["last_seen_step"], state["nav_map_prior"])
        )
        state["completed_steps"] = step

        state["team_trace_rows"].append(
            _team_trace_row(
                team_step=step,
                assignments=assignments,
                joint_summary=joint_summary,
                conflict_type=conflict_type,
                conflict_penalty=conflict_penalty,
                wait_applied_map=wait_applied_map,
                team_detected_count=team_detected_count,
            )
        )
        for usv_id, local in enumerate(state["usv_states"]):
            effective_gain, stale_ratio = local_observation_terms[usv_id]
            _append_trimmed(local["recent_effective_observation_gains"], effective_gain, max_len=10)
            state["trace_rows"].append(
                _local_trace_row(
                    team_step=step,
                    usv_id=usv_id,
                    local=local,
                    clue_acquisition_mode=str(state.get("clue_acquisition_mode", "ucb")),
                    responsibility_owner_map=state.get("responsibility_owner_map"),
                    assignment=assignments[usv_id],
                    wait_applied=wait_applied_map[usv_id],
                    conflict_type=conflict_type,
                    conflict_penalty=conflict_penalty,
                    detected_count_this_step=detected_by_usv[usv_id],
                    effective_observation_gain=effective_gain,
                    stale_refresh_ratio=stale_ratio,
                    joint_assignment_score=float(joint_summary["joint_assignment_score"]),
                )
            )

        if np.all(state["found_mask"]):
            state["terminated_reason"] = "all_found"
            break
    else:
        state["completed_steps"] = max_iters

    return _summarize_two_usv_result(state, policy_name)


def run_visual_two_usv_search_knownmap(
    episode_seed: int = 0,
    max_iters: int = 240,
    policy_name: str = "marine_knownmap_path_v2_infosampled_2usv",
    show_true_targets_in_viz: bool = True,
    **kwargs,
) -> None:
    result = run_episode_two_usv_search_knownmap(
        episode_seed=episode_seed,
        max_iters=max_iters,
        policy_name=policy_name,
        render=True,
        show_true_targets_in_viz=show_true_targets_in_viz,
        **kwargs,
    )
    plt.show()
    placement_suffix = (
        f" | placement={result['placement_status']}"
        if result["placement_status"] != "satisfied"
        else ""
    )
    print(
        f"\n2-USV known-map search result | policy={policy_name} | "
        f"success_all_found={result['success_all_found']} | "
        f"found_count={result['found_count']} | miss_count={result['miss_count']} | "
        f"steps={result['completed_steps']} | "
        f"known_free_obs={result['known_free_observation_ratio_final']:.2f}"
        f"{placement_suffix}"
    )


def run_evaluation_two_usv_search_knownmap(
    n_episodes: int = 5,
    max_iters: int = 240,
    policy_names: tuple[str, ...] | list[str] | None = None,
    output_dir: str | None = None,
    save_artifacts: bool = False,
    episode_seeds: tuple[int, ...] | list[int] | None = None,
    **episode_kwargs,
) -> dict[str, list[dict[str, object]]]:
    if policy_names is None:
        resolved_policy_names = SUPPORTED_TWO_USV_KNOWNMAP_POLICIES
    else:
        resolved_policy_names = tuple(str(policy_name) for policy_name in policy_names)
    for policy_name in resolved_policy_names:
        _team_underlying_policy(policy_name)

    resolved_episode_seeds = (
        tuple(int(seed) for seed in episode_seeds)
        if episode_seeds is not None
        else tuple(range(int(n_episodes)))
    )
    results_by_policy: dict[str, list[dict[str, object]]] = {}
    eval_output_dir = _make_output_dir(output_dir, default_leaf="search_eval_knownmap_2usv") if save_artifacts else None

    for policy_name in resolved_policy_names:
        policy_results: list[dict[str, object]] = []
        print(
            f"Evaluate 2-USV known-map suspicious search | policy={policy_name} | "
            f"episodes={len(resolved_episode_seeds)} | max_iters={int(max_iters)}"
        )
        for episode_seed in resolved_episode_seeds:
            result = run_episode_two_usv_search_knownmap(
                episode_seed=episode_seed,
                max_iters=max_iters,
                policy_name=policy_name,
                **episode_kwargs,
            )
            policy_results.append(result)
            print(
                f"  [seed={episode_seed}] success={result['success_all_found']} "
                f"found={result['found_count']} first={result['time_to_first_detection']} "
                f"all={result['time_to_all_found']} known_free_obs={result['known_free_observation_ratio_final']:.2f}"
            )
        results_by_policy[policy_name] = policy_results

    if eval_output_dir is not None:
        comparison_matrix = (
            summarize_two_usv_knownmap_policy_comparison_matrix(
                results_by_policy,
                policy_names=resolved_policy_names,
            )
            if len(resolved_policy_names) >= 2
            else None
        )
        summary_payload = {
            "created_at": datetime.now().isoformat(),
            "n_episodes": len(resolved_episode_seeds),
            "max_iters": int(max_iters),
            "policy_names": list(resolved_policy_names),
            "episode_seeds": list(resolved_episode_seeds),
            "episode_kwargs": _json_safe(episode_kwargs),
            "policy_summary": {
                policy_name: _two_usv_policy_summary_rows(results)
                for policy_name, results in results_by_policy.items()
            },
            "two_usv_knownmap_policy_comparison_matrix": _json_safe(comparison_matrix),
        }
        _write_csv(
            eval_output_dir / "team_results.csv",
            [
                {
                    "policy_name": policy_name,
                    "assignment_mode": result.get("assignment_mode"),
                    "clue_acquisition_mode": result.get("clue_acquisition_mode"),
                    "path_safety_mode": result.get("path_safety_mode"),
                    "team_path_avoidance_mode": result.get("team_path_avoidance_mode"),
                    "safe_nav_inflation_radius_cells": result.get(
                        "safe_nav_inflation_radius_cells"
                    ),
                    "safe_nav_soft_clearance_radius_cells": result.get(
                        "safe_nav_soft_clearance_radius_cells"
                    ),
                    "safe_nav_lambda_clearance": result.get("safe_nav_lambda_clearance"),
                    "team_reservation_safety_distance_cells": result.get(
                        "team_reservation_safety_distance_cells"
                    ),
                    "team_reservation_lambda": result.get("team_reservation_lambda"),
                    "episode_seed": episode_seed,
                    "found_count": result["found_count"],
                    "time_to_first_detection": result["time_to_first_detection"],
                    "time_to_all_found": result["time_to_all_found"],
                    "known_free_observation_ratio_final": result["known_free_observation_ratio_final"],
                    "planning_time_ms_mean": result["planning_time_ms_mean"],
                    "anomaly_top_band_selection_ratio_pre_first_detection": result.get(
                        "anomaly_top_band_selection_ratio_pre_first_detection"
                    ),
                    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": result.get(
                        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection"
                    ),
                    "duplicate_viewpoint_ratio": result["duplicate_viewpoint_ratio"],
                    "cross_region_assignment_ratio": result["cross_region_assignment_ratio"],
                    "conflict_intervention_count": result["conflict_intervention_count"],
                    "wait_count_total": result["wait_count_total"],
                    "reservation_wait_fallback_count": result.get(
                        "reservation_wait_fallback_count"
                    ),
                    "reservation_near_neighbor_step_ratio_mean": result.get(
                        "reservation_near_neighbor_step_ratio_mean"
                    ),
                    "reservation_same_cell_violation_count": result.get(
                        "reservation_same_cell_violation_count"
                    ),
                    "reservation_swap_violation_count": result.get(
                        "reservation_swap_violation_count"
                    ),
                }
                for policy_name, results in results_by_policy.items()
                for episode_seed, result in zip(resolved_episode_seeds, results)
            ],
        )
        if comparison_matrix is not None:
            with (eval_output_dir / "comparison_matrix.json").open("w", encoding="utf-8") as f:
                json.dump(_json_safe(comparison_matrix), f, indent=2, ensure_ascii=False)
        with (eval_output_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(summary_payload), f, indent=2, ensure_ascii=False)

    return results_by_policy


def run_phase7_knownmap_comparison(
    *,
    map_kinds: tuple[str, ...] | list[str] = PHASE7_DEFAULT_MAP_KINDS,
    episode_seeds: tuple[int, ...] | list[int] | None = None,
    max_iters: int | None = None,
    target_motion_mode: str | None = None,
    clue_acquisition_mode: str = "ucb",
    anomaly_tail_quantile: float = 0.90,
    anomaly_weight_lambda: float = 1.0,
    output_dir: str | None = None,
    save_artifacts: bool = True,
) -> dict[str, object]:
    contract = load_knownmap_experiment_contract_2usv()
    frozen_config = dict(contract["frozen_config"])
    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_episode_seeds = (
        tuple(int(seed) for seed in episode_seeds)
        if episode_seeds is not None
        else tuple(int(seed) for seed in frozen_config["episode_seeds"])
    )
    resolved_max_iters = (
        int(max_iters) if max_iters is not None else int(frozen_config["max_iters"])
    )
    resolved_target_motion_mode = (
        str(target_motion_mode)
        if target_motion_mode is not None
        else str(frozen_config["target_motion_mode"])
    )
    output_path = (
        _make_output_dir(output_dir, default_leaf="phase7_knownmap_comparison")
        if save_artifacts
        else None
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

    config_snapshot = _phase7_config_snapshot(
        map_kinds=resolved_map_kinds,
        episode_seeds=resolved_episode_seeds,
        max_iters=resolved_max_iters,
        contract=contract,
        target_motion_mode=resolved_target_motion_mode,
        clue_acquisition_mode=clue_acquisition_mode,
        anomaly_tail_quantile=anomaly_tail_quantile,
        anomaly_weight_lambda=anomaly_weight_lambda,
    )
    results_by_system: dict[str, dict[str, list[dict[str, object]]]] = {
        PHASE7_SYSTEM_SINGLE: {map_kind: [] for map_kind in resolved_map_kinds},
        PHASE7_SYSTEM_TWO_USV_INDEPENDENT: {map_kind: [] for map_kind in resolved_map_kinds},
        PHASE7_SYSTEM_TWO_USV_COORDINATED: {map_kind: [] for map_kind in resolved_map_kinds},
    }

    for map_kind in resolved_map_kinds:
        for episode_seed in resolved_episode_seeds:
            print(
                f"Phase 7 known-map benchmark | system={PHASE7_SYSTEM_SINGLE} | "
                f"map={map_kind} | seed={episode_seed} | max_iters={resolved_max_iters}"
            )
            single_result = dict(
                run_episode_single_usv_search_knownmap(
                    episode_seed=episode_seed,
                    max_iters=resolved_max_iters,
                    policy_name="marine_knownmap_path_v2_infosampled",
                    map_kind=map_kind,
                    target_motion_mode=resolved_target_motion_mode,
                    clue_acquisition_mode=clue_acquisition_mode,
                    anomaly_tail_quantile=anomaly_tail_quantile,
                    anomaly_weight_lambda=anomaly_weight_lambda,
                    **base_episode_kwargs,
                )
            )
            single_result["episode_seed"] = int(episode_seed)
            single_result["map_kind"] = map_kind
            single_result["assignment_mode"] = None
            single_result["system_name"] = PHASE7_SYSTEM_SINGLE
            results_by_system[PHASE7_SYSTEM_SINGLE][map_kind].append(single_result)

            for system_name, assignment_mode in (
                (PHASE7_SYSTEM_TWO_USV_INDEPENDENT, "independent"),
                (PHASE7_SYSTEM_TWO_USV_COORDINATED, "coordinated"),
            ):
                print(
                    f"Phase 7 known-map benchmark | system={system_name} | "
                    f"map={map_kind} | seed={episode_seed} | max_iters={resolved_max_iters}"
                )
                result = dict(
                    run_episode_two_usv_search_knownmap(
                        episode_seed=episode_seed,
                        max_iters=resolved_max_iters,
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode=assignment_mode,
                        map_kind=map_kind,
                        target_motion_mode=resolved_target_motion_mode,
                        clue_acquisition_mode=clue_acquisition_mode,
                        anomaly_tail_quantile=anomaly_tail_quantile,
                        anomaly_weight_lambda=anomaly_weight_lambda,
                        **base_episode_kwargs,
                    )
                )
                result["episode_seed"] = int(episode_seed)
                result["map_kind"] = map_kind
                result["assignment_mode"] = assignment_mode
                result["system_name"] = system_name
                results_by_system[system_name][map_kind].append(result)

    comparison_run = {
        "config_snapshot": config_snapshot,
        "results_by_system": results_by_system,
    }

    if output_path is not None:
        with (output_path / "config_snapshot.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)

        for system_name, results_by_map in results_by_system.items():
            for map_kind, map_results in results_by_map.items():
                map_output_dir = output_path / system_name / map_kind
                map_output_dir.mkdir(parents=True, exist_ok=True)
                with (map_output_dir / "episode_results.json").open("w", encoding="utf-8") as f:
                    json.dump(_json_safe(map_results), f, indent=2, ensure_ascii=False)
                with (map_output_dir / "policy_summary.json").open("w", encoding="utf-8") as f:
                    json.dump(
                        _json_safe(
                            {
                                "system_name": system_name,
                                "map_kind": map_kind,
                                "summary": _phase7_system_summary(map_results),
                            }
                        ),
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

        phase7_summary = summarize_phase7_knownmap_comparison(comparison_run)
        pairwise_output_dir = output_path / "pairwise"
        pairwise_output_dir.mkdir(parents=True, exist_ok=True)
        pairwise_file_map = {
            f"{PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{PHASE7_SYSTEM_TWO_USV_INDEPENDENT}":
                "coordinated_vs_independent.json",
            f"{PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{PHASE7_SYSTEM_SINGLE}":
                "coordinated_vs_single.json",
            f"{PHASE7_SYSTEM_TWO_USV_INDEPENDENT}__vs__{PHASE7_SYSTEM_SINGLE}":
                "independent_vs_single.json",
        }
        for pair_label, filename in pairwise_file_map.items():
            with (pairwise_output_dir / filename).open("w", encoding="utf-8") as f:
                json.dump(
                    _json_safe(phase7_summary["pairwise"][pair_label]),
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        with (pairwise_output_dir / "phase7_overall_summary.json").open("w", encoding="utf-8") as f:
            json.dump(_json_safe(phase7_summary), f, indent=2, ensure_ascii=False)

    return comparison_run


def summarize_phase7_knownmap_comparison(
    comparison_run: dict[str, object],
) -> dict[str, object]:
    config_snapshot = dict(comparison_run["config_snapshot"])
    results_by_system = comparison_run["results_by_system"]
    system_names = (
        PHASE7_SYSTEM_SINGLE,
        PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
        PHASE7_SYSTEM_TWO_USV_COORDINATED,
    )
    map_kinds = tuple(str(map_kind) for map_kind in config_snapshot["map_kinds"])

    flattened_results_by_system = {
        system_name: [
            result
            for map_kind in map_kinds
            for result in results_by_system[system_name].get(map_kind, [])
        ]
        for system_name in system_names
    }
    system_summaries = {
        system_name: _phase7_system_summary(flattened_results_by_system[system_name])
        for system_name in system_names
    }
    mapwise_summaries = {
        map_kind: {
            system_name: _phase7_system_summary(results_by_system[system_name].get(map_kind, []))
            for system_name in system_names
        }
        for map_kind in map_kinds
    }
    pairwise = {
        f"{PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{PHASE7_SYSTEM_TWO_USV_INDEPENDENT}":
            _summarize_phase7_pairwise_results(
                flattened_results_by_system[PHASE7_SYSTEM_TWO_USV_INDEPENDENT],
                flattened_results_by_system[PHASE7_SYSTEM_TWO_USV_COORDINATED],
                baseline_system_name=PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
                challenger_system_name=PHASE7_SYSTEM_TWO_USV_COORDINATED,
            ),
        f"{PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{PHASE7_SYSTEM_SINGLE}":
            _summarize_phase7_pairwise_results(
                flattened_results_by_system[PHASE7_SYSTEM_SINGLE],
                flattened_results_by_system[PHASE7_SYSTEM_TWO_USV_COORDINATED],
                baseline_system_name=PHASE7_SYSTEM_SINGLE,
                challenger_system_name=PHASE7_SYSTEM_TWO_USV_COORDINATED,
            ),
        f"{PHASE7_SYSTEM_TWO_USV_INDEPENDENT}__vs__{PHASE7_SYSTEM_SINGLE}":
            _summarize_phase7_pairwise_results(
                flattened_results_by_system[PHASE7_SYSTEM_SINGLE],
                flattened_results_by_system[PHASE7_SYSTEM_TWO_USV_INDEPENDENT],
                baseline_system_name=PHASE7_SYSTEM_SINGLE,
                challenger_system_name=PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
            ),
    }
    return {
        "config_snapshot": config_snapshot,
        "system_summaries": system_summaries,
        "mapwise_summaries": mapwise_summaries,
        "pairwise": pairwise,
        "overall_scorecard": _phase7_overall_scorecard(pairwise),
    }
