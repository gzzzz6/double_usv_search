# Phase 5B-2: E2E Dual SurfaceVessel Coordinated Search One-Step Bridge Report

## Simulation Environment
- **Run Label**: `dual_usv_one_step_holoocean_bridge`
- **HoloOcean World**: `OpenWater`
- **Package**: `Ocean`
- **Search USVs**: `sv0` and `sv1` (both in `control_scheme=0` direct propeller manual force mode)

## Centralized Algorithm Alignment
- **Coordinated Policy**: `marine_knownmap_path_v2_infosampled_2usv`
- **Centralized Planner**: `coordinated`
- **Sigma Parameters**:
  - `clue_sigma_m = 30.0` (As confirmed from current local runtime default value)
  - `clue_sigma_cells = 3`
- **Initial Grid Alignment Check**: `PASSED`
  - `sv0` Start Cell: `[25, 2]` ↔ Planned Target Cell: `[24, 2]`
  - `sv1` Start Cell: `[35, 2]` ↔ Planned Target Cell: `[35, 3]`

## Physical Execution & Step Progress
- **Total Physical Simulation Ticks**: `76`
- **Arrival Status**:
  - `sv0_arrived` : `True` (`ticks = 76`, final error: `4.99 m`)
  - `sv1_arrived` : `True` (`ticks = 76`, final error: `0.14 m`)
- **Timeout Count**: `0`
- **Chebyshev Target Cell Alignment**:
  - `sv0` final projected grid matches algorithm target: `True` (final: `[24, 2]`)
  - `sv1` final projected grid matches algorithm target: `True` (final: `[35, 3]`)

## Inter-Vessel Separation & Collision Metrics
- **Min Inter-Vessel Distance**: `100.00 m` (Warning limit: `30.0 m`, hard limit: `20.0 m`)
- **Collision Warning Ticks (< 30m)**: `0`
- **Collision Fail Ticks (< 20m)**: `0`
- **Separation Safety Compliance**: `PASSED`

## Sensor Source & Fallback Statistics
- **sv0 Selected Sensor Counts**:
  - `LocationSensor` : `76`
  - `GPSSensor`      : `0`
  - `last_known`     : `0`
- **sv1 Selected Sensor Counts**:
  - `LocationSensor` : `76`
  - `GPSSensor`      : `0`
  - `last_known`     : `0`
- **Total Fallbacks Encountered**:
  - `sv0` fallback count: `0`
  - `sv1` fallback count: `0`

## Verification Standard Checklist
- **Bi-directional coordinate mapping**: `PASSED`
- **One-step coordinated algorithm target matches Phase 5B-1**: `PASSED`
- **No target spawner / sonar / camera active**: `PASSED`
- **100% Waypoint Arrival**: `PASSED`
- **Zero Timeout Navigation**: `PASSED`
- **Collision Safety Margin Compliance**: `PASSED`
