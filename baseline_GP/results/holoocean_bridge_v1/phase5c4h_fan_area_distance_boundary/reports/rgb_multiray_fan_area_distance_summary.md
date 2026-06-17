# Phase 5C-4H Fan-Area Distance Boundary Summary

- Tested Distances: `[20.0, 35.0, 50.0]`
- Tested Fan Angles: `[{'label': 'left_outer', 'angle_deg': 25.0}, {'label': 'left_inner', 'angle_deg': 15.0}, {'label': 'center', 'angle_deg': 0.0}, {'label': 'right_inner', 'angle_deg': -15.0}, {'label': 'right_outer', 'angle_deg': -25.0}]`
- RGB Calibration Scene: `calibration_target_front_center_10m`
- Max Effective Distance By Angle: `{'left_outer': 35.0, 'left_inner': 50.0, 'center': 50.0, 'right_inner': 50.0, 'right_outer': 35.0}`
- Fan Reliable Distances: `[20.0, 35.0]`
- Max Fan Reliable Distance: `35.0`
- Distractor False Positive Scenes: `['distractor_only_left_inner_20m', 'distractor_only_center_20m', 'distractor_only_right_inner_20m', 'distractor_only_left_inner_50m', 'distractor_only_center_50m', 'distractor_only_right_inner_50m']`
- Direction Mismatch Scenes: `['target_left_inner_20m', 'target_right_inner_20m', 'target_left_inner_35m', 'target_right_inner_35m', 'target_left_inner_50m', 'target_right_inner_50m', 'distractor_only_left_inner_20m', 'distractor_only_right_inner_20m', 'distractor_only_left_inner_50m', 'distractor_only_right_inner_50m']`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | RGB Signature | Range Hit | Matched Beam | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_target_front_center_10m` | `calibration` | `center` | `10.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_left_outer_20m` | `target` | `left_outer` | `20.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_left_inner_20m` | `target` | `left_inner` | `20.0` | `True` | `True` | `False` | `True` | `true_positive` |
| `target_center_20m` | `target` | `center` | `20.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_right_inner_20m` | `target` | `right_inner` | `20.0` | `True` | `True` | `False` | `True` | `true_positive` |
| `target_right_outer_20m` | `target` | `right_outer` | `20.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_left_outer_35m` | `target` | `left_outer` | `35.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_left_inner_35m` | `target` | `left_inner` | `35.0` | `True` | `True` | `False` | `True` | `true_positive` |
| `target_center_35m` | `target` | `center` | `35.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_right_inner_35m` | `target` | `right_inner` | `35.0` | `True` | `True` | `False` | `True` | `true_positive` |
| `target_right_outer_35m` | `target` | `right_outer` | `35.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_left_outer_50m` | `target` | `left_outer` | `50.0` | `True` | `False` | `False` | `False` | `false_negative` |
| `target_left_inner_50m` | `target` | `left_inner` | `50.0` | `True` | `True` | `False` | `True` | `true_positive` |
| `target_center_50m` | `target` | `center` | `50.0` | `True` | `True` | `True` | `True` | `true_positive` |
| `target_right_inner_50m` | `target` | `right_inner` | `50.0` | `True` | `True` | `False` | `True` | `true_positive` |
| `target_right_outer_50m` | `target` | `right_outer` | `50.0` | `True` | `False` | `False` | `False` | `false_negative` |
| `distractor_only_left_outer_20m` | `distractor_only` | `left_outer` | `20.0` | `True` | `False` | `False` | `False` | `true_negative` |
| `distractor_only_left_inner_20m` | `distractor_only` | `left_inner` | `20.0` | `True` | `True` | `False` | `True` | `false_positive` |
| `distractor_only_center_20m` | `distractor_only` | `center` | `20.0` | `True` | `True` | `True` | `True` | `false_positive` |
| `distractor_only_right_inner_20m` | `distractor_only` | `right_inner` | `20.0` | `True` | `True` | `False` | `True` | `false_positive` |
| `distractor_only_right_outer_20m` | `distractor_only` | `right_outer` | `20.0` | `True` | `False` | `False` | `False` | `true_negative` |
| `distractor_only_left_outer_50m` | `distractor_only` | `left_outer` | `50.0` | `True` | `False` | `False` | `False` | `true_negative` |
| `distractor_only_left_inner_50m` | `distractor_only` | `left_inner` | `50.0` | `True` | `True` | `False` | `True` | `false_positive` |
| `distractor_only_center_50m` | `distractor_only` | `center` | `50.0` | `True` | `True` | `True` | `True` | `false_positive` |
| `distractor_only_right_inner_50m` | `distractor_only` | `right_inner` | `50.0` | `True` | `True` | `False` | `True` | `false_positive` |
| `distractor_only_right_outer_50m` | `distractor_only` | `right_outer` | `50.0` | `True` | `False` | `False` | `False` | `true_negative` |
