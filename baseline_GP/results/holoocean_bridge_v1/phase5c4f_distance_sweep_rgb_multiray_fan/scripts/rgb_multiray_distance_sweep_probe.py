"""Phase 5C-4F distance sweep for RGB signature + fan RangeFinder adapter.

This phase answers a narrow question: with the target centered in front of the
camera, at which tested distances does the current RGB signature plus fan
RangeFinder method still produce a found event?

Distances tested: 10 m, 15 m, 20 m, 25 m, 30 m.
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
PHASE_NAME = "phase5c4f_distance_sweep_rgb_multiray_fan"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_tick_trace.csv"))
MATRIX_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_matrix.json"))
MATRIX_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_matrix.csv"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_distance_sweep_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_distance_sweep_summary.md"))
OVERVIEW_PNG = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_distance_sweep_overview.png"))

CAPTURE_TICKS = 12
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "FrontRGBCamera"
FAN_RANGEFINDER_PREFIX = "FanRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
FAN_YAW_DEGREES = [30.0, 22.5, 15.0, 7.5, 0.0, -7.5, -15.0, -22.5, -30.0]
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

# Same RGB signature logic as 5C-4C/5C-4D/5C-4E.
RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
RGB_TARGET_OVERLAP_MIN = 1

CONTROLLED_SV0_CELL = [23, 20]
CONTROLLED_SV1_CELL = [35, 2]
TARGET_AGENT_TYPE = "SurfaceVessel"
DISTANCES_M = [10.0, 15.0, 20.0, 25.0, 30.0]


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
            writer.writerow({key: json.dumps(_json_safe(row.get(key))) if isinstance(row.get(key), (dict, list, tuple)) else _json_safe(row.get(key)) for key in keys})
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


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    sv0_world = _cell_world(CONTROLLED_SV0_CELL)
    sv1_world = _cell_world(CONTROLLED_SV1_CELL)
    scenes: List[Dict[str, Any]] = [
        {
            "name": "baseline",
            "role": "background_reference",
            "include_target": False,
            "target": None,
            "distance_m": None,
            "expected_target_present_for_audit": False,
        }
    ]
    for distance in DISTANCES_M:
        scenes.append(
            {
                "name": "target_front_center_{0:02d}m".format(int(distance)),
                "role": "center_distance_sweep",
                "include_target": True,
                "target": {
                    "agent_type": TARGET_AGENT_TYPE,
                    "location": _offset_world(sv0_world, distance, 0.0, 0.0),
                    "rotation": [0.0, 0.0, 0.0],
                    "forward_m": float(distance),
                    "lateral_m": 0.0,
                    "yaw_deg": 0.0,
                },
                "distance_m": float(distance),
                "expected_target_present_for_audit": True,
            }
        )
    return {
        "phase_name": PHASE_NAME,
        "purpose": "distance sweep for current RGB signature plus fan RangeFinder adapter",
        "scope": "front-center static target distances 10/15/20/25/30m",
        "distances_m": DISTANCES_M,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rgb_signature_logic_matches_5c4c_5c4d_5c4e": True,
        "rangefinder_mode": "yaw_rotated_single_ray_fan",
        "horizontal_fan_sensor_count": len(FAN_YAW_DEGREES),
        "horizontal_fan_yaw_degrees": list(FAN_YAW_DEGREES),
        "found_rule": "rgb_has_target_signature and any_rangefinder_hit",
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min": RGB_TARGET_OVERLAP_MIN,
            "baseline_source": "baseline",
            "signature_calibration_source": "target_front_center_10m",
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
    return {
        "name": "phase5c4f_{0}".format(scene["name"]),
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
        "any_hit": bool(len(hit_indices) > 0),
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
    return np.clip(arr, 0, 255).astype(np.uint8)


def _save_preview(path: str, value: Any) -> bool:
    try:
        import matplotlib.pyplot as plt

        os.makedirs(os.path.dirname(path), exist_ok=True)
        plt.figure(figsize=(6, 4))
        plt.imshow(_preview_array(value))
        plt.axis("off")
        plt.savefig(path, dpi=120, bbox_inches="tight", pad_inches=0)
        plt.close()
        return True
    except Exception as exc:
        print("[WARN] Preview save failed for {0}: {1}".format(path, exc))
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
        "include_target": bool(scene.get("include_target", False)),
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


def _make_events(scene_results: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    baseline_rgb = scene_results.get("baseline", {}).get("first_rgb_raw")
    target_rgb = scene_results.get("target_front_center_10m", {}).get("first_rgb_raw")
    target_sig = _rgb_diff_signature(target_rgb, baseline_rgb)
    target_signature_colors = sorted(list(set(str(v) for v in target_sig.get("signature_colors", []))))
    events: List[Dict[str, Any]] = []
    matrix: List[Dict[str, Any]] = []
    for scene in config["scenes"]:
        name = str(scene["name"])
        result = scene_results.get(name, {})
        expected_target = bool(scene.get("expected_target_present_for_audit", False))
        rgb_diff = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)
        scene_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        overlap = sorted(list(set(target_signature_colors) & scene_colors))
        rgb_has_target_signature = len(overlap) >= RGB_TARGET_OVERLAP_MIN
        range_summary = result.get("rangefinder_summary", {})
        any_hit = bool(range_summary.get("any_hit", False))
        found = bool(rgb_has_target_signature and any_hit)
        outcome = _outcome(expected_target, found)
        event = {
            "scene": name,
            "distance_m": scene.get("distance_m"),
            "expected_target_present_for_audit": expected_target,
            "rgb_has_target_signature": bool(rgb_has_target_signature),
            "rgb_signature_overlap": overlap,
            "rgb_signature_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
            "rgb_changed_pixels": rgb_diff.get("changed_pixels"),
            "rangefinder_raw_beams": range_summary.get("raw"),
            "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
            "rangefinder_hit_sectors": range_summary.get("hit_sectors"),
            "any_rangefinder_hit": any_hit,
            "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
            "found": found,
            "found_rule": "rgb_has_target_signature and any_rangefinder_hit",
            "outcome": outcome,
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
        }
        events.append(event)
        matrix.append(dict(event))
    target_rows = [row for row in matrix if row.get("distance_m") is not None]
    effective_distances = [float(row["distance_m"]) for row in target_rows if row["found"]]
    failed_distances = [float(row["distance_m"]) for row in target_rows if not row["found"]]
    conclusion = {
        "target_signature_colors": target_signature_colors,
        "target_signature_present": bool(target_signature_colors),
        "tested_distances_m": DISTANCES_M,
        "effective_distances_m": effective_distances,
        "failed_distances_m": failed_distances,
        "max_tested_effective_distance_m": max(effective_distances) if effective_distances else None,
        "first_tested_failure_distance_m": min(failed_distances) if failed_distances else None,
        "outcome_counts": _count_by(matrix, "outcome"),
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
        "probe_completed": True,
        "terminated_reason": "distance_sweep_complete",
        "tested_distances_m": DISTANCES_M,
        "scene_count": len(matrix),
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rgb_signature_logic_matches_5c4c_5c4d_5c4e": True,
        "rangefinder_mode": config.get("rangefinder_mode"),
        "horizontal_fan_sensor_count": config.get("horizontal_fan_sensor_count"),
        "horizontal_fan_yaw_degrees": config.get("horizontal_fan_yaw_degrees"),
        "found_rule": config.get("found_rule"),
        "rgb_signature_detector": config.get("rgb_signature_detector"),
        "target_signature_present": conclusion.get("target_signature_present"),
        "effective_distances_m": conclusion.get("effective_distances_m"),
        "failed_distances_m": conclusion.get("failed_distances_m"),
        "max_tested_effective_distance_m": conclusion.get("max_tested_effective_distance_m"),
        "first_tested_failure_distance_m": conclusion.get("first_tested_failure_distance_m"),
        "outcome_counts": conclusion.get("outcome_counts"),
        "all_scene_launch_ok": conclusion.get("all_scene_launch_ok"),
        "all_scenes_rgb_output": conclusion.get("all_scenes_rgb_output"),
        "all_scenes_rangefinder_output": conclusion.get("all_scenes_rangefinder_output"),
        "distance_matrix": matrix,
        "boundary_conclusion": "tested effective up to {0} m; first tested failure at {1} m".format(
            conclusion.get("max_tested_effective_distance_m"),
            conclusion.get("first_tested_failure_distance_m"),
        ),
        "runtime_python_executable": sys.executable,
        "runtime_python_version": sys.version,
        "wall_time_s": float(time.perf_counter() - started),
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4F Distance Sweep Summary",
        "",
        "- Tested Distances: `{0}`".format(summary.get("tested_distances_m")),
        "- Effective Distances: `{0}`".format(summary.get("effective_distances_m")),
        "- Failed Distances: `{0}`".format(summary.get("failed_distances_m")),
        "- Max Tested Effective Distance: `{0}`".format(summary.get("max_tested_effective_distance_m")),
        "- First Tested Failure Distance: `{0}`".format(summary.get("first_tested_failure_distance_m")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "",
        "| Distance | RGB Signature | Range Hit | Found | Outcome |",
        "|---:|---:|---:|---:|---|",
    ]
    for row in summary.get("distance_matrix", []):
        if row.get("distance_m") is None:
            continue
        lines.append(
            "| `{0}` | `{1}` | `{2}` | `{3}` | `{4}` |".format(
                row.get("distance_m"),
                row.get("rgb_has_target_signature"),
                row.get("any_rangefinder_hit"),
                row.get("found"),
                row.get("outcome"),
            )
        )
    return "\n".join(lines) + "\n"


def _save_overview_visual(matrix: List[Dict[str, Any]]) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont

        rows = [row for row in matrix if row.get("distance_m") is not None and row.get("rgb_artifact") and os.path.exists(str(row.get("rgb_artifact")))]
        if not rows:
            return False
        thumb_w, thumb_h = 256, 192
        cols = len(rows)
        pad = 14
        header_h = 58
        footer_h = 56
        out_w = cols * thumb_w + (cols + 1) * pad
        out_h = header_h + thumb_h + footer_h + 2 * pad
        canvas = Image.new("RGB", (out_w, out_h), (244, 246, 248))
        draw = ImageDraw.Draw(canvas)
        try:
            title_font = ImageFont.truetype("arial.ttf", 18)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            title_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        for idx, row in enumerate(rows):
            x = pad + idx * (thumb_w + pad)
            y = pad
            color = (30, 128, 73) if row.get("found") else (190, 120, 20)
            draw.rectangle([x - 1, y - 1, x + thumb_w + 1, y + header_h + thumb_h + footer_h + 1], fill=(255, 255, 255), outline=(210, 216, 224))
            draw.rectangle([x, y, x + thumb_w, y + 5], fill=color)
            draw.text((x + 8, y + 12), "{0} m".format(row.get("distance_m")), fill=(20, 28, 38), font=title_font)
            draw.text((x + 8, y + 36), str(row.get("outcome")), fill=color, font=small_font)
            img = Image.open(str(row.get("rgb_artifact"))).convert("RGB").resize((thumb_w, thumb_h))
            canvas.paste(img, (x, y + header_h))
            facts = "rgb={0} range={1} found={2}".format(row.get("rgb_has_target_signature"), row.get("any_rangefinder_hit"), row.get("found"))
            draw.text((x + 8, y + header_h + thumb_h + 10), facts, fill=(45, 55, 66), font=small_font)
            draw.text((x + 8, y + header_h + thumb_h + 30), "beams={0}".format(row.get("rangefinder_hit_beam_indices")), fill=(82, 92, 105), font=small_font)
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
    events, matrix, conclusion = _make_events(scene_results, config)
    summary = _build_summary(config, events, matrix, conclusion, started)
    _save_json(SCENE_RESULTS_JSON, {name: _strip_scene_raw(result) for name, result in scene_results.items()})
    _save_json(DETECTION_EVENTS_JSON, events)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(MATRIX_JSON, matrix)
    _save_csv(MATRIX_CSV, matrix)
    _save_json(SUMMARY_JSON, summary)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    post_git_status = _run_git_status()
    _save_json(GIT_STATUS_JSON, {"phase_name": PHASE_NAME, "pre_git_status": pre_git_status, "post_git_status": post_git_status, "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_git_status, post_git_status)})
    print("Phase 5C-4F capture finished: effective={0}, failed={1}".format(summary["effective_distances_m"], summary["failed_distances_m"]))
    return summary


def run_report() -> Dict[str, Any]:
    started = time.perf_counter()
    summary = _safe_load_json(SUMMARY_JSON)
    matrix = _safe_load_json(MATRIX_JSON)
    summary["overview_visual_saved"] = _save_overview_visual(matrix)
    summary["report_python_executable"] = sys.executable
    summary["report_python_version"] = sys.version
    summary["report_wall_time_s"] = float(time.perf_counter() - started)
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
