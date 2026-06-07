# Phase 4D-moving Static & Dynamic Search Audit Summary Report

## Audit Status
- **Overall Status**: `PASSED`
- **Audit Type**: 10m E2E Closed-Loop Dynamic Cross-Grid Search Validation

## Crucial Execution Note
> [!NOTE]
> - **Dynamic target observed cell changed across grid cells.**
> - **Found status**: `True`.
> - **If found=false, found/update chain is not validated in this run.**

## Detailed Checks Table

| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **decisions_json_exists** | `dynamic_target_search_res10_moving_decisions.json` exists | `True` | ✅ |
| **decisions_csv_exists** | `dynamic_target_search_res10_moving_decisions.csv` exists | `True` | ✅ |
| **tick_trace_exists** | `dynamic_target_search_res10_moving_tick_trace.csv` exists | `True` | ✅ |
| **policy_trace_exists** | `dynamic_target_search_res10_moving_policy_trace_rows.json` exists| `True` | ✅ |
| **target_manifest_exists**| `dynamic_target_search_res10_moving_target_trace.json` exists | `True` | ✅ |
| **found_events_exists** | `dynamic_target_search_res10_moving_found_events.json` exists | `True` | ✅ |
| **summary_md_exists** | `dynamic_target_search_res10_moving_summary.md` summary exists | `True` | ✅ |
| **route_map_exists** | `dynamic_target_search_res10_moving_route_map.png` route map exists | `True` | ✅ |
| **map_id_is_res10** | Map ID is `openwater_open_res10_v1` | `True` | ✅ |
| **world_is_openwater** | HoloOcean world is `OpenWater` | `True` | ✅ |
| **package_name_is_ocean** | Package name is `Ocean` | `True` | ✅ |
| **cell_size_m_is_10** | Cell size is `10.0` meters | `True` | ✅ |
| **origin_is_correct** | Origin XY is `[-400.0, 400.0]` | `True` | ✅ |
| **agents_contain_both** | Scenario agents list contains `sv` and `target` | `True` | ✅ |
| **sv_control_scheme_0** | Search USV runs in `control_scheme=0` twin-prop mode | `True` | ✅ |
| **target_scheme_1** | Target runs in `control_scheme=1` tracker mode | `True` | ✅ |
| **no_camera_sensor** | No cameras defined in scenario config | `True` | ✅ |
| **no_sonar_sensor** | No sonars defined in scenario config | `True` | ✅ |
| **target_agent_exists** | Target agent `target` exists | `True` | ✅ |
| **no_target_prop** | Standalone dynamic target agent runs without prop spawn | `True` | ✅ |
| **sv_start_40_40** | Search USV starts at `(40, 40)` | `True` | ✅ |
| **target_start_45_60** | Dynamic target starts at `(45, 60)` | `True` | ✅ |
| **target_schedule** | Schedule includes key cells `(45, 60)`, `(40, 55)`, `(35, 50)`, `(30, 45)` | `True` | ✅ |
| **target_observed_cell**| Observed cell retrieved from LocationSensor per step | `True` | ✅ |
| **target_trace_len** | Target trace length matches actual steps count | `True` | ✅ |
| **target_observed_bounds**| Target observed cells are strictly within grid bounds | `True` | ✅ |
| **target_pos_source** | Position source labeled as `holoocean_agent_projection` | `True` | ✅ |
| **unique_observed_cells** | Observed target cells count $\ge$ 2 | `True` | ✅ |
| **target_changed** | target_cell_changed is true | `True` | ✅ |
| **at_least_one_changed** | At least one record has changed == true | `True` | ✅ |
| **cross_grid_valid** | target_cross_grid_motion_valid is true | `True` | ✅ |
| **no_step_targets** | Smoke script does not directly invoke `step_targets` | `True` | ✅ |
| **motion_mode_static** | Policy planning run with `target_motion_mode="static"` | `True` | ✅ |
| **policy_name_correct** | Active policy is `marine_knownmap_path_v2_infosampled` | `True` | ✅ |
| **viewpoint_gen_ring** | viewpoint generation mode is `simple_ring_v1` | `True` | ✅ |
| **path_safety_astar** | path planning safety runs `soft_clearance_astar_v1` | `True` | ✅ |
| **clue_acq_mode_ucb** | clue acquisition mode is `ucb` | `True` | ✅ |
| **resolution_m_is_10** | state parameter `resolution_m` == `10.0` | `True` | ✅ |
| **sensor_range_m_is_50**| state parameter `sensor_range_m` == `50.0` | `True` | ✅ |
| **sensor_range_cells** | state parameter `sensor_range_cells` == `5` | `True` | ✅ |
| **gp_length_scale** | state parameter `gp_length_scale_m` == `40.0` | `True` | ✅ |
| **clue_sigma_m_is_40** | state parameter `clue_sigma_m` == `40.0` | `True` | ✅ |
| **clue_sigma_cells** | state parameter `clue_sigma_cells` == `4` | `True` | ✅ |
| **segment_start_anch** | segment_path[0] matches SV pos before step | `True` | ✅ |
| **next_cell_path_ali** | next_cell matches segment_path[1] | `True` | ✅ |
| **final_proj_matches** | projected grid cell matches planned waypoint grid | `True` | ✅ |
| **all_steps_arrived** | Zero timeouts encountered (100% arrival rate) | `True` | ✅ |
| **timeout_count_is_0** | Timeout count == `0` | `True` | ✅ |
| **max_dist_lte_5m** | Max distance to physical waypoint $\le$ `5.0` meters | `True` | ✅ |
| **found_non_decreasing**| Found count is monotonic non-decreasing | `True` | ✅ |
| **steps_increasing** | completed steps is strictly monotonic increasing | `True` | ✅ |
| **remaining_mass_valid**| remaining mass holds non-negative valid values | `True` | ✅ |
| **peak_intensity_valid**| peak intensity ratio holds non-negative valid values | `True` | ✅ |
| **reason_is_correct** | if target discovered, `terminated_reason == all_found` | `True` | ✅ |
| **smoke_no_simple** | Standalone script compiles on `OpenWater` (no Simple) | `True` | ✅ |
| **smoke_no_injections**| Statically audited to contain zero dynamic loader hacks| `True` | ✅ |
| **smoke_no_shortcuts** | Search SV is strictly algorithm-driven (no fixed paths) | `True` | ✅ |
| **uses_policy_planning**| Smoke script uses standard plan_next_policy_cell | `True` | ✅ |
| **uses_finalize_hooks**| Smoke script uses finalize_policy_step_after_holoocean | `True` | ✅ |

### Found Branch Checks (Applicable)
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **found_step_lte_act** | if target discovered, `found_step <= actual_steps` | `True` | ✅ |
| **found_cells_dist** | if target discovered, distance is $\le$ `5` grid cells | `True` | ✅ |
| **mass_converged_0** | if target discovered, remaining mass converged to `0.0`| `True` | ✅ |
| **found_count_final_1** | Final found count is exactly 1 | `True` | ✅ |

*Audit verified both statically and dynamically from simulation logs.*
