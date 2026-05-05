"""Run single-USV UCB ablation for simple_ring_v1 viewpoint generation."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean, pstdev

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baseline_GP.marine_knownmap_runtime import _json_safe, run_episode_single_usv_search_knownmap


BASE_RESULTS_DIR = Path(
    r"F:\pythonprojects\baseline_GP\results\paper_parallel_run_20260501_190059"
)
OUTPUT_DIR = BASE_RESULTS_DIR / "viewpoint_simple_ring_ablation"
MAP_KINDS = ("open_water", "harbor_cove", "peninsula_passage")
MOTION_MODES = ("static", "random_walk")
SEEDS = tuple(range(10))

METRICS = (
    "time_to_first_detection",
    "time_to_all_found",
    "success_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "path_length",
    "planning_time_ms_mean",
    "candidate_pool_size_mean",
    "reachable_pool_size_mean",
    "a_star_checked_pool_size_mean",
    "selected_viewpoint_rank_mean",
)


def compact_result(result: dict[str, object]) -> dict[str, object]:
    row = {
        "episode_seed": result.get("episode_seed"),
        "map_kind": result.get("map_kind"),
        "target_motion_mode": result.get("target_motion_mode"),
        "policy_name": result.get("policy_name"),
        "clue_acquisition_mode": result.get("clue_acquisition_mode"),
        "path_safety_mode": result.get("path_safety_mode"),
        "viewpoint_generation_mode": result.get("viewpoint_generation_mode"),
        "terminated_reason": result.get("terminated_reason"),
        "completed_steps": result.get("completed_steps"),
    }
    for metric in METRICS:
        row[metric] = result.get(metric)
    return row


def load_baseline_result(motion_mode: str, map_kind: str, seed: int) -> dict[str, object]:
    fp = (
        BASE_RESULTS_DIR
        / f"single_usv_{motion_mode}"
        / "raw_results"
        / "ucb"
        / map_kind
        / "episode_results.json"
    )
    data = json.loads(fp.read_text(encoding="utf-8"))
    for result in data:
        if int(result["episode_seed"]) == int(seed):
            return result
    raise KeyError(f"baseline result not found: motion={motion_mode}, map={map_kind}, seed={seed}")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def numeric_values(rows: list[dict[str, object]], key: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            values.append(1.0 if value else 0.0)
        else:
            values.append(float(value))
    return values


def summarize(rows: list[dict[str, object]], *, group_keys: tuple[str, ...]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        key = tuple(row.get(item) for item in group_keys)
        groups.setdefault(key, []).append(row)
    summary_rows = []
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        out = {group_key: value for group_key, value in zip(group_keys, key)}
        out["n"] = len(group)
        for metric in METRICS:
            values = numeric_values(group, metric)
            out[f"{metric}_mean"] = mean(values) if values else None
            out[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0 if values else None
        summary_rows.append(out)
    return summary_rows


def delta_row(
    baseline: dict[str, object],
    simple: dict[str, object],
) -> dict[str, object]:
    row = {
        "episode_seed": simple.get("episode_seed"),
        "map_kind": simple.get("map_kind"),
        "target_motion_mode": simple.get("target_motion_mode"),
        "baseline_viewpoint_generation_mode": "infosampled_pool_v1",
        "challenger_viewpoint_generation_mode": "simple_ring_v1",
    }
    for metric in METRICS:
        b = baseline.get(metric)
        s = simple.get(metric)
        if b is None or s is None:
            row[f"{metric}_delta"] = None
            continue
        row[f"{metric}_delta"] = (1.0 if s is True else 0.0 if s is False else float(s)) - (
            1.0 if b is True else 0.0 if b is False else float(b)
        )
    return row


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    simple_rows: list[dict[str, object]] = []
    delta_rows: list[dict[str, object]] = []
    raw_compact: dict[str, dict[str, list[dict[str, object]]]] = {
        motion: {map_kind: [] for map_kind in MAP_KINDS}
        for motion in MOTION_MODES
    }

    for motion_mode in MOTION_MODES:
        for map_kind in MAP_KINDS:
            for seed in SEEDS:
                result = run_episode_single_usv_search_knownmap(
                    episode_seed=int(seed),
                    max_iters=240,
                    policy_name="marine_knownmap_path_v2_infosampled",
                    n_targets=3,
                    map_kind=map_kind,
                    map_height_cells=40,
                    map_width_cells=60,
                    target_motion_mode=motion_mode,
                    clue_acquisition_mode="ucb",
                    path_safety_mode="soft_clearance_astar_v1",
                    safe_nav_inflation_radius_cells=0,
                    safe_nav_soft_clearance_radius_cells=1,
                    safe_nav_lambda_clearance=1.0,
                    viewpoint_generation_mode="simple_ring_v1",
                    render=False,
                    save_artifacts=False,
                )
                simple = compact_result(result)
                baseline = compact_result(load_baseline_result(motion_mode, map_kind, int(seed)))
                simple_rows.append(simple)
                delta_rows.append(delta_row(baseline, simple))
                raw_compact[motion_mode][map_kind].append(simple)
                print(
                    f"done motion={motion_mode} map={map_kind} seed={seed} "
                    f"found={simple.get('found_count')} first={simple.get('time_to_first_detection')} "
                    f"all={simple.get('time_to_all_found')}"
                )

    (OUTPUT_DIR / "raw_compact_results.json").write_text(
        json.dumps(_json_safe(raw_compact), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(OUTPUT_DIR / "simple_ring_episode_results.csv", simple_rows)
    write_csv(OUTPUT_DIR / "simple_ring_vs_infosampled_pool_episode_deltas.csv", delta_rows)
    write_csv(
        OUTPUT_DIR / "simple_ring_summary_by_motion_map.csv",
        summarize(simple_rows, group_keys=("target_motion_mode", "map_kind")),
    )
    write_csv(
        OUTPUT_DIR / "simple_ring_summary_by_motion.csv",
        summarize(simple_rows, group_keys=("target_motion_mode",)),
    )
    write_csv(
        OUTPUT_DIR / "delta_summary_by_motion_map.csv",
        summarize(delta_rows, group_keys=("target_motion_mode", "map_kind")),
    )
    write_csv(
        OUTPUT_DIR / "delta_summary_by_motion.csv",
        summarize(delta_rows, group_keys=("target_motion_mode",)),
    )
    (OUTPUT_DIR / "config.json").write_text(
        json.dumps(
            _json_safe(
                {
                    "baseline_results_dir": str(BASE_RESULTS_DIR),
                    "output_dir": str(OUTPUT_DIR),
                    "maps": MAP_KINDS,
                    "motion_modes": MOTION_MODES,
                    "seeds": SEEDS,
                    "max_iters": 240,
                    "policy_name": "marine_knownmap_path_v2_infosampled",
                    "clue_acquisition_mode": "ucb",
                    "path_safety_mode": "soft_clearance_astar_v1",
                    "baseline_viewpoint_generation_mode": "infosampled_pool_v1",
                    "challenger_viewpoint_generation_mode": "simple_ring_v1",
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"output_dir={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
