# Phase 5C-4E RGB + Multi-Ray RangeFinder Fan Boundary Summary

## Status
- Probe Completed: `True`
- Scene Count: `15`
- RangeFinder Mode: `yaw_rotated_single_ray_fan`
- Laser Count: `9`
- Laser Angle: `60.0`
- Horizontal Fan Sensor Count: `9`
- Native Multi-Ray All-No-Hit Observed: `True`
- Truth Used For Detection: `False`
- Any-Hit Outcomes: `{'true_negative': 4, 'true_positive': 7, 'false_negative': 4}`
- Aligned-Hit Outcomes: `{'true_negative': 4, 'true_positive': 4, 'false_negative': 7}`
- Left/Right Fixed By Any-Hit: `True`
- Left/Right Fixed By Aligned-Hit: `False`
- Any-Hit False Positives: `[]`
- Aligned-Hit False Positives: `[]`
- Conclusion: `multi-ray fan helps coverage, but aligned sector mapping needs calibration before becoming the primary adapter`

## Matrix
| Scene | RGB Sector | Hit Beams | Hit Sectors | Any Found | Aligned Found | Any Outcome | Aligned Outcome |
|---|---|---|---|---:|---:|---|---|
| `baseline` | `none` | `[]` | `[]` | `False` | `False` | `true_negative` | `true_negative` |
| `target_front_center_near` | `center` | `[3, 4, 5]` | `['center']` | `True` | `True` | `true_positive` | `true_positive` |
| `target_left_offset_near` | `center` | `[0]` | `['left']` | `True` | `False` | `true_positive` | `false_negative` |
| `target_right_offset_near` | `right` | `[8]` | `['right']` | `True` | `True` | `true_positive` | `true_positive` |
| `target_left_fov_edge_near` | `none` | `[]` | `[]` | `False` | `False` | `false_negative` | `false_negative` |
| `target_right_fov_edge_near` | `right` | `[]` | `[]` | `False` | `False` | `false_negative` | `false_negative` |
| `target_front_center_mid` | `center` | `[4]` | `['center']` | `False` | `False` | `false_negative` | `false_negative` |
| `target_front_center_far` | `center` | `[4]` | `['center']` | `False` | `False` | `false_negative` | `false_negative` |
| `distractor_only_center` | `center` | `[4]` | `['center']` | `False` | `False` | `true_negative` | `true_negative` |
| `distractor_only_left` | `left` | `[]` | `[]` | `False` | `False` | `true_negative` | `true_negative` |
| `distractor_only_right` | `right` | `[]` | `[]` | `False` | `False` | `true_negative` | `true_negative` |
| `target_left_with_distractor_right` | `center` | `[0]` | `['left']` | `True` | `False` | `true_positive` | `false_negative` |
| `target_right_with_distractor_left` | `center` | `[8]` | `['right']` | `True` | `False` | `true_positive` | `false_negative` |
| `target_center_with_side_distractor` | `center` | `[3, 4, 5]` | `['center']` | `True` | `True` | `true_positive` | `true_positive` |
| `distractor_occludes_target` | `center` | `[4]` | `['center']` | `True` | `True` | `true_positive` | `true_positive` |

## Boundary
- Any-hit asks whether multi-ray fan coverage solves misses.
- Aligned-hit asks whether RGB sector and beam sector can be matched without actor truth.
- RangeFinder beams remain range evidence only; identity still comes from RGB signature.
