"""Phase 5D-9 RGB geometry diagnostic for live planner standoff work.

This diagnostic compares the known-good Phase 5D-7 local geometry with the
same relative geometry translated into the Phase 5D-8/5D-9 planner world area.
It does not modify the baseline_GP planner, adapter, detection rule, or target
class. Truth locations are used only to construct audit scenarios and labels.
"""

from __future__ import annotations

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
PHASE_NAME = "phase5d9_live_planner_standoff_capture_search"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
PROBE_PATH = os.path.join(PHASE_DIR, "scripts", "live_planner_standoff_capture_search_probe.py")

DIAG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_rgb_geometry_diagnostic.json")
DIAG_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_rgb_geometry_diagnostic.csv")
DIAG_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d9_rgb_geometry_diagnostic.md")

CAPTURE_TICKS = 16


def _load_module(path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load module from {0}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5D9 = _load_module(PROBE_PATH, "phase5d9_probe_for_rgb_geometry_diag")
P5D1A = P5D9.P5D3.P5D1A


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
        if maxv > 0.0:
            finite = finite / maxv * 255.0
        return np.clip(finite, 0, 255).astype(np.uint8)
    return np.zeros((16, 16), dtype=np.uint8)


def _save_preview(path: str, value: Any) -> Optional[str]:
    try:
        from PIL import Image

        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(_preview_array(value)).save(path)
        return path
    except Exception as exc:
        print("[WARN] preview save failed for {0}: {1}".format(path, exc))
        return None


def _safe_name(name: str) -> str:
    keep = []
    for ch in str(name):
        if ch.isalnum() or ch in ("_", "-"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)


def _control_action(agent_type: str, control_scheme: int) -> np.ndarray:
    del control_scheme
    return P5D1A._zero_action(agent_type)


def _surface_vessel_agent(
    *,
    location: List[float],
    rotation: List[float],
    control_scheme: int,
    dense_fan: bool,
) -> Dict[str, Any]:
    sensors = [
        {"sensor_type": "LocationSensor", "socket": "COM"},
        {"sensor_type": "GPSSensor", "socket": "COM"},
        {"sensor_type": "OrientationSensor", "socket": "COM"},
        P5D1A._camera_sensor(),
    ]
    sensors += P5D9._bridge_fan_rangefinder_sensors() if dense_fan else P5D1A._fan_rangefinder_sensors()
    return {
        "agent_name": "sv0",
        "agent_type": P5D9.TEAMMATE_AGENT_TYPE,
        "sensors": sensors,
        "control_scheme": int(control_scheme),
        "location": [float(v) for v in location],
        "rotation": [float(v) for v in rotation],
    }


def _scenario_config(case: Dict[str, Any], include_target: bool) -> Dict[str, Any]:
    agents = [
        _surface_vessel_agent(
            location=list(case["observer_world_location"]),
            rotation=list(case.get("observer_rotation_deg", [0.0, 0.0, 0.0])),
            control_scheme=int(case.get("observer_control_scheme", 0)),
            dense_fan=bool(case.get("dense_fan", True)),
        )
    ]
    if include_target:
        agents.append(
            {
                "agent_name": "target",
                "agent_type": P5D9.TARGET_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": P5D1A._control_scheme(P5D9.TARGET_AGENT_TYPE),
                "location": [float(v) for v in case["target_world_location"]],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    return {
        "name": "phase5d9_rgb_diag_{0}_{1}".format(
            _safe_name(case["case_name"]),
            "target" if include_target else "baseline",
        ),
        "world": "OpenWater",
        "package_name": "Ocean",
        "main_agent": "sv0",
        "agents": agents,
    }


def _fan_names(dense_fan: bool) -> List[str]:
    if dense_fan:
        return P5D9._fan_rangefinder_names()
    return P5D1A._fan_rangefinder_names()


def _aggregate_fan_range(state: Dict[str, Any], dense_fan: bool) -> List[float]:
    values: List[float] = []
    for name in _fan_names(dense_fan):
        value = get_sensor_vector(state, "sv0", name)
        if value is None:
            values.append(-1.0)
            continue
        arr = np.asarray(value).astype(float).reshape(-1)
        values.append(float(arr[0]) if arr.size else -1.0)
    return values


def _capture_case(case: Dict[str, Any], include_target: bool) -> Dict[str, Any]:
    import holoocean

    dense_fan = bool(case.get("dense_fan", True))
    control_scheme = int(case.get("observer_control_scheme", 0))
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
                env.act("sv0", _control_action(P5D9.TEAMMATE_AGENT_TYPE, control_scheme))
                if include_target:
                    env.act("target", _control_action(P5D9.TARGET_AGENT_TYPE, P5D1A._control_scheme(P5D9.TARGET_AGENT_TYPE)))
                state = env.tick()
                rgb = get_sensor_vector(state, "sv0", P5D9.P5D3.RGB_CAMERA_NAME)
                fan_range = _aggregate_fan_range(state, dense_fan)
                loc = get_sensor_vector(state, "sv0", "LocationSensor")
                orient = get_sensor_vector(state, "sv0", "OrientationSensor")
                heading = P5D9._heading_from_orientation(orient)
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
    changed_pixels = rgb3[diff_mask]
    top_changed_mean = None
    if changed_pixels.size:
        top_changed_mean = np.mean(changed_pixels.astype(float), axis=0).tolist()
    return {
        "roi_xyxy": [x0, y0, x1, y1],
        "diff_ge_threshold_roi_pixels": int(np.count_nonzero(diff_mask)),
        "bright_roi_pixels": int(np.count_nonzero(bright_mask)),
        "neutral_roi_pixels": int(np.count_nonzero(neutral_mask)),
        "diff_and_bright_roi_pixels": int(np.count_nonzero(diff_mask & bright_mask)),
        "diff_and_neutral_roi_pixels": int(np.count_nonzero(diff_mask & neutral_mask)),
        "white_neutral_mask_pixels": int(np.count_nonzero(white_neutral_mask)),
        "max_diff_roi": float(np.max(diff[roi])) if np.count_nonzero(roi) else None,
        "mean_changed_rgb": top_changed_mean,
    }


def _range_yaws(dense_fan: bool) -> List[float]:
    if dense_fan:
        return list(P5D9.BRIDGE_FAN_YAW_DEGREES)
    return list(P5D1A.FAN_YAW_DEGREES)


def _local_blob_for_case(case: Dict[str, Any], sphere_blob: Dict[str, Any], range_summary: Dict[str, Any]) -> Dict[str, Any]:
    old_yaws = list(P5D9.BRIDGE_FAN_YAW_DEGREES)
    try:
        P5D9.BRIDGE_FAN_YAW_DEGREES = _range_yaws(bool(case.get("dense_fan", True)))
        return P5D9._local_range_scaled_blob_signature(
            sphere_blob.get("local_candidate_blobs"),
            range_summary.get("raw"),
        )
    finally:
        P5D9.BRIDGE_FAN_YAW_DEGREES = old_yaws


def _diff_preview(rgb_value: Any, baseline_value: Any) -> Optional[np.ndarray]:
    if rgb_value is None or baseline_value is None:
        return None
    rgb = np.asarray(rgb_value)[..., :3].astype(np.int16)
    baseline = np.asarray(baseline_value)[..., :3].astype(np.int16)
    if rgb.shape[:2] != baseline.shape[:2]:
        return None
    diff = np.max(np.abs(rgb - baseline), axis=-1)
    return np.clip(diff * 4, 0, 255).astype(np.uint8)


def _best_row_for_case(case: Dict[str, Any], baseline_run: Dict[str, Any], target_run: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for tick in range(1, CAPTURE_TICKS + 1):
        rgb = target_run["rgb_by_tick"].get(tick)
        baseline_rgb = baseline_run["rgb_by_tick"].get(tick)
        fan_range = target_run["fan_by_tick"].get(tick)
        range_summary = P5D1A._range_summary(fan_range)
        rgb_diff = P5D1A._rgb_diff_signature(rgb, baseline_rgb)
        sphere_blob = P5D1A._sphere_blob_signature(rgb, baseline_rgb)
        local_blob = _local_blob_for_case(case, sphere_blob, range_summary)
        rows.append(
            {
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
        )
    accepted = [row for row in rows if row.get("local_range_scaled_blob_present") is True]
    if accepted:
        best = sorted(
            accepted,
            key=lambda row: float(row.get("local_blob_range_scaled_area") or 0.0),
            reverse=True,
        )[0]
    else:
        best = sorted(
            rows,
            key=lambda row: (
                int(row.get("sphere_blob_local_candidate_count", 0) or 0),
                int(row.get("sphere_blob_white_neutral_changed_pixels", 0) or 0),
                int(row.get("rgb_changed_pixels", 0) or 0),
            ),
            reverse=True,
        )[0]
    best_tick = int(best["tick"])
    visual_prefix = os.path.join(PHASE_DIR, "visuals", "phase5d9_rgb_diag_{0}".format(_safe_name(case["case_name"])))
    best["target_rgb_preview_path"] = _save_preview(visual_prefix + "_target_tick{0}.png".format(best_tick), target_run["rgb_by_tick"].get(best_tick))
    best["baseline_rgb_preview_path"] = _save_preview(visual_prefix + "_baseline_tick{0}.png".format(best_tick), baseline_run["rgb_by_tick"].get(best_tick))
    diff = _diff_preview(target_run["rgb_by_tick"].get(best_tick), baseline_run["rgb_by_tick"].get(best_tick))
    best["diff_preview_path"] = _save_preview(visual_prefix + "_diff_tick{0}.png".format(best_tick), diff) if diff is not None else None
    best["per_tick_rows"] = rows
    return best


def _case_row(case: Dict[str, Any], baseline_run: Dict[str, Any], target_run: Dict[str, Any]) -> Dict[str, Any]:
    best = _best_row_for_case(case, baseline_run, target_run)
    dx = float(case["target_world_location"][0]) - float(case["observer_world_location"][0])
    dy = float(case["target_world_location"][1]) - float(case["observer_world_location"][1])
    nominal_range = math.hypot(dx, dy)
    nominal_bearing = math.degrees(math.atan2(dy, dx))
    row = {
        "case_name": case["case_name"],
        "case_role": case.get("case_role"),
        "observer_world_location": case["observer_world_location"],
        "target_world_location": case["target_world_location"],
        "observer_rotation_deg": case.get("observer_rotation_deg", [0.0, 0.0, 0.0]),
        "observer_control_scheme": int(case.get("observer_control_scheme", 0)),
        "dense_fan": bool(case.get("dense_fan", True)),
        "nominal_target_range_m": nominal_range,
        "nominal_target_bearing_deg": nominal_bearing,
        "baseline_launch_ok": baseline_run.get("launch_ok"),
        "target_launch_ok": target_run.get("launch_ok"),
        "baseline_error": baseline_run.get("error"),
        "target_error": target_run.get("error"),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        **{key: value for key, value in best.items() if key != "per_tick_rows"},
    }
    return row


def _build_cases() -> List[Dict[str, Any]]:
    return [
        {
            "case_name": "origin_5d7_sv0_like",
            "case_role": "known_good_relative_geometry_near_origin",
            "observer_world_location": [2.0, -6.0, 0.0],
            "target_world_location": [31.0, 0.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
        {
            "case_name": "origin_5d1a_front_30m",
            "case_role": "known_good_front_center_near_origin",
            "observer_world_location": [1.0, 0.0, 0.0],
            "target_world_location": [31.0, 0.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
        {
            "case_name": "planner_translated_5d7_sv0_like",
            "case_role": "same_relative_geometry_translated_to_phase5d8_target_area",
            "observer_world_location": [-299.0, 215.0, 0.0],
            "target_world_location": [-270.0, 221.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
        {
            "case_name": "planner_front_center_30m",
            "case_role": "phase5d9_standoff_center_30m",
            "observer_world_location": [-300.0, 221.0, 0.0],
            "target_world_location": [-270.0, 221.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
        {
            "case_name": "planner_front_center_20m",
            "case_role": "phase5d9_standoff_center_20m",
            "observer_world_location": [-290.0, 221.0, 0.0],
            "target_world_location": [-270.0, 221.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
        {
            "case_name": "planner_front_center_10m",
            "case_role": "phase5d9_standoff_center_10m",
            "observer_world_location": [-280.0, 221.0, 0.0],
            "target_world_location": [-270.0, 221.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
        {
            "case_name": "map_center_front_30m",
            "case_role": "world_midpoint_front_center_30m",
            "observer_world_location": [-30.0, 0.0, 0.0],
            "target_world_location": [0.0, 0.0, 0.5],
            "observer_rotation_deg": [0.0, 0.0, 0.0],
            "observer_control_scheme": 0,
            "dense_fan": True,
        },
    ]


def _build_summary(rows: List[Dict[str, Any]], started: float) -> Dict[str, Any]:
    passing = [row for row in rows if row.get("local_range_scaled_blob_present") is True]
    translated = next((row for row in rows if row.get("case_name") == "planner_translated_5d7_sv0_like"), None)
    origin = next((row for row in rows if row.get("case_name") == "origin_5d7_sv0_like"), None)
    planner_front = next((row for row in rows if row.get("case_name") == "planner_front_center_30m"), None)
    return {
        "phase_name": PHASE_NAME,
        "diagnostic_name": "phase5d9_rgb_geometry_diagnostic",
        "recommended_rule_id": P5D9.RECOMMENDED_RULE_ID,
        "target_agent_type": P5D9.TARGET_AGENT_TYPE,
        "observer_agent_type": P5D9.TEAMMATE_AGENT_TYPE,
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
        "accepted_case_names": [row.get("case_name") for row in passing],
        "accepted_case_count": len(passing),
        "origin_5d7_like_accepted": bool(origin and origin.get("local_range_scaled_blob_present") is True),
        "planner_translated_5d7_like_accepted": bool(translated and translated.get("local_range_scaled_blob_present") is True),
        "planner_front_center_30m_accepted": bool(planner_front and planner_front.get("local_range_scaled_blob_present") is True),
        "wall_time_s": round(time.perf_counter() - started, 6),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "rows": rows,
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    rows = summary.get("rows", [])
    lines = [
        "# Phase 5D-9 RGB Geometry Diagnostic",
        "",
        "- Accepted Case Count: `{0}`".format(summary.get("accepted_case_count")),
        "- Accepted Cases: `{0}`".format(summary.get("accepted_case_names")),
        "- Origin 5D-7-like Accepted: `{0}`".format(summary.get("origin_5d7_like_accepted")),
        "- Planner-translated 5D-7-like Accepted: `{0}`".format(summary.get("planner_translated_5d7_like_accepted")),
        "- Planner Front Center 30m Accepted: `{0}`".format(summary.get("planner_front_center_30m_accepted")),
        "",
        "| case | accepted | range_m | rgb_changed | white_neutral | local_candidates | matched_range | preview |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {0} | {1} | {2:.3f} | {3} | {4} | {5} | {6} | {7} |".format(
                row.get("case_name"),
                row.get("local_range_scaled_blob_present"),
                float(row.get("nominal_target_range_m") or 0.0),
                row.get("rgb_changed_pixels"),
                row.get("sphere_blob_white_neutral_changed_pixels"),
                row.get("sphere_blob_local_candidate_count"),
                row.get("matched_range_m"),
                row.get("target_rgb_preview_path"),
            )
        )
    lines.extend(
        [
            "",
            "This diagnostic is audit-only. It uses static SphereAgent geometry to identify why live planner capture did or did not produce the existing sphere_blob_local_range_scaled_any_hit evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def run_diagnostic() -> Dict[str, Any]:
    started = time.perf_counter()
    rows: List[Dict[str, Any]] = []
    cases = _build_cases()
    for index, case in enumerate(cases, start=1):
        print("[{0}/{1}] Capturing {2}".format(index, len(cases), case["case_name"]))
        baseline_run = _capture_case(case, include_target=False)
        target_run = _capture_case(case, include_target=True)
        rows.append(_case_row(case, baseline_run, target_run))
    summary = _build_summary(rows, started)
    _save_json(DIAG_JSON, summary)
    _save_csv(DIAG_CSV, rows)
    os.makedirs(os.path.dirname(DIAG_SUMMARY_MD), exist_ok=True)
    with open(DIAG_SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary written to: {0}".format(DIAG_SUMMARY_MD))
    return summary


def main() -> None:
    run_diagnostic()


if __name__ == "__main__":
    main()
