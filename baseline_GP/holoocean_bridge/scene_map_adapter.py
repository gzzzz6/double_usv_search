"""Adapter for creating and managing known static maps derived from HoloOcean scenes."""

from __future__ import annotations

import json
from typing import Tuple, Dict, Any, List

import numpy as np

# Local bridge constants to decouple from core_map module
FREE = 0
OCCUPIED = 1

from baseline_GP.holoocean_bridge.coordinate_adapter import CoordinateAdapterConfig, world_to_grid


def load_scene_map_spec(path: str) -> Dict[str, Any]:
    """Load the JSON specification for a HoloOcean scene map.

    Args:
        path: Path to the JSON specification file.

    Returns:
        Dict[str, Any]: The parsed map specification.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def scene_map_config_from_spec(spec: Dict[str, Any]) -> CoordinateAdapterConfig:
    """Create a CoordinateAdapterConfig from a map specification.

    Args:
        spec: The map specification dictionary.

    Returns:
        CoordinateAdapterConfig: Configured coordinate adapter settings.
    """
    return CoordinateAdapterConfig(
        cell_size_m=float(spec["cell_size_m"]),
        origin_world_xy=tuple(float(v) for v in spec["origin_world_xy"]),
        water_surface_z=float(spec["water_surface_z"]),
    )


def build_scene_occupancy_grid(spec: Dict[str, Any]) -> np.ndarray:
    """Construct a 2D occupancy grid according to the map specification.

    Args:
        spec: The map specification dictionary.

    Returns:
        np.ndarray: The 2D occupancy grid of shape (height, width).
    """
    height = int(spec["height"])
    width = int(spec["width"])
    grid = np.full((height, width), FREE, dtype=np.int32)

    # 1. Fill boundaries if requested
    if spec.get("boundary_occupied", False):
        grid[0, :] = OCCUPIED
        grid[-1, :] = OCCUPIED
        grid[:, 0] = OCCUPIED
        grid[:, -1] = OCCUPIED

    # 2. Fill occupied rectangles in world coordinates
    occupied_rects = spec.get("occupied_rects_world", [])
    if occupied_rects:
        config = scene_map_config_from_spec(spec)
        map_shape = (height, width)
        for rect in occupied_rects:
            xmin = float(rect["xmin"])
            xmax = float(rect["xmax"])
            ymin = float(rect["ymin"])
            ymax = float(rect["ymax"])

            # Map the rectangle's corners to grid cell coordinates with clamping
            r_from_ymax, c_from_xmin = world_to_grid((xmin, ymax), config, map_shape, clamp=True)
            r_from_ymin, c_from_xmax = world_to_grid((xmax, ymin), config, map_shape, clamp=True)

            r_start = min(r_from_ymax, r_from_ymin)
            r_end = max(r_from_ymax, r_from_ymin)
            c_start = min(c_from_xmin, c_from_xmax)
            c_end = max(c_from_xmin, c_from_xmax)

            grid[r_start : r_end + 1, c_start : c_end + 1] = OCCUPIED

    return grid


def save_scene_map_npz(output_path: str, nav_map_prior: np.ndarray, spec: Dict[str, Any]) -> None:
    """Save the occupancy grid and its corresponding specification into an NPZ file.

    Args:
        output_path: The file path to save the NPZ data.
        nav_map_prior: The 2D occupancy grid.
        spec: The map specification dictionary.
    """
    spec_json = json.dumps(spec)
    np.savez_compressed(output_path, nav_map_prior=nav_map_prior, spec_json=spec_json)


def load_scene_map_npz(path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Load an occupancy grid and its specification from an NPZ file.

    Args:
        path: Path to the NPZ file.

    Returns:
        Tuple[np.ndarray, Dict[str, Any]]: The loaded (nav_map_prior, spec).
    """
    data = np.load(path, allow_pickle=True)
    nav_map_prior = data["nav_map_prior"]
    spec_json = str(data["spec_json"])
    spec = json.loads(spec_json)
    return nav_map_prior, spec


def scene_map_world_bounds(spec: Dict[str, Any]) -> Dict[str, float]:
    """Calculate the world coordinate boundaries of the scene map grid.

    Args:
        spec: The map specification dictionary.

    Returns:
        Dict[str, float]: A dictionary with keys 'xmin', 'xmax', 'ymin', 'ymax'.
    """
    origin_x, origin_y = spec["origin_world_xy"]
    cell_size = float(spec["cell_size_m"])
    height = int(spec["height"])
    width = int(spec["width"])

    xmin = float(origin_x)
    xmax = float(origin_x + (width - 1) * cell_size)
    ymin = float(origin_y - (height - 1) * cell_size)
    ymax = float(origin_y)

    return {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax}


def validate_scene_map(nav_map_prior: np.ndarray, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that a generated occupancy grid complies with its specification.

    Args:
        nav_map_prior: The 2D occupancy grid to validate.
        spec: The map specification dictionary.

    Returns:
        Dict[str, Any]: A report containing 'is_valid' and a list of 'errors' if any.
    """
    errors = []
    h, w = nav_map_prior.shape
    expected_h = int(spec["height"])
    expected_w = int(spec["width"])

    if h != expected_h or w != expected_w:
        errors.append(f"Shape mismatch: expected ({expected_h}, {expected_w}), got ({h}, {w})")

    if spec.get("boundary_occupied", False):
        if not np.all(nav_map_prior[0, :] == OCCUPIED):
            errors.append("First row is not fully occupied")
        if not np.all(nav_map_prior[-1, :] == OCCUPIED):
            errors.append("Last row is not fully occupied")
        if not np.all(nav_map_prior[:, 0] == OCCUPIED):
            errors.append("First column is not fully occupied")
        if not np.all(nav_map_prior[:, -1] == OCCUPIED):
            errors.append("Last column is not fully occupied")

    # If occupied_rects_world is provided, we can verify those cells are occupied
    occupied_rects = spec.get("occupied_rects_world", [])
    if occupied_rects:
        config = scene_map_config_from_spec(spec)
        for idx, rect in enumerate(occupied_rects):
            xmin = float(rect["xmin"])
            xmax = float(rect["xmax"])
            ymin = float(rect["ymin"])
            ymax = float(rect["ymax"])

            r_from_ymax, c_from_xmin = world_to_grid((xmin, ymax), config, (h, w), clamp=True)
            r_from_ymin, c_from_xmax = world_to_grid((xmax, ymin), config, (h, w), clamp=True)

            r_start = min(r_from_ymax, r_from_ymin)
            r_end = max(r_from_ymax, r_from_ymin)
            c_start = min(c_from_xmin, c_from_xmax)
            c_end = max(c_from_xmin, c_from_xmax)

            subgrid = nav_map_prior[r_start : r_end + 1, c_start : c_end + 1]
            if not np.all(subgrid == OCCUPIED):
                errors.append(f"Occupied rect index {idx} contains free cells in grid")

    is_valid = len(errors) == 0
    return {
        "is_valid": is_valid,
        "errors": errors,
    }
