"""Audit for Phase 5D-7 live capture provider coupling."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d7_live_capture_provider_coupling"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "live_capture_provider_coupling_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "live_capture_provider_coupling_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_config.json")
LIVE_BASELINE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_baseline_run.json")
LIVE_TARGET_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_target_run.json")
LIVE_COOEXIST_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_coexist_run.json")
LIVE_TEAMMATE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_teammate_only_run.json")
LIVE_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_tick_trace.json")
LIVE_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_tick_trace.csv")
LIVE_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_per_agent_detection_events.json")
LIVE_EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_per_agent_detection_events.csv")
LIVE_FUSION_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_candidate_fusion_trace.json")
LIVE_FUSION_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_candidate_fusion_trace.csv")
LIVE_PROVIDER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_provider_trace.json")
LIVE_PROVIDER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_provider_trace.csv")
ADAPTER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_adapter_observe_trace.json")
ADAPTER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_adapter_observe_trace.csv")
FOUND_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_found_trace.json")
FOUND_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_found_trace.csv")
PRODUCTION_CONTRACT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_production_adapter_contract.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d7_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d7_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d7_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d7_audit_summary.md")

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
        "# Phase 5D-7 Live Capture Provider Coupling Audit Summary",
        "",
        "- Production Adapter Module: `{0}`".format(metrics.get("production_adapter_module")),
        "- Live Capture Primary Detection Source: `{0}`".format(metrics.get("live_capture_primary_detection_source")),
        "- Replay Events Used For Detection: `{0}`".format(metrics.get("replay_events_used_for_detection")),
        "- First Live Detection Step: `{0}`".format(metrics.get("first_live_detection_step")),
        "- First Shared Found Step: `{0}`".format(metrics.get("first_shared_found_step")),
        "- Target Adapter All Found Step: `{0}`".format(metrics.get("target_adapter_all_found_step")),
        "- Teammate False Positive Steps: `{0}`".format(metrics.get("teammate_false_positive_steps")),
        "- Duplicate Observation Fused Steps: `{0}`".format(metrics.get("duplicate_observation_fused_steps")),
        "- Live Planner Callback Integrated: `{0}`".format(metrics.get("live_planner_callback_integrated")),
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
        LIVE_BASELINE_RUN_JSON,
        LIVE_TARGET_RUN_JSON,
        LIVE_COOEXIST_RUN_JSON,
        LIVE_TEAMMATE_RUN_JSON,
        LIVE_TICK_TRACE_JSON,
        LIVE_TICK_TRACE_CSV,
        LIVE_EVENTS_JSON,
        LIVE_EVENTS_CSV,
        LIVE_FUSION_JSON,
        LIVE_FUSION_CSV,
        LIVE_PROVIDER_TRACE_JSON,
        LIVE_PROVIDER_TRACE_CSV,
        ADAPTER_TRACE_JSON,
        ADAPTER_TRACE_CSV,
        FOUND_TRACE_JSON,
        PRODUCTION_CONTRACT_JSON,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    baseline_run = _load(LIVE_BASELINE_RUN_JSON, checks, "baseline_run_parse_ok")
    target_run = _load(LIVE_TARGET_RUN_JSON, checks, "target_run_parse_ok")
    coexist_run = _load(LIVE_COOEXIST_RUN_JSON, checks, "coexist_run_parse_ok")
    teammate_run = _load(LIVE_TEAMMATE_RUN_JSON, checks, "teammate_run_parse_ok")
    tick_trace = _load(LIVE_TICK_TRACE_JSON, checks, "tick_trace_parse_ok")
    live_events = _load(LIVE_EVENTS_JSON, checks, "live_events_parse_ok")
    live_fusion = _load(LIVE_FUSION_JSON, checks, "live_fusion_parse_ok")
    provider_trace = _load(LIVE_PROVIDER_TRACE_JSON, checks, "provider_trace_parse_ok")
    adapter_trace = _load(ADAPTER_TRACE_JSON, checks, "adapter_trace_parse_ok")
    found_trace = _load(FOUND_TRACE_JSON, checks, "found_trace_parse_ok")
    contract = _load(PRODUCTION_CONTRACT_JSON, checks, "production_contract_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(baseline_run, dict):
        baseline_run = {}
    if not isinstance(target_run, dict):
        target_run = {}
    if not isinstance(coexist_run, dict):
        coexist_run = {}
    if not isinstance(teammate_run, dict):
        teammate_run = {}
    if not isinstance(tick_trace, list):
        tick_trace = []
    if not isinstance(live_events, list):
        live_events = []
    if not isinstance(live_fusion, list):
        live_fusion = []
    if not isinstance(provider_trace, list):
        provider_trace = []
    if not isinstance(adapter_trace, list):
        adapter_trace = []
    if not isinstance(found_trace, list):
        found_trace = []
    if not isinstance(contract, dict):
        contract = {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    target_events = [row for row in live_events if row.get("run_kind") == "target"]
    teammate_events = [row for row in live_events if row.get("run_kind") == "teammate_only"]
    target_fusion = [row for row in live_fusion if row.get("run_kind") == "target"]
    teammate_fusion = [row for row in live_fusion if row.get("run_kind") == "teammate_only"]
    target_adapter_rows = [row for row in adapter_trace if row.get("run_kind") == "target"]
    teammate_adapter_rows = [row for row in adapter_trace if row.get("run_kind") == "teammate_only"]

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME
    checks["source_audits_passed"] = (
        config.get("source_5d3_audit_all_passed") is True
        and config.get("source_5d6_audit_all_passed") is True
        and summary.get("source_5d3_audit_all_passed") is True
        and summary.get("source_5d6_audit_all_passed") is True
    )
    checks["scope_boundaries_ok"] = (
        config.get("target_agent_type") == "SphereAgent"
        and config.get("teammate_agent_type") == "SurfaceVessel"
        and config.get("target_is_static") is True
        and config.get("dynamic_target_tracking_enabled") is False
        and summary.get("dynamic_target_tracking_enabled") is False
        and summary.get("non_sphere_like_target_expansion_enabled") is False
    )
    checks["recommended_rule_reused"] = (
        config.get("recommended_rule_id") == EXPECTED_RULE_ID
        and summary.get("recommended_rule_id") == EXPECTED_RULE_ID
    )
    checks["live_holoocean_runs_launched"] = (
        baseline_run.get("launch_ok") is True
        and target_run.get("launch_ok") is True
        and coexist_run.get("launch_ok") is True
        and teammate_run.get("launch_ok") is True
        and summary.get("all_runs_launch_ok") is True
    )
    checks["live_capture_primary_not_replay"] = (
        config.get("live_capture_primary_detection_source") is True
        and config.get("replay_events_used_for_detection") is False
        and config.get("phase5d3_json_events_used_for_detection") is False
        and summary.get("live_capture_primary_detection_source") is True
        and summary.get("replay_events_used_for_detection") is False
        and summary.get("phase5d3_json_events_used_for_detection") is False
        and all(row.get("live_capture_primary_detection_source") is True for row in provider_trace)
        and all(row.get("replay_events_used_for_detection") is False for row in provider_trace)
    )
    checks["production_adapter_import_used"] = (
        contract.get("module") == EXPECTED_PRODUCTION_MODULE
        and summary.get("production_adapter_module") == EXPECTED_PRODUCTION_MODULE
        and all(row.get("adapter_module") == EXPECTED_PRODUCTION_MODULE for row in adapter_trace)
    )
    checks["live_events_and_fusion_present"] = (
        len(tick_trace) > 0
        and len(live_events) > 0
        and len(live_fusion) == 12
        and summary.get("live_event_count") == len(live_events)
        and summary.get("live_fusion_trace_count") == len(live_fusion)
        and any(row.get("accepted_candidate") is True for row in target_events)
        and any(row.get("shared_found_this_step") is True for row in target_fusion)
    )
    checks["provider_to_adapter_called_each_step"] = (
        len(provider_trace) == 12
        and len(adapter_trace) == 12
        and summary.get("live_provider_trace_count") == 12
        and summary.get("adapter_trace_count") == 12
        and all(row.get("live_capture_provider_called") is True for row in provider_trace)
        and all(isinstance(row.get("detected_mask"), list) for row in adapter_trace)
    )
    checks["target_live_detection_success"] = (
        summary.get("live_detection_success") is True
        and summary.get("first_live_detection_step") is not None
        and summary.get("first_shared_found_step") is not None
        and summary.get("target_adapter_all_found") is True
        and summary.get("target_adapter_all_found_step") is not None
        and any(row.get("all_found_after_adapter_update") is True for row in target_adapter_rows)
    )
    checks["coexist_live_detection_success"] = (
        summary.get("coexist_live_detection_success") is True
        and summary.get("coexist_first_live_detection_step") is not None
        and summary.get("coexist_first_shared_found_step") is not None
        and summary.get("coexist_adapter_all_found") is True
    )
    checks["all_found_step_one_not_required"] = (
        config.get("all_found_step_1_required") is False
        and summary.get("all_found_step_1_required") is False
        and summary.get("target_adapter_all_found_step") is not None
    )
    checks["teammate_only_no_false_positive"] = (
        summary.get("teammate_false_positive_steps") == []
        and summary.get("teammate_only_false_positive_count") == 0
        and summary.get("teammate_adapter_all_found") is False
        and all(row.get("shared_found_this_step") is False for row in teammate_fusion)
        and all(not any(bool(v) for v in row.get("detected_mask", [])) for row in teammate_adapter_rows)
        and all(row.get("accepted_candidate") is not True for row in teammate_events)
    )
    checks["duplicate_observation_fused"] = (
        summary.get("duplicate_observation_fused") is True
        and bool(summary.get("duplicate_observation_fused_steps"))
        and any(
            int(row.get("accepted_candidate_count", 0)) >= 2
            and int(row.get("fused_candidate_count", 0)) == 1
            for row in target_fusion
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
        and _truth_flags_false(live_events)
        and _truth_flags_false(live_fusion)
        and _truth_flags_false(provider_trace)
        and _truth_flags_false(adapter_trace)
        and _truth_flags_false(found_trace)
    )
    checks["no_semantic_or_sonar_detection"] = (
        summary.get("semantic_sensor_used_for_detection") is False
        and summary.get("sonar_used") is False
    )
    checks["core_runtime_and_search_algorithm_not_modified"] = (
        summary.get("baseline_runtime_source_modified") is False
        and summary.get("search_decision_algorithm_modified") is False
        and config.get("existing_holoocean_bridge_modified") is False
        and _protected_core_clean(git_status)
    )
    checks["planner_callback_boundary_recorded"] = (
        config.get("live_planner_callback_integrated") is False
        and config.get("live_planner_callback_deferred_to_5d8") is True
        and summary.get("live_planner_callback_integrated") is False
        and summary.get("live_planner_callback_deferred_to_5d8") is True
    )
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")

    metrics = {
        "production_adapter_module": summary.get("production_adapter_module"),
        "live_capture_primary_detection_source": summary.get("live_capture_primary_detection_source"),
        "replay_events_used_for_detection": summary.get("replay_events_used_for_detection"),
        "first_live_detection_step": summary.get("first_live_detection_step"),
        "first_shared_found_step": summary.get("first_shared_found_step"),
        "target_adapter_all_found_step": summary.get("target_adapter_all_found_step"),
        "coexist_adapter_all_found_step": summary.get("coexist_adapter_all_found_step"),
        "teammate_false_positive_steps": summary.get("teammate_false_positive_steps"),
        "duplicate_observation_fused_steps": summary.get("duplicate_observation_fused_steps"),
        "max_reliable_detection_distance_observed_m": summary.get("max_reliable_detection_distance_observed_m"),
        "live_planner_callback_integrated": summary.get("live_planner_callback_integrated"),
        "live_event_count": summary.get("live_event_count"),
        "adapter_trace_count": summary.get("adapter_trace_count"),
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
