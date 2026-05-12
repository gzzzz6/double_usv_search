from __future__ import annotations

import csv
import json
import math
from pathlib import Path


OLD_ROOT = Path(r"F:\pythonprojects\baseline_GP\results\paper_simple_ring_mainline_20260505")
NEW_ROOT = Path(r"F:\pythonprojects\baseline_GP\results\paper_obstacle_field_mainline_20260510")
OUT_DIR = NEW_ROOT / "paper_tables_merged_for_report"
OUT_JSON = OUT_DIR / "table_payload.json"
OUT_MD = OUT_DIR / "table_payload_preview.md"

MAP_ORDER = ("ALL", "open_water", "obstacle_field", "peninsula_passage")
MAP_LABEL = {
    "ALL": "总体",
    "open_water": "open_water",
    "obstacle_field": "obstacle_field",
    "peninsula_passage": "peninsula_passage",
}

GROUPS = (
    "single_static",
    "single_random_walk",
    "two_independent_static",
    "two_independent_random_walk",
    "two_coordinated_static",
    "two_coordinated_random_walk",
)


def _float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def fmt1(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "N/A"
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:.1f}"


def fmt_int(value: int) -> str:
    return str(int(value))


def load_old_group(group: str) -> list[dict]:
    path = OLD_ROOT / group / "episode_results.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("map_kind") in {"open_water", "peninsula_passage"}]


def load_new_group(group: str) -> list[dict]:
    rows: list[dict] = []
    for clue in ("ucb", "anomaly_upper_tail"):
        path = NEW_ROOT / group / "raw_results" / clue / "obstacle_field" / "episode_results.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(loaded)
    return rows


def load_combined() -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for group in GROUPS:
        rows = load_old_group(group) + load_new_group(group)
        maps = {r.get("map_kind") for r in rows}
        if maps != {"open_water", "obstacle_field", "peninsula_passage"}:
            raise AssertionError(f"{group}: unexpected maps {maps}")
        modes = {r.get("clue_acquisition_mode") for r in rows}
        if modes != {"ucb", "anomaly_upper_tail"}:
            raise AssertionError(f"{group}: unexpected clue modes {modes}")
        data[group] = rows
    return data


class Stats:
    def __init__(self, rows: list[dict], map_kind: str | None = None):
        if map_kind is None:
            self.rows = rows
        else:
            self.rows = [r for r in rows if r.get("map_kind") == map_kind]
        self.n = len(self.rows)
        self.first_vals = [_float(r.get("time_to_first_detection")) for r in self.rows]
        self.all_vals = [_float(r.get("time_to_all_found")) for r in self.rows]
        self.n_first = sum(v is not None for v in self.first_vals)
        self.n_all = sum(v is not None for v in self.all_vals)

    def mean(self, key: str) -> float | None:
        vals = [_float(r.get(key)) for r in self.rows]
        return _mean([v for v in vals if v is not None])

    def success_pct(self) -> float:
        return 100.0 * self.n_all / self.n if self.n else 0.0

    def mean_pct(self, key: str) -> float | None:
        v = self.mean(key)
        return None if v is None else 100.0 * v


def subset(rows: list[dict], **conds) -> list[dict]:
    out = rows
    for key, value in conds.items():
        out = [r for r in out if r.get(key) == value]
    return out


def table_single_ucb(rows: list[dict]) -> tuple[list[list[str]], list[list[str]]]:
    ucb = subset(rows, clue_acquisition_mode="ucb")
    metrics: list[list[str]] = [["地图", "T_first", "T_all", "success（%）", "detection（%）", "obs（%）", "path"]]
    counts: list[list[str]] = [["地图", "n", "n_first", "n_all"]]
    for mk in MAP_ORDER:
        s = Stats(ucb, None if mk == "ALL" else mk)
        metrics.append([
            MAP_LABEL[mk],
            fmt1(s.mean("time_to_first_detection")),
            fmt1(s.mean("time_to_all_found")),
            fmt1(s.success_pct()),
            fmt1(s.mean_pct("detection_rate")),
            fmt1(s.mean_pct("known_free_observation_ratio_final")),
            fmt1(s.mean("path_length")),
        ])
        counts.append([MAP_LABEL[mk], fmt_int(s.n), fmt_int(s.n_first), fmt_int(s.n_all)])
    return metrics, counts


def table_two_assignment(ind_rows: list[dict], coord_rows: list[dict]) -> tuple[list[list[str]], list[list[str]]]:
    rows_by_mode = [("independent", subset(ind_rows, clue_acquisition_mode="ucb")), ("coordinated", subset(coord_rows, clue_acquisition_mode="ucb"))]
    metrics: list[list[str]] = [["地图", "方法", "T_first", "T_all", "success（%）", "detection（%）", "obs（%）", "duplicate（%）", "cross（%）", "wait"]]
    counts: list[list[str]] = [["地图", "方法", "n", "n_first", "n_all"]]
    for mode, rows in rows_by_mode:
        for mk in MAP_ORDER:
            s = Stats(rows, None if mk == "ALL" else mk)
            metrics.append([
                MAP_LABEL[mk],
                mode,
                fmt1(s.mean("time_to_first_detection")),
                fmt1(s.mean("time_to_all_found")),
                fmt1(s.success_pct()),
                fmt1(s.mean_pct("detection_rate")),
                fmt1(s.mean_pct("known_free_observation_ratio_final")),
                fmt1(s.mean_pct("duplicate_viewpoint_ratio")),
                fmt1(s.mean_pct("cross_region_assignment_ratio")),
                fmt1(s.mean("wait_count_total")),
            ])
            counts.append([MAP_LABEL[mk], mode, fmt_int(s.n), fmt_int(s.n_first), fmt_int(s.n_all)])
    return metrics, counts


def table_two_delta(ind_rows: list[dict], coord_rows: list[dict]) -> list[list[str]]:
    ind = subset(ind_rows, clue_acquisition_mode="ucb")
    coord = subset(coord_rows, clue_acquisition_mode="ucb")
    table: list[list[str]] = [["地图", "ΔT_first", "ΔT_all", "Δsuccess（百分点）", "Δdetection（百分点）", "Δduplicate（百分点）", "Δcross（百分点）", "Δwait"]]
    for mk in MAP_ORDER:
        c_sub = coord if mk == "ALL" else [r for r in coord if r.get("map_kind") == mk]
        i_sub = ind if mk == "ALL" else [r for r in ind if r.get("map_kind") == mk]
        c_map = {(r.get("map_kind"), str(r.get("episode_seed"))): r for r in c_sub}
        i_map = {(r.get("map_kind"), str(r.get("episode_seed"))): r for r in i_sub}

        def paired_delta_mean(key: str) -> float | None:
            vals: list[float] = []
            for pair_key, c_row in c_map.items():
                i_row = i_map.get(pair_key)
                if i_row is None:
                    continue
                c_val = _float(c_row.get(key))
                i_val = _float(i_row.get(key))
                if c_val is not None and i_val is not None:
                    vals.append(c_val - i_val)
            return _mean(vals)

        saf_vals: list[float] = []
        for pair_key, c_row in c_map.items():
            i_row = i_map.get(pair_key)
            if i_row is None:
                continue
            c_saf = 1.0 if _float(c_row.get("time_to_all_found")) is not None else 0.0
            i_saf = 1.0 if _float(i_row.get("time_to_all_found")) is not None else 0.0
            saf_vals.append(100.0 * (c_saf - i_saf))

        row = [
            MAP_LABEL[mk],
            fmt1(paired_delta_mean("time_to_first_detection"), signed=True),
            fmt1(paired_delta_mean("time_to_all_found"), signed=True),
            fmt1(_mean(saf_vals), signed=True),
            fmt1(None if paired_delta_mean("detection_rate") is None else 100.0 * paired_delta_mean("detection_rate"), signed=True),
            fmt1(None if paired_delta_mean("duplicate_viewpoint_ratio") is None else 100.0 * paired_delta_mean("duplicate_viewpoint_ratio"), signed=True),
            fmt1(None if paired_delta_mean("cross_region_assignment_ratio") is None else 100.0 * paired_delta_mean("cross_region_assignment_ratio"), signed=True),
            fmt1(paired_delta_mean("wait_count_total"), signed=True),
        ]
        table.append(row)
    return table


def table_ucb_vs_anomaly(rows: list[dict]) -> tuple[list[list[str]], list[list[str]]]:
    metrics: list[list[str]] = [["地图", "采集方式", "T_first", "T_all", "success（%）", "detection（%）", "obs（%）"]]
    counts: list[list[str]] = [["地图", "采集方式", "n", "n_first", "n_all"]]
    for clue_label, clue in (("UCB", "ucb"), ("anomaly_upper_tail", "anomaly_upper_tail")):
        clue_rows = subset(rows, clue_acquisition_mode=clue)
        for mk in MAP_ORDER:
            s = Stats(clue_rows, None if mk == "ALL" else mk)
            metrics.append([
                MAP_LABEL[mk],
                clue_label,
                fmt1(s.mean("time_to_first_detection")),
                fmt1(s.mean("time_to_all_found")),
                fmt1(s.success_pct()),
                fmt1(s.mean_pct("detection_rate")),
                fmt1(s.mean_pct("known_free_observation_ratio_final")),
            ])
            counts.append([MAP_LABEL[mk], clue_label, fmt_int(s.n), fmt_int(s.n_first), fmt_int(s.n_all)])
    return metrics, counts


def table_anomaly_delta(static_rows: list[dict], random_rows: list[dict]) -> list[list[str]]:
    table: list[list[str]] = [["目标模式", "地图", "ΔT_first", "ΔT_all", "Δsuccess（百分点）", "Δdetection（百分点）", "Δobs（百分点）"]]
    for motion, rows in (("static", static_rows), ("random_walk", random_rows)):
        ucb = subset(rows, clue_acquisition_mode="ucb")
        ano = subset(rows, clue_acquisition_mode="anomaly_upper_tail")
        for mk in MAP_ORDER:
            a_sub = ano if mk == "ALL" else [r for r in ano if r.get("map_kind") == mk]
            u_sub = ucb if mk == "ALL" else [r for r in ucb if r.get("map_kind") == mk]
            a_map = {(r.get("map_kind"), str(r.get("episode_seed"))): r for r in a_sub}
            u_map = {(r.get("map_kind"), str(r.get("episode_seed"))): r for r in u_sub}

            def paired_delta_mean(key: str) -> float | None:
                vals: list[float] = []
                for pair_key, a_row in a_map.items():
                    u_row = u_map.get(pair_key)
                    if u_row is None:
                        continue
                    a_val = _float(a_row.get(key))
                    u_val = _float(u_row.get(key))
                    if a_val is not None and u_val is not None:
                        vals.append(a_val - u_val)
                return _mean(vals)

            saf_vals: list[float] = []
            for pair_key, a_row in a_map.items():
                u_row = u_map.get(pair_key)
                if u_row is None:
                    continue
                a_saf = 1.0 if _float(a_row.get("time_to_all_found")) is not None else 0.0
                u_saf = 1.0 if _float(u_row.get("time_to_all_found")) is not None else 0.0
                saf_vals.append(100.0 * (a_saf - u_saf))

            table.append([
                motion,
                MAP_LABEL[mk],
                fmt1(paired_delta_mean("time_to_first_detection"), signed=True),
                fmt1(paired_delta_mean("time_to_all_found"), signed=True),
                fmt1(_mean(saf_vals), signed=True),
                fmt1(None if paired_delta_mean("detection_rate") is None else 100.0 * paired_delta_mean("detection_rate"), signed=True),
                fmt1(None if paired_delta_mean("known_free_observation_ratio_final") is None else 100.0 * paired_delta_mean("known_free_observation_ratio_final"), signed=True),
            ])
    return table


def build_payload() -> dict[str, list[list[str]]]:
    data = load_combined()
    payload: dict[str, list[list[str]]] = {}
    payload["single_static_metrics"], payload["single_static_counts"] = table_single_ucb(data["single_static"])
    payload["single_random_metrics"], payload["single_random_counts"] = table_single_ucb(data["single_random_walk"])
    payload["two_static_assignment"], payload["two_static_counts"] = table_two_assignment(data["two_independent_static"], data["two_coordinated_static"])
    payload["two_static_delta"] = table_two_delta(data["two_independent_static"], data["two_coordinated_static"])
    payload["two_random_assignment"], payload["two_random_counts"] = table_two_assignment(data["two_independent_random_walk"], data["two_coordinated_random_walk"])
    payload["two_random_delta"] = table_two_delta(data["two_independent_random_walk"], data["two_coordinated_random_walk"])
    payload["single_static_anomaly"], payload["single_static_anomaly_counts"] = table_ucb_vs_anomaly(data["single_static"])
    payload["single_random_anomaly"], payload["single_random_anomaly_counts"] = table_ucb_vs_anomaly(data["single_random_walk"])
    payload["single_anomaly_delta"] = table_anomaly_delta(data["single_static"], data["single_random_walk"])
    payload["two_static_anomaly"], payload["two_static_anomaly_counts"] = table_ucb_vs_anomaly(data["two_coordinated_static"])
    payload["two_random_anomaly"], payload["two_random_anomaly_counts"] = table_ucb_vs_anomaly(data["two_coordinated_random_walk"])
    payload["two_anomaly_delta"] = table_anomaly_delta(data["two_coordinated_static"], data["two_coordinated_random_walk"])
    return payload


def write_preview(payload: dict[str, list[list[str]]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    parts: list[str] = ["# Obstacle-field merged table payload\n\n"]
    for name, table in payload.items():
        parts.append(f"## {name}\n\n")
        header = table[0]
        parts.append("| " + " | ".join(header) + " |\n")
        parts.append("| " + " | ".join("---" for _ in header) + " |\n")
        for row in table[1:]:
            parts.append("| " + " | ".join(row) + " |\n")
        parts.append("\n")
    OUT_MD.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    payload = build_payload()
    write_preview(payload)
    print(OUT_JSON)
    print(OUT_MD)
