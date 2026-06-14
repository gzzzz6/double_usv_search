# Phase 5C-4D RGB+RangeFinder Robustness Boundary Summary

## Status
- Probe Completed: `True`
- Scene Count: `13`
- Found Trigger Rule: `rgb_has_target_signature and rangefinder_hit`
- Truth Used For Detection: `False`
- Outcome Counts: `{'true_negative': 2, 'true_positive': 5, 'false_negative': 6}`
- Failure Counts: `{'none': 7, 'false_negative_no_range_hit': 2, 'false_negative_no_rgb_signature_and_no_range_hit': 2, 'false_negative_no_rgb_signature': 2}`
- RGB Target Signature Without Range Hit Observed: `True`
- Range Hit Without Target RGB Signature Observed: `True`
- RangeFinder Identity Ambiguity Observed: `True`
- Recommendation: `do_not_treat_as_general_detector_yet; use only in validated front/center/static conditions or add stronger vision/geometric gating`

## Matrix
| Scene | RGB Target | Range Hit | Found | Outcome | Failure Mode |
|---|---:|---:|---:|---|---|
| `baseline` | `False` | `False` | `False` | `true_negative` | `none` |
| `target_front_center_near` | `True` | `True` | `True` | `true_positive` | `none` |
| `target_yaw45_center_near` | `True` | `True` | `True` | `true_positive` | `none` |
| `target_yaw90_center_near` | `True` | `True` | `True` | `true_positive` | `none` |
| `target_left_offset_near` | `True` | `False` | `False` | `false_negative` | `false_negative_no_range_hit` |
| `target_right_offset_near` | `True` | `False` | `False` | `false_negative` | `false_negative_no_range_hit` |
| `target_right_fov_edge_near` | `False` | `False` | `False` | `false_negative` | `false_negative_no_rgb_signature_and_no_range_hit` |
| `target_front_center_mid` | `False` | `True` | `False` | `false_negative` | `false_negative_no_rgb_signature` |
| `target_front_center_far` | `False` | `True` | `False` | `false_negative` | `false_negative_no_rgb_signature` |
| `distractor_only_center` | `False` | `True` | `False` | `true_negative` | `none` |
| `target_with_side_distractor` | `True` | `True` | `True` | `true_positive` | `none` |
| `distractor_occludes_target` | `True` | `True` | `True` | `true_positive` | `none` |
| `target_rgb_rangefinder_mismatch_candidate` | `False` | `False` | `False` | `false_negative` | `false_negative_no_rgb_signature_and_no_range_hit` |

## Boundary
- This phase preserves the Phase 5C-4C RGB signature plus RangeFinder hit rule.
- Failure scenes are expected evidence: they define where the simple adapter stops being reliable.
- RGBCamera provides only calibrated color-signature evidence; RangeFinderSensor provides object-presence/range evidence only.
