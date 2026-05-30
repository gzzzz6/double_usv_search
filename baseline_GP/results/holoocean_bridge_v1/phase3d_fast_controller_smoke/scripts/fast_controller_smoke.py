"""HoloOcean Phase 3D-0: SurfaceVessel control_scheme=0 fast waypoint controller smoke.

Evaluates a customized proportional waypoint controller using twin propeller thrust.
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

# Add root directory to sys.path
sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid, CoordinateAdapterConfig
from baseline_GP.holoocean_bridge.scene_map_adapter import load_scene_map_npz
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector

# ---------------------------------------------------------------------------
# Paths configuration
# ---------------------------------------------------------------------------
BASE_DIR = r"baseline_GP"
MAP_NPZ = os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_v1.npz")
PHASE_DIR = os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase3d_fast_controller_smoke")

TRACE_JSON      = os.path.join(PHASE_DIR, "manifests", "fast_controller_trace.json")
TRACE_CSV       = os.path.join(PHASE_DIR, "manifests", "fast_controller_trace.csv")
SUMMARY_JSON    = os.path.join(PHASE_DIR, "manifests", "fast_controller_waypoint_summary.json")
SUMMARY_MD      = os.path.join(PHASE_DIR, "reports",   "fast_controller_summary.md")
PREVIEW_PNG     = os.path.join(PHASE_DIR, "visuals",   "fast_controller_path.png")

# Controller parameters
MAX_FORCE = 8000.0
MIN_FORCE = 1500.0
TURN_GAIN = 0.8
DIST_SLOW_RADIUS_M = 8.0
ARRIVAL_RADIUS_M = 2.5
MAX_TICKS_PER_WAYPOINT = 400

REF_TICKS = {
    0: 583,  # (40, 45)
    1: 630,  # (45, 45)
    2: 628,  # (45, 40)
    3: 628,  # (40, 40)
}


def save_trace_csv(path: str, trace: List[Dict[str, Any]]) -> None:
    if not trace:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = list(trace[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(trace)
    print(f"Tick trace CSV saved to: {path}")


def generate_preview_map(
    nav_map_prior: np.ndarray,
    waypoints: List[Tuple[int, int]],
    trace: List[Dict[str, Any]],
    preview_path: str,
) -> None:
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 10))
        plt.imshow(nav_map_prior, cmap="gray_r", origin="upper")

        # Plot planned waypoints
        wp_rows = [wp[0] for wp in waypoints]
        wp_cols = [wp[1] for wp in waypoints]
        plt.scatter(wp_cols, wp_rows, color="red", marker="o", s=100, zorder=5, label="Target Waypoints")
        for i, wp in enumerate(waypoints):
            plt.annotate(
                f"WP {i+1}\n({wp[0]},{wp[1]})",
                xy=(wp[1], wp[0]),
                xytext=(8, -8),
                textcoords="offset points",
                fontsize=9,
                color="red",
                weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.8),
            )

        # Plot simulated path
        if trace:
            sv_rows = [t["projected_row"] for t in trace]
            sv_cols = [t["projected_col"] for t in trace]
            plt.plot(sv_cols, sv_rows, color="blue", linewidth=2.0, alpha=0.8, label="SV Trajectory (control_scheme=0)")
            plt.scatter(sv_cols[0], sv_rows[0], color="green", marker="*", s=200, edgecolors="black", zorder=6, label="Start")

        plt.title(
            f"Phase 3D-0 fast waypoint controller smoke\n"
            f"(openwater_open_v1, 81x81, cell=5m, scheme=0)",
            fontsize=12,
            pad=10,
        )
        plt.xlabel("Column", fontsize=10)
        plt.ylabel("Row", fontsize=10)
        plt.xlim(-0.5, 80.5)
        plt.ylim(80.5, -0.5)
        plt.grid(True, which="both", color="lightgray", linestyle=":", alpha=0.4)
        plt.legend(loc="upper right")

        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        plt.savefig(preview_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Preview map saved to: {preview_path}")
    except Exception as e:
        print(f"[WARN] Skipping visual preview: {e}")


def write_summary_report(
    summary_path: str,
    spec: dict,
    waypoint_summary: List[Dict[str, Any]],
    elapsed_time: float,
    total_ticks: int,
) -> None:
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    n = len(waypoint_summary)
    mean_ticks = total_ticks / max(1, n)
    arrived_count = sum(1 for w in waypoint_summary if w["arrived"])
    timeout_count = sum(1 for w in waypoint_summary if w["timeout"])

    header = f"""# Phase 3D-0: SurfaceVessel control_scheme=0 Fast Controller Smoke Report
 
## Simulation Environment
- **Run Label**: `fast_controller_smoke`
- **HoloOcean World**: `{spec.get("world", "OpenWater")}`
- **Package**: `{spec.get("package_name", "Ocean")}`
- **Search USV**: `SurfaceVessel` (`sv`)
- **Control Scheme**: `0` (Twin-propeller manual force control mode)
- **Controller Config**:
  - `MAX_FORCE = {MAX_FORCE}`
  - `MIN_FORCE = {MIN_FORCE}`
  - `TURN_GAIN = {TURN_GAIN}`
  - `DIST_SLOW_RADIUS_M = {DIST_SLOW_RADIUS_M}`
  - `ARRIVAL_RADIUS_M = {ARRIVAL_RADIUS_M}`
  - `MAX_TICKS_PER_WAYPOINT = {MAX_TICKS_PER_WAYPOINT}`

## Execution Summary
- **Total Waypoints**: `{n}`
- **Total Ticks**: `{total_ticks}`
- **Wall Time**: `{elapsed_time:.2f} s`
- **Mean Ticks/Waypoint**: `{mean_ticks:.1f}`
- **Arrived Count**: `{arrived_count}` / {n}
- **Timeout Count**: `{timeout_count}`

## Waypoint Details Table
| WP | Target Cell | Start World | Final World | Final Proj Cell | Ticks | Arr | TO | Min Dist(m) | Final Dist(m) | Ref Ticks (Scheme=1) | Speedup |
| :-: | :---: | :---: | :---: | :---: | :---: | :-: | :-: | :---: | :---: | :---: | :---: |
"""
    rows = []
    for w in waypoint_summary:
        sc = w["start_world"]
        fw = w["final_world"]
        tc = w["target_cell"]
        fpc = w["final_projected_cell"]
        speedup = w["baseline_control_scheme_1_reference_ticks"] / max(1, w["ticks"])
        rows.append(
            f"| {w['waypoint_index']+1} | ({tc[0]},{tc[1]}) | "
            f"({sc[0]:.1f},{sc[1]:.1f}) | ({fw[0]:.1f},{fw[1]:.1f}) | "
            f"({fpc[0]},{fpc[1]}) | {w['ticks']} | "
            f"{'Y' if w['arrived'] else 'N'} | {'Y' if w['timeout'] else 'N'} | "
            f"{w['min_distance_to_target_m']:.2f} | {w['final_distance_to_target_m']:.2f} | "
            f"{w['baseline_control_scheme_1_reference_ticks']} | {speedup:.2f}x |"
        )

    footer = f"""
## Performance Verification
- **All targets matched**: `{'PASSED' if all(w['final_projected_cell'] == w['target_cell'] for w in waypoint_summary) else 'FAILED'}`
- **All arrived**: `{'PASSED' if arrived_count == n else 'FAILED'}`
- **Zero timeout**: `{'PASSED' if timeout_count == 0 else 'FAILED'}`
- **Mean ticks < 300**: `{'PASSED' if mean_ticks < 300 else 'FAILED'}`
- **Mean ticks < 150 (Ideal)**: `{'PASSED' if mean_ticks < 150 else 'FAILED'}`
"""
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(rows) + footer)
    print(f"Summary report written to: {summary_path}")


def main() -> None:
    print("=== Phase 3D-0: Launching Fast Waypoint Controller Smoke ===")

    # 1. Load scene adapter config
    nav_map_prior, spec = load_scene_map_npz(MAP_NPZ)
    from baseline_GP.holoocean_bridge.scene_map_adapter import scene_map_config_from_spec
    adapter_config = scene_map_config_from_spec(spec)

    start_cell = (40, 40)
    waypoints_grid = [
        (40, 45),
        (45, 45),
        (45, 40),
        (40, 40),
    ]

    start_pos_world = list(grid_to_world(start_cell, config=adapter_config))
    start_pos_world[2] = 2.0  # safe depth

    scenario_cfg = {
        "name": "fast_controller_smoke",
        "world": spec["world"],
        "package_name": spec["package_name"],
        "main_agent": "sv",
        "agents": [
            {
                "agent_name": "sv",
                "agent_type": "SurfaceVessel",
                "sensors": [
                    {"sensor_type": "GPSSensor", "socket": "COM"},
                    {"sensor_type": "LocationSensor", "socket": "COM"},
                    {"sensor_type": "OrientationSensor", "socket": "COM"}
                ],
                "control_scheme": 0,
                "location": start_pos_world,
                "rotation": [0.0, 0.0, 0.0]
            }
        ]
    }

    import holoocean

    all_tick_trace: List[Dict[str, Any]] = []
    waypoint_summary: List[Dict[str, Any]] = []
    global_tick_offset = 0

    print("Launching simulator...")
    start_time = time.time()

    with holoocean.make(scenario_cfg=scenario_cfg) as env:
        # Initial step to stabilize
        env.act("sv", np.zeros(2, dtype=np.float32))
        state = env.tick()

        for wp_idx, target_cell in enumerate(waypoints_grid):
            target_world_3d = grid_to_world(target_cell, config=adapter_config)
            tx, ty = float(target_world_3d[0]), float(target_world_3d[1])

            # Get initial position
            loc_sv = get_sensor_vector(state, "sv", "LocationSensor")
            gps_sv = get_sensor_vector(state, "sv", "GPSSensor")
            curr_pos_sv = loc_sv if loc_sv is not None else gps_sv
            start_world = [float(curr_pos_sv[0]), float(curr_pos_sv[1]), float(curr_pos_sv[2])] if curr_pos_sv is not None else [0.0, 0.0, 2.0]

            print(f"\nWaypoint {wp_idx+1}/{len(waypoints_grid)} -> Target Grid: {target_cell} (World: {tx:.1f}, {ty:.1f})")

            wp_ticks = 0
            arrived = False
            timeout = False
            min_dist = 9999.0
            max_cmd_abs = 0.0

            last_sv_x, last_sv_y, last_sv_z = start_world[0], start_world[1], start_world[2]

            while not arrived and not timeout:
                # Read sensors
                loc_sv = get_sensor_vector(state, "sv", "LocationSensor")
                gps_sv = get_sensor_vector(state, "sv", "GPSSensor")
                orient_sv = get_sensor_vector(state, "sv", "OrientationSensor")  # 3x3 matrix as flattened or 2D array
                
                curr_pos_sv = loc_sv if loc_sv is not None else gps_sv
                if curr_pos_sv is not None:
                    last_sv_x, last_sv_y, last_sv_z = float(curr_pos_sv[0]), float(curr_pos_sv[1]), float(curr_pos_sv[2])

                # Calculate distance
                dx = tx - last_sv_x
                dy = ty - last_sv_y
                dist = math.hypot(dx, dy)
                if dist < min_dist:
                    min_dist = dist

                # Calculate headings
                target_heading_deg = np.degrees(np.arctan2(dy, dx)) % 360.0

                heading_deg = 0.0
                if orient_sv is not None:
                    # orient_sv is usually flat 9-element array or 3x3 array.
                    # Standard columns: forward is R[:, 0].
                    r_matrix = np.reshape(orient_sv, (3, 3))
                    forward = r_matrix[:, 0]
                    heading_deg = np.degrees(np.arctan2(forward[1], forward[0])) % 360.0

                heading_error_deg = (target_heading_deg - heading_deg + 180) % 360 - 180

                # -----------------------------------------------------------
                # Waypoint Proportional Controller logic
                # -----------------------------------------------------------
                heading_error_rad = np.radians(heading_error_deg)
                turn = TURN_GAIN * heading_error_rad * MAX_FORCE

                # P-control for forward thrust based on distance
                if dist < DIST_SLOW_RADIUS_M:
                    forward = MIN_FORCE + (MAX_FORCE - MIN_FORCE) * (dist / DIST_SLOW_RADIUS_M)
                else:
                    forward = MAX_FORCE

                # Slow down forward thrust when heading error is huge to rotate in place
                forward_factor = np.cos(heading_error_rad)
                if forward_factor < 0:
                    forward_factor = 0.0
                forward = forward * forward_factor

                # Twin propeller commands
                left_thrust = forward - turn
                right_thrust = forward + turn

                # Clip
                left_thrust = np.clip(left_thrust, -MAX_FORCE, MAX_FORCE)
                right_thrust = np.clip(right_thrust, -MAX_FORCE, MAX_FORCE)

                max_cmd_abs = max(max_cmd_abs, abs(left_thrust), abs(right_thrust))
                command = np.array([left_thrust, right_thrust], dtype=np.float32)

                # Send command to simulator
                env.act("sv", command)
                state = env.tick()

                wp_ticks += 1
                global_tick_offset += 1

                # Project back to grid cell
                proj_cell = world_to_grid([last_sv_x, last_sv_y, last_sv_z], adapter_config, nav_map_prior.shape, clamp=True)

                if dist < ARRIVAL_RADIUS_M and proj_cell == target_cell:
                    arrived = True
                elif wp_ticks >= MAX_TICKS_PER_WAYPOINT:
                    timeout = True

                # Record tick trace
                tick_entry = {
                    "tick_global": global_tick_offset,
                    "waypoint_index": wp_idx,
                    "target_cell": [int(target_cell[0]), int(target_cell[1])],
                    "target_world_x": tx,
                    "target_world_y": ty,
                    "location_x": last_sv_x,
                    "location_y": last_sv_y,
                    "location_z": last_sv_z,
                    "projected_row": int(proj_cell[0]),
                    "projected_col": int(proj_cell[1]),
                    "distance_to_target_m": dist,
                    "heading_deg": heading_deg,
                    "target_heading_deg": target_heading_deg,
                    "heading_error_deg": heading_error_deg,
                    "command_0": float(left_thrust),
                    "command_1": float(right_thrust),
                    "arrived": arrived,
                    "timeout": timeout,
                }
                all_tick_trace.append(tick_entry)

            print(f"  SV Arrived: {arrived} in {wp_ticks} ticks. Min Dist: {min_dist:.2f}m. Final Dist: {dist:.2f}m.")

            # Record waypoint summary
            wp_summary_entry = {
                "waypoint_index": wp_idx,
                "target_cell": [int(target_cell[0]), int(target_cell[1])],
                "target_world": [tx, ty],
                "start_world": start_world,
                "final_world": [last_sv_x, last_sv_y, last_sv_z],
                "final_projected_cell": [int(proj_cell[0]), int(proj_cell[1])],
                "ticks": wp_ticks,
                "arrived": arrived,
                "timeout": timeout,
                "min_distance_to_target_m": min_dist,
                "final_distance_to_target_m": dist,
                "max_command_abs": float(max_cmd_abs),
                "controller_config": {
                    "MAX_FORCE": MAX_FORCE,
                    "MIN_FORCE": MIN_FORCE,
                    "TURN_GAIN": TURN_GAIN,
                    "DIST_SLOW_RADIUS_M": DIST_SLOW_RADIUS_M,
                    "ARRIVAL_RADIUS_M": ARRIVAL_RADIUS_M,
                    "MAX_TICKS_PER_WAYPOINT": MAX_TICKS_PER_WAYPOINT,
                },
                "baseline_control_scheme_1_reference_ticks": REF_TICKS[wp_idx],
            }
            waypoint_summary.append(wp_summary_entry)

    elapsed_time = time.time() - start_time
    total_ticks = len(all_tick_trace)

    print(f"\n==========================================")
    print(f"Fast Controller Smoke Completed!")
    print(f"  Total waypoints  : {len(waypoint_summary)}")
    print(f"  Total ticks      : {total_ticks}")
    print(f"  Wall time        : {elapsed_time:.2f}s")
    print(f"  Mean ticks/wp    : {total_ticks / len(waypoint_summary):.1f}")
    print(f"==========================================")

    # Save manifests
    save_trace_csv(TRACE_CSV, all_tick_trace)
    os.makedirs(os.path.dirname(TRACE_JSON), exist_ok=True)
    with open(TRACE_JSON, "w", encoding="utf-8") as f:
        json.dump(all_tick_trace, f, indent=2)
    print(f"Tick trace JSON saved to: {TRACE_JSON}")

    os.makedirs(os.path.dirname(SUMMARY_JSON), exist_ok=True)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(waypoint_summary, f, indent=2)
    print(f"Waypoint summary JSON saved to: {SUMMARY_JSON}")

    # Generate summary report and preview path PNG
    write_summary_report(SUMMARY_MD, spec, waypoint_summary, elapsed_time, total_ticks)
    generate_preview_map(nav_map_prior, waypoints_grid, all_tick_trace, PREVIEW_PNG)
    print("Phase 3D-0 smoke complete!")


if __name__ == "__main__":
    main()
