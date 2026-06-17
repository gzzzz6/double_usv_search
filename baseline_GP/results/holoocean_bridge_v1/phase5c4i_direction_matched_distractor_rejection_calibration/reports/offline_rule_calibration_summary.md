# Phase 5C-4I-1 Offline Rule Calibration Summary

- Source Phase: `phase5c4h_fan_area_distance_boundary`
- Raw RGB Source: `visuals/*_rgb_raw.npy`
- scene_results first_rgb_raw used: `False`
- Candidate Rule Count: `1056`
- Old Direction Inner Target Failure Count: `6`

## Baseline

- Rule: `baseline_any_hit`
- Target TP/FN: `13/2`
- Distractor FP/TN: `6/4`

## Best Stronger RGB

- Rule ID: `stronger_rgb_any_hit_overlap7_px0`
- overlap_min: `7`
- rgb_changed_pixels_min: `0`
- Target TP/FN: `12/3`
- 20m TP: `5/5`
- 35m TP: `5/5`
- 50m center/inner TP: `2/3`
- Distractor FP/TN: `0/10`
- New target false negatives: `['target_left_outer_50m', 'target_center_50m', 'target_right_outer_50m']`

## Recommended Rule

- Rule ID: `stronger_rgb_any_hit_overlap7_px0`
- Rule Name: `stronger_rgb_any_hit`
- overlap_min: `7`
- rgb_changed_pixels_min: `0`
- direction_tolerance_deg: `None`
- distractor_overlap_min: `None`
- Target TP/FN: `12/3`
- Distractor FP/TN: `0/10`
- 20m target TP: `5/5`
- 35m target TP: `5/5`
- 50m center/inner target TP: `2/3`
- Target false negatives: `['target_left_outer_50m', 'target_center_50m', 'target_right_outer_50m']`

## Conclusion

The offline recommendation prioritizes stronger RGB overlap thresholding. The old 5C-4H direction flag is retained only as a failure reference, because direct use would reject inner-angle true targets.
