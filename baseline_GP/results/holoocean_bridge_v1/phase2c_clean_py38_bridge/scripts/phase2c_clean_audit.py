"""Static audit and telemetry verification script for HoloOcean Phase 2C-clean."""

import os
import json
from typing import Dict, Any, List

# Paths
BASE_DIR = r"baseline_GP"
BRIDGE_DIR = os.path.join(BASE_DIR, "holoocean_bridge")
CLEAN_PHASE_DIR = os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase2c_clean_py38_bridge")

COORDINATE_ADAPTER_PATH = os.path.join(BRIDGE_DIR, "coordinate_adapter.py")
SCENE_MAP_ADAPTER_PATH = os.path.join(BRIDGE_DIR, "scene_map_adapter.py")
SMOKE_CLEAN_SCRIPT_PATH = os.path.join(CLEAN_PHASE_DIR, "scripts", "openwater_grid_waypoint_smoke_clean.py")

SUMMARY_MD_PATH = os.path.join(CLEAN_PHASE_DIR, "reports", "openwater_waypoint_smoke_clean_summary.md")
TRACE_JSON_PATH = os.path.join(CLEAN_PHASE_DIR, "manifests", "openwater_waypoint_trace_clean.json")

AUDIT_JSON_PATH = os.path.join(CLEAN_PHASE_DIR, "manifests", "phase2c_clean_audit.json")
AUDIT_SUMMARY_PATH = os.path.join(CLEAN_PHASE_DIR, "reports", "phase2c_clean_audit_summary.md")


def audit_file_content(filepath: str, forbidden_patterns: List[str]) -> List[str]:
    """Check a file for forbidden string patterns."""
    violations = []
    if not os.path.exists(filepath):
        violations.append(f"File not found: {filepath}")
        return violations
        
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            for pat in forbidden_patterns:
                if pat in line:
                    violations.append(f"Line {idx+1}: contains forbidden pattern '{pat}'")
    return violations


def run_audit() -> None:
    print("=== Phase 2C-clean: Starting Audit Verification ===")
    
    audit_results = {
        "status": "PASSED",
        "coordinate_adapter_check": {"passed": True, "violations": []},
        "scene_map_adapter_check": {"passed": True, "violations": []},
        "smoke_clean_script_check": {"passed": True, "violations": []},
        "outputs_verification": {
            "summary_exists": False,
            "trace_json_exists": False,
            "total_waypoints": 0,
            "arrived_count": 0,
            "success_rate": 0.0,
            "passed": True,
            "errors": []
        }
    }

    # 1. Audit coordinate_adapter.py
    print(f"Auditing: {COORDINATE_ADAPTER_PATH}")
    adapter_violations = audit_file_content(COORDINATE_ADAPTER_PATH, ["import baseline_GP.core_map", "from baseline_GP.core_map", "import core_map"])
    if adapter_violations:
        audit_results["coordinate_adapter_check"]["passed"] = False
        audit_results["coordinate_adapter_check"]["violations"] = adapter_violations
        audit_results["status"] = "FAILED"
        print(f"  FAILED: Found core_map imports in {COORDINATE_ADAPTER_PATH}")
    else:
        print("  PASSED: No core_map imports found.")

    # 2. Audit scene_map_adapter.py
    print(f"Auditing: {SCENE_MAP_ADAPTER_PATH}")
    scene_violations = audit_file_content(SCENE_MAP_ADAPTER_PATH, ["import baseline_GP.core_map", "from baseline_GP.core_map", "import core_map"])
    if scene_violations:
        audit_results["scene_map_adapter_check"]["passed"] = False
        audit_results["scene_map_adapter_check"]["violations"] = scene_violations
        audit_results["status"] = "FAILED"
        print(f"  FAILED: Found core_map imports in {SCENE_MAP_ADAPTER_PATH}")
    else:
        print("  PASSED: No core_map imports found.")

    # 3. Audit openwater_grid_waypoint_smoke_clean.py
    print(f"Auditing: {SMOKE_CLEAN_SCRIPT_PATH}")
    smoke_violations = audit_file_content(
        SMOKE_CLEAN_SCRIPT_PATH, 
        ["ModuleType", "sys.modules", "exec(compile", "replace("]
    )
    # Ignore self-contained docstrings or comments about auditing itself if any,
    # but the above pattern checks are strict.
    if smoke_violations:
        # Filter out comments mentioning "replace" if they are just comments, but to be safe keep strict
        audit_results["smoke_clean_script_check"]["passed"] = False
        audit_results["smoke_clean_script_check"]["violations"] = smoke_violations
        audit_results["status"] = "FAILED"
        print(f"  FAILED: Found compatibility hacks in {SMOKE_CLEAN_SCRIPT_PATH}")
    else:
        print("  PASSED: No compatibility hacks found.")

    # 4. Verify output files
    print("Verifying generated outputs...")
    
    # Check Summary MD
    if os.path.exists(SUMMARY_MD_PATH):
        audit_results["outputs_verification"]["summary_exists"] = True
        print(f"  PASSED: Summary report found at {SUMMARY_MD_PATH}")
    else:
        audit_results["outputs_verification"]["passed"] = False
        audit_results["outputs_verification"]["errors"].append("Summary MD file missing")
        audit_results["status"] = "FAILED"
        print("  FAILED: Summary report MD file missing!")

    # Check Trace JSON
    if os.path.exists(TRACE_JSON_PATH):
        audit_results["outputs_verification"]["trace_json_exists"] = True
        print(f"  PASSED: Telemetry JSON found at {TRACE_JSON_PATH}")
        try:
            # Parse trace JSON to verify arrived count
            with open(TRACE_JSON_PATH, "r", encoding="utf-8") as f:
                trace_data = json.load(f)
                
            # Filter trace for the end-of-waypoint events or analyze waypoint_summaries.
            # In our trace JSON, every tick is logged. The last tick of a waypoint has 'arrived' or 'timeout' as True.
            # Or we can read the summaries. But let's look at the trace records.
            # Let's count how many distinct waypoint indexes reached arrived=True.
            arrived_wps = set()
            for entry in trace_data:
                if entry.get("arrived", False):
                    arrived_wps.add(entry.get("waypoint_index"))
            
            total_wps = 4 # We know we have 4 waypoints: index 0, 1, 2, 3
            arrived_count = len(arrived_wps)
            success_rate = (arrived_count / total_wps) * 100.0
            
            audit_results["outputs_verification"]["total_waypoints"] = total_wps
            audit_results["outputs_verification"]["arrived_count"] = arrived_count
            audit_results["outputs_verification"]["success_rate"] = success_rate
            
            print(f"  Waypoint Arrived Count: {arrived_count} / {total_wps} ({success_rate:.1f}%)")
            
            if arrived_count < total_wps:
                audit_results["outputs_verification"]["passed"] = False
                audit_results["outputs_verification"]["errors"].append(f"Only {arrived_count}/4 waypoints arrived")
                audit_results["status"] = "FAILED"
        except Exception as e:
            audit_results["outputs_verification"]["passed"] = False
            audit_results["outputs_verification"]["errors"].append(f"Failed to parse trace JSON: {e}")
            audit_results["status"] = "FAILED"
            print(f"  FAILED: Error parsing trace JSON: {e}")
    else:
        audit_results["outputs_verification"]["passed"] = False
        audit_results["outputs_verification"]["errors"].append("Trace JSON file missing")
        audit_results["status"] = "FAILED"
        print("  FAILED: Telemetry JSON file missing!")

    # 5. Save Audit JSON
    os.makedirs(os.path.dirname(AUDIT_JSON_PATH), exist_ok=True)
    with open(AUDIT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)
    print(f"Audit results JSON saved to: {AUDIT_JSON_PATH}")

    # 6. Save Audit Markdown Report
    os.makedirs(os.path.dirname(AUDIT_SUMMARY_PATH), exist_ok=True)
    
    # Format violations list
    def fmt_v(v_list):
        if not v_list:
            return "* `NONE` (Clean)"
        return "\n".join([f"- {v}" for v in v_list])

    errors_str = ""
    if audit_results["outputs_verification"]["errors"]:
        errors_str = "\n### Errors Encountered\n" + "\n".join([f"- **Error**: {err}" for err in audit_results["outputs_verification"]["errors"]])

    audit_md = f"""# HoloOcean Clean Audit Report - Phase 2C-clean

## Audit Status
- **Overall Status**: `{"PASSED" if audit_results["status"] == "PASSED" else "FAILED"}`

## 1. Decoupling Check (Forbidden Import core_map)
- **`coordinate_adapter.py` Status**: `{"PASSED" if audit_results["coordinate_adapter_check"]["passed"] else "FAILED"}`
  - Violations:
{fmt_v(audit_results["coordinate_adapter_check"]["violations"])}
- **`scene_map_adapter.py` Status**: `{"PASSED" if audit_results["scene_map_adapter_check"]["passed"] else "FAILED"}`
  - Violations:
{fmt_v(audit_results["scene_map_adapter_check"]["violations"])}

## 2. Compatibility Check (Clean Import Verification)
- **`openwater_grid_waypoint_smoke_clean.py` Status**: `{"PASSED" if audit_results["smoke_clean_script_check"]["passed"] else "FAILED"}`
  - Violations:
{fmt_v(audit_results["smoke_clean_script_check"]["violations"])}

## 3. Telemetry Outputs Verification
- **Build Summary MD**: `{"EXIST" if audit_results["outputs_verification"]["summary_exists"] else "MISSING"}`
- **Compressed Telemetry JSON**: `{"EXIST" if audit_results["outputs_verification"]["trace_json_exists"] else "MISSING"}`
- **Waypoint Arrived Status**: `{audit_results["outputs_verification"]["arrived_count"]} / {audit_results["outputs_verification"]["total_waypoints"]} Arrived` ({audit_results["outputs_verification"]["success_rate"]:.1f}% Success)
{errors_str}

---
*Report statically generated by phase2c_clean_audit.py.*
"""
    with open(AUDIT_SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(audit_md)
    print(f"Audit summary report saved to: {AUDIT_SUMMARY_PATH}")
    print("=== Audit Verification Completed ===")


if __name__ == "__main__":
    run_audit()
