# Phase 5C-1 Runtime-Only Multistep Audit Summary

## Status
- Overall: `PASSED`
- Checks: `76`

## Checks
| Check | Result |
| :--- | :---: |
| `probe_script_exists` | `True` |
| `audit_script_exists` | `True` |
| `config_json_exists` | `True` |
| `trace_json_exists` | `True` |
| `trace_csv_exists` | `True` |
| `found_json_exists` | `True` |
| `git_status_json_exists` | `True` |
| `config_json_parse_ok` | `True` |
| `trace_json_parse_ok` | `True` |
| `found_json_parse_ok` | `True` |
| `git_status_json_parse_ok` | `True` |
| `policy_name_correct` | `True` |
| `assignment_mode_coordinated` | `True` |
| `target_motion_static` | `True` |
| `map_is_81x81_res10` | `True` |
| `clue_sigma_m_is_30` | `True` |
| `episode_seed_is_0` | `True` |
| `max_steps_is_240` | `True` |
| `initial_usvs_match_phase5b` | `True` |
| `no_import_holoocean` | `True` |
| `no_env_act` | `True` |
| `no_env_tick` | `True` |
| `no_env_step` | `True` |
| `no_sonar_or_camera` | `True` |
| `no_target_agent` | `True` |
| `source_contains_step_targets` | `True` |
| `source_contains_predict_intensity` | `True` |
| `source_contains__joint_assign_two_usv_segments` | `True` |
| `source_contains__apply_joint_assignment_to_locals` | `True` |
| `source_contains__resolve_execution_conflict` | `True` |
| `source_contains_execute_next_step` | `True` |
| `source_contains__update_local_after_execution` | `True` |
| `source_contains_refresh_last_seen` | `True` |
| `source_contains_build_staleness_map` | `True` |
| `source_contains_apply_known_occupancy_constraints` | `True` |
| `source_contains_detect_targets` | `True` |
| `source_contains_update_found_mask` | `True` |
| `source_contains__apply_team_miss_updates` | `True` |
| `source_contains_hit_update_intensity` | `True` |
| `source_contains__sample_and_update_team_gp` | `True` |
| `source_contains__update_team_search_info_state` | `True` |
| `source_contains_gp_field` | `True` |
| `source_contains_n_obs` | `True` |
| `initial_branch_valid` | `True` |
| `trace_count_matches_completed_steps` | `True` |
| `trace_steps_sequential` | `True` |
| `all_steps_called_step_targets` | `True` |
| `all_static_targets_unchanged` | `True` |
| `all_steps_called_predict_intensity` | `True` |
| `all_steps_have_two_assignments` | `True` |
| `all_steps_apply_assignment` | `True` |
| `all_steps_resolve_conflict` | `True` |
| `all_steps_update_two_locals` | `True` |
| `all_steps_refresh_last_seen` | `True` |
| `all_steps_rebuild_staleness` | `True` |
| `all_steps_apply_known_occupancy` | `True` |
| `all_steps_detect_targets` | `True` |
| `all_steps_update_found_mask` | `True` |
| `all_steps_team_miss_update` | `True` |
| `all_steps_gp_update` | `True` |
| `all_steps_search_info_update` | `True` |
| `all_steps_team_trace_written` | `True` |
| `all_steps_local_trace_written` | `True` |
| `all_remaining_mass_valid` | `True` |
| `all_peak_ratio_valid` | `True` |
| `all_search_info_valid` | `True` |
| `all_search_info_shape_ok` | `True` |
| `all_search_info_no_nan` | `True` |
| `all_gp_counts_consistent` | `True` |
| `gp_n_obs_grew` | `True` |
| `found_count_monotonic` | `True` |
| `found_count_final_gt_0` | `True` |
| `hit_branch_or_initial_found_covered` | `True` |
| `runtime_team_trace_count_matches` | `True` |
| `runtime_local_trace_count_matches` | `True` |
| `git_changes_limited_to_phase_dir` | `True` |

## Metrics
```json
{
  "initial_all_found": false,
  "completed_steps": 32,
  "trace_rows_count": 32,
  "found_count_final": 1,
  "terminated_reason": "all_found",
  "gp_n_obs_initial": 48,
  "gp_n_obs_final": 400,
  "pre_git_status": [
    "?? baseline_GP/results/holoocean_bridge_v1/phase5c1_res10_dual_usv_static_runtime_probe/"
  ],
  "current_git_status": [
    "?? baseline_GP/results/holoocean_bridge_v1/phase5c1_res10_dual_usv_static_runtime_probe/"
  ],
  "outside_phase_new_or_changed": []
}
```