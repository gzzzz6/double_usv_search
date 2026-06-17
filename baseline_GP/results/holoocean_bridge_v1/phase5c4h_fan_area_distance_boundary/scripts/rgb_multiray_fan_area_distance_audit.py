"""Audit for Phase 5C-4H fan-area distance boundary probe."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4h_fan_area_distance_boundary"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "rgb_multiray_fan_area_distance_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "rgb_multiray_fan_area_distance_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_config.json")
SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_scene_results.json")
EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_detection_events.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_tick_trace.csv")
MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_boundary_matrix.json")
MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_boundary_matrix.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_area_distance_summary.md")
OVERVIEW_PNG = os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_area_distance_overview.png")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_area_distance_audit_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "rgb_multiray_fan_area_distance_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "rgb_multiray_fan_area_distance_py_compile_holo.txt")


def _load(path: str, checks: Dict[str, bool], key: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        checks[key] = True
        return data
    except Exception:
        checks[key] = False
        return None


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("JSON saved to: {0}".format(path))


def _log_ok(path: str, marker: str) -> bool:
    text = _read(path)
    return bool(marker in text and "Traceback" not in text and "SyntaxError" not in text)


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4H Fan-Area Distance Boundary Audit Summary",
        "",
        "- Tested Distances: `{0}`".format(metrics.get("tested_distances_m")),
        "- Fan Reliable Distances: `{0}`".format(metrics.get("fan_reliable_distances_m")),
        "- Max Effective By Angle: `{0}`".format(metrics.get("max_effective_distance_by_angle_m")),
        "- Distractor False Positives: `{0}`".format(metrics.get("distractor_false_positive_scenes")),
        "- Direction Mismatch Count: `{0}`".format(metrics.get("direction_mismatch_count")),
        "- All Passed: `{0}`".format(all(checks.values())),
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
    for key in sorted(checks):
        lines.append("| `{0}` | `{1}` |".format(key, checks[key]))
    return "\n".join(lines) + "\n"


def main() -> None:
    checks: Dict[str, bool] = {}
    required_paths = [
        PROBE_SCRIPT,
        AUDIT_SCRIPT,
        CONFIG_JSON,
        SCENE_RESULTS_JSON,
        EVENTS_JSON,
        TICK_TRACE_JSON,
        TICK_TRACE_CSV,
        MATRIX_JSON,
        MATRIX_CSV,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        OVERVIEW_PNG,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    scene_results = _load(SCENE_RESULTS_JSON, checks, "scene_results_parse_ok")
    events = _load(EVENTS_JSON, checks, "events_parse_ok")
    matrix = _load(MATRIX_JSON, checks, "matrix_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")
    if not isinstance(config, dict):
        config = {}
    if not isinstance(scene_results, dict):
        scene_results = {}
    if not isinstance(events, list):
        events = []
    if not isinstance(matrix, list):
        matrix = []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    expected_distances = [20.0, 35.0, 50.0]
    expected_distractor_distances = [20.0, 50.0]
    expected_angles = ["left_outer", "left_inner", "center", "right_inner", "right_outer"]
    target_rows = [row for row in matrix if row.get("scenario_kind") == "target"]
    distractor_rows = [row for row in matrix if row.get("scenario_kind") == "distractor_only"]
    calibration_rows = [row for row in matrix if bool(row.get("is_calibration_scene", False))]

    target_pairs = sorted((float(row.get("distance_m")), str(row.get("angle_label"))) for row in target_rows)
    expected_target_pairs = sorted((distance, angle) for distance in expected_distances for angle in expected_angles)
    distractor_pairs = sorted((float(row.get("distance_m")), str(row.get("angle_label"))) for row in distractor_rows)
    expected_distractor_pairs = sorted((distance, angle) for distance in expected_distractor_distances for angle in expected_angles)

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME and git_status.get("phase_name") == PHASE_NAME
    checks["scene_count_matches"] = len(matrix) == 27 and len(events) == 27 and len(scene_results) == 27 and int(summary.get("scene_count", -1)) == 27
    checks["target_matrix_complete"] = target_pairs == expected_target_pairs and summary.get("tested_distances_m") == expected_distances
    checks["distractor_matrix_complete"] = distractor_pairs == expected_distractor_pairs and summary.get("distractor_tested_distances_m") == expected_distractor_distances
    checks["calibration_scene_present"] = len(calibration_rows) == 1 and float(calibration_rows[0].get("distance_m")) == 10.0
    checks["fan_angles_exact"] = [item.get("label") for item in config.get("fan_test_angles", [])] == expected_angles
    checks["truth_flags_false"] = (
        summary.get("truth_used_for_detection") is False
        and summary.get("actor_truth_used_for_detection") is False
        and summary.get("target_truth_used_for_detection") is False
        and all(event.get("truth_used_for_detection") is False for event in events)
        and all(event.get("actor_truth_used_for_detection") is False for event in events)
        and all(event.get("target_truth_used_for_detection") is False for event in events)
    )
    checks["direction_matching_diagnostic_only"] = (
        summary.get("direction_matching_used_for_detection") is False
        and summary.get("matched_rangefinder_beam_hit_is_diagnostic_only") is True
        and all(row.get("found") == (bool(row.get("rgb_has_target_signature")) and bool(row.get("any_rangefinder_hit"))) for row in matrix)
    )
    checks["rgb_logic_preserved"] = (
        summary.get("rgb_signature_logic_matches_5c4c_5c4d_5c4e") is True
        and config.get("rgb_signature_detector", {}).get("diff_threshold") == 28.0
        and config.get("rgb_signature_detector", {}).get("quantization") == 32
        and config.get("rgb_signature_detector", {}).get("top_k") == 24
        and config.get("rgb_signature_detector", {}).get("target_overlap_min") == 1
    )
    checks["rangefinder_fan_configured"] = summary.get("rangefinder_mode") == "yaw_rotated_single_ray_fan" and int(summary.get("horizontal_fan_sensor_count", 0)) == 9
    checks["all_scene_launch_ok"] = all(bool(v.get("launch_ok", False)) for v in scene_results.values())
    checks["all_scenes_rgb_output"] = all(bool(v.get("rgb_stats", {}).get("present", False)) for v in scene_results.values())
    checks["all_scenes_rangefinder_output"] = all(bool(v.get("rangefinder_summary", {}).get("present", False)) for v in scene_results.values())
    checks["matrix_has_required_fields"] = all(
        all(
            key in row
            for key in (
                "rgb_has_target_signature",
                "any_rangefinder_hit",
                "found",
                "rgb_changed_pixels",
                "rgb_bbox",
                "rangefinder_hit_beam_indices",
                "rangefinder_hit_sectors",
                "rangefinder_min_positive_range_m",
                "matched_rangefinder_beam_hit",
            )
        )
        for row in matrix
    )
    checks["test_scenes_have_images"] = all(bool(row.get("rgb_artifact")) and os.path.exists(str(row.get("rgb_artifact"))) for row in target_rows + distractor_rows)
    checks["summary_boundary_present"] = (
        "max_effective_distance_by_angle_m" in summary
        and "fan_reliable_distances_m" in summary
        and "max_fan_reliable_distance_m" in summary
        and "distractor_false_positive_scenes" in summary
    )
    checks["overview_visual_exists"] = os.path.exists(OVERVIEW_PNG) and os.path.getsize(OVERVIEW_PNG) > 0
    checks["git_changes_limited_to_phase"] = git_status.get("outside_phase_new_or_changed") == []
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")
    checks["compiled_expected_scripts"] = (
        "rgb_multiray_fan_area_distance_probe.py" in _read(BASE_COMPILE_LOG)
        and "rgb_multiray_fan_area_distance_audit.py" in _read(BASE_COMPILE_LOG)
        and "rgb_multiray_fan_area_distance_probe.py" in _read(HOLO_COMPILE_LOG)
        and "rgb_multiray_fan_area_distance_audit.py" in _read(HOLO_COMPILE_LOG)
    )

    metrics = {
        "phase_name": PHASE_NAME,
        "tested_distances_m": summary.get("tested_distances_m"),
        "fan_reliable_distances_m": summary.get("fan_reliable_distances_m"),
        "max_fan_reliable_distance_m": summary.get("max_fan_reliable_distance_m"),
        "max_effective_distance_by_angle_m": summary.get("max_effective_distance_by_angle_m"),
        "distractor_false_positive_scenes": summary.get("distractor_false_positive_scenes"),
        "direction_mismatch_count": summary.get("direction_mismatch_count"),
        "all_passed": all(checks.values()),
    }
    audit = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, audit)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("Audit summary saved to: {0}".format(AUDIT_MD))
    print("Phase 5C-4H audit finished: all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()
