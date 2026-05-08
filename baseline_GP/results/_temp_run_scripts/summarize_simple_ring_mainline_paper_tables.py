"""
Summarize simple_ring_v1 mainline experiment results into paper-ready tables.

Sections: 6.2 (single USV UCB baseline), 6.3 (two-USV assignment comparison),
6.4 (anomaly ablation). Outputs .csv and a single paper_tables_markdown.md.

n = total episode count (ALL=30, per-map=10), NOT count of non-empty values.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

# ── paths ───────────────────────────────────────────────────────────────────
ROOT = Path(r"F:\pythonprojects\baseline_GP\results\paper_simple_ring_mainline_20260505")
OUT = ROOT / "paper_tables"
MD_PATH = OUT / "paper_tables_markdown.md"

MAP_ORDER = ("ALL", "open_water", "harbor_cove", "peninsula_passage")
DECIMALS = 3

# ── helpers ──────────────────────────────────────────────────────────────────

def fmt_val(v: float) -> str:
    return f"{v:.{DECIMALS}f}"

def _float(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def safe_mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sum(vals) / len(vals)

def safe_std(vals: list[float], mean: float | None = None) -> float | None:
    n = len(vals)
    if n < 2:
        return None
    if mean is None:
        mean = safe_mean(vals)
        if mean is None:
            return None
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))

def load_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open("r", encoding="utf-8-sig")))


# ── unified stats helper ────────────────────────────────────────────────────

class RowStats:
    """Computed statistics for a filtered set of rows."""

    __slots__ = (
        "n_total", "n_first_detected", "n_all_found", "success_all_found",
        "metrics",  # dict[str, dict]  key -> {mean, std}
    )

    def __init__(
        self,
        rows: list[dict],
        metric_keys: list[str],
        map_kind: str | None = None,
    ) -> None:
        subset = rows if map_kind is None else [r for r in rows if r.get("map_kind") == map_kind]
        self.n_total = len(subset)

        fd_vals = [_float(r.get("time_to_first_detection")) for r in subset]
        self.n_first_detected = sum(1 for v in fd_vals if v is not None)

        af_vals = [_float(r.get("time_to_all_found")) for r in subset]
        self.n_all_found = sum(1 for v in af_vals if v is not None)
        self.success_all_found = self.n_all_found / self.n_total if self.n_total > 0 else 0.0

        self.metrics: dict[str, dict] = {}
        for key in metric_keys:
            vals = [v for v in (_float(r.get(key)) for r in subset) if v is not None]
            m = safe_mean(vals)
            s = safe_std(vals, m)
            self.metrics[key] = {"mean": m, "std": s, "n_valid": len(vals)}

    def mean(self, key: str) -> float | None:
        return self.metrics.get(key, {}).get("mean")

    def std(self, key: str) -> float | None:
        return self.metrics.get(key, {}).get("std")

    def n_valid(self, key: str) -> int:
        return self.metrics.get(key, {}).get("n_valid", 0)


# ── validation ───────────────────────────────────────────────────────────────

def validate_and_load() -> dict[str, list[dict]]:
    """Load all 6 groups, run mandatory checks, return {group_key: rows}."""
    groups_spec = {
        "single_static":                 {"n": 60, "motion": "static",      "sys": "single", "assign": None},
        "single_random_walk":            {"n": 60, "motion": "random_walk", "sys": "single", "assign": None},
        "two_coordinated_static":        {"n": 60, "motion": "static",      "sys": "two_usv", "assign": "coordinated"},
        "two_coordinated_random_walk":   {"n": 60, "motion": "random_walk", "sys": "two_usv", "assign": "coordinated"},
        "two_independent_static":        {"n": 60, "motion": "static",      "sys": "two_usv", "assign": "independent"},
        "two_independent_random_walk":   {"n": 60, "motion": "random_walk", "sys": "two_usv", "assign": "independent"},
    }
    errors: list[str] = []
    data: dict[str, list[dict]] = {}

    for group, spec in groups_spec.items():
        d = ROOT / group
        if not d.exists():
            errors.append(f"missing dir: {d}")
            continue
        config_path = d / "config_snapshot.json"
        csv_path = d / "episode_results.csv"
        if not config_path.exists():
            errors.append(f"{group}: missing config_snapshot.json")
        if not csv_path.exists():
            errors.append(f"{group}: missing episode_results.csv")
            continue

        config = json.loads(config_path.read_text(encoding="utf-8"))
        vp = config.get("viewpoint_generation_mode")
        if vp != "simple_ring_v1":
            errors.append(f"{group}: config viewpoint_generation_mode={vp}")

        rows = load_csv(csv_path)
        if len(rows) != spec["n"]:
            errors.append(f"{group}: expected {spec['n']} rows, got {len(rows)}")

        vp_set = {r.get("viewpoint_generation_mode") for r in rows}
        if vp_set != {"simple_ring_v1"}:
            errors.append(f"{group}: csv viewpoint_generation_modes={vp_set}")

        ps_set = {r.get("path_safety_mode") for r in rows}
        if ps_set != {"soft_clearance_astar_v1"}:
            errors.append(f"{group}: csv path_safety_modes={ps_set}")

        motion_set = {r.get("target_motion_mode") for r in rows}
        if motion_set != {spec["motion"]}:
            errors.append(f"{group}: csv motions={motion_set}")

        clue_set = {r.get("clue_acquisition_mode") for r in rows}
        if clue_set != {"ucb", "anomaly_upper_tail"}:
            errors.append(f"{group}: csv clue_modes={clue_set}")

        map_set = {r.get("map_kind") for r in rows}
        if map_set != {"open_water", "harbor_cove", "peninsula_passage"}:
            errors.append(f"{group}: csv maps={map_set}")

        anomaly_rows = [r for r in rows if r.get("clue_acquisition_mode") == "anomaly_upper_tail"]
        q_set = {r.get("anomaly_tail_quantile") for r in anomaly_rows}
        l_set = {r.get("anomaly_weight_lambda") for r in anomaly_rows}
        if q_set != {"0.9"}:
            errors.append(f"{group}: anomaly_tail_quantile={q_set}")
        if l_set != {"1.25"}:
            errors.append(f"{group}: anomaly_weight_lambda={l_set}")

        if spec["assign"] is not None:
            a_set = {r.get("assignment_mode") for r in rows}
            if a_set != {spec["assign"]}:
                errors.append(f"{group}: assignment_mode={a_set}")
            tm_set = {r.get("team_path_avoidance_mode") for r in rows}
            if tm_set != {"reservation_v1"}:
                errors.append(f"{group}: team_path_avoidance_mode={tm_set}")

        data[group] = rows
        print(f"  OK {group}: {len(rows)} rows, q={q_set}, lambda={l_set}")

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        raise AssertionError(f"{len(errors)} validation error(s)")
    return data


# ── CSV/MD writers ───────────────────────────────────────────────────────────

def write_csv(path: Path, headers: list[str], body: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in body:
            w.writerow(row)

def write_md_section(title: str) -> None:
    with MD_PATH.open("a", encoding="utf-8") as f:
        f.write(f"## {title}\n\n")

def write_md_table(title: str, headers: list[str], body: list[list[str]]) -> None:
    with MD_PATH.open("a", encoding="utf-8") as f:
        f.write(f"### {title}\n\n")
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for row in body:
            f.write("| " + " | ".join(row) + " |\n")
        f.write("\n\n")


# ═══════════════════════════════════════════════════════════════════════════════
# 6.2  Single USV UCB baseline
# ═══════════════════════════════════════════════════════════════════════════════

METRICS_6_2 = [
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length",
]

HEADERS_6_2 = [
    "map_kind", "n", "n_first_detected", "n_all_found",
    "time_to_first_detection_mean", "time_to_first_detection_std",
    "time_to_all_found_mean", "time_to_all_found_std",
    "success_all_found_mean",
    "detection_rate_mean",
    "found_count_mean",
    "known_free_observation_ratio_final_mean",
    "path_length_mean",
]


def build_6_2_table(data: dict[str, list[dict]], group_key: str, out_name: str, label: str) -> str:
    rows = data[group_key]
    ucb = [r for r in rows if r.get("clue_acquisition_mode") == "ucb"]

    body: list[list[str]] = []
    for mk in MAP_ORDER:
        stats = RowStats(ucb, METRICS_6_2, mk if mk != "ALL" else None)
        row = [
            mk,
            str(stats.n_total),
            str(stats.n_first_detected),
            str(stats.n_all_found),
            fmt_val(stats.mean("time_to_first_detection")) if stats.mean("time_to_first_detection") is not None else "N/A",
            fmt_val(stats.std("time_to_first_detection")) if stats.std("time_to_first_detection") is not None else "N/A",
            fmt_val(stats.mean("time_to_all_found")) if stats.mean("time_to_all_found") is not None else "N/A",
            fmt_val(stats.std("time_to_all_found")) if stats.std("time_to_all_found") is not None else "N/A",
            fmt_val(stats.success_all_found),
            fmt_val(stats.mean("detection_rate")) if stats.mean("detection_rate") is not None else "N/A",
            fmt_val(stats.mean("found_count")) if stats.mean("found_count") is not None else "N/A",
            fmt_val(stats.mean("known_free_observation_ratio_final")) if stats.mean("known_free_observation_ratio_final") is not None else "N/A",
            fmt_val(stats.mean("path_length")) if stats.mean("path_length") is not None else "N/A",
        ]
        body.append(row)

    csv_path = OUT / out_name
    write_csv(csv_path, HEADERS_6_2, body)
    write_md_table(label, HEADERS_6_2, body)
    return out_name


# ═══════════════════════════════════════════════════════════════════════════════
# 6.3  Two-USV assignment comparison (UCB only)
# ═══════════════════════════════════════════════════════════════════════════════

METRICS_6_3 = [
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "wait_count_total",
    "reservation_wait_fallback_count",
]

HEADERS_6_3_MAIN = [
    "target_motion_mode", "map_kind", "assignment_mode", "n",
    "n_first_detected", "n_all_found",
    "time_to_first_detection_mean",
    "time_to_all_found_mean",
    "success_all_found_mean",
    "detection_rate_mean",
    "found_count_mean",
    "known_free_observation_ratio_final_mean",
    "duplicate_viewpoint_ratio_mean",
    "cross_region_assignment_ratio_mean",
    "wait_count_total_mean",
    "reservation_wait_fallback_count_mean",
]


def build_6_3_main_table(
    data: dict[str, list[dict]],
    motion: str,
    out_name: str,
    label: str,
) -> str:
    coord_key = f"two_coordinated_{motion}"
    indep_key = f"two_independent_{motion}"

    coord_rows = [r for r in data[coord_key] if r.get("clue_acquisition_mode") == "ucb"]
    indep_rows = [r for r in data[indep_key] if r.get("clue_acquisition_mode") == "ucb"]

    body: list[list[str]] = []
    for assign_label, rows in [("independent", indep_rows), ("coordinated", coord_rows)]:
        for mk in MAP_ORDER:
            stats = RowStats(rows, METRICS_6_3, mk if mk != "ALL" else None)
            row = [
                motion, mk, assign_label, str(stats.n_total),
                str(stats.n_first_detected),
                str(stats.n_all_found),
                fmt_val(stats.mean("time_to_first_detection")) if stats.mean("time_to_first_detection") is not None else "N/A",
                fmt_val(stats.mean("time_to_all_found")) if stats.mean("time_to_all_found") is not None else "N/A",
                fmt_val(stats.success_all_found),
                fmt_val(stats.mean("detection_rate")) if stats.mean("detection_rate") is not None else "N/A",
                fmt_val(stats.mean("found_count")) if stats.mean("found_count") is not None else "N/A",
                fmt_val(stats.mean("known_free_observation_ratio_final")) if stats.mean("known_free_observation_ratio_final") is not None else "N/A",
                fmt_val(stats.mean("duplicate_viewpoint_ratio")) if stats.mean("duplicate_viewpoint_ratio") is not None else "N/A",
                fmt_val(stats.mean("cross_region_assignment_ratio")) if stats.mean("cross_region_assignment_ratio") is not None else "N/A",
                fmt_val(stats.mean("wait_count_total")) if stats.mean("wait_count_total") is not None else "N/A",
                fmt_val(stats.mean("reservation_wait_fallback_count")) if stats.mean("reservation_wait_fallback_count") is not None else "N/A",
            ]
            body.append(row)

    csv_path = OUT / out_name
    write_csv(csv_path, HEADERS_6_3_MAIN, body)
    write_md_table(label, HEADERS_6_3_MAIN, body)
    return out_name


DELTA_METRICS_6_3 = [
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "wait_count_total",
]

HEADERS_6_3_DELTA = [
    "map_kind",
    "delta_time_to_first_detection_mean",
    "delta_time_to_all_found_mean",
    "delta_success_all_found_mean",
    "delta_detection_rate_mean",
    "delta_found_count_mean",
    "delta_duplicate_viewpoint_ratio_mean",
    "delta_cross_region_assignment_ratio_mean",
    "delta_wait_count_total_mean",
]


def build_6_3_delta_table(
    data: dict[str, list[dict]],
    motion: str,
    out_name: str,
    label: str,
) -> str:
    coord_key = f"two_coordinated_{motion}"
    indep_key = f"two_independent_{motion}"

    coord_rows = [r for r in data[coord_key] if r.get("clue_acquisition_mode") == "ucb"]
    indep_rows = [r for r in data[indep_key] if r.get("clue_acquisition_mode") == "ucb"]

    body: list[list[str]] = []
    for mk in MAP_ORDER:
        c_sub = coord_rows if mk == "ALL" else [r for r in coord_rows if r.get("map_kind") == mk]
        i_sub = indep_rows if mk == "ALL" else [r for r in indep_rows if r.get("map_kind") == mk]

        c_map: dict[tuple, dict] = {}
        for r in c_sub:
            c_map[(r.get("map_kind", ""), r.get("episode_seed", ""))] = r
        i_map: dict[tuple, dict] = {}
        for r in i_sub:
            i_map[(r.get("map_kind", ""), r.get("episode_seed", ""))] = r

        row = [mk]
        for metric in DELTA_METRICS_6_3:
            deltas: list[float] = []
            for key in c_map:
                if key in i_map:
                    cv = _float(c_map[key].get(metric))
                    iv = _float(i_map[key].get(metric))
                    if cv is not None and iv is not None:
                        deltas.append(cv - iv)
            m = safe_mean(deltas)
            row.append(fmt_val(m) if m is not None else "N/A")

        # success_all_found delta
        saf_deltas: list[float] = []
        for key in c_map:
            if key in i_map:
                c_saf = 1.0 if c_map[key].get("time_to_all_found", "") not in (None, "", "N/A") else 0.0
                i_saf = 1.0 if i_map[key].get("time_to_all_found", "") not in (None, "", "N/A") else 0.0
                saf_deltas.append(c_saf - i_saf)
        saf_m = safe_mean(saf_deltas)
        row.insert(3, fmt_val(saf_m) if saf_m is not None else "N/A")

        body.append(row)

    csv_path = OUT / out_name
    write_csv(csv_path, HEADERS_6_3_DELTA, body)
    write_md_table(label, HEADERS_6_3_DELTA, body)
    return out_name


# ═══════════════════════════════════════════════════════════════════════════════
# 6.4  Anomaly ablation
# ═══════════════════════════════════════════════════════════════════════════════

METRICS_6_4 = [
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
]

HEADERS_6_4_MAIN = [
    "map_kind", "clue_acquisition_mode", "n",
    "n_first_detected", "n_all_found",
    "time_to_first_detection_mean",
    "time_to_all_found_mean",
    "success_all_found_mean",
    "detection_rate_mean",
    "found_count_mean",
    "known_free_observation_ratio_final_mean",
]

DELTA_METRICS_6_4 = [
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
]

HEADERS_6_4_DELTA = [
    "map_kind",
    "delta_time_to_first_detection_mean",
    "delta_time_to_all_found_mean",
    "delta_success_all_found_mean",
    "delta_detection_rate_mean",
    "delta_found_count_mean",
    "delta_known_free_observation_ratio_final_mean",
]


def build_6_4_main_table(
    data: dict[str, list[dict]],
    group_key: str,
    out_name: str,
    label: str,
) -> str:
    rows = data[group_key]

    body: list[list[str]] = []
    for clue_mode in ("ucb", "anomaly_upper_tail"):
        clue_rows = [r for r in rows if r.get("clue_acquisition_mode") == clue_mode]
        for mk in MAP_ORDER:
            stats = RowStats(clue_rows, METRICS_6_4, mk if mk != "ALL" else None)
            row = [
                mk, clue_mode, str(stats.n_total),
                str(stats.n_first_detected),
                str(stats.n_all_found),
                fmt_val(stats.mean("time_to_first_detection")) if stats.mean("time_to_first_detection") is not None else "N/A",
                fmt_val(stats.mean("time_to_all_found")) if stats.mean("time_to_all_found") is not None else "N/A",
                fmt_val(stats.success_all_found),
                fmt_val(stats.mean("detection_rate")) if stats.mean("detection_rate") is not None else "N/A",
                fmt_val(stats.mean("found_count")) if stats.mean("found_count") is not None else "N/A",
                fmt_val(stats.mean("known_free_observation_ratio_final")) if stats.mean("known_free_observation_ratio_final") is not None else "N/A",
            ]
            body.append(row)

    csv_path = OUT / out_name
    write_csv(csv_path, HEADERS_6_4_MAIN, body)
    write_md_table(label, HEADERS_6_4_MAIN, body)
    return out_name


def build_6_4_delta_table(
    data: dict[str, list[dict]],
    group_key: str,
    out_name: str,
    label: str,
) -> str:
    rows = data[group_key]
    anom_rows = [r for r in rows if r.get("clue_acquisition_mode") == "anomaly_upper_tail"]
    ucb_rows = [r for r in rows if r.get("clue_acquisition_mode") == "ucb"]

    body: list[list[str]] = []
    for mk in MAP_ORDER:
        a_sub = anom_rows if mk == "ALL" else [r for r in anom_rows if r.get("map_kind") == mk]
        u_sub = ucb_rows if mk == "ALL" else [r for r in ucb_rows if r.get("map_kind") == mk]

        a_map: dict[tuple, dict] = {}
        for r in a_sub:
            a_map[(r.get("map_kind", ""), r.get("episode_seed", ""))] = r
        u_map: dict[tuple, dict] = {}
        for r in u_sub:
            u_map[(r.get("map_kind", ""), r.get("episode_seed", ""))] = r

        row = [mk]
        for metric in DELTA_METRICS_6_4:
            deltas: list[float] = []
            for key in a_map:
                if key in u_map:
                    av = _float(a_map[key].get(metric))
                    uv = _float(u_map[key].get(metric))
                    if av is not None and uv is not None:
                        deltas.append(av - uv)
            m = safe_mean(deltas)
            row.append(fmt_val(m) if m is not None else "N/A")

        # success_all_found delta
        saf_deltas: list[float] = []
        for key in a_map:
            if key in u_map:
                a_saf = 1.0 if a_map[key].get("time_to_all_found", "") not in (None, "", "N/A") else 0.0
                u_saf = 1.0 if u_map[key].get("time_to_all_found", "") not in (None, "", "N/A") else 0.0
                saf_deltas.append(a_saf - u_saf)
        saf_m = safe_mean(saf_deltas)
        row.insert(3, fmt_val(saf_m) if saf_m is not None else "N/A")

        body.append(row)

    csv_path = OUT / out_name
    write_csv(csv_path, HEADERS_6_4_DELTA, body)
    write_md_table(label, HEADERS_6_4_DELTA, body)
    return out_name


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=== Phase 1: Load & Validate ===")
    data = validate_and_load()

    OUT.mkdir(parents=True, exist_ok=True)

    # Clear markdown
    MD_PATH.write_text("# Paper Tables — simple_ring_v1 Mainline\n\n", encoding="utf-8")
    generated: list[str] = []

    # ── 6.2 ──────────────────────────────────────────────────────────────
    print("\n=== 6.2 Single USV UCB baseline ===")
    write_md_section("6.2 单 USV 已知地图搜索基线及目标运动鲁棒性实验")
    generated.append(build_6_2_table(data, "single_static", "table_6_2_static_single_ucb.csv", "表 6-1 单艇 static UCB 结果"))
    generated.append(build_6_2_table(data, "single_random_walk", "table_6_2_random_walk_single_ucb.csv", "表 6-2 单艇 random_walk UCB 结果"))

    # ── 6.3 ──────────────────────────────────────────────────────────────
    print("\n=== 6.3 Two-USV assignment comparison ===")
    write_md_section("6.3 双 USV 协同搜索实验")
    generated.append(build_6_3_main_table(data, "static", "table_6_3_static_two_usv_ucb_assignment.csv", "表 6-3 static coordinated vs independent"))
    generated.append(build_6_3_main_table(data, "random_walk", "table_6_3_random_walk_two_usv_ucb_assignment.csv", "表 6-4 random_walk coordinated vs independent"))
    generated.append(build_6_3_delta_table(data, "static", "table_6_3_static_two_usv_coord_minus_independent.csv", "表 6-5 static coordinated − independent 差值"))
    generated.append(build_6_3_delta_table(data, "random_walk", "table_6_3_random_walk_two_usv_coord_minus_independent.csv", "表 6-6 random_walk coordinated − independent 差值"))

    # ── 6.4 ──────────────────────────────────────────────────────────────
    print("\n=== 6.4 Anomaly ablation ===")
    write_md_section("6.4 anomaly-aware acquisition 消融实验")

    six_four_groups = [
        "single_static",
        "single_random_walk",
        "two_coordinated_static",
        "two_coordinated_random_walk",
    ]
    six_four_labels_main = [
        "单艇 static UCB vs anomaly",
        "单艇 random_walk UCB vs anomaly",
        "双艇 coordinated static UCB vs anomaly",
        "双艇 coordinated random_walk UCB vs anomaly",
    ]

    table_idx = 7
    for group_key, lbl in zip(six_four_groups, six_four_labels_main):
        main_name = f"table_6_4_{group_key}_ucb_vs_anomaly.csv"
        main_label = f"表 6-{table_idx} {lbl}"
        generated.append(build_6_4_main_table(data, group_key, main_name, main_label))
        table_idx += 1

    for group_key, lbl in zip(six_four_groups, six_four_labels_main):
        delta_name = f"table_6_4_{group_key}_delta_anomaly_minus_ucb.csv"
        delta_label = f"表 6-{table_idx} {lbl} — anomaly − UCB 差值"
        generated.append(build_6_4_delta_table(data, group_key, delta_name, delta_label))
        table_idx += 1

    # ── n-compliance check ───────────────────────────────────────────────
    print("\n=== n-compliance check ===")
    n_ok = True
    tables_with_n = 0
    for fname in generated:
        csv_path = OUT / fname
        rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8-sig")))
        if "n" not in rows[0]:
            # delta tables don't have n column — skip
            continue
        tables_with_n += 1
        for r in rows:
            mk = r.get("map_kind", "?")
            n_val = r.get("n", "?")
            expected = "30" if mk == "ALL" else "10"
            if n_val != expected:
                print(f"  FAIL {fname}: map_kind={mk}, n={n_val}, expected={expected}")
                n_ok = False
    if n_ok:
        print(f"  ALL n values correct: ALL=30, map=10 ({tables_with_n} tables checked, {len(generated) - tables_with_n} delta tables skipped)")

    # ── done ─────────────────────────────────────────────────────────────
    print(f"\n=== PAPER_TABLES_GENERATED ===")
    print(f"Output directory: {OUT}")
    print(f"Files generated: {len(generated)}")
    for fname in generated:
        print(f"  {fname}")
    print(f"Markdown: {MD_PATH}")


if __name__ == "__main__":
    main()
