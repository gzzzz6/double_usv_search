"""Audit for Phase 5C-4E RGB + multi-ray RangeFinder fan test."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4e_rgb_multiray_rangefinder_fan_boundary"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "rgb_multiray_rangefinder_fan_probe.py"))
AUDIT_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "rgb_multiray_rangefinder_fan_audit.py"))
CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_tick_trace.csv"))
BOUNDARY_MATRIX_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_boundary_matrix.json"))
BOUNDARY_MATRIX_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_boundary_matrix.csv"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_summary.md"))
OVERVIEW_PNG = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_overview.png"))
AUDIT_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_multiray_fan_audit.json"))
AUDIT_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_multiray_fan_audit_summary.md"))
BASE_COMPILE_LOG = os.path.normpath(os.path.join(PHASE_DIR, "logs", "rgb_multiray_fan_py_compile_base.txt"))
HOLO_COMPILE_LOG = os.path.normpath(os.path.join(PHASE_DIR, "logs", "rgb_multiray_fan_py_compile_holo.txt"))


def _safe_load(path: str, checks: Dict[str, bool], key: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        checks[key] = True
        return data
    except Exception:
        checks[key] = False
        return None


def _read_text(path: str) -> str:
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


def _all_paths_exist(paths: List[str]) -> bool:
    return all(os.path.exists(path) for path in paths)


def _log_ok(path: str, marker: str) -> bool:
    text = _read_text(path)
    return bool(marker in text and "Traceback" not in text and "SyntaxError" not in text)


def _events_by_scene(events: Any) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not isinstance(events, list):
        return result
    for event in events:
        if isinstance(event, dict) and "scene" in event:
            result[str(event["scene"])] = event
    return result


def _build_audit_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4E RGB + Multi-Ray RangeFinder Fan Audit Summary",
        "",
        "## Metrics",
        "- Scene Count: `{0}`".format(metrics.get("scene_count")),
        "- Any-Hit Outcomes: `{0}`".format(metrics.get("outcome_counts_any_hit")),
        "- Aligned-Hit Outcomes: `{0}`".format(metrics.get("outcome_counts_aligned")),
        "- Left/Right Any Fixed: `{0}`".format(metrics.get("left_right_any_hit_fixed")),
        "- Left/Right Aligned Fixed: `{0}`".format(metrics.get("left_right_aligned_hit_fixed")),
        "- Boundary Conclusion: `{0}`".format(metrics.get("boundary_conclusion")),
        "- All Passed: `{0}`".format(all(checks.values())),
        "",
        "## Checks",
        "| Check | Passed |",
        "|---|---|",
    ]
    for key in sorted(checks):
        lines.append("| `{0}` | `{1}` |".format(key, checks[key]))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    checks: Dict[str, bool] = {}
    required_paths = [
        PROBE_SCRIPT,
        AUDIT_SCRIPT,
        CONFIG_JSON,
        SCENE_RESULTS_JSON,
        DETECTION_EVENTS_JSON,
        TICK_TRACE_JSON,
        TICK_TRACE_CSV,
        BOUNDARY_MATRIX_JSON,
        BOUNDARY_MATRIX_CSV,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        OVERVIEW_PNG,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = _all_paths_exist(required_paths)

    config = _safe_load(CONFIG_JSON, checks, "config_json_parse_ok")
    scene_results = _safe_load(SCENE_RESULTS_JSON, checks, "scene_results_json_parse_ok")
    events = _safe_load(DETECTION_EVENTS_JSON, checks, "detection_events_json_parse_ok")
    matrix = _safe_load(BOUNDARY_MATRIX_JSON, checks, "boundary_matrix_json_parse_ok")
    summary = _safe_load(SUMMARY_JSON, checks, "summary_json_parse_ok")
    git_status = _safe_load(GIT_STATUS_JSON, checks, "git_status_json_parse_ok")

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

    probe_source = _read_text(PROBE_SCRIPT)
    audit_source = _read_text(AUDIT_SCRIPT)
    events_by_scene = _events_by_scene(events)
    scene_names = [str(scene.get("name")) for scene in config.get("scenes", []) if isinstance(scene, dict)]
    scene_set = set(scene_names)
    matrix_scene_set = {str(row.get("scene")) for row in matrix}

    checks["phase_name_matches"] = (
        config.get("phase_name") == PHASE_NAME
        and summary.get("phase_name") == PHASE_NAME
        and git_status.get("phase_name") == PHASE_NAME
    )
    checks["scene_count_matches"] = (
        len(scene_names) >= 15
        and len(events) == len(scene_names)
        and len(matrix) == len(scene_names)
        and set(events_by_scene.keys()) == scene_set
        and matrix_scene_set == scene_set
        and int(summary.get("scene_count", -1)) == len(scene_names)
    )
    checks["required_named_scenes_present"] = {
        "baseline",
        "target_front_center_near",
        "target_left_offset_near",
        "target_right_offset_near",
        "target_left_fov_edge_near",
        "target_right_fov_edge_near",
        "target_front_center_mid",
        "target_front_center_far",
        "distractor_only_center",
        "distractor_only_left",
        "distractor_only_right",
        "target_left_with_distractor_right",
        "target_right_with_distractor_left",
        "target_center_with_side_distractor",
        "distractor_occludes_target",
    }.issubset(scene_set)
    checks["multiray_configured"] = (
        config.get("rangefinder_mode") == "yaw_rotated_single_ray_fan"
        and int(config.get("rangefinder_laser_count", 0)) == 9
        and float(config.get("rangefinder_laser_angle", 0.0)) == 60.0
        and int(config.get("horizontal_fan_sensor_count", 0)) == 9
        and config.get("native_multiray_diagnostic_enabled") is True
        and summary.get("rangefinder_mode") == "yaw_rotated_single_ray_fan"
        and int(summary.get("rangefinder_laser_count", 0)) == 9
        and float(summary.get("rangefinder_laser_angle", 0.0)) == 60.0
        and int(summary.get("horizontal_fan_sensor_count", 0)) == 9
        and summary.get("native_multiray_diagnostic_enabled") is True
        and '"LaserCount": RANGEFINDER_LASER_COUNT' in probe_source
        and '"LaserAngle": RANGEFINDER_LASER_ANGLE' in probe_source
        and "FAN_YAW_DEGREES" in probe_source
    )
    checks["rgb_signature_logic_preserved"] = (
        config.get("rgb_signature_logic_matches_5c4c_5c4d") is True
        and summary.get("rgb_signature_logic_matches_5c4c_5c4d") is True
        and config.get("rgb_signature_detector", {}).get("diff_threshold") == 28.0
        and config.get("rgb_signature_detector", {}).get("quantization") == 32
        and config.get("rgb_signature_detector", {}).get("top_k") == 24
        and config.get("rgb_signature_detector", {}).get("target_overlap_min") == 1
    )
    checks["two_rules_evaluated"] = (
        "any_hit" in config.get("rules_evaluated", {})
        and "aligned_hit" in config.get("rules_evaluated", {})
        and "found_any_hit" in probe_source
        and "found_aligned" in probe_source
        and "matched_rangefinder_beam_hit" in probe_source
    )
    checks["perception_sensors_exact"] = (
        config.get("perception_sensors") == ["RGBCamera", "RangeFinderSensor"]
        and summary.get("perception_sensors") == ["RGBCamera", "RangeFinderSensor"]
    )
    checks["semantic_not_used_for_detection"] = (
        config.get("semantic_sensor_used_for_detection") is False
        and summary.get("semantic_sensor_used_for_detection") is False
        and "SemanticSegmentationCamera" not in probe_source
    )
    checks["sonar_not_used"] = (
        config.get("sonar_used") is False
        and summary.get("sonar_used") is False
        and "Sonar" not in probe_source
    )
    checks["truth_flags_false"] = (
        config.get("truth_used_for_detection") is False
        and config.get("actor_truth_used_for_detection") is False
        and config.get("target_truth_used_for_detection") is False
        and summary.get("truth_used_for_detection") is False
        and summary.get("actor_truth_used_for_detection") is False
        and summary.get("target_truth_used_for_detection") is False
        and all(event.get("truth_used_for_detection") is False for event in events)
        and all(event.get("actor_truth_used_for_detection") is False for event in events)
        and all(event.get("target_truth_used_for_detection") is False for event in events)
    )
    checks["source_uses_env_act_tick"] = "env.act(" in probe_source and "env.tick(" in probe_source
    checks["source_does_not_use_env_step"] = "env.step(" not in probe_source
    checks["source_does_not_call_baseline_detect_targets"] = "detect_targets(" not in probe_source
    checks["no_core_runtime_imports"] = "marine_knownmap_runtime" not in probe_source and "core_search_policy" not in probe_source
    checks["event_has_required_fields"] = all(
        all(
            key in event
            for key in (
                "rgb_has_target_signature",
                "rgb_signature_bbox_xyxy",
                "rgb_signature_sector",
                "rangefinder_raw_beams",
                "rangefinder_hit_beam_indices",
                "rangefinder_hit_sectors",
                "any_rangefinder_hit",
                "matched_rangefinder_beam_hit",
                "found_any_hit",
                "found_aligned",
                "outcome_any_hit",
                "outcome_aligned",
            )
        )
        for event in events
    )
    checks["matrix_has_required_fields"] = all(
        all(
            key in row
            for key in (
                "rgb_has_target_signature",
                "rgb_signature_bbox_xyxy",
                "rgb_signature_sector",
                "rangefinder_raw_beams",
                "rangefinder_hit_beam_indices",
                "rangefinder_hit_sectors",
                "any_rangefinder_hit",
                "matched_rangefinder_beam_hit",
                "found_any_hit",
                "found_aligned",
                "outcome_any_hit",
                "outcome_aligned",
            )
        )
        for row in matrix
    )
    checks["found_rules_applied_all_events"] = all(
        bool(event.get("found_any_hit")) == bool(event.get("rgb_has_target_signature") and event.get("any_rangefinder_hit"))
        and bool(event.get("found_aligned")) == bool(event.get("rgb_has_target_signature") and event.get("matched_rangefinder_beam_hit"))
        for event in events
    )
    checks["rangefinder_not_identity_source"] = all(
        event.get("sensor_evidence", {}).get("RangeFinderSensor", {}).get("identity_supported") is False
        for event in events
    )
    checks["native_multiray_diagnostic_recorded"] = (
        summary.get("native_multiray_all_no_hit_observed") in (True, False)
        and "LaserAngle as elevation" in str(summary.get("native_multiray_laser_angle_semantics", ""))
        and all("NativeMultiRayDiagnostic" in event.get("sensor_evidence", {}) for event in events)
    )
    checks["observed_beam_arrays_multiray"] = all(
        isinstance(row.get("rangefinder_raw_beams"), list) and len(row.get("rangefinder_raw_beams")) == 9
        for row in matrix
    )
    checks["all_scene_launch_ok"] = all(bool(v.get("launch_ok", False)) for v in scene_results.values())
    checks["all_scenes_rgb_output"] = all(bool(v.get("rgb_stats", {}).get("present", False)) for v in scene_results.values())
    checks["all_scenes_rangefinder_output"] = all(bool(v.get("rangefinder_summary", {}).get("present", False)) for v in scene_results.values())
    checks["each_scene_has_rgb_artifact"] = all(
        bool(row.get("rgb_artifact")) and os.path.exists(str(row.get("rgb_artifact")))
        for row in matrix
    )
    checks["coverage_positions"] = {"center", "left_offset", "right_offset", "left_fov_edge", "right_fov_edge"}.issubset(
        {str(row.get("target_position")) for row in matrix}
    )
    checks["coverage_distances"] = {"near_10m", "mid_30m", "far_70m"}.issubset({str(row.get("target_distance")) for row in matrix})
    checks["coverage_distractors"] = {
        "none",
        "distractor_only_center",
        "distractor_only_left",
        "distractor_only_right",
        "target_left_distractor_right",
        "target_right_distractor_left",
        "side_distractor",
        "occluding_distractor",
    }.issubset({str(row.get("distractor_condition")) for row in matrix})
    checks["left_right_any_result_recorded"] = summary.get("left_right_any_hit_fixed") in (True, False)
    checks["left_right_aligned_result_recorded"] = summary.get("left_right_aligned_hit_fixed") in (True, False)
    checks["false_positive_lists_present"] = (
        isinstance(summary.get("any_hit_false_positive_scenes"), list)
        and isinstance(summary.get("aligned_hit_false_positive_scenes"), list)
        and isinstance(summary.get("any_hit_distractor_only_false_positive_scenes"), list)
        and isinstance(summary.get("aligned_hit_distractor_only_false_positive_scenes"), list)
    )
    checks["outcome_counts_present"] = bool(summary.get("outcome_counts_any_hit")) and bool(summary.get("outcome_counts_aligned"))
    checks["boundary_conclusion_present"] = bool(summary.get("boundary_conclusion"))
    checks["overview_visual_exists"] = os.path.exists(OVERVIEW_PNG) and os.path.getsize(OVERVIEW_PNG) > 0
    checks["git_changes_limited_to_phase"] = git_status.get("outside_phase_new_or_changed") == []
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")
    checks["compiled_expected_scripts"] = (
        "rgb_multiray_rangefinder_fan_probe.py" in _read_text(BASE_COMPILE_LOG)
        and "rgb_multiray_rangefinder_fan_audit.py" in _read_text(BASE_COMPILE_LOG)
        and "rgb_multiray_rangefinder_fan_probe.py" in _read_text(HOLO_COMPILE_LOG)
        and "rgb_multiray_rangefinder_fan_audit.py" in _read_text(HOLO_COMPILE_LOG)
    )
    checks["audit_source_readable"] = bool(audit_source)

    metrics = {
        "phase_name": PHASE_NAME,
        "scene_count": summary.get("scene_count"),
        "outcome_counts_any_hit": summary.get("outcome_counts_any_hit"),
        "outcome_counts_aligned": summary.get("outcome_counts_aligned"),
        "left_right_any_hit_fixed": summary.get("left_right_any_hit_fixed"),
        "left_right_aligned_hit_fixed": summary.get("left_right_aligned_hit_fixed"),
        "boundary_conclusion": summary.get("boundary_conclusion"),
        "all_passed": all(checks.values()),
    }
    audit = {
        "phase_name": PHASE_NAME,
        "checks": checks,
        "metrics": metrics,
        "all_passed": all(checks.values()),
    }
    _save_json(AUDIT_JSON, audit)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_audit_md(checks, metrics))
    print("Audit summary saved to: {0}".format(AUDIT_MD))
    print("Phase 5C-4E audit finished: all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()
