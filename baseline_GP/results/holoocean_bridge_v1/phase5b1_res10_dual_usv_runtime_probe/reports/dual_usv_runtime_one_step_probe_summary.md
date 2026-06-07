# Phase 5B-1: E2E Dual USV Runtime One-Step Probe Report

## Probe Environment Configuration
- **Runtime Target**: `marine_knownmap_path_v2_infosampled_2usv`
- **Centralized Planner Mode**: `coordinated`
- **Active Conflict Avoidance**: `reservation_v1` (`team_reservation_safety_distance_cells = 1.5`)
- **Safety Pathfinder**: `soft_clearance_astar_v1`
- **Viewpoint Mode**: `simple_ring_v1`
- **Sigma Parameters**:
  - `clue_sigma_m = 30.0`
  - `clue_sigma_cells = 3.0`
- **USV Starting Cells**:
  - `sv0`: `[25, 2]`
  - `sv1`: `[35, 2]`

## E2E Step 1 Probe Telemetry Table
| USV | Pos Before | Next Cell Alg | Wait Applied | Holo Target | Exec Success | Pos After | Commit Aft | Seg Advanced | Matches Exec |
| :-: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `sv0` | (25, 2) | (24, 2) | `False` | (24, 2) | `True` | (24, 2) | `3` | `True` | `True` |
| `sv1` | (35, 2) | (35, 3) | `False` | (35, 3) | `True` | (35, 3) | `3` | `True` | `True` |
## Verification Conclusions
- **One-step bridge feasibility**: `PASSED`
- **Synchronous A* Coordinated Segment Planner Integrity**: `PASSED`
- **HoloOcean segment target projection compatibility**: `PASSED`

*Successfully verified from the local baseline search runtime.*
