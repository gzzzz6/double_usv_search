# Phase 5D-11 RGB/Range Sync Visual Diagnostic

- Source Phase: `phase5d10_live_planner_standoff_viewpoint_search`
- Source 5D-10 audit all_passed is false: `True`
- Control Case Accepted: `True`
- Target Failure Static Replay Accepted Count: `3`
- Target Failure Static Replay Accepted Cases: `['target_range_hit_failure_1', 'target_range_hit_failure_2', 'target_range_hit_failure_3']`

| case | accepted | replay_range_m | replay_rel_bearing | src_step | src_phase | src_rgb | src_local_candidates | replay_rgb | replay_white_neutral | replay_local_candidates | replay_hit_beams | overlay |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| control_5d9_planner_front_center_30m | True | 30.000 | 0.000 | None | static_control | None | None | 91 | 22 | 1 | [30] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_control_5d9_planner_front_center_30m_tick7_overlay.png |
| target_range_hit_failure_1 | True | 23.120 | -26.015 | 16 | post_arrival_scan | 0 | 0 | 56 | 38 | 1 | [55, 56, 57] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_target_range_hit_failure_1_tick13_overlay.png |
| target_range_hit_failure_2 | True | 23.120 | -28.015 | 16 | post_arrival_scan | 0 | 0 | 56 | 40 | 1 | [57, 58, 59] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_target_range_hit_failure_2_tick13_overlay.png |
| target_range_hit_failure_3 | True | 23.120 | -30.070 | 16 | post_arrival_scan | 0 | 0 | 68 | 42 | 1 | [60] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_target_range_hit_failure_3_tick13_overlay.png |
| target_best_candidate_failure | False | 8.469 | -139.507 | 19 | standoff_viewpoint_hold | 9509 | 6 | 361 | 6 | 0 | [] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_target_best_candidate_failure_tick13_overlay.png |
| target_large_diff_failure | False | 2.909 | 93.220 | 18 | post_arrival_scan | 24542 | 0 | 2 | 1 | 0 | [] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_target_large_diff_failure_tick13_overlay.png |
| target_standoff_candidate_failure | False | 8.469 | -139.507 | 19 | standoff_viewpoint_hold | 9509 | 6 | 93 | 4 | 0 | [] | baseline_GP\results\holoocean_bridge_v1\phase5d11_live_target_rgb_range_sync_diagnostic\visuals\phase5d11_target_standoff_candidate_failure_tick7_overlay.png |

This diagnostic is audit-only. Source 5D-10 target truth is used to reconstruct static visual cases and labels, not as a detection input.
