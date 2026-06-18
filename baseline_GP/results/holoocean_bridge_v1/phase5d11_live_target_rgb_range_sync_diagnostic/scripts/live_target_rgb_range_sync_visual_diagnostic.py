"""Phase 5D-11 visual diagnostic for live target RGB/RangeFinder sync.

This diagnostic does not change baseline_GP planner/runtime code.  It replays a
small set of Phase 5D-10 target-failure observer poses as static HoloOcean
capture cases, saves RGB/diff/overlay evidence, and evaluates the existing
sphere_blob_local_range_scaled_any_hit rule.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d11_live_target_rgb_range_sync_diagnostic"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SOURCE_5D10_PHASE_NAME = "phase5d10_live_planner_standoff_viewpoint_search"
SOURCE_5D10_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D10_PHASE_NAME))
SOURCE_5D10_PROBE = os.path.join(SOURCE_5D10_DIR, "scripts", "live_planner_standoff_viewpoint_search_probe.py")
SOURCE_5D10_EVENTS_CSV = os.path.join(SOURCE_5D10_DIR, "manifests", "phase5d10_live_per_agent_detection_events.csv")
SOURCE_5D10_SUMMARY_JSON = os.path.join(SOURCE_5D10_DIR, "manifests", "phase5d10_summary.json")
SOURCE_5D10_AUDIT_JSON = os.path.join(SOURCE_5D10_DIR, "manifests", "phase5d10_audit.json")

DIAG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_diagnostic.json")
DIAG_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_diagnostic.csv")
PER_TICK_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_per_tick.csv")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d11_rgb_range_sync_diagnostic.md")

CAPTURE_TICKS = 16
RECOMMENDED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"


def _load_module(path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load module from {0}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5D10 = _load_module(SOURCE_5D10_PROBE, "phase5d11_p5d10_probe_source")
P5D1A = P5D10.P5D3.P5D1A


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


def _flatten(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set, np.ndarray)):
        return json.dumps(_json_safe(value), sort_keys=True)
    return _json_safe(value)


def _save_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    keys: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten(row.get(key)) for key in keys})
    print("CSV saved to: {0}".format(path))


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(name))


def _parse_list(value: Any) -> Optional[List[Any]]:
    if isinstance(value, list):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = ast.literal_eval(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, list) else None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except Exception:
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _rgb_image(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim >= 3:
        img = arr[..., :3]
        if np.issubdtype(img.dtype, np.floating) and float(np.nanmax(img)) <= 1.0:
            img = img * 255.0
        return np.clip(img, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        finite = np.nan_to_num(arr.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
        maxv = float(np.max(finite)) if finite.size else 0.0
        if maxv > 0.0:
            finite = finite / maxv * 255.0
        return np.clip(finite, 0, 255).astype(np.uint8)
    return np.zeros((16, 16, 3), dtype=np.uint8)


def _save_image(path: str, value: Any) -> Optional[str]:
    try:
        from PIL import Image

        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(_rgb_image(value)).save(path)
        return path
    except Exception as exc:
        print("[WARN] image save failed for {0}: {1}".format(path, exc))
        return None


def _diff_image(rgb_value: Any, baseline_value: Any) -> Optional[np.ndarray]:
    if rgb_value is None or baseline_value is None:
        return None
    rgb = np.asarray(rgb_value)[..., :3].astype(np.int16)
    baseline = np.asarray(baseline_value)[..., :3].astype(np.int16)
    if rgb.shape[:2] != baseline.shape[:2]:
        return None
    diff = np.max(np.abs(rgb - baseline), axis=-1)
    return np.clip(diff * 4, 0, 255).astype(np.uint8)


def _white_neutral_mask_image(rgb_value: Any, baseline_value: Any) -> Optional[np.ndarray]:
    if rgb_value is None or baseline_value is None:
        return None
    rgb = np.asarray(rgb_value)[..., :3].astype(np.int16)
    baseline = np.asarray(baseline_value)[..., :3].astype(np.int16)
    if rgb.shape[:2] != baseline.shape[:2]:
        return None
    diff = np.max(np.abs(rgb - baseline), axis=-1)
    height, width = diff.shape[:2]
    roi = np.zeros_like(diff, dtype=bool)
    roi[int(height * 0.18) : int(height * 0.82), int(width * 0.08) : int(width * 0.92)] = True
    max_channel = np.max(rgb, axis=-1)
    min_channel = np.min(rgb, axis=-1)
    mask = (
        (diff >= float(P5D1A.SPHERE_BLOB_DIFF_THRESHOLD))
        & (max_channel >= int(P5D1A.SPHERE_BLOB_MIN_RGB))
        & ((max_channel - min_channel) <= int(P5D1A.SPHERE_BLOB_NEUTRAL_TOLERANCE))
        & roi
    )
    return np.where(mask, 255, 0).astype(np.uint8)


def _overlay_image(
    *,
    rgb_value: Any,
    sphere_blob: Dict[str, Any],
    local_blob: Dict[str, Any],
    range_summary: Dict[str, Any],
) -> Optional[np.ndarray]:
    try:
        from PIL import Image, ImageDraw

        img = Image.fromarray(_rgb_image(rgb_value)).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        roi = [int(width * 0.08), int(height * 0.18), int(width * 0.92), int(height * 0.82)]
        draw.rectangle(roi, outline=(80, 160, 255), width=1)
        for blob in sphere_blob.get("local_candidate_blobs", []) or []:
            x = int(blob.get("x", 0))
            y = int(blob.get("y", 0))
            w = int(blob.get("w", 0))
            h = int(blob.get("h", 0))
            draw.rectangle([x, y, x + w, y + h], outline=(255, 220, 0), width=2)
        best = local_blob.get("local_range_scaled_best_blob")
        if isinstance(best, dict):
            x = int(best.get("x", 0))
            y = int(best.get("y", 0))
            w = int(best.get("w", 0))
            h = int(best.get("h", 0))
            color = (0, 255, 0) if local_blob.get("local_range_scaled_blob_present") else (255, 80, 0)
            draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        for index in range(len(P5D10.BRIDGE_FAN_YAW_DEGREES)):
            yaw = float(P5D10.BRIDGE_FAN_YAW_DEGREES[index])
            x = int(width * (0.5 - yaw / 70.0))
            color = (255, 60, 60) if index in set(range_summary.get("hit_beam_indices") or []) else (80, 80, 80)
            draw.line([x, height - 1, x, int(height * 0.86)], fill=color, width=1)
        return np.asarray(img)
    except Exception as exc:
        print("[WARN] overlay failed: {0}".format(exc))
        return None


def _mask_diagnostics(rgb_value: Any, baseline_value: Any) -> Dict[str, Any]:
    if rgb_value is None or baseline_value is None:
        return {}
    rgb = np.asarray(rgb_value)
    baseline = np.asarray(baseline_value)
    if rgb.ndim < 3 or baseline.ndim < 3 or rgb.shape[:2] != baseline.shape[:2]:
        return {"mask_error": "rgb/baseline shape mismatch"}
    rgb3 = rgb[..., :3].astype(np.int16)
    baseline3 = baseline[..., :3].astype(np.int16)
    diff = np.max(np.abs(rgb3 - baseline3), axis=-1)
    height, width = diff.shape[:2]
    y0 = int(height * 0.18)
    y1 = int(height * 0.82)
    x0 = int(width * 0.08)
    x1 = int(width * 0.92)
    roi = np.zeros_like(diff, dtype=bool)
    roi[y0:y1, x0:x1] = True
    max_channel = np.max(rgb3, axis=-1)
    min_channel = np.min(rgb3, axis=-1)
    diff_mask = (diff >= float(P5D1A.SPHERE_BLOB_DIFF_THRESHOLD)) & roi
    bright_mask = (max_channel >= int(P5D1A.SPHERE_BLOB_MIN_RGB)) & roi
    neutral_mask = ((max_channel - min_channel) <= int(P5D1A.SPHERE_BLOB_NEUTRAL_TOLERANCE)) & roi
    white_neutral_mask = diff_mask & bright_mask & neutral_mask
    return {
        "roi_xyxy": [x0, y0, x1, y1],
        "diff_ge_threshold_roi_pixels": int(np.count_nonzero(diff_mask)),
        "bright_roi_pixels": int(np.count_nonzero(bright_mask)),
        "neutral_roi_pixels": int(np.count_nonzero(neutral_mask)),
        "diff_and_bright_roi_pixels": int(np.count_nonzero(diff_mask & bright_mask)),
        "diff_and_neutral_roi_pixels": int(np.count_nonzero(diff_mask & neutral_mask)),
        "white_neutral_mask_pixels": int(np.count_nonzero(white_neutral_mask)),
        "max_diff_roi": float(np.max(diff[roi])) if np.count_nonzero(roi) else None,
    }


def _surface_vessel_agent(*, location: List[float], heading_deg: float) -> Dict[str, Any]:
    return {
        "agent_name": "sv0",
        "agent_type": P5D10.TEAMMATE_AGENT_TYPE,
        "sensors": [
            {"sensor_type": "LocationSensor", "socket": "COM"},
            {"sensor_type": "GPSSensor", "socket": "COM"},
            {"sensor_type": "OrientationSensor", "socket": "COM"},
            P5D10.P5D3._camera_sensor(),
        ]
        + P5D10._bridge_fan_rangefinder_sensors(),
        "control_scheme": 0,
        "location": [float(v) for v in location],
        "rotation": [0.0, 0.0, float(heading_deg)],
    }


def _scenario_config(case: Dict[str, Any], include_target: bool) -> Dict[str, Any]:
    agents = [
        _surface_vessel_agent(
            location=list(case["observer_world_location"]),
            heading_deg=float(case["observer_heading_deg"]),
        )
    ]
    if include_target:
        agents.append(
            {
                "agent_name": "target",
                "agent_type": P5D10.TARGET_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": P5D10.P5D3._control_scheme(P5D10.TARGET_AGENT_TYPE),
                "location": [float(v) for v in case["target_world_location"]],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    return {
        "name": "phase5d11_{0}_{1}".format(_safe_name(case["case_name"]), "target" if include_target else "baseline"),
        "world": "OpenWater",
        "package_name": "Ocean",
        "main_agent": "sv0",
        "agents": agents,
    }


def _zero_action(agent_type: str, control_scheme: int) -> np.ndarray:
    del control_scheme
    return P5D1A._zero_action(agent_type)


def _aggregate_fan_range(state: Dict[str, Any]) -> List[float]:
    values: List[float] = []
    for name in P5D10._fan_rangefinder_names():
        value = get_sensor_vector(state, "sv0", name)
        if value is None:
            values.append(-1.0)
            continue
        arr = np.asarray(value).astype(float).reshape(-1)
        values.append(float(arr[0]) if arr.size else -1.0)
    return values


def _capture_case(case: Dict[str, Any], include_target: bool) -> Dict[str, Any]:
    import holoocean

    tick_rows: List[Dict[str, Any]] = []
    rgb_by_tick: Dict[int, np.ndarray] = {}
    fan_by_tick: Dict[int, np.ndarray] = {}
    launch_ok = False
    error = ""
    started = time.perf_counter()
    try:
        with holoocean.make(scenario_cfg=_scenario_config(case, include_target)) as env:
            launch_ok = True
            for tick in range(1, CAPTURE_TICKS + 1):
                env.act("sv0", _zero_action(P5D10.TEAMMATE_AGENT_TYPE, 0))
                if include_target:
                    env.act("target", _zero_action(P5D10.TARGET_AGENT_TYPE, P5D10.P5D3._control_scheme(P5D10.TARGET_AGENT_TYPE)))
                state = env.tick()
                rgb = get_sensor_vector(state, "sv0", P5D10.P5D3.RGB_CAMERA_NAME)
                fan_range = _aggregate_fan_range(state)
                loc = get_sensor_vector(state, "sv0", "LocationSensor")
                orient = get_sensor_vector(state, "sv0", "OrientationSensor")
                heading = P5D10._heading_from_orientation(orient)
                if rgb is not None:
                    rgb_by_tick[tick] = np.asarray(rgb).copy()
                fan_by_tick[tick] = np.asarray(fan_range, dtype=float).copy()
                rsum = P5D1A._range_summary(fan_range)
                tick_rows.append(
                    {
                        "tick": int(tick),
                        "include_target": bool(include_target),
                        "rgb_present": rgb is not None,
                        "any_rangefinder_hit": bool(rsum.get("any_hit", False)),
                        "rangefinder_hit_beam_indices": rsum.get("hit_beam_indices"),
                        "rangefinder_min_positive_range_m": rsum.get("min_positive_range_m"),
                        "loc": None if loc is None else np.asarray(loc).astype(float).reshape(-1).tolist(),
                        "heading_deg": heading,
                    }
                )
    except Exception as exc:
        error = "{0}: {1}".format(type(exc).__name__, exc)
        tick_rows.append({"tick": 0, "include_target": bool(include_target), "scenario_error": error})
    return {
        "include_target": bool(include_target),
        "launch_ok": bool(launch_ok),
        "error": error,
        "wall_time_s": float(time.perf_counter() - started),
        "tick_rows": tick_rows,
        "rgb_by_tick": rgb_by_tick,
        "fan_by_tick": fan_by_tick,
    }


def _local_blob_for_capture(sphere_blob: Dict[str, Any], range_summary: Dict[str, Any]) -> Dict[str, Any]:
    return P5D10._local_range_scaled_blob_signature(
        sphere_blob.get("local_candidate_blobs"),
        range_summary.get("raw"),
    )


def _tick_eval(case: Dict[str, Any], tick: int, baseline_run: Dict[str, Any], target_run: Dict[str, Any]) -> Dict[str, Any]:
    rgb = target_run["rgb_by_tick"].get(tick)
    baseline_rgb = baseline_run["rgb_by_tick"].get(tick)
    fan_range = target_run["fan_by_tick"].get(tick)
    range_summary = P5D1A._range_summary(fan_range)
    rgb_diff = P5D1A._rgb_diff_signature(rgb, baseline_rgb)
    sphere_blob = P5D1A._sphere_blob_signature(rgb, baseline_rgb)
    local_blob = _local_blob_for_capture(sphere_blob, range_summary)
    row = {
        "case_name": case["case_name"],
        "case_source": case.get("case_source"),
        "tick": int(tick),
        "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0)),
        "rgb_change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
        "sphere_blob_candidate_count": int(sphere_blob.get("candidate_blob_count", 0)),
        "sphere_blob_local_candidate_count": int(sphere_blob.get("local_candidate_blob_count", 0)),
        "sphere_blob_white_neutral_changed_pixels": int(sphere_blob.get("white_neutral_changed_pixels", 0)),
        "sphere_blob_largest": sphere_blob.get("largest_blob"),
        "sphere_blob_local_best": sphere_blob.get("local_best_blob"),
        "local_range_scaled_blob_present": bool(local_blob.get("local_range_scaled_blob_present", False)),
        "local_blob_area": int(local_blob.get("local_blob_area", 0) or 0),
        "local_blob_range_scaled_area": local_blob.get("local_blob_range_scaled_area"),
        "matched": bool(local_blob.get("matched", False)),
        "blob_yaw_deg": local_blob.get("blob_yaw_deg"),
        "matched_beam_index": local_blob.get("matched_beam_index"),
        "matched_beam_yaw_deg": local_blob.get("matched_beam_yaw_deg"),
        "matched_range_m": local_blob.get("matched_range_m"),
        "beam_yaw_error_deg": local_blob.get("beam_yaw_error_deg"),
        "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
        "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
        **_mask_diagnostics(rgb, baseline_rgb),
    }
    return row


def _select_best_tick(case: Dict[str, Any], baseline_run: Dict[str, Any], target_run: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    rows = [_tick_eval(case, tick, baseline_run, target_run) for tick in range(1, CAPTURE_TICKS + 1)]
    accepted = [row for row in rows if row.get("local_range_scaled_blob_present") is True]
    if accepted:
        best = sorted(accepted, key=lambda row: float(row.get("local_blob_range_scaled_area") or 0.0), reverse=True)[0]
    else:
        best = sorted(
            rows,
            key=lambda row: (
                int(row.get("sphere_blob_local_candidate_count", 0) or 0),
                int(row.get("sphere_blob_white_neutral_changed_pixels", 0) or 0),
                int(row.get("rgb_changed_pixels", 0) or 0),
                1 if row.get("rangefinder_hit_beam_indices") else 0,
            ),
            reverse=True,
        )[0]
    return best, rows


def _save_visuals(case: Dict[str, Any], best: Dict[str, Any], baseline_run: Dict[str, Any], target_run: Dict[str, Any]) -> Dict[str, Optional[str]]:
    tick = int(best["tick"])
    base = os.path.join(PHASE_DIR, "visuals", "phase5d11_{0}_tick{1}".format(_safe_name(case["case_name"]), tick))
    rgb = target_run["rgb_by_tick"].get(tick)
    baseline_rgb = baseline_run["rgb_by_tick"].get(tick)
    fan_range = target_run["fan_by_tick"].get(tick)
    range_summary = P5D1A._range_summary(fan_range)
    sphere_blob = P5D1A._sphere_blob_signature(rgb, baseline_rgb)
    local_blob = _local_blob_for_capture(sphere_blob, range_summary)
    return {
        "target_rgb_preview_path": _save_image(base + "_target_rgb.png", rgb),
        "baseline_rgb_preview_path": _save_image(base + "_baseline_rgb.png", baseline_rgb),
        "diff_preview_path": _save_image(base + "_diff.png", _diff_image(rgb, baseline_rgb)),
        "white_neutral_mask_preview_path": _save_image(base + "_white_neutral_mask.png", _white_neutral_mask_image(rgb, baseline_rgb)),
        "overlay_preview_path": _save_image(
            base + "_overlay.png",
            _overlay_image(rgb_value=rgb, sphere_blob=sphere_blob, local_blob=local_blob, range_summary=range_summary),
        ),
    }


def _case_row(case: Dict[str, Any], baseline_run: Dict[str, Any], target_run: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    best, per_tick = _select_best_tick(case, baseline_run, target_run)
    visuals = _save_visuals(case, best, baseline_run, target_run)
    dx = float(case["target_world_location"][0]) - float(case["observer_world_location"][0])
    dy = float(case["target_world_location"][1]) - float(case["observer_world_location"][1])
    nominal_range = math.hypot(dx, dy)
    world_bearing = math.degrees(math.atan2(dy, dx))
    relative_bearing = (world_bearing - float(case["observer_heading_deg"]) + 180.0) % 360.0 - 180.0
    row = {
        "case_name": case["case_name"],
        "case_source": case.get("case_source"),
        "source_policy_step": case.get("source_policy_step"),
        "source_tick_global": case.get("source_tick_global"),
        "source_capture_phase": case.get("source_capture_phase"),
        "observer_world_location": case["observer_world_location"],
        "observer_heading_deg": case["observer_heading_deg"],
        "target_world_location": case["target_world_location"],
        "nominal_target_range_m": nominal_range,
        "nominal_world_bearing_deg": world_bearing,
        "nominal_relative_bearing_deg": relative_bearing,
        "source_5d10_rgb_changed_pixels": case.get("source_rgb_changed_pixels"),
        "source_5d10_local_candidate_count": case.get("source_local_candidate_count"),
        "source_5d10_rangefinder_hit_beam_indices": case.get("source_rangefinder_hit_beam_indices"),
        "baseline_launch_ok": baseline_run.get("launch_ok"),
        "target_launch_ok": target_run.get("launch_ok"),
        "baseline_error": baseline_run.get("error"),
        "target_error": target_run.get("error"),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        **best,
        **visuals,
    }
    return row, per_tick


def _event_sort_tuple(row: Dict[str, str]) -> Tuple[int, int, float]:
    return (
        _as_int(row.get("sphere_blob_local_candidate_count")),
        _as_int(row.get("rgb_changed_pixels")),
        _as_float(row.get("rangefinder_min_positive_range_m"), 999999.0),
    )


def _case_from_event(name: str, row: Dict[str, str], summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "case_name": name,
        "case_source": "phase5d10_target_event",
        "source_policy_step": _as_int(row.get("policy_step")),
        "source_tick_global": _as_int(row.get("tick_global")),
        "source_capture_phase": row.get("capture_phase"),
        "observer_world_location": [float(v) for v in (_parse_list(row.get("observer_world_location")) or [0.0, 0.0, 0.0])],
        "observer_heading_deg": _as_float(row.get("observer_heading_deg")),
        "target_world_location": [float(v) for v in summary.get("target_world_location", [-270.0, 221.0, 0.5])],
        "source_rgb_changed_pixels": _as_int(row.get("rgb_changed_pixels")),
        "source_local_candidate_count": _as_int(row.get("sphere_blob_local_candidate_count")),
        "source_rangefinder_hit_beam_indices": _parse_list(row.get("rangefinder_hit_beam_indices")) or [],
    }


def _build_cases_from_5d10() -> List[Dict[str, Any]]:
    summary = _load_json(SOURCE_5D10_SUMMARY_JSON)
    target_events: List[Dict[str, str]] = []
    with open(SOURCE_5D10_EVENTS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("run_kind") == "target":
                target_events.append(row)

    def has_hit(row: Dict[str, str]) -> bool:
        return bool(_parse_list(row.get("rangefinder_hit_beam_indices")))

    def candidate_count(row: Dict[str, str]) -> int:
        return _as_int(row.get("sphere_blob_local_candidate_count"))

    cases: List[Dict[str, Any]] = [
        {
            "case_name": "control_5d9_planner_front_center_30m",
            "case_source": "phase5d9_known_good_static_geometry",
            "observer_world_location": [-300.0, 221.0, 0.0],
            "observer_heading_deg": 0.0,
            "target_world_location": [float(v) for v in summary.get("target_world_location", [-270.0, 221.0, 0.5])],
            "source_capture_phase": "static_control",
            "source_rgb_changed_pixels": None,
            "source_local_candidate_count": None,
            "source_rangefinder_hit_beam_indices": None,
        }
    ]

    for index, row in enumerate([row for row in target_events if has_hit(row)][:3], start=1):
        cases.append(_case_from_event("target_range_hit_failure_{0}".format(index), row, summary))

    candidate_rows = [row for row in target_events if candidate_count(row) > 0]
    if candidate_rows:
        cases.append(
            _case_from_event(
                "target_best_candidate_failure",
                sorted(candidate_rows, key=_event_sort_tuple, reverse=True)[0],
                summary,
            )
        )
    changed_rows = sorted(target_events, key=lambda row: _as_int(row.get("rgb_changed_pixels")), reverse=True)
    if changed_rows:
        cases.append(_case_from_event("target_large_diff_failure", changed_rows[0], summary))
    standoff_rows = [row for row in candidate_rows if row.get("capture_phase") == "standoff_viewpoint_hold"]
    if standoff_rows:
        cases.append(
            _case_from_event(
                "target_standoff_candidate_failure",
                sorted(standoff_rows, key=_event_sort_tuple, reverse=True)[0],
                summary,
            )
        )

    unique: List[Dict[str, Any]] = []
    seen = set()
    for case in cases:
        key = (case.get("case_name"), case.get("source_tick_global"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    return unique


def _source_audit_all_passed() -> bool:
    try:
        return _load_json(SOURCE_5D10_AUDIT_JSON).get("all_passed") is False
    except Exception:
        return False


def _build_summary(rows: List[Dict[str, Any]], per_tick_rows: List[Dict[str, Any]], started: float) -> Dict[str, Any]:
    control = next((row for row in rows if row.get("case_name") == "control_5d9_planner_front_center_30m"), None)
    failure_rows = [row for row in rows if str(row.get("case_name", "")).startswith("target_")]
    failure_accepted = [row for row in failure_rows if row.get("local_range_scaled_blob_present") is True]
    failure_range_hit_rows = [row for row in failure_rows if row.get("rangefinder_hit_beam_indices")]
    failure_local_candidate_rows = [row for row in failure_rows if int(row.get("sphere_blob_local_candidate_count") or 0) > 0]
    return {
        "phase_name": PHASE_NAME,
        "diagnostic_name": "phase5d11_rgb_range_sync_visual_diagnostic",
        "source_5d10_phase_name": SOURCE_5D10_PHASE_NAME,
        "source_5d10_audit_all_passed_false": _source_audit_all_passed(),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "target_agent_type": P5D10.TARGET_AGENT_TYPE,
        "observer_agent_type": P5D10.TEAMMATE_AGENT_TYPE,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "baseline_runtime_source_modified": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "case_count": len(rows),
        "control_case_accepted": bool(control and control.get("local_range_scaled_blob_present") is True),
        "target_failure_case_count": len(failure_rows),
        "target_failure_static_replay_accepted_count": len(failure_accepted),
        "target_failure_static_replay_accepted_cases": [row.get("case_name") for row in failure_accepted],
        "target_failure_static_replay_range_hit_case_count": len(failure_range_hit_rows),
        "target_failure_static_replay_local_candidate_case_count": len(failure_local_candidate_rows),
        "per_tick_row_count": len(per_tick_rows),
        "wall_time_s": round(time.perf_counter() - started, 6),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "rows": rows,
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    rows = summary.get("rows", [])
    lines = [
        "# Phase 5D-11 RGB/Range Sync Visual Diagnostic",
        "",
        "- Source Phase: `{0}`".format(summary.get("source_5d10_phase_name")),
        "- Source 5D-10 audit all_passed is false: `{0}`".format(summary.get("source_5d10_audit_all_passed_false")),
        "- Control Case Accepted: `{0}`".format(summary.get("control_case_accepted")),
        "- Target Failure Static Replay Accepted Count: `{0}`".format(summary.get("target_failure_static_replay_accepted_count")),
        "- Target Failure Static Replay Accepted Cases: `{0}`".format(summary.get("target_failure_static_replay_accepted_cases")),
        "",
        "| case | accepted | replay_range_m | replay_rel_bearing | src_step | src_phase | src_rgb | src_local_candidates | replay_rgb | replay_white_neutral | replay_local_candidates | replay_hit_beams | overlay |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {case} | {accepted} | {range_m:.3f} | {bearing:.3f} | {src_step} | {src_phase} | {src_rgb} | {src_local} | {rgb} | {white} | {local} | {beams} | {overlay} |".format(
                case=row.get("case_name"),
                accepted=row.get("local_range_scaled_blob_present"),
                range_m=float(row.get("nominal_target_range_m") or 0.0),
                bearing=float(row.get("nominal_relative_bearing_deg") or 0.0),
                src_step=row.get("source_policy_step"),
                src_phase=row.get("source_capture_phase"),
                src_rgb=row.get("source_5d10_rgb_changed_pixels"),
                src_local=row.get("source_5d10_local_candidate_count"),
                rgb=row.get("rgb_changed_pixels"),
                white=row.get("sphere_blob_white_neutral_changed_pixels"),
                local=row.get("sphere_blob_local_candidate_count"),
                beams=row.get("rangefinder_hit_beam_indices"),
                overlay=row.get("overlay_preview_path"),
            )
        )
    lines.extend(
        [
            "",
            "This diagnostic is audit-only. Source 5D-10 target truth is used to reconstruct static visual cases and labels, not as a detection input.",
            "",
        ]
    )
    return "\n".join(lines)


def run_diagnostic() -> Dict[str, Any]:
    started = time.perf_counter()
    rows: List[Dict[str, Any]] = []
    per_tick_rows: List[Dict[str, Any]] = []
    cases = _build_cases_from_5d10()
    for index, case in enumerate(cases, start=1):
        print("[{0}/{1}] Capturing {2}".format(index, len(cases), case["case_name"]))
        baseline_run = _capture_case(case, include_target=False)
        target_run = _capture_case(case, include_target=True)
        row, ticks = _case_row(case, baseline_run, target_run)
        rows.append(row)
        per_tick_rows.extend(ticks)
    summary = _build_summary(rows, per_tick_rows, started)
    _save_json(DIAG_JSON, summary)
    _save_csv(DIAG_CSV, rows)
    _save_csv(PER_TICK_CSV, per_tick_rows)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary written to: {0}".format(SUMMARY_MD))
    return summary


def main() -> None:
    run_diagnostic()


if __name__ == "__main__":
    main()
