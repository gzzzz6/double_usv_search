# Phase 5D-15 Continuous Rolling RGB/RF Sync Audit

- All Passed: `True`
- Phase Completed: `True`
- Phase Status: `live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed`
- Target All Found Step: `20`
- Target Accepted Candidate From RGB Sync Count: `32`
- Teammate False Positive Steps: `[]`

## Accepted RGB Sync Events

| step | tick | agent | target_rgb_tick | baseline_rgb_tick | target_offset | baseline_offset | range_m | beams |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 20 | 17 | `sv0` | 14 | 14 | -3 | -3 | 10.143 | `[2, 3, 4, 5, 6, 7]` |
| 20 | 18 | `sv0` | 14 | 14 | -4 | -4 | 10.109 | `[1, 2, 3, 4, 5, 6]` |
| 20 | 19 | `sv0` | 14 | 14 | -5 | -5 | 10.153 | `[1, 2, 3, 4, 5]` |
| 20 | 20 | `sv0` | 14 | 14 | -6 | -6 | 10.408 | `[0, 1, 2, 3, 4, 5]` |
| 20 | 21 | `sv0` | 14 | 14 | -7 | -7 | 10.428 | `[0, 1, 2, 3, 4]` |
| 20 | 22 | `sv0` | 14 | 14 | -8 | -8 | 10.679 | `[0, 1, 2, 3, 4]` |
| 20 | 23 | `sv0` | 26 | 26 | 3 | 3 | 10.583 | `[0, 1, 2, 3]` |
| 20 | 24 | `sv0` | 26 | 26 | 2 | 2 | 10.749 | `[0, 1, 2, 3]` |
| 20 | 25 | `sv0` | 26 | 26 | 1 | 1 | 10.932 | `[0, 1, 2]` |
| 20 | 26 | `sv0` | 26 | 26 | 0 | 0 | 11.140 | `[0, 1, 2]` |
| 20 | 27 | `sv0` | 26 | 26 | -1 | -1 | 11.399 | `[0, 1, 2]` |
| 20 | 28 | `sv0` | 26 | 26 | -2 | -2 | 11.354 | `[0, 1]` |
| 20 | 29 | `sv0` | 26 | 26 | -3 | -3 | 11.562 | `[0, 1]` |
| 20 | 30 | `sv0` | 26 | 26 | -4 | -4 | 11.820 | `[0, 1]` |
| 20 | 31 | `sv0` | 26 | 26 | -5 | -5 | 11.747 | `[0]` |
| 20 | 32 | `sv0` | 26 | 26 | -6 | -6 | 11.940 | `[0]` |
| 20 | 33 | `sv0` | 26 | 26 | -7 | -7 | 12.161 | `[0]` |
| 20 | 55 | `sv0` | 50 | 50 | -5 | -5 | 14.582 | `[0]` |
| 20 | 56 | `sv0` | 50 | 50 | -6 | -6 | 14.563 | `[0, 1]` |
| 20 | 57 | `sv0` | 50 | 50 | -7 | -7 | 14.622 | `[0, 1]` |
| 20 | 58 | `sv0` | 50 | 50 | -8 | -8 | 14.786 | `[0, 1, 2]` |
| 20 | 59 | `sv0` | 56 | 56 | -3 | -3 | 14.836 | `[1, 2, 3]` |
| 20 | 60 | `sv0` | 68 | 68 | 8 | 8 | 14.950 | `[2, 3, 4]` |
| 20 | 61 | `sv0` | 68 | 68 | 7 | 7 | 15.015 | `[3, 4, 5]` |
| 20 | 62 | `sv0` | 68 | 68 | 6 | 6 | 15.064 | `[4, 5, 6]` |
| 20 | 63 | `sv0` | 68 | 68 | 5 | 5 | 15.026 | `[5, 6, 7]` |
| 20 | 64 | `sv0` | 68 | 68 | 4 | 4 | 15.402 | `[6, 7, 8]` |
| 20 | 65 | `sv0` | 68 | 68 | 3 | 3 | 15.194 | `[8, 9]` |
| 20 | 66 | `sv0` | 68 | 68 | 2 | 2 | 15.323 | `[9, 10, 11]` |
| 20 | 67 | `sv0` | 68 | 68 | 1 | 1 | 15.297 | `[11, 12]` |
| 20 | 68 | `sv0` | 68 | 68 | 0 | 0 | 15.406 | `[12, 13]` |
| 20 | 69 | `sv0` | 68 | 68 | -1 | -1 | 15.611 | `[13, 14, 15]` |

## Checks

| Check | Passed |
|---|---|
| `adapter_returned_mainline_detected_mask` | `True` |
| `candidate_fusion_shared_found` | `True` |
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
| `rgb_sync_fix_enabled_and_used` | `True` |
| `scope_boundaries_ok` | `True` |
| `target_accepted_candidates_from_rgb_sync` | `True` |
| `teammate_negative_clean` | `True` |
| `truth_flags_false` | `True` |
