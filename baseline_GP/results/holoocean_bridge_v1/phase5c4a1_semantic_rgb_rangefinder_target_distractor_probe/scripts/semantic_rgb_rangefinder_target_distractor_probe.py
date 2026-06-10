"""Phase 5C-4A-1: semantic/RGB/rangefinder target-vs-distractor probe.

This probe uses controlled HoloOcean scenes to check whether perception sensor
outputs can form an audited detection event without using runtime target truth.
It does not import or modify the known-map search runtime.
"""

from __future__ import annotations

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

from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4a1_semantic_rgb_rangefinder_target_distractor_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_tick_trace.csv"))
CONCLUSION_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_conclusion.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "semantic_rgb_rangefinder_target_distractor_summary.md"))

CAPTURE_TICKS = 25
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "ReferenceRGBCamera"
SEMANTIC_CAMERA_NAME = "FrontSemanticSegmentationCamera"
RANGEFINDER_NAME = "FrontRangeFinder"
RANGEFINDER_MAX_DISTANCE_M = 80.0
CAMERA_LOCATION = [0.0, 0.0, 2.0]
RANGEFINDER_LOCATION = [0.0, 0.0, 0.6]

OBSERVER_LOCATION = [0.0, 0.0, 0.0]
TARGET_LOCATION = [12.0, 0.0, 0.0]
DISTRACTOR_LOCATION = [12.0, 0.0, 0.5]
TARGET_WITH_DISTRACTOR_LOCATION = [12.0, 0.0, 0.0]
DISTRACTOR_WITH_TARGET_LOCATION = [12.0, 4.0, 0.5]
TARGET_AGENT_TYPE = "SurfaceVessel"
DISTRACTOR_AGENT_TYPE = "SphereAgent"
RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
RGB_TARGET_OVERLAP_MIN = 1

SCENES = [
    {"name": "baseline", "include_target": False, "include_distractor": False},
    {"name": "target_only", "include_target": True, "include_distractor": False, "target_location": TARGET_LOCATION},
    {"name": "distractor_only", "include_target": False, "include_distractor": True, "distractor_location": DISTRACTOR_LOCATION},
    {
        "name": "target_and_distractor",
        "include_target": True,
        "include_distractor": True,
        "target_location": TARGET_WITH_DISTRACTOR_LOCATION,
        "distractor_location": DISTRACTOR_WITH_TARGET_LOCATION,
    },
]


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


def _phase_config() -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "purpose": "Target vs non-target perception evidence probe",
        "holo_world": "OpenWater",
        "holo_package": "Ocean",
        "capture_ticks": CAPTURE_TICKS,
        "observer_agent_name": "sv0",
        "observer_agent_type": "SurfaceVessel",
        "target_agent_name": "target",
        "target_agent_type": TARGET_AGENT_TYPE,
        "distractor_agent_name": "distractor",
        "distractor_agent_type": DISTRACTOR_AGENT_TYPE,
        "observer_location": OBSERVER_LOCATION,
        "target_location": TARGET_LOCATION,
        "distractor_location": DISTRACTOR_LOCATION,
        "target_with_distractor_location": TARGET_WITH_DISTRACTOR_LOCATION,
        "distractor_with_target_location": DISTRACTOR_WITH_TARGET_LOCATION,
        "camera_location": CAMERA_LOCATION,
        "rangefinder_location": RANGEFINDER_LOCATION,
        "camera_width": CAMERA_WIDTH,
        "camera_height": CAMERA_HEIGHT,
        "camera_hz": CAMERA_HZ,
        "rgb_camera_name": RGB_CAMERA_NAME,
        "semantic_camera_name": SEMANTIC_CAMERA_NAME,
        "rangefinder_name": RANGEFINDER_NAME,
        "rangefinder_max_distance_m": RANGEFINDER_MAX_DISTANCE_M,
        "perception_sensors": [
            "SemanticSegmentationCamera",
            "RGBCamera",
            "RangeFinderSensor",
        ],
        "navigation_sensors_not_detection_evidence": [
            "LocationSensor",
            "GPSSensor",
            "OrientationSensor",
        ],
        "sensor_roles": {
            "SemanticSegmentationCamera": "semantic identity evidence if a target-specific label/signature exists",
            "RGBCamera": "visual identity evidence through audited RGB difference signatures",
            "RangeFinderSensor": "range/object-presence evidence only, not target identity",
        },
        "rgb_signature_detector": {
            "diff_threshold": RGB_DIFF_THRESHOLD,
            "quantization": RGB_SIGNATURE_QUANTIZATION,
            "top_k": RGB_SIGNATURE_TOP_K,
            "target_overlap_min": RGB_TARGET_OVERLAP_MIN,
        },
        "scenes": SCENES,
        "sonar_used": False,
        "runtime_imported": False,
        "search_decision_algorithm_modified": False,
        "truth_used_for_detection": False,
        "detection_event_source": "SemanticSegmentationCamera signature, RangeFinderSensor range evidence, RGBCamera visual evidence",
    }


def _camera_sensor(sensor_type: str, sensor_name: str) -> Dict[str, Any]:
    return {
        "sensor_type": sensor_type,
        "sensor_name": sensor_name,
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


def _control_scheme(agent_type: str) -> int:
    if agent_type == "SphereAgent":
        return 1
    return 0


def _scenario_config(scene: Dict[str, Any]) -> Dict[str, Any]:
    agents: List[Dict[str, Any]] = [
        {
            "agent_name": "sv0",
            "agent_type": "SurfaceVessel",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "COM"},
                {"sensor_type": "GPSSensor", "socket": "COM"},
                {"sensor_type": "OrientationSensor", "socket": "COM"},
                _camera_sensor("RGBCamera", RGB_CAMERA_NAME),
                _camera_sensor("SemanticSegmentationCamera", SEMANTIC_CAMERA_NAME),
                _rangefinder_sensor(),
            ],
            "control_scheme": 0,
            "location": OBSERVER_LOCATION,
            "rotation": [0.0, 0.0, 0.0],
        }
    ]
    if bool(scene.get("include_target", False)):
        agents.append(
            {
                "agent_name": "target",
                "agent_type": TARGET_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(TARGET_AGENT_TYPE),
                "location": list(scene.get("target_location", TARGET_LOCATION)),
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    if bool(scene.get("include_distractor", False)):
        agents.append(
            {
                "agent_name": "distractor",
                "agent_type": DISTRACTOR_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": _control_scheme(DISTRACTOR_AGENT_TYPE),
                "location": list(scene.get("distractor_location", DISTRACTOR_LOCATION)),
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    return {
        "name": "phase5c4a1_{0}".format(scene["name"]),
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
            stats["min"] = float(np.nanmin(arr.astype(float)))
            stats["max"] = float(np.nanmax(arr.astype(float)))
            stats["unique_count"] = int(len(np.unique(arr)))
        except Exception as exc:
            stats["stats_error"] = str(exc)
    return stats


def _semantic_colors(value: Any) -> Set[Tuple[int, int, int, int]]:
    if value is None:
        return set()
    arr = np.asarray(value)
    if arr.ndim == 2:
        flat = arr.reshape(-1)
        return set((int(v), int(v), int(v), 255) for v in np.unique(flat))
    if arr.ndim >= 3:
        channels = arr.shape[-1]
        if channels == 1:
            flat1 = arr.reshape(-1)
            return set((int(v), int(v), int(v), 255) for v in np.unique(flat1))
        if channels >= 4:
            flat4 = arr[..., :4].reshape(-1, 4)
            unique4 = np.unique(flat4, axis=0)
            return set(tuple(int(v) for v in row) for row in unique4)
        if channels >= 3:
            flat3 = arr[..., :3].reshape(-1, 3)
            unique3 = np.unique(flat3, axis=0)
            return set((int(row[0]), int(row[1]), int(row[2]), 255) for row in unique3)
    return set()


def _color_counts(value: Any) -> Dict[str, int]:
    if value is None:
        return {}
    arr = np.asarray(value)
    if arr.ndim == 2:
        flat = arr.reshape(-1)
        unique, counts = np.unique(flat, return_counts=True)
        return {"{0},{0},{0},255".format(int(v)): int(c) for v, c in zip(unique, counts)}
    if arr.ndim >= 3:
        if arr.shape[-1] >= 4:
            flat = arr[..., :4].reshape(-1, 4)
        elif arr.shape[-1] >= 3:
            rgb = arr[..., :3]
            alpha = np.full(rgb.shape[:2] + (1,), 255, dtype=rgb.dtype)
            flat = np.concatenate([rgb, alpha], axis=-1).reshape(-1, 4)
        else:
            flat = np.repeat(arr.reshape(-1, 1), 4, axis=1)
            flat[:, 3] = 255
        unique, counts = np.unique(flat, axis=0, return_counts=True)
        return {",".join(str(int(v)) for v in row): int(c) for row, c in zip(unique, counts)}
    return {}


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


def _save_scene_artifacts(scene_name: str, rgb: Any, semantic: Any) -> Dict[str, Any]:
    artifacts = {
        "rgb_preview_path": None,
        "semantic_preview_path": None,
        "semantic_raw_path": None,
        "rgb_preview_saved": False,
        "semantic_preview_saved": False,
        "semantic_raw_saved": False,
    }
    if rgb is not None:
        path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_rgb.png".format(scene_name)))
        artifacts["rgb_preview_saved"] = _save_preview(path, rgb)
        artifacts["rgb_preview_path"] = path if artifacts["rgb_preview_saved"] else None
    if semantic is not None:
        raw_path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_semantic_raw.npy".format(scene_name)))
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        np.save(raw_path, np.asarray(semantic))
        artifacts["semantic_raw_path"] = raw_path
        artifacts["semantic_raw_saved"] = True
        preview_path = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "{0}_semantic_preview.png".format(scene_name)))
        artifacts["semantic_preview_saved"] = _save_preview(preview_path, semantic)
        artifacts["semantic_preview_path"] = preview_path if artifacts["semantic_preview_saved"] else None
    return artifacts


def _zero_action(agent_type: str) -> np.ndarray:
    if agent_type == "SurfaceVessel":
        return np.zeros(2, dtype=np.float32)
    if agent_type == "TorpedoAUV":
        return np.zeros(5, dtype=np.float32)
    if agent_type == "HoveringAUV":
        return np.zeros(8, dtype=np.float32)
    if agent_type in ("SphereAgent", "SphereRobot"):
        return np.zeros(2, dtype=np.float32)
    return np.zeros(2, dtype=np.float32)


def _run_scene(scene: Dict[str, Any]) -> Dict[str, Any]:
    import holoocean

    scene_name = str(scene["name"])
    tick_rows: List[Dict[str, Any]] = []
    first_rgb = None
    first_semantic = None
    first_range = None
    launch_ok = False
    error = ""
    started = time.perf_counter()
    try:
        with holoocean.make(scenario_cfg=_scenario_config(scene)) as env:
            launch_ok = True
            for tick in range(1, CAPTURE_TICKS + 1):
                env.act("sv0", _zero_action("SurfaceVessel"))
                if bool(scene.get("include_target", False)):
                    env.act("target", _zero_action(TARGET_AGENT_TYPE))
                if bool(scene.get("include_distractor", False)):
                    env.act("distractor", _zero_action(DISTRACTOR_AGENT_TYPE))
                state = env.tick()
                rgb = get_sensor_vector(state, "sv0", RGB_CAMERA_NAME)
                semantic = get_sensor_vector(state, "sv0", SEMANTIC_CAMERA_NAME)
                range_data = get_sensor_vector(state, "sv0", RANGEFINDER_NAME)
                if first_rgb is None and rgb is not None:
                    first_rgb = np.asarray(rgb).copy()
                if first_semantic is None and semantic is not None:
                    first_semantic = np.asarray(semantic).copy()
                if first_range is None and range_data is not None:
                    first_range = np.asarray(range_data).copy()
                rsum = _range_summary(range_data)
                tick_rows.append(
                    {
                        "scene": scene_name,
                        "tick": int(tick),
                        "rgb_present": rgb is not None,
                        "semantic_present": semantic is not None,
                        "rangefinder_present": range_data is not None,
                        "rangefinder_hit": bool(rsum["hit"]),
                        "rangefinder_min_positive_range_m": rsum["min_positive_range_m"],
                    }
                )
    except Exception as exc:
        error = "{0}: {1}".format(type(exc).__name__, exc)
        tick_rows.append({"scene": scene_name, "tick": 0, "scenario_error": error, "traceback": traceback.format_exc()})

    artifacts = _save_scene_artifacts(scene_name, first_rgb, first_semantic)
    semantic_colors = _semantic_colors(first_semantic)
    return {
        "scene": scene_name,
        "include_target": bool(scene.get("include_target", False)),
        "include_distractor": bool(scene.get("include_distractor", False)),
        "launch_ok": launch_ok,
        "error": error,
        "wall_time_s": float(time.perf_counter() - started),
        "rgb_stats": _array_stats(first_rgb),
        "semantic_stats": _array_stats(first_semantic),
        "rangefinder_summary": _range_summary(first_range),
        "semantic_colors": sorted([",".join(str(v) for v in color) for color in semantic_colors]),
        "semantic_color_counts": _color_counts(first_semantic),
        "first_rgb_raw": first_rgb,
        "first_semantic_raw": first_semantic,
        "artifacts": artifacts,
        "tick_rows": tick_rows,
    }


def _colors_from_scene(result: Dict[str, Any]) -> Set[str]:
    return set(str(v) for v in result.get("semantic_colors", []))


def _make_detection_events(scene_results: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    baseline = _colors_from_scene(scene_results.get("baseline", {}))
    target_only = _colors_from_scene(scene_results.get("target_only", {}))
    distractor_only = _colors_from_scene(scene_results.get("distractor_only", {}))

    target_signature = sorted(list(target_only - baseline))
    distractor_signature = sorted(list(distractor_only - baseline))
    target_vs_distractor_disjoint = bool(target_signature) and bool(distractor_signature) and set(target_signature).isdisjoint(set(distractor_signature))

    baseline_rgb = scene_results.get("baseline", {}).get("first_rgb_raw")
    for result in scene_results.values():
        result["rgb_diff_from_baseline"] = _rgb_diff_signature(result.get("first_rgb_raw"), baseline_rgb)

    target_rgb_colors = set(scene_results.get("target_only", {}).get("rgb_diff_from_baseline", {}).get("signature_colors", []))
    distractor_rgb_colors = set(scene_results.get("distractor_only", {}).get("rgb_diff_from_baseline", {}).get("signature_colors", []))
    rgb_target_signature = sorted(list(target_rgb_colors - distractor_rgb_colors))
    rgb_distractor_signature = sorted(list(distractor_rgb_colors - target_rgb_colors))
    rgb_target_distractor_disjoint = bool(rgb_target_signature) and bool(rgb_distractor_signature)

    events: List[Dict[str, Any]] = []
    for scene_name, result in scene_results.items():
        colors = _colors_from_scene(result)
        has_target_signature = bool(set(target_signature) & colors)
        has_distractor_signature = bool(set(distractor_signature) & colors)
        rgb_diff = result.get("rgb_diff_from_baseline", {})
        rgb_colors = set(str(v) for v in rgb_diff.get("signature_colors", []))
        rgb_target_overlap = sorted(list(set(rgb_target_signature) & rgb_colors))
        rgb_distractor_overlap = sorted(list(set(rgb_distractor_signature) & rgb_colors))
        rgb_has_target_signature = len(rgb_target_overlap) >= RGB_TARGET_OVERLAP_MIN
        rgb_has_distractor_signature = bool(rgb_distractor_overlap)
        expected_target_present = bool(result.get("include_target", False))
        range_summary = result.get("rangefinder_summary", {})
        event = {
            "scene": scene_name,
            "expected_target_present_for_audit": expected_target_present,
            "sensor_evidence": {
                "SemanticSegmentationCamera": {
                    "role": "semantic identity evidence if a target-specific signature exists",
                    "target_signature_colors": target_signature,
                    "distractor_signature_colors": distractor_signature,
                    "has_target_signature": has_target_signature,
                    "has_distractor_signature": has_distractor_signature,
                    "identity_supported": has_target_signature,
                },
                "RGBCamera": {
                    "role": "visual identity evidence through RGB difference signature",
                    "target_signature_colors": rgb_target_signature,
                    "distractor_signature_colors": rgb_distractor_signature,
                    "scene_signature_colors": sorted(list(rgb_colors)),
                    "target_signature_overlap": rgb_target_overlap,
                    "distractor_signature_overlap": rgb_distractor_overlap,
                    "changed_pixels": rgb_diff.get("changed_pixels"),
                    "change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
                    "identity_supported": rgb_has_target_signature,
                },
                "RangeFinderSensor": {
                    "role": "range/object-presence evidence only, not target identity",
                    "present": bool(range_summary.get("present", False)),
                    "hit": bool(range_summary.get("hit", False)),
                    "min_positive_range_m": range_summary.get("min_positive_range_m"),
                    "raw": range_summary.get("raw"),
                    "identity_supported": False,
                },
            },
            "rgb_artifact": result.get("artifacts", {}).get("rgb_preview_path"),
            "semantic_artifact": result.get("artifacts", {}).get("semantic_preview_path"),
            "detection_event_source": "SemanticSegmentationCamera signature, RGBCamera signature, and RangeFinderSensor range evidence",
            "identity_decision_source": "RGBCamera" if rgb_has_target_signature else ("SemanticSegmentationCamera" if has_target_signature else "none"),
            "truth_used_for_detection": False,
        }
        event["semantic_target_signature_colors"] = target_signature
        event["semantic_distractor_signature_colors"] = distractor_signature
        event["semantic_has_target_signature"] = has_target_signature
        event["semantic_has_distractor_signature"] = has_distractor_signature
        event["rgb_target_signature_colors"] = rgb_target_signature
        event["rgb_distractor_signature_colors"] = rgb_distractor_signature
        event["rgb_has_target_signature"] = rgb_has_target_signature
        event["rgb_has_distractor_signature"] = rgb_has_distractor_signature
        event["rangefinder_present"] = bool(range_summary.get("present", False))
        event["rangefinder_hit"] = bool(range_summary.get("hit", False))
        event["rangefinder_min_positive_range_m"] = range_summary.get("min_positive_range_m")
        event["sensor_detected_target"] = bool(has_target_signature or rgb_has_target_signature)
        event["target_detection_correct_for_scene"] = bool(event["sensor_detected_target"] == expected_target_present)
        events.append(event)

    object_scene_names = ("target_only", "distractor_only", "target_and_distractor")
    baseline_range_hit = bool(scene_results.get("baseline", {}).get("rangefinder_summary", {}).get("hit", False))
    object_range_hits = [
        bool(scene_results.get(name, {}).get("rangefinder_summary", {}).get("hit", False))
        for name in object_scene_names
    ]
    conclusion = {
        "target_signature_colors": target_signature,
        "distractor_signature_colors": distractor_signature,
        "target_signature_present": bool(target_signature),
        "distractor_signature_present": bool(distractor_signature),
        "target_vs_distractor_semantic_disjoint": target_vs_distractor_disjoint,
        "semantic_identity_supported": target_vs_distractor_disjoint,
        "rgb_target_signature_colors": rgb_target_signature,
        "rgb_distractor_signature_colors": rgb_distractor_signature,
        "rgb_target_signature_present": bool(rgb_target_signature),
        "rgb_distractor_signature_present": bool(rgb_distractor_signature),
        "rgb_target_vs_distractor_disjoint": rgb_target_distractor_disjoint,
        "rgb_can_distinguish_target_from_distractor": bool(rgb_target_distractor_disjoint),
        "rangefinder_baseline_hit": baseline_range_hit,
        "rangefinder_object_scene_hits": object_range_hits,
        "rangefinder_object_presence_supported": bool((not baseline_range_hit) and any(object_range_hits)),
        "all_scene_launch_ok": all(bool(r.get("launch_ok", False)) for r in scene_results.values()),
        "all_scenes_rgb_output": all(bool(r.get("rgb_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_semantic_output": all(bool(r.get("semantic_stats", {}).get("present", False)) for r in scene_results.values()),
        "all_scenes_rangefinder_output": all(bool(r.get("rangefinder_summary", {}).get("present", False)) for r in scene_results.values()),
        "all_detection_events_correct": all(bool(e["target_detection_correct_for_scene"]) for e in events),
    }
    conclusion["semantic_can_distinguish_target_from_distractor"] = bool(
        conclusion["all_scene_launch_ok"]
        and conclusion["all_scenes_semantic_output"]
        and conclusion["target_signature_present"]
        and conclusion["distractor_signature_present"]
        and conclusion["target_vs_distractor_semantic_disjoint"]
        and conclusion["all_detection_events_correct"]
    )
    conclusion["rangefinder_available_as_range_evidence"] = bool(conclusion["all_scenes_rangefinder_output"])
    conclusion["rgb_available_as_visual_evidence"] = bool(conclusion["all_scenes_rgb_output"])
    conclusion["composite_sensor_detection_supported"] = bool(
        conclusion["all_scene_launch_ok"]
        and conclusion["rgb_available_as_visual_evidence"]
        and conclusion["rangefinder_available_as_range_evidence"]
        and conclusion["rgb_can_distinguish_target_from_distractor"]
        and conclusion["rangefinder_object_presence_supported"]
        and conclusion["all_detection_events_correct"]
    )
    return events, conclusion


def _build_summary_md(conclusion: Dict[str, Any]) -> str:
    return """# Phase 5C-4A-1 Semantic/RGB/RangeFinder Target-Distractor Summary

## Status
- Probe Completed: `{probe_completed}`
- Semantic Can Distinguish Target From Distractor: `{semantic_can_distinguish}`
- RGB Can Distinguish Target From Distractor: `{rgb_can_distinguish}`
- RangeFinder Object Presence Supported: `{rangefinder_presence}`
- Composite Sensor Detection Supported: `{composite_supported}`
- RGB Available As Visual Evidence: `{rgb_available}`
- RangeFinder Available As Range Evidence: `{rangefinder_available}`
- All Detection Events Correct: `{events_correct}`

## Signature
- Semantic Target Signature Colors: `{target_signature}`
- Semantic Distractor Signature Colors: `{distractor_signature}`
- Semantic Target/Distractor Disjoint: `{disjoint}`
- RGB Target Signature Colors: `{rgb_target_signature}`
- RGB Distractor Signature Colors: `{rgb_distractor_signature}`
- RGB Target/Distractor Disjoint: `{rgb_disjoint}`

## Notes
- Runtime search is not imported.
- Search decision algorithms remain frozen.
- SemanticSegmentationCamera is recorded as identity evidence only if it produces a target-specific signature.
- RGBCamera provides visual identity evidence through an audited RGB difference signature.
- RangeFinderSensor is range evidence only, not target identity.
- Sonar is disabled.
""".format(
        probe_completed=conclusion.get("probe_completed"),
        semantic_can_distinguish=conclusion.get("semantic_can_distinguish_target_from_distractor"),
        rgb_can_distinguish=conclusion.get("rgb_can_distinguish_target_from_distractor"),
        rangefinder_presence=conclusion.get("rangefinder_object_presence_supported"),
        composite_supported=conclusion.get("composite_sensor_detection_supported"),
        rgb_available=conclusion.get("rgb_available_as_visual_evidence"),
        rangefinder_available=conclusion.get("rangefinder_available_as_range_evidence"),
        events_correct=conclusion.get("all_detection_events_correct"),
        target_signature=conclusion.get("target_signature_colors"),
        distractor_signature=conclusion.get("distractor_signature_colors"),
        disjoint=conclusion.get("target_vs_distractor_semantic_disjoint"),
        rgb_target_signature=conclusion.get("rgb_target_signature_colors"),
        rgb_distractor_signature=conclusion.get("rgb_distractor_signature_colors"),
        rgb_disjoint=conclusion.get("rgb_target_vs_distractor_disjoint"),
    )


def run_probe() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    config = _phase_config()
    raw_scene_result_list: List[Dict[str, Any]] = []
    tick_trace: List[Dict[str, Any]] = []
    for scene in SCENES:
        result = _run_scene(scene)
        raw_scene_result_list.append(result)
        tick_trace.extend(result["tick_rows"])

    scene_results = {str(r["scene"]): r for r in raw_scene_result_list}
    detection_events, perception_conclusion = _make_detection_events(scene_results)
    scene_result_list: List[Dict[str, Any]] = []
    for result in raw_scene_result_list:
        scene_result_list.append(
            {
                k: v
                for k, v in result.items()
                if k not in ("tick_rows", "first_rgb_raw", "first_semantic_raw")
            }
        )
    conclusion = dict(perception_conclusion)
    conclusion.update(
        {
            "phase_name": PHASE_NAME,
            "probe_completed": True,
            "wall_time_s": float(time.perf_counter() - started),
            "truth_used_for_detection": False,
            "runtime_imported": False,
            "sonar_used": False,
        }
    )

    _save_json(CONFIG_JSON, config)
    _save_json(SCENE_RESULTS_JSON, scene_result_list)
    _save_json(DETECTION_EVENTS_JSON, detection_events)
    _save_json(TICK_TRACE_JSON, tick_trace)
    _save_csv(TICK_TRACE_CSV, tick_trace)
    _save_json(CONCLUSION_JSON, conclusion)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(conclusion))
    print("Summary saved to: {0}".format(SUMMARY_MD))

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
        "scene_results": scene_result_list,
        "detection_events": detection_events,
        "conclusion": conclusion,
        "git_status": git_status,
    }


def main() -> None:
    print("=== Phase 5C-4A-1: Semantic/RGB/RangeFinder target-distractor probe ===")
    result = run_probe()
    conclusion = result["conclusion"]
    print(
        "Phase 5C-4A-1 finished: semantic_distinguish={0}, rgb={1}, rangefinder={2}, events_correct={3}".format(
            conclusion["semantic_can_distinguish_target_from_distractor"],
            conclusion["rgb_can_distinguish_target_from_distractor"],
            conclusion["rangefinder_object_presence_supported"],
            conclusion["all_detection_events_correct"],
        )
    )


if __name__ == "__main__":
    main()
