# Phase 5E Bridge Clue Sensor Search Audit

- All Passed: `True`
- Phase Completed: `True`
- Phase Status: `live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed`
- Audit Conclusion: `bridge_clue_gp_observations_with_rgb_rf_only_found_mask_trigger_closed_target_search`
- Target All Found Step: `20`
- Target Accepted Candidate From RGB Sync Count: `33`
- Teammate False Positive Steps: `[]`
- Bridge Clue Observation Count: `756`
- Bridge Clue Rows Used For GP: `756`
- Bridge Clue Rows Used For Detection: `0`
- Baseline Target-Induced Clue Used For GP: `False`
- Clue Directly Updates Found Mask: `False`
- RGB/RF Detection Updates Found Mask: `True`

## Stage Report

| Stage | Completed |
|---|---|
| `5E-0` | `True` |
| `5E-1` | `True` |
| `5E-2` | `True` |
| `5E-3` | `True` |
| `5E-4` | `True` |

## Accepted RGB Sync Events

| step | tick | agent | target_rgb_tick | baseline_rgb_tick | target_offset | baseline_offset | range_m | beams |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 20 | 25 | `sv0` | 19 | 31 | -6 | 6 | 10.069 | `[0, 1, 2]` |
| 20 | 26 | `sv0` | 19 | 31 | -7 | 5 | 10.171 | `[0, 1, 2]` |
| 20 | 27 | `sv0` | 19 | 31 | -8 | 4 | 10.279 | `[0, 1]` |
| 20 | 28 | `sv0` | 25 | 31 | -3 | 3 | 10.289 | `[0, 1]` |
| 20 | 29 | `sv0` | 25 | 37 | -4 | 8 | 10.386 | `[0, 1]` |
| 20 | 30 | `sv0` | 25 | 37 | -5 | 7 | 10.488 | `[0, 1]` |
| 20 | 31 | `sv0` | 25 | 37 | -6 | 6 | 10.595 | `[0, 1]` |
| 20 | 32 | `sv0` | 25 | 37 | -7 | 5 | 10.710 | `[0]` |
| 20 | 33 | `sv0` | 25 | 37 | -8 | 4 | 10.835 | `[0]` |
| 20 | 34 | `sv0` | 37 | 31 | 3 | -3 | 10.975 | `[0]` |
| 20 | 35 | `sv0` | 37 | 31 | 2 | -4 | 11.147 | `[0]` |
| 20 | 64 | `sv0` | 67 | 61 | 3 | -3 | 12.740 | `[60]` |
| 20 | 65 | `sv0` | 67 | 73 | 2 | 8 | 12.734 | `[58, 59, 60]` |
| 20 | 66 | `sv0` | 67 | 73 | 1 | 7 | 12.856 | `[57, 58, 59]` |
| 20 | 67 | `sv0` | 73 | 73 | 6 | 6 | 12.933 | `[56, 57, 58]` |
| 20 | 68 | `sv0` | 73 | 73 | 5 | 5 | 12.987 | `[54, 55, 56]` |
| 20 | 69 | `sv0` | 73 | 73 | 4 | 4 | 13.206 | `[53, 54, 55]` |
| 20 | 70 | `sv0` | 73 | 73 | 3 | 3 | 13.199 | `[52, 53]` |
| 20 | 71 | `sv0` | 73 | 73 | 2 | 2 | 13.368 | `[50, 51, 52]` |
| 20 | 72 | `sv0` | 73 | 73 | 1 | 1 | 13.387 | `[49, 50]` |
| 20 | 73 | `sv0` | 73 | 73 | 0 | 0 | 13.533 | `[48, 49]` |
| 20 | 74 | `sv0` | 73 | 73 | -1 | -1 | 13.727 | `[46, 47, 48]` |
| 20 | 75 | `sv0` | 79 | 79 | 4 | 4 | 13.721 | `[45, 46]` |
| 20 | 76 | `sv0` | 79 | 79 | 3 | 3 | 13.865 | `[44, 45]` |
| 20 | 77 | `sv0` | 85 | 73 | 8 | -4 | 13.962 | `[43, 44]` |
| 20 | 78 | `sv0` | 85 | 73 | 7 | -5 | 14.080 | `[42, 43]` |
| 20 | 79 | `sv0` | 85 | 73 | 6 | -6 | 14.372 | `[40, 41]` |
| 20 | 80 | `sv0` | 85 | 73 | 5 | -7 | 14.447 | `[39, 40]` |
| 20 | 81 | `sv0` | 85 | 73 | 4 | -8 | 14.489 | `[38, 39]` |
| 20 | 82 | `sv0` | 85 | 85 | 3 | 3 | 14.634 | `[37, 38]` |
| 20 | 83 | `sv0` | 85 | 85 | 2 | 2 | 14.780 | `[36, 37]` |
| 20 | 84 | `sv0` | 85 | 85 | 1 | 1 | 14.925 | `[35, 36]` |
| 20 | 85 | `sv0` | 85 | 85 | 0 | 0 | 15.066 | `[34, 35]` |

## Checks

| Check | Passed |
|---|---|
| `adapter_returned_mainline_detected_mask` | `True` |
| `baseline_target_induced_clue_disabled` | `True` |
| `bridge_clue_sensor_enabled_and_traced` | `True` |
| `candidate_fusion_shared_found` | `True` |
| `clue_not_detection_or_found_trigger` | `True` |
| `core_runtime_and_search_algorithm_not_modified` | `True` |
| `json_parse_ok` | `True` |
| `live_planner_mainline_path` | `True` |
| `multicamera_coverage_enabled` | `True` |
| `no_stop_scan_used` | `True` |
| `original_update_found_mask_closed_all_found` | `True` |
| `outputs_in_independent_phase_dir` | `True` |
| `phase_goal_completed` | `True` |
| `phase_name_matches` | `True` |
| `py_compile_ok` | `True` |
| `recommended_rule_reused` | `True` |
| `required_paths_exist` | `True` |
| `rgb_rf_remains_found_trigger` | `True` |
| `rgb_sync_fix_enabled_and_used` | `True` |
| `scope_boundaries_ok` | `True` |
| `target_accepted_candidates_from_rgb_sync` | `True` |
| `teammate_negative_clean` | `True` |
| `truth_flags_false` | `True` |
