"""
Batch runner for obstacle_field mainline experiments.

Output roots:
  smoke: baseline_GP/results/paper_obstacle_field_mainline_20260510_smoke/
  full:  baseline_GP/results/paper_obstacle_field_mainline_20260510/

6 experiment groups:
  single_static, single_random_walk,
  two_independent_static, two_independent_random_walk,
  two_coordinated_static, two_coordinated_random_walk

Full: 3 maps x 2 clue_modes x 10 seeds x 240 iters = 60 episodes per group.
Smoke: obstacle_field only, seed=0, max_iters=20.

Checkpoint/resume validates all key fields, not just episode_seed,
so smoke and full results never cross-contaminate.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from baseline_GP.marine_knownmap_runtime import (
    _json_safe,
    run_episode_single_usv_search_knownmap,
)
from baseline_GP.marine_knownmap_runtime_2usv import (
    run_episode_two_usv_search_knownmap,
)

# ---------------------------------------------------------------------------
# Fixed configuration
# ---------------------------------------------------------------------------
_OUTPUT_BASE = _PROJECT_ROOT / "baseline_GP" / "results"
FULL_OUTPUT_ROOT = _OUTPUT_BASE / "paper_obstacle_field_mainline_20260510"
SMOKE_OUTPUT_ROOT = _OUTPUT_BASE / "paper_obstacle_field_mainline_20260510_smoke"

MAP_KINDS = ("obstacle_field",)
CLUE_MODES = ("ucb", "anomaly_upper_tail")
EPISODE_SEEDS = tuple(range(10))
FULL_MAX_ITERS = 240

# Single-USV constants
SINGLE_POLICY_NAME = "marine_knownmap_path_v2_infosampled"
SINGLE_MAP_H = 40
SINGLE_MAP_W = 60
VIEWPOINT_MODE = "simple_ring_v1"
PATH_SAFETY_MODE = "soft_clearance_astar_v1"
SAFE_NAV_KWARGS = {
    "path_safety_mode": PATH_SAFETY_MODE,
    "safe_nav_inflation_radius_cells": 0,
    "safe_nav_soft_clearance_radius_cells": 1,
    "safe_nav_lambda_clearance": 1.0,
}

# Two-USV constants
TWO_USV_POLICY_NAME = "marine_knownmap_path_v2_infosampled_2usv"
TWO_USV_MAP_H = 60
TWO_USV_MAP_W = 80
TEAM_PATH_AVOIDANCE_MODE = "reservation_v1"
TEAM_RESERVATION_KWARGS = {
    "team_path_avoidance_mode": TEAM_PATH_AVOIDANCE_MODE,
    "team_reservation_safety_distance_cells": 1.5,
    "team_reservation_lambda": 1.0,
}

# Anomaly upper_tail fixed parameters
ANOMALY_TAIL_QUANTILE = 0.90
ANOMALY_WEIGHT_LAMBDA = 1.25

# Smoke settings
SMOKE_MAX_ITERS = 20
SMOKE_MAP_KINDS = ("obstacle_field",)
SMOKE_SEEDS = (0,)

# ---------------------------------------------------------------------------
# Group definitions: (group_name, motion_mode, system_type)
# system_type: "single" | "two_independent" | "two_coordinated"
# ---------------------------------------------------------------------------
GROUPS = [
    ("single_static", "static", "single"),
    ("single_random_walk", "random_walk", "single"),
    ("two_independent_static", "static", "two_independent"),
    ("two_independent_random_walk", "random_walk", "two_independent"),
    ("two_coordinated_static", "static", "two_coordinated"),
    ("two_coordinated_random_walk", "random_walk", "two_coordinated"),
]

# ---------------------------------------------------------------------------
# Per-result key fields that must match exactly for checkpoint/resume
# ---------------------------------------------------------------------------
_RESUME_VALIDATION_KEYS = (
    "episode_seed",
    "map_kind",
    "clue_acquisition_mode",
    "target_motion_mode",
    "max_iters",
    "run_mode",
    "viewpoint_generation_mode",
    "path_safety_mode",
    "anomaly_tail_quantile",
    "anomaly_weight_lambda",
    "assignment_mode",
    "team_path_avoidance_mode",
)


def _expected_validation_values(
    episode_seed: int,
    map_kind: str,
    clue_mode: str,
    motion_mode: str,
    max_iters: int,
    run_mode: str,
    system_type: str,
) -> dict[str, object]:
    if system_type == "single":
        assignment_mode = None
        team_avoid = "off"
    elif system_type == "two_coordinated":
        assignment_mode = "coordinated"
        team_avoid = TEAM_PATH_AVOIDANCE_MODE
    else:
        assignment_mode = "independent"
        team_avoid = TEAM_PATH_AVOIDANCE_MODE

    return {
        "episode_seed": int(episode_seed),
        "map_kind": map_kind,
        "clue_acquisition_mode": clue_mode,
        "target_motion_mode": motion_mode,
        "max_iters": int(max_iters),
        "run_mode": run_mode,
        "viewpoint_generation_mode": VIEWPOINT_MODE,
        "path_safety_mode": PATH_SAFETY_MODE,
        "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
        "anomaly_weight_lambda": ANOMALY_WEIGHT_LAMBDA,
        "assignment_mode": assignment_mode,
        "team_path_avoidance_mode": team_avoid,
    }


def _result_matches_expected(
    result: dict[str, object],
    expected: dict[str, object],
) -> bool:
    for key, expected_val in expected.items():
        actual = result.get(key)
        if actual != expected_val:
            return False
    return True


def _make_config_snapshot(
    group_name: str,
    motion_mode: str,
    system_type: str,
    max_iters: int,
    map_kinds: tuple[str, ...],
    episode_seeds: tuple[int, ...],
    run_mode: str,
) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "run_mode": run_mode,
        "group_name": group_name,
        "map_kinds": list(map_kinds),
        "episode_seeds": list(episode_seeds),
        "max_iters": max_iters,
        "target_motion_mode": motion_mode,
        "clue_acquisition_modes": list(CLUE_MODES),
        "viewpoint_generation_mode": VIEWPOINT_MODE,
        "path_safety_mode": PATH_SAFETY_MODE,
        "safe_nav_kwargs": dict(SAFE_NAV_KWARGS),
        "anomaly_upper_tail_config": {
            "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
            "anomaly_weight_lambda": ANOMALY_WEIGHT_LAMBDA,
        },
    }
    if system_type == "single":
        snapshot["map_height_cells"] = SINGLE_MAP_H
        snapshot["map_width_cells"] = SINGLE_MAP_W
        snapshot["policy_name"] = SINGLE_POLICY_NAME
        snapshot["clue_sigma_m"] = 20.0
    else:
        snapshot["map_height_cells"] = TWO_USV_MAP_H
        snapshot["map_width_cells"] = TWO_USV_MAP_W
        snapshot["policy_name"] = TWO_USV_POLICY_NAME
        snapshot["clue_sigma_m"] = 15.0
        snapshot["team_path_avoidance_mode"] = TEAM_PATH_AVOIDANCE_MODE
        snapshot["team_reservation_kwargs"] = dict(TEAM_RESERVATION_KWARGS)
        snapshot["assignment_mode"] = (
            "coordinated" if system_type == "two_coordinated" else "independent"
        )
    return snapshot


def _load_existing_results(
    raw_output_dir: Path,
    map_kinds: tuple[str, ...],
    motion_mode: str,
    max_iters: int,
    run_mode: str,
    system_type: str,
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Load existing results, keeping only rows that match all validation keys."""
    results: dict[str, dict[str, list[dict[str, object]]]] = {
        clue_mode: {map_kind: [] for map_kind in map_kinds}
        for clue_mode in CLUE_MODES
    }
    if not raw_output_dir.exists():
        return results
    for clue_mode in CLUE_MODES:
        for map_kind in map_kinds:
            fp = raw_output_dir / clue_mode / map_kind / "episode_results.json"
            if not fp.exists():
                continue
            try:
                loaded = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(loaded, list):
                continue
            # Filter to only rows whose validation keys match
            validated: list[dict[str, object]] = []
            for row in loaded:
                expected = _expected_validation_values(
                    episode_seed=row.get("episode_seed", -1),
                    map_kind=map_kind,
                    clue_mode=clue_mode,
                    motion_mode=motion_mode,
                    max_iters=max_iters,
                    run_mode=run_mode,
                    system_type=system_type,
                )
                if _result_matches_expected(row, expected):
                    validated.append(row)
            results[clue_mode][map_kind] = validated
    return results


def _write_raw_result_group(
    raw_output_dir: Path,
    config_snapshot: dict[str, object],
    clue_mode: str,
    map_kind: str,
    map_results: list[dict[str, object]],
    group_name: str,
    system_type: str,
    motion_mode: str,
) -> None:
    clue_dir = raw_output_dir / clue_mode
    clue_dir.mkdir(parents=True, exist_ok=True)
    with (clue_dir / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)

    map_dir = clue_dir / map_kind
    map_dir.mkdir(parents=True, exist_ok=True)
    with (map_dir / "episode_results.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(map_results), f, indent=2, ensure_ascii=False)

    summary = {
        "group_name": group_name,
        "system_type": system_type,
        "motion_mode": motion_mode,
        "clue_acquisition_mode": clue_mode,
        "map_kind": map_kind,
        "n_episodes": len(map_results),
    }
    with (map_dir / "policy_summary.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(summary), f, indent=2, ensure_ascii=False)


def run_single_episode(
    system_type: str,
    episode_seed: int,
    max_iters: int,
    map_kind: str,
    motion_mode: str,
    clue_mode: str,
    run_mode: str,
) -> dict[str, object]:
    common = {
        "episode_seed": episode_seed,
        "max_iters": max_iters,
        "map_kind": map_kind,
        "target_motion_mode": motion_mode,
        "clue_acquisition_mode": clue_mode,
        "anomaly_tail_quantile": ANOMALY_TAIL_QUANTILE,
        "anomaly_weight_lambda": ANOMALY_WEIGHT_LAMBDA,
        "viewpoint_generation_mode": VIEWPOINT_MODE,
        "path_safety_mode": PATH_SAFETY_MODE,
        "render": False,
        **SAFE_NAV_KWARGS,
    }

    if system_type == "single":
        result = run_episode_single_usv_search_knownmap(
            policy_name=SINGLE_POLICY_NAME,
            n_targets=3,
            map_height_cells=SINGLE_MAP_H,
            map_width_cells=SINGLE_MAP_W,
            save_artifacts=False,
            **common,
        )
        result["assignment_mode"] = None
        result["team_path_avoidance_mode"] = "off"
    else:
        assignment_mode = (
            "coordinated" if system_type == "two_coordinated" else "independent"
        )
        result = run_episode_two_usv_search_knownmap(
            policy_name=TWO_USV_POLICY_NAME,
            assignment_mode=assignment_mode,
            n_targets=3,
            map_height_cells=TWO_USV_MAP_H,
            map_width_cells=TWO_USV_MAP_W,
            **common,
            **TEAM_RESERVATION_KWARGS,
        )
        result["assignment_mode"] = assignment_mode
        result["team_path_avoidance_mode"] = TEAM_PATH_AVOIDANCE_MODE

    result["episode_seed"] = int(episode_seed)
    result["map_kind"] = map_kind
    result["target_motion_mode"] = motion_mode
    result["clue_acquisition_mode"] = clue_mode
    result["viewpoint_generation_mode"] = VIEWPOINT_MODE
    result["path_safety_mode"] = PATH_SAFETY_MODE
    result["anomaly_tail_quantile"] = ANOMALY_TAIL_QUANTILE
    result["anomaly_weight_lambda"] = ANOMALY_WEIGHT_LAMBDA
    result["max_iters"] = int(max_iters)
    result["run_mode"] = run_mode
    return result


def run_group(
    group_name: str,
    motion_mode: str,
    system_type: str,
    *,
    smoke: bool = False,
) -> dict[str, object]:
    run_mode = "smoke" if smoke else "full"
    max_iters = SMOKE_MAX_ITERS if smoke else FULL_MAX_ITERS
    map_kinds = SMOKE_MAP_KINDS if smoke else MAP_KINDS
    episode_seeds = SMOKE_SEEDS if smoke else EPISODE_SEEDS
    resolved_seeds = tuple(int(s) for s in episode_seeds)
    output_root = SMOKE_OUTPUT_ROOT if smoke else FULL_OUTPUT_ROOT

    config_snapshot = _make_config_snapshot(
        group_name=group_name,
        motion_mode=motion_mode,
        system_type=system_type,
        max_iters=max_iters,
        map_kinds=map_kinds,
        episode_seeds=resolved_seeds,
        run_mode=run_mode,
    )

    output_path = output_root / group_name
    raw_output_dir = output_path / "raw_results"
    raw_output_dir.mkdir(parents=True, exist_ok=True)

    with (output_path / "config_snapshot.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)

    # Checkpoint resume with full field validation
    results_by_clue = _load_existing_results(
        raw_output_dir=raw_output_dir,
        map_kinds=map_kinds,
        motion_mode=motion_mode,
        max_iters=max_iters,
        run_mode=run_mode,
        system_type=system_type,
    )

    total_episodes = len(map_kinds) * len(CLUE_MODES) * len(resolved_seeds)
    completed_count = sum(
        len(results_by_clue[cm][mk]) for cm in CLUE_MODES for mk in map_kinds
    )

    log_lines: list[str] = []
    log_lines.append(
        f"[{datetime.now().isoformat()}] group={group_name} start, "
        f"motion={motion_mode}, system={system_type}, "
        f"max_iters={max_iters}, run_mode={run_mode}, "
        f"resumed={completed_count}/{total_episodes}"
    )
    print(log_lines[-1])

    for clue_mode in CLUE_MODES:
        for map_kind in map_kinds:
            existing = results_by_clue[clue_mode][map_kind]
            completed_seeds = {
                int(r["episode_seed"])
                for r in existing
                if r.get("episode_seed") is not None
            }
            for seed in resolved_seeds:
                if seed in completed_seeds:
                    continue
                label = (
                    f"group={group_name} | motion={motion_mode} | "
                    f"clue={clue_mode} | map={map_kind} | seed={seed}"
                )
                print(f"  {label}")
                try:
                    result = run_single_episode(
                        system_type=system_type,
                        episode_seed=seed,
                        max_iters=max_iters,
                        map_kind=map_kind,
                        motion_mode=motion_mode,
                        clue_mode=clue_mode,
                        run_mode=run_mode,
                    )
                except Exception as exc:
                    msg = f"  FAIL {label}: {exc}"
                    print(msg)
                    log_lines.append(msg)
                    continue

                results_by_clue[clue_mode][map_kind].append(result)
                _write_raw_result_group(
                    raw_output_dir=raw_output_dir,
                    config_snapshot=config_snapshot,
                    clue_mode=clue_mode,
                    map_kind=map_kind,
                    map_results=results_by_clue[clue_mode][map_kind],
                    group_name=group_name,
                    system_type=system_type,
                    motion_mode=motion_mode,
                )

    final_count = sum(
        len(results_by_clue[cm][mk]) for cm in CLUE_MODES for mk in map_kinds
    )
    log_lines.append(
        f"[{datetime.now().isoformat()}] group={group_name} done, "
        f"episodes={final_count}/{total_episodes}"
    )
    print(log_lines[-1])

    log_dir = output_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{group_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file.write_text("\n".join(log_lines), encoding="utf-8")

    return {
        "group_name": group_name,
        "total_episodes": total_episodes,
        "completed_episodes": final_count,
        "output_path": str(output_path),
        "run_mode": run_mode,
    }


def _parse_selected_groups() -> list[int] | None:
    """Parse --groups=0,1,3 style argument. Returns None if not specified."""
    for arg in sys.argv:
        if arg.startswith("--groups="):
            parts = arg.split("=", 1)[1]
            return [int(x.strip()) for x in parts.split(",") if x.strip()]
    return None


def main() -> None:
    smoke = "--smoke" in sys.argv
    run_mode = "smoke" if smoke else "full"
    output_root = SMOKE_OUTPUT_ROOT if smoke else FULL_OUTPUT_ROOT
    selected = _parse_selected_groups()

    if selected is not None:
        active_groups = [GROUPS[i] for i in selected if 0 <= i < len(GROUPS)]
    else:
        active_groups = list(GROUPS)

    print(f"=== obstacle_field mainline runner ({run_mode.upper()}) ===")
    print(f"Output root: {output_root}")
    print(f"Groups: {[g[0] for g in active_groups]}")
    print()

    results = {}
    for group_name, motion_mode, system_type in active_groups:
        result = run_group(
            group_name=group_name,
            motion_mode=motion_mode,
            system_type=system_type,
            smoke=smoke,
        )
        results[group_name] = result
        print()

    manifest = {
        "created_at": datetime.now().isoformat(),
        "output_root": str(output_root),
        "run_mode": run_mode,
        "groups": results,
    }
    manifest_path = output_root / "runner_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(manifest), f, indent=2, ensure_ascii=False)

    print("=== All groups complete ===")
    for g_name, g_result in results.items():
        print(f"  {g_name}: {g_result['completed_episodes']}/{g_result['total_episodes']}")


if __name__ == "__main__":
    main()
