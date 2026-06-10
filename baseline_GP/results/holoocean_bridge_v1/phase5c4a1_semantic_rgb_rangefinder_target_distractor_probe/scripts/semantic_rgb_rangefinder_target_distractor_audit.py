"""Audit for Phase 5C-4A-1 semantic/RGB/rangefinder target-distractor probe."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4a1_semantic_rgb_rangefinder_target_distractor_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "semantic_rgb_rangefinder_target_distractor_probe.py"))
AUDIT_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "semantic_rgb_rangefinder_target_distractor_audit.py"))
CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_config.json"))
SCENE_RESULTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_scene_results.json"))
DETECTION_EVENTS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_detection_events.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_tick_trace.csv"))
CONCLUSION_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_conclusion.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "semantic_rgb_rangefinder_target_distractor_summary.md"))
AUDIT_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_rgb_rangefinder_target_distractor_audit.json"))
AUDIT_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "semantic_rgb_rangefinder_target_distractor_audit_summary.md"))


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_load(path: str, checks: Dict[str, bool], key: str) -> Any:
    try:
        data = _load_json(path)
        checks[key] = True
        return data
    except Exception:
        checks[key] = False
        return None


def _source_checks(source: str) -> Dict[str, bool]:
    forbidden_runtime_tokens = [
        "marine_knownmap_runtime",
        "core_search_policy",
        "detect_targets",
        "update_found_mask",
        "hit_update_intensity",
        "_joint_assign_two_usv_segments",
        "_apply_team_miss_updates",
        "_sample_and_update_team_gp",
        "_update_team_search_info_state",
    ]
    return {
        "source_imports_holoocean": "import holoocean" in source.lower(),
        "source_uses_env_act": "env.act(" in source,
        "source_uses_env_tick": "env.tick(" in source,
        "source_no_env_step": "env.step(" not in source,
        "source_contains_semantic_camera": "SemanticSegmentationCamera" in source,
        "source_contains_rgb_camera": "RGBCamera" in source,
        "source_contains_rangefinder": "RangeFinderSensor" in source,
        "source_no_sonar_sensor": (
            "SinglebeamSonar" not in source
            and "ImagingSonar" not in source
            and "ProfilingSonar" not in source
            and "AcousticBeaconSensor" not in source
        ),
        "source_no_runtime_or_search_updates": all(token not in source for token in forbidden_runtime_tokens),
    }


def _artifact_paths_exist(scene_results: List[Dict[str, Any]]) -> bool:
    for result in scene_results:
        artifacts = result.get("artifacts", {})
        for key in ("rgb_preview_path", "semantic_preview_path", "semantic_raw_path"):
            path = artifacts.get(key)
            if not path or not os.path.exists(path):
                return False
    return True


def _events_have_sensor_evidence(detection_events: List[Dict[str, Any]]) -> bool:
    required = {"SemanticSegmentationCamera", "RGBCamera", "RangeFinderSensor"}
    for event in detection_events:
        evidence = event.get("sensor_evidence", {})
        if set(evidence.keys()) != required:
            return False
        if not event.get("identity_decision_source"):
            return False
        range_evidence = evidence.get("RangeFinderSensor", {})
        if bool(range_evidence.get("identity_supported", True)):
            return False
    return True


def _build_report(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4A-1 Semantic/RGB/RangeFinder Target-Distractor Audit Summary",
        "",
        "## Status",
        "- Overall: `{0}`".format("PASSED" if all(checks.values()) else "FAILED"),
        "- Checks: `{0}`".format(len(checks)),
        "- Semantic Can Distinguish: `{0}`".format(metrics.get("semantic_can_distinguish_target_from_distractor")),
        "- RGB Can Distinguish: `{0}`".format(metrics.get("rgb_can_distinguish_target_from_distractor")),
        "- RangeFinder Object Presence Supported: `{0}`".format(metrics.get("rangefinder_object_presence_supported")),
        "- Composite Sensor Detection Supported: `{0}`".format(metrics.get("composite_sensor_detection_supported")),
        "",
        "## Checks",
        "| Check | Result |",
        "| :--- | :---: |",
    ]
    for key in sorted(checks.keys()):
        lines.append("| `{0}` | `{1}` |".format(key, bool(checks[key])))
    lines.extend(["", "## Metrics", "```json", json.dumps(metrics, indent=2), "```", ""])
    return "\n".join(lines)


def run_audit() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    for key, path in {
        "probe_script_exists": PROBE_SCRIPT,
        "audit_script_exists": AUDIT_SCRIPT,
        "config_json_exists": CONFIG_JSON,
        "scene_results_json_exists": SCENE_RESULTS_JSON,
        "detection_events_json_exists": DETECTION_EVENTS_JSON,
        "tick_trace_json_exists": TICK_TRACE_JSON,
        "tick_trace_csv_exists": TICK_TRACE_CSV,
        "conclusion_json_exists": CONCLUSION_JSON,
        "git_status_json_exists": GIT_STATUS_JSON,
        "summary_md_exists": SUMMARY_MD,
    }.items():
        checks[key] = os.path.exists(path)

    config = _safe_load(CONFIG_JSON, checks, "config_json_parse_ok")
    scene_results = _safe_load(SCENE_RESULTS_JSON, checks, "scene_results_json_parse_ok")
    detection_events = _safe_load(DETECTION_EVENTS_JSON, checks, "detection_events_json_parse_ok")
    tick_trace = _safe_load(TICK_TRACE_JSON, checks, "tick_trace_json_parse_ok")
    conclusion = _safe_load(CONCLUSION_JSON, checks, "conclusion_json_parse_ok")
    git_status = _safe_load(GIT_STATUS_JSON, checks, "git_status_json_parse_ok")

    if config is None:
        config = {}
    if not isinstance(scene_results, list):
        scene_results = []
    if not isinstance(detection_events, list):
        detection_events = []
    if not isinstance(tick_trace, list):
        tick_trace = []
    if conclusion is None:
        conclusion = {}
    if git_status is None:
        git_status = {}

    with open(PROBE_SCRIPT, "r", encoding="utf-8") as f:
        source = f.read()
    checks.update(_source_checks(source))

    checks["phase_name_correct"] = config.get("phase_name") == PHASE_NAME and conclusion.get("phase_name") == PHASE_NAME
    checks["only_stage_dir_changes"] = not bool(git_status.get("outside_phase_new_or_changed", []))
    checks["config_sonar_disabled"] = not bool(config.get("sonar_used", True))
    checks["config_runtime_not_imported"] = not bool(config.get("runtime_imported", True))
    checks["search_decision_algorithm_not_modified_flag"] = not bool(config.get("search_decision_algorithm_modified", True))
    checks["truth_not_used_for_detection"] = not bool(config.get("truth_used_for_detection", True)) and not bool(conclusion.get("truth_used_for_detection", True))
    checks["config_perception_sensors_explicit"] = config.get("perception_sensors") == [
        "SemanticSegmentationCamera",
        "RGBCamera",
        "RangeFinderSensor",
    ]
    checks["config_navigation_sensors_not_detection_evidence"] = config.get("navigation_sensors_not_detection_evidence") == [
        "LocationSensor",
        "GPSSensor",
        "OrientationSensor",
    ]
    sensor_roles = config.get("sensor_roles", {})
    checks["config_sensor_roles_explicit"] = all(
        key in sensor_roles
        for key in ("SemanticSegmentationCamera", "RGBCamera", "RangeFinderSensor")
    )
    checks["all_expected_scenes_present"] = sorted([r.get("scene") for r in scene_results]) == [
        "baseline",
        "distractor_only",
        "target_and_distractor",
        "target_only",
    ]
    checks["all_scene_launch_ok"] = bool(conclusion.get("all_scene_launch_ok", False))
    checks["all_scenes_rgb_output"] = bool(conclusion.get("all_scenes_rgb_output", False))
    checks["all_scenes_semantic_output"] = bool(conclusion.get("all_scenes_semantic_output", False))
    checks["all_scenes_rangefinder_output"] = bool(conclusion.get("all_scenes_rangefinder_output", False))
    checks["semantic_identity_conclusion_recorded"] = (
        "semantic_identity_supported" in conclusion
        and "semantic_can_distinguish_target_from_distractor" in conclusion
    )
    checks["rgb_target_signature_present"] = bool(conclusion.get("rgb_target_signature_present", False))
    checks["rgb_distractor_signature_present"] = bool(conclusion.get("rgb_distractor_signature_present", False))
    checks["rgb_target_distractor_disjoint"] = bool(conclusion.get("rgb_target_vs_distractor_disjoint", False))
    checks["rgb_can_distinguish"] = bool(conclusion.get("rgb_can_distinguish_target_from_distractor", False))
    checks["rangefinder_object_presence_supported"] = bool(conclusion.get("rangefinder_object_presence_supported", False))
    checks["composite_sensor_detection_supported"] = bool(conclusion.get("composite_sensor_detection_supported", False))
    checks["rgb_available_as_visual_evidence"] = bool(conclusion.get("rgb_available_as_visual_evidence", False))
    checks["rangefinder_available_as_range_evidence"] = bool(conclusion.get("rangefinder_available_as_range_evidence", False))
    checks["all_detection_events_correct"] = bool(conclusion.get("all_detection_events_correct", False))
    checks["four_detection_events"] = len(detection_events) == 4
    checks["detection_events_sensor_evidence_schema"] = _events_have_sensor_evidence(detection_events)
    checks["detection_events_have_source_and_no_truth"] = all(
        event.get("detection_event_source") and not bool(event.get("truth_used_for_detection", True))
        for event in detection_events
    )
    checks["tick_trace_nonempty"] = len(tick_trace) > 0
    checks["visual_artifacts_exist"] = _artifact_paths_exist(scene_results)

    metrics = {
        "semantic_can_distinguish_target_from_distractor": conclusion.get("semantic_can_distinguish_target_from_distractor"),
        "semantic_identity_supported": conclusion.get("semantic_identity_supported"),
        "rgb_can_distinguish_target_from_distractor": conclusion.get("rgb_can_distinguish_target_from_distractor"),
        "rangefinder_object_presence_supported": conclusion.get("rangefinder_object_presence_supported"),
        "composite_sensor_detection_supported": conclusion.get("composite_sensor_detection_supported"),
        "rgb_available_as_visual_evidence": conclusion.get("rgb_available_as_visual_evidence"),
        "rangefinder_available_as_range_evidence": conclusion.get("rangefinder_available_as_range_evidence"),
        "all_detection_events_correct": conclusion.get("all_detection_events_correct"),
        "target_signature_colors": conclusion.get("target_signature_colors"),
        "distractor_signature_colors": conclusion.get("distractor_signature_colors"),
        "target_vs_distractor_semantic_disjoint": conclusion.get("target_vs_distractor_semantic_disjoint"),
        "rgb_target_signature_colors": conclusion.get("rgb_target_signature_colors"),
        "rgb_distractor_signature_colors": conclusion.get("rgb_distractor_signature_colors"),
        "rgb_target_vs_distractor_disjoint": conclusion.get("rgb_target_vs_distractor_disjoint"),
        "rangefinder_object_scene_hits": conclusion.get("rangefinder_object_scene_hits"),
        "outside_phase_new_or_changed": git_status.get("outside_phase_new_or_changed", []),
    }
    audit = {
        "all_passed": bool(all(checks.values())),
        "checks": checks,
        "metrics": metrics,
    }
    os.makedirs(os.path.dirname(AUDIT_JSON), exist_ok=True)
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(_build_report(checks, metrics))
    print("Audit JSON saved to: {0}".format(AUDIT_JSON))
    print("Audit summary saved to: {0}".format(AUDIT_MD))
    print("all_passed={0}, checks={1}".format(audit["all_passed"], len(checks)))
    return audit


def main() -> None:
    run_audit()


if __name__ == "__main__":
    main()
