from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASELINE_DIR = PROJECT_ROOT / "baseline_GP"
IMAGES_DIR = PROJECT_ROOT / "images"
OUTPUT_DATA_DIR = BASELINE_DIR / "results" / "_temp_run_scripts" / "figure_source_data"

if str(BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(BASELINE_DIR))

from core_map import FREE, OCCUPIED, create_world  # noqa: E402
import marine_knownmap_runtime_2usv as rt2  # noqa: E402


FIG4_1_PATH = IMAGES_DIR / "fig4_1_static_responsibility_prior_current_maps.png"
FIG4_2_PATH = IMAGES_DIR / "fig4_2_residual_map_sequential_allocation_obstacle_field.png"
FIG4_1_DATA_PATH = OUTPUT_DATA_DIR / "fig4_1_static_responsibility_prior_current_maps.json"
FIG4_2_DATA_PATH = OUTPUT_DATA_DIR / "fig4_2_residual_map_sequential_allocation_obstacle_field.json"

MAP_KINDS = ("open_water", "obstacle_field", "peninsula_passage")
MAP_HEIGHT = 60
MAP_WIDTH = 80
SENSOR_RANGE_CELLS = 5

plt.rcParams.update(
    {
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "legend.fontsize": 7,
        "figure.titlesize": 11,
    }
)


def _ensure_dirs() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _cell_xy(cell: tuple[int, int]) -> tuple[int, int]:
    return int(cell[1]), int(cell[0])


def _plot_obstacles(ax: plt.Axes, nav_map: np.ndarray, *, alpha: float = 1.0) -> None:
    obstacle_rgba = np.zeros((*nav_map.shape, 4), dtype=float)
    obstacle_rgba[nav_map == OCCUPIED] = (0.0, 0.0, 0.0, alpha)
    ax.imshow(obstacle_rgba, origin="upper", interpolation="nearest")


def _plot_mask_overlay(
    ax: plt.Axes,
    mask: np.ndarray,
    color: tuple[float, float, float],
    *,
    alpha: float,
) -> None:
    rgba = np.zeros((*mask.shape, 4), dtype=float)
    rgba[np.asarray(mask, dtype=bool)] = (*color, alpha)
    ax.imshow(rgba, origin="upper", interpolation="nearest")


def _set_map_axes(ax: plt.Axes, nav_map: np.ndarray) -> None:
    h, w = nav_map.shape
    ax.set_xlim(-0.5, w - 0.5)
    ax.set_ylim(h - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(1.1)
        spine.set_color("#222222")


def generate_fig4_1() -> dict[str, object]:
    cmap = LinearSegmentedColormap.from_list(
        "responsibility_prior",
        ["#f4a261", "#f7f7f7", "#4da3ff"],
        N=256,
    )

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.55), constrained_layout=True)
    source_rows: list[dict[str, object]] = []
    image = None

    for ax, map_kind in zip(axes, MAP_KINDS):
        nav_map = create_world(h=MAP_HEIGHT, w=MAP_WIDTH, map_kind=map_kind)
        starts = rt2._select_two_usv_start_positions(nav_map)
        responsibility = rt2._build_responsibility_maps(
            nav_map,
            starts,
            sensor_range_cells=SENSOR_RANGE_CELLS,
        )
        score0 = np.asarray(responsibility["responsibility_score_map"][0], dtype=float)
        buffer_band = np.asarray(responsibility["buffer_band_mask"], dtype=bool)

        score_plot = np.ma.masked_where(nav_map == OCCUPIED, score0)
        image = ax.imshow(
            score_plot,
            cmap=cmap,
            vmin=-1.0,
            vmax=1.0,
            origin="upper",
            interpolation="nearest",
        )
        _plot_mask_overlay(ax, buffer_band, (0.62, 0.62, 0.62), alpha=0.55)
        _plot_obstacles(ax, nav_map)

        for usv_id, start in enumerate(starts):
            x, y = _cell_xy(start)
            marker_color = "#1479ff" if usv_id == 0 else "#ff8c1a"
            ax.scatter(
                [x],
                [y],
                s=80,
                color=marker_color,
                edgecolors="white",
                linewidths=1.3,
                zorder=5,
            )
            ax.text(
                x + 1.0,
                y - 1.0,
                f"U{usv_id}",
                color=marker_color,
                fontsize=9,
                weight="bold",
                zorder=6,
            )

        ax.set_title(map_kind, fontsize=9, pad=5)
        _set_map_axes(ax, nav_map)
        source_rows.append(
            {
                "map_kind": map_kind,
                "shape": [int(nav_map.shape[0]), int(nav_map.shape[1])],
                "starts_row_col": [[int(v) for v in start] for start in starts],
                "sensor_range_cells": SENSOR_RANGE_CELLS,
                "buffer_band_width_cells": int(rt2.RESPONSIBILITY_BUFFER_BAND_CELLS),
                "free_cells": int(np.count_nonzero(nav_map == FREE)),
                "buffer_band_cells": int(np.count_nonzero(buffer_band)),
                "score0_min": float(np.min(score0[nav_map == FREE])),
                "score0_max": float(np.max(score0[nav_map == FREE])),
            }
        )

    assert image is not None
    cbar = fig.colorbar(image, ax=axes, shrink=0.78, pad=0.015)
    cbar.set_label("responsibility score for U0", fontsize=8)
    handles = [
        Patch(facecolor="#4da3ff", edgecolor="none", label="U0-favored area"),
        Patch(facecolor="#f4a261", edgecolor="none", label="U1-favored area"),
        Patch(facecolor="#9e9e9e", edgecolor="none", alpha=0.65, label="buffer band"),
        Patch(facecolor="#000000", edgecolor="none", label="obstacle"),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="#1479ff",
            markeredgecolor="white",
            markersize=8,
            label="U0 start",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="#ff8c1a",
            markeredgecolor="white",
            markersize=8,
            label="U1 start",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.035),
        ncol=6,
        frameon=False,
        fontsize=7,
    )
    fig.savefig(FIG4_1_PATH, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    data = {
        "figure": str(FIG4_1_PATH),
        "method": "runtime _build_responsibility_maps over current formal map kinds",
        "maps": source_rows,
    }
    FIG4_1_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _capture_residual_record(max_iters: int = 20) -> tuple[dict[str, object], dict[str, object]]:
    original_joint_assign = rt2._joint_assign_two_usv_segments
    captured: list[dict[str, object]] = []

    def wrapped_joint_assign(*, team_state, policy_name, predicted_intensity, step):
        before = {
            "step": int(step),
            "nav_map_prior": np.array(team_state["nav_map_prior"], copy=True),
            "search_info_map": np.array(team_state["search_info_map"], copy=True),
            "robot_positions": [
                tuple(int(v) for v in local["robot_pos"])
                for local in team_state["usv_states"]
            ],
        }
        assignments, joint_summary = original_joint_assign(
            team_state=team_state,
            policy_name=policy_name,
            predicted_intensity=predicted_intensity,
            step=step,
        )
        assignment_copy: dict[int, dict[str, object]] = {}
        for usv_id, item in assignments.items():
            details = dict(item.get("plan_details", {}))
            assignment_copy[int(usv_id)] = {
                "segment_path": [
                    tuple(int(v) for v in cell)
                    for cell in item.get("segment_path", [])
                ],
                "visible_cells": {
                    tuple(int(v) for v in cell)
                    for cell in item.get("visible_cells", set())
                },
                "viewpoint_cell": (
                    tuple(int(v) for v in details["viewpoint_cell"])
                    if details.get("viewpoint_cell") is not None
                    else None
                ),
                "anchor_cell": (
                    tuple(int(v) for v in details["anchor_cell"])
                    if details.get("anchor_cell") is not None
                    else None
                ),
                "total_score": float(details.get("total_score", 0.0)),
                "overlap_penalty": float(item.get("overlap_penalty", 0.0)),
                "order_rank": int(item.get("order_rank", -1)),
            }
        captured.append(
            {
                **before,
                "assignments": assignment_copy,
                "joint_summary": dict(joint_summary),
            }
        )
        return assignments, joint_summary

    rt2._joint_assign_two_usv_segments = wrapped_joint_assign
    try:
        result = rt2.run_episode_two_usv_search_knownmap(
            episode_seed=0,
            max_iters=max_iters,
            policy_name="marine_knownmap_path_v2_infosampled_2usv",
            assignment_mode="coordinated",
            n_targets=3,
            map_kind="obstacle_field",
            map_height_cells=MAP_HEIGHT,
            map_width_cells=MAP_WIDTH,
            target_motion_mode="static",
            clue_acquisition_mode="ucb",
            anomaly_tail_quantile=0.90,
            anomaly_weight_lambda=1.25,
            path_safety_mode="soft_clearance_astar_v1",
            safe_nav_inflation_radius_cells=0,
            safe_nav_soft_clearance_radius_cells=1,
            safe_nav_lambda_clearance=1.0,
            team_path_avoidance_mode="reservation_v1",
            team_reservation_safety_distance_cells=1.5,
            team_reservation_lambda=1.0,
            viewpoint_generation_mode="simple_ring_v1",
            render=False,
        )
    finally:
        rt2._joint_assign_two_usv_segments = original_joint_assign

    if not captured:
        raise RuntimeError("No coordinated assignment was captured.")

    selected = captured[-1]
    return selected, result


def _cells_to_mask(cells: set[tuple[int, int]], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    for r, c in cells:
        if 0 <= r < shape[0] and 0 <= c < shape[1]:
            mask[r, c] = True
    return mask


def _plot_heatmap_panel(
    ax: plt.Axes,
    data: np.ndarray,
    nav_map: np.ndarray,
    *,
    title: str,
    vmin: float,
    vmax: float,
) -> object:
    plot_data = np.ma.masked_where(nav_map == OCCUPIED, data)
    image = ax.imshow(
        plot_data,
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
        origin="upper",
        interpolation="nearest",
    )
    _plot_obstacles(ax, nav_map)
    ax.set_title(title, fontsize=11, pad=6)
    _set_map_axes(ax, nav_map)
    return image


def _plot_segment(ax: plt.Axes, path: list[tuple[int, int]], *, color: str, label: str) -> None:
    if not path:
        return
    ys = [int(cell[0]) for cell in path]
    xs = [int(cell[1]) for cell in path]
    ax.plot(xs, ys, color=color, linewidth=2.4, marker="o", markersize=3.2, label=label, zorder=6)


def _plot_point(
    ax: plt.Axes,
    cell: tuple[int, int] | None,
    *,
    color: str,
    marker: str,
    label: str,
    size: int = 70,
) -> None:
    if cell is None:
        return
    x, y = _cell_xy(cell)
    scatter_kwargs = {
        "s": size,
        "color": color,
        "marker": marker,
        "label": label,
        "zorder": 7,
    }
    if marker not in {"x", "+", "1", "2", "3", "4"}:
        scatter_kwargs.update({"edgecolors": "white", "linewidths": 1.0})
    ax.scatter([x], [y], **scatter_kwargs)


def generate_fig4_2() -> dict[str, object]:
    record, result = _capture_residual_record(max_iters=20)
    nav_map = np.asarray(record["nav_map_prior"], dtype=int)
    base_map = np.asarray(record["search_info_map"], dtype=float)

    summary = record["joint_summary"]
    order_raw = summary.get("assignment_order")
    priority_raw = summary.get("reservation_priority_order")
    chosen_order = priority_raw or order_raw or (0, 1)
    order = tuple(int(v) for v in chosen_order)
    first_id, second_id = order
    first = record["assignments"][first_id]
    second = record["assignments"][second_id]
    first_visible = set(first["visible_cells"])
    second_visible = set(second["visible_cells"])

    residual_after_first = np.array(base_map, copy=True)
    for cell in first_visible:
        residual_after_first[cell] = 0.0
    residual_after_second = np.array(residual_after_first, copy=True)
    for cell in second_visible:
        residual_after_second[cell] = 0.0

    vmax = max(float(np.max(base_map)), 1e-9)
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.35), constrained_layout=True)
    axes_flat = axes.ravel()

    im = _plot_heatmap_panel(
        axes_flat[0],
        base_map,
        nav_map,
        title=f"(a) Shared search_info_map, step {record['step']}",
        vmin=0.0,
        vmax=vmax,
    )
    _plot_point(axes_flat[0], tuple(record["robot_positions"][0]), color="#1479ff", marker="o", label="U0")
    _plot_point(axes_flat[0], tuple(record["robot_positions"][1]), color="#ff8c1a", marker="o", label="U1")

    _plot_heatmap_panel(
        axes_flat[1],
        residual_after_first,
        nav_map,
        title=f"(b) U{first_id} selected; visible cells removed",
        vmin=0.0,
        vmax=vmax,
    )
    _plot_mask_overlay(axes_flat[1], _cells_to_mask(first_visible, nav_map.shape), (0.08, 0.47, 1.0), alpha=0.32)
    _plot_segment(axes_flat[1], first["segment_path"], color="#1479ff", label=f"U{first_id} segment")
    _plot_point(axes_flat[1], first["viewpoint_cell"], color="#ffdf2e", marker="x", label=f"U{first_id} viewpoint", size=95)
    _plot_point(axes_flat[1], first["anchor_cell"], color="#d936ff", marker="D", label=f"U{first_id} anchor", size=70)

    _plot_heatmap_panel(
        axes_flat[2],
        residual_after_first,
        nav_map,
        title=f"(c) U{second_id} plans on residual_map",
        vmin=0.0,
        vmax=vmax,
    )
    _plot_mask_overlay(axes_flat[2], _cells_to_mask(first_visible, nav_map.shape), (0.08, 0.47, 1.0), alpha=0.22)
    _plot_mask_overlay(axes_flat[2], _cells_to_mask(second_visible, nav_map.shape), (1.0, 0.55, 0.1), alpha=0.32)
    _plot_segment(axes_flat[2], second["segment_path"], color="#ff8c1a", label=f"U{second_id} segment")
    _plot_point(axes_flat[2], second["viewpoint_cell"], color="#ffdf2e", marker="x", label=f"U{second_id} viewpoint", size=95)
    _plot_point(axes_flat[2], second["anchor_cell"], color="#d936ff", marker="D", label=f"U{second_id} anchor", size=70)

    _plot_heatmap_panel(
        axes_flat[3],
        residual_after_second,
        nav_map,
        title="(d) Final residual after both segments",
        vmin=0.0,
        vmax=vmax,
    )
    overlap_cells = first_visible & second_visible
    _plot_mask_overlay(axes_flat[3], _cells_to_mask(first_visible, nav_map.shape), (0.08, 0.47, 1.0), alpha=0.22)
    _plot_mask_overlay(axes_flat[3], _cells_to_mask(second_visible, nav_map.shape), (1.0, 0.55, 0.1), alpha=0.22)
    if overlap_cells:
        _plot_mask_overlay(axes_flat[3], _cells_to_mask(overlap_cells, nav_map.shape), (0.55, 0.1, 0.75), alpha=0.42)
    _plot_segment(axes_flat[3], first["segment_path"], color="#1479ff", label=f"U{first_id} segment")
    _plot_segment(axes_flat[3], second["segment_path"], color="#ff8c1a", label=f"U{second_id} segment")

    cbar = fig.colorbar(im, ax=axes_flat, shrink=0.82, pad=0.012)
    cbar.set_label("search_info value", fontsize=8)
    handles = [
        Line2D([0], [0], color="#1479ff", linewidth=2.4, label="first / U0 path"),
        Line2D([0], [0], color="#ff8c1a", linewidth=2.4, label="second / U1 path"),
        Patch(facecolor="#1479ff", edgecolor="none", alpha=0.32, label="first visible cells"),
        Patch(facecolor="#ff8c1a", edgecolor="none", alpha=0.32, label="second visible cells"),
        Patch(facecolor="#000000", edgecolor="none", label="obstacle"),
    ]
    axes_flat[3].legend(
        handles=handles,
        loc="lower right",
        frameon=True,
        framealpha=0.88,
        fontsize=7,
        borderpad=0.4,
    )
    fig.suptitle(
        f"Residual-map sequential allocation on obstacle_field, order={order}",
        fontsize=11,
        y=1.025,
    )
    fig.savefig(FIG4_2_PATH, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    data = {
        "figure": str(FIG4_2_PATH),
        "method": "runtime coordinated assignment capture; residual_map cells zeroed by visible_cells",
        "episode_seed": 0,
        "map_kind": "obstacle_field",
        "target_motion_mode": "static",
        "clue_acquisition_mode": "ucb",
        "policy_name": "marine_knownmap_path_v2_infosampled_2usv",
        "assignment_mode": "coordinated",
        "path_safety_mode": "soft_clearance_astar_v1",
        "team_path_avoidance_mode": "reservation_v1",
        "viewpoint_generation_mode": "simple_ring_v1",
        "captured_step": int(record["step"]),
        "assignment_order": [int(v) for v in order],
        "joint_assignment_score": float(summary.get("joint_assignment_score", 0.0)),
        "joint_overlap_penalty": float(summary.get("joint_overlap_penalty", 0.0)),
        "first_usv": int(first_id),
        "second_usv": int(second_id),
        "first_visible_cells": int(len(first_visible)),
        "second_visible_cells": int(len(second_visible)),
        "overlap_visible_cells": int(len(first_visible & second_visible)),
        "first_segment_path": [[int(r), int(c)] for r, c in first["segment_path"]],
        "second_segment_path": [[int(r), int(c)] for r, c in second["segment_path"]],
        "first_viewpoint_cell": (
            [int(v) for v in first["viewpoint_cell"]]
            if first["viewpoint_cell"] is not None
            else None
        ),
        "second_viewpoint_cell": (
            [int(v) for v in second["viewpoint_cell"]]
            if second["viewpoint_cell"] is not None
            else None
        ),
        "result_completed_steps": int(result.get("completed_steps", 0)),
        "result_found_count": int(result.get("found_count", 0)),
    }
    FIG4_2_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> None:
    _ensure_dirs()
    fig4_1 = generate_fig4_1()
    fig4_2 = generate_fig4_2()
    print(json.dumps({"fig4_1": fig4_1, "fig4_2": fig4_2}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
