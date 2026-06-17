# Phase 5D-1A Local Range-Scaled Blob Calibration Summary

- Target Agent Type: `SphereAgent`
- Teammate Negative Agent Type: `SurfaceVessel`
- Same Model Teammate And Target: `False`
- Recommended Rule ID: `sphere_blob_local_range_scaled_any_hit`
- Found Rule: `sphere_blob_local_range_scaled_any_hit`
- RGB target_overlap_min: `None`
- RGB changed_pixels_min: `None`
- Target Signature Color Count: `12`
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
| `calibration_sphere_front_center_10m` | `calibration` | `center` | `10.0` | `12` | `237` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_20m` | `target` | `left_outer` | `20.0` | `8` | `55` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_20m` | `target` | `left_inner` | `20.0` | `7` | `52` | `True` | `True` | `true_positive` |
| `target_sphere_center_20m` | `target` | `center` | `20.0` | `5` | `45` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_20m` | `target` | `right_inner` | `20.0` | `7` | `56` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_20m` | `target` | `right_outer` | `20.0` | `9` | `64` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_25m` | `target` | `left_outer` | `25.0` | `9` | `45` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_25m` | `target` | `left_inner` | `25.0` | `7` | `30` | `True` | `True` | `true_positive` |
| `target_sphere_center_25m` | `target` | `center` | `25.0` | `5` | `35` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_25m` | `target` | `right_inner` | `25.0` | `10` | `61` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_25m` | `target` | `right_outer` | `25.0` | `9` | `50` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_30m` | `target` | `left_outer` | `30.0` | `7` | `32` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_30m` | `target` | `left_inner` | `30.0` | `5` | `25` | `True` | `True` | `true_positive` |
| `target_sphere_center_30m` | `target` | `center` | `30.0` | `5` | `21` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_30m` | `target` | `right_inner` | `30.0` | `5` | `24` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_30m` | `target` | `right_outer` | `30.0` | `7` | `27` | `True` | `True` | `true_positive` |
| `target_sphere_left_outer_35m` | `target` | `left_outer` | `35.0` | `6` | `22` | `True` | `True` | `true_positive` |
| `target_sphere_left_inner_35m` | `target` | `left_inner` | `35.0` | `4` | `14` | `True` | `True` | `true_positive` |
| `target_sphere_center_35m` | `target` | `center` | `35.0` | `3` | `8` | `True` | `True` | `true_positive` |
| `target_sphere_right_inner_35m` | `target` | `right_inner` | `35.0` | `7` | `17` | `True` | `True` | `true_positive` |
| `target_sphere_right_outer_35m` | `target` | `right_outer` | `35.0` | `6` | `19` | `True` | `True` | `true_positive` |
| `teammate_only_surfacevessel_left_outer_20m` | `teammate_only` | `left_outer` | `20.0` | `7` | `283` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_20m` | `teammate_only` | `left_inner` | `20.0` | `8` | `207` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_20m` | `teammate_only` | `center` | `20.0` | `8` | `112` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_20m` | `teammate_only` | `right_inner` | `20.0` | `9` | `184` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_20m` | `teammate_only` | `right_outer` | `20.0` | `6` | `301` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_25m` | `teammate_only` | `left_outer` | `25.0` | `7` | `189` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_25m` | `teammate_only` | `left_inner` | `25.0` | `8` | `133` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_25m` | `teammate_only` | `center` | `25.0` | `8` | `76` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_25m` | `teammate_only` | `right_inner` | `25.0` | `9` | `135` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_25m` | `teammate_only` | `right_outer` | `25.0` | `7` | `209` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_30m` | `teammate_only` | `left_outer` | `30.0` | `7` | `139` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_30m` | `teammate_only` | `left_inner` | `30.0` | `7` | `93` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_30m` | `teammate_only` | `center` | `30.0` | `8` | `44` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_30m` | `teammate_only` | `right_inner` | `30.0` | `10` | `95` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_30m` | `teammate_only` | `right_outer` | `30.0` | `6` | `144` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_outer_35m` | `teammate_only` | `left_outer` | `35.0` | `9` | `99` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_left_inner_35m` | `teammate_only` | `left_inner` | `35.0` | `9` | `73` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_center_35m` | `teammate_only` | `center` | `35.0` | `6` | `31` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_inner_35m` | `teammate_only` | `right_inner` | `35.0` | `8` | `54` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_right_outer_35m` | `teammate_only` | `right_outer` | `35.0` | `7` | `94` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_inner_25m` | `teammate_only` | `left_right_inner_pair` | `25.0` | `8` | `247` | `True` | `False` | `true_negative` |
| `teammate_only_surfacevessel_pair_outer_30m` | `teammate_only` | `left_right_outer_pair` | `30.0` | `7` | `281` | `True` | `False` | `true_negative` |
| `coexist_sphere_center_20m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `20.0` | `5` | `44` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_25m_teammate_left_inner_20m` | `target_with_teammate` | `target_center_teammate_left_inner` | `25.0` | `9` | `246` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_30m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `30.0` | `10` | `218` | `True` | `True` | `true_positive` |
| `coexist_sphere_left_inner_25m_teammate_right_outer_25m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `25.0` | `9` | `233` | `True` | `True` | `true_positive` |
| `coexist_sphere_right_inner_30m_teammate_left_outer_30m` | `target_with_teammate` | `target_right_inner_teammate_left_outer` | `30.0` | `9` | `163` | `True` | `True` | `true_positive` |
| `coexist_sphere_left_outer_30m_teammate_right_inner_25m` | `target_with_teammate` | `target_left_outer_teammate_right_inner` | `30.0` | `9` | `156` | `True` | `True` | `true_positive` |
| `coexist_sphere_right_outer_25m_teammate_left_inner_25m` | `target_with_teammate` | `target_right_outer_teammate_left_inner` | `25.0` | `11` | `183` | `True` | `True` | `true_positive` |
| `coexist_sphere_center_35m_teammate_right_inner_20m` | `target_with_teammate` | `target_center_teammate_right_inner` | `35.0` | `9` | `199` | `True` | `True` | `true_positive` |
| `coexist_sphere_left_inner_35m_teammate_right_outer_35m` | `target_with_teammate` | `target_left_inner_teammate_right_outer` | `35.0` | `9` | `111` | `True` | `True` | `true_positive` |
