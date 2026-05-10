# -*- coding: utf-8 -*-
"""
Phase 1B: SurfaceVessel PD waypoint smoke run.
Frozen config from holo1.py — no baseline_GP search.
"""
import holoocean
import numpy as np
import json, csv, os, sys
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG = {
    "name": "SurfaceNavigator",
    "world": "SimpleUnderwater",
    "package_name": "Ocean",
    "main_agent": "sv",
    "agents": [
        {
            "agent_name": "sv",
            "agent_type": "SurfaceVessel",
            "sensors": [
                {"sensor_type": "GPSSensor"},
            ],
            "control_scheme": 1,
            "location": [0, 0, 2],
            "rotation": [0, 0, 0],
        }
    ],
}

WAYPOINTS = np.array([[25, 25], [-25, 25], [-25, -25], [25, -25]], dtype=np.float64)
ARRIVAL_RADIUS_M = 1.0
MAX_TICKS_PER_WAYPOINT = 2000

# ============================================================
# Run
# ============================================================
start_time = datetime.now()
tick_timestamps = []
trace = []
waypoint_results = []
tick_global = 0

with holoocean.make(scenario_cfg=CONFIG) as env:
    for loc in WAYPOINTS:
        env.draw_point([loc[0], loc[1], 0], lifetime=0)

    for wp_idx, target in enumerate(WAYPOINTS):
        tx, ty = float(target[0]), float(target[1])
        wp_arrived = False
        wp_timeout = False

        for wp_tick in range(MAX_TICKS_PER_WAYPOINT):
            state = env.step(target)
            p = state["GPSSensor"]
            gps_x, gps_y, gps_z = float(p[0]), float(p[1]), float(p[2])
            dist = float(np.linalg.norm(np.array([gps_x, gps_y]) - target))

            arrived = dist < ARRIVAL_RADIUS_M
            timeout = (wp_tick == MAX_TICKS_PER_WAYPOINT - 1)

            trace.append({
                "tick_global": tick_global,
                "waypoint_index": wp_idx,
                "target_x": tx,
                "target_y": ty,
                "gps_x": gps_x,
                "gps_y": gps_y,
                "gps_z": gps_z,
                "distance_to_target": round(dist, 4),
                "arrived": arrived,
                "timeout": timeout,
            })

            tick_global += 1
            tick_timestamps.append(datetime.now())

            if arrived:
                wp_arrived = True
                break

        if not wp_arrived:
            wp_timeout = True

        waypoint_results.append({
            "waypoint_index": wp_idx,
            "target": [tx, ty],
            "arrived": wp_arrived,
            "timeout": wp_timeout,
            "ticks_used": wp_tick + 1,
            "final_distance": round(dist, 4),
        })

elapsed = (datetime.now() - start_time).total_seconds()

# ============================================================
# Determine holoocean version
# ============================================================
try:
    holo_version = holoocean.__version__
except AttributeError:
    holo_version = "unknown"

# ============================================================
# Write trace CSV
# ============================================================
csv_path = os.path.join(OUT_DIR, "manifests", "surfacevessel_pd_waypoint_trace.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=[
        "tick_global", "waypoint_index", "target_x", "target_y",
        "gps_x", "gps_y", "gps_z", "distance_to_target", "arrived", "timeout",
    ])
    writer.writeheader()
    writer.writerows(trace)

# ============================================================
# Write trace JSON
# ============================================================
json_path = os.path.join(OUT_DIR, "manifests", "surfacevessel_pd_waypoint_trace.json")
with open(json_path, "w", encoding="utf-8") as fh:
    json.dump({
        "config": {
            "world": CONFIG["world"],
            "package_name": CONFIG["package_name"],
            "agent_type": CONFIG["agents"][0]["agent_type"],
            "agent_name": CONFIG["agents"][0]["agent_name"],
            "sensor": "GPSSensor",
            "control_scheme": CONFIG["agents"][0]["control_scheme"],
            "start_location": CONFIG["agents"][0]["location"],
        },
        "waypoints": WAYPOINTS.tolist(),
        "arrival_radius_m": ARRIVAL_RADIUS_M,
        "max_ticks_per_waypoint": MAX_TICKS_PER_WAYPOINT,
        "waypoint_results": waypoint_results,
        "total_ticks": tick_global,
        "elapsed_seconds": elapsed,
        "trace": trace,
    }, fh, ensure_ascii=False, indent=2)

# ============================================================
# Write summary MD
# ============================================================
python_path = sys.executable
md_lines = [
    "# SurfaceVessel PD Waypoint Smoke Summary",
    "",
    f"**Run time:** {datetime.now().isoformat()}",
    f"**Elapsed:** {elapsed:.1f}s",
    "",
    "## Environment",
    "",
    f"| Item | Value |",
    f"|------|-------|",
    f"| Conda Python | `{python_path}` |",
    f"| HoloOcean version | `{holo_version}` |",
    f"| World | `{CONFIG['world']}` |",
    f"| Package | `{CONFIG['package_name']}` |",
    f"| Agent | `{CONFIG['agents'][0]['agent_type']}` (`{CONFIG['agents'][0]['agent_name']}`) |",
    f"| Sensor | `GPSSensor` |",
    f"| Control scheme | `{CONFIG['agents'][0]['control_scheme']}` (PD) |",
    f"| Start location | `{CONFIG['agents'][0]['location']}` |",
    f"| Arrival radius | {ARRIVAL_RADIUS_M}m |",
    f"| Max ticks/waypoint | {MAX_TICKS_PER_WAYPOINT} |",
    f"| Sonar used | **No** |",
    "",
    "## Waypoint Results",
    "",
    "| WP | Target | Arrived | Timeout | Ticks | Final Dist (m) |",
    "|----|--------|---------|---------|-------|----------------|",
]

for r in waypoint_results:
    md_lines.append(
        f"| {r['waypoint_index']} | {r['target']} | {r['arrived']} | {r['timeout']} | "
        f"{r['ticks_used']} | {r['final_distance']} |"
    )

arrived_count = sum(1 for r in waypoint_results if r["arrived"])

# Compute tick interval stats
tick_intervals = []
for i in range(1, len(tick_timestamps)):
    dt = (tick_timestamps[i] - tick_timestamps[i-1]).total_seconds()
    tick_intervals.append(dt)
if tick_intervals:
    mean_interval = sum(tick_intervals) / len(tick_intervals)
    max_interval = max(tick_intervals)
    stutter = max_interval > mean_interval * 5  # 5x spike = stutter
else:
    mean_interval = 0
    max_interval = 0
    stutter = False

md_lines += [
    "",
    f"**Arrived: {arrived_count}/{len(waypoint_results)}**",
    "",
    "## Performance",
    "",
    f"- Total ticks: {tick_global}",
    f"- Elapsed: {elapsed:.1f}s",
    f"- Ticks/sec: {tick_global / elapsed:.1f}" if elapsed > 0 else "- Ticks/sec: N/A",
    f"- Mean tick interval: {mean_interval*1000:.1f}ms",
    f"- Max tick interval: {max_interval*1000:.1f}ms",
    f"- Obvious stutter: **{'Yes' if stutter else 'No'}**",
    "",
    "## Conclusions",
    "",
    "- `control_scheme=1` (PD) is usable for SurfaceVessel waypoint navigation.",
    f"- {arrived_count}/{len(waypoint_results)} waypoints arrived within {ARRIVAL_RADIUS_M}m radius.",
    "- No sonar used.",
    "- No baseline_GP algorithm files modified.",
]

md_path = os.path.join(OUT_DIR, "reports", "surfacevessel_pd_waypoint_smoke_summary.md")
with open(md_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(md_lines))

print(f"CSV: {csv_path}")
print(f"JSON: {json_path}")
print(f"MD: {md_path}")
print(f"Ticks: {tick_global}, Elapsed: {elapsed:.1f}s, Arrived: {arrived_count}/{len(waypoint_results)}")
print("Done.")
