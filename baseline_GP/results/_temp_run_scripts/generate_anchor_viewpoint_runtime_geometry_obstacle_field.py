from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASELINE_DIR = PROJECT_ROOT / "baseline_GP"
IMAGES_DIR = PROJECT_ROOT / "images"
DATA_DIR = BASELINE_DIR / "results" / "_temp_run_scripts" / "figure_source_data"

if str(BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(BASELINE_DIR))

from core_map import FREE, OCCUPIED  # noqa: E402
from core_safe_nav import (  # noqa: E402
    a_star_safe,
    build_clearance_cost_map,
    build_obstacle_distance_map,
    inflate_occupancy_map,
)
import marine_knownmap_runtime as rt1  # noqa: E402


OUT_PATH = IMAGES_DIR / "fig_anchor_viewpoint_runtime_geometry_obstacle_field.png"
DATA_PATH = DATA_DIR / "fig_anchor_viewpoint_runtime_geometry_obstacle_field.json"

POLICY = "marine_knownmap_path_v2_infosampled"
MAP_KIND = "obstacle_field"
EPISODE_SEED = 0
TARGET_MOTION_MODE = "static"
MAP_HEIGHT = 40
MAP_WIDTH = 60
SENSOR_RANGE_CELLS = 5

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def _cell_to_xy(cell: tuple[int, int]) -> tuple[int, int]:
    return int(cell[1]), int(cell[0])


def _path_xy(path: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
    xs = [int(cell[1]) for cell in path]
    ys = [int(cell[0]) for cell in path]
    return xs, ys


def _path_turns(path: list[tuple[int, int]]) -> int:
    if len(path) < 3:
        return 0
    turns = 0
    prev = (path[1][0] - path[0][0], path[1][1] - path[0][1])
    for a, b in zip(path[1:-1], path[2:]):
        cur = (b[0] - a[0], b[1] - a[1])
        if cur != prev:
            turns += 1
        prev = cur
    return turns


def _capture_records() -> tuple[list[dict[str, object]], dict[str, object]]:
    original = rt1.select_knownmap_path_segment_policy
    captured: list[dict[str, object]] = []

    def wrapped_select_knownmap_path_segment_policy(*args, **kwargs):
        segment_path, details = original(*args, **kwargs)
        if segment_path is not None and details:
            captured.append(
                {
                    "robot_pos_before_replan": tuple(int(v) for v in kwargs["robot_pos"]),
                    "segment_path": [tuple(int(v) for v in cell) for cell in segment_path],
                    "details": dict(details),
                    "search_info_map": np.array(
                        kwargs.get("search_info_map"), dtype=float, copy=True
                    ),
                    "nav_map_prior": np.array(kwargs["nav_map_prior"], dtype=int, copy=True),
                    "sampled_viewpoint_pool_cells": [
                        tuple(int(v) for v in cell)
                        for cell in details.get("sampled_viewpoint_pool_cells", [])
                    ],
                }
            )
        return segment_path, details

    rt1.select_knownmap_path_segment_policy = wrapped_select_knownmap_path_segment_policy
    try:
        result = rt1.run_episode_single_usv_search_knownmap(
            episode_seed=EPISODE_SEED,
            max_iters=100,
            policy_name=POLICY,
            n_targets=3,
            map_kind=MAP_KIND,
            map_height_cells=MAP_HEIGHT,
            map_width_cells=MAP_WIDTH,
            target_motion_mode=TARGET_MOTION_MODE,
            clue_acquisition_mode="ucb",
            anomaly_tail_quantile=0.90,
            anomaly_weight_lambda=1.25,
            path_safety_mode="soft_clearance_astar_v1",
            safe_nav_inflation_radius_cells=0,
            safe_nav_soft_clearance_radius_cells=1,
            safe_nav_lambda_clearance=1.0,
            viewpoint_generation_mode="simple_ring_v1",
            render=False,
        )
    finally:
        rt1.select_knownmap_path_segment_policy = original

    replan_rows = [row for row in result["trace_rows"] if row.get("replanned_this_step")]
    if len(replan_rows) != len(captured):
        raise RuntimeError(
            f"Captured {len(captured)} planner calls but found {len(replan_rows)} replan rows."
        )
    for record, row in zip(captured, replan_rows):
        record["step"] = int(row["step"])
        record["robot_pos_after_step"] = tuple(int(v) for v in row["robot_cell"])
    return captured, result


def _choose_record(records: list[dict[str, object]]) -> dict[str, object]:
    preferred = [record for record in records if int(record["step"]) == 56]
    if preferred:
        return preferred[0]

    best_record: dict[str, object] | None = None
    best_score = -1e9
    for record in records:
        details = record["details"]
        anchor = details.get("anchor_cell")
        viewpoint = details.get("viewpoint_cell")
        if anchor is None or viewpoint is None:
            continue
        path = list(record["segment_path"])
        if len(path) <= 3:
            continue
        nav_map = np.asarray(record["nav_map_prior"])
        rows = [int(cell[0]) for cell in path] + [int(anchor[0]), int(viewpoint[0])]
        cols = [int(cell[1]) for cell in path] + [int(anchor[1]), int(viewpoint[1])]
        r0, r1 = max(0, min(rows) - 7), min(nav_map.shape[0], max(rows) + 8)
        c0, c1 = max(0, min(cols) - 7), min(nav_map.shape[1], max(cols) + 8)
        local_obstacles = int(np.sum(nav_map[r0:r1, c0:c1] == OCCUPIED))
        score = (
            8.0 * _path_turns(path)
            + 0.03 * local_obstacles
            - 0.15 * abs(int(record["step"]) - 56)
        )
        if score > best_score:
            best_score = score
            best_record = record
    if best_record is None:
        raise RuntimeError("No usable anchor-viewpoint replan record was captured.")
    return best_record


def _reconstruct_full_path(
    nav_map: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    obstacle_distance_map = build_obstacle_distance_map(nav_map)
    inflated_nav_map = inflate_occupancy_map(
        nav_map,
        inflation_radius_cells=0,
        obstacle_distance_map=obstacle_distance_map,
    )
    clearance_cost_map = build_clearance_cost_map(
        nav_map,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=obstacle_distance_map,
        inflated_nav_map=inflated_nav_map,
    )
    path = a_star_safe(
        nav_map,
        start,
        goal,
        inflated_nav_map=inflated_nav_map,
        clearance_cost_map=clearance_cost_map,
        lambda_clearance=1.0,
    )
    if path is None:
        return []
    return [tuple(int(v) for v in cell) for cell in path]


def _plot_map_base(ax: plt.Axes, nav_map: np.ndarray) -> None:
    h, w = nav_map.shape
    rgba = np.ones((h, w, 4), dtype=float)
    rgba[..., :3] = 1.0
    rgba[nav_map == OCCUPIED] = (0.0, 0.0, 0.0, 1.0)
    ax.imshow(rgba, origin="upper", interpolation="nearest", extent=(-0.5, w - 0.5, h - 0.5, -0.5))
    ax.set_xlim(-0.5, w - 0.5)
    ax.set_ylim(h - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.set_xlabel("x / grid cell")
    ax.set_ylabel("y / grid cell")
    ax.set_xticks(np.arange(0, w + 1, 10))
    ax.set_yticks(np.arange(0, h + 1, 5))
    for spine in ax.spines.values():
        spine.set_linewidth(1.4)
        spine.set_color("black")


def _plot_geometry(
    ax: plt.Axes,
    *,
    nav_map: np.ndarray,
    trajectory: list[tuple[int, int]],
    segment_path: list[tuple[int, int]],
    full_path: list[tuple[int, int]],
    robot: tuple[int, int],
    viewpoint: tuple[int, int],
    anchor: tuple[int, int],
    candidate_pool: list[tuple[int, int]],
    local: bool,
) -> None:
    _plot_map_base(ax, nav_map)

    if trajectory:
        xs, ys = _path_xy(trajectory)
        ax.plot(xs, ys, color="#12dfe8", linewidth=1.6, label="Trajectory", zorder=3)

    if full_path and len(full_path) > len(segment_path):
        xs, ys = _path_xy(full_path)
        ax.plot(
            xs,
            ys,
            color="#24c92d",
            linewidth=1.2,
            linestyle=":",
            label="Full path to viewpoint",
            zorder=3,
        )

    if segment_path:
        xs, ys = _path_xy(segment_path)
        ax.plot(xs, ys, color="#22dd28", linewidth=2.6, label="Plan segment", zorder=4)
        ax.scatter(xs, ys, s=14, color="#22dd28", edgecolor="white", linewidth=0.25, zorder=5)

    for cell in candidate_pool:
        if cell == viewpoint:
            continue
        x, y = _cell_to_xy(cell)
        ax.scatter(
            x,
            y,
            s=34 if local else 18,
            facecolor="white",
            edgecolor="#9b9b9b",
            linewidth=1.1,
            alpha=0.95,
            zorder=5,
        )

    vx, vy = _cell_to_xy(viewpoint)
    ax.add_patch(
        Circle(
            (vx, vy),
            SENSOR_RANGE_CELLS,
            fill=False,
            edgecolor="#ff3b30",
            linestyle=(0, (2, 2)),
            linewidth=1.7,
            zorder=4,
        )
    )
    ax.add_patch(
        Circle(
            _cell_to_xy(anchor),
            SENSOR_RANGE_CELLS,
            fill=False,
            edgecolor="#e100ff",
            linestyle=(0, (4, 2)),
            linewidth=1.5,
            zorder=4,
        )
    )

    rx, ry = _cell_to_xy(robot)
    ax.scatter(rx, ry, s=90, color="#1684f5", edgecolor="white", linewidth=1.0, label="Robot", zorder=8)
    ax.scatter(vx, vy, marker="x", s=105, color="#ffd500", linewidth=2.2, label="Viewpoint", zorder=9)
    ax.scatter(
        *_cell_to_xy(anchor),
        marker="D",
        s=75,
        facecolor="#ff00d4",
        edgecolor="black",
        linewidth=0.8,
        label="Anchor",
        zorder=9,
    )

    if local:
        ax.text(vx + 0.7, vy - 1.2, "viewpoint", color="#d00000", fontsize=9, weight="bold")
        ax.text(
            anchor[1] + 0.7,
            anchor[0] + 1.4,
            "anchor",
            color="#d000d8",
            fontsize=9,
            weight="bold",
        )


def generate() -> dict[str, object]:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    records, result = _capture_records()
    record = _choose_record(records)
    details = record["details"]
    nav_map = np.asarray(record["nav_map_prior"], dtype=int)
    robot = tuple(int(v) for v in record["robot_pos_before_replan"])
    viewpoint = tuple(int(v) for v in details["viewpoint_cell"])
    anchor = tuple(int(v) for v in details["anchor_cell"])
    segment_path = [tuple(int(v) for v in cell) for cell in record["segment_path"]]
    full_path = _reconstruct_full_path(nav_map, robot, viewpoint)
    candidate_pool = [tuple(int(v) for v in cell) for cell in record["sampled_viewpoint_pool_cells"]]

    trace_rows = list(result["trace_rows"])
    trajectory: list[tuple[int, int]] = [(1, 1)]
    for row in trace_rows:
        if int(row["step"]) >= int(record["step"]):
            break
        trajectory.append(tuple(int(v) for v in row["robot_cell"]))
    if not trajectory or trajectory[-1] != robot:
        trajectory.append(robot)

    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(12.8, 5.4),
        gridspec_kw={"width_ratios": [1.18, 1.0], "wspace": 0.18},
        constrained_layout=True,
    )
    fig.suptitle(
        f"Anchor-Viewpoint Runtime Geometry | {MAP_KIND}, seed={EPISODE_SEED}, step={record['step']}",
        fontsize=15,
        fontweight="bold",
    )

    _plot_geometry(
        ax0,
        nav_map=nav_map,
        trajectory=trajectory,
        segment_path=segment_path,
        full_path=full_path,
        robot=robot,
        viewpoint=viewpoint,
        anchor=anchor,
        candidate_pool=[],
        local=False,
    )
    ax0.set_title("Runtime Main Map", fontsize=12)

    _plot_geometry(
        ax1,
        nav_map=nav_map,
        trajectory=[],
        segment_path=segment_path,
        full_path=full_path,
        robot=robot,
        viewpoint=viewpoint,
        anchor=anchor,
        candidate_pool=candidate_pool,
        local=True,
    )
    ax1.set_title("Anchor-Viewpoint Local Geometry", fontsize=12)
    local_cells = segment_path + full_path + [robot, viewpoint, anchor] + candidate_pool
    rows = [int(cell[0]) for cell in local_cells]
    cols = [int(cell[1]) for cell in local_cells]
    margin = 6
    local_x0 = max(-0.5, min(cols) - margin)
    local_x1 = min(nav_map.shape[1] - 0.5, max(cols) + margin)
    local_y0 = max(-0.5, min(rows) - margin)
    local_y1 = min(nav_map.shape[0] - 0.5, max(rows) + margin)
    ax1.set_xticks(np.arange(np.ceil(local_x0 / 5.0) * 5.0, local_x1 + 0.1, 5.0))
    ax1.set_yticks(np.arange(np.ceil(local_y0 / 5.0) * 5.0, local_y1 + 0.1, 5.0))
    ax1.set_xlim(local_x0, local_x1)
    ax1.set_ylim(local_y1, local_y0)

    legend_handles = [
        Patch(facecolor="black", edgecolor="black", label="Obstacle"),
        plt.Line2D([0], [0], color="#12dfe8", lw=1.6, label="Trajectory"),
        plt.Line2D([0], [0], color="#22dd28", lw=2.6, label="Plan segment"),
        plt.Line2D([0], [0], color="#24c92d", lw=1.2, linestyle=":", label="Full path"),
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="#1684f5", markeredgecolor="white", markersize=9, label="Robot"),
        plt.Line2D([0], [0], marker="x", color="#ffd500", markersize=9, lw=0, markeredgewidth=2, label="Viewpoint"),
        plt.Line2D([0], [0], marker="D", color="black", markerfacecolor="#ff00d4", markersize=8, lw=0, label="Anchor"),
        plt.Line2D([0], [0], marker="o", color="#9b9b9b", markerfacecolor="white", markersize=7, lw=0, label="Candidate viewpoint"),
    ]
    ax1.legend(
        handles=legend_handles,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=8,
        frameon=True,
    )

    fig.savefig(OUT_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)

    payload = {
        "output_path": str(OUT_PATH),
        "map_kind": MAP_KIND,
        "map_height_cells": MAP_HEIGHT,
        "map_width_cells": MAP_WIDTH,
        "episode_seed": EPISODE_SEED,
        "target_motion_mode": TARGET_MOTION_MODE,
        "policy": POLICY,
        "clue_acquisition_mode": "ucb",
        "path_safety_mode": "soft_clearance_astar_v1",
        "viewpoint_generation_mode": "simple_ring_v1",
        "step": int(record["step"]),
        "robot_pos_before_replan": list(robot),
        "viewpoint_cell": list(viewpoint),
        "anchor_cell": list(anchor),
        "segment_path": [list(cell) for cell in segment_path],
        "full_path_to_viewpoint": [list(cell) for cell in full_path],
        "candidate_viewpoint_pool_size": len(candidate_pool),
        "selected_viewpoint_rank": int(details.get("selected_viewpoint_rank", -1)),
        "planned_viewpoint_path_length": int(details.get("planned_viewpoint_path_length", 0)),
        "segment_path_length": int(details.get("segment_path_length", 0)),
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    info = generate()
    print(json.dumps(info, ensure_ascii=False, indent=2))
