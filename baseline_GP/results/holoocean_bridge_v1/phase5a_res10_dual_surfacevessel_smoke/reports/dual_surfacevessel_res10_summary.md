# Phase 5A: Dual SurfaceVessel 10m OpenWater Fast-Controller Smoke Report

## Simulation Environment
- **Run Label**: `dual_surfacevessel_res10_smoke`
- **HoloOcean World**: `OpenWater`
- **Package**: `Ocean`
- **Search USVs**: `sv0` and `sv1` (both in `control_scheme=0` twin-propeller mode)
- **Controller Parameters**:
  - `MAX_FORCE = 8000.0`
  - `MIN_FORCE = 1500.0`
  - `TURN_GAIN = 0.8`
  - `DIST_SLOW_RADIUS_M = 12.0`
  - `ARRIVAL_RADIUS_M = 5.0`
  - `MAX_TICKS_PER_PAIRED_WAYPOINT = 400`

## Physical Execution & Security Summary
- **Paired Waypoints**: `4`
- **Total Agent Waypoints**: `8`
- **Arrived Count**: `8` / 8
- **Timeout Count**: `0`
- **Total Simulation Ticks**: `319`
- **Mean Ticks/Waypoint Pair**: `79.8`
- **Wall Clock Time**: `18.88 s`

## Inter-Vessel Separation & Collision Metrics
- **Min Inter-Vessel Distance**: `78.33 m` (Safety Limit: `20.0 m`, Warning: `30.0 m`)
- **Collision Warning Counts (< 30m)**: `0`
- **Collision Violations (< 20m)**: `0`
- **Vessel Collision Safety Verification**: `PASSED`

## Waypoint Sequence Execution Table
| Pair | sv0 Target | sv0 Proj | sv0 Ticks | sv0 Arr | sv1 Target | sv1 Proj | sv1 Ticks | sv1 Arr | Total Ticks | Min Sep(m) |
| :-: | :---: | :---: | :---: | :-: | :---: | :---: | :---: | :-: | :---: | :---: |
| 1 | (39,35) | (39,35) | 76 | Y | (41,45) | (41,45) | 76 | Y | 76 | 100.00 |
| 2 | (39,36) | (39,36) | 93 | Y | (41,44) | (41,44) | 68 | Y | 93 | 88.96 |
| 3 | (40,36) | (40,36) | 59 | Y | (40,44) | (40,44) | 70 | Y | 70 | 78.68 |
| 4 | (40,35) | (40,35) | 80 | Y | (40,45) | (40,45) | 75 | Y | 80 | 78.33 |
## Verification Standard Checklist
- **Bi-directional coordinate mapping**: `PASSED`
- **Zero active search/clue pollution**: `PASSED`
- **Multi-agent active movement**: `PASSED`
- **All targets matched**: `PASSED`
- **100% Waypoint Arrival**: `PASSED`
- **Zero Timeout Navigation**: `PASSED`
- **Collision Safety Margin Compliance**: `PASSED`
