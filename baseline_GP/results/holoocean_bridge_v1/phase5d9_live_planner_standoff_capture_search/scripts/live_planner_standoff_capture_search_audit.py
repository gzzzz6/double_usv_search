"""Audit for Phase 5D-9 live planner callback continuous search."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d9_live_planner_standoff_capture_search"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "live_planner_standoff_capture_search_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "live_planner_standoff_capture_search_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_config.json")
PRODUCTION_CONTRACT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_production_adapter_contract.json")
CALIBRATION_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_calibration_run.json")
TARGET_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_target_run.json")
TEAMMATE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_teammate_only_run.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_tick_trace.csv")
POLICY_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_policy_trace.json")
POLICY_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_policy_trace.csv")
EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_per_agent_detection_events.json")
EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_per_agent_detection_events.csv")
FUSION_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_candidate_fusion_trace.json")
FUSION_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_live_candidate_fusion_trace.csv")
ADAPTER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_adapter_observe_trace.json")
ADAPTER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_adapter_observe_trace.csv")
MAINLINE_UPDATE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_mainline_update_found_trace.json")
MAINLINE_UPDATE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d9_mainline_update_found_trace.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d9_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d9_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d9_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d9_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d9_audit_summary.md")

EXPECTED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"
EXPECTED_PRODUCTION_MODULE = "baseline_GP.holoocean_bridge.mainline_perception_adapter"


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


def _protected_core_clean(git_status: Dict[str, Any]) -> bool:
    return git_status.get("protected_core_path_status") == []


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-9 Live Planner Callback Continuous Search Audit Summary",
        "",
        "- Production Adapter Module: `{0}`".format(metrics.get("production_adapter_module")),
        "- Planned Path Source: `{0}`".format(metrics.get("planned_path_source")),
        "- Bridge Fan RangeFinder Sensor Count: `{0}`".format(
            metrics.get("bridge_fan_rangefinder_sensor_count")
        ),
        "- Target Terminated Reason: `{0}`".format(metrics.get("target_terminated_reason")),
        "- Target All Found Step: `{0}`".format(metrics.get("target_all_found_step")),
        "- Phase Status: `{0}`".format(metrics.get("phase_status")),
        "- Phase Goal Completed: `{0}`".format(metrics.get("phase_goal_completed")),
        "- Target Live Detection Success: `{0}`".format(metrics.get("target_live_detection_success")),
        "- Post Arrival Scan Enabled: `{0}`".format(metrics.get("post_arrival_scan_enabled")),
        "- Target Scan Tick Count: `{0}`".format(metrics.get("target_scan_tick_count")),
        "- Target Accepted Candidate From Scan: `{0}`".format(
            metrics.get("target_accepted_candidate_from_scan")
        ),
        "- Mainline Found Mask Updated From Live Adapter: `{0}`".format(
            metrics.get("mainline_found_mask_updated_from_live_adapter")
        ),
        "- Teammate False Positive Steps: `{0}`".format(metrics.get("teammate_false_positive_steps")),
        "- Event Count: `{0}`".format(metrics.get("event_count")),
        "- Update Found Mask Calls: `{0}`".format(metrics.get("mainline_update_found_mask_called_count")),
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
        PRODUCTION_CONTRACT_JSON,
        CALIBRATION_RUN_JSON,
        TARGET_RUN_JSON,
        TEAMMATE_RUN_JSON,
        TICK_TRACE_JSON,
        TICK_TRACE_CSV,
        POLICY_TRACE_JSON,
        POLICY_TRACE_CSV,
        EVENTS_JSON,
        EVENTS_CSV,
        FUSION_JSON,
        FUSION_CSV,
        ADAPTER_TRACE_JSON,
        ADAPTER_TRACE_CSV,
        MAINLINE_UPDATE_TRACE_JSON,
        MAINLINE_UPDATE_TRACE_CSV,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    contract = _load(PRODUCTION_CONTRACT_JSON, checks, "production_contract_parse_ok")
    calibration_run = _load(CALIBRATION_RUN_JSON, checks, "calibration_run_parse_ok")
    target_run = _load(TARGET_RUN_JSON, checks, "target_run_parse_ok")
    teammate_run = _load(TEAMMATE_RUN_JSON, checks, "teammate_run_parse_ok")
    tick_trace = _load(TICK_TRACE_JSON, checks, "tick_trace_parse_ok")
    policy_trace = _load(POLICY_TRACE_JSON, checks, "policy_trace_parse_ok")
    events = _load(EVENTS_JSON, checks, "events_parse_ok")
    fusion = _load(FUSION_JSON, checks, "fusion_parse_ok")
    adapter_trace = _load(ADAPTER_TRACE_JSON, checks, "adapter_trace_parse_ok")
    update_trace = _load(MAINLINE_UPDATE_TRACE_JSON, checks, "mainline_update_trace_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(contract, dict):
        contract = {}
    if not isinstance(calibration_run, dict):
        calibration_run = {}
    if not isinstance(target_run, dict):
        target_run = {}
    if not isinstance(teammate_run, dict):
        teammate_run = {}
    if not isinstance(tick_trace, list):
        tick_trace = []
    if not isinstance(policy_trace, list):
        policy_trace = []
    if not isinstance(events, list):
        events = []
    if not isinstance(fusion, list):
        fusion = []
    if not isinstance(adapter_trace, list):
        adapter_trace = []
    if not isinstance(update_trace, list):
        update_trace = []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    target_events = [row for row in events if row.get("run_kind") == "target"]
    teammate_events = [row for row in events if row.get("run_kind") == "teammate_only"]
    target_fusion = [row for row in fusion if row.get("run_kind") == "target"]
    teammate_fusion = [row for row in fusion if row.get("run_kind") == "teammate_only"]
    target_updates = [row for row in update_trace if row.get("run_kind") == "target"]
    teammate_updates = [row for row in update_trace if row.get("run_kind") == "teammate_only"]

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME
    phase_goal_completed = summary.get("phase_goal_completed") is True
    checks["phase_completion_fields_consistent"] = (
        summary.get("phase_completed") == summary.get("phase_goal_completed")
        and (
            (
                phase_goal_completed
                and summary.get("phase_status") == "live_planner_callback_scan_capture_all_found_closed"
            )
            or (
                not phase_goal_completed
                and summary.get("phase_status")
                == "planner_live_callback_integrated_but_live_detection_all_found_not_closed"
            )
        )
    )
    checks["source_audits_passed"] = (
        config.get("source_5d6_audit_all_passed") is True
        and config.get("source_5d7_audit_all_passed") is True
        and summary.get("source_5d6_audit_all_passed") is True
        and summary.get("source_5d7_audit_all_passed") is True
    )
    checks["scope_boundaries_ok"] = (
        config.get("target_agent_type") == "SphereAgent"
        and config.get("teammate_agent_type") == "SurfaceVessel"
        and config.get("observer_agent_type") == "SurfaceVessel"
        and config.get("target_is_static") is True
        and config.get("dynamic_target_tracking_enabled") is False
        and config.get("non_sphere_like_target_expansion_enabled") is False
        and summary.get("dynamic_target_tracking_enabled") is False
        and summary.get("non_sphere_like_target_expansion_enabled") is False
    )
    checks["recommended_rule_reused"] = (
        config.get("recommended_rule_id") == EXPECTED_RULE_ID
        and summary.get("recommended_rule_id") == EXPECTED_RULE_ID
    )
    checks["dense_bridge_fan_geometry_used"] = (
        int(config.get("bridge_fan_rangefinder_sensor_count", 0) or 0) == 61
        and int(summary.get("bridge_fan_rangefinder_sensor_count", 0) or 0) == 61
        and "not_detection_rule_change" in str(config.get("bridge_fan_geometry_role"))
        and "not_detection_rule_change" in str(summary.get("bridge_fan_geometry_role"))
    )
    checks["production_adapter_import_used"] = (
        contract.get("module") == EXPECTED_PRODUCTION_MODULE
        and summary.get("production_adapter_module") == EXPECTED_PRODUCTION_MODULE
        and all(row.get("adapter_module") == EXPECTED_PRODUCTION_MODULE for row in adapter_trace)
    )
    checks["live_holoocean_runs_launched"] = (
        calibration_run.get("launch_ok") is True
        and target_run.get("launch_ok") is True
        and teammate_run.get("launch_ok") is True
        and summary.get("all_runs_launch_ok") is True
    )
    checks["planner_callback_integrated"] = (
        config.get("live_planner_callback_integrated") is True
        and summary.get("live_planner_callback_integrated") is True
        and summary.get("planned_path_source") == "baseline_GP_mainline_planner"
        and summary.get("preset_trajectory_used") is False
        and bool(policy_trace)
        and all(row.get("planner_callback_called") is True for row in policy_trace)
        and any(row.get("sv0_segment_path") for row in policy_trace if row.get("run_kind") == "target")
        and any(row.get("sv1_segment_path") for row in policy_trace if row.get("run_kind") == "target")
    )
    checks["post_arrival_scan_capture_enabled"] = (
        config.get("post_arrival_scan_enabled") is True
        and summary.get("post_arrival_scan_enabled") is True
        and int(summary.get("target_scan_tick_count", 0) or 0) > 0
        and int(summary.get("teammate_scan_tick_count", 0) or 0) > 0
        and any(row.get("post_arrival_scan_tick") is True for row in tick_trace)
        and any(row.get("post_arrival_scan_tick") is True for row in events)
    )
    checks["holo_physical_execution_from_planner_path"] = (
        bool(tick_trace)
        and all(row.get("planned_path_source") == "baseline_GP_mainline_planner" for row in tick_trace)
        and all(row.get("preset_trajectory_used") is False for row in tick_trace)
        and any(row.get("projection_matches_target") is True for row in tick_trace)
        and target_run.get("physical_failure") is False
    )
    checks["live_capture_primary_not_replay"] = (
        config.get("live_capture_primary_detection_source") is True
        and config.get("replay_events_used_for_detection") is False
        and config.get("phase5d3_json_events_used_for_detection") is False
        and summary.get("live_capture_primary_detection_source") is True
        and summary.get("replay_events_used_for_detection") is False
        and summary.get("phase5d3_json_events_used_for_detection") is False
        and bool(events)
        and all(row.get("live_capture_primary_detection_source") is True for row in events)
        and all(row.get("replay_events_used_for_detection") is False for row in events)
    )
    checks["calibration_reference_not_detection_replay"] = (
        config.get("live_calibration_reference_used") is True
        and "not_detection_event_replay" in str(config.get("live_calibration_reference_role"))
        and summary.get("live_calibration_reference_used") is True
        and all(row.get("calibration_reference_used") is True for row in events)
    )
    checks["orientation_projection_used"] = (
        config.get("orientation_sensor_used_for_world_projection") is True
        and summary.get("orientation_sensor_used_for_world_projection") is True
        and all(row.get("world_projection_uses_observer_heading") is True for row in events)
        and any(row.get("observer_heading_deg") is not None for row in events)
    )
    checks["events_and_fusion_traces_present"] = (
        len(target_events) > 0
        and len(teammate_events) > 0
        and len(target_fusion) > 0
        and len(teammate_fusion) > 0
        and len(adapter_trace) == len(update_trace)
        and summary.get("event_count") == len(events)
    )
    checks["target_live_accepted_candidate_present"] = any(
        row.get("accepted_candidate") is True for row in target_events
    )
    checks["target_shared_found_fusion_present"] = any(
        row.get("shared_found_this_step") is True for row in target_fusion
    )
    checks["target_all_found_from_live_adapter"] = (
        target_run.get("terminated_reason") == "all_found"
        and target_run.get("all_found") is True
        and target_run.get("all_found_step") is not None
        and summary.get("target_success_all_found") is True
        and summary.get("mainline_all_found_driven_by_live_adapter") is True
        and any(row.get("all_found_after_update") is True for row in target_updates)
    )
    checks["mainline_update_found_mask_original_called"] = (
        summary.get("mainline_update_found_mask_called") is True
        and summary.get("mainline_update_found_mask_called_count") == len(update_trace)
        and all(row.get("update_found_mask_original_called") is True for row in update_trace)
    )
    checks["mainline_found_mask_updated_from_live_adapter"] = (
        summary.get("mainline_found_mask_updated_from_live_adapter") is True
        and any(row.get("new_found_indices") == [0] for row in target_updates)
    )
    checks["teammate_only_no_false_positive"] = (
        summary.get("teammate_false_positive_steps") == []
        and summary.get("teammate_only_no_false_positive") is True
        and summary.get("teammate_events_accepted_count") == 0
        and teammate_run.get("all_found") is False
        and teammate_run.get("find_times_final") == [None]
        and all(row.get("shared_found_this_step") is False for row in teammate_fusion)
        and all(not any(bool(v) for v in row.get("detected_mask", [])) for row in teammate_updates)
    )
    checks["duplicate_or_shared_fusion_recorded"] = (
        summary.get("candidate_fusion_called") is True
        and all(row.get("candidate_fusion_called") is True for row in fusion)
        and (
            summary.get("duplicate_observation_fused") is True
            or bool(summary.get("dual_reporter_fused_steps"))
            or any(int(row.get("fused_candidate_count", 0)) >= 1 for row in target_fusion)
        )
    )
    checks["reliable_distance_boundary_observed"] = (
        float(config.get("reliable_distance_limit_m", -1.0)) == 35.0
        and float(summary.get("reliable_distance_limit_m", -1.0)) == 35.0
        and summary.get("max_reliable_detection_distance_observed_m") is not None
        and float(summary.get("max_reliable_detection_distance_observed_m")) <= 36.0
    )
    checks["truth_flags_false"] = (
        summary.get("truth_used_for_detection") is False
        and summary.get("truth_flags_false") is True
        and _truth_flags_false(events)
        and _truth_flags_false(fusion)
        and _truth_flags_false(adapter_trace)
        and _truth_flags_false(update_trace)
        and _truth_flags_false(policy_trace)
    )
    checks["no_semantic_or_sonar_detection"] = (
        config.get("semantic_sensor_used_for_detection") is False
        and config.get("sonar_used") is False
        and summary.get("semantic_sensor_used_for_detection") is False
        and summary.get("sonar_used") is False
    )
    checks["core_runtime_and_search_algorithm_not_modified"] = (
        config.get("baseline_runtime_source_modified") is False
        and config.get("search_decision_algorithm_modified") is False
        and config.get("existing_holoocean_bridge_modified") is False
        and summary.get("baseline_runtime_source_modified") is False
        and summary.get("search_decision_algorithm_modified") is False
        and _protected_core_clean(git_status)
    )
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")

    metrics = {
        "production_adapter_module": summary.get("production_adapter_module"),
        "planned_path_source": summary.get("planned_path_source"),
        "target_terminated_reason": summary.get("target_terminated_reason"),
        "target_all_found_step": summary.get("target_all_found_step"),
        "target_completed_steps": summary.get("target_completed_steps"),
        "phase_status": summary.get("phase_status"),
        "phase_completed": summary.get("phase_completed"),
        "phase_goal_completed": summary.get("phase_goal_completed"),
        "target_live_detection_success": summary.get("target_live_detection_success"),
        "bridge_fan_rangefinder_sensor_count": summary.get("bridge_fan_rangefinder_sensor_count"),
        "post_arrival_scan_enabled": summary.get("post_arrival_scan_enabled"),
        "target_scan_tick_count": summary.get("target_scan_tick_count"),
        "target_accepted_candidate_from_scan": summary.get("target_accepted_candidate_from_scan"),
        "mainline_found_mask_updated_from_live_adapter": summary.get(
            "mainline_found_mask_updated_from_live_adapter"
        ),
        "teammate_false_positive_steps": summary.get("teammate_false_positive_steps"),
        "event_count": summary.get("event_count"),
        "fusion_trace_count": summary.get("fusion_trace_count"),
        "adapter_trace_count": summary.get("adapter_trace_count"),
        "mainline_update_found_mask_called_count": summary.get("mainline_update_found_mask_called_count"),
        "max_reliable_detection_distance_observed_m": summary.get("max_reliable_detection_distance_observed_m"),
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
        f.write(_build_md(checks, metrics))
    print("Audit written to: {0}".format(AUDIT_MD))
    print("all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()



