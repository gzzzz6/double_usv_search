"""Script to build the openwater_open_res10_v1 static occupancy grid from JSON spec."""

import os
import json
import numpy as np
import hashlib
from typing import Dict, Any

from baseline_GP.core_map import FREE, OCCUPIED
from baseline_GP.holoocean_bridge.coordinate_adapter import CoordinateAdapterConfig, grid_to_world, world_to_grid
from baseline_GP.holoocean_bridge.scene_map_adapter import (
    load_scene_map_spec,
    build_scene_occupancy_grid,
    save_scene_map_npz,
    load_scene_map_npz,
    scene_map_world_bounds,
    validate_scene_map,
    scene_map_config_from_spec,
)

# Paths
BASE_DIR = r"baseline_GP"
SPEC_PATH = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.json"))
NPZ_PATH = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", "phase4a_res10_bridge_sync"))
MANIFEST_PATH = os.path.normpath(os.path.join(PHASE_DIR, "manifests", "openwater_open_res10_v1_manifest.json"))
SUMMARY_PATH = os.path.normpath(os.path.join(PHASE_DIR, "reports", "openwater_open_res10_v1_summary.md"))
PREVIEW_PATH = os.path.normpath(os.path.join(PHASE_DIR, "visuals", "openwater_open_res10_v1_preview.png"))


def compute_file_sha256(filepath: str) -> str:
    """Compute the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_preview(nav_map_prior: np.ndarray, config: CoordinateAdapterConfig, preview_path: str):
    """Generate a visual preview of the occupancy grid using matplotlib."""
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(8, 8))
        # Display the 2D occupancy grid where OCCUPIED is dark/black and FREE is white
        # The 10m grid spans from -400 to 400. Extent represents the physical corners of the grid.
        plt.imshow(nav_map_prior, cmap="gray_r", origin="upper", extent=[-405.0, 405.0, -405.0, 405.0])
        
        # Plot key points
        # Grid Center (40, 40) is world [0, 0]
        plt.scatter(0.0, 0.0, color="red", marker="x", s=150, linewidths=2.5, label="Center Cell (40,40) / World [0.0, 0.0]")
        
        # Grid boundaries in World coordinates
        # origin_world_xy is [-400, 400], which is Top-Left (row=0, col=0)
        plt.scatter(-400.0, 400.0, color="blue", marker="o", s=80, label="Top-Left Cell (0,0) / World [-400, 400]")
        plt.scatter(400.0, -400.0, color="green", marker="o", s=80, label="Bottom-Right Cell (80,80) / World [400, -400]")

        plt.title("HoloOcean OpenWater 10m Occupancy Grid (openwater_open_res10_v1)\n(81x81, cell_size=10m, boundary occupied)", fontsize=11, pad=10)
        plt.xlabel("World X (East-West) [m]", fontsize=10)
        plt.ylabel("World Y (North-South) [m]", fontsize=10)
        plt.grid(True, which="both", color="gray", linestyle="--", alpha=0.5)
        plt.legend(loc="upper right", framealpha=0.9)
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        plt.savefig(preview_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Preview image successfully saved to: {preview_path}")
    except ImportError:
        print("Warning: matplotlib not installed. Creating simplified visualization via text representation...")
        text_preview_path = preview_path.replace(".png", "_text.txt")
        with open(text_preview_path, "w", encoding="utf-8") as f:
            f.write("Grid Preview (81x81):\n")
            f.write("Boundary occupied = True\n")
            f.write("Center Cell (40, 40) mapped to World [0.0, 0.0]\n")
            for r in [0, 40, 80]:
                row_str = "".join(["#" if nav_map_prior[r, c] == OCCUPIED else "." for c in [0, 40, 80]])
                f.write(f"Row {r:02d}: col[0, 40, 80] = {row_str}\n")
        print(f"Simplified text preview saved to: {text_preview_path}")


def main():
    print("=== Phase 4A: Building 10m OpenWater static occupancy grid ===")
    
    # 1. Load the specification JSON
    print(f"Loading specification from: {SPEC_PATH}")
    spec = load_scene_map_spec(SPEC_PATH)
    
    # 2. Build the occupancy grid map
    print("Constructing 2D occupancy grid...")
    nav_map_prior = build_scene_occupancy_grid(spec)
    
    # Verify shape and counts
    h, w = nav_map_prior.shape
    total_cells = h * w
    occupied_count = np.sum(nav_map_prior == OCCUPIED)
    free_count = np.sum(nav_map_prior == FREE)
    print(f"Grid built successfully: shape=({h}, {w}), total_cells={total_cells}")
    print(f"Occupied cells: {occupied_count} (expected: 320)")
    print(f"Free cells: {free_count} (expected: 6241)")
    
    # 3. Validate grid maps
    print("Validating the built grid map against spec...")
    validation_report = validate_scene_map(nav_map_prior, spec)
    if not validation_report["is_valid"]:
        print(f"Validation FAILED: {validation_report['errors']}")
        raise ValueError("Generated map failed validation check.")
    print("Validation passed successfully!")

    # 4. Save to NPZ file
    print(f"Saving NPZ to: {NPZ_PATH}")
    os.makedirs(os.path.dirname(NPZ_PATH), exist_ok=True)
    save_scene_map_npz(NPZ_PATH, nav_map_prior, spec)
    
    # Verify save
    loaded_grid, loaded_spec = load_scene_map_npz(NPZ_PATH)
    assert np.array_equal(loaded_grid, nav_map_prior), "Loaded map does not match generated one"
    assert loaded_spec == spec, "Loaded spec does not match original one"
    print("NPZ save and load-back verification successful!")

    # 5. Coordinate Round-Trip Check
    config = scene_map_config_from_spec(spec)
    
    test_cells = [(40, 40), (0, 0), (80, 80)]
    expected_worlds = [
        [0.0, 0.0, 0.0],
        [-400.0, 400.0, 0.0],
        [400.0, -400.0, 0.0]
    ]
    
    roundtrip_checks = []
    for cell, exp_w in zip(test_cells, expected_worlds):
        w_coord = grid_to_world(cell, config)
        print(f"grid {cell} -> world {w_coord} (expected: {exp_w})")
        np.testing.assert_allclose(w_coord, exp_w, atol=1e-7)
        
        back_cell = world_to_grid(w_coord, config, nav_map_prior.shape)
        print(f"world {w_coord} -> grid {back_cell} (expected: {cell})")
        assert back_cell == cell, f"Round-trip failed: got {back_cell}, expected {cell}"
        
        roundtrip_checks.append({
            "cell": cell,
            "world_coord": list(w_coord),
            "back_to_cell": back_cell,
            "passed": True
        })

    # 6. Generate visual preview
    generate_preview(nav_map_prior, config, PREVIEW_PATH)

    # Compute checksums
    json_hash = compute_file_sha256(SPEC_PATH)
    npz_hash = compute_file_sha256(NPZ_PATH)

    # 7. Generate Manifest
    print(f"Writing manifest to: {MANIFEST_PATH}")
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    
    # We must explicitly set forbidden_holoocean_import = false
    manifest = {
        "map_id": spec["map_id"],
        "world": spec["world"],
        "package_name": spec["package_name"],
        "grid_shape": [h, w],
        "cell_size_m": float(spec["cell_size_m"]),
        "origin_world_xy": list(spec["origin_world_xy"]),
        "water_surface_z": float(spec["water_surface_z"]),
        "free_count": int(free_count),
        "occupied_count": int(occupied_count),
        "forbidden_holoocean_import": False,
        "created_files": [
            os.path.relpath(SPEC_PATH, "."),
            os.path.relpath(NPZ_PATH, "."),
            os.path.relpath(MANIFEST_PATH, "."),
            os.path.relpath(PREVIEW_PATH, ".")
        ],
        "roundtrip_checks": roundtrip_checks,
        "files": {
            "specification_json": {
                "path": os.path.relpath(SPEC_PATH, "."),
                "sha256": json_hash
            },
            "compressed_npz": {
                "path": os.path.relpath(NPZ_PATH, "."),
                "sha256": npz_hash
            },
            "preview_png": {
                "path": os.path.relpath(PREVIEW_PATH, ".")
            }
        },
        "coordinate_mapping": {
            "cell_size_m": spec["cell_size_m"],
            "origin_world_xy": spec["origin_world_xy"],
            "water_surface_z": spec["water_surface_z"],
            "bounds": scene_map_world_bounds(spec)
        }
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 8. Generate Summary MD Report
    print(f"Writing summary report to: {SUMMARY_PATH}")
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    
    summary_content = f"""# HoloOcean Scene-derived Map Build Report - Phase 4A

## Map Metadata
- **Map ID**: `{spec["map_id"]}`
- **HoloOcean World**: `{spec["world"]}`
- **HoloOcean Package**: `{spec["package_name"]}`
- **Description**: {spec["description"]}

## Grid Configuration
- **Shape**: `{h} x {w}` (Total cells: `{total_cells}`)
- **Cell Size**: `{spec["cell_size_m"]} m`
- **Origin World XY**: `{spec["origin_world_xy"]}`
- **Water Surface Z**: `{spec["water_surface_z"]} m`

## Cell Distribution
- **FREE Cells**: `{free_count}` (Interior cells)
- **OCCUPIED Cells**: `{occupied_count}` (Boundary cells)
- **Boundary Occupied**: `{spec["boundary_occupied"]}`
- **Internal Obstacles Count**: `{len(spec["occupied_rects_world"])}`

## Coordinate Adapter Verification
The static coordinate translation maps exactly as follows:
- **Top-Left Cell `(0, 0)`** $\\rightarrow$ World Coordinate `[-400.0, 400.0, 0.0]`
- **Center Cell `(40, 40)`** $\\rightarrow$ World Coordinate `[0.0, 0.0, 0.0]`
- **Bottom-Right Cell `(80, 80)`** $\\rightarrow$ World Coordinate `[400.0, -400.0, 0.0]`

All three coordinates pass bi-directional round-trip checks.

## File Outputs
1. **JSON Specification**: `[openwater_open_res10_v1.json]({os.path.relpath(SPEC_PATH, ".")})`
   - SHA256: `{json_hash}`
2. **Compressed Occupancy NPZ**: `[openwater_open_res10_v1.npz]({os.path.relpath(NPZ_PATH, ".")})`
   - SHA256: `{npz_hash}`
3. **Build Manifest**: `[openwater_open_res10_v1_manifest.json]({os.path.relpath(MANIFEST_PATH, ".")})`
4. **Visual Preview**: `[openwater_open_res10_v1_preview.png]({os.path.relpath(PREVIEW_PATH, ".")})`

## Validation Results
- **Validation Status**: `PASSED`
- **Errors Encountered**: None

*Note: This static map was generated cleanly by analytical derivation without importing holoocean or executing simulator instances.*
"""
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(summary_content)

    print("Phase 4A map build completed successfully!")


if __name__ == "__main__":
    main()
