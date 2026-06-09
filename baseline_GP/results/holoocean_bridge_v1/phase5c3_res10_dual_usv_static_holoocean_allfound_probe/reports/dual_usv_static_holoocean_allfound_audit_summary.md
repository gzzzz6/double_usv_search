# Phase 5C-3 HoloOcean All Found Probe Audit Summary

## Status
- Overall: `PASSED`
- Checks: `116`

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
| `completed_policy_steps_expected_32` | `True` |
| `completed_steps_valid` | `True` |
| `config_json_exists` | `True` |
| `config_json_parse_ok` | `True` |
| `episode_seed_is_0` | `True` |
| `exactly_two_usvs` | `True` |
| `expected_initial_target_positions_match` | `True` |
| `expected_runtime_all_found_step_is_32` | `True` |
| `expected_step_detected_target` | `True` |
| `expected_step_row_present` | `True` |
| `fallback_count_total_zero` | `True` |
| `find_times_final_32` | `True` |
| `found_count_final_is_1` | `True` |
| `found_count_monotonic` | `True` |
| `found_event_details_complete` | `True` |
| `found_event_details_present` | `True` |
| `found_expected_runtime_step_recorded` | `True` |
| `found_expected_target_positions_recorded` | `True` |
| `found_json_exists` | `True` |
| `found_json_matches_summary_found` | `True` |
| `found_json_matches_summary_reason` | `True` |
| `found_json_matches_summary_steps` | `True` |
| `found_json_parse_ok` | `True` |
| `found_mask_final_true` | `True` |
| `git_changes_limited_to_phase_dir` | `True` |
| `git_status_json_exists` | `True` |
| `git_status_json_parse_ok` | `True` |
| `gp_counts_nondecreasing` | `True` |
| `gp_final_counts_consistent` | `True` |
| `gp_final_ge_initial` | `True` |
| `hit_branch_covered_required` | `True` |
| `hit_update_called_when_new_found` | `True` |
| `initial_target_positions_match_expected` | `True` |
| `initial_usvs_match_phase5b` | `True` |
| `map_is_81x81_res10` | `True` |
| `max_policy_steps_is_40` | `True` |
| `only_allowed_sensors_configured` | `True` |
| `paths_png_exists` | `True` |
| `peak_intensity_ratio_final_zero` | `True` |
| `policy_name_correct` | `True` |
| `policy_steps_sequential` | `True` |
| `policy_trace_csv_exists` | `True` |
| `policy_trace_json_exists` | `True` |
| `policy_trace_json_parse_ok` | `True` |
| `remaining_intensity_mass_final_zero` | `True` |
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
| `terminated_reason_all_found` | `True` |
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
  "completed_policy_steps": 32,
  "max_policy_steps": 40,
  "terminated_reason": "all_found",
  "total_physical_ticks": 2769,
  "found_count_final": 1,
  "found_mask_final": [
    true
  ],
  "find_times_final": [
    32
  ],
  "hit_branch_covered": true,
  "expected_runtime_all_found_step": 32,
  "remaining_intensity_mass_final": 0.0,
  "peak_intensity_ratio_final": 0.0,
  "gp_n_obs_initial": 48,
  "gp_n_obs_final": 400,
  "found_event_details": [
    {
      "target_index": 0,
      "found_step": 32,
      "detected_usvs": [
        0
      ],
      "target_position": [
        23,
        21
      ],
      "usv_projected_cells": {
        "0": [
          20,
          25
        ]
      }
    }
  ],
  "fallback_count_total": 0,
  "min_inter_vessel_distance_m": 99.99850441416972,
  "collision_warning_ticks": 0,
  "collision_fail_ticks": 0,
  "outside_phase_new_or_changed": []
}
```
