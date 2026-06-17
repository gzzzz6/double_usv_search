"""Phase 5C-4I-1 offline rule calibration.

This script reads the audited Phase 5C-4H artifacts and evaluates stricter
candidate detection rules without launching HoloOcean.

Important input constraint:
    5C-4H scene_results JSON intentionally strips first_rgb_raw. Any RGB
    signature recomputation must load visuals/*_rgb_raw.npy.
"""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4i_direction_matched_distractor_rejection_calibration"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SOURCE_PHASE_NAME = "phase5c4h_fan_area_distance_boundary"
SOURCE_PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_PHASE_NAME))
SOURCE_MANIFESTS_DIR = os.path.join(SOURCE_PHASE_DIR, "manifests")
SOURCE_VISUALS_DIR = os.path.join(SOURCE_PHASE_DIR, "visuals")

SOURCE_MATRIX_JSON = os.path.join(SOURCE_MANIFESTS_DIR, "rgb_multiray_fan_area_distance_boundary_matrix.json")
SOURCE_SCENE_RESULTS_JSON = os.path.join(SOURCE_MANIFESTS_DIR, "rgb_multiray_fan_area_distance_scene_results.json")
SOURCE_EVENTS_JSON = os.path.join(SOURCE_MANIFESTS_DIR, "rgb_multiray_fan_area_distance_detection_events.json")
SOURCE_CONFIG_JSON = os.path.join(SOURCE_MANIFESTS_DIR, "rgb_multiray_fan_area_distance_config.json")

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "offline_rule_calibration_config.json")
RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "candidate_rule_matrix.json")
RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "candidate_rule_matrix.csv")
RULE_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "candidate_rule_summary.json")
RECOMMENDED_RULE_JSON = os.path.join(PHASE_DIR, "manifests", "recommended_candidate_rule.json")
RECOMPUTED_EVIDENCE_JSON = os.path.join(PHASE_DIR, "manifests", "recomputed_rgb_evidence.json")
OLD_DIRECTION_FAILURE_JSON = os.path.join(PHASE_DIR, "manifests", "old_direction_match_failure_reference.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "offline_rule_calibration_git_status.json")

OFFLINE_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "offline_rule_calibration_summary.md")
OLD_DIRECTION_FAILURE_MD = os.path.join(PHASE_DIR, "reports", "old_direction_match_failure_reference.md")

RGB_DIFF_THRESHOLD = 28.0
RGB_SIGNATURE_QUANTIZATION = 32
RGB_SIGNATURE_TOP_K = 24
OVERLAP_MIN_VALUES = [1, 2, 3, 4, 5, 6, 7]
CHANGED_PIXELS_MIN_VALUES = [0, 10, 15, 20, 40, 80]
RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES = [7.5, 10.0, 12.5, 15.0]
CAMERA_HORIZONTAL_FOV_DEG = 90.0
DISTRACTOR_OVERLAP_MIN_VALUES = [1, 2, 3, 4]
DISTRACTOR_SIGNATURE_MIN_SCENE_FREQUENCY = 2


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


def _rgb_raw_path(scene: str) -> str:
    return os.path.join(SOURCE_VISUALS_DIR, "{0}_rgb_raw.npy".format(scene))


def _load_rgb_raw(scene: str) -> np.ndarray:
    path = _rgb_raw_path(scene)
    return np.load(path)


def _rgb_diff_signature(
    rgb_value: Any,
    baseline_value: Any,
    diff_threshold: float,
    quantization: int,
    top_k: int,
) -> Dict[str, Any]:
    if rgb_value is None or baseline_value is None:
        return {
            "present": False,
            "changed_pixels": 0,
            "change_bbox_xyxy": None,
            "signature_colors": [],
            "signature_color_counts": {},
            "mask": None,
            "quantized_pixels": None,
            "xs": None,
            "ys": None,
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
            "mask": None,
            "quantized_pixels": None,
            "xs": None,
            "ys": None,
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
    mask = (diff >= float(diff_threshold)) & roi
    changed_pixels = int(np.count_nonzero(mask))
    if changed_pixels == 0:
        return {
            "present": True,
            "changed_pixels": 0,
            "change_bbox_xyxy": None,
            "signature_colors": [],
            "signature_color_counts": {},
            "roi_xyxy": [x0, y0, x1, y1],
            "mask": mask,
            "quantized_pixels": None,
            "xs": np.array([], dtype=int),
            "ys": np.array([], dtype=int),
        }
    ys, xs = np.nonzero(mask)
    pixels = rgb3[mask].astype(np.uint8)
    quant = (pixels // int(quantization)) * int(quantization)
    unique, counts = np.unique(quant, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1]
    signature_counts: Dict[str, int] = {}
    signature_colors: List[str] = []
    for index in order[: int(top_k)]:
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
        "mask": mask,
        "quantized_pixels": quant,
        "xs": xs,
        "ys": ys,
    }


def _color_keys(quantized_pixels: Optional[np.ndarray]) -> np.ndarray:
    if quantized_pixels is None:
        return np.array([], dtype=object)
    keys = [
        "{0},{1},{2},255".format(int(color[0]), int(color[1]), int(color[2]))
        for color in np.asarray(quantized_pixels)
    ]
    return np.asarray(keys, dtype=object)


def _bbox_from_points(xs: np.ndarray, ys: np.ndarray) -> Optional[List[int]]:
    if xs.size == 0 or ys.size == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _angle_from_x(x_center: Optional[float], width: int, horizontal_fov_deg: float) -> Optional[float]:
    if x_center is None or width <= 0:
        return None
    return (float(width) / 2.0 - float(x_center)) / (float(width) / 2.0) * (float(horizontal_fov_deg) / 2.0)


def _recalibrated_direction_match(
    rgb_angle_deg: Optional[float],
    hit_beam_indices: Iterable[Any],
    fan_yaw_degrees: List[float],
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
        if index < 0 or index >= len(fan_yaw_degrees):
            continue
        yaw = float(fan_yaw_degrees[index])
        delta = abs(float(rgb_angle_deg) - yaw)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_yaw = yaw
    return bool(best_delta is not None and best_delta <= float(tolerance_deg)), best_delta, best_yaw


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


def _build_recomputed_evidence(
    source_matrix: List[Dict[str, Any]],
    source_config: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    diff_threshold = float(source_config.get("rgb_signature_detector", {}).get("diff_threshold", RGB_DIFF_THRESHOLD))
    quantization = int(source_config.get("rgb_signature_detector", {}).get("quantization", RGB_SIGNATURE_QUANTIZATION))
    top_k = int(source_config.get("rgb_signature_detector", {}).get("top_k", RGB_SIGNATURE_TOP_K))
    calibration_scene = str(source_config.get("rgb_signature_calibration_scene", "calibration_target_front_center_10m"))
    fan_yaw_degrees = [float(v) for v in source_config.get("horizontal_fan_yaw_degrees", [])]
    if not fan_yaw_degrees:
        fan_yaw_degrees = [30.0, 22.5, 15.0, 7.5, 0.0, -7.5, -15.0, -22.5, -30.0]

    baseline_rgb = _load_rgb_raw("baseline")
    calibration_rgb = _load_rgb_raw(calibration_scene)
    target_sig = _rgb_diff_signature(calibration_rgb, baseline_rgb, diff_threshold, quantization, top_k)
    target_signature_colors = sorted(set(str(v) for v in target_sig.get("signature_colors", [])))
    target_signature_color_set = set(target_signature_colors)

    evidence_rows: List[Dict[str, Any]] = []
    scene_color_sets: Dict[str, set] = {}
    for source_row in source_matrix:
        scene = str(source_row["scene"])
        rgb = _load_rgb_raw(scene)
        sig = _rgb_diff_signature(rgb, baseline_rgb, diff_threshold, quantization, top_k)
        scene_colors = set(str(v) for v in sig.get("signature_colors", []))
        scene_color_sets[scene] = scene_colors
        overlap_colors = sorted(target_signature_color_set & scene_colors)

        color_keys = _color_keys(sig.get("quantized_pixels"))
        xs = sig.get("xs")
        ys = sig.get("ys")
        target_pixel_mask = np.array([str(key) in target_signature_color_set for key in color_keys], dtype=bool)
        target_overlap_xs = np.asarray(xs)[target_pixel_mask] if xs is not None and target_pixel_mask.size else np.array([], dtype=int)
        target_overlap_ys = np.asarray(ys)[target_pixel_mask] if ys is not None and target_pixel_mask.size else np.array([], dtype=int)
        target_overlap_bbox = _bbox_from_points(target_overlap_xs, target_overlap_ys)
        target_overlap_x_center = None
        if target_overlap_bbox is not None:
            target_overlap_x_center = (float(target_overlap_bbox[0]) + float(target_overlap_bbox[2])) / 2.0

        rgb_shape = list(np.asarray(rgb).shape)
        width = int(rgb_shape[1]) if len(rgb_shape) >= 2 else int(source_config.get("camera_width", 320))
        rgb_target_angle_deg = _angle_from_x(target_overlap_x_center, width, CAMERA_HORIZONTAL_FOV_DEG)
        direction_matches: Dict[str, Any] = {}
        for tolerance in RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES:
            matched, delta, yaw = _recalibrated_direction_match(
                rgb_target_angle_deg,
                source_row.get("rangefinder_hit_beam_indices", []),
                fan_yaw_degrees,
                tolerance,
            )
            direction_matches[str(tolerance)] = {
                "matched": matched,
                "best_delta_deg": delta,
                "best_hit_beam_yaw_deg": yaw,
            }

        evidence_rows.append(
            {
                "scene": scene,
                "scenario_kind": source_row.get("scenario_kind"),
                "is_calibration_scene": bool(source_row.get("is_calibration_scene", False)),
                "expected_target_present_for_audit": bool(source_row.get("expected_target_present_for_audit", False)),
                "distance_m": source_row.get("distance_m"),
                "angle_label": source_row.get("angle_label"),
                "angle_deg": source_row.get("angle_deg"),
                "rgb_raw_path": _rgb_raw_path(scene),
                "rgb_raw_loaded": True,
                "scene_results_first_rgb_raw_used": False,
                "rgb_signature_colors": sorted(scene_colors),
                "rgb_signature_overlap": overlap_colors,
                "rgb_signature_overlap_count": len(overlap_colors),
                "rgb_changed_pixels": int(sig.get("changed_pixels", 0)),
                "rgb_change_bbox_xyxy": sig.get("change_bbox_xyxy"),
                "rgb_target_overlap_pixel_count": int(target_overlap_xs.size),
                "rgb_target_overlap_bbox_xyxy": target_overlap_bbox,
                "rgb_target_overlap_x_center": target_overlap_x_center,
                "rgb_target_angle_deg": rgb_target_angle_deg,
                "rangefinder_hit_beam_indices": source_row.get("rangefinder_hit_beam_indices", []),
                "rangefinder_raw_beams": source_row.get("rangefinder_raw_beams", []),
                "any_rangefinder_hit": bool(source_row.get("any_rangefinder_hit", False)),
                "old_matched_rangefinder_beam_hit": bool(source_row.get("matched_rangefinder_beam_hit", False)),
                "recalibrated_direction_matches": direction_matches,
                "source_rgb_overlap_count": len(source_row.get("rgb_signature_overlap", []) or []),
                "source_rgb_changed_pixels": source_row.get("rgb_changed_pixels"),
                "source_found": bool(source_row.get("found", False)),
                "source_outcome": source_row.get("outcome"),
            }
        )

    distractor_rows = [row for row in evidence_rows if row.get("scenario_kind") == "distractor_only"]
    distractor_frequency: Dict[str, int] = {}
    for row in distractor_rows:
        for color in row.get("rgb_signature_colors", []):
            distractor_frequency[color] = distractor_frequency.get(color, 0) + 1
    distractor_signature_colors = sorted(
        color
        for color, frequency in distractor_frequency.items()
        if int(frequency) >= DISTRACTOR_SIGNATURE_MIN_SCENE_FREQUENCY
    )
    distractor_signature_set = set(distractor_signature_colors)
    for row in evidence_rows:
        scene_colors = scene_color_sets[str(row["scene"])]
        overlap = sorted(distractor_signature_set & scene_colors)
        row["distractor_signature_overlap"] = overlap
        row["distractor_signature_overlap_count"] = len(overlap)

    meta = {
        "source_phase_name": SOURCE_PHASE_NAME,
        "source_matrix_json": SOURCE_MATRIX_JSON,
        "source_scene_results_json": SOURCE_SCENE_RESULTS_JSON,
        "source_detection_events_json": SOURCE_EVENTS_JSON,
        "source_rgb_raw_glob": os.path.join(SOURCE_VISUALS_DIR, "*_rgb_raw.npy"),
        "raw_rgb_loaded_from_visuals": True,
        "scene_results_first_rgb_raw_used": False,
        "scene_results_first_rgb_raw_stripped": True,
        "diff_threshold": diff_threshold,
        "quantization": quantization,
        "top_k": top_k,
        "target_signature_colors": target_signature_colors,
        "target_signature_color_count": len(target_signature_colors),
        "distractor_signature_min_scene_frequency": DISTRACTOR_SIGNATURE_MIN_SCENE_FREQUENCY,
        "distractor_signature_colors": distractor_signature_colors,
        "distractor_signature_color_count": len(distractor_signature_colors),
        "distractor_signature_scene_frequency": distractor_frequency,
        "camera_horizontal_fov_deg": CAMERA_HORIZONTAL_FOV_DEG,
        "fan_yaw_degrees": fan_yaw_degrees,
    }
    return evidence_rows, meta


def _rule_found(
    rule_name: str,
    evidence: Dict[str, Any],
    overlap_min: int = 1,
    changed_pixels_min: int = 0,
    tolerance_deg: Optional[float] = None,
    distractor_overlap_min: Optional[int] = None,
) -> bool:
    overlap_ok = int(evidence.get("rgb_signature_overlap_count", 0)) >= int(overlap_min)
    changed_ok = int(evidence.get("rgb_changed_pixels", 0)) >= int(changed_pixels_min)
    any_hit = bool(evidence.get("any_rangefinder_hit", False))
    if rule_name == "baseline_any_hit":
        return bool(overlap_ok and any_hit)
    if rule_name == "stronger_rgb_any_hit":
        return bool(overlap_ok and changed_ok and any_hit)
    if rule_name == "old_direction_matched_as_failure_reference":
        return bool(overlap_ok and bool(evidence.get("old_matched_rangefinder_beam_hit", False)))
    if rule_name == "recalibrated_direction_matched":
        match = evidence.get("recalibrated_direction_matches", {}).get(str(tolerance_deg), {})
        return bool(overlap_ok and bool(match.get("matched", False)))
    if rule_name == "stronger_rgb_recalibrated_direction":
        match = evidence.get("recalibrated_direction_matches", {}).get(str(tolerance_deg), {})
        return bool(overlap_ok and changed_ok and bool(match.get("matched", False)))
    if rule_name == "stronger_rgb_distractor_rejected":
        distractor_like = int(evidence.get("distractor_signature_overlap_count", 0)) >= int(distractor_overlap_min or 1)
        return bool(overlap_ok and changed_ok and any_hit and not distractor_like)
    if rule_name == "stronger_rgb_recalibrated_direction_distractor_rejected":
        match = evidence.get("recalibrated_direction_matches", {}).get(str(tolerance_deg), {})
        distractor_like = int(evidence.get("distractor_signature_overlap_count", 0)) >= int(distractor_overlap_min or 1)
        return bool(overlap_ok and changed_ok and bool(match.get("matched", False)) and not distractor_like)
    raise ValueError("Unknown rule_name: {0}".format(rule_name))


def _iter_rule_configs() -> Iterable[Dict[str, Any]]:
    yield {
        "rule_name": "baseline_any_hit",
        "rule_family": "baseline",
        "target_overlap_min": 1,
        "rgb_changed_pixels_min": 0,
        "direction_tolerance_deg": None,
        "distractor_overlap_min": None,
        "uses_old_direction_match": False,
        "uses_recalibrated_direction_match": False,
        "uses_distractor_rejection": False,
    }
    yield {
        "rule_name": "old_direction_matched_as_failure_reference",
        "rule_family": "failure_reference",
        "target_overlap_min": 1,
        "rgb_changed_pixels_min": 0,
        "direction_tolerance_deg": None,
        "distractor_overlap_min": None,
        "uses_old_direction_match": True,
        "uses_recalibrated_direction_match": False,
        "uses_distractor_rejection": False,
    }
    for overlap_min in OVERLAP_MIN_VALUES:
        for pixels_min in CHANGED_PIXELS_MIN_VALUES:
            yield {
                "rule_name": "stronger_rgb_any_hit",
                "rule_family": "stronger_rgb",
                "target_overlap_min": overlap_min,
                "rgb_changed_pixels_min": pixels_min,
                "direction_tolerance_deg": None,
                "distractor_overlap_min": None,
                "uses_old_direction_match": False,
                "uses_recalibrated_direction_match": False,
                "uses_distractor_rejection": False,
            }
    for tolerance in RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES:
        yield {
            "rule_name": "recalibrated_direction_matched",
            "rule_family": "recalibrated_direction",
            "target_overlap_min": 1,
            "rgb_changed_pixels_min": 0,
            "direction_tolerance_deg": tolerance,
            "distractor_overlap_min": None,
            "uses_old_direction_match": False,
            "uses_recalibrated_direction_match": True,
            "uses_distractor_rejection": False,
        }
    for overlap_min in OVERLAP_MIN_VALUES:
        for pixels_min in CHANGED_PIXELS_MIN_VALUES:
            for tolerance in RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES:
                yield {
                    "rule_name": "stronger_rgb_recalibrated_direction",
                    "rule_family": "stronger_rgb_recalibrated_direction",
                    "target_overlap_min": overlap_min,
                    "rgb_changed_pixels_min": pixels_min,
                    "direction_tolerance_deg": tolerance,
                    "distractor_overlap_min": None,
                    "uses_old_direction_match": False,
                    "uses_recalibrated_direction_match": True,
                    "uses_distractor_rejection": False,
                }
    for overlap_min in OVERLAP_MIN_VALUES:
        for pixels_min in CHANGED_PIXELS_MIN_VALUES:
            for distractor_overlap_min in DISTRACTOR_OVERLAP_MIN_VALUES:
                yield {
                    "rule_name": "stronger_rgb_distractor_rejected",
                    "rule_family": "stronger_rgb_distractor_rejected",
                    "target_overlap_min": overlap_min,
                    "rgb_changed_pixels_min": pixels_min,
                    "direction_tolerance_deg": None,
                    "distractor_overlap_min": distractor_overlap_min,
                    "uses_old_direction_match": False,
                    "uses_recalibrated_direction_match": False,
                    "uses_distractor_rejection": True,
                }
    for overlap_min in OVERLAP_MIN_VALUES:
        for pixels_min in CHANGED_PIXELS_MIN_VALUES:
            for tolerance in RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES:
                for distractor_overlap_min in DISTRACTOR_OVERLAP_MIN_VALUES:
                    yield {
                        "rule_name": "stronger_rgb_recalibrated_direction_distractor_rejected",
                        "rule_family": "stronger_rgb_recalibrated_direction_distractor_rejected",
                        "target_overlap_min": overlap_min,
                        "rgb_changed_pixels_min": pixels_min,
                        "direction_tolerance_deg": tolerance,
                        "distractor_overlap_min": distractor_overlap_min,
                        "uses_old_direction_match": False,
                        "uses_recalibrated_direction_match": True,
                        "uses_distractor_rejection": True,
                    }


def _rule_id(config: Dict[str, Any]) -> str:
    parts = [
        str(config["rule_name"]),
        "overlap{0}".format(config.get("target_overlap_min")),
        "px{0}".format(config.get("rgb_changed_pixels_min")),
    ]
    if config.get("direction_tolerance_deg") is not None:
        parts.append("tol{0}".format(config.get("direction_tolerance_deg")))
    if config.get("distractor_overlap_min") is not None:
        parts.append("dist{0}".format(config.get("distractor_overlap_min")))
    return "_".join(parts).replace(".", "p")


def _summarize_rule(rule_config: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_rows = [row for row in rows if row.get("scenario_kind") == "target"]
    distractor_rows = [row for row in rows if row.get("scenario_kind") == "distractor_only"]
    baseline_rows = [row for row in rows if row.get("scenario_kind") == "baseline"]
    calibration_rows = [row for row in rows if row.get("scenario_kind") == "calibration"]

    def _target_hits(distance: float) -> int:
        return sum(1 for row in target_rows if float(row.get("distance_m")) == float(distance) and bool(row.get("candidate_found")))

    def _target_total(distance: float) -> int:
        return sum(1 for row in target_rows if float(row.get("distance_m")) == float(distance))

    target_true_positives = [str(row["scene"]) for row in target_rows if row.get("candidate_found")]
    target_false_negatives = [str(row["scene"]) for row in target_rows if not row.get("candidate_found")]
    distractor_false_positives = [str(row["scene"]) for row in distractor_rows if row.get("candidate_found")]
    distractor_true_negatives = [str(row["scene"]) for row in distractor_rows if not row.get("candidate_found")]
    baseline_false_positives = [str(row["scene"]) for row in baseline_rows if row.get("candidate_found")]
    calibration_true_positive = bool(calibration_rows and calibration_rows[0].get("candidate_found"))
    return {
        "rule_id": _rule_id(rule_config),
        **rule_config,
        "outcome_counts_all_scenes": _count_by(rows, "candidate_outcome"),
        "target_true_positive_count": len(target_true_positives),
        "target_false_negative_count": len(target_false_negatives),
        "distractor_false_positive_count": len(distractor_false_positives),
        "distractor_true_negative_count": len(distractor_true_negatives),
        "baseline_false_positive_count": len(baseline_false_positives),
        "calibration_true_positive": calibration_true_positive,
        "target_true_positive_scenes": target_true_positives,
        "target_false_negative_scenes": target_false_negatives,
        "distractor_false_positive_scenes": distractor_false_positives,
        "distractor_true_negative_scenes": distractor_true_negatives,
        "baseline_false_positive_scenes": baseline_false_positives,
        "target_20m_true_positive_count": _target_hits(20.0),
        "target_20m_total": _target_total(20.0),
        "target_35m_true_positive_count": _target_hits(35.0),
        "target_35m_total": _target_total(35.0),
        "target_50m_true_positive_count": _target_hits(50.0),
        "target_50m_total": _target_total(50.0),
        "target_50m_center_inner_true_positive_count": sum(
            1
            for row in target_rows
            if float(row.get("distance_m")) == 50.0
            and str(row.get("angle_label")) in ("center", "left_inner", "right_inner")
            and bool(row.get("candidate_found"))
        ),
        "target_50m_center_inner_total": sum(
            1
            for row in target_rows
            if float(row.get("distance_m")) == 50.0
            and str(row.get("angle_label")) in ("center", "left_inner", "right_inner")
        ),
    }


def _evaluate_candidate_rules(evidence_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    matrix_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    for rule_config in _iter_rule_configs():
        per_rule_rows: List[Dict[str, Any]] = []
        for evidence in evidence_rows:
            expected_target = bool(evidence.get("expected_target_present_for_audit", False))
            found = _rule_found(
                str(rule_config["rule_name"]),
                evidence,
                overlap_min=int(rule_config.get("target_overlap_min", 1)),
                changed_pixels_min=int(rule_config.get("rgb_changed_pixels_min", 0)),
                tolerance_deg=rule_config.get("direction_tolerance_deg"),
                distractor_overlap_min=rule_config.get("distractor_overlap_min"),
            )
            direction_match = None
            direction_delta = None
            direction_yaw = None
            if rule_config.get("direction_tolerance_deg") is not None:
                direction_data = evidence.get("recalibrated_direction_matches", {}).get(str(rule_config.get("direction_tolerance_deg")), {})
                direction_match = direction_data.get("matched")
                direction_delta = direction_data.get("best_delta_deg")
                direction_yaw = direction_data.get("best_hit_beam_yaw_deg")
            distractor_like = None
            if rule_config.get("distractor_overlap_min") is not None:
                distractor_like = int(evidence.get("distractor_signature_overlap_count", 0)) >= int(rule_config.get("distractor_overlap_min"))
            row = {
                "rule_id": _rule_id(rule_config),
                **rule_config,
                "scene": evidence.get("scene"),
                "scenario_kind": evidence.get("scenario_kind"),
                "is_calibration_scene": evidence.get("is_calibration_scene"),
                "expected_target_present_for_audit": expected_target,
                "distance_m": evidence.get("distance_m"),
                "angle_label": evidence.get("angle_label"),
                "angle_deg": evidence.get("angle_deg"),
                "rgb_signature_overlap_count": evidence.get("rgb_signature_overlap_count"),
                "rgb_changed_pixels": evidence.get("rgb_changed_pixels"),
                "stronger_rgb_target_signature": bool(
                    int(evidence.get("rgb_signature_overlap_count", 0)) >= int(rule_config.get("target_overlap_min", 1))
                    and int(evidence.get("rgb_changed_pixels", 0)) >= int(rule_config.get("rgb_changed_pixels_min", 0))
                ),
                "any_rangefinder_hit": evidence.get("any_rangefinder_hit"),
                "rangefinder_hit_beam_indices": evidence.get("rangefinder_hit_beam_indices"),
                "old_matched_rangefinder_beam_hit": evidence.get("old_matched_rangefinder_beam_hit"),
                "rgb_target_angle_deg": evidence.get("rgb_target_angle_deg"),
                "recalibrated_direction_matched": direction_match,
                "recalibrated_direction_best_delta_deg": direction_delta,
                "recalibrated_direction_best_hit_beam_yaw_deg": direction_yaw,
                "distractor_signature_overlap_count": evidence.get("distractor_signature_overlap_count"),
                "distractor_like": distractor_like,
                "candidate_found": found,
                "candidate_outcome": _outcome(expected_target, found),
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
            }
            matrix_rows.append(row)
            per_rule_rows.append(row)
        summary_rows.append(_summarize_rule(rule_config, per_rule_rows))
    return matrix_rows, summary_rows


def _recommend_rule(summary_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    eligible = [
        row
        for row in summary_rows
        if row.get("rule_name") != "old_direction_matched_as_failure_reference"
        and row.get("target_20m_true_positive_count") == row.get("target_20m_total") == 5
        and row.get("target_35m_true_positive_count") == row.get("target_35m_total") == 5
        and row.get("calibration_true_positive") is True
        and row.get("baseline_false_positive_count") == 0
    ]
    family_priority = {
        "stronger_rgb": 0,
        "stronger_rgb_distractor_rejected": 1,
        "stronger_rgb_recalibrated_direction": 2,
        "stronger_rgb_recalibrated_direction_distractor_rejected": 3,
        "recalibrated_direction": 4,
        "baseline": 5,
    }
    if not eligible:
        eligible = [row for row in summary_rows if row.get("rule_name") != "old_direction_matched_as_failure_reference"]
    ranked = sorted(
        eligible,
        key=lambda row: (
            int(row.get("distractor_false_positive_count", 999)),
            -int(row.get("target_true_positive_count", 0)),
            -int(row.get("target_50m_center_inner_true_positive_count", 0)),
            family_priority.get(str(row.get("rule_family")), 99),
            int(row.get("target_overlap_min", 999)),
            int(row.get("rgb_changed_pixels_min", 999)),
            float(row.get("direction_tolerance_deg") or 999.0),
            int(row.get("distractor_overlap_min") or 999),
        ),
    )
    chosen = dict(ranked[0])
    chosen["recommendation_reason"] = (
        "Selected lowest-FP rule that preserves all 20m and 35m target positives; "
        "ties prefer simpler stronger-RGB rules before direction or distractor rejection."
    )
    chosen["recommended_for_holoocean_rerun"] = True
    return chosen


def _old_direction_failure_reference(summary_rows: List[Dict[str, Any]], evidence_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    old_summary = next(row for row in summary_rows if row.get("rule_name") == "old_direction_matched_as_failure_reference")
    inner_target_failures = [
        {
            "scene": row.get("scene"),
            "distance_m": row.get("distance_m"),
            "angle_label": row.get("angle_label"),
            "old_matched_rangefinder_beam_hit": row.get("old_matched_rangefinder_beam_hit"),
            "source_found": row.get("source_found"),
            "rangefinder_hit_beam_indices": row.get("rangefinder_hit_beam_indices"),
            "rgb_target_angle_deg": row.get("rgb_target_angle_deg"),
        }
        for row in evidence_rows
        if row.get("scenario_kind") == "target"
        and str(row.get("angle_label")) in ("left_inner", "right_inner")
        and bool(row.get("source_found"))
        and not bool(row.get("old_matched_rangefinder_beam_hit"))
    ]
    return {
        "old_direction_rule_summary": old_summary,
        "inner_target_failures_if_old_direction_used": inner_target_failures,
        "inner_target_failure_count": len(inner_target_failures),
        "conclusion": (
            "The 5C-4H matched_rangefinder_beam_hit field is a diagnostic only. "
            "Using it directly as a detection rule would create false negatives for inner-angle true targets."
        ),
    }


def _build_offline_summary(
    recommended: Dict[str, Any],
    summary_rows: List[Dict[str, Any]],
    evidence_meta: Dict[str, Any],
    old_failure: Dict[str, Any],
    started: float,
) -> Dict[str, Any]:
    baseline = next(row for row in summary_rows if row.get("rule_name") == "baseline_any_hit")
    old_direction = next(row for row in summary_rows if row.get("rule_name") == "old_direction_matched_as_failure_reference")
    best_stronger = [
        row
        for row in summary_rows
        if row.get("rule_name") == "stronger_rgb_any_hit"
        and row.get("target_20m_true_positive_count") == 5
        and row.get("target_35m_true_positive_count") == 5
    ]
    best_stronger = sorted(
        best_stronger,
        key=lambda row: (
            int(row.get("distractor_false_positive_count", 999)),
            -int(row.get("target_true_positive_count", 0)),
            int(row.get("target_overlap_min", 999)),
            int(row.get("rgb_changed_pixels_min", 999)),
        ),
    )
    return {
        "phase_name": PHASE_NAME,
        "offline_calibration_completed": True,
        "source_phase_name": SOURCE_PHASE_NAME,
        "source_inputs": {
            "boundary_matrix_json": SOURCE_MATRIX_JSON,
            "scene_results_json": SOURCE_SCENE_RESULTS_JSON,
            "detection_events_json": SOURCE_EVENTS_JSON,
            "rgb_raw_artifacts": os.path.join(SOURCE_VISUALS_DIR, "*_rgb_raw.npy"),
        },
        "scene_results_first_rgb_raw_used": False,
        "raw_rgb_loaded_from_visuals": True,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "rgb_signature_detector": {
            "diff_threshold": evidence_meta.get("diff_threshold"),
            "quantization": evidence_meta.get("quantization"),
            "top_k": evidence_meta.get("top_k"),
            "target_overlap_min_values": OVERLAP_MIN_VALUES,
            "rgb_changed_pixels_min_values": CHANGED_PIXELS_MIN_VALUES,
        },
        "direction_recalibration": {
            "old_matched_rangefinder_beam_hit_used_as_failure_reference_only": True,
            "camera_horizontal_fov_deg": CAMERA_HORIZONTAL_FOV_DEG,
            "fan_yaw_degrees": evidence_meta.get("fan_yaw_degrees"),
            "tolerance_deg_values": RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES,
            "rgb_angle_source": "target-signature-overlap pixel bbox center from raw npy",
        },
        "distractor_signature": {
            "source": "5C-4H distractor_only raw npy signatures",
            "min_scene_frequency": DISTRACTOR_SIGNATURE_MIN_SCENE_FREQUENCY,
            "color_count": evidence_meta.get("distractor_signature_color_count"),
            "overlap_min_values": DISTRACTOR_OVERLAP_MIN_VALUES,
        },
        "baseline_any_hit_summary": baseline,
        "old_direction_match_failure_reference_summary": old_direction,
        "old_direction_inner_target_failure_count": old_failure.get("inner_target_failure_count"),
        "best_stronger_rgb_any_hit_summary": best_stronger[0] if best_stronger else None,
        "recommended_candidate_rule": recommended,
        "candidate_rule_count": len(summary_rows),
        "wall_time_s": float(time.perf_counter() - started),
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    recommended = summary.get("recommended_candidate_rule", {})
    stronger = summary.get("best_stronger_rgb_any_hit_summary") or {}
    baseline = summary.get("baseline_any_hit_summary", {})
    lines = [
        "# Phase 5C-4I-1 Offline Rule Calibration Summary",
        "",
        "- Source Phase: `{0}`".format(summary.get("source_phase_name")),
        "- Raw RGB Source: `visuals/*_rgb_raw.npy`",
        "- scene_results first_rgb_raw used: `{0}`".format(summary.get("scene_results_first_rgb_raw_used")),
        "- Candidate Rule Count: `{0}`".format(summary.get("candidate_rule_count")),
        "- Old Direction Inner Target Failure Count: `{0}`".format(summary.get("old_direction_inner_target_failure_count")),
        "",
        "## Baseline",
        "",
        "- Rule: `baseline_any_hit`",
        "- Target TP/FN: `{0}/{1}`".format(
            baseline.get("target_true_positive_count"),
            baseline.get("target_false_negative_count"),
        ),
        "- Distractor FP/TN: `{0}/{1}`".format(
            baseline.get("distractor_false_positive_count"),
            baseline.get("distractor_true_negative_count"),
        ),
        "",
        "## Best Stronger RGB",
        "",
        "- Rule ID: `{0}`".format(stronger.get("rule_id")),
        "- overlap_min: `{0}`".format(stronger.get("target_overlap_min")),
        "- rgb_changed_pixels_min: `{0}`".format(stronger.get("rgb_changed_pixels_min")),
        "- Target TP/FN: `{0}/{1}`".format(
            stronger.get("target_true_positive_count"),
            stronger.get("target_false_negative_count"),
        ),
        "- 20m TP: `{0}/{1}`".format(stronger.get("target_20m_true_positive_count"), stronger.get("target_20m_total")),
        "- 35m TP: `{0}/{1}`".format(stronger.get("target_35m_true_positive_count"), stronger.get("target_35m_total")),
        "- 50m center/inner TP: `{0}/{1}`".format(
            stronger.get("target_50m_center_inner_true_positive_count"),
            stronger.get("target_50m_center_inner_total"),
        ),
        "- Distractor FP/TN: `{0}/{1}`".format(
            stronger.get("distractor_false_positive_count"),
            stronger.get("distractor_true_negative_count"),
        ),
        "- New target false negatives: `{0}`".format(stronger.get("target_false_negative_scenes")),
        "",
        "## Recommended Rule",
        "",
        "- Rule ID: `{0}`".format(recommended.get("rule_id")),
        "- Rule Name: `{0}`".format(recommended.get("rule_name")),
        "- overlap_min: `{0}`".format(recommended.get("target_overlap_min")),
        "- rgb_changed_pixels_min: `{0}`".format(recommended.get("rgb_changed_pixels_min")),
        "- direction_tolerance_deg: `{0}`".format(recommended.get("direction_tolerance_deg")),
        "- distractor_overlap_min: `{0}`".format(recommended.get("distractor_overlap_min")),
        "- Target TP/FN: `{0}/{1}`".format(
            recommended.get("target_true_positive_count"),
            recommended.get("target_false_negative_count"),
        ),
        "- Distractor FP/TN: `{0}/{1}`".format(
            recommended.get("distractor_false_positive_count"),
            recommended.get("distractor_true_negative_count"),
        ),
        "- 20m target TP: `{0}/{1}`".format(recommended.get("target_20m_true_positive_count"), recommended.get("target_20m_total")),
        "- 35m target TP: `{0}/{1}`".format(recommended.get("target_35m_true_positive_count"), recommended.get("target_35m_total")),
        "- 50m center/inner target TP: `{0}/{1}`".format(
            recommended.get("target_50m_center_inner_true_positive_count"),
            recommended.get("target_50m_center_inner_total"),
        ),
        "- Target false negatives: `{0}`".format(recommended.get("target_false_negative_scenes")),
        "",
        "## Conclusion",
        "",
        "The offline recommendation prioritizes stronger RGB overlap thresholding. "
        "The old 5C-4H direction flag is retained only as a failure reference, because direct use would reject inner-angle true targets.",
    ]
    return "\n".join(lines) + "\n"


def _build_old_direction_md(old_failure: Dict[str, Any]) -> str:
    lines = [
        "# Old Direction Match Failure Reference",
        "",
        "The 5C-4H `matched_rangefinder_beam_hit` field is diagnostic only.",
        "",
        "- Inner target failures if old direction field is used: `{0}`".format(old_failure.get("inner_target_failure_count")),
        "",
        "| Scene | Distance | Angle | Old Matched | Source Found | Hit Beams | RGB Target Angle |",
        "|---|---:|---|---:|---:|---|---:|",
    ]
    for row in old_failure.get("inner_target_failures_if_old_direction_used", []):
        lines.append(
            "| `{0}` | `{1}` | `{2}` | `{3}` | `{4}` | `{5}` | `{6}` |".format(
                row.get("scene"),
                row.get("distance_m"),
                row.get("angle_label"),
                row.get("old_matched_rangefinder_beam_hit"),
                row.get("source_found"),
                row.get("rangefinder_hit_beam_indices"),
                None if row.get("rgb_target_angle_deg") is None else round(float(row.get("rgb_target_angle_deg")), 3),
            )
        )
    lines.extend(["", str(old_failure.get("conclusion"))])
    return "\n".join(lines) + "\n"


def run_offline_calibration() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_git_status = _run_git_status()
    required_inputs = [SOURCE_MATRIX_JSON, SOURCE_SCENE_RESULTS_JSON, SOURCE_EVENTS_JSON, SOURCE_CONFIG_JSON]
    missing = [path for path in required_inputs if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError("Missing required 5C-4H inputs: {0}".format(missing))
    source_matrix = _load_json(SOURCE_MATRIX_JSON)
    source_scene_results = _load_json(SOURCE_SCENE_RESULTS_JSON)
    source_events = _load_json(SOURCE_EVENTS_JSON)
    source_config = _load_json(SOURCE_CONFIG_JSON)
    if not isinstance(source_matrix, list):
        raise TypeError("source matrix must be a list")
    if not isinstance(source_scene_results, dict):
        raise TypeError("source scene_results must be a dict")
    if not isinstance(source_events, list):
        raise TypeError("source detection_events must be a list")

    raw_paths = [_rgb_raw_path(str(row["scene"])) for row in source_matrix]
    missing_raw = [path for path in raw_paths if not os.path.exists(path)]
    if missing_raw:
        raise FileNotFoundError("Missing raw RGB npy files: {0}".format(missing_raw))

    scene_results_has_first_rgb_raw = any(
        isinstance(value, dict) and "first_rgb_raw" in value for value in source_scene_results.values()
    )

    config = {
        "phase_name": PHASE_NAME,
        "source_phase_name": SOURCE_PHASE_NAME,
        "source_inputs": {
            "boundary_matrix_json": SOURCE_MATRIX_JSON,
            "scene_results_json": SOURCE_SCENE_RESULTS_JSON,
            "detection_events_json": SOURCE_EVENTS_JSON,
            "config_json": SOURCE_CONFIG_JSON,
            "rgb_raw_artifacts": os.path.join(SOURCE_VISUALS_DIR, "*_rgb_raw.npy"),
        },
        "scene_results_has_first_rgb_raw": scene_results_has_first_rgb_raw,
        "scene_results_first_rgb_raw_used": False,
        "raw_rgb_loaded_from_visuals": True,
        "candidate_scans": {
            "target_overlap_min_values": OVERLAP_MIN_VALUES,
            "rgb_changed_pixels_min_values": CHANGED_PIXELS_MIN_VALUES,
            "recalibrated_direction_tolerance_deg_values": RECALIBRATED_DIRECTION_TOLERANCE_DEG_VALUES,
            "distractor_overlap_min_values": DISTRACTOR_OVERLAP_MIN_VALUES,
        },
        "camera_horizontal_fov_deg": CAMERA_HORIZONTAL_FOV_DEG,
    }
    _save_json(CONFIG_JSON, config)

    evidence_rows, evidence_meta = _build_recomputed_evidence(source_matrix, source_config)
    # Lightweight consistency check against the source matrix.
    mismatches = []
    for row in evidence_rows:
        if int(row.get("rgb_signature_overlap_count", -1)) != int(row.get("source_rgb_overlap_count", -2)):
            mismatches.append({"scene": row.get("scene"), "field": "rgb_signature_overlap_count"})
        if int(row.get("rgb_changed_pixels", -1)) != int(row.get("source_rgb_changed_pixels", -2)):
            mismatches.append({"scene": row.get("scene"), "field": "rgb_changed_pixels"})
    evidence_meta["recomputed_vs_source_mismatches"] = mismatches
    evidence_meta["recomputed_matches_source_matrix"] = len(mismatches) == 0
    _save_json(RECOMPUTED_EVIDENCE_JSON, {"meta": evidence_meta, "rows": evidence_rows})

    matrix_rows, summary_rows = _evaluate_candidate_rules(evidence_rows)
    recommended = _recommend_rule(summary_rows)
    old_failure = _old_direction_failure_reference(summary_rows, evidence_rows)
    offline_summary = _build_offline_summary(recommended, summary_rows, evidence_meta, old_failure, started)

    _save_json(RULE_MATRIX_JSON, matrix_rows)
    _save_csv(RULE_MATRIX_CSV, matrix_rows)
    _save_json(RULE_SUMMARY_JSON, {"phase_name": PHASE_NAME, "candidate_rule_summaries": summary_rows, "offline_summary": offline_summary})
    _save_json(RECOMMENDED_RULE_JSON, recommended)
    _save_json(OLD_DIRECTION_FAILURE_JSON, old_failure)

    os.makedirs(os.path.dirname(OFFLINE_SUMMARY_MD), exist_ok=True)
    with open(OFFLINE_SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(offline_summary))
    with open(OLD_DIRECTION_FAILURE_MD, "w", encoding="utf-8") as f:
        f.write(_build_old_direction_md(old_failure))

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
        "Phase 5C-4I-1 offline calibration finished: recommended={0}, target_tp={1}, distractor_fp={2}".format(
            recommended.get("rule_id"),
            recommended.get("target_true_positive_count"),
            recommended.get("distractor_false_positive_count"),
        )
    )
    return offline_summary


def main() -> None:
    run_offline_calibration()


if __name__ == "__main__":
    main()
