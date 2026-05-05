"""Run two-USV coordinated UCB ablation for simple_ring_v1 viewpoint generation."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baseline_GP.marine_knownmap_runtime import _json_safe
from baseline_GP.marine_knownmap_runtime_2usv import run_episode_two_usv_search_knownmap


BASE_RESULTS_DIR = Path(
    r"F:\pythonprojects\baseline_GP\results\paper_parallel_run_20260501_190059"
)
OUTPUT_DIR = BASE_RESULTS_DIR / "viewpoint_simple_ring_ablation" / "two_usv_coordinated_ucb"
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
    "path_length_total",
    "planning_time_ms_mean",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "reservation_wait_fallback_count",
    "candidate_pool_size_mean",
    "reachable_pool_size_mean",
    "a_star_checked_pool_size_mean",
)


def compact_result(result: dict[str, object]) -> dict[str, object]:
    row = {
        "episode_seed": result.get("episode_seed"),
        "map_kind": result.get("map_kind"),
        "target_motion_mode": result.get("target_motion_mode"),
        "policy_name": result.get("policy_name"),
        "assignment_mode": result.get("assignment_mode"),
        "clue_acquisition_mode": result.get("clue_acquisition_mode"),
        "path_safety_mode": result.get("path_safety_mode"),
        "team_path_avoidance_mode": result.get("team_path_avoidance_mode"),
        "viewpoint_generation_mode": result.get("viewpoint_generation_mode"),
        "terminated_reason": result.get("terminated_reason"),
        "completed_steps": result.get("completed_steps"),
    }
    for metric in METRICS:
        row[metric] = result.get(metric)
    return row


def baseline_path(motion_mode: str, map_kind: str) -> Path:
    folder = "two_usv_static" if motion_mode == "static" else "two_usv_random_walk"
    return (
        BASE_RESULTS_DIR
        / folder
        / "raw_results"
        / "ucb"
        / map_kind
        / "episode_results.json"
    )


def load_baseline_result(motion_mode: str, map_kind: str, seed: int) -> dict[str, object]:
    data = json.loads(baseline_path(motion_mode, map_kind).read_text(encoding="utf-8"))
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


def value(row: dict[str, object], key: str) -> float | None:
    raw = row.get(key)
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if raw in ("True", "true"):
        return 1.0
    if raw in ("False", "false"):
        return 0.0
    return float(raw)


def group(rows: list[dict[str, object]], keys: tuple[str, ...]) -> dict[tuple[object, ...], list[dict[str, object]]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(tuple(row.get(key) for key in keys), []).append(row)
    return groups


def metric_mean(rows: list[dict[str, object]], metric: str) -> float | None:
    clean = [float(v) for row in rows if (v := value(row, metric)) is not None]
    return mean(clean) if clean else None


def comparison_rows(
    baseline_rows: list[dict[str, object]],
    simple_rows: list[dict[str, object]],
    group_keys: tuple[str, ...],
) -> list[dict[str, object]]:
    simple_groups = group(simple_rows, group_keys)
    baseline_groups = group(baseline_rows, group_keys)
    rows = []
    for key in sorted(simple_groups, key=lambda item: tuple(str(v) for v in item)):
        simple = simple_groups[key]
        baseline = baseline_groups[key]
        row = {group_key: value for group_key, value in zip(group_keys, key)}
        row["n"] = len(simple)
        for metric in METRICS:
            base_mean = metric_mean(baseline, metric)
            simple_mean = metric_mean(simple, metric)
            row[f"{metric}_baseline_mean"] = base_mean
            row[f"{metric}_simple_ring_mean"] = simple_mean
            row[f"{metric}_delta"] = (
                None if base_mean is None or simple_mean is None else simple_mean - base_mean
            )
        rows.append(row)
    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    simple_rows: list[dict[str, object]] = []
    baseline_rows: list[dict[str, object]] = []
    raw_compact: dict[str, dict[str, list[dict[str, object]]]] = {
        motion: {map_kind: [] for map_kind in MAP_KINDS}
        for motion in MOTION_MODES
    }

    for motion_mode in MOTION_MODES:
        for map_kind in MAP_KINDS:
            for seed in SEEDS:
                result = run_episode_two_usv_search_knownmap(
                    episode_seed=int(seed),
                    max_iters=240,
                    policy_name="marine_knownmap_path_v2_infosampled_2usv",
                    assignment_mode="coordinated",
                    n_targets=3,
                    map_kind=map_kind,
                    map_height_cells=60,
                    map_width_cells=80,
                    target_motion_mode=motion_mode,
                    clue_acquisition_mode="ucb",
                    path_safety_mode="soft_clearance_astar_v1",
                    safe_nav_inflation_radius_cells=0,
                    safe_nav_soft_clearance_radius_cells=1,
                    safe_nav_lambda_clearance=1.0,
                    team_path_avoidance_mode="reservation_v1",
                    viewpoint_generation_mode="simple_ring_v1",
                    render=False,
                )
                simple = compact_result(result)
                baseline = compact_result(load_baseline_result(motion_mode, map_kind, int(seed)))
                simple_rows.append(simple)
                baseline_rows.append(baseline)
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
    write_csv(OUTPUT_DIR / "baseline_infosampled_pool_episode_results.csv", baseline_rows)
    write_csv(
        OUTPUT_DIR / "comparison_summary_by_motion.csv",
        comparison_rows(baseline_rows, simple_rows, ("target_motion_mode",)),
    )
    write_csv(
        OUTPUT_DIR / "comparison_summary_by_motion_map.csv",
        comparison_rows(baseline_rows, simple_rows, ("target_motion_mode", "map_kind")),
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
                    "policy_name": "marine_knownmap_path_v2_infosampled_2usv",
                    "assignment_mode": "coordinated",
                    "clue_acquisition_mode": "ucb",
                    "path_safety_mode": "soft_clearance_astar_v1",
                    "team_path_avoidance_mode": "reservation_v1",
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
