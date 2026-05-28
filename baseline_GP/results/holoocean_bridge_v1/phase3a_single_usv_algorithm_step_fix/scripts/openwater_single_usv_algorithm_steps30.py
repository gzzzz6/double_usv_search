"""E2E Closed-loop integration smoke test – Phase 3A-extended: 30-step long-run stability.

Runs single-USV search policy decisions in HoloOcean for up to 30 steps.
Standard imports only. Zero dynamic import hooks or runtime source patching.
"""

from __future__ import annotations

import os
import sys
import csv
import json
import time
from typing import List, Tuple, Dict, Any
import numpy as np

# Add root directory to sys.path to guarantee clean module loading
sys.path.append(os.path.abspath("."))

# Standard imports without dynamic hooks
from baseline_GP.holoocean_bridge.single_usv_policy_adapter import (
    load_openwater_policy_state,
    plan_next_policy_cell,
    finalize_policy_step_after_holoocean,
)
from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz
from baseline_GP.holoocean_bridge.scenario_builder import build_surface_vessel_scenario
from baseline_GP.holoocean_bridge.execution_backend import run_single_grid_cell_waypoint
from baseline_GP.core_intensity import remaining_intensity_mass, peak_intensity_ratio

# ---------------------------------------------------------------------------
# Paths configuration – all outputs use steps30_ prefix; never overwrite 8-step results
# ---------------------------------------------------------------------------
BASE_DIR = r"baseline_GP"
MAP_NPZ = os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_v1.npz")
PHASE_DIR = os.path.join(
    BASE_DIR, "results", "holoocean_bridge_v1", "phase3a_single_usv_algorithm_step_fix"
)

TICK_CSV       = os.path.join(PHASE_DIR, "manifests", "steps30_holoocean_tick_trace.csv")
DECISIONS_JSON = os.path.join(PHASE_DIR, "manifests", "steps30_algorithm_decisions.json")
DECISIONS_CSV  = os.path.join(PHASE_DIR, "manifests", "steps30_algorithm_decisions.csv")
POLICY_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "steps30_policy_trace_rows.json")
SUMMARY_MD     = os.path.join(PHASE_DIR, "reports",   "steps30_longrun_summary.md")
PREVIEW_PNG    = os.path.join(PHASE_DIR, "visuals",   "steps30_algorithm_trajectory_preview.png")

MAX_STEPS = 30


# ---------------------------------------------------------------------------
# Helper: guard against overwriting 8-step baseline results
# ---------------------------------------------------------------------------
_PROTECTED_FILES = {
    os.path.abspath(os.path.join(PHASE_DIR, "manifests", "phase3a_algorithm_decisions.json")),
    os.path.abspath(os.path.join(PHASE_DIR, "manifests", "phase3a_algorithm_decisions.csv")),
    os.path.abspath(os.path.join(PHASE_DIR, "manifests", "phase3a_holoocean_tick_trace.csv")),
    os.path.abspath(os.path.join(PHASE_DIR, "manifests", "phase3a_policy_trace_rows.json")),
    os.path.abspath(os.path.join(PHASE_DIR, "manifests", "phase3a_audit.json")),
    os.path.abspath(os.path.join(PHASE_DIR, "reports",   "phase3a_single_usv_algorithm_step_summary.md")),
    os.path.abspath(os.path.join(PHASE_DIR, "reports",   "phase3a_audit_summary.md")),
    os.path.abspath(os.path.join(PHASE_DIR, "visuals",   "phase3a_algorithm_trajectory_preview.png")),
}

for _out in [TICK_CSV, DECISIONS_JSON, DECISIONS_CSV, POLICY_TRACE_JSON, SUMMARY_MD, PREVIEW_PNG]:
    assert os.path.abspath(_out) not in _PROTECTED_FILES, (
        f"PROTECTION VIOLATION: output path {_out!r} collides with an 8-step baseline result file."
    )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def save_decisions_csv(path: str, decisions: List[Dict[str, Any]]) -> None:
    """Save algorithm decisions to a CSV file."""
    if not decisions:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = list(decisions[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(decisions)
    print(f"Decisions CSV saved to: {path}")


def save_ticks_csv(path: str, tick_trace: List[Dict[str, Any]]) -> None:
    """Save per-tick telemetry trace to a CSV file."""
    if not tick_trace:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = list(tick_trace[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(tick_trace)
    print(f"Tick telemetry CSV saved to: {path}")


def generate_trajectory_preview(
    nav_map_prior: np.ndarray,
    decisions: List[Dict[str, Any]],
    preview_path: str,
) -> None:
    """Generate visual preview of the 30-step algorithm trajectory."""
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(12, 12))
        plt.imshow(nav_map_prior, cmap="gray_r", origin="upper")

        start_r, start_c = decisions[0]["robot_pos_before"]
        grid_rows = [start_r] + [d["next_cell"][0] for d in decisions]
        grid_cols = [start_c] + [d["next_cell"][1] for d in decisions]

        target_rows = [d["next_cell"][0] for d in decisions]
        target_cols = [d["next_cell"][1] for d in decisions]

        plt.plot(target_cols, target_rows, color="green", linestyle="--",
                 linewidth=1.5, alpha=0.5, label="Planned waypoints")
        plt.scatter(target_cols, target_rows, color="green", marker="o",
                    s=60, edgecolors="darkgreen", zorder=5)
        plt.plot(grid_cols, grid_rows, color="blue", linewidth=2.0,
                 alpha=0.8, label="USV trajectory")
        plt.scatter(grid_cols, grid_rows, color="blue", marker="x",
                    s=50, zorder=6)
        plt.scatter(start_c, start_r, color="red", marker="*",
                    s=250, edgecolors="black", zorder=7, label="Start (1,1)")

        # Annotate every 5th step to keep the plot readable
        for step_idx, d in enumerate(decisions):
            if (step_idx + 1) % 5 == 0 or step_idx == 0 or step_idx == len(decisions) - 1:
                r, c = d["next_cell"]
                plt.annotate(
                    f"S{step_idx+1}\n({r},{c})",
                    xy=(c, r),
                    xytext=(4, 4),
                    textcoords="offset points",
                    fontsize=7,
                    color="darkblue",
                    weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="lightyellow", alpha=0.75),
                )

        plt.title(
            f"Phase 3A-extended: 30-step Long-run Single-USV Stability Smoke\n"
            f"(openwater_open_v1, 81x81, cell=5m, steps={len(decisions)})",
            fontsize=11,
            pad=10,
        )
        plt.xlabel("Column", fontsize=10)
        plt.ylabel("Row", fontsize=10)
        plt.xlim(-0.5, 80.5)
        plt.ylim(80.5, -0.5)
        plt.grid(True, which="both", color="lightgray", linestyle=":", alpha=0.4)
        plt.legend(loc="upper right", framealpha=0.95)

        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        plt.savefig(preview_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Trajectory preview saved to: {preview_path}")
    except Exception as e:
        print(f"[WARN] Skipping visual preview: {e}")


def write_summary_report(
    summary_path: str,
    spec: dict,
    decisions: List[Dict[str, Any]],
    elapsed_time: float,
    total_ticks: int,
    terminated_reason: str,
) -> None:
    """Write Markdown long-run summary report."""
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    n = len(decisions)
    mean_ticks = total_ticks / max(1, n)
    max_ticks_step = max((d["ticks"] for d in decisions), default=0)
    arrived_count = sum(1 for d in decisions if d.get("arrived"))
    timeout_count = sum(1 for d in decisions if d.get("timeout"))
    found_final = decisions[-1].get("found_count", 0) if decisions else 0
    final_cell = decisions[-1]["final_projected_cell"] if decisions else None

    header = f"""# Phase 3A-extended: 30-step Long-run Stability Smoke Report

## Run Configuration
- **Label**: `steps30`
- **HoloOcean World**: `{spec.get("world", "OpenWater")}`
- **Package**: `{spec.get("package_name", "Ocean")}`
- **Agent**: `SurfaceVessel` (`sv`) / Control Scheme 1
- **Sensors**: `GPSSensor`, `LocationSensor`
- **Policy**: `marine_knownmap_path_v2_infosampled`
- **Path Safety Mode**: `soft_clearance_astar_v1`
- **Viewpoint Mode**: `simple_ring_v1`
- **Clue Acquisition**: `ucb` (temporary for Phase 3A long-run smoke)
- **Arrival Radius**: 2.5 m  |  **Max Ticks / Cell**: 800

## Execution Summary
- **Actual Steps**: `{n}` / {MAX_STEPS}
- **Terminated Reason**: `{terminated_reason}`
- **Total Ticks**: `{total_ticks}`
- **Wall Time**: `{elapsed_time:.2f} s`
- **Mean Ticks/Step**: `{mean_ticks:.1f}`
- **Max Ticks/Step**: `{max_ticks_step}`
- **Arrived Count**: `{arrived_count}` / {n}
- **Timeout Count**: `{timeout_count}`
- **Found (final)**: `{found_final}`
- **Final Cell**: `{final_cell}`

## Step-by-Step Table
| Step | Before | Target | World (X,Y) | Proj | Ticks | Arr | Dist(m) | Found | Replan |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    rows = []
    for i, d in enumerate(decisions):
        pb = d["robot_pos_before"]
        nc = d["next_cell"]
        fp = d["final_projected_cell"]
        tw = d["target_world"]
        rows.append(
            f"| {i+1} | ({pb[0]},{pb[1]}) | ({nc[0]},{nc[1]}) | "
            f"({tw[0]:.1f},{tw[1]:.1f}) | ({fp[0]},{fp[1]}) | "
            f"{d['ticks']} | {'Y' if d['arrived'] else 'N'} | "
            f"{d['distance_to_target_m']:.2f} | {d.get('found_count',0)} | "
            f"{'Y' if d.get('replanned') else 'N'} |"
        )

    footer = f"""
## Verification
- **Three-fold alignment (all steps)**: `{'PASSED' if all(d['final_projected_cell_equals_next_cell'] for d in decisions) else 'FAILED'}`
- **All arrived**: `{'PASSED' if arrived_count == n else 'FAILED'}`
- **Zero timeout**: `{'PASSED' if timeout_count == 0 else 'FAILED'}`
- **Clue note**: `clue_acquisition_mode = ucb temporary for Phase 3A long-run smoke`
- **Import hooks**: NONE (standard Python imports only)
"""
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(rows) + footer)
    print(f"Summary report written to: {summary_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Phase 3A-extended: 30-step long-run single-USV stability smoke ===")

    # 1. Load policy state
    print(f"Loading map and policy state from: {MAP_NPZ}")
    state, adapter_config, nav_map_prior = load_openwater_policy_state(
        map_spec_npz_path=MAP_NPZ,
        episode_seed=0,
        policy_name="marine_knownmap_path_v2_infosampled",
        n_targets=3,
        target_motion_mode="static",
    )

    spec = load_scene_map_npz(MAP_NPZ)[1]

    robot_pos_init = state["robot_pos"]
    assert robot_pos_init == (1, 1), (
        f"RIGID INITIAL CONSTRAINT VIOLATION: position is {robot_pos_init}, must be (1, 1)"
    )
    print(f"  Rigid start verified: cell={robot_pos_init} -> OK")

    # 2. Build scenario
    start_world = [-195.0, 195.0, 0.0]
    print(f"Building SurfaceVessel scenario: start_world={start_world}")
    scenario_cfg = build_surface_vessel_scenario(
        agent_name="sv",
        world=spec["world"],
        package_name=spec["package_name"],
        start_world=start_world,
        control_scheme=1,
    )

    import holoocean

    all_decisions: List[Dict[str, Any]] = []
    all_tick_trace: List[Dict[str, Any]] = []
    global_tick_offset = 0
    commit_remaining = 0
    terminated_reason = "completed_all_steps"

    print("Launching simulator...")
    start_time = time.time()

    with holoocean.make(scenario_cfg=scenario_cfg) as env:
        for step in range(1, MAX_STEPS + 1):

            # Early stop: all targets found
            if np.all(state["found_mask"]):
                terminated_reason = "all_found"
                print(f"  [EARLY STOP] All targets found at step {step}. Stopping.")
                break

            robot_pos_before = state["robot_pos"]

            # Step A: plan next cell
            next_cell, segment_path, commit_remaining, plan_details = plan_next_policy_cell(
                state=state,
                step=step,
                commit_remaining=commit_remaining,
                episode_seed=0,
                policy_name="marine_knownmap_path_v2_infosampled",
            )

            target_pos_3d = grid_to_world(next_cell, config=adapter_config)
            target_x, target_y = float(target_pos_3d[0]), float(target_pos_3d[1])

            print(f"\n--- STEP {step} ---")
            print(f"  Before: {robot_pos_before}  Target: {next_cell}  "
                  f"World: [{target_x:.2f}, {target_y:.2f}]")

            # Step B: HoloOcean execution
            step_ticks, step_summary = run_single_grid_cell_waypoint(
                env=env,
                agent_name="sv",
                target_cell=next_cell,
                adapter_config=adapter_config,
                nav_map_prior=nav_map_prior,
                arrival_radius_m=2.5,
                max_ticks=800,
                tick_offset=global_tick_offset,
            )

            global_tick_offset += len(step_ticks)
            for t in step_ticks:
                t["algorithm_step"] = step
            all_tick_trace.extend(step_ticks)

            # Step C: 3-fold audit
            final_projected_cell = tuple(step_summary["final_projected_cell"])
            next_cell_is_segment_1   = (next_cell == segment_path[1])
            segment_0_is_robot_before = (segment_path[0] == robot_pos_before)
            final_projected_matches  = (final_projected_cell == next_cell)

            print(f"  Ticks: {step_summary['ticks']}  Arrived: {step_summary['arrived']}"
                  f"  Projected: {final_projected_cell}")

            # Fail-fast on any violation
            if not step_summary["arrived"]:
                raise ValueError(
                    f"CRITICAL: Step {step} did not arrive (timeout={step_summary['timeout']})."
                )
            if not next_cell_is_segment_1:
                raise ValueError(
                    f"CRITICAL: Step {step} next_cell {next_cell} != segment_path[1] {segment_path[1]}."
                )
            if not segment_0_is_robot_before:
                raise ValueError(
                    f"CRITICAL: Step {step} segment_path[0] {segment_path[0]} != robot_pos_before {robot_pos_before}."
                )
            if not final_projected_matches:
                raise ValueError(
                    f"CRITICAL: Step {step} final_projected_cell {final_projected_cell} != next_cell {next_cell}."
                )

            # Step D: finalize state
            state = finalize_policy_step_after_holoocean(
                state=state,
                step=step,
                robot_pos_before=robot_pos_before,
                next_cell=next_cell,
                final_projected_cell=final_projected_cell,
                gp_fit_every=5,
            )

            # Collect extended decision record fields from state
            replanned         = bool(state.get("_audit_replanned", False))
            replan_reason     = state.get("_audit_replan_reason") or "none"
            committed_vp      = state.get("committed_viewpoint")
            committed_anchor  = state.get("committed_anchor")
            anchor_source     = state.get("last_anchor_source") or "none"
            found_count       = int(state["found_mask"].sum())
            completed_steps   = int(state.get("completed_steps", step))
            path_length       = int(state.get("path_length", 0))
            rem_intensity     = float(remaining_intensity_mass(state["intensity_map"]))
            si_map            = state.get("search_info_map")
            if si_map is not None:
                si_peak = float(np.max(si_map))
                si_mean = float(np.mean(si_map))
            else:
                si_peak, si_mean = 0.0, 0.0

            decision_record: Dict[str, Any] = {
                # Core policy telemetry
                "policy_name":                       "marine_knownmap_path_v2_infosampled",
                "viewpoint_generation_mode":         "simple_ring_v1",
                "path_safety_mode":                  "soft_clearance_astar_v1",
                "clue_acquisition_mode":             "ucb",
                "clue_mode_note":                    "clue_acquisition_mode = ucb temporary for Phase 3A long-run smoke",
                # Position / path
                "robot_pos_before":                  [int(robot_pos_before[0]), int(robot_pos_before[1])],
                "segment_path":                      [[int(pt[0]), int(pt[1])] for pt in segment_path],
                "next_cell":                         [int(next_cell[0]), int(next_cell[1])],
                "target_cell_source":                "algorithm_segment_path",
                # 3-fold audit flags
                "segment_path_0_equals_robot_pos_before": bool(segment_0_is_robot_before),
                "next_cell_equals_segment_path_1":        bool(next_cell_is_segment_1),
                "final_projected_cell_equals_next_cell":  bool(final_projected_matches),
                # World coordinates
                "target_world":                      [target_x, target_y],
                "final_world":                       step_summary["final_world"],
                # Execution feedback
                "ticks":                             step_summary["ticks"],
                "arrived":                           bool(step_summary["arrived"]),
                "timeout":                           bool(step_summary["timeout"]),
                "distance_to_target_m":              float(step_ticks[-1]["distance_to_target_m"]),
                "final_projected_cell":              [int(final_projected_cell[0]), int(final_projected_cell[1])],
                # Extended planning fields
                "replanned":                         replanned,
                "replan_reason":                     replan_reason,
                "committed_viewpoint":               (
                    [int(committed_vp[0]), int(committed_vp[1])]
                    if committed_vp is not None else None
                ),
                "committed_anchor":                  (
                    [int(committed_anchor[0]), int(committed_anchor[1])]
                    if committed_anchor is not None else None
                ),
                "anchor_source":                     anchor_source,
                "found_count":                       found_count,
                "completed_steps":                   completed_steps,
                "path_length":                       path_length,
                "remaining_intensity_mass":          rem_intensity,
                "search_info_map_peak":              si_peak,
                "search_info_map_mean":              si_mean,
            }
            all_decisions.append(decision_record)

    elapsed_time = time.time() - start_time
    total_ticks  = len(all_tick_trace)
    actual_steps = len(all_decisions)

    print(f"\n==========================================")
    print(f"30-step smoke completed!")
    print(f"  Actual steps     : {actual_steps}")
    print(f"  Terminated reason: {terminated_reason}")
    print(f"  Total ticks      : {total_ticks}")
    print(f"  Wall time        : {elapsed_time:.2f}s")
    print(f"==========================================")

    # 4. Save manifests
    save_decisions_csv(DECISIONS_CSV, all_decisions)
    os.makedirs(os.path.dirname(DECISIONS_JSON), exist_ok=True)
    with open(DECISIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_decisions, f, indent=2)
    print(f"Decisions JSON saved to: {DECISIONS_JSON}")

    save_ticks_csv(TICK_CSV, all_tick_trace)

    os.makedirs(os.path.dirname(POLICY_TRACE_JSON), exist_ok=True)
    with open(POLICY_TRACE_JSON, "w", encoding="utf-8") as f:
        json.dump(state["trace_rows"], f, indent=2)
    print(f"Policy trace rows saved to: {POLICY_TRACE_JSON}")

    # 5. Summary report and trajectory preview
    write_summary_report(SUMMARY_MD, spec, all_decisions, elapsed_time, total_ticks, terminated_reason)
    generate_trajectory_preview(nav_map_prior, all_decisions, PREVIEW_PNG)
    print("Phase 3A-extended steps30 smoke complete!")


if __name__ == "__main__":
    main()
