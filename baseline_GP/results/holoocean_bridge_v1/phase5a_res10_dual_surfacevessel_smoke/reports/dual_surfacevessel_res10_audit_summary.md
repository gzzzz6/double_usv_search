# Phase 5A Dual SurfaceVessel Waypoints Smoke Audit Summary Report

## Audit Status
- **Overall Status**: `PASSED`
- **Audit Type**: 10m OpenWater Dual-USV Waypoint-Following Physical Smoke Auditing Checks

## E2E Telemetry Checkpoints
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **tick_json_exists** | `dual_surfacevessel_res10_tick_trace.json` exists | `True` | ✅ |
| **tick_csv_exists** | `dual_surfacevessel_res10_tick_trace.csv` exists | `True` | ✅ |
| **waypoint_json_exists** | `dual_surfacevessel_res10_waypoint_summary.json` exists | `True` | ✅ |
| **agent_json_exists** | `dual_surfacevessel_res10_agent_manifest.json` exists | `True` | ✅ |
| **collision_json_exists** | `dual_surfacevessel_res10_collision_metrics.json` exists | `True` | ✅ |
| **summary_md_exists** | `dual_surfacevessel_res10_summary.md` summary exists | `True` | ✅ |
| **paths_png_exists** | `dual_surfacevessel_res10_paths.png` paths map exists | `True` | ✅ |
| **map_id_is_res10** | Map ID is `openwater_open_res10_v1` | `True` | ✅ |
| **world_is_openwater** | HoloOcean world is `OpenWater` | `True` | ✅ |
| **package_name_is_ocean** | Package name is `Ocean` | `True` | ✅ |
| **cell_size_m_is_10** | Cell size is `10.0` meters | `True` | ✅ |
| **origin_is_correct** | Origin XY is `[-400.0, 400.0]` | `True` | ✅ |
| **no_sonar_sensor** | No ImagingSonar/sonars defined in scenario | `True` | ✅ |
| **no_camera_sensor** | No cameras defined in scenario | `True` | ✅ |
| **agents_are_sv0_and_sv1**| Config contains exactly `sv0` and `sv1` agents | `True` | ✅ |
| **no_target_agent** | No dynamic target agent defined | `True` | ✅ |
| **no_target_prop** | No target prop placeholder defined | `True` | ✅ |
| **no_search_libraries** | Isolated from all core baseline search files | `True` | ✅ |
| **no_import_plan_hooks**| No imports of coordinate planner interfaces | `True` | ✅ |
| **no_search_parameters**| No found_mask/belief intensities referenced | `True` | ✅ |
| **uses_env_act_sv0_sv1** | Steps actuators using multi-agent act directives | `True` | ✅ |
| **uses_single_env_tick** | Synchronizes steps via single global env.tick() | `True` | ✅ |
| **no_env_step_calls** | No deprecated legacy env.step() calls | `True` | ✅ |
| **manifest_has_two_agents**| Manifest confirms physical setup has two agents | `True` | ✅ |
| **both_agents_scheme_0** | Both agents operate in direct twin-prop force mode| `True` | ✅ |
| **agent_names_matched** | Names matching `sv0` and `sv1` in manifest | `True` | ✅ |
| **waypoint_count_is_4**| Exactly 4 paired waypoint sets executed | `True` | ✅ |
| **waypoint_roundtrips**| Grid cells pass bidirectional roundtrip conversions | `True` | ✅ |
| **arrived_count_is_8** | Total waypoint arrived count == `8` | `True` | ✅ |
| **timeout_count_is_0** | Total waypoint timeout count == `0` | `True` | ✅ |
| **projected_matches** | Each `final_projected_cell` matches planned target| `True` | ✅ |
| **max_dist_lte_5m** | Final coordinate error limits $\le$ `5.0` meters | `True` | ✅ |
| **mean_ticks_lt_300** | Mean execution ticks per waypoint pair $<$ `300` | `True` | ✅ |
| **max_ticks_lte_400** | Maximum waypoint pair ticks $\le$ `400` | `True` | ✅ |
| **total_ticks_gt_0** | Accumulated E2E execution ticks $>$ `0` | `True` | ✅ |
| **trajectory_in_bounds**| Complete dynamic pathways mapped within bounds | `True` | ✅ |
| **min_dist_ge_30** | Minimum inter-vessel separation distance $\ge$ `30m`| `True` | ✅ |
| **collision_fail_ticks**| Total collision violations ($<$ 20m) is strictly 0 | `True` | ✅ |
| **collision_safety** | Dynamic separation compliance verification | `True` | ✅ |
| **sv0_unique_cells** | sv0 traversed $\ge$ 3 unique projected grid cells | `True` | ✅ |
| **sv1_unique_cells** | sv1 traversed $\ge$ 3 unique projected grid cells | `True` | ✅ |
| **sv0_path_length** | sv0 E2E accumulated path length $>$ `20.0` meters | `True` | ✅ |
| **sv1_path_length** | sv1 E2E accumulated path length $>$ `20.0` meters | `True` | ✅ |
| **smoke_no_simple** | Smoke compiles on `OpenWater` (no Simple) | `True` | ✅ |
| **smoke_no_injections**| Free of unsafe dynamic loading injection hacks | `True` | ✅ |

## Sensory Feedback Analysis
- **Location Sensor Failures**: `0` ticks out of `319` (`0.00%` fallback)

*Audit verified both statically and dynamically from E2E simulation logs.*
