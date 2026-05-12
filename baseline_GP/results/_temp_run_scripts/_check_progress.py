import json, os
base = r"F:\pythonprojects\baseline_GP\results\paper_obstacle_field_mainline_20260510"
groups = ["two_independent_static","two_independent_random_walk","two_coordinated_static","two_coordinated_random_walk"]
clues = ["ucb","anomaly_upper_tail"]
for g in groups:
    for c in clues:
        p = os.path.join(base, g, "raw_results", c, "obstacle_field", "episode_results.json")
        if os.path.exists(p):
            n = len(json.load(open(p, encoding="utf-8")))
            print(f"{g}/{c}: {n} eps")
        else:
            print(f"{g}/{c}: no file")
