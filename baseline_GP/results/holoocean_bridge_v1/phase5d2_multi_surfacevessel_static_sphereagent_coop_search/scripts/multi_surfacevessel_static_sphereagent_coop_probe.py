"""Phase 5D-2: multi-SurfaceVessel cooperative static SphereAgent search.

This phase keeps the 5D-1A target profile:

    teammate agents: SurfaceVessel
    target agent:    static SphereAgent
    detection rule:  sphere_blob_local_range_scaled_any_hit

The new behavior validated here is phase-local cooperative evidence handling:
each SurfaceVessel observer emits its own detection event, events are shared as
target candidates, known teammate positions are used for exclusion, and nearby
candidates are fused into a shared static target hypothesis.

Truth labels and actor locations are used only for scenario setup and audit.
They are not used to trigger the visual/range detection rule.
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d2_multi_surfacevessel_static_sphereagent_coop_search"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
SOURCE_5D1A_PHASE_NAME = "phase5d1a_sphere_blob_local_range_scaled_validation"
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

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_config.json")
SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_scene_results.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_tick_trace.csv")
PER_AGENT_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_per_agent_detection_events.json")
PER_AGENT_EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d2_per_agent_detection_events.csv")
FUSION_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_candidate_fusion_trace.json")
FUSION_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d2_candidate_fusion_trace.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d2_coop_summary.md")

CAPTURE_TICKS = 12
RGB_CAMERA_NAME = "FrontRGBCamera"
FAN_RANGEFINDER_PREFIX = "FanRangeFinder"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
TARGET_Z = 0.5
TEAMMATE_Z = 0.0
OBSERVER_Z = 0.0
RELIABLE_DISTANCE_LIMIT_M = 35.0
TEAMMATE_EXCLUSION_RADIUS_M = 10.0
FUSION_DISTANCE_THRESHOLD_M = 15.0
TARGET_AUDIT_DISTANCE_THRESHOLD_M = 15.0
AGENT_NAMES = ["sv0", "sv1"]


def _load_5d1a_module() -> Any:
    spec = importlib.util.spec_from_file_location("phase5d1a_local_probe", SOURCE_5D1A_PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load 5D-1A probe module from {0}".format(SOURCE_5D1A_PROBE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5D1A = _load_5d1a_module()


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


def _base_observers() -> List[Dict[str, Any]]:
    return [
        {"agent_name": "sv0", "location": [0.0, -5.0, OBSERVER_Z], "rotation": [0.0, 0.0, 0.0]},
        {"agent_name": "sv1", "location": [0.0, 5.0, OBSERVER_Z], "rotation": [0.0, 0.0, 0.0]},
    ]


def _actor(agent_name: str, agent_type: str, location: List[float], z: float) -> Dict[str, Any]:
    loc = [float(location[0]), float(location[1]), float(z)]
    return {
        "agent_name": agent_name,
        "agent_type": agent_type,
        "location": loc,
        "rotation": [0.0, 0.0, 0.0],
    }


def _build_scenes() -> List[Dict[str, Any]]:
    observers = _base_observers()
    baseline = {
        "name": "baseline_two_observers_search_pose",
        "scenario_kind": "baseline",
        "sequence_step": 0,
        "baseline_scene": None,
        "observers": observers,
        "target": None,
        "extra_teammates": [],
        "expected_target_present_for_audit": False,
        "expected_duplicate_observation_for_audit": False,
        "description": "Two SurfaceVessel observers at the shared search pose, no target and no extra teammate.",
    }
    baseline_name = str(baseline["name"])
    return [
        baseline,
        {
            "name": "target_sphere_duplicate_20m_two_observers",
            "scenario_kind": "target",
            "sequence_step": 1,
            "baseline_scene": baseline_name,
            "observers": observers,
            "target": _actor("target", TARGET_AGENT_TYPE, [20.0, 0.0, TARGET_Z], TARGET_Z),
            "extra_teammates": [],
            "expected_target_present_for_audit": True,
            "expected_duplicate_observation_for_audit": True,
            "description": "Static SphereAgent is inside both observers' 35 m reliable sector and should produce duplicate candidate observations.",
        },
        {
            "name": "target_sphere_35m_with_surfacevessel_teammate",
            "scenario_kind": "target_with_teammate",
            "sequence_step": 2,
            "baseline_scene": baseline_name,
            "observers": observers,
            "target": _actor("target", TARGET_AGENT_TYPE, [35.0, -5.0, TARGET_Z], TARGET_Z),
            "extra_teammates": [_actor("teammate_extra0", TEAMMATE_AGENT_TYPE, [22.0, 12.0, TEAMMATE_Z], TEAMMATE_Z)],
            "expected_target_present_for_audit": True,
            "expected_duplicate_observation_for_audit": False,
            "description": "35 m static SphereAgent with an extra SurfaceVessel teammate in view.",
        },
        {
            "name": "teammate_only_surfacevessel_at_20m_target_like_pose",
            "scenario_kind": "teammate_only",
            "sequence_step": 3,
            "baseline_scene": baseline_name,
            "observers": observers,
            "target": None,
            "extra_teammates": [_actor("teammate_extra0", TEAMMATE_AGENT_TYPE, [20.0, 0.0, TEAMMATE_Z], TEAMMATE_Z)],
            "expected_target_present_for_audit": False,
            "expected_duplicate_observation_for_audit": False,
            "description": "A SurfaceVessel teammate occupies the same geometry as the 20 m target case and must not become a target.",
        },
        {
            "name": "teammate_only_surfacevessel_at_35m_target_like_pose",
            "scenario_kind": "teammate_only",
            "sequence_step": 4,
            "baseline_scene": baseline_name,
            "observers": observers,
            "target": None,
            "extra_teammates": [_actor("teammate_extra0", TEAMMATE_AGENT_TYPE, [35.0, -5.0, TEAMMATE_Z], TEAMMATE_Z)],
            "expected_target_present_for_audit": False,
            "expected_duplicate_observation_for_audit": False,
            "description": "A SurfaceVessel teammate occupies the 35 m target geometry and must not become a target.",
        },
    ]


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    scenes = _build_scenes()
    source_audit = _load_json(SOURCE_5D1A_AUDIT) if os.path.exists(SOURCE_5D1A_AUDIT) else {}
    return {
        "phase_name": PHASE_NAME,
        "phase_goal": "Multi-SurfaceVessel cooperative search for a static SphereAgent using 5D-1A perception events.",
        "source_5d1a_phase_name": SOURCE_5D1A_PHASE_NAME,
        "source_5d1a_probe": SOURCE_5D1A_PROBE,
        "source_5d1a_audit": SOURCE_5D1A_AUDIT,
        "source_5d1a_audit_all_passed": source_audit.get("all_passed"),
        "recommended_rule_id": "sphere_blob_local_range_scaled_any_hit",
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "observer_count": len(AGENT_NAMES),
        "observer_agent_names": list(AGENT_NAMES),
        "minimum_observer_count": 2,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "teammate_exclusion_radius_m": TEAMMATE_EXCLUSION_RADIUS_M,
        "fusion_distance_threshold_m": FUSION_DISTANCE_THRESHOLD_M,
        "target_audit_distance_threshold_m": TARGET_AUDIT_DISTANCE_THRESHOLD_M,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "candidate_fields_required": ["reporter_usv_id", "sensor_id", "estimated_world_position", "matched_range_m", "bearing_deg"],
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
        "world": "OpenWater",
        "package_name": "Ocean",
        "capture_ticks": CAPTURE_TICKS,
        "rgb_camera_name": RGB_CAMERA_NAME,
        "fan_rangefinder_prefix": FAN_RANGEFINDER_PREFIX,
        "scenes": scenes,
        "planned_scene_counts": {
            "total": len(scenes),
            "baseline": sum(1 for scene in scenes if scene.get("scenario_kind") == "baseline"),
            "target": sum(1 for scene in scenes if scene.get("scenario_kind") == "target"),
            "target_with_teammate": sum(1 for scene in scenes if scene.get("scenario_kind") == "target_with_teammate"),
            "teammate_only": sum(1 for scene in scenes if scene.get("scenario_kind") == "teammate_only"),
        },
        "pre_git_status": pre_git_status or [],
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _camera_sensor() -> Dict[str, Any]:
    return P5D1A._camera_sensor()


def _fan_rangefinder_sensors() -> List[Dict[str, Any]]:
    return P5D1A._fan_rangefinder_sensors()


def _fan_rangefinder_names() -> List[str]:
    return ["{0}_{1:02d}".format(FAN_RANGEFINDER_PREFIX, index) for index in range(len(P5D1A.FAN_YAW_DEGREES))]


def _control_scheme(agent_type: str) -> int:
    return P5D1A._control_scheme(agent_type)


def _zero_action(agent_type: str) -> np.ndarray:
    return P5D1A._zero_action(agent_type)


def _scenario_config(scene: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    agents: List[Dict[str, Any]] = []
    for observer in scene.get("observers", []):
        agents.append(
            {
                "agent_name": str(observer["agent_name"]),
                "agent_type": TEAMMATE_AGENT_TYPE,
                "sensors": [
                    {"sensor_type": "LocationSensor", "socket": "COM"},
                    {"sensor_type": "GPSSensor", "socket": "COM"},
                    {"sensor_type": "OrientationSensor", "socket": "COM"},
                    _camera_sensor(),
                ]
                + _fan_rangefinder_sensors(),
                "control_scheme": 0,
                "location": list(observer["location"]),
                "rotation": list(observer.get("rotation", [0.0, 0.0, 0.0])),
            }
        )
    target = scene.get("target")
    if isinstance(target, dict):
        agent_type = str(target["agent_type"])
        agents.append(
            {
                "agent_name": str(target["agent_name"]),
                "agent_type": agent_type,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(agent_type),
                "location": list(target["location"]),
                "rotation": list(target.get("rotation", [0.0, 0.0, 0.0])),
            }
        )
    for teammate in scene.get("extra_teammates", []):
        if not isinstance(teammate, dict):
            continue
        agent_type = str(teammate["agent_type"])
        agents.append(
            {
                "agent_name": str(teammate["agent_name"]),
                "agent_type": agent_type,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(agent_type),
                "location": list(teammate["location"]),
                "rotation": list(teammate.get("rotation", [0.0, 0.0, 0.0])),
            }
        )
    return {
        "name": "phase5d2_{0}".format(scene["name"]),
        "world": "OpenWater",
        "package_name": "Ocean",
        "main_agent": "sv0",
        "agents": agents,
    }


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


def _array_stats(value: Any) -> Dict[str, Any]:
    return P5D1A._array_stats(value)


def _save_preview(path: str, value: Any) -> bool:
    return P5D1A._save_preview(path, value)


def _save_agent_artifacts(scene_name: str, agent_name: str, rgb: Any) -> Dict[str, Any]:
    artifacts = {"rgb_raw_saved": False, "rgb_raw_path": None, "rgb_preview_saved": False, "rgb_preview_path": None}
    if rgb is None:
        return artifacts
    safe = "{0}_{1}".format(scene_name, agent_name)
    raw_path = os.path.join(PHASE_DIR, "visuals", "{0}_rgb_raw.npy".format(safe))
    preview_path = os.path.join(PHASE_DIR, "visuals", "{0}_rgb.png".format(safe))
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    np.save(raw_path, np.asarray(rgb))
    artifacts["rgb_raw_saved"] = True
    artifacts["rgb_raw_path"] = raw_path
    artifacts["rgb_preview_saved"] = _save_preview(preview_path, rgb)
    artifacts["rgb_preview_path"] = preview_path if artifacts["rgb_preview_saved"] else None
    return artifacts


def _run_scene(scene: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    import holoocean

    scene_name = str(scene["name"])
    tick_rows: List[Dict[str, Any]] = []
    first_rgb_by_agent: Dict[str, Any] = {}
    first_range_by_agent: Dict[str, Any] = {}
    launch_ok = False
    error = ""
    started = time.perf_counter()
    try:
        with holoocean.make(scenario_cfg=_scenario_config(scene, config)) as env:
            launch_ok = True
            for tick in range(1, CAPTURE_TICKS + 1):
                for observer in scene.get("observers", []):
                    env.act(str(observer["agent_name"]), _zero_action(TEAMMATE_AGENT_TYPE))
                target = scene.get("target")
                if isinstance(target, dict):
                    env.act(str(target["agent_name"]), _zero_action(str(target["agent_type"])))
                for teammate in scene.get("extra_teammates", []):
                    if isinstance(teammate, dict):
                        env.act(str(teammate["agent_name"]), _zero_action(str(teammate["agent_type"])))
                state = env.tick()
                for observer in scene.get("observers", []):
                    agent_name = str(observer["agent_name"])
                    rgb = get_sensor_vector(state, agent_name, RGB_CAMERA_NAME)
                    fan_range = _aggregate_fan_range(state, agent_name)
                    if agent_name not in first_rgb_by_agent and rgb is not None:
                        first_rgb_by_agent[agent_name] = np.asarray(rgb).copy()
                    if agent_name not in first_range_by_agent and fan_range is not None:
                        first_range_by_agent[agent_name] = np.asarray(fan_range).copy()
                    rsum = P5D1A._range_summary(fan_range)
                    tick_rows.append(
                        {
                            "scene": scene_name,
                            "tick": int(tick),
                            "agent_name": agent_name,
                            "rgb_present": rgb is not None,
                            "rangefinder_raw_beams": rsum.get("raw"),
                            "rangefinder_hit_beam_indices": rsum.get("hit_beam_indices"),
                            "any_rangefinder_hit": bool(rsum.get("any_hit", False)),
                            "rangefinder_min_positive_range_m": rsum.get("min_positive_range_m"),
                        }
                    )
    except Exception as exc:
        error = "{0}: {1}".format(type(exc).__name__, exc)
        tick_rows.append({"scene": scene_name, "tick": 0, "scenario_error": error, "traceback": traceback.format_exc()})

    agent_results: Dict[str, Dict[str, Any]] = {}
    for observer in scene.get("observers", []):
        agent_name = str(observer["agent_name"])
        rgb = first_rgb_by_agent.get(agent_name)
        fan_range = first_range_by_agent.get(agent_name)
        agent_results[agent_name] = {
            "agent_name": agent_name,
            "observer_world_location": list(observer["location"]),
            "observer_rotation": list(observer.get("rotation", [0.0, 0.0, 0.0])),
            "rgb_stats": _array_stats(rgb),
            "rangefinder_summary": P5D1A._range_summary(fan_range),
            "first_rgb_raw": rgb,
            "artifacts": _save_agent_artifacts(scene_name, agent_name, rgb),
        }

    target = scene.get("target")
    extra_teammates = scene.get("extra_teammates", [])
    known_teammates = []
    for observer in scene.get("observers", []):
        known_teammates.append(
            {
                "agent_name": str(observer["agent_name"]),
                "agent_type": TEAMMATE_AGENT_TYPE,
                "location": list(observer["location"]),
                "is_observer": True,
            }
        )
    for teammate in extra_teammates:
        if isinstance(teammate, dict):
            known_teammates.append(
                {
                    "agent_name": str(teammate["agent_name"]),
                    "agent_type": str(teammate["agent_type"]),
                    "location": list(teammate["location"]),
                    "is_observer": False,
                }
            )
    return {
        "scene": scene_name,
        "scenario_kind": scene.get("scenario_kind"),
        "sequence_step": scene.get("sequence_step"),
        "baseline_scene": scene.get("baseline_scene"),
        "expected_target_present_for_audit": bool(scene.get("expected_target_present_for_audit", False)),
        "expected_duplicate_observation_for_audit": bool(scene.get("expected_duplicate_observation_for_audit", False)),
        "target_world_location": list(target["location"]) if isinstance(target, dict) else None,
        "target_agent_type": str(target["agent_type"]) if isinstance(target, dict) else None,
        "known_teammates": known_teammates,
        "observer_count": len(scene.get("observers", [])),
        "extra_teammate_count": len(extra_teammates),
        "launch_ok": launch_ok,
        "error": error,
        "wall_time_s": float(time.perf_counter() - started),
        "agent_results": agent_results,
        "tick_rows": tick_rows,
    }


def _strip_scene_raw(result: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(result)
    clean_agents: Dict[str, Any] = {}
    for agent_name, agent_result in result.get("agent_results", {}).items():
        agent_clean = dict(agent_result)
        agent_clean.pop("first_rgb_raw", None)
        clean_agents[str(agent_name)] = agent_clean
    clean["agent_results"] = clean_agents
    return clean


def _capture_scenes(config: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    scene_results: Dict[str, Dict[str, Any]] = {}
    tick_trace: List[Dict[str, Any]] = []
    for index, scene in enumerate(config["scenes"], start=1):
        print("[{0}/{1}] Capturing {2}".format(index, len(config["scenes"]), scene["name"]))
        result = _run_scene(scene, config)
        scene_results[str(scene["name"])] = result
        tick_trace.extend(result.get("tick_rows", []))
    return scene_results, tick_trace


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


def _event_outcome(target_present: bool, accepted: bool) -> str:
    if target_present and accepted:
        return "candidate_positive"
    if target_present and not accepted:
        return "candidate_negative"
    if not target_present and accepted:
        return "false_positive_candidate"
    return "true_negative_event"


def _build_events(scene_results: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for scene in config["scenes"]:
        scene_name = str(scene["name"])
        result = scene_results.get(scene_name, {})
        baseline_scene = str(scene.get("baseline_scene") or scene_name)
        baseline_result = scene_results.get(baseline_scene, {})
        target_present = bool(scene.get("expected_target_present_for_audit", False))
        target_location = result.get("target_world_location")
        known_teammates = result.get("known_teammates", [])
        for agent_name in AGENT_NAMES:
            agent_result = result.get("agent_results", {}).get(agent_name, {})
            baseline_agent = baseline_result.get("agent_results", {}).get(agent_name, {})
            rgb = agent_result.get("first_rgb_raw")
            baseline_rgb = baseline_agent.get("first_rgb_raw")
            range_summary = agent_result.get("rangefinder_summary", {})
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
            observer_location = agent_result.get("observer_world_location")
            estimated_position = _estimate_world_position(observer_location, bearing, matched_range)
            nearest_teammate = _nearest_teammate(estimated_position, known_teammates)
            teammate_rejected = bool(raw_found and nearest_teammate.get("within_teammate_exclusion_radius") is True)
            range_limited = bool(matched_range is not None and float(matched_range) <= RELIABLE_DISTANCE_LIMIT_M + 1.0)
            accepted = bool(raw_found and range_limited and not teammate_rejected)
            target_distance = _distance_2d(estimated_position, target_location if isinstance(target_location, list) else None)
            events.append(
                {
                    "scene": scene_name,
                    "scenario_kind": scene.get("scenario_kind"),
                    "sequence_step": scene.get("sequence_step"),
                    "reporter_usv_id": agent_name,
                    "agent_id": agent_name,
                    "sensor_id": "{0}+fan_rangefinder".format(RGB_CAMERA_NAME),
                    "recommended_rule_id": config.get("recommended_rule_id"),
                    "expected_target_present_for_audit": target_present,
                    "expected_duplicate_observation_for_audit": bool(scene.get("expected_duplicate_observation_for_audit", False)),
                    "raw_sensor_found": raw_found,
                    "accepted_candidate": accepted,
                    "teammate_rejected": teammate_rejected,
                    "range_limited": range_limited,
                    "outcome": _event_outcome(target_present, accepted),
                    "estimated_world_position": estimated_position,
                    "target_world_location_for_audit": target_location,
                    "target_position_error_m": target_distance,
                    "observer_world_location": observer_location,
                    "matched_range_m": matched_range,
                    "bearing_deg": bearing,
                    "blob_yaw_deg": local_blob.get("blob_yaw_deg"),
                    "matched_beam_index": local_blob.get("matched_beam_index"),
                    "matched_beam_yaw_deg": local_blob.get("matched_beam_yaw_deg"),
                    "beam_yaw_error_deg": local_blob.get("beam_yaw_error_deg"),
                    "local_range_scaled_blob_present": local_blob.get("local_range_scaled_blob_present"),
                    "local_range_scaled_best_blob": local_blob.get("local_range_scaled_best_blob"),
                    "local_blob_area": local_blob.get("local_blob_area"),
                    "local_blob_range_scaled_area": local_blob.get("local_blob_range_scaled_area"),
                    "local_blob_min_range_scaled_area": local_blob.get("local_blob_min_range_scaled_area"),
                    "sphere_blob_local_candidate_count": int(sphere_blob.get("local_candidate_blob_count", 0)),
                    "sphere_blob_candidate_count": int(sphere_blob.get("candidate_blob_count", 0)),
                    "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0)),
                    "rgb_change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
                    "rangefinder_raw_beams": range_summary.get("raw"),
                    "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
                    "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                    **nearest_teammate,
                    "teammate_exclusion_radius_m": TEAMMATE_EXCLUSION_RADIUS_M,
                    "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
                    "rgb_artifact": agent_result.get("artifacts", {}).get("rgb_preview_path"),
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
        chosen: Optional[Dict[str, Any]] = None
        for cluster in clusters:
            center = cluster.get("fused_world_position")
            distance = _distance_2d(position, center if isinstance(center, list) else None)
            if distance is not None and distance <= FUSION_DISTANCE_THRESHOLD_M:
                chosen = cluster
                break
        if chosen is None:
            chosen = {
                "cluster_id": len(clusters),
                "candidate_count": 0,
                "reporter_usv_ids": [],
                "source_event_indices": [],
                "positions": [],
                "fused_world_position": None,
            }
            clusters.append(chosen)
        chosen["candidate_count"] = int(chosen["candidate_count"]) + 1
        if str(candidate.get("reporter_usv_id")) not in chosen["reporter_usv_ids"]:
            chosen["reporter_usv_ids"].append(str(candidate.get("reporter_usv_id")))
        chosen["source_event_indices"].append(int(candidate.get("event_index", -1)))
        chosen["positions"].append(position)
        arr = np.asarray(chosen["positions"], dtype=float)
        chosen["fused_world_position"] = arr.mean(axis=0).tolist()
    return clusters


def _fusion_outcome(target_present: bool, found: bool) -> str:
    if target_present and found:
        return "true_positive"
    if target_present and not found:
        return "false_negative"
    if not target_present and found:
        return "false_positive"
    return "true_negative"


def _build_fusion_trace(events: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    indexed_events: List[Dict[str, Any]] = []
    for idx, event in enumerate(events):
        row = dict(event)
        row["event_index"] = idx
        indexed_events.append(row)

    trace: List[Dict[str, Any]] = []
    for scene in config["scenes"]:
        scene_name = str(scene["name"])
        scene_events = [event for event in indexed_events if event.get("scene") == scene_name]
        accepted = [event for event in scene_events if event.get("accepted_candidate") is True]
        clusters = _cluster_candidates(accepted)
        target_present = bool(scene.get("expected_target_present_for_audit", False))
        target_location = next((event.get("target_world_location_for_audit") for event in scene_events if event.get("target_world_location_for_audit") is not None), None)
        for cluster in clusters:
            error = _distance_2d(cluster.get("fused_world_position"), target_location if isinstance(target_location, list) else None)
            cluster["target_position_error_m"] = error
            cluster["confirmed_static_target_candidate"] = bool(
                target_present
                and error is not None
                and error <= TARGET_AUDIT_DISTANCE_THRESHOLD_M
            )
        scene_found = bool(clusters) if not target_present else any(cluster.get("confirmed_static_target_candidate") for cluster in clusters)
        trace.append(
            {
                "scene": scene_name,
                "scenario_kind": scene.get("scenario_kind"),
                "sequence_step": scene.get("sequence_step"),
                "expected_target_present_for_audit": target_present,
                "expected_duplicate_observation_for_audit": bool(scene.get("expected_duplicate_observation_for_audit", False)),
                "raw_sensor_detection_count": sum(1 for event in scene_events if event.get("raw_sensor_found") is True),
                "accepted_candidate_count": len(accepted),
                "teammate_rejected_count": sum(1 for event in scene_events if event.get("teammate_rejected") is True),
                "fused_candidate_count": len(clusters),
                "fused_candidates": clusters,
                "shared_found": scene_found,
                "outcome": _fusion_outcome(target_present, scene_found),
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
            }
        )
    return trace


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _summarize(config: Dict[str, Any], scene_results: Dict[str, Dict[str, Any]], events: List[Dict[str, Any]], fusion_trace: List[Dict[str, Any]], started: float) -> Dict[str, Any]:
    target_fusion = [row for row in fusion_trace if row.get("scenario_kind") in ("target", "target_with_teammate")]
    teammate_fusion = [row for row in fusion_trace if row.get("scenario_kind") == "teammate_only"]
    baseline_fusion = [row for row in fusion_trace if row.get("scenario_kind") == "baseline"]
    duplicate_rows = [row for row in fusion_trace if row.get("expected_duplicate_observation_for_audit") is True]
    target_events = [row for row in events if row.get("expected_target_present_for_audit") is True]
    teammate_events = [row for row in events if row.get("scenario_kind") == "teammate_only"]
    accepted_events = [row for row in events if row.get("accepted_candidate") is True]
    search_found_step = next((row.get("sequence_step") for row in target_fusion if row.get("shared_found") is True), None)
    return {
        "phase_name": PHASE_NAME,
        "phase_completed": True,
        "source_5d1a_phase_name": SOURCE_5D1A_PHASE_NAME,
        "source_5d1a_audit_all_passed": config.get("source_5d1a_audit_all_passed"),
        "recommended_rule_id": config.get("recommended_rule_id"),
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "observer_count": len(AGENT_NAMES),
        "observer_agent_names": list(AGENT_NAMES),
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "teammate_identity_position_available_externally": True,
        "teammate_position_used_for_candidate_exclusion": True,
        "teammate_exclusion_radius_m": TEAMMATE_EXCLUSION_RADIUS_M,
        "fusion_distance_threshold_m": FUSION_DISTANCE_THRESHOLD_M,
        "target_audit_distance_threshold_m": TARGET_AUDIT_DISTANCE_THRESHOLD_M,
        "scene_count": len(fusion_trace),
        "planned_scene_counts": config.get("planned_scene_counts"),
        "event_count": len(events),
        "accepted_candidate_count": len(accepted_events),
        "per_agent_event_count_by_reporter": _count_by(events, "reporter_usv_id"),
        "fusion_outcome_counts": _count_by(fusion_trace, "outcome"),
        "target_fusion_outcome_counts": _count_by(target_fusion, "outcome"),
        "teammate_fusion_outcome_counts": _count_by(teammate_fusion, "outcome"),
        "baseline_fusion_outcome_counts": _count_by(baseline_fusion, "outcome"),
        "target_false_negative_scenes": [str(row["scene"]) for row in target_fusion if row.get("shared_found") is not True],
        "teammate_false_positive_scenes": [str(row["scene"]) for row in teammate_fusion if row.get("shared_found") is True],
        "baseline_false_positive_scenes": [str(row["scene"]) for row in baseline_fusion if row.get("shared_found") is True],
        "target_event_accepted_count": sum(1 for row in target_events if row.get("accepted_candidate") is True),
        "teammate_event_accepted_count": sum(1 for row in teammate_events if row.get("accepted_candidate") is True),
        "duplicate_merge_scenes": [
            str(row["scene"])
            for row in duplicate_rows
            if int(row.get("accepted_candidate_count", 0)) >= 2 and int(row.get("fused_candidate_count", 0)) == 1
        ],
        "duplicate_merge_failed_scenes": [
            str(row["scene"])
            for row in duplicate_rows
            if not (int(row.get("accepted_candidate_count", 0)) >= 2 and int(row.get("fused_candidate_count", 0)) == 1)
        ],
        "shared_target_found": any(row.get("shared_found") is True for row in target_fusion),
        "shared_target_found_step": search_found_step,
        "all_scene_launch_ok": all(bool(row.get("launch_ok", False)) for row in scene_results.values()),
        "all_observer_rgb_output": all(
            bool(agent_result.get("rgb_stats", {}).get("present", False))
            for scene_result in scene_results.values()
            for agent_result in scene_result.get("agent_results", {}).values()
        ),
        "all_observer_rangefinder_output": all(
            bool(agent_result.get("rangefinder_summary", {}).get("present", False))
            for scene_result in scene_results.values()
            for agent_result in scene_result.get("agent_results", {}).values()
        ),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "wall_time_s": float(time.perf_counter() - started),
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-2 Multi-SurfaceVessel Static SphereAgent Cooperative Search Summary",
        "",
        "- Recommended Rule: `{0}`".format(summary.get("recommended_rule_id")),
        "- Observer Count: `{0}`".format(summary.get("observer_count")),
        "- Scene Count: `{0}`".format(summary.get("scene_count")),
        "- Event Count: `{0}`".format(summary.get("event_count")),
        "- Fusion Outcome Counts: `{0}`".format(summary.get("fusion_outcome_counts")),
        "- Target Fusion Outcome Counts: `{0}`".format(summary.get("target_fusion_outcome_counts")),
        "- Teammate Fusion Outcome Counts: `{0}`".format(summary.get("teammate_fusion_outcome_counts")),
        "- Duplicate Merge Scenes: `{0}`".format(summary.get("duplicate_merge_scenes")),
        "- Target False Negative Scenes: `{0}`".format(summary.get("target_false_negative_scenes")),
        "- Teammate False Positive Scenes: `{0}`".format(summary.get("teammate_false_positive_scenes")),
        "- Shared Target Found: `{0}`".format(summary.get("shared_target_found")),
        "- Reliable Distance Limit: `{0}`".format(summary.get("reliable_distance_limit_m")),
        "",
        "Phase 5D-2 uses 5D-1A perception as per-agent evidence and validates phase-local candidate sharing, teammate exclusion, and target-candidate fusion.",
        "",
    ]
    return "\n".join(lines)


def run_capture() -> Dict[str, Any]:
    _ensure_dirs()
    started = time.perf_counter()
    pre_status = _run_git_status()
    config = _phase_config(pre_status)
    scene_results, tick_trace = _capture_scenes(config)
    events = _build_events(scene_results, config)
    fusion_trace = _build_fusion_trace(events, config)
    summary = _summarize(config, scene_results, events, fusion_trace, started)
    post_status = _run_git_status()
    git_doc = {
        "phase_name": PHASE_NAME,
        "pre_status": pre_status,
        "post_status": post_status,
        "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_status, post_status),
    }

    _save_json(CONFIG_JSON, config)
    _save_json(SCENE_RESULTS_JSON, {name: _strip_scene_raw(result) for name, result in scene_results.items()})
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(PER_AGENT_EVENTS_JSON, events)
    _save_csv(PER_AGENT_EVENTS_CSV, events)
    _save_json(FUSION_TRACE_JSON, fusion_trace)
    _save_csv(FUSION_TRACE_CSV, fusion_trace)
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
