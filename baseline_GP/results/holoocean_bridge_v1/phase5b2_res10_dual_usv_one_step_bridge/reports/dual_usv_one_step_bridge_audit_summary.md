# Phase 5B-2 One-Step Bridge Audit Summary Report

## Audit Status
- **Overall Status**: `PASSED`
- **Audit Type**: HoloOcean Dual-USV One-Step Bridge Centralized Planner Validation

## E2E Telemetry Checkpoints
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **probe_json_exists** | `dual_usv_one_step_bridge_runtime_probe.json` exists | `True` | ✅ |
| **trace_json_exists** | `dual_usv_one_step_bridge_tick_trace.json` exists | `True` | ✅ |
| **trace_csv_exists** | `dual_usv_one_step_bridge_tick_trace.csv` exists | `True` | ✅ |
| **summary_json_exists** | `dual_usv_one_step_bridge_summary.json` exists | `True` | ✅ |
| **sensor_json_exists** | `dual_usv_one_step_bridge_sensor_sources.json` exists | `True` | ✅ |
| **collision_json_exists**| `dual_usv_one_step_bridge_collision_metrics.json` exists | `True` | ✅ |
| **config_json_exists** | `dual_usv_one_step_bridge_config.json` exists | `True` | ✅ |
| **summary_md_exists** | `dual_usv_one_step_bridge_summary.md` summary exists | `True` | ✅ |
| **paths_png_exists** | `dual_usv_one_step_bridge_paths.png` paths map exists | `True` | ✅ |
| **sv0_start_is_25_2** | sv0 starting grid aligns with `[25, 2]` | `True` | ✅ |
| **sv1_start_is_35_2** | sv1 starting grid aligns with `[35, 2]` | `True` | ✅ |
| **sv0_target_is_24_2**| sv0 target grid aligns with `[24, 2]` | `True` | ✅ |
| **sv1_target_is_35_3**| sv1 target grid aligns with `[35, 3]` | `True` | ✅ |
| **map_id_is_res10** | Map scale limits match 81x81 boundary grid | `True` | ✅ |
| **resolution_m_is_10** | Map resolution scale is exactly `10.0m` | `True` | ✅ |
| **sensor_range_m_is_50**| Sensor range scale is exactly `50.0m` | `True` | ✅ |
| **exactly_two_usvs** | E2E setup features exactly two USV configurations | `True` | ✅ |
| **no_sonar_sensor** | No ImagingSonar/sonars defined in scenario | `True` | ✅ |
| **no_camera_sensor** | No cameras defined in scenario | `True` | ✅ |
| **no_env_step_calls** | No deprecated legacy env.step() calls | `True` | ✅ |
| **planner_intensity_input_allowed**| Planner reads intensity_map directly | `True` | ✅ |
| **no_dynamic_string_bypass**| No dynamic string concatenation bypass | `True` | ✅ |
| **no_post_holoocean_belief_update**| No GP or belief updates after execution | `True` | ✅ |
| **no_target_detection_closed_loop**| No dynamic target detection closed-loop | `True` | ✅ |
| **uses_env_act_and_tick**| Steps physical actuators and ticks synchronizer | `True` | ✅ |
| **sv0_arrived** | sv0 successfully arrived at planned target | `True` | ✅ |
| **sv1_arrived** | sv1 successfully arrived at planned target | `True` | ✅ |
| **zero_timeouts** | Zero timeouts encountered during physical execution | `True` | ✅ |
| **sv0_matches_alg** | sv0 final projected grid matches algorithm target| `True` | ✅ |
| **sv1_matches_alg** | sv1 final projected grid matches algorithm target| `True` | ✅ |
| **sv0_final_dist_ok** | sv0 final distance offset $\le$ `5.0` meters | `True` | ✅ |
| **sv1_final_dist_ok** | sv1 final distance offset $\le$ `5.0` meters | `True` | ✅ |
| **ticks_within_bounds** | E2E ticks taken is active and $\le$ `500` | `True` | ✅ |
| **min_separation_ge_30m**| Minimum separation distance is $\ge$ `30.0m` | `True` | ✅ |
| **zero_collision_fails**| Total collision violations is strictly 0 | `True` | ✅ |
| **selected_sensor_keys**| Selected sensor telemetry keys are valid | `True` | ✅ |
| **no_modified_files** | No *new* core algorithm modifications created | `True` | ✅ |

## Pre-Existing Working Tree Dirty States
- **Pre-existing modified files**: `['baseline_GP/holoocean_bridge/single_usv_policy_adapter.py', 'baseline_GP/knownmap_experiment_contract.json', 'baseline_GP/knownmap_experiment_contract_2usv_largegrid_template.json', 'baseline_GP/knownmap_experiment_contract_2usv_v1.json', 'baseline_GP/knownmap_experiment_contract_largegrid_v1.json', 'baseline_GP/marine_knownmap_runtime.py', 'baseline_GP/marine_knownmap_runtime_2usv.py', 'baseline_GP/single_usv_post_avoidance_anomaly.py', 'baseline_GP/two_usv_coordinated_post_avoidance_anomaly.py']`

*Audit verified both statically and dynamically from E2E simulation logs.*
