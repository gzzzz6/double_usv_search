"""Phase 5D-1A distance focus probe: 25 m and 30 m.

This phase stress-tests the heterogeneous static target rule from 5D-0:

    observer: SurfaceVessel
    target:   static SphereAgent
    negative: SurfaceVessel teammate-like actors

It does not use actor truth to trigger detection. Truth labels are used only
after capture to summarize target-only, teammate-only, and coexistence outcomes.
"""

from __future__ import annotations

import argparse
import csv
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

from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world  # noqa: E402
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d1a_distance_focus_25m_30m"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

CAL_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_calibration_config.json")
CAL_SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_calibration_scene_results.json")
CAL_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_calibration_tick_trace.json")
CAL_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1a_calibration_tick_trace.csv")
RECOMPUTED_EVIDENCE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_recomputed_rgb_evidence.json")
CANDIDATE_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_candidate_rule_matrix.json")
CANDIDATE_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1a_candidate_rule_matrix.csv")
CANDIDATE_RULE_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_candidate_rule_summary.json")
RECOMMENDED_RULE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_recommended_candidate_rule.json")
CAL_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_calibration_summary.json")
CAL_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_calibration_git_status.json")
CAL_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d1a_calibration_summary.md")

VAL_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_config.json")
VAL_SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_scene_results.json")
VAL_DETECTION_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_detection_events.json")
VAL_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_rule_matrix.json")
VAL_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_rule_matrix.csv")
VAL_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_tick_trace.json")
VAL_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_tick_trace.csv")
VAL_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_summary.json")
VAL_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1a_validation_git_status.json")
VAL_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d1a_validation_summary.md")

CAPTURE_TICKS = 12
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "FrontRGBCamera"
FAN_RANGEFINDER_PREFIX = "FanRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
FAN_YAW_DEGREES = [30.0, 25.0, 20.0, 15.0, 10.0, 5.0, 0.0, -5.0, -10.0, -15.0, -20.0, -25.0, -30.0]
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
OVERLAP_MIN_VALUES = list(range(1, 13))
CHANGED_PIXELS_MIN_VALUES = [0, 5, 10, 15, 20, 40, 80, 120, 200]
SPHERE_BLOB_DIFF_THRESHOLD = 20.0
SPHERE_BLOB_MIN_RGB = 180
SPHERE_BLOB_NEUTRAL_TOLERANCE = 35
SPHERE_BLOB_MIN_AREA = 4
SPHERE_BLOB_MIN_ASPECT = 0.5
SPHERE_BLOB_MAX_ASPECT = 2.5
SPHERE_BLOB_MIN_FILL = 0.7
SPHERE_BLOB_MIN_CY = 124.0
SPHERE_BLOB_MIN_AREA_RATIO = 0.6
SPHERE_BLOB_CLOSE_KERNEL_W = 1
SPHERE_BLOB_CLOSE_KERNEL_H = 3

OBSERVER_CELL = [23, 20]
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_NEGATIVE_AGENT_TYPE = "SurfaceVessel"
TARGET_Z = 0.5
TEAMMATE_Z = 0.0
TARGET_DISTANCES_M = [25.0, 30.0]
TEAMMATE_SINGLE_DISTANCES_M = [25.0, 30.0]
TEAMMATE_EDGE_DISTANCES_M: List[float] = []
FAN_TEST_ANGLES = [
    {"label": "left_outer", "angle_deg": 25.0},
    {"label": "left_inner", "angle_deg": 15.0},
    {"label": "center", "angle_deg": 0.0},
    {"label": "right_inner", "angle_deg": -15.0},
    {"label": "right_outer", "angle_deg": -25.0},
]
TEAMMATE_EDGE_ANGLES = [
    {"label": "left_edge", "angle_deg": 30.0},
    {"label": "right_edge", "angle_deg": -30.0},
]
RGB_SIGNATURE_CALIBRATION_DISTANCE_M = 10.0
RGB_SIGNATURE_CALIBRATION_SCENE = "calibration_sphere_front_center_10m"
FIXED_RECOMMENDED_RULE = {
    "rule_id": "sphere_blob_any_hit",
    "rule_name": "sphere_blob_any_hit",
    "rule_family": "sphere_blob",
    "target_overlap_min": None,
    "rgb_changed_pixels_min": None,
    "uses_rgb_signature": False,
    "uses_sphere_blob": True,
    "uses_rangefinder": True,
    "recommended_for_holoocean_rerun": True,
    "source_phase": "phase5d0_sphereagent_static_target_calibration",
}


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
            out: Dict[str, Any] = {}
            for key in keys:
                value = row.get(key)
                out[key] = json.dumps(_json_safe(value), sort_keys=True) if isinstance(value, (dict, list, tuple)) else _json_safe(value)
            writer.writerow(out)
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


def _load_adapter_config() -> Tuple[Any, np.ndarray, Dict[str, Any]]:
    nav_map_prior, spec = load_scene_map_npz(MAP_NPZ)
    adapter_config = scene_map_config_from_spec(spec)
    return adapter_config, nav_map_prior, spec


def _cell_world(cell: List[int]) -> List[float]:
    adapter_config, _, _ = _load_adapter_config()
    world = grid_to_world(tuple(int(v) for v in cell), config=adapter_config)
    return [float(world[0]), float(world[1]), 0.0]


def _offset_world(origin: List[float], forward_m: float, lateral_m: float = 0.0, z: float = 0.0) -> List[float]:
    return [float(origin[0]) + float(forward_m), float(origin[1]) + float(lateral_m), float(z)]


def _angle_lateral(forward_m: float, angle_deg: float) -> float:
    return float(math.tan(math.radians(float(angle_deg))) * float(forward_m))


def _object_spec(agent_type: str, origin: List[float], forward_m: float, angle_deg: float, z: float) -> Dict[str, Any]:
    lateral_m = _angle_lateral(forward_m, angle_deg)
    return {
        "agent_type": agent_type,
        "location": _offset_world(origin, forward_m, lateral_m, z),
        "rotation": [0.0, 0.0, 0.0],
        "forward_m": float(forward_m),
        "lateral_m": float(lateral_m),
        "angle_deg": float(angle_deg),
        "z": float(z),
    }


def _build_scenes() -> List[Dict[str, Any]]:
    observer_world = _cell_world(OBSERVER_CELL)
    scenes: List[Dict[str, Any]] = [
        {
            "name": "baseline",
            "role": "background_reference",
            "scenario_kind": "baseline",
            "target": None,
            "teammates": [],
            "include_target": False,
            "include_teammate": False,
            "teammate_count": 0,
            "distance_m": None,
            "angle_label": None,
            "angle_deg": None,
            "is_calibration_scene": False,
            "expected_target_present_for_audit": False,
        },
        {
            "name": RGB_SIGNATURE_CALIBRATION_SCENE,
            "role": "sphere_rgb_signature_calibration",
            "scenario_kind": "calibration",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, RGB_SIGNATURE_CALIBRATION_DISTANCE_M, 0.0, TARGET_Z),
            "teammates": [],
            "include_target": True,
            "include_teammate": False,
            "teammate_count": 0,
            "distance_m": float(RGB_SIGNATURE_CALIBRATION_DISTANCE_M),
            "angle_label": "center",
            "angle_deg": 0.0,
            "is_calibration_scene": True,
            "expected_target_present_for_audit": True,
        },
    ]
    for distance in TARGET_DISTANCES_M:
        for angle in FAN_TEST_ANGLES:
            label = str(angle["label"])
            angle_deg = float(angle["angle_deg"])
            scenes.append(
                {
                    "name": "target_sphere_{0}_{1:02d}m".format(label, int(distance)),
                    "role": "sphere_target_distance_boundary",
                    "scenario_kind": "target",
                    "target": _object_spec(TARGET_AGENT_TYPE, observer_world, distance, angle_deg, TARGET_Z),
                    "teammates": [],
                    "include_target": True,
                    "include_teammate": False,
                    "teammate_count": 0,
                    "distance_m": float(distance),
                    "angle_label": label,
                    "angle_deg": angle_deg,
                    "is_calibration_scene": False,
                    "expected_target_present_for_audit": True,
                }
            )
    for distance in TEAMMATE_SINGLE_DISTANCES_M:
        for angle in FAN_TEST_ANGLES:
            label = str(angle["label"])
            angle_deg = float(angle["angle_deg"])
            scenes.append(
                {
                    "name": "teammate_only_surfacevessel_{0}_{1:02d}m".format(label, int(distance)),
                    "role": "surfacevessel_teammate_negative",
                    "scenario_kind": "teammate_only",
                    "target": None,
                    "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, distance, angle_deg, TEAMMATE_Z)],
                    "include_target": False,
                    "include_teammate": True,
                    "teammate_count": 1,
                    "distance_m": float(distance),
                    "angle_label": label,
                    "angle_deg": angle_deg,
                    "is_calibration_scene": False,
                    "expected_target_present_for_audit": False,
                }
            )
    for distance in TEAMMATE_EDGE_DISTANCES_M:
        for angle in TEAMMATE_EDGE_ANGLES:
            label = str(angle["label"])
            angle_deg = float(angle["angle_deg"])
            scenes.append(
                {
                    "name": "teammate_only_surfacevessel_{0}_{1:02d}m".format(label, int(distance)),
                    "role": "surfacevessel_edge_teammate_negative",
                    "scenario_kind": "teammate_only",
                    "target": None,
                    "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, distance, angle_deg, TEAMMATE_Z)],
                    "include_target": False,
                    "include_teammate": True,
                    "teammate_count": 1,
                    "distance_m": float(distance),
                    "angle_label": label,
                    "angle_deg": angle_deg,
                    "is_calibration_scene": False,
                    "expected_target_present_for_audit": False,
                }
            )
    multi_specs = [
        {
            "name": "teammate_only_surfacevessel_pair_inner_25m",
            "role": "surfacevessel_multi_teammate_negative",
            "teammates": [
                _object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 25.0, 15.0, TEAMMATE_Z),
                _object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 25.0, -15.0, TEAMMATE_Z),
            ],
            "distance_m": 25.0,
            "angle_label": "left_right_inner_pair",
            "angle_deg": None,
        },
        {
            "name": "teammate_only_surfacevessel_pair_outer_30m",
            "role": "surfacevessel_multi_teammate_negative",
            "teammates": [
                _object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 30.0, 25.0, TEAMMATE_Z),
                _object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 30.0, -25.0, TEAMMATE_Z),
            ],
            "distance_m": 30.0,
            "angle_label": "left_right_outer_pair",
            "angle_deg": None,
        },
    ]
    for spec in multi_specs:
        teammates = list(spec["teammates"])
        scenes.append(
            {
                "name": spec["name"],
                "role": spec["role"],
                "scenario_kind": "teammate_only",
                "target": None,
                "teammates": teammates,
                "include_target": False,
                "include_teammate": True,
                "teammate_count": len(teammates),
                "distance_m": spec["distance_m"],
                "angle_label": spec["angle_label"],
                "angle_deg": spec["angle_deg"],
                "is_calibration_scene": False,
                "expected_target_present_for_audit": False,
            }
        )
    coexist_specs = [
        {
            "name": "coexist_sphere_center_25m_teammate_left_inner_20m",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, 25.0, 0.0, TARGET_Z),
            "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 20.0, 15.0, TEAMMATE_Z)],
            "distance_m": 25.0,
            "angle_label": "target_center_teammate_left_inner",
            "angle_deg": 0.0,
        },
        {
            "name": "coexist_sphere_center_30m_teammate_right_inner_20m",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, 30.0, 0.0, TARGET_Z),
            "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 20.0, -15.0, TEAMMATE_Z)],
            "distance_m": 30.0,
            "angle_label": "target_center_teammate_right_inner",
            "angle_deg": 0.0,
        },
        {
            "name": "coexist_sphere_left_inner_25m_teammate_right_outer_25m",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, 25.0, 15.0, TARGET_Z),
            "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 25.0, -25.0, TEAMMATE_Z)],
            "distance_m": 25.0,
            "angle_label": "target_left_inner_teammate_right_outer",
            "angle_deg": 15.0,
        },
        {
            "name": "coexist_sphere_right_inner_30m_teammate_left_outer_30m",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, 30.0, -15.0, TARGET_Z),
            "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 30.0, 25.0, TEAMMATE_Z)],
            "distance_m": 30.0,
            "angle_label": "target_right_inner_teammate_left_outer",
            "angle_deg": -15.0,
        },
        {
            "name": "coexist_sphere_left_outer_30m_teammate_right_inner_25m",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, 30.0, 25.0, TARGET_Z),
            "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 25.0, -15.0, TEAMMATE_Z)],
            "distance_m": 30.0,
            "angle_label": "target_left_outer_teammate_right_inner",
            "angle_deg": 25.0,
        },
        {
            "name": "coexist_sphere_right_outer_25m_teammate_left_inner_25m",
            "target": _object_spec(TARGET_AGENT_TYPE, observer_world, 25.0, -25.0, TARGET_Z),
            "teammates": [_object_spec(TEAMMATE_NEGATIVE_AGENT_TYPE, observer_world, 25.0, 15.0, TEAMMATE_Z)],
            "distance_m": 25.0,
            "angle_label": "target_right_outer_teammate_left_inner",
            "angle_deg": -25.0,
        },
    ]
    for spec in coexist_specs:
        teammates = list(spec["teammates"])
        scenes.append(
            {
                "name": spec["name"],
                "role": "sphere_target_with_surfacevessel_teammate",
                "scenario_kind": "target_with_teammate",
                "target": spec["target"],
                "teammates": teammates,
                "include_target": True,
                "include_teammate": True,
                "teammate_count": len(teammates),
                "distance_m": spec["distance_m"],
                "angle_label": spec["angle_label"],
                "angle_deg": spec["angle_deg"],
                "is_calibration_scene": False,
                "expected_target_present_for_audit": True,
            }
        )
    return scenes


def _phase_config(mode: str, pre_git_status: Optional[List[str]] = None, recommended_rule: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    observer_world = _cell_world(OBSERVER_CELL)
    scenes = _build_scenes()
    return {
        "phase_name": PHASE_NAME,
        "mode": mode,
        "purpose": "25 m and 30 m distance focus validation for the fixed 5D-0 SphereAgent RGB/RangeFinder rule under target-only, teammate-only, and coexistence scenes",
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_negative_agent_type": TEAMMATE_NEGATIVE_AGENT_TYPE,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "same_model_teammate_and_target": False,
        "found_rule": "sphere_blob_any_hit and any_rangefinder_hit",
        "recommended_candidate_rule": recommended_rule,
        "target_distances_m": TARGET_DISTANCES_M,
        "teammate_single_distances_m": TEAMMATE_SINGLE_DISTANCES_M,
        "teammate_edge_distances_m": TEAMMATE_EDGE_DISTANCES_M,
        "fan_test_angles": FAN_TEST_ANGLES,
        "teammate_edge_angles": TEAMMATE_EDGE_ANGLES,
        "rgb_signature_calibration_distance_m": RGB_SIGNATURE_CALIBRATION_DISTANCE_M,
        "rgb_signature_calibration_scene": RGB_SIGNATURE_CALIBRATION_SCENE,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rangefinder_mode": "yaw_rotated_single_ray_fan",
        "horizontal_fan_sensor_count": len(FAN_YAW_DEGREES),
        "horizontal_fan_yaw_degrees": list(FAN_YAW_DEGREES),
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min_values": OVERLAP_MIN_VALUES,
            "rgb_changed_pixels_min_values": CHANGED_PIXELS_MIN_VALUES,
            "baseline_source": "baseline",
            "signature_calibration_source": RGB_SIGNATURE_CALIBRATION_SCENE,
            "sphere_blob_detector": {
                "diff_threshold": SPHERE_BLOB_DIFF_THRESHOLD,
                "min_rgb": SPHERE_BLOB_MIN_RGB,
                "neutral_tolerance": SPHERE_BLOB_NEUTRAL_TOLERANCE,
                "min_area": SPHERE_BLOB_MIN_AREA,
                "min_aspect": SPHERE_BLOB_MIN_ASPECT,
                "max_aspect": SPHERE_BLOB_MAX_ASPECT,
                "min_fill": SPHERE_BLOB_MIN_FILL,
                "min_cy": SPHERE_BLOB_MIN_CY,
                "min_area_ratio": SPHERE_BLOB_MIN_AREA_RATIO,
                "close_kernel_wh": [SPHERE_BLOB_CLOSE_KERNEL_W, SPHERE_BLOB_CLOSE_KERNEL_H],
            },
        },
        "holo_world": "OpenWater",
        "holo_package": "Ocean",
        "capture_ticks": CAPTURE_TICKS,
        "camera_width": CAMERA_WIDTH,
        "camera_height": CAMERA_HEIGHT,
        "camera_hz": CAMERA_HZ,
        "camera_location": CAMERA_LOCATION,
        "rangefinder_location": RANGEFINDER_LOCATION,
        "rangefinder_max_distance_m": RANGEFINDER_MAX_DISTANCE_M,
        "rgb_camera_name": RGB_CAMERA_NAME,
        "observer_world_location": observer_world,
        "planned_scene_counts": {
            "total": len(scenes),
            "baseline": 1,
            "calibration": 1,
            "target": sum(1 for scene in scenes if scene.get("scenario_kind") == "target"),
            "target_with_teammate": sum(1 for scene in scenes if scene.get("scenario_kind") == "target_with_teammate"),
            "teammate_only": sum(1 for scene in scenes if scene.get("scenario_kind") == "teammate_only"),
        },
        "scenes": scenes,
        "map_npz": MAP_NPZ,
        "pre_git_status": pre_git_status if pre_git_status is not None else [],
    }


def _camera_sensor() -> Dict[str, Any]:
    return {
        "sensor_type": "RGBCamera",
        "sensor_name": RGB_CAMERA_NAME,
        "location": CAMERA_LOCATION,
        "rotation": [0.0, 0.0, 0.0],
        "Hz": CAMERA_HZ,
        "configuration": {"CaptureWidth": CAMERA_WIDTH, "CaptureHeight": CAMERA_HEIGHT},
    }


def _fan_rangefinder_sensors() -> List[Dict[str, Any]]:
    sensors: List[Dict[str, Any]] = []
    for index, yaw_deg in enumerate(FAN_YAW_DEGREES):
        sensors.append(
            {
                "sensor_type": "RangeFinderSensor",
                "sensor_name": "{0}_{1:02d}".format(FAN_RANGEFINDER_PREFIX, index),
                "location": RANGEFINDER_LOCATION,
                "rotation": [0.0, 0.0, float(yaw_deg)],
                "configuration": {
                    "LaserMaxDistance": RANGEFINDER_MAX_DISTANCE_M,
                    "LaserCount": 1,
                    "LaserAngle": 0.0,
                    "LaserDebug": False,
                },
            }
        )
    return sensors


def _control_scheme(agent_type: str) -> int:
    if agent_type in ("SphereAgent", "SphereRobot"):
        return 1
    return 0


def _zero_action(agent_type: str) -> np.ndarray:
    return np.zeros(2, dtype=np.float32)


def _scenario_config(scene: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    agents: List[Dict[str, Any]] = [
        {
            "agent_name": "sv0",
            "agent_type": "SurfaceVessel",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "COM"},
                {"sensor_type": "GPSSensor", "socket": "COM"},
                {"sensor_type": "OrientationSensor", "socket": "COM"},
                _camera_sensor(),
            ]
            + _fan_rangefinder_sensors(),
            "control_scheme": 0,
            "location": list(config["observer_world_location"]),
            "rotation": [0.0, 0.0, 0.0],
        }
    ]
    target = scene.get("target")
    if isinstance(target, dict):
        agent_type = str(target["agent_type"])
        agents.append(
            {
                "agent_name": "target",
                "agent_type": agent_type,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(agent_type),
                "location": list(target["location"]),
                "rotation": list(target["rotation"]),
            }
        )
    for teammate_index, teammate in enumerate(scene.get("teammates", [])):
        if not isinstance(teammate, dict):
            continue
        agent_type = str(teammate["agent_type"])
        agents.append(
            {
                "agent_name": "teammate{0}".format(teammate_index),
                "agent_type": agent_type,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(agent_type),
                "location": list(teammate["location"]),
                "rotation": list(teammate["rotation"]),
            }
        )
    return {
        "name": "phase5d1a_{0}_{1}".format(config.get("mode", "capture"), scene["name"]),
        "world": "OpenWater",
        "package_name": "Ocean",
        "main_agent": "sv0",
        "agents": agents,
    }


def _fan_rangefinder_names() -> List[str]:
    return ["{0}_{1:02d}".format(FAN_RANGEFINDER_PREFIX, index) for index in range(len(FAN_YAW_DEGREES))]


def _aggregate_fan_range(state: Dict[str, Any]) -> List[float]:
    values: List[float] = []
    for name in _fan_rangefinder_names():
        value = get_sensor_vector(state, "sv0", name)
        if value is None:
            values.append(-1.0)
            continue
        arr = np.asarray(value).astype(float).reshape(-1)
        values.append(float(arr[0]) if arr.size else -1.0)
    return values


def _beam_sector(index: int, count: int) -> str:
    if count <= 1:
        return "center"
    third = count / 3.0
    if index < third:
        return "left"
    if index >= 2.0 * third:
        return "right"
    return "center"


def _range_summary(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"present": False, "raw": None, "beam_count": 0, "hit_beam_indices": [], "hit_sectors": [], "min_positive_range_m": None, "any_hit": False}
    arr = np.asarray(value).astype(float).reshape(-1)
    positives = arr > 0.0
    hit_indices = [int(i) for i, hit in enumerate(positives.tolist()) if bool(hit)]
    hit_sectors = sorted({_beam_sector(i, int(arr.size)) for i in hit_indices})
    positive_values = arr[positives]
    return {
        "present": True,
        "raw": arr.tolist(),
        "beam_count": int(arr.size),
        "hit_beam_indices": hit_indices,
        "hit_sectors": hit_sectors,
        "min_positive_range_m": None if positive_values.size == 0 else float(np.min(positive_values)),
        "any_hit": bool(hit_indices),
    }


def _rgb_diff_signature(rgb_value: Any, baseline_value: Any) -> Dict[str, Any]:
    if rgb_value is None or baseline_value is None:
        return {"present": False, "changed_pixels": 0, "change_bbox_xyxy": None, "signature_colors": [], "signature_color_counts": {}}
    rgb = np.asarray(rgb_value)
    baseline = np.asarray(baseline_value)
    if rgb.ndim < 3 or baseline.ndim < 3 or rgb.shape[:2] != baseline.shape[:2]:
        return {"present": False, "changed_pixels": 0, "change_bbox_xyxy": None, "signature_colors": [], "signature_color_counts": {}, "error": "rgb/baseline shape mismatch"}
    rgb3 = rgb[..., :3].astype(np.int16)
    baseline3 = baseline[..., :3].astype(np.int16)
    diff = np.max(np.abs(rgb3 - baseline3), axis=-1)
    height, width = diff.shape[:2]
    roi = np.zeros_like(diff, dtype=bool)
    y0 = int(height * 0.18)
    y1 = int(height * 0.82)
    x0 = int(width * 0.08)
    x1 = int(width * 0.92)
    roi[y0:y1, x0:x1] = True
    mask = (diff >= RGB_DIFF_THRESHOLD) & roi
    changed_pixels = int(np.count_nonzero(mask))
    if changed_pixels == 0:
        return {"present": True, "changed_pixels": 0, "change_bbox_xyxy": None, "signature_colors": [], "signature_color_counts": {}, "roi_xyxy": [x0, y0, x1, y1]}
    ys, xs = np.nonzero(mask)
    pixels = rgb3[mask].astype(np.uint8)
    quant = (pixels // RGB_SIGNATURE_QUANTIZATION) * RGB_SIGNATURE_QUANTIZATION
    unique, counts = np.unique(quant, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1]
    signature_counts: Dict[str, int] = {}
    signature_colors: List[str] = []
    for index in order[:RGB_SIGNATURE_TOP_K]:
        color = unique[index]
        color_key = "{0},{1},{2},255".format(int(color[0]), int(color[1]), int(color[2]))
        signature_counts[color_key] = int(counts[index])
        signature_colors.append(color_key)
    return {
        "present": True,
        "changed_pixels": changed_pixels,
        "change_bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        "signature_colors": signature_colors,
        "signature_color_counts": signature_counts,
        "roi_xyxy": [x0, y0, x1, y1],
    }


def _sphere_blob_signature(rgb_value: Any, baseline_value: Any) -> Dict[str, Any]:
    if rgb_value is None or baseline_value is None:
        return {"present": False, "sphere_blob_present": False, "candidate_blob_count": 0, "best_blob": None}
    rgb = np.asarray(rgb_value)
    baseline = np.asarray(baseline_value)
    if rgb.ndim < 3 or baseline.ndim < 3 or rgb.shape[:2] != baseline.shape[:2]:
        return {"present": False, "sphere_blob_present": False, "candidate_blob_count": 0, "best_blob": None, "error": "rgb/baseline shape mismatch"}
    rgb3 = rgb[..., :3].astype(np.int16)
    baseline3 = baseline[..., :3].astype(np.int16)
    diff = np.max(np.abs(rgb3 - baseline3), axis=-1)
    height, width = diff.shape[:2]
    roi = np.zeros_like(diff, dtype=bool)
    y0 = int(height * 0.18)
    y1 = int(height * 0.82)
    x0 = int(width * 0.08)
    x1 = int(width * 0.92)
    roi[y0:y1, x0:x1] = True
    max_channel = np.max(rgb3, axis=-1)
    min_channel = np.min(rgb3, axis=-1)
    mask = (
        (diff >= float(SPHERE_BLOB_DIFF_THRESHOLD))
        & (max_channel >= int(SPHERE_BLOB_MIN_RGB))
        & ((max_channel - min_channel) <= int(SPHERE_BLOB_NEUTRAL_TOLERANCE))
        & roi
    )
    try:
        import cv2

        mask_u8 = mask.astype(np.uint8)
        if int(SPHERE_BLOB_CLOSE_KERNEL_W) > 1 or int(SPHERE_BLOB_CLOSE_KERNEL_H) > 1:
            close_kernel = np.ones((int(SPHERE_BLOB_CLOSE_KERNEL_H), int(SPHERE_BLOB_CLOSE_KERNEL_W)), dtype=np.uint8)
            mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, close_kernel)
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, 8)
    except Exception as exc:
        return {
            "present": True,
            "sphere_blob_present": False,
            "candidate_blob_count": 0,
            "best_blob": None,
            "white_neutral_changed_pixels": int(np.count_nonzero(mask)),
            "error": "connected components failed: {0}".format(exc),
        }
    candidates: List[Dict[str, Any]] = []
    all_blobs: List[Dict[str, Any]] = []
    for index in range(1, int(count)):
        x, y, blob_w, blob_h, area = [int(v) for v in stats[index]]
        if area <= 0 or blob_w <= 0 or blob_h <= 0:
            continue
        aspect = float(blob_w) / float(blob_h)
        fill = float(area) / float(blob_w * blob_h)
        blob = {
            "x": x,
            "y": y,
            "w": blob_w,
            "h": blob_h,
            "area": area,
            "aspect": aspect,
            "fill": fill,
            "cx": float(centroids[index][0]),
            "cy": float(centroids[index][1]),
        }
        all_blobs.append(blob)
        if (
            area >= int(SPHERE_BLOB_MIN_AREA)
            and aspect >= float(SPHERE_BLOB_MIN_ASPECT)
            and aspect <= float(SPHERE_BLOB_MAX_ASPECT)
            and fill >= float(SPHERE_BLOB_MIN_FILL)
            and float(centroids[index][1]) >= float(SPHERE_BLOB_MIN_CY)
        ):
            candidates.append(blob)
    candidates = sorted(candidates, key=lambda item: int(item.get("area", 0)), reverse=True)
    all_blobs = sorted(all_blobs, key=lambda item: int(item.get("area", 0)), reverse=True)
    white_pixels = int(np.count_nonzero(mask_u8))
    best_blob = candidates[0] if candidates else None
    best_area_ratio = None
    if best_blob is not None and white_pixels > 0:
        best_area_ratio = float(best_blob.get("area", 0)) / float(white_pixels)
    return {
        "present": True,
        "sphere_blob_present": bool(best_blob is not None and best_area_ratio is not None and best_area_ratio >= float(SPHERE_BLOB_MIN_AREA_RATIO)),
        "candidate_blob_count": len(candidates),
        "best_blob": best_blob,
        "candidate_blobs": candidates[:5],
        "largest_blob": all_blobs[0] if all_blobs else None,
        "white_neutral_changed_pixels": white_pixels,
        "white_neutral_changed_pixels_pre_morphology": int(np.count_nonzero(mask)),
        "best_blob_area_ratio": best_area_ratio,
        "roi_xyxy": [x0, y0, x1, y1],
        "params": {
            "diff_threshold": SPHERE_BLOB_DIFF_THRESHOLD,
            "min_rgb": SPHERE_BLOB_MIN_RGB,
            "neutral_tolerance": SPHERE_BLOB_NEUTRAL_TOLERANCE,
            "min_area": SPHERE_BLOB_MIN_AREA,
            "min_aspect": SPHERE_BLOB_MIN_ASPECT,
            "max_aspect": SPHERE_BLOB_MAX_ASPECT,
            "min_fill": SPHERE_BLOB_MIN_FILL,
            "min_cy": SPHERE_BLOB_MIN_CY,
            "min_area_ratio": SPHERE_BLOB_MIN_AREA_RATIO,
            "close_kernel_wh": [SPHERE_BLOB_CLOSE_KERNEL_W, SPHERE_BLOB_CLOSE_KERNEL_H],
        },
    }


def _array_stats(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"present": False, "shape": None, "dtype": None, "size": 0}
    arr = np.asarray(value)
    return {"present": True, "shape": list(arr.shape), "dtype": str(arr.dtype), "size": int(arr.size)}


def _preview_array(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim >= 3:
        img = arr[..., :3]
        if np.issubdtype(img.dtype, np.floating) and float(np.nanmax(img)) <= 1.0:
            img = img * 255.0
        return np.clip(img, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        finite = np.nan_to_num(arr.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
        maxv = float(np.max(finite)) if finite.size else 0.0
        if maxv > 0:
            finite = finite / maxv * 255.0
        return np.clip(finite, 0, 255).astype(np.uint8)
    return np.zeros((16, 16), dtype=np.uint8)


def _save_preview(path: str, value: Any) -> bool:
    try:
        from PIL import Image

        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(_preview_array(value)).save(path)
        return True
    except Exception as exc:
        print("[WARN] preview save failed for {0}: {1}".format(path, exc))
        return False


def _save_scene_artifacts(scene_name: str, mode: str, rgb: Any) -> Dict[str, Any]:
    artifacts = {"rgb_preview_path": None, "rgb_raw_path": None, "rgb_preview_saved": False, "rgb_raw_saved": False}
    if rgb is not None:
        prefix = "{0}_{1}".format(mode, scene_name)
        raw_path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_rgb_raw.npy".format(prefix)))
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        np.save(raw_path, np.asarray(rgb))
        artifacts["rgb_raw_path"] = raw_path
        artifacts["rgb_raw_saved"] = True
        preview_path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_rgb.png".format(prefix)))
        artifacts["rgb_preview_saved"] = _save_preview(preview_path, rgb)
        artifacts["rgb_preview_path"] = preview_path if artifacts["rgb_preview_saved"] else None
    return artifacts


def _run_scene(scene: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    import holoocean

    scene_name = str(scene["name"])
    tick_rows: List[Dict[str, Any]] = []
    first_rgb = None
    first_range = None
    launch_ok = False
    error = ""
    started = time.perf_counter()
    try:
        with holoocean.make(scenario_cfg=_scenario_config(scene, config)) as env:
            launch_ok = True
            for tick in range(1, CAPTURE_TICKS + 1):
                env.act("sv0", _zero_action("SurfaceVessel"))
                if bool(scene.get("include_target", False)):
                    env.act("target", _zero_action(TARGET_AGENT_TYPE))
                for teammate_index, teammate in enumerate(scene.get("teammates", [])):
                    if isinstance(teammate, dict):
                        env.act("teammate{0}".format(teammate_index), _zero_action(str(teammate.get("agent_type", TEAMMATE_NEGATIVE_AGENT_TYPE))))
                state = env.tick()
                rgb = get_sensor_vector(state, "sv0", RGB_CAMERA_NAME)
                fan_range = _aggregate_fan_range(state)
                if first_rgb is None and rgb is not None:
                    first_rgb = np.asarray(rgb).copy()
                if first_range is None and fan_range is not None:
                    first_range = np.asarray(fan_range).copy()
                rsum = _range_summary(fan_range)
                tick_rows.append(
                    {
                        "scene": scene_name,
                        "tick": int(tick),
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
    artifacts = _save_scene_artifacts(scene_name, str(config.get("mode", "capture")), first_rgb)
    return {
        "scene": scene_name,
        "role": scene.get("role"),
        "distance_m": scene.get("distance_m"),
        "angle_label": scene.get("angle_label"),
        "angle_deg": scene.get("angle_deg"),
        "scenario_kind": scene.get("scenario_kind"),
        "is_calibration_scene": bool(scene.get("is_calibration_scene", False)),
        "include_target": bool(scene.get("include_target", False)),
        "include_teammate": bool(scene.get("include_teammate", False)),
        "teammate_count": int(scene.get("teammate_count", 0)),
        "expected_target_present_for_audit": bool(scene.get("expected_target_present_for_audit", False)),
        "launch_ok": launch_ok,
        "error": error,
        "wall_time_s": float(time.perf_counter() - started),
        "rgb_stats": _array_stats(first_rgb),
        "rangefinder_summary": _range_summary(first_range),
        "first_rgb_raw": first_rgb,
        "artifacts": artifacts,
        "tick_rows": tick_rows,
    }


def _strip_scene_raw(result: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(result)
    clean.pop("first_rgb_raw", None)
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


def _outcome(target_present: bool, found: bool) -> str:
    if target_present and found:
        return "true_positive"
    if target_present and not found:
        return "false_negative"
    if not target_present and found:
        return "false_positive"
    return "true_negative"


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _build_evidence(scene_results: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    baseline_rgb = scene_results.get("baseline", {}).get("first_rgb_raw")
    calibration_rgb = scene_results.get(RGB_SIGNATURE_CALIBRATION_SCENE, {}).get("first_rgb_raw")
    target_sig = _rgb_diff_signature(calibration_rgb, baseline_rgb)
    target_signature_colors = sorted(set(str(v) for v in target_sig.get("signature_colors", [])))
    target_signature_set = set(target_signature_colors)

    rows: List[Dict[str, Any]] = []
    for scene in config["scenes"]:
        name = str(scene["name"])
        result = scene_results.get(name, {})
        rgb_diff = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)
        sphere_blob = _sphere_blob_signature(result.get("first_rgb_raw"), baseline_rgb)
        scene_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        overlap = sorted(target_signature_set & scene_colors)
        range_summary = result.get("rangefinder_summary", {})
        rows.append(
            {
                "scene": name,
                "scenario_kind": scene.get("scenario_kind"),
                "role": scene.get("role"),
                "is_calibration_scene": bool(scene.get("is_calibration_scene", False)),
                "expected_target_present_for_audit": bool(scene.get("expected_target_present_for_audit", False)),
                "include_target": bool(scene.get("include_target", False)),
                "include_teammate": bool(scene.get("include_teammate", False)),
                "teammate_count": int(scene.get("teammate_count", 0)),
                "distance_m": scene.get("distance_m"),
                "angle_label": scene.get("angle_label"),
                "angle_deg": scene.get("angle_deg"),
                "rgb_signature_colors": sorted(scene_colors),
                "rgb_signature_overlap": overlap,
                "rgb_signature_overlap_count": len(overlap),
                "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0)),
                "rgb_change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
                "sphere_blob_present": bool(sphere_blob.get("sphere_blob_present", False)),
                "sphere_blob_candidate_count": int(sphere_blob.get("candidate_blob_count", 0)),
                "sphere_blob_best": sphere_blob.get("best_blob"),
                "sphere_blob_largest": sphere_blob.get("largest_blob"),
                "sphere_blob_white_neutral_changed_pixels": int(sphere_blob.get("white_neutral_changed_pixels", 0)),
                "sphere_blob_best_area_ratio": sphere_blob.get("best_blob_area_ratio"),
                "rangefinder_raw_beams": range_summary.get("raw"),
                "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
                "rangefinder_hit_sectors": range_summary.get("hit_sectors"),
                "any_rangefinder_hit": bool(range_summary.get("any_hit", False)),
                "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                "rgb_raw_path": result.get("artifacts", {}).get("rgb_raw_path"),
                "rgb_preview_path": result.get("artifacts", {}).get("rgb_preview_path"),
                "rgb_raw_saved": result.get("artifacts", {}).get("rgb_raw_saved"),
                "rgb_preview_saved": result.get("artifacts", {}).get("rgb_preview_saved"),
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
            }
        )
    meta = {
        "phase_name": PHASE_NAME,
        "mode": config.get("mode"),
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_negative_agent_type": TEAMMATE_NEGATIVE_AGENT_TYPE,
        "target_signature_calibration_scene": RGB_SIGNATURE_CALIBRATION_SCENE,
        "target_signature_colors": target_signature_colors,
        "target_signature_color_count": len(target_signature_colors),
        "calibration_changed_pixels": int(target_sig.get("changed_pixels", 0)),
        "calibration_change_bbox_xyxy": target_sig.get("change_bbox_xyxy"),
        "diff_threshold": RGB_DIFF_THRESHOLD,
        "quantization": RGB_SIGNATURE_QUANTIZATION,
        "top_k": RGB_SIGNATURE_TOP_K,
        "sphere_blob_detector": {
            "diff_threshold": SPHERE_BLOB_DIFF_THRESHOLD,
            "min_rgb": SPHERE_BLOB_MIN_RGB,
            "neutral_tolerance": SPHERE_BLOB_NEUTRAL_TOLERANCE,
            "min_area": SPHERE_BLOB_MIN_AREA,
            "min_aspect": SPHERE_BLOB_MIN_ASPECT,
            "max_aspect": SPHERE_BLOB_MAX_ASPECT,
            "min_fill": SPHERE_BLOB_MIN_FILL,
            "min_cy": SPHERE_BLOB_MIN_CY,
            "min_area_ratio": SPHERE_BLOB_MIN_AREA_RATIO,
            "close_kernel_wh": [SPHERE_BLOB_CLOSE_KERNEL_W, SPHERE_BLOB_CLOSE_KERNEL_H],
        },
        "raw_rgb_source": "captured HoloOcean RGBCamera visuals/*_rgb_raw.npy",
        "scene_results_first_rgb_raw_used_for_evidence": True,
        "truth_used_for_detection": False,
    }
    return rows, meta


def _rule_configs() -> Iterable[Dict[str, Any]]:
    yield {
        "rule_id": "range_only_failure_reference",
        "rule_name": "range_only_failure_reference",
        "rule_family": "failure_reference",
        "target_overlap_min": 0,
        "rgb_changed_pixels_min": 0,
        "uses_rgb_signature": False,
        "uses_sphere_blob": False,
        "uses_rangefinder": True,
    }
    yield {
        "rule_id": "sphere_blob_any_hit",
        "rule_name": "sphere_blob_any_hit",
        "rule_family": "sphere_blob",
        "target_overlap_min": None,
        "rgb_changed_pixels_min": None,
        "uses_rgb_signature": False,
        "uses_sphere_blob": True,
        "uses_rangefinder": True,
    }
    for overlap_min in OVERLAP_MIN_VALUES:
        for pixels_min in CHANGED_PIXELS_MIN_VALUES:
            yield {
                "rule_id": "sphere_rgb_any_hit_overlap{0}_px{1}".format(overlap_min, pixels_min),
                "rule_name": "sphere_rgb_any_hit",
                "rule_family": "sphere_rgb_any_hit",
                "target_overlap_min": int(overlap_min),
                "rgb_changed_pixels_min": int(pixels_min),
                "uses_rgb_signature": True,
                "uses_sphere_blob": False,
                "uses_rangefinder": True,
            }


def _rule_found(rule: Dict[str, Any], evidence: Dict[str, Any]) -> bool:
    any_hit = bool(evidence.get("any_rangefinder_hit", False))
    if str(rule.get("rule_name")) == "range_only_failure_reference":
        return any_hit
    if str(rule.get("rule_name")) == "sphere_blob_any_hit":
        return bool(evidence.get("sphere_blob_present", False) and any_hit)
    overlap_ok = int(evidence.get("rgb_signature_overlap_count", 0)) >= int(rule.get("target_overlap_min", 1))
    pixels_ok = int(evidence.get("rgb_changed_pixels", 0)) >= int(rule.get("rgb_changed_pixels_min", 0))
    return bool(overlap_ok and pixels_ok and any_hit)


def _summarize_rule(rule: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_rows = [row for row in rows if row.get("scenario_kind") in ("target", "target_with_teammate")]
    target_only_rows = [row for row in rows if row.get("scenario_kind") == "target"]
    target_with_teammate_rows = [row for row in rows if row.get("scenario_kind") == "target_with_teammate"]
    teammate_rows = [row for row in rows if row.get("scenario_kind") == "teammate_only"]
    baseline_rows = [row for row in rows if row.get("scenario_kind") == "baseline"]
    calibration_rows = [row for row in rows if row.get("scenario_kind") == "calibration"]

    def _hits(distance: float) -> int:
        return sum(1 for row in target_only_rows if float(row.get("distance_m")) == float(distance) and bool(row.get("candidate_found")))

    def _total(distance: float) -> int:
        return sum(1 for row in target_only_rows if float(row.get("distance_m")) == float(distance))

    fan_reliable = []
    for distance in TARGET_DISTANCES_M:
        rows_at_distance = [row for row in target_only_rows if float(row.get("distance_m")) == float(distance)]
        if rows_at_distance and all(bool(row.get("candidate_found")) for row in rows_at_distance):
            fan_reliable.append(float(distance))

    return {
        **rule,
        "outcome_counts_all_scenes": _count_by(rows, "candidate_outcome"),
        "target_true_positive_count": sum(1 for row in target_rows if row.get("candidate_found")),
        "target_false_negative_count": sum(1 for row in target_rows if not row.get("candidate_found")),
        "target_only_true_positive_count": sum(1 for row in target_only_rows if row.get("candidate_found")),
        "target_only_false_negative_count": sum(1 for row in target_only_rows if not row.get("candidate_found")),
        "target_with_teammate_true_positive_count": sum(1 for row in target_with_teammate_rows if row.get("candidate_found")),
        "target_with_teammate_false_negative_count": sum(1 for row in target_with_teammate_rows if not row.get("candidate_found")),
        "teammate_false_positive_count": sum(1 for row in teammate_rows if row.get("candidate_found")),
        "teammate_true_negative_count": sum(1 for row in teammate_rows if not row.get("candidate_found")),
        "baseline_false_positive_count": sum(1 for row in baseline_rows if row.get("candidate_found")),
        "calibration_true_positive": bool(calibration_rows and calibration_rows[0].get("candidate_found")),
        "target_true_positive_scenes": [str(row["scene"]) for row in target_rows if row.get("candidate_found")],
        "target_false_negative_scenes": [str(row["scene"]) for row in target_rows if not row.get("candidate_found")],
        "target_with_teammate_false_negative_scenes": [str(row["scene"]) for row in target_with_teammate_rows if not row.get("candidate_found")],
        "teammate_false_positive_scenes": [str(row["scene"]) for row in teammate_rows if row.get("candidate_found")],
        "baseline_false_positive_scenes": [str(row["scene"]) for row in baseline_rows if row.get("candidate_found")],
        "target_20m_true_positive_count": _hits(20.0),
        "target_20m_total": _total(20.0),
        "target_35m_true_positive_count": _hits(35.0),
        "target_35m_total": _total(35.0),
        "fan_reliable_distances_m": fan_reliable,
        "max_fan_reliable_distance_m": max(fan_reliable) if fan_reliable else None,
    }


def _evaluate_candidate_rules(evidence_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    matrix_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    for rule in _rule_configs():
        per_rule: List[Dict[str, Any]] = []
        for evidence in evidence_rows:
            expected_target = bool(evidence.get("expected_target_present_for_audit", False))
            found = _rule_found(rule, evidence)
            row = {
                **rule,
                "scene": evidence.get("scene"),
                "scenario_kind": evidence.get("scenario_kind"),
                "expected_target_present_for_audit": expected_target,
                "distance_m": evidence.get("distance_m"),
                "angle_label": evidence.get("angle_label"),
                "angle_deg": evidence.get("angle_deg"),
                "rgb_signature_overlap_count": evidence.get("rgb_signature_overlap_count"),
                "rgb_changed_pixels": evidence.get("rgb_changed_pixels"),
                "sphere_blob_present": evidence.get("sphere_blob_present"),
                "sphere_blob_candidate_count": evidence.get("sphere_blob_candidate_count"),
                "sphere_blob_best": evidence.get("sphere_blob_best"),
                "sphere_blob_white_neutral_changed_pixels": evidence.get("sphere_blob_white_neutral_changed_pixels"),
                "sphere_rgb_target_signature": bool(
                    int(evidence.get("rgb_signature_overlap_count", 0)) >= int(rule.get("target_overlap_min", 1))
                    and int(evidence.get("rgb_changed_pixels", 0)) >= int(rule.get("rgb_changed_pixels_min", 0))
                )
                if bool(rule.get("uses_rgb_signature"))
                else None,
                "any_rangefinder_hit": evidence.get("any_rangefinder_hit"),
                "rangefinder_hit_beam_indices": evidence.get("rangefinder_hit_beam_indices"),
                "candidate_found": found,
                "candidate_outcome": _outcome(expected_target, found),
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
            }
            per_rule.append(row)
            matrix_rows.append(row)
        summary_rows.append(_summarize_rule(rule, per_rule))
    return matrix_rows, summary_rows


def _recommend_rule(summary_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    eligible = [
        row
        for row in summary_rows
        if row.get("rule_name") in ("sphere_blob_any_hit", "sphere_rgb_any_hit")
        and row.get("calibration_true_positive") is True
        and row.get("baseline_false_positive_count") == 0
        and row.get("teammate_false_positive_count") == 0
        and row.get("target_20m_true_positive_count") == row.get("target_20m_total") == 5
    ]
    if not eligible:
        eligible = [row for row in summary_rows if row.get("rule_name") in ("sphere_blob_any_hit", "sphere_rgb_any_hit")]
    family_priority = {"sphere_blob": 0, "sphere_rgb_any_hit": 1}
    ranked = sorted(
        eligible,
        key=lambda row: (
            -(float(row.get("max_fan_reliable_distance_m") or 0.0)),
            int(row.get("teammate_false_positive_count", 999)),
            int(row.get("baseline_false_positive_count", 999)),
            -int(row.get("target_true_positive_count", 0)),
            family_priority.get(str(row.get("rule_family")), 99),
            int(row.get("target_overlap_min") if row.get("target_overlap_min") is not None else 999),
            int(row.get("rgb_changed_pixels_min") if row.get("rgb_changed_pixels_min") is not None else 999),
        ),
    )
    chosen = dict(ranked[0])
    chosen["recommendation_reason"] = (
        "Selected SphereAgent visual-evidence + fan-RangeFinder rule with zero SurfaceVessel-only teammate false positives, "
        "baseline false positives zero, and the largest audited fan reliable distance; ties prefer the compact sphere-blob rule."
    )
    chosen["recommended_for_holoocean_rerun"] = True
    return chosen


def _fixed_recommended_rule(summary_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    fixed = dict(FIXED_RECOMMENDED_RULE)
    matched = next((row for row in summary_rows if row.get("rule_name") == fixed["rule_name"]), {})
    fixed.update(matched)
    fixed.update(FIXED_RECOMMENDED_RULE)
    fixed["recommendation_reason"] = (
        "Phase 5D-1A distance focus validates the fixed Phase 5D-0 SphereAgent sphere-blob + fan-RangeFinder rule "
        "at 25 m and 30 m under target-only, teammate-only, and coexistence scenes; it does not reselect the detector."
    )
    fixed["recommended_for_holoocean_rerun"] = True
    return fixed


def _apply_recommended_rule(evidence_rows: List[Dict[str, Any]], recommended: Dict[str, Any], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for evidence in evidence_rows:
        expected_target = bool(evidence.get("expected_target_present_for_audit", False))
        found = _rule_found(recommended, evidence)
        uses_blob = str(recommended.get("rule_name")) == "sphere_blob_any_hit"
        row = {
            "scene": evidence.get("scene"),
            "scenario_kind": evidence.get("scenario_kind"),
            "role": evidence.get("role"),
            "is_calibration_scene": evidence.get("is_calibration_scene"),
            "expected_target_present_for_audit": expected_target,
            "include_target": evidence.get("include_target"),
            "include_teammate": evidence.get("include_teammate"),
            "teammate_count": evidence.get("teammate_count"),
            "distance_m": evidence.get("distance_m"),
            "angle_label": evidence.get("angle_label"),
            "angle_deg": evidence.get("angle_deg"),
            "rgb_signature_overlap": evidence.get("rgb_signature_overlap"),
            "rgb_signature_overlap_count": evidence.get("rgb_signature_overlap_count"),
            "rgb_changed_pixels": evidence.get("rgb_changed_pixels"),
            "rgb_change_bbox_xyxy": evidence.get("rgb_change_bbox_xyxy"),
            "sphere_rgb_target_signature": bool(
                int(evidence.get("rgb_signature_overlap_count", 0)) >= int(recommended.get("target_overlap_min", 1))
                and int(evidence.get("rgb_changed_pixels", 0)) >= int(recommended.get("rgb_changed_pixels_min", 0))
            ) if not uses_blob else None,
            "sphere_blob_target_signature": bool(evidence.get("sphere_blob_present", False)) if uses_blob else None,
            "sphere_blob_present": evidence.get("sphere_blob_present"),
            "sphere_blob_candidate_count": evidence.get("sphere_blob_candidate_count"),
            "sphere_blob_best": evidence.get("sphere_blob_best"),
            "sphere_blob_white_neutral_changed_pixels": evidence.get("sphere_blob_white_neutral_changed_pixels"),
            "target_overlap_min": None if recommended.get("target_overlap_min") is None else int(recommended.get("target_overlap_min", 1)),
            "rgb_changed_pixels_min": None if recommended.get("rgb_changed_pixels_min") is None else int(recommended.get("rgb_changed_pixels_min", 0)),
            "rangefinder_raw_beams": evidence.get("rangefinder_raw_beams"),
            "rangefinder_hit_beam_indices": evidence.get("rangefinder_hit_beam_indices"),
            "rangefinder_hit_sectors": evidence.get("rangefinder_hit_sectors"),
            "any_rangefinder_hit": evidence.get("any_rangefinder_hit"),
            "rangefinder_min_positive_range_m": evidence.get("rangefinder_min_positive_range_m"),
            "found": found,
            "found_rule": config.get("found_rule"),
            "outcome": _outcome(expected_target, found),
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "teammate_truth_used_for_detection": False,
            "rgb_artifact": evidence.get("rgb_preview_path"),
        }
        rows.append(row)
    return rows, _summary_metrics(rows)


def _summary_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_rows = [row for row in rows if row.get("scenario_kind") in ("target", "target_with_teammate")]
    target_only_rows = [row for row in rows if row.get("scenario_kind") == "target"]
    target_with_teammate_rows = [row for row in rows if row.get("scenario_kind") == "target_with_teammate"]
    teammate_rows = [row for row in rows if row.get("scenario_kind") == "teammate_only"]
    baseline_rows = [row for row in rows if row.get("scenario_kind") == "baseline"]
    calibration_rows = [row for row in rows if row.get("scenario_kind") == "calibration"]
    fan_reliable: List[float] = []
    max_effective_by_angle: Dict[str, Optional[float]] = {}
    failed_by_angle: Dict[str, List[float]] = {}
    for distance in TARGET_DISTANCES_M:
        rows_at_distance = [row for row in target_only_rows if float(row.get("distance_m")) == float(distance)]
        if rows_at_distance and all(bool(row.get("found")) for row in rows_at_distance):
            fan_reliable.append(float(distance))
    for angle in FAN_TEST_ANGLES:
        label = str(angle["label"])
        rows_at_angle = [row for row in target_only_rows if row.get("angle_label") == label]
        hits = [float(row["distance_m"]) for row in rows_at_angle if row.get("found")]
        misses = [float(row["distance_m"]) for row in rows_at_angle if not row.get("found")]
        max_effective_by_angle[label] = max(hits) if hits else None
        failed_by_angle[label] = sorted(misses)
    return {
        "outcome_counts": _count_by(rows, "outcome"),
        "target_outcome_counts": _count_by(target_rows, "outcome"),
        "target_only_outcome_counts": _count_by(target_only_rows, "outcome"),
        "target_with_teammate_outcome_counts": _count_by(target_with_teammate_rows, "outcome"),
        "teammate_outcome_counts": _count_by(teammate_rows, "outcome"),
        "baseline_outcome_counts": _count_by(baseline_rows, "outcome"),
        "calibration_outcome_counts": _count_by(calibration_rows, "outcome"),
        "target_false_negative_scenes": [str(row["scene"]) for row in target_rows if not row.get("found")],
        "target_only_false_negative_scenes": [str(row["scene"]) for row in target_only_rows if not row.get("found")],
        "target_with_teammate_false_negative_scenes": [str(row["scene"]) for row in target_with_teammate_rows if not row.get("found")],
        "teammate_false_positive_scenes": [str(row["scene"]) for row in teammate_rows if row.get("found")],
        "baseline_false_positive_scenes": [str(row["scene"]) for row in baseline_rows if row.get("found")],
        "calibration_true_positive": bool(calibration_rows and calibration_rows[0].get("found")),
        "fan_reliable_distances_m": fan_reliable,
        "max_fan_reliable_distance_m": max(fan_reliable) if fan_reliable else None,
        "max_effective_distance_by_angle_m": max_effective_by_angle,
        "failed_distances_by_angle_m": failed_by_angle,
    }


def _build_calibration_summary(
    config: Dict[str, Any],
    evidence_meta: Dict[str, Any],
    candidate_summaries: List[Dict[str, Any]],
    recommended: Dict[str, Any],
    final_rows: List[Dict[str, Any]],
    final_metrics: Dict[str, Any],
    started: float,
) -> Dict[str, Any]:
    range_only = next((row for row in candidate_summaries if row.get("rule_name") == "range_only_failure_reference"), {})
    return {
        "phase_name": PHASE_NAME,
        "calibration_completed": True,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_negative_agent_type": TEAMMATE_NEGATIVE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "found_rule": config.get("found_rule"),
        "recommended_candidate_rule": recommended,
        "candidate_rule_count": len(candidate_summaries),
        "range_only_failure_reference_summary": range_only,
        "target_signature_colors": evidence_meta.get("target_signature_colors"),
        "target_signature_present": bool(evidence_meta.get("target_signature_colors")),
        "target_signature_color_count": evidence_meta.get("target_signature_color_count"),
        "calibration_changed_pixels": evidence_meta.get("calibration_changed_pixels"),
        "target_distances_m": TARGET_DISTANCES_M,
        "teammate_single_distances_m": TEAMMATE_SINGLE_DISTANCES_M,
        "teammate_edge_distances_m": TEAMMATE_EDGE_DISTANCES_M,
        "fan_test_angles": FAN_TEST_ANGLES,
        "teammate_edge_angles": TEAMMATE_EDGE_ANGLES,
        "scene_count": len(final_rows),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rgb_signature_detector": config.get("rgb_signature_detector"),
        "rule_matrix": final_rows,
        **final_metrics,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "wall_time_s": float(time.perf_counter() - started),
    }


def _build_validation_summary(
    config: Dict[str, Any],
    evidence_meta: Dict[str, Any],
    matrix: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    scene_results: Dict[str, Dict[str, Any]],
    started: float,
) -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "validation_completed": True,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_negative_agent_type": TEAMMATE_NEGATIVE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "recommended_candidate_rule": config.get("recommended_candidate_rule"),
        "found_rule": config.get("found_rule"),
        "target_signature_colors": evidence_meta.get("target_signature_colors"),
        "target_signature_present": bool(evidence_meta.get("target_signature_colors")),
        "target_signature_color_count": evidence_meta.get("target_signature_color_count"),
        "calibration_changed_pixels": evidence_meta.get("calibration_changed_pixels"),
        "target_distances_m": TARGET_DISTANCES_M,
        "teammate_single_distances_m": TEAMMATE_SINGLE_DISTANCES_M,
        "teammate_edge_distances_m": TEAMMATE_EDGE_DISTANCES_M,
        "fan_test_angles": FAN_TEST_ANGLES,
        "teammate_edge_angles": TEAMMATE_EDGE_ANGLES,
        "scene_count": len(matrix),
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rgb_signature_detector": config.get("rgb_signature_detector"),
        "rule_matrix": matrix,
        "all_scene_launch_ok": all(bool(r.get("launch_ok", False)) for r in scene_results.values()),
        "all_scenes_rgb_output": all(bool(r.get("rgb_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(r.get("rangefinder_summary", {}).get("present", False)) for r in scene_results.values()),
        **metrics,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "wall_time_s": float(time.perf_counter() - started),
    }


def _build_summary_md(summary: Dict[str, Any], title: str) -> str:
    recommended = summary.get("recommended_candidate_rule", {})
    lines = [
        "# {0}".format(title),
        "",
        "- Target Agent Type: `{0}`".format(summary.get("target_agent_type")),
        "- Teammate Negative Agent Type: `{0}`".format(summary.get("teammate_negative_agent_type")),
        "- Same Model Teammate And Target: `{0}`".format(summary.get("same_model_teammate_and_target")),
        "- Recommended Rule ID: `{0}`".format(recommended.get("rule_id")),
        "- Found Rule: `{0}`".format(summary.get("found_rule")),
        "- RGB target_overlap_min: `{0}`".format(recommended.get("target_overlap_min")),
        "- RGB changed_pixels_min: `{0}`".format(recommended.get("rgb_changed_pixels_min")),
        "- Target Signature Color Count: `{0}`".format(summary.get("target_signature_color_count")),
        "- Target Outcome Counts: `{0}`".format(summary.get("target_outcome_counts")),
        "- Target-only Outcome Counts: `{0}`".format(summary.get("target_only_outcome_counts")),
        "- Target-with-teammate Outcome Counts: `{0}`".format(summary.get("target_with_teammate_outcome_counts")),
        "- Teammate Outcome Counts: `{0}`".format(summary.get("teammate_outcome_counts")),
        "- Fan Reliable Distances: `{0}`".format(summary.get("fan_reliable_distances_m")),
        "- Max Fan Reliable Distance: `{0}`".format(summary.get("max_fan_reliable_distance_m")),
        "- Teammate False Positive Scenes: `{0}`".format(summary.get("teammate_false_positive_scenes")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "",
        "| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary.get("rule_matrix", []):
        if row.get("distance_m") is None:
            continue
        lines.append(
            "| `{0}` | `{1}` | `{2}` | `{3}` | `{4}` | `{5}` | `{6}` | `{7}` | `{8}` |".format(
                row.get("scene"),
                row.get("scenario_kind"),
                row.get("angle_label"),
                row.get("distance_m"),
                row.get("rgb_signature_overlap_count"),
                row.get("rgb_changed_pixels"),
                row.get("any_rangefinder_hit"),
                row.get("found"),
                row.get("outcome"),
            )
        )
    return "\n".join(lines) + "\n"


def run_calibrate() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    config = _phase_config("calibration", pre_git_status=pre_git_status)
    _save_json(CAL_CONFIG_JSON, config)
    scene_results, tick_trace = _capture_scenes(config)
    evidence_rows, evidence_meta = _build_evidence(scene_results, config)
    candidate_matrix, candidate_summaries = _evaluate_candidate_rules(evidence_rows)
    recommended = _fixed_recommended_rule(candidate_summaries)
    config["recommended_candidate_rule"] = recommended
    _save_json(CAL_CONFIG_JSON, config)
    final_rows, final_metrics = _apply_recommended_rule(evidence_rows, recommended, config)
    summary = _build_calibration_summary(config, evidence_meta, candidate_summaries, recommended, final_rows, final_metrics, started)

    _save_json(CAL_SCENE_RESULTS_JSON, {name: _strip_scene_raw(result) for name, result in scene_results.items()})
    _save_json(CAL_TICK_TRACE_JSON, tick_trace)
    _save_csv(CAL_TICK_TRACE_CSV, tick_trace)
    _save_json(RECOMPUTED_EVIDENCE_JSON, {"meta": evidence_meta, "rows": evidence_rows})
    _save_json(CANDIDATE_RULE_MATRIX_JSON, candidate_matrix)
    _save_csv(CANDIDATE_RULE_MATRIX_CSV, candidate_matrix)
    _save_json(CANDIDATE_RULE_SUMMARY_JSON, {"phase_name": PHASE_NAME, "candidate_rule_summaries": candidate_summaries})
    _save_json(RECOMMENDED_RULE_JSON, recommended)
    _save_json(CAL_SUMMARY_JSON, summary)
    os.makedirs(os.path.dirname(CAL_SUMMARY_MD), exist_ok=True)
    with open(CAL_SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary, "Phase 5D-1A 25m/30m Calibration Summary"))
    post_git_status = _run_git_status()
    _save_json(CAL_GIT_STATUS_JSON, {"phase_name": PHASE_NAME, "pre_git_status": pre_git_status, "post_git_status": post_git_status, "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_git_status, post_git_status)})
    print(
        "Phase 5D-1A calibration finished: recommended={0}, reliable={1}, teammate_fp={2}".format(
            recommended.get("rule_id"),
            summary.get("max_fan_reliable_distance_m"),
            summary.get("teammate_false_positive_scenes"),
        )
    )
    return summary


def run_validate() -> Dict[str, Any]:
    started = time.perf_counter()
    recommended = _load_json(RECOMMENDED_RULE_JSON)
    pre_git_status = _run_git_status()
    config = _phase_config("validation", pre_git_status=pre_git_status, recommended_rule=recommended)
    target_overlap_min = recommended.get("target_overlap_min")
    rgb_changed_pixels_min = recommended.get("rgb_changed_pixels_min")
    config["rgb_signature_detector"]["target_overlap_min"] = None if target_overlap_min is None else int(target_overlap_min)
    config["rgb_signature_detector"]["rgb_changed_pixels_min"] = None if rgb_changed_pixels_min is None else int(rgb_changed_pixels_min)
    _save_json(VAL_CONFIG_JSON, config)
    scene_results, tick_trace = _capture_scenes(config)
    evidence_rows, evidence_meta = _build_evidence(scene_results, config)
    matrix, metrics = _apply_recommended_rule(evidence_rows, recommended, config)
    summary = _build_validation_summary(config, evidence_meta, matrix, metrics, scene_results, started)

    _save_json(VAL_SCENE_RESULTS_JSON, {name: _strip_scene_raw(result) for name, result in scene_results.items()})
    _save_json(VAL_DETECTION_EVENTS_JSON, matrix)
    _save_json(VAL_RULE_MATRIX_JSON, matrix)
    _save_csv(VAL_RULE_MATRIX_CSV, matrix)
    _save_json(VAL_TICK_TRACE_JSON, tick_trace)
    _save_csv(VAL_TICK_TRACE_CSV, tick_trace)
    _save_json(VAL_SUMMARY_JSON, summary)
    os.makedirs(os.path.dirname(VAL_SUMMARY_MD), exist_ok=True)
    with open(VAL_SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary, "Phase 5D-1A 25m/30m HoloOcean Validation Summary"))
    post_git_status = _run_git_status()
    _save_json(VAL_GIT_STATUS_JSON, {"phase_name": PHASE_NAME, "pre_git_status": pre_git_status, "post_git_status": post_git_status, "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_git_status, post_git_status)})
    print(
        "Phase 5D-1A validation finished: target={0}, teammate={1}, reliable={2}".format(
            summary.get("target_outcome_counts"),
            summary.get("teammate_outcome_counts"),
            summary.get("max_fan_reliable_distance_m"),
        )
    )
    return summary


def run_report() -> None:
    if os.path.exists(CAL_SUMMARY_JSON):
        summary = _load_json(CAL_SUMMARY_JSON)
        with open(CAL_SUMMARY_MD, "w", encoding="utf-8") as f:
            f.write(_build_summary_md(summary, "Phase 5D-1A 25m/30m Calibration Summary"))
    if os.path.exists(VAL_SUMMARY_JSON):
        summary = _load_json(VAL_SUMMARY_JSON)
        with open(VAL_SUMMARY_MD, "w", encoding="utf-8") as f:
            f.write(_build_summary_md(summary, "Phase 5D-1A 25m/30m HoloOcean Validation Summary"))
    print("Reports refreshed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["calibrate", "validate", "report"], required=True)
    args = parser.parse_args()
    if args.mode == "calibrate":
        run_calibrate()
    elif args.mode == "validate":
        run_validate()
    else:
        run_report()


if __name__ == "__main__":
    main()
