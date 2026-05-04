"""
Intensity-field state for dynamic multi-target marine suspicious search.
"""

from __future__ import annotations

import math

import numpy as np

try:
    from .core_map import OCCUPIED, sensor_cells
except ImportError:
    from core_map import OCCUPIED, sensor_cells


def init_intensity_map(
    known_map: np.ndarray,
    total_mass: float,
) -> np.ndarray:
    """Initialize a uniform expected-target-count field over cells not known occupied."""
    total_mass = max(float(total_mass), 0.0)
    intensity = np.zeros(known_map.shape, dtype=float)
    admissible_mask = known_map != OCCUPIED
    admissible_count = int(np.count_nonzero(admissible_mask))
    if admissible_count == 0 or total_mass <= 0.0:
        return intensity
    intensity[admissible_mask] = total_mass / float(admissible_count)
    return intensity


def _admissible_intensity_seed(
    shape: tuple[int, int],
    total_mass: float,
    *,
    known_map: np.ndarray | None = None,
    excluded_mask: np.ndarray | None = None,
) -> np.ndarray:
    seeded = np.zeros(shape, dtype=float)
    total_mass = max(float(total_mass), 0.0)
    if total_mass <= 0.0:
        return seeded
    admissible_mask = np.ones(shape, dtype=bool)
    if known_map is not None:
        admissible_mask &= np.asarray(known_map) != OCCUPIED
    if excluded_mask is not None:
        admissible_mask &= ~np.asarray(excluded_mask, dtype=bool)
    admissible_count = int(np.count_nonzero(admissible_mask))
    if admissible_count <= 0:
        return seeded
    seeded[admissible_mask] = total_mass / float(admissible_count)
    return seeded


def renormalize_intensity_total_mass(
    intensity_map: np.ndarray,
    total_mass: float,
    *,
    known_map: np.ndarray | None = None,
    excluded_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Rescale an intensity map to a target total mass over admissible cells."""
    target_mass = max(float(total_mass), 0.0)
    updated = np.array(intensity_map, dtype=float, copy=True)
    updated[updated < 0.0] = 0.0
    if known_map is not None:
        updated[np.asarray(known_map) == OCCUPIED] = 0.0
    if excluded_mask is not None:
        updated[np.asarray(excluded_mask, dtype=bool)] = 0.0
    current_mass = float(np.sum(updated))
    if target_mass <= 0.0:
        updated[:] = 0.0
        return updated
    if current_mass <= 1e-12:
        return _admissible_intensity_seed(
            updated.shape,
            target_mass,
            known_map=known_map,
            excluded_mask=excluded_mask,
        )
    updated *= target_mass / current_mass
    updated[updated < 0.0] = 0.0
    return updated


def _valid_random_walk_neighbors(
    cell: tuple[int, int],
    known_map: np.ndarray,
) -> list[tuple[int, int]]:
    x, y = cell
    h, w = known_map.shape
    candidates = [(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
    valid = []
    for nx, ny in candidates:
        if 0 <= nx < h and 0 <= ny < w and known_map[nx, ny] != OCCUPIED:
            valid.append((nx, ny))
    return valid


def apply_known_occupancy_constraints(
    intensity_map: np.ndarray,
    known_map: np.ndarray,
    preserve_mass: bool = True,
) -> np.ndarray:
    """Zero out known-occupied cells and optionally renormalize remaining mass."""
    updated = np.array(intensity_map, dtype=float, copy=True)
    updated[updated < 0.0] = 0.0
    mass_before = float(np.sum(updated))
    updated[known_map == OCCUPIED] = 0.0
    updated[updated < 0.0] = 0.0
    if not preserve_mass:
        return updated
    remaining_mass = float(np.sum(updated))
    if mass_before <= 0.0 or remaining_mass <= 0.0:
        return updated
    if math.isclose(mass_before, remaining_mass, rel_tol=1e-12, abs_tol=1e-12):
        return updated
    updated *= mass_before / remaining_mass
    updated[updated < 0.0] = 0.0
    return updated


def predict_intensity(
    intensity_map: np.ndarray,
    known_map: np.ndarray,
    motion_mode: str = "static",
) -> np.ndarray:
    """Predict one step forward while preserving total mass."""
    if motion_mode not in {"static", "random_walk"}:
        raise ValueError(f"Unsupported motion_mode='{motion_mode}'")

    current = apply_known_occupancy_constraints(
        intensity_map,
        known_map,
        preserve_mass=True,
    )

    if motion_mode == "static":
        return current

    predicted = np.zeros_like(current)
    h, w = current.shape
    for x in range(h):
        for y in range(w):
            mass = float(current[x, y])
            if mass <= 0.0 or known_map[x, y] == OCCUPIED:
                continue
            valid_neighbors = _valid_random_walk_neighbors((x, y), known_map)
            if not valid_neighbors:
                predicted[x, y] += mass
                continue
            share = mass / float(len(valid_neighbors))
            for nx, ny in valid_neighbors:
                predicted[nx, ny] += share

    return apply_known_occupancy_constraints(
        predicted,
        known_map,
        preserve_mass=True,
    )


def detection_probability_at_offset(
    dx: int,
    dy: int,
    sensor_range_cells: int,
) -> float:
    dist = float(math.hypot(dx, dy))
    if dist > sensor_range_cells:
        return 0.0
    if dist == 0.0:
        return 1.0
    return float(math.exp(-dist / float(sensor_range_cells)))


def miss_update_intensity(
    predicted_intensity: np.ndarray,
    robot_pos: tuple[int, int],
    sensor_range_cells: int,
    known_map: np.ndarray | None = None,
    preserve_total_mass: bool = True,
    target_total_mass: float | None = None,
) -> np.ndarray:
    """Apply the miss update and optionally preserve the remaining target mass."""
    updated = np.array(predicted_intensity, dtype=float, copy=True)
    mass_before = float(np.sum(np.clip(updated, 0.0, None)))
    rx, ry = robot_pos
    for x, y in sensor_cells(robot_pos, updated.shape, sensor_range_cells):
        if known_map is not None and known_map[x, y] == OCCUPIED:
            continue
        p_detect = detection_probability_at_offset(x - rx, y - ry, sensor_range_cells)
        updated[x, y] *= (1.0 - p_detect)
    updated[updated < 0.0] = 0.0
    if known_map is not None:
        updated = apply_known_occupancy_constraints(updated, known_map, preserve_mass=False)
    if preserve_total_mass:
        resolved_total_mass = mass_before if target_total_mass is None else float(target_total_mass)
        updated = renormalize_intensity_total_mass(
            updated,
            resolved_total_mass,
            known_map=known_map,
        )
    return updated


def hit_update_intensity(
    predicted_intensity: np.ndarray,
    hit_positions: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    hit_count: int,
    r_hit: int = 1,
    known_map: np.ndarray | None = None,
    target_total_mass: float | None = None,
) -> np.ndarray:
    """Apply the frozen hit-update rule from the implementation spec."""
    updated = np.array(predicted_intensity, dtype=float, copy=True)
    if known_map is not None:
        updated = apply_known_occupancy_constraints(updated, known_map, preserve_mass=True)
    mass_before = float(np.sum(updated))
    excluded_mask = np.zeros_like(updated, dtype=bool)

    for hx, hy in hit_positions:
        for x in range(max(0, hx - r_hit), min(updated.shape[0], hx + r_hit + 1)):
            for y in range(max(0, hy - r_hit), min(updated.shape[1], hy + r_hit + 1)):
                if (x - hx) ** 2 + (y - hy) ** 2 <= r_hit * r_hit:
                    updated[x, y] = 0.0
                    excluded_mask[x, y] = True

    updated[updated < 0.0] = 0.0
    resolved_target_mass = (
        max(mass_before - float(hit_count), 0.0)
        if target_total_mass is None
        else max(float(target_total_mass), 0.0)
    )
    return renormalize_intensity_total_mass(
        updated,
        resolved_target_mass,
        known_map=known_map,
        excluded_mask=excluded_mask,
    )


def remaining_intensity_mass(intensity_map: np.ndarray) -> float:
    return float(np.sum(np.clip(intensity_map, 0.0, None)))


def peak_intensity_ratio(
    intensity_map: np.ndarray,
    known_map: np.ndarray,
) -> float:
    active_values = intensity_map[known_map != OCCUPIED]
    if active_values.size == 0:
        return 0.0
    mean_value = float(np.mean(active_values))
    return float(np.max(active_values)) / (mean_value + 1e-9)


def peak_intensity_cell(
    intensity_map: np.ndarray,
    known_map: np.ndarray,
) -> tuple[int, int] | None:
    active_mask = known_map != OCCUPIED
    if not np.any(active_mask):
        return None
    masked = np.where(active_mask, intensity_map, -np.inf)
    flat_idx = int(np.argmax(masked))
    if not np.isfinite(masked.reshape(-1)[flat_idx]):
        return None
    return tuple(int(v) for v in np.unravel_index(flat_idx, intensity_map.shape))


def local_intensity_mass(
    intensity_map: np.ndarray,
    center: tuple[int, int] | None,
    radius: int,
    known_map: np.ndarray | None = None,
) -> float:
    if center is None:
        return 0.0
    cx, cy = center
    total = 0.0
    h, w = intensity_map.shape
    for x in range(max(0, cx - radius), min(h, cx + radius + 1)):
        for y in range(max(0, cy - radius), min(w, cy + radius + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 > radius * radius:
                continue
            if known_map is not None and known_map[x, y] == OCCUPIED:
                continue
            total += float(intensity_map[x, y])
    return total
