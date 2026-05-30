# Phase 3B-min: Single-USV Target Search Closed Loop Report

## Run Configuration
- **Label**: `target_search`
- **HoloOcean World**: `OpenWater`
- **Package**: `Ocean`
- **Agent**: `SurfaceVessel` (`sv`) / Control Scheme 1
- **Sensors**: `GPSSensor`, `LocationSensor`
- **Policy**: `marine_knownmap_path_v2_infosampled`
- **Path Safety Mode**: `soft_clearance_astar_v1`
- **Viewpoint Mode**: `simple_ring_v1`
- **Clue Acquisition**: `ucb` (temporary for Phase 3B-min)
- **Arrival Radius**: 2.5 m  |  **Max Ticks / Cell**: 800

## Execution Summary
- **Actual Steps**: `26` / 60
- **Terminated Reason**: `all_found`
- **Total Ticks**: `5558`
- **Wall Time**: `195.95 s`
- **Mean Ticks/Step**: `213.8`
- **Max Ticks/Step**: `220`
- **Arrived Count**: `26` / 26
- **Timeout Count**: `0`
- **Found (final)**: `1`
- **Final Cell**: `[2, 26]`
- **Found Events**: `{"found": true, "found_step": 26, "found_target_indices": [0], "found_target_cells": [[2, 30]], "usv_cell_at_found": [2, 26], "usv_world_at_found": [-72.49307250976562, 190.0, 0.1793944537639618], "sensor_range_cells": 5, "detection_model": "baseline_GP.core_targets.detect_targets", "note": "HoloOcean prop provides visual/scene target; detection still uses baseline_GP native simulated detection model."}`

## Step-by-Step Table
| Step | Before | Target | World (X,Y) | Proj | Ticks | Arr | Dist(m) | Found | Remaining Mass | Peak Peak/Mean | Replan |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | (1,1) | (1,2) | (-190.0,195.0) | (1,2) | 100 | Y | 2.50 | 0 | 1.0000 | 1.0000/0.9149 | Y |
| 2 | (1,2) | (2,2) | (-190.0,190.0) | (2,2) | 193 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9420 | N |
| 3 | (2,2) | (2,3) | (-185.0,190.0) | (2,3) | 205 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9405 | N |
| 4 | (2,3) | (2,4) | (-180.0,190.0) | (2,4) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9384 | N |
| 5 | (2,4) | (2,5) | (-175.0,190.0) | (2,5) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9236 | N |
| 6 | (2,5) | (2,6) | (-170.0,190.0) | (2,6) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9366 | Y |
| 7 | (2,6) | (2,7) | (-165.0,190.0) | (2,7) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9349 | N |
| 8 | (2,7) | (2,8) | (-160.0,190.0) | (2,8) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9339 | N |
| 9 | (2,8) | (2,9) | (-155.0,190.0) | (2,9) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9328 | N |
| 10 | (2,9) | (2,10) | (-150.0,190.0) | (2,10) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9305 | N |
| 11 | (2,10) | (2,11) | (-145.0,190.0) | (2,11) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9273 | Y |
| 12 | (2,11) | (2,12) | (-140.0,190.0) | (2,12) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9286 | N |
| 13 | (2,12) | (2,13) | (-135.0,190.0) | (2,13) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9264 | N |
| 14 | (2,13) | (2,14) | (-130.0,190.0) | (2,14) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9213 | N |
| 15 | (2,14) | (2,15) | (-125.0,190.0) | (2,15) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9084 | N |
| 16 | (2,15) | (2,16) | (-120.0,190.0) | (2,16) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9237 | Y |
| 17 | (2,16) | (2,17) | (-115.0,190.0) | (2,17) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8756 | N |
| 18 | (2,17) | (2,18) | (-110.0,190.0) | (2,18) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.9229 | N |
| 19 | (2,18) | (2,19) | (-105.0,190.0) | (2,19) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8990 | N |
| 20 | (2,19) | (2,20) | (-100.0,190.0) | (2,20) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8917 | N |
| 21 | (2,20) | (2,21) | (-95.0,190.0) | (2,21) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8219 | Y |
| 22 | (2,21) | (2,22) | (-90.0,190.0) | (2,22) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8601 | N |
| 23 | (2,22) | (2,23) | (-85.0,190.0) | (2,23) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8724 | N |
| 24 | (2,23) | (2,24) | (-80.0,190.0) | (2,24) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.7801 | N |
| 25 | (2,24) | (2,25) | (-75.0,190.0) | (2,25) | 220 | Y | 2.49 | 0 | 1.0000 | 1.0000/0.8701 | N |
| 26 | (2,25) | (2,26) | (-70.0,190.0) | (2,26) | 220 | Y | 2.49 | 1 | 0.0000 | 0.5000/0.3468 | Y |
## Verification
- **Three-fold alignment (all steps)**: `PASSED`
- **All arrived**: `PASSED`
- **Zero timeout**: `PASSED`
- **Clue note**: `clue_acquisition_mode = ucb temporary for Phase 3B-min`
- **Import hooks**: NONE (standard Python imports only)
