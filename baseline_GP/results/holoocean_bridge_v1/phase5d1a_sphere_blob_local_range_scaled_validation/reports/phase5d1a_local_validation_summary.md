# Phase 5D-1A Local Range-Scaled Blob HoloOcean Validation Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_local_range_scaled_any_hit`
- Found Rule: `sphere_blob_local_range_scaled_any_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `13`
- Target Outcome Counts: `{'true_positive': 29}`
- Target-only Outcome Counts: `{'true_positive': 20}`
- Target-with-teammate Outcome Counts: `{'true_positive': 9}`
- Teammate Outcome Counts: `{'true_negative': 22}`
- Fan Reliable Distances: `[20.0, 25.0, 30.0, 35.0]`
- Max Fan Reliable Distance: `35.0`
- Teammate False Positive Scenes: `[]`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `13` | `241` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_20m` | `target` | `left_outer` | `20.0` | `11` | `1009` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_20m` | `target` | `left_inner` | `20.0` | `11` | `91` | `True` | `True` | `true_positive` |
| `target_sphere_center_20m` | `target` | `center` | `20.0` | `5` | `44` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_20m` | `target` | `right_inner` | `20.0` | `8` | `56` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_20m` | `target` | `right_outer` | `20.0` | `10` | `69` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_25m` | `target` | `left_outer` | `25.0` | `10` | `58` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_25m` | `target` | `left_inner` | `25.0` | `8` | `32` | `True` | `True` | `true_positive` |
| `target_sphere_center_25m` | `target` | `center` | `25.0` | `9` | `52` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_25m` | `target` | `right_inner` | `25.0` | `7` | `35` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_25m` | `target` | `right_outer` | `25.0` | `11` | `49` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_30m` | `target` | `left_outer` | `30.0` | `8` | `33` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_30m` | `target` | `left_inner` | `30.0` | `6` | `29` | `True` | `True` | `true_positive` |
| `target_sphere_center_30m` | `target` | `center` | `30.0` | `7` | `21` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_30m` | `target` | `right_inner` | `30.0` | `8` | `39` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_30m` | `target` | `right_outer` | `30.0` | `9` | `30` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_35m` | `target` | `left_outer` | `35.0` | `9` | `32` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_35m` | `target` | `left_inner` | `35.0` | `8` | `50` | `True` | `True` | `true_positive` |
| `target_sphere_center_35m` | `target` | `center` | `35.0` | `3` | `8` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_35m` | `target` | `right_inner` | `35.0` | `10` | `18` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_35m` | `target` | `right_outer` | `35.0` | `7` | `22` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_20m` | `teammate_only` | `left_outer` | `20.0` | `9` | `285` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_20m` | `teammate_only` | `left_inner` | `20.0` | `10` | `208` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_20m` | `teammate_only` | `center` | `20.0` | `9` | `111` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_20m` | `teammate_only` | `right_inner` | `20.0` | `10` | `189` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_20m` | `teammate_only` | `right_outer` | `20.0` | `9` | `294` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_25m` | `teammate_only` | `left_outer` | `25.0` | `8` | `187` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_25m` | `teammate_only` | `left_inner` | `25.0` | `9` | `127` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_25m` | `teammate_only` | `center` | `25.0` | `10` | `76` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_25m` | `teammate_only` | `right_inner` | `25.0` | `9` | `122` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_25m` | `teammate_only` | `right_outer` | `25.0` | `10` | `196` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_30m` | `teammate_only` | `left_outer` | `30.0` | `9` | `153` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_30m` | `teammate_only` | `left_inner` | `30.0` | `10` | `98` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_30m` | `teammate_only` | `center` | `30.0` | `9` | `37` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_30m` | `teammate_only` | `right_inner` | `30.0` | `12` | `95` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_30m` | `teammate_only` | `right_outer` | `30.0` | `8` | `142` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_35m` | `teammate_only` | `left_outer` | `35.0` | `11` | `117` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_35m` | `teammate_only` | `left_inner` | `35.0` | `11` | `72` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_35m` | `teammate_only` | `center` | `35.0` | `8` | `31` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_35m` | `teammate_only` | `right_inner` | `35.0` | `12` | `107` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_35m` | `teammate_only` | `right_outer` | `35.0` | `9` | `97` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_inner_25m` | `teammate_only` | `left_right_inner_pair` | `25.0` | `11` | `262` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_outer_30m` | `teammate_only` | `left_right_outer_pair` | `30.0` | `11` | `293` | `True` | `False` | `true_negative` |
| `coexist_sphere_center_20m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `20.0` | `6` | `44` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_25m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `25.0` | `11` | `245` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_30m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `30.0` | `12` | `213` | `True` | `True` | `true_positive` |
| `coexist_sphere_left_inner_25m_teammate_right_outer_25m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `25.0` | `11` | `232` | `True` | `True` | `true_positive` |
| `coexist_sphere_right_inner_30m_teammate_left_outer_30m` | `target_with_teammate` | `target_right_inner_teammate_left_outer` | `30.0` | `12` | `171` | `True` | `True` | `true_positive` |
| `coexist_sphere_left_outer_30m_teammate_right_inner_25m` | `target_with_teammate` | `target_left_outer_teammate_right_inner` | `30.0` | `11` | `157` | `True` | `True` | `true_positive` |
| `coexist_sphere_right_outer_25m_teammate_left_inner_25m` | `target_with_teammate` | `target_right_outer_teammate_left_inner` | `25.0` | `12` | `175` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_35m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `35.0` | `10` | `200` | `True` | `True` | `true_positive` |
| `coexist_sphere_left_inner_35m_teammate_right_outer_35m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `35.0` | `11` | `112` | `True` | `True` | `true_positive` |
