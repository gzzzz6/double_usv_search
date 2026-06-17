"""Phase 5C-4I-2 HoloOcean validation probe.

This reruns the Phase 5C-4H scene matrix in HoloOcean with the offline
recommended 5C-4I rule:

    found_candidate = stronger_rgb_target_signature and any_rangefinder_hit

For the current recommendation, stronger_rgb_target_signature is:

    rgb_signature_overlap_count >= recommended.target_overlap_min
    and rgb_changed_pixels >= recommended.rgb_changed_pixels_min

Direction matching and distractor rejection are recorded as diagnostics unless
the recommended rule explicitly enables them.
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
PHASE_NAME = "phase5c4i_direction_matched_distractor_rejection_calibration"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

RECOMMENDED_RULE_JSON = os.path.join(PHASE_DIR, "manifests", "recommended_candidate_rule.json")

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_validation_config.json")
SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_scene_results.json")
DETECTION_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_detection_events.json")
RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_rule_matrix.json")
RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5c4i_rule_matrix.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_summary.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5c4i_tick_trace.csv")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_validation_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5c4i_validation_summary.md")

CAPTURE_TICKS = 12
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "FrontRGBCamera"
FAN_RANGEFINDER_PREFIX = "FanRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
FAN_YAW_DEGREES = [30.0, 22.5, 15.0, 7.5, 0.0, -7.5, -15.0, -22.5, -30.0]
CAMERA_HORIZONTAL_FOV_DEG = 90.0
RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES = [7.5, 10.0, 12.5, 15.0]
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24

CONTROLLED_SV0_CELL = [23, 20]
CONTROLLED_SV1_CELL = [35, 2]
TARGET_AGENT_TYPE = "SurfaceVessel"
DISTRACTOR_AGENT_TYPE = "SphereAgent"
DISTANCES_M = [20.0, 35.0, 50.0]
DISTRACTOR_DISTANCES_M = [20.0, 50.0]
FAN_TEST_ANGLES = [
    {"label": "left_outer", "angle_deg": 25.0},
    {"label": "left_inner", "angle_deg": 15.0},
    {"label": "center", "angle_deg": 0.0},
    {"label": "right_inner", "angle_deg": -15.0},
    {"label": "right_outer", "angle_deg": -25.0},
]
RGB_SIGNATURE_CALIBRATION_DISTANCE_M = 10.0
RGB_SIGNATURE_CALIBRATION_SCENE = "calibration_target_front_center_10m"


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
                out[key] = json.dumps(_json_safe(value)) if isinstance(value, (dict, list, tuple)) else _json_safe(value)
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


def _object_spec(agent_type: str, origin: List[float], forward_m: float, angle_deg: float, z: float, yaw_deg: float = 0.0) -> Dict[str, Any]:
    lateral_m = _angle_lateral(forward_m, angle_deg)
    return {
        "agent_type": agent_type,
        "location": _offset_world(origin, forward_m, lateral_m, z),
        "rotation": [0.0, 0.0, float(yaw_deg)],
        "forward_m": float(forward_m),
        "lateral_m": float(lateral_m),
        "angle_deg": float(angle_deg),
        "yaw_deg": float(yaw_deg),
    }


def _load_recommended_rule() -> Dict[str, Any]:
    rule = _load_json(RECOMMENDED_RULE_JSON)
    if not isinstance(rule, dict):
        raise TypeError("recommended rule must be a dict")
    return rule


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    recommended_rule = _load_recommended_rule()
    sv0_world = _cell_world(CONTROLLED_SV0_CELL)
    sv1_world = _cell_world(CONTROLLED_SV1_CELL)
    scenes: List[Dict[str, Any]] = [
        {
            "name": "baseline",
            "role": "background_reference",
            "include_target": False,
            "include_distractor": False,
            "target": None,
            "distractor": None,
            "distance_m": None,
            "angle_label": None,
            "angle_deg": None,
            "scenario_kind": "baseline",
            "expected_target_present_for_audit": False,
        }
    ]
    scenes.append(
        {
            "name": RGB_SIGNATURE_CALIBRATION_SCENE,
            "role": "rgb_signature_calibration",
            "include_target": True,
            "include_distractor": False,
            "target": _object_spec(TARGET_AGENT_TYPE, sv0_world, RGB_SIGNATURE_CALIBRATION_DISTANCE_M, 0.0, 0.0),
            "distractor": None,
            "distance_m": float(RGB_SIGNATURE_CALIBRATION_DISTANCE_M),
            "angle_label": "center",
            "angle_deg": 0.0,
            "scenario_kind": "calibration",
            "is_calibration_scene": True,
            "expected_target_present_for_audit": True,
        }
    )
    for distance in DISTANCES_M:
        for angle in FAN_TEST_ANGLES:
            label = str(angle["label"])
            angle_deg = float(angle["angle_deg"])
            scenes.append(
                {
                    "name": "target_{0}_{1:02d}m".format(label, int(distance)),
                    "role": "fan_area_target_boundary",
                    "include_target": True,
                    "include_distractor": False,
                    "target": _object_spec(TARGET_AGENT_TYPE, sv0_world, distance, angle_deg, 0.0),
                    "distractor": None,
                    "distance_m": float(distance),
                    "angle_label": label,
                    "angle_deg": angle_deg,
                    "scenario_kind": "target",
                    "is_calibration_scene": False,
                    "expected_target_present_for_audit": True,
                }
            )
    for distance in DISTRACTOR_DISTANCES_M:
        for angle in FAN_TEST_ANGLES:
            label = str(angle["label"])
            angle_deg = float(angle["angle_deg"])
            scenes.append(
                {
                    "name": "distractor_only_{0}_{1:02d}m".format(label, int(distance)),
                    "role": "fan_area_distractor_negative",
                    "include_target": False,
                    "include_distractor": True,
                    "target": None,
                    "distractor": _object_spec(DISTRACTOR_AGENT_TYPE, sv0_world, distance, angle_deg, 0.5),
                    "distance_m": float(distance),
                    "angle_label": label,
                    "angle_deg": angle_deg,
                    "scenario_kind": "distractor_only",
                    "is_calibration_scene": False,
                    "expected_target_present_for_audit": False,
                }
            )
    return {
        "phase_name": PHASE_NAME,
        "source_phase_name": "phase5c4h_fan_area_distance_boundary",
        "purpose": "HoloOcean rerun validation for Phase 5C-4I recommended rule",
        "recommended_candidate_rule": recommended_rule,
        "found_rule": "stronger_rgb_target_signature and any_rangefinder_hit",
        "direction_matching_used_for_detection": bool(recommended_rule.get("uses_recalibrated_direction_match", False)),
        "old_direction_matching_used_for_detection": False,
        "old_direction_matching_recorded_as_failure_reference_only": True,
        "distractor_rejection_enabled": bool(recommended_rule.get("uses_distractor_rejection", False)),
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rangefinder_mode": "yaw_rotated_single_ray_fan",
        "horizontal_fan_sensor_count": len(FAN_YAW_DEGREES),
        "horizontal_fan_yaw_degrees": FAN_YAW_DEGREES,
        "camera_horizontal_fov_deg": CAMERA_HORIZONTAL_FOV_DEG,
        "recalibrated_direction_tolerance_deg_values": RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES,
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min": int(recommended_rule.get("target_overlap_min", 1)),
            "rgb_changed_pixels_min": int(recommended_rule.get("rgb_changed_pixels_min", 0)),
            "baseline_source": "baseline",
            "signature_calibration_source": RGB_SIGNATURE_CALIBRATION_SCENE,
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
        "controlled_world_locations": {"sv0": sv0_world, "sv1": sv1_world},
        "planned_scene_counts": {
            "total": len(scenes),
            "baseline": 1,
            "calibration": 1,
            "target": len(DISTANCES_M) * len(FAN_TEST_ANGLES),
            "distractor_only": len(DISTRACTOR_DISTANCES_M) * len(FAN_TEST_ANGLES),
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


def _zero_action() -> np.ndarray:
    return np.zeros(2, dtype=np.float32)


def _scenario_config(scene: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    locations = config["controlled_world_locations"]
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
            "location": list(locations["sv0"]),
            "rotation": [0.0, 0.0, 0.0],
        },
        {
            "agent_name": "sv1",
            "agent_type": "SurfaceVessel",
            "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
            "control_scheme": 0,
            "location": list(locations["sv1"]),
            "rotation": [0.0, 0.0, 0.0],
        },
    ]
    target = scene.get("target")
    if isinstance(target, dict):
        agents.append(
            {
                "agent_name": "target",
                "agent_type": str(target["agent_type"]),
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": 0,
                "location": list(target["location"]),
                "rotation": list(target["rotation"]),
            }
        )
    distractor = scene.get("distractor")
    if isinstance(distractor, dict):
        agents.append(
            {
                "agent_name": "distractor",
                "agent_type": str(distractor["agent_type"]),
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": 0,
                "location": list(distractor["location"]),
                "rotation": list(distractor["rotation"]),
            }
        )
    return {
        "name": "phase5c4i_{0}".format(scene["name"]),
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


def _sector_from_x(x_center: Optional[float], width: int) -> str:
    if x_center is None:
        return "none"
    left_cut = float(width) / 3.0
    right_cut = 2.0 * float(width) / 3.0
    if x_center < left_cut:
        return "left"
    if x_center > right_cut:
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
        "any_hit": bool(len(hit_indices) > 0),
    }


def _rgb_diff_signature(rgb_value: Any, baseline_value: Any) -> Dict[str, Any]:
    if rgb_value is None or baseline_value is None:
        return {"present": False, "changed_pixels": 0, "change_bbox_xyxy": None, "signature_colors": [], "signature_color_counts": {}, "mask": None, "quantized_pixels": None, "xs": None, "ys": None}
    rgb = np.asarray(rgb_value)
    baseline = np.asarray(baseline_value)
    if rgb.ndim < 3 or baseline.ndim < 3 or rgb.shape[:2] != baseline.shape[:2]:
        return {"present": False, "changed_pixels": 0, "change_bbox_xyxy": None, "signature_colors": [], "signature_color_counts": {}, "error": "rgb/baseline shape mismatch", "mask": None, "quantized_pixels": None, "xs": None, "ys": None}
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
        return {"present": True, "changed_pixels": 0, "change_bbox_xyxy": None, "signature_colors": [], "signature_color_counts": {}, "roi_xyxy": [x0, y0, x1, y1], "mask": mask, "quantized_pixels": None, "xs": np.array([], dtype=int), "ys": np.array([], dtype=int)}
    ys, xs = np.nonzero(mask)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
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
        "change_bbox_xyxy": bbox,
        "signature_colors": signature_colors,
        "signature_color_counts": signature_counts,
        "roi_xyxy": [x0, y0, x1, y1],
        "mask": mask,
        "quantized_pixels": quant,
        "xs": xs,
        "ys": ys,
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
        arr = _preview_array(value)
        Image.fromarray(arr).save(path)
        return True
    except Exception as exc:
        print("[WARN] preview save failed for {0}: {1}".format(path, exc))
        return False


def _save_scene_artifacts(scene_name: str, rgb: Any) -> Dict[str, Any]:
    artifacts = {"rgb_preview_path": None, "rgb_raw_path": None, "rgb_preview_saved": False, "rgb_raw_saved": False}
    if rgb is not None:
        raw_path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_rgb_raw.npy".format(scene_name)))
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        np.save(raw_path, np.asarray(rgb))
        artifacts["rgb_raw_path"] = raw_path
        artifacts["rgb_raw_saved"] = True
        preview_path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_rgb.png".format(scene_name)))
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
                env.act("sv0", _zero_action())
                env.act("sv1", _zero_action())
                if bool(scene.get("include_target", False)):
                    env.act("target", _zero_action())
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
    artifacts = _save_scene_artifacts(scene_name, first_rgb)
    return {
        "scene": scene_name,
        "role": scene.get("role"),
        "distance_m": scene.get("distance_m"),
        "angle_label": scene.get("angle_label"),
        "angle_deg": scene.get("angle_deg"),
        "scenario_kind": scene.get("scenario_kind"),
        "is_calibration_scene": bool(scene.get("is_calibration_scene", False)),
        "include_target": bool(scene.get("include_target", False)),
        "include_distractor": bool(scene.get("include_distractor", False)),
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


def _outcome(target_present: bool, found: bool) -> str:
    if target_present and found:
        return "true_positive"
    if target_present and not found:
        return "false_negative"
    if not target_present and found:
        return "false_positive"
    return "true_negative"


def _color_keys(quantized_pixels: Optional[np.ndarray]) -> np.ndarray:
    if quantized_pixels is None:
        return np.array([], dtype=object)
    return np.asarray(
        [
            "{0},{1},{2},255".format(int(color[0]), int(color[1]), int(color[2]))
            for color in np.asarray(quantized_pixels)
        ],
        dtype=object,
    )


def _bbox_from_points(xs: np.ndarray, ys: np.ndarray) -> Optional[List[int]]:
    if xs.size == 0 or ys.size == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _angle_from_x(x_center: Optional[float], width: int) -> Optional[float]:
    if x_center is None or width <= 0:
        return None
    return (float(width) / 2.0 - float(x_center)) / (float(width) / 2.0) * (CAMERA_HORIZONTAL_FOV_DEG / 2.0)


def _recalibrated_direction_match(
    rgb_angle_deg: Optional[float],
    hit_beam_indices: Iterable[Any],
    tolerance_deg: float,
) -> Tuple[bool, Optional[float], Optional[float]]:
    if rgb_angle_deg is None:
        return False, None, None
    best_delta: Optional[float] = None
    best_yaw: Optional[float] = None
    for raw_index in hit_beam_indices or []:
        try:
            index = int(raw_index)
        except Exception:
            continue
        if index < 0 or index >= len(FAN_YAW_DEGREES):
            continue
        yaw = float(FAN_YAW_DEGREES[index])
        delta = abs(float(rgb_angle_deg) - yaw)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_yaw = yaw
    return bool(best_delta is not None and best_delta <= float(tolerance_deg)), best_delta, best_yaw


def _make_events(scene_results: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    recommended = dict(config.get("recommended_candidate_rule", {}))
    target_overlap_min = int(recommended.get("target_overlap_min", 1))
    changed_pixels_min = int(recommended.get("rgb_changed_pixels_min", 0))
    direction_tolerance = recommended.get("direction_tolerance_deg")
    distractor_overlap_min = recommended.get("distractor_overlap_min")
    uses_direction = bool(recommended.get("uses_recalibrated_direction_match", False))
    uses_distractor = bool(recommended.get("uses_distractor_rejection", False))

    baseline_rgb = scene_results.get("baseline", {}).get("first_rgb_raw")
    calibration_scene = str(config.get("rgb_signature_calibration_scene", RGB_SIGNATURE_CALIBRATION_SCENE))
    target_rgb = scene_results.get(calibration_scene, {}).get("first_rgb_raw")
    target_sig = _rgb_diff_signature(target_rgb, baseline_rgb)
    target_signature_colors = sorted(list(set(str(v) for v in target_sig.get("signature_colors", []))))
    target_signature_set = set(target_signature_colors)

    raw_rows: List[Dict[str, Any]] = []
    scene_color_sets: Dict[str, set] = {}
    for scene in config["scenes"]:
        name = str(scene["name"])
        result = scene_results.get(name, {})
        rgb_diff = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)
        scene_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        scene_color_sets[name] = scene_colors
        overlap = sorted(list(target_signature_set & scene_colors))
        bbox = rgb_diff.get("change_bbox_xyxy")
        x_center = None
        if isinstance(bbox, list) and len(bbox) == 4:
            x_center = (float(bbox[0]) + float(bbox[2])) / 2.0
        stats = result.get("rgb_stats", {})
        shape = stats.get("shape") if isinstance(stats, dict) else None
        width = CAMERA_WIDTH
        if isinstance(shape, list) and len(shape) >= 2:
            width = int(shape[1])
        old_rgb_signature_sector = _sector_from_x(x_center, width)
        range_summary = result.get("rangefinder_summary", {})
        any_hit = bool(range_summary.get("any_hit", False))
        hit_sectors = list(range_summary.get("hit_sectors", []) or [])
        old_matched_hit = bool(old_rgb_signature_sector != "none" and old_rgb_signature_sector in set(hit_sectors))

        color_keys = _color_keys(rgb_diff.get("quantized_pixels"))
        xs = rgb_diff.get("xs")
        ys = rgb_diff.get("ys")
        target_pixel_mask = np.array([str(key) in target_signature_set for key in color_keys], dtype=bool)
        target_overlap_xs = np.asarray(xs)[target_pixel_mask] if xs is not None and target_pixel_mask.size else np.array([], dtype=int)
        target_overlap_ys = np.asarray(ys)[target_pixel_mask] if ys is not None and target_pixel_mask.size else np.array([], dtype=int)
        target_overlap_bbox = _bbox_from_points(target_overlap_xs, target_overlap_ys)
        target_overlap_x_center = None
        if target_overlap_bbox is not None:
            target_overlap_x_center = (float(target_overlap_bbox[0]) + float(target_overlap_bbox[2])) / 2.0
        rgb_target_angle_deg = _angle_from_x(target_overlap_x_center, width)
        direction_matches: Dict[str, Any] = {}
        for tolerance in RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES:
            matched, delta, yaw = _recalibrated_direction_match(
                rgb_target_angle_deg,
                range_summary.get("hit_beam_indices", []),
                tolerance,
            )
            direction_matches[str(tolerance)] = {"matched": matched, "best_delta_deg": delta, "best_hit_beam_yaw_deg": yaw}
        raw_rows.append(
            {
                "scene": name,
                "scene_spec": scene,
                "result": result,
                "rgb_diff": rgb_diff,
                "rgb_signature_overlap": overlap,
                "rgb_signature_overlap_count": len(overlap),
                "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0)),
                "rgb_bbox": bbox,
                "rgb_signature_sector": old_rgb_signature_sector,
                "rgb_target_overlap_bbox_xyxy": target_overlap_bbox,
                "rgb_target_angle_deg": rgb_target_angle_deg,
                "range_summary": range_summary,
                "any_rangefinder_hit": any_hit,
                "rangefinder_hit_sectors": hit_sectors,
                "old_matched_rangefinder_beam_hit": old_matched_hit,
                "recalibrated_direction_matches": direction_matches,
            }
        )

    distractor_frequency: Dict[str, int] = {}
    for row in raw_rows:
        scene = row["scene"]
        scene_spec = row["scene_spec"]
        if scene_spec.get("scenario_kind") == "distractor_only":
            for color in scene_color_sets[scene]:
                distractor_frequency[color] = distractor_frequency.get(color, 0) + 1
    distractor_signature = sorted(color for color, count in distractor_frequency.items() if int(count) >= 2)
    distractor_signature_set = set(distractor_signature)

    events: List[Dict[str, Any]] = []
    matrix: List[Dict[str, Any]] = []
    for row in raw_rows:
        scene = row["scene"]
        scene_spec = row["scene_spec"]
        result = row["result"]
        expected_target = bool(scene_spec.get("expected_target_present_for_audit", False))
        stronger_rgb = bool(row["rgb_signature_overlap_count"] >= target_overlap_min and row["rgb_changed_pixels"] >= changed_pixels_min)
        selected_direction_match = True
        selected_direction_data = None
        if uses_direction:
            selected_direction_data = row["recalibrated_direction_matches"].get(str(direction_tolerance), {})
            selected_direction_match = bool(selected_direction_data.get("matched", False))
        distractor_overlap = sorted(distractor_signature_set & scene_color_sets[scene])
        distractor_like = False
        if uses_distractor:
            distractor_like = len(distractor_overlap) >= int(distractor_overlap_min or 1)
        found = bool(stronger_rgb and bool(row["any_rangefinder_hit"]) and selected_direction_match and not distractor_like)
        outcome = _outcome(expected_target, found)
        event = {
            "scene": scene,
            "distance_m": scene_spec.get("distance_m"),
            "angle_label": scene_spec.get("angle_label"),
            "angle_deg": scene_spec.get("angle_deg"),
            "scenario_kind": scene_spec.get("scenario_kind"),
            "is_calibration_scene": bool(scene_spec.get("is_calibration_scene", False)),
            "expected_target_present_for_audit": expected_target,
            "rgb_signature_overlap": row["rgb_signature_overlap"],
            "rgb_signature_overlap_count": row["rgb_signature_overlap_count"],
            "rgb_changed_pixels": row["rgb_changed_pixels"],
            "rgb_has_target_signature_5c4h_baseline": bool(row["rgb_signature_overlap_count"] >= 1),
            "stronger_rgb_target_signature": stronger_rgb,
            "target_overlap_min": target_overlap_min,
            "rgb_changed_pixels_min": changed_pixels_min,
            "rgb_bbox": row["rgb_bbox"],
            "rgb_signature_bbox_xyxy": row["rgb_bbox"],
            "rgb_signature_sector_legacy": row["rgb_signature_sector"],
            "rgb_target_overlap_bbox_xyxy": row["rgb_target_overlap_bbox_xyxy"],
            "rgb_target_angle_deg": row["rgb_target_angle_deg"],
            "rangefinder_raw_beams": row["range_summary"].get("raw"),
            "rangefinder_hit_beam_indices": row["range_summary"].get("hit_beam_indices"),
            "rangefinder_hit_sectors": row["rangefinder_hit_sectors"],
            "any_rangefinder_hit": row["any_rangefinder_hit"],
            "rangefinder_min_positive_range_m": row["range_summary"].get("min_positive_range_m"),
            "old_matched_rangefinder_beam_hit": row["old_matched_rangefinder_beam_hit"],
            "old_direction_matching_used_for_detection": False,
            "recalibrated_direction_matches": row["recalibrated_direction_matches"],
            "recalibrated_direction_matching_used_for_detection": uses_direction,
            "selected_recalibrated_direction_tolerance_deg": direction_tolerance,
            "selected_recalibrated_direction_match": selected_direction_match if uses_direction else None,
            "selected_recalibrated_direction_data": selected_direction_data,
            "distractor_signature_overlap": distractor_overlap,
            "distractor_signature_overlap_count": len(distractor_overlap),
            "distractor_like": distractor_like,
            "distractor_rejection_enabled": uses_distractor,
            "found": found,
            "found_rule": config.get("found_rule"),
            "outcome": outcome,
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
        }
        events.append(event)
        matrix.append(dict(event))

    target_rows = [row for row in matrix if row.get("scenario_kind") == "target"]
    distractor_rows = [row for row in matrix if row.get("scenario_kind") == "distractor_only"]
    effective_distances = [float(row["distance_m"]) for row in target_rows if row["found"]]
    failed_distances = [float(row["distance_m"]) for row in target_rows if not row["found"]]
    max_effective_by_angle: Dict[str, Optional[float]] = {}
    failed_by_angle: Dict[str, List[float]] = {}
    for angle in FAN_TEST_ANGLES:
        label = str(angle["label"])
        rows = [row for row in target_rows if row.get("angle_label") == label]
        hits = [float(row["distance_m"]) for row in rows if row.get("found")]
        misses = [float(row["distance_m"]) for row in rows if not row.get("found")]
        max_effective_by_angle[label] = max(hits) if hits else None
        failed_by_angle[label] = sorted(misses)
    fan_reliable_distances = []
    for distance in DISTANCES_M:
        rows = [row for row in target_rows if float(row.get("distance_m")) == float(distance)]
        if rows and all(bool(row.get("found")) for row in rows):
            fan_reliable_distances.append(float(distance))
    distractor_false_positive_scenes = [str(row["scene"]) for row in distractor_rows if row.get("found")]
    old_direction_inner_failure_reference = [
        str(row["scene"])
        for row in target_rows
        if row.get("found")
        and str(row.get("angle_label")) in ("left_inner", "right_inner")
        and not bool(row.get("old_matched_rangefinder_beam_hit"))
    ]
    conclusion = {
        "target_signature_colors": target_signature_colors,
        "target_signature_present": bool(target_signature_colors),
        "distractor_signature_colors": distractor_signature,
        "distractor_signature_present": bool(distractor_signature),
        "tested_distances_m": DISTANCES_M,
        "fan_test_angles": FAN_TEST_ANGLES,
        "effective_distances_m": effective_distances,
        "failed_distances_m": failed_distances,
        "max_tested_effective_distance_m": max(effective_distances) if effective_distances else None,
        "first_tested_failure_distance_m": min(failed_distances) if failed_distances else None,
        "max_effective_distance_by_angle_m": max_effective_by_angle,
        "failed_distances_by_angle_m": failed_by_angle,
        "fan_reliable_distances_m": fan_reliable_distances,
        "max_fan_reliable_distance_m": max(fan_reliable_distances) if fan_reliable_distances else None,
        "distractor_false_positive_scenes": distractor_false_positive_scenes,
        "old_direction_inner_failure_reference_scenes": old_direction_inner_failure_reference,
        "old_direction_inner_failure_reference_count": len(old_direction_inner_failure_reference),
        "outcome_counts": _count_by(matrix, "outcome"),
        "target_outcome_counts": _count_by(target_rows, "outcome"),
        "distractor_outcome_counts": _count_by(distractor_rows, "outcome"),
        "all_scene_launch_ok": all(bool(r.get("launch_ok", False)) for r in scene_results.values()),
        "all_scenes_rgb_output": all(bool(r.get("rgb_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(r.get("rangefinder_summary", {}).get("present", False)) for r in scene_results.values()),
    }
    return events, matrix, conclusion


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _build_summary(config: Dict[str, Any], events: List[Dict[str, Any]], matrix: List[Dict[str, Any]], conclusion: Dict[str, Any], started: float) -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "validation_completed": True,
        "terminated_reason": "phase5c4i_validation_complete",
        "source_phase_name": config.get("source_phase_name"),
        "recommended_candidate_rule": config.get("recommended_candidate_rule"),
        "tested_distances_m": DISTANCES_M,
        "distractor_tested_distances_m": DISTRACTOR_DISTANCES_M,
        "fan_test_angles": config.get("fan_test_angles", FAN_TEST_ANGLES),
        "scene_count": len(matrix),
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rangefinder_mode": config.get("rangefinder_mode"),
        "horizontal_fan_sensor_count": config.get("horizontal_fan_sensor_count"),
        "horizontal_fan_yaw_degrees": config.get("horizontal_fan_yaw_degrees"),
        "found_rule": config.get("found_rule"),
        "direction_matching_used_for_detection": bool(config.get("direction_matching_used_for_detection", False)),
        "old_direction_matching_used_for_detection": False,
        "old_direction_matching_recorded_as_failure_reference_only": True,
        "distractor_rejection_enabled": bool(config.get("distractor_rejection_enabled", False)),
        "rgb_signature_detector": config.get("rgb_signature_detector"),
        "target_signature_present": conclusion.get("target_signature_present"),
        "distractor_signature_present": conclusion.get("distractor_signature_present"),
        "effective_distances_m": conclusion.get("effective_distances_m"),
        "failed_distances_m": conclusion.get("failed_distances_m"),
        "max_tested_effective_distance_m": conclusion.get("max_tested_effective_distance_m"),
        "first_tested_failure_distance_m": conclusion.get("first_tested_failure_distance_m"),
        "max_effective_distance_by_angle_m": conclusion.get("max_effective_distance_by_angle_m"),
        "failed_distances_by_angle_m": conclusion.get("failed_distances_by_angle_m"),
        "fan_reliable_distances_m": conclusion.get("fan_reliable_distances_m"),
        "max_fan_reliable_distance_m": conclusion.get("max_fan_reliable_distance_m"),
        "distractor_false_positive_scenes": conclusion.get("distractor_false_positive_scenes"),
        "old_direction_inner_failure_reference_scenes": conclusion.get("old_direction_inner_failure_reference_scenes"),
        "old_direction_inner_failure_reference_count": conclusion.get("old_direction_inner_failure_reference_count"),
        "target_outcome_counts": conclusion.get("target_outcome_counts"),
        "distractor_outcome_counts": conclusion.get("distractor_outcome_counts"),
        "outcome_counts": conclusion.get("outcome_counts"),
        "all_scene_launch_ok": conclusion.get("all_scene_launch_ok"),
        "all_scenes_rgb_output": conclusion.get("all_scenes_rgb_output"),
        "all_scenes_rangefinder_output": conclusion.get("all_scenes_rangefinder_output"),
        "rule_matrix": matrix,
        "validation_conclusion": "recommended rule retained fan reliability to {0} m with distractor false positives {1}".format(
            conclusion.get("max_fan_reliable_distance_m"),
            conclusion.get("distractor_false_positive_scenes"),
        ),
        "runtime_python_executable": sys.executable,
        "runtime_python_version": sys.version,
        "wall_time_s": float(time.perf_counter() - started),
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    recommended = summary.get("recommended_candidate_rule", {})
    lines = [
        "# Phase 5C-4I HoloOcean Validation Summary",
        "",
        "- Recommended Rule ID: `{0}`".format(recommended.get("rule_id")),
        "- Found Rule: `{0}`".format(summary.get("found_rule")),
        "- RGB target_overlap_min: `{0}`".format(summary.get("rgb_signature_detector", {}).get("target_overlap_min")),
        "- RGB changed_pixels_min: `{0}`".format(summary.get("rgb_signature_detector", {}).get("rgb_changed_pixels_min")),
        "- Direction Matching Used For Detection: `{0}`".format(summary.get("direction_matching_used_for_detection")),
        "- Distractor Rejection Enabled: `{0}`".format(summary.get("distractor_rejection_enabled")),
        "- Target Outcome Counts: `{0}`".format(summary.get("target_outcome_counts")),
        "- Distractor Outcome Counts: `{0}`".format(summary.get("distractor_outcome_counts")),
        "- Fan Reliable Distances: `{0}`".format(summary.get("fan_reliable_distances_m")),
        "- Max Fan Reliable Distance: `{0}`".format(summary.get("max_fan_reliable_distance_m")),
        "- Distractor False Positive Scenes: `{0}`".format(summary.get("distractor_false_positive_scenes")),
        "- Old Direction Inner Failure Reference Count: `{0}`".format(summary.get("old_direction_inner_failure_reference_count")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "",
        "| Scene | Kind | Angle | Distance | Overlap | Strong RGB | Range Hit | Found | Outcome |",
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
                row.get("stronger_rgb_target_signature"),
                row.get("any_rangefinder_hit"),
                row.get("found"),
                row.get("outcome"),
            )
        )
    return "\n".join(lines) + "\n"


def run_capture() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    config = _phase_config(pre_git_status=pre_git_status)
    _save_json(CONFIG_JSON, config)
    scene_results: Dict[str, Dict[str, Any]] = {}
    tick_trace: List[Dict[str, Any]] = []
    for scene in config["scenes"]:
        result = _run_scene(scene, config)
        scene_results[str(scene["name"])] = result
        tick_trace.extend(result.get("tick_rows", []))
    events, matrix, conclusion = _make_events(scene_results, config)
    summary = _build_summary(config, events, matrix, conclusion, started)
    _save_json(SCENE_RESULTS_JSON, {name: _strip_scene_raw(result) for name, result in scene_results.items()})
    _save_json(DETECTION_EVENTS_JSON, events)
    _save_json(RULE_MATRIX_JSON, matrix)
    _save_csv(RULE_MATRIX_CSV, matrix)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(SUMMARY_JSON, summary)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    post_git_status = _run_git_status()
    _save_json(GIT_STATUS_JSON, {"phase_name": PHASE_NAME, "pre_git_status": pre_git_status, "post_git_status": post_git_status, "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_git_status, post_git_status)})
    print(
        "Phase 5C-4I validation capture finished: target={0}, distractor={1}, fan_reliable={2}".format(
            summary["target_outcome_counts"],
            summary["distractor_outcome_counts"],
            summary["fan_reliable_distances_m"],
        )
    )
    return summary


def run_report() -> Dict[str, Any]:
    summary = _load_json(SUMMARY_JSON)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary saved to: {0}".format(SUMMARY_MD))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["capture", "report"], required=True)
    args = parser.parse_args()
    if args.mode == "capture":
        run_capture()
    elif args.mode == "report":
        run_report()


if __name__ == "__main__":
    main()
