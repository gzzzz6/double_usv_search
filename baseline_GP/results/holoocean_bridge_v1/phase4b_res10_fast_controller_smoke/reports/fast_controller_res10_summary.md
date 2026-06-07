# Phase 4B: SurfaceVessel control_scheme=0 Fast Controller Smoke Report (10m)
 
## Simulation Environment
- **Run Label**: `fast_controller_res10_smoke`
- **HoloOcean World**: `OpenWater`
- **Package**: `Ocean`
- **Search USV**: `SurfaceVessel` (`sv`)
- **Control Scheme**: `0` (Twin-propeller manual force control mode)
- **Controller Config**:
  - `MAX_FORCE = 8000.0`
  - `MIN_FORCE = 1500.0`
  - `TURN_GAIN = 0.8`
  - `DIST_SLOW_RADIUS_M = 12.0`
  - `ARRIVAL_RADIUS_M = 5.0`
  - `MAX_TICKS_PER_WAYPOINT = 400`

## Execution Summary
- **Total Waypoints**: `4`
- **Total Ticks**: `254`
- **Wall Time**: `16.61 s`
- **Mean Ticks/Waypoint**: `63.5`
- **Arrived Count**: `4` / 4
- **Timeout Count**: `0`

## Waypoint Details Table
| WP | Target Cell | Start World | Final World | Final Proj Cell | Ticks | Arr | TO | Min Dist(m) | Final Dist(m) |
| :-: | :---: | :---: | :---: | :---: | :---: | :-: | :-: | :---: | :---: |
| 1 | (40,41) | (0.0,0.0) | (5.1,0.0) | (40,41) | 44 | Y | N | 4.90 | 4.90 |
| 2 | (41,41) | (5.2,0.0) | (9.7,-5.0) | (41,41) | 73 | Y | N | 4.96 | 4.96 |
| 3 | (41,40) | (9.8,-5.2) | (4.9,-9.6) | (41,40) | 70 | Y | N | 4.89 | 4.89 |
| 4 | (40,40) | (4.7,-9.6) | (0.3,-4.9) | (40,40) | 67 | Y | N | 4.93 | 4.93 |
## Performance Verification
- **All targets matched**: `PASSED`
- **All arrived**: `PASSED`
- **Zero timeout**: `PASSED`
- **Mean ticks < 300**: `PASSED`
