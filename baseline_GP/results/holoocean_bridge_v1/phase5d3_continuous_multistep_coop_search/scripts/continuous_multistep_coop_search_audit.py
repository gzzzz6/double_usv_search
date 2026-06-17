"""Audit for Phase 5D-3 continuous multi-step cooperative search."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d3_continuous_multistep_coop_search"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "continuous_multistep_coop_search_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "continuous_multistep_coop_search_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_config.json")
BASELINE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_baseline_run.json")
TARGET_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_target_run.json")
TEAMMATE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_teammate_only_run.json")
POLICY_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_policy_trace.json")
POLICY_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_policy_trace.csv")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_tick_trace.csv")
PER_AGENT_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_per_agent_detection_events.json")
PER_AGENT_EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_per_agent_detection_events.csv")
FUSION_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_candidate_fusion_trace.json")
FUSION_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d3_candidate_fusion_trace.csv")
FOUND_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_found_events.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d3_continuous_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d3_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d3_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d3_continuous_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d3_continuous_audit_summary.md")

EXPECTED_RUN_COUNT = 4
EXPECTED_POLICY_TRACE_COUNT = 12
EXPECTED_FUSION_TRACE_COUNT = 12
EXPECTED_EVENT_COUNT = 288


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


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    return all(
        row.get("truth_used_for_detection") is False
        and row.get("actor_truth_used_for_detection") is False
        and row.get("target_truth_used_for_detection") is False
        and row.get("teammate_truth_used_for_detection") is False
        for row in rows
    )


def _log_ok(path: str, marker: str) -> bool:
    text = _read(path)
    return bool(marker in text and "Traceback" not in text and "SyntaxError" not in text)


def _phase_limited(git_status: Dict[str, Any]) -> bool:
    return git_status.get("outside_phase_new_or_changed") == []


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-3 Continuous Multi-Step Cooperative Search Audit Summary",
        "",
        "- Recommended Rule: `{0}`".format(metrics.get("recommended_rule_id")),
        "- Event Count: `{0}`".format(metrics.get("event_count")),
        "- Policy Trace Count: `{0}`".format(metrics.get("policy_trace_count")),
        "- Fusion Trace Count: `{0}`".format(metrics.get("fusion_trace_count")),
        "- Target Found Steps: `{0}`".format(metrics.get("target_found_steps")),
        "- Coexist Found Steps: `{0}`".format(metrics.get("coexist_found_steps")),
        "- Teammate False Positive Steps: `{0}`".format(metrics.get("teammate_false_positive_steps")),
        "- Duplicate Observation Fused Steps: `{0}`".format(metrics.get("duplicate_observation_fused_steps")),
        "- All Found Step: `{0}`".format(metrics.get("all_found_step")),
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
        BASELINE_RUN_JSON,
        TARGET_RUN_JSON,
        TEAMMATE_RUN_JSON,
        POLICY_TRACE_JSON,
        POLICY_TRACE_CSV,
        TICK_TRACE_JSON,
        TICK_TRACE_CSV,
        PER_AGENT_EVENTS_JSON,
        PER_AGENT_EVENTS_CSV,
        FUSION_TRACE_JSON,
        FUSION_TRACE_CSV,
        FOUND_EVENTS_JSON,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    baseline_run = _load(BASELINE_RUN_JSON, checks, "baseline_run_parse_ok")
    target_run = _load(TARGET_RUN_JSON, checks, "target_run_parse_ok")
    teammate_run = _load(TEAMMATE_RUN_JSON, checks, "teammate_run_parse_ok")
    policy_trace = _load(POLICY_TRACE_JSON, checks, "policy_trace_parse_ok")
    tick_trace = _load(TICK_TRACE_JSON, checks, "tick_trace_parse_ok")
    events = _load(PER_AGENT_EVENTS_JSON, checks, "events_parse_ok")
    fusion_trace = _load(FUSION_TRACE_JSON, checks, "fusion_trace_parse_ok")
    found_events = _load(FOUND_EVENTS_JSON, checks, "found_events_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(baseline_run, dict):
        baseline_run = {}
    if not isinstance(target_run, dict):
        target_run = {}
    if not isinstance(teammate_run, dict):
        teammate_run = {}
    if not isinstance(policy_trace, list):
        policy_trace = []
    if not isinstance(tick_trace, list):
        tick_trace = []
    if not isinstance(events, list):
        events = []
    if not isinstance(fusion_trace, list):
        fusion_trace = []
    if not isinstance(found_events, list):
        found_events = []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    target_rows = [row for row in fusion_trace if row.get("run_kind") == "target"]
    coexist_rows = [row for row in fusion_trace if row.get("run_kind") == "coexist"]
    teammate_rows = [row for row in fusion_trace if row.get("run_kind") == "teammate_only"]
    target_policy = [row for row in policy_trace if row.get("run_kind") == "target"]
    target_found_policy = [row for row in target_policy if row.get("all_found_after") is True]

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME
    checks["source_audits_passed"] = config.get("source_5d1a_audit_all_passed") is True and config.get("source_5d2_audit_all_passed") is True and summary.get("source_5d1a_audit_all_passed") is True and summary.get("source_5d2_audit_all_passed") is True
    checks["target_and_teammate_types_correct"] = (
        config.get("target_agent_type") == "SphereAgent"
        and config.get("teammate_agent_type") == "SurfaceVessel"
        and config.get("observer_agent_type") == "SurfaceVessel"
        and config.get("same_model_teammate_and_target") is False
        and summary.get("same_model_teammate_and_target") is False
    )
    checks["continuous_loop_enabled"] = config.get("continuous_search_loop_enabled") is True and summary.get("continuous_search_loop_enabled") is True
    checks["observer_config_ok"] = (
        config.get("observer_count") == 2
        and summary.get("observer_count") == 2
        and sorted(config.get("observer_agent_names", [])) == ["sv0", "sv1"]
    )
    checks["recommended_rule_reused"] = config.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit" and summary.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
    checks["run_launch_ok"] = baseline_run.get("launch_ok") is True and target_run.get("launch_ok") is True and teammate_run.get("launch_ok") is True and summary.get("all_runs_launch_ok") is True
    checks["counts_ok"] = (
        len(policy_trace) == EXPECTED_POLICY_TRACE_COUNT
        and len(fusion_trace) == EXPECTED_FUSION_TRACE_COUNT
        and len(events) == EXPECTED_EVENT_COUNT
        and summary.get("policy_trace_count") == EXPECTED_POLICY_TRACE_COUNT
        and summary.get("fusion_trace_count") == EXPECTED_FUSION_TRACE_COUNT
        and summary.get("event_count") == EXPECTED_EVENT_COUNT
    )
    checks["tick_trace_nonempty"] = len(tick_trace) == EXPECTED_RUN_COUNT * int(config.get("total_ticks", 0)) * 2
    checks["per_agent_events_present"] = summary.get("per_agent_event_count_by_reporter", {}).get("sv0") == EXPECTED_EVENT_COUNT // 2 and summary.get("per_agent_event_count_by_reporter", {}).get("sv1") == EXPECTED_EVENT_COUNT // 2
    checks["candidate_fields_present"] = all(
        row.get("reporter_usv_id") in ("sv0", "sv1")
        and row.get("sensor_id") is not None
        and row.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
        and (row.get("accepted_candidate") is not True or row.get("estimated_world_position") is not None)
        and (row.get("accepted_candidate") is not True or row.get("matched_range_m") is not None)
        and (row.get("accepted_candidate") is not True or row.get("bearing_deg") is not None)
        for row in events
    )
    checks["target_shared_found_and_all_found"] = (
        bool(summary.get("target_found_steps"))
        and summary.get("target_all_found") is True
        and summary.get("all_found_step") is not None
        and bool(target_found_policy)
        and all(row.get("terminated_reason_after_step") == "all_found" for row in target_found_policy)
    )
    checks["coexist_shared_found"] = bool(summary.get("coexist_found_steps")) and summary.get("coexist_shared_found") is True
    checks["teammate_only_no_false_positive"] = (
        summary.get("teammate_only_false_positive_count") == 0
        and summary.get("teammate_false_positive_steps") == []
        and all(row.get("shared_found_this_step") is False for row in teammate_rows)
    )
    checks["duplicate_observations_fused"] = (
        summary.get("duplicate_observations_fused") is True
        and bool(summary.get("duplicate_observation_fused_steps"))
        and any(int(row.get("accepted_candidate_count", 0)) >= 2 and int(row.get("fused_candidate_count", 0)) == 1 for row in target_rows)
    )
    checks["found_mask_updated_from_fusion"] = (
        bool(found_events)
        and all(row.get("fused_candidate_count", 0) >= 1 for row in found_events)
        and any(row.get("global_found_mask_after") == [True] for row in target_rows)
        and all(row.get("found_mask_update_called") is True for row in policy_trace)
    )
    checks["target_no_false_negative"] = summary.get("target_false_negative") is False
    checks["coexist_no_false_negative"] = summary.get("coexist_false_negative") is False
    checks["reliable_distance_boundary_35m"] = float(config.get("reliable_distance_limit_m", -1.0)) == 35.0 and float(summary.get("reliable_distance_limit_m", -1.0)) == 35.0
    checks["teammate_position_exclusion_enabled"] = config.get("teammate_identity_position_available_externally") is True and summary.get("teammate_position_used_for_candidate_exclusion") is True
    checks["truth_flags_false"] = (
        config.get("truth_used_for_detection") is False
        and summary.get("truth_used_for_detection") is False
        and _truth_flags_false(events)
        and _truth_flags_false(fusion_trace)
        and _truth_flags_false(policy_trace)
        and _truth_flags_false(found_events)
    )
    checks["no_semantic_or_sonar_detection"] = config.get("semantic_sensor_used_for_detection") is False and summary.get("semantic_sensor_used_for_detection") is False and config.get("sonar_used") is False and summary.get("sonar_used") is False
    checks["phase_limited_git_changes"] = _phase_limited(git_status)
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")

    metrics = {
        "recommended_rule_id": summary.get("recommended_rule_id"),
        "event_count": summary.get("event_count"),
        "policy_trace_count": summary.get("policy_trace_count"),
        "fusion_trace_count": summary.get("fusion_trace_count"),
        "target_found_steps": summary.get("target_found_steps"),
        "coexist_found_steps": summary.get("coexist_found_steps"),
        "teammate_false_positive_steps": summary.get("teammate_false_positive_steps"),
        "duplicate_observation_fused_steps": summary.get("duplicate_observation_fused_steps"),
        "all_found_step": summary.get("all_found_step"),
    }
    report = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, report)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("All passed:", report["all_passed"])


if __name__ == "__main__":
    main()
