# Phase 5D-1A 25m/30m HoloOcean Validation Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_any_hit`
- Found Rule: `sphere_blob_any_hit and any_rangefinder_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `14`
- Target Outcome Counts: `{'true_positive': 10, 'false_negative': 6}`
- Target-only Outcome Counts: `{'true_positive': 10}`
- Target-with-teammate Outcome Counts: `{'false_negative': 6}`
- Teammate Outcome Counts: `{'true_negative': 12}`
- Fan Reliable Distances: `[25.0, 30.0]`
- Max Fan Reliable Distance: `30.0`
- Teammate False Positive Scenes: `[]`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `14` | `237` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_25m` | `target` | `left_outer` | `25.0` | `10` | `44` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_25m` | `target` | `left_inner` | `25.0` | `7` | `30` | `True` | `True` | `true_positive` |
| `target_sphere_center_25m` | `target` | `center` | `25.0` | `9` | `50` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_25m` | `target` | `right_inner` | `25.0` | `7` | `35` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_25m` | `target` | `right_outer` | `25.0` | `11` | `65` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_30m` | `target` | `left_outer` | `30.0` | `7` | `33` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_30m` | `target` | `left_inner` | `30.0` | `7` | `25` | `True` | `True` | `true_positive` |
| `target_sphere_center_30m` | `target` | `center` | `30.0` | `8` | `24` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_30m` | `target` | `right_inner` | `30.0` | `8` | `43` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_30m` | `target` | `right_outer` | `30.0` | `9` | `45` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_25m` | `teammate_only` | `left_outer` | `25.0` | `9` | `208` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_25m` | `teammate_only` | `left_inner` | `25.0` | `9` | `126` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_25m` | `teammate_only` | `center` | `25.0` | `9` | `77` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_25m` | `teammate_only` | `right_inner` | `25.0` | `8` | `125` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_25m` | `teammate_only` | `right_outer` | `25.0` | `8` | `198` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_30m` | `teammate_only` | `left_outer` | `30.0` | `9` | `137` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_30m` | `teammate_only` | `left_inner` | `30.0` | `9` | `97` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_30m` | `teammate_only` | `center` | `30.0` | `11` | `49` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_30m` | `teammate_only` | `right_inner` | `30.0` | `10` | `79` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_30m` | `teammate_only` | `right_outer` | `30.0` | `10` | `178` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_inner_25m` | `teammate_only` | `left_right_inner_pair` | `25.0` | `12` | `270` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_outer_30m` | `teammate_only` | `left_right_outer_pair` | `30.0` | `9` | `282` | `True` | `False` | `true_negative` |
| `coexist_sphere_center_25m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `25.0` | `11` | `258` | `True` | `False` | `false_negative` |
| `coexist_sphere_center_30m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `30.0` | `11` | `221` | `True` | `False` | `false_negative` |
| `coexist_sphere_left_inner_25m_teammate_right_outer_25m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `25.0` | `11` | `230` | `True` | `False` | `false_negative` |
| `coexist_sphere_right_inner_30m_teammate_left_outer_30m` | `target_with_teammate` | `target_right_inner_teammate_left_outer` | `30.0` | `11` | `163` | `True` | `False` | `false_negative` |
| `coexist_sphere_left_outer_30m_teammate_right_inner_25m` | `target_with_teammate` | `target_left_outer_teammate_right_inner` | `30.0` | `11` | `163` | `True` | `False` | `false_negative` |
| `coexist_sphere_right_outer_25m_teammate_left_inner_25m` | `target_with_teammate` | `target_right_outer_teammate_left_inner` | `25.0` | `11` | `173` | `True` | `False` | `false_negative` |
