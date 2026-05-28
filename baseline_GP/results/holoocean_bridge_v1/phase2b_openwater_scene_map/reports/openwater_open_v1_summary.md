# HoloOcean Scene-derived Map Build Report - Phase 2B

## Map Metadata
- **Map ID**: `openwater_open_v1`
- **HoloOcean World**: `OpenWater`
- **HoloOcean Package**: `Ocean`
- **Description**: OpenWater scene-derived open-water known static map. Interior cells are FREE and boundary cells are OCCUPIED.

## Grid Configuration
- **Shape**: `81 x 81` (Total cells: `6561`)
- **Cell Size**: `5.0 m`
- **Origin World XY**: `[-200.0, 200.0]`
- **Water Surface Z**: `0.0 m`

## Cell Distribution
- **FREE Cells**: `6241` (Interior cells)
- **OCCUPIED Cells**: `320` (Boundary cells)
- **Boundary Occupied**: `True`
- **Internal Obstacles Count**: `0`

## Coordinate Adapter Verification
The static coordinate translation maps exactly as follows:
- **Top-Left Cell `(0, 0)`** $\rightarrow$ World Coordinate `[-200.0, 200.0, 0.0]`
- **Center Cell `(40, 40)`** $\rightarrow$ World Coordinate `[0.0, 0.0, 0.0]`
- **Bottom-Right Cell `(80, 80)`** $\rightarrow$ World Coordinate `[200.0, -200.0, 0.0]`

## File Outputs
1. **JSON Specification**: `[openwater_open_v1.json](baseline_GP\holoocean_bridge\maps\openwater_open_v1.json)`
   - SHA256: `0525c4fa6d67e5779a77cec28d635f1ff8fbf899563598d250ed8fe7a6f31e6e`
2. **Compressed Occupancy NPZ**: `[openwater_open_v1.npz](baseline_GP\holoocean_bridge\maps\openwater_open_v1.npz)`
   - SHA256: `dc9a80366ba2ccf008a9292830922f621491a9599731f84404bbe64d04bf3924`
3. **Build Manifest**: `[openwater_open_v1_manifest.json](baseline_GP\results\holoocean_bridge_v1\phase2b_openwater_scene_map\manifests\openwater_open_v1_manifest.json)`
4. **Visual Preview**: `[openwater_open_v1_preview.png](baseline_GP\results\holoocean_bridge_v1\phase2b_openwater_scene_map\visuals\openwater_open_v1_preview.png)`

## Validation Results
- **Validation Status**: `PASSED`
- **Errors Encountered**: None

*Note: This static map was generated cleanly by analytical derivation without importing holoocean or executing simulator instances.*
