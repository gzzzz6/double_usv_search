# Phase 5C-4E RGB + Multi-Ray RangeFinder Fan Audit Summary

## Metrics
- Scene Count: `15`
- Any-Hit Outcomes: `{'true_negative': 4, 'true_positive': 7, 'false_negative': 4}`
- Aligned-Hit Outcomes: `{'true_negative': 4, 'true_positive': 4, 'false_negative': 7}`
- Left/Right Any Fixed: `True`
- Left/Right Aligned Fixed: `False`
- Boundary Conclusion: `multi-ray fan helps coverage, but aligned sector mapping needs calibration before becoming the primary adapter`
- All Passed: `True`

## Checks
| Check | Passed |
|---|---|
| `all_scene_launch_ok` | `True` |
| `all_scenes_rangefinder_output` | `True` |
| `all_scenes_rgb_output` | `True` |
| `audit_source_readable` | `True` |
| `base_py_compile_ok` | `True` |
| `boundary_conclusion_present` | `True` |
| `boundary_matrix_json_parse_ok` | `True` |
| `compiled_expected_scripts` | `True` |
| `config_json_parse_ok` | `True` |
| `coverage_distances` | `True` |
| `coverage_distractors` | `True` |
| `coverage_positions` | `True` |
| `detection_events_json_parse_ok` | `True` |
| `each_scene_has_rgb_artifact` | `True` |
| `event_has_required_fields` | `True` |
| `false_positive_lists_present` | `True` |
| `found_rules_applied_all_events` | `True` |
| `git_changes_limited_to_phase` | `True` |
| `git_status_json_parse_ok` | `True` |
| `holo_py_compile_ok` | `True` |
| `left_right_aligned_result_recorded` | `True` |
| `left_right_any_result_recorded` | `True` |
| `matrix_has_required_fields` | `True` |
| `multiray_configured` | `True` |
| `native_multiray_diagnostic_recorded` | `True` |
| `no_core_runtime_imports` | `True` |
| `observed_beam_arrays_multiray` | `True` |
| `outcome_counts_present` | `True` |
| `overview_visual_exists` | `True` |
| `perception_sensors_exact` | `True` |
| `phase_name_matches` | `True` |
| `rangefinder_not_identity_source` | `True` |
| `required_named_scenes_present` | `True` |
| `required_paths_exist` | `True` |
| `rgb_signature_logic_preserved` | `True` |
| `scene_count_matches` | `True` |
| `scene_results_json_parse_ok` | `True` |
| `semantic_not_used_for_detection` | `True` |
| `sonar_not_used` | `True` |
| `source_does_not_call_baseline_detect_targets` | `True` |
| `source_does_not_use_env_step` | `True` |
| `source_uses_env_act_tick` | `True` |
| `summary_json_parse_ok` | `True` |
| `truth_flags_false` | `True` |
| `two_rules_evaluated` | `True` |
