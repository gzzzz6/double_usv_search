"""Audit for Phase 5C-4B RGB+RangeFinder detection adapter mini-closure."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4b_rgb_rangefinder_static_detection_adapter_miniclosure"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "rgb_rangefinder_detection_adapter_probe.py"))
AUDIT_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "rgb_rangefinder_detection_adapter_audit.py"))
CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_tick_trace.csv"))
RUNTIME_UPDATE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_runtime_update.json"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_rangefinder_detection_adapter_summary.md"))
AUDIT_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "rgb_rangefinder_detection_adapter_audit.json"))
AUDIT_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "rgb_rangefinder_detection_adapter_audit_summary.md"))
BASE_COMPILE_LOG = os.path.normpath(os.path.join(PHASE_DIR, "logs", "rgb_rangefinder_detection_adapter_py_compile_base.txt"))
HOLO_COMPILE_LOG = os.path.normpath(os.path.join(PHASE_DIR, "logs", "rgb_rangefinder_detection_adapter_py_compile_holo.txt"))


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


def _detection_event(events: Any) -> Dict[str, Any]:
    if not isinstance(events, list):
        return {}
    for event in events:
        if isinstance(event, dict) and event.get("event_name") == "detection_step_sensor_adapter_event":
            return event
    return {}


def _negative_event(events: Any) -> Dict[str, Any]:
    if not isinstance(events, list):
        return {}
    for event in events:
        if isinstance(event, dict) and event.get("event_name") == "baseline_no_target_negative_check":
            return event
    return {}


def _all_paths_exist(paths: List[str]) -> bool:
    return all(os.path.exists(path) for path in paths)


def _log_ok(path: str, marker: str) -> bool:
    text = _read_text(path)
    return bool(marker in text and "Traceback" not in text and "SyntaxError" not in text)


def _build_audit_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4B RGB+RangeFinder Detection Adapter Audit Summary",
        "",
        "## Metrics",
        "- Probe Completed: `{0}`".format(metrics.get("probe_completed")),
        "- Sensor Detected Target: `{0}`".format(metrics.get("sensor_detected_target")),
        "- Found Mask Final: `{0}`".format(metrics.get("found_mask_final")),
        "- Truth Used For Detection: `{0}`".format(metrics.get("truth_used_for_detection")),
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
        RUNTIME_UPDATE_JSON,
        SUMMARY_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        BASE_COMPILE_LOG,
        HOLO_COMPILE_LOG,
    ]
    checks["required_paths_exist"] = _all_paths_exist(required_paths)

    config = _safe_load(CONFIG_JSON, checks, "config_json_parse_ok")
    scene_results = _safe_load(SCENE_RESULTS_JSON, checks, "scene_results_json_parse_ok")
    events = _safe_load(DETECTION_EVENTS_JSON, checks, "detection_events_json_parse_ok")
    runtime_update = _safe_load(RUNTIME_UPDATE_JSON, checks, "runtime_update_json_parse_ok")
    summary = _safe_load(SUMMARY_JSON, checks, "summary_json_parse_ok")
    git_status = _safe_load(GIT_STATUS_JSON, checks, "git_status_json_parse_ok")

    if not isinstance(config, dict):
        config = {}
    if not isinstance(scene_results, dict):
        scene_results = {}
    if not isinstance(runtime_update, dict):
        runtime_update = {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(git_status, dict):
        git_status = {}

    event = _detection_event(events)
    negative = _negative_event(events)
    probe_source = _read_text(PROBE_SCRIPT)
    audit_source = _read_text(AUDIT_SCRIPT)

    checks["phase_name_matches"] = (
        config.get("phase_name") == PHASE_NAME
        and summary.get("phase_name") == PHASE_NAME
        and git_status.get("phase_name") == PHASE_NAME
    )
    checks["perception_sensors_exact"] = (
        config.get("perception_sensors") == ["RGBCamera", "RangeFinderSensor"]
        and summary.get("perception_sensors") == ["RGBCamera", "RangeFinderSensor"]
    )
    checks["semantic_not_used_for_detection"] = (
        config.get("semantic_sensor_used_for_detection") is False
        and summary.get("semantic_sensor_used_for_detection") is False
        and "SemanticSegmentationCamera" not in config.get("perception_sensors", [])
        and "SemanticSegmentationCamera" not in summary.get("perception_sensors", [])
        and "\"sensor_type\": \"SemanticSegmentationCamera\"" not in probe_source
    )
    checks["sonar_not_used"] = (
        config.get("sonar_used") is False
        and summary.get("sonar_used") is False
        and "Sonar" not in probe_source
        and "sonar" in probe_source
    )
    checks["truth_flags_false"] = (
        config.get("truth_used_for_detection") is False
        and config.get("actor_truth_used_for_detection") is False
        and config.get("target_truth_used_for_detection") is False
        and event.get("truth_used_for_detection") is False
        and event.get("actor_truth_used_for_detection") is False
        and event.get("target_truth_used_for_detection") is False
        and summary.get("truth_used_for_detection") is False
        and summary.get("actor_truth_used_for_detection") is False
        and summary.get("target_truth_used_for_detection") is False
    )
    checks["source_has_mode_split"] = "choices=[\"capture\", \"runtime\"]" in probe_source and "def _runtime_imports" in probe_source
    checks["source_uses_env_act_tick"] = "env.act(" in probe_source and "env.tick(" in probe_source
    checks["source_does_not_use_env_step"] = "env.step(" not in probe_source
    checks["source_does_not_call_baseline_detect_targets"] = "detect_targets(" not in probe_source
    checks["source_contains_update_found_mask"] = "update_found_mask" in probe_source
    checks["source_contains_hit_update_intensity"] = "hit_update_intensity" in probe_source
    checks["source_contains_gp_update"] = "_sample_and_update_team_gp" in probe_source
    checks["source_contains_search_info_update"] = "_update_team_search_info_state" in probe_source

    sensor_evidence = event.get("sensor_evidence", {}) if isinstance(event, dict) else {}
    rgb_evidence = sensor_evidence.get("RGBCamera", {}) if isinstance(sensor_evidence, dict) else {}
    range_evidence = sensor_evidence.get("RangeFinderSensor", {}) if isinstance(sensor_evidence, dict) else {}
    checks["event_has_rgb_and_range_evidence"] = bool(rgb_evidence) and bool(range_evidence)
    checks["rgb_identity_supported"] = bool(event.get("rgb_has_target_signature")) and bool(rgb_evidence.get("identity_supported"))
    checks["rangefinder_hit_supported"] = bool(event.get("rangefinder_hit")) and bool(range_evidence.get("hit"))
    checks["rangefinder_not_identity_source"] = range_evidence.get("identity_supported") is False
    checks["found_trigger_rule_exact"] = event.get("found_trigger_rule") == "rgb_has_target_signature and rangefinder_hit"
    checks["found_trigger_rule_applied"] = bool(event.get("sensor_detected_target")) == bool(
        event.get("rgb_has_target_signature") and event.get("rangefinder_hit")
    )
    checks["identity_decision_from_rgb"] = event.get("identity_decision_source") == "RGBCamera"
    checks["target_index_mapping_contract"] = (
        event.get("target_index_selected") == 0
        and event.get("target_index_mapping_source") == "single_target_static_adapter_contract"
    )
    checks["negative_scene_no_false_positive"] = (
        negative.get("expected_target_present_for_audit") is False
        and negative.get("sensor_detected_target") is False
        and negative.get("no_target_false_positive") is False
    )

    checks["all_scene_launch_ok"] = all(bool(v.get("launch_ok", False)) for v in scene_results.values())
    checks["all_scenes_rgb_output"] = all(bool(v.get("rgb_stats", {}).get("present", False)) for v in scene_results.values())
    checks["all_scenes_rangefinder_output"] = all(bool(v.get("rangefinder_summary", {}).get("present", False)) for v in scene_results.values())
    checks["runtime_update_found_mask_called"] = runtime_update.get("update_found_mask_called") is True
    checks["runtime_found_index_zero"] = runtime_update.get("new_found_indices") == [0]
    checks["runtime_found_mask_final_true"] = runtime_update.get("found_mask_after") == [True]
    checks["runtime_find_times_step_one"] = runtime_update.get("find_times_after") == [1]
    checks["runtime_hit_update_called"] = runtime_update.get("hit_update_called") is True
    checks["runtime_gp_update_called"] = runtime_update.get("team_gp_update_called") is True
    checks["runtime_search_info_update_called"] = runtime_update.get("team_search_info_update_called") is True
    checks["runtime_miss_update_skipped"] = (
        runtime_update.get("team_miss_update_called") is False
        and runtime_update.get("circular_miss_update_skipped_due_to_camera_fov") is True
    )
    checks["summary_found_final"] = summary.get("found_count_final") == 1 and summary.get("found_mask_final") == [True]
    checks["summary_hit_branch_covered"] = summary.get("hit_branch_covered") is True
    checks["remaining_intensity_zero"] = abs(float(summary.get("remaining_intensity_mass_final", 1.0))) <= 1e-9
    checks["gp_count_increased"] = (
        isinstance(summary.get("gp_n_obs_initial"), int)
        and isinstance(summary.get("gp_n_obs_final"), int)
        and int(summary.get("gp_n_obs_final")) > int(summary.get("gp_n_obs_initial"))
        and summary.get("gp_count_consistent_final") is True
    )
    checks["search_info_valid"] = summary.get("search_info_shape_ok_final") is True and summary.get("search_info_valid_final") is True
    checks["controlled_boundary_recorded"] = (
        "camera FOV-grid footprint replacement is not attempted" in config.get("controlled_simplifications", [])
        and "not a full replacement for baseline circular sensor geometry" in config.get("not_claimed", [])
    )
    checks["git_changes_limited_to_phase"] = git_status.get("outside_phase_new_or_changed") == []
    checks["base_py_compile_ok"] = _log_ok(BASE_COMPILE_LOG, "BASE_PY_COMPILE_OK")
    checks["holo_py_compile_ok"] = _log_ok(HOLO_COMPILE_LOG, "HOLO_PY_COMPILE_OK")
    checks["audit_source_compiled_marker_expected"] = "rgb_rangefinder_detection_adapter_audit.py" in _read_text(BASE_COMPILE_LOG)
    checks["probe_source_compiled_marker_expected"] = "rgb_rangefinder_detection_adapter_probe.py" in _read_text(BASE_COMPILE_LOG)
    checks["audit_source_readable"] = bool(audit_source)

    metrics = {
        "phase_name": PHASE_NAME,
        "probe_completed": summary.get("probe_completed"),
        "sensor_detected_target": summary.get("sensor_detected_target"),
        "rgb_has_target_signature": summary.get("rgb_has_target_signature"),
        "rangefinder_hit": summary.get("rangefinder_hit"),
        "truth_used_for_detection": summary.get("truth_used_for_detection"),
        "found_mask_final": summary.get("found_mask_final"),
        "find_times_final": summary.get("find_times_final"),
        "remaining_intensity_mass_final": summary.get("remaining_intensity_mass_final"),
        "gp_n_obs_initial": summary.get("gp_n_obs_initial"),
        "gp_n_obs_final": summary.get("gp_n_obs_final"),
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
    print("Phase 5C-4B audit finished: all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()
