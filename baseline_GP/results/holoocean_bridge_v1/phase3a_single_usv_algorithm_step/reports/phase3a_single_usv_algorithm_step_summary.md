# HoloOcean Algorithm Step Smoke Test Report - Phase 3A
 
## Simulation Environment
- **HoloOcean World**: `OpenWater`
- **HoloOcean Package**: `Ocean`
- **Agent Name**: `sv`
- **Agent Type**: `SurfaceVessel`
- **Control Scheme**: `1` (Waypoint Coordinate input `[target_x, target_y]`)
- **Sensors Used**: `GPSSensor`, `LocationSensor`
- **Search Policy**: `marine_search_soft_knownmap` (GP Clue + Search Info)

## Control Configuration
- **Arrival Radius**: `2.5 m`
- **Max Ticks Per Cell Waypoint**: `800`
- **Starting Position (Rigid)**: Cell `(1, 1)` $\rightarrow$ World `[-195.0, 195.0, 0.0]`
- **Total Steps Executed**: `8`
 
## Execution Metrics
- **Total Simulator Ticks**: `1640`
- **Total Execution Time**: `74.28 seconds`
- **Average Simulator Ticks Per Step**: `205.0`
- **Average Wall Time Per Step**: `9.29 seconds`
- **Waypoints Successfully Arrived**: `8 / 8`

## Step-by-Step Decision and Audit Chain
| Step | Position Before | Target Cell (Algorithm) | Target World (X, Y) | Final World (X, Y) | Final Grid Cell | Ticks | Arrived | Chebyshev Audit | Replan Trigger |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | (1, 1) | (1, 2) | (-190.0, 195.0) | (-192.49, 194.76) | (1, 2) | 100 | `PASSED` | `PASSED` | `initial_plan|commit_expired|segment_empty` |
| 2 | (1, 2) | (1, 3) | (-185.0, 195.0) | (-187.49, 194.94) | (1, 3) | 220 | `PASSED` | `PASSED` | `NONE` |
| 3 | (1, 3) | (1, 4) | (-180.0, 195.0) | (-182.49, 195.00) | (1, 4) | 220 | `PASSED` | `PASSED` | `NONE` |
| 4 | (1, 4) | (1, 5) | (-175.0, 195.0) | (-177.49, 195.00) | (1, 5) | 220 | `PASSED` | `PASSED` | `NONE` |
| 5 | (1, 5) | (1, 6) | (-170.0, 195.0) | (-172.49, 195.00) | (1, 6) | 220 | `PASSED` | `PASSED` | `NONE` |
| 6 | (1, 6) | (1, 7) | (-165.0, 195.0) | (-167.49, 195.00) | (1, 7) | 220 | `PASSED` | `PASSED` | `commit_expired` |
| 7 | (1, 7) | (1, 8) | (-160.0, 195.0) | (-162.49, 195.00) | (1, 8) | 220 | `PASSED` | `PASSED` | `NONE` |
| 8 | (1, 8) | (1, 9) | (-155.0, 195.0) | (-157.49, 195.00) | (1, 9) | 220 | `PASSED` | `PASSED` | `NONE` |

## Verification Outcome
- **Execution Status**: `SUCCESS`
- **Rigid Initial Verification**: `PASSED`
  - Algorithm state `robot_pos` correctly loaded as `(1, 1)`.
  - HoloOcean physical start world correctly initialized at `[-195.0, 195.0, 0.0]`.
- **Three-fold Audit Compliance**: `PASSED`
  - 100% of steps strictly satisfied: `next_cell == segment_path[1]`, `segment_path[0] == robot_pos_before`, and `final_projected_cell == next_cell`.
  - Zero manual steering waypoints injected.
- **Backwards Compatibility**: `CONFIRMED`
  - Smooth execution under Python 3.8 Conda environments.
