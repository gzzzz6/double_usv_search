"""Phase 5C-3 visual-only runner for dual-USV static-target HoloOcean all_found.

This visual variant keeps the audited Phase 5C-3 search/control chain intact,
but adds a main agent and RGB cameras so the HoloOcean viewport can follow and
switch between USV viewpoints. Camera output is not used for target detection.
"""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.core_execution import ExecutionStepResult  # noqa: E402
from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid  # noqa: E402
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec  # noqa: E402
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
PHASE_NAME = "phase5c3_res10_dual_usv_static_holoocean_allfound_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))
RUNTIME_FILE = os.path.normpath(os.path.join(BASE_DIR, "marine_knownmap_runtime_2usv.py"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_config.json"))
POLICY_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_policy_trace.json"))
POLICY_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_policy_trace.csv"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_tick_trace.csv"))
FOUND_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_found_events.json"))
SENSOR_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_sensor_sources.json"))
COLLISION_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_collision_metrics.json"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "visual_dual_usv_static_holoocean_allfound_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "visual_dual_usv_static_holoocean_allfound_summary.md"))
PATHS_PNG = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "visual_dual_usv_static_holoocean_allfound_paths.png"))

MAX_FORCE = 8000.0
MIN_FORCE = 1500.0
TURN_GAIN = 0.8
DIST_SLOW_RADIUS_M = 12.0
ARRIVAL_RADIUS_M = 5.0
MAX_TICKS_PER_ONE_STEP = 500
COLLISION_WARNING_M = 30.0
COLLISION_FAIL_M = 20.0
MAX_POLICY_STEPS = 40
EXPECTED_RUNTIME_ALL_FOUND_STEP = 32
EXPECTED_INITIAL_TARGET_POSITIONS = [[23, 21]]
VISUAL_CAMERA_NAME = "FrontRGBCamera"
VISUAL_CAMERA_WIDTH = 320
VISUAL_CAMERA_HEIGHT = 240
VISUAL_CAMERA_HZ = 5


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


def _status_path(line: str) -> str:
    if line.startswith("?? "):
        return line[3:].strip().strip('"')
    if len(line) > 3:
        return line[3:].strip().strip('"')
    return line.strip().strip('"')


def _outside_phase_new_or_changed(pre_status: List[str], post_status: List[str]) -> List[str]:
    pre_set = set(pre_status)
    phase_prefix = "baseline_GP/results/holoocean_bridge_v1/{0}/".format(PHASE_NAME)
    outside: List[str] = []
    for line in post_status:
        path = _status_path(line).replace("\\", "/")
        if path.startswith(phase_prefix):
            continue
        if line not in pre_set:
            outside.append(line)
    return outside


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
        "max_policy_steps": MAX_POLICY_STEPS,
        "expected_runtime_all_found_step": EXPECTED_RUNTIME_ALL_FOUND_STEP,
        "expected_initial_target_positions": EXPECTED_INITIAL_TARGET_POSITIONS,
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
        "map_npz": MAP_NPZ,
        "arrival_radius_m": ARRIVAL_RADIUS_M,
        "max_ticks_per_one_step": MAX_TICKS_PER_ONE_STEP,
        "collision_warning_m": COLLISION_WARNING_M,
        "collision_fail_m": COLLISION_FAIL_M,
        "scenario_agent_names": ["sv0", "sv1"],
        "scenario_main_agent": "sv0",
        "scenario_sensor_types": ["GPSSensor", "LocationSensor", "OrientationSensor", "RGBCamera"],
        "visual_only_runner": True,
        "visual_camera_name": VISUAL_CAMERA_NAME,
        "visual_camera_width": VISUAL_CAMERA_WIDTH,
        "visual_camera_height": VISUAL_CAMERA_HEIGHT,
        "visual_camera_hz": VISUAL_CAMERA_HZ,
        "visual_camera_used_for_detection": False,
        "holo_world": "OpenWater",
        "holo_package": "Ocean",
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


def compute_controller_cmd(
    tx: float,
    ty: float,
    curr_pos: List[float],
    orient_sensor: Optional[np.ndarray],
) -> Tuple[float, float, float, float, float, float]:
    dx = tx - curr_pos[0]
    dy = ty - curr_pos[1]
    dist = math.hypot(dx, dy)
    target_heading_deg = np.degrees(np.arctan2(dy, dx)) % 360.0

    heading_deg = 0.0
    if orient_sensor is not None:
        r_matrix = np.reshape(orient_sensor, (3, 3))
        forward = r_matrix[:, 0]
        heading_deg = np.degrees(np.arctan2(forward[1], forward[0])) % 360.0

    heading_error_deg = (target_heading_deg - heading_deg + 180) % 360 - 180
    heading_error_rad = np.radians(heading_error_deg)
    turn = TURN_GAIN * heading_error_rad * MAX_FORCE

    if dist < DIST_SLOW_RADIUS_M:
        forward = MIN_FORCE + (MAX_FORCE - MIN_FORCE) * (dist / DIST_SLOW_RADIUS_M)
    else:
        forward = MAX_FORCE
    forward_factor = np.cos(heading_error_rad)
    if forward_factor < 0:
        forward_factor = 0.0
    forward *= forward_factor

    left_thrust = np.clip(forward - turn, -MAX_FORCE, MAX_FORCE)
    right_thrust = np.clip(forward + turn, -MAX_FORCE, MAX_FORCE)
    return float(left_thrust), float(right_thrust), float(dist), float(heading_deg), float(target_heading_deg), float(heading_error_deg)


def _select_sensor(state_env: Dict[str, Any], agent_name: str, last_known: List[float]) -> Dict[str, Any]:
    loc = get_sensor_vector(state_env, agent_name, "LocationSensor")
    gps = get_sensor_vector(state_env, agent_name, "GPSSensor")
    orient = get_sensor_vector(state_env, agent_name, "OrientationSensor")
    if loc is not None:
        selected_sensor = "LocationSensor"
        curr_pos = [float(loc[0]), float(loc[1]), float(loc[2])]
        fallback_used = False
    elif gps is not None:
        selected_sensor = "GPSSensor"
        curr_pos = [float(gps[0]), float(gps[1]), float(gps[2])]
        fallback_used = False
    else:
        selected_sensor = "last_known"
        curr_pos = [float(last_known[0]), float(last_known[1]), float(last_known[2])]
        fallback_used = True
    return {
        "selected_sensor": selected_sensor,
        "curr_pos": curr_pos,
        "orient": orient,
        "loc_avail": loc is not None,
        "gps_avail": gps is not None,
        "fallback_used": fallback_used,
    }


def _agent_key(usv_id: int) -> str:
    return "sv{0}".format(usv_id)


def _make_scenario_config(spec: Dict[str, Any], start_world: Dict[int, List[float]]) -> Dict[str, Any]:
    agents = []
    for usv_id in (0, 1):
        agents.append(
            {
                "agent_name": _agent_key(usv_id),
                "agent_type": "SurfaceVessel",
                "sensors": [
                    {"sensor_type": "GPSSensor", "socket": "COM"},
                    {"sensor_type": "LocationSensor", "socket": "COM"},
                    {"sensor_type": "OrientationSensor", "socket": "COM"},
                    {
                        "sensor_type": "RGBCamera",
                        "sensor_name": VISUAL_CAMERA_NAME,
                        "location": [0.0, 0.0, 4.0],
                        "rotation": [0.0, 0.0, 0.0],
                        "Hz": VISUAL_CAMERA_HZ,
                        "configuration": {
                            "CaptureWidth": VISUAL_CAMERA_WIDTH,
                            "CaptureHeight": VISUAL_CAMERA_HEIGHT,
                        },
                    },
                ],
                "control_scheme": 0,
                "location": start_world[usv_id],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    return {
        "name": "dual_usv_static_holoocean_allfound_probe_visual",
        "world": spec["world"],
        "package_name": spec["package_name"],
        "main_agent": "sv0",
        "agents": agents,
    }


def _physical_state(start_world: Dict[int, List[float]]) -> Dict[str, Any]:
    return {
        "last_known": {
            0: [float(v) for v in start_world[0]],
            1: [float(v) for v in start_world[1]],
        },
        "global_tick": 0,
        "sensor_counts": {
            0: {"LocationSensor": 0, "GPSSensor": 0, "last_known": 0},
            1: {"LocationSensor": 0, "GPSSensor": 0, "last_known": 0},
        },
        "fallback_counts": {0: 0, 1: 0},
        "min_inter_vessel_distance_m": 999999.0,
        "collision_warning_ticks": 0,
        "collision_fail_ticks": 0,
    }


def _drive_policy_step(
    env: Any,
    state_env: Dict[str, Any],
    adapter_config: Any,
    nav_map_prior: np.ndarray,
    phys_state: Dict[str, Any],
    policy_step: int,
    target_cells: Dict[int, Tuple[int, int]],
    wait_applied_map: Dict[int, bool],
    tick_trace: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    target_world = {}
    for usv_id in (0, 1):
        w = list(grid_to_world(target_cells[usv_id], config=adapter_config))
        target_world[usv_id] = [float(w[0]), float(w[1]), float(w[2])]

    arrived = {0: False, 1: False}
    final_sensor = {}
    final_proj = {0: None, 1: None}
    final_dist = {0: None, 1: None}
    timeout = False
    step_tick_count = 0
    per_step_fallback = {0: 0, 1: 0}
    per_step_sensor_counts = {
        0: {"LocationSensor": 0, "GPSSensor": 0, "last_known": 0},
        1: {"LocationSensor": 0, "GPSSensor": 0, "last_known": 0},
    }

    while not (arrived[0] and arrived[1]) and not timeout:
        selected = {}
        commands = {}
        for usv_id in (0, 1):
            agent = _agent_key(usv_id)
            selected[usv_id] = _select_sensor(state_env, agent, phys_state["last_known"][usv_id])
            phys_state["last_known"][usv_id] = selected[usv_id]["curr_pos"]
            sensor_key = selected[usv_id]["selected_sensor"]
            phys_state["sensor_counts"][usv_id][sensor_key] += 1
            per_step_sensor_counts[usv_id][sensor_key] += 1
            if selected[usv_id]["fallback_used"]:
                phys_state["fallback_counts"][usv_id] += 1
                per_step_fallback[usv_id] += 1

            tx = float(target_world[usv_id][0])
            ty = float(target_world[usv_id][1])
            cmd_l, cmd_r, dist, heading, target_heading, err = compute_controller_cmd(
                tx,
                ty,
                selected[usv_id]["curr_pos"],
                selected[usv_id]["orient"],
            )
            commands[usv_id] = {
                "cmd_l": cmd_l,
                "cmd_r": cmd_r,
                "dist": dist,
                "heading": heading,
                "target_heading": target_heading,
                "err": err,
            }

        env.act("sv0", np.array([commands[0]["cmd_l"], commands[0]["cmd_r"]], dtype=np.float32))
        env.act("sv1", np.array([commands[1]["cmd_l"], commands[1]["cmd_r"]], dtype=np.float32))
        state_env = env.tick()
        step_tick_count += 1
        phys_state["global_tick"] += 1

        proj = {}
        for usv_id in (0, 1):
            p = world_to_grid(
                phys_state["last_known"][usv_id],
                config=adapter_config,
                map_shape=nav_map_prior.shape,
                clamp=True,
            )
            proj[usv_id] = (int(p[0]), int(p[1]))
            final_proj[usv_id] = proj[usv_id]
            final_dist[usv_id] = float(commands[usv_id]["dist"])
            if commands[usv_id]["dist"] < ARRIVAL_RADIUS_M and proj[usv_id] == target_cells[usv_id]:
                arrived[usv_id] = True

        sep = math.hypot(
            phys_state["last_known"][0][0] - phys_state["last_known"][1][0],
            phys_state["last_known"][0][1] - phys_state["last_known"][1][1],
        )
        phys_state["min_inter_vessel_distance_m"] = min(float(phys_state["min_inter_vessel_distance_m"]), float(sep))
        if sep < COLLISION_WARNING_M:
            phys_state["collision_warning_ticks"] += 1
        if sep < COLLISION_FAIL_M:
            phys_state["collision_fail_ticks"] += 1

        tick_trace.append(
            {
                "policy_step": int(policy_step),
                "tick_in_policy_step": int(step_tick_count),
                "tick_global": int(phys_state["global_tick"]),
                "sv0_target_cell": list(target_cells[0]),
                "sv1_target_cell": list(target_cells[1]),
                "sv0_wait_applied": bool(wait_applied_map[0]),
                "sv1_wait_applied": bool(wait_applied_map[1]),
                "sv0_target_world": target_world[0],
                "sv1_target_world": target_world[1],
                "sv0_loc_x": float(phys_state["last_known"][0][0]),
                "sv0_loc_y": float(phys_state["last_known"][0][1]),
                "sv0_loc_z": float(phys_state["last_known"][0][2]),
                "sv0_proj_row": int(proj[0][0]),
                "sv0_proj_col": int(proj[0][1]),
                "sv0_dist_m": float(commands[0]["dist"]),
                "sv0_heading_deg": float(commands[0]["heading"]),
                "sv0_target_heading_deg": float(commands[0]["target_heading"]),
                "sv0_heading_error_deg": float(commands[0]["err"]),
                "sv0_cmd_l": float(commands[0]["cmd_l"]),
                "sv0_cmd_r": float(commands[0]["cmd_r"]),
                "sv0_arrived": bool(arrived[0]),
                "sv0_loc_avail": bool(selected[0]["loc_avail"]),
                "sv0_gps_avail": bool(selected[0]["gps_avail"]),
                "sv0_selected_sensor": selected[0]["selected_sensor"],
                "sv1_loc_x": float(phys_state["last_known"][1][0]),
                "sv1_loc_y": float(phys_state["last_known"][1][1]),
                "sv1_loc_z": float(phys_state["last_known"][1][2]),
                "sv1_proj_row": int(proj[1][0]),
                "sv1_proj_col": int(proj[1][1]),
                "sv1_dist_m": float(commands[1]["dist"]),
                "sv1_heading_deg": float(commands[1]["heading"]),
                "sv1_target_heading_deg": float(commands[1]["target_heading"]),
                "sv1_heading_error_deg": float(commands[1]["err"]),
                "sv1_cmd_l": float(commands[1]["cmd_l"]),
                "sv1_cmd_r": float(commands[1]["cmd_r"]),
                "sv1_arrived": bool(arrived[1]),
                "sv1_loc_avail": bool(selected[1]["loc_avail"]),
                "sv1_gps_avail": bool(selected[1]["gps_avail"]),
                "sv1_selected_sensor": selected[1]["selected_sensor"],
                "inter_vessel_distance_m": float(sep),
            }
        )

        if step_tick_count >= MAX_TICKS_PER_ONE_STEP and not (arrived[0] and arrived[1]):
            timeout = True

    for usv_id in (0, 1):
        final_sensor[usv_id] = {
            "last_known_world": list(phys_state["last_known"][usv_id]),
            "final_projected_cell": None if final_proj[usv_id] is None else list(final_proj[usv_id]),
            "final_distance_to_target_m": final_dist[usv_id],
            "arrived": bool(arrived[usv_id]),
            "target_cell": list(target_cells[usv_id]),
            "projection_matches_target": bool(final_proj[usv_id] == target_cells[usv_id]),
        }

    return state_env, {
        "policy_step": int(policy_step),
        "step_ticks": int(step_tick_count),
        "timeout": bool(timeout),
        "arrived": {str(k): bool(v) for k, v in arrived.items()},
        "target_cells": {str(k): list(v) for k, v in target_cells.items()},
        "target_world": {str(k): list(v) for k, v in target_world.items()},
        "per_step_sensor_counts": {str(k): v for k, v in per_step_sensor_counts.items()},
        "per_step_fallback_counts": {str(k): int(v) for k, v in per_step_fallback.items()},
        "final_by_usv": {str(k): v for k, v in final_sensor.items()},
        "step_min_inter_vessel_distance_m": float(
            min([row["inter_vessel_distance_m"] for row in tick_trace if row["policy_step"] == policy_step] or [999999.0])
        ),
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    return """# Phase 5C-3 HoloOcean All Found Visual Runner Summary

## Configuration
- Policy: `{policy}`
- Assignment: `{assignment}`
- Target Motion: `{motion}`
- Map: `{height}x{width}` at `{resolution}` m
- Episode Seed: `{seed}`
- Max Policy Steps: `{max_policy_steps}`
- Expected Runtime All Found Step: `{expected_step}`
- Main Agent: `{main_agent}`
- Visual Camera: `{camera_name}` (`{camera_width}x{camera_height}` at `{camera_hz}` Hz)
- Visual Camera Used For Detection: `{camera_for_detection}`

## Result
- Terminated Reason: `{terminated}`
- Completed Policy Steps: `{completed_steps}`
- Total Physical Ticks: `{total_ticks}`
- Initial All Found: `{initial_all_found}`
- Final Found Count: `{found_final}`
- Hit Branch Covered: `{hit_covered}`
- GP n_obs Initial/Final: `{gp_initial}` -> `{gp_final}`
- Min Inter-Vessel Distance: `{min_sep:.2f}` m
- Fallback Count Total: `{fallback_total}`

## Notes
- This is a visual-only runner derived from Phase 5C-3.
- The original Phase 5C-3 audited outputs are not overwritten by this script.
- Use `H`, `Tab`, `C`, and `V` in the HoloOcean viewport to inspect agents and camera modes.
- This probe requires the static target hit branch and all_found termination.
- Runtime state movement uses final HoloOcean projected cells.
""".format(
        policy=summary["policy_name"],
        assignment=summary["assignment_mode"],
        motion=summary["target_motion_mode"],
        height=summary["map_height_cells"],
        width=summary["map_width_cells"],
        resolution=summary["resolution_m"],
        seed=summary["episode_seed"],
        max_policy_steps=summary["max_policy_steps"],
        expected_step=summary["expected_runtime_all_found_step"],
        main_agent=summary["scenario_main_agent"],
        camera_name=summary["visual_camera_name"],
        camera_width=summary["visual_camera_width"],
        camera_height=summary["visual_camera_height"],
        camera_hz=summary["visual_camera_hz"],
        camera_for_detection=summary["visual_camera_used_for_detection"],
        terminated=summary["terminated_reason"],
        completed_steps=summary["completed_policy_steps"],
        total_ticks=summary["total_physical_ticks"],
        initial_all_found=summary["initial_all_found"],
        found_final=summary["found_count_final"],
        hit_covered=summary["hit_branch_covered"],
        gp_initial=summary["gp_n_obs_initial"],
        gp_final=summary["gp_n_obs_final"],
        min_sep=summary["min_inter_vessel_distance_m"],
        fallback_total=summary["fallback_count_total"],
    )


def _generate_paths_png(nav_map_prior: np.ndarray, policy_trace: List[Dict[str, Any]], tick_trace: List[Dict[str, Any]]) -> None:
    try:
        import matplotlib.pyplot as plt

        os.makedirs(os.path.dirname(PATHS_PNG), exist_ok=True)
        plt.figure(figsize=(10, 10))
        plt.imshow(nav_map_prior, cmap="gray_r", origin="upper")
        if policy_trace:
            first = policy_trace[0]
            local_before = first.get("local_before", {})
            sv0_before = local_before.get(0, local_before.get("0"))
            sv1_before = local_before.get(1, local_before.get("1"))
            if sv0_before is None or sv1_before is None:
                raise KeyError("local_before")
            plt.scatter(
                [sv0_before["robot_pos"][1], sv1_before["robot_pos"][1]],
                [sv0_before["robot_pos"][0], sv1_before["robot_pos"][0]],
                c=["blue", "red"],
                marker="o",
                s=70,
                label="Initial USVs",
            )
            target_positions = first.get("target_positions_after_step_targets", [])
            if target_positions:
                plt.scatter(
                    [target_positions[0][1]],
                    [target_positions[0][0]],
                    c="green",
                    marker="*",
                    s=140,
                    label="Static target truth",
                )
        sv0_cols = [int(row["sv0_proj_col"]) for row in tick_trace]
        sv0_rows = [int(row["sv0_proj_row"]) for row in tick_trace]
        sv1_cols = [int(row["sv1_proj_col"]) for row in tick_trace]
        sv1_rows = [int(row["sv1_proj_row"]) for row in tick_trace]
        if sv0_cols:
            plt.plot(sv0_cols, sv0_rows, color="deepskyblue", linewidth=2.0, label="sv0 projected path")
        if sv1_cols:
            plt.plot(sv1_cols, sv1_rows, color="coral", linewidth=2.0, label="sv1 projected path")
        plt.title("Phase 5C-3 HoloOcean Dual-USV Static All Found Visual Runner")
        plt.xlabel("Column")
        plt.ylabel("Row")
        plt.xlim(-0.5, 80.5)
        plt.ylim(80.5, -0.5)
        plt.grid(True, color="lightgray", linestyle=":", alpha=0.4)
        plt.legend(loc="upper right")
        plt.savefig(PATHS_PNG, dpi=150, bbox_inches="tight")
        plt.close()
        print("Paths map saved to: {0}".format(PATHS_PNG))
    except Exception as exc:
        print("[WARN] Skipping visual rendering: {0}".format(exc))


def run_smoke() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    config = _phase_config()
    state = _initialize_state(config)
    nav_map_prior, spec = load_scene_map_npz(MAP_NPZ)
    adapter_config = scene_map_config_from_spec(spec)

    initial_gp_counts = _gp_observation_counts(state)
    initial_found_count = int(state["found_mask"].sum())
    initial_all_found = bool(np.all(state["found_mask"]))
    initial_target_positions = _json_safe(state["target_positions"])
    initial_robot_positions = [list(local["robot_pos"]) for local in state["usv_states"]]
    initial_find_times = _json_safe(state["find_times"])

    start_world: Dict[int, List[float]] = {}
    for usv_id, local in enumerate(state["usv_states"]):
        cell = tuple(int(v) for v in local["robot_pos"])
        world = list(grid_to_world(cell, config=adapter_config))
        roundtrip = world_to_grid(world, config=adapter_config, map_shape=nav_map_prior.shape)
        if tuple(roundtrip) != cell:
            raise AssertionError("Initial grid/world roundtrip mismatch for sv{0}: {1} -> {2} -> {3}".format(usv_id, cell, world, roundtrip))
        world[2] = 2.0
        start_world[usv_id] = [float(v) for v in world]

    scenario_cfg = _make_scenario_config(spec, start_world)
    phys_state = _physical_state(start_world)
    policy_trace: List[Dict[str, Any]] = []
    tick_trace: List[Dict[str, Any]] = []
    found_event_details: List[Dict[str, Any]] = []
    hit_branch_covered = False
    terminated_reason = "initial_all_found" if initial_all_found else "max_policy_steps"
    physical_failure = False

    import holoocean

    state_env: Optional[Dict[str, Any]] = None
    if not initial_all_found:
        with holoocean.make(scenario_cfg=scenario_cfg) as env:
            env.act("sv0", np.zeros(2, dtype=np.float32))
            env.act("sv1", np.zeros(2, dtype=np.float32))
            state_env = env.tick()

            for step in range(1, int(config["max_policy_steps"]) + 1):
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
                wait_applied_map = {int(k): bool(v) for k, v in wait_applied_map.items()}

                local_before = {}
                target_cells: Dict[int, Tuple[int, int]] = {}
                local_observation_terms: Dict[int, Tuple[float, float]] = {}
                for usv_id, local in enumerate(state["usv_states"]):
                    local_before[usv_id] = {
                        "robot_pos": list(local["robot_pos"]),
                        "commit_remaining": int(local.get("commit_remaining", 0)),
                        "committed_segment": [list(c) for c in local.get("committed_segment", [])],
                    }
                    local_observation_terms[usv_id] = _observation_progress_for_robot(state, local["robot_pos"])
                    if wait_applied_map[usv_id]:
                        target_cells[usv_id] = tuple(int(v) for v in local["robot_pos"])
                    else:
                        segment = local.get("committed_segment", [])
                        if len(segment) < 2:
                            raise AssertionError("sv{0} has no next target cell at step {1}".format(usv_id, step))
                        target_cells[usv_id] = tuple(int(v) for v in segment[1])
                    target_world = list(grid_to_world(target_cells[usv_id], config=adapter_config))
                    target_roundtrip = world_to_grid(target_world, config=adapter_config, map_shape=nav_map_prior.shape)
                    if tuple(target_roundtrip) != target_cells[usv_id]:
                        raise AssertionError("Target roundtrip mismatch for sv{0}: {1}".format(usv_id, target_cells[usv_id]))

                state_env, physical_result = _drive_policy_step(
                    env,
                    state_env,
                    adapter_config,
                    nav_map_prior,
                    phys_state,
                    step,
                    target_cells,
                    wait_applied_map,
                    tick_trace,
                )

                exec_results: Dict[int, Optional[ExecutionStepResult]] = {}
                step_physical_success = not bool(physical_result["timeout"])
                for usv_id, local in enumerate(state["usv_states"]):
                    final_info = physical_result["final_by_usv"][str(usv_id)]
                    final_cell_raw = final_info["final_projected_cell"]
                    final_cell = tuple(int(v) for v in final_cell_raw) if final_cell_raw is not None else tuple(int(v) for v in local["robot_pos"])
                    projection_ok = bool(final_info["projection_matches_target"])
                    arrived_ok = bool(final_info["arrived"])
                    success = bool(projection_ok and arrived_ok and not physical_result["timeout"])
                    if wait_applied_map[usv_id]:
                        success = bool(projection_ok and not physical_result["timeout"])
                        exec_results[usv_id] = None
                    else:
                        exec_results[usv_id] = ExecutionStepResult(
                            move_success=success,
                            collision=False,
                            collision_cell=None,
                            new_robot_pos=final_cell,
                        )
                    step_physical_success = bool(step_physical_success and success)

                if not step_physical_success:
                    physical_failure = True
                    terminated_reason = "physical_failure"
                    step_record = {
                        "step": int(step),
                        "physical_step_success": False,
                        "physical_result": physical_result,
                        "local_before": local_before,
                        "wait_applied_map": {str(k): bool(v) for k, v in wait_applied_map.items()},
                        "holo_target_cells": {str(k): list(v) for k, v in target_cells.items()},
                        "terminated_reason_after_step": terminated_reason,
                    }
                    policy_trace.append(step_record)
                    break

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
                    for target_idx in new_indices:
                        detected_usvs = []
                        projected_cells = {}
                        for usv_id in (0, 1):
                            mask = detection_masks_by_usv.get(usv_id, [])
                            if target_idx < len(mask) and bool(mask[target_idx]):
                                detected_usvs.append(usv_id)
                                projected_cells[str(usv_id)] = list(state["usv_states"][usv_id]["robot_pos"])
                        found_event_details.append(
                            {
                                "target_index": int(target_idx),
                                "found_step": int(step),
                                "detected_usvs": detected_usvs,
                                "target_position": list(state["target_positions"][target_idx]),
                                "usv_projected_cells": projected_cells,
                            }
                        )
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
                    hit_positions = [tuple(int(v) for v in state["target_positions"][idx]) for idx in new_indices]
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
                    "holo_target_cells": {str(k): list(v) for k, v in target_cells.items()},
                    "physical_execution_called": True,
                    "physical_step_success": True,
                    "physical_result": physical_result,
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
                    "terminated_reason_after_step": "all_found" if np.all(state["found_mask"]) else "running",
                }
                step_record.update(gp_counts)
                step_record.update(search_stats)
                policy_trace.append(step_record)

                if np.all(state["found_mask"]):
                    state["terminated_reason"] = "all_found"
                    terminated_reason = "all_found"
                    break
            else:
                state["completed_steps"] = int(config["max_policy_steps"])
                state["terminated_reason"] = "max_policy_steps"
                terminated_reason = "max_policy_steps"
    else:
        state["terminated_reason"] = "all_found"
        terminated_reason = "all_found"

    final_gp_counts = _gp_observation_counts(state)
    found_count_final = int(state["found_mask"].sum())
    fallback_total = int(sum(int(v) for v in phys_state["fallback_counts"].values()))
    total_physical_ticks = int(phys_state["global_tick"])
    min_sep = float(phys_state["min_inter_vessel_distance_m"])
    if total_physical_ticks == 0:
        min_sep = 0.0

    found_events = {
        "phase_name": PHASE_NAME,
        "initial_found_count": initial_found_count,
        "initial_all_found": initial_all_found,
        "initial_target_positions": initial_target_positions,
        "expected_initial_target_positions": EXPECTED_INITIAL_TARGET_POSITIONS,
        "initial_robot_positions": initial_robot_positions,
        "initial_find_times": initial_find_times,
        "expected_runtime_all_found_step": EXPECTED_RUNTIME_ALL_FOUND_STEP,
        "terminated_reason": terminated_reason,
        "completed_policy_steps": int(state.get("completed_steps", 0)),
        "max_policy_steps": int(config["max_policy_steps"]),
        "found_count_final": found_count_final,
        "found_mask_final": _json_safe(state["found_mask"]),
        "find_times_final": _json_safe(state["find_times"]),
        "found_event_details": found_event_details,
        "hit_branch_covered": bool(hit_branch_covered),
        "physical_failure": bool(physical_failure),
        "remaining_intensity_mass_final": float(remaining_intensity_mass(state["intensity_map"])),
        "peak_intensity_ratio_final": float(peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])),
        "known_free_observation_ratio_final": float(state["known_free_observation_ratio_curve"][-1]) if state["known_free_observation_ratio_curve"] else 0.0,
        "gp_n_obs_initial": initial_gp_counts["gp_n_obs"],
        "gp_n_obs_final": final_gp_counts["gp_n_obs"],
        "gp_x_obs_len_final": final_gp_counts["gp_x_obs_len"],
        "gp_y_obs_len_final": final_gp_counts["gp_y_obs_len"],
        "gp_count_consistent_final": final_gp_counts["gp_count_consistent"],
        "runtime_team_trace_rows_count": int(len(state.get("team_trace_rows", []))),
        "runtime_local_trace_rows_count": int(len(state.get("trace_rows", []))),
        "wall_time_s": float(time.perf_counter() - started),
    }

    sensor_summary = {
        "selected_sensor_counts_by_usv": {
            "sv0": phys_state["sensor_counts"][0],
            "sv1": phys_state["sensor_counts"][1],
        },
        "fallback_count_by_usv": {
            "sv0": int(phys_state["fallback_counts"][0]),
            "sv1": int(phys_state["fallback_counts"][1]),
        },
        "fallback_count_total": fallback_total,
        "total_physical_ticks": total_physical_ticks,
        "location_sensor_integrity_ratio": {
            "sv0": float(phys_state["sensor_counts"][0]["LocationSensor"] / max(1, total_physical_ticks)),
            "sv1": float(phys_state["sensor_counts"][1]["LocationSensor"] / max(1, total_physical_ticks)),
        },
    }
    collision_summary = {
        "min_inter_vessel_distance_m": min_sep,
        "collision_warning_ticks": int(phys_state["collision_warning_ticks"]),
        "collision_fail_ticks": int(phys_state["collision_fail_ticks"]),
        "collision_warning_distance_limit_m": COLLISION_WARNING_M,
        "collision_fail_distance_limit_m": COLLISION_FAIL_M,
        "min_separation_margin_ok": bool(min_sep >= COLLISION_WARNING_M),
        "collision_fail_free": bool(int(phys_state["collision_fail_ticks"]) == 0),
    }
    summary = {
        "phase_name": PHASE_NAME,
        "policy_name": config["policy_name"],
        "assignment_mode": config["assignment_mode"],
        "target_motion_mode": config["target_motion_mode"],
        "map_height_cells": config["map_height_cells"],
        "map_width_cells": config["map_width_cells"],
        "resolution_m": config["resolution_m"],
        "episode_seed": config["episode_seed"],
        "max_policy_steps": config["max_policy_steps"],
        "expected_runtime_all_found_step": config["expected_runtime_all_found_step"],
        "expected_initial_target_positions": config["expected_initial_target_positions"],
        "scenario_main_agent": config["scenario_main_agent"],
        "visual_only_runner": config["visual_only_runner"],
        "visual_camera_name": config["visual_camera_name"],
        "visual_camera_width": config["visual_camera_width"],
        "visual_camera_height": config["visual_camera_height"],
        "visual_camera_hz": config["visual_camera_hz"],
        "visual_camera_used_for_detection": config["visual_camera_used_for_detection"],
        "terminated_reason": terminated_reason,
        "completed_policy_steps": int(state.get("completed_steps", 0)),
        "total_physical_ticks": total_physical_ticks,
        "initial_all_found": initial_all_found,
        "found_count_final": found_count_final,
        "hit_branch_covered": bool(hit_branch_covered),
        "gp_n_obs_initial": initial_gp_counts["gp_n_obs"],
        "gp_n_obs_final": final_gp_counts["gp_n_obs"],
        "min_inter_vessel_distance_m": min_sep,
        "fallback_count_total": fallback_total,
        "physical_failure": bool(physical_failure),
        "runtime_team_trace_rows_count": found_events["runtime_team_trace_rows_count"],
        "runtime_local_trace_rows_count": found_events["runtime_local_trace_rows_count"],
    }

    _save_json(CONFIG_JSON, config)
    _save_json(POLICY_TRACE_JSON, policy_trace)
    _save_csv(POLICY_TRACE_CSV, policy_trace)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(FOUND_JSON, found_events)
    _save_json(SENSOR_JSON, sensor_summary)
    _save_json(COLLISION_JSON, collision_summary)
    _save_json(SUMMARY_JSON, summary)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary saved to: {0}".format(SUMMARY_MD))

    _generate_paths_png(nav_map_prior, policy_trace, tick_trace)

    post_git_status = _run_git_status()
    git_status = {
        "pre_git_status": pre_git_status,
        "post_git_status": post_git_status,
        "phase_dir": PHASE_DIR.replace("\\", "/"),
        "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_git_status, post_git_status),
    }
    _save_json(GIT_STATUS_JSON, git_status)

    return {
        "config": config,
        "policy_trace": policy_trace,
        "tick_trace": tick_trace,
        "found_events": found_events,
        "sensor_summary": sensor_summary,
        "collision_summary": collision_summary,
        "summary": summary,
        "git_status": git_status,
    }


def main() -> None:
    print("=== Phase 5C-3: dual-USV static HoloOcean all_found visual runner ===")
    print("Viewport keys: H=HUD, Tab=switch agent, C=chase/perspective camera, V=spectator/free-cam.")
    print("Visual camera is for viewport inspection only; runtime target detection remains unchanged.")
    result = run_smoke()
    summary = result["summary"]
    print(
        "Phase 5C-3 visual runner finished: reason={0}, policy_steps={1}, ticks={2}, found={3}".format(
            summary["terminated_reason"],
            summary["completed_policy_steps"],
            summary["total_physical_ticks"],
            summary["found_count_final"],
        )
    )


if __name__ == "__main__":
    main()
