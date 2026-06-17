# Phase 5D-1 Calibration Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_any_hit`
- Found Rule: `sphere_blob_any_hit and any_rangefinder_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `15`
- Target Outcome Counts: `{'true_positive': 11, 'false_negative': 2}`
- Target-only Outcome Counts: `{'true_positive': 10}`
- Target-with-teammate Outcome Counts: `{'true_positive': 1, 'false_negative': 2}`
- Teammate Outcome Counts: `{'true_negative': 27}`
- Fan Reliable Distances: `[20.0, 35.0]`
- Max Fan Reliable Distance: `35.0`
- Teammate False Positive Scenes: `[]`
- Truth Used For Detection: `False`

| Scene | Kind | Angle | Distance | Overlap | Pixels | Range Hit | Found | Outcome |
|---|---|---|---:|---:|---:|---:|---:|---|
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `15` | `235` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_20m` | `target` | `left_outer` | `20.0` | `8` | `55` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_20m` | `target` | `left_inner` | `20.0` | `7` | `52` | `True` | `True` | `true_positive` |
| `target_sphere_center_20m` | `target` | `center` | `20.0` | `6` | `44` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_20m` | `target` | `right_inner` | `20.0` | `8` | `56` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_20m` | `target` | `right_outer` | `20.0` | `11` | `76` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_35m` | `target` | `left_outer` | `35.0` | `7` | `22` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_35m` | `target` | `left_inner` | `35.0` | `4` | `14` | `True` | `True` | `true_positive` |
| `target_sphere_center_35m` | `target` | `center` | `35.0` | `3` | `8` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_35m` | `target` | `right_inner` | `35.0` | `7` | `18` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_35m` | `target` | `right_outer` | `35.0` | `8` | `24` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_10m` | `teammate_only` | `left_outer` | `10.0` | `6` | `1480` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_10m` | `teammate_only` | `left_inner` | `10.0` | `7` | `1184` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_10m` | `teammate_only` | `center` | `10.0` | `10` | `886` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_10m` | `teammate_only` | `right_inner` | `10.0` | `10` | `1132` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_10m` | `teammate_only` | `right_outer` | `10.0` | `7` | `1475` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_15m` | `teammate_only` | `left_outer` | `15.0` | `8` | `568` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_15m` | `teammate_only` | `left_inner` | `15.0` | `11` | `426` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_15m` | `teammate_only` | `center` | `15.0` | `10` | `263` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_15m` | `teammate_only` | `right_inner` | `15.0` | `13` | `396` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_15m` | `teammate_only` | `right_outer` | `15.0` | `8` | `538` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_20m` | `teammate_only` | `left_outer` | `20.0` | `11` | `286` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_20m` | `teammate_only` | `left_inner` | `20.0` | `11` | `205` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_20m` | `teammate_only` | `center` | `20.0` | `11` | `108` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_20m` | `teammate_only` | `right_inner` | `20.0` | `12` | `193` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_20m` | `teammate_only` | `right_outer` | `20.0` | `9` | `293` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_35m` | `teammate_only` | `left_outer` | `35.0` | `10` | `96` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_35m` | `teammate_only` | `left_inner` | `35.0` | `13` | `69` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_35m` | `teammate_only` | `center` | `35.0` | `10` | `37` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_35m` | `teammate_only` | `right_inner` | `35.0` | `9` | `53` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_35m` | `teammate_only` | `right_outer` | `35.0` | `11` | `98` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_edge_15m` | `teammate_only` | `left_edge` | `15.0` | `8` | `628` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_edge_15m` | `teammate_only` | `right_edge` | `15.0` | `7` | `644` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_edge_35m` | `teammate_only` | `left_edge` | `35.0` | `10` | `96` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_edge_35m` | `teammate_only` | `right_edge` | `35.0` | `10` | `119` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_inner_20m` | `teammate_only` | `left_right_inner_pair` | `20.0` | `13` | `399` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_outer_35m` | `teammate_only` | `left_right_outer_pair` | `35.0` | `12` | `200` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_triple_fan_20m` | `teammate_only` | `center_plus_inner_pair` | `20.0` | `12` | `526` | `True` | `False` | `true_negative` |
| `coexist_sphere_center_20m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `20.0` | `5` | `43` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_35m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `35.0` | `12` | `199` | `True` | `False` | `false_negative` |
| `coexist_sphere_left_inner_35m_teammate_right_outer_35m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `35.0` | `13` | `115` | `True` | `False` | `false_negative` |
