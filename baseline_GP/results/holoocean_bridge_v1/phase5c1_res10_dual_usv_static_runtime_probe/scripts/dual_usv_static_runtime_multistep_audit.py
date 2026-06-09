"""Phase 5C-1 runtime-only multistep probe audit."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from typing import Any, Dict, List

import numpy as np

sys.path.append(os.path.abspath("."))


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5c1_res10_dual_usv_static_runtime_probe"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
PHASE_PREFIX = "baseline_GP/results/holoocean_bridge_v1/{0}/".format(PHASE_NAME)

PROBE_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "dual_usv_static_runtime_multistep_probe.py"))
AUDIT_SCRIPT = os.path.normpath(os.path.join(PHASE_DIR, "scripts", "dual_usv_static_runtime_multistep_audit.py"))
CONFIG_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_config.json"))
TRACE_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_trace.json"))
TRACE_CSV = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_trace.csv"))
FOUND_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_found_events.json"))
GIT_STATUS_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_git_status.json"))
AUDIT_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_static_runtime_multistep_audit.json"))
AUDIT_SUMMARY_MD = os.path.normpath(os.path.join(PHASE_DIR, "reports", "dual_usv_static_runtime_multistep_audit_summary.md"))


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    return obj


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(data), f, indent=2)
    print("JSON saved to: {0}".format(path))


def _run_git_status() -> List[str]:
    repo_root = os.path.abspath(".")
    result = subprocess.run(
        ["git", "-c", "safe.directory={0}".format(repo_root.replace("\\", "/")), "status", "--porcelain"],
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if result.stderr.strip():
        lines.append("STDERR: {0}".format(result.stderr.strip()))
    return lines


def _status_path(line: str) -> str:
    if line.startswith("STDERR:"):
        return line
    path = line[3:] if len(line) > 3 else line
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.replace("\\", "/")


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _all_rows(rows: List[Dict[str, Any]], key: str, expected: Any = True) -> bool:
    if not rows:
        return False
    return all(row.get(key) == expected for row in rows)


def _write_summary(results: Dict[str, Any]) -> None:
    lines = [
        "# Phase 5C-1 Runtime-Only Multistep Audit Summary",
        "",
        "## Status",
        "- Overall: `{0}`".format("PASSED" if results["all_passed"] else "FAILED"),
        "- Checks: `{0}`".format(len(results["checks"])),
        "",
        "## Checks",
        "| Check | Result |",
        "| :--- | :---: |",
    ]
    for key, value in results["checks"].items():
        lines.append("| `{0}` | `{1}` |".format(key, bool(value)))
    lines.extend([
        "",
        "## Metrics",
        "```json",
        json.dumps(_json_safe(results["metrics"]), indent=2),
        "```",
    ])
    os.makedirs(os.path.dirname(AUDIT_SUMMARY_MD), exist_ok=True)
    with open(AUDIT_SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Audit summary saved to: {0}".format(AUDIT_SUMMARY_MD))


def run_audit() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    metrics: Dict[str, Any] = {}

    checks["probe_script_exists"] = os.path.exists(PROBE_SCRIPT)
    checks["audit_script_exists"] = os.path.exists(AUDIT_SCRIPT)
    checks["config_json_exists"] = os.path.exists(CONFIG_JSON)
    checks["trace_json_exists"] = os.path.exists(TRACE_JSON)
    checks["trace_csv_exists"] = os.path.exists(TRACE_CSV)
    checks["found_json_exists"] = os.path.exists(FOUND_JSON)
    checks["git_status_json_exists"] = os.path.exists(GIT_STATUS_JSON)

    config: Dict[str, Any] = {}
    trace_rows: List[Dict[str, Any]] = []
    found_events: Dict[str, Any] = {}
    git_status: Dict[str, Any] = {}

    try:
        config = _load_json(CONFIG_JSON)
        checks["config_json_parse_ok"] = True
    except Exception:
        checks["config_json_parse_ok"] = False

    try:
        trace_rows = _load_json(TRACE_JSON)
        checks["trace_json_parse_ok"] = isinstance(trace_rows, list)
    except Exception:
        checks["trace_json_parse_ok"] = False

    try:
        found_events = _load_json(FOUND_JSON)
        checks["found_json_parse_ok"] = True
    except Exception:
        checks["found_json_parse_ok"] = False

    try:
        git_status = _load_json(GIT_STATUS_JSON)
        checks["git_status_json_parse_ok"] = True
    except Exception:
        checks["git_status_json_parse_ok"] = False

    probe_src = ""
    if checks["probe_script_exists"]:
        with open(PROBE_SCRIPT, "r", encoding="utf-8") as f:
            probe_src = f.read()

    checks["policy_name_correct"] = config.get("policy_name") == "marine_knownmap_path_v2_infosampled_2usv"
    checks["assignment_mode_coordinated"] = config.get("assignment_mode") == "coordinated"
    checks["target_motion_static"] = config.get("target_motion_mode") == "static"
    checks["map_is_81x81_res10"] = (
        config.get("map_height_cells") == 81
        and config.get("map_width_cells") == 81
        and float(config.get("resolution_m", 0.0)) == 10.0
    )
    checks["clue_sigma_m_is_30"] = float(config.get("clue_sigma_m", -1.0)) == 30.0
    checks["episode_seed_is_0"] = int(config.get("episode_seed", -1)) == 0
    checks["max_steps_is_240"] = int(config.get("max_steps", -1)) == 240
    checks["initial_usvs_match_phase5b"] = config.get("initial_robot_positions") == [[25, 2], [35, 2]]

    lower_src = probe_src.lower()
    checks["no_import_holoocean"] = "import holoocean" not in lower_src
    checks["no_env_act"] = "env.act(" not in probe_src
    checks["no_env_tick"] = "env.tick(" not in probe_src
    checks["no_env_step"] = "env.step(" not in probe_src
    checks["no_sonar_or_camera"] = not any(
        token in probe_src
        for token in ["ImagingSonar", "SidescanSonar", "ProfilingSonar", "SinglebeamSonar", "SonarSensor", "CameraSensor"]
    )
    checks["no_target_agent"] = '"target"' not in probe_src and "'target'" not in probe_src

    required_source_tokens = [
        "step_targets(",
        "predict_intensity(",
        "_joint_assign_two_usv_segments(",
        "_apply_joint_assignment_to_locals(",
        "_resolve_execution_conflict(",
        "execute_next_step(",
        "_update_local_after_execution(",
        "refresh_last_seen(",
        "build_staleness_map(",
        "apply_known_occupancy_constraints(",
        "detect_targets(",
        "update_found_mask(",
        "_apply_team_miss_updates(",
        "hit_update_intensity(",
        "_sample_and_update_team_gp(",
        "_update_team_search_info_state(",
        "gp_field",
        "n_obs",
    ]
    for token in required_source_tokens:
        checks["source_contains_{0}".format(token.replace("(", "").replace("[", "").replace("]", "").replace('"', "").replace(" ", "_"))] = token in probe_src

    initial_all_found = bool(found_events.get("initial_all_found", False))
    completed_steps = int(found_events.get("completed_steps", 0))
    found_count_final = int(found_events.get("found_count_final", 0))
    hit_branch_covered = bool(found_events.get("hit_branch_covered", False))
    metrics["initial_all_found"] = initial_all_found
    metrics["completed_steps"] = completed_steps
    metrics["trace_rows_count"] = len(trace_rows)
    metrics["found_count_final"] = found_count_final
    metrics["terminated_reason"] = found_events.get("terminated_reason")
    metrics["gp_n_obs_initial"] = found_events.get("gp_n_obs_initial")
    metrics["gp_n_obs_final"] = found_events.get("gp_n_obs_final")

    checks["initial_branch_valid"] = bool(initial_all_found or completed_steps >= 2)
    checks["trace_count_matches_completed_steps"] = len(trace_rows) == (0 if initial_all_found else completed_steps)
    checks["trace_steps_sequential"] = (
        initial_all_found
        or [int(row.get("step", -1)) for row in trace_rows] == list(range(1, completed_steps + 1))
    )

    if trace_rows:
        checks["all_steps_called_step_targets"] = _all_rows(trace_rows, "step_targets_called")
        checks["all_static_targets_unchanged"] = _all_rows(trace_rows, "target_positions_static_after_step_targets")
        checks["all_steps_called_predict_intensity"] = _all_rows(trace_rows, "predict_intensity_called")
        checks["all_steps_have_two_assignments"] = all(int(row.get("assignment_count", 0)) == 2 for row in trace_rows)
        checks["all_steps_apply_assignment"] = _all_rows(trace_rows, "apply_assignment_called")
        checks["all_steps_resolve_conflict"] = _all_rows(trace_rows, "resolve_conflict_called")
        checks["all_steps_update_two_locals"] = all(int(row.get("local_update_called_count", 0)) == 2 for row in trace_rows)
        checks["all_steps_refresh_last_seen"] = _all_rows(trace_rows, "last_seen_refreshed")
        checks["all_steps_rebuild_staleness"] = _all_rows(trace_rows, "staleness_rebuilt")
        checks["all_steps_apply_known_occupancy"] = _all_rows(trace_rows, "apply_known_occupancy_constraints_called")
        checks["all_steps_detect_targets"] = _all_rows(trace_rows, "detect_targets_called")
        checks["all_steps_update_found_mask"] = _all_rows(trace_rows, "update_found_mask_called")
        checks["all_steps_team_miss_update"] = _all_rows(trace_rows, "team_miss_update_called")
        checks["all_steps_gp_update"] = _all_rows(trace_rows, "team_gp_update_called")
        checks["all_steps_search_info_update"] = _all_rows(trace_rows, "team_search_info_update_called")
        checks["all_steps_team_trace_written"] = _all_rows(trace_rows, "team_trace_row_written")
        checks["all_steps_local_trace_written"] = all(int(row.get("local_trace_rows_written", 0)) == 2 for row in trace_rows)
        checks["all_remaining_mass_valid"] = all(
            _is_finite_number(row.get("remaining_intensity_mass_after"))
            and float(row.get("remaining_intensity_mass_after")) >= 0.0
            for row in trace_rows
        )
        checks["all_peak_ratio_valid"] = all(_is_finite_number(row.get("peak_intensity_ratio_after")) for row in trace_rows)
        checks["all_search_info_valid"] = all(bool(row.get("search_info_valid", False)) for row in trace_rows)
        checks["all_search_info_shape_ok"] = all(bool(row.get("search_info_shape_ok", False)) for row in trace_rows)
        checks["all_search_info_no_nan"] = all(not bool(row.get("search_info_has_nan", True)) for row in trace_rows)
        checks["all_gp_counts_consistent"] = all(bool(row.get("gp_count_consistent", False)) for row in trace_rows)
        checks["gp_n_obs_grew"] = (
            found_events.get("gp_n_obs_initial") is not None
            and found_events.get("gp_n_obs_final") is not None
            and int(found_events["gp_n_obs_final"]) > int(found_events["gp_n_obs_initial"])
        )
        counts = [int(found_events.get("initial_found_count", 0))] + [int(row.get("found_count_after", 0)) for row in trace_rows]
        checks["found_count_monotonic"] = all(a <= b for a, b in zip(counts, counts[1:]))
    else:
        for key in [
            "all_steps_called_step_targets",
            "all_static_targets_unchanged",
            "all_steps_called_predict_intensity",
            "all_steps_have_two_assignments",
            "all_steps_apply_assignment",
            "all_steps_resolve_conflict",
            "all_steps_update_two_locals",
            "all_steps_refresh_last_seen",
            "all_steps_rebuild_staleness",
            "all_steps_apply_known_occupancy",
            "all_steps_detect_targets",
            "all_steps_update_found_mask",
            "all_steps_team_miss_update",
            "all_steps_gp_update",
            "all_steps_search_info_update",
            "all_steps_team_trace_written",
            "all_steps_local_trace_written",
            "all_remaining_mass_valid",
            "all_peak_ratio_valid",
            "all_search_info_valid",
            "all_search_info_shape_ok",
            "all_search_info_no_nan",
            "all_gp_counts_consistent",
            "gp_n_obs_grew",
            "found_count_monotonic",
        ]:
            checks[key] = bool(initial_all_found)

    checks["found_count_final_gt_0"] = found_count_final > 0
    checks["hit_branch_or_initial_found_covered"] = bool(hit_branch_covered or int(found_events.get("initial_found_count", 0)) > 0)
    checks["runtime_team_trace_count_matches"] = int(found_events.get("runtime_team_trace_rows_count", -1)) == (0 if initial_all_found else completed_steps)
    checks["runtime_local_trace_count_matches"] = int(found_events.get("runtime_local_trace_rows_count", -1)) == (0 if initial_all_found else completed_steps * 2)

    pre_status = list(git_status.get("pre_git_status", []))
    current_status = _run_git_status()
    pre_set = set(pre_status)
    outside_new_or_changed = []
    for line in current_status:
        path = _status_path(line)
        if path.startswith(PHASE_PREFIX):
            continue
        if line in pre_set:
            continue
        outside_new_or_changed.append(line)
    metrics["pre_git_status"] = pre_status
    metrics["current_git_status"] = current_status
    metrics["outside_phase_new_or_changed"] = outside_new_or_changed
    checks["git_changes_limited_to_phase_dir"] = len(outside_new_or_changed) == 0

    all_passed = all(bool(value) for value in checks.values())
    results = {
        "all_passed": bool(all_passed),
        "checks": checks,
        "metrics": metrics,
    }
    _save_json(AUDIT_JSON, results)
    _write_summary(results)
    return results


def main() -> None:
    print("=== Phase 5C-1: runtime-only multistep audit ===")
    results = run_audit()
    print("All passed: {0}".format(results["all_passed"]))
    print("Checks: {0}".format(len(results["checks"])))


if __name__ == "__main__":
    main()
