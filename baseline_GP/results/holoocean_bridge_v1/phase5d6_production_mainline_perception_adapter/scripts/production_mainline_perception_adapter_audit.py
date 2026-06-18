"""Audit for Phase 5D-6 production mainline perception adapter."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d6_production_mainline_perception_adapter"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "production_mainline_perception_adapter_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "production_mainline_perception_adapter_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_config.json")
PRODUCTION_CONTRACT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_production_adapter_contract.json")
MIGRATION_MANIFEST_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_migration_manifest.json")
OFFLINE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_offline_regression_trace.json")
OFFLINE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d6_offline_regression_trace.csv")
MAINLINE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_mainline_wrapper_trace.json")
MAINLINE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d6_mainline_wrapper_trace.csv")
MAINLINE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_mainline_runtime_results.json")
LIVE_CAPTURE_EVAL_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_live_capture_interface_evaluation.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d6_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d6_py_compile_base.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d6_audit_summary.md")

PRODUCTION_MODULE_PATH = os.path.join(BASE_DIR, "holoocean_bridge", "mainline_perception_adapter.py")
PRODUCTION_INIT_PATH = os.path.join(BASE_DIR, "holoocean_bridge", "__init__.py")

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


def _case_result(results: List[Dict[str, Any]], run_kind: str) -> Dict[str, Any]:
    for row in results:
        if row.get("run_kind") == run_kind:
            return row
    return {}


def _protected_core_clean(git_status: Dict[str, Any]) -> bool:
    return git_status.get("protected_core_path_status") == []


def _production_paths_changed_only_as_expected(git_status: Dict[str, Any]) -> bool:
    statuses = git_status.get("production_path_status")
    if not isinstance(statuses, list):
        return False
    normalized = "\n".join(str(row).replace("\\", "/") for row in statuses)
    return (
        "baseline_GP/holoocean_bridge/mainline_perception_adapter.py" in normalized
        and "baseline_GP/holoocean_bridge/__init__.py" in normalized
    )


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-6 Production Mainline Perception Adapter Audit Summary",
        "",
        "- Adapter Module: `{0}`".format(metrics.get("adapter_module")),
        "- Production Module Created: `{0}`".format(metrics.get("production_module_created")),
        "- Package Export OK: `{0}`".format(metrics.get("package_export_ok")),
        "- Mainline Target Time To All Found: `{0}`".format(metrics.get("mainline_target_time_to_all_found")),
        "- Mainline Coexist Time To All Found: `{0}`".format(metrics.get("mainline_coexist_time_to_all_found")),
        "- Mainline Teammate False Positive Steps: `{0}`".format(metrics.get("mainline_teammate_false_positive_steps")),
        "- Mainline Duplicate Detected Steps: `{0}`".format(metrics.get("mainline_duplicate_detected_steps")),
        "- Live Capture Long Term Callback Integrated: `{0}`".format(
            metrics.get("live_capture_long_term_callback_integrated")
        ),
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
        PRODUCTION_MODULE_PATH,
        PRODUCTION_INIT_PATH,
        PROBE_SCRIPT,
        AUDIT_SCRIPT,
        CONFIG_JSON,
        PRODUCTION_CONTRACT_JSON,
        MIGRATION_MANIFEST_JSON,
        OFFLINE_TRACE_JSON,
        OFFLINE_TRACE_CSV,
        MAINLINE_TRACE_JSON,
        MAINLINE_TRACE_CSV,
        MAINLINE_RESULTS_JSON,
        LIVE_CAPTURE_EVAL_JSON,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    contract = _load(PRODUCTION_CONTRACT_JSON, checks, "production_contract_parse_ok")
    migration = _load(MIGRATION_MANIFEST_JSON, checks, "migration_manifest_parse_ok")
    offline_trace = _load(OFFLINE_TRACE_JSON, checks, "offline_trace_parse_ok")
    mainline_trace = _load(MAINLINE_TRACE_JSON, checks, "mainline_trace_parse_ok")
    runtime_results = _load(MAINLINE_RESULTS_JSON, checks, "mainline_results_parse_ok")
    live_capture_eval = _load(LIVE_CAPTURE_EVAL_JSON, checks, "live_capture_eval_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(contract, dict):
        contract = {}
    if not isinstance(migration, dict):
        migration = {}
    if not isinstance(offline_trace, list):
        offline_trace = []
    if not isinstance(mainline_trace, list):
        mainline_trace = []
    if not isinstance(runtime_results, list):
        runtime_results = []
    if not isinstance(live_capture_eval, dict):
        live_capture_eval = {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    target_result = _case_result(runtime_results, "target").get("runtime_result", {})
    coexist_result = _case_result(runtime_results, "coexist").get("runtime_result", {})
    teammate_result = _case_result(runtime_results, "teammate_only").get("runtime_result", {})
    duplicate_result = _case_result(runtime_results, "duplicate_replay").get("runtime_result", {})
    if not isinstance(target_result, dict):
        target_result = {}
    if not isinstance(coexist_result, dict):
        coexist_result = {}
    if not isinstance(teammate_result, dict):
        teammate_result = {}
    if not isinstance(duplicate_result, dict):
        duplicate_result = {}

    offline_target = [row for row in offline_trace if row.get("run_kind") == "target"]
    offline_coexist = [row for row in offline_trace if row.get("run_kind") == "coexist"]
    offline_teammate = [row for row in offline_trace if row.get("run_kind") == "teammate_only"]
    offline_duplicate = [row for row in offline_trace if row.get("run_kind") == "duplicate_replay"]
    mainline_updates = [row for row in mainline_trace if row.get("trace_type") == "mainline_update"]
    mainline_adapter_outputs = [row for row in mainline_trace if row.get("trace_type") == "adapter_output"]
    duplicate_updates = [
        row
        for row in mainline_updates
        if row.get("run_kind") == "duplicate_replay" and any(bool(value) for value in row.get("detected_mask", []))
    ]
    teammate_updates = [row for row in mainline_updates if row.get("run_kind") == "teammate_only"]

    module_text = _read(PRODUCTION_MODULE_PATH)
    init_text = _read(PRODUCTION_INIT_PATH)

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME
    checks["source_audits_passed"] = (
        config.get("source_5d3_audit_all_passed") is True
        and config.get("source_5d5_audit_all_passed") is True
        and summary.get("source_5d3_audit_all_passed") is True
        and summary.get("source_5d5_audit_all_passed") is True
    )
    checks["production_module_created_and_exported"] = (
        os.path.exists(PRODUCTION_MODULE_PATH)
        and migration.get("production_module_exists") is True
        and migration.get("production_module_created") is True
        and migration.get("production_phase_local_only") is False
        and migration.get("package_export_ok") is True
        and summary.get("package_export_ok") is True
        and "ReusableMainlinePerceptionAdapter" in init_text
        and "mainline_perception_adapter_contract" in init_text
    )
    checks["production_import_path_used"] = (
        summary.get("adapter_module") == EXPECTED_PRODUCTION_MODULE
        and migration.get("direct_import_module") == EXPECTED_PRODUCTION_MODULE
        and migration.get("package_export_module") == EXPECTED_PRODUCTION_MODULE
        and all(row.get("adapter_module") == EXPECTED_PRODUCTION_MODULE for row in offline_trace)
        and all(
            row.get("adapter_module") == EXPECTED_PRODUCTION_MODULE
            for row in mainline_trace
            if row.get("trace_type") == "adapter_detect"
        )
    )
    checks["api_contract_complete"] = (
        contract.get("adapter_class") == "ReusableMainlinePerceptionAdapter"
        and contract.get("module") == EXPECTED_PRODUCTION_MODULE
        and contract.get("production_module_created") is True
        and contract.get("phase_local_only") is False
        and set(contract.get("adapter_input_fields", [])) >= {
            "per_agent_events",
            "candidate_fusion_result",
            "step_index",
            "target_count",
            "found_mask_before",
            "known_teammates",
        }
        and set(contract.get("adapter_output_fields", [])) >= {
            "detected_mask",
            "shared_found",
            "new_found_candidate_count",
            "found_update_trace",
            "truth_used_for_detection",
        }
        and set(item.get("name") for item in contract.get("methods", [])) >= {
            "reset_episode",
            "observe_step",
            "build_detected_mask",
            "fusion_trace",
        }
    )
    checks["production_module_is_adapter_only"] = (
        migration.get("module_contains_runtime_or_planner_rewrite") is False
        and "run_episode_two_usv_search_knownmap(" not in module_text
        and "select_knownmap_path_segment_policy" not in module_text
        and "sample_targets(" not in module_text
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
        and contract.get("recommended_rule_id") == EXPECTED_RULE_ID
    )
    checks["offline_regression_preserves_5d5_semantics"] = (
        summary.get("offline_target_all_found_step") == 1
        and summary.get("offline_coexist_all_found_step") == 1
        and summary.get("offline_teammate_false_positive_steps") == []
        and summary.get("offline_duplicate_all_found_step") == 3
        and any(row.get("all_found_after_replay") is True for row in offline_target)
        and any(row.get("all_found_after_replay") is True for row in offline_coexist)
        and all(not any(bool(v) for v in row.get("detected_mask", [])) for row in offline_teammate)
        and any(row.get("step_index") == 3 and row.get("shared_found") is True for row in offline_duplicate)
    )
    checks["mainline_wrapper_preserves_5d5_semantics"] = (
        target_result.get("terminated_reason") == "all_found"
        and target_result.get("time_to_all_found") == 1
        and coexist_result.get("terminated_reason") == "all_found"
        and coexist_result.get("time_to_all_found") == 1
        and teammate_result.get("terminated_reason") == "max_iters"
        and teammate_result.get("find_times") == [None]
        and duplicate_result.get("terminated_reason") == "all_found"
        and duplicate_result.get("time_to_all_found") == 3
    )
    checks["teammate_only_no_false_positive"] = (
        summary.get("mainline_teammate_false_positive_steps") == []
        and all(not any(bool(v) for v in row.get("detected_mask", [])) for row in teammate_updates)
    )
    checks["duplicate_observation_fused"] = (
        summary.get("duplicate_observation_fused") is True
        and summary.get("mainline_duplicate_detected_steps") == [3]
        and any(
            int(row.get("source_accepted_candidate_count", 0)) >= 2
            and int(row.get("source_fused_candidate_count", 0)) == 1
            for row in duplicate_updates
        )
    )
    checks["mainline_update_found_mask_original_called"] = (
        summary.get("mainline_update_found_mask_called") is True
        and all(row.get("update_found_mask_original_called") is True for row in mainline_updates)
        and any(row.get("new_found_indices") == [0] for row in mainline_updates)
    )
    checks["adapter_outputs_are_mainline_ready"] = (
        bool(mainline_adapter_outputs)
        and all("found_update_trace" in row for row in mainline_adapter_outputs)
        and all(isinstance(row.get("detected_mask"), list) for row in mainline_adapter_outputs)
        and all("shared_found" in row for row in mainline_adapter_outputs)
    )
    checks["truth_flags_false"] = (
        config.get("truth_used_for_detection") is False
        and summary.get("truth_used_for_detection") is False
        and contract.get("truth_policy") == "truth is audit-only and is not an adapter input needed for detection"
        and _truth_flags_false(offline_trace)
        and _truth_flags_false(mainline_trace)
    )
    checks["reliable_distance_boundary_35m"] = (
        float(config.get("reliable_distance_limit_m", -1.0)) == 35.0
        and float(summary.get("reliable_distance_limit_m", -1.0)) == 35.0
        and float(contract.get("reliable_distance_limit_m", -1.0)) == 35.0
    )
    checks["no_semantic_or_sonar_detection"] = (
        config.get("semantic_sensor_used_for_detection") is False
        and summary.get("semantic_sensor_used_for_detection") is False
        and config.get("sonar_used") is False
        and summary.get("sonar_used") is False
    )
    checks["core_runtime_and_search_algorithm_not_modified"] = (
        config.get("baseline_runtime_source_modified") is False
        and config.get("search_decision_algorithm_modified") is False
        and config.get("core_search_policy_modified") is False
        and config.get("core_execution_modified") is False
        and config.get("core_targets_modified") is False
        and config.get("core_intensity_modified") is False
        and config.get("core_safe_nav_modified") is False
        and summary.get("baseline_runtime_source_modified") is False
        and summary.get("search_decision_algorithm_modified") is False
        and _protected_core_clean(git_status)
    )
    checks["production_bridge_changes_are_declared"] = (
        config.get("existing_holoocean_bridge_modified") is True
        and summary.get("existing_holoocean_bridge_modified") is True
        and _production_paths_changed_only_as_expected(git_status)
    )
    checks["live_capture_boundary_recorded"] = (
        live_capture_eval.get("long_term_live_capture_callback_integrated") is False
        and live_capture_eval.get("live_capture_deferred_to_next_phase") is True
        and live_capture_eval.get("adapter_ready_for_live_capture_provider") is True
        and summary.get("live_capture_long_term_callback_integrated") is False
        and summary.get("live_capture_deferred_to_next_phase") is True
    )
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")

    metrics = {
        "adapter_module": summary.get("adapter_module"),
        "production_module_created": summary.get("production_module_created"),
        "package_export_ok": summary.get("package_export_ok"),
        "offline_target_all_found_step": summary.get("offline_target_all_found_step"),
        "mainline_target_time_to_all_found": summary.get("mainline_target_time_to_all_found"),
        "mainline_coexist_time_to_all_found": summary.get("mainline_coexist_time_to_all_found"),
        "mainline_teammate_false_positive_steps": summary.get("mainline_teammate_false_positive_steps"),
        "mainline_duplicate_detected_steps": summary.get("mainline_duplicate_detected_steps"),
        "duplicate_observation_fused": summary.get("duplicate_observation_fused"),
        "offline_trace_count": summary.get("offline_trace_count"),
        "mainline_trace_count": summary.get("mainline_trace_count"),
        "live_capture_long_term_callback_integrated": summary.get("live_capture_long_term_callback_integrated"),
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
