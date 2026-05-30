# Phase 3D-0: SurfaceVessel control_scheme=0 Fast Controller Smoke Report
 
## Simulation Environment
- **Run Label**: `fast_controller_smoke`
- **HoloOcean World**: `OpenWater`
- **Package**: `Ocean`
- **Search USV**: `SurfaceVessel` (`sv`)
- **Control Scheme**: `0` (Twin-propeller manual force control mode)
- **Controller Config**:
  - `MAX_FORCE = 8000.0`
  - `MIN_FORCE = 1500.0`
  - `TURN_GAIN = 0.8`
  - `DIST_SLOW_RADIUS_M = 8.0`
  - `ARRIVAL_RADIUS_M = 2.5`
  - `MAX_TICKS_PER_WAYPOINT = 400`

## Execution Summary
- **Total Waypoints**: `4`
- **Total Ticks**: `914`
- **Wall Time**: `37.50 s`
- **Mean Ticks/Waypoint**: `228.5`
- **Arrived Count**: `4` / 4
- **Timeout Count**: `0`

## Waypoint Details Table
| WP | Target Cell | Start World | Final World | Final Proj Cell | Ticks | Arr | TO | Min Dist(m) | Final Dist(m) | Ref Ticks (Scheme=1) | Speedup |
| :-: | :---: | :---: | :---: | :---: | :---: | :-: | :-: | :---: | :---: | :---: | :---: |
| 1 | (40,45) | (0.0,0.0) | (22.6,0.0) | (40,45) | 161 | Y | N | 2.44 | 2.44 | 583 | 3.62x |
| 2 | (45,45) | (22.7,0.0) | (22.8,-26.0) | (45,45) | 271 | Y | N | 2.44 | 2.44 | 630 | 2.32x |
| 3 | (45,40) | (22.9,-26.0) | (0.9,-27.3) | (45,40) | 251 | Y | N | 2.50 | 2.50 | 628 | 2.50x |
| 4 | (40,40) | (0.9,-27.3) | (2.4,-0.0) | (40,40) | 231 | Y | N | 2.44 | 2.44 | 628 | 2.72x |
## Performance Verification
- **All targets matched**: `PASSED`
- **All arrived**: `PASSED`
- **Zero timeout**: `PASSED`
- **Mean ticks < 300**: `PASSED`
- **Mean ticks < 150 (Ideal)**: `FAILED`
