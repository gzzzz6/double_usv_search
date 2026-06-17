"""Audit for Phase 5D-2 multi-SurfaceVessel static SphereAgent cooperative search."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d2_multi_surfacevessel_static_sphereagent_coop_search"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "multi_surfacevessel_static_sphereagent_coop_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "multi_surfacevessel_static_sphereagent_coop_audit.py")
CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_config.json")
SCENE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_scene_results.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_tick_trace.csv")
PER_AGENT_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_per_agent_detection_events.json")
PER_AGENT_EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d2_per_agent_detection_events.csv")
FUSION_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_candidate_fusion_trace.json")
FUSION_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d2_candidate_fusion_trace.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d2_coop_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d2_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d2_py_compile_holo.txt")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d2_coop_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d2_coop_audit_summary.md")

EXPECTED_SCENE_COUNT = 5
EXPECTED_EVENT_COUNT = 10
EXPECTED_OBSERVER_COUNT = 2


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
        "# Phase 5D-2 Cooperative Search Audit Summary",
        "",
        "- Recommended Rule: `{0}`".format(metrics.get("recommended_rule_id")),
        "- Observer Count: `{0}`".format(metrics.get("observer_count")),
        "- Scene Count: `{0}`".format(metrics.get("scene_count")),
        "- Event Count: `{0}`".format(metrics.get("event_count")),
        "- Fusion Outcome Counts: `{0}`".format(metrics.get("fusion_outcome_counts")),
        "- Target Fusion Outcome Counts: `{0}`".format(metrics.get("target_fusion_outcome_counts")),
        "- Teammate Fusion Outcome Counts: `{0}`".format(metrics.get("teammate_fusion_outcome_counts")),
        "- Target False Negative Scenes: `{0}`".format(metrics.get("target_false_negative_scenes")),
        "- Teammate False Positive Scenes: `{0}`".format(metrics.get("teammate_false_positive_scenes")),
        "- Duplicate Merge Scenes: `{0}`".format(metrics.get("duplicate_merge_scenes")),
        "- Shared Target Found: `{0}`".format(metrics.get("shared_target_found")),
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
        TICK_TRACE_JSON,
        TICK_TRACE_CSV,
        PER_AGENT_EVENTS_JSON,
        PER_AGENT_EVENTS_CSV,
        FUSION_TRACE_JSON,
        FUSION_TRACE_CSV,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    config = _load(CONFIG_JSON, checks, "config_parse_ok")
    scene_results = _load(SCENE_RESULTS_JSON, checks, "scene_results_parse_ok")
    events = _load(PER_AGENT_EVENTS_JSON, checks, "events_parse_ok")
    fusion_trace = _load(FUSION_TRACE_JSON, checks, "fusion_trace_parse_ok")
    summary = _load(SUMMARY_JSON, checks, "summary_parse_ok")
    git_status = _load(GIT_STATUS_JSON, checks, "git_status_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(scene_results, dict):
        scene_results = {}
    if not isinstance(events, list):
        events = []
    if not isinstance(fusion_trace, list):
        fusion_trace = []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    target_fusion = [row for row in fusion_trace if row.get("scenario_kind") in ("target", "target_with_teammate")]
    teammate_fusion = [row for row in fusion_trace if row.get("scenario_kind") == "teammate_only"]
    baseline_fusion = [row for row in fusion_trace if row.get("scenario_kind") == "baseline"]
    target_events = [row for row in events if row.get("expected_target_present_for_audit") is True]
    teammate_events = [row for row in events if row.get("scenario_kind") == "teammate_only"]
    duplicate_rows = [row for row in fusion_trace if row.get("expected_duplicate_observation_for_audit") is True]

    checks["phase_name_matches"] = config.get("phase_name") == PHASE_NAME and summary.get("phase_name") == PHASE_NAME
    checks["source_5d1a_audit_passed"] = config.get("source_5d1a_audit_all_passed") is True and summary.get("source_5d1a_audit_all_passed") is True
    checks["target_and_teammate_types_correct"] = (
        config.get("target_agent_type") == "SphereAgent"
        and config.get("teammate_agent_type") == "SurfaceVessel"
        and config.get("observer_agent_type") == "SurfaceVessel"
        and config.get("same_model_teammate_and_target") is False
        and summary.get("same_model_teammate_and_target") is False
    )
    checks["multi_observer_configured"] = (
        int(config.get("observer_count", 0)) >= EXPECTED_OBSERVER_COUNT
        and int(summary.get("observer_count", 0)) >= EXPECTED_OBSERVER_COUNT
        and sorted(config.get("observer_agent_names", [])) == ["sv0", "sv1"]
    )
    checks["recommended_rule_reused"] = (
        config.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
        and summary.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
    )
    checks["planned_scene_counts_ok"] = (
        config.get("planned_scene_counts", {}).get("total") == EXPECTED_SCENE_COUNT
        and config.get("planned_scene_counts", {}).get("target") == 1
        and config.get("planned_scene_counts", {}).get("target_with_teammate") == 1
        and config.get("planned_scene_counts", {}).get("teammate_only") == 2
        and config.get("planned_scene_counts", {}).get("baseline") == 1
    )
    checks["scene_and_event_counts_ok"] = (
        len(scene_results) == EXPECTED_SCENE_COUNT
        and len(fusion_trace) == EXPECTED_SCENE_COUNT
        and len(events) == EXPECTED_EVENT_COUNT
        and summary.get("event_count") == EXPECTED_EVENT_COUNT
    )
    checks["per_agent_events_present"] = (
        summary.get("per_agent_event_count_by_reporter", {}).get("sv0") == EXPECTED_SCENE_COUNT
        and summary.get("per_agent_event_count_by_reporter", {}).get("sv1") == EXPECTED_SCENE_COUNT
        and all(row.get("reporter_usv_id") in ("sv0", "sv1") for row in events)
    )
    checks["candidate_fields_present"] = all(
        row.get("reporter_usv_id") is not None
        and row.get("sensor_id") is not None
        and row.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
        and (row.get("accepted_candidate") is not True or row.get("estimated_world_position") is not None)
        and (row.get("accepted_candidate") is not True or row.get("matched_range_m") is not None)
        and (row.get("accepted_candidate") is not True or row.get("bearing_deg") is not None)
        for row in events
    )
    checks["target_scenes_shared_found"] = (
        len(target_fusion) == 2
        and all(row.get("shared_found") is True and row.get("outcome") == "true_positive" for row in target_fusion)
        and summary.get("target_false_negative_scenes") == []
        and summary.get("shared_target_found") is True
    )
    checks["teammate_only_no_false_positive"] = (
        len(teammate_fusion) == 2
        and all(row.get("shared_found") is False and row.get("outcome") == "true_negative" for row in teammate_fusion)
        and summary.get("teammate_false_positive_scenes") == []
        and summary.get("teammate_event_accepted_count") == 0
    )
    checks["baseline_no_false_positive"] = (
        len(baseline_fusion) == 1
        and all(row.get("shared_found") is False and row.get("outcome") == "true_negative" for row in baseline_fusion)
        and summary.get("baseline_false_positive_scenes") == []
    )
    checks["duplicate_observations_fused"] = (
        bool(duplicate_rows)
        and all(int(row.get("accepted_candidate_count", 0)) >= 2 and int(row.get("fused_candidate_count", 0)) == 1 for row in duplicate_rows)
        and summary.get("duplicate_merge_failed_scenes") == []
    )
    checks["teammate_position_exclusion_enabled"] = (
        config.get("teammate_identity_position_available_externally") is True
        and config.get("teammate_position_used_for_candidate_exclusion") is True
        and summary.get("teammate_identity_position_available_externally") is True
        and summary.get("teammate_position_used_for_candidate_exclusion") is True
    )
    checks["reliable_distance_boundary_35m"] = (
        float(config.get("reliable_distance_limit_m", -1.0)) == 35.0
        and float(summary.get("reliable_distance_limit_m", -1.0)) == 35.0
    )
    checks["truth_flags_false"] = (
        config.get("truth_used_for_detection") is False
        and summary.get("truth_used_for_detection") is False
        and _truth_flags_false(events)
        and _truth_flags_false(fusion_trace)
    )
    checks["no_semantic_or_sonar_detection"] = (
        config.get("semantic_sensor_used_for_detection") is False
        and summary.get("semantic_sensor_used_for_detection") is False
        and config.get("sonar_used") is False
        and summary.get("sonar_used") is False
    )
    checks["phase_limited_git_changes"] = _phase_limited(git_status)
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")
    checks["validation_outputs_present"] = (
        summary.get("all_scene_launch_ok") is True
        and summary.get("all_observer_rgb_output") is True
        and summary.get("all_observer_rangefinder_output") is True
    )

    metrics = {
        "recommended_rule_id": summary.get("recommended_rule_id"),
        "observer_count": summary.get("observer_count"),
        "scene_count": summary.get("scene_count"),
        "event_count": summary.get("event_count"),
        "fusion_outcome_counts": summary.get("fusion_outcome_counts"),
        "target_fusion_outcome_counts": summary.get("target_fusion_outcome_counts"),
        "teammate_fusion_outcome_counts": summary.get("teammate_fusion_outcome_counts"),
        "target_false_negative_scenes": summary.get("target_false_negative_scenes"),
        "teammate_false_positive_scenes": summary.get("teammate_false_positive_scenes"),
        "duplicate_merge_scenes": summary.get("duplicate_merge_scenes"),
        "shared_target_found": summary.get("shared_target_found"),
    }
    report = {"phase_name": PHASE_NAME, "checks": checks, "metrics": metrics, "all_passed": all(checks.values())}
    _save_json(AUDIT_JSON, report)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_md(checks, metrics))
    print("All passed:", report["all_passed"])


if __name__ == "__main__":
    main()
