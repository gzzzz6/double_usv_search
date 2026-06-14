# Phase 5C-4D RGB+RangeFinder Robustness Boundary Audit Summary

## Metrics
- Scene Count: `13`
- Outcome Counts: `{'true_negative': 2, 'true_positive': 5, 'false_negative': 6}`
- Failure Counts: `{'none': 7, 'false_negative_no_range_hit': 2, 'false_negative_no_rgb_signature_and_no_range_hit': 2, 'false_negative_no_rgb_signature': 2}`
- Truth Used For Detection: `False`
- Recommendation: `do_not_treat_as_general_detector_yet; use only in validated front/center/static conditions or add stronger vision/geometric gating`
- All Passed: `True`

## Checks
| Check | Passed |
|---|---|
| `adapter_logic_not_modified` | `True` |
| `all_scene_launch_ok` | `True` |
| `all_scenes_rangefinder_output` | `True` |
| `all_scenes_rgb_output` | `True` |
| `audit_source_readable` | `True` |
| `base_py_compile_ok` | `True` |
| `boundary_failures_documented_or_zero` | `True` |
| `boundary_matrix_json_parse_ok` | `True` |
| `compiled_expected_scripts` | `True` |
| `config_json_parse_ok` | `True` |
| `coverage_distance` | `True` |
| `coverage_distractors` | `True` |
| `coverage_orientation` | `True` |
| `coverage_position` | `True` |
| `coverage_range_boundaries` | `True` |
| `detection_events_json_parse_ok` | `True` |
| `each_scene_has_rgb_artifact` | `True` |
| `event_has_rgb_and_range_evidence` | `True` |
| `found_trigger_rule_applied_all_events` | `True` |
| `git_changes_limited_to_phase` | `True` |
| `git_status_json_parse_ok` | `True` |
| `holo_py_compile_ok` | `True` |
| `identity_ambiguity_recorded` | `True` |
| `no_core_runtime_imports` | `True` |
| `outcome_matrix_has_effective_cases` | `True` |
| `overview_visual_exists` | `True` |
| `perception_sensors_exact` | `True` |
| `phase_name_matches` | `True` |
| `range_hit_without_target_rgb_observed` | `True` |
| `rangefinder_not_identity_source` | `True` |
| `required_named_scenes_present` | `True` |
| `required_paths_exist` | `True` |
| `rgb_target_without_range_hit_observed` | `True` |
| `scene_count_matches` | `True` |
| `scene_results_json_parse_ok` | `True` |
| `semantic_not_used_for_detection` | `True` |
| `sonar_not_used` | `True` |
| `source_does_not_call_baseline_detect_targets` | `True` |
| `source_does_not_use_env_step` | `True` |
| `source_uses_env_act_tick` | `True` |
| `summary_json_parse_ok` | `True` |
| `summary_recommendation_present` | `True` |
| `truth_flags_false` | `True` |
