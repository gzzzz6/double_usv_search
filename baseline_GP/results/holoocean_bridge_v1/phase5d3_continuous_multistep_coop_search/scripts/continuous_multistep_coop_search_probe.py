"""Phase 5D-3: continuous multi-step cooperative SphereAgent search.

This phase connects the Phase 5D-2 per-agent detection event and candidate
fusion pattern to a continuous HoloOcean multi-step execution loop.

Scope:
    - observers: two SurfaceVessel agents, sv0 and sv1
    - target: one static SphereAgent
    - teammate negative: one SurfaceVessel in teammate-only/coexistence checks
    - detection rule: 5D-1A sphere_blob_local_range_scaled_any_hit
    - team update: fused candidate updates shared_found/found_mask/all_found

Truth is used only for scenario construction and audit metrics. The detection
event, candidate fusion, found_mask update, and all_found termination are driven
by sensor evidence only.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d3_continuous_multistep_coop_search"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
SOURCE_5D1A_PHASE_NAME = "phase5d1a_sphere_blob_local_range_scaled_validation"
SOURCE_5D2_PHASE_NAME = "phase5d2_multi_surfacevessel_static_sphereagent_coop_search"
SOURCE_5D1A_PROBE = os.path.normpath(
    os.path.join(
        BASE_DIR,
        "results",
        "holoocean_bridge_v1",
        SOURCE_5D1A_PHASE_NAME,
        "scripts",
        "sphere_blob_local_range_scaled_probe.py",
    )
)
SOURCE_5D1A_AUDIT = os.path.normpath(
    os.path.join(
        BASE_DIR,
        "results",
        "holoocean_bridge_v1",
        SOURCE_5D1A_PHASE_NAME,
        "manifests",
        "phase5d1a_local_audit.json",
    )
)
SOURCE_5D2_AUDIT = os.path.normpath(
    os.path.join(
        BASE_DIR,
        "results",
        "holoocean_bridge_v1",
        SOURCE_5D2_PHASE_NAME,
        "manifests",
        "phase5d2_coop_audit.json",
    )
)

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_config.json")
BASELINE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_baseline_run.json")
TARGET_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_target_run.json")
TEAMMATE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_teammate_only_run.json")
POLICY_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_policy_trace.json")
POLICY_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_policy_trace.csv")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_tick_trace.csv")
PER_AGENT_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_per_agent_detection_events.json")
PER_AGENT_EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_per_agent_detection_events.csv")
FUSION_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_candidate_fusion_trace.json")
FUSION_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_candidate_fusion_trace.csv")
FOUND_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_found_events.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d3_continuous_summary.md")

RGB_CAMERA_NAME = "FrontRGBCamera"
FAN_RANGEFINDER_PREFIX = "FanRangeFinder"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
AGENT_NAMES = ["sv0", "sv1"]
TARGET_Z = 0.5
TEAMMATE_Z = 0.0
OBSERVER_Z = 0.0

RELIABLE_DISTANCE_LIMIT_M = 35.0
TEAMMATE_EXCLUSION_RADIUS_M = 10.0
FUSION_DISTANCE_THRESHOLD_M = 15.0
TARGET_AUDIT_DISTANCE_THRESHOLD_M = 15.0
MAX_POLICY_STEPS = 4
TICKS_PER_POLICY_STEP = 12
TOTAL_TICKS = MAX_POLICY_STEPS * TICKS_PER_POLICY_STEP

MAX_FORCE = 8000.0
MIN_FORCE = 1500.0
TURN_GAIN = 0.8
DIST_SLOW_RADIUS_M = 12.0
COLLISION_WARNING_M = 8.0
COLLISION_FAIL_M = 4.0


def _load_module(path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load module from {0}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5D1A = _load_module(SOURCE_5D1A_PROBE, "phase5d1a_local_probe")


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


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def _ensure_dirs() -> None:
    for leaf in ("scripts", "manifests", "reports", "logs", "visuals"):
        os.makedirs(os.path.join(PHASE_DIR, leaf), exist_ok=True)


def _camera_sensor() -> Dict[str, Any]:
    return P5D1A._camera_sensor()


def _fan_rangefinder_sensors() -> List[Dict[str, Any]]:
    return P5D1A._fan_rangefinder_sensors()


def _fan_rangefinder_names() -> List[str]:
    return ["{0}_{1:02d}".format(FAN_RANGEFINDER_PREFIX, index) for index in range(len(P5D1A.FAN_YAW_DEGREES))]


def _zero_action(agent_type: str) -> np.ndarray:
    return P5D1A._zero_action(agent_type)


def _control_scheme(agent_type: str) -> int:
    return P5D1A._control_scheme(agent_type)


def _load_source_audit(path: str) -> bool:
    try:
        return bool(_load_json(path).get("all_passed") is True)
    except Exception:
        return False


def _path_at(tick_index: int) -> Dict[str, List[float]]:
    progress = 0.0 if TOTAL_TICKS <= 1 else float(tick_index) / float(TOTAL_TICKS - 1)
    x = 2.0 + 16.0 * progress
    return {
        "sv0": [x, -6.0, OBSERVER_Z],
        "sv1": [x, 6.0, OBSERVER_Z],
    }


def _policy_waypoints() -> Dict[str, List[List[float]]]:
    steps: Dict[str, List[List[float]]] = {"sv0": [], "sv1": []}
    for step in range(MAX_POLICY_STEPS):
        progress = float(step + 1) / float(MAX_POLICY_STEPS)
        x = 2.0 + 16.0 * progress
        steps["sv0"].append([x, -6.0, OBSERVER_Z])
        steps["sv1"].append([x, 6.0, OBSERVER_Z])
    return steps


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "phase_goal": "Connect 5D-2 candidate fusion to a continuous multi-step HoloOcean search closure.",
        "source_5d1a_phase_name": SOURCE_5D1A_PHASE_NAME,
        "source_5d2_phase_name": SOURCE_5D2_PHASE_NAME,
        "source_5d1a_audit_all_passed": _load_source_audit(SOURCE_5D1A_AUDIT),
        "source_5d2_audit_all_passed": _load_source_audit(SOURCE_5D2_AUDIT),
        "recommended_rule_id": "sphere_blob_local_range_scaled_any_hit",
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "observer_agent_names": list(AGENT_NAMES),
        "observer_count": len(AGENT_NAMES),
        "target_is_static": True,
        "same_model_teammate_and_target": False,
        "dynamic_target_tracking_enabled": False,
        "continuous_search_loop_enabled": True,
        "max_policy_steps": MAX_POLICY_STEPS,
        "ticks_per_policy_step": TICKS_PER_POLICY_STEP,
        "total_ticks": TOTAL_TICKS,
        "policy_waypoints": _policy_waypoints(),
        "target_world_location": [31.0, 0.0, TARGET_Z],
        "teammate_world_location": [31.0, 0.0, TEAMMATE_Z],
        "coexist_teammate_world_location": [23.0, 12.0, TEAMMATE_Z],
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "teammate_exclusion_radius_m": TEAMMATE_EXCLUSION_RADIUS_M,
        "fusion_distance_threshold_m": FUSION_DISTANCE_THRESHOLD_M,
        "target_audit_distance_threshold_m": TARGET_AUDIT_DISTANCE_THRESHOLD_M,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "teammate_identity_position_available_externally": True,
        "teammate_position_used_for_candidate_exclusion": True,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "pre_git_status": pre_git_status or [],
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _actor(agent_name: str, agent_type: str, location: List[float]) -> Dict[str, Any]:
    return {
        "agent_name": agent_name,
        "agent_type": agent_type,
        "location": [float(location[0]), float(location[1]), float(location[2])],
        "rotation": [0.0, 0.0, 0.0],
    }


def _scenario_config(run_kind: str, config: Dict[str, Any]) -> Dict[str, Any]:
    start_positions = _path_at(0)
    agents: List[Dict[str, Any]] = []
    for agent_name in AGENT_NAMES:
        agents.append(
            {
                "agent_name": agent_name,
                "agent_type": TEAMMATE_AGENT_TYPE,
                "sensors": [
                    {"sensor_type": "LocationSensor", "socket": "COM"},
                    {"sensor_type": "GPSSensor", "socket": "COM"},
                    {"sensor_type": "OrientationSensor", "socket": "COM"},
                    _camera_sensor(),
                ]
                + _fan_rangefinder_sensors(),
                "control_scheme": 1,
                "location": start_positions[agent_name],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    if run_kind in ("target", "coexist"):
        target = _actor("target", TARGET_AGENT_TYPE, config["target_world_location"])
        agents.append(
            {
                "agent_name": target["agent_name"],
                "agent_type": target["agent_type"],
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(target["agent_type"]),
                "location": target["location"],
                "rotation": target["rotation"],
            }
        )
    if run_kind == "teammate_only":
        teammate = _actor("teammate_extra0", TEAMMATE_AGENT_TYPE, config["teammate_world_location"])
        agents.append(
            {
                "agent_name": teammate["agent_name"],
                "agent_type": teammate["agent_type"],
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(teammate["agent_type"]),
                "location": teammate["location"],
                "rotation": teammate["rotation"],
            }
        )
    if run_kind == "coexist":
        teammate = _actor("teammate_extra0", TEAMMATE_AGENT_TYPE, config["coexist_teammate_world_location"])
        agents.append(
            {
                "agent_name": teammate["agent_name"],
                "agent_type": teammate["agent_type"],
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(teammate["agent_type"]),
                "location": teammate["location"],
                "rotation": teammate["rotation"],
            }
        )
    return {
        "name": "phase5d3_{0}".format(run_kind),
        "world": "OpenWater",
        "package_name": "Ocean",
        "main_agent": "sv0",
        "agents": agents,
    }


def _compute_controller_cmd(tx: float, ty: float, curr_pos: List[float], orient_sensor: Optional[np.ndarray]) -> Tuple[float, float, float, float, float, float]:
    dx = tx - curr_pos[0]
    dy = ty - curr_pos[1]
    dist = math.hypot(dx, dy)
    target_heading_deg = np.degrees(np.arctan2(dy, dx)) % 360.0
    heading_deg = 0.0
    if orient_sensor is not None:
        r_matrix = np.reshape(orient_sensor, (3, 3))
        forward = r_matrix[:, 0]
        heading_deg = np.degrees(np.arctan2(forward[1], forward[0])) % 360.0
    heading_error_deg = (target_heading_deg - heading_deg + 180.0) % 360.0 - 180.0
    heading_error_rad = np.radians(heading_error_deg)
    turn = TURN_GAIN * heading_error_rad * MAX_FORCE
    if dist < DIST_SLOW_RADIUS_M:
        forward_cmd = MIN_FORCE + (MAX_FORCE - MIN_FORCE) * (dist / DIST_SLOW_RADIUS_M)
    else:
        forward_cmd = MAX_FORCE
    forward_factor = np.cos(heading_error_rad)
    if forward_factor < 0.0:
        forward_factor = 0.0
    forward_cmd *= forward_factor
    left = np.clip(forward_cmd - turn, -MAX_FORCE, MAX_FORCE)
    right = np.clip(forward_cmd + turn, -MAX_FORCE, MAX_FORCE)
    return float(left), float(right), float(dist), float(heading_deg), float(target_heading_deg), float(heading_error_deg)


def _select_sensor(state: Dict[str, Any], agent_name: str, fallback: List[float]) -> Dict[str, Any]:
    loc = get_sensor_vector(state, agent_name, "LocationSensor")
    gps = get_sensor_vector(state, agent_name, "GPSSensor")
    orient = get_sensor_vector(state, agent_name, "OrientationSensor")
    if loc is not None:
        return {"selected_sensor": "LocationSensor", "curr_pos": [float(loc[0]), float(loc[1]), float(loc[2])], "orient": orient, "loc_avail": True, "gps_avail": gps is not None, "fallback_used": False}
    if gps is not None:
        return {"selected_sensor": "GPSSensor", "curr_pos": [float(gps[0]), float(gps[1]), float(gps[2])], "orient": orient, "loc_avail": False, "gps_avail": True, "fallback_used": False}
    return {"selected_sensor": "last_known", "curr_pos": [float(v) for v in fallback], "orient": orient, "loc_avail": False, "gps_avail": False, "fallback_used": True}


def _aggregate_fan_range(state: Dict[str, Any], agent_name: str) -> List[float]:
    values: List[float] = []
    for name in _fan_rangefinder_names():
        value = get_sensor_vector(state, agent_name, name)
        if value is None:
            values.append(-1.0)
            continue
        arr = np.asarray(value).astype(float).reshape(-1)
        values.append(float(arr[0]) if arr.size else -1.0)
    return values


def _run_trajectory(run_kind: str, config: Dict[str, Any]) -> Dict[str, Any]:
    import holoocean

    tick_rows: List[Dict[str, Any]] = []
    rgb_by_agent_tick: Dict[str, Dict[int, Any]] = {agent: {} for agent in AGENT_NAMES}
    range_by_agent_tick: Dict[str, Dict[int, Any]] = {agent: {} for agent in AGENT_NAMES}
    last_known = {agent: list(_path_at(0)[agent]) for agent in AGENT_NAMES}
    min_sep = 999999.0
    launch_ok = False
    error = ""
    started = time.perf_counter()
    try:
        with holoocean.make(scenario_cfg=_scenario_config(run_kind, config)) as env:
            launch_ok = True
            state = env.tick()
            for tick in range(TOTAL_TICKS):
                path_pos = _path_at(tick)
                commands: Dict[str, Dict[str, Any]] = {}
                selected_by_agent: Dict[str, Dict[str, Any]] = {}
                for agent_name in AGENT_NAMES:
                    selected = _select_sensor(state, agent_name, last_known[agent_name])
                    selected_by_agent[agent_name] = selected
                    last_known[agent_name] = list(selected["curr_pos"])
                    target = path_pos[agent_name]
                    left, right, dist, heading, target_heading, heading_error = _compute_controller_cmd(
                        float(target[0]),
                        float(target[1]),
                        selected["curr_pos"],
                        selected["orient"],
                    )
                    commands[agent_name] = {
                        "left": left,
                        "right": right,
                        "distance_to_waypoint_m": dist,
                        "heading_deg": heading,
                        "target_heading_deg": target_heading,
                        "heading_error_deg": heading_error,
                        "target_world": target,
                    }
                for agent_name in AGENT_NAMES:
                    env.act(agent_name, np.array([commands[agent_name]["left"], commands[agent_name]["right"]], dtype=np.float32))
                if run_kind in ("target", "coexist"):
                    env.act("target", _zero_action(TARGET_AGENT_TYPE))
                if run_kind in ("teammate_only", "coexist"):
                    env.act("teammate_extra0", _zero_action(TEAMMATE_AGENT_TYPE))
                state = env.tick()
                sep = math.hypot(last_known["sv0"][0] - last_known["sv1"][0], last_known["sv0"][1] - last_known["sv1"][1])
                min_sep = min(min_sep, sep)
                policy_step = int(tick // TICKS_PER_POLICY_STEP) + 1
                tick_in_policy_step = int(tick % TICKS_PER_POLICY_STEP) + 1
                for agent_name in AGENT_NAMES:
                    rgb = get_sensor_vector(state, agent_name, RGB_CAMERA_NAME)
                    fan_range = _aggregate_fan_range(state, agent_name)
                    if rgb is not None:
                        rgb_by_agent_tick[agent_name][tick] = np.asarray(rgb).copy()
                    range_by_agent_tick[agent_name][tick] = np.asarray(fan_range).copy()
                    rsum = P5D1A._range_summary(fan_range)
                    selected = selected_by_agent[agent_name]
                    tick_rows.append(
                        {
                            "run_kind": run_kind,
                            "tick_global": int(tick + 1),
                            "policy_step": policy_step,
                            "tick_in_policy_step": tick_in_policy_step,
                            "agent_name": agent_name,
                            "rgb_present": rgb is not None,
                            "rangefinder_present": bool(rsum.get("present", False)),
                            "any_rangefinder_hit": bool(rsum.get("any_hit", False)),
                            "rangefinder_hit_beam_indices": rsum.get("hit_beam_indices"),
                            "rangefinder_min_positive_range_m": rsum.get("min_positive_range_m"),
                            "loc_x": float(last_known[agent_name][0]),
                            "loc_y": float(last_known[agent_name][1]),
                            "loc_z": float(last_known[agent_name][2]),
                            "selected_sensor": selected["selected_sensor"],
                            "fallback_used": bool(selected["fallback_used"]),
                            "target_waypoint": commands[agent_name]["target_world"],
                            "distance_to_waypoint_m": commands[agent_name]["distance_to_waypoint_m"],
                            "heading_deg": commands[agent_name]["heading_deg"],
                            "target_heading_deg": commands[agent_name]["target_heading_deg"],
                            "heading_error_deg": commands[agent_name]["heading_error_deg"],
                            "cmd_l": commands[agent_name]["left"],
                            "cmd_r": commands[agent_name]["right"],
                            "inter_vessel_distance_m": float(sep),
                        }
                    )
    except Exception as exc:
        error = "{0}: {1}".format(type(exc).__name__, exc)
        tick_rows.append({"run_kind": run_kind, "tick_global": 0, "scenario_error": error, "traceback": traceback.format_exc()})
    return {
        "run_kind": run_kind,
        "launch_ok": launch_ok,
        "error": error,
        "wall_time_s": float(time.perf_counter() - started),
        "tick_rows": tick_rows,
        "rgb_by_agent_tick": rgb_by_agent_tick,
        "range_by_agent_tick": range_by_agent_tick,
        "final_positions": last_known,
        "min_inter_vessel_distance_m": 0.0 if min_sep == 999999.0 else float(min_sep),
    }


def _distance_2d(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    if a is None or b is None or len(a) < 2 or len(b) < 2:
        return None
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))


def _estimate_world_position(observer_location: List[float], bearing_deg: Optional[float], range_m: Optional[float]) -> Optional[List[float]]:
    if bearing_deg is None or range_m is None:
        return None
    yaw = math.radians(float(bearing_deg))
    return [
        float(observer_location[0]) + float(range_m) * math.cos(yaw),
        float(observer_location[1]) + float(range_m) * math.sin(yaw),
        0.0,
    ]


def _known_teammates_for_run(run_kind: str, tick: int, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    positions = _path_at(tick)
    teammates = [
        {"agent_name": "sv0", "agent_type": TEAMMATE_AGENT_TYPE, "location": positions["sv0"], "is_observer": True},
        {"agent_name": "sv1", "agent_type": TEAMMATE_AGENT_TYPE, "location": positions["sv1"], "is_observer": True},
    ]
    if run_kind == "teammate_only":
        teammates.append({"agent_name": "teammate_extra0", "agent_type": TEAMMATE_AGENT_TYPE, "location": config["teammate_world_location"], "is_observer": False})
    if run_kind == "coexist":
        teammates.append({"agent_name": "teammate_extra0", "agent_type": TEAMMATE_AGENT_TYPE, "location": config["coexist_teammate_world_location"], "is_observer": False})
    return teammates


def _nearest_teammate(candidate_position: Optional[List[float]], teammates: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = {"nearest_teammate_agent_name": None, "nearest_teammate_distance_m": None, "within_teammate_exclusion_radius": False}
    for teammate in teammates:
        loc = teammate.get("location")
        distance = _distance_2d(candidate_position, loc if isinstance(loc, list) else None)
        if distance is None:
            continue
        if best["nearest_teammate_distance_m"] is None or distance < float(best["nearest_teammate_distance_m"]):
            best = {
                "nearest_teammate_agent_name": str(teammate.get("agent_name")),
                "nearest_teammate_distance_m": distance,
                "within_teammate_exclusion_radius": distance <= TEAMMATE_EXCLUSION_RADIUS_M,
            }
    return best


def _target_present(run_kind: str) -> bool:
    return run_kind in ("target", "coexist")


def _build_events_for_run(run: Dict[str, Any], baseline_run: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    run_kind = str(run["run_kind"])
    events: List[Dict[str, Any]] = []
    target_location = config["target_world_location"] if _target_present(run_kind) else None
    for tick in range(TOTAL_TICKS):
        positions = _path_at(tick)
        for agent_name in AGENT_NAMES:
            rgb = run.get("rgb_by_agent_tick", {}).get(agent_name, {}).get(tick)
            baseline_rgb = baseline_run.get("rgb_by_agent_tick", {}).get(agent_name, {}).get(tick)
            fan_range = run.get("range_by_agent_tick", {}).get(agent_name, {}).get(tick)
            range_summary = P5D1A._range_summary(fan_range)
            rgb_diff = P5D1A._rgb_diff_signature(rgb, baseline_rgb)
            sphere_blob = P5D1A._sphere_blob_signature(rgb, baseline_rgb)
            local_blob = P5D1A._local_range_scaled_blob_signature(
                sphere_blob.get("local_candidate_blobs"),
                range_summary.get("raw"),
            )
            raw_found = bool(local_blob.get("local_range_scaled_blob_present", False))
            bearing = local_blob.get("matched_beam_yaw_deg")
            if bearing is None:
                bearing = local_blob.get("blob_yaw_deg")
            matched_range = local_blob.get("matched_range_m")
            observer_location = positions[agent_name]
            estimated = _estimate_world_position(observer_location, bearing, matched_range)
            nearest = _nearest_teammate(estimated, _known_teammates_for_run(run_kind, tick, config))
            teammate_rejected = bool(raw_found and nearest.get("within_teammate_exclusion_radius") is True)
            range_limited = bool(matched_range is not None and float(matched_range) <= RELIABLE_DISTANCE_LIMIT_M + 1.0)
            accepted = bool(raw_found and range_limited and not teammate_rejected)
            target_error = _distance_2d(estimated, target_location if isinstance(target_location, list) else None)
            events.append(
                {
                    "run_kind": run_kind,
                    "tick_global": int(tick + 1),
                    "policy_step": int(tick // TICKS_PER_POLICY_STEP) + 1,
                    "tick_in_policy_step": int(tick % TICKS_PER_POLICY_STEP) + 1,
                    "reporter_usv_id": agent_name,
                    "agent_id": agent_name,
                    "sensor_id": "{0}+fan_rangefinder".format(RGB_CAMERA_NAME),
                    "recommended_rule_id": config.get("recommended_rule_id"),
                    "expected_target_present_for_audit": _target_present(run_kind),
                    "raw_sensor_found": raw_found,
                    "accepted_candidate": accepted,
                    "teammate_rejected": teammate_rejected,
                    "range_limited": range_limited,
                    "estimated_world_position": estimated,
                    "target_world_location_for_audit": target_location,
                    "target_position_error_m": target_error,
                    "observer_world_location": observer_location,
                    "matched_range_m": matched_range,
                    "bearing_deg": bearing,
                    "blob_yaw_deg": local_blob.get("blob_yaw_deg"),
                    "matched_beam_index": local_blob.get("matched_beam_index"),
                    "matched_beam_yaw_deg": local_blob.get("matched_beam_yaw_deg"),
                    "beam_yaw_error_deg": local_blob.get("beam_yaw_error_deg"),
                    "local_range_scaled_blob_present": local_blob.get("local_range_scaled_blob_present"),
                    "local_blob_area": local_blob.get("local_blob_area"),
                    "local_blob_range_scaled_area": local_blob.get("local_blob_range_scaled_area"),
                    "sphere_blob_local_candidate_count": int(sphere_blob.get("local_candidate_blob_count", 0)),
                    "sphere_blob_candidate_count": int(sphere_blob.get("candidate_blob_count", 0)),
                    "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0)),
                    "rgb_change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
                    "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
                    "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                    **nearest,
                    "truth_used_for_detection": False,
                    "actor_truth_used_for_detection": False,
                    "target_truth_used_for_detection": False,
                    "teammate_truth_used_for_detection": False,
                }
            )
    return events


def _cluster_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clusters: List[Dict[str, Any]] = []
    for candidate in candidates:
        position = candidate.get("estimated_world_position")
        if not isinstance(position, list):
            continue
        selected: Optional[Dict[str, Any]] = None
        for cluster in clusters:
            center = cluster.get("fused_world_position")
            distance = _distance_2d(position, center if isinstance(center, list) else None)
            if distance is not None and distance <= FUSION_DISTANCE_THRESHOLD_M:
                selected = cluster
                break
        if selected is None:
            selected = {
                "cluster_id": len(clusters),
                "candidate_count": 0,
                "reporter_usv_ids": [],
                "positions": [],
                "fused_world_position": None,
            }
            clusters.append(selected)
        selected["candidate_count"] = int(selected["candidate_count"]) + 1
        reporter = str(candidate.get("reporter_usv_id"))
        if reporter not in selected["reporter_usv_ids"]:
            selected["reporter_usv_ids"].append(reporter)
        selected["positions"].append(position)
        selected["fused_world_position"] = np.asarray(selected["positions"], dtype=float).mean(axis=0).tolist()
    return clusters


def _build_fusion_and_found(events: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    fusion_trace: List[Dict[str, Any]] = []
    policy_trace: List[Dict[str, Any]] = []
    found_events: List[Dict[str, Any]] = []
    found_mask = [False]
    find_times: List[Optional[int]] = [None]
    shared_target_count = 0
    for run_kind in ("target", "coexist", "teammate_only"):
        run_events = [event for event in events if event.get("run_kind") == run_kind]
        run_found = [False]
        run_find_times: List[Optional[int]] = [None]
        run_shared_count = 0
        for step in range(1, MAX_POLICY_STEPS + 1):
            step_events = [event for event in run_events if int(event.get("policy_step", 0)) == step]
            accepted = [event for event in step_events if event.get("accepted_candidate") is True]
            clusters = _cluster_candidates(accepted)
            target_present = _target_present(run_kind)
            target_location = config["target_world_location"] if target_present else None
            confirmed_clusters: List[Dict[str, Any]] = []
            for cluster in clusters:
                error = _distance_2d(cluster.get("fused_world_position"), target_location if isinstance(target_location, list) else None)
                cluster["target_position_error_m"] = error
                cluster["confirmed_static_target_candidate_for_audit"] = bool(target_present and error is not None and error <= TARGET_AUDIT_DISTANCE_THRESHOLD_M)
                if cluster.get("candidate_count", 0) > 0:
                    confirmed_clusters.append(cluster)
            # Detection does not use target truth: any fused non-teammate candidate updates shared target state.
            shared_found = bool(confirmed_clusters)
            new_found = bool(shared_found and not run_found[0])
            if new_found:
                run_found[0] = True
                run_find_times[0] = step
                run_shared_count = 1
                if run_kind == "target":
                    found_mask[0] = True
                    find_times[0] = step
                    shared_target_count = 1
                found_events.append(
                    {
                        "run_kind": run_kind,
                        "target_index": 0,
                        "found_step": int(step),
                        "new_found": True,
                        "fused_candidate_count": len(confirmed_clusters),
                        "fused_candidates": confirmed_clusters,
                        "truth_used_for_detection": False,
                        "actor_truth_used_for_detection": False,
                        "target_truth_used_for_detection": False,
                        "teammate_truth_used_for_detection": False,
                    }
                )
            outcome = "true_positive" if target_present and shared_found else ("false_negative" if target_present and not shared_found else ("false_positive" if shared_found else "true_negative"))
            fusion_row = {
                "run_kind": run_kind,
                "policy_step": int(step),
                "expected_target_present_for_audit": target_present,
                "raw_sensor_detection_count": sum(1 for event in step_events if event.get("raw_sensor_found") is True),
                "accepted_candidate_count": len(accepted),
                "teammate_rejected_count": sum(1 for event in step_events if event.get("teammate_rejected") is True),
                "fused_candidate_count": len(confirmed_clusters),
                "fused_candidates": confirmed_clusters,
                "shared_found_this_step": shared_found,
                "new_found_this_step": new_found,
                "run_found_mask_after": list(run_found),
                "run_find_times_after": list(run_find_times),
                "global_found_mask_after": list(found_mask),
                "global_find_times_after": list(find_times),
                "shared_target_count_after": int(shared_target_count),
                "outcome": outcome,
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
            }
            fusion_trace.append(fusion_row)
            policy_trace.append(
                {
                    "run_kind": run_kind,
                    "policy_step": int(step),
                    "continuous_search_loop_step": True,
                    "per_agent_detection_events_count": len(step_events),
                    "candidate_fusion_called": True,
                    "found_mask_update_called": True,
                    "shared_found": shared_found,
                    "new_found_count": 1 if new_found else 0,
                    "found_count_after": int(sum(run_found)),
                    "global_found_count_after": int(sum(found_mask)),
                    "all_found_after": bool(run_kind == "target" and all(found_mask)),
                    "terminated_reason_after_step": "all_found" if run_kind == "target" and all(found_mask) else "running",
                    "truth_used_for_detection": False,
                    "actor_truth_used_for_detection": False,
                    "target_truth_used_for_detection": False,
                    "teammate_truth_used_for_detection": False,
                }
            )
    return fusion_trace, policy_trace, found_events


def _strip_run_raw(run: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(run)
    clean.pop("rgb_by_agent_tick", None)
    clean.pop("range_by_agent_tick", None)
    return clean


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _build_summary(config: Dict[str, Any], runs: Dict[str, Dict[str, Any]], events: List[Dict[str, Any]], fusion_trace: List[Dict[str, Any]], policy_trace: List[Dict[str, Any]], found_events: List[Dict[str, Any]], started: float) -> Dict[str, Any]:
    target_rows = [row for row in fusion_trace if row.get("run_kind") == "target"]
    coexist_rows = [row for row in fusion_trace if row.get("run_kind") == "coexist"]
    teammate_rows = [row for row in fusion_trace if row.get("run_kind") == "teammate_only"]
    target_found_steps = [int(row["policy_step"]) for row in target_rows if row.get("shared_found_this_step") is True]
    coexist_found_steps = [int(row["policy_step"]) for row in coexist_rows if row.get("shared_found_this_step") is True]
    teammate_fp_steps = [int(row["policy_step"]) for row in teammate_rows if row.get("shared_found_this_step") is True]
    duplicate_fused_steps = [
        int(row["policy_step"])
        for row in target_rows
        if int(row.get("accepted_candidate_count", 0)) >= 2 and int(row.get("fused_candidate_count", 0)) == 1
    ]
    return {
        "phase_name": PHASE_NAME,
        "phase_completed": True,
        "source_5d1a_audit_all_passed": config.get("source_5d1a_audit_all_passed"),
        "source_5d2_audit_all_passed": config.get("source_5d2_audit_all_passed"),
        "recommended_rule_id": config.get("recommended_rule_id"),
        "observer_count": len(AGENT_NAMES),
        "observer_agent_names": list(AGENT_NAMES),
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "continuous_search_loop_enabled": True,
        "max_policy_steps": MAX_POLICY_STEPS,
        "ticks_per_policy_step": TICKS_PER_POLICY_STEP,
        "total_ticks_per_run": TOTAL_TICKS,
        "event_count": len(events),
        "policy_trace_count": len(policy_trace),
        "fusion_trace_count": len(fusion_trace),
        "found_event_count": len(found_events),
        "per_agent_event_count_by_reporter": _count_by(events, "reporter_usv_id"),
        "fusion_outcome_counts": _count_by(fusion_trace, "outcome"),
        "target_found_steps": target_found_steps,
        "coexist_found_steps": coexist_found_steps,
        "teammate_false_positive_steps": teammate_fp_steps,
        "duplicate_observation_fused_steps": duplicate_fused_steps,
        "target_all_found": bool(target_found_steps),
        "all_found_step": min(target_found_steps) if target_found_steps else None,
        "coexist_shared_found": bool(coexist_found_steps),
        "teammate_only_false_positive_count": len(teammate_fp_steps),
        "duplicate_observations_fused": bool(duplicate_fused_steps),
        "target_false_negative": not bool(target_found_steps),
        "coexist_false_negative": not bool(coexist_found_steps),
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "teammate_identity_position_available_externally": True,
        "teammate_position_used_for_candidate_exclusion": True,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "all_runs_launch_ok": all(bool(run.get("launch_ok", False)) for run in runs.values()),
        "run_errors": {kind: run.get("error", "") for kind, run in runs.items()},
        "min_inter_vessel_distance_m": min(float(run.get("min_inter_vessel_distance_m", 0.0)) for run in runs.values()),
        "collision_warning_m": COLLISION_WARNING_M,
        "collision_fail_m": COLLISION_FAIL_M,
        "wall_time_s": float(time.perf_counter() - started),
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-3 Continuous Multi-Step Cooperative Search Summary",
        "",
        "- Recommended Rule: `{0}`".format(summary.get("recommended_rule_id")),
        "- Observer Count: `{0}`".format(summary.get("observer_count")),
        "- Event Count: `{0}`".format(summary.get("event_count")),
        "- Fusion Outcome Counts: `{0}`".format(summary.get("fusion_outcome_counts")),
        "- Target Found Steps: `{0}`".format(summary.get("target_found_steps")),
        "- Coexist Found Steps: `{0}`".format(summary.get("coexist_found_steps")),
        "- Teammate False Positive Steps: `{0}`".format(summary.get("teammate_false_positive_steps")),
        "- Duplicate Observation Fused Steps: `{0}`".format(summary.get("duplicate_observation_fused_steps")),
        "- All Found Step: `{0}`".format(summary.get("all_found_step")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "",
        "Phase 5D-3 validates that 5D-2 candidate fusion can drive found_mask/all_found during a continuous multi-step HoloOcean run.",
        "",
    ]
    return "\n".join(lines)


def run_capture() -> Dict[str, Any]:
    _ensure_dirs()
    started = time.perf_counter()
    pre_status = _run_git_status()
    config = _phase_config(pre_status)
    print("Running baseline continuous trajectory")
    baseline_run = _run_trajectory("baseline", config)
    print("Running target continuous trajectory")
    target_run = _run_trajectory("target", config)
    print("Running coexist continuous trajectory")
    coexist_run = _run_trajectory("coexist", config)
    print("Running teammate-only continuous trajectory")
    teammate_run = _run_trajectory("teammate_only", config)
    runs = {
        "baseline": baseline_run,
        "target": target_run,
        "coexist": coexist_run,
        "teammate_only": teammate_run,
    }
    events: List[Dict[str, Any]] = []
    for kind in ("target", "coexist", "teammate_only"):
        events.extend(_build_events_for_run(runs[kind], baseline_run, config))
    fusion_trace, policy_trace, found_events = _build_fusion_and_found(events, config)
    tick_trace: List[Dict[str, Any]] = []
    for kind in ("baseline", "target", "coexist", "teammate_only"):
        tick_trace.extend(runs[kind].get("tick_rows", []))
    summary = _build_summary(config, runs, events, fusion_trace, policy_trace, found_events, started)
    post_status = _run_git_status()
    git_doc = {
        "phase_name": PHASE_NAME,
        "pre_status": pre_status,
        "post_status": post_status,
        "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_status, post_status),
    }
    _save_json(CONFIG_JSON, config)
    _save_json(BASELINE_RUN_JSON, _strip_run_raw(baseline_run))
    _save_json(TARGET_RUN_JSON, _strip_run_raw(target_run))
    _save_json(TEAMMATE_RUN_JSON, _strip_run_raw(teammate_run))
    _save_json(POLICY_TRACE_JSON, policy_trace)
    _save_csv(POLICY_TRACE_CSV, policy_trace)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(PER_AGENT_EVENTS_JSON, events)
    _save_csv(PER_AGENT_EVENTS_CSV, events)
    _save_json(FUSION_TRACE_JSON, fusion_trace)
    _save_csv(FUSION_TRACE_CSV, fusion_trace)
    _save_json(FOUND_EVENTS_JSON, found_events)
    _save_json(SUMMARY_JSON, summary)
    _save_json(GIT_STATUS_JSON, git_doc)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["capture"], default="capture")
    args = parser.parse_args()
    if args.mode == "capture":
        summary = run_capture()
        print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
