# Phase 5D-1A 25m/30m Distance Focus Result

## Calibration

- Scene count: `30`
- Target-only: `{'true_positive': 9, 'false_negative': 1}`
- Target-with-teammate: `{'false_negative': 6}`
- Teammate-only: `{'true_negative': 12}`
- Teammate FP scenes: `[]`
- Target FN scenes: `['target_sphere_center_30m', 'coexist_sphere_center_25m_teammate_left_inner_20m', 'coexist_sphere_center_30m_teammate_right_inner_20m', 'coexist_sphere_left_inner_25m_teammate_right_outer_25m', 'coexist_sphere_right_inner_30m_teammate_left_outer_30m', 'coexist_sphere_left_outer_30m_teammate_right_inner_25m', 'coexist_sphere_right_outer_25m_teammate_left_inner_25m']`
- Fan reliable distances: `[25.0]`

## Validation

- Scene count: `30`
- Target-only: `{'true_positive': 10}`
- Target-with-teammate: `{'false_negative': 6}`
- Teammate-only: `{'true_negative': 12}`
- Teammate FP scenes: `[]`
- Target FN scenes: `['coexist_sphere_center_25m_teammate_left_inner_20m', 'coexist_sphere_center_30m_teammate_right_inner_20m', 'coexist_sphere_left_inner_25m_teammate_right_outer_25m', 'coexist_sphere_right_inner_30m_teammate_left_outer_30m', 'coexist_sphere_left_outer_30m_teammate_right_inner_25m', 'coexist_sphere_right_outer_25m_teammate_left_inner_25m']`
- Fan reliable distances: `[25.0, 30.0]`

## Interpretation

25m and 30m target-only pass in validation; teammate-only remains zero false positive; all 25m/30m coexistence scenes fail under current sphere_blob_any_hit because global white-neutral area ratio is diluted or the target blob is absent under occlusion.
