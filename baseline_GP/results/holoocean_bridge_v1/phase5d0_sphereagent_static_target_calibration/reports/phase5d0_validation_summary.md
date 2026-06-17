# Phase 5D-0 HoloOcean Validation Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_any_hit`
- Found Rule: `sphere_blob_any_hit and any_rangefinder_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `13`
- Target Outcome Counts: `{'true_positive': 15}`
- Teammate Outcome Counts: `{'true_negative': 15}`
- Fan Reliable Distances: `[20.0, 35.0, 50.0]`
- Max Fan Reliable Distance: `50.0`
- Teammate False Positive Scenes: `[]`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `13` | `230` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_20m` | `target` | `left_outer` | `20.0` | `9` | `60` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_20m` | `target` | `left_inner` | `20.0` | `7` | `52` | `True` | `True` | `true_positive` |
| `target_sphere_center_20m` | `target` | `center` | `20.0` | `6` | `43` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_20m` | `target` | `right_inner` | `20.0` | `9` | `60` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_20m` | `target` | `right_outer` | `20.0` | `7` | `63` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_35m` | `target` | `left_outer` | `35.0` | `8` | `31` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_35m` | `target` | `left_inner` | `35.0` | `4` | `13` | `True` | `True` | `true_positive` |
| `target_sphere_center_35m` | `target` | `center` | `35.0` | `3` | `9` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_35m` | `target` | `right_inner` | `35.0` | `7` | `18` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_35m` | `target` | `right_outer` | `35.0` | `9` | `128` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_50m` | `target` | `left_outer` | `50.0` | `5` | `27` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_50m` | `target` | `left_inner` | `50.0` | `7` | `52` | `True` | `True` | `true_positive` |
| `target_sphere_center_50m` | `target` | `center` | `50.0` | `3` | `8` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_50m` | `target` | `right_inner` | `50.0` | `6` | `11` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_50m` | `target` | `right_outer` | `50.0` | `2` | `9` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_20m` | `teammate_only` | `left_outer` | `20.0` | `9` | `283` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_20m` | `teammate_only` | `left_inner` | `20.0` | `11` | `227` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_20m` | `teammate_only` | `center` | `20.0` | `11` | `112` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_20m` | `teammate_only` | `right_inner` | `20.0` | `12` | `192` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_20m` | `teammate_only` | `right_outer` | `20.0` | `8` | `317` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_35m` | `teammate_only` | `left_outer` | `35.0` | `11` | `102` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_35m` | `teammate_only` | `left_inner` | `35.0` | `10` | `74` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_35m` | `teammate_only` | `center` | `35.0` | `9` | `32` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_35m` | `teammate_only` | `right_inner` | `35.0` | `9` | `54` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_35m` | `teammate_only` | `right_outer` | `35.0` | `8` | `93` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_50m` | `teammate_only` | `left_outer` | `50.0` | `11` | `55` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_50m` | `teammate_only` | `left_inner` | `50.0` | `9` | `30` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_50m` | `teammate_only` | `center` | `50.0` | `4` | `17` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_50m` | `teammate_only` | `right_inner` | `50.0` | `8` | `33` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_50m` | `teammate_only` | `right_outer` | `50.0` | `9` | `45` | `True` | `False` | `true_negative` |
