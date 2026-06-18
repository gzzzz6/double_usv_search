"""Audit for Phase 5D-4 mainline search interface coupling."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d4_mainline_search_interface_coupling"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "mainline_search_interface_coupling_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "mainline_search_interface_coupling_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_config.json")
INTERFACE_MAP_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_interface_map.json")
ADAPTER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_adapter_trace.json")
ADAPTER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d4_adapter_trace.csv")
MAINLINE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_trace.json")
MAINLINE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_trace.csv")
RUNTIME_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_runtime_results.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d4_mainline_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d4_py_compile_base.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d4_mainline_audit_summary.md")

EXPECTED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"


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


def _case_result(results: List[Dict[str, Any]], run_kind: str) -> Dict[str, Any]:
    for row in results:
        if row.get("run_kind") == run_kind:
            return row
    return {}


def _build_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-4 Mainline Search Interface Coupling Audit Summary",
        "",
        "- Recommended Rule: `{0}`".format(metrics.get("recommended_rule_id")),
        "- Target Terminated Reason: `{0}`".format(metrics.get("target_terminated_reason")),
        "- Target Time To All Found: `{0}`".format(metrics.get("target_time_to_all_found")),
        "- Coexist Terminated Reason: `{0}`".format(metrics.get("coexist_terminated_reason")),
        "- Teammate False Positive Steps: `{0}`".format(metrics.get("teammate_false_positive_steps")),
        "- Duplicate Replay Detected Steps: `{0}`".format(metrics.get("duplicate_replay_detected_steps")),
        "- Duplicate Observation Fused: `{0}`".format(metrics.get("duplicate_observation_fused")),
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
        INTERFACE_MAP_JSON,
        ADAPTER_TRACE_JSON,
        ADAPTER_TRACE_CSV,
        MAINLINE_TRACE_JSON,
        MAINLINE_TRACE_CSV,
        RUNTIME_RESULTS_JSON,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    interface_map = _load(INTERFACE_MAP_JSON, checks, "interface_map_parse_ok")
    adapter_trace = _load(ADAPTER_TRACE_JSON, checks, "adapter_trace_parse_ok")
    mainline_trace = _load(MAINLINE_TRACE_JSON, checks, "mainline_trace_parse_ok")
    runtime_results = _load(RUNTIME_RESULTS_JSON, checks, "runtime_results_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(interface_map, dict):
        interface_map = {}
    if not isinstance(adapter_trace, list):
        adapter_trace = []
    if not isinstance(mainline_trace, list):
        mainline_trace = []
    if not isinstance(runtime_results, list):
        runtime_results = []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    target_result = _case_result(runtime_results, "target")
    coexist_result = _case_result(runtime_results, "coexist")
    teammate_result = _case_result(runtime_results, "teammate_only")
    duplicate_result = _case_result(runtime_results, "duplicate_replay")
    target_runtime = target_result.get("runtime_result", {}) if isinstance(target_result.get("runtime_result"), dict) else {}
    coexist_runtime = coexist_result.get("runtime_result", {}) if isinstance(coexist_result.get("runtime_result"), dict) else {}
    teammate_runtime = teammate_result.get("runtime_result", {}) if isinstance(teammate_result.get("runtime_result"), dict) else {}
    duplicate_runtime = duplicate_result.get("runtime_result", {}) if isinstance(duplicate_result.get("runtime_result"), dict) else {}

    target_rows = [row for row in mainline_trace if row.get("run_kind") == "target"]
    coexist_rows = [row for row in mainline_trace if row.get("run_kind") == "coexist"]
    teammate_rows = [row for row in mainline_trace if row.get("run_kind") == "teammate_only"]
    duplicate_rows = [row for row in mainline_trace if row.get("run_kind") == "duplicate_replay"]
    duplicate_detect_rows = [
        row for row in duplicate_rows if any(bool(value) for value in row.get("detected_mask", []))
    ]

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME
    checks["source_5d3_audit_passed"] = config.get("source_5d3_audit_all_passed") is True and summary.get("source_5d3_audit_all_passed") is True
    checks["target_and_teammate_types_correct"] = (
        config.get("target_agent_type") == "SphereAgent"
        and config.get("teammate_agent_type") == "SurfaceVessel"
        and config.get("observer_agent_type") == "SurfaceVessel"
        and config.get("same_model_teammate_and_target") is False
        and summary.get("same_model_teammate_and_target") is False
    )
    checks["scope_boundaries_ok"] = (
        config.get("target_is_static") is True
        and config.get("dynamic_target_tracking_enabled") is False
        and config.get("non_sphere_like_target_expansion_enabled") is False
        and summary.get("dynamic_target_tracking_enabled") is False
        and summary.get("non_sphere_like_target_expansion_enabled") is False
    )
    checks["recommended_rule_reused"] = config.get("recommended_rule_id") == EXPECTED_RULE_ID and summary.get("recommended_rule_id") == EXPECTED_RULE_ID
    checks["mainline_interface_mapped"] = (
        interface_map.get("core_update_found_mask_source_contains_latch") is True
        and len(interface_map.get("mainline_interface_points", [])) >= 7
        and all(point.get("line") is not None for point in interface_map.get("mainline_interface_points", []))
    )
    checks["adapter_strategy_is_runtime_only"] = (
        config.get("adapter_strategy") == "runtime detect_targets replacement plus update_found_mask trace wrapper"
        and config.get("baseline_runtime_source_modified") is False
        and summary.get("baseline_runtime_source_modified") is False
    )
    checks["all_runs_launch_ok"] = summary.get("all_runs_launch_ok") is True and all(row.get("launch_ok") is True for row in runtime_results)
    checks["target_drives_mainline_all_found"] = (
        target_runtime.get("terminated_reason") == "all_found"
        and target_runtime.get("success_all_found") is True
        and target_runtime.get("time_to_all_found") == 1
        and summary.get("mainline_all_found_driven_by_adapter") is True
        and any(row.get("all_found_after_update") is True for row in target_rows)
    )
    checks["coexist_drives_mainline_found"] = (
        coexist_runtime.get("terminated_reason") == "all_found"
        and coexist_runtime.get("success_all_found") is True
        and coexist_runtime.get("time_to_all_found") == 1
        and any(row.get("new_found_indices") == [0] for row in coexist_rows)
    )
    checks["teammate_only_no_false_positive"] = (
        teammate_runtime.get("terminated_reason") == "max_iters"
        and teammate_runtime.get("success_all_found") is False
        and teammate_runtime.get("find_times") == [None]
        and summary.get("teammate_false_positive_steps") == []
        and all(not any(bool(value) for value in row.get("detected_mask", [])) for row in teammate_rows)
    )
    checks["duplicate_observation_fused_and_drives_mainline"] = (
        duplicate_runtime.get("terminated_reason") == "all_found"
        and duplicate_runtime.get("success_all_found") is True
        and duplicate_runtime.get("time_to_all_found") == 3
        and summary.get("duplicate_observation_fused") is True
        and summary.get("duplicate_replay_detected_steps") == [3]
        and any(
            int(row.get("source_accepted_candidate_count", 0)) >= 2
            and int(row.get("source_fused_candidate_count", 0)) == 1
            and row.get("new_found_indices") == [0]
            for row in duplicate_detect_rows
        )
    )
    checks["mainline_update_found_mask_original_called"] = (
        summary.get("mainline_update_found_mask_called") is True
        and all(row.get("update_found_mask_original_called") is True for row in mainline_trace)
        and any(row.get("new_found_indices") == [0] for row in mainline_trace)
    )
    checks["adapter_trace_uses_5d3_sensor_fusion"] = (
        adapter_trace
        and all(row.get("detection_source") == "phase5d3_sensor_event_candidate_fusion" for row in adapter_trace)
        and any(row.get("source_accepted_candidate_count", 0) > 0 for row in adapter_trace)
        and any(row.get("source_fused_candidate_count", 0) == 1 for row in adapter_trace)
    )
    checks["truth_flags_false"] = (
        config.get("truth_used_for_detection") is False
        and summary.get("truth_used_for_detection") is False
        and _truth_flags_false(adapter_trace)
        and _truth_flags_false(mainline_trace)
    )
    checks["reliable_distance_boundary_35m"] = float(config.get("reliable_distance_limit_m", -1.0)) == 35.0 and float(summary.get("reliable_distance_limit_m", -1.0)) == 35.0
    checks["no_semantic_or_sonar_detection"] = (
        config.get("semantic_sensor_used_for_detection") is False
        and summary.get("semantic_sensor_used_for_detection") is False
        and config.get("sonar_used") is False
        and summary.get("sonar_used") is False
    )
    checks["core_algorithm_files_not_modified_by_phase"] = (
        config.get("search_decision_algorithm_modified") is False
        and config.get("existing_holoocean_bridge_modified") is False
        and config.get("core_search_policy_modified") is False
        and config.get("core_execution_modified") is False
        and config.get("core_targets_modified") is False
        and config.get("core_intensity_modified") is False
        and config.get("core_safe_nav_modified") is False
        and summary.get("search_decision_algorithm_modified") is False
        and summary.get("existing_holoocean_bridge_modified") is False
    )
    checks["phase_limited_git_changes"] = _phase_limited(git_status)
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")

    metrics = {
        "recommended_rule_id": summary.get("recommended_rule_id"),
        "target_terminated_reason": summary.get("target_terminated_reason"),
        "target_time_to_all_found": summary.get("target_time_to_all_found"),
        "coexist_terminated_reason": summary.get("coexist_terminated_reason"),
        "teammate_false_positive_steps": summary.get("teammate_false_positive_steps"),
        "duplicate_replay_detected_steps": summary.get("duplicate_replay_detected_steps"),
        "duplicate_observation_fused": summary.get("duplicate_observation_fused"),
        "adapter_trace_count": summary.get("adapter_trace_count"),
        "mainline_trace_count": summary.get("mainline_trace_count"),
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
