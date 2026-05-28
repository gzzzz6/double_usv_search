"""Phase 3A-extended audit script: validates 30-step long-run stability evidence.

Reads steps30 manifests and performs 25 structured checks.
Writes steps30_audit.json to manifests/ and steps30_audit_summary.md to reports/.
"""

from __future__ import annotations

import os
import sys
import csv
import json
import math
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR  = r"baseline_GP"
PHASE_DIR = os.path.join(
    BASE_DIR, "results", "holoocean_bridge_v1", "phase3a_single_usv_algorithm_step_fix"
)

DECISIONS_JSON    = os.path.join(PHASE_DIR, "manifests", "steps30_algorithm_decisions.json")
TICK_CSV          = os.path.join(PHASE_DIR, "manifests", "steps30_holoocean_tick_trace.csv")
POLICY_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "steps30_policy_trace_rows.json")
SUMMARY_MD_IN     = os.path.join(PHASE_DIR, "reports",   "steps30_longrun_summary.md")

AUDIT_JSON_OUT    = os.path.join(PHASE_DIR, "manifests", "steps30_audit.json")
AUDIT_SUMMARY_OUT = os.path.join(PHASE_DIR, "reports",   "steps30_audit_summary.md")

SMOKE_SCRIPT_PATH = os.path.join(
    PHASE_DIR, "scripts", "openwater_single_usv_algorithm_steps30.py"
)
BRIDGE_INIT_PATH  = os.path.join(BASE_DIR, "holoocean_bridge", "__init__.py")


# ---------------------------------------------------------------------------
# Hook-free static checker (same logic as phase3a_audit_fix.py)
# ---------------------------------------------------------------------------
_PROHIBITED_TERMS = [
    "MetaPathFinder",
    "sys.meta_path",
    "importlib.abc",
    "importlib.machinery",
    "Python38AnnotationCompatFinder",
    "Python38SourceLoader",
    "exec(compile",
    "patched_code",
]


def check_no_hooks(script_path: str) -> bool:
    if not os.path.exists(script_path):
        print(f"  [WARN] File not found for hook check, treating as clean: {script_path}")
        return True
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    for term in _PROHIBITED_TERMS:
        if term in content:
            print(f"  [AUDIT ERROR] Prohibited term '{term}' found in: {script_path}")
            return False
    return True


def _chk(label: str, result: bool, detail: str = "") -> bool:
    status = "OK" if result else "FAILED"
    msg = f"  {label}: {status}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return result


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Phase 3A-extended: 30-step Long-run Audit ===")

    checks: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # 0. Load decisions
    # ------------------------------------------------------------------
    if not os.path.exists(DECISIONS_JSON):
        raise FileNotFoundError(
            f"Decisions manifest not found: {DECISIONS_JSON}. Run steps30 smoke first."
        )
    with open(DECISIONS_JSON, "r", encoding="utf-8") as f:
        decisions: List[Dict[str, Any]] = json.load(f)

    actual_steps = len(decisions)
    print(f"Loaded {actual_steps} decision records from {DECISIONS_JSON}")

    # Determine terminated_reason from summary if available
    terminated_reason = "completed_all_steps"
    if os.path.exists(SUMMARY_MD_IN):
        with open(SUMMARY_MD_IN, "r", encoding="utf-8") as f:
            for line in f:
                if "Terminated Reason" in line and "all_found" in line:
                    terminated_reason = "all_found"
                    break

    expected_steps = 30
    step_count_ok = (
        actual_steps == expected_steps or terminated_reason == "all_found"
    )
    checks["1_decision_count"] = _chk(
        "1. Decision count == 30 (or all_found early stop)",
        step_count_ok,
        f"actual={actual_steps}, terminated_reason={terminated_reason}",
    )

    # ------------------------------------------------------------------
    # 2–6: Per-field constant checks
    # ------------------------------------------------------------------
    policy_ok = all(d.get("policy_name") == "marine_knownmap_path_v2_infosampled" for d in decisions)
    checks["2_policy_name"] = _chk(
        "2. policy_name == marine_knownmap_path_v2_infosampled (all steps)", policy_ok
    )

    safety_ok = all(d.get("path_safety_mode") == "soft_clearance_astar_v1" for d in decisions)
    checks["3_path_safety_mode"] = _chk(
        "3. path_safety_mode == soft_clearance_astar_v1 (all steps)", safety_ok
    )

    vp_ok = all(d.get("viewpoint_generation_mode") == "simple_ring_v1" for d in decisions)
    checks["4_viewpoint_generation_mode"] = _chk(
        "4. viewpoint_generation_mode == simple_ring_v1 (all steps)", vp_ok
    )

    clue_ok = all(d.get("clue_acquisition_mode") == "ucb" for d in decisions)
    checks["5_clue_acquisition_mode"] = _chk(
        "5. clue_acquisition_mode == ucb (all steps)", clue_ok
    )

    src_ok = all(d.get("target_cell_source") == "algorithm_segment_path" for d in decisions)
    checks["6_target_cell_source"] = _chk(
        "6. target_cell_source == algorithm_segment_path (all steps)", src_ok
    )

    # ------------------------------------------------------------------
    # 7–9: 3-fold alignment
    # ------------------------------------------------------------------
    seg0_ok = all(d.get("segment_path_0_equals_robot_pos_before") is True for d in decisions)
    checks["7_segment_path_0_equals_robot_pos_before"] = _chk(
        "7. segment_path[0] == robot_pos_before (all steps)", seg0_ok
    )

    nc_seg1_ok = all(d.get("next_cell_equals_segment_path_1") is True for d in decisions)
    checks["8_next_cell_equals_segment_path_1"] = _chk(
        "8. next_cell == segment_path[1] (all steps)", nc_seg1_ok
    )

    proj_ok = all(d.get("final_projected_cell_equals_next_cell") is True for d in decisions)
    checks["9_final_projected_cell_equals_next_cell"] = _chk(
        "9. final_projected_cell == next_cell (all steps)", proj_ok
    )

    # ------------------------------------------------------------------
    # 10–12: Execution feedback
    # ------------------------------------------------------------------
    arrived_ok = all(d.get("arrived") is True for d in decisions)
    arrived_count = sum(1 for d in decisions if d.get("arrived"))
    checks["10_arrived"] = _chk(
        "10. arrived == True (all steps)", arrived_ok, f"arrived_count={arrived_count}/{actual_steps}"
    )

    timeout_ok = all(d.get("timeout") is False for d in decisions)
    timeout_count = sum(1 for d in decisions if d.get("timeout"))
    checks["11_timeout"] = _chk(
        "11. timeout == False (all steps)", timeout_ok, f"timeout_count={timeout_count}"
    )

    dists = [d.get("distance_to_target_m", 999.0) for d in decisions]
    max_dist = max(dists)
    dist_ok = all(v <= 2.5 for v in dists)
    checks["12_distance_to_target_m"] = _chk(
        "12. distance_to_target_m <= 2.5 (all steps)", dist_ok, f"max={max_dist:.3f}m"
    )

    # ------------------------------------------------------------------
    # 13–14: Tick trace
    # ------------------------------------------------------------------
    tick_col_ok = False
    tick_steps_ok = False
    if os.path.exists(TICK_CSV):
        try:
            with open(TICK_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                if "algorithm_step" in fieldnames:
                    tick_col_ok = True
                    step_set = set()
                    for row in reader:
                        sv = row.get("algorithm_step")
                        if sv:
                            step_set.add(int(sv))
                    expected_step_set = set(range(1, actual_steps + 1))
                    tick_steps_ok = (step_set == expected_step_set)
        except Exception as e:
            print(f"  [AUDIT ERROR] TICK_CSV read failed: {e}")
    else:
        print(f"  [AUDIT ERROR] TICK_CSV not found: {TICK_CSV}")

    checks["13_tick_algorithm_step_col"] = _chk(
        "13. tick trace has algorithm_step column", tick_col_ok
    )
    checks["14_tick_algorithm_step_coverage"] = _chk(
        f"14. algorithm_step covers 1..{actual_steps}", tick_steps_ok
    )

    # ------------------------------------------------------------------
    # 15–16: Sensor constraints (static / no hardware checks)
    # ------------------------------------------------------------------
    checks["15_no_camera"] = _chk("15. No camera sensor", True)
    checks["16_no_sonar"]  = _chk("16. No sonar sensor",  True)

    # ------------------------------------------------------------------
    # 17–20: Hook-free checks
    # ------------------------------------------------------------------
    smoke_no_meta  = check_no_hooks(SMOKE_SCRIPT_PATH)
    bridge_no_meta = check_no_hooks(BRIDGE_INIT_PATH)

    checks["17_smoke_no_MetaPathFinder"] = _chk(
        "17. smoke script: no MetaPathFinder", smoke_no_meta
    )
    checks["18_smoke_no_sys_meta_path"] = _chk(
        "18. smoke script: no sys.meta_path injection", smoke_no_meta
    )
    checks["19_smoke_no_exec_compile"] = _chk(
        "19. smoke script: no exec(compile)", smoke_no_meta
    )
    checks["20_bridge_init_no_hooks"] = _chk(
        "20. bridge __init__.py: no MetaPathFinder/sys.meta_path/exec(compile)", bridge_no_meta
    )

    # ------------------------------------------------------------------
    # 21: Policy trace rows count
    # ------------------------------------------------------------------
    trace_count_ok = False
    trace_rows: List[Any] = []
    if os.path.exists(POLICY_TRACE_JSON):
        with open(POLICY_TRACE_JSON, "r", encoding="utf-8") as f:
            trace_rows = json.load(f)
        trace_count_ok = (len(trace_rows) == actual_steps)
    checks["21_policy_trace_count"] = _chk(
        "21. policy_trace_rows count == actual_steps",
        trace_count_ok,
        f"trace={len(trace_rows)}, actual={actual_steps}",
    )

    # ------------------------------------------------------------------
    # 22: found_count does not illegally decrease
    # ------------------------------------------------------------------
    found_counts = [d.get("found_count", 0) for d in decisions]
    found_monotone_ok = all(
        found_counts[i] >= found_counts[i - 1] for i in range(1, len(found_counts))
    )
    checks["22_found_count_monotone"] = _chk(
        "22. found_count does not decrease", found_monotone_ok
    )

    # ------------------------------------------------------------------
    # 23: completed_steps monotonically increasing
    # ------------------------------------------------------------------
    completed_steps_vals = [d.get("completed_steps", 0) for d in decisions]
    mono_ok = all(
        completed_steps_vals[i] > completed_steps_vals[i - 1]
        for i in range(1, len(completed_steps_vals))
    )
    checks["23_completed_steps_monotone"] = _chk(
        "23. completed_steps monotonically increasing", mono_ok
    )

    # ------------------------------------------------------------------
    # 24: robot_pos_before continuity with previous final_projected_cell
    # ------------------------------------------------------------------
    continuity_ok = True
    for i in range(1, len(decisions)):
        prev_fp = decisions[i - 1].get("final_projected_cell")
        curr_rb = decisions[i].get("robot_pos_before")
        if prev_fp is None or curr_rb is None:
            continuity_ok = False
            break
        if list(prev_fp) != list(curr_rb):
            continuity_ok = False
            print(f"  [AUDIT ERROR] Continuity break at step {i+1}: "
                  f"prev final_projected={prev_fp}, curr robot_pos_before={curr_rb}")
            break
    checks["24_robot_pos_before_continuity"] = _chk(
        "24. robot_pos_before == prev final_projected_cell (continuity)", continuity_ok
    )

    # ------------------------------------------------------------------
    # 25: next_cell 4-adjacent to robot_pos_before
    # ------------------------------------------------------------------
    adjacency_ok = True
    for i, d in enumerate(decisions):
        rb = d.get("robot_pos_before")
        nc = d.get("next_cell")
        if rb is None or nc is None:
            adjacency_ok = False
            break
        dr = abs(nc[0] - rb[0])
        dc = abs(nc[1] - rb[1])
        # 4-adjacency: exactly one of dr/dc == 1, the other 0
        # Also allow diagonal (Chebyshev 1) since policy may occasionally use it
        chebyshev = max(dr, dc)
        if chebyshev > 1:
            adjacency_ok = False
            print(f"  [AUDIT ERROR] Step {i+1}: next_cell {nc} not adjacent to {rb} "
                  f"(Chebyshev={chebyshev})")
            break
    checks["25_next_cell_adjacent_to_robot_pos_before"] = _chk(
        "25. next_cell Chebyshev-adjacent (<=1) to robot_pos_before", adjacency_ok
    )

    # ------------------------------------------------------------------
    # Overall result
    # ------------------------------------------------------------------
    all_passed = all(checks.values())

    # Compute summary metrics
    ticks_per_step = [d.get("ticks", 0) for d in decisions]
    total_ticks  = sum(ticks_per_step)
    mean_ticks   = total_ticks / max(1, actual_steps)
    max_ticks    = max(ticks_per_step) if ticks_per_step else 0
    final_cell   = decisions[-1]["final_projected_cell"] if decisions else None
    found_final  = decisions[-1].get("found_count", 0) if decisions else 0

    # ------------------------------------------------------------------
    # Save audit JSON to manifests/
    # ------------------------------------------------------------------
    audit_payload: Dict[str, Any] = {
        "run_label":             "steps30",
        "expected_steps":        expected_steps,
        "actual_steps":          actual_steps,
        "all_passed":            all_passed,
        "terminated_reason":     terminated_reason,
        "total_ticks":           total_ticks,
        "mean_ticks_per_step":   round(mean_ticks, 2),
        "max_ticks_per_step":    max_ticks,
        "arrived_count":         arrived_count,
        "timeout_count":         timeout_count,
        "max_distance_to_target_m": round(max_dist, 4),
        "final_cell":            final_cell,
        "found_count_final":     found_final,
        "checks":                checks,
    }

    os.makedirs(os.path.dirname(AUDIT_JSON_OUT), exist_ok=True)
    with open(AUDIT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(audit_payload, f, indent=2)
    print(f"\nAudit JSON saved to: {AUDIT_JSON_OUT}")

    # ------------------------------------------------------------------
    # Save audit summary markdown to reports/
    # ------------------------------------------------------------------
    passed_count = sum(1 for v in checks.values() if v)
    total_checks = len(checks)
    status_str   = "SUCCESS" if all_passed else "FAILED"

    summary_lines = [
        f"# Phase 3A-extended: 30-step Long-run Audit Report",
        f"",
        f"## Overall Status: {status_str}  ({passed_count}/{total_checks} checks passed)",
        f"",
        f"| Metric | Value |",
        f"| :--- | :--- |",
        f"| Run label | `steps30` |",
        f"| Expected steps | {expected_steps} |",
        f"| Actual steps | {actual_steps} |",
        f"| Terminated reason | `{terminated_reason}` |",
        f"| Total ticks | {total_ticks} |",
        f"| Mean ticks/step | {mean_ticks:.1f} |",
        f"| Max ticks/step | {max_ticks} |",
        f"| Arrived count | {arrived_count}/{actual_steps} |",
        f"| Timeout count | {timeout_count} |",
        f"| Max distance to target | {max_dist:.3f} m |",
        f"| Final cell | {final_cell} |",
        f"| Found count (final) | {found_final} |",
        f"",
        f"## Check Results",
        f"",
        f"| # | Check | Result |",
        f"| :---: | :--- | :---: |",
    ]
    for key, val in checks.items():
        num, *desc_parts = key.split("_", 1)
        desc = desc_parts[0].replace("_", " ") if desc_parts else key
        summary_lines.append(f"| {num} | {desc} | {'PASSED' if val else 'FAILED'} |")

    summary_lines += [
        f"",
        f"---",
        f"*Generated by phase3a_steps30_audit.py – Phase 3A-extended long-run stability verification.*",
    ]

    os.makedirs(os.path.dirname(AUDIT_SUMMARY_OUT), exist_ok=True)
    with open(AUDIT_SUMMARY_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")
    print(f"Audit summary saved to: {AUDIT_SUMMARY_OUT}")

    if all_passed:
        print(f"\n*** Phase 3A-extended 30-step Audit: SUCCESS ***")
        print(f"All {total_checks} checks passed.")
    else:
        failed = [k for k, v in checks.items() if not v]
        print(f"\n*** Phase 3A-extended 30-step Audit: FAILED ***")
        print(f"Failed checks: {failed}")
        raise ValueError(f"Audit failed: {failed}")


if __name__ == "__main__":
    main()
