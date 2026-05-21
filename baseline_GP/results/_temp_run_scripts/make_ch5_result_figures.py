"""
Chapter 5 result figures — coordination & anomaly comparisons.
Reads table_payload.json; outputs PNG, SVG, CSV, and verification report.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT = Path(__file__).resolve().parents[3]
_PAYLOAD = (
    _PROJECT / "baseline_GP" / "results"
    / "paper_obstacle_field_mainline_20260510"
    / "paper_tables_merged_for_report" / "table_payload.json"
)
_OUT_DIR = _PROJECT / "baseline_GP" / "results" / "thesis_ch5_figures"
_IMG_DIR = _PROJECT / "images"
for _d in (_OUT_DIR, _IMG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with open(_PAYLOAD, "r", encoding="utf-8") as f:
    payload = json.load(f)

MAP_ORDER = ("open_water", "obstacle_field", "peninsula_passage")
MAP_LABELS = ("Open water", "Obstacle field", "Peninsula passage")
COLORS = {
    "independent": "#2196F3",
    "coordinated": "#FF9800",
    "UCB": "#2196F3",
    "anomaly_upper_tail": "#E53935",
    "single_static": "#90CAF9",
    "single_random_walk": "#1565C0",
    "two_static": "#FFCC80",
    "two_random_walk": "#E65100",
}
METHOD_LABELS = {
    "independent": "Independent",
    "coordinated": "Coordinated",
    "UCB": "UCB",
    "anomaly_upper_tail": "Anomaly",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_num(val: str) -> float | None:
    """Parse a numeric value, returning None for N/A."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s.upper() == "N/A" or s == "":
        return None
    # Handle signed strings like "+20.0"
    return float(s)


def _extract_map_rows(rows: list[list], map_col: int, method_col: int | None = None):
    """Return {map: {method: {col_name: value}}} for non-总体 rows."""
    header = rows[0]
    out: dict[str, dict[str | None, dict[str, float | None]]] = {}
    for row in rows[1:]:
        map_name = str(row[map_col]).strip()
        if map_name == "总体":
            continue
        method = str(row[method_col]).strip() if method_col is not None else None
        values = {}
        for i, col_name in enumerate(header):
            if i in (map_col, method_col if method_col is not None else -1):
                continue
            values[col_name] = _parse_num(row[i])
        out.setdefault(map_name, {})[method] = values
    return out


def _setup_figure(figsize=(10, 7)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    return fig, ax


def _save_fig(fig, stem: str):
    for fmt, dpi in [(".png", 300), (".svg", None)]:
        p = _OUT_DIR / f"{stem}{fmt}"
        fig.savefig(str(p), dpi=dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
        print(f"  saved: {p}")
    # Copy PNG to images/
    png_src = _OUT_DIR / f"{stem}.png"
    png_dst = _IMG_DIR / f"{stem}.png"
    png_dst.write_bytes(png_src.read_bytes())
    print(f"  copied: {png_dst}")


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

# --- 5.3 Coordination data ---
data_two_static = _extract_map_rows(payload["two_static_assignment"], map_col=0, method_col=1)
data_two_random = _extract_map_rows(payload["two_random_assignment"], map_col=0, method_col=1)

# --- 5.4 Anomaly data ---
data_single_static_anomaly = _extract_map_rows(payload["single_static_anomaly"], map_col=0, method_col=1)
data_single_random_anomaly = _extract_map_rows(payload["single_random_anomaly"], map_col=0, method_col=1)
data_two_static_anomaly = _extract_map_rows(payload["two_static_anomaly"], map_col=0, method_col=1)
data_two_random_anomaly = _extract_map_rows(payload["two_random_anomaly"], map_col=0, method_col=1)

# --- Delta data ---
# single_anomaly_delta / two_anomaly_delta have: 目标模式, 地图, ΔT_first, ΔT_all, Δsuccess（百分点）, ...
def _extract_delta_rows(rows: list[list], mode_col: int = 0, map_col: int = 1):
    header = rows[0]
    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for row in rows[1:]:
        mode = str(row[mode_col]).strip()
        map_name = str(row[map_col]).strip()
        if map_name == "总体":
            continue
        values = {}
        for i, col_name in enumerate(header):
            if i in (mode_col, map_col):
                continue
            values[col_name] = _parse_num(row[i])
        out.setdefault(mode, {})[map_name] = values
    return out

data_single_delta = _extract_delta_rows(payload["single_anomaly_delta"])
data_two_delta = _extract_delta_rows(payload["two_anomaly_delta"])

# ===================================================================
# Figure 1: 5.3 Coordination Task Metrics (success + detection)
# ===================================================================
def make_fig5_3_task_metrics():
    metrics = ["success（%）", "detection（%）"]
    metric_labels = ["Success (%)", "Detection (%)"]
    datasets = [
        ("Static", data_two_static),
        ("Random walk", data_two_random),
    ]
    methods = ["independent", "coordinated"]
    n_maps = len(MAP_ORDER)
    x = np.arange(n_maps)
    bar_width = 0.35

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.patch.set_facecolor("white")

    for col, (metric, mlabel) in enumerate(zip(metrics, metric_labels)):
        for row, (mode_label, data) in enumerate(datasets):
            ax = axes[row][col]
            ax.set_facecolor("white")
            for mi, method in enumerate(methods):
                vals = []
                for mp in MAP_ORDER:
                    v = data.get(mp, {}).get(method, {}).get(metric)
                    vals.append(v if v is not None else 0)
                offset = (mi - 0.5) * bar_width + bar_width / 2
                ax.bar(x + offset, vals, bar_width,
                       color=COLORS[method], edgecolor="white", linewidth=0.5,
                       label=METHOD_LABELS[method])

            ax.set_title(f"{mode_label} — {mlabel}", fontsize=11, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(MAP_LABELS, fontsize=9)
            ax.set_ylabel(mlabel, fontsize=10)
            ax.set_ylim(0, 105)
            ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
            ax.tick_params(axis="y", labelsize=9)
            if row == 0 and col == 0:
                ax.legend(fontsize=9, loc="upper right")

    fig.suptitle("Dual-USV Task Completion: Independent vs Coordinated", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    _save_fig(fig, "fig5_3_coordination_task_metrics")
    plt.close(fig)
    return {
        "data_keys": ["two_static_assignment", "two_random_assignment"],
        "maps_used": list(MAP_ORDER),
        "metrics_used": metrics,
    }


# ===================================================================
# Figure 2: 5.3 Coordination Behavior Metrics (duplicate + cross)
# ===================================================================
def make_fig5_3_behavior_metrics():
    metrics = ["duplicate（%）", "cross（%）"]
    metric_labels = ["Duplicate (%)", "Cross (%)"]
    datasets = [
        ("Static", data_two_static),
        ("Random walk", data_two_random),
    ]
    methods = ["independent", "coordinated"]
    n_maps = len(MAP_ORDER)
    x = np.arange(n_maps)
    bar_width = 0.35

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.patch.set_facecolor("white")

    for col, (metric, mlabel) in enumerate(zip(metrics, metric_labels)):
        for row, (mode_label, data) in enumerate(datasets):
            ax = axes[row][col]
            ax.set_facecolor("white")
            for mi, method in enumerate(methods):
                vals = []
                for mp in MAP_ORDER:
                    v = data.get(mp, {}).get(method, {}).get(metric)
                    vals.append(v if v is not None else 0)
                offset = (mi - 0.5) * bar_width + bar_width / 2
                ax.bar(x + offset, vals, bar_width,
                       color=COLORS[method], edgecolor="white", linewidth=0.5,
                       label=METHOD_LABELS[method])

            ax.set_title(f"{mode_label} — {mlabel}", fontsize=11, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(MAP_LABELS, fontsize=9)
            ax.set_ylabel(mlabel, fontsize=10)
            ax.set_ylim(0, max(ax.get_ylim()[1] * 1.15, 55))
            ax.tick_params(axis="y", labelsize=9)
            if row == 0 and col == 0:
                ax.legend(fontsize=9, loc="upper right")

    fig.suptitle("Dual-USV Coordination Behavior: Independent vs Coordinated", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    _save_fig(fig, "fig5_3_coordination_behavior_metrics")
    plt.close(fig)
    return {
        "data_keys": ["two_static_assignment", "two_random_assignment"],
        "maps_used": list(MAP_ORDER),
        "metrics_used": metrics,
    }


# ===================================================================
# Figure 3: 5.4 Anomaly Success Line Chart
# ===================================================================
def make_fig5_4_anomaly_success_lines():
    panels = [
        ("Single-USV — Static", data_single_static_anomaly),
        ("Single-USV — Random walk", data_single_random_anomaly),
        ("Two-USV Coordinated — Static", data_two_static_anomaly),
        ("Two-USV Coordinated — Random walk", data_two_random_anomaly),
    ]
    clue_modes = ["UCB", "anomaly_upper_tail"]
    markers = {"UCB": "o", "anomaly_upper_tail": "s"}
    x_idx = np.arange(len(MAP_ORDER))

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    fig.patch.set_facecolor("white")

    for idx, (title, data) in enumerate(panels):
        ax = axes[idx // 2][idx % 2]
        ax.set_facecolor("white")
        for cm in clue_modes:
            vals = []
            for mp in MAP_ORDER:
                v = data.get(mp, {}).get(cm, {}).get("success（%）")
                vals.append(v if v is not None else None)
            ax.plot(x_idx, vals, marker=markers[cm], linewidth=2, markersize=8,
                    color=COLORS[cm], label=METHOD_LABELS[cm])

        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xticks(x_idx)
        ax.set_xticklabels(MAP_LABELS, fontsize=9)
        ax.set_ylabel("Success (%)", fontsize=10)
        ax.set_ylim(0, 105)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
        ax.tick_params(axis="y", labelsize=9)
        if idx == 0:
            ax.legend(fontsize=9)

    fig.suptitle("UCB vs Anomaly-Upper-Tail: Success Rate", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    _save_fig(fig, "fig5_4_anomaly_success_lines")
    plt.close(fig)
    return {
        "data_keys": ["single_static_anomaly", "single_random_anomaly",
                       "two_static_anomaly", "two_random_anomaly"],
        "maps_used": list(MAP_ORDER),
        "metrics_used": ["success（%）"],
    }


# ===================================================================
# Figure 4: 5.4 Anomaly Delta Bars
# ===================================================================
def make_fig5_4_anomaly_delta_bars():
    groups = [
        ("single_static", data_single_delta.get("static", {})),
        ("single_random_walk", data_single_delta.get("random_walk", {})),
        ("two_static", data_two_delta.get("static", {})),
        ("two_random_walk", data_two_delta.get("random_walk", {})),
    ]
    group_labels = ["Single\nstatic", "Single\nrandom", "Two-USV\nstatic", "Two-USV\nrandom"]

    n_maps = len(MAP_ORDER)
    n_groups = len(groups)
    x = np.arange(n_maps)
    bar_width = 0.8 / n_groups

    # Top: Δsuccess, Bottom: ΔT_first
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.patch.set_facecolor("white")
    ax1.set_facecolor("white")
    ax2.set_facecolor("white")

    for gi, (gname, gdata) in enumerate(groups):
        # Δsuccess
        delta_success = []
        for mp in MAP_ORDER:
            v = gdata.get(mp, {}).get("Δsuccess（百分点）")
            delta_success.append(v if v is not None else 0)
        offset = (gi - (n_groups - 1) / 2) * bar_width
        ax1.bar(x + offset, delta_success, bar_width,
                color=COLORS[gname], edgecolor="white", linewidth=0.5,
                label=group_labels[gi].replace("\n", " "))

        # ΔT_first
        delta_tfirst = []
        for mp in MAP_ORDER:
            v = gdata.get(mp, {}).get("ΔT_first")
            delta_tfirst.append(v if v is not None else 0)
        ax2.bar(x + offset, delta_tfirst, bar_width,
                color=COLORS[gname], edgecolor="white", linewidth=0.5,
                label=group_labels[gi].replace("\n", " "))

    # Format ax1 — Δsuccess
    ax1.set_title("Δ Success (Anomaly − UCB)", fontsize=11, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(MAP_LABELS, fontsize=9)
    ax1.set_ylabel("Δ Success (pp)", fontsize=10)
    ax1.axhline(y=0, color="black", linewidth=0.8, linestyle="--")
    ax1.legend(fontsize=8, ncol=4, loc="upper left")
    ax1.tick_params(axis="y", labelsize=9)

    # Format ax2 — ΔT_first
    ax2.set_title("Δ T_first (Anomaly − UCB)", fontsize=11, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(MAP_LABELS, fontsize=9)
    ax2.set_ylabel("Δ T_first (steps)", fontsize=10)
    ax2.axhline(y=0, color="black", linewidth=0.8, linestyle="--")
    ax2.legend(fontsize=8, ncol=4, loc="lower left")
    ax2.tick_params(axis="y", labelsize=9)

    fig.suptitle("Anomaly − UCB: Delta by Map and Configuration", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    _save_fig(fig, "fig5_4_anomaly_delta_bars")
    plt.close(fig)
    return {
        "data_keys": ["single_anomaly_delta", "two_anomaly_delta"],
        "maps_used": list(MAP_ORDER),
        "metrics_used": ["Δsuccess（百分点）", "ΔT_first"],
    }


# ===================================================================
# CSV export
# ===================================================================
def _write_csv(stem: str, rows: list[list[str]]):
    p = _OUT_DIR / f"{stem}.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        for row in rows:
            f.write(",".join(str(c) for c in row) + "\n")
    print(f"  csv: {p}")


def export_csvs():
    # Fig 5.3 task metrics CSV
    _write_csv("fig5_3_coordination_task_metrics_data", [
        ["Figure", "Mode", "Map", "Method", "Success (%)", "Detection (%)"],
        *[
            ["fig5_3_task", mode, mp, method,
             data.get(mp, {}).get(method, {}).get("success（%）"),
             data.get(mp, {}).get(method, {}).get("detection（%）")]
            for mode, data in [("static", data_two_static), ("random_walk", data_two_random)]
            for mp in MAP_ORDER
            for method in ["independent", "coordinated"]
        ]
    ])

    # Fig 5.3 behavior metrics CSV
    _write_csv("fig5_3_coordination_behavior_metrics_data", [
        ["Figure", "Mode", "Map", "Method", "Duplicate (%)", "Cross (%)"],
        *[
            ["fig5_3_behavior", mode, mp, method,
             data.get(mp, {}).get(method, {}).get("duplicate（%）"),
             data.get(mp, {}).get(method, {}).get("cross（%）")]
            for mode, data in [("static", data_two_static), ("random_walk", data_two_random)]
            for mp in MAP_ORDER
            for method in ["independent", "coordinated"]
        ]
    ])

    # Fig 5.4 anomaly success CSV
    _write_csv("fig5_4_anomaly_success_lines_data", [
        ["Figure", "Panel", "Map", "Clue Mode", "Success (%)"],
        *[
            ["fig5_4_success", panel, mp, cm,
             data.get(mp, {}).get(cm, {}).get("success（%）")]
            for panel, data in [
                ("single_static", data_single_static_anomaly),
                ("single_random_walk", data_single_random_anomaly),
                ("two_static", data_two_static_anomaly),
                ("two_random_walk", data_two_random_anomaly),
            ]
            for mp in MAP_ORDER
            for cm in ["UCB", "anomaly_upper_tail"]
        ]
    ])

    # Fig 5.4 delta CSV
    _write_csv("fig5_4_anomaly_delta_bars_data", [
        ["Figure", "Group", "Map", "Δsuccess (pp)", "ΔT_first"],
        *[
            ["fig5_4_delta", gname, mp,
             gdata.get(mp, {}).get("Δsuccess（百分点）"),
             gdata.get(mp, {}).get("ΔT_first")]
            for gname, gdata in [
                ("single_static", data_single_delta.get("static", {})),
                ("single_random_walk", data_single_delta.get("random_walk", {})),
                ("two_static", data_two_delta.get("static", {})),
                ("two_random_walk", data_two_delta.get("random_walk", {})),
            ]
            for mp in MAP_ORDER
        ]
    ])


# ===================================================================
# Verification report
# ===================================================================
def _check_harbor_cove(data_dict) -> bool:
    """Check if 'harbor_cove' appears in any dataset."""
    for key, rows in payload.items():
        if isinstance(rows, list):
            for row in rows:
                for cell in row:
                    if isinstance(cell, str) and "harbor_cove" in cell.lower():
                        return True
    return False


def _check_missing_values(data_dict) -> dict[str, list[str]]:
    """Find entries with N/A or missing values."""
    missing: dict[str, list[str]] = {}
    for key, rows in payload.items():
        if not isinstance(rows, list):
            continue
        problems = []
        for i, row in enumerate(rows[1:], start=1):
            for j, cell in enumerate(row):
                if isinstance(cell, str) and cell.strip().upper() == "N/A":
                    problems.append(f"row={i}, col={rows[0][j]}, map={row[0]}")
        if problems:
            missing[key] = problems
    return missing


def make_report(figure_info: list[dict]):
    output_files = sorted([f.name for f in _OUT_DIR.iterdir() if f.is_file()])

    report = {
        "input_json": str(_PAYLOAD),
        "output_directory": str(_OUT_DIR),
        "output_files": output_files,
        "figures": figure_info,
        "harbor_cove_present": _check_harbor_cove(payload),
        "overall_rows_excluded": True,
        "overall_rows_comment": "总体 (overall) rows exist in payload but are NOT plotted in any figure.",
        "missing_values": _check_missing_values(payload),
    }

    rp = _OUT_DIR / "figure_generation_report.json"
    json.dump(report, rp.open("w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nReport: {rp}")
    return report


# ===================================================================
# Main
# ===================================================================
def main():
    print("=== Ch5 Figure Generation ===\n")
    os.chdir(str(_PROJECT))

    figure_info = []

    print("[1/4] Fig 5.3 — Coordination Task Metrics")
    figure_info.append(make_fig5_3_task_metrics())

    print("\n[2/4] Fig 5.3 — Coordination Behavior Metrics")
    figure_info.append(make_fig5_3_behavior_metrics())

    print("\n[3/4] Fig 5.4 — Anomaly Success Lines")
    figure_info.append(make_fig5_4_anomaly_success_lines())

    print("\n[4/4] Fig 5.4 — Anomaly Delta Bars")
    figure_info.append(make_fig5_4_anomaly_delta_bars())

    print("\n[CSV] Exporting data CSVs")
    export_csvs()

    print("\n[Report] Generating verification report")
    report = make_report(figure_info)

    print(f"\n=== Done ===")
    print(f"Figures in: {_OUT_DIR}")
    print(f"Copies in: {_IMG_DIR}")
    print(f"Harbor cove present: {report['harbor_cove_present']}")
    missing_count = sum(len(v) for v in report["missing_values"].values())
    print(f"Missing (N/A) entries: {missing_count}")


if __name__ == "__main__":
    main()
