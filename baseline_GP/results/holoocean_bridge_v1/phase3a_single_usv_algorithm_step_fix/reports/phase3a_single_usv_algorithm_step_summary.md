# HoloOcean Algorithm Step Smoke Test Report - Phase 3A-fix
 
## Simulation Environment
- **HoloOcean World**: `OpenWater`
- **HoloOcean Package**: `Ocean`
- **Agent Name**: `sv`
- **Agent Type**: `SurfaceVessel`
- **Control Scheme**: `1` (Waypoint Coordinate input `[target_x, target_y]`)
- **Sensors Used**: `GPSSensor`, `LocationSensor`
- **Search Policy**: `marine_knownmap_path_v2_infosampled` (GP Clue + Search Info)

## Control Configuration
- **Arrival Radius**: `2.5 m`
- **Max Ticks Per Cell Waypoint**: `800`
- **Starting Position (Rigid)**: Cell `(1, 1)` $ightarrow$ World `[-195.0, 195.0, 0.0]`
- **Total Steps Executed**: `8`
 
## Execution Metrics
- **Total Simulator Ticks**: `1598`
- **Total Execution Time**: `62.35 seconds`
- **Average Simulator Ticks Per Step**: `199.8`
- **Average Wall Time Per Step**: `7.79 seconds`

## Step-by-Step Decision and Audit Chain
| Step | Position Before | Target Cell (Algorithm) | Target World (X, Y) | Final Grid Cell | Ticks | Chebyshev Audit | Replan Trigger |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | (1, 1) | (1, 2) | (-190.0, 195.0) | (1, 2) | 100 | `PASSED` | `NONE` |
| 2 | (1, 2) | (2, 2) | (-190.0, 190.0) | (2, 2) | 193 | `PASSED` | `NONE` |
| 3 | (2, 2) | (2, 3) | (-185.0, 190.0) | (2, 3) | 205 | `PASSED` | `NONE` |
| 4 | (2, 3) | (2, 4) | (-180.0, 190.0) | (2, 4) | 220 | `PASSED` | `NONE` |
| 5 | (2, 4) | (2, 5) | (-175.0, 190.0) | (2, 5) | 220 | `PASSED` | `NONE` |
| 6 | (2, 5) | (2, 6) | (-170.0, 190.0) | (2, 6) | 220 | `PASSED` | `NONE` |
| 7 | (2, 6) | (2, 7) | (-165.0, 190.0) | (2, 7) | 220 | `PASSED` | `NONE` |
| 8 | (2, 7) | (2, 8) | (-160.0, 190.0) | (2, 8) | 220 | `PASSED` | `NONE` |

## Verification Outcome
- **Execution Status**: `SUCCESS`
- **Rigid Initial Verification**: `PASSED`
  - Algorithm state `robot_pos` correctly loaded as `(1, 1)`.
  - HoloOcean physical start world correctly initialized at `[-195.0, 195.0, 0.0]`.
- **Three-fold Audit Compliance**: `PASSED`
  - 100% of steps strictly satisfied: `next_cell == segment_path[1]`, `segment_path[0] == robot_pos_before`, and `final_projected_cell == next_cell`.
  - Zero manual steering waypoints injected.
- **Clue Acquisition Note**:
  - `clue_acquisition_mode = ucb temporary for Phase 3A smoke`
- **Backwards Compatibility**: `CONFIRMED`
  - Smooth execution under Python 3.8 Conda environments.
  - Zero sys import hooks or dynamic source patching hooks.
