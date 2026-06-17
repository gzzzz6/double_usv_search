# Phase 5D-1 Audit Summary

- Recommended Rule: `sphere_blob_any_hit`
- Validation Scene Count: `42`
- Target-only Outcome Counts: `{'true_positive': 10}`
- Target-with-teammate Outcome Counts: `{'true_positive': 1, 'false_negative': 2}`
- Teammate-only Outcome Counts: `{'true_negative': 27}`
- Teammate False Positive Scenes: `[]`
- Target False Negative Scenes: `['coexist_sphere_center_35m_teammate_right_inner_20m', 'coexist_sphere_left_inner_35m_teammate_right_outer_35m']`
- Max Fan Reliable Distance: `35.0`
- All Passed: `False`

| Check | Passed |
|---|---|
| `all_target_present_true_positive` | `False` |
| `all_teammate_only_true_negative` | `True` |
| `base_py_compile_ok` | `True` |
| `baseline_false_positive_zero` | `True` |
| `calibration_config_parse_ok` | `True` |
| `calibration_git_status_parse_ok` | `True` |
| `calibration_summary_parse_ok` | `True` |
| `calibration_true_positive` | `True` |
| `candidate_reference_present` | `True` |
| `candidate_rule_matrix_parse_ok` | `True` |
| `candidate_rule_summary_parse_ok` | `True` |
| `conservative_reliable_distance_remains_35m` | `True` |
| `holo_py_compile_ok` | `True` |
| `no_semantic_or_sonar_detection` | `True` |
| `phase_limited_git_changes` | `True` |
| `phase_name_matches` | `True` |
| `planned_scene_counts_ok` | `True` |
| `recommended_rule_is_fixed_5d0_rule` | `True` |
| `recommended_rule_parse_ok` | `True` |
| `recomputed_evidence_parse_ok` | `True` |
| `required_paths_exist` | `True` |
| `static_target_boundary_ok` | `True` |
| `target_and_teammate_types_correct` | `True` |
| `target_with_teammate_true_positive` | `False` |
| `truth_flags_false` | `True` |
| `validation_config_parse_ok` | `True` |
| `validation_events_parse_ok` | `True` |
| `validation_git_status_parse_ok` | `True` |
| `validation_matrix_counts_ok` | `True` |
| `validation_outputs_present` | `True` |
| `validation_rule_matrix_parse_ok` | `True` |
| `validation_scene_results_parse_ok` | `True` |
| `validation_summary_parse_ok` | `True` |
