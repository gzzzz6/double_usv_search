from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap


def _find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "baseline_GP").is_dir():
            return parent
    raise RuntimeError("Could not locate repository root containing baseline_GP")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baseline_GP.core_map import create_world  # noqa: E402
from baseline_GP.holoocean_bridge.coordinate_adapter import (  # noqa: E402
    CoordinateAdapterConfig,
    grid_to_world,
)


PHASE_DIR = REPO_ROOT / "baseline_GP" / "results" / "holoocean_bridge_v1" / "phase2_coordinate_bridge"
VISUAL_DIR = PHASE_DIR / "visuals"
REPORT_DIR = PHASE_DIR / "reports"


def _plot_points_grid(ax: plt.Axes, starts: list[tuple[int, int]]) -> None:
    colors = ["#d62728", "#1f77b4"]
    for idx, cell in enumerate(starts):
        row, col = cell
        ax.scatter(col, row, s=70, c=colors[idx], edgecolors="white", linewidths=1.2, zorder=5)
        ax.text(
            col + 1.0,
            row,
            f"USV{idx} {cell}",
            color=colors[idx],
            fontsize=9,
            weight="bold",
            va="center",
        )


def _plot_points_world(
    ax: plt.Axes,
    starts: list[tuple[int, int]],
    config: CoordinateAdapterConfig,
) -> None:
    colors = ["#d62728", "#1f77b4"]
    for idx, cell in enumerate(starts):
        world = grid_to_world(cell, config)
        ax.scatter(world[0], world[1], s=70, c=colors[idx], edgecolors="white", linewidths=1.2, zorder=5)
        ax.text(
            world[0] + 6.0,
            world[1],
            f"USV{idx} [{world[0]:.0f}, {world[1]:.0f}]",
            color=colors[idx],
            fontsize=9,
            weight="bold",
            va="center",
        )


def _save_global_overlay(nav_map: np.ndarray, config: CoordinateAdapterConfig) -> Path:
    starts = [(25, 2), (35, 2)]
    h, w = nav_map.shape
    cell_size = float(config.cell_size_m)
    cmap = ListedColormap(["#c7e9f1", "#4b4b4b"])

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)

    ax = axes[0]
    ax.imshow(nav_map, cmap=cmap, origin="upper", interpolation="nearest")
    _plot_points_grid(ax, starts)
    ax.set_title("baseline_GP grid coordinates")
    ax.set_xlabel("col")
    ax.set_ylabel("row")
    ax.set_xlim(-1, 15)
    ax.set_ylim(42, 18)
    ax.grid(color="white", linewidth=0.35, alpha=0.45)
    ax.annotate(
        "col +1",
        xy=(3, 25),
        xytext=(8, 23.8),
        arrowprops={"arrowstyle": "->", "color": "#222222"},
        ha="center",
        va="center",
    )
    ax.annotate(
        "row +1",
        xy=(2, 26),
        xytext=(4, 29),
        arrowprops={"arrowstyle": "->", "color": "#222222"},
        ha="center",
        va="center",
    )

    ax = axes[1]
    extent = [
        -0.5 * cell_size,
        (w - 0.5) * cell_size,
        -(h - 0.5) * cell_size,
        0.5 * cell_size,
    ]
    ax.imshow(nav_map, cmap=cmap, origin="upper", interpolation="nearest", extent=extent)
    _plot_points_world(ax, starts, config)
    ax.set_title("HoloOcean world coordinates")
    ax.set_xlabel("x meters")
    ax.set_ylabel("y meters")
    ax.set_xlim(-5, 75)
    ax.set_ylim(-210, -90)
    ax.grid(color="white", linewidth=0.35, alpha=0.45)
    ax.annotate(
        "col +1 => x +5m",
        xy=(15, -125),
        xytext=(48, -115),
        arrowprops={"arrowstyle": "->", "color": "#222222"},
        ha="center",
        va="center",
    )
    ax.annotate(
        "row +1 => y -5m",
        xy=(10, -130),
        xytext=(36, -160),
        arrowprops={"arrowstyle": "->", "color": "#222222"},
        ha="center",
        va="center",
    )

    output_path = VISUAL_DIR / "phase2_coordinate_bridge_global_overlay.png"
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def _save_local_round_trip(config: CoordinateAdapterConfig) -> Path:
    start = (25, 2)
    neighbors = {
        "start": start,
        "east": (25, 3),
        "south": (26, 2),
        "north": (24, 2),
    }
    colors = {
        "start": "#d62728",
        "east": "#2ca02c",
        "south": "#9467bd",
        "north": "#ff7f0e",
    }

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    ax = axes[0]
    for label, cell in neighbors.items():
        row, col = cell
        ax.scatter(col, row, s=80, c=colors[label], edgecolors="white", linewidths=1.0, zorder=5)
        ax.text(col + 0.08, row + 0.08, f"{label}\n{cell}", fontsize=8, color=colors[label])
    ax.set_title("Local grid cells")
    ax.set_xlabel("col")
    ax.set_ylabel("row")
    ax.set_xlim(1.3, 3.7)
    ax.set_ylim(26.7, 23.3)
    ax.set_xticks(np.arange(1, 5))
    ax.set_yticks(np.arange(23, 28))
    ax.grid(True, linewidth=0.8, alpha=0.5)

    ax = axes[1]
    for label, cell in neighbors.items():
        world = grid_to_world(cell, config)
        ax.scatter(world[0], world[1], s=80, c=colors[label], edgecolors="white", linewidths=1.0, zorder=5)
        ax.text(
            world[0] + 0.6,
            world[1] + 0.6,
            f"{label}\n[{world[0]:.0f}, {world[1]:.0f}]",
            fontsize=8,
            color=colors[label],
        )
    ax.set_title("Same cells in HoloOcean x-y")
    ax.set_xlabel("x meters")
    ax.set_ylabel("y meters")
    ax.set_xlim(5, 20)
    ax.set_ylim(-135, -115)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linewidth=0.8, alpha=0.5)

    output_path = VISUAL_DIR / "phase2_coordinate_bridge_local_round_trip.png"
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def main() -> None:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    config = CoordinateAdapterConfig(cell_size_m=5.0)
    nav_map = create_world(h=60, w=80, map_kind="harbor_cove")
    global_path = _save_global_overlay(nav_map, config)
    local_path = _save_local_round_trip(config)

    report = [
        "# Phase 2 Coordinate Bridge Visuals",
        "",
        f"**Generated at:** {datetime.now().isoformat()}",
        "",
        "## Files",
        "",
        f"- Global overlay: `{global_path}`",
        f"- Local round-trip view: `{local_path}`",
        "",
        "## Reading Rule",
        "",
        "- Grid cell `(row, col)` maps to HoloOcean `[x, y, z]`.",
        "- `x = col * 5.0` meters.",
        "- `y = -row * 5.0` meters.",
        "- Increasing `col` moves right in both views.",
        "- Increasing `row` moves down in the grid and toward more negative `y` in HoloOcean.",
    ]
    (REPORT_DIR / "phase2_coordinate_bridge_visual_summary.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
