# Phase 5B-1 One-Step Probe Audit Summary Report

## Audit Status
- **Overall Status**: `PASSED`
- **Audit Type**: Centralized 2-USV Coordinated Known-Map Runtime One-step Integrity Verification

## E2E Telemetry Checkpoints
| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **probe_json_exists** | `dual_usv_runtime_one_step_probe.json` exists | `True` | ✅ |
| **probe_csv_exists** | `dual_usv_runtime_one_step_probe.csv` exists | `True` | ✅ |
| **assignments_json_exists** | `dual_usv_runtime_one_step_assignments.json` exists | `True` | ✅ |
| **config_json_exists** | `dual_usv_runtime_one_step_config.json` exists | `True` | ✅ |
| **summary_md_exists** | `dual_usv_runtime_one_step_probe_summary.md` summary exists | `True` | ✅ |
| **policy_name_is_correct** | policy is `marine_knownmap_path_v2_infosampled_2usv` | `True` | ✅ |
| **assignment_mode_coordinated**| planner is centralized joint `coordinated` mode | `True` | ✅ |
| **team_path_avoidance** | avoidance algorithm is `reservation_v1` | `True` | ✅ |
| **path_safety_mode_astar** | safety path selection is `soft_clearance_astar_v1`| `True` | ✅ |
| **viewpoint_gen_mode** | viewpoints mode is `simple_ring_v1` | `True` | ✅ |
| **resolution_m_is_10** | Map resolution scale is exactly `10.0m` | `True` | ✅ |
| **sensor_range_m_is_50**| Sensor range scale is exactly `50.0m` | `True` | ✅ |
| **sensor_range_cells** | Sensor range cells is exactly `5` | `True` | ✅ |
| **exactly_two_usvs** | E2E setup features exactly two USV configurations | `True` | ✅ |
| **committed_segments** | Segment paths generated are active (length $\ge$ 2)| `True` | ✅ |
| **next_cells_aligned** | Next targets align with segment indices `[1]` | `True` | ✅ |
| **active_usv_exec** | Active USV correctly commits next_cell projection | `True` | ✅ |
| **waiting_usv_exec** | Waiting USV respects reservation wait projection | `True` | ✅ |
| **target_cells_bounds**| Target cells coordinates are within 81x81 bounds | `True` | ✅ |
| **no_modified_files** | Strictly zero modified frozen baseline search files | `True` | ✅ |

*Audit verified both statically and dynamically from step 1 simulation logs.*
