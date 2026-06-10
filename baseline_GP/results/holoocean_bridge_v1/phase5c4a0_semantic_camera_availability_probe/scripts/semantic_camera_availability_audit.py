"""Audit for Phase 5C-4A-0 SemanticSegmentationCamera availability probe."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import numpy as np


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c4a0_semantic_camera_availability_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

PROBE_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "semantic_camera_availability_probe.py"))
AUDIT_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "semantic_camera_availability_audit.py"))
CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_config.json"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_tick_trace.csv"))
SENSOR_STATS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_sensor_stats.json"))
CONCLUSION_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_conclusion.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "semantic_camera_availability_summary.md"))
AUDIT_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "semantic_camera_availability_audit.json"))
AUDIT_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "semantic_camera_availability_audit_summary.md"))

REFERENCE_RGB_PNG = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "reference_rgb_first_valid.png"))
SEMANTIC_PREVIEW_PNG = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "semantic_first_valid_preview.png"))
SEMANTIC_RAW_NPY = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "semantic_first_valid_raw.npy"))


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


def _has_semantic_inspection_rows(tick_trace: List[Dict[str, Any]]) -> bool:
    for row in tick_trace:
        if bool(row.get("scenario_includes_semantic", False)) and int(row.get("tick", 0)) > 0:
            return "semantic_present" in row and "semantic_shape" in row and "semantic_dtype" in row
    return False


def _semantic_artifacts_ok(conclusion: Dict[str, Any]) -> bool:
    if not bool(conclusion.get("semantic_camera_available", False)):
        return True
    if not (bool(conclusion.get("semantic_raw_saved", False)) and bool(conclusion.get("semantic_preview_saved", False))):
        return False
    if not (os.path.exists(SEMANTIC_RAW_NPY) and os.path.exists(SEMANTIC_PREVIEW_PNG)):
        return False
    try:
        arr = np.load(SEMANTIC_RAW_NPY)
        stats = conclusion.get("semantic_first_stats", {})
        return list(arr.shape) == stats.get("shape") and int(arr.size) == int(stats.get("size", -1))
    except Exception:
        return False


def _source_checks(source: str) -> Dict[str, bool]:
    lower_source = source.lower()
    forbidden_runtime_tokens = [
        "marine_knownmap_runtime",
        "detect_targets",
        "update_found_mask",
        "hit_update_intensity",
        "_apply_team_miss_updates",
        "_sample_and_update_team_gp",
        "_update_team_search_info_state",
    ]
    return {
        "source_imports_holoocean": "import holoocean" in lower_source,
        "source_uses_env_act": "env.act(" in source,
        "source_uses_env_tick": "env.tick(" in source,
        "source_no_env_step": "env.step(" not in source,
        "source_contains_semantic_camera": "SemanticSegmentationCamera" in source,
        "source_contains_rgb_camera": "RGBCamera" in source,
        "source_no_sonar_sensor": (
            "SinglebeamSonar" not in source
            and "ImagingSonar" not in source
            and "ProfilingSonar" not in source
            and "AcousticBeaconSensor" not in source
        ),
        "source_no_runtime_updates": all(token not in source for token in forbidden_runtime_tokens),
        "source_no_target_agent": '"agent_name": "target"' not in source and "'agent_name': 'target'" not in source,
    }


def _build_report(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-4A-0 Semantic Camera Availability Audit Summary",
        "",
        "## Status",
        "- Overall: `{0}`".format("PASSED" if all(checks.values()) else "FAILED"),
        "- Checks: `{0}`".format(len(checks)),
        "- Semantic Camera Available: `{0}`".format(metrics.get("semantic_camera_available")),
        "- Availability Conclusion: `{0}`".format(metrics.get("availability_conclusion")),
        "",
        "## Checks",
        "| Check | Result |",
        "| :--- | :---: |",
    ]
    for key in sorted(checks.keys()):
        lines.append("| `{0}` | `{1}` |".format(key, bool(checks[key])))
    lines.extend(
        [
            "",
            "## Metrics",
            "```json",
            json.dumps(metrics, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}

    for key, path in {
        "probe_script_exists": PROBE_SCRIPT,
        "audit_script_exists": AUDIT_SCRIPT,
        "config_json_exists": CONFIG_JSON,
        "tick_trace_json_exists": TICK_TRACE_JSON,
        "tick_trace_csv_exists": TICK_TRACE_CSV,
        "sensor_stats_json_exists": SENSOR_STATS_JSON,
        "conclusion_json_exists": CONCLUSION_JSON,
        "git_status_json_exists": GIT_STATUS_JSON,
        "summary_md_exists": SUMMARY_MD,
    }.items():
        checks[key] = os.path.exists(path)

    config = _safe_load(CONFIG_JSON, checks, "config_json_parse_ok")
    tick_trace = _safe_load(TICK_TRACE_JSON, checks, "tick_trace_json_parse_ok")
    sensor_stats = _safe_load(SENSOR_STATS_JSON, checks, "sensor_stats_json_parse_ok")
    conclusion = _safe_load(CONCLUSION_JSON, checks, "conclusion_json_parse_ok")
    git_status = _safe_load(GIT_STATUS_JSON, checks, "git_status_json_parse_ok")

    if config is None:
        config = {}
    if not isinstance(tick_trace, list):
        tick_trace = []
    if sensor_stats is None:
        sensor_stats = {}
    if conclusion is None:
        conclusion = {}
    if git_status is None:
        git_status = {}

    checks["phase_name_correct"] = config.get("phase_name") == PHASE_NAME and conclusion.get("phase_name") == PHASE_NAME
    checks["map_is_res10_81x81"] = (
        int(config.get("map_height_cells", -1)) == 81
        and int(config.get("map_width_cells", -1)) == 81
        and float(config.get("resolution_m", -1.0)) == 10.0
    )
    checks["start_cell_center"] = config.get("start_cell") == [40, 40]
    checks["capture_ticks_30"] = int(config.get("capture_ticks", -1)) == 30
    checks["single_surface_vessel_config"] = (
        config.get("agent_name") == "sv0"
        and config.get("main_agent") == "sv0"
        and config.get("agent_type") == "SurfaceVessel"
        and int(config.get("control_scheme", -1)) == 0
    )
    checks["camera_config_expected"] = (
        config.get("rgb_camera_name") == "ReferenceRGBCamera"
        and config.get("semantic_camera_name") == "FrontSemanticSegmentationCamera"
        and int(config.get("camera_width", -1)) == 320
        and int(config.get("camera_height", -1)) == 240
        and int(config.get("camera_hz", -1)) == 5
    )
    checks["semantic_not_used_for_detection"] = not bool(config.get("semantic_camera_used_for_detection", True))
    checks["no_target_or_obstacle_or_sonar_config"] = (
        not bool(config.get("sonar_used", True))
        and not bool(config.get("target_agent_used", True))
        and not bool(config.get("obstacle_used", True))
        and not bool(config.get("runtime_imported", True))
    )

    with open(PROBE_SCRIPT, "r", encoding="utf-8") as f:
        source = f.read()
    checks.update(_source_checks(source))

    checks["probe_completed"] = bool(conclusion.get("probe_completed", False))
    checks["availability_conclusion_recorded"] = str(conclusion.get("availability_conclusion", "")) in {
        "available",
        "semantic_launch_ok_but_no_output",
        "semantic_unavailable_rgb_control_ok",
        "semantic_and_rgb_control_failed",
        "semantic_launch_failed_no_control_result",
    }
    checks["semantic_fields_recorded"] = (
        "semantic_camera_available" in conclusion
        and "semantic_scenario_launch_ok" in conclusion
        and "semantic_output_seen" in conclusion
    )
    checks["tick_trace_nonempty"] = len(tick_trace) > 0
    if bool(conclusion.get("semantic_scenario_launch_ok", False)):
        checks["semantic_inspection_rows_recorded"] = _has_semantic_inspection_rows(tick_trace)
    else:
        checks["semantic_inspection_rows_recorded"] = bool(conclusion.get("semantic_error"))
    if not bool(conclusion.get("semantic_scenario_launch_ok", False)):
        checks["control_result_recorded_when_semantic_launch_fails"] = conclusion.get("control_rgb_scenario_ok") is not None
    else:
        checks["control_result_recorded_when_semantic_launch_fails"] = True
    checks["semantic_artifacts_consistent"] = _semantic_artifacts_ok(conclusion)
    checks["rgb_artifact_present_when_output_seen"] = (
        not bool(conclusion.get("rgb_output_seen", False))
        or (bool(conclusion.get("rgb_preview_saved", False)) and os.path.exists(REFERENCE_RGB_PNG))
    )
    checks["sensor_stats_consistent"] = isinstance(sensor_stats.get("semantic_scenario", {}), dict)
    checks["git_changes_limited_to_phase_dir"] = not bool(git_status.get("outside_phase_new_or_changed", []))

    metrics = {
        "availability_conclusion": conclusion.get("availability_conclusion"),
        "semantic_camera_available": conclusion.get("semantic_camera_available"),
        "semantic_scenario_launch_ok": conclusion.get("semantic_scenario_launch_ok"),
        "semantic_output_seen": conclusion.get("semantic_output_seen"),
        "semantic_error": conclusion.get("semantic_error"),
        "control_rgb_scenario_ok": conclusion.get("control_rgb_scenario_ok"),
        "control_rgb_output_seen": conclusion.get("control_rgb_output_seen"),
        "control_error": conclusion.get("control_error"),
        "rgb_output_seen": conclusion.get("rgb_output_seen"),
        "semantic_first_stats": conclusion.get("semantic_first_stats"),
        "rgb_first_stats": conclusion.get("rgb_first_stats"),
        "wall_time_s": conclusion.get("wall_time_s"),
        "memory_before_mb": conclusion.get("memory_before_mb"),
        "memory_after_mb": conclusion.get("memory_after_mb"),
        "memory_delta_mb": conclusion.get("memory_delta_mb"),
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
