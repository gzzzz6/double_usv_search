"""Phase 5C-1: dual-USV static-target runtime-only multistep probe.

This script does not start HoloOcean. It mirrors the core multistep loop in
marine_knownmap_runtime_2usv.py and exports phase-local telemetry for audit.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.marine_knownmap_runtime_2usv import (  # noqa: E402
    FREE,
    _append_anomaly_target_neighborhood_metric,
    _append_trimmed,
    _apply_joint_assignment_to_locals,
    _apply_team_miss_updates,
    _init_two_usv_knownmap_state,
    _joint_assign_two_usv_segments,
    _local_trace_row,
    _observation_progress_for_robot,
    _remaining_target_intensity_mass,
    _resolve_execution_conflict,
    _sample_and_update_team_gp,
    _team_trace_row,
    _update_local_after_execution,
    _update_team_search_info_state,
    apply_known_occupancy_constraints,
    build_staleness_map,
    detect_targets,
    execute_next_step,
    hit_update_intensity,
    known_free_observation_ratio,
    peak_intensity_ratio,
    predict_intensity,
    refresh_last_seen,
    remaining_intensity_mass,
    step_targets,
    update_found_mask,
)


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c1_res10_dual_usv_static_runtime_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
SCRIPT_PATH = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "dual_usv_static_runtime_multistep_probe.py"))
RUNTIME_FILE = os.path.normpath(os.path.join(BASE_DIR, "marine_knownmap_runtime_2usv.py"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_config.json"))
TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_trace.json"))
TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_trace.csv"))
FOUND_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_found_events.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "dual_usv_static_runtime_multistep_summary.md"))


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    return obj


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(data), f, indent=2)
    print("JSON saved to: {0}".format(path))


def _flatten_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set, np.ndarray)):
        return json.dumps(_json_safe(value), sort_keys=True)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    return value


def _save_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten_for_csv(row.get(key)) for key in keys})
    print("CSV saved to: {0}".format(path))


def _run_git_status() -> List[str]:
    repo_root = os.path.abspath(".")
    result = subprocess.run(
        ["git", "-c", "safe.directory={0}".format(repo_root.replace("\\", "/")), "status", "--porcelain"],
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if result.stderr.strip():
        lines.append("STDERR: {0}".format(result.stderr.strip()))
    return lines


def _phase_config() -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "policy_name": "marine_knownmap_path_v2_infosampled_2usv",
        "assignment_mode": "coordinated",
        "target_motion_mode": "static",
        "map_kind": "open_water",
        "map_height_cells": 81,
        "map_width_cells": 81,
        "resolution_m": 10.0,
        "sensor_range_m": 50.0,
        "sensor_range_cells": 5,
        "min_target_separation_m": 60.0,
        "min_start_distance_m": 80.0,
        "gp_length_scale_m": 40.0,
        "viewpoint_generation_mode": "simple_ring_v1",
        "path_safety_mode": "soft_clearance_astar_v1",
        "team_path_avoidance_mode": "reservation_v1",
        "team_reservation_safety_distance_cells": 1.5,
        "episode_seed": 0,
        "n_targets": 1,
        "max_steps": 240,
        "gp_noise_std": 0.03,
        "gp_prior_mean": 0.0,
        "gp_beta": 0.5,
        "gp_optimize_hyperparams": False,
        "clue_amplitude": 2.0,
        "clue_noise_std": 0.03,
        "clue_sigma_m": 30.0,
        "target_count_upper_bound": 1,
        "staleness_tau_steps": 12,
        "search_info_clue_weight": 0.5,
        "search_info_intensity_weight": 0.5,
        "clue_acquisition_mode": "ucb",
        "anomaly_tail_quantile": 0.90,
        "anomaly_weight_lambda": 1.0,
        "anomaly_warmup_steps": 20,
        "anomaly_min_gp_points": 64,
        "anomaly_top_quantile": 0.90,
        "anomaly_top_mass_min": 0.18,
        "anomaly_entropy_max": 0.85,
        "anomaly_stability_min": 0.30,
        "anomaly_alpha_max": 0.40,
        "anomaly_pre_first_alpha_cap": 0.15,
        "safe_nav_inflation_radius_cells": 0,
        "safe_nav_soft_clearance_radius_cells": 1,
        "safe_nav_lambda_clearance": 1.0,
        "team_reservation_lambda": 1.0,
        "constraint_mode": "hard",
        "r_hit": 1,
        "clue_samples_per_step": 24,
        "search_commit_window": 4,
        "search_commit_max_window": 10,
        "search_commit_path_divisor": 2,
        "initial_robot_positions": [[25, 2], [35, 2]],
        "runtime_file": RUNTIME_FILE,
        "runtime_file_mtime": os.path.getmtime(RUNTIME_FILE) if os.path.exists(RUNTIME_FILE) else None,
    }


def _initialize_state(config: Dict[str, Any]) -> Dict[str, Any]:
    state = _init_two_usv_knownmap_state(
        episode_seed=int(config["episode_seed"]),
        n_targets=int(config["n_targets"]),
        map_kind=str(config["map_kind"]),
        target_motion_mode=str(config["target_motion_mode"]),
        target_count_upper_bound=int(config["target_count_upper_bound"]),
        staleness_tau_steps=int(config["staleness_tau_steps"]),
        resolution_m=float(config["resolution_m"]),
        sensor_range_m=float(config["sensor_range_m"]),
        min_target_separation_m=float(config["min_target_separation_m"]),
        min_start_distance_m=float(config["min_start_distance_m"]),
        gp_length_scale_m=float(config["gp_length_scale_m"]),
        gp_noise_std=float(config["gp_noise_std"]),
        gp_prior_mean=float(config["gp_prior_mean"]),
        gp_beta=float(config["gp_beta"]),
        gp_optimize_hyperparams=bool(config["gp_optimize_hyperparams"]),
        clue_sigma_m=float(config["clue_sigma_m"]),
        clue_amplitude=float(config["clue_amplitude"]),
        clue_noise_std=float(config["clue_noise_std"]),
        map_height_cells=int(config["map_height_cells"]),
        map_width_cells=int(config["map_width_cells"]),
        search_info_clue_weight=float(config["search_info_clue_weight"]),
        search_info_intensity_weight=float(config["search_info_intensity_weight"]),
        clue_acquisition_mode=str(config["clue_acquisition_mode"]),
        anomaly_tail_quantile=float(config["anomaly_tail_quantile"]),
        anomaly_weight_lambda=float(config["anomaly_weight_lambda"]),
        anomaly_warmup_steps=int(config["anomaly_warmup_steps"]),
        anomaly_min_gp_points=int(config["anomaly_min_gp_points"]),
        anomaly_top_quantile=float(config["anomaly_top_quantile"]),
        anomaly_top_mass_min=float(config["anomaly_top_mass_min"]),
        anomaly_entropy_max=float(config["anomaly_entropy_max"]),
        anomaly_stability_min=float(config["anomaly_stability_min"]),
        anomaly_alpha_max=float(config["anomaly_alpha_max"]),
        anomaly_pre_first_alpha_cap=float(config["anomaly_pre_first_alpha_cap"]),
        path_safety_mode=str(config["path_safety_mode"]),
        safe_nav_inflation_radius_cells=int(config["safe_nav_inflation_radius_cells"]),
        safe_nav_soft_clearance_radius_cells=int(config["safe_nav_soft_clearance_radius_cells"]),
        safe_nav_lambda_clearance=float(config["safe_nav_lambda_clearance"]),
        team_path_avoidance_mode=str(config["team_path_avoidance_mode"]),
        team_reservation_safety_distance_cells=float(config["team_reservation_safety_distance_cells"]),
        team_reservation_lambda=float(config["team_reservation_lambda"]),
        constraint_mode=str(config["constraint_mode"]),
        r_hit=int(config["r_hit"]),
        clue_samples_per_step=int(config["clue_samples_per_step"]),
    )

    state["gp_max_points"] = 400
    state["lambda_u_turn"] = 2.0
    state["gamma"] = 0.95
    state["segment_horizon"] = 8
    state["top_k_anchors"] = 6
    state["viewpoints_per_anchor"] = 6
    state["infosampled_inspected_limit_multiplier"] = 3.0
    state["infosampled_inspected_limit_floor"] = 4
    state["viewpoint_generation_mode"] = str(config["viewpoint_generation_mode"])
    state["assignment_mode"] = str(config["assignment_mode"])
    state["planner_adaptation_mode"] = "adaptive"
    return state


def _gp_observation_counts(state: Dict[str, Any]) -> Dict[str, Any]:
    gp_field = state.get("gp_field")
    if gp_field is None:
        return {"gp_n_obs": None, "gp_x_obs_len": None, "gp_y_obs_len": None, "gp_count_consistent": False}
    n_obs = getattr(gp_field, "n_obs", None)
    x_obs = getattr(gp_field, "X_obs", None)
    y_obs = getattr(gp_field, "y_obs", None)
    x_len = None if x_obs is None else int(len(x_obs))
    y_len = None if y_obs is None else int(len(y_obs))
    n_value = None if n_obs is None else int(n_obs)
    return {
        "gp_n_obs": n_value,
        "gp_x_obs_len": x_len,
        "gp_y_obs_len": y_len,
        "gp_count_consistent": bool(n_value is not None and x_len == n_value and y_len == n_value),
    }


def _search_info_stats(state: Dict[str, Any]) -> Dict[str, Any]:
    search_info = np.asarray(state["search_info_map"], dtype=float)
    nav_map = np.asarray(state["nav_map_prior"])
    free_mask = nav_map == FREE
    free_values = search_info[free_mask]
    valid_values = free_values[np.isfinite(free_values)]
    return {
        "search_info_shape": list(search_info.shape),
        "search_info_expected_shape": list(nav_map.shape),
        "search_info_has_nan": bool(np.isnan(search_info).any()),
        "search_info_free_valid_count": int(valid_values.size),
        "search_info_map_peak": float(state.get("search_info_map_peak", 0.0)),
        "search_info_map_mean": float(state.get("search_info_map_mean", 0.0)),
        "search_info_shape_ok": bool(search_info.shape == nav_map.shape),
        "search_info_valid": bool(search_info.shape == nav_map.shape and not np.isnan(search_info).any() and valid_values.size > 0),
    }


def _exec_result_record(exec_result: Any) -> Dict[str, Any]:
    if exec_result is None:
        return {
            "exec_result_present": False,
            "exec_move_success": False,
            "exec_collision": False,
            "exec_collision_cell": None,
            "exec_new_robot_pos": None,
        }
    return {
        "exec_result_present": True,
        "exec_move_success": bool(getattr(exec_result, "move_success", False)),
        "exec_collision": bool(getattr(exec_result, "collision", False)),
        "exec_collision_cell": _json_safe(getattr(exec_result, "collision_cell", None)),
        "exec_new_robot_pos": _json_safe(getattr(exec_result, "new_robot_pos", None)),
    }


def _build_summary_md(config: Dict[str, Any], found_events: Dict[str, Any], trace_rows: List[Dict[str, Any]]) -> str:
    return """# Phase 5C-1 Runtime-Only Multistep Probe Summary

## Configuration
- Policy: `{policy}`
- Assignment: `{assignment}`
- Target Motion: `{motion}`
- Map: `{height}x{width}` at `{resolution}` m
- Episode Seed: `{seed}`
- Max Steps: `{max_steps}`

## Result
- Terminated Reason: `{terminated}`
- Initial All Found: `{initial_all_found}`
- Completed Steps: `{completed_steps}`
- Final Found Count: `{found_final}`
- Hit Branch Covered: `{hit_covered}`
- GP n_obs Initial/Final: `{gp_initial}` -> `{gp_final}`
- Trace Rows: `{trace_count}`

## Notes
- Runtime-only probe: no HoloOcean import or env control calls.
- The step loop mirrors `marine_knownmap_runtime_2usv.py` step_targets -> predict_intensity -> assignment -> execute_next_step -> team belief update.
""".format(
        policy=config["policy_name"],
        assignment=config["assignment_mode"],
        motion=config["target_motion_mode"],
        height=config["map_height_cells"],
        width=config["map_width_cells"],
        resolution=config["resolution_m"],
        seed=config["episode_seed"],
        max_steps=config["max_steps"],
        terminated=found_events["terminated_reason"],
        initial_all_found=found_events["initial_all_found"],
        completed_steps=found_events["completed_steps"],
        found_final=found_events["found_count_final"],
        hit_covered=found_events["hit_branch_covered"],
        gp_initial=found_events["gp_n_obs_initial"],
        gp_final=found_events["gp_n_obs_final"],
        trace_count=len(trace_rows),
    )


def run_probe() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    config = _phase_config()
    state = _initialize_state(config)

    initial_gp_counts = _gp_observation_counts(state)
    initial_found_count = int(state["found_mask"].sum())
    initial_all_found = bool(np.all(state["found_mask"]))
    initial_target_positions = _json_safe(state["target_positions"])
    initial_robot_positions = [list(local["robot_pos"]) for local in state["usv_states"]]
    initial_find_times = _json_safe(state["find_times"])
    trace_rows: List[Dict[str, Any]] = []
    hit_branch_covered = False
    terminated_reason = "initial_all_found" if initial_all_found else "max_steps"

    if initial_all_found:
        state["terminated_reason"] = "all_found"
    else:
        for step in range(1, int(config["max_steps"]) + 1):
            step_start = time.perf_counter()
            target_positions_before = np.array(state["target_positions"], dtype=int, copy=True)
            state["target_positions"] = step_targets(
                state["target_positions"],
                motion_mode=str(config["target_motion_mode"]),
                occ_grid=state["true_map"],
                rng=state["scenario_rng"],
                found_mask=state["found_mask"],
            )
            target_positions_after = np.array(state["target_positions"], dtype=int, copy=True)
            target_positions_static = bool(np.array_equal(target_positions_before, target_positions_after))
            predicted_intensity = predict_intensity(
                state["intensity_map"],
                state["nav_map_prior"],
                motion_mode=str(config["target_motion_mode"]),
            )

            t0 = time.perf_counter()
            assignments, joint_summary = _joint_assign_two_usv_segments(
                team_state=state,
                policy_name=str(config["policy_name"]),
                predicted_intensity=predicted_intensity,
                step=step,
            )
            joint_summary["clue_acquisition_mode"] = str(state.get("clue_acquisition_mode", "ucb"))
            anomaly_conditional_diag = {
                "anomaly_conditional_alpha": float(state.get("anomaly_conditional_alpha", 0.0)),
                "anomaly_conditional_triggered": bool(state.get("anomaly_conditional_triggered", False)),
                "anomaly_gate_reason": str(state.get("anomaly_gate_reason", "mode_not_conditional")),
                "anomaly_top_mass_ratio": float(state.get("anomaly_top_mass_ratio", 0.0)),
                "anomaly_entropy_norm": float(state.get("anomaly_entropy_norm", 0.0)),
                "anomaly_hotspot_stability": float(state.get("anomaly_hotspot_stability", 1.0)),
                "anomaly_pre_first_alpha_capped": bool(state.get("anomaly_pre_first_alpha_capped", False)),
            }
            joint_summary.update(anomaly_conditional_diag)
            for assignment in assignments.values():
                assignment["plan_details"].update(anomaly_conditional_diag)
            _apply_joint_assignment_to_locals(
                state,
                str(config["policy_name"]),
                assignments,
                search_commit_window=int(config["search_commit_window"]),
                search_commit_max_window=int(config["search_commit_max_window"]),
                search_commit_path_divisor=int(config["search_commit_path_divisor"]),
            )
            planning_time_ms = (time.perf_counter() - t0) * 1000.0
            state["planning_time_ms"].append(planning_time_ms)

            wait_applied_map, conflict_type, conflict_penalty = _resolve_execution_conflict(
                state,
                assignments,
                safety_distance_cells=float(config["team_reservation_safety_distance_cells"]),
            )

            local_before = {}
            exec_results = {}
            local_observation_terms: Dict[int, Tuple[float, float]] = {}
            for usv_id, local in enumerate(state["usv_states"]):
                local_before[usv_id] = {
                    "robot_pos": list(local["robot_pos"]),
                    "commit_remaining": int(local.get("commit_remaining", 0)),
                    "committed_segment": [list(c) for c in local.get("committed_segment", [])],
                }
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
                _update_local_after_execution(local, wait_applied_map[usv_id], exec_results[usv_id])

            local_after = {}
            for usv_id, local in enumerate(state["usv_states"]):
                local_after[usv_id] = {
                    "robot_pos": list(local["robot_pos"]),
                    "commit_remaining": int(local.get("commit_remaining", 0)),
                    "committed_segment": [list(c) for c in local.get("committed_segment", [])],
                }

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
                tau_stale=int(config["staleness_tau_steps"]),
            )

            predicted_intensity = apply_known_occupancy_constraints(
                predicted_intensity,
                state["nav_map_prior"],
                preserve_mass=True,
            )
            remaining_target_mass_before = _remaining_target_intensity_mass(state)
            team_detected_mask = np.zeros_like(state["found_mask"], dtype=bool)
            detected_by_usv = {0: 0, 1: 0}
            detection_masks_by_usv = {}
            for usv_id, local in enumerate(state["usv_states"]):
                detected_mask = detect_targets(
                    local["robot_pos"],
                    state["target_positions"],
                    state["found_mask"],
                    state["sensor_range_cells"],
                    state["detection_rng"],
                )
                detection_masks_by_usv[usv_id] = _json_safe(detected_mask)
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
            hit_update_applied = False
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
                hit_update_applied = True
                hit_branch_covered = True
            state["intensity_map"] = updated_intensity
            _sample_and_update_team_gp(state, step=step, gp_fit_every=5)
            _update_team_search_info_state(state, state["intensity_map"])
            _append_anomaly_target_neighborhood_metric(state, step=step)

            found_count_after = int(state["found_mask"].sum())
            remaining_mass_after = remaining_intensity_mass(state["intensity_map"])
            peak_ratio_after = peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
            state["found_count_curve"].append(found_count_after)
            state["remaining_intensity_mass_curve"].append(remaining_mass_after)
            state["peak_intensity_ratio_curve"].append(peak_ratio_after)
            state["known_free_observation_ratio_curve"].append(
                known_free_observation_ratio(state["last_seen_step"], state["nav_map_prior"])
            )
            state["completed_steps"] = step

            team_row = _team_trace_row(
                team_step=step,
                assignments=assignments,
                joint_summary=joint_summary,
                conflict_type=conflict_type,
                conflict_penalty=conflict_penalty,
                wait_applied_map=wait_applied_map,
                team_detected_count=team_detected_count,
            )
            state["team_trace_rows"].append(team_row)

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

            gp_counts = _gp_observation_counts(state)
            search_stats = _search_info_stats(state)
            exec_records = {str(usv_id): _exec_result_record(exec_results[usv_id]) for usv_id in exec_results}
            step_record = {
                "step": int(step),
                "step_targets_called": True,
                "target_motion_mode": str(config["target_motion_mode"]),
                "target_positions_before_step_targets": _json_safe(target_positions_before),
                "target_positions_after_step_targets": _json_safe(target_positions_after),
                "target_positions_static_after_step_targets": target_positions_static,
                "predict_intensity_called": True,
                "joint_assignment_called": True,
                "assignment_count": int(len(assignments)),
                "assignment_mode": str(config["assignment_mode"]),
                "apply_assignment_called": True,
                "resolve_conflict_called": True,
                "conflict_type": conflict_type,
                "conflict_penalty": float(conflict_penalty),
                "wait_applied_map": {str(k): bool(v) for k, v in wait_applied_map.items()},
                "execute_next_step_called_count": int(sum(1 for v in exec_results.values() if v is not None)),
                "local_update_called_count": int(len(state["usv_states"])),
                "local_before": local_before,
                "local_after": local_after,
                "exec_results": exec_records,
                "last_seen_refreshed": True,
                "staleness_rebuilt": True,
                "apply_known_occupancy_constraints_called": True,
                "remaining_target_mass_before": float(remaining_target_mass_before),
                "detect_targets_called": True,
                "detected_by_usv": {str(k): int(v) for k, v in detected_by_usv.items()},
                "detection_masks_by_usv": detection_masks_by_usv,
                "team_detected_mask": _json_safe(team_detected_mask),
                "update_found_mask_called": True,
                "new_found_indices": [int(v) for v in new_indices],
                "team_detected_count": int(team_detected_count),
                "team_miss_update_called": True,
                "hit_update_called": hit_update_applied,
                "team_gp_update_called": True,
                "team_search_info_update_called": True,
                "team_trace_row_written": True,
                "local_trace_rows_written": 2,
                "found_count_after": found_count_after,
                "found_mask_after": _json_safe(state["found_mask"]),
                "find_times_after": _json_safe(state["find_times"]),
                "remaining_intensity_mass_after": float(remaining_mass_after),
                "peak_intensity_ratio_after": float(peak_ratio_after),
                "known_free_observation_ratio_after": float(state["known_free_observation_ratio_curve"][-1]),
                "planning_time_ms": float(planning_time_ms),
                "step_elapsed_ms": float((time.perf_counter() - step_start) * 1000.0),
            }
            step_record.update(gp_counts)
            step_record.update(search_stats)
            trace_rows.append(step_record)

            if np.all(state["found_mask"]):
                state["terminated_reason"] = "all_found"
                terminated_reason = "all_found"
                break
        else:
            state["completed_steps"] = int(config["max_steps"])
            state["terminated_reason"] = "max_steps"
            terminated_reason = "max_steps"

    final_gp_counts = _gp_observation_counts(state)
    found_count_final = int(state["found_mask"].sum())
    found_events = {
        "phase_name": PHASE_NAME,
        "initial_found_count": initial_found_count,
        "initial_all_found": initial_all_found,
        "initial_target_positions": initial_target_positions,
        "initial_robot_positions": initial_robot_positions,
        "initial_find_times": initial_find_times,
        "terminated_reason": terminated_reason,
        "completed_steps": int(state.get("completed_steps", 0)),
        "max_steps": int(config["max_steps"]),
        "found_count_final": found_count_final,
        "found_mask_final": _json_safe(state["found_mask"]),
        "find_times_final": _json_safe(state["find_times"]),
        "hit_branch_covered": bool(hit_branch_covered),
        "remaining_intensity_mass_final": float(remaining_intensity_mass(state["intensity_map"])),
        "peak_intensity_ratio_final": float(peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])),
        "known_free_observation_ratio_final": float(state["known_free_observation_ratio_curve"][-1]),
        "gp_n_obs_initial": initial_gp_counts["gp_n_obs"],
        "gp_n_obs_final": final_gp_counts["gp_n_obs"],
        "gp_x_obs_len_final": final_gp_counts["gp_x_obs_len"],
        "gp_y_obs_len_final": final_gp_counts["gp_y_obs_len"],
        "gp_count_consistent_final": final_gp_counts["gp_count_consistent"],
        "runtime_team_trace_rows_count": int(len(state.get("team_trace_rows", []))),
        "runtime_local_trace_rows_count": int(len(state.get("trace_rows", []))),
        "wall_time_s": float(time.perf_counter() - started),
    }

    _save_json(CONFIG_JSON, config)
    _save_json(TRACE_JSON, trace_rows)
    _save_csv(TRACE_CSV, trace_rows)
    _save_json(FOUND_JSON, found_events)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(config, found_events, trace_rows))
    print("Summary saved to: {0}".format(SUMMARY_MD))

    post_git_status = _run_git_status()
    git_status = {
        "pre_git_status": pre_git_status,
        "post_git_status": post_git_status,
        "phase_dir": PHASE_DIR.replace("\\", "/"),
    }
    _save_json(GIT_STATUS_JSON, git_status)

    return {
        "config": config,
        "trace_rows": trace_rows,
        "found_events": found_events,
        "git_status": git_status,
    }


def main() -> None:
    print("=== Phase 5C-1: dual-USV static runtime-only multistep probe ===")
    result = run_probe()
    found_events = result["found_events"]
    print("Completed steps: {0}".format(found_events["completed_steps"]))
    print("Terminated reason: {0}".format(found_events["terminated_reason"]))
    print("Found final: {0}".format(found_events["found_count_final"]))
    print("Hit branch covered: {0}".format(found_events["hit_branch_covered"]))
    print("GP n_obs final: {0}".format(found_events["gp_n_obs_final"]))


if __name__ == "__main__":
    main()
