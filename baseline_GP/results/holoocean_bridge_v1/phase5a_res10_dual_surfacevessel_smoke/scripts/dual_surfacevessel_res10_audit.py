"""Static and dynamic audit script for Phase 5A: Dual SurfaceVessel 10m fast controller physical smoke.

Performs static code checks for sensor/algorithm isolation, runs E2E trajectory bounds verification,
analyzes separation metrics, and generates official audit reports.
"""

import os
import sys
import json
import math
from typing import Dict, Any, List
import numpy as np

# Add root directory to sys.path
sys.path.append(os.path.abspath("."))


# Target Paths
BASE_DIR = r"baseline_GP"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase5a_res10_dual_surfacevessel_smoke"))

TICK_JSON       = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_surfacevessel_res10_tick_trace.json"))
TICK_CSV        = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_surfacevessel_res10_tick_trace.csv"))
WAYPOINT_JSON   = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_surfacevessel_res10_waypoint_summary.json"))
AGENT_JSON      = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_surfacevessel_res10_agent_manifest.json"))
COLLISION_JSON  = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_surfacevessel_res10_collision_metrics.json"))
SUMMARY_MD      = os.path.normpath(os.path.join(PHASE_DIR, "reports",   "dual_surfacevessel_res10_summary.md"))
PATHS_PNG       = os.path.normpath(os.path.join(PHASE_DIR, "visuals",   "dual_surfacevessel_res10_paths.png"))

SMOKE_SCRIPT    = os.path.normpath(os.path.join(PHASE_DIR, "scripts",   "dual_surfacevessel_res10_smoke.py"))

AUDIT_JSON      = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "dual_surfacevessel_res10_audit.json"))
AUDIT_MD        = os.path.normpath(os.path.join(PHASE_DIR, "reports",   "dual_surfacevessel_res10_audit_summary.md"))


def run_audits() -> Dict[str, Any]:
    checks = {}

    # Checks 1-7: Verification files existence
    checks["tick_json_exists"] = os.path.exists(TICK_JSON)
    checks["tick_csv_exists"] = os.path.exists(TICK_CSV)
    checks["waypoint_json_exists"] = os.path.exists(WAYPOINT_JSON)
    checks["agent_json_exists"] = os.path.exists(AGENT_JSON)
    checks["collision_json_exists"] = os.path.exists(COLLISION_JSON)
    checks["summary_md_exists"] = os.path.exists(SUMMARY_MD)
    checks["paths_png_exists"] = os.path.exists(PATHS_PNG)

    # 1. Load waypoint summary JSON
    wps = []
    if checks["waypoint_json_exists"]:
        try:
            with open(WAYPOINT_JSON, "r", encoding="utf-8") as f:
                wps = json.load(f)
            checks["waypoint_json_parse_ok"] = True
        except Exception as e:
            checks["waypoint_json_parse_ok"] = False
            checks["waypoint_json_parse_error"] = str(e)
    else:
        checks["waypoint_json_parse_ok"] = False

    # 2. Load tick trace JSON
    trace = []
    if checks["tick_json_exists"]:
        try:
            with open(TICK_JSON, "r", encoding="utf-8") as f:
                trace = json.load(f)
            checks["tick_json_parse_ok"] = True
            checks["total_trace_ticks"] = len(trace)
        except Exception as e:
            checks["tick_json_parse_ok"] = False
            checks["tick_json_parse_error"] = str(e)
            checks["total_trace_ticks"] = 0
    else:
        checks["tick_json_parse_ok"] = False
        checks["total_trace_ticks"] = 0

    # 3. Load agent manifest
    manifest = {}
    if checks["agent_json_exists"]:
        try:
            with open(AGENT_JSON, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            checks["agent_json_parse_ok"] = True
        except Exception as e:
            checks["agent_json_parse_ok"] = False
            checks["agent_json_parse_error"] = str(e)
    else:
        checks["agent_json_parse_ok"] = False

    # 4. Load collision metrics
    collision = {}
    if checks["collision_json_exists"]:
        try:
            with open(COLLISION_JSON, "r", encoding="utf-8") as f:
                collision = json.load(f)
            checks["collision_json_parse_ok"] = True
        except Exception as e:
            checks["collision_json_parse_ok"] = False
            checks["collision_json_parse_error"] = str(e)
    else:
        checks["collision_json_parse_ok"] = False

    # Load 10m Map Spec for comparison
    map_spec_ok = False
    map_npz_path = os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz")
    if os.path.exists(map_npz_path):
        try:
            data = np.load(map_npz_path, allow_pickle=True)
            spec = json.loads(str(data["spec_json"]))
            map_spec_ok = True
        except Exception as e:
            print(f"[WARN] Error loading map spec npz: {e}")

    # Checks 8-12: Scenario parameters validation
    if map_spec_ok:
        checks["map_id_is_res10"] = (spec.get("map_id") == "openwater_open_res10_v1")
        checks["world_is_openwater"] = (spec.get("world") == "OpenWater")
        checks["package_name_is_ocean"] = (spec.get("package_name") == "Ocean")
        checks["cell_size_m_is_10"] = (float(spec.get("cell_size_m", 0.0)) == 10.0)
        checks["origin_is_correct"] = (spec.get("origin_world_xy") == [-400.0, 400.0])
    else:
        checks["map_id_is_res10"] = False
        checks["world_is_openwater"] = False
        checks["package_name_is_ocean"] = False
        checks["cell_size_m_is_10"] = False
        checks["origin_is_correct"] = False

    # Static code checking of smoke script
    smoke_src = ""
    if os.path.exists(SMOKE_SCRIPT):
        try:
            with open(SMOKE_SCRIPT, "r", encoding="utf-8") as f:
                smoke_src = f.read()
            checks["smoke_script_readable"] = True
        except Exception as e:
            checks["smoke_script_readable"] = False
            print(f"[WARN] Could not read smoke script: {e}")
    else:
        checks["smoke_script_readable"] = False

    # Checks 13-17: Sensor & Agent type checks
    if checks["smoke_script_readable"]:
        # Verify no sonars
        checks["no_sonar_sensor"] = not any(s in smoke_src for s in ["ImagingSonar", "SidescanSonar", "ProfilingSonar", "SinglebeamSonar", "SonarSensor"])
        # Verify no cameras
        checks["no_camera_sensor"] = ("CameraSensor" not in smoke_src and "Camera" not in smoke_src)
        
        # Verify agent name boundaries
        checks["agents_are_sv0_and_sv1"] = ("sv0" in smoke_src and "sv1" in smoke_src and "agent_name\": \"sv\"" not in smoke_src)
        checks["no_target_agent"] = ("agent_name\": \"target\"" not in smoke_src)
        checks["no_target_prop"] = ("target_prop" not in smoke_src)
    else:
        checks["no_sonar_sensor"] = False
        checks["no_camera_sensor"] = False
        checks["agents_are_sv0_and_sv1"] = False
        checks["no_target_agent"] = False
        checks["no_target_prop"] = False

    # Checks 18-20: E2E Search/GP libraries clean isolation verification
    if checks["smoke_script_readable"]:
        checks["no_search_libraries"] = not any(l in smoke_src for l in ["marine_knownmap_runtime_2usv", "marine_knownmap_runtime", "core_search_policy"])
        checks["no_import_plan_hooks"] = ("plan_next_policy_cell" not in smoke_src and "finalize_policy_step" not in smoke_src)
        checks["no_search_parameters"] = not any(k in smoke_src for k in ["found_mask", "intensity_map", "search_info_map"])
    else:
        checks["no_search_libraries"] = False
        checks["no_import_plan_hooks"] = False
        checks["no_search_parameters"] = False

    # Checks 21-23: Simulator API compliance
    if checks["smoke_script_readable"]:
        checks["uses_env_act_sv0_sv1"] = ("env.act(\"sv0\"" in smoke_src and "env.act(\"sv1\"" in smoke_src)
        checks["uses_single_env_tick"] = ("env.tick()" in smoke_src)
        checks["no_env_step_calls"] = ("env.step(" not in smoke_src)
    else:
        checks["uses_env_act_sv0_sv1"] = False
        checks["uses_single_env_tick"] = False
        checks["no_env_step_calls"] = False

    # Check agents and fast controller in manifest
    if checks["agent_json_parse_ok"] and "agents" in manifest:
        agents = manifest["agents"]
        checks["manifest_has_two_agents"] = (len(agents) == 2)
        checks["both_agents_scheme_0"] = (agents[0]["control_scheme"] == 0 and agents[1]["control_scheme"] == 0)
        checks["agent_names_matched"] = (agents[0]["name"] == "sv0" and agents[1]["name"] == "sv1")
    else:
        checks["manifest_has_two_agents"] = False
        checks["both_agents_scheme_0"] = False
        checks["agent_names_matched"] = False

    # Checks 24-29: Dynamic physical waypoint performance
    if checks["waypoint_json_parse_ok"] and len(wps) == 4:
        checks["waypoint_count_is_4"] = True
        
        # Grid bidirectional checks for waypoints
        bi_roundtrips = True
        if map_spec_ok:
            try:
                from baseline_GP.holoocean_bridge.coordinate_adapter import CoordinateAdapterConfig, grid_to_world, world_to_grid
                from baseline_GP.holoocean_bridge.scene_map_adapter import scene_map_config_from_spec
                cfg = scene_map_config_from_spec(spec)
                for w in wps:
                    g0 = tuple(w["sv0_target_cell"])
                    g1 = tuple(w["sv1_target_cell"])
                    # Check sv0
                    w0_pt = grid_to_world(g0, cfg)
                    g0_back = world_to_grid(w0_pt, cfg, (81, 81))
                    if g0_back != g0:
                        bi_roundtrips = False
                    # Check sv1
                    w1_pt = grid_to_world(g1, cfg)
                    g1_back = world_to_grid(w1_pt, cfg, (81, 81))
                    if g1_back != g1:
                        bi_roundtrips = False
            except Exception as e:
                print(f"[WARN] Coordinate mapping error in audit: {e}")
                bi_roundtrips = False
        else:
            bi_roundtrips = False

        checks["waypoint_roundtrips_passed"] = bi_roundtrips

        # Arrive count and timeouts check
        arrived_0 = sum(1 for w in wps if w["sv0_arrived"])
        arrived_1 = sum(1 for w in wps if w["sv1_arrived"])
        checks["arrived_count_is_8"] = (arrived_0 + arrived_1 == 8)

        timeout_0 = sum(1 for w in wps if w["sv0_timeout"])
        timeout_1 = sum(1 for w in wps if w["sv1_timeout"])
        checks["timeout_count_is_0"] = (timeout_0 + timeout_1 == 0)

        # Confirm target projected matched and error distance is <= 5.0m
        sv0_proj_ok = all(w["sv0_final_projected_cell"] == w["sv0_target_cell"] for w in wps)
        sv1_proj_ok = all(w["sv1_final_projected_cell"] == w["sv1_target_cell"] for w in wps)
        checks["each_final_projected_matches_target"] = (sv0_proj_ok and sv1_proj_ok)

        max_dist_0 = max(w["sv0_final_dist_m"] for w in wps)
        max_dist_1 = max(w["sv1_final_dist_m"] for w in wps)
        checks["max_final_distance_lte_5m"] = (max_dist_0 <= 5.0 and max_dist_1 <= 5.0)
    else:
        checks["waypoint_count_is_4"] = False
        checks["waypoint_roundtrips_passed"] = False
        checks["arrived_count_is_8"] = False
        checks["timeout_count_is_0"] = False
        checks["each_final_projected_matches_target"] = False
        checks["max_final_distance_lte_5m"] = False

    # Checks 30-33: Time ticks and boundary limits
    if checks["waypoint_json_parse_ok"] and len(wps) == 4 and checks["tick_json_parse_ok"]:
        total_paired_ticks = sum(w["paired_total_ticks"] for w in wps)
        mean_ticks = total_paired_ticks / 4.0
        max_ticks = max(w["paired_total_ticks"] for w in wps)

        checks["mean_ticks_lt_300"] = (mean_ticks < 300.0)
        checks["max_ticks_lte_400"] = (max_ticks <= 400)
        checks["total_ticks_gt_0"] = (total_paired_ticks > 0)

        # Check boundary integrity
        bounds_ok = True
        for t in trace:
            r0, c0 = t["sv0_proj_row"], t["sv0_proj_col"]
            r1, c1 = t["sv1_proj_row"], t["sv1_proj_col"]
            if not (0 <= r0 < 81 and 0 <= c0 < 81 and 0 <= r1 < 81 and 0 <= c1 < 81):
                bounds_ok = False
                break
        checks["trajectory_in_bounds"] = bounds_ok
    else:
        checks["mean_ticks_lt_300"] = False
        checks["max_ticks_lte_400"] = False
        checks["total_ticks_gt_0"] = False
        checks["trajectory_in_bounds"] = False

    # Checks 34-36: Collision avoidance compliance
    if checks["collision_json_parse_ok"]:
        checks["min_inter_vessel_distance_m_ge_30"] = (collision.get("min_inter_vessel_distance_m", 0.0) >= 30.0)
        checks["collision_fail_ticks_is_0"] = (collision.get("collision_fail_ticks", 99) == 0)
        checks["collision_safety_verified"] = (collision.get("collision_safety_verified") is True)
    else:
        checks["min_inter_vessel_distance_m_ge_30"] = False
        checks["collision_fail_ticks_is_0"] = False
        checks["collision_safety_verified"] = False

    # Checks 37-38: Dynamic Active Movement validation (vessels must actively move)
    if checks["tick_json_parse_ok"] and len(trace) > 1:
        # 1. Unique cells
        unique_cells_0 = set((t["sv0_proj_row"], t["sv0_proj_col"]) for t in trace)
        unique_cells_1 = set((t["sv1_proj_row"], t["sv1_proj_col"]) for t in trace)
        checks["sv0_unique_cells_ge_3"] = (len(unique_cells_0) >= 3)
        checks["sv1_unique_cells_ge_3"] = (len(unique_cells_1) >= 3)

        # 2. Accumulated actual physical path length in meters
        len_0 = 0.0
        len_1 = 0.0
        for i in range(1, len(trace)):
            # sv0
            dx0 = trace[i]["sv0_loc_x"] - trace[i-1]["sv0_loc_x"]
            dy0 = trace[i]["sv0_loc_y"] - trace[i-1]["sv0_loc_y"]
            len_0 += math.hypot(dx0, dy0)
            # sv1
            dx1 = trace[i]["sv1_loc_x"] - trace[i-1]["sv1_loc_x"]
            dy1 = trace[i]["sv1_loc_y"] - trace[i-1]["sv1_loc_y"]
            len_1 += math.hypot(dx1, dy1)

        checks["sv0_path_length_m_gt_20"] = (len_0 > 20.0)
        checks["sv1_path_length_m_gt_20"] = (len_1 > 20.0)
    else:
        checks["sv0_unique_cells_ge_3"] = False
        checks["sv1_unique_cells_ge_3"] = False
        checks["sv0_path_length_m_gt_20"] = False
        checks["sv1_path_length_m_gt_20"] = False

    # Check Location fallback frequency counts (Location Sensor vs GPS fallback)
    if checks["tick_json_parse_ok"]:
        total_ticks = len(trace)
        fallback_ticks = 0
        for t in trace:
            # Under dual SurfaceVessels, sensor vector has location read. Check fallback indicator
            # Here we just track if LocationSensor readings were correctly fetched
            if t.get("sv0_loc_x") == 0.0 and t.get("sv0_loc_y") == 0.0:
                fallback_ticks += 1
        checks["location_sensor_fallback_ticks"] = fallback_ticks
        checks["location_sensor_fallback_percentage"] = (fallback_ticks / max(1, total_ticks)) * 100.0
    else:
        checks["location_sensor_fallback_ticks"] = 0
        checks["location_sensor_fallback_percentage"] = 0.0

    # Checks 39-40: Code Cleanliness verification
    if checks["smoke_script_readable"]:
        checks["smoke_no_simpleunderwater"] = ("SimpleUnderwater" not in smoke_src)
        checks["smoke_no_injections"] = not any(sig in smoke_src for sig in ["sys.meta_path", "MetaPathFinder", "exec(compile)", "ModuleType"])
    else:
        checks["smoke_no_simpleunderwater"] = False
        checks["smoke_no_injections"] = False

    # Compile critical checklists
    required_keys = [
        "tick_json_exists",
        "tick_csv_exists",
        "waypoint_json_exists",
        "agent_json_exists",
        "collision_json_exists",
        "summary_md_exists",
        "paths_png_exists",
        "map_id_is_res10",
        "world_is_openwater",
        "package_name_is_ocean",
        "cell_size_m_is_10",
        "origin_is_correct",
        "no_sonar_sensor",
        "no_camera_sensor",
        "agents_are_sv0_and_sv1",
        "no_target_agent",
        "no_target_prop",
        "no_search_libraries",
        "no_import_plan_hooks",
        "no_search_parameters",
        "uses_env_act_sv0_sv1",
        "uses_single_env_tick",
        "no_env_step_calls",
        "manifest_has_two_agents",
        "both_agents_scheme_0",
        "agent_names_matched",
        "waypoint_count_is_4",
        "waypoint_roundtrips_passed",
        "arrived_count_is_8",
        "timeout_count_is_0",
        "each_final_projected_matches_target",
        "max_final_distance_lte_5m",
        "mean_ticks_lt_300",
        "max_ticks_lte_400",
        "total_ticks_gt_0",
        "trajectory_in_bounds",
        "min_inter_vessel_distance_m_ge_30",
        "collision_fail_ticks_is_0",
        "collision_safety_verified",
        "sv0_unique_cells_ge_3",
        "sv1_unique_cells_ge_3",
        "sv0_path_length_m_gt_20",
        "sv1_path_length_m_gt_20",
        "smoke_no_simpleunderwater",
        "smoke_no_injections"
    ]

    all_passed = all(checks.get(key, False) for key in required_keys)

    return {
        "all_passed": all_passed,
        "checks": checks
    }


def main() -> None:
    print("=== Running Phase 5A Dual SurfaceVessel Smoke Audit Check ===")
    results = run_audits()

    print(f"Audit Result: {'PASSED' if results['all_passed'] else 'FAILED'}")
    for k, v in results["checks"].items():
        print(f"  - {k}: {v}")

    # Output JSON manifest report
    os.makedirs(os.path.dirname(AUDIT_JSON), exist_ok=True)
    
    serialized_checks = {}
    for k, v in results["checks"].items():
        if isinstance(v, (np.bool_, bool)):
            serialized_checks[k] = bool(v)
        elif isinstance(v, (np.integer, int)):
            serialized_checks[k] = int(v)
        elif isinstance(v, (np.floating, float)):
            serialized_checks[k] = float(v)
        elif isinstance(v, np.ndarray):
            serialized_checks[k] = v.tolist()
        else:
            serialized_checks[k] = v

    serialized_results = {
        "all_passed": bool(results["all_passed"]),
        "checks": serialized_checks
    }

    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(serialized_results, f, indent=2)
    print(f"Saved audit JSON results: {AUDIT_JSON}")

    # Output Markdown summary report
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)

    summary_content = f"""# Phase 5A Dual SurfaceVessel Waypoints Smoke Audit Summary Report

## Audit Status
- **Overall Status**: `{'PASSED' if results['all_passed'] else 'FAILED'}`
- **Audit Type**: 10m OpenWater Dual-USV Waypoint-Following Physical Smoke Auditing Checks

## E2E Telemetry Checkpoints
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **tick_json_exists** | `dual_surfacevessel_res10_tick_trace.json` exists | `{results['checks']['tick_json_exists']}` | {'✅' if results['checks']['tick_json_exists'] else '❌'} |
| **tick_csv_exists** | `dual_surfacevessel_res10_tick_trace.csv` exists | `{results['checks']['tick_csv_exists']}` | {'✅' if results['checks']['tick_csv_exists'] else '❌'} |
| **waypoint_json_exists** | `dual_surfacevessel_res10_waypoint_summary.json` exists | `{results['checks']['waypoint_json_exists']}` | {'✅' if results['checks']['waypoint_json_exists'] else '❌'} |
| **agent_json_exists** | `dual_surfacevessel_res10_agent_manifest.json` exists | `{results['checks']['agent_json_exists']}` | {'✅' if results['checks']['agent_json_exists'] else '❌'} |
| **collision_json_exists** | `dual_surfacevessel_res10_collision_metrics.json` exists | `{results['checks']['collision_json_exists']}` | {'✅' if results['checks']['collision_json_exists'] else '❌'} |
| **summary_md_exists** | `dual_surfacevessel_res10_summary.md` summary exists | `{results['checks']['summary_md_exists']}` | {'✅' if results['checks']['summary_md_exists'] else '❌'} |
| **paths_png_exists** | `dual_surfacevessel_res10_paths.png` paths map exists | `{results['checks']['paths_png_exists']}` | {'✅' if results['checks']['paths_png_exists'] else '❌'} |
| **map_id_is_res10** | Map ID is `openwater_open_res10_v1` | `{results['checks'].get('map_id_is_res10')}` | {'✅' if results['checks'].get('map_id_is_res10') else '❌'} |
| **world_is_openwater** | HoloOcean world is `OpenWater` | `{results['checks'].get('world_is_openwater')}` | {'✅' if results['checks'].get('world_is_openwater') else '❌'} |
| **package_name_is_ocean** | Package name is `Ocean` | `{results['checks'].get('package_name_is_ocean')}` | {'✅' if results['checks'].get('package_name_is_ocean') else '❌'} |
| **cell_size_m_is_10** | Cell size is `10.0` meters | `{results['checks'].get('cell_size_m_is_10')}` | {'✅' if results['checks'].get('cell_size_m_is_10') else '❌'} |
| **origin_is_correct** | Origin XY is `[-400.0, 400.0]` | `{results['checks'].get('origin_is_correct')}` | {'✅' if results['checks'].get('origin_is_correct') else '❌'} |
| **no_sonar_sensor** | No ImagingSonar/sonars defined in scenario | `{results['checks'].get('no_sonar_sensor')}` | {'✅' if results['checks'].get('no_sonar_sensor') else '❌'} |
| **no_camera_sensor** | No cameras defined in scenario | `{results['checks'].get('no_camera_sensor')}` | {'✅' if results['checks'].get('no_camera_sensor') else '❌'} |
| **agents_are_sv0_and_sv1**| Config contains exactly `sv0` and `sv1` agents | `{results['checks'].get('agents_are_sv0_and_sv1')}` | {'✅' if results['checks'].get('agents_are_sv0_and_sv1') else '❌'} |
| **no_target_agent** | No dynamic target agent defined | `{results['checks'].get('no_target_agent')}` | {'✅' if results['checks'].get('no_target_agent') else '❌'} |
| **no_target_prop** | No target prop placeholder defined | `{results['checks'].get('no_target_prop')}` | {'✅' if results['checks'].get('no_target_prop') else '❌'} |
| **no_search_libraries** | Isolated from all core baseline search files | `{results['checks'].get('no_search_libraries')}` | {'✅' if results['checks'].get('no_search_libraries') else '❌'} |
| **no_import_plan_hooks**| No imports of coordinate planner interfaces | `{results['checks'].get('no_import_plan_hooks')}` | {'✅' if results['checks'].get('no_import_plan_hooks') else '❌'} |
| **no_search_parameters**| No found_mask/belief intensities referenced | `{results['checks'].get('no_search_parameters')}` | {'✅' if results['checks'].get('no_search_parameters') else '❌'} |
| **uses_env_act_sv0_sv1** | Steps actuators using multi-agent act directives | `{results['checks'].get('uses_env_act_sv0_sv1')}` | {'✅' if results['checks'].get('uses_env_act_sv0_sv1') else '❌'} |
| **uses_single_env_tick** | Synchronizes steps via single global env.tick() | `{results['checks'].get('uses_single_env_tick')}` | {'✅' if results['checks'].get('uses_single_env_tick') else '❌'} |
| **no_env_step_calls** | No deprecated legacy env.step() calls | `{results['checks'].get('no_env_step_calls')}` | {'✅' if results['checks'].get('no_env_step_calls') else '❌'} |
| **manifest_has_two_agents**| Manifest confirms physical setup has two agents | `{results['checks'].get('manifest_has_two_agents')}` | {'✅' if results['checks'].get('manifest_has_two_agents') else '❌'} |
| **both_agents_scheme_0** | Both agents operate in direct twin-prop force mode| `{results['checks'].get('both_agents_scheme_0')}` | {'✅' if results['checks'].get('both_agents_scheme_0') else '❌'} |
| **agent_names_matched** | Names matching `sv0` and `sv1` in manifest | `{results['checks'].get('agent_names_matched')}` | {'✅' if results['checks'].get('agent_names_matched') else '❌'} |
| **waypoint_count_is_4**| Exactly 4 paired waypoint sets executed | `{results['checks'].get('waypoint_count_is_4')}` | {'✅' if results['checks'].get('waypoint_count_is_4') else '❌'} |
| **waypoint_roundtrips**| Grid cells pass bidirectional roundtrip conversions | `{results['checks'].get('waypoint_roundtrips_passed')}` | {'✅' if results['checks'].get('waypoint_roundtrips_passed') else '❌'} |
| **arrived_count_is_8** | Total waypoint arrived count == `8` | `{results['checks'].get('arrived_count_is_8')}` | {'✅' if results['checks'].get('arrived_count_is_8') else '❌'} |
| **timeout_count_is_0** | Total waypoint timeout count == `0` | `{results['checks'].get('timeout_count_is_0')}` | {'✅' if results['checks'].get('timeout_count_is_0') else '❌'} |
| **projected_matches** | Each `final_projected_cell` matches planned target| `{results['checks'].get('each_final_projected_matches_target')}` | {'✅' if results['checks'].get('each_final_projected_matches_target') else '❌'} |
| **max_dist_lte_5m** | Final coordinate error limits $\\le$ `5.0` meters | `{results['checks'].get('max_final_distance_lte_5m')}` | {'✅' if results['checks'].get('max_final_distance_lte_5m') else '❌'} |
| **mean_ticks_lt_300** | Mean execution ticks per waypoint pair $<$ `300` | `{results['checks'].get('mean_ticks_lt_300')}` | {'✅' if results['checks'].get('mean_ticks_lt_300') else '❌'} |
| **max_ticks_lte_400** | Maximum waypoint pair ticks $\\le$ `400` | `{results['checks'].get('max_ticks_lte_400')}` | {'✅' if results['checks'].get('max_ticks_lte_400') else '❌'} |
| **total_ticks_gt_0** | Accumulated E2E execution ticks $>$ `0` | `{results['checks'].get('total_ticks_gt_0')}` | {'✅' if results['checks'].get('total_ticks_gt_0') else '❌'} |
| **trajectory_in_bounds**| Complete dynamic pathways mapped within bounds | `{results['checks'].get('trajectory_in_bounds')}` | {'✅' if results['checks'].get('trajectory_in_bounds') else '❌'} |
| **min_dist_ge_30** | Minimum inter-vessel separation distance $\\ge$ `30m`| `{results['checks'].get('min_inter_vessel_distance_m_ge_30')}` | {'✅' if results['checks'].get('min_inter_vessel_distance_m_ge_30') else '❌'} |
| **collision_fail_ticks**| Total collision violations ($<$ 20m) is strictly 0 | `{results['checks'].get('collision_fail_ticks_is_0')}` | {'✅' if results['checks'].get('collision_fail_ticks_is_0') else '❌'} |
| **collision_safety** | Dynamic separation compliance verification | `{results['checks'].get('collision_safety_verified')}` | {'✅' if results['checks'].get('collision_safety_verified') else '❌'} |
| **sv0_unique_cells** | sv0 traversed $\\ge$ 3 unique projected grid cells | `{results['checks'].get('sv0_unique_cells_ge_3')}` | {'✅' if results['checks'].get('sv0_unique_cells_ge_3') else '❌'} |
| **sv1_unique_cells** | sv1 traversed $\\ge$ 3 unique projected grid cells | `{results['checks'].get('sv1_unique_cells_ge_3')}` | {'✅' if results['checks'].get('sv1_unique_cells_ge_3') else '❌'} |
| **sv0_path_length** | sv0 E2E accumulated path length $>$ `20.0` meters | `{results['checks'].get('sv0_path_length_m_gt_20')}` | {'✅' if results['checks'].get('sv0_path_length_m_gt_20') else '❌'} |
| **sv1_path_length** | sv1 E2E accumulated path length $>$ `20.0` meters | `{results['checks'].get('sv1_path_length_m_gt_20')}` | {'✅' if results['checks'].get('sv1_path_length_m_gt_20') else '❌'} |
| **smoke_no_simple** | Smoke compiles on `OpenWater` (no Simple) | `{results['checks'].get('smoke_no_simpleunderwater')}` | {'✅' if results['checks'].get('smoke_no_simpleunderwater') else '❌'} |
| **smoke_no_injections**| Free of unsafe dynamic loading injection hacks | `{results['checks'].get('smoke_no_injections')}` | {'✅' if results['checks'].get('smoke_no_injections') else '❌'} |

## Sensory Feedback Analysis
- **Location Sensor Failures**: `{results['checks']['location_sensor_fallback_ticks']}` ticks out of `{results['checks']['total_trace_ticks'] if results['checks']['tick_json_parse_ok'] else 0}` (`{results['checks']['location_sensor_fallback_percentage']:.2f}%` fallback)

*Audit verified both statically and dynamically from E2E simulation logs.*
"""
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(summary_content)

    print(f"Saved audit report summary: {AUDIT_MD}")


if __name__ == "__main__":
    main()
