"""Phase 5C-4C RGB+RangeFinder static detection adapter positive/negative closure.

This stage keeps the search-policy code frozen.  It verifies a narrow adapter:
HoloOcean RGBCamera + RangeFinderSensor evidence creates audited target
detection events across baseline, target-only, distractor-only, and
target-with-distractor scenes.  Each event is then passed through the runtime
found/hit/GP/search_info post-update chain.

Run in two modes:

1. Holo Python:
   python rgb_rangefinder_detection_adapter_probe.py --mode capture

2. Base Python:
   python rgb_rangefinder_detection_adapter_probe.py --mode runtime
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
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid  # noqa: E402
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4c_rgb_rangefinder_static_detection_adapter_positive_negative_closure"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))
RUNTIME_FILE = os.path.normpath(os.path.join(BASE_DIR, "marine_knownmap_runtime_2usv.py"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_tick_trace.csv"))
RUNTIME_UPDATE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_runtime_update.json"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_rangefinder_detection_adapter_summary.md"))

CAPTURE_TICKS = 25
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "FrontRGBCamera"
RANGEFINDER_NAME = "FrontRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
RGB_TARGET_OVERLAP_MIN = 1

CONTROLLED_SV0_CELL = [23, 20]
CONTROLLED_SV1_CELL = [35, 2]
CONTROLLED_TARGET_CELL = [23, 21]
CONTROLLED_DISTRACTOR_ONLY_CELL = [23, 21]
CONTROLLED_DISTRACTOR_WITH_TARGET_CELL = [24, 21]
EXPECTED_INITIAL_TARGET_POSITIONS = [[23, 21]]
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


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    sv0_world = _cell_world(CONTROLLED_SV0_CELL)
    sv1_world = _cell_world(CONTROLLED_SV1_CELL)
    target_world = _cell_world(CONTROLLED_TARGET_CELL)
    distractor_only_world = _cell_world(CONTROLLED_DISTRACTOR_ONLY_CELL)
    distractor_with_target_world = _cell_world(CONTROLLED_DISTRACTOR_WITH_TARGET_CELL)
    distractor_only_world[2] = 0.5
    distractor_with_target_world[2] = 0.5
    return {
        "phase_name": PHASE_NAME,
        "purpose": "RGB+RangeFinder positive/negative sensor-evidence closure",
        "scope": "controlled static target/distractor scenes",
        "not_claimed": [
            "not a full replacement for baseline circular sensor geometry",
            "not a general image-recognition model",
            "not dynamic target handling",
            "not obstacle handling",
        ],
        "policy_name": "marine_knownmap_path_v2_infosampled_2usv",
        "assignment_mode": "not_run_in_this_adapter_probe",
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
        "path_safety_mode": "soft_clearance_astar_v1",
        "team_path_avoidance_mode": "reservation_v1",
        "team_reservation_safety_distance_cells": 1.5,
        "safe_nav_inflation_radius_cells": 0,
        "safe_nav_soft_clearance_radius_cells": 1,
        "safe_nav_lambda_clearance": 1.0,
        "team_reservation_lambda": 1.0,
        "constraint_mode": "hard",
        "r_hit": 1,
        "clue_samples_per_step": 24,
        "episode_seed": 0,
        "n_targets": 1,
        "expected_initial_target_positions": EXPECTED_INITIAL_TARGET_POSITIONS,
        "controlled_step": CONTROLLED_STEP,
        "controlled_runtime_cells": {
            "sv0": CONTROLLED_SV0_CELL,
            "sv1": CONTROLLED_SV1_CELL,
            "target_index_0": CONTROLLED_TARGET_CELL,
            "distractor_only_marker": CONTROLLED_DISTRACTOR_ONLY_CELL,
            "distractor_with_target_marker": CONTROLLED_DISTRACTOR_WITH_TARGET_CELL,
        },
        "controlled_world_locations": {
            "sv0": sv0_world,
            "sv1": sv1_world,
            "target": target_world,
            "distractor_only": distractor_only_world,
            "distractor_with_target": distractor_with_target_world,
        },
        "controlled_simplifications": [
            "target marker is a SurfaceVessel actor placed one 10m grid cell directly in front of sv0",
            "distractor marker is a SphereAgent actor placed in controlled frontal/side positions",
            "sv0 camera and rangefinder point along +X toward the target",
            "target index mapping is the single-target adapter contract",
            "camera FOV-grid footprint replacement is not attempted",
            "circular miss update is skipped",
        ],
        "holo_world": "OpenWater",
        "holo_package": "Ocean",
        "capture_ticks": CAPTURE_TICKS,
        "camera_width": CAMERA_WIDTH,
        "camera_height": CAMERA_HEIGHT,
        "camera_hz": CAMERA_HZ,
        "camera_location": CAMERA_LOCATION,
        "rangefinder_location": RANGEFINDER_LOCATION,
        "rgb_camera_name": RGB_CAMERA_NAME,
        "rangefinder_name": RANGEFINDER_NAME,
        "rangefinder_max_distance_m": RANGEFINDER_MAX_DISTANCE_M,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "runtime_imported_in_capture_mode": False,
        "runtime_imported_in_runtime_mode": True,
        "search_decision_algorithm_modified": False,
        "core_algorithm_files_frozen": [
            "core_search_policy.py",
            "core_execution.py",
            "core_targets.py",
            "core_intensity.py",
            "core_safe_nav.py",
            "marine_knownmap_runtime.py",
            "marine_knownmap_runtime_2usv.py",
            "holoocean_bridge/*",
        ],
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "detection_event_source": "RGBCamera RGB signature overlap AND RangeFinderSensor range hit",
        "identity_decision_source": "RGBCamera signature overlap",
        "range_decision_source": "RangeFinderSensor hit",
        "found_trigger_rule": "rgb_has_target_signature and rangefinder_hit",
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min": RGB_TARGET_OVERLAP_MIN,
            "baseline_source": "no_target_baseline_scene",
            "signature_calibration_source": "target_only_scene",
            "distractor_rejection_source": "distractor_only_scene",
        },
        "scenes": [
            {
                "name": "baseline",
                "include_target": False,
                "include_distractor": False,
                "expected_target_present_for_audit": False,
                "expected_sensor_detected_target": False,
                "role": "background_reference",
            },
            {
                "name": "target_only",
                "include_target": True,
                "include_distractor": False,
                "expected_target_present_for_audit": True,
                "expected_sensor_detected_target": True,
                "role": "target_positive_and_signature_calibration",
            },
            {
                "name": "distractor_only",
                "include_target": False,
                "include_distractor": True,
                "distractor_location_key": "distractor_only",
                "expected_target_present_for_audit": False,
                "expected_sensor_detected_target": False,
                "role": "distractor_negative",
            },
            {
                "name": "target_and_distractor",
                "include_target": True,
                "include_distractor": True,
                "distractor_location_key": "distractor_with_target",
                "expected_target_present_for_audit": True,
                "expected_sensor_detected_target": True,
                "role": "target_positive_with_distractor_present",
            },
        ],
        "map_npz": MAP_NPZ,
        "runtime_file": RUNTIME_FILE,
        "runtime_file_mtime": os.path.getmtime(RUNTIME_FILE) if os.path.exists(RUNTIME_FILE) else None,
        "pre_git_status": pre_git_status if pre_git_status is not None else [],
    }


def _camera_sensor() -> Dict[str, Any]:
    return {
        "sensor_type": "RGBCamera",
        "sensor_name": RGB_CAMERA_NAME,
        "location": CAMERA_LOCATION,
        "rotation": [0.0, 0.0, 0.0],
        "Hz": CAMERA_HZ,
        "configuration": {
            "CaptureWidth": CAMERA_WIDTH,
            "CaptureHeight": CAMERA_HEIGHT,
        },
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


def _zero_action(agent_name: str) -> np.ndarray:
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
    if bool(scene.get("include_target", False)):
        agents.append(
            {
                "agent_name": "target",
                "agent_type": TARGET_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": 0,
                "location": list(locations["target"]),
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    if bool(scene.get("include_distractor", False)):
        location_key = str(scene.get("distractor_location_key", "distractor_only"))
        agents.append(
            {
                "agent_name": "distractor",
                "agent_type": DISTRACTOR_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": 1,
                "location": list(locations[location_key]),
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    return {
        "name": "phase5c4c_{0}".format(scene["name"]),
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
                env.act("sv0", _zero_action("sv0"))
                env.act("sv1", _zero_action("sv1"))
                if bool(scene.get("include_target", False)):
                    env.act("target", _zero_action("target"))
                if bool(scene.get("include_distractor", False)):
                    env.act("distractor", _zero_action("distractor"))
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
        "expected_sensor_detected_target": bool(scene.get("expected_sensor_detected_target", False)),
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


def _make_detection_events(scene_results: Dict[str, Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    baseline_rgb = scene_results.get("baseline", {}).get("first_rgb_raw")
    target_rgb = scene_results.get("target_only", {}).get("first_rgb_raw")
    distractor_rgb = scene_results.get("distractor_only", {}).get("first_rgb_raw")

    target_sig = _rgb_diff_signature(target_rgb, baseline_rgb)
    distractor_sig = _rgb_diff_signature(distractor_rgb, baseline_rgb)
    baseline_sig = _rgb_diff_signature(baseline_rgb, baseline_rgb)

    target_raw_colors = set(str(v) for v in target_sig.get("signature_colors", []))
    distractor_raw_colors = set(str(v) for v in distractor_sig.get("signature_colors", []))
    target_signature_colors = sorted(list(target_raw_colors - distractor_raw_colors))
    distractor_signature_colors = sorted(list(distractor_raw_colors - target_raw_colors))
    shared_signature_colors = sorted(list(target_raw_colors & distractor_raw_colors))
    target_vs_distractor_disjoint = bool(target_signature_colors) and bool(distractor_signature_colors)

    scene_cfg = {}
    for scene in config.get("scenes", []):
        if isinstance(scene, dict) and "name" in scene:
            scene_cfg[str(scene["name"])] = scene

    events: List[Dict[str, Any]] = []
    scene_matrix: Dict[str, Dict[str, Any]] = {}
    for scene_name in ("baseline", "target_only", "distractor_only", "target_and_distractor"):
        result = scene_results.get(scene_name, {})
        scene = scene_cfg.get(scene_name, {})
        expected_target_present = bool(scene.get("expected_target_present_for_audit", False))
        expected_sensor_detected = bool(scene.get("expected_sensor_detected_target", False))
        rgb_diff = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)
        scene_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        rgb_target_overlap = sorted(list(set(target_signature_colors) & scene_colors))
        rgb_distractor_overlap = sorted(list(set(distractor_signature_colors) & scene_colors))
        rgb_has_target_signature = len(rgb_target_overlap) >= RGB_TARGET_OVERLAP_MIN
        rgb_has_distractor_signature = len(rgb_distractor_overlap) >= RGB_TARGET_OVERLAP_MIN
        range_summary = result.get("rangefinder_summary", {})
        rangefinder_hit = bool(range_summary.get("hit", False))
        sensor_detected_target = bool(rgb_has_target_signature and rangefinder_hit)
        target_detection_correct = bool(sensor_detected_target == expected_sensor_detected)
        false_positive = bool(sensor_detected_target and not expected_target_present)

        event = {
            "event_name": "{0}_sensor_adapter_event".format(scene_name),
            "scene": scene_name,
            "role": str(scene.get("role", "")),
            "expected_target_present_for_audit": expected_target_present,
            "expected_sensor_detected_target": expected_sensor_detected,
            "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
            "sensor_evidence": {
                "RGBCamera": {
                    "role": "visual identity evidence via calibrated RGB difference signature",
                    "signature_detector": dict(config["rgb_signature_detector"]),
                    "calibration_scene": "target_only",
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
            "target_index_selected": 0 if sensor_detected_target else None,
            "target_index_mapping_source": "single_target_static_adapter_contract",
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
            "target_detection_correct_for_scene": bool(target_detection_correct),
            "distractor_false_positive": bool(false_positive),
        }
        events.append(event)
        scene_matrix[scene_name] = {
            "expected_target_present_for_audit": expected_target_present,
            "expected_sensor_detected_target": expected_sensor_detected,
            "rgb_has_target_signature": bool(rgb_has_target_signature),
            "rgb_has_distractor_signature": bool(rgb_has_distractor_signature),
            "rangefinder_hit": bool(rangefinder_hit),
            "sensor_detected_target": bool(sensor_detected_target),
            "target_detection_correct_for_scene": bool(target_detection_correct),
            "distractor_false_positive": bool(false_positive),
        }

    baseline_range = scene_results.get("baseline", {}).get("rangefinder_summary", {})
    object_scene_names = ("target_only", "distractor_only", "target_and_distractor")
    positive_scene_names = ("target_only", "target_and_distractor")
    negative_scene_names = ("baseline", "distractor_only")
    positive_scene_detected = all(bool(scene_matrix.get(name, {}).get("sensor_detected_target", False)) for name in positive_scene_names)
    negative_scene_not_detected = all(not bool(scene_matrix.get(name, {}).get("sensor_detected_target", False)) for name in negative_scene_names)
    distractor_negative_ok = not bool(scene_matrix.get("distractor_only", {}).get("distractor_false_positive", False))
    target_and_distractor_ok = bool(scene_matrix.get("target_and_distractor", {}).get("sensor_detected_target", False))

    conclusion = {
        "target_signature_colors": target_signature_colors,
        "distractor_signature_colors": distractor_signature_colors,
        "shared_signature_colors": shared_signature_colors,
        "target_signature_present": bool(target_signature_colors),
        "distractor_signature_present": bool(distractor_signature_colors),
        "target_vs_distractor_disjoint": bool(target_vs_distractor_disjoint),
        "rgb_target_vs_distractor_disjoint": bool(target_vs_distractor_disjoint),
        "positive_scene_detected": bool(positive_scene_detected),
        "negative_scene_not_detected": bool(negative_scene_not_detected),
        "distractor_negative_ok": bool(distractor_negative_ok),
        "target_and_distractor_ok": bool(target_and_distractor_ok),
        "rangefinder_baseline_hit": bool(baseline_range.get("hit", False)),
        "rangefinder_object_scene_hits": [
            bool(scene_results.get(name, {}).get("rangefinder_summary", {}).get("hit", False))
            for name in object_scene_names
        ],
        "rangefinder_object_presence_supported": bool(
            (not bool(baseline_range.get("hit", False)))
            and any(
                bool(scene_results.get(name, {}).get("rangefinder_summary", {}).get("hit", False))
                for name in object_scene_names
            )
        ),
        "all_scene_launch_ok": all(bool(r.get("launch_ok", False)) for r in scene_results.values()),
        "all_scenes_rgb_output": all(bool(r.get("rgb_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(r.get("rangefinder_summary", {}).get("present", False)) for r in scene_results.values()),
        "all_detection_events_correct": all(bool(e["target_detection_correct_for_scene"]) for e in events),
        "composite_sensor_detection_supported": bool(positive_scene_detected and negative_scene_not_detected and distractor_negative_ok),
    }
    return events, conclusion


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

    detection_events, capture_conclusion = _make_detection_events(scene_results, config)
    capture_conclusion["capture_wall_time_s"] = float(time.perf_counter() - started)
    capture_conclusion["capture_python_executable"] = sys.executable
    capture_conclusion["capture_python_version"] = sys.version

    scene_results_clean = {name: _strip_scene_raw(result) for name, result in scene_results.items()}
    _save_json(SCENE_RESULTS_JSON, scene_results_clean)
    _save_json(DETECTION_EVENTS_JSON, detection_events)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    print(
        "Phase 5C-4C capture finished: positives={0}, negatives={1}, events_correct={2}".format(
            capture_conclusion["positive_scene_detected"],
            capture_conclusion["negative_scene_not_detected"],
            capture_conclusion["all_detection_events_correct"],
        )
    )
    return capture_conclusion


def _runtime_imports() -> Dict[str, Any]:
    from baseline_GP.core_staleness import init_last_seen
    from baseline_GP.marine_knownmap_runtime_2usv import (
        FREE,
        _append_anomaly_target_neighborhood_metric,
        _init_two_usv_knownmap_state,
        _remaining_target_intensity_mass,
        _sample_and_update_team_gp,
        _update_team_search_info_state,
        apply_known_occupancy_constraints,
        build_staleness_map,
        hit_update_intensity,
        known_free_observation_ratio,
        peak_intensity_ratio,
        refresh_last_seen,
        remaining_intensity_mass,
        update_found_mask,
    )

    return {
        "FREE": FREE,
        "init_last_seen": init_last_seen,
        "_append_anomaly_target_neighborhood_metric": _append_anomaly_target_neighborhood_metric,
        "_init_two_usv_knownmap_state": _init_two_usv_knownmap_state,
        "_remaining_target_intensity_mass": _remaining_target_intensity_mass,
        "_sample_and_update_team_gp": _sample_and_update_team_gp,
        "_update_team_search_info_state": _update_team_search_info_state,
        "apply_known_occupancy_constraints": apply_known_occupancy_constraints,
        "build_staleness_map": build_staleness_map,
        "hit_update_intensity": hit_update_intensity,
        "known_free_observation_ratio": known_free_observation_ratio,
        "peak_intensity_ratio": peak_intensity_ratio,
        "refresh_last_seen": refresh_last_seen,
        "remaining_intensity_mass": remaining_intensity_mass,
        "update_found_mask": update_found_mask,
    }


def _initialize_state(config: Dict[str, Any], rt: Dict[str, Any]) -> Dict[str, Any]:
    init_state = rt["_init_two_usv_knownmap_state"]
    state = init_state(
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
    state["viewpoint_generation_mode"] = "simple_ring_v1"
    state["assignment_mode"] = "coordinated"
    state["planner_adaptation_mode"] = "adaptive"
    return state


def _configure_controlled_runtime_state(state: Dict[str, Any], config: Dict[str, Any], rt: Dict[str, Any]) -> Dict[str, Any]:
    initial_target_positions = _json_safe(state["target_positions"])
    expected = config["expected_initial_target_positions"]
    if initial_target_positions != expected:
        raise AssertionError("Unexpected seed target positions: {0} != {1}".format(initial_target_positions, expected))

    cells = config["controlled_runtime_cells"]
    state["usv_states"][0]["robot_pos"] = tuple(int(v) for v in cells["sv0"])
    state["usv_states"][0]["trajectory"] = [tuple(int(v) for v in cells["sv0"])]
    state["usv_states"][0]["committed_segment"] = [tuple(int(v) for v in cells["sv0"])]
    state["usv_states"][1]["robot_pos"] = tuple(int(v) for v in cells["sv1"])
    state["usv_states"][1]["trajectory"] = [tuple(int(v) for v in cells["sv1"])]
    state["usv_states"][1]["committed_segment"] = [tuple(int(v) for v in cells["sv1"])]

    init_last_seen = rt["init_last_seen"]
    refresh_last_seen = rt["refresh_last_seen"]
    build_staleness_map = rt["build_staleness_map"]
    state["last_seen_step"] = init_last_seen(state["nav_map_prior"])
    for local in state["usv_states"]:
        refresh_last_seen(
            state["last_seen_step"],
            state["nav_map_prior"],
            tuple(int(v) for v in local["robot_pos"]),
            state["sensor_range_cells"],
            step=0,
        )
    state["staleness_map"] = build_staleness_map(
        state["last_seen_step"],
        state["nav_map_prior"],
        current_step=0,
        tau_stale=int(config["staleness_tau_steps"]),
    )
    return {
        "initial_target_positions": initial_target_positions,
        "controlled_robot_positions": [list(state["usv_states"][0]["robot_pos"]), list(state["usv_states"][1]["robot_pos"])],
        "controlled_target_positions": _json_safe(state["target_positions"]),
    }


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


def _search_info_stats(state: Dict[str, Any], rt: Dict[str, Any]) -> Dict[str, Any]:
    search_info = np.asarray(state["search_info_map"], dtype=float)
    nav_map = np.asarray(state["nav_map_prior"])
    free_mask = nav_map == rt["FREE"]
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
        "search_info_valid": bool(search_info.shape == nav_map.shape and not np.isnan(search_info).any()),
    }


def _runtime_update_from_sensor_event(
    state: Dict[str, Any],
    event: Dict[str, Any],
    config: Dict[str, Any],
    rt: Dict[str, Any],
) -> Dict[str, Any]:
    step = int(config["controlled_step"])
    update_found_mask = rt["update_found_mask"]
    hit_update_intensity = rt["hit_update_intensity"]
    apply_known_occupancy_constraints = rt["apply_known_occupancy_constraints"]
    remaining_intensity_mass = rt["remaining_intensity_mass"]
    peak_intensity_ratio = rt["peak_intensity_ratio"]
    known_free_observation_ratio = rt["known_free_observation_ratio"]
    _remaining_target_intensity_mass = rt["_remaining_target_intensity_mass"]
    _sample_and_update_team_gp = rt["_sample_and_update_team_gp"]
    _update_team_search_info_state = rt["_update_team_search_info_state"]
    _append_anomaly_target_neighborhood_metric = rt["_append_anomaly_target_neighborhood_metric"]

    initial_gp_counts = _gp_observation_counts(state)
    initial_search_stats = _search_info_stats(state, rt)
    initial_found_mask = _json_safe(state["found_mask"])
    initial_find_times = _json_safe(state["find_times"])
    remaining_target_mass_before = float(_remaining_target_intensity_mass(state))

    team_detected_mask = np.zeros_like(state["found_mask"], dtype=bool)
    if bool(event.get("sensor_detected_target", False)):
        target_index = int(event.get("target_index_selected", 0))
        team_detected_mask[target_index] = True

    predicted_intensity = apply_known_occupancy_constraints(
        state["intensity_map"],
        state["nav_map_prior"],
        preserve_mass=True,
    )
    new_indices = update_found_mask(state["found_mask"], team_detected_mask, state["find_times"], step)

    updated_intensity = predicted_intensity
    hit_update_applied = False
    if new_indices:
        hit_positions = [tuple(int(v) for v in state["target_positions"][idx]) for idx in new_indices]
        updated_intensity = hit_update_intensity(
            updated_intensity,
            hit_positions=hit_positions,
            hit_count=len(new_indices),
            r_hit=int(state["r_hit"]),
            known_map=state["nav_map_prior"],
            target_total_mass=_remaining_target_intensity_mass(state),
        )
        hit_update_applied = True

    state["intensity_map"] = updated_intensity
    _sample_and_update_team_gp(state, step=step, gp_fit_every=1)
    _update_team_search_info_state(state, state["intensity_map"])
    _append_anomaly_target_neighborhood_metric(state, step=step)

    found_count_after = int(state["found_mask"].sum())
    remaining_mass_after = float(remaining_intensity_mass(state["intensity_map"]))
    peak_ratio_after = float(peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"]))
    state["found_count_curve"].append(found_count_after)
    state["remaining_intensity_mass_curve"].append(remaining_mass_after)
    state["peak_intensity_ratio_curve"].append(peak_ratio_after)
    state["known_free_observation_ratio_curve"].append(
        known_free_observation_ratio(state["last_seen_step"], state["nav_map_prior"])
    )
    state["completed_steps"] = step
    state["terminated_reason"] = "sensor_found_adapter_complete" if found_count_after == int(config["n_targets"]) else "sensor_adapter_no_detection"

    final_gp_counts = _gp_observation_counts(state)
    final_search_stats = _search_info_stats(state, rt)
    trace = {
        "step": step,
        "scene": str(event.get("scene", "")),
        "controlled_adapter_step": True,
        "physical_execution_called": False,
        "physical_execution_reason": "controlled static sensor capture only; no search-policy movement in 5C-4C",
        "baseline_detect_targets_called": False,
        "detect_targets_replaced_by_sensor_adapter": True,
        "sensor_detection_event": event,
        "team_detected_mask_source": "sensor_adapter_event_only",
        "team_detected_mask": _json_safe(team_detected_mask),
        "update_found_mask_called": True,
        "new_found_indices": [int(v) for v in new_indices],
        "team_detected_count": int(len(new_indices)),
        "team_miss_update_called": False,
        "circular_miss_update_skipped_due_to_camera_fov": True,
        "hit_update_called": bool(hit_update_applied),
        "hit_update_source": "sensor_adapter_found_event",
        "team_gp_update_called": True,
        "team_search_info_update_called": True,
        "anomaly_metric_update_called": True,
        "found_count_before": int(np.sum(initial_found_mask)),
        "found_count_after": found_count_after,
        "found_mask_before": initial_found_mask,
        "found_mask_after": _json_safe(state["found_mask"]),
        "find_times_before": initial_find_times,
        "find_times_after": _json_safe(state["find_times"]),
        "target_positions": _json_safe(state["target_positions"]),
        "remaining_target_mass_before": remaining_target_mass_before,
        "remaining_target_mass_after": float(_remaining_target_intensity_mass(state)),
        "remaining_intensity_mass_after": remaining_mass_after,
        "peak_intensity_ratio_after": peak_ratio_after,
    }
    trace.update({"initial_" + k: v for k, v in initial_gp_counts.items()})
    trace.update({"final_" + k: v for k, v in final_gp_counts.items()})
    trace.update({"initial_" + k: v for k, v in initial_search_stats.items()})
    trace.update({"final_" + k: v for k, v in final_search_stats.items()})
    return trace


def _build_summary_md(summary: Dict[str, Any]) -> str:
    return """# Phase 5C-4C RGB+RangeFinder Positive/Negative Detection Adapter Closure

## Status
- Probe Completed: `{probe_completed}`
- Terminated Reason: `{terminated_reason}`
- Positive Scenes Detected: `{positive_scenes_detected}`
- Negative Scenes Not Detected: `{negative_scenes_not_detected}`
- Runtime Positive Scenes Found: `{runtime_positive_scenes_found}`
- Runtime Negative Scenes Not Found: `{runtime_negative_scenes_not_found}`
- Found Trigger Rule: `{found_trigger_rule}`
- RangeFinder Object Presence Supported: `{rangefinder_object_presence_supported}`
- Truth Used For Detection: `{truth_used_for_detection}`
- Scene Sensor Outcomes: `{scene_sensor_outcomes}`
- Scene Runtime Outcomes: `{scene_runtime_outcomes}`
- Team GP Update All Scenes: `{team_gp_update_all_scenes}`
- Team Search Info Update All Scenes: `{team_search_info_update_all_scenes}`
- Circular Miss Update Applied Any Scene: `{circular_miss_update_applied_any}`

## Boundary
- Controlled static target/distractor scenes only.
- RGBCamera provides identity evidence through RGB signature overlap.
- RangeFinderSensor provides range/object-presence evidence only.
- SemanticSegmentationCamera and sonar are not used.
- This phase does not replace the baseline circular sensor geometry.
""".format(
        probe_completed=summary.get("probe_completed"),
        terminated_reason=summary.get("terminated_reason"),
        positive_scenes_detected=summary.get("positive_scenes_detected"),
        negative_scenes_not_detected=summary.get("negative_scenes_not_detected"),
        runtime_positive_scenes_found=summary.get("runtime_positive_scenes_found"),
        runtime_negative_scenes_not_found=summary.get("runtime_negative_scenes_not_found"),
        found_trigger_rule=summary.get("found_trigger_rule"),
        rangefinder_object_presence_supported=summary.get("rangefinder_object_presence_supported"),
        truth_used_for_detection=summary.get("truth_used_for_detection"),
        scene_sensor_outcomes=summary.get("scene_sensor_outcomes"),
        scene_runtime_outcomes=summary.get("scene_runtime_outcomes"),
        team_gp_update_all_scenes=summary.get("team_gp_update_all_scenes"),
        team_search_info_update_all_scenes=summary.get("team_search_info_update_all_scenes"),
        circular_miss_update_applied_any=summary.get("circular_miss_update_applied_any"),
    )


def run_runtime() -> Dict[str, Any]:
    started = time.perf_counter()
    if not os.path.exists(CONFIG_JSON):
        raise FileNotFoundError("Missing capture config: {0}".format(CONFIG_JSON))
    if not os.path.exists(DETECTION_EVENTS_JSON):
        raise FileNotFoundError("Missing detection events: {0}".format(DETECTION_EVENTS_JSON))

    config = _safe_load_json(CONFIG_JSON)
    events = _safe_load_json(DETECTION_EVENTS_JSON)
    scene_results = _safe_load_json(SCENE_RESULTS_JSON)
    if not isinstance(events, list):
        raise ValueError("Detection events JSON must be a list")
    if not isinstance(scene_results, dict):
        raise ValueError("Scene results JSON must be a dict")
    events_by_scene: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if isinstance(event, dict) and "scene" in event:
            events_by_scene[str(event["scene"])] = event
    required_scene_names = ("baseline", "target_only", "distractor_only", "target_and_distractor")
    missing_events = [name for name in required_scene_names if name not in events_by_scene]
    if missing_events:
        raise ValueError("Missing detection events for scenes: {0}".format(missing_events))

    rt = _runtime_imports()
    runtime_updates: Dict[str, Dict[str, Any]] = {}
    for scene_name in required_scene_names:
        state = _initialize_state(config, rt)
        controlled_runtime = _configure_controlled_runtime_state(state, config, rt)
        scene_trace = _runtime_update_from_sensor_event(state, events_by_scene[scene_name], config, rt)
        scene_trace["controlled_runtime"] = controlled_runtime
        scene_trace["runtime_python_executable"] = sys.executable
        scene_trace["runtime_python_version"] = sys.version
        runtime_updates[scene_name] = scene_trace

    positive_scene_names = ("target_only", "target_and_distractor")
    negative_scene_names = ("baseline", "distractor_only")
    scene_sensor_outcomes = {
        name: {
            "expected_sensor_detected_target": bool(events_by_scene[name].get("expected_sensor_detected_target", False)),
            "sensor_detected_target": bool(events_by_scene[name].get("sensor_detected_target", False)),
            "rgb_has_target_signature": bool(events_by_scene[name].get("rgb_has_target_signature", False)),
            "rgb_has_distractor_signature": bool(events_by_scene[name].get("rgb_has_distractor_signature", False)),
            "rangefinder_hit": bool(events_by_scene[name].get("rangefinder_hit", False)),
            "target_detection_correct_for_scene": bool(events_by_scene[name].get("target_detection_correct_for_scene", False)),
            "distractor_false_positive": bool(events_by_scene[name].get("distractor_false_positive", False)),
        }
        for name in required_scene_names
    }
    scene_runtime_outcomes = {
        name: {
            "found_mask_after": runtime_updates[name].get("found_mask_after"),
            "find_times_after": runtime_updates[name].get("find_times_after"),
            "new_found_indices": runtime_updates[name].get("new_found_indices"),
            "hit_update_called": bool(runtime_updates[name].get("hit_update_called", False)),
            "team_gp_update_called": bool(runtime_updates[name].get("team_gp_update_called", False)),
            "team_search_info_update_called": bool(runtime_updates[name].get("team_search_info_update_called", False)),
            "team_miss_update_called": bool(runtime_updates[name].get("team_miss_update_called", False)),
            "remaining_intensity_mass_after": runtime_updates[name].get("remaining_intensity_mass_after"),
            "gp_n_obs_initial": runtime_updates[name].get("initial_gp_n_obs"),
            "gp_n_obs_final": runtime_updates[name].get("final_gp_n_obs"),
            "search_info_valid_final": runtime_updates[name].get("final_search_info_valid"),
        }
        for name in required_scene_names
    }

    positive_scenes_detected = all(bool(events_by_scene[name].get("sensor_detected_target", False)) for name in positive_scene_names)
    negative_scenes_not_detected = all(not bool(events_by_scene[name].get("sensor_detected_target", False)) for name in negative_scene_names)
    runtime_positive_scenes_found = all(
        runtime_updates[name].get("found_mask_after") == [True]
        and runtime_updates[name].get("new_found_indices") == [0]
        and bool(runtime_updates[name].get("hit_update_called", False))
        for name in positive_scene_names
    )
    runtime_negative_scenes_not_found = all(
        runtime_updates[name].get("found_mask_after") == [False]
        and runtime_updates[name].get("new_found_indices") == []
        and not bool(runtime_updates[name].get("hit_update_called", False))
        for name in negative_scene_names
    )
    all_detection_events_correct = all(bool(events_by_scene[name].get("target_detection_correct_for_scene", False)) for name in required_scene_names)
    team_gp_update_all_scenes = all(bool(runtime_updates[name].get("team_gp_update_called", False)) for name in required_scene_names)
    team_search_info_update_all_scenes = all(bool(runtime_updates[name].get("team_search_info_update_called", False)) for name in required_scene_names)
    circular_miss_update_applied_any = any(bool(runtime_updates[name].get("team_miss_update_called", False)) for name in required_scene_names)

    target_evidence = events_by_scene["target_only"].get("sensor_evidence", {}).get("RGBCamera", {})
    target_signature_colors = target_evidence.get("target_signature_colors", [])
    distractor_signature_colors = target_evidence.get("distractor_signature_colors", [])
    shared_signature_colors = target_evidence.get("shared_signature_colors", [])
    rangefinder_hit_by_scene = {
        name: bool(events_by_scene[name].get("rangefinder_hit", False)) for name in required_scene_names
    }
    rangefinder_object_presence_supported = bool(
        not rangefinder_hit_by_scene["baseline"]
        and all(rangefinder_hit_by_scene[name] for name in ("target_only", "distractor_only", "target_and_distractor"))
    )

    summary = {
        "phase_name": PHASE_NAME,
        "probe_completed": True,
        "terminated_reason": "positive_negative_closure_complete"
        if positive_scenes_detected and negative_scenes_not_detected and runtime_positive_scenes_found and runtime_negative_scenes_not_found
        else "positive_negative_closure_incomplete",
        "controlled_adapter_step": True,
        "full_search_policy_loop_run": False,
        "search_decision_algorithm_modified": False,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "found_trigger_rule": "rgb_has_target_signature and rangefinder_hit",
        "scene_sensor_outcomes": scene_sensor_outcomes,
        "scene_runtime_outcomes": scene_runtime_outcomes,
        "positive_scene_names": list(positive_scene_names),
        "negative_scene_names": list(negative_scene_names),
        "positive_scenes_detected": bool(positive_scenes_detected),
        "negative_scenes_not_detected": bool(negative_scenes_not_detected),
        "distractor_only_no_false_positive": not bool(events_by_scene["distractor_only"].get("distractor_false_positive", False)),
        "target_and_distractor_detected": bool(events_by_scene["target_and_distractor"].get("sensor_detected_target", False)),
        "all_detection_events_correct": bool(all_detection_events_correct),
        "runtime_positive_scenes_found": bool(runtime_positive_scenes_found),
        "runtime_negative_scenes_not_found": bool(runtime_negative_scenes_not_found),
        "hit_branch_covered": bool(runtime_positive_scenes_found),
        "hit_update_called_positive_scenes": {
            name: bool(runtime_updates[name].get("hit_update_called", False)) for name in positive_scene_names
        },
        "hit_update_called_negative_scenes": {
            name: bool(runtime_updates[name].get("hit_update_called", False)) for name in negative_scene_names
        },
        "team_gp_update_all_scenes": bool(team_gp_update_all_scenes),
        "team_search_info_update_all_scenes": bool(team_search_info_update_all_scenes),
        "circular_miss_update_applied_any": bool(circular_miss_update_applied_any),
        "circular_miss_update_skipped_due_to_camera_fov": True,
        "target_signature_colors": target_signature_colors,
        "distractor_signature_colors": distractor_signature_colors,
        "shared_signature_colors": shared_signature_colors,
        "target_signature_present": bool(target_signature_colors),
        "distractor_signature_present": bool(distractor_signature_colors),
        "rgb_target_vs_distractor_disjoint": bool(target_signature_colors and distractor_signature_colors),
        "rangefinder_hit_by_scene": rangefinder_hit_by_scene,
        "rangefinder_object_presence_supported": bool(rangefinder_object_presence_supported),
        "all_scene_launch_ok": all(bool(v.get("launch_ok", False)) for v in scene_results.values()),
        "all_scenes_rgb_output": all(bool(v.get("rgb_stats", {}).get("present", False)) for v in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(v.get("rangefinder_summary", {}).get("present", False)) for v in scene_results.values()),
        "runtime_python_executable": sys.executable,
        "runtime_python_version": sys.version,
        "runtime_wall_time_s": float(time.perf_counter() - started),
        "controlled_simplifications": config.get("controlled_simplifications", []),
        "not_claimed": config.get("not_claimed", []),
    }

    post_git_status = _run_git_status()
    git_status = {
        "phase_name": PHASE_NAME,
        "pre_git_status": config.get("pre_git_status", []),
        "post_git_status": post_git_status,
        "outside_phase_new_or_changed": _outside_phase_new_or_changed(config.get("pre_git_status", []), post_git_status),
    }

    _save_json(RUNTIME_UPDATE_JSON, runtime_updates)
    _save_json(SUMMARY_JSON, summary)
    _save_json(GIT_STATUS_JSON, git_status)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary saved to: {0}".format(SUMMARY_MD))
    print(
        "Phase 5C-4C runtime finished: reason={0}, positives={1}, negatives={2}".format(
            summary["terminated_reason"],
            summary["runtime_positive_scenes_found"],
            summary["runtime_negative_scenes_not_found"],
        )
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["capture", "runtime"], required=True)
    args = parser.parse_args()
    if args.mode == "capture":
        run_capture()
    elif args.mode == "runtime":
        run_runtime()


if __name__ == "__main__":
    main()
