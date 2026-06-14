# Phase 5C-4C RGB+RangeFinder Positive/Negative Detection Adapter Closure

## Status
- Probe Completed: `True`
- Terminated Reason: `positive_negative_closure_complete`
- Positive Scenes Detected: `True`
- Negative Scenes Not Detected: `True`
- Runtime Positive Scenes Found: `True`
- Runtime Negative Scenes Not Found: `True`
- Found Trigger Rule: `rgb_has_target_signature and rangefinder_hit`
- RangeFinder Object Presence Supported: `True`
- Truth Used For Detection: `False`
- Scene Sensor Outcomes: `{'baseline': {'expected_sensor_detected_target': False, 'sensor_detected_target': False, 'rgb_has_target_signature': False, 'rgb_has_distractor_signature': False, 'rangefinder_hit': False, 'target_detection_correct_for_scene': True, 'distractor_false_positive': False}, 'target_only': {'expected_sensor_detected_target': True, 'sensor_detected_target': True, 'rgb_has_target_signature': True, 'rgb_has_distractor_signature': False, 'rangefinder_hit': True, 'target_detection_correct_for_scene': True, 'distractor_false_positive': False}, 'distractor_only': {'expected_sensor_detected_target': False, 'sensor_detected_target': False, 'rgb_has_target_signature': False, 'rgb_has_distractor_signature': True, 'rangefinder_hit': True, 'target_detection_correct_for_scene': True, 'distractor_false_positive': False}, 'target_and_distractor': {'expected_sensor_detected_target': True, 'sensor_detected_target': True, 'rgb_has_target_signature': True, 'rgb_has_distractor_signature': True, 'rangefinder_hit': True, 'target_detection_correct_for_scene': True, 'distractor_false_positive': False}}`
- Scene Runtime Outcomes: `{'baseline': {'found_mask_after': [False], 'find_times_after': [None], 'new_found_indices': [], 'hit_update_called': False, 'team_gp_update_called': True, 'team_search_info_update_called': True, 'team_miss_update_called': False, 'remaining_intensity_mass_after': 1.0000000000000002, 'gp_n_obs_initial': 48, 'gp_n_obs_final': 96, 'search_info_valid_final': True}, 'target_only': {'found_mask_after': [True], 'find_times_after': [1], 'new_found_indices': [0], 'hit_update_called': True, 'team_gp_update_called': True, 'team_search_info_update_called': True, 'team_miss_update_called': False, 'remaining_intensity_mass_after': 0.0, 'gp_n_obs_initial': 48, 'gp_n_obs_final': 96, 'search_info_valid_final': True}, 'distractor_only': {'found_mask_after': [False], 'find_times_after': [None], 'new_found_indices': [], 'hit_update_called': False, 'team_gp_update_called': True, 'team_search_info_update_called': True, 'team_miss_update_called': False, 'remaining_intensity_mass_after': 1.0000000000000002, 'gp_n_obs_initial': 48, 'gp_n_obs_final': 96, 'search_info_valid_final': True}, 'target_and_distractor': {'found_mask_after': [True], 'find_times_after': [1], 'new_found_indices': [0], 'hit_update_called': True, 'team_gp_update_called': True, 'team_search_info_update_called': True, 'team_miss_update_called': False, 'remaining_intensity_mass_after': 0.0, 'gp_n_obs_initial': 48, 'gp_n_obs_final': 96, 'search_info_valid_final': True}}`
- Team GP Update All Scenes: `True`
- Team Search Info Update All Scenes: `True`
- Circular Miss Update Applied Any Scene: `False`

## Boundary
- Controlled static target/distractor scenes only.
- RGBCamera provides identity evidence through RGB signature overlap.
- RangeFinderSensor provides range/object-presence evidence only.
- SemanticSegmentationCamera and sonar are not used.
- This phase does not replace the baseline circular sensor geometry.
