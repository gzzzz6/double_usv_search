# Phase 5D-0 Calibration Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_any_hit`
- Found Rule: `sphere_blob_any_hit and any_rangefinder_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `12`
- Target Outcome Counts: `{'true_positive': 14, 'false_negative': 1}`
- Teammate Outcome Counts: `{'true_negative': 15}`
- Fan Reliable Distances: `[20.0, 35.0]`
- Max Fan Reliable Distance: `35.0`
- Teammate False Positive Scenes: `[]`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `12` | `234` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_20m` | `target` | `left_outer` | `20.0` | `8` | `57` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_20m` | `target` | `left_inner` | `20.0` | `7` | `52` | `True` | `True` | `true_positive` |
| `target_sphere_center_20m` | `target` | `center` | `20.0` | `6` | `46` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_20m` | `target` | `right_inner` | `20.0` | `9` | `60` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_20m` | `target` | `right_outer` | `20.0` | `8` | `63` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_35m` | `target` | `left_outer` | `35.0` | `6` | `24` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_35m` | `target` | `left_inner` | `35.0` | `4` | `13` | `True` | `True` | `true_positive` |
| `target_sphere_center_35m` | `target` | `center` | `35.0` | `3` | `14` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_35m` | `target` | `right_inner` | `35.0` | `6` | `17` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_35m` | `target` | `right_outer` | `35.0` | `7` | `26` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_50m` | `target` | `left_outer` | `50.0` | `3` | `9` | `True` | `False` | `false_negative` |
| `target_sphere_left_inner_50m` | `target` | `left_inner` | `50.0` | `5` | `10` | `True` | `True` | `true_positive` |
| `target_sphere_center_50m` | `target` | `center` | `50.0` | `4` | `8` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_50m` | `target` | `right_inner` | `50.0` | `5` | `8` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_50m` | `target` | `right_outer` | `50.0` | `3` | `9` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_20m` | `teammate_only` | `left_outer` | `20.0` | `9` | `287` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_20m` | `teammate_only` | `left_inner` | `20.0` | `10` | `217` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_20m` | `teammate_only` | `center` | `20.0` | `10` | `104` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_20m` | `teammate_only` | `right_inner` | `20.0` | `11` | `182` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_20m` | `teammate_only` | `right_outer` | `20.0` | `8` | `297` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_35m` | `teammate_only` | `left_outer` | `35.0` | `9` | `101` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_35m` | `teammate_only` | `left_inner` | `35.0` | `11` | `111` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_35m` | `teammate_only` | `center` | `35.0` | `8` | `33` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_35m` | `teammate_only` | `right_inner` | `35.0` | `9` | `59` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_35m` | `teammate_only` | `right_outer` | `35.0` | `10` | `96` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_50m` | `teammate_only` | `left_outer` | `50.0` | `10` | `57` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_50m` | `teammate_only` | `left_inner` | `50.0` | `12` | `32` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_50m` | `teammate_only` | `center` | `50.0` | `6` | `22` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_50m` | `teammate_only` | `right_inner` | `50.0` | `8` | `30` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_50m` | `teammate_only` | `right_outer` | `50.0` | `8` | `46` | `True` | `False` | `true_negative` |
