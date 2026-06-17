"""Audit for Phase 5C-4I direction/distractor calibration."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4i_direction_matched_distractor_rejection_calibration"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SOURCE_PHASE_NAME = "phase5c4h_fan_area_distance_boundary"
SOURCE_PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_PHASE_NAME))

OFFLINE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "direction_matched_distractor_rejection_offline_calibration.py")
VALIDATION_SCRIPT = os.path.join(PHASE_DIR, "scripts", "direction_matched_distractor_rejection_validation_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "direction_matched_distractor_rejection_audit.py")

OFFLINE_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "offline_rule_calibration_config.json")
RECOMPUTED_EVIDENCE_JSON = os.path.join(PHASE_DIR, "manifests", "recomputed_rgb_evidence.json")
CANDIDATE_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "candidate_rule_matrix.json")
CANDIDATE_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "candidate_rule_matrix.csv")
CANDIDATE_RULE_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "candidate_rule_summary.json")
RECOMMENDED_RULE_JSON = os.path.join(PHASE_DIR, "manifests", "recommended_candidate_rule.json")
OLD_DIRECTION_FAILURE_JSON = os.path.join(PHASE_DIR, "manifests", "old_direction_match_failure_reference.json")
OFFLINE_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "offline_rule_calibration_git_status.json")

VALIDATION_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_validation_config.json")
SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_scene_results.json")
DETECTION_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_detection_events.json")
RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_rule_matrix.json")
RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5c4i_rule_matrix.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_summary.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5c4i_tick_trace.csv")
VALIDATION_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_validation_git_status.json")

OFFLINE_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "offline_rule_calibration_summary.md")
OLD_DIRECTION_FAILURE_MD = os.path.join(PHASE_DIR, "reports", "old_direction_match_failure_reference.md")
VALIDATION_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5c4i_validation_summary.md")

BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5c4i_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5c4i_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5c4i_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5c4i_audit_summary.md")

SOURCE_MATRIX_JSON = os.path.join(SOURCE_PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_boundary_matrix.json")
SOURCE_SCENE_RESULTS_JSON = os.path.join(SOURCE_PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_scene_results.json")
SOURCE_EVENTS_JSON = os.path.join(SOURCE_PHASE_DIR, "manifests", "rgb_multiray_fan_area_distance_detection_events.json")


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


def _phase_limited(git_status: Dict[str, Any]) -> bool:
    return git_status.get("outside_phase_new_or_changed") == []


def _rows_by_kind(rows: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    return [row for row in rows if row.get("scenario_kind") == kind]


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4I Audit Summary",
        "",
        "- Recommended Rule: `{0}`".format(metrics.get("recommended_rule_id")),
        "- Target Outcome Counts: `{0}`".format(metrics.get("target_outcome_counts")),
        "- Distractor Outcome Counts: `{0}`".format(metrics.get("distractor_outcome_counts")),
        "- Fan Reliable Distances: `{0}`".format(metrics.get("fan_reliable_distances_m")),
        "- Distractor False Positive Scenes: `{0}`".format(metrics.get("distractor_false_positive_scenes")),
        "- Old Direction Inner Failure Reference Count: `{0}`".format(metrics.get("old_direction_inner_failure_reference_count")),
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
        SOURCE_MATRIX_JSON,
        SOURCE_SCENE_RESULTS_JSON,
        SOURCE_EVENTS_JSON,
        OFFLINE_SCRIPT,
        VALIDATION_SCRIPT,
        AUDIT_SCRIPT,
        OFFLINE_CONFIG_JSON,
        RECOMPUTED_EVIDENCE_JSON,
        CANDIDATE_RULE_MATRIX_JSON,
        CANDIDATE_RULE_MATRIX_CSV,
        CANDIDATE_RULE_SUMMARY_JSON,
        RECOMMENDED_RULE_JSON,
        OLD_DIRECTION_FAILURE_JSON,
        OFFLINE_GIT_STATUS_JSON,
        VALIDATION_CONFIG_JSON,
        SCENE_RESULTS_JSON,
        DETECTION_EVENTS_JSON,
        RULE_MATRIX_JSON,
        RULE_MATRIX_CSV,
        SUMMARY_JSON,
        TICK_TRACE_JSON,
        TICK_TRACE_CSV,
        VALIDATION_GIT_STATUS_JSON,
        OFFLINE_SUMMARY_MD,
        OLD_DIRECTION_FAILURE_MD,
        VALIDATION_SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    offline_config = _load(OFFLINE_CONFIG_JSON, checks, "offline_config_parse_ok")
    recomputed = _load(RECOMPUTED_EVIDENCE_JSON, checks, "recomputed_evidence_parse_ok")
    candidate_matrix = _load(CANDIDATE_RULE_MATRIX_JSON, checks, "candidate_rule_matrix_parse_ok")
    candidate_summary_doc = _load(CANDIDATE_RULE_SUMMARY_JSON, checks, "candidate_rule_summary_parse_ok")
    recommended = _load(RECOMMENDED_RULE_JSON, checks, "recommended_rule_parse_ok")
    old_failure = _load(OLD_DIRECTION_FAILURE_JSON, checks, "old_direction_failure_parse_ok")
    offline_git = _load(OFFLINE_GIT_STATUS_JSON, checks, "offline_git_status_parse_ok")
    validation_config = _load(VALIDATION_CONFIG_JSON, checks, "validation_config_parse_ok")
    scene_results = _load(SCENE_RESULTS_JSON, checks, "scene_results_parse_ok")
    events = _load(DETECTION_EVENTS_JSON, checks, "events_parse_ok")
    matrix = _load(RULE_MATRIX_JSON, checks, "rule_matrix_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    validation_git = _load(VALIDATION_GIT_STATUS_JSON, checks, "validation_git_status_parse_ok")

    if not isinstance(offline_config, dict):
        offline_config = {}
    if not isinstance(recomputed, dict):
        recomputed = {}
    if not isinstance(candidate_matrix, list):
        candidate_matrix = []
    if not isinstance(candidate_summary_doc, dict):
        candidate_summary_doc = {}
    if not isinstance(recommended, dict):
        recommended = {}
    if not isinstance(old_failure, dict):
        old_failure = {}
    if not isinstance(offline_git, dict):
        offline_git = {}
    if not isinstance(validation_config, dict):
        validation_config = {}
    if not isinstance(scene_results, dict):
        scene_results = {}
    if not isinstance(events, list):
        events = []
    if not isinstance(matrix, list):
        matrix = []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(validation_git, dict):
        validation_git = {}

    candidate_summaries = candidate_summary_doc.get("candidate_rule_summaries", [])
    if not isinstance(candidate_summaries, list):
        candidate_summaries = []

    expected_angles = ["left_outer", "left_inner", "center", "right_inner", "right_outer"]
    expected_target_pairs = sorted((distance, angle) for distance in [20.0, 35.0, 50.0] for angle in expected_angles)
    expected_distractor_pairs = sorted((distance, angle) for distance in [20.0, 50.0] for angle in expected_angles)
    target_rows = _rows_by_kind(matrix, "target")
    distractor_rows = _rows_by_kind(matrix, "distractor_only")
    target_pairs = sorted((float(row.get("distance_m")), str(row.get("angle_label"))) for row in target_rows)
    distractor_pairs = sorted((float(row.get("distance_m")), str(row.get("angle_label"))) for row in distractor_rows)

    checks["phase_name_matches"] = summary.get("phase_name") == PHASE_NAME and validation_config.get("phase_name") == PHASE_NAME
    checks["source_inputs_aligned"] = (
        offline_config.get("source_inputs", {}).get("boundary_matrix_json") == SOURCE_MATRIX_JSON
        and offline_config.get("source_inputs", {}).get("scene_results_json") == SOURCE_SCENE_RESULTS_JSON
        and offline_config.get("source_inputs", {}).get("detection_events_json") == SOURCE_EVENTS_JSON
    )
    checks["scene_results_not_used_as_pixel_source"] = (
        offline_config.get("scene_results_first_rgb_raw_used") is False
        and offline_config.get("raw_rgb_loaded_from_visuals") is True
        and recomputed.get("meta", {}).get("scene_results_first_rgb_raw_used") is False
        and recomputed.get("meta", {}).get("raw_rgb_loaded_from_visuals") is True
    )
    checks["raw_rgb_count_complete"] = len(recomputed.get("rows", [])) == 27 and all(row.get("rgb_raw_loaded") is True for row in recomputed.get("rows", []))
    checks["candidate_rule_matrix_complete"] = len(candidate_matrix) == 27 * int(summary.get("candidate_rule_count", len(candidate_summaries)) or len(candidate_summaries)) or len(candidate_matrix) == 27 * len(candidate_summaries)
    checks["candidate_rule_summary_complete"] = len(candidate_summaries) >= 5 and any(row.get("rule_name") == "stronger_rgb_any_hit" for row in candidate_summaries)
    checks["recommended_rule_expected"] = (
        recommended.get("rule_id") == "stronger_rgb_any_hit_overlap7_px0"
        and recommended.get("rule_name") == "stronger_rgb_any_hit"
        and int(recommended.get("target_overlap_min", -1)) == 7
        and int(recommended.get("rgb_changed_pixels_min", -1)) == 0
        and recommended.get("uses_recalibrated_direction_match") is False
        and recommended.get("uses_distractor_rejection") is False
    )
    checks["old_direction_failure_reference_recorded"] = old_failure.get("inner_target_failure_count") == 6
    checks["validation_scene_count_matches"] = len(matrix) == 27 and len(events) == 27 and len(scene_results) == 27 and int(summary.get("scene_count", -1)) == 27
    checks["validation_scene_matrix_complete"] = target_pairs == expected_target_pairs and distractor_pairs == expected_distractor_pairs
    checks["validation_rule_matches_recommendation"] = (
        validation_config.get("recommended_candidate_rule", {}).get("rule_id") == recommended.get("rule_id")
        and summary.get("recommended_candidate_rule", {}).get("rule_id") == recommended.get("rule_id")
        and summary.get("found_rule") == "stronger_rgb_target_signature and any_rangefinder_hit"
    )
    checks["truth_flags_false"] = (
        summary.get("truth_used_for_detection") is False
        and summary.get("actor_truth_used_for_detection") is False
        and summary.get("target_truth_used_for_detection") is False
        and all(event.get("truth_used_for_detection") is False for event in events)
        and all(event.get("actor_truth_used_for_detection") is False for event in events)
        and all(event.get("target_truth_used_for_detection") is False for event in events)
    )
    checks["direction_and_distractor_flags_match_rule"] = (
        summary.get("direction_matching_used_for_detection") is False
        and summary.get("old_direction_matching_used_for_detection") is False
        and summary.get("old_direction_matching_recorded_as_failure_reference_only") is True
        and summary.get("distractor_rejection_enabled") is False
        and all(event.get("recalibrated_direction_matching_used_for_detection") is False for event in events)
        and all(event.get("distractor_rejection_enabled") is False for event in events)
    )
    checks["validation_target_retention_expected"] = (
        summary.get("target_outcome_counts") == {"true_positive": 12, "false_negative": 3}
        and all(bool(row.get("found")) for row in target_rows if float(row.get("distance_m")) in (20.0, 35.0))
        and sorted(str(row.get("scene")) for row in target_rows if not row.get("found"))
        == ["target_center_50m", "target_left_outer_50m", "target_right_outer_50m"]
    )
    checks["validation_distractor_fp_zero"] = summary.get("distractor_outcome_counts") == {"true_negative": 10} and summary.get("distractor_false_positive_scenes") == []
    checks["validation_fan_reliable_35m"] = summary.get("fan_reliable_distances_m") == [20.0, 35.0] and float(summary.get("max_fan_reliable_distance_m")) == 35.0
    checks["validation_all_scenes_outputs"] = (
        summary.get("all_scene_launch_ok") is True
        and summary.get("all_scenes_rgb_output") is True
        and summary.get("all_scenes_rangefinder_output") is True
    )
    checks["validation_raw_and_preview_complete"] = all(
        bool(row.get("rgb_artifact")) and os.path.exists(str(row.get("rgb_artifact"))) for row in matrix if row.get("scenario_kind") in ("target", "distractor_only")
    )
    checks["git_changes_limited_to_phase"] = _phase_limited(offline_git) and _phase_limited(validation_git)
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")
    checks["compiled_expected_scripts"] = (
        "direction_matched_distractor_rejection_offline_calibration.py" in _read(BASE_COMPILE_LOG)
        and "direction_matched_distractor_rejection_validation_probe.py" in _read(BASE_COMPILE_LOG)
        and "direction_matched_distractor_rejection_audit.py" in _read(BASE_COMPILE_LOG)
        and "direction_matched_distractor_rejection_offline_calibration.py" in _read(HOLO_COMPILE_LOG)
        and "direction_matched_distractor_rejection_validation_probe.py" in _read(HOLO_COMPILE_LOG)
        and "direction_matched_distractor_rejection_audit.py" in _read(HOLO_COMPILE_LOG)
    )

    metrics = {
        "phase_name": PHASE_NAME,
        "recommended_rule_id": recommended.get("rule_id"),
        "target_outcome_counts": summary.get("target_outcome_counts"),
        "distractor_outcome_counts": summary.get("distractor_outcome_counts"),
        "fan_reliable_distances_m": summary.get("fan_reliable_distances_m"),
        "max_fan_reliable_distance_m": summary.get("max_fan_reliable_distance_m"),
        "distractor_false_positive_scenes": summary.get("distractor_false_positive_scenes"),
        "old_direction_inner_failure_reference_count": summary.get("old_direction_inner_failure_reference_count"),
        "all_passed": all(checks.values()),
    }
    audit = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, audit)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("Audit summary saved to: {0}".format(AUDIT_MD))
    print("Phase 5C-4I audit finished: all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()
