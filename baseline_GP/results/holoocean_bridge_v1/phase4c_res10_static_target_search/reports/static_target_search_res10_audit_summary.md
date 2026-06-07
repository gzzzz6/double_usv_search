# Phase 4C Static & Dynamic Search Audit Summary Report

## Audit Status
- **Overall Status**: `PASSED`
- **Audit Type**: 10m E2E Closed-Loop Static Target Search Validation

## Crucial Execution Note
> [!NOTE]
> - **Phase 4C did not trigger target discovery.**
> - **Closed-loop execution passed.**
> - **Hit-update/found chain not validated in this run.**

## Detailed Checks Table

| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **decisions_json_exists** | `static_target_search_res10_decisions.json` exists | `True` | ✅ |
| **decisions_csv_exists** | `static_target_search_res10_decisions.csv` exists | `True` | ✅ |
| **tick_trace_exists** | `static_target_search_res10_tick_trace.csv` exists | `True` | ✅ |
| **policy_trace_exists** | `static_target_search_res10_policy_trace_rows.json` exists| `True` | ✅ |
| **target_manifest_exists**| `static_target_search_res10_target_manifest.json` exists | `True` | ✅ |
| **found_events_exists** | `static_target_search_res10_found_events.json` exists | `True` | ✅ |
| **summary_md_exists** | `static_target_search_res10_summary.md` summary exists | `True` | ✅ |
| **route_map_exists** | `static_target_search_res10_route_map.png` route map exists | `True` | ✅ |
| **map_id_is_res10** | Map ID is `openwater_open_res10_v1` | `True` | ✅ |
| **world_is_openwater** | HoloOcean world is `OpenWater` | `True` | ✅ |
| **package_name_is_ocean** | Package name is `Ocean` | `True` | ✅ |
| **cell_size_m_is_10** | Cell size is `10.0` meters | `True` | ✅ |
| **origin_is_correct** | Origin XY is `[-400.0, 400.0]` | `True` | ✅ |
| **control_scheme_is_0**| SurfaceVessel runs in `control_scheme=0` mode | `True` | ✅ |
| **no_camera_sensor** | No cameras defined in scenario config | `True` | ✅ |
| **no_sonar_sensor** | No sonars defined in scenario config | `True` | ✅ |
| **single_sv_agent** | Scenario contains only one agent `sv` | `True` | ✅ |
| **no_target_agent** | No dynamic target proxy agent spawned | `True` | ✅ |
| **target_cell_is_20_45**| Static target truth cell set at `(20, 45)` | `True` | ✅ |
| **target_world_correct**| Target world coordinate maps to [50, 200] | `True` | ✅ |
| **target_roundtrip** | Target cell passes grid $\leftrightarrow$ world round-trip | `True` | ✅ |
| **policy_name_correct** | Active policy is `marine_knownmap_path_v2_infosampled` | `True` | ✅ |
| **viewpoint_gen_ring** | view points generated via `simple_ring_v1` | `True` | ✅ |
| **path_safety_astar** | safety nav path planning via `soft_clearance_astar_v1` | `True` | ✅ |
| **clue_acq_mode_ucb** | clue acquisition via `ucb` | `True` | ✅ |
| **resolution_m_is_10** | state parameter `resolution_m` == `10.0` | `True` | ✅ |
| **sensor_range_m_is_50**| state parameter `sensor_range_m` == `50.0` | `True` | ✅ |
| **sensor_range_cells** | state parameter `sensor_range_cells` == `5` | `True` | ✅ |
| **gp_length_scale** | state parameter `gp_length_scale_m` == `40.0` | `True` | ✅ |
| **clue_sigma_m_is_40** | state parameter `clue_sigma_m` == `40.0` | `True` | ✅ |
| **clue_sigma_cells** | state parameter `clue_sigma_cells` == `4` | `True` | ✅ |
| **final_proj_matches** | Every steps' projected cell matches next cell target | `True` | ✅ |
| **all_steps_arrived** | Zero timeouts encountered (100% arrival rate) | `True` | ✅ |
| **timeout_count_is_0** | Timeout count == `0` | `True` | ✅ |
| **max_dist_lte_5m** | Max distance to physical waypoint $\le$ `5.0` meters | `True` | ✅ |
| **actual_steps_lte120**| Total search steps $\le$ `120` | `True` | ✅ |
| **found_non_decreasing**| Found count is monotonic non-decreasing | `True` | ✅ |
| **steps_increasing** | completed steps is strictly monotonic increasing | `True` | ✅ |
| **remaining_mass_valid**| remaining mass holds non-negative valid values | `True` | ✅ |
| **peak_intensity_valid**| peak intensity ratio holds non-negative valid values | `True` | ✅ |
| **reason_is_correct** | if target discovered, `terminated_reason == all_found` | `True` | ✅ |
| **smoke_no_simple** | Standalone script compiles on `OpenWater` (no Simple) | `True` | ✅ |
| **smoke_no_injections**| Statically audited to contain zero dynamic loader hacks| `True` | ✅ |
| **smoke_no_shortcuts** | Search SV is strictly algorithm-driven (no fixed paths) | `True` | ✅ |

### Found Branch Checks (Skipped for this Not-Found run)
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **found_branch_applicable** | Found branch is applicable | `False` | ⚪ |
| **found_branch_checks_skipped** | Found branch checks are skipped | `True` | ✅ |
| **not_found_branch_valid** | Not-found branch is mathematically valid | `True` | ✅ |
| **final_sv_cell** | Final USV grid cell coordinate | `[23, 49]` | ⚪ |
| **target_cell** | Synchronized static target grid coordinate | `[20, 45]` | ⚪ |
| **final_distance_to_target_cells** | Final grid distance to target cells | `5.0` | ⚪ |
| **min_distance_to_target_cells** | Minimum grid distance to target cells | `5.0` | ⚪ |
| **steps_within_sensor_range_count** | Number of steps within 5.0 cell sensor range | `1` | ⚪ |

*Audit verified both statically and dynamically from simulation logs.*
