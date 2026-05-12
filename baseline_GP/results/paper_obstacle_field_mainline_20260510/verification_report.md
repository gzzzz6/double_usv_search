# Phase 6 Verification Report

**Verified:** 2026-05-10
**Data root:** `F:\pythonprojects\baseline_GP\results\paper_obstacle_field_mainline_20260510`
**Status:** PASSED

## Episode Counts
Total: **120** / 120

| Group | Episodes | time_to_all_found=None |
|---|---|---|
| single_static | 20 | 7 |
| single_random_walk | 20 | 6 |
| two_independent_static | 20 | 15 |
| two_independent_random_walk | 20 | 13 |
| two_coordinated_static | 20 | 11 |
| two_coordinated_random_walk | 20 | 9 |

## Distributions

- **map_kind:** {'obstacle_field': 120}
- **run_mode:** {'full': 120}
- **max_iters:** {240: 120}
- **viewpoint_generation_mode:** {'simple_ring_v1': 120}
- **path_safety_mode:** {'soft_clearance_astar_v1': 120}
- **anomaly_tail_quantile:** {0.9: 120}
- **anomaly_weight_lambda:** {1.25: 120}
- **team_path_avoidance_mode:** {'off': 40, 'reservation_v1': 80}