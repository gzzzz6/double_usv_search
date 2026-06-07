"""Unit tests for the HoloOcean scene map adapter module."""

import os
import tempfile
import numpy as np
import pytest

from baseline_GP.core_map import FREE, OCCUPIED
from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid
from baseline_GP.holoocean_bridge.scene_map_adapter import (
    load_scene_map_spec,
    scene_map_config_from_spec,
    build_scene_occupancy_grid,
    save_scene_map_npz,
    load_scene_map_npz,
    scene_map_world_bounds,
    validate_scene_map,
)

SPEC_PATH = r"baseline_GP/holoocean_bridge/maps/openwater_open_v1.json"


def test_load_scene_map_spec():
    """Verify that JSON spec can be loaded and fields are correct."""
    assert os.path.exists(SPEC_PATH), f"Specification file not found at {SPEC_PATH}"
    spec = load_scene_map_spec(SPEC_PATH)
    assert spec["map_id"] == "openwater_open_v1"
    assert spec["world"] == "OpenWater"
    assert spec["package_name"] == "Ocean"
    assert spec["cell_size_m"] == 5.0
    assert spec["origin_world_xy"] == [-200.0, 200.0]
    assert spec["water_surface_z"] == 0.0
    assert spec["height"] == 81
    assert spec["width"] == 81
    assert spec["boundary_occupied"] is True
    assert spec["occupied_rects_world"] == []


def test_scene_map_config_from_spec():
    """Verify CoordinateAdapterConfig setup from spec."""
    spec = load_scene_map_spec(SPEC_PATH)
    config = scene_map_config_from_spec(spec)
    assert config.cell_size_m == 5.0
    assert config.origin_world_xy == (-200.0, 200.0)
    assert config.water_surface_z == 0.0


def test_build_scene_occupancy_grid():
    """Verify shape, boundaries, and interior values of the built grid."""
    spec = load_scene_map_spec(SPEC_PATH)
    grid = build_scene_occupancy_grid(spec)

    assert grid.shape == (81, 81)

    # Check boundaries are OCCUPIED
    assert np.all(grid[0, :] == OCCUPIED)
    assert np.all(grid[-1, :] == OCCUPIED)
    assert np.all(grid[:, 0] == OCCUPIED)
    assert np.all(grid[:, -1] == OCCUPIED)

    # Check interior is FREE
    interior = grid[1:-1, 1:-1]
    assert np.all(interior == FREE)


def test_coordinate_mapping():
    """Verify grid cells map correctly to physical coordinates under openwater config."""
    spec = load_scene_map_spec(SPEC_PATH)
    config = scene_map_config_from_spec(spec)

    # Test center cell (40, 40) -> [0, 0, 0]
    center_world = grid_to_world((40, 40), config)
    np.testing.assert_allclose(center_world, [0.0, 0.0, 0.0], atol=1e-7)

    # Test cell (0, 0) -> [-200, 200, 0]
    topleft_world = grid_to_world((0, 0), config)
    np.testing.assert_allclose(topleft_world, [-200.0, 200.0, 0.0], atol=1e-7)

    # Test cell (80, 80) -> [200, -200, 0]
    bottomright_world = grid_to_world((80, 80), config)
    np.testing.assert_allclose(bottomright_world, [200.0, -200.0, 0.0], atol=1e-7)

    # Inverse mapping checks
    assert world_to_grid([0.0, 0.0, 0.0], config, (81, 81)) == (40, 40)
    assert world_to_grid([-200.0, 200.0, 0.0], config, (81, 81)) == (0, 0)
    assert world_to_grid([200.0, -200.0, 0.0], config, (81, 81)) == (80, 80)


def test_save_load_npz():
    """Verify save/load integrity and validation logic."""
    spec = load_scene_map_spec(SPEC_PATH)
    grid = build_scene_occupancy_grid(spec)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_npz = os.path.join(tmpdir, "test_map.npz")
        save_scene_map_npz(temp_npz, grid, spec)

        loaded_grid, loaded_spec = load_scene_map_npz(temp_npz)

        np.testing.assert_array_equal(loaded_grid, grid)
        assert loaded_spec == spec

        # Test validate_scene_map utility
        report = validate_scene_map(loaded_grid, loaded_spec)
        assert report["is_valid"] is True
        assert len(report["errors"]) == 0


def test_occupied_rects_world_synthetic():
    """Verify that occupied_rects_world is correctly projected to occupied grid cells."""
    synthetic_spec = {
        "map_id": "synthetic_test",
        "world": "OpenWater",
        "package_name": "Ocean",
        "cell_size_m": 5.0,
        "origin_world_xy": [-100.0, 100.0],
        "water_surface_z": 0.0,
        "height": 41,  # xmin is -100, xmax is 100. Center is (20, 20) -> [0, 0, 0]
        "width": 41,
        "boundary_occupied": False,
        "occupied_rects_world": [
            # A rectangle spanning x in [-10, 10] and y in [-10, 10]
            # Since cell_size is 5, origin is [-100, 100], Center is (20,20)
            # xmin = -10 corresponds to col = (-10 - (-100)) / 5 = 18
            # xmax = 10 corresponds to col = (10 - (-100)) / 5 = 22
            # ymin = -10 corresponds to row = (100 - (-10)) / 5 = 22
            # ymax = 10 corresponds to row = (100 - 10) / 5 = 18
            # Range: row in [18, 22], col in [18, 22]
            {"xmin": -10.0, "xmax": 10.0, "ymin": -10.0, "ymax": 10.0}
        ],
    }

    grid = build_scene_occupancy_grid(synthetic_spec)

    # Boundaries should be FREE
    assert grid[0, 0] == FREE
    assert grid[-1, -1] == FREE

    # The region row 18-22, col 18-22 should be OCCUPIED
    assert np.all(grid[18:23, 18:23] == OCCUPIED)

    # Outside the region (e.g. cell (17, 17) or (23, 23)) should be FREE
    assert grid[17, 17] == FREE
    assert grid[23, 23] == FREE

    # Test validator on this synthetic map
    report = validate_scene_map(grid, synthetic_spec)
    assert report["is_valid"] is True


def test_scene_map_world_bounds():
    """Verify bounds calculations."""
    spec = load_scene_map_spec(SPEC_PATH)
    bounds = scene_map_world_bounds(spec)
    assert bounds["xmin"] == -200.0
    assert bounds["xmax"] == 200.0  # -200 + (81-1)*5 = 200
    assert bounds["ymin"] == -200.0  # 200 - (81-1)*5 = -200
    assert bounds["ymax"] == 200.0


def test_openwater_res10_spec():
    """Verify res10 json/npz exists and spec matches."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    res10_json_path = os.path.normpath(os.path.join(current_dir, "..", "holoocean_bridge", "maps", "openwater_open_res10_v1.json"))
    res10_npz_path = os.path.normpath(os.path.join(current_dir, "..", "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

    assert os.path.exists(res10_json_path), f"Spec file not found at {res10_json_path}"
    assert os.path.exists(res10_npz_path), f"NPZ file not found at {res10_npz_path}"

    spec = load_scene_map_spec(res10_json_path)
    assert spec["map_id"] == "openwater_open_res10_v1"
    assert spec["world"] == "OpenWater"
    assert spec["package_name"] == "Ocean"
    assert spec["cell_size_m"] == 10.0
    assert spec["origin_world_xy"] == [-400.0, 400.0]
    assert spec["water_surface_z"] == 0.0
    assert spec["height"] == 81
    assert spec["width"] == 81
    assert spec["boundary_occupied"] is True

    grid, loaded_spec = load_scene_map_npz(res10_npz_path)
    assert grid.shape == (81, 81)
    assert loaded_spec == spec


def test_openwater_res10_coordinate_mapping():
    """Verify grid cells map correctly under res10 config."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    res10_json_path = os.path.normpath(os.path.join(current_dir, "..", "holoocean_bridge", "maps", "openwater_open_res10_v1.json"))
    spec = load_scene_map_spec(res10_json_path)
    config = scene_map_config_from_spec(spec)

    # test boundaries & center
    c_w = grid_to_world((40, 40), config)
    np.testing.assert_allclose(c_w, [0.0, 0.0, 0.0], atol=1e-7)

    tl_w = grid_to_world((0, 0), config)
    np.testing.assert_allclose(tl_w, [-400.0, 400.0, 0.0], atol=1e-7)

    br_w = grid_to_world((80, 80), config)
    np.testing.assert_allclose(br_w, [400.0, -400.0, 0.0], atol=1e-7)

    # world to grid
    assert world_to_grid([0.0, 0.0, 0.0], config, (81, 81)) == (40, 40)
    assert world_to_grid([-400.0, 400.0, 0.0], config, (81, 81)) == (0, 0)
    assert world_to_grid([400.0, -400.0, 0.0], config, (81, 81)) == (80, 80)

