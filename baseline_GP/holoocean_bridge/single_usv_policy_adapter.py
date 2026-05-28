"""Adapter for bridging single-USV baseline_GP search policy decisions and state updates with HoloOcean execution."""

from __future__ import annotations

import time
import numpy as np
from typing import Tuple, Dict, List, Union, Optional, Any

# Native helpers from baseline_GP runtime stack
from baseline_GP.marine_knownmap_runtime import (
    _init_knownmap_state,
    step_targets,
    predict_intensity,
    _update_search_info_state,
    apply_known_occupancy_constraints,
    _policy_commit_window,
    _augment_plan_details_with_anomaly,
    _safe_nav_wait_plan_details,
    _append_trimmed,
    _same_anchor_cluster_state,
    _semantic_anchor_source,
    _focus_anchor_source,
    _observation_progress_terms,
    refresh_last_seen,
    build_staleness_map,
    _remaining_target_intensity_mass,
    detect_targets,
    update_found_mask,
    hit_update_intensity,
    miss_update_intensity,
    _sample_and_update_gp,
    _append_anomaly_target_neighborhood_metric,
    _trace_row,
    SEARCH_MODE,
)
from baseline_GP.core_intensity import (
    remaining_intensity_mass,
    peak_intensity_ratio,
)
from baseline_GP.core_staleness import known_free_observation_ratio
from baseline_GP.core_search_policy import select_knownmap_path_segment_policy
from baseline_GP.core_switch_penalty import move_direction
from baseline_GP.holoocean_bridge.coordinate_adapter import CoordinateAdapterConfig
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec


def load_openwater_policy_state(
    map_spec_npz_path: str,
    episode_seed: int = 0,
    policy_name: str = "marine_knownmap_path_v2_infosampled",
    n_targets: int = 3,
    target_motion_mode: str = "static",
    gp_optimize_hyperparams: bool = False,
    gp_max_points: int = 400,
    anomaly_tail_quantile: float = 0.90,
) -> Tuple[Dict[str, Any], CoordinateAdapterConfig, np.ndarray]:
    """Initialize single-USV baseline search policy state.

    Enforces that the starting position is exactly (1, 1).
    """
    # 1. Load the scene-derived openwater static grid
    nav_map_prior, spec = load_scene_map_npz(map_spec_npz_path)
    adapter_config = scene_map_config_from_spec(spec)

    # 2. Call the native baseline state initializer
    state = _init_knownmap_state(
        episode_seed=episode_seed,
        policy_name=policy_name,
        n_targets=n_targets,
        map_kind="open_water",
        map_height_cells=int(spec["height"]),
        map_width_cells=int(spec["width"]),
        target_motion_mode=target_motion_mode,
        target_count_upper_bound=n_targets,
        staleness_tau_steps=12,
        resolution_m=float(spec["cell_size_m"]),
        sensor_range_m=25.0,
        min_target_separation_m=30.0,
        min_start_distance_m=40.0,
        gp_length_scale_m=20.0,
        gp_noise_std=0.03,
        gp_prior_mean=0.0,
        gp_beta=0.5,
        gp_optimize_hyperparams=gp_optimize_hyperparams,
        clue_sigma_m=20.0,
        clue_amplitude=2.0,
        clue_noise_std=0.03,
        search_info_clue_weight=0.5,
        search_info_intensity_weight=0.5,
        clue_acquisition_mode="ucb",
        anomaly_tail_quantile=anomaly_tail_quantile,
        constraint_mode="hard",
        r_hit=1,
        clue_samples_per_step=24,
        path_safety_mode="soft_clearance_astar_v1",
        safe_nav_inflation_radius_cells=0,
        safe_nav_soft_clearance_radius_cells=1,
        safe_nav_lambda_clearance=1.0,
    )


    state["gp_max_points"] = gp_max_points

    # 3. CRITICAL Start Position constraint checks
    robot_pos = state["robot_pos"]
    if robot_pos != (1, 1):
        raise ValueError(
            f"CRITICAL MISMATCH: Policy state initialized 'robot_pos' to {robot_pos}, "
            "but Phase 3A rigidly requires starting position to be (1, 1)."
        )

    # 4. Map integrity verification
    if not np.array_equal(state["nav_map_prior"], nav_map_prior):
        raise ValueError("CRITICAL MAP MISMATCH: Policy nav_map_prior does not match loaded NPZ map prior.")

    return state, adapter_config, nav_map_prior


def plan_next_policy_cell(
    state: Dict[str, Any],
    step: int,
    commit_remaining: int,
    episode_seed: int = 0,
    policy_name: str = "marine_knownmap_path_v2_infosampled",
    target_motion_mode: str = "static",
    gp_fit_every: int = 5,
    lambda_u_turn: float = 2.0,
    segment_horizon: int = 8,
    top_k_anchors: int = 6,
    viewpoints_per_anchor: int = 6,
    gamma: float = 0.95,
    infosampled_inspected_limit_multiplier: float = 3.0,
    infosampled_inspected_limit_floor: int = 4,
    tree_discount_gamma: float = 0.85,
    tree_enable_diminishing_returns: bool = True,
    tree_enable_child_oracle_diagnostics: bool = True,
) -> Tuple[Tuple[int, int], List[Tuple[int, int]], int, Dict[str, Any]]:
    """Determine the next target grid cell using the active search policy.

    Implements the native replanning trigger conditions and baseline planning logic.
    Identical to baseline_GP runtime main loop (marine_knownmap_runtime.py: L2630-2786).
    """
    # 1. Target motion prediction & intensity updates
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
    state["kappa_commit"] = 0.0

    # 2. Check if replanning is needed
    replan_reasons = []
    if state["committed_viewpoint"] is None:
        replan_reasons.append("initial_plan")
    if commit_remaining <= 0:
        replan_reasons.append("commit_expired")
    if len(state["committed_segment"]) <= 1:
        replan_reasons.append("segment_empty")

    need_replan = bool(replan_reasons)
    replanned_this_step = False
    replan_reason = None
    path_length_current = max(len(state["committed_segment"]) - 1, 0)
    previous_viewpoint = state["committed_viewpoint"]
    previous_anchor_source = state.get("last_anchor_source")
    previous_anchor_centroid = state.get("committed_anchor_centroid")
    prev_plan_length = int(state.get("last_planned_segment_length", 0))

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
            tree_first_layer_top_m=3,
            tree_second_layer_top_n=3,
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
            # Fallback path if A* fails
            segment_path = [tuple(int(v) for v in state["robot_pos"])]
            plan_details = {
                **state.get("current_plan_details", {}),
                **_safe_nav_wait_plan_details(state),
            }

        plan_details = _augment_plan_details_with_anomaly(
            state=state,
            plan_details=plan_details,
            segment_path=list(segment_path),
        )

        new_viewpoint = plan_details.get("viewpoint_cell")
        if new_viewpoint != previous_viewpoint:
            state["switch_count"] += 1

        planned_segment_length = max(len(segment_path) - 1, 0)
        commit_remaining, commit_policy = _policy_commit_window(
            policy_name=policy_name,
            planned_segment_length=planned_segment_length,
            search_commit_window=4,
            search_commit_max_window=10,
            search_commit_path_divisor=2,
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

    # Get next planned grid step (segment_path[0] is current, segment_path[1] is next target)
    segment_path_list = state["committed_segment"]
    if len(segment_path_list) <= 1:
        raise ValueError(
            f"CRITICAL ERROR: Committed path segment length too short ({len(segment_path_list)}) for closed-loop execution."
        )

    next_cell = tuple(int(v) for v in segment_path_list[1])
    
    # Store decision records in state for auditing
    state["_audit_plan_details"] = plan_details
    state["_audit_replanned"] = replanned_this_step
    state["_audit_replan_reason"] = replan_reason
    state["_audit_commit_remaining"] = commit_remaining
    state["_audit_path_length_current"] = path_length_current
    state["_audit_fraction_before_replan"] = fraction_before_replan

    return next_cell, list(segment_path_list), commit_remaining, plan_details


def finalize_policy_step_after_holoocean(
    state: Dict[str, Any],
    step: int,
    robot_pos_before: Tuple[int, int],
    next_cell: Tuple[int, int],
    final_projected_cell: Tuple[int, int],
    collision_this_step: bool = False,
    collision_cell: Optional[Tuple[int, int]] = None,
    gp_fit_every: int = 5,
    staleness_tau_steps: int = 12,
) -> Dict[str, Any]:
    """Execute status tracking and target belief/GP suspicion updates after simulator execution.

    Keeps state changes identical to the baseline search runner.
    Identical to baseline_GP runtime main loop (marine_knownmap_runtime.py: L2818-2932).
    """
    # 1. Verify Chebyshev distance limit is satisfied to prevent manual waypoint drift
    dx = abs(final_projected_cell[0] - next_cell[0])
    dy = abs(final_projected_cell[1] - next_cell[1])
    chebyshev_dist = max(dx, dy)
    if chebyshev_dist > 1:
        raise ValueError(
            f"CRITICAL DRIFT EXCEEDED: Chebyshev distance from projected {final_projected_cell} "
            f"to algorithm targeted next_cell {next_cell} is {chebyshev_dist} (> 1)."
        )

    # 2. Update search position state
    state["robot_pos"] = final_projected_cell
    state["committed_segment"] = state["committed_segment"][1:]
    state["path_length"] += 1
    state["trajectory"].append(state["robot_pos"])
    state["steps_since_replan"] += 1
    state["last_move_dir"] = move_direction(robot_pos_before, state["robot_pos"])

    if _semantic_anchor_source(state.get("last_anchor_source")):
        state["same_anchor_steps"] += 1
    else:
        state["same_anchor_steps"] = 0

    # 3. Telemetry and last_seen updates
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

    # 4. Target miss/hit detection & intensity maps
    predicted_intensity = apply_known_occupancy_constraints(
        state["intensity_map"],
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
        state["time_since_last_detection"] += 1
        state["intensity_map"] = miss_update_intensity(
            predicted_intensity,
            state["robot_pos"],
            state["sensor_range_cells"],
            known_map=state["nav_map_prior"],
            preserve_total_mass=True,
            target_total_mass=remaining_target_mass_before,
        )

    # 5. GPSuspicionField sampling & GP updates
    _sample_and_update_gp(state, step=step, gp_fit_every=gp_fit_every)
    _update_search_info_state(state, state["intensity_map"])
    _append_anomaly_target_neighborhood_metric(state, step=step)

    # 6. Save tracking curve values
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

    # 7. Record native trace logs
    replanned_this_step = state.get("_audit_replanned", False)
    replan_reason = state.get("_audit_replan_reason")
    commit_remaining = state.get("_audit_commit_remaining", 0)
    path_length_current = state.get("_audit_path_length_current", 0)
    fraction_before_replan = state.get("_audit_fraction_before_replan", 0.0)
    plan_details = state.get("_audit_plan_details", {})

    state["trace_rows"].append(
        _trace_row(
            step=step,
            state=state,
            policy_name=plan_details.get("policy_name", "marine_knownmap_path_v2_infosampled"),
            replanned_this_step=replanned_this_step,
            replan_reason=replan_reason,
            commit_remaining=commit_remaining,
            path_length_current=path_length_current,
            fraction_before_replan=fraction_before_replan,
            plan_details=plan_details,
            detected_count_this_step=detected_count_this_step,
            collision_this_step=collision_this_step,
            collision_cell=collision_cell,
            effective_observation_gain=effective_observation_gain,
            stale_refresh_ratio=stale_refresh_ratio,
        )
    )


    return state
