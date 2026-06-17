"""Audit for Phase 5C-4G far-distance boundary probe."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4g_front_far_distance_boundary"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "rgb_multiray_front_far_distance_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "rgb_multiray_front_far_distance_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_config.json")
SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_scene_results.json")
EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_detection_events.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_tick_trace.csv")
MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_matrix.json")
MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_matrix.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "rgb_multiray_front_far_distance_summary.md")
OVERVIEW_PNG = os.path.join(PHASE_DIR, "reports", "rgb_multiray_front_far_distance_overview.png")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "rgb_multiray_front_far_distance_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "rgb_multiray_front_far_distance_audit_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "rgb_multiray_front_far_distance_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "rgb_multiray_front_far_distance_py_compile_holo.txt")


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
        "# Phase 5C-4G Far-Distance Boundary Audit Summary",
        "",
        "- Tested Distances: `{0}`".format(metrics.get("tested_distances_m")),
        "- Effective Distances: `{0}`".format(metrics.get("effective_distances_m")),
        "- Failed Distances: `{0}`".format(metrics.get("failed_distances_m")),
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

    expected_distances = [35.0, 40.0, 45.0, 50.0]
    target_rows = [row for row in matrix if row.get("distance_m") is not None and not bool(row.get("is_calibration_scene", False))]
    calibration_rows = [row for row in matrix if bool(row.get("is_calibration_scene", False))]
    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME and git_status.get("phase_name") == PHASE_NAME
    checks["distance_set_exact"] = sorted(float(row.get("distance_m")) for row in target_rows) == expected_distances and summary.get("tested_distances_m") == expected_distances
    checks["calibration_scene_present"] = len(calibration_rows) == 1 and float(calibration_rows[0].get("distance_m")) == 10.0
    checks["scene_count_matches"] = len(matrix) == 6 and len(events) == 6 and len(scene_results) == 6 and int(summary.get("scene_count", -1)) == 6
    checks["truth_flags_false"] = (
        summary.get("truth_used_for_detection") is False
        and summary.get("actor_truth_used_for_detection") is False
        and summary.get("target_truth_used_for_detection") is False
        and all(event.get("truth_used_for_detection") is False for event in events)
        and all(event.get("actor_truth_used_for_detection") is False for event in events)
        and all(event.get("target_truth_used_for_detection") is False for event in events)
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
        all(key in row for key in ("distance_m", "rgb_has_target_signature", "any_rangefinder_hit", "found", "outcome", "rangefinder_raw_beams", "rangefinder_hit_beam_indices", "rgb_artifact"))
        for row in matrix
    )
    checks["each_target_scene_has_image"] = all(bool(row.get("rgb_artifact")) and os.path.exists(str(row.get("rgb_artifact"))) for row in target_rows)
    checks["summary_boundary_present"] = "max_tested_effective_distance_m" in summary and "first_tested_failure_distance_m" in summary and "boundary_conclusion" in summary
    checks["overview_visual_exists"] = os.path.exists(OVERVIEW_PNG) and os.path.getsize(OVERVIEW_PNG) > 0
    checks["git_changes_limited_to_phase"] = git_status.get("outside_phase_new_or_changed") == []
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")
    checks["compiled_expected_scripts"] = (
        "rgb_multiray_front_far_distance_probe.py" in _read(BASE_COMPILE_LOG)
        and "rgb_multiray_front_far_distance_audit.py" in _read(BASE_COMPILE_LOG)
        and "rgb_multiray_front_far_distance_probe.py" in _read(HOLO_COMPILE_LOG)
        and "rgb_multiray_front_far_distance_audit.py" in _read(HOLO_COMPILE_LOG)
    )

    metrics = {
        "phase_name": PHASE_NAME,
        "tested_distances_m": summary.get("tested_distances_m"),
        "effective_distances_m": summary.get("effective_distances_m"),
        "failed_distances_m": summary.get("failed_distances_m"),
        "max_tested_effective_distance_m": summary.get("max_tested_effective_distance_m"),
        "first_tested_failure_distance_m": summary.get("first_tested_failure_distance_m"),
        "all_passed": all(checks.values()),
    }
    audit = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, audit)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("Audit summary saved to: {0}".format(AUDIT_MD))
    print("Phase 5C-4G audit finished: all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()
