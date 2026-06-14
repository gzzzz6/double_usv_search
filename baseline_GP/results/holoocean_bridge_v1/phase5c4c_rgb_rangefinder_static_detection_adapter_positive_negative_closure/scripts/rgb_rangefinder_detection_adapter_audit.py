"""Audit for Phase 5C-4C RGB+RangeFinder positive/negative closure."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4c_rgb_rangefinder_static_detection_adapter_positive_negative_closure"
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


def _events_by_scene(events: Any) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not isinstance(events, list):
        return result
    for event in events:
        if isinstance(event, dict) and "scene" in event:
            result[str(event["scene"])] = event
    return result


def _all_paths_exist(paths: List[str]) -> bool:
    return all(os.path.exists(path) for path in paths)


def _log_ok(path: str, marker: str) -> bool:
    text = _read_text(path)
    return bool(marker in text and "Traceback" not in text and "SyntaxError" not in text)


def _build_audit_md(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4C RGB+RangeFinder Detection Adapter Audit Summary",
        "",
        "## Metrics",
        "- Probe Completed: `{0}`".format(metrics.get("probe_completed")),
        "- Positive Scenes Detected: `{0}`".format(metrics.get("positive_scenes_detected")),
        "- Negative Scenes Not Detected: `{0}`".format(metrics.get("negative_scenes_not_detected")),
        "- Runtime Positive Scenes Found: `{0}`".format(metrics.get("runtime_positive_scenes_found")),
        "- Runtime Negative Scenes Not Found: `{0}`".format(metrics.get("runtime_negative_scenes_not_found")),
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

    events_by_scene = _events_by_scene(events)
    probe_source = _read_text(PROBE_SCRIPT)
    audit_source = _read_text(AUDIT_SCRIPT)
    required_scene_names = ("baseline", "target_only", "distractor_only", "target_and_distractor")
    required_scene_set = set(required_scene_names)
    scene_sensor_outcomes = summary.get("scene_sensor_outcomes", {}) if isinstance(summary.get("scene_sensor_outcomes", {}), dict) else {}
    scene_runtime_outcomes = summary.get("scene_runtime_outcomes", {}) if isinstance(summary.get("scene_runtime_outcomes", {}), dict) else {}
    runtime_update_by_scene = runtime_update if isinstance(runtime_update, dict) else {}
    scene_cfg = {}
    for scene in config.get("scenes", []):
        if isinstance(scene, dict) and "name" in scene:
            scene_cfg[str(scene["name"])] = scene

    checks["config_scene_names_exact"] = set(scene_cfg.keys()) == required_scene_set
    checks["scene_results_scene_names_exact"] = set(scene_results.keys()) == required_scene_set
    checks["events_scene_names_exact"] = set(events_by_scene.keys()) == required_scene_set
    checks["four_detection_events"] = len(events) == 4
    checks["scene_sensor_outcomes_complete"] = set(scene_sensor_outcomes.keys()) == required_scene_set
    checks["scene_runtime_outcomes_complete"] = set(scene_runtime_outcomes.keys()) == required_scene_set
    checks["runtime_update_scene_names_exact"] = set(runtime_update_by_scene.keys()) == required_scene_set

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
        and all(bool(event.get("truth_used_for_detection", True)) is False for event in events)
        and all(bool(event.get("actor_truth_used_for_detection", True)) is False for event in events)
        and all(bool(event.get("target_truth_used_for_detection", True)) is False for event in events)
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

    baseline_event = events_by_scene.get("baseline", {})
    target_only_event = events_by_scene.get("target_only", {})
    distractor_only_event = events_by_scene.get("distractor_only", {})
    target_and_distractor_event = events_by_scene.get("target_and_distractor", {})

    baseline_evidence = baseline_event.get("sensor_evidence", {}) if isinstance(baseline_event, dict) else {}
    target_evidence = target_only_event.get("sensor_evidence", {}) if isinstance(target_only_event, dict) else {}
    distractor_evidence = distractor_only_event.get("sensor_evidence", {}) if isinstance(distractor_only_event, dict) else {}
    both_evidence = target_and_distractor_event.get("sensor_evidence", {}) if isinstance(target_and_distractor_event, dict) else {}
    baseline_rgb = baseline_evidence.get("RGBCamera", {}) if isinstance(baseline_evidence, dict) else {}
    target_rgb = target_evidence.get("RGBCamera", {}) if isinstance(target_evidence, dict) else {}
    distractor_rgb = distractor_evidence.get("RGBCamera", {}) if isinstance(distractor_evidence, dict) else {}
    both_rgb = both_evidence.get("RGBCamera", {}) if isinstance(both_evidence, dict) else {}
    baseline_range = baseline_evidence.get("RangeFinderSensor", {}) if isinstance(baseline_evidence, dict) else {}
    target_range = target_evidence.get("RangeFinderSensor", {}) if isinstance(target_evidence, dict) else {}
    distractor_range = distractor_evidence.get("RangeFinderSensor", {}) if isinstance(distractor_evidence, dict) else {}
    both_range = both_evidence.get("RangeFinderSensor", {}) if isinstance(both_evidence, dict) else {}

    checks["event_has_rgb_and_range_evidence"] = all(
        bool(events_by_scene[name].get("sensor_evidence", {}).get("RGBCamera", {}))
        and bool(events_by_scene[name].get("sensor_evidence", {}).get("RangeFinderSensor", {}))
        for name in required_scene_names
    )
    checks["baseline_scene_negative"] = (
        baseline_event.get("expected_target_present_for_audit") is False
        and baseline_event.get("sensor_detected_target") is False
        and baseline_event.get("rgb_has_target_signature") is False
        and baseline_event.get("rangefinder_hit") is False
        and baseline_event.get("distractor_false_positive") is False
    )
    checks["target_only_scene_positive"] = (
        target_only_event.get("expected_target_present_for_audit") is True
        and target_only_event.get("sensor_detected_target") is True
        and target_only_event.get("rgb_has_target_signature") is True
        and target_only_event.get("rangefinder_hit") is True
        and target_only_event.get("distractor_false_positive") is False
        and target_only_event.get("target_detection_correct_for_scene") is True
    )
    checks["distractor_only_scene_negative"] = (
        distractor_only_event.get("expected_target_present_for_audit") is False
        and distractor_only_event.get("sensor_detected_target") is False
        and distractor_only_event.get("rgb_has_target_signature") is False
        and distractor_only_event.get("rangefinder_hit") is True
        and distractor_only_event.get("distractor_false_positive") is False
        and distractor_only_event.get("target_detection_correct_for_scene") is True
    )
    checks["target_and_distractor_scene_positive"] = (
        target_and_distractor_event.get("expected_target_present_for_audit") is True
        and target_and_distractor_event.get("sensor_detected_target") is True
        and target_and_distractor_event.get("rgb_has_target_signature") is True
        and target_and_distractor_event.get("rangefinder_hit") is True
        and target_and_distractor_event.get("distractor_false_positive") is False
        and target_and_distractor_event.get("target_detection_correct_for_scene") is True
    )
    checks["identity_decision_from_rgb"] = all(
        events_by_scene[name].get("identity_decision_source") == "RGBCamera"
        for name in ("target_only", "target_and_distractor")
    )
    checks["rangefinder_not_identity_source"] = all(
        events_by_scene[name].get("sensor_evidence", {}).get("RangeFinderSensor", {}).get("identity_supported") is False
        for name in required_scene_names
    )
    checks["found_trigger_rule_exact"] = all(
        events_by_scene[name].get("found_trigger_rule") == "rgb_has_target_signature and rangefinder_hit"
        for name in required_scene_names
    )
    checks["found_trigger_rule_applied"] = all(
        bool(events_by_scene[name].get("sensor_detected_target")) == bool(
            events_by_scene[name].get("rgb_has_target_signature") and events_by_scene[name].get("rangefinder_hit")
        )
        for name in required_scene_names
    )
    checks["target_index_mapping_contract"] = all(
        events_by_scene[name].get("target_index_mapping_source") == "single_target_static_adapter_contract"
        for name in ("target_only", "target_and_distractor")
    ) and all(events_by_scene[name].get("target_index_selected") == 0 for name in ("target_only", "target_and_distractor"))
    checks["all_scene_launch_ok"] = all(bool(v.get("launch_ok", False)) for v in scene_results.values())
    checks["all_scenes_rgb_output"] = all(bool(v.get("rgb_stats", {}).get("present", False)) for v in scene_results.values())
    checks["all_scenes_rangefinder_output"] = all(bool(v.get("rangefinder_summary", {}).get("present", False)) for v in scene_results.values())
    checks["runtime_baseline_no_found"] = runtime_update_by_scene.get("baseline", {}).get("found_mask_after") == [False]
    checks["runtime_target_only_found"] = runtime_update_by_scene.get("target_only", {}).get("found_mask_after") == [True]
    checks["runtime_distractor_only_no_found"] = runtime_update_by_scene.get("distractor_only", {}).get("found_mask_after") == [False]
    checks["runtime_target_and_distractor_found"] = runtime_update_by_scene.get("target_and_distractor", {}).get("found_mask_after") == [True]
    checks["runtime_positive_found_indices"] = (
        runtime_update_by_scene.get("target_only", {}).get("new_found_indices") == [0]
        and runtime_update_by_scene.get("target_and_distractor", {}).get("new_found_indices") == [0]
    )
    checks["runtime_negative_no_found_indices"] = (
        runtime_update_by_scene.get("baseline", {}).get("new_found_indices") == []
        and runtime_update_by_scene.get("distractor_only", {}).get("new_found_indices") == []
    )
    checks["runtime_hit_update_positive_only"] = (
        runtime_update_by_scene.get("target_only", {}).get("hit_update_called") is True
        and runtime_update_by_scene.get("target_and_distractor", {}).get("hit_update_called") is True
        and runtime_update_by_scene.get("baseline", {}).get("hit_update_called") is False
        and runtime_update_by_scene.get("distractor_only", {}).get("hit_update_called") is False
    )
    checks["runtime_gp_update_all_scenes"] = all(
        bool(runtime_update_by_scene.get(name, {}).get("team_gp_update_called", False))
        for name in required_scene_names
    )
    checks["runtime_search_info_update_all_scenes"] = all(
        bool(runtime_update_by_scene.get(name, {}).get("team_search_info_update_called", False))
        for name in required_scene_names
    )
    checks["runtime_miss_update_skipped_all_scenes"] = all(
        runtime_update_by_scene.get(name, {}).get("team_miss_update_called") is False
        and runtime_update_by_scene.get(name, {}).get("circular_miss_update_skipped_due_to_camera_fov") is True
        for name in required_scene_names
    )
    checks["scene_sensor_outcomes_match_events"] = all(
        scene_sensor_outcomes.get(name, {}).get("expected_sensor_detected_target") == events_by_scene.get(name, {}).get("expected_sensor_detected_target")
        and scene_sensor_outcomes.get(name, {}).get("sensor_detected_target") == events_by_scene.get(name, {}).get("sensor_detected_target")
        and scene_sensor_outcomes.get(name, {}).get("target_detection_correct_for_scene") == events_by_scene.get(name, {}).get("target_detection_correct_for_scene")
        for name in required_scene_names
    )
    checks["scene_runtime_outcomes_match_runtime"] = all(
        scene_runtime_outcomes.get(name, {}).get("found_mask_after") == runtime_update_by_scene.get(name, {}).get("found_mask_after")
        and scene_runtime_outcomes.get(name, {}).get("hit_update_called") == runtime_update_by_scene.get(name, {}).get("hit_update_called")
        for name in required_scene_names
    )
    checks["summary_positive_negative_flags"] = (
        summary.get("positive_scenes_detected") is True
        and summary.get("negative_scenes_not_detected") is True
        and summary.get("runtime_positive_scenes_found") is True
        and summary.get("runtime_negative_scenes_not_found") is True
        and summary.get("all_detection_events_correct") is True
        and summary.get("distractor_only_no_false_positive") is True
        and summary.get("target_and_distractor_detected") is True
    )
    checks["summary_target_distractor_signature_flags"] = (
        summary.get("target_signature_present") is True
        and summary.get("distractor_signature_present") is True
        and summary.get("rgb_target_vs_distractor_disjoint") is True
    )
    checks["summary_rangefinder_presence_flag"] = summary.get("rangefinder_object_presence_supported") is True
    checks["summary_rangefinder_hit_matrix"] = summary.get("rangefinder_hit_by_scene") == {
        "baseline": False,
        "target_only": True,
        "distractor_only": True,
        "target_and_distractor": True,
    }
    checks["summary_gp_search_info_flags"] = (
        summary.get("team_gp_update_all_scenes") is True
        and summary.get("team_search_info_update_all_scenes") is True
    )
    checks["summary_runtime_miss_skipped"] = summary.get("circular_miss_update_applied_any") is False
    checks["summary_scene_matrices_complete"] = (
        set(summary.get("scene_sensor_outcomes", {}).keys()) == required_scene_set
        and set(summary.get("scene_runtime_outcomes", {}).keys()) == required_scene_set
    )
    checks["remaining_intensity_positive_zero_positive_scenes"] = (
        abs(float(runtime_update_by_scene.get("target_only", {}).get("remaining_intensity_mass_after", 1.0))) <= 1e-9
        and abs(float(runtime_update_by_scene.get("target_and_distractor", {}).get("remaining_intensity_mass_after", 1.0))) <= 1e-9
    )
    checks["negative_scene_remaining_mass_positive"] = (
        float(runtime_update_by_scene.get("baseline", {}).get("remaining_intensity_mass_after", 0.0)) > 0.0
        and float(runtime_update_by_scene.get("distractor_only", {}).get("remaining_intensity_mass_after", 0.0)) > 0.0
    )
    checks["gp_count_increased_all_scenes"] = all(
        isinstance(runtime_update_by_scene.get(name, {}).get("initial_gp_n_obs"), int)
        and isinstance(runtime_update_by_scene.get(name, {}).get("final_gp_n_obs"), int)
        and int(runtime_update_by_scene.get(name, {}).get("final_gp_n_obs")) > int(runtime_update_by_scene.get(name, {}).get("initial_gp_n_obs"))
        and runtime_update_by_scene.get(name, {}).get("final_gp_count_consistent") is True
        for name in required_scene_names
    )
    checks["search_info_valid"] = all(
        bool(runtime_update_by_scene.get(name, {}).get("final_search_info_valid", False))
        for name in required_scene_names
    )
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
        "positive_scenes_detected": summary.get("positive_scenes_detected"),
        "negative_scenes_not_detected": summary.get("negative_scenes_not_detected"),
        "runtime_positive_scenes_found": summary.get("runtime_positive_scenes_found"),
        "runtime_negative_scenes_not_found": summary.get("runtime_negative_scenes_not_found"),
        "distractor_only_no_false_positive": summary.get("distractor_only_no_false_positive"),
        "target_and_distractor_detected": summary.get("target_and_distractor_detected"),
        "truth_used_for_detection": summary.get("truth_used_for_detection"),
        "scene_sensor_outcomes": summary.get("scene_sensor_outcomes"),
        "scene_runtime_outcomes": summary.get("scene_runtime_outcomes"),
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
    print("Phase 5C-4C audit finished: all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()
