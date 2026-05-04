"""
Visualization helpers for the marine search baselines.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:
    from .core_map import FREE, OCCUPIED, UNKNOWN
except ImportError:
    from core_map import FREE, OCCUPIED, UNKNOWN


def _known_map_rgb(known_map: np.ndarray) -> np.ndarray:
    show = np.zeros_like(known_map, dtype=float)
    show[known_map == OCCUPIED] = 0.0
    show[known_map == UNKNOWN] = 0.5
    show[known_map == FREE] = 1.0
    return show


_TEAM_ROBOT_COLORS = ("dodgerblue", "darkorange")
_TEAM_TRAJECTORY_COLORS = ("cyan", "orange")
_TEAM_PLAN_COLORS = ("lime", "gold")
_TEAM_GOAL_COLORS = ("yellow", "red")
_TEAM_ANCHOR_COLORS = ("magenta", "orchid")


def _deduped_legend_items(ax) -> list[tuple[object, str]]:
    handles, labels = ax.get_legend_handles_labels()
    seen: set[str] = set()
    deduped: list[tuple[object, str]] = []
    for handle, label in zip(handles, labels):
        if not label or label in seen:
            continue
        seen.add(label)
        deduped.append((handle, label))
    return deduped


def _dedupe_legend(ax) -> None:
    deduped = _deduped_legend_items(ax)
    if deduped:
        ax.legend(
            [handle for handle, _ in deduped],
            [label for _, label in deduped],
            fontsize=8,
            loc="upper right",
        )


def _team_status_lines(
    *,
    usv_states: list[dict],
    joint_summary: dict | None = None,
    conflict_type: str | None = None,
    wait_applied_map: dict[int, bool] | None = None,
) -> list[str]:
    lines: list[str] = []
    if conflict_type is not None:
        lines.append(f"Conflict: {conflict_type}")
    if wait_applied_map:
        waited = [f"U{idx}" for idx, waited in sorted(wait_applied_map.items()) if waited]
        if waited:
            lines.append("Wait: " + ", ".join(waited))
    if joint_summary is not None:
        cross_ids = [
            f"U{idx}"
            for idx in range(len(usv_states))
            if bool(joint_summary.get(f"cross_region_selected_{idx}", False))
        ]
        if cross_ids:
            lines.append("Cross-region: " + ", ".join(cross_ids))
    return lines


def _draw_team_legend_panel(
    ax,
    *,
    legend_source_ax,
    usv_states: list[dict],
    joint_summary: dict | None = None,
    conflict_type: str | None = None,
    wait_applied_map: dict[int, bool] | None = None,
) -> None:
    ax.axis("off")
    ax.set_title("Legend", fontsize=10)

    status_lines = _team_status_lines(
        usv_states=usv_states,
        joint_summary=joint_summary,
        conflict_type=conflict_type,
        wait_applied_map=wait_applied_map,
    )
    legend_top = 0.98
    if status_lines:
        ax.text(
            0.02,
            legend_top,
            "\n".join(status_lines),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            color="black",
            bbox={"facecolor": "white", "alpha": 0.92, "edgecolor": "#d0d0d0"},
        )
        legend_top = 0.80

    deduped = _deduped_legend_items(legend_source_ax)
    if deduped:
        ax.legend(
            [handle for handle, _ in deduped],
            [label for _, label in deduped],
            fontsize=8,
            loc="upper left",
            bbox_to_anchor=(0.0, legend_top),
            borderaxespad=0.0,
            frameon=False,
            handlelength=2.2,
            handletextpad=0.6,
            labelspacing=0.45,
        )


def _draw_main_map(
    ax,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    trajectory: list[tuple[int, int]] | None = None,
    path: list[tuple[int, int]] | None = None,
    goal: tuple[int, int] | None = None,
    anchor: tuple[int, int] | None = None,
    step: int = 0,
    policy_name: str = "",
    show_true_targets: bool = True,
) -> None:
    ax.imshow(_known_map_rgb(known_map), cmap="gray", origin="upper", vmin=0, vmax=1)

    if trajectory and len(trajectory) > 1:
        xs = [p[1] for p in trajectory]
        ys = [p[0] for p in trajectory]
        ax.plot(xs, ys, color="cyan", linewidth=1.0, alpha=0.7, label="Trajectory")

    if path and len(path) > 1:
        xs = [p[1] for p in path]
        ys = [p[0] for p in path]
        ax.plot(xs, ys, color="lime", linewidth=1.5, label="Plan")

    if show_true_targets and target_positions.size > 0:
        unfound = target_positions[~found_mask]
        found = target_positions[found_mask]
        if len(unfound) > 0:
            ax.scatter(
                unfound[:, 1],
                unfound[:, 0],
                marker="*",
                s=130,
                c="red",
                label="Unfound Target",
                zorder=5,
            )
        if len(found) > 0:
            ax.scatter(
                found[:, 1],
                found[:, 0],
                marker="*",
                s=130,
                c="gold",
                edgecolors="black",
                linewidths=0.6,
                label="Found Target",
                zorder=5,
            )

    ax.scatter(
        robot_pos[1],
        robot_pos[0],
        marker="o",
        s=90,
        c="dodgerblue",
        label="Robot",
        zorder=6,
    )

    if goal is not None:
        ax.scatter(
            goal[1],
            goal[0],
            marker="x",
            s=100,
            c="yellow",
            label="Goal",
            zorder=6,
        )
    if anchor is not None:
        ax.scatter(
            anchor[1],
            anchor[0],
            marker="D",
            s=55,
            c="magenta",
            edgecolors="black",
            linewidths=0.6,
            label="Anchor",
            zorder=6,
        )

    ax.set_title("Main Map", fontsize=10)
    _dedupe_legend(ax)


def _draw_team_main_map(
    ax,
    known_map: np.ndarray,
    usv_states: list[dict],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    *,
    wait_applied_map: dict[int, bool] | None = None,
    conflict_type: str | None = None,
    responsibility_owner_map: np.ndarray | None = None,
    buffer_band_mask: np.ndarray | None = None,
    show_true_targets: bool = True,
) -> None:
    ax.imshow(_known_map_rgb(known_map), cmap="gray", origin="upper", vmin=0, vmax=1)
    if responsibility_owner_map is not None and buffer_band_mask is not None:
        overlay = np.zeros((*known_map.shape, 4), dtype=float)
        traversable_mask = known_map != OCCUPIED
        owner0_mask = traversable_mask & (np.asarray(responsibility_owner_map, dtype=int) == 0)
        owner1_mask = traversable_mask & (np.asarray(responsibility_owner_map, dtype=int) == 1)
        band_mask = traversable_mask & np.asarray(buffer_band_mask, dtype=bool)
        owner0_mask &= ~band_mask
        owner1_mask &= ~band_mask
        overlay[owner0_mask] = np.asarray([0.25, 0.55, 1.0, 0.12], dtype=float)
        overlay[owner1_mask] = np.asarray([1.0, 0.58, 0.16, 0.12], dtype=float)
        overlay[band_mask] = np.asarray([0.55, 0.55, 0.55, 0.18], dtype=float)
        ax.imshow(overlay, origin="upper")
        if np.any(owner0_mask):
            ax.plot([], [], color="dodgerblue", linewidth=6, alpha=0.35, label="Resp U0")
        if np.any(owner1_mask):
            ax.plot([], [], color="darkorange", linewidth=6, alpha=0.35, label="Resp U1")
        if np.any(band_mask):
            ax.plot([], [], color="gray", linewidth=6, alpha=0.45, label="Buffer Band")

    if show_true_targets and target_positions.size > 0:
        unfound = target_positions[~found_mask]
        found = target_positions[found_mask]
        if len(unfound) > 0:
            ax.scatter(
                unfound[:, 1],
                unfound[:, 0],
                marker="*",
                s=130,
                c="red",
                label="Unfound Target",
                zorder=5,
            )
        if len(found) > 0:
            ax.scatter(
                found[:, 1],
                found[:, 0],
                marker="*",
                s=130,
                c="gold",
                edgecolors="black",
                linewidths=0.6,
                label="Found Target",
                zorder=5,
            )

    next_cells: list[tuple[float, float]] = []
    for idx, local in enumerate(usv_states):
        robot_pos = tuple(int(v) for v in local.get("robot_pos", (0, 0)))
        trajectory = [tuple(int(v) for v in cell) for cell in local.get("trajectory", [])]
        committed_segment = [
            tuple(int(v) for v in cell) for cell in local.get("committed_segment", [])
        ]
        viewpoint = local.get("committed_viewpoint")
        anchor = local.get("committed_anchor")
        current_plan_details = local.get("current_plan_details") or {}

        if trajectory and len(trajectory) > 1:
            xs = [p[1] for p in trajectory]
            ys = [p[0] for p in trajectory]
            ax.plot(
                xs,
                ys,
                color=_TEAM_TRAJECTORY_COLORS[idx % len(_TEAM_TRAJECTORY_COLORS)],
                linewidth=1.2,
                alpha=0.8,
                label=f"Trajectory U{idx}",
            )

        if committed_segment and len(committed_segment) > 1:
            xs = [p[1] for p in committed_segment]
            ys = [p[0] for p in committed_segment]
            ax.plot(
                xs,
                ys,
                color=_TEAM_PLAN_COLORS[idx % len(_TEAM_PLAN_COLORS)],
                linewidth=1.8,
                alpha=0.95,
                label=f"Plan U{idx}",
            )
            next_cells.append((float(committed_segment[1][1]), float(committed_segment[1][0])))

        ax.scatter(
            robot_pos[1],
            robot_pos[0],
            marker="o",
            s=95,
            c=_TEAM_ROBOT_COLORS[idx % len(_TEAM_ROBOT_COLORS)],
            edgecolors="black",
            linewidths=0.7,
            label=f"USV {idx}",
            zorder=6,
        )

        if viewpoint is not None:
            ax.scatter(
                viewpoint[1],
                viewpoint[0],
                marker="x",
                s=110,
                c=_TEAM_GOAL_COLORS[idx % len(_TEAM_GOAL_COLORS)],
                linewidths=2.0,
                label=f"Viewpoint U{idx}",
                zorder=6,
            )
            if bool(current_plan_details.get("cross_region_selected", False)):
                ax.scatter(
                    viewpoint[1],
                    viewpoint[0],
                    marker="o",
                    s=165,
                    facecolors="none",
                    edgecolors="black",
                    linewidths=1.3,
                    label=f"Cross-region U{idx}",
                    zorder=6,
                )
        if anchor is not None:
            ax.scatter(
                anchor[1],
                anchor[0],
                marker="D",
                s=58,
                c=_TEAM_ANCHOR_COLORS[idx % len(_TEAM_ANCHOR_COLORS)],
                edgecolors="black",
                linewidths=0.6,
                label=f"Anchor U{idx}",
                zorder=6,
            )

        if wait_applied_map and bool(wait_applied_map.get(idx, False)):
            ax.scatter(
                robot_pos[1],
                robot_pos[0],
                marker="s",
                s=180,
                facecolors="none",
                edgecolors="red",
                linewidths=1.6,
                label=f"Wait U{idx}",
                zorder=7,
            )

    if conflict_type is not None and next_cells:
        conflict_x = float(np.mean([cell[0] for cell in next_cells]))
        conflict_y = float(np.mean([cell[1] for cell in next_cells]))
        ax.scatter(
            conflict_x,
            conflict_y,
            marker="X",
            s=140,
            c="red",
            edgecolors="black",
            linewidths=0.8,
            label="Conflict",
            zorder=7,
        )

    ax.set_title("Main Map", fontsize=10)


def _draw_heatmap_panel(
    ax,
    known_map: np.ndarray,
    heatmap: np.ndarray | None,
    title: str,
    robot_pos: tuple[int, int] | None = None,
    goal: tuple[int, int] | None = None,
    anchor: tuple[int, int] | None = None,
    candidate_cells: list[tuple[int, int]] | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    ax.imshow(_known_map_rgb(known_map), cmap="gray", origin="upper", vmin=0, vmax=1, alpha=0.35)
    ax.set_title(title, fontsize=10)
    if heatmap is None:
        ax.text(
            0.5,
            0.5,
            "N/A",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="black",
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
        )
    else:
        heatmap_data = np.asarray(heatmap, dtype=float)
        heatmap_masked = np.ma.masked_where(
            (known_map == OCCUPIED) | ~np.isfinite(heatmap_data),
            heatmap_data,
        )
        im = ax.imshow(
            heatmap_masked,
            cmap="viridis",
            origin="upper",
            alpha=0.9,
            vmin=vmin,
            vmax=vmax,
        )
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    if robot_pos is not None:
        ax.scatter(robot_pos[1], robot_pos[0], c="white", s=80, marker="o", edgecolors="black")
    if goal is not None:
        ax.scatter(goal[1], goal[0], c="red", s=80, marker="x")
    if anchor is not None:
        ax.scatter(anchor[1], anchor[0], c="magenta", s=45, marker="D", edgecolors="black")
    if candidate_cells:
        xs = [int(cell[1]) for cell in candidate_cells]
        ys = [int(cell[0]) for cell in candidate_cells]
        ax.scatter(
            xs,
            ys,
            s=22,
            facecolors="none",
            edgecolors="white",
            linewidths=0.8,
            alpha=0.9,
        )


def _overlay_team_heatmap_markers(
    ax,
    usv_states: list[dict],
) -> None:
    for idx, local in enumerate(usv_states):
        robot_pos = local.get("robot_pos")
        viewpoint = local.get("committed_viewpoint")
        anchor = local.get("committed_anchor")
        if robot_pos is not None:
            ax.scatter(
                robot_pos[1],
                robot_pos[0],
                s=82,
                marker="o",
                facecolors="white",
                edgecolors=_TEAM_ROBOT_COLORS[idx % len(_TEAM_ROBOT_COLORS)],
                linewidths=1.3,
                zorder=6,
            )
        if viewpoint is not None:
            ax.scatter(
                viewpoint[1],
                viewpoint[0],
                s=88,
                marker="x",
                c=_TEAM_GOAL_COLORS[idx % len(_TEAM_GOAL_COLORS)],
                linewidths=1.7,
                zorder=6,
            )
        if anchor is not None:
            ax.scatter(
                anchor[1],
                anchor[0],
                s=45,
                marker="D",
                c=_TEAM_ANCHOR_COLORS[idx % len(_TEAM_ANCHOR_COLORS)],
                edgecolors="black",
                linewidths=0.5,
                zorder=6,
            )


def _format_semantic_score_value(
    plan_details: dict,
    label: str,
    norm_key: str,
    raw_key: str,
) -> str:
    return (
        f"{label}={float(plan_details.get(norm_key, 0.0)):.2f}"
        f"[{float(plan_details.get(raw_key, 0.0)):.2f}]"
    )


def _format_score_line(plan_details: dict | None) -> str:
    if not plan_details:
        return "Scores | F=-- S=-- C=-- I=-- P=-- L=-- K=-- | Total=--"
    if plan_details.get("score_schema") == "infosampled_tree_d2":
        maneuver_penalty = float(plan_details.get("maneuver_penalty_raw", 0.0))
        return (
            "Score | "
            f"{_format_semantic_score_value(plan_details, 'Search Info Gain', 'marginal_information_gain_norm', 'marginal_information_gain_raw')} "
            f"{_format_semantic_score_value(plan_details, 'Recency Bias', 'recency_bias_norm', 'recency_bias_raw')} "
            f"{_format_semantic_score_value(plan_details, 'Exec Cost', 'execution_cost_norm', 'execution_cost_raw')} "
            f"Continuity Bonus={float(plan_details.get('continuity_bonus_raw', 0.0)):.2f} "
            f"T1={float(plan_details.get('tree_root_score_raw', 0.0)):.2f} "
            f"T2={float(plan_details.get('tree_child_score_raw', 0.0)):.2f} "
            f"G2={float(plan_details.get('tree_conditional_gain_lvl2', 0.0)):.2f} "
            f"R2={float(plan_details.get('tree_redundant_visible_ratio_lvl2', 0.0)):.2f} "
            f"M={int(plan_details.get('tree_first_layer_top_m', 0))} "
            f"N={int(plan_details.get('tree_second_layer_top_n', 0))} "
            f"{'Maneuver Penalty=' + format(maneuver_penalty, '.2f') + ' ' if maneuver_penalty > 0.0 else ''}"
            f"| Total={float(plan_details.get('tree_total_score', 0.0)):.2f}"
        )
    if plan_details.get("score_schema") == "infosampled":
        selected_rank = int(plan_details.get("selected_viewpoint_rank", 0))
        pool_size = int(plan_details.get("candidate_pool_size", 0))
        reachable_pool_size = int(plan_details.get("reachable_pool_size", 0))
        maneuver_penalty = float(plan_details.get("maneuver_penalty_raw", 0.0))
        return (
            "Score | "
            f"{_format_semantic_score_value(plan_details, 'Search Info Gain', 'marginal_information_gain_norm', 'marginal_information_gain_raw')} "
            f"{_format_semantic_score_value(plan_details, 'Recency Bias', 'recency_bias_norm', 'recency_bias_raw')} "
            f"{_format_semantic_score_value(plan_details, 'Exec Cost', 'execution_cost_norm', 'execution_cost_raw')} "
            f"Continuity Bonus={float(plan_details.get('continuity_bonus_raw', 0.0)):.2f} "
            f"{_format_semantic_score_value(plan_details, 'Sampling Priority', 'sampling_priority_norm', 'sampling_priority_raw')} "
            f"R={selected_rank} P={pool_size}->{reachable_pool_size} "
            f"{'Maneuver Penalty=' + format(maneuver_penalty, '.2f') + ' ' if maneuver_penalty > 0.0 else ''}"
            f"| Total={float(plan_details.get('total_score', 0.0)):.2f}"
        )
    if plan_details.get("score_schema") == "infofused":
        maneuver_penalty = float(plan_details.get("maneuver_penalty_raw", 0.0))
        return (
            "Score | "
            f"{_format_semantic_score_value(plan_details, 'Search Info Gain', 'marginal_information_gain_norm', 'marginal_information_gain_raw')} "
            f"{_format_semantic_score_value(plan_details, 'Recency Bias', 'recency_bias_norm', 'recency_bias_raw')} "
            f"{_format_semantic_score_value(plan_details, 'Exec Cost', 'execution_cost_norm', 'execution_cost_raw')} "
            f"Continuity Bonus={float(plan_details.get('continuity_bonus_raw', 0.0)):.2f} "
            f"{'Maneuver Penalty=' + format(maneuver_penalty, '.2f') + ' ' if maneuver_penalty > 0.0 else ''}"
            f"| Total={float(plan_details.get('total_score', 0.0)):.2f}"
        )
    if any(
        key in plan_details
        for key in (
            "explore_utility_norm",
            "focus_utility_norm",
            "recency_utility_norm",
            "exec_cost_norm",
        )
    ):
        return (
            "Scores | "
            f"EU={float(plan_details.get('explore_utility_norm', 0.0)):.2f}"
            f"[{float(plan_details.get('explore_utility_raw', 0.0)):.2f}] "
            f"FU={float(plan_details.get('focus_utility_norm', 0.0)):.2f}"
            f"[{float(plan_details.get('focus_utility_raw', 0.0)):.2f}] "
            f"RU={float(plan_details.get('recency_utility_norm', 0.0)):.2f}"
            f"[{float(plan_details.get('recency_utility_raw', 0.0)):.2f}] "
            f"EC={float(plan_details.get('exec_cost_norm', 0.0)):.2f}"
            f"[{float(plan_details.get('exec_cost_raw', 0.0)):.2f}] "
            f"K={float(plan_details.get('kappa_commit', 0.0)):.2f} "
            f"| Total={float(plan_details.get('total_score', 0.0)):.2f}"
        )
    return (
        "Scores | "
        f"F={float(plan_details.get('frontier_term_norm', 0.0)):.2f}"
        f"[{float(plan_details.get('frontier_term_raw', 0.0)):.2f}] "
        f"S={float(plan_details.get('staleness_term_norm', 0.0)):.2f}"
        f"[{float(plan_details.get('staleness_term_raw', 0.0)):.2f}] "
        f"C={float(plan_details.get('clue_term_norm', 0.0)):.2f}"
        f"[{float(plan_details.get('clue_term_raw', 0.0)):.2f}] "
        f"I={float(plan_details.get('intensity_term_norm', 0.0)):.2f}"
        f"[{float(plan_details.get('intensity_term_raw', 0.0)):.2f}] "
        f"P={float(plan_details.get('path_cost_term_norm', 0.0)):.2f}"
        f"[{float(plan_details.get('path_cost_term_raw', 0.0)):.2f}] "
        f"L={float(plan_details.get('raw_path_length_penalty_term', 0.0)):.2f} "
        f"K={float(plan_details.get('kappa_commit', 0.0)):.2f} "
        f"| Total={float(plan_details.get('total_score', 0.0)):.2f}"
    )


def _format_team_score_line(
    usv_states: list[dict],
    *,
    joint_summary: dict | None = None,
    conflict_type: str | None = None,
    wait_applied_map: dict[int, bool] | None = None,
) -> str:
    per_usv_parts: list[str] = []
    for idx, local in enumerate(usv_states):
        details = local.get("current_plan_details") or {}
        per_usv_parts.append(
            " ".join(
                [
                    f"U{idx}",
                    _format_semantic_score_value(
                        details,
                        "Search Info Gain",
                        "marginal_information_gain_norm",
                        "marginal_information_gain_raw",
                    ),
                    _format_semantic_score_value(
                        details,
                        "Recency Bias",
                        "recency_bias_norm",
                        "recency_bias_raw",
                    ),
                    _format_semantic_score_value(
                        details,
                        "Exec Cost",
                        "execution_cost_norm",
                        "execution_cost_raw",
                    ),
                    f"Continuity Bonus={float(details.get('continuity_bonus_raw', 0.0)):.2f}",
                    f"Total={float(details.get('total_score', 0.0)):.2f}",
                ]
            )
        )
    summary_parts = list(per_usv_parts)
    if joint_summary is not None:
        summary_parts.append(
            (
                f"Joint={float(joint_summary.get('joint_assignment_score', 0.0)):.2f} "
                f"Overlap={float(joint_summary.get('joint_overlap_penalty', 0.0)):.2f}"
            )
        )
        if "cross_region_count" in joint_summary:
            cross_ids = [
                f"U{idx}"
                for idx in range(len(usv_states))
                if bool(joint_summary.get(f"cross_region_selected_{idx}", False))
            ]
            summary_parts.append(
                "Cross=" + (",".join(cross_ids) if cross_ids else "0")
            )
    if conflict_type is not None:
        summary_parts.append(f"Conflict={conflict_type}")
    if wait_applied_map:
        waited = [f"U{idx}" for idx, waited in sorted(wait_applied_map.items()) if waited]
        if waited:
            summary_parts.append("Wait=" + ",".join(waited))
    return " | ".join(summary_parts) if summary_parts else "Team Scores | --"


def _render_search_figure(
    fig,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    trajectory: list[tuple[int, int]] | None = None,
    path: list[tuple[int, int]] | None = None,
    goal: tuple[int, int] | None = None,
    anchor: tuple[int, int] | None = None,
    step: int = 0,
    policy_name: str = "",
    clue_map: np.ndarray | None = None,
    clue_title: str = "GP Clue UCB",
    clue_heatmap_limits: tuple[float, float] | None = None,
    search_info_map: np.ndarray | None = None,
    intensity_map: np.ndarray | None = None,
    staleness_map: np.ndarray | None = None,
    plan_details: dict | None = None,
    show_true_targets: bool = True,
) -> None:
    fig.clear()
    clue_vmin = float(clue_heatmap_limits[0]) if clue_heatmap_limits is not None else None
    clue_vmax = float(clue_heatmap_limits[1]) if clue_heatmap_limits is not None else None
    if search_info_map is None:
        axes = fig.subplots(2, 2)
        _draw_main_map(
            axes[0, 0],
            known_map,
            robot_pos,
            target_positions,
            found_mask,
            trajectory=trajectory,
            path=path,
            goal=goal,
            anchor=anchor,
            step=step,
            policy_name=policy_name,
            show_true_targets=show_true_targets,
        )
        _draw_heatmap_panel(
            axes[0, 1],
            known_map,
            clue_map,
            title=clue_title,
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
            vmin=clue_vmin,
            vmax=clue_vmax,
        )
        _draw_heatmap_panel(
            axes[1, 0],
            known_map,
            intensity_map,
            title="Intensity",
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
        )
        _draw_heatmap_panel(
            axes[1, 1],
            known_map,
            staleness_map,
            title="Staleness",
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
        )
    else:
        axes = fig.subplots(2, 3)
        _draw_main_map(
            axes[0, 0],
            known_map,
            robot_pos,
            target_positions,
            found_mask,
            trajectory=trajectory,
            path=path,
            goal=goal,
            anchor=anchor,
            step=step,
            policy_name=policy_name,
            show_true_targets=show_true_targets,
        )
        _draw_heatmap_panel(
            axes[0, 1],
            known_map,
            search_info_map,
            title="Search Info",
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
            candidate_cells=(
                list(plan_details.get("sampled_viewpoint_pool_cells", []))
                if plan_details is not None
                else None
            ),
        )
        _draw_heatmap_panel(
            axes[0, 2],
            known_map,
            clue_map,
            title=clue_title,
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
            vmin=clue_vmin,
            vmax=clue_vmax,
        )
        _draw_heatmap_panel(
            axes[1, 0],
            known_map,
            intensity_map,
            title="Intensity",
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
        )
        _draw_heatmap_panel(
            axes[1, 1],
            known_map,
            staleness_map,
            title="Recency Bias",
            robot_pos=robot_pos,
            goal=goal,
            anchor=anchor,
        )
        axes[1, 2].axis("off")
        axes[1, 2].set_title("Sampling Priority", fontsize=10)
        axes[1, 2].text(
            0.02,
            0.98,
            (
                "Sampling Priority\n"
                f"Sampling mode: {plan_details.get('viewpoint_sampling_mode', 'n/a') if plan_details else 'n/a'}\n"
                f"Selected rank: {int(plan_details.get('selected_viewpoint_rank', 0)) if plan_details else 0}\n"
                f"Pool: {int(plan_details.get('candidate_pool_size', 0)) if plan_details else 0} -> "
                f"{int(plan_details.get('reachable_pool_size', 0)) if plan_details else 0} -> "
                f"{int(plan_details.get('a_star_checked_pool_size', 0)) if plan_details else 0}\n"
                f"Sampling Priority: {float(plan_details.get('sampling_priority_raw', 0.0)) if plan_details else 0.0:.2f}\n"
                f"Continuity Bonus: {float(plan_details.get('continuity_bonus_raw', 0.0)) if plan_details else 0.0:.2f}\n"
                f"Maneuver Penalty: {float(plan_details.get('maneuver_penalty_raw', 0.0)) if plan_details else 0.0:.2f}\n"
                f"Final-score winner: {bool(plan_details.get('selected_by_final_score', False)) if plan_details else False}"
            ),
            transform=axes[1, 2].transAxes,
            ha="left",
            va="top",
            fontsize=10,
        )
    title = f"Target Search | Step {step}"
    if policy_name:
        title += f" | {policy_name}"
    fig.suptitle(f"{title}\n{_format_score_line(plan_details)}", fontsize=11)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))


def plot_search_state(
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    trajectory: list[tuple[int, int]] | None = None,
    path: list[tuple[int, int]] | None = None,
    goal: tuple[int, int] | None = None,
    anchor: tuple[int, int] | None = None,
    step: int = 0,
    policy_name: str = "",
    clue_map: np.ndarray | None = None,
    clue_title: str = "GP Clue UCB",
    clue_heatmap_limits: tuple[float, float] | None = None,
    search_info_map: np.ndarray | None = None,
    intensity_map: np.ndarray | None = None,
    staleness_map: np.ndarray | None = None,
    plan_details: dict | None = None,
    show_true_targets: bool = True,
) -> None:
    """Render the target-search state on a dashboard.

    `show_true_targets=False` keeps the main panel restricted to online-visible
    navigation state instead of oracle target overlays.
    """
    plt.clf()
    fig = plt.gcf()
    if search_info_map is not None:
        fig.set_size_inches(15, 9)
    else:
        fig.set_size_inches(12, 9)
    _render_search_figure(
        fig,
        known_map,
        robot_pos,
        target_positions,
        found_mask,
        trajectory=trajectory,
        path=path,
        goal=goal,
        anchor=anchor,
        step=step,
        policy_name=policy_name,
        clue_map=clue_map,
        clue_title=clue_title,
        clue_heatmap_limits=clue_heatmap_limits,
        search_info_map=search_info_map,
        intensity_map=intensity_map,
        staleness_map=staleness_map,
        plan_details=plan_details,
        show_true_targets=show_true_targets,
    )
    plt.pause(0.05)


def save_search_snapshot(
    output_path: str | Path,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    trajectory: list[tuple[int, int]] | None = None,
    path: list[tuple[int, int]] | None = None,
    goal: tuple[int, int] | None = None,
    anchor: tuple[int, int] | None = None,
    step: int = 0,
    policy_name: str = "",
    clue_map: np.ndarray | None = None,
    clue_title: str = "GP Clue UCB",
    clue_heatmap_limits: tuple[float, float] | None = None,
    search_info_map: np.ndarray | None = None,
    intensity_map: np.ndarray | None = None,
    staleness_map: np.ndarray | None = None,
    plan_details: dict | None = None,
    show_true_targets: bool = True,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(15, 9) if search_info_map is not None else (12, 9))
    _render_search_figure(
        fig,
        known_map,
        robot_pos,
        target_positions,
        found_mask,
        trajectory=trajectory,
        path=path,
        goal=goal,
        anchor=anchor,
        step=step,
        policy_name=policy_name,
        clue_map=clue_map,
        clue_title=clue_title,
        clue_heatmap_limits=clue_heatmap_limits,
        search_info_map=search_info_map,
        intensity_map=intensity_map,
        staleness_map=staleness_map,
        plan_details=plan_details,
        show_true_targets=show_true_targets,
    )
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_team_search_state(
    known_map: np.ndarray,
    usv_states: list[dict],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    *,
    step: int = 0,
    policy_name: str = "",
    clue_map: np.ndarray | None = None,
    clue_title: str = "GP Clue UCB",
    clue_heatmap_limits: tuple[float, float] | None = None,
    search_info_map: np.ndarray | None = None,
    intensity_map: np.ndarray | None = None,
    staleness_map: np.ndarray | None = None,
    wait_applied_map: dict[int, bool] | None = None,
    conflict_type: str | None = None,
    joint_summary: dict | None = None,
    responsibility_owner_map: np.ndarray | None = None,
    buffer_band_mask: np.ndarray | None = None,
    show_true_targets: bool = True,
) -> None:
    plt.clf()
    fig = plt.gcf()
    fig.set_size_inches(17, 9)
    fig.clear()

    grid = fig.add_gridspec(2, 4, width_ratios=(1.45, 1.0, 1.0, 0.78))
    main_ax = fig.add_subplot(grid[:, 0])
    heatmap_axes = [
        fig.add_subplot(grid[0, 1]),
        fig.add_subplot(grid[0, 2]),
        fig.add_subplot(grid[1, 1]),
        fig.add_subplot(grid[1, 2]),
    ]
    legend_ax = fig.add_subplot(grid[:, 3])

    _draw_team_main_map(
        main_ax,
        known_map=known_map,
        usv_states=usv_states,
        target_positions=target_positions,
        found_mask=found_mask,
        wait_applied_map=wait_applied_map,
        conflict_type=conflict_type,
        responsibility_owner_map=responsibility_owner_map,
        buffer_band_mask=buffer_band_mask,
        show_true_targets=show_true_targets,
    )
    _draw_team_legend_panel(
        legend_ax,
        legend_source_ax=main_ax,
        usv_states=usv_states,
        joint_summary=joint_summary,
        conflict_type=conflict_type,
        wait_applied_map=wait_applied_map,
    )

    candidate_union: list[tuple[int, int]] = []
    seen_candidates: set[tuple[int, int]] = set()
    for local in usv_states:
        details = local.get("current_plan_details") or {}
        for cell in details.get("sampled_viewpoint_pool_cells", []):
            candidate = tuple(int(v) for v in cell)
            if candidate in seen_candidates:
                continue
            seen_candidates.add(candidate)
            candidate_union.append(candidate)

    titles_and_heatmaps = [
        ("Search Info", search_info_map, candidate_union),
        (clue_title, clue_map, None),
        ("Intensity", intensity_map, None),
        ("Recency Bias", staleness_map, None),
    ]
    clue_vmin = float(clue_heatmap_limits[0]) if clue_heatmap_limits is not None else None
    clue_vmax = float(clue_heatmap_limits[1]) if clue_heatmap_limits is not None else None

    for panel_idx, (ax, (title, heatmap, candidate_cells)) in enumerate(
        zip(heatmap_axes, titles_and_heatmaps)
    ):
        _draw_heatmap_panel(
            ax,
            known_map,
            heatmap,
            title=title,
            candidate_cells=candidate_cells,
            vmin=clue_vmin if panel_idx == 1 else None,
            vmax=clue_vmax if panel_idx == 1 else None,
        )
        _overlay_team_heatmap_markers(ax, usv_states)

    title = f"Target Search | Team Step {step}"
    if policy_name:
        title += f" | {policy_name}"
    fig.suptitle(
        f"{title}\n{_format_team_score_line(usv_states, joint_summary=joint_summary, conflict_type=conflict_type, wait_applied_map=wait_applied_map)}",
        fontsize=11,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    plt.pause(0.05)


def save_heatmap_snapshot(
    output_path: str | Path,
    known_map: np.ndarray,
    heatmap: np.ndarray,
    title: str,
    robot_pos: tuple[int, int] | None = None,
    goal: tuple[int, int] | None = None,
    anchor: tuple[int, int] | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(7, 6))
    ax.imshow(_known_map_rgb(known_map), cmap="gray", origin="upper", vmin=0, vmax=1, alpha=0.35)
    heatmap_data = np.asarray(heatmap, dtype=float)
    heatmap_masked = np.ma.masked_where(
        (known_map == OCCUPIED) | ~np.isfinite(heatmap_data),
        heatmap_data,
    )
    im = ax.imshow(
        heatmap_masked,
        cmap="viridis",
        origin="upper",
        alpha=0.9,
        vmin=vmin,
        vmax=vmax,
    )
    if robot_pos is not None:
        ax.scatter(robot_pos[1], robot_pos[0], c="white", s=80, marker="o", edgecolors="black")
    if goal is not None:
        ax.scatter(goal[1], goal[0], c="red", s=80, marker="x")
    if anchor is not None:
        ax.scatter(anchor[1], anchor[0], c="magenta", s=45, marker="D", edgecolors="black")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def save_mode_timeline(
    output_path: str | Path,
    mode_history: list[str],
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(7, 2.5))
    if mode_history:
        y = np.array([0 if mode == "SEARCH" else 1 for mode in mode_history], dtype=float)
        x = np.arange(1, len(mode_history) + 1)
        ax.step(x, y, where="post", linewidth=2.0)
        ax.set_yticks([0, 1], labels=["SEARCH", "REACQUIRE"])
        ax.set_xlim(1, len(mode_history))
    else:
        ax.set_yticks([0, 1], labels=["SEARCH", "REACQUIRE"])
        ax.set_xlim(0, 1)
    ax.set_xlabel("Step")
    ax.set_title("Mode Timeline")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
