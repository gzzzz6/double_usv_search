"""Phase 5C-4E RGB + multi-ray RangeFinder fan boundary probe.

This independent phase tests whether a fan-shaped multi-ray RangeFinder can
reduce the left/right-offset misses found in Phase 5C-4D.  It preserves the
RGB signature method from 5C-4C/5C-4D and evaluates two range rules:

    found_any_hit = rgb_has_target_signature and any_rangefinder_hit
    found_aligned = rgb_has_target_signature and matched_rangefinder_beam_hit

Truth labels are used only for audit outcome classification, not for detection.
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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world  # noqa: E402
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4e_rgb_multiray_rangefinder_fan_boundary"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_tick_trace.csv"))
BOUNDARY_MATRIX_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_boundary_matrix.json"))
BOUNDARY_MATRIX_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_boundary_matrix.csv"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_summary.md"))
OVERVIEW_PNG = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_overview.png"))

CAPTURE_TICKS = 12
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "FrontRGBCamera"
RANGEFINDER_NAME = "FanRangeFinderAggregate"
NATIVE_MULTIRAY_RANGEFINDER_NAME = "NativeMultiRayRangeFinder"
FAN_RANGEFINDER_PREFIX = "FanRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
RANGEFINDER_LASER_COUNT = 9
RANGEFINDER_LASER_ANGLE = 60.0
FAN_YAW_DEGREES = [30.0, 22.5, 15.0, 7.5, 0.0, -7.5, -15.0, -22.5, -30.0]
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

# Intentionally copied from Phase 5C-4C/5C-4D.
RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
RGB_TARGET_OVERLAP_MIN = 1

CONTROLLED_SV0_CELL = [23, 20]
CONTROLLED_SV1_CELL = [35, 2]
TARGET_AGENT_TYPE = "SurfaceVessel"
DISTRACTOR_AGENT_TYPE = "SphereAgent"


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


def _safe_load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set, np.ndarray)):
        return json.dumps(_json_safe(value), sort_keys=True)
    return _json_safe(value)


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


def _load_adapter_config() -> Tuple[Any, np.ndarray, Dict[str, Any]]:
    nav_map_prior, spec = load_scene_map_npz(MAP_NPZ)
    adapter_config = scene_map_config_from_spec(spec)
    return adapter_config, nav_map_prior, spec


def _cell_world(cell: List[int]) -> List[float]:
    adapter_config, _, _ = _load_adapter_config()
    world = grid_to_world(tuple(int(v) for v in cell), config=adapter_config)
    return [float(world[0]), float(world[1]), 0.0]


def _offset_world(origin: List[float], forward_m: float, lateral_m: float, z: float = 0.0) -> List[float]:
    return [float(origin[0]) + float(forward_m), float(origin[1]) + float(lateral_m), float(z)]


def _scene(
    name: str,
    role: str,
    target: Optional[Dict[str, Any]],
    distractor: Optional[Dict[str, Any]],
    position: str,
    distance: str,
    distractor_condition: str,
    expected_target_present: bool,
) -> Dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "include_target": target is not None,
        "include_distractor": distractor is not None,
        "target": target,
        "distractor": distractor,
        "expected_target_present_for_audit": bool(expected_target_present),
        "scenario_factors": {
            "target_position": position,
            "target_distance": distance,
            "distractor_condition": distractor_condition,
        },
    }


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    sv0_world = _cell_world(CONTROLLED_SV0_CELL)
    sv1_world = _cell_world(CONTROLLED_SV1_CELL)

    def target(forward_m: float, lateral_m: float = 0.0, yaw_deg: float = 0.0) -> Dict[str, Any]:
        return {
            "agent_type": TARGET_AGENT_TYPE,
            "location": _offset_world(sv0_world, forward_m, lateral_m, 0.0),
            "rotation": [0.0, 0.0, float(yaw_deg)],
            "forward_m": float(forward_m),
            "lateral_m": float(lateral_m),
            "yaw_deg": float(yaw_deg),
        }

    def distractor(forward_m: float, lateral_m: float = 0.0) -> Dict[str, Any]:
        return {
            "agent_type": DISTRACTOR_AGENT_TYPE,
            "location": _offset_world(sv0_world, forward_m, lateral_m, 0.5),
            "rotation": [0.0, 0.0, 0.0],
            "forward_m": float(forward_m),
            "lateral_m": float(lateral_m),
        }

    scenes = [
        _scene("baseline", "background_reference", None, None, "center", "none", "none", False),
        _scene("target_front_center_near", "calibration_positive_center", target(10.0, 0.0), None, "center", "near_10m", "none", True),
        _scene("target_left_offset_near", "left_offset_regression_from_5c4d", target(10.0, 7.0), None, "left_offset", "near_10m", "none", True),
        _scene("target_right_offset_near", "right_offset_regression_from_5c4d", target(10.0, -7.0), None, "right_offset", "near_10m", "none", True),
        _scene("target_left_fov_edge_near", "left_fov_edge_boundary", target(10.0, 12.0), None, "left_fov_edge", "near_10m", "none", True),
        _scene("target_right_fov_edge_near", "right_fov_edge_boundary", target(10.0, -12.0), None, "right_fov_edge", "near_10m", "none", True),
        _scene("target_front_center_mid", "mid_distance_regression", target(30.0, 0.0), None, "center", "mid_30m", "none", True),
        _scene("target_front_center_far", "far_distance_regression", target(70.0, 0.0), None, "center", "far_70m", "none", True),
        _scene("distractor_only_center", "center_distractor_negative", None, distractor(10.0, 0.0), "center", "near_10m", "distractor_only_center", False),
        _scene("distractor_only_left", "left_distractor_negative", None, distractor(10.0, 7.0), "left_offset", "near_10m", "distractor_only_left", False),
        _scene("distractor_only_right", "right_distractor_negative", None, distractor(10.0, -7.0), "right_offset", "near_10m", "distractor_only_right", False),
        _scene(
            "target_left_with_distractor_right",
            "cross_side_ambiguity_any_hit_risk",
            target(10.0, 7.0),
            distractor(10.0, -7.0),
            "left_offset",
            "near_10m",
            "target_left_distractor_right",
            True,
        ),
        _scene(
            "target_right_with_distractor_left",
            "cross_side_ambiguity_any_hit_risk",
            target(10.0, -7.0),
            distractor(10.0, 7.0),
            "right_offset",
            "near_10m",
            "target_right_distractor_left",
            True,
        ),
        _scene(
            "target_center_with_side_distractor",
            "center_target_side_distractor",
            target(10.0, 0.0),
            distractor(10.0, -10.0),
            "center",
            "near_10m",
            "side_distractor",
            True,
        ),
        _scene(
            "distractor_occludes_target",
            "occluding_distractor_between_camera_and_target",
            target(14.0, 0.0),
            distractor(9.0, 0.0),
            "center",
            "near_14m_occluded",
            "occluding_distractor",
            True,
        ),
    ]

    return {
        "phase_name": PHASE_NAME,
        "purpose": "test whether multi-ray fan RangeFinder mitigates 5C-4D left/right misses without adding distractor false positives",
        "scope": "controlled static target/distractor fan-range boundary scenes",
        "not_claimed": [
            "not a trained image-recognition model",
            "not a production detector",
            "not dynamic target handling",
            "not a modification to baseline search policy",
        ],
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "phase5c4c_or_5c4d_results_modified": False,
        "rgb_signature_logic_matches_5c4c_5c4d": True,
        "rangefinder_mode": "yaw_rotated_single_ray_fan",
        "native_multiray_diagnostic_enabled": True,
        "rangefinder_laser_count": RANGEFINDER_LASER_COUNT,
        "rangefinder_laser_angle": RANGEFINDER_LASER_ANGLE,
        "horizontal_fan_sensor_count": len(FAN_YAW_DEGREES),
        "horizontal_fan_yaw_degrees": list(FAN_YAW_DEGREES),
        "rules_evaluated": {
            "any_hit": "rgb_has_target_signature and any_rangefinder_hit",
            "aligned_hit": "rgb_has_target_signature and matched_rangefinder_beam_hit",
        },
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min": RGB_TARGET_OVERLAP_MIN,
            "baseline_source": "baseline",
            "signature_calibration_source": "target_front_center_near",
            "distractor_rejection_source": "distractor_only_center",
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
        "rangefinder_name": RANGEFINDER_NAME,
        "controlled_world_locations": {"sv0": sv0_world, "sv1": sv1_world},
        "controlled_simplifications": [
            "native LaserCount=9/LaserAngle=60 is captured as a diagnostic because HoloOcean defines LaserAngle as elevation",
            "horizontal fan evidence uses nine yaw-rotated single-ray RangeFinderSensor instances in this independent phase",
            "RGB signature detector thresholds and calibration method are preserved",
            "truth fields are audit labels only",
            "aligned-hit uses image-sector to beam-sector matching, not actor truth",
        ],
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


def _native_multiray_sensor() -> Dict[str, Any]:
    return {
        "sensor_type": "RangeFinderSensor",
        "sensor_name": NATIVE_MULTIRAY_RANGEFINDER_NAME,
        "location": RANGEFINDER_LOCATION,
        "rotation": [0.0, 0.0, 0.0],
        "configuration": {
            "LaserMaxDistance": RANGEFINDER_MAX_DISTANCE_M,
            "LaserCount": RANGEFINDER_LASER_COUNT,
            "LaserAngle": RANGEFINDER_LASER_ANGLE,
            "LaserDebug": False,
        },
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
                _native_multiray_sensor(),
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
                "control_scheme": 1,
                "location": list(distractor["location"]),
                "rotation": list(distractor["rotation"]),
            }
        )
    return {
        "name": "phase5c4e_{0}".format(scene["name"]),
        "world": "OpenWater",
        "package_name": "Ocean",
        "main_agent": "sv0",
        "agents": agents,
    }


def _array_stats(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"present": False, "shape": None, "dtype": None, "size": 0, "min": None, "max": None, "unique_count": None}
    arr = np.asarray(value)
    stats: Dict[str, Any] = {
        "present": True,
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size": int(arr.size),
        "min": None,
        "max": None,
        "unique_count": None,
    }
    if arr.size > 0:
        try:
            numeric = arr.astype(float)
            stats["min"] = float(np.nanmin(numeric))
            stats["max"] = float(np.nanmax(numeric))
            stats["unique_count"] = int(len(np.unique(arr)))
        except Exception as exc:
            stats["stats_error"] = str(exc)
    return stats


def _rgb_diff_signature(rgb_value: Any, baseline_value: Any) -> Dict[str, Any]:
    if rgb_value is None or baseline_value is None:
        return {
            "present": False,
            "changed_pixels": 0,
            "change_bbox_xyxy": None,
            "signature_colors": [],
            "signature_color_counts": {},
        }
    rgb = np.asarray(rgb_value)
    baseline = np.asarray(baseline_value)
    if rgb.ndim < 3 or baseline.ndim < 3 or rgb.shape[:2] != baseline.shape[:2]:
        return {
            "present": False,
            "changed_pixels": 0,
            "change_bbox_xyxy": None,
            "signature_colors": [],
            "signature_color_counts": {},
            "error": "rgb/baseline shape mismatch",
        }

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
        return {
            "present": True,
            "changed_pixels": 0,
            "change_bbox_xyxy": None,
            "signature_colors": [],
            "signature_color_counts": {},
            "roi_xyxy": [x0, y0, x1, y1],
        }

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
    }


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


def _beam_sector(index: int, count: int) -> str:
    if count <= 1:
        return "center"
    third = count / 3.0
    if index < third:
        return "left"
    if index >= 2.0 * third:
        return "right"
    return "center"


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


def _range_summary(value: Any) -> Dict[str, Any]:
    if value is None:
        return {
            "present": False,
            "raw": None,
            "beam_count": 0,
            "hit_beam_indices": [],
            "hit_sectors": [],
            "min_positive_range_m": None,
            "any_hit": False,
        }
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


def _preview_array(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim == 2:
        numeric = arr.astype(float)
        lo = float(np.nanmin(numeric)) if numeric.size else 0.0
        hi = float(np.nanmax(numeric)) if numeric.size else 1.0
        if math.isclose(lo, hi):
            return np.zeros_like(numeric, dtype=np.uint8)
        return np.clip((numeric - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)
    if arr.ndim >= 3:
        img = arr[..., :3] if arr.shape[-1] >= 3 else np.repeat(arr, 3, axis=-1)
        if np.issubdtype(img.dtype, np.floating) and float(np.nanmax(img)) <= 1.0:
            img = img * 255.0
        return np.clip(img, 0, 255).astype(np.uint8)
    return np.clip(arr, 0, 255).astype(np.uint8)


def _save_preview(path: str, value: Any) -> bool:
    try:
        import matplotlib.pyplot as plt

        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = _preview_array(value)
        plt.figure(figsize=(6, 4))
        if img.ndim == 2:
            plt.imshow(img, cmap="viridis")
        else:
            plt.imshow(img)
        plt.axis("off")
        plt.savefig(path, dpi=120, bbox_inches="tight", pad_inches=0)
        plt.close()
        return True
    except Exception as exc:
        print("[WARN] Preview save failed for {0}: {1}".format(path, exc))
        return False


def _save_scene_artifacts(scene_name: str, rgb: Any) -> Dict[str, Any]:
    artifacts = {
        "rgb_preview_path": None,
        "rgb_raw_path": None,
        "rgb_preview_saved": False,
        "rgb_raw_saved": False,
    }
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
    first_native_range = None
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
                if bool(scene.get("include_distractor", False)):
                    env.act("distractor", _zero_action())
                state = env.tick()
                rgb = get_sensor_vector(state, "sv0", RGB_CAMERA_NAME)
                native_range_data = get_sensor_vector(state, "sv0", NATIVE_MULTIRAY_RANGEFINDER_NAME)
                range_data = _aggregate_fan_range(state)
                if first_rgb is None and rgb is not None:
                    first_rgb = np.asarray(rgb).copy()
                if first_range is None and range_data is not None:
                    first_range = np.asarray(range_data).copy()
                if first_native_range is None and native_range_data is not None:
                    first_native_range = np.asarray(native_range_data).copy()
                rsum = _range_summary(range_data)
                native_rsum = _range_summary(native_range_data)
                tick_rows.append(
                    {
                        "scene": scene_name,
                        "tick": int(tick),
                        "rgb_present": rgb is not None,
                        "rangefinder_present": range_data is not None,
                        "native_multiray_rangefinder_raw_beams": native_rsum.get("raw"),
                        "native_multiray_any_hit": bool(native_rsum.get("any_hit", False)),
                        "rangefinder_raw_beams": rsum.get("raw"),
                        "rangefinder_hit_beam_indices": rsum.get("hit_beam_indices"),
                        "rangefinder_hit_sectors": rsum.get("hit_sectors"),
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
        "role": str(scene.get("role", "")),
        "include_target": bool(scene.get("include_target", False)),
        "include_distractor": bool(scene.get("include_distractor", False)),
        "expected_target_present_for_audit": bool(scene.get("expected_target_present_for_audit", False)),
        "scenario_factors": scene.get("scenario_factors", {}),
        "target": scene.get("target"),
        "distractor": scene.get("distractor"),
        "launch_ok": launch_ok,
        "error": error,
        "wall_time_s": float(time.perf_counter() - started),
        "rgb_stats": _array_stats(first_rgb),
        "rangefinder_summary": _range_summary(first_range),
        "native_multiray_rangefinder_summary": _range_summary(first_native_range),
        "first_rgb_raw": first_rgb,
        "artifacts": artifacts,
        "tick_rows": tick_rows,
    }


def _strip_scene_raw(result: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(result)
    clean.pop("first_rgb_raw", None)
    return clean


def _outcome_class(target_present: bool, detected: bool) -> str:
    if target_present and detected:
        return "true_positive"
    if target_present and not detected:
        return "false_negative"
    if not target_present and detected:
        return "false_positive"
    return "true_negative"


def _failure_mode(target_present: bool, detected: bool, rgb_target: bool, any_hit: bool, matched_hit: bool, rule: str) -> str:
    range_ok = any_hit if rule == "any" else matched_hit
    if target_present and not detected:
        if not rgb_target and not range_ok:
            return "false_negative_no_rgb_signature_and_no_required_range_hit"
        if not rgb_target:
            return "false_negative_no_rgb_signature"
        if not range_ok:
            return "false_negative_no_required_range_hit"
    if not target_present and detected:
        return "false_positive_rgb_target_signature_and_required_range_hit"
    return "none"


def _make_detection_events(scene_results: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    baseline_rgb = scene_results.get("baseline", {}).get("first_rgb_raw")
    target_rgb = scene_results.get("target_front_center_near", {}).get("first_rgb_raw")
    distractor_rgb = scene_results.get("distractor_only_center", {}).get("first_rgb_raw")

    target_sig = _rgb_diff_signature(target_rgb, baseline_rgb)
    distractor_sig = _rgb_diff_signature(distractor_rgb, baseline_rgb)
    target_raw_colors = set(str(v) for v in target_sig.get("signature_colors", []))
    distractor_raw_colors = set(str(v) for v in distractor_sig.get("signature_colors", []))
    target_signature_colors = sorted(list(target_raw_colors - distractor_raw_colors))
    distractor_signature_colors = sorted(list(distractor_raw_colors - target_raw_colors))
    shared_signature_colors = sorted(list(target_raw_colors & distractor_raw_colors))

    events: List[Dict[str, Any]] = []
    matrix: List[Dict[str, Any]] = []
    for scene in config.get("scenes", []):
        scene_name = str(scene["name"])
        result = scene_results.get(scene_name, {})
        expected_target_present = bool(scene.get("expected_target_present_for_audit", False))
        rgb_diff = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)
        scene_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        rgb_target_overlap = sorted(list(set(target_signature_colors) & scene_colors))
        rgb_distractor_overlap = sorted(list(set(distractor_signature_colors) & scene_colors))
        rgb_has_target_signature = len(rgb_target_overlap) >= RGB_TARGET_OVERLAP_MIN
        rgb_has_distractor_signature = len(rgb_distractor_overlap) >= RGB_TARGET_OVERLAP_MIN
        bbox = rgb_diff.get("change_bbox_xyxy")
        width = CAMERA_WIDTH
        x_center = None
        if isinstance(bbox, list) and len(bbox) == 4:
            x_center = (float(bbox[0]) + float(bbox[2])) / 2.0
        rgb_signature_sector = _sector_from_x(x_center, width)
        range_summary = result.get("rangefinder_summary", {})
        raw_beams = range_summary.get("raw")
        beam_count = int(range_summary.get("beam_count", 0) or 0)
        hit_indices = list(range_summary.get("hit_beam_indices", []) or [])
        hit_sectors = list(range_summary.get("hit_sectors", []) or [])
        any_hit = bool(range_summary.get("any_hit", False))
        matched_hit = bool(rgb_signature_sector != "none" and rgb_signature_sector in set(hit_sectors))
        found_any_hit = bool(rgb_has_target_signature and any_hit)
        found_aligned = bool(rgb_has_target_signature and matched_hit)
        outcome_any = _outcome_class(expected_target_present, found_any_hit)
        outcome_aligned = _outcome_class(expected_target_present, found_aligned)
        failure_any = _failure_mode(expected_target_present, found_any_hit, rgb_has_target_signature, any_hit, matched_hit, "any")
        failure_aligned = _failure_mode(expected_target_present, found_aligned, rgb_has_target_signature, any_hit, matched_hit, "aligned")
        any_beam_without_aligned = bool(any_hit and not matched_hit)

        event = {
            "event_name": "{0}_multiray_sensor_adapter_event".format(scene_name),
            "scene": scene_name,
            "role": str(scene.get("role", "")),
            "scenario_factors": scene.get("scenario_factors", {}),
            "expected_target_present_for_audit": expected_target_present,
            "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
            "sensor_evidence": {
                "RGBCamera": {
                    "role": "visual identity evidence via calibrated RGB difference signature",
                    "signature_detector": dict(config["rgb_signature_detector"]),
                    "calibration_scene": "target_front_center_near",
                    "baseline_scene": "baseline",
                    "target_signature_colors": target_signature_colors,
                    "distractor_signature_colors": distractor_signature_colors,
                    "shared_signature_colors": shared_signature_colors,
                    "scene_signature_colors": sorted(list(scene_colors)),
                    "target_signature_overlap": rgb_target_overlap,
                    "distractor_signature_overlap": rgb_distractor_overlap,
                    "changed_pixels": rgb_diff.get("changed_pixels"),
                    "change_bbox_xyxy": bbox,
                    "rgb_signature_x_center": x_center,
                    "rgb_signature_sector": rgb_signature_sector,
                    "identity_supported": bool(rgb_has_target_signature),
                },
                "RangeFinderSensor": {
                    "role": "horizontal fan range/object-presence evidence from yaw-rotated single-ray RangeFinder sensors only, not target identity",
                    "present": bool(range_summary.get("present", False)),
                    "rangefinder_mode": "yaw_rotated_single_ray_fan",
                    "horizontal_fan_sensor_count": len(FAN_YAW_DEGREES),
                    "horizontal_fan_yaw_degrees": list(FAN_YAW_DEGREES),
                    "beam_count_observed": beam_count,
                    "raw_beams": raw_beams,
                    "hit_beam_indices": hit_indices,
                    "hit_sectors": hit_sectors,
                    "any_hit": any_hit,
                    "matched_rangefinder_beam_hit": matched_hit,
                    "min_positive_range_m": range_summary.get("min_positive_range_m"),
                    "identity_supported": False,
                },
                "NativeMultiRayDiagnostic": {
                    "role": "diagnostic only; HoloOcean RangeFinder LaserAngle is elevation, not horizontal yaw fan",
                    "laser_count_configured": RANGEFINDER_LASER_COUNT,
                    "laser_angle_configured": RANGEFINDER_LASER_ANGLE,
                    "summary": result.get("native_multiray_rangefinder_summary", {}),
                    "used_for_detection": False,
                },
            },
            "rgb_has_target_signature": bool(rgb_has_target_signature),
            "rgb_has_distractor_signature": bool(rgb_has_distractor_signature),
            "rgb_signature_bbox_xyxy": bbox,
            "rgb_signature_sector": rgb_signature_sector,
            "rangefinder_raw_beams": raw_beams,
            "rangefinder_hit_beam_indices": hit_indices,
            "rangefinder_hit_sectors": hit_sectors,
            "any_rangefinder_hit": any_hit,
            "matched_rangefinder_beam_hit": matched_hit,
            "found_any_hit": found_any_hit,
            "found_aligned": found_aligned,
            "any_hit_rule": "rgb_has_target_signature and any_rangefinder_hit",
            "aligned_hit_rule": "rgb_has_target_signature and matched_rangefinder_beam_hit",
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "identity_decision_source": "RGBCamera" if rgb_has_target_signature else "none",
            "range_decision_source": "RangeFinderSensor" if any_hit else "none",
            "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
            "outcome_any_hit": outcome_any,
            "outcome_aligned": outcome_aligned,
            "failure_mode_any_hit": failure_any,
            "failure_mode_aligned": failure_aligned,
            "any_beam_without_aligned_match": any_beam_without_aligned,
        }
        events.append(event)
        matrix.append(
            {
                "scene": scene_name,
                "target_position": scene.get("scenario_factors", {}).get("target_position"),
                "target_distance": scene.get("scenario_factors", {}).get("target_distance"),
                "distractor_condition": scene.get("scenario_factors", {}).get("distractor_condition"),
                "target_present": expected_target_present,
                "rgb_has_target_signature": bool(rgb_has_target_signature),
                "rgb_has_distractor_signature": bool(rgb_has_distractor_signature),
                "rgb_signature_bbox_xyxy": bbox,
                "rgb_signature_sector": rgb_signature_sector,
                "rangefinder_raw_beams": raw_beams,
                "rangefinder_hit_beam_indices": hit_indices,
                "rangefinder_hit_sectors": hit_sectors,
                "any_rangefinder_hit": any_hit,
                "matched_rangefinder_beam_hit": matched_hit,
                "found_any_hit": found_any_hit,
                "found_aligned": found_aligned,
                "outcome_any_hit": outcome_any,
                "outcome_aligned": outcome_aligned,
                "failure_mode_any_hit": failure_any,
                "failure_mode_aligned": failure_aligned,
                "any_beam_without_aligned_match": any_beam_without_aligned,
                "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
            }
        )

    conclusion = _build_conclusion(matrix, target_signature_colors, distractor_signature_colors, shared_signature_colors, scene_results)
    return events, matrix, conclusion


def _count_by(matrix: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in matrix:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _build_conclusion(
    matrix: List[Dict[str, Any]],
    target_signature_colors: List[str],
    distractor_signature_colors: List[str],
    shared_signature_colors: List[str],
    scene_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    left_right_regression_scenes = {"target_left_offset_near", "target_right_offset_near"}
    d_only_scenes = {"distractor_only_center", "distractor_only_left", "distractor_only_right"}
    cross_side_scenes = {"target_left_with_distractor_right", "target_right_with_distractor_left"}
    by_scene = {str(row["scene"]): row for row in matrix}
    left_right_any_fixed = all(bool(by_scene.get(name, {}).get("found_any_hit", False)) for name in left_right_regression_scenes)
    left_right_aligned_fixed = all(bool(by_scene.get(name, {}).get("found_aligned", False)) for name in left_right_regression_scenes)
    any_false_positive_scenes = [row["scene"] for row in matrix if row.get("outcome_any_hit") == "false_positive"]
    aligned_false_positive_scenes = [row["scene"] for row in matrix if row.get("outcome_aligned") == "false_positive"]
    any_distractor_fp = [name for name in d_only_scenes if by_scene.get(name, {}).get("found_any_hit")]
    aligned_distractor_fp = [name for name in d_only_scenes if by_scene.get(name, {}).get("found_aligned")]
    cross_side_any_success = [name for name in cross_side_scenes if by_scene.get(name, {}).get("found_any_hit")]
    cross_side_aligned_success = [name for name in cross_side_scenes if by_scene.get(name, {}).get("found_aligned")]
    native_all_no_hit = all(
        not bool(result.get("native_multiray_rangefinder_summary", {}).get("any_hit", False))
        for result in scene_results.values()
    )
    conclusion_text = (
        "multi-ray horizontal fan did not solve the 5C-4D left/right misses in this run; inspect beam-sector mapping and HoloOcean sensor geometry before promotion"
    )
    if left_right_aligned_fixed and not aligned_false_positive_scenes:
        conclusion_text = "multi-ray fan plus aligned-hit is suitable for next adapter candidate in tested near left/right scenes"
    elif left_right_any_fixed and not any_false_positive_scenes:
        conclusion_text = "multi-ray fan helps coverage, but aligned sector mapping needs calibration before becoming the primary adapter"

    return {
        "target_signature_colors": target_signature_colors,
        "distractor_signature_colors": distractor_signature_colors,
        "shared_signature_colors": shared_signature_colors,
        "target_signature_present": bool(target_signature_colors),
        "distractor_signature_present": bool(distractor_signature_colors),
        "rgb_target_vs_distractor_disjoint": bool(target_signature_colors and distractor_signature_colors),
        "outcome_counts_any_hit": _count_by(matrix, "outcome_any_hit"),
        "outcome_counts_aligned": _count_by(matrix, "outcome_aligned"),
        "failure_counts_any_hit": _count_by(matrix, "failure_mode_any_hit"),
        "failure_counts_aligned": _count_by(matrix, "failure_mode_aligned"),
        "left_right_any_hit_fixed": bool(left_right_any_fixed),
        "left_right_aligned_hit_fixed": bool(left_right_aligned_fixed),
        "any_hit_false_positive_scenes": any_false_positive_scenes,
        "aligned_hit_false_positive_scenes": aligned_false_positive_scenes,
        "any_hit_distractor_only_false_positive_scenes": any_distractor_fp,
        "aligned_hit_distractor_only_false_positive_scenes": aligned_distractor_fp,
        "cross_side_any_hit_success_scenes": cross_side_any_success,
        "cross_side_aligned_hit_success_scenes": cross_side_aligned_success,
        "any_beam_without_aligned_match_observed": any(bool(row.get("any_beam_without_aligned_match")) for row in matrix),
        "native_multiray_all_no_hit_observed": bool(native_all_no_hit),
        "native_multiray_laser_angle_semantics": "HoloOcean 2.2.2 documents RangeFinderSensor LaserAngle as elevation, not horizontal yaw fan",
        "all_scene_launch_ok": all(bool(r.get("launch_ok", False)) for r in scene_results.values()),
        "all_scenes_rgb_output": all(bool(r.get("rgb_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(r.get("rangefinder_summary", {}).get("present", False)) for r in scene_results.values()),
        "conclusion": conclusion_text,
    }


def _build_summary(config: Dict[str, Any], events: List[Dict[str, Any]], matrix: List[Dict[str, Any]], conclusion: Dict[str, Any], started: float) -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "probe_completed": True,
        "terminated_reason": "multiray_fan_boundary_matrix_complete",
        "scene_count": len(matrix),
        "controlled_adapter_step": True,
        "full_search_policy_loop_run": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "phase5c4c_or_5c4d_results_modified": False,
        "rgb_signature_logic_matches_5c4c_5c4d": True,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "rangefinder_mode": config.get("rangefinder_mode"),
        "native_multiray_diagnostic_enabled": config.get("native_multiray_diagnostic_enabled"),
        "rangefinder_laser_count": RANGEFINDER_LASER_COUNT,
        "rangefinder_laser_angle": RANGEFINDER_LASER_ANGLE,
        "horizontal_fan_sensor_count": len(FAN_YAW_DEGREES),
        "horizontal_fan_yaw_degrees": list(FAN_YAW_DEGREES),
        "rules_evaluated": config.get("rules_evaluated", {}),
        "rgb_signature_detector": config.get("rgb_signature_detector", {}),
        "outcome_counts_any_hit": conclusion.get("outcome_counts_any_hit", {}),
        "outcome_counts_aligned": conclusion.get("outcome_counts_aligned", {}),
        "failure_counts_any_hit": conclusion.get("failure_counts_any_hit", {}),
        "failure_counts_aligned": conclusion.get("failure_counts_aligned", {}),
        "left_right_any_hit_fixed": conclusion.get("left_right_any_hit_fixed"),
        "left_right_aligned_hit_fixed": conclusion.get("left_right_aligned_hit_fixed"),
        "any_hit_false_positive_scenes": conclusion.get("any_hit_false_positive_scenes", []),
        "aligned_hit_false_positive_scenes": conclusion.get("aligned_hit_false_positive_scenes", []),
        "any_hit_distractor_only_false_positive_scenes": conclusion.get("any_hit_distractor_only_false_positive_scenes", []),
        "aligned_hit_distractor_only_false_positive_scenes": conclusion.get("aligned_hit_distractor_only_false_positive_scenes", []),
        "cross_side_any_hit_success_scenes": conclusion.get("cross_side_any_hit_success_scenes", []),
        "cross_side_aligned_hit_success_scenes": conclusion.get("cross_side_aligned_hit_success_scenes", []),
        "any_beam_without_aligned_match_observed": conclusion.get("any_beam_without_aligned_match_observed"),
        "native_multiray_all_no_hit_observed": conclusion.get("native_multiray_all_no_hit_observed"),
        "native_multiray_laser_angle_semantics": conclusion.get("native_multiray_laser_angle_semantics"),
        "target_signature_colors": conclusion.get("target_signature_colors", []),
        "distractor_signature_colors": conclusion.get("distractor_signature_colors", []),
        "shared_signature_colors": conclusion.get("shared_signature_colors", []),
        "target_signature_present": conclusion.get("target_signature_present"),
        "distractor_signature_present": conclusion.get("distractor_signature_present"),
        "rgb_target_vs_distractor_disjoint": conclusion.get("rgb_target_vs_distractor_disjoint"),
        "all_scene_launch_ok": conclusion.get("all_scene_launch_ok"),
        "all_scenes_rgb_output": conclusion.get("all_scenes_rgb_output"),
        "all_scenes_rangefinder_output": conclusion.get("all_scenes_rangefinder_output"),
        "boundary_conclusion": conclusion.get("conclusion"),
        "events_brief": [
            {
                "scene": event["scene"],
                "rgb_has_target_signature": event["rgb_has_target_signature"],
                "rgb_signature_sector": event["rgb_signature_sector"],
                "rangefinder_hit_beam_indices": event["rangefinder_hit_beam_indices"],
                "rangefinder_hit_sectors": event["rangefinder_hit_sectors"],
                "any_rangefinder_hit": event["any_rangefinder_hit"],
                "matched_rangefinder_beam_hit": event["matched_rangefinder_beam_hit"],
                "found_any_hit": event["found_any_hit"],
                "found_aligned": event["found_aligned"],
                "outcome_any_hit": event["outcome_any_hit"],
                "outcome_aligned": event["outcome_aligned"],
                "failure_mode_any_hit": event["failure_mode_any_hit"],
                "failure_mode_aligned": event["failure_mode_aligned"],
                "rgb_artifact": event["rgb_artifact"],
            }
            for event in events
        ],
        "runtime_python_executable": sys.executable,
        "runtime_python_version": sys.version,
        "wall_time_s": float(time.perf_counter() - started),
        "controlled_simplifications": config.get("controlled_simplifications", []),
        "not_claimed": config.get("not_claimed", []),
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4E RGB + Multi-Ray RangeFinder Fan Boundary Summary",
        "",
        "## Status",
        "- Probe Completed: `{0}`".format(summary.get("probe_completed")),
        "- Scene Count: `{0}`".format(summary.get("scene_count")),
        "- RangeFinder Mode: `{0}`".format(summary.get("rangefinder_mode")),
        "- Laser Count: `{0}`".format(summary.get("rangefinder_laser_count")),
        "- Laser Angle: `{0}`".format(summary.get("rangefinder_laser_angle")),
        "- Horizontal Fan Sensor Count: `{0}`".format(summary.get("horizontal_fan_sensor_count")),
        "- Native Multi-Ray All-No-Hit Observed: `{0}`".format(summary.get("native_multiray_all_no_hit_observed")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "- Any-Hit Outcomes: `{0}`".format(summary.get("outcome_counts_any_hit")),
        "- Aligned-Hit Outcomes: `{0}`".format(summary.get("outcome_counts_aligned")),
        "- Left/Right Fixed By Any-Hit: `{0}`".format(summary.get("left_right_any_hit_fixed")),
        "- Left/Right Fixed By Aligned-Hit: `{0}`".format(summary.get("left_right_aligned_hit_fixed")),
        "- Any-Hit False Positives: `{0}`".format(summary.get("any_hit_false_positive_scenes")),
        "- Aligned-Hit False Positives: `{0}`".format(summary.get("aligned_hit_false_positive_scenes")),
        "- Conclusion: `{0}`".format(summary.get("boundary_conclusion")),
        "",
        "## Matrix",
        "| Scene | RGB Sector | Hit Beams | Hit Sectors | Any Found | Aligned Found | Any Outcome | Aligned Outcome |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for row in summary.get("events_brief", []):
        lines.append(
            "| `{scene}` | `{sector}` | `{beams}` | `{sectors}` | `{any_found}` | `{aligned_found}` | `{any_outcome}` | `{aligned_outcome}` |".format(
                scene=row.get("scene"),
                sector=row.get("rgb_signature_sector"),
                beams=row.get("rangefinder_hit_beam_indices"),
                sectors=row.get("rangefinder_hit_sectors"),
                any_found=row.get("found_any_hit"),
                aligned_found=row.get("found_aligned"),
                any_outcome=row.get("outcome_any_hit"),
                aligned_outcome=row.get("outcome_aligned"),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "- Any-hit asks whether multi-ray fan coverage solves misses.",
            "- Aligned-hit asks whether RGB sector and beam sector can be matched without actor truth.",
            "- RangeFinder beams remain range evidence only; identity still comes from RGB signature.",
        ]
    )
    return "\n".join(lines) + "\n"


def _save_overview_visual(matrix: List[Dict[str, Any]]) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont

        rows = []
        for row in matrix:
            path = row.get("rgb_artifact")
            if not path or not os.path.exists(str(path)):
                continue
            rows.append((row, Image.open(str(path)).convert("RGB")))
        if not rows:
            return False
        thumb_w, thumb_h = 256, 192
        cols = 3
        pad = 14
        header_h = 70
        footer_h = 58
        cell_w = thumb_w
        cell_h = header_h + thumb_h + footer_h
        n_rows = int(math.ceil(len(rows) / float(cols)))
        out_w = cols * cell_w + (cols + 1) * pad
        out_h = n_rows * cell_h + (n_rows + 1) * pad
        canvas = Image.new("RGB", (out_w, out_h), (244, 246, 248))
        draw = ImageDraw.Draw(canvas)
        try:
            title_font = ImageFont.truetype("arial.ttf", 17)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            title_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        for idx, (row, img) in enumerate(rows):
            col = idx % cols
            grid_row = idx // cols
            x = pad + col * (cell_w + pad)
            y = pad + grid_row * (cell_h + pad)
            any_ok = str(row.get("outcome_any_hit"))
            aligned_ok = str(row.get("outcome_aligned"))
            color = (30, 128, 73) if aligned_ok == "true_positive" or aligned_ok == "true_negative" else (190, 120, 20)
            if aligned_ok == "false_positive":
                color = (180, 40, 40)
            draw.rectangle([x - 1, y - 1, x + cell_w + 1, y + cell_h + 1], fill=(255, 255, 255), outline=(210, 216, 224))
            draw.rectangle([x, y, x + cell_w, y + 5], fill=color)
            draw.text((x + 8, y + 12), str(row.get("scene"))[:31], fill=(20, 28, 38), font=title_font)
            draw.text((x + 8, y + 38), "any={0} aligned={1}".format(any_ok, aligned_ok), fill=color, font=small_font)
            thumb = img.resize((thumb_w, thumb_h))
            canvas.paste(thumb, (x, y + header_h))
            facts1 = "rgb={0}/{1} any={2} aligned={3}".format(
                row.get("rgb_has_target_signature"),
                row.get("rgb_signature_sector"),
                row.get("found_any_hit"),
                row.get("found_aligned"),
            )
            facts2 = "beams={0} sectors={1}".format(row.get("rangefinder_hit_beam_indices"), row.get("rangefinder_hit_sectors"))
            draw.text((x + 8, y + header_h + thumb_h + 8), facts1[:42], fill=(45, 55, 66), font=small_font)
            draw.text((x + 8, y + header_h + thumb_h + 28), facts2[:42], fill=(82, 92, 105), font=small_font)
        os.makedirs(os.path.dirname(OVERVIEW_PNG), exist_ok=True)
        canvas.save(OVERVIEW_PNG)
        print("Overview saved to: {0}".format(OVERVIEW_PNG))
        return True
    except Exception as exc:
        print("[WARN] Overview visual save failed: {0}".format(exc))
        return False


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

    events, matrix, conclusion = _make_detection_events(scene_results, config)
    summary = _build_summary(config, events, matrix, conclusion, started)
    summary["capture_python_executable"] = sys.executable
    summary["capture_python_version"] = sys.version

    _save_json(SCENE_RESULTS_JSON, {name: _strip_scene_raw(result) for name, result in scene_results.items()})
    _save_json(DETECTION_EVENTS_JSON, events)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(BOUNDARY_MATRIX_JSON, matrix)
    _save_csv(BOUNDARY_MATRIX_CSV, matrix)
    _save_json(SUMMARY_JSON, summary)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    post_git_status = _run_git_status()
    _save_json(
        GIT_STATUS_JSON,
        {
            "phase_name": PHASE_NAME,
            "pre_git_status": pre_git_status,
            "post_git_status": post_git_status,
            "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_git_status, post_git_status),
        },
    )
    print(
        "Phase 5C-4E capture finished: scenes={0}, any={1}, aligned={2}".format(
            summary["scene_count"],
            summary["outcome_counts_any_hit"],
            summary["outcome_counts_aligned"],
        )
    )
    return summary


def run_report() -> Dict[str, Any]:
    started = time.perf_counter()
    config = _safe_load_json(CONFIG_JSON)
    events = _safe_load_json(DETECTION_EVENTS_JSON)
    matrix = _safe_load_json(BOUNDARY_MATRIX_JSON)
    if not isinstance(events, list):
        raise ValueError("Detection events JSON must be a list")
    if not isinstance(matrix, list):
        raise ValueError("Boundary matrix JSON must be a list")
    target_colors = events[0]["sensor_evidence"]["RGBCamera"].get("target_signature_colors", []) if events else []
    distractor_colors = events[0]["sensor_evidence"]["RGBCamera"].get("distractor_signature_colors", []) if events else []
    shared_colors = events[0]["sensor_evidence"]["RGBCamera"].get("shared_signature_colors", []) if events else []
    scene_results = _safe_load_json(SCENE_RESULTS_JSON)
    conclusion = _build_conclusion(matrix, target_colors, distractor_colors, shared_colors, scene_results)
    summary = _build_summary(config, events, matrix, conclusion, started)
    summary["report_python_executable"] = sys.executable
    summary["report_python_version"] = sys.version
    summary["overview_visual_saved"] = _save_overview_visual(matrix)
    _save_json(SUMMARY_JSON, summary)
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
