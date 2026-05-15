from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASELINE_DIR = PROJECT_ROOT / "baseline_GP"
IMAGES_DIR = PROJECT_ROOT / "images"
DATA_DIR = BASELINE_DIR / "results" / "_temp_run_scripts" / "figure_source_data"

if str(BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(BASELINE_DIR))

from core_map import FREE, OCCUPIED  # noqa: E402
import core_search_policy as policy  # noqa: E402
import marine_knownmap_runtime as rt1  # noqa: E402


OUT_PATH = IMAGES_DIR / "fig_anchor_cluster_process_obstacle_field_runtime.png"
DATA_PATH = DATA_DIR / "fig_anchor_cluster_process_obstacle_field_runtime.json"

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def _capture_replan_records() -> list[dict[str, object]]:
    original = rt1.select_knownmap_path_segment_policy
    records: list[dict[str, object]] = []
    current_context = {"seed": 0, "replan_index": 0}

    def wrapped_select_knownmap_path_segment_policy(*args, **kwargs):
        segment_path, details = original(*args, **kwargs)
        search_info_map = kwargs.get("search_info_map")
        nav_map_prior = kwargs.get("nav_map_prior")
        if search_info_map is not None and nav_map_prior is not None and details is not None:
            records.append(
                {
                    "episode_seed": int(current_context["seed"]),
                    "replan_index": int(current_context["replan_index"]),
                    "search_info_map": np.array(search_info_map, dtype=float, copy=True),
                    "nav_map_prior": np.array(nav_map_prior, dtype=int, copy=True),
                    "details": dict(details),
                    "robot_pos": tuple(int(v) for v in kwargs.get("robot_pos", (0, 0))),
                    "sensor_range": int(kwargs.get("sensor_range", 5)),
                }
            )
            current_context["replan_index"] += 1
        return segment_path, details

    rt1.select_knownmap_path_segment_policy = wrapped_select_knownmap_path_segment_policy
    try:
        for seed in range(10):
            current_context["seed"] = seed
            current_context["replan_index"] = 0
            rt1.run_episode_single_usv_search_knownmap(
                episode_seed=seed,
                max_iters=160,
                policy_name="marine_knownmap_path_v2_infosampled",
                n_targets=3,
                map_kind="obstacle_field",
                map_height_cells=40,
                map_width_cells=60,
                target_motion_mode="static",
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
    return records


def _selected_record(records: list[dict[str, object]]) -> tuple[int, dict[str, object], list[dict[str, object]], np.ndarray, float]:
    best_idx = -1
    best_score = -1.0
    best_clusters: list[dict[str, object]] = []
    best_high_mask: np.ndarray | None = None
    best_threshold = 0.0

    for idx, record in enumerate(records):
        search_info = np.asarray(record["search_info_map"], dtype=float)
        nav_map = np.asarray(record["nav_map_prior"], dtype=int)
        candidate_mask = nav_map == FREE
        high_mask, threshold = policy._high_value_mask(
            search_info,
            candidate_mask,
            rel_thr=policy.ANCHOR_CLUSTER_REL_THR,
            abs_thr=policy.ANCHOR_CLUSTER_ABS_THR,
        )
        clusters = policy._cluster_hotspots(
            search_info,
            candidate_mask,
            top_k=6,
        )
        if high_mask is None:
            continue
        areas = [len(component) for component in _connected_components_for_score(high_mask)]
        max_area = max(areas) if areas else 0
        total_area = sum(areas)
        selected_anchor = record["details"].get("anchor_cell")
        selected_bonus = 25.0 if selected_anchor is not None else 0.0
        compact_bonus = 120.0 if max_area <= 180 and total_area <= 260 else 0.0
        huge_penalty = 0.25 * max(0, max_area - 260)
        score = len(clusters) * 100.0 + compact_bonus + selected_bonus - huge_penalty
        if score > best_score:
            best_idx = idx
            best_score = score
            best_clusters = clusters
            best_high_mask = high_mask
            best_threshold = float(threshold)

    if best_idx < 0 or best_high_mask is None:
        raise RuntimeError("No usable hotspot clustering record was captured.")
    return best_idx, records[best_idx], best_clusters, best_high_mask, best_threshold


def _connected_components_for_score(high_mask: np.ndarray) -> list[list[tuple[int, int]]]:
    return policy._connected_components(
        high_mask,
        connectivity=policy.ANCHOR_CLUSTER_CONNECTIVITY,
    )


def _normalize_free(values: np.ndarray, nav_map: np.ndarray) -> np.ndarray:
    out = np.zeros_like(values, dtype=float)
    free = nav_map == FREE
    if not np.any(free):
        return out
    free_values = np.asarray(values[free], dtype=float)
    lo = float(np.min(free_values))
    hi = float(np.max(free_values))
    if hi <= lo + 1e-12:
        return out
    out[free] = (values[free] - lo) / (hi - lo)
    return out


def _cluster_component_masks(high_mask: np.ndarray) -> list[list[tuple[int, int]]]:
    return policy._connected_components(
        high_mask,
        connectivity=policy.ANCHOR_CLUSTER_CONNECTIVITY,
    )


def _plot_obstacles(ax: plt.Axes, nav_map: np.ndarray) -> None:
    rgba = np.zeros((*nav_map.shape, 4), dtype=float)
    rgba[nav_map == OCCUPIED] = (0.0, 0.0, 0.0, 1.0)
    ax.imshow(rgba, origin="upper", interpolation="nearest")


def _plot_cell_outline(ax: plt.Axes, mask: np.ndarray, color: str, linewidth: float = 2.0) -> None:
    ax.contour(
        mask.astype(float),
        levels=[0.5],
        colors=[color],
        linewidths=linewidth,
        origin="upper",
    )


def _set_axes(ax: plt.Axes, nav_map: np.ndarray) -> None:
    h, w = nav_map.shape
    ax.set_xlim(-0.5, w - 0.5)
    ax.set_ylim(h - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#1b4f9c")
        spine.set_linewidth(1.0)


def _scatter_cell(ax: plt.Axes, cell: tuple[int, int], **kwargs) -> None:
    ax.scatter([int(cell[1])], [int(cell[0])], **kwargs)


def generate() -> dict[str, object]:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    records = _capture_replan_records()
    idx, record, clusters, high_mask, threshold = _selected_record(records)
    search_info = np.asarray(record["search_info_map"], dtype=float)
    nav_map = np.asarray(record["nav_map_prior"], dtype=int)
    norm_info = _normalize_free(search_info, nav_map)
    components = _cluster_component_masks(high_mask)

    cluster_masks: list[np.ndarray] = []
    for component in components:
        mask = np.zeros_like(high_mask, dtype=bool)
        for cell in component:
            mask[cell] = True
        cluster_masks.append(mask)

    selected_clusters = clusters[: min(6, len(clusters))]

    fig, axes = plt.subplots(3, 1, figsize=(3.15, 8.6), constrained_layout=True)
    for ax, title in zip(
        axes,
        ("高价值区域聚类", "热点簇筛选", "加权中心 Anchor"),
    ):
        ax.imshow(norm_info, cmap="Blues", norm=Normalize(0.0, 1.0), origin="upper", interpolation="nearest")
        _plot_obstacles(ax, nav_map)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=5)
        _set_axes(ax, nav_map)

    # Panel 1: all high-value connected components.
    for mask in cluster_masks:
        _plot_cell_outline(axes[0], mask, color="white", linewidth=2.0)
        _plot_cell_outline(axes[0], mask, color="#2f64d6", linewidth=0.8)

    # Panel 2: clusters retained by runtime ranking.
    retained_masks = []
    retained_anchor_cells = {tuple(int(v) for v in item["anchor_cell"]) for item in selected_clusters}
    for mask in cluster_masks:
        if any(mask[cell] for cell in retained_anchor_cells):
            retained_masks.append(mask)
    for mask in retained_masks:
        _plot_cell_outline(axes[1], mask, color="#f2c300", linewidth=2.0)

    # Panel 3: weighted-center anchors selected by component scoring.
    for item in selected_clusters:
        anchor = tuple(int(v) for v in item["anchor_cell"])
        centroid = tuple(int(v) for v in item["anchor_centroid_cell"])
        _scatter_cell(
            axes[2],
            centroid,
            s=58,
            marker="o",
            color="#ffffff",
            edgecolors="#1b4f9c",
            linewidths=1.0,
            zorder=5,
        )
        _scatter_cell(
            axes[2],
            anchor,
            s=70,
            marker="D",
            color="#ffcc00",
            edgecolors="#1a1a1a",
            linewidths=0.8,
            zorder=6,
        )

    legend_handles = [
        Patch(facecolor="none", edgecolor="#f2c300", linewidth=2.0, label="保留热点簇"),
        plt.Line2D([0], [0], marker="D", color="none", markerfacecolor="#ffcc00", markeredgecolor="#1a1a1a", markersize=7, label="Anchor"),
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="#ffffff", markeredgecolor="#1b4f9c", markersize=7, label="加权中心"),
    ]
    axes[2].legend(handles=legend_handles, loc="lower left", fontsize=7, frameon=True, framealpha=0.9)
    fig.text(
        0.5,
        0.012,
        "Anchor 来自 search_info_map 高价值连通簇，按加权中心附近代表点确定。",
        ha="center",
        va="bottom",
        fontsize=8,
    )
    fig.savefig(OUT_PATH, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    data = {
        "figure": str(OUT_PATH),
        "map_kind": "obstacle_field",
        "map_height_cells": 40,
        "map_width_cells": 60,
        "episode_seed": int(record.get("episode_seed", 0)),
        "policy_name": "marine_knownmap_path_v2_infosampled",
        "clue_acquisition_mode": "ucb",
        "path_safety_mode": "soft_clearance_astar_v1",
        "viewpoint_generation_mode": "simple_ring_v1",
        "captured_record_index": int(idx),
        "captured_replan_index_in_episode": int(record.get("replan_index", -1)),
        "threshold": float(threshold),
        "n_components": int(len(components)),
        "n_retained_clusters": int(len(selected_clusters)),
        "clusters": [
            {
                "anchor_cell": [int(v) for v in item["anchor_cell"]],
                "anchor_centroid_cell": [int(v) for v in item["anchor_centroid_cell"]],
                "anchor_cluster_size": int(item["anchor_cluster_size"]),
                "anchor_cluster_peak": float(item["anchor_cluster_peak"]),
                "anchor_cluster_mean": float(item["anchor_cluster_mean"]),
                "anchor_value": float(item["anchor_value"]),
            }
            for item in selected_clusters
        ],
    }
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> None:
    print(json.dumps(generate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
