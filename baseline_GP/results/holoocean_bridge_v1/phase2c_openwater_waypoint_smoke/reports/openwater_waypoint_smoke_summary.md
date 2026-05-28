# HoloOcean Waypoint Smoke Test Report - Phase 2C

## Simulation Environment
- **HoloOcean World**: `OpenWater`
- **HoloOcean Package**: `Ocean`
- **Agent Name**: `sv`
- **Agent Type**: `SurfaceVessel`
- **Control Scheme**: `1` (Waypoint Coordinate input `[target_x, target_y]`)
- **Sensors Used**: `GPSSensor`, `LocationSensor`
- **Camera/Sonar**: `Disabled` (Pure location smoke validation)

## Control Configuration
- **Arrival Radius**: `2.5 m`
- **Max Ticks Per Waypoint**: `1500`
- **Total Waypoints**: `4`
- **Start Location**: Cell `(40, 40)` $\rightarrow$ World `[0.0, 0.0, 0.0]`

## Execution Metrics
- **Total Ticks Simulated**: `2469`
- **Total Wall-Clock Time**: `91.40 seconds`
- **Average Tick Processing Time**: `37.02 ms/tick`
- **Simulation Stuttering/Lag**: `None observed`

## Waypoint Sequence Execution Details
| WP Index | Target Cell | Target World (X, Y) | Final World (X, Y) | Final Grid Cell | Ticks | Arrived | Timeout |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0 | (40, 45) | (25.0, 0.0) | (22.52, -0.16) | (40, 45) | 583 | `TRUE` | `FALSE` |
| 1 | (45, 45) | (25.0, -25.0) | (25.13, -22.51) | (45, 45) | 630 | `TRUE` | `FALSE` |
| 2 | (45, 40) | (0.0, -25.0) | (2.48, -25.11) | (45, 40) | 628 | `TRUE` | `FALSE` |
| 3 | (40, 40) | (0.0, 0.0) | (-0.11, -2.49) | (40, 40) | 628 | `TRUE` | `FALSE` |

## Verification Outcome
- **Execution Status**: `SUCCESS` (4 / 4 arrived)
- **Grid-to-World Alignment**: `CONFIRMED`
  - Chebyshev distance for all targets is $\le 1$ cell size.
  - Final world locations correspond precisely to physical cell grids converted via `CoordinateAdapterConfig`.

*Note: This smoke test executed cleanly without importing any GP/intensity search policies or core search algorithms.*
