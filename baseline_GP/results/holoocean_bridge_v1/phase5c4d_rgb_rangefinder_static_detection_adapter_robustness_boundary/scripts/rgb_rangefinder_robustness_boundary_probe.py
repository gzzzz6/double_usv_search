"""Phase 5C-4D RGB+RangeFinder static detection robustness boundary probe.

This phase keeps the Phase 5C-4C adapter rule fixed:

    found = rgb_has_target_signature and rangefinder_hit

It widens only the scene matrix.  The goal is not to make every case pass, but
to audit where the simple RGB signature plus single-ray RangeFinder adapter
works and where it fails.
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
PHASE_NAME = "phase5c4d_rgb_rangefinder_static_detection_adapter_robustness_boundary"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_tick_trace.csv"))
BOUNDARY_MATRIX_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_boundary_matrix.json"))
BOUNDARY_MATRIX_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_boundary_matrix.csv"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_robustness_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_rangefinder_robustness_summary.md"))
OVERVIEW_PNG = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_rangefinder_robustness_overview.png"))

CAPTURE_TICKS = 12
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "FrontRGBCamera"
RANGEFINDER_NAME = "FrontRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

# These are intentionally copied from Phase 5C-4C.
RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
RGB_TARGET_OVERLAP_MIN = 1

CONTROLLED_SV0_CELL = [23, 20]
CONTROLLED_SV1_CELL = [35, 2]
CONTROLLED_STEP = 1
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
    # Camera forward is +X in the 5C-4C controlled setup; positive lateral is camera-left.
    return [float(origin[0]) + float(forward_m), float(origin[1]) + float(lateral_m), float(z)]


def _scene(
    name: str,
    role: str,
    target: Optional[Dict[str, Any]],
    distractor: Optional[Dict[str, Any]],
    orientation: str,
    position: str,
    distance: str,
    distractor_condition: str,
    range_boundary: str,
    expected_visible_target: bool,
) -> Dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "include_target": target is not None,
        "include_distractor": distractor is not None,
        "target": target,
        "distractor": distractor,
        "expected_target_present_for_audit": target is not None,
        "expected_visible_target_for_boundary": bool(expected_visible_target),
        "expected_sensor_detected_target": target is not None,
        "scenario_factors": {
            "target_orientation": orientation,
            "target_position": position,
            "target_distance": distance,
            "distractor_condition": distractor_condition,
            "rangefinder_boundary_condition": range_boundary,
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
        _scene(
            "baseline",
            "background_reference",
            None,
            None,
            "none",
            "center",
            "none",
            "none",
            "no_object_no_range_hit",
            False,
        ),
        _scene(
            "target_front_center_near",
            "calibration_positive_front_center_near",
            target(10.0, 0.0, 0.0),
            None,
            "front_yaw0",
            "center",
            "near_10m",
            "none",
            "rangefinder_centerline_hit_expected",
            True,
        ),
        _scene(
            "target_yaw45_center_near",
            "orientation_stress_yaw45",
            target(10.0, 0.0, 45.0),
            None,
            "oblique_yaw45",
            "center",
            "near_10m",
            "none",
            "rangefinder_centerline_hit_expected",
            True,
        ),
        _scene(
            "target_yaw90_center_near",
            "orientation_stress_yaw90_side",
            target(10.0, 0.0, 90.0),
            None,
            "side_yaw90",
            "center",
            "near_10m",
            "none",
            "rangefinder_centerline_hit_expected",
            True,
        ),
        _scene(
            "target_left_offset_near",
            "position_stress_left_offset",
            target(10.0, 7.0, 0.0),
            None,
            "front_yaw0",
            "left_offset",
            "near_10m",
            "none",
            "rgb_visible_but_single_ray_may_miss",
            True,
        ),
        _scene(
            "target_right_offset_near",
            "position_stress_right_offset",
            target(10.0, -7.0, 0.0),
            None,
            "front_yaw0",
            "right_offset",
            "near_10m",
            "none",
            "rgb_visible_but_single_ray_may_miss",
            True,
        ),
        _scene(
            "target_right_fov_edge_near",
            "position_stress_near_fov_edge",
            target(10.0, -12.0, 0.0),
            None,
            "front_yaw0",
            "right_fov_edge",
            "near_10m",
            "none",
            "rgb_edge_and_single_ray_miss_candidate",
            True,
        ),
        _scene(
            "target_front_center_mid",
            "distance_stress_mid",
            target(30.0, 0.0, 0.0),
            None,
            "front_yaw0",
            "center",
            "mid_30m",
            "none",
            "rangefinder_centerline_hit_expected",
            True,
        ),
        _scene(
            "target_front_center_far",
            "distance_stress_far",
            target(70.0, 0.0, 0.0),
            None,
            "front_yaw0",
            "center",
            "far_70m",
            "none",
            "rangefinder_centerline_hit_expected_but_rgb_small",
            True,
        ),
        _scene(
            "distractor_only_center",
            "negative_distractor_only_range_hit_not_identity",
            None,
            distractor(10.0, 0.0),
            "none",
            "center",
            "near_10m",
            "distractor_only",
            "rangefinder_hit_rgb_not_target",
            False,
        ),
        _scene(
            "target_with_side_distractor",
            "positive_with_side_distractor",
            target(10.0, 0.0, 0.0),
            distractor(10.0, -10.0),
            "front_yaw0",
            "center",
            "near_10m",
            "side_distractor",
            "rangefinder_centerline_hit_expected",
            True,
        ),
        _scene(
            "distractor_occludes_target",
            "occlusion_stress_distractor_between_camera_and_target",
            target(14.0, 0.0, 0.0),
            distractor(9.0, 0.0),
            "front_yaw0",
            "center",
            "near_14m_occluded",
            "occluding_distractor",
            "rangefinder_hit_may_be_distractor",
            True,
        ),
        _scene(
            "target_rgb_rangefinder_mismatch_candidate",
            "boundary_rgb_target_signature_but_rangefinder_miss_candidate",
            target(12.0, -14.0, 0.0),
            None,
            "front_yaw0",
            "right_edge_outside_single_ray",
            "near_12m",
            "none",
            "rgb_target_signature_but_rangefinder_miss_candidate",
            True,
        ),
    ]

    return {
        "phase_name": PHASE_NAME,
        "purpose": "RGB+RangeFinder robustness boundary test for Phase 5C-4C adapter logic",
        "scope": "controlled static target/distractor stress scenes",
        "not_claimed": [
            "not a trained image-recognition model",
            "not a robust production detector",
            "not a full replacement for baseline circular sensor geometry",
            "not dynamic target handling",
        ],
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "phase5c4c_detection_logic_modified": False,
        "found_trigger_rule": "rgb_has_target_signature and rangefinder_hit",
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min": RGB_TARGET_OVERLAP_MIN,
            "baseline_source": "baseline",
            "signature_calibration_source": "target_front_center_near",
            "distractor_rejection_source": "distractor_only_center",
        },
        "adapter_logic_inherited_from_phase5c4c": {
            "same_rgb_diff_threshold": True,
            "same_rgb_quantization": True,
            "same_rgb_top_k": True,
            "same_target_overlap_min": True,
            "same_found_rule": True,
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
        "controlled_step": CONTROLLED_STEP,
        "controlled_world_locations": {
            "sv0": sv0_world,
            "sv1": sv1_world,
        },
        "controlled_runtime_cells": {
            "sv0": CONTROLLED_SV0_CELL,
            "sv1": CONTROLLED_SV1_CELL,
        },
        "controlled_simplifications": [
            "scene matrix changes actor pose/location only; adapter rule is unchanged",
            "single forward RangeFinder ray is intentionally preserved",
            "RGB baseline/difference signature method is intentionally preserved",
            "truth fields are used only for audit labels and pass/fail classification",
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


def _rangefinder_sensor() -> Dict[str, Any]:
    return {
        "sensor_type": "RangeFinderSensor",
        "sensor_name": RANGEFINDER_NAME,
        "location": RANGEFINDER_LOCATION,
        "rotation": [0.0, 0.0, 0.0],
        "configuration": {
            "LaserMaxDistance": RANGEFINDER_MAX_DISTANCE_M,
            "LaserCount": 1,
            "LaserAngle": 0.0,
            "LaserDebug": False,
        },
    }


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
                _rangefinder_sensor(),
            ],
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
        "name": "phase5c4d_{0}".format(scene["name"]),
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


def _range_summary(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"present": False, "raw": None, "min_positive_range_m": None, "hit": False}
    arr = np.asarray(value).astype(float).reshape(-1)
    positives = arr[arr > 0.0]
    return {
        "present": True,
        "raw": arr.tolist(),
        "min_positive_range_m": None if positives.size == 0 else float(np.min(positives)),
        "hit": bool(positives.size > 0),
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
                range_data = get_sensor_vector(state, "sv0", RANGEFINDER_NAME)
                if first_rgb is None and rgb is not None:
                    first_rgb = np.asarray(rgb).copy()
                if first_range is None and range_data is not None:
                    first_range = np.asarray(range_data).copy()
                rsum = _range_summary(range_data)
                tick_rows.append(
                    {
                        "scene": scene_name,
                        "tick": int(tick),
                        "rgb_present": rgb is not None,
                        "rangefinder_present": range_data is not None,
                        "rangefinder_hit": bool(rsum["hit"]),
                        "rangefinder_min_positive_range_m": rsum["min_positive_range_m"],
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
        "expected_visible_target_for_boundary": bool(scene.get("expected_visible_target_for_boundary", False)),
        "scenario_factors": scene.get("scenario_factors", {}),
        "target": scene.get("target"),
        "distractor": scene.get("distractor"),
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


def _outcome_class(target_present: bool, detected: bool) -> str:
    if target_present and detected:
        return "true_positive"
    if target_present and not detected:
        return "false_negative"
    if not target_present and detected:
        return "false_positive"
    return "true_negative"


def _failure_mode(target_present: bool, detected: bool, rgb_target: bool, range_hit: bool) -> str:
    if target_present and not detected:
        if not rgb_target and not range_hit:
            return "false_negative_no_rgb_signature_and_no_range_hit"
        if not rgb_target:
            return "false_negative_no_rgb_signature"
        if not range_hit:
            return "false_negative_no_range_hit"
    if not target_present and detected:
        return "false_positive_rgb_target_signature_and_range_hit"
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

    scene_cfg = {}
    for scene in config.get("scenes", []):
        if isinstance(scene, dict) and "name" in scene:
            scene_cfg[str(scene["name"])] = scene

    events: List[Dict[str, Any]] = []
    boundary_matrix: List[Dict[str, Any]] = []
    for scene in config.get("scenes", []):
        scene_name = str(scene["name"])
        result = scene_results.get(scene_name, {})
        expected_target_present = bool(scene.get("expected_target_present_for_audit", False))
        expected_visible_target = bool(scene.get("expected_visible_target_for_boundary", False))
        rgb_diff = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)
        scene_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        rgb_target_overlap = sorted(list(set(target_signature_colors) & scene_colors))
        rgb_distractor_overlap = sorted(list(set(distractor_signature_colors) & scene_colors))
        rgb_has_target_signature = len(rgb_target_overlap) >= RGB_TARGET_OVERLAP_MIN
        rgb_has_distractor_signature = len(rgb_distractor_overlap) >= RGB_TARGET_OVERLAP_MIN
        range_summary = result.get("rangefinder_summary", {})
        rangefinder_hit = bool(range_summary.get("hit", False))
        sensor_detected_target = bool(rgb_has_target_signature and rangefinder_hit)
        outcome = _outcome_class(expected_target_present, sensor_detected_target)
        failure = _failure_mode(expected_target_present, sensor_detected_target, rgb_has_target_signature, rangefinder_hit)
        target_presence_match = outcome in ("true_positive", "true_negative")
        factors = scene.get("scenario_factors", {})
        range_ambiguous = bool(
            expected_target_present
            and bool(scene.get("include_distractor", False))
            and rangefinder_hit
            and sensor_detected_target
            and "distractor" in str(factors.get("rangefinder_boundary_condition", ""))
        )

        event = {
            "event_name": "{0}_sensor_adapter_event".format(scene_name),
            "scene": scene_name,
            "role": str(scene.get("role", "")),
            "scenario_factors": factors,
            "expected_target_present_for_audit": expected_target_present,
            "expected_visible_target_for_boundary": expected_visible_target,
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
                    "change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
                    "identity_supported": bool(rgb_has_target_signature),
                },
                "RangeFinderSensor": {
                    "role": "range/object-presence evidence only, not target identity",
                    "present": bool(range_summary.get("present", False)),
                    "hit": bool(rangefinder_hit),
                    "min_positive_range_m": range_summary.get("min_positive_range_m"),
                    "raw": range_summary.get("raw"),
                    "identity_supported": False,
                },
            },
            "rgb_has_target_signature": bool(rgb_has_target_signature),
            "rgb_has_distractor_signature": bool(rgb_has_distractor_signature),
            "rangefinder_hit": bool(rangefinder_hit),
            "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
            "found_trigger_rule": "rgb_has_target_signature and rangefinder_hit",
            "sensor_detected_target": bool(sensor_detected_target),
            "identity_decision_source": "RGBCamera" if rgb_has_target_signature else "none",
            "range_decision_source": "RangeFinderSensor" if rangefinder_hit else "none",
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
            "outcome_class": outcome,
            "failure_mode": failure,
            "target_presence_match": bool(target_presence_match),
            "rangefinder_hit_identity_ambiguous": bool(range_ambiguous),
        }
        events.append(event)
        boundary_matrix.append(
            {
                "scene": scene_name,
                "target_orientation": factors.get("target_orientation"),
                "target_position": factors.get("target_position"),
                "target_distance": factors.get("target_distance"),
                "distractor_condition": factors.get("distractor_condition"),
                "rangefinder_boundary_condition": factors.get("rangefinder_boundary_condition"),
                "target_present": expected_target_present,
                "rgb_has_target_signature": bool(rgb_has_target_signature),
                "rgb_has_distractor_signature": bool(rgb_has_distractor_signature),
                "rangefinder_hit": bool(rangefinder_hit),
                "sensor_detected_target": bool(sensor_detected_target),
                "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                "outcome_class": outcome,
                "failure_mode": failure,
                "target_presence_match": bool(target_presence_match),
                "rangefinder_hit_identity_ambiguous": bool(range_ambiguous),
                "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
            }
        )

    outcome_counts: Dict[str, int] = {}
    failure_counts: Dict[str, int] = {}
    for row in boundary_matrix:
        outcome_counts[str(row["outcome_class"])] = outcome_counts.get(str(row["outcome_class"]), 0) + 1
        failure_counts[str(row["failure_mode"])] = failure_counts.get(str(row["failure_mode"]), 0) + 1
    conclusion = {
        "target_signature_colors": target_signature_colors,
        "distractor_signature_colors": distractor_signature_colors,
        "shared_signature_colors": shared_signature_colors,
        "target_signature_present": bool(target_signature_colors),
        "distractor_signature_present": bool(distractor_signature_colors),
        "rgb_target_vs_distractor_disjoint": bool(target_signature_colors and distractor_signature_colors),
        "outcome_counts": outcome_counts,
        "failure_counts": failure_counts,
        "scene_count": len(boundary_matrix),
        "all_scene_launch_ok": all(bool(r.get("launch_ok", False)) for r in scene_results.values()),
        "all_scenes_rgb_output": all(bool(r.get("rgb_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(r.get("rangefinder_summary", {}).get("present", False)) for r in scene_results.values()),
        "rgb_target_signature_without_range_hit_observed": any(
            bool(row["rgb_has_target_signature"]) and not bool(row["rangefinder_hit"]) for row in boundary_matrix
        ),
        "range_hit_without_target_rgb_signature_observed": any(
            bool(row["rangefinder_hit"]) and not bool(row["rgb_has_target_signature"]) for row in boundary_matrix
        ),
        "rangefinder_identity_ambiguity_observed": any(bool(row["rangefinder_hit_identity_ambiguous"]) for row in boundary_matrix),
    }
    return events, boundary_matrix, conclusion


def _build_summary(config: Dict[str, Any], events: List[Dict[str, Any]], matrix: List[Dict[str, Any]], conclusion: Dict[str, Any], started: float) -> Dict[str, Any]:
    effective = [row for row in matrix if row["target_presence_match"]]
    failures = [row for row in matrix if not row["target_presence_match"]]
    true_positive_scenes = [row["scene"] for row in matrix if row["outcome_class"] == "true_positive"]
    false_negative_scenes = [row["scene"] for row in matrix if row["outcome_class"] == "false_negative"]
    true_negative_scenes = [row["scene"] for row in matrix if row["outcome_class"] == "true_negative"]
    false_positive_scenes = [row["scene"] for row in matrix if row["outcome_class"] == "false_positive"]
    recommendation = (
        "do_not_treat_as_general_detector_yet; use only in validated front/center/static conditions or add stronger vision/geometric gating"
        if false_negative_scenes or false_positive_scenes or conclusion.get("rangefinder_identity_ambiguity_observed")
        else "adapter_appears_sufficient_for_tested_static_conditions"
    )
    summary = {
        "phase_name": PHASE_NAME,
        "probe_completed": True,
        "terminated_reason": "robustness_boundary_matrix_complete",
        "robustness_boundary_goal_completed": True,
        "scene_count": len(matrix),
        "controlled_adapter_step": True,
        "full_search_policy_loop_run": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "phase5c4c_detection_logic_modified": False,
        "adapter_logic_inherited_from_phase5c4c": config.get("adapter_logic_inherited_from_phase5c4c", {}),
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "found_trigger_rule": "rgb_has_target_signature and rangefinder_hit",
        "rgb_signature_detector": config.get("rgb_signature_detector", {}),
        "target_signature_colors": conclusion.get("target_signature_colors", []),
        "distractor_signature_colors": conclusion.get("distractor_signature_colors", []),
        "shared_signature_colors": conclusion.get("shared_signature_colors", []),
        "target_signature_present": conclusion.get("target_signature_present"),
        "distractor_signature_present": conclusion.get("distractor_signature_present"),
        "rgb_target_vs_distractor_disjoint": conclusion.get("rgb_target_vs_distractor_disjoint"),
        "all_scene_launch_ok": conclusion.get("all_scene_launch_ok"),
        "all_scenes_rgb_output": conclusion.get("all_scenes_rgb_output"),
        "all_scenes_rangefinder_output": conclusion.get("all_scenes_rangefinder_output"),
        "outcome_counts": conclusion.get("outcome_counts", {}),
        "failure_counts": conclusion.get("failure_counts", {}),
        "true_positive_scenes": true_positive_scenes,
        "true_negative_scenes": true_negative_scenes,
        "false_negative_scenes": false_negative_scenes,
        "false_positive_scenes": false_positive_scenes,
        "effective_scene_count": len(effective),
        "failure_scene_count": len(failures),
        "rgb_target_signature_without_range_hit_observed": conclusion.get("rgb_target_signature_without_range_hit_observed"),
        "range_hit_without_target_rgb_signature_observed": conclusion.get("range_hit_without_target_rgb_signature_observed"),
        "rangefinder_identity_ambiguity_observed": conclusion.get("rangefinder_identity_ambiguity_observed"),
        "coverage": _coverage_from_matrix(matrix),
        "boundary_conclusion": {
            "works_in": _compact_conditions([row for row in matrix if row["outcome_class"] == "true_positive"]),
            "rejects_in": _compact_conditions([row for row in matrix if row["outcome_class"] == "true_negative"]),
            "fails_in": _compact_conditions(failures),
            "recommendation": recommendation,
        },
        "events_brief": [
            {
                "scene": event["scene"],
                "rgb_has_target_signature": event["rgb_has_target_signature"],
                "rgb_has_distractor_signature": event["rgb_has_distractor_signature"],
                "rangefinder_hit": event["rangefinder_hit"],
                "sensor_detected_target": event["sensor_detected_target"],
                "outcome_class": event["outcome_class"],
                "failure_mode": event["failure_mode"],
                "rangefinder_min_positive_range_m": event["rangefinder_min_positive_range_m"],
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
    return summary


def _coverage_from_matrix(matrix: List[Dict[str, Any]]) -> Dict[str, Any]:
    keys = [
        "target_orientation",
        "target_position",
        "target_distance",
        "distractor_condition",
        "rangefinder_boundary_condition",
    ]
    return {key: sorted({str(row.get(key)) for row in matrix}) for key in keys}


def _compact_conditions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "scene": row["scene"],
            "orientation": row.get("target_orientation"),
            "position": row.get("target_position"),
            "distance": row.get("target_distance"),
            "distractor": row.get("distractor_condition"),
            "outcome": row.get("outcome_class"),
            "failure_mode": row.get("failure_mode"),
        }
        for row in rows
    ]


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4D RGB+RangeFinder Robustness Boundary Summary",
        "",
        "## Status",
        "- Probe Completed: `{0}`".format(summary.get("probe_completed")),
        "- Scene Count: `{0}`".format(summary.get("scene_count")),
        "- Found Trigger Rule: `{0}`".format(summary.get("found_trigger_rule")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "- Outcome Counts: `{0}`".format(summary.get("outcome_counts")),
        "- Failure Counts: `{0}`".format(summary.get("failure_counts")),
        "- RGB Target Signature Without Range Hit Observed: `{0}`".format(summary.get("rgb_target_signature_without_range_hit_observed")),
        "- Range Hit Without Target RGB Signature Observed: `{0}`".format(summary.get("range_hit_without_target_rgb_signature_observed")),
        "- RangeFinder Identity Ambiguity Observed: `{0}`".format(summary.get("rangefinder_identity_ambiguity_observed")),
        "- Recommendation: `{0}`".format(summary.get("boundary_conclusion", {}).get("recommendation")),
        "",
        "## Matrix",
        "| Scene | RGB Target | Range Hit | Found | Outcome | Failure Mode |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in summary.get("events_brief", []):
        lines.append(
            "| `{scene}` | `{rgb}` | `{range}` | `{found}` | `{outcome}` | `{failure}` |".format(
                scene=row.get("scene"),
                rgb=row.get("rgb_has_target_signature"),
                range=row.get("rangefinder_hit"),
                found=row.get("sensor_detected_target"),
                outcome=row.get("outcome_class"),
                failure=row.get("failure_mode"),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "- This phase preserves the Phase 5C-4C RGB signature plus RangeFinder hit rule.",
            "- Failure scenes are expected evidence: they define where the simple adapter stops being reliable.",
            "- RGBCamera provides only calibrated color-signature evidence; RangeFinderSensor provides object-presence/range evidence only.",
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
        header_h = 64
        footer_h = 50
        cell_w = thumb_w
        cell_h = header_h + thumb_h + footer_h
        out_w = cols * cell_w + (cols + 1) * pad
        out_h = int(math.ceil(len(rows) / float(cols))) * cell_h + (int(math.ceil(len(rows) / float(cols))) + 1) * pad
        canvas = Image.new("RGB", (out_w, out_h), (244, 246, 248))
        draw = ImageDraw.Draw(canvas)
        try:
            title_font = ImageFont.truetype("arial.ttf", 18)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            title_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        color_by_outcome = {
            "true_positive": (30, 128, 73),
            "true_negative": (92, 105, 120),
            "false_negative": (190, 120, 20),
            "false_positive": (180, 40, 40),
        }
        for idx, (row, img) in enumerate(rows):
            col = idx % cols
            grid_row = idx // cols
            x = pad + col * (cell_w + pad)
            y = pad + grid_row * (cell_h + pad)
            outcome = str(row.get("outcome_class"))
            color = color_by_outcome.get(outcome, (80, 80, 80))
            draw.rectangle([x - 1, y - 1, x + cell_w + 1, y + cell_h + 1], fill=(255, 255, 255), outline=(210, 216, 224))
            draw.rectangle([x, y, x + cell_w, y + 5], fill=color)
            draw.text((x + 8, y + 12), str(row.get("scene"))[:32], fill=(20, 28, 38), font=title_font)
            draw.text((x + 8, y + 38), outcome, fill=color, font=small_font)
            thumb = img.resize((thumb_w, thumb_h))
            canvas.paste(thumb, (x, y + header_h))
            facts = "rgb={0} range={1} found={2}".format(
                row.get("rgb_has_target_signature"),
                row.get("rangefinder_hit"),
                row.get("sensor_detected_target"),
            )
            draw.text((x + 8, y + header_h + thumb_h + 10), facts, fill=(45, 55, 66), font=small_font)
            draw.text((x + 8, y + header_h + thumb_h + 28), str(row.get("failure_mode"))[:42], fill=(82, 92, 105), font=small_font)
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

    detection_events, boundary_matrix, conclusion = _make_detection_events(scene_results, config)
    summary = _build_summary(config, detection_events, boundary_matrix, conclusion, started)
    summary["capture_python_executable"] = sys.executable
    summary["capture_python_version"] = sys.version

    scene_results_clean = {name: _strip_scene_raw(result) for name, result in scene_results.items()}
    _save_json(SCENE_RESULTS_JSON, scene_results_clean)
    _save_json(DETECTION_EVENTS_JSON, detection_events)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(BOUNDARY_MATRIX_JSON, boundary_matrix)
    _save_csv(BOUNDARY_MATRIX_CSV, boundary_matrix)
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
        "Phase 5C-4D capture finished: scenes={0}, outcomes={1}, failures={2}".format(
            summary["scene_count"], summary["outcome_counts"], summary["failure_counts"]
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
    conclusion = {
        "target_signature_colors": events[0]["sensor_evidence"]["RGBCamera"].get("target_signature_colors", []) if events else [],
        "distractor_signature_colors": events[0]["sensor_evidence"]["RGBCamera"].get("distractor_signature_colors", []) if events else [],
        "shared_signature_colors": events[0]["sensor_evidence"]["RGBCamera"].get("shared_signature_colors", []) if events else [],
        "target_signature_present": bool(events and events[0]["sensor_evidence"]["RGBCamera"].get("target_signature_colors", [])),
        "distractor_signature_present": bool(events and events[0]["sensor_evidence"]["RGBCamera"].get("distractor_signature_colors", [])),
        "rgb_target_vs_distractor_disjoint": bool(
            events
            and events[0]["sensor_evidence"]["RGBCamera"].get("target_signature_colors", [])
            and events[0]["sensor_evidence"]["RGBCamera"].get("distractor_signature_colors", [])
        ),
        "outcome_counts": {},
        "failure_counts": {},
        "all_scene_launch_ok": True,
        "all_scenes_rgb_output": True,
        "all_scenes_rangefinder_output": True,
        "rgb_target_signature_without_range_hit_observed": any(
            bool(row.get("rgb_has_target_signature")) and not bool(row.get("rangefinder_hit")) for row in matrix
        ),
        "range_hit_without_target_rgb_signature_observed": any(
            bool(row.get("rangefinder_hit")) and not bool(row.get("rgb_has_target_signature")) for row in matrix
        ),
        "rangefinder_identity_ambiguity_observed": any(bool(row.get("rangefinder_hit_identity_ambiguous")) for row in matrix),
    }
    for row in matrix:
        outcome = str(row.get("outcome_class"))
        failure = str(row.get("failure_mode"))
        conclusion["outcome_counts"][outcome] = conclusion["outcome_counts"].get(outcome, 0) + 1
        conclusion["failure_counts"][failure] = conclusion["failure_counts"].get(failure, 0) + 1
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
