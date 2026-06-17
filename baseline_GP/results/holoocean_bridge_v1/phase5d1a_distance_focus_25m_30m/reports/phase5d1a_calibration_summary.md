# Phase 5D-1A 25m/30m Calibration Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_any_hit`
- Found Rule: `sphere_blob_any_hit and any_rangefinder_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `15`
- Target Outcome Counts: `{'true_positive': 9, 'false_negative': 7}`
- Target-only Outcome Counts: `{'true_positive': 9, 'false_negative': 1}`
- Target-with-teammate Outcome Counts: `{'false_negative': 6}`
- Teammate Outcome Counts: `{'true_negative': 12}`
- Fan Reliable Distances: `[25.0]`
- Max Fan Reliable Distance: `25.0`
- Teammate False Positive Scenes: `[]`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `15` | `286` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_25m` | `target` | `left_outer` | `25.0` | `9` | `45` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_25m` | `target` | `left_inner` | `25.0` | `7` | `30` | `True` | `True` | `true_positive` |
| `target_sphere_center_25m` | `target` | `center` | `25.0` | `5` | `36` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_25m` | `target` | `right_inner` | `25.0` | `8` | `35` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_25m` | `target` | `right_outer` | `25.0` | `12` | `48` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_30m` | `target` | `left_outer` | `30.0` | `7` | `34` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_30m` | `target` | `left_inner` | `30.0` | `8` | `26` | `True` | `True` | `true_positive` |
| `target_sphere_center_30m` | `target` | `center` | `30.0` | `9` | `31` | `True` | `False` | `false_negative` |
| `target_sphere_right_inner_30m` | `target` | `right_inner` | `30.0` | `8` | `47` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_30m` | `target` | `right_outer` | `30.0` | `8` | `26` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_25m` | `teammate_only` | `left_outer` | `25.0` | `9` | `188` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_25m` | `teammate_only` | `left_inner` | `25.0` | `9` | `127` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_25m` | `teammate_only` | `center` | `25.0` | `8` | `74` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_25m` | `teammate_only` | `right_inner` | `25.0` | `12` | `133` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_25m` | `teammate_only` | `right_outer` | `25.0` | `8` | `200` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_30m` | `teammate_only` | `left_outer` | `30.0` | `8` | `134` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_30m` | `teammate_only` | `left_inner` | `30.0` | `12` | `115` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_30m` | `teammate_only` | `center` | `30.0` | `9` | `45` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_30m` | `teammate_only` | `right_inner` | `30.0` | `10` | `91` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_30m` | `teammate_only` | `right_outer` | `30.0` | `10` | `141` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_inner_25m` | `teammate_only` | `left_right_inner_pair` | `25.0` | `10` | `255` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_outer_30m` | `teammate_only` | `left_right_outer_pair` | `30.0` | `9` | `274` | `True` | `False` | `true_negative` |
| `coexist_sphere_center_25m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `25.0` | `10` | `238` | `True` | `False` | `false_negative` |
| `coexist_sphere_center_30m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `30.0` | `12` | `205` | `True` | `False` | `false_negative` |
| `coexist_sphere_left_inner_25m_teammate_right_outer_25m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `25.0` | `10` | `235` | `True` | `False` | `false_negative` |
| `coexist_sphere_right_inner_30m_teammate_left_outer_30m` | `target_with_teammate` | `target_right_inner_teammate_left_outer` | `30.0` | `11` | `162` | `True` | `False` | `false_negative` |
| `coexist_sphere_left_outer_30m_teammate_right_inner_25m` | `target_with_teammate` | `target_left_outer_teammate_right_inner` | `30.0` | `11` | `158` | `True` | `False` | `false_negative` |
| `coexist_sphere_right_outer_25m_teammate_left_inner_25m` | `target_with_teammate` | `target_right_outer_teammate_left_inner` | `25.0` | `12` | `181` | `True` | `False` | `false_negative` |
