# Phase 5D-12 Raw Frame/Baseline Sync Audit

- Diagnostic Audit Only: `True`
- All Passed: `True`
- Phase Completed: `False`
- Phase Status: `planner_live_callback_integrated_but_live_detection_all_found_not_closed`
- Target Live Detection Success: `False`
- Target All Found Step: `None`
- Mainline update_found_mask Calls: `40`
- Mainline found_mask Updated From Live Adapter: `False`
- Teammate False Positive Steps: `[]`

## Conclusion

The 3 RangeFinder-hit ticks have target/baseline capture containers and tight pose alignment, but both target and baseline sides are missing FrontRGBCamera frames. The live search loop is therefore still not closed by perception; this audit only closes the diagnostic.

## Range-Hit Rows

| policy_step | tick_in_policy_step | tick_global | agent | beams | target_rgb | baseline_rgb | pose_delta_m | recomputed_rgb |
|---|---:|---:|---|---|---|---|---:|---:|
| 16 | 240 | 5305 | `sv0` | `[56]` | `False` | `False` | 0.000879335 | 0 |
| 16 | 241 | 5306 | `sv0` | `[58]` | `False` | `False` | 0.000879335 | 0 |
| 16 | 242 | 5307 | `sv0` | `[60]` | `False` | `False` | 0.000879335 | 0 |

## Checks

| Check | Passed |
|---|---|
| `core_runtime_and_search_algorithm_not_modified` | `True` |
| `diagnostic_audit_only` | `True` |
| `expected_range_hit_case_count` | `True` |
| `json_parse_ok` | `True` |
| `live_planner_callback_integrated` | `True` |
| `mainline_update_found_mask_called_but_not_updated` | `True` |
| `phase_correctly_not_completed` | `True` |
| `phase_name_matches` | `True` |
| `py_compile_ok` | `True` |
| `range_hit_capture_containers_present` | `True` |
| `range_hit_pose_alignment_tight` | `True` |
| `range_hit_recomputed_rgb_zero` | `True` |
| `range_hit_rgb_frames_missing_on_both_sides` | `True` |
| `range_hit_rows_are_expected_ticks` | `True` |
| `recommended_rule_reused` | `True` |
| `required_paths_exist` | `True` |
| `rgb_positive_rows_have_visuals` | `True` |
| `scope_boundaries_ok` | `True` |
| `source_zero_rgb_not_recovered_by_recompute` | `True` |
| `summary_reports_core_unmodified` | `True` |
| `teammate_negative_clean` | `True` |
| `truth_flags_false` | `True` |
