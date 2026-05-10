# Phase 0 Config Audit Report

**Audit time:** 2026-05-09T14:17:47.972585
**Results directory:** `F:\pythonprojects\baseline_GP\results\paper_simple_ring_mainline_20260505`

## Summary

| Metric | Value |
|--------|-------|
| Config snapshots found | 18 |
| Episode results files | 36 |
| Paper tables exist | Yes |
| Paper table files | 15 |
| Anomalies detected | 132 |

## Expected Mainline Configuration

| Key | Expected Value |
|-----|---------------|
| `viewpoint_generation_mode` | `simple_ring_v1` |
| `path_safety_mode` | `soft_clearance_astar_v1` |
| `team_path_avoidance_mode` | `reservation_v1` |
| `anomaly_tail_quantile` | `0.9` |
| `anomaly_weight_lambda` | `1.25` |
| `assignment_mode` | `coordinated` |
| single-USV map | 40x60 |
| two-USV map | 60x80 |
| two-USV starts | ((25, 2), (35, 2)) |

## Config Snapshots Found

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `marine_knownmap_path_v2_infosampled` | OK |
| `assignment_mode` | `None` | **MISSING** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `40` | OK |
| `map_width_cells` | `60` | OK |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `marine_knownmap_path_v2_infosampled` | OK |
| `assignment_mode` | `None` | **MISSING** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `40` | OK |
| `map_width_cells` | `60` | OK |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `marine_knownmap_path_v2_infosampled` | OK |
| `assignment_mode` | `None` | **MISSING** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `40` | OK |
| `map_width_cells` | `60` | OK |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `marine_knownmap_path_v2_infosampled` | OK |
| `assignment_mode` | `None` | **MISSING** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `40` | OK |
| `map_width_cells` | `60` | OK |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `marine_knownmap_path_v2_infosampled` | OK |
| `assignment_mode` | `None` | **MISSING** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `40` | OK |
| `map_width_cells` | `60` | OK |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `marine_knownmap_path_v2_infosampled` | OK |
| `assignment_mode` | `None` | **MISSING** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `40` | OK |
| `map_width_cells` | `60` | OK |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `coordinated` | OK |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `coordinated` | OK |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `coordinated` | OK |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `coordinated` | OK |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `coordinated` | OK |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `coordinated` | OK |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `independent` | **MISMATCH** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `independent` | **MISMATCH** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `independent` | **MISMATCH** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `random_walk` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `independent` | **MISMATCH** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `independent` | **MISMATCH** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

### config_snapshot.json (single-USV)

| Field | Value | Status |
|-------|-------|--------|
| `policy_name` | `None` | **MISSING** |
| `assignment_mode` | `independent` | **MISMATCH** |
| `map_kind` | `None` | **MISSING** |
| `map_height_cells` | `None` | **MISSING** |
| `map_width_cells` | `None` | **MISSING** |
| `target_motion_mode` | `static` | OK |
| `viewpoint_generation_mode` | `simple_ring_v1` | OK |
| `path_safety_mode` | `None` | **MISSING** |
| `team_path_avoidance_mode` | `None` | **MISSING** |
| `anomaly_tail_quantile` | `None` | **MISSING** |
| `anomaly_weight_lambda` | `None` | **MISSING** |

## Anomalies

- MISSING_FIELD: assignment_mode in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: assignment_mode in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: assignment_mode in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: assignment_mode in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: assignment_mode in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: assignment_mode in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
- MISSING_FIELD: policy_name in config_snapshot.json
- MISSING_FIELD: map_kind in config_snapshot.json
- MISSING_FIELD: map_height_cells in config_snapshot.json
- MISSING_FIELD: map_width_cells in config_snapshot.json
- MISSING_FIELD: path_safety_mode in config_snapshot.json
- MISSING_FIELD: team_path_avoidance_mode in config_snapshot.json
- MISSING_FIELD: anomaly_tail_quantile in config_snapshot.json
- MISSING_FIELD: anomaly_weight_lambda in config_snapshot.json
