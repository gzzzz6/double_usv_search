# Phase 5C-2 HoloOcean Multistep Smoke Audit Summary

## Status
- Overall: `PASSED`
- Checks: `100`

## Checks
| Check | Result |
| :--- | :---: |
| `all_final_projections_match_targets` | `True` |
| `all_gp_counts_consistent` | `True` |
| `all_peak_ratio_valid` | `True` |
| `all_remaining_mass_valid` | `True` |
| `all_search_info_no_nan` | `True` |
| `all_search_info_shape_ok` | `True` |
| `all_search_info_valid` | `True` |
| `all_static_targets_unchanged` | `True` |
| `all_step_tick_counts_in_bounds` | `True` |
| `all_steps_detect_targets` | `True` |
| `all_steps_gp_update` | `True` |
| `all_steps_have_two_assignments` | `True` |
| `all_steps_local_trace_written` | `True` |
| `all_steps_local_update` | `True` |
| `all_steps_physical_called` | `True` |
| `all_steps_physical_success` | `True` |
| `all_steps_search_info_update` | `True` |
| `all_steps_team_miss_update` | `True` |
| `all_steps_team_trace_written` | `True` |
| `all_steps_update_found_mask` | `True` |
| `assignment_mode_coordinated` | `True` |
| `audit_script_exists` | `True` |
| `clue_sigma_m_is_30` | `True` |
| `collision_fail_ticks_zero` | `True` |
| `collision_json_exists` | `True` |
| `collision_json_parse_ok` | `True` |
| `collision_min_sep_ge_warning` | `True` |
| `completed_steps_valid` | `True` |
| `config_json_exists` | `True` |
| `config_json_parse_ok` | `True` |
| `episode_seed_is_0` | `True` |
| `exactly_two_usvs` | `True` |
| `fallback_count_total_zero` | `True` |
| `found_count_monotonic` | `True` |
| `found_final_nonnegative` | `True` |
| `found_json_exists` | `True` |
| `found_json_matches_summary_found` | `True` |
| `found_json_matches_summary_steps` | `True` |
| `found_json_parse_ok` | `True` |
| `git_changes_limited_to_phase_dir` | `True` |
| `git_status_json_exists` | `True` |
| `git_status_json_parse_ok` | `True` |
| `gp_counts_nondecreasing` | `True` |
| `gp_final_counts_consistent` | `True` |
| `gp_final_ge_initial` | `True` |
| `hit_branch_optional_but_consistent` | `True` |
| `hit_update_called_when_new_found` | `True` |
| `initial_usvs_match_phase5b` | `True` |
| `map_is_81x81_res10` | `True` |
| `max_policy_steps_is_4` | `True` |
| `only_allowed_sensors_configured` | `True` |
| `paths_png_exists` | `True` |
| `policy_name_correct` | `True` |
| `policy_steps_sequential` | `True` |
| `policy_trace_csv_exists` | `True` |
| `policy_trace_json_exists` | `True` |
| `policy_trace_json_parse_ok` | `True` |
| `runtime_local_trace_count_matches` | `True` |
| `runtime_team_trace_count_matches` | `True` |
| `sensor_json_exists` | `True` |
| `sensor_json_parse_ok` | `True` |
| `sensor_total_ticks_matches_summary` | `True` |
| `smoke_script_exists` | `True` |
| `source_contains_ExecutionStepResult` | `True` |
| `source_contains__apply_joint_assignment_to_locals` | `True` |
| `source_contains__apply_team_miss_updates` | `True` |
| `source_contains__joint_assign_two_usv_segments` | `True` |
| `source_contains__resolve_execution_conflict` | `True` |
| `source_contains__sample_and_update_team_gp` | `True` |
| `source_contains__update_local_after_execution` | `True` |
| `source_contains__update_team_search_info_state` | `True` |
| `source_contains_apply_known_occupancy_constraints` | `True` |
| `source_contains_build_staleness_map` | `True` |
| `source_contains_detect_targets` | `True` |
| `source_contains_grid_to_world` | `True` |
| `source_contains_hit_update_intensity` | `True` |
| `source_contains_predict_intensity` | `True` |
| `source_contains_refresh_last_seen` | `True` |
| `source_contains_step_targets` | `True` |
| `source_contains_update_found_mask` | `True` |
| `source_contains_world_to_grid` | `True` |
| `source_imports_holoocean` | `True` |
| `source_no_env_step` | `True` |
| `source_no_runtime_execute_next_step` | `True` |
| `source_no_sonar_or_camera` | `True` |
| `source_uses_env_act` | `True` |
| `source_uses_env_tick` | `True` |
| `summary_json_exists` | `True` |
| `summary_json_parse_ok` | `True` |
| `summary_md_exists` | `True` |
| `summary_no_physical_failure` | `True` |
| `target_motion_static` | `True` |
| `tick_trace_count_matches_summary` | `True` |
| `tick_trace_csv_exists` | `True` |
| `tick_trace_has_policy_step` | `True` |
| `tick_trace_has_projection` | `True` |
| `tick_trace_json_exists` | `True` |
| `tick_trace_json_parse_ok` | `True` |
| `tick_trace_nonempty` | `True` |
| `tick_trace_sensor_keys_valid` | `True` |

## Metrics
```json
{
  "completed_policy_steps": 4,
  "max_policy_steps": 4,
  "terminated_reason": "max_policy_steps",
  "total_physical_ticks": 403,
  "found_count_final": 0,
  "hit_branch_covered": false,
  "gp_n_obs_initial": 48,
  "gp_n_obs_final": 240,
  "fallback_count_total": 0,
  "min_inter_vessel_distance_m": 99.99850463462172,
  "collision_warning_ticks": 0,
  "collision_fail_ticks": 0,
  "outside_phase_new_or_changed": []
}
```
