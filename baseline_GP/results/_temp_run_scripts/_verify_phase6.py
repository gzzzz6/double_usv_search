"""Phase 6: comprehensive verification of obstacle_field mainline data."""
import json, os
from collections import Counter
from pathlib import Path

BASE = Path(r"F:\pythonprojects\baseline_GP\results\paper_obstacle_field_mainline_20260510")

EXPECTED_GROUPS = [
    "single_static", "single_random_walk",
    "two_independent_static", "two_independent_random_walk",
    "two_coordinated_static", "two_coordinated_random_walk",
]
CLUES = ["ucb", "anomaly_upper_tail"]
MAP_KIND = "obstacle_field"
EXPECTED_SEEDS = set(range(10))
EXPECTED_MAX_ITERS = 240
EXPECTED_RUN_MODE = "full"
EXPECTED_VIEWPOINT = "simple_ring_v1"
EXPECTED_PATH_SAFETY = "soft_clearance_astar_v1"
EXPECTED_TAIL_QUANTILE = 0.90
EXPECTED_WEIGHT_LAMBDA = 1.25
EXPECTED_TEAM_AVOIDANCE = "reservation_v1"

SINGLE_GROUPS = {"single_static", "single_random_walk"}
INDEPENDENT_GROUPS = {"two_independent_static", "two_independent_random_walk"}
COORDINATED_GROUPS = {"two_coordinated_static", "two_coordinated_random_walk"}

errors = []
warnings = []
stats = {
    "total_episodes": 0,
    "per_group": {},
    "time_to_all_found_none": {},
    "per_group_time_none": {},
}

map_kinds_seen = Counter()
run_modes_seen = Counter()
max_iters_seen = Counter()
viewpoints_seen = Counter()
path_safeties_seen = Counter()
tail_quantiles_seen = Counter()
weight_lambdas_seen = Counter()
assignment_modes = {}
team_avoidances = Counter()
seed_sets = {}

for group in EXPECTED_GROUPS:
    group_dir = BASE / group
    if not group_dir.is_dir():
        errors.append(f"MISSING group dir: {group}")
        stats["per_group"][group] = 0
        stats["time_to_all_found_none"][group] = 0
        continue

    raw_dir = group_dir / "raw_results"
    if not raw_dir.is_dir():
        errors.append(f"MISSING raw_results dir: {group}")
        stats["per_group"][group] = 0
        stats["time_to_all_found_none"][group] = 0
        continue

    group_total = 0
    group_none_count = 0
    group_seeds = set()
    group_assignment_modes = set()

    for cm in CLUES:
        fp = raw_dir / cm / MAP_KIND / "episode_results.json"
        if not fp.exists():
            errors.append(f"MISSING file: {fp}")
            continue

        try:
            rows = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"BAD JSON in {fp}: {e}")
            continue

        if not isinstance(rows, list):
            errors.append(f"NOT a list: {fp}")
            continue

        group_total += len(rows)

        for r in rows:
            stats["total_episodes"] += 1

            # -- mandatory keys --
            mk = r.get("map_kind")
            if mk is not None:
                map_kinds_seen[mk] += 1
            if mk and mk not in (MAP_KIND, "benchmark"):
                errors.append(f"UNEXPECTED map_kind '{mk}' in {group}/{cm} seed={r.get('episode_seed')}")

            rm = r.get("run_mode")
            if rm is not None:
                run_modes_seen[rm] += 1
            if rm != EXPECTED_RUN_MODE:
                errors.append(f"WRONG run_mode '{rm}' in {group}/{cm} seed={r.get('episode_seed')}")

            mi = r.get("max_iters")
            if mi is not None:
                max_iters_seen[mi] += 1
            if mi != EXPECTED_MAX_ITERS:
                errors.append(f"WRONG max_iters '{mi}' in {group}/{cm} seed={r.get('episode_seed')}")

            vp = r.get("viewpoint_generation_mode")
            if vp is not None:
                viewpoints_seen[vp] += 1
            if vp != EXPECTED_VIEWPOINT:
                errors.append(f"WRONG viewpoint '{vp}' in {group}/{cm} seed={r.get('episode_seed')}")

            ps = r.get("path_safety_mode")
            if ps is not None:
                path_safeties_seen[ps] += 1
            if ps != EXPECTED_PATH_SAFETY:
                errors.append(f"WRONG path_safety '{ps}' in {group}/{cm} seed={r.get('episode_seed')}")

            clue = r.get("clue_acquisition_mode")
            if clue != cm:
                errors.append(f"WRONG clue '{clue}' expected '{cm}' in {group} seed={r.get('episode_seed')}")

            tq = r.get("anomaly_tail_quantile")
            if tq is not None:
                tail_quantiles_seen[tq] += 1
            if cm == "anomaly_upper_tail" and tq != EXPECTED_TAIL_QUANTILE:
                errors.append(f"WRONG tail_quantile {tq} in {group}/{cm} seed={r.get('episode_seed')}")

            wl = r.get("anomaly_weight_lambda")
            if wl is not None:
                weight_lambdas_seen[wl] += 1
            if cm == "anomaly_upper_tail" and wl != EXPECTED_WEIGHT_LAMBDA:
                errors.append(f"WRONG weight_lambda {wl} in {group}/{cm} seed={r.get('episode_seed')}")

            am = r.get("assignment_mode")
            group_assignment_modes.add(am)
            assignment_modes.setdefault(group, set()).add(am)

            ta = r.get("team_path_avoidance_mode")
            if ta is not None:
                team_avoidances[ta] += 1
            if group in SINGLE_GROUPS and ta != "off":
                errors.append(f"WRONG team_avoidance '{ta}' for single group {group}")
            if group not in SINGLE_GROUPS and ta != EXPECTED_TEAM_AVOIDANCE:
                errors.append(f"WRONG team_avoidance '{ta}' in {group} seed={r.get('episode_seed')}")

            seed = r.get("episode_seed")
            if seed is not None:
                group_seeds.add(int(seed))

            # time_to_all_found check
            ttaf = r.get("time_to_all_found")
            if ttaf is None:
                group_none_count += 1

    seed_sets[group] = group_seeds
    stats["per_group"][group] = group_total
    stats["time_to_all_found_none"][group] = group_none_count
    stats["per_group_time_none"][group] = group_none_count

    # Validate seed completeness
    missing_seeds = EXPECTED_SEEDS - group_seeds
    extra_seeds = group_seeds - EXPECTED_SEEDS
    if missing_seeds:
        errors.append(f"MISSING seeds in {group}: {sorted(missing_seeds)}")
    if extra_seeds:
        errors.append(f"EXTRA seeds in {group}: {sorted(extra_seeds)}")

    # Validate assignment_mode per group
    if group in SINGLE_GROUPS:
        if group_assignment_modes != {None}:
            errors.append(f"WRONG assignment modes for {group}: {group_assignment_modes}, expected {{None}}")
    elif group in INDEPENDENT_GROUPS:
        if group_assignment_modes != {"independent"}:
            errors.append(f"WRONG assignment modes for {group}: {group_assignment_modes}, expected {{'independent'}}")
    elif group in COORDINATED_GROUPS:
        if group_assignment_modes != {"coordinated"}:
            errors.append(f"WRONG assignment modes for {group}: {group_assignment_modes}, expected {{'coordinated'}}")

# Check forbidden values
if "benchmark" in map_kinds_seen:
    errors.append("FORBIDDEN: 'benchmark' map_kind found!")
if "harbor_cove" in map_kinds_seen:
    errors.append("FORBIDDEN: 'harbor_cove' map_kind found!")

print("=" * 60)
print("PHASE 6 VERIFICATION REPORT")
print("=" * 60)
print(f"\nTotal episodes: {stats['total_episodes']}")
print(f"Expected: 120")
print(f"\nPer-group counts:")
for g in EXPECTED_GROUPS:
    print(f"  {g}: {stats['per_group'].get(g, 0)} episodes, {stats['time_to_all_found_none'].get(g, 0)} time_to_all_found=None")

print(f"\nmap_kind distribution: {dict(map_kinds_seen)}")
print(f"run_mode distribution: {dict(run_modes_seen)}")
print(f"max_iters distribution: {dict(max_iters_seen)}")
print(f"viewpoint_generation_mode: {dict(viewpoints_seen)}")
print(f"path_safety_mode: {dict(path_safeties_seen)}")
print(f"anomaly_tail_quantile: {dict(tail_quantiles_seen)}")
print(f"anomaly_weight_lambda: {dict(weight_lambdas_seen)}")
print(f"team_path_avoidance_mode: {dict(team_avoidances)}")

print(f"\nErrors ({len(errors)}):")
for e in errors:
    print(f"  ERROR: {e}")

if warnings:
    print(f"\nWarnings ({len(warnings)}):")
    for w in warnings:
        print(f"  WARN: {w}")

passed = len(errors) == 0 and stats["total_episodes"] == 120
print(f"\n{'ALL CHECKS PASSED' if passed else 'VERIFICATION FAILED'}")

# Write reports
report = {
    "verified_at": "2026-05-10",
    "data_root": str(BASE),
    "passed": passed,
    "total_episodes": stats["total_episodes"],
    "expected_episodes": 120,
    "errors": errors,
    "per_group": stats["per_group"],
    "time_to_all_found_none": {
        g: stats["time_to_all_found_none"].get(g, 0)
        for g in EXPECTED_GROUPS
    },
    "distributions": {
        "map_kind": dict(map_kinds_seen),
        "run_mode": dict(run_modes_seen),
        "max_iters": dict(max_iters_seen),
        "viewpoint_generation_mode": dict(viewpoints_seen),
        "path_safety_mode": dict(path_safeties_seen),
        "anomaly_tail_quantile": dict(tail_quantiles_seen),
        "anomaly_weight_lambda": dict(weight_lambdas_seen),
        "team_path_avoidance_mode": dict(team_avoidances),
    },
}

json_path = BASE / "verification_report.json"
json_path.parent.mkdir(parents=True, exist_ok=True)
json.dump(report, json_path.open("w", encoding="utf-8"), indent=2, ensure_ascii=False)

md_lines = [
    "# Phase 6 Verification Report",
    "",
    f"**Verified:** 2026-05-10",
    f"**Data root:** `{BASE}`",
    f"**Status:** {'PASSED' if passed else 'FAILED'}",
    "",
    f"## Episode Counts",
    f"Total: **{stats['total_episodes']}** / 120",
    "",
    "| Group | Episodes | time_to_all_found=None |",
    "|---|---|---|",
]
for g in EXPECTED_GROUPS:
    eps = stats["per_group"].get(g, 0)
    none_count = stats["time_to_all_found_none"].get(g, 0)
    md_lines.append(f"| {g} | {eps} | {none_count} |")

md_lines += [
    "",
    "## Distributions",
    "",
    f"- **map_kind:** {dict(map_kinds_seen)}",
    f"- **run_mode:** {dict(run_modes_seen)}",
    f"- **max_iters:** {dict(max_iters_seen)}",
    f"- **viewpoint_generation_mode:** {dict(viewpoints_seen)}",
    f"- **path_safety_mode:** {dict(path_safeties_seen)}",
    f"- **anomaly_tail_quantile:** {dict(tail_quantiles_seen)}",
    f"- **anomaly_weight_lambda:** {dict(weight_lambdas_seen)}",
    f"- **team_path_avoidance_mode:** {dict(team_avoidances)}",
]

if errors:
    md_lines += ["", "## Errors", ""]
    for e in errors:
        md_lines.append(f"- {e}")

md_path = BASE / "verification_report.md"
md_path.write_text("\n".join(md_lines), encoding="utf-8")

print(f"\nReports written to:")
print(f"  {json_path}")
print(f"  {md_path}")
