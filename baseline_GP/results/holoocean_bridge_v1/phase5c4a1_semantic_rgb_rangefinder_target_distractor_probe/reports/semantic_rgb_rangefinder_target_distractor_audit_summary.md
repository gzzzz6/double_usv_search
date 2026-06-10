# Phase 5C-4A-1 Semantic/RGB/RangeFinder Target-Distractor Audit Summary

## Status
- Overall: `PASSED`
- Checks: `54`
- Semantic Can Distinguish: `False`
- RGB Can Distinguish: `True`
- RangeFinder Object Presence Supported: `True`
- Composite Sensor Detection Supported: `True`

## Checks
| Check | Result |
| :--- | :---: |
| `all_detection_events_correct` | `True` |
| `all_expected_scenes_present` | `True` |
| `all_scene_launch_ok` | `True` |
| `all_scenes_rangefinder_output` | `True` |
| `all_scenes_rgb_output` | `True` |
| `all_scenes_semantic_output` | `True` |
| `audit_script_exists` | `True` |
| `composite_sensor_detection_supported` | `True` |
| `conclusion_json_exists` | `True` |
| `conclusion_json_parse_ok` | `True` |
| `config_json_exists` | `True` |
| `config_json_parse_ok` | `True` |
| `config_navigation_sensors_not_detection_evidence` | `True` |
| `config_perception_sensors_explicit` | `True` |
| `config_runtime_not_imported` | `True` |
| `config_sensor_roles_explicit` | `True` |
| `config_sonar_disabled` | `True` |
| `detection_events_have_source_and_no_truth` | `True` |
| `detection_events_json_exists` | `True` |
| `detection_events_json_parse_ok` | `True` |
| `detection_events_sensor_evidence_schema` | `True` |
| `four_detection_events` | `True` |
| `git_status_json_exists` | `True` |
| `git_status_json_parse_ok` | `True` |
| `only_stage_dir_changes` | `True` |
| `phase_name_correct` | `True` |
| `probe_script_exists` | `True` |
| `rangefinder_available_as_range_evidence` | `True` |
| `rangefinder_object_presence_supported` | `True` |
| `rgb_available_as_visual_evidence` | `True` |
| `rgb_can_distinguish` | `True` |
| `rgb_distractor_signature_present` | `True` |
| `rgb_target_distractor_disjoint` | `True` |
| `rgb_target_signature_present` | `True` |
| `scene_results_json_exists` | `True` |
| `scene_results_json_parse_ok` | `True` |
| `search_decision_algorithm_not_modified_flag` | `True` |
| `semantic_identity_conclusion_recorded` | `True` |
| `source_contains_rangefinder` | `True` |
| `source_contains_rgb_camera` | `True` |
| `source_contains_semantic_camera` | `True` |
| `source_imports_holoocean` | `True` |
| `source_no_env_step` | `True` |
| `source_no_runtime_or_search_updates` | `True` |
| `source_no_sonar_sensor` | `True` |
| `source_uses_env_act` | `True` |
| `source_uses_env_tick` | `True` |
| `summary_md_exists` | `True` |
| `tick_trace_csv_exists` | `True` |
| `tick_trace_json_exists` | `True` |
| `tick_trace_json_parse_ok` | `True` |
| `tick_trace_nonempty` | `True` |
| `truth_not_used_for_detection` | `True` |
| `visual_artifacts_exist` | `True` |

## Metrics
```json
{
  "semantic_can_distinguish_target_from_distractor": false,
  "semantic_identity_supported": false,
  "rgb_can_distinguish_target_from_distractor": true,
  "rangefinder_object_presence_supported": true,
  "composite_sensor_detection_supported": true,
  "rgb_available_as_visual_evidence": true,
  "rangefinder_available_as_range_evidence": true,
  "all_detection_events_correct": true,
  "target_signature_colors": [],
  "distractor_signature_colors": [],
  "target_vs_distractor_semantic_disjoint": false,
  "rgb_target_signature_colors": [
    "128,128,128,255",
    "128,128,96,255",
    "128,64,32,255",
    "128,96,64,255",
    "128,96,96,255",
    "160,160,192,255",
    "160,96,64,255",
    "192,160,96,255",
    "224,160,128,255",
    "224,192,128,255",
    "96,64,32,255",
    "96,64,64,255",
    "96,96,64,255"
  ],
  "rgb_distractor_signature_colors": [
    "224,192,192,255"
  ],
  "rgb_target_vs_distractor_disjoint": true,
  "rangefinder_object_scene_hits": [
    true,
    true,
    true
  ],
  "outside_phase_new_or_changed": []
}
```
