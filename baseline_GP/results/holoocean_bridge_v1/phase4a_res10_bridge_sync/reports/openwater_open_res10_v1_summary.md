# HoloOcean Scene-derived Map Build Report - Phase 4A

## Map Metadata
- **Map ID**: `openwater_open_res10_v1`
- **HoloOcean World**: `OpenWater`
- **HoloOcean Package**: `Ocean`
- **Description**: OpenWater scene-derived 10m open-water known static map. Interior cells are FREE and boundary cells are OCCUPIED.

## Grid Configuration
- **Shape**: `81 x 81` (Total cells: `6561`)
- **Cell Size**: `10.0 m`
- **Origin World XY**: `[-400.0, 400.0]`
- **Water Surface Z**: `0.0 m`

## Cell Distribution
- **FREE Cells**: `6241` (Interior cells)
- **OCCUPIED Cells**: `320` (Boundary cells)
- **Boundary Occupied**: `True`
- **Internal Obstacles Count**: `0`

## Coordinate Adapter Verification
The static coordinate translation maps exactly as follows:
- **Top-Left Cell `(0, 0)`** $\rightarrow$ World Coordinate `[-400.0, 400.0, 0.0]`
- **Center Cell `(40, 40)`** $\rightarrow$ World Coordinate `[0.0, 0.0, 0.0]`
- **Bottom-Right Cell `(80, 80)`** $\rightarrow$ World Coordinate `[400.0, -400.0, 0.0]`

All three coordinates pass bi-directional round-trip checks.

## File Outputs
1. **JSON Specification**: `[openwater_open_res10_v1.json](baseline_GP\holoocean_bridge\maps\openwater_open_res10_v1.json)`
   - SHA256: `2f0c28048a0584cda3c0f3109775a5437447b747a70751ef500be25ce9264af0`
2. **Compressed Occupancy NPZ**: `[openwater_open_res10_v1.npz](baseline_GP\holoocean_bridge\maps\openwater_open_res10_v1.npz)`
   - SHA256: `b33a4e8114e5b57a234eda19aae27df9043c7f6f309a728b7fb69450f2c5af02`
3. **Build Manifest**: `[openwater_open_res10_v1_manifest.json](baseline_GP\results\holoocean_bridge_v1\phase4a_res10_bridge_sync\manifests\openwater_open_res10_v1_manifest.json)`
4. **Visual Preview**: `[openwater_open_res10_v1_preview.png](baseline_GP\results\holoocean_bridge_v1\phase4a_res10_bridge_sync\visuals\openwater_open_res10_v1_preview.png)`

## Validation Results
- **Validation Status**: `PASSED`
- **Errors Encountered**: None

*Note: This static map was generated cleanly by analytical derivation without importing holoocean or executing simulator instances.*
