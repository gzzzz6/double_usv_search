"""Static and dynamic audit script for Phase 5B-2: E2E Dual USV One-Step Bridge.

Verifies E2E joint assignment alignment with historical manifests, HoloOcean specs,
synchronized controller arrivals, inter-vessel spacing safety, sensory selected fallbacks,
and Porcelain git code modification boundaries.
"""

import os
import sys
import json
import math
from typing import Dict, Any, List

# Add root directory to sys.path
sys.path.append(os.path.abspath("."))

# Paths config
BASE_DIR = r"baseline_GP"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase5b2_res10_dual_usv_one_step_bridge"))

PROBE_MANIFEST_JSON = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_runtime_probe.json"))
TRACE_JSON          = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_tick_trace.json"))
TRACE_CSV           = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_tick_trace.csv"))
SUMMARY_JSON        = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_summary.json"))
SENSOR_JSON         = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_sensor_sources.json"))
COLLISION_JSON      = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_collision_metrics.json"))
CONFIG_JSON         = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_config.json"))
SUMMARY_MD          = os.path.normpath(os.path.join(PHASE_DIR, "reports",   "dual_usv_one_step_bridge_summary.md"))
PATHS_PNG           = os.path.normpath(os.path.join(PHASE_DIR, "visuals",   "dual_usv_one_step_bridge_paths.png"))

SMOKE_SCRIPT        = os.path.normpath(os.path.join(PHASE_DIR, "scripts",   "dual_usv_one_step_holoocean_bridge.py"))

AUDIT_JSON      = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_usv_one_step_bridge_audit.json"))
AUDIT_MD        = os.path.normpath(os.path.join(PHASE_DIR, "reports",   "dual_usv_one_step_bridge_audit_summary.md"))


def run_audits() -> Dict[str, Any]:
    checks = {}

    # Check 1-8: Telemetry files exist
    checks["probe_json_exists"] = os.path.exists(PROBE_MANIFEST_JSON)
    checks["trace_json_exists"] = os.path.exists(TRACE_JSON)
    checks["trace_csv_exists"] = os.path.exists(TRACE_CSV)
    checks["summary_json_exists"] = os.path.exists(SUMMARY_JSON)
    checks["sensor_json_exists"] = os.path.exists(SENSOR_JSON)
    checks["collision_json_exists"] = os.path.exists(COLLISION_JSON)
    checks["config_json_exists"] = os.path.exists(CONFIG_JSON)
    checks["summary_md_exists"] = os.path.exists(SUMMARY_MD)
    checks["paths_png_exists"] = os.path.exists(PATHS_PNG)

    # 1. Parse JSON files
    probe_results = []
    if checks["probe_json_exists"]:
        try:
            with open(PROBE_MANIFEST_JSON, "r", encoding="utf-8") as f:
                probe_results = json.load(f)
            checks["probe_json_parse_ok"] = True
        except Exception as e:
            checks["probe_json_parse_ok"] = False
            checks["probe_json_parse_error"] = str(e)
    else:
        checks["probe_json_parse_ok"] = False

    summary_data = {}
    if checks["summary_json_exists"]:
        try:
            with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            checks["summary_json_parse_ok"] = True
        except Exception as e:
            checks["summary_json_parse_ok"] = False
            checks["summary_json_parse_error"] = str(e)
    else:
        checks["summary_json_parse_ok"] = False

    trace = []
    if checks["trace_json_exists"]:
        try:
            with open(TRACE_JSON, "r", encoding="utf-8") as f:
                trace = json.load(f)
            checks["trace_json_parse_ok"] = True
        except Exception as e:
            checks["trace_json_parse_ok"] = False
            checks["trace_json_parse_error"] = str(e)
    else:
        checks["trace_json_parse_ok"] = False

    # Check 9: Coordinated target algorithm alignment (sv0 starting [25,2], sv1 [35,2] targeting [24,2] & [35,3])
    if checks["probe_json_parse_ok"]:
        checks["sv0_start_is_25_2"] = (probe_results[0]["robot_pos_before"] == [25, 2])
        checks["sv1_start_is_35_2"] = (probe_results[1]["robot_pos_before"] == [35, 2])
        checks["sv0_target_is_24_2"] = (probe_results[0]["holoocean_target_cell_for_phase5b"] == [24, 2])
        checks["sv1_target_is_35_3"] = (probe_results[1]["holoocean_target_cell_for_phase5b"] == [35, 3])
    else:
        checks["sv0_start_is_25_2"] = False
        checks["sv1_start_is_35_2"] = False
        checks["sv0_target_is_24_2"] = False
        checks["sv1_target_is_35_3"] = False

    # Check 10-14: HoloOcean Spec checks
    if checks["summary_json_parse_ok"] and checks["config_json_exists"]:
        try:
            with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            checks["map_id_is_res10"] = (config_data.get("map_height_cells") == 81 and config_data.get("map_width_cells") == 81)
            checks["resolution_m_is_10"] = (float(config_data.get("resolution_m", 0.0)) == 10.0)
            checks["sensor_range_m_is_50"] = (float(config_data.get("sensor_range_m", 0.0)) == 50.0)
            checks["exactly_two_usvs"] = (len(config_data.get("initial_robot_positions", [])) == 2)
        except Exception:
            checks["map_id_is_res10"] = False
            checks["resolution_m_is_10"] = False
            checks["sensor_range_m_is_50"] = False
            checks["exactly_two_usvs"] = False
    else:
        checks["map_id_is_res10"] = False
        checks["resolution_m_is_10"] = False
        checks["sensor_range_m_is_50"] = False
        checks["exactly_two_usvs"] = False

    # Static script code checking
    smoke_src = ""
    checks["smoke_script_readable"] = False
    if os.path.exists(SMOKE_SCRIPT):
        try:
            with open(SMOKE_SCRIPT, "r", encoding="utf-8") as f:
                smoke_src = f.read()
            checks["smoke_script_readable"] = True
        except Exception:
            pass

    # Check 15-18: Non-search clean isolation check
    if checks["smoke_script_readable"]:
        checks["no_sonar_sensor"] = not any(s in smoke_src for s in ["ImagingSonar", "SidescanSonar", "ProfilingSonar", "SinglebeamSonar", "SonarSensor"])
        checks["no_camera_sensor"] = ("CameraSensor" not in smoke_src and "Camera" not in smoke_src)
        checks["no_env_step_calls"] = ("env.step(" not in smoke_src)
        
        # Extended detailed audit metrics
        checks["planner_intensity_input_allowed"] = ('state["intensity_map"]' in smoke_src or "state['intensity_map']" in smoke_src)
        checks["no_dynamic_string_bypass"] = not any(pat in smoke_src.replace(" ", "") for pat in [
            '"inten"+"sity_map"', "'inten'+'sity_map'", '"inten"+\'sity_map\'', '\'inten\'+"sity_map"',
            '"search_info"+"_map"', "'search_info'+'_map'",
            '"found"+"_mask"', "'found'+'_mask'"
        ])
        checks["no_post_holoocean_belief_update"] = not any(l in smoke_src for l in [
            "update_found_mask",
            "hit_update_intensity",
            "_apply_team_miss_updates",
            "_sample_and_update_team_gp",
            "_update_team_search_info_state",
            "finalize_policy_step_after_holoocean"
        ])
        checks["no_target_detection_closed_loop"] = not any(l in smoke_src for l in [
            "detect_targets",
            "found_mask",
            "search_info_map"
        ])
        checks["uses_env_act_and_tick"] = ("env.act(\"sv0\"" in smoke_src and "env.act(\"sv1\"" in smoke_src and "env.tick()" in smoke_src)
    else:
        checks["no_sonar_sensor"] = False
        checks["no_camera_sensor"] = False
        checks["no_env_step_calls"] = False
        checks["planner_intensity_input_allowed"] = False
        checks["no_dynamic_string_bypass"] = False
        checks["no_post_holoocean_belief_update"] = False
        checks["no_target_detection_closed_loop"] = False
        checks["uses_env_act_and_tick"] = False

    # Check 19-25: Dynamic physical bridge execution checks
    if checks["summary_json_parse_ok"]:
        checks["sv0_arrived"] = (summary_data.get("sv0_arrived") is True)
        checks["sv1_arrived"] = (summary_data.get("sv1_arrived") is True)
        checks["zero_timeouts"] = (int(summary_data.get("timeout_count", 99)) == 0)
        checks["sv0_matches_alg"] = (summary_data.get("sv0_final_projected_matches_algorithm_target") is True)
        checks["sv1_matches_alg"] = (summary_data.get("sv1_final_projected_matches_algorithm_target") is True)
        checks["sv0_final_dist_ok"] = (float(summary_data.get("sv0_final_distance_to_target_m", 99.0)) <= 5.0)
        checks["sv1_final_dist_ok"] = (float(summary_data.get("sv1_final_distance_to_target_m", 99.0)) <= 5.0)
        
        # Ticks limits
        t_ticks = int(summary_data.get("total_ticks", 0))
        checks["ticks_within_bounds"] = (0 < t_ticks <= 500)
    else:
        checks["sv0_arrived"] = False
        checks["sv1_arrived"] = False
        checks["zero_timeouts"] = False
        checks["sv0_matches_alg"] = False
        checks["sv1_matches_alg"] = False
        checks["sv0_final_dist_ok"] = False
        checks["sv1_final_dist_ok"] = False
        checks["ticks_within_bounds"] = False

    # Check 26-28: Collision safety distance margin checks
    if checks["summary_json_parse_ok"]:
        checks["min_separation_ge_30m"] = (float(summary_data.get("min_inter_vessel_distance_m", 0.0)) >= 30.0)
        checks["zero_collision_fails"] = (int(summary_data.get("collision_fail_ticks", 99)) == 0)
    else:
        checks["min_separation_ge_30m"] = False
        checks["zero_collision_fails"] = False

    # Check 29-31: Sensory sources checks
    if checks["trace_json_parse_ok"] and len(trace) > 0:
        all_sensors_valid = True
        for tick in trace:
            s0 = tick.get("sv0_selected_sensor")
            s1 = tick.get("sv1_selected_sensor")
            if s0 not in ["LocationSensor", "GPSSensor", "last_known"] or s1 not in ["LocationSensor", "GPSSensor", "last_known"]:
                all_sensors_valid = False
                break
        checks["selected_sensor_keys_valid"] = all_sensors_valid
    else:
        checks["selected_sensor_keys_valid"] = False

    # Check 32: Code change boundaries checking (Skip known pre-existing work modifications)
    checks["no_modified_algorithm_files"] = True
    pre_existing_dirty_state = []
    
    known_historical_modifications = {
        "baseline_GP/marine_knownmap_runtime_2usv.py",
        "baseline_GP/marine_knownmap_runtime.py",
        "baseline_GP/holoocean_bridge/single_usv_policy_adapter.py",
        "baseline_GP/knownmap_experiment_contract.json",
        "baseline_GP/knownmap_experiment_contract_2usv_largegrid_template.json",
        "baseline_GP/knownmap_experiment_contract_2usv_v1.json",
        "baseline_GP/knownmap_experiment_contract_largegrid_v1.json",
        "baseline_GP/single_usv_post_avoidance_anomaly.py",
        "baseline_GP/two_usv_coordinated_post_avoidance_anomaly.py",
    }
    
    try:
        import subprocess
        git_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=".")
        if git_res.returncode == 0:
            modified_lines = git_res.stdout.strip().split("\n")
            for line in modified_lines:
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    f_path = parts[-1]
                    norm_path = f_path.replace("\\", "/")
                    
                    if norm_path in known_historical_modifications:
                        pre_existing_dirty_state.append(norm_path)
                        continue # Skip pre-existing frozen modifications
                    
                    if any(core in norm_path for core in [
                        "core_search_policy.py",
                        "core_execution.py",
                        "core_targets.py",
                        "core_intensity.py",
                        "core_safe_nav.py",
                        "marine_knownmap_runtime.py",
                        "marine_knownmap_runtime_2usv.py",
                    ]):
                        checks["no_modified_algorithm_files"] = False
                        print(f"[WARN] Unauthorized modification: {norm_path}")
    except Exception as e:
        print(f"[WARN] Error scanning Porcelain: {e}")

    checks["pre_existing_dirty_state_logged"] = (len(pre_existing_dirty_state) > 0)

    # E2E checklists compilation
    required_keys = [
        "probe_json_exists",
        "trace_json_exists",
        "trace_csv_exists",
        "summary_json_exists",
        "sensor_json_exists",
        "collision_json_exists",
        "config_json_exists",
        "summary_md_exists",
        "paths_png_exists",
        "sv0_start_is_25_2",
        "sv1_start_is_35_2",
        "sv0_target_is_24_2",
        "sv1_target_is_35_3",
        "map_id_is_res10",
        "resolution_m_is_10",
        "sensor_range_m_is_50",
        "exactly_two_usvs",
        "no_sonar_sensor",
        "no_camera_sensor",
        "no_env_step_calls",
        "planner_intensity_input_allowed",
        "no_dynamic_string_bypass",
        "no_post_holoocean_belief_update",
        "no_target_detection_closed_loop",
        "uses_env_act_and_tick",
        "sv0_arrived",
        "sv1_arrived",
        "zero_timeouts",
        "sv0_matches_alg",
        "sv1_matches_alg",
        "sv0_final_dist_ok",
        "sv1_final_dist_ok",
        "ticks_within_bounds",
        "min_separation_ge_30m",
        "zero_collision_fails",
        "selected_sensor_keys_valid",
        "no_modified_algorithm_files"
    ]

    all_passed = all(checks.get(key, False) for key in required_keys)

    return {
        "all_passed": all_passed,
        "checks": checks,
        "pre_existing_dirty_state": pre_existing_dirty_state
    }


def main() -> None:
    print("=== Running Phase 5B-2 One-Step Bridge Audit Check ===")
    results = run_audits()

    print(f"Audit Result: {'PASSED' if results['all_passed'] else 'FAILED'}")
    for k, v in results["checks"].items():
        print(f"  - {k}: {v}")

    # Output JSON manifest report
    os.makedirs(os.path.dirname(AUDIT_JSON), exist_ok=True)
    
    serialized_results = {
        "all_passed": bool(results["all_passed"]),
        "checks": {k: bool(v) for k, v in results["checks"].items()},
        "pre_existing_dirty_state": results["pre_existing_dirty_state"]
    }

    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(serialized_results, f, indent=2)
    print(f"Saved audit JSON results: {AUDIT_JSON}")

    # Output Markdown summary report
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)

    summary_content = f"""# Phase 5B-2 One-Step Bridge Audit Summary Report

## Audit Status
- **Overall Status**: `{'PASSED' if results['all_passed'] else 'FAILED'}`
- **Audit Type**: HoloOcean Dual-USV One-Step Bridge Centralized Planner Validation

## E2E Telemetry Checkpoints
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **probe_json_exists** | `dual_usv_one_step_bridge_runtime_probe.json` exists | `{results['checks']['probe_json_exists']}` | {'✅' if results['checks']['probe_json_exists'] else '❌'} |
| **trace_json_exists** | `dual_usv_one_step_bridge_tick_trace.json` exists | `{results['checks']['trace_json_exists']}` | {'✅' if results['checks']['trace_json_exists'] else '❌'} |
| **trace_csv_exists** | `dual_usv_one_step_bridge_tick_trace.csv` exists | `{results['checks']['trace_csv_exists']}` | {'✅' if results['checks']['trace_csv_exists'] else '❌'} |
| **summary_json_exists** | `dual_usv_one_step_bridge_summary.json` exists | `{results['checks']['summary_json_exists']}` | {'✅' if results['checks']['summary_json_exists'] else '❌'} |
| **sensor_json_exists** | `dual_usv_one_step_bridge_sensor_sources.json` exists | `{results['checks']['sensor_json_exists']}` | {'✅' if results['checks']['sensor_json_exists'] else '❌'} |
| **collision_json_exists**| `dual_usv_one_step_bridge_collision_metrics.json` exists | `{results['checks']['collision_json_exists']}` | {'✅' if results['checks']['collision_json_exists'] else '❌'} |
| **config_json_exists** | `dual_usv_one_step_bridge_config.json` exists | `{results['checks']['config_json_exists']}` | {'✅' if results['checks']['config_json_exists'] else '❌'} |
| **summary_md_exists** | `dual_usv_one_step_bridge_summary.md` summary exists | `{results['checks']['summary_md_exists']}` | {'✅' if results['checks']['summary_md_exists'] else '❌'} |
| **paths_png_exists** | `dual_usv_one_step_bridge_paths.png` paths map exists | `{results['checks']['paths_png_exists']}` | {'✅' if results['checks']['paths_png_exists'] else '❌'} |
| **sv0_start_is_25_2** | sv0 starting grid aligns with `[25, 2]` | `{results['checks'].get('sv0_start_is_25_2')}` | {'✅' if results['checks'].get('sv0_start_is_25_2') else '❌'} |
| **sv1_start_is_35_2** | sv1 starting grid aligns with `[35, 2]` | `{results['checks'].get('sv1_start_is_35_2')}` | {'✅' if results['checks'].get('sv1_start_is_35_2') else '❌'} |
| **sv0_target_is_24_2**| sv0 target grid aligns with `[24, 2]` | `{results['checks'].get('sv0_target_is_24_2')}` | {'✅' if results['checks'].get('sv0_target_is_24_2') else '❌'} |
| **sv1_target_is_35_3**| sv1 target grid aligns with `[35, 3]` | `{results['checks'].get('sv1_target_is_35_3')}` | {'✅' if results['checks'].get('sv1_target_is_35_3') else '❌'} |
| **map_id_is_res10** | Map scale limits match 81x81 boundary grid | `{results['checks'].get('map_id_is_res10')}` | {'✅' if results['checks'].get('map_id_is_res10') else '❌'} |
| **resolution_m_is_10** | Map resolution scale is exactly `10.0m` | `{results['checks'].get('resolution_m_is_10')}` | {'✅' if results['checks'].get('resolution_m_is_10') else '❌'} |
| **sensor_range_m_is_50**| Sensor range scale is exactly `50.0m` | `{results['checks'].get('sensor_range_m_is_50')}` | {'✅' if results['checks'].get('sensor_range_m_is_50') else '❌'} |
| **exactly_two_usvs** | E2E setup features exactly two USV configurations | `{results['checks'].get('exactly_two_usvs')}` | {'✅' if results['checks'].get('exactly_two_usvs') else '❌'} |
| **no_sonar_sensor** | No ImagingSonar/sonars defined in scenario | `{results['checks'].get('no_sonar_sensor')}` | {'✅' if results['checks'].get('no_sonar_sensor') else '❌'} |
| **no_camera_sensor** | No cameras defined in scenario | `{results['checks'].get('no_camera_sensor')}` | {'✅' if results['checks'].get('no_camera_sensor') else '❌'} |
| **no_env_step_calls** | No deprecated legacy env.step() calls | `{results['checks'].get('no_env_step_calls')}` | {'✅' if results['checks'].get('no_env_step_calls') else '❌'} |
| **planner_intensity_input_allowed**| Planner reads intensity_map directly | `{results['checks'].get('planner_intensity_input_allowed')}` | {'✅' if results['checks'].get('planner_intensity_input_allowed') else '❌'} |
| **no_dynamic_string_bypass**| No dynamic string concatenation bypass | `{results['checks'].get('no_dynamic_string_bypass')}` | {'✅' if results['checks'].get('no_dynamic_string_bypass') else '❌'} |
| **no_post_holoocean_belief_update**| No GP or belief updates after execution | `{results['checks'].get('no_post_holoocean_belief_update')}` | {'✅' if results['checks'].get('no_post_holoocean_belief_update') else '❌'} |
| **no_target_detection_closed_loop**| No dynamic target detection closed-loop | `{results['checks'].get('no_target_detection_closed_loop')}` | {'✅' if results['checks'].get('no_target_detection_closed_loop') else '❌'} |
| **uses_env_act_and_tick**| Steps physical actuators and ticks synchronizer | `{results['checks'].get('uses_env_act_and_tick')}` | {'✅' if results['checks'].get('uses_env_act_and_tick') else '❌'} |
| **sv0_arrived** | sv0 successfully arrived at planned target | `{results['checks'].get('sv0_arrived')}` | {'✅' if results['checks'].get('sv0_arrived') else '❌'} |
| **sv1_arrived** | sv1 successfully arrived at planned target | `{results['checks'].get('sv1_arrived')}` | {'✅' if results['checks'].get('sv1_arrived') else '❌'} |
| **zero_timeouts** | Zero timeouts encountered during physical execution | `{results['checks'].get('zero_timeouts')}` | {'✅' if results['checks'].get('zero_timeouts') else '❌'} |
| **sv0_matches_alg** | sv0 final projected grid matches algorithm target| `{results['checks'].get('sv0_matches_alg')}` | {'✅' if results['checks'].get('sv0_matches_alg') else '❌'} |
| **sv1_matches_alg** | sv1 final projected grid matches algorithm target| `{results['checks'].get('sv1_matches_alg')}` | {'✅' if results['checks'].get('sv1_matches_alg') else '❌'} |
| **sv0_final_dist_ok** | sv0 final distance offset $\\le$ `5.0` meters | `{results['checks'].get('sv0_final_dist_ok')}` | {'✅' if results['checks'].get('sv0_final_dist_ok') else '❌'} |
| **sv1_final_dist_ok** | sv1 final distance offset $\\le$ `5.0` meters | `{results['checks'].get('sv1_final_dist_ok')}` | {'✅' if results['checks'].get('sv1_final_dist_ok') else '❌'} |
| **ticks_within_bounds** | E2E ticks taken is active and $\\le$ `500` | `{results['checks'].get('ticks_within_bounds')}` | {'✅' if results['checks'].get('ticks_within_bounds') else '❌'} |
| **min_separation_ge_30m**| Minimum separation distance is $\\ge$ `30.0m` | `{results['checks'].get('min_separation_ge_30m')}` | {'✅' if results['checks'].get('min_separation_ge_30m') else '❌'} |
| **zero_collision_fails**| Total collision violations is strictly 0 | `{results['checks'].get('zero_collision_fails')}` | {'✅' if results['checks'].get('zero_collision_fails') else '❌'} |
| **selected_sensor_keys**| Selected sensor telemetry keys are valid | `{results['checks'].get('selected_sensor_keys_valid')}` | {'✅' if results['checks'].get('selected_sensor_keys_valid') else '❌'} |
| **no_modified_files** | No *new* core algorithm modifications created | `{results['checks'].get('no_modified_algorithm_files')}` | {'✅' if results['checks'].get('no_modified_algorithm_files') else '❌'} |

## Pre-Existing Working Tree Dirty States
- **Pre-existing modified files**: `{results['pre_existing_dirty_state']}`

*Audit verified both statically and dynamically from E2E simulation logs.*
"""
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(summary_content)

    print(f"Saved audit report summary: {AUDIT_MD}")


if __name__ == "__main__":
    main()
