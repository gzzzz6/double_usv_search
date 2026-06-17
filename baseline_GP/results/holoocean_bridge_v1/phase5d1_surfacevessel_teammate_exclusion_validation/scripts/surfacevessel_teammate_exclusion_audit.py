"""Audit for Phase 5D-1 SurfaceVessel teammate exclusion validation."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d1_surfacevessel_teammate_exclusion_validation"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "surfacevessel_teammate_exclusion_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "surfacevessel_teammate_exclusion_audit.py")

CAL_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_calibration_config.json")
CAL_SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_calibration_scene_results.json")
CAL_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_calibration_tick_trace.json")
CAL_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1_calibration_tick_trace.csv")
RECOMPUTED_EVIDENCE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_recomputed_rgb_evidence.json")
CANDIDATE_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_candidate_rule_matrix.json")
CANDIDATE_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1_candidate_rule_matrix.csv")
CANDIDATE_RULE_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_candidate_rule_summary.json")
RECOMMENDED_RULE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_recommended_candidate_rule.json")
CAL_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_calibration_summary.json")
CAL_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_calibration_git_status.json")
CAL_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d1_calibration_summary.md")

VAL_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_config.json")
VAL_SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_scene_results.json")
VAL_DETECTION_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_detection_events.json")
VAL_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_rule_matrix.json")
VAL_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_rule_matrix.csv")
VAL_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_tick_trace.json")
VAL_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_tick_trace.csv")
VAL_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_summary.json")
VAL_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_validation_git_status.json")
VAL_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d1_validation_summary.md")

BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d1_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d1_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d1_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d1_audit_summary.md")

EXPECTED_SCENE_COUNT = 42
EXPECTED_TARGET_ONLY_COUNT = 10
EXPECTED_TEAMMATE_ONLY_COUNT = 27
EXPECTED_TARGET_WITH_TEAMMATE_COUNT = 3


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


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    return all(
        row.get("truth_used_for_detection") is False
        and row.get("actor_truth_used_for_detection") is False
        and row.get("target_truth_used_for_detection") is False
        and row.get("teammate_truth_used_for_detection") is False
        for row in rows
    )


def _planned_counts_ok(config: Dict[str, Any]) -> bool:
    counts = config.get("planned_scene_counts", {})
    return (
        counts.get("total") == EXPECTED_SCENE_COUNT
        and counts.get("target") == EXPECTED_TARGET_ONLY_COUNT
        and counts.get("teammate_only") == EXPECTED_TEAMMATE_ONLY_COUNT
        and counts.get("target_with_teammate") == EXPECTED_TARGET_WITH_TEAMMATE_COUNT
    )


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-1 Audit Summary",
        "",
        "- Recommended Rule: `{0}`".format(metrics.get("recommended_rule_id")),
        "- Validation Scene Count: `{0}`".format(metrics.get("validation_scene_count")),
        "- Target-only Outcome Counts: `{0}`".format(metrics.get("target_only_outcome_counts")),
        "- Target-with-teammate Outcome Counts: `{0}`".format(metrics.get("target_with_teammate_outcome_counts")),
        "- Teammate-only Outcome Counts: `{0}`".format(metrics.get("teammate_outcome_counts")),
        "- Teammate False Positive Scenes: `{0}`".format(metrics.get("teammate_false_positive_scenes")),
        "- Target False Negative Scenes: `{0}`".format(metrics.get("target_false_negative_scenes")),
        "- Max Fan Reliable Distance: `{0}`".format(metrics.get("max_fan_reliable_distance_m")),
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
        CAL_CONFIG_JSON,
        CAL_SCENE_RESULTS_JSON,
        CAL_TICK_TRACE_JSON,
        CAL_TICK_TRACE_CSV,
        RECOMPUTED_EVIDENCE_JSON,
        CANDIDATE_RULE_MATRIX_JSON,
        CANDIDATE_RULE_MATRIX_CSV,
        CANDIDATE_RULE_SUMMARY_JSON,
        RECOMMENDED_RULE_JSON,
        CAL_SUMMARY_JSON,
        CAL_GIT_STATUS_JSON,
        CAL_SUMMARY_MD,
        VAL_CONFIG_JSON,
        VAL_SCENE_RESULTS_JSON,
        VAL_DETECTION_EVENTS_JSON,
        VAL_RULE_MATRIX_JSON,
        VAL_RULE_MATRIX_CSV,
        VAL_TICK_TRACE_JSON,
        VAL_TICK_TRACE_CSV,
        VAL_SUMMARY_JSON,
        VAL_GIT_STATUS_JSON,
        VAL_SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    cal_config = _load(CAL_CONFIG_JSON, checks, "calibration_config_parse_ok")
    evidence_doc = _load(RECOMPUTED_EVIDENCE_JSON, checks, "recomputed_evidence_parse_ok")
    candidate_matrix = _load(CANDIDATE_RULE_MATRIX_JSON, checks, "candidate_rule_matrix_parse_ok")
    candidate_summary_doc = _load(CANDIDATE_RULE_SUMMARY_JSON, checks, "candidate_rule_summary_parse_ok")
    recommended = _load(RECOMMENDED_RULE_JSON, checks, "recommended_rule_parse_ok")
    cal_summary = _load(CAL_SUMMARY_JSON, checks, "calibration_summary_parse_ok")
    cal_git = _load(CAL_GIT_STATUS_JSON, checks, "calibration_git_status_parse_ok")
    val_config = _load(VAL_CONFIG_JSON, checks, "validation_config_parse_ok")
    val_scene_results = _load(VAL_SCENE_RESULTS_JSON, checks, "validation_scene_results_parse_ok")
    val_events = _load(VAL_DETECTION_EVENTS_JSON, checks, "validation_events_parse_ok")
    val_matrix = _load(VAL_RULE_MATRIX_JSON, checks, "validation_rule_matrix_parse_ok")
    val_summary = _load(VAL_SUMMARY_JSON, checks, "validation_summary_parse_ok")
    val_git = _load(VAL_GIT_STATUS_JSON, checks, "validation_git_status_parse_ok")

    if not isinstance(cal_config, dict):
        cal_config = {}
    if not isinstance(evidence_doc, dict):
        evidence_doc = {}
    if not isinstance(candidate_matrix, list):
        candidate_matrix = []
    if not isinstance(candidate_summary_doc, dict):
        candidate_summary_doc = {}
    if not isinstance(recommended, dict):
        recommended = {}
    if not isinstance(cal_summary, dict):
        cal_summary = {}
    if not isinstance(cal_git, dict):
        cal_git = {}
    if not isinstance(val_config, dict):
        val_config = {}
    if not isinstance(val_scene_results, dict):
        val_scene_results = {}
    if not isinstance(val_events, list):
        val_events = []
    if not isinstance(val_matrix, list):
        val_matrix = []
    if not isinstance(val_summary, dict):
        val_summary = {}
    if not isinstance(val_git, dict):
        val_git = {}

    candidate_summaries = candidate_summary_doc.get("candidate_rule_summaries", [])
    if not isinstance(candidate_summaries, list):
        candidate_summaries = []
    evidence_rows = evidence_doc.get("rows", [])
    if not isinstance(evidence_rows, list):
        evidence_rows = []

    target_only_rows = [row for row in val_matrix if row.get("scenario_kind") == "target"]
    target_with_teammate_rows = [row for row in val_matrix if row.get("scenario_kind") == "target_with_teammate"]
    target_present_rows = target_only_rows + target_with_teammate_rows
    teammate_rows = [row for row in val_matrix if row.get("scenario_kind") == "teammate_only"]
    baseline_rows = [row for row in val_matrix if row.get("scenario_kind") == "baseline"]
    calibration_rows = [row for row in val_matrix if row.get("scenario_kind") == "calibration"]

    checks["phase_name_matches"] = cal_summary.get("phase_name") == PHASE_NAME and val_summary.get("phase_name") == PHASE_NAME
    checks["planned_scene_counts_ok"] = _planned_counts_ok(cal_config) and _planned_counts_ok(val_config)
    checks["target_and_teammate_types_correct"] = (
        cal_config.get("target_agent_type") == "SphereAgent"
        and cal_config.get("teammate_negative_agent_type") == "SurfaceVessel"
        and val_config.get("target_agent_type") == "SphereAgent"
        and val_config.get("teammate_negative_agent_type") == "SurfaceVessel"
        and cal_summary.get("same_model_teammate_and_target") is False
        and val_summary.get("same_model_teammate_and_target") is False
    )
    checks["static_target_boundary_ok"] = (
        cal_summary.get("target_is_static") is True
        and val_summary.get("target_is_static") is True
        and val_summary.get("dynamic_target_tracking_enabled") is False
    )
    checks["truth_flags_false"] = (
        cal_summary.get("truth_used_for_detection") is False
        and val_summary.get("truth_used_for_detection") is False
        and val_summary.get("actor_truth_used_for_detection") is False
        and val_summary.get("target_truth_used_for_detection") is False
        and val_summary.get("teammate_truth_used_for_detection") is False
        and _truth_flags_false(val_events)
        and _truth_flags_false(val_matrix)
    )
    checks["no_semantic_or_sonar_detection"] = (
        cal_summary.get("semantic_sensor_used_for_detection") is False
        and val_summary.get("semantic_sensor_used_for_detection") is False
        and cal_summary.get("sonar_used") is False
        and val_summary.get("sonar_used") is False
    )
    checks["recommended_rule_is_fixed_5d0_rule"] = (
        recommended.get("rule_id") == "sphere_blob_any_hit"
        and recommended.get("rule_name") == "sphere_blob_any_hit"
        and recommended.get("source_phase") == "phase5d0_sphereagent_static_target_calibration"
        and recommended.get("recommended_for_holoocean_rerun") is True
        and val_config.get("recommended_candidate_rule", {}).get("rule_id") == recommended.get("rule_id")
        and val_summary.get("recommended_candidate_rule", {}).get("rule_id") == recommended.get("rule_id")
    )
    checks["candidate_reference_present"] = (
        len(candidate_summaries) >= 2
        and any(row.get("rule_name") == "sphere_blob_any_hit" for row in candidate_summaries)
        and any(row.get("rule_name") == "sphere_rgb_any_hit" for row in candidate_summaries)
        and len(candidate_matrix) >= EXPECTED_SCENE_COUNT
        and len(evidence_rows) == EXPECTED_SCENE_COUNT
    )
    checks["validation_matrix_counts_ok"] = (
        len(val_scene_results) == EXPECTED_SCENE_COUNT
        and len(val_events) == EXPECTED_SCENE_COUNT
        and len(val_matrix) == EXPECTED_SCENE_COUNT
        and len(target_only_rows) == EXPECTED_TARGET_ONLY_COUNT
        and len(teammate_rows) == EXPECTED_TEAMMATE_ONLY_COUNT
        and len(target_with_teammate_rows) == EXPECTED_TARGET_WITH_TEAMMATE_COUNT
        and len(baseline_rows) == 1
        and len(calibration_rows) == 1
    )
    checks["validation_outputs_present"] = (
        val_summary.get("all_scene_launch_ok") is True
        and val_summary.get("all_scenes_rgb_output") is True
        and val_summary.get("all_scenes_rangefinder_output") is True
    )
    checks["all_teammate_only_true_negative"] = (
        val_summary.get("teammate_false_positive_scenes") == []
        and len(teammate_rows) == EXPECTED_TEAMMATE_ONLY_COUNT
        and all(row.get("found") is False and row.get("outcome") == "true_negative" for row in teammate_rows)
    )
    checks["baseline_false_positive_zero"] = val_summary.get("baseline_false_positive_scenes") == [] and all(row.get("found") is False for row in baseline_rows)
    checks["all_target_present_true_positive"] = (
        len(target_present_rows) == EXPECTED_TARGET_ONLY_COUNT + EXPECTED_TARGET_WITH_TEAMMATE_COUNT
        and all(row.get("found") is True and row.get("outcome") == "true_positive" for row in target_present_rows)
    )
    checks["target_with_teammate_true_positive"] = (
        len(target_with_teammate_rows) == EXPECTED_TARGET_WITH_TEAMMATE_COUNT
        and all(row.get("found") is True for row in target_with_teammate_rows)
    )
    checks["conservative_reliable_distance_remains_35m"] = val_summary.get("max_fan_reliable_distance_m") == 35.0
    checks["calibration_true_positive"] = bool(cal_summary.get("calibration_true_positive")) and bool(val_summary.get("calibration_true_positive"))
    checks["phase_limited_git_changes"] = _phase_limited(cal_git) and _phase_limited(val_git)
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")

    metrics = {
        "recommended_rule_id": recommended.get("rule_id"),
        "validation_scene_count": len(val_matrix),
        "target_only_outcome_counts": val_summary.get("target_only_outcome_counts"),
        "target_with_teammate_outcome_counts": val_summary.get("target_with_teammate_outcome_counts"),
        "teammate_outcome_counts": val_summary.get("teammate_outcome_counts"),
        "teammate_false_positive_scenes": val_summary.get("teammate_false_positive_scenes"),
        "target_false_negative_scenes": val_summary.get("target_false_negative_scenes"),
        "target_with_teammate_false_negative_scenes": val_summary.get("target_with_teammate_false_negative_scenes"),
        "fan_reliable_distances_m": val_summary.get("fan_reliable_distances_m"),
        "max_fan_reliable_distance_m": val_summary.get("max_fan_reliable_distance_m"),
    }
    report = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, report)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("All passed:", report["all_passed"])


if __name__ == "__main__":
    main()
