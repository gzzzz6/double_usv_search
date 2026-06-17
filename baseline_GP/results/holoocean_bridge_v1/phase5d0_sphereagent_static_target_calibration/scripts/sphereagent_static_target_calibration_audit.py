"""Audit for Phase 5D-0 static SphereAgent target calibration."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d0_sphereagent_static_target_calibration"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "sphereagent_static_target_calibration_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "sphereagent_static_target_calibration_audit.py")

CAL_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_calibration_config.json")
CAL_SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_calibration_scene_results.json")
CAL_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_calibration_tick_trace.json")
CAL_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d0_calibration_tick_trace.csv")
RECOMPUTED_EVIDENCE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_recomputed_rgb_evidence.json")
CANDIDATE_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_candidate_rule_matrix.json")
CANDIDATE_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d0_candidate_rule_matrix.csv")
CANDIDATE_RULE_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_candidate_rule_summary.json")
RECOMMENDED_RULE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_recommended_candidate_rule.json")
CAL_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_calibration_summary.json")
CAL_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_calibration_git_status.json")
CAL_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d0_calibration_summary.md")

VAL_CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_config.json")
VAL_SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_scene_results.json")
VAL_DETECTION_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_detection_events.json")
VAL_RULE_MATRIX_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_rule_matrix.json")
VAL_RULE_MATRIX_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_rule_matrix.csv")
VAL_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_tick_trace.json")
VAL_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_tick_trace.csv")
VAL_SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_summary.json")
VAL_GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_validation_git_status.json")
VAL_SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d0_validation_summary.md")

BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d0_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d0_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d0_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d0_audit_summary.md")


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


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-0 Audit Summary",
        "",
        "- Recommended Rule: `{0}`".format(metrics.get("recommended_rule_id")),
        "- Target Outcome Counts: `{0}`".format(metrics.get("target_outcome_counts")),
        "- Teammate Outcome Counts: `{0}`".format(metrics.get("teammate_outcome_counts")),
        "- Validation Fan Reliable Distances: `{0}`".format(metrics.get("validation_fan_reliable_distances_m")),
        "- Conservative Fan Reliable Distances: `{0}`".format(metrics.get("conservative_fan_reliable_distances_m")),
        "- Conservative Max Reliable Distance: `{0}`".format(metrics.get("conservative_max_fan_reliable_distance_m")),
        "- Teammate False Positive Scenes: `{0}`".format(metrics.get("teammate_false_positive_scenes")),
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

    target_rows = [row for row in val_matrix if row.get("scenario_kind") == "target"]
    teammate_rows = [row for row in val_matrix if row.get("scenario_kind") == "teammate_only"]
    recommended_reliable = recommended.get("fan_reliable_distances_m")
    validation_reliable = val_summary.get("fan_reliable_distances_m")
    if not isinstance(recommended_reliable, list):
        recommended_reliable = []
    if not isinstance(validation_reliable, list):
        validation_reliable = []
    conservative_reliable = sorted(
        set(float(distance) for distance in recommended_reliable).intersection(
            set(float(distance) for distance in validation_reliable)
        )
    )

    checks["phase_name_matches"] = cal_summary.get("phase_name") == PHASE_NAME and val_summary.get("phase_name") == PHASE_NAME
    checks["target_and_negative_types_correct"] = (
        cal_config.get("target_agent_type") == "SphereAgent"
        and cal_config.get("teammate_negative_agent_type") == "SurfaceVessel"
        and val_config.get("target_agent_type") == "SphereAgent"
        and val_config.get("teammate_negative_agent_type") == "SurfaceVessel"
        and cal_summary.get("same_model_teammate_and_target") is False
        and val_summary.get("same_model_teammate_and_target") is False
    )
    checks["truth_flags_false"] = (
        cal_summary.get("truth_used_for_detection") is False
        and val_summary.get("truth_used_for_detection") is False
        and val_summary.get("actor_truth_used_for_detection") is False
        and val_summary.get("target_truth_used_for_detection") is False
        and all(event.get("truth_used_for_detection") is False for event in val_events)
    )
    checks["candidate_rule_summary_present"] = (
        len(candidate_summaries) >= 2
        and any(row.get("rule_name") == "sphere_blob_any_hit" for row in candidate_summaries)
        and any(row.get("rule_name") == "sphere_rgb_any_hit" for row in candidate_summaries)
    )
    checks["recommended_rule_is_sphere_blob"] = recommended.get("rule_name") == "sphere_blob_any_hit" and recommended.get("recommended_for_holoocean_rerun") is True
    checks["recommended_rule_has_zero_teammate_fp"] = int(recommended.get("teammate_false_positive_count", -1)) == 0
    checks["calibration_scene_results_complete"] = len(val_scene_results) == 32 and len(val_events) == 32 and len(val_matrix) == 32
    checks["validation_recommended_rule_matches"] = val_config.get("recommended_candidate_rule", {}).get("rule_id") == recommended.get("rule_id") and val_summary.get("recommended_candidate_rule", {}).get("rule_id") == recommended.get("rule_id")
    checks["fan_reliable_nonempty"] = len(conservative_reliable) >= 1
    checks["conservative_reliable_distance_is_35m"] = conservative_reliable and max(conservative_reliable) == 35.0
    checks["validation_outputs_present"] = val_summary.get("all_scene_launch_ok") is True and val_summary.get("all_scenes_rgb_output") is True and val_summary.get("all_scenes_rangefinder_output") is True
    checks["teammate_false_positive_zero"] = val_summary.get("teammate_false_positive_scenes") == [] and all(not row.get("found") for row in teammate_rows)
    checks["baseline_false_positive_zero"] = val_summary.get("baseline_false_positive_scenes") == []
    checks["target_true_positive_exists"] = any(bool(row.get("found")) for row in target_rows)
    checks["calibration_true_positive"] = bool(cal_summary.get("calibration_true_positive")) and bool(val_summary.get("calibration_true_positive"))
    checks["phase_limited_git_changes"] = _phase_limited(cal_git) and _phase_limited(val_git)
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")

    metrics = {
        "recommended_rule_id": recommended.get("rule_id"),
        "target_outcome_counts": val_summary.get("target_outcome_counts"),
        "teammate_outcome_counts": val_summary.get("teammate_outcome_counts"),
        "recommended_fan_reliable_distances_m": recommended_reliable,
        "validation_fan_reliable_distances_m": validation_reliable,
        "conservative_fan_reliable_distances_m": conservative_reliable,
        "conservative_max_fan_reliable_distance_m": max(conservative_reliable) if conservative_reliable else None,
        "teammate_false_positive_scenes": val_summary.get("teammate_false_positive_scenes"),
    }
    report = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, report)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("All passed:", report["all_passed"])


if __name__ == "__main__":
    main()
