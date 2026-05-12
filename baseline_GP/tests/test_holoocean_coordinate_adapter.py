from __future__ import annotations

import numpy as np
import pytest

from baseline_GP.core_map import FREE, OCCUPIED
from baseline_GP.holoocean_bridge.coordinate_adapter import (
    CoordinateAdapterConfig,
    grid_path_to_world,
    grid_to_world,
    is_in_bounds,
    project_world_to_nearest_free_cell,
    world_to_grid,
)


def test_origin_cell_maps_to_origin_world() -> None:
    world = grid_to_world((0, 0), CoordinateAdapterConfig())
    np.testing.assert_allclose(world, np.array([0.0, 0.0, 0.0]))


def test_two_usv_mainline_starts_map_to_expected_world_points() -> None:
    config = CoordinateAdapterConfig(cell_size_m=5.0)

    np.testing.assert_allclose(grid_to_world((25, 2), config), [10.0, -125.0, 0.0])
    np.testing.assert_allclose(grid_to_world((35, 2), config), [10.0, -175.0, 0.0])


def test_exact_round_trip_returns_original_cell() -> None:
    config = CoordinateAdapterConfig(cell_size_m=5.0)
    cell = (24, 3)

    assert world_to_grid(grid_to_world(cell, config), config, map_shape=(60, 80)) == cell


def test_perturbed_world_position_returns_nearest_cell() -> None:
    config = CoordinateAdapterConfig(cell_size_m=5.0)
    world = grid_to_world((24, 3), config)
    perturbed = world + np.array([1.9, -1.9, 0.0])

    assert world_to_grid(perturbed, config, map_shape=(60, 80)) == (24, 3)


def test_out_of_bounds_without_clamp_raises() -> None:
    config = CoordinateAdapterConfig(cell_size_m=5.0)

    with pytest.raises(ValueError):
        world_to_grid([-5.0, 0.0], config, map_shape=(40, 60), clamp=False)


def test_out_of_bounds_with_clamp_returns_boundary_cell() -> None:
    config = CoordinateAdapterConfig(cell_size_m=5.0)

    assert world_to_grid([-5.0, 500.0], config, map_shape=(40, 60), clamp=True) == (0, 0)


def test_project_world_to_nearest_free_cell_skips_occupied_cells() -> None:
    nav_map = np.full((5, 5), OCCUPIED, dtype=np.int8)
    nav_map[2, 3] = FREE
    config = CoordinateAdapterConfig(cell_size_m=5.0)

    assert project_world_to_nearest_free_cell(grid_to_world((2, 2), config), nav_map, config) == (2, 3)


def test_project_world_to_nearest_free_cell_raises_when_no_free_cell() -> None:
    nav_map = np.full((3, 3), OCCUPIED, dtype=np.int8)

    with pytest.raises(ValueError):
        project_world_to_nearest_free_cell([0.0, 0.0], nav_map)


def test_grid_path_to_world_shape_and_values() -> None:
    config = CoordinateAdapterConfig(cell_size_m=5.0)
    world_path = grid_path_to_world([(0, 0), (1, 2), (3, 4)], config)

    assert world_path.shape == (3, 3)
    np.testing.assert_allclose(world_path[1], [10.0, -5.0, 0.0])


def test_is_in_bounds_accepts_shape_or_array() -> None:
    nav_map = np.zeros((3, 4), dtype=np.int8)

    assert is_in_bounds((2, 3), nav_map)
    assert not is_in_bounds((3, 3), nav_map.shape)

