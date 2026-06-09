"""Audit for Phase 5C-2 dual-USV static HoloOcean multistep smoke."""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List

import numpy as np


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c2_res10_dual_usv_static_holoocean_multistep_smoke"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
PHASE_PREFIX = "baseline_GP/results/holoocean_bridge_v1/{0}/".format(PHASE_NAME)

SMOKE_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "dual_usv_static_holoocean_multistep_smoke.py"))
AUDIT_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "dual_usv_static_holoocean_multistep_audit.py"))
CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_config.json"))
POLICY_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_policy_trace.json"))
POLICY_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_policy_trace.csv"))
TICK_TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_tick_trace.json"))
TICK_TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_tick_trace.csv"))
FOUND_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_found_events.json"))
SENSOR_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_sensor_sources.json"))
COLLISION_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_collision_metrics.json"))
SUMMARY_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_summary.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_git_status.json"))
SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "dual_usv_static_holoocean_multistep_summary.md"))
AUDIT_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_holoocean_multistep_audit.json"))
AUDIT_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "dual_usv_static_holoocean_multistep_audit_summary.md"))
PATHS_PNG = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "dual_usv_static_holoocean_multistep_paths.png"))


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


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _as_bool(value: Any) -> bool:
    return bool(value)


def _found_counts_monotonic(policy_trace: List[Dict[str, Any]]) -> bool:
    last_value = 0
    for row in policy_trace:
        value = int(row.get("found_count_after", last_value))
        if value < last_value:
            return False
        last_value = value
    return True


def _gp_counts_nondecreasing(policy_trace: List[Dict[str, Any]]) -> bool:
    last_value = None
    for row in policy_trace:
        value = row.get("gp_n_obs")
        if value is None:
            continue
        value_int = int(value)
        if last_value is not None and value_int < last_value:
            return False
        last_value = value_int
    return True


def _all_policy_steps_ok(policy_trace: List[Dict[str, Any]], max_policy_steps: int, terminated_reason: str) -> Dict[str, bool]:
    checks: Dict[str, bool] = {}
    if terminated_reason == "all_found":
        checks["completed_steps_valid"] = 1 <= len(policy_trace) <= max_policy_steps
    else:
        checks["completed_steps_valid"] = len(policy_trace) == max_policy_steps

    steps = [int(row.get("step", -1)) for row in policy_trace]
    checks["policy_steps_sequential"] = steps == list(range(1, len(policy_trace) + 1))
    checks["all_steps_have_two_assignments"] = all(int(row.get("assignment_count", 0)) == 2 for row in policy_trace)
    checks["all_steps_physical_success"] = all(bool(row.get("physical_step_success", False)) for row in policy_trace)
    checks["all_steps_physical_called"] = all(bool(row.get("physical_execution_called", False)) for row in policy_trace)
    checks["all_steps_local_update"] = all(int(row.get("local_update_called_count", 0)) == 2 for row in policy_trace)
    checks["all_steps_detect_targets"] = all(bool(row.get("detect_targets_called", False)) for row in policy_trace)
    checks["all_steps_update_found_mask"] = all(bool(row.get("update_found_mask_called", False)) for row in policy_trace)
    checks["all_steps_team_miss_update"] = all(bool(row.get("team_miss_update_called", False)) for row in policy_trace)
    checks["all_steps_gp_update"] = all(bool(row.get("team_gp_update_called", False)) for row in policy_trace)
    checks["all_steps_search_info_update"] = all(bool(row.get("team_search_info_update_called", False)) for row in policy_trace)
    checks["all_steps_team_trace_written"] = all(bool(row.get("team_trace_row_written", False)) for row in policy_trace)
    checks["all_steps_local_trace_written"] = all(int(row.get("local_trace_rows_written", 0)) == 2 for row in policy_trace)
    checks["all_static_targets_unchanged"] = all(bool(row.get("target_positions_static_after_step_targets", False)) for row in policy_trace)
    checks["all_search_info_shape_ok"] = all(bool(row.get("search_info_shape_ok", False)) for row in policy_trace)
    checks["all_search_info_no_nan"] = all(not bool(row.get("search_info_has_nan", True)) for row in policy_trace)
    checks["all_search_info_valid"] = all(bool(row.get("search_info_valid", False)) for row in policy_trace)
    checks["all_gp_counts_consistent"] = all(bool(row.get("gp_count_consistent", False)) for row in policy_trace)
    checks["all_remaining_mass_valid"] = all(
        _is_finite_number(row.get("remaining_intensity_mass_after")) and float(row.get("remaining_intensity_mass_after")) >= -1e-9
        for row in policy_trace
    )
    checks["all_peak_ratio_valid"] = all(_is_finite_number(row.get("peak_intensity_ratio_after")) for row in policy_trace)
    checks["found_count_monotonic"] = _found_counts_monotonic(policy_trace)
    checks["gp_counts_nondecreasing"] = _gp_counts_nondecreasing(policy_trace)

    projection_ok = True
    tick_count_ok = True
    hit_branch_ok = True
    for row in policy_trace:
        physical = row.get("physical_result", {})
        ticks = int(physical.get("step_ticks", 0))
        if ticks < 1 or ticks > 500:
            tick_count_ok = False
        final_by_usv = physical.get("final_by_usv", {})
        wait_map = row.get("wait_applied_map", {})
        for usv_key in ("0", "1"):
            final_info = final_by_usv.get(usv_key, {})
            if not bool(final_info.get("projection_matches_target", False)):
                projection_ok = False
            if not bool(wait_map.get(usv_key, False)) and not bool(final_info.get("arrived", False)):
                projection_ok = False
        if int(row.get("team_detected_count", 0)) > 0 and not bool(row.get("hit_update_called", False)):
            hit_branch_ok = False
    checks["all_step_tick_counts_in_bounds"] = tick_count_ok
    checks["all_final_projections_match_targets"] = projection_ok
    checks["hit_update_called_when_new_found"] = hit_branch_ok
    return checks


def _tick_trace_checks(tick_trace: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, bool]:
    checks: Dict[str, bool] = {}
    checks["tick_trace_nonempty"] = len(tick_trace) > 0
    checks["tick_trace_count_matches_summary"] = len(tick_trace) == int(summary.get("total_physical_ticks", -1))
    allowed_sensors = {"LocationSensor", "GPSSensor", "last_known"}
    checks["tick_trace_sensor_keys_valid"] = all(
        row.get("sv0_selected_sensor") in allowed_sensors and row.get("sv1_selected_sensor") in allowed_sensors
        for row in tick_trace
    )
    checks["tick_trace_has_policy_step"] = all(int(row.get("policy_step", 0)) >= 1 for row in tick_trace)
    checks["tick_trace_has_projection"] = all(
        "sv0_proj_row" in row and "sv0_proj_col" in row and "sv1_proj_row" in row and "sv1_proj_col" in row
        for row in tick_trace
    )
    return checks


def _build_report(checks: Dict[str, bool], metrics: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5C-2 HoloOcean Multistep Smoke Audit Summary",
        "",
        "## Status",
        "- Overall: `{0}`".format("PASSED" if all(checks.values()) else "FAILED"),
        "- Checks: `{0}`".format(len(checks)),
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
        "smoke_script_exists": SMOKE_SCRIPT,
        "audit_script_exists": AUDIT_SCRIPT,
        "config_json_exists": CONFIG_JSON,
        "policy_trace_json_exists": POLICY_TRACE_JSON,
        "policy_trace_csv_exists": POLICY_TRACE_CSV,
        "tick_trace_json_exists": TICK_TRACE_JSON,
        "tick_trace_csv_exists": TICK_TRACE_CSV,
        "found_json_exists": FOUND_JSON,
        "sensor_json_exists": SENSOR_JSON,
        "collision_json_exists": COLLISION_JSON,
        "summary_json_exists": SUMMARY_JSON,
        "git_status_json_exists": GIT_STATUS_JSON,
        "summary_md_exists": SUMMARY_MD,
        "paths_png_exists": PATHS_PNG,
    }.items():
        checks[key] = os.path.exists(path)

    config = _safe_load(CONFIG_JSON, checks, "config_json_parse_ok")
    policy_trace = _safe_load(POLICY_TRACE_JSON, checks, "policy_trace_json_parse_ok")
    tick_trace = _safe_load(TICK_TRACE_JSON, checks, "tick_trace_json_parse_ok")
    found = _safe_load(FOUND_JSON, checks, "found_json_parse_ok")
    sensor = _safe_load(SENSOR_JSON, checks, "sensor_json_parse_ok")
    collision = _safe_load(COLLISION_JSON, checks, "collision_json_parse_ok")
    summary = _safe_load(SUMMARY_JSON, checks, "summary_json_parse_ok")
    git_status = _safe_load(GIT_STATUS_JSON, checks, "git_status_json_parse_ok")

    if config is None:
        config = {}
    if not isinstance(policy_trace, list):
        policy_trace = []
    if not isinstance(tick_trace, list):
        tick_trace = []
    if found is None:
        found = {}
    if sensor is None:
        sensor = {}
    if collision is None:
        collision = {}
    if summary is None:
        summary = {}
    if git_status is None:
        git_status = {}

    checks["policy_name_correct"] = config.get("policy_name") == "marine_knownmap_path_v2_infosampled_2usv"
    checks["assignment_mode_coordinated"] = config.get("assignment_mode") == "coordinated"
    checks["target_motion_static"] = config.get("target_motion_mode") == "static"
    checks["map_is_81x81_res10"] = (
        int(config.get("map_height_cells", -1)) == 81
        and int(config.get("map_width_cells", -1)) == 81
        and float(config.get("resolution_m", -1.0)) == 10.0
    )
    checks["clue_sigma_m_is_30"] = float(config.get("clue_sigma_m", -1.0)) == 30.0
    checks["episode_seed_is_0"] = int(config.get("episode_seed", -1)) == 0
    checks["max_policy_steps_is_4"] = int(config.get("max_policy_steps", -1)) == 4
    checks["initial_usvs_match_phase5b"] = config.get("initial_robot_positions") == [[25, 2], [35, 2]]
    checks["exactly_two_usvs"] = config.get("scenario_agent_names") == ["sv0", "sv1"]
    checks["only_allowed_sensors_configured"] = set(config.get("scenario_sensor_types", [])) == {"GPSSensor", "LocationSensor", "OrientationSensor"}

    with open(SMOKE_SCRIPT, "r", encoding="utf-8") as f:
        source = f.read()
    lower_source = source.lower()
    checks["source_imports_holoocean"] = "import holoocean" in lower_source
    checks["source_uses_env_act"] = "env.act(" in source
    checks["source_uses_env_tick"] = "env.tick(" in source
    checks["source_no_env_step"] = "env.step(" not in source
    checks["source_no_sonar_or_camera"] = "sonar" not in lower_source and "camera" not in lower_source
    checks["source_no_runtime_execute_next_step"] = "execute_next_step" not in source
    for token in [
        "step_targets",
        "predict_intensity",
        "_joint_assign_two_usv_segments",
        "_apply_joint_assignment_to_locals",
        "_resolve_execution_conflict",
        "_update_local_after_execution",
        "refresh_last_seen",
        "build_staleness_map",
        "apply_known_occupancy_constraints",
        "detect_targets",
        "update_found_mask",
        "_apply_team_miss_updates",
        "hit_update_intensity",
        "_sample_and_update_team_gp",
        "_update_team_search_info_state",
        "world_to_grid",
        "grid_to_world",
        "ExecutionStepResult",
    ]:
        checks["source_contains_{0}".format(token)] = token in source

    max_policy_steps = int(config.get("max_policy_steps", 4))
    terminated_reason = str(found.get("terminated_reason", summary.get("terminated_reason", "")))
    checks.update(_all_policy_steps_ok(policy_trace, max_policy_steps, terminated_reason))
    checks.update(_tick_trace_checks(tick_trace, summary))

    checks["found_json_matches_summary_steps"] = int(found.get("completed_policy_steps", -1)) == int(summary.get("completed_policy_steps", -2))
    checks["found_json_matches_summary_found"] = int(found.get("found_count_final", -1)) == int(summary.get("found_count_final", -2))
    checks["found_final_nonnegative"] = int(found.get("found_count_final", -1)) >= 0
    checks["hit_branch_optional_but_consistent"] = (
        bool(found.get("hit_branch_covered", False))
        or all(int(row.get("team_detected_count", 0)) == 0 for row in policy_trace)
    )
    checks["runtime_team_trace_count_matches"] = int(found.get("runtime_team_trace_rows_count", -1)) == len(policy_trace)
    checks["runtime_local_trace_count_matches"] = int(found.get("runtime_local_trace_rows_count", -1)) == len(policy_trace) * 2
    checks["gp_final_ge_initial"] = int(found.get("gp_n_obs_final", 0)) >= int(found.get("gp_n_obs_initial", 0))
    checks["gp_final_counts_consistent"] = bool(found.get("gp_count_consistent_final", False))

    checks["fallback_count_total_zero"] = int(sensor.get("fallback_count_total", -1)) == 0
    checks["sensor_total_ticks_matches_summary"] = int(sensor.get("total_physical_ticks", -1)) == int(summary.get("total_physical_ticks", -2))
    checks["collision_min_sep_ge_warning"] = float(collision.get("min_inter_vessel_distance_m", -1.0)) >= 30.0
    checks["collision_fail_ticks_zero"] = int(collision.get("collision_fail_ticks", -1)) == 0
    checks["summary_no_physical_failure"] = not bool(summary.get("physical_failure", True))

    checks["git_changes_limited_to_phase_dir"] = not bool(git_status.get("outside_phase_new_or_changed", []))

    metrics = {
        "completed_policy_steps": int(summary.get("completed_policy_steps", 0)),
        "max_policy_steps": int(config.get("max_policy_steps", 0)),
        "terminated_reason": summary.get("terminated_reason"),
        "total_physical_ticks": int(summary.get("total_physical_ticks", 0)),
        "found_count_final": int(summary.get("found_count_final", 0)),
        "hit_branch_covered": bool(summary.get("hit_branch_covered", False)),
        "gp_n_obs_initial": found.get("gp_n_obs_initial"),
        "gp_n_obs_final": found.get("gp_n_obs_final"),
        "fallback_count_total": sensor.get("fallback_count_total"),
        "min_inter_vessel_distance_m": collision.get("min_inter_vessel_distance_m"),
        "collision_warning_ticks": collision.get("collision_warning_ticks"),
        "collision_fail_ticks": collision.get("collision_fail_ticks"),
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
