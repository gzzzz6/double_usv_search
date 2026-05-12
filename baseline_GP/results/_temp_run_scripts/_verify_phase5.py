"""Phase 5 comprehensive verification script."""
import json, os
from collections import Counter

BASE = r"F:\pythonprojects\baseline_GP\results\paper_obstacle_field_mainline_20260510"
GROUPS = [
    "single_static", "single_random_walk",
    "two_independent_static", "two_independent_random_walk",
    "two_coordinated_static", "two_coordinated_random_walk",
]
CLUES = ["ucb", "anomaly_upper_tail"]

errors = []
total = 0
map_kinds_seen = Counter()
run_modes_seen = Counter()
max_iters_seen = Counter()

for group in GROUPS:
    group_dir = os.path.join(BASE, group)
    if not os.path.isdir(group_dir):
        errors.append(f"MISSING dir: {group}")
        print(f"  MISSING dir: {group}")
        continue
    group_total = 0
    for cm in CLUES:
        fp = os.path.join(group_dir, "raw_results", cm, "obstacle_field", "episode_results.json")
        if not os.path.exists(fp):
            errors.append(f"MISSING file: {fp}")
            print(f"  MISSING file: {fp}")
            continue
        rows = json.load(open(fp, encoding="utf-8"))
        group_total += len(rows)
        total += len(rows)
        for r in rows:
            map_kinds_seen[r.get("map_kind")] += 1
            run_modes_seen[r.get("run_mode")] += 1
            max_iters_seen[r.get("max_iters")] += 1
    print(f"  {group}: {group_total} episodes")

print(f"\nTotal episodes: {total}")
print(f"map_kind distribution: {dict(map_kinds_seen)}")
print(f"run_mode distribution: {dict(run_modes_seen)}")
print(f"max_iters distribution: {dict(max_iters_seen)}")

# Check for forbidden values
forbidden_maps = {"benchmark", "harbor_cove"}
for fmap in forbidden_maps:
    if fmap in map_kinds_seen:
        errors.append(f"FORBIDDEN map_kind found: {fmap}")

if "obstacle_field" not in map_kinds_seen:
    errors.append("obstacle_field NOT found in results!")
if "full" not in run_modes_seen:
    errors.append("run_mode 'full' NOT found!")
if 240 not in max_iters_seen:
    errors.append("max_iters=240 NOT found!")

print(f"\nErrors: {len(errors)}")
for e in errors:
    print(f"  ERROR: {e}")

if not errors:
    print("ALL CHECKS PASSED")
