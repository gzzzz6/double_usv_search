"""Coordinate conversion between baseline_GP grid cells and world waypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple, Union, Optional

import numpy as np

# Bridge local constants to avoid importing from core_map module
FREE = 0


Cell = Tuple[int, int]


@dataclass(frozen=True)
class CoordinateAdapterConfig:
    """Static parameters for grid/world coordinate conversion."""

    cell_size_m: float = 5.0
    origin_world_xy: Tuple[float, float] = (0.0, 0.0)
    water_surface_z: float = 0.0

    def __post_init__(self) -> None:
        if float(self.cell_size_m) <= 0.0:
            raise ValueError("cell_size_m must be positive")
        if len(self.origin_world_xy) != 2:
            raise ValueError("origin_world_xy must contain exactly two values")


def _resolve_config(config: Optional[CoordinateAdapterConfig]) -> CoordinateAdapterConfig:
    return config if config is not None else CoordinateAdapterConfig()


def _shape_tuple(map_shape: Union[Sequence[int], np.ndarray]) -> Tuple[int, int]:
    shape = np.asarray(map_shape).shape if isinstance(map_shape, np.ndarray) else tuple(map_shape)
    if len(shape) < 2:
        raise ValueError("map_shape must contain at least two dimensions")
    height, width = int(shape[0]), int(shape[1])
    if height <= 0 or width <= 0:
        raise ValueError("map_shape dimensions must be positive")
    return height, width


def _normalize_cell(cell: Sequence[int]) -> Cell:
    if len(cell) != 2:
        raise ValueError("cell must contain exactly two values: (row, col)")
    return int(cell[0]), int(cell[1])


def _nearest_int(value: float) -> int:
    return int(np.floor(float(value) + 0.5))


def is_in_bounds(cell: Sequence[int], map_shape: Union[Sequence[int], np.ndarray]) -> bool:
    row, col = _normalize_cell(cell)
    height, width = _shape_tuple(map_shape)
    return 0 <= row < height and 0 <= col < width


def grid_to_world(
    cell: Sequence[int],
    config: Optional[CoordinateAdapterConfig] = None,
) -> np.ndarray:
    cfg = _resolve_config(config)
    row, col = _normalize_cell(cell)
    origin_x, origin_y = cfg.origin_world_xy
    return np.array(
        [
            float(origin_x) + float(col) * float(cfg.cell_size_m),
            float(origin_y) - float(row) * float(cfg.cell_size_m),
            float(cfg.water_surface_z),
        ],
        dtype=float,
    )


def world_to_grid(
    world_xy: Sequence[float],
    config: Optional[CoordinateAdapterConfig] = None,
    map_shape: Optional[Union[Sequence[int], np.ndarray]] = None,
    clamp: bool = False,
) -> Cell:
    if len(world_xy) < 2:
        raise ValueError("world_xy must contain at least x and y")

    cfg = _resolve_config(config)
    origin_x, origin_y = cfg.origin_world_xy
    x, y = float(world_xy[0]), float(world_xy[1])
    col = _nearest_int((x - float(origin_x)) / float(cfg.cell_size_m))
    row = _nearest_int((float(origin_y) - y) / float(cfg.cell_size_m))

    if map_shape is None:
        return row, col

    height, width = _shape_tuple(map_shape)
    if clamp:
        row = min(max(row, 0), height - 1)
        col = min(max(col, 0), width - 1)
        return row, col

    if not is_in_bounds((row, col), (height, width)):
        raise ValueError(f"world position maps outside grid bounds: {(row, col)}")
    return row, col


def grid_path_to_world(
    path: Sequence[Sequence[int]],
    config: Optional[CoordinateAdapterConfig] = None,
) -> np.ndarray:
    if len(path) == 0:
        return np.empty((0, 3), dtype=float)
    return np.vstack([grid_to_world(cell, config=config) for cell in path]).astype(float)


def _world_to_fractional_grid(
    world_xy: Sequence[float],
    config: CoordinateAdapterConfig,
) -> Tuple[float, float]:
    origin_x, origin_y = config.origin_world_xy
    x, y = float(world_xy[0]), float(world_xy[1])
    col_f = (x - float(origin_x)) / float(config.cell_size_m)
    row_f = (float(origin_y) - y) / float(config.cell_size_m)
    return row_f, col_f


def project_world_to_nearest_free_cell(
    world_xy: Sequence[float],
    nav_map_prior: np.ndarray,
    config: Optional[CoordinateAdapterConfig] = None,
) -> Cell:
    if len(world_xy) < 2:
        raise ValueError("world_xy must contain at least x and y")

    cfg = _resolve_config(config)
    nav_map = np.asarray(nav_map_prior)
    if nav_map.ndim != 2:
        raise ValueError("nav_map_prior must be a 2D occupancy grid")

    free_cells = np.argwhere(nav_map == FREE)
    if free_cells.size == 0:
        raise ValueError("nav_map_prior contains no free cells")

    row_f, col_f = _world_to_fractional_grid(world_xy, cfg)
    deltas = free_cells.astype(float) - np.array([row_f, col_f], dtype=float)
    nearest_index = int(np.argmin(np.einsum("ij,ij->i", deltas, deltas)))
    nearest = free_cells[nearest_index]
    return int(nearest[0]), int(nearest[1])
