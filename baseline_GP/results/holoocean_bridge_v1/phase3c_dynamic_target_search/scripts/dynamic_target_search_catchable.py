"""E2E Closed-loop integration test – Phase 3C-1: Single-USV Dynamic Target Search.

Runs single-USV search policy decisions in HoloOcean with a dynamic target agent proxy.
Standard imports only. Zero dynamic import hooks or runtime source patching.
"""

from __future__ import annotations

import os
import sys
import csv
import json
import time
import math
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
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz, scene_map_config_from_spec
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector
from baseline_GP.core_intensity import remaining_intensity_mass, peak_intensity_ratio
from baseline_GP.core_clue_field import sample_clue_field
from baseline_GP.core_intensity import init_intensity_map
from baseline_GP.marine_knownmap_runtime import (
    _update_clue_truth_map,
    _refresh_gp_state,
    _update_search_info_state,
    miss_update_intensity,
)

# ---------------------------------------------------------------------------
# Paths configuration
# ---------------------------------------------------------------------------
BASE_DIR = r"baseline_GP"
MAP_NPZ = os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_v1.npz")
PHASE_DIR = os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase3c_dynamic_target_search")

DECISIONS_JSON  = os.path.join(PHASE_DIR, "manifests", "dynamic_target_search_catchable_decisions.json")
DECISIONS_CSV   = os.path.join(PHASE_DIR, "manifests", "dynamic_target_search_catchable_decisions.csv")
TICK_CSV        = os.path.join(PHASE_DIR, "manifests", "dynamic_target_search_catchable_tick_trace.csv")
TARGET_JSON     = os.path.join(PHASE_DIR, "manifests", "dynamic_target_search_catchable_target_trace.json")
TARGET_CSV      = os.path.join(PHASE_DIR, "manifests", "dynamic_target_search_catchable_target_trace.csv")
FOUND_JSON      = os.path.join(PHASE_DIR, "manifests", "dynamic_target_search_catchable_found_events.json")
SUMMARY_MD      = os.path.join(PHASE_DIR, "reports",   "dynamic_target_search_catchable_summary.md")
PREVIEW_PNG     = os.path.join(PHASE_DIR, "visuals",   "dynamic_target_search_catchable_route_map.png")

MAX_STEPS = 100
TARGET_MOTION_TICKS_PER_STEP = 10
SV_ARRIVAL_RADIUS_M = 2.5
TARGET_ARRIVAL_RADIUS_M = 2.5
MAX_TICKS_PER_CELL = 800


def save_decisions_csv(path: str, decisions: List[Dict[str, Any]]) -> None:
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
    target_trace: List[Dict[str, Any]],
    found_events: dict,
    preview_path: str,
) -> None:
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(12, 12))
        plt.imshow(nav_map_prior, cmap="gray_r", origin="upper")

        # 1. Plot SV Trajectory
        if decisions:
            start_r, start_c = decisions[0]["robot_pos_before"]
            sv_rows = [start_r] + [d["next_cell"][0] for d in decisions]
            sv_cols = [start_c] + [d["next_cell"][1] for d in decisions]
            plt.plot(sv_cols, sv_rows, color="blue", linewidth=2.0, alpha=0.8, label="Search USV Trajectory (sv)")
            plt.scatter(sv_cols, sv_rows, color="blue", marker="x", s=40, zorder=6)
            plt.scatter(start_c, start_r, color="red", marker="*", s=220, edgecolors="black", zorder=7, label="sv Start (1,1)")

        # 2. Plot Target Trajectory
        if target_trace:
            t_start_r, t_start_c = target_trace[0]["target_cell_observed"] if "target_cell_observed" in target_trace[0] else (20, 20)
            t_rows = [t_start_r] + [t["target_cell_observed"][0] for t in target_trace if "target_cell_observed" in t]
            t_cols = [t_start_c] + [t["target_cell_observed"][1] for t in target_trace if "target_cell_observed" in t]
            plt.plot(t_cols, t_rows, color="orange", linewidth=1.5, alpha=0.8, label="Target Proxy Trajectory (target)")
            plt.scatter(t_cols, t_rows, color="orange", marker="o", s=30, zorder=5)
            plt.scatter(t_start_c, t_start_r, color="yellow", marker="d", s=180, edgecolors="black", zorder=7, label="target Start (20,20)")

        # 3. Mark Scheduled Waypoints
        schedule_cells = [(20, 20), (20, 25), (25, 25), (25, 30), (25, 30), (25, 30)]
        sc_rows = [c[0] for c in schedule_cells]
        sc_cols = [c[1] for c in schedule_cells]
        plt.scatter(sc_cols, sc_rows, color="red", marker="p", s=120, edgecolors="black", zorder=8, label="Scheduled target Waypoints")

        # 4. Found point
        if found_events.get("found"):
            found_r, found_c = found_events["sv_cell_at_found"]
            plt.scatter(found_c, found_r, color="magenta", marker="h", s=300, edgecolors="black", linewidths=2.0, zorder=9,
                        label=f"Target Found (Step {found_events['found_step']})")
            
            tf_r, tf_c = found_events["target_cell_at_found"]
            plt.scatter(tf_c, tf_r, color="cyan", marker="o", s=150, edgecolors="black", linewidths=1.5, zorder=9,
                        label="target Position at Found")

        # Annotate step indices on SV route
        for step_idx, d in enumerate(decisions):
            if (step_idx + 1) % 15 == 0 or step_idx == 0 or step_idx == len(decisions) - 1:
                r, c = d["next_cell"]
                plt.annotate(
                    f"S{step_idx+1}",
                    xy=(c, r),
                    xytext=(4, 4),
                    textcoords="offset points",
                    fontsize=8,
                    color="darkblue",
                    weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="lightcyan", alpha=0.75),
                )

        plt.title(
            f"Phase 3C-1 Dynamic Target Search: HoloOcean target agent + baseline_GP search\n"
            f"(openwater_open_v1, 81x81, cell=5m, steps={len(decisions)}, found={found_events.get('found')})",
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
        print(f"Route map preview saved to: {preview_path}")
    except Exception as e:
        print(f"[WARN] Skipping visual preview: {e}")


def write_summary_report(
    summary_path: str,
    spec: dict,
    decisions: List[Dict[str, Any]],
    elapsed_time: float,
    total_ticks: int,
    terminated_reason: str,
    found_events: dict,
) -> None:
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    n = len(decisions)
    mean_ticks = total_ticks / max(1, n)
    max_ticks_step = max((d["ticks"] for d in decisions), default=0)
    arrived_count = sum(1 for d in decisions if d.get("arrived"))
    timeout_count = sum(1 for d in decisions if d.get("timeout"))
    found_final = decisions[-1].get("found_count_after", 0) if decisions else 0

    header = f"""# Phase 3C-1: Single-USV Dynamic Target Search Closed Loop Report
 
## Simulation Environment
- **Run Label**: `dynamic_target_search_catchable`
- **Phase Note**: `Phase 3C-1-catchable dynamic target search positive-control run; target agent follows a catchable schedule near the search corridor; no HoloOcean sonar/camera.`
- **Label**: `dynamic_target_search_catchable`
- **HoloOcean World**: `{spec.get("world", "OpenWater")}`
- **Package**: `{spec.get("package_name", "Ocean")}`
- **Search USV**: `SurfaceVessel` (`sv`) / Start Cell `(1,1)`
- **Target Proxy**: `SurfaceVessel` (`target`) / Start Cell `(20,20)`
- **Coordination Mode**: `Sequential target-before-search step synchronization; simultaneous continuous pursuit is deferred.`
- **Policy Config**: `marine_knownmap_path_v2_infosampled`
- **Path Safety Mode**: `soft_clearance_astar_v1`
- **Viewpoint Mode**: `simple_ring_v1`
- **Clue Acquisition**: `ucb` (temporary for Phase 3C-1)
- **Arrival Radius**: `2.5 m`  |  **Max Ticks / Cell**: `800`

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
- **Found Events**: `{json.dumps(found_events)}`

## Step-by-Step Table
| Step | SV Pos Before | Target Cell Observed | SV Target grid | SV Target World (X,Y) | Proj | Ticks | Arr | Dist(m) | Found | Remaining Mass | Peak/Mean | Replan |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    rows = []
    for i, d in enumerate(decisions):
        pb = d["robot_pos_before"]
        tco = d["target_cell_current"]
        nc = d["next_cell"]
        fp = d["sv_final_projected_cell"]
        tw = d["next_cell_world"]
        rows.append(
            f"| {i+1} | ({pb[0]},{pb[1]}) | ({tco[0]},{tco[1]}) | ({nc[0]},{nc[1]}) | "
            f"({tw[0]:.1f},{tw[1]:.1f}) | ({fp[0]},{fp[1]}) | "
            f"{d['ticks']} | {'Y' if d['arrived'] else 'N'} | "
            f"{d['distance_to_next_cell_m']:.2f} | {d.get('found_count_after',0)} | "
            f"{d.get('remaining_intensity_mass',0.0):.4f} | "
            f"{d.get('search_info_map_peak',0.0):.4f}/{d.get('search_info_map_mean',0.0):.4f} | "
            f"{'Y' if d.get('replanned') else 'N'} |"
        )

    footer = f"""
## Verification
- **Three-fold alignment (all steps)**: `{'PASSED' if all(d['sv_final_projected_cell'] == d['next_cell'] for d in decisions) else 'FAILED'}`
- **All arrived**: `{'PASSED' if arrived_count == n else 'FAILED'}`
- **Zero timeout**: `{'PASSED' if timeout_count == 0 else 'FAILED'}`
- **Clue note**: `clue_acquisition_mode = ucb temporary for Phase 3C-1`
- **Import hooks**: NONE (standard Python imports only)
"""
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(rows) + footer)
    print(f"Summary report written to: {summary_path}")


def get_target_waypoint(step: int) -> Tuple[int, int]:
    """Pre-defined schedule for target waypoints to ensure auditability and repeatability."""
    if step <= 15:
        return (20, 20)
    elif step <= 30:
        return (20, 25)
    elif step <= 45:
        return (25, 25)
    else:
        return (25, 30)


def main() -> None:
    print("=== Phase 3C-1-catchable: Launching Single-USV Dynamic Target Search ===")

    # 1. Load policy state
    print(f"Loading map and policy state from: {MAP_NPZ}")
    state, adapter_config, nav_map_prior = load_openwater_policy_state(
        map_spec_npz_path=MAP_NPZ,
        episode_seed=0,
        policy_name="marine_knownmap_path_v2_infosampled",
        n_targets=1,
        target_motion_mode="static",
    )

    spec = load_scene_map_npz(MAP_NPZ)[1]

    robot_pos_init = state["robot_pos"]
    assert robot_pos_init == (1, 1), (
        f"RIGID INITIAL CONSTRAINT VIOLATION: position is {robot_pos_init}, must be (1, 1)"
    )
    print(f"  Rigid start verified: cell={robot_pos_init} -> OK")

    # Align Step 0 target_positions and GP state
    initial_target_cell = (20, 20)
    state["target_positions"] = np.array([[int(initial_target_cell[0]), int(initial_target_cell[1])]], dtype=int)
    state["found_mask"] = np.zeros(1, dtype=bool)
    state["find_times"] = [None]

    _update_clue_truth_map(state)
    state["gp_field"].reset()
    X_init, y_init = sample_clue_field(
        state["clue_field_fn"],
        state["robot_pos"],
        state["sensor_range_cells"],
        state["observation_rng"],
        n_samples=state["clue_samples_per_step"],
        noise_std=state["clue_noise_std"],
        resolution=state["resolution_m"],
        map_shape=state["true_map"].shape,
    )
    if len(X_init) > 0:
        state["gp_field"].add_observations(X_init, y_init, t=0.0)
    _refresh_gp_state(state, optimize_hyperparams=state["gp_optimize_hyperparams"])

    # Re-initialize intensity map
    state["intensity_map"] = init_intensity_map(state["nav_map_prior"], total_mass=1.0)
    state["intensity_map"] = miss_update_intensity(
        state["intensity_map"],
        state["robot_pos"],
        state["sensor_range_cells"],
        known_map=state["nav_map_prior"],
        preserve_total_mass=True,
        target_total_mass=1.0,
    )
    state["remaining_intensity_mass_curve"] = [remaining_intensity_mass(state["intensity_map"])]
    state["peak_intensity_ratio_curve"] = [
        peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
    ]
    _update_search_info_state(state, state["intensity_map"])

    print("Belief initialization sync completed for dynamic target at (20,20).")

    # 2. Coordinate scenario builder configuration
    start_pos_target = list(grid_to_world(initial_target_cell, config=adapter_config))
    start_pos_target[2] = 2.0  # Safe depth z coordinate

    scenario_cfg = {
        "name": "dynamic_target_search_catchable",
        "world": spec["world"],
        "package_name": spec["package_name"],
        "main_agent": "sv",
        "agents": [
            {
                "agent_name": "sv",
                "agent_type": "SurfaceVessel",
                "sensors": [
                    {"sensor_type": "GPSSensor", "socket": "COM"},
                    {"sensor_type": "LocationSensor", "socket": "COM"}
                ],
                "control_scheme": 1,
                "location": [-195.0, 195.0, 2.0],
                "rotation": [0.0, 0.0, 0.0]
            },
            {
                "agent_name": "target",
                "agent_type": "SurfaceVessel",
                "sensors": [
                    {"sensor_type": "GPSSensor", "socket": "COM"},
                    {"sensor_type": "LocationSensor", "socket": "COM"}
                ],
                "control_scheme": 1,
                "location": start_pos_target,
                "rotation": [0.0, 0.0, 0.0]
            }
        ]
    }

    import holoocean

    all_decisions: List[Dict[str, Any]] = []
    all_target_trace: List[Dict[str, Any]] = []
    all_tick_trace: List[Dict[str, Any]] = []
    global_tick_offset = 0
    commit_remaining = 0
    terminated_reason = "max_steps_reached"

    found_events = {
        "found": False,
        "found_step": None,
        "found_target_indices": [],
        "target_cell_at_found": None,
        "target_world_at_found": None,
        "sv_cell_at_found": None,
        "sv_world_at_found": None,
        "euclidean_distance_cells_at_found": None,
        "sensor_range_cells": int(state["sensor_range_cells"]),
        "detection_model": "baseline_GP.core_targets.detect_targets",
        "note": "target truth comes from HoloOcean target proxy agent; detection still uses baseline_GP native simulated detection model.",
        "run_label": "dynamic_target_search_catchable",
        "phase_note": "Phase 3C-1-catchable dynamic target search positive-control run; target agent follows a catchable schedule near the search corridor; no HoloOcean sonar/camera."
    }

    print("Launching simulator...")
    start_time = time.time()

    with holoocean.make(scenario_cfg=scenario_cfg) as env:
        for step in range(1, MAX_STEPS + 1):
            # Early stop check
            if np.all(state["found_mask"]):
                terminated_reason = "all_found"
                print(f"  [EARLY STOP] Dynamic target found at step {step-1}. Stopping.")
                break

            robot_pos_before = state["robot_pos"]

            # Step 1: Pre-calculate current target scheduled waypoint
            target_wp_cell = get_target_waypoint(step)
            target_wp_world_3d = grid_to_world(target_wp_cell, config=adapter_config)
            target_wp_x, target_wp_y = float(target_wp_world_3d[0]), float(target_wp_world_3d[1])

            # Step 2: Push target agent forward by TARGET_MOTION_TICKS_PER_STEP ticks before planning
            last_target_x, last_target_y, last_target_z = 0.0, 0.0, 0.0
            for _ in range(TARGET_MOTION_TICKS_PER_STEP):
                env.act("sv", np.array([0.0, 0.0], dtype=np.float32))  # sv stationary
                env.act("target", np.array([target_wp_x, target_wp_y], dtype=np.float32))
                t_state = env.tick()

                loc_data_t = get_sensor_vector(t_state, "target", "LocationSensor")
                gps_data_t = get_sensor_vector(t_state, "target", "GPSSensor")
                curr_pos_t = loc_data_t if loc_data_t is not None else gps_data_t
                if curr_pos_t is not None:
                    last_target_x, last_target_y, last_target_z = float(curr_pos_t[0]), float(curr_pos_t[1]), float(curr_pos_t[2])

            # Step 3: Project target position back to grid coordinates
            target_cell_current = world_to_grid([last_target_x, last_target_y, last_target_z], adapter_config, nav_map_prior.shape, clamp=True)
            dist_t_to_wp = math.sqrt((last_target_x - target_wp_x)**2 + (last_target_y - target_wp_y)**2)

            # Record target trace
            target_trace_entry = {
                "step": step,
                "target_waypoint_cell": [int(target_wp_cell[0]), int(target_wp_cell[1])],
                "target_waypoint_world": [target_wp_x, target_wp_y],
                "target_world_observed": [last_target_x, last_target_y, last_target_z],
                "target_cell_observed": [int(target_cell_current[0]), int(target_cell_current[1])],
                "target_distance_to_waypoint_m": dist_t_to_wp,
                "target_ticks_this_step": TARGET_MOTION_TICKS_PER_STEP,
                "target_proxy_agent_name": "target",
                "target_motion_source": "holoocean_agent_proxy"
            }
            all_target_trace.append(target_trace_entry)

            # Step 4: Write target_cell_current into baseline_GP state target_positions and refresh clue truth
            state["target_positions"] = np.array([[int(target_cell_current[0]), int(target_cell_current[1])]], dtype=int)
            _update_clue_truth_map(state)

            # Step 5: SV plans next cell using baseline_GP policy
            next_cell, segment_path, commit_remaining, plan_details = plan_next_policy_cell(
                state=state,
                step=step,
                commit_remaining=commit_remaining,
                episode_seed=0,
                policy_name="marine_knownmap_path_v2_infosampled",
                target_motion_mode="static",  # Static policy logic since target motion is manually fed
            )

            sv_target_world = grid_to_world(next_cell, config=adapter_config)
            sv_tx, sv_ty = float(sv_target_world[0]), float(sv_target_world[1])

            print(f"\n--- STEP {step} ---")
            print(f"  SV Position Before: {robot_pos_before} -> Next Targeted Cell: {next_cell}")
            print(f"  Target Proxy Expected Waypoint: {target_wp_cell} -> Observed Current Grid: {target_cell_current}")

            # Step 6: Steer SV to next_cell waypoint while keeping target agent commanded
            wp_ticks = 0
            arrived = False
            timeout = False
            last_sv_x, last_sv_y, last_sv_z = 0.0, 0.0, 0.0

            while not arrived and not timeout:
                env.act("sv", np.array([sv_tx, sv_ty], dtype=np.float32))
                env.act("target", np.array([target_wp_x, target_wp_y], dtype=np.float32))  # Continuous pursuit
                
                state_tick = env.tick()
                wp_ticks += 1
                global_tick_offset += 1

                # Read SV position
                loc_sv = get_sensor_vector(state_tick, "sv", "LocationSensor")
                gps_sv = get_sensor_vector(state_tick, "sv", "GPSSensor")
                curr_pos_sv = loc_sv if loc_sv is not None else gps_sv
                if curr_pos_sv is not None:
                    last_sv_x, last_sv_y, last_sv_z = float(curr_pos_sv[0]), float(curr_pos_sv[1]), float(curr_pos_sv[2])

                # Read target position to ensure tick trace integrity
                loc_t = get_sensor_vector(state_tick, "target", "LocationSensor")
                gps_t = get_sensor_vector(state_tick, "target", "GPSSensor")
                curr_pos_t = loc_t if loc_t is not None else gps_t
                if curr_pos_t is not None:
                    last_target_x, last_target_y, last_target_z = float(curr_pos_t[0]), float(curr_pos_t[1]), float(curr_pos_t[2])

                dist_sv = math.sqrt((last_sv_x - sv_tx)**2 + (last_sv_y - sv_ty)**2)

                # Project back to grid cells
                try:
                    proj_row_sv, proj_col_sv = world_to_grid([last_sv_x, last_sv_y, last_sv_z], adapter_config, nav_map_prior.shape)
                except ValueError:
                    proj_row_sv, proj_col_sv = world_to_grid([last_sv_x, last_sv_y, last_sv_z], adapter_config, nav_map_prior.shape, clamp=True)

                if dist_sv < SV_ARRIVAL_RADIUS_M:
                    arrived = True
                elif wp_ticks >= MAX_TICKS_PER_CELL:
                    timeout = True

                # Record tick trace telemetry
                tick_entry = {
                    "tick_global": global_tick_offset,
                    "waypoint_index": 0,
                    "target_row": int(next_cell[0]),
                    "target_col": int(next_cell[1]),
                    "target_x": sv_tx,
                    "target_y": sv_ty,
                    "location_x": last_sv_x,
                    "location_y": last_sv_y,
                    "location_z": last_sv_z,
                    "gps_x": float(gps_sv[0]) if gps_sv is not None else last_sv_x,
                    "gps_y": float(gps_sv[1]) if gps_sv is not None else last_sv_y,
                    "gps_z": float(gps_sv[2]) if gps_sv is not None else last_sv_z,
                    "projected_row": int(proj_row_sv),
                    "projected_col": int(proj_col_sv),
                    "distance_to_target_m": dist_sv,
                    "arrived": arrived,
                    "timeout": timeout,
                    "algorithm_step": step,
                    "target_proxy_x": last_target_x,
                    "target_proxy_y": last_target_y,
                    "target_proxy_z": last_target_z,
                }
                all_tick_trace.append(tick_entry)

            print(f"  SV Arrived: {arrived} in {wp_ticks} ticks. Final error distance: {dist_sv:.2f}m")

            # Step 7: Post-step projection and 3-Fold compliance checks
            sv_final_projected_cell = world_to_grid([last_sv_x, last_sv_y, last_sv_z], adapter_config, nav_map_prior.shape, clamp=True)
            
            next_cell_is_segment_1   = (next_cell == segment_path[1])
            segment_0_is_robot_before = (segment_path[0] == robot_pos_before)
            final_projected_matches  = (sv_final_projected_cell == next_cell)

            if not next_cell_is_segment_1:
                raise ValueError(f"CRITICAL: Next targeted cell {next_cell} != segment_path[1] {segment_path[1]}.")
            if not segment_0_is_robot_before:
                raise ValueError(f"CRITICAL: segment_path[0] {segment_path[0]} != robot_pos_before {robot_pos_before}.")
            if not final_projected_matches:
                raise ValueError(f"CRITICAL: Projected cell {sv_final_projected_cell} != targeted next_cell {next_cell}.")

            found_count_before = int(state["found_mask"].sum())

            # Step 8: Finalize policy step using adapter library
            state = finalize_policy_step_after_holoocean(
                state=state,
                step=step,
                robot_pos_before=robot_pos_before,
                next_cell=next_cell,
                final_projected_cell=sv_final_projected_cell,
                gp_fit_every=5,
            )

            found_count_after = int(state["found_mask"].sum())
            detected_count_this_step = found_count_after - found_count_before

            # Step 9: Record found event details immediately if dynamic target is located
            if detected_count_this_step > 0 and not found_events["found"]:
                found_events["found"] = True
                found_events["found_step"] = step
                found_events["found_target_indices"] = [0]
                found_events["target_cell_at_found"] = [int(target_cell_current[0]), int(target_cell_current[1])]
                found_events["target_world_at_found"] = [last_target_x, last_target_y, last_target_z]
                found_events["sv_cell_at_found"] = [int(sv_final_projected_cell[0]), int(sv_final_projected_cell[1])]
                found_events["sv_world_at_found"] = [last_sv_x, last_sv_y, last_sv_z]
                found_events["euclidean_distance_cells_at_found"] = float(
                    np.hypot(sv_final_projected_cell[0] - target_cell_current[0],
                             sv_final_projected_cell[1] - target_cell_current[1])
                )
                found_events["hit_update_note"] = "found_mask/intensity_map/GP/search_info updated through finalize_policy_step_after_holoocean"
                print(f"*** DYNAMIC TARGET DETECTED at step {step}! Distance: {found_events['euclidean_distance_cells_at_found']:.2f} cells ***")

            # Collect decision feedback parameters
            replanned         = bool(state.get("_audit_replanned", False))
            replan_reason     = state.get("_audit_replan_reason") or "none"
            committed_vp      = state.get("committed_viewpoint")
            committed_anchor  = state.get("committed_anchor")
            anchor_source     = state.get("last_anchor_source") or "none"
            rem_intensity     = float(remaining_intensity_mass(state["intensity_map"]))
            si_map            = state.get("search_info_map")
            if si_map is not None:
                si_peak = float(np.max(si_map))
                si_mean = float(np.mean(si_map))
            else:
                si_peak, si_mean = 0.0, 0.0

            decision_record = {
                "step":                              step,
                "robot_pos_before":                  [int(robot_pos_before[0]), int(robot_pos_before[1])],
                "sv_world_before":                   [float(tick_entry["gps_x"]), float(tick_entry["gps_y"])],
                "target_waypoint_cell":              [int(target_wp_cell[0]), int(target_wp_cell[1])],
                "target_waypoint_world":             [target_wp_x, target_wp_y],
                "target_world_current":              [last_target_x, last_target_y, last_target_z],
                "target_cell_current":               [int(target_cell_current[0]), int(target_cell_current[1])],
                "target_motion_ticks":               TARGET_MOTION_TICKS_PER_STEP,
                "target_distance_to_waypoint_m":      dist_t_to_wp,
                "segment_path":                      [[int(pt[0]), int(pt[1])] for pt in segment_path],
                "next_cell":                         [int(next_cell[0]), int(next_cell[1])],
                "next_cell_world":                   [sv_tx, sv_ty],
                "sv_final_world":                    [last_sv_x, last_sv_y, last_sv_z],
                "sv_final_projected_cell":           [int(sv_final_projected_cell[0]), int(sv_final_projected_cell[1])],
                "arrived":                           bool(arrived),
                "timeout":                           bool(timeout),
                "ticks":                             wp_ticks,
                "distance_to_next_cell_m":           dist_sv,
                "found_count_before":                found_count_before,
                "found_count_after":                 found_count_after,
                "detected_count_this_step":          detected_count_this_step,
                "found_mask":                        [bool(f) for f in state["found_mask"]],
                "find_times":                        state["find_times"],
                "remaining_intensity_mass":          rem_intensity,
                "search_info_map_peak":              si_peak,
                "search_info_map_mean":              si_mean,
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
                "target_cell_source":                "algorithm_segment_path",
                "target_motion_source":              "holoocean_agent_proxy",
                "target_motion_mode_for_policy":      "static",
                "viewpoint_generation_mode":         "simple_ring_v1",
                "path_safety_mode":                  "soft_clearance_astar_v1",
                "clue_acquisition_mode":             "ucb",
                "run_label":                         "dynamic_target_search_catchable",
                "phase_note":                        "Phase 3C-1-catchable dynamic target search positive-control run; target agent follows a catchable schedule near the search corridor; no HoloOcean sonar/camera.",
                "world":                             spec.get("world", "OpenWater"),
            }
            all_decisions.append(decision_record)

        # Check final loop end found mask
        if np.all(state["found_mask"]):
            terminated_reason = "all_found"

        if not found_events["found"]:
            found_events["reason"] = terminated_reason
            found_events["final_cell"] = [int(state["robot_pos"][0]), int(state["robot_pos"][1])]
            found_events["target_cell"] = [int(target_cell_current[0]), int(target_cell_current[1])]
            dist_cells = float(np.hypot(state["robot_pos"][0] - target_cell_current[0], state["robot_pos"][1] - target_cell_current[1]))
            found_events["final_distance_to_target_cells"] = dist_cells

    elapsed_time = time.time() - start_time
    total_ticks  = len(all_tick_trace)
    actual_steps = len(all_decisions)

    print(f"\n==========================================")
    print(f"Dynamic Target Search Completed!")
    print(f"  Actual steps     : {actual_steps}")
    print(f"  Terminated reason: {terminated_reason}")
    print(f"  Total ticks      : {total_ticks}")
    print(f"  Wall time        : {elapsed_time:.2f}s")
    print(f"  Target found     : {found_events['found']} at step {found_events['found_step']}")
    print(f"==========================================")

    # Save manifests
    save_decisions_csv(DECISIONS_CSV, all_decisions)
    os.makedirs(os.path.dirname(DECISIONS_JSON), exist_ok=True)
    with open(DECISIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_decisions, f, indent=2)
    print(f"Decisions JSON saved to: {DECISIONS_JSON}")

    save_ticks_csv(TICK_CSV, all_tick_trace)

    # Target trace saving
    os.makedirs(os.path.dirname(TARGET_JSON), exist_ok=True)
    with open(TARGET_JSON, "w", encoding="utf-8") as f:
        json.dump(all_target_trace, f, indent=2)
    print(f"Target trace JSON saved to: {TARGET_JSON}")

    if all_target_trace:
        keys_t = list(all_target_trace[0].keys())
        with open(TARGET_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys_t)
            writer.writeheader()
            writer.writerows(all_target_trace)
        print(f"Target trace CSV saved to: {TARGET_CSV}")

    os.makedirs(os.path.dirname(FOUND_JSON), exist_ok=True)
    with open(FOUND_JSON, "w", encoding="utf-8") as f:
        json.dump(found_events, f, indent=2)
    print(f"Found events JSON saved to: {FOUND_JSON}")

    # Summary report and route map preview
    write_summary_report(SUMMARY_MD, spec, all_decisions, elapsed_time, total_ticks, terminated_reason, found_events)
    generate_trajectory_preview(nav_map_prior, all_decisions, all_target_trace, found_events, PREVIEW_PNG)
    print("Phase 3C-1 smoke complete!")


if __name__ == "__main__":
    main()
