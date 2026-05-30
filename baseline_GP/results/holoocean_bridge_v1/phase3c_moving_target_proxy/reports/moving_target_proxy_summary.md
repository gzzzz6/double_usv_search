# HoloOcean Moving Target Proxy Smoke Report - Phase 3C-0
 
## Simulation Environment
- **HoloOcean World**: `OpenWater`
- **HoloOcean Package**: `Ocean`
- **Map Shape**: `81 x 81`
- **Cell Size**: `5.0 m`
- **Proxy Type Selected**: `agent`
- **Movement Method**: `act`
- **Movable Certification**: `True`

## Execution Metrics
- **Total Simulator Ticks**: `2447`
- **Total Wall Clock Time**: `92.58 seconds`
- **Total Waypoints Executed**: `5`
- **Average Ticks Per Waypoint**: `489.4`

## Waypoint Moving Detail
| Index | Target Expected | Target World (X, Y) | Target Observed | Final Projected Cell | Chebyshev Error | Distance Error (m) | Ticks Used | Arrived |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0 | (20, 20) | (-100.0, 100.0) | (-99.31, 99.99) | (20, 20) | 0 | 0.69 | 1 | `SUCCESS` |
| 1 | (20, 25) | (-75.0, 100.0) | (-77.50, 99.88) | (20, 25) | 0 | 2.50 | 559 | `SUCCESS` |
| 2 | (25, 25) | (-75.0, 75.0) | (-74.87, 77.49) | (25, 25) | 0 | 2.50 | 629 | `SUCCESS` |
| 3 | (25, 30) | (-50.0, 75.0) | (-52.50, 74.87) | (25, 30) | 0 | 2.50 | 629 | `SUCCESS` |
| 4 | (30, 30) | (-50.0, 50.0) | (-49.87, 52.50) | (30, 30) | 0 | 2.50 | 629 | `SUCCESS` |

## Verification Outcome
- **Movable Status**: `PASSED`
- **Summary**:
  - Prop Movement Approach (Scheme A): Failed due to missing move/teleport APIs in HoloOcean Environment.
  - Agent Movement Approach (Scheme B): Successfully launched "target" USV as proxy. Demonstrated full grid path tracking compliance.
