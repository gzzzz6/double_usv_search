# Phase 5C-4I HoloOcean Validation Summary

- Recommended Rule ID: `stronger_rgb_any_hit_overlap7_px0`
- Found Rule: `stronger_rgb_target_signature and any_rangefinder_hit`
- RGB target_overlap_min: `7`
- RGB changed_pixels_min: `0`
- Direction Matching Used For Detection: `False`
- Distractor Rejection Enabled: `False`
- Target Outcome Counts: `{'true_positive': 12, 'false_negative': 3}`
- Distractor Outcome Counts: `{'true_negative': 10}`
- Fan Reliable Distances: `[20.0, 35.0]`
- Max Fan Reliable Distance: `35.0`
- Distractor False Positive Scenes: `[]`
- Old Direction Inner Failure Reference Count: `6`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Strong RGB | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_target_front_center_10m` | `calibration` | `center` | `10.0` | `24` | `True` | `True` | `True` | `true_positive` |
| `target_left_outer_20m` | `target` | `left_outer` | `20.0` | `20` | `True` | `True` | `True` | `true_positive` |
| `target_left_inner_20m` | `target` | `left_inner` | `20.0` | `19` | `True` | `True` | `True` | `true_positive` |
| `target_center_20m` | `target` | `center` | `20.0` | `12` | `True` | `True` | `True` | `true_positive` |
| `target_right_inner_20m` | `target` | `right_inner` | `20.0` | `16` | `True` | `True` | `True` | `true_positive` |
| `target_right_outer_20m` | `target` | `right_outer` | `20.0` | `21` | `True` | `True` | `True` | `true_positive` |
| `target_left_outer_35m` | `target` | `left_outer` | `35.0` | `16` | `True` | `True` | `True` | `true_positive` |
| `target_left_inner_35m` | `target` | `left_inner` | `35.0` | `18` | `True` | `True` | `True` | `true_positive` |
| `target_center_35m` | `target` | `center` | `35.0` | `7` | `True` | `True` | `True` | `true_positive` |
| `target_right_inner_35m` | `target` | `right_inner` | `35.0` | `13` | `True` | `True` | `True` | `true_positive` |
| `target_right_outer_35m` | `target` | `right_outer` | `35.0` | `16` | `True` | `True` | `True` | `true_positive` |
| `target_left_outer_50m` | `target` | `left_outer` | `50.0` | `13` | `True` | `False` | `False` | `false_negative` |
| `target_left_inner_50m` | `target` | `left_inner` | `50.0` | `9` | `True` | `True` | `True` | `true_positive` |
| `target_center_50m` | `target` | `center` | `50.0` | `5` | `False` | `True` | `False` | `false_negative` |
| `target_right_inner_50m` | `target` | `right_inner` | `50.0` | `9` | `True` | `True` | `True` | `true_positive` |
| `target_right_outer_50m` | `target` | `right_outer` | `50.0` | `12` | `True` | `False` | `False` | `false_negative` |
| `distractor_only_left_outer_20m` | `distractor_only` | `left_outer` | `20.0` | `6` | `False` | `False` | `False` | `true_negative` |
| `distractor_only_left_inner_20m` | `distractor_only` | `left_inner` | `20.0` | `6` | `False` | `True` | `False` | `true_negative` |
| `distractor_only_center_20m` | `distractor_only` | `center` | `20.0` | `4` | `False` | `True` | `False` | `true_negative` |
| `distractor_only_right_inner_20m` | `distractor_only` | `right_inner` | `20.0` | `6` | `False` | `True` | `False` | `true_negative` |
| `distractor_only_right_outer_20m` | `distractor_only` | `right_outer` | `20.0` | `8` | `True` | `False` | `False` | `true_negative` |
| `distractor_only_left_outer_50m` | `distractor_only` | `left_outer` | `50.0` | `4` | `False` | `False` | `False` | `true_negative` |
| `distractor_only_left_inner_50m` | `distractor_only` | `left_inner` | `50.0` | `3` | `False` | `True` | `False` | `true_negative` |
| `distractor_only_center_50m` | `distractor_only` | `center` | `50.0` | `3` | `False` | `True` | `False` | `true_negative` |
| `distractor_only_right_inner_50m` | `distractor_only` | `right_inner` | `50.0` | `3` | `False` | `True` | `False` | `true_negative` |
| `distractor_only_right_outer_50m` | `distractor_only` | `right_outer` | `50.0` | `2` | `False` | `False` | `False` | `true_negative` |
