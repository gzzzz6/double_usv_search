# Phase 5C-4A-0 Semantic Camera Availability Audit Summary

## Status
- Overall: `PASSED`
- Checks: `41`
- Semantic Camera Available: `True`
- Availability Conclusion: `available`

## Checks
| Check | Result |
| :--- | :---: |
| `audit_script_exists` | `True` |
| `availability_conclusion_recorded` | `True` |
| `camera_config_expected` | `True` |
| `capture_ticks_30` | `True` |
| `conclusion_json_exists` | `True` |
| `conclusion_json_parse_ok` | `True` |
| `config_json_exists` | `True` |
| `config_json_parse_ok` | `True` |
| `control_result_recorded_when_semantic_launch_fails` | `True` |
| `git_changes_limited_to_phase_dir` | `True` |
| `git_status_json_exists` | `True` |
| `git_status_json_parse_ok` | `True` |
| `map_is_res10_81x81` | `True` |
| `no_target_or_obstacle_or_sonar_config` | `True` |
| `phase_name_correct` | `True` |
| `probe_completed` | `True` |
| `probe_script_exists` | `True` |
| `rgb_artifact_present_when_output_seen` | `True` |
| `semantic_artifacts_consistent` | `True` |
| `semantic_fields_recorded` | `True` |
| `semantic_inspection_rows_recorded` | `True` |
| `semantic_not_used_for_detection` | `True` |
| `sensor_stats_consistent` | `True` |
| `sensor_stats_json_exists` | `True` |
| `sensor_stats_json_parse_ok` | `True` |
| `single_surface_vessel_config` | `True` |
| `source_contains_rgb_camera` | `True` |
| `source_contains_semantic_camera` | `True` |
| `source_imports_holoocean` | `True` |
| `source_no_env_step` | `True` |
| `source_no_runtime_updates` | `True` |
| `source_no_sonar_sensor` | `True` |
| `source_no_target_agent` | `True` |
| `source_uses_env_act` | `True` |
| `source_uses_env_tick` | `True` |
| `start_cell_center` | `True` |
| `summary_md_exists` | `True` |
| `tick_trace_csv_exists` | `True` |
| `tick_trace_json_exists` | `True` |
| `tick_trace_json_parse_ok` | `True` |
| `tick_trace_nonempty` | `True` |

## Metrics
```json
{
  "availability_conclusion": "available",
  "semantic_camera_available": true,
  "semantic_scenario_launch_ok": true,
  "semantic_output_seen": true,
  "semantic_error": "",
  "control_rgb_scenario_ok": null,
  "control_rgb_output_seen": null,
  "control_error": "",
  "rgb_output_seen": true,
  "semantic_first_stats": {
    "present": true,
    "shape": [
      240,
      320,
      4
    ],
    "dtype": "uint8",
    "size": 307200,
    "min": 0.0,
    "max": 255.0,
    "unique_count": 2,
    "finite_ratio": 1.0
  },
  "rgb_first_stats": {
    "present": true,
    "shape": [
      240,
      320,
      4
    ],
    "dtype": "uint8",
    "size": 307200,
    "min": 72.0,
    "max": 255.0,
    "unique_count": 180,
    "finite_ratio": 1.0
  },
  "wall_time_s": 10.994766299999998,
  "memory_before_mb": 101.44140625,
  "memory_after_mb": 129.46875,
  "memory_delta_mb": 28.02734375,
  "outside_phase_new_or_changed": []
}
```
