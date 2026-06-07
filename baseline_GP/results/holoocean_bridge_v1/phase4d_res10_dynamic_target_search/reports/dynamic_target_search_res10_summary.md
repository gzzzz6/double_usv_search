# Phase 4D: E2E 10m OpenWater Dynamic Target Discovery Summary Report

## Simulation Environment
- **Run Label**: `dynamic_target_search_res10_smoke`
- **HoloOcean World**: `OpenWater`
- **Package**: `Ocean`
- **Search USV**: `SurfaceVessel` (`sv` in `control_scheme=0` twin propeller mode)
- **Dynamic Target**: `SurfaceVessel` (`target` in `control_scheme=1` coordinate tracker mode)
- **Map resolution**: `10.0 m` (Shape: `81 x 81`, Origin: `[-400.0, 400.0]`)

## Search Parameters
- **Policy Planner**: `marine_knownmap_path_v2_infosampled`
- **Viewpoint Generation Mode**: `simple_ring_v1`
- **Path Safety Mode**: `soft_clearance_astar_v1`
- **Sensor Range**: `5 cells` (`50.0 m`)
- **GP Length Scale**: `40.0 m`
- **Clue Sigma**: `40.0 m` (`4.0 cells`)

## Search Execution Summary
- **Actual Search Steps**: `7` / `120`
- **Total Physical Ticks**: `601`
- **Wall Time**: `31.61 s`
- **Mean Ticks/Step**: `85.9`
- **Terminated Reason**: `all_found`
- **Target Found**: `True`
- **Found at Step**: `7`

## Decision History Details Table
| Step | Rob Pos Before | Target Cell Obs | Next Target Grid | Final Proj Grid | Ticks | Arr | TO | Mass Initial | Mass Final | Peak Initial | Peak Final |
| :-: | :---: | :---: | :---: | :---: | :---: | :-: | :-: | :---: | :---: | :---: | :---: |
| 1 | (40,40) | (30,43) | (39,40) | (39,40) | 76 | Y | N | 1.0000 | 1.0000 | 1.0068 | 1.0102 |
| 2 | (39,40) | (30,43) | (38,40) | (38,40) | 113 | Y | N | 1.0000 | 1.0000 | 1.0102 | 1.0124 |
| 3 | (38,40) | (30,43) | (37,40) | (37,40) | 89 | Y | N | 1.0000 | 1.0000 | 1.0124 | 1.0141 |
| 4 | (37,40) | (30,43) | (36,40) | (36,40) | 69 | Y | N | 1.0000 | 1.0000 | 1.0141 | 1.0158 |
| 5 | (36,40) | (30,43) | (35,40) | (35,40) | 96 | Y | N | 1.0000 | 1.0000 | 1.0158 | 1.0174 |
| 6 | (35,40) | (30,43) | (34,40) | (34,40) | 87 | Y | N | 1.0000 | 1.0000 | 1.0174 | 1.0190 |
| 7 | (34,40) | (30,43) | (33,40) | (33,40) | 71 | Y | N | 1.0000 | 0.0000 | 1.0190 | 0.0000 |
## Verification Details
- **Dynamic Path Planning Integrity**: `PASSED`
- **Closed-Loop Execution Fidelity**: `PASSED`
- **Dynamic Target Spawner & Projection Compliance**: `PASSED`
- **Coordinate Adapter Accuracy**: `PASSED`
