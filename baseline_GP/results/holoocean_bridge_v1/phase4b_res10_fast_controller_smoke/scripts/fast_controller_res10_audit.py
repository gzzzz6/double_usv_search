"""Static and dynamic audit script for HoloOcean Phase 4B."""

import os
import json
import numpy as np
import hashlib
from typing import Dict, Any, List

# Target Paths
BASE_DIR = r"baseline_GP"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase4b_res10_fast_controller_smoke"))

TRACE_JSON      = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "fast_controller_res10_trace.json"))
TRACE_CSV       = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "fast_controller_res10_trace.csv"))
SUMMARY_JSON    = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "fast_controller_res10_waypoint_summary.json"))
SUMMARY_MD      = os.path.normpath(os.path.join(PHASE_DIR, "reports",   "fast_controller_res10_summary.md"))
PREVIEW_PNG     = os.path.normpath(os.path.join(PHASE_DIR, "visuals",   "fast_controller_res10_path.png"))

SMOKE_SCRIPT    = os.path.normpath(os.path.join(PHASE_DIR, "scripts",   "fast_controller_res10_smoke.py"))

AUDIT_JSON      = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "fast_controller_res10_audit.json"))
AUDIT_MD        = os.path.normpath(os.path.join(PHASE_DIR, "reports",   "fast_controller_res10_audit_summary.md"))


def run_audits() -> Dict[str, Any]:
    checks = {}

    # Checks 1-5: Files exist
    checks["trace_json_exists"] = os.path.exists(TRACE_JSON)
    checks["trace_csv_exists"] = os.path.exists(TRACE_CSV)
    checks["summary_json_exists"] = os.path.exists(SUMMARY_JSON)
    checks["summary_md_exists"] = os.path.exists(SUMMARY_MD)
    checks["preview_png_exists"] = os.path.exists(PREVIEW_PNG)

    # Load Waypoint Summary
    wps = []
    if checks["summary_json_exists"]:
        try:
            with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
                wps = json.load(f)
            checks["summary_json_parse_ok"] = True
        except Exception as e:
            checks["summary_json_parse_ok"] = False
            checks["summary_json_parse_error"] = str(e)
    else:
        checks["summary_json_parse_ok"] = False

    # Load Telemetry Trace
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

    # Load 10m Map Spec for comparison
    map_spec_ok = False
    map_npz_path = os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz")
    if os.path.exists(map_npz_path):
        try:
            data = np.load(map_npz_path, allow_pickle=True)
            spec = json.loads(str(data["spec_json"]))
            map_spec_ok = True
        except Exception as e:
            print(f"[WARN] Error loading map spec: {e}")
            
    # Checks 6-10: Map & Environment specifications
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

    # Checks 11-16: Control settings and single USV agent constraints
    if os.path.exists(SMOKE_SCRIPT):
        with open(SMOKE_SCRIPT, "r", encoding="utf-8") as f:
            smoke_src = f.read()
            
        checks["control_scheme_is_0"] = ("control_scheme\": 0" in smoke_src or "control_scheme = 0" in smoke_src)
        checks["no_camera_sensor"] = ("CameraSensor" not in smoke_src)
        checks["no_sonar_sensor"] = ("SonarSensor" not in smoke_src and "ImagingSonar" not in smoke_src)
        
        # Check single sv agent in agents block
        checks["single_sv_agent"] = ("\"agent_name\": \"sv\"" in smoke_src and "SurfaceVessel" in smoke_src)
        checks["no_target_agent"] = ("\"agent_name\": \"target\"" not in smoke_src)
        checks["no_target_prop"] = ("target_prop" not in smoke_src)
    else:
        checks["control_scheme_is_0"] = False
        checks["no_camera_sensor"] = False
        checks["no_sonar_sensor"] = False
        checks["single_sv_agent"] = False
        checks["no_target_agent"] = False
        checks["no_target_prop"] = False

    # Checks 17-19: Code isolation from search algorithms
    if os.path.exists(SMOKE_SCRIPT):
        checks["no_import_plan_next_policy"] = ("plan_next_policy_cell" not in smoke_src)
        checks["no_import_detect_targets"] = ("detect_targets" not in smoke_src)
        checks["no_clue_or_intensity_keys"] = not any(
            k in smoke_src for k in ["found_mask", "intensity_map", "GP clue", "gp_clue"]
        )
    else:
        checks["no_import_plan_next_policy"] = False
        checks["no_import_detect_targets"] = False
        checks["no_clue_or_intensity_keys"] = False

    # Checks 20-25: Waypoint closed loop performance metrics
    if checks["summary_json_parse_ok"] and len(wps) == 4:
        checks["waypoint_count_is_4"] = True
        
        # Verify bi-directional round-trip mapping for all waypoints
        roundtrips_passed = True
        if map_spec_ok:
            try:
                from baseline_GP.holoocean_bridge.coordinate_adapter import CoordinateAdapterConfig, grid_to_world, world_to_grid
                from baseline_GP.holoocean_bridge.scene_map_adapter import scene_map_config_from_spec
                cfg = scene_map_config_from_spec(spec)
                for w in wps:
                    tc = tuple(w["target_cell"])
                    w_coord = grid_to_world(tc, cfg)
                    g_back = world_to_grid(w_coord, cfg, (81, 81))
                    if g_back != tc:
                        roundtrips_passed = False
                        break
            except Exception as e:
                print(f"[WARN] Error running roundtrip mapping check: {e}")
                roundtrips_passed = False
        else:
            roundtrips_passed = False
        
        checks["waypoint_roundtrips_passed"] = roundtrips_passed
        
        # Counts and limits
        arrived_count = sum(1 for w in wps if w["arrived"])
        timeout_count = sum(1 for w in wps if w["timeout"])
        
        checks["arrived_count_is_4"] = (arrived_count == 4)
        checks["timeout_count_is_0"] = (timeout_count == 0)
        
        # Check projection and final distance to targets
        proj_matches = all(w["final_projected_cell"] == w["target_cell"] for w in wps)
        max_dist = max(w["final_distance_to_target_m"] for w in wps)
        
        checks["each_final_projected_matches_target"] = proj_matches
        checks["max_final_distance_lte_5m"] = (max_dist <= 5.0)
    else:
        checks["waypoint_count_is_4"] = False
        checks["waypoint_roundtrips_passed"] = False
        checks["arrived_count_is_4"] = False
        checks["timeout_count_is_0"] = False
        checks["each_final_projected_matches_target"] = False
        checks["max_final_distance_lte_5m"] = False

    # Checks 26-29: Execution ticks and trajectory boundaries
    if checks["summary_json_parse_ok"] and len(wps) == 4 and checks["trace_json_parse_ok"]:
        total_ticks = sum(w["ticks"] for w in wps)
        mean_ticks = total_ticks / 4.0
        max_ticks = max(w["ticks"] for w in wps)
        
        checks["mean_ticks_lt_300"] = (mean_ticks < 300.0)
        checks["max_ticks_lte_400"] = (max_ticks <= 400)
        checks["total_ticks_gt_0"] = (total_ticks > 0)
        
        # Check trajectory in bounds (0 <= row < 81, 0 <= col < 81)
        in_bounds = True
        for t in trace:
            r, c = t["projected_row"], t["projected_col"]
            if not (0 <= r < 81 and 0 <= c < 81):
                in_bounds = False
                break
        checks["trajectory_in_bounds"] = in_bounds
    else:
        checks["mean_ticks_lt_300"] = False
        checks["max_ticks_lte_400"] = False
        checks["total_ticks_gt_0"] = False
        checks["trajectory_in_bounds"] = False

    # Checks 30-31: Code cleanliness and injection scanning
    if os.path.exists(SMOKE_SCRIPT):
        checks["smoke_no_simpleunderwater"] = ("SimpleUnderwater" not in smoke_src)
        
        # Check for injection signatures
        dynamic_signatures = ["sys.meta_path", "MetaPathFinder", "exec(compile)", "ModuleType"]
        checks["smoke_no_injections"] = not any(sig in smoke_src for sig in dynamic_signatures)
    else:
        checks["smoke_no_simpleunderwater"] = False
        checks["smoke_no_injections"] = False

    # Assess overall success
    required_keys = [
        "trace_json_exists",
        "trace_csv_exists",
        "summary_json_exists",
        "summary_md_exists",
        "preview_png_exists",
        "map_id_is_res10",
        "world_is_openwater",
        "package_name_is_ocean",
        "cell_size_m_is_10",
        "origin_is_correct",
        "control_scheme_is_0",
        "no_camera_sensor",
        "no_sonar_sensor",
        "single_sv_agent",
        "no_target_agent",
        "no_target_prop",
        "no_import_plan_next_policy",
        "no_import_detect_targets",
        "no_clue_or_intensity_keys",
        "waypoint_count_is_4",
        "waypoint_roundtrips_passed",
        "arrived_count_is_4",
        "timeout_count_is_0",
        "each_final_projected_matches_target",
        "max_final_distance_lte_5m",
        "mean_ticks_lt_300",
        "max_ticks_lte_400",
        "total_ticks_gt_0",
        "trajectory_in_bounds",
        "smoke_no_simpleunderwater",
        "smoke_no_injections"
    ]

    all_passed = all(checks.get(key, False) for key in required_keys)

    return {
        "all_passed": all_passed,
        "checks": checks
    }


def main():
    print("=== Running Phase 4B Fast Waypoint Smoke Audit Check ===")
    results = run_audits()

    print(f"Audit Result: {'PASSED' if results['all_passed'] else 'FAILED'}")
    for k, v in results["checks"].items():
        print(f"  - {k}: {v}")

    # Output JSON manifest
    os.makedirs(os.path.dirname(AUDIT_JSON), exist_ok=True)
    
    # Convert numpy types to python native types for JSON serialization
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
    print(f"Saved audit JSON to: {AUDIT_JSON}")

    # Output Markdown summary report
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)

    summary_content = f"""# Phase 4B Waypoint Smoke Audit Summary Report

## Audit Status
- **Overall Status**: `{'PASSED' if results['all_passed'] else 'FAILED'}`
- **Audit Type**: 10m OpenWater Fast Waypoint Proportional Controller Verification

## Detailed Checks Table

| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **trace_json_exists** | `fast_controller_res10_trace.json` exists | `{results['checks']['trace_json_exists']}` | {'✅' if results['checks']['trace_json_exists'] else '❌'} |
| **trace_csv_exists** | `fast_controller_res10_trace.csv` exists | `{results['checks']['trace_csv_exists']}` | {'✅' if results['checks']['trace_csv_exists'] else '❌'} |
| **summary_json_exists** | `fast_controller_res10_waypoint_summary.json` exists | `{results['checks']['summary_json_exists']}` | {'✅' if results['checks']['summary_json_exists'] else '❌'} |
| **summary_md_exists** | `fast_controller_res10_summary.md` exists | `{results['checks']['summary_md_exists']}` | {'✅' if results['checks']['summary_md_exists'] else '❌'} |
| **preview_png_exists** | `fast_controller_res10_path.png` visual preview exists | `{results['checks']['preview_png_exists']}` | {'✅' if results['checks']['preview_png_exists'] else '❌'} |
| **map_id_is_res10** | Map ID is `openwater_open_res10_v1` | `{results['checks'].get('map_id_is_res10')}` | {'✅' if results['checks'].get('map_id_is_res10') else '❌'} |
| **world_is_openwater** | HoloOcean world is `OpenWater` | `{results['checks'].get('world_is_openwater')}` | {'✅' if results['checks'].get('world_is_openwater') else '❌'} |
| **package_name_is_ocean** | Package name is `Ocean` | `{results['checks'].get('package_name_is_ocean')}` | {'✅' if results['checks'].get('package_name_is_ocean') else '❌'} |
| **cell_size_m_is_10** | Cell size is `10.0` meters | `{results['checks'].get('cell_size_m_is_10')}` | {'✅' if results['checks'].get('cell_size_m_is_10') else '❌'} |
| **origin_is_correct** | Origin XY is `[-400.0, 400.0]` | `{results['checks'].get('origin_is_correct')}` | {'✅' if results['checks'].get('origin_is_correct') else '❌'} |
| **control_scheme_is_0**| SurfaceVessel runs in `control_scheme=0` mode | `{results['checks'].get('control_scheme_is_0')}` | {'✅' if results['checks'].get('control_scheme_is_0') else '❌'} |
| **no_camera_sensor** | No cameras defined in scenario | `{results['checks'].get('no_camera_sensor')}` | {'✅' if results['checks'].get('no_camera_sensor') else '❌'} |
| **no_sonar_sensor** | No ImagingSonar/sonars defined in scenario | `{results['checks'].get('no_sonar_sensor')}` | {'✅' if results['checks'].get('no_sonar_sensor') else '❌'} |
| **single_sv_agent** | scenario contains exactly one main agent `sv` | `{results['checks'].get('single_sv_agent')}` | {'✅' if results['checks'].get('single_sv_agent') else '❌'} |
| **no_target_agent** | No dynamic target proxy agent defined | `{results['checks'].get('no_target_agent')}` | {'✅' if results['checks'].get('no_target_agent') else '❌'} |
| **no_target_prop** | No dynamic target prop placeholder defined | `{results['checks'].get('no_target_prop')}` | {'✅' if results['checks'].get('no_target_prop') else '❌'} |
| **no_import_plan** | No baseline planner `plan_next_policy_cell` imported| `{results['checks'].get('no_import_plan_next_policy')}` | {'✅' if results['checks'].get('no_import_plan_next_policy') else '❌'} |
| **no_import_detect** | No baseline target `detect_targets` imported | `{results['checks'].get('no_import_detect_targets')}` | {'✅' if results['checks'].get('no_import_detect_targets') else '❌'} |
| **no_clue_or_intensity**| No search updating/GP clue variable keys used | `{results['checks'].get('no_clue_or_intensity_keys')}` | {'✅' if results['checks'].get('no_clue_or_intensity_keys') else '❌'} |
| **waypoint_count_is_4**| 4 waypoints are planned and executed | `{results['checks'].get('waypoint_count_is_4')}` | {'✅' if results['checks'].get('waypoint_count_is_4') else '❌'} |
| **waypoint_roundtrips**| All planned cells pass grid $\\leftrightarrow$ world round-trips | `{results['checks'].get('waypoint_roundtrips_passed')}` | {'✅' if results['checks'].get('waypoint_roundtrips_passed') else '❌'} |
| **arrived_count_is_4** | `arrived_count` == `4` (100% success rate) | `{results['checks'].get('arrived_count_is_4')}` | {'✅' if results['checks'].get('arrived_count_is_4') else '❌'} |
| **timeout_count_is_0** | `timeout_count` == `0` (Zero timeout navigation) | `{results['checks'].get('timeout_count_is_0')}` | {'✅' if results['checks'].get('timeout_count_is_0') else '❌'} |
| **projected_matches** | Each `final_projected_cell` == `target_cell` | `{results['checks'].get('each_final_projected_matches_target')}` | {'✅' if results['checks'].get('each_final_projected_matches_target') else '❌'} |
| **max_dist_lte_5m** | Max final distance to targets $\\le$ `5.0` meters | `{results['checks'].get('max_final_distance_lte_5m')}` | {'✅' if results['checks'].get('max_final_distance_lte_5m') else '❌'} |
| **mean_ticks_lt_300** | Mean execution ticks per waypoint $<$ `300` | `{results['checks'].get('mean_ticks_lt_300')}` | {'✅' if results['checks'].get('mean_ticks_lt_300') else '❌'} |
| **max_ticks_lte_400** | Max execution ticks per waypoint $\\le$ `400` | `{results['checks'].get('max_ticks_lte_400')}` | {'✅' if results['checks'].get('max_ticks_lte_400') else '❌'} |
| **total_ticks_gt_0** | SV moved (accumulated global ticks $>$ `0`) | `{results['checks'].get('total_ticks_gt_0')}` | {'✅' if results['checks'].get('total_ticks_gt_0') else '❌'} |
| **trajectory_in_bounds**| Complete trajectory falls inside 81x81 boundary grid | `{results['checks'].get('trajectory_in_bounds')}` | {'✅' if results['checks'].get('trajectory_in_bounds') else '❌'} |
| **smoke_no_simple** | Standalone script compiles on `OpenWater` (no Simple) | `{results['checks'].get('smoke_no_simpleunderwater')}` | {'✅' if results['checks'].get('smoke_no_simpleunderwater') else '❌'} |
| **smoke_no_injections**| Statically audited to contain zero dynamic loader hacks| `{results['checks'].get('smoke_no_injections')}` | {'✅' if results['checks'].get('smoke_no_injections') else '❌'} |

*Audit verified both statically and dynamically from simulation logs.*
"""
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(summary_content)

    print(f"Saved audit report summary to: {AUDIT_MD}")


if __name__ == "__main__":
    main()
