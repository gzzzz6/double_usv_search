"""Phase 5C-4A-0: SemanticSegmentationCamera availability probe.

This probe only checks whether HoloOcean's SemanticSegmentationCamera can be
created, read, summarized, and saved on the local machine. It does not run the
search runtime and does not perform target detection.
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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid  # noqa: E402
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4a0_semantic_camera_availability_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_config.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_tick_trace.csv"))
SENSOR_STATS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_sensor_stats.json"))
CONCLUSION_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_conclusion.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "semantic_camera_availability_summary.md"))

REFERENCE_RGB_PNG = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "reference_rgb_first_valid.png"))
SEMANTIC_PREVIEW_PNG = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "semantic_first_valid_preview.png"))
SEMANTIC_RAW_NPY = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "semantic_first_valid_raw.npy"))

START_CELL = (40, 40)
CAPTURE_TICKS = 30
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_HZ = 5
RGB_CAMERA_NAME = "ReferenceRGBCamera"
SEMANTIC_CAMERA_NAME = "FrontSemanticSegmentationCamera"


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


def _memory_mb() -> Optional[float]:
    try:
        import psutil  # type: ignore

        process = psutil.Process(os.getpid())
        return float(process.memory_info().rss / (1024.0 * 1024.0))
    except Exception:
        return None


def _phase_config() -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "purpose": "SemanticSegmentationCamera availability probe",
        "map_npz": MAP_NPZ,
        "map_height_cells": 81,
        "map_width_cells": 81,
        "resolution_m": 10.0,
        "start_cell": list(START_CELL),
        "capture_ticks": CAPTURE_TICKS,
        "holo_world": "OpenWater",
        "holo_package": "Ocean",
        "main_agent": "sv0",
        "agent_name": "sv0",
        "agent_type": "SurfaceVessel",
        "control_scheme": 0,
        "rgb_camera_name": RGB_CAMERA_NAME,
        "semantic_camera_name": SEMANTIC_CAMERA_NAME,
        "camera_width": CAMERA_WIDTH,
        "camera_height": CAMERA_HEIGHT,
        "camera_hz": CAMERA_HZ,
        "semantic_camera_used_for_detection": False,
        "sonar_used": False,
        "target_agent_used": False,
        "obstacle_used": False,
        "runtime_imported": False,
        "official_doc": "https://byu-holoocean.github.io/holoocean-docs/v2.2.2/holoocean/sensors.html",
    }


def _camera_sensor(sensor_type: str, sensor_name: str) -> Dict[str, Any]:
    return {
        "sensor_type": sensor_type,
        "sensor_name": sensor_name,
        "location": [0.0, 0.0, 4.0],
        "rotation": [0.0, 0.0, 0.0],
        "Hz": CAMERA_HZ,
        "configuration": {
            "CaptureWidth": CAMERA_WIDTH,
            "CaptureHeight": CAMERA_HEIGHT,
        },
    }


def _scenario_config(spec: Dict[str, Any], start_world: List[float], include_semantic: bool, name_suffix: str) -> Dict[str, Any]:
    sensors: List[Dict[str, Any]] = [
        {"sensor_type": "LocationSensor", "socket": "COM"},
        {"sensor_type": "GPSSensor", "socket": "COM"},
        {"sensor_type": "OrientationSensor", "socket": "COM"},
        _camera_sensor("RGBCamera", RGB_CAMERA_NAME),
    ]
    if include_semantic:
        sensors.append(_camera_sensor("SemanticSegmentationCamera", SEMANTIC_CAMERA_NAME))

    return {
        "name": "semantic_camera_availability_{0}".format(name_suffix),
        "world": spec["world"],
        "package_name": spec["package_name"],
        "main_agent": "sv0",
        "agents": [
            {
                "agent_name": "sv0",
                "agent_type": "SurfaceVessel",
                "sensors": sensors,
                "control_scheme": 0,
                "location": start_world,
                "rotation": [0.0, 0.0, 0.0],
            }
        ],
    }


def _sensor_stats(value: Any) -> Dict[str, Any]:
    if value is None:
        return {
            "present": False,
            "shape": None,
            "dtype": None,
            "size": 0,
            "min": None,
            "max": None,
            "unique_count": None,
            "finite_ratio": None,
        }
    arr = np.asarray(value)
    stats: Dict[str, Any] = {
        "present": True,
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size": int(arr.size),
        "min": None,
        "max": None,
        "unique_count": None,
        "finite_ratio": None,
    }
    if arr.size > 0:
        try:
            numeric = arr.astype(float, copy=False)
            finite = np.isfinite(numeric)
            stats["finite_ratio"] = float(np.mean(finite))
            if np.any(finite):
                stats["min"] = float(np.nanmin(numeric))
                stats["max"] = float(np.nanmax(numeric))
            stats["unique_count"] = int(len(np.unique(arr)))
        except Exception as exc:
            stats["stats_error"] = str(exc)
    return stats


def _array_for_preview(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim == 2:
        numeric = arr.astype(float)
        lo = float(np.nanmin(numeric)) if numeric.size else 0.0
        hi = float(np.nanmax(numeric)) if numeric.size else 1.0
        if math.isclose(lo, hi):
            return np.zeros_like(numeric, dtype=np.uint8)
        return np.clip((numeric - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)
    if arr.ndim >= 3:
        img = arr
        if img.shape[-1] >= 3:
            img = img[..., :3]
        if np.issubdtype(img.dtype, np.floating):
            max_value = float(np.nanmax(img)) if img.size else 1.0
            if max_value <= 1.0:
                img = img * 255.0
        return np.clip(img, 0, 255).astype(np.uint8)
    numeric = arr.astype(float)
    return np.clip(numeric, 0, 255).astype(np.uint8)


def _save_preview_png(path: str, value: Any) -> bool:
    try:
        import matplotlib.pyplot as plt

        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = _array_for_preview(value)
        plt.figure(figsize=(6, 4))
        if img.ndim == 2:
            plt.imshow(img, cmap="viridis")
        else:
            plt.imshow(img)
        plt.axis("off")
        plt.savefig(path, dpi=120, bbox_inches="tight", pad_inches=0)
        plt.close()
        print("Preview saved to: {0}".format(path))
        return True
    except Exception as exc:
        print("[WARN] Could not save preview {0}: {1}".format(path, exc))
        return False


def _run_scenario(
    scenario_cfg: Dict[str, Any],
    include_semantic: bool,
    capture_ticks: int,
) -> Tuple[bool, Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    import holoocean

    tick_trace: List[Dict[str, Any]] = []
    first_rgb = None
    first_semantic = None
    launch_ok = False
    scenario_error = ""
    started = time.perf_counter()

    try:
        with holoocean.make(scenario_cfg=scenario_cfg) as env:
            launch_ok = True
            state = {}
            for tick in range(1, capture_ticks + 1):
                env.act("sv0", np.zeros(2, dtype=np.float32))
                state = env.tick()
                loc = get_sensor_vector(state, "sv0", "LocationSensor")
                gps = get_sensor_vector(state, "sv0", "GPSSensor")
                orient = get_sensor_vector(state, "sv0", "OrientationSensor")
                rgb = get_sensor_vector(state, "sv0", RGB_CAMERA_NAME)
                semantic = get_sensor_vector(state, "sv0", SEMANTIC_CAMERA_NAME) if include_semantic else None
                if first_rgb is None and rgb is not None:
                    first_rgb = np.asarray(rgb).copy()
                if include_semantic and first_semantic is None and semantic is not None:
                    first_semantic = np.asarray(semantic).copy()

                rgb_stats = _sensor_stats(rgb)
                semantic_stats = _sensor_stats(semantic)
                tick_trace.append(
                    {
                        "scenario_includes_semantic": bool(include_semantic),
                        "tick": int(tick),
                        "state_top_keys": sorted([str(k) for k in state.keys()]),
                        "sv0_sensor_keys": sorted([str(k) for k in state.get("sv0", {}).keys()]) if isinstance(state.get("sv0"), dict) else [],
                        "location_present": loc is not None,
                        "gps_present": gps is not None,
                        "orientation_present": orient is not None,
                        "rgb_present": bool(rgb_stats["present"]),
                        "rgb_shape": rgb_stats["shape"],
                        "rgb_dtype": rgb_stats["dtype"],
                        "rgb_size": rgb_stats["size"],
                        "semantic_present": bool(semantic_stats["present"]),
                        "semantic_shape": semantic_stats["shape"],
                        "semantic_dtype": semantic_stats["dtype"],
                        "semantic_size": semantic_stats["size"],
                        "semantic_min": semantic_stats["min"],
                        "semantic_max": semantic_stats["max"],
                        "semantic_unique_count": semantic_stats["unique_count"],
                        "semantic_finite_ratio": semantic_stats["finite_ratio"],
                    }
                )
    except Exception as exc:
        scenario_error = "{0}: {1}".format(type(exc).__name__, exc)
        tick_trace.append(
            {
                "scenario_includes_semantic": bool(include_semantic),
                "tick": 0,
                "scenario_error": scenario_error,
                "traceback": traceback.format_exc(),
            }
        )

    sensor_stats = {
        "scenario_launch_ok": bool(launch_ok),
        "scenario_error": scenario_error,
        "capture_ticks_requested": int(capture_ticks),
        "capture_ticks_recorded": int(len([row for row in tick_trace if int(row.get("tick", 0)) > 0])),
        "rgb_output_seen": first_rgb is not None,
        "semantic_output_seen": first_semantic is not None,
        "first_rgb_stats": _sensor_stats(first_rgb),
        "first_semantic_stats": _sensor_stats(first_semantic),
        "wall_time_s": float(time.perf_counter() - started),
    }
    artifacts = {
        "first_rgb": first_rgb,
        "first_semantic": first_semantic,
    }
    return bool(launch_ok), sensor_stats, tick_trace, artifacts


def _build_summary_md(conclusion: Dict[str, Any]) -> str:
    return """# Phase 5C-4A-0 Semantic Camera Availability Summary

## Status
- Probe Completed: `{probe_completed}`
- Availability Conclusion: `{availability_conclusion}`
- Semantic Camera Available: `{semantic_camera_available}`
- Semantic Scenario Launch OK: `{semantic_scenario_launch_ok}`
- Control RGB Scenario OK: `{control_rgb_scenario_ok}`
- Semantic Output Seen: `{semantic_output_seen}`
- RGB Output Seen: `{rgb_output_seen}`

## Notes
- This phase does not run runtime search.
- This phase does not create target agents or obstacles.
- Semantic camera output is not used for target detection.
- Sonar is disabled.

## Error
```text
{error}
```
""".format(
        probe_completed=conclusion.get("probe_completed"),
        availability_conclusion=conclusion.get("availability_conclusion"),
        semantic_camera_available=conclusion.get("semantic_camera_available"),
        semantic_scenario_launch_ok=conclusion.get("semantic_scenario_launch_ok"),
        control_rgb_scenario_ok=conclusion.get("control_rgb_scenario_ok"),
        semantic_output_seen=conclusion.get("semantic_output_seen"),
        rgb_output_seen=conclusion.get("rgb_output_seen"),
        error=conclusion.get("semantic_error") or conclusion.get("control_error") or "",
    )


def run_probe() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    config = _phase_config()
    nav_map, spec = load_scene_map_npz(MAP_NPZ)
    adapter_config = scene_map_config_from_spec(spec)
    start_world = list(grid_to_world(START_CELL, config=adapter_config))
    roundtrip = world_to_grid(start_world, config=adapter_config, map_shape=nav_map.shape)
    if tuple(int(v) for v in roundtrip) != START_CELL:
        raise AssertionError("Start roundtrip mismatch: {0} != {1}".format(roundtrip, START_CELL))
    config["start_world"] = [float(v) for v in start_world]
    config["start_roundtrip"] = [int(v) for v in roundtrip]

    memory_before = _memory_mb()
    semantic_scenario = _scenario_config(spec, [float(v) for v in start_world], include_semantic=True, name_suffix="semantic")
    semantic_launch_ok, semantic_stats, semantic_tick_trace, semantic_artifacts = _run_scenario(
        semantic_scenario,
        include_semantic=True,
        capture_ticks=CAPTURE_TICKS,
    )

    control_stats: Dict[str, Any] = {}
    control_tick_trace: List[Dict[str, Any]] = []
    control_artifacts: Dict[str, Any] = {"first_rgb": None, "first_semantic": None}
    control_launch_ok = None
    if not semantic_launch_ok:
        control_scenario = _scenario_config(spec, [float(v) for v in start_world], include_semantic=False, name_suffix="rgb_control")
        control_launch_ok_bool, control_stats, control_tick_trace, control_artifacts = _run_scenario(
            control_scenario,
            include_semantic=False,
            capture_ticks=CAPTURE_TICKS,
        )
        control_launch_ok = bool(control_launch_ok_bool)

    first_rgb = semantic_artifacts.get("first_rgb")
    if first_rgb is None:
        first_rgb = control_artifacts.get("first_rgb")
    first_semantic = semantic_artifacts.get("first_semantic")

    rgb_preview_saved = False
    semantic_preview_saved = False
    semantic_raw_saved = False
    if first_rgb is not None:
        rgb_preview_saved = _save_preview_png(REFERENCE_RGB_PNG, first_rgb)
    if first_semantic is not None:
        os.makedirs(os.path.dirname(SEMANTIC_RAW_NPY), exist_ok=True)
        np.save(SEMANTIC_RAW_NPY, np.asarray(first_semantic))
        semantic_raw_saved = True
        print("Semantic raw saved to: {0}".format(SEMANTIC_RAW_NPY))
        semantic_preview_saved = _save_preview_png(SEMANTIC_PREVIEW_PNG, first_semantic)

    semantic_camera_available = bool(
        semantic_launch_ok
        and semantic_stats.get("semantic_output_seen", False)
        and semantic_stats.get("first_semantic_stats", {}).get("size", 0) > 0
    )
    if semantic_camera_available:
        availability_conclusion = "available"
    elif semantic_launch_ok:
        availability_conclusion = "semantic_launch_ok_but_no_output"
    elif control_launch_ok is True:
        availability_conclusion = "semantic_unavailable_rgb_control_ok"
    elif control_launch_ok is False:
        availability_conclusion = "semantic_and_rgb_control_failed"
    else:
        availability_conclusion = "semantic_launch_failed_no_control_result"

    memory_after = _memory_mb()
    conclusion = {
        "phase_name": PHASE_NAME,
        "probe_completed": True,
        "availability_conclusion": availability_conclusion,
        "semantic_camera_available": semantic_camera_available,
        "semantic_scenario_launch_ok": bool(semantic_launch_ok),
        "semantic_output_seen": bool(semantic_stats.get("semantic_output_seen", False)),
        "semantic_error": semantic_stats.get("scenario_error", ""),
        "control_rgb_scenario_ok": control_launch_ok,
        "control_rgb_output_seen": bool(control_stats.get("rgb_output_seen", False)) if control_stats else None,
        "control_error": control_stats.get("scenario_error", "") if control_stats else "",
        "rgb_output_seen": first_rgb is not None,
        "rgb_preview_saved": rgb_preview_saved,
        "semantic_preview_saved": semantic_preview_saved,
        "semantic_raw_saved": semantic_raw_saved,
        "semantic_raw_path": SEMANTIC_RAW_NPY if semantic_raw_saved else None,
        "semantic_preview_path": SEMANTIC_PREVIEW_PNG if semantic_preview_saved else None,
        "rgb_preview_path": REFERENCE_RGB_PNG if rgb_preview_saved else None,
        "semantic_first_stats": semantic_stats.get("first_semantic_stats", {}),
        "rgb_first_stats": semantic_stats.get("first_rgb_stats", {}) if semantic_stats.get("rgb_output_seen") else control_stats.get("first_rgb_stats", {}),
        "wall_time_s": float(time.perf_counter() - started),
        "memory_before_mb": memory_before,
        "memory_after_mb": memory_after,
        "memory_delta_mb": None if memory_before is None or memory_after is None else float(memory_after - memory_before),
    }

    all_tick_trace = semantic_tick_trace + control_tick_trace
    sensor_stats = {
        "semantic_scenario": semantic_stats,
        "control_rgb_scenario": control_stats,
        "semantic_scenario_tick_count": len(semantic_tick_trace),
        "control_rgb_scenario_tick_count": len(control_tick_trace),
        "first_rgb_artifact": REFERENCE_RGB_PNG if rgb_preview_saved else None,
        "first_semantic_raw_artifact": SEMANTIC_RAW_NPY if semantic_raw_saved else None,
        "first_semantic_preview_artifact": SEMANTIC_PREVIEW_PNG if semantic_preview_saved else None,
    }

    _save_json(CONFIG_JSON, config)
    _save_json(TICK_TRACE_JSON, all_tick_trace)
    _save_csv(TICK_TRACE_CSV, all_tick_trace)
    _save_json(SENSOR_STATS_JSON, sensor_stats)
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
        "tick_trace": all_tick_trace,
        "sensor_stats": sensor_stats,
        "conclusion": conclusion,
        "git_status": git_status,
    }


def main() -> None:
    print("=== Phase 5C-4A-0: SemanticSegmentationCamera availability probe ===")
    result = run_probe()
    conclusion = result["conclusion"]
    print(
        "Phase 5C-4A-0 finished: conclusion={0}, semantic_available={1}, semantic_launch_ok={2}, control_rgb_ok={3}".format(
            conclusion["availability_conclusion"],
            conclusion["semantic_camera_available"],
            conclusion["semantic_scenario_launch_ok"],
            conclusion["control_rgb_scenario_ok"],
        )
    )


if __name__ == "__main__":
    main()
