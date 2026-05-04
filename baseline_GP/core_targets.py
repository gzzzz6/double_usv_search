"""
Utilities for multi-target generation, motion, and detection.
"""

from __future__ import annotations

import math

import numpy as np

try:
    from .core_map import FREE
except ImportError:
    from core_map import FREE


class PlacementInfeasibleError(ValueError):
    """Raised when hard target-placement constraints cannot be satisfied."""


def _euclidean_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return float(math.hypot(a[0] - b[0], a[1] - b[1]))


def _fill_targets(
    selected: list[tuple[int, int]],
    free_cells: list[tuple[int, int]],
    permuted: np.ndarray,
    n_targets: int,
    valid_fn,
) -> None:
    for idx in permuted:
        cell = free_cells[int(idx)]
        if cell in selected:
            continue
        if not valid_fn(cell, selected):
            continue
        selected.append(cell)
        if len(selected) >= n_targets:
            return


def _actual_min_target_separation_cells(target_positions: np.ndarray) -> float | None:
    if len(target_positions) < 2:
        return None

    min_distance = float("inf")
    for idx in range(len(target_positions)):
        for jdx in range(idx + 1, len(target_positions)):
            dist = _euclidean_distance(
                (int(target_positions[idx, 0]), int(target_positions[idx, 1])),
                (int(target_positions[jdx, 0]), int(target_positions[jdx, 1])),
            )
            min_distance = min(min_distance, dist)
    return min_distance if math.isfinite(min_distance) else None


def _actual_min_start_distance_cells(
    target_positions: np.ndarray,
    start_pos: tuple[int, int] | list[tuple[int, int]] | np.ndarray | None,
) -> float | None:
    start_positions = _normalize_start_positions(start_pos)
    if not start_positions or len(target_positions) == 0:
        return None
    return min(
        _euclidean_distance((int(pos[0]), int(pos[1])), launch_pos)
        for pos in target_positions
        for launch_pos in start_positions
    )


def _normalize_start_positions(
    start_pos: tuple[int, int] | list[tuple[int, int]] | np.ndarray | None,
) -> list[tuple[int, int]]:
    if start_pos is None:
        return []
    if isinstance(start_pos, np.ndarray):
        start_array = np.asarray(start_pos, dtype=int)
        if start_array.ndim == 1:
            if start_array.shape[0] != 2:
                raise ValueError("start_pos array must have shape (2,) or (N, 2)")
            return [tuple(int(v) for v in start_array)]
        if start_array.ndim == 2 and start_array.shape[1] == 2:
            return [tuple(int(v) for v in row) for row in start_array]
        raise ValueError("start_pos array must have shape (2,) or (N, 2)")

    try:
        if len(start_pos) == 2 and all(np.isscalar(v) for v in start_pos):
            return [tuple(int(v) for v in start_pos)]
    except TypeError:
        pass

    return [tuple(int(v) for v in pos) for pos in start_pos]


def generate_static_targets(
    true_map: np.ndarray,
    n_targets: int,
    rng: np.random.Generator,
    start_pos: tuple[int, int] | list[tuple[int, int]] | np.ndarray | None = None,
    min_target_separation_cells: float = 6.0,
    min_start_distance_cells: float = 8.0,
    constraint_mode: str = "hard",
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Sample static targets on FREE cells with explicit placement semantics.

    Returns
    -------
    target_positions : np.ndarray shape (N, 2)
    target_ids       : np.ndarray shape (N,)
    placement_info   : dict with constraint_mode / placement_status / actual minima
    """
    if constraint_mode not in {"hard", "soft_relax"}:
        raise ValueError(f"Unsupported constraint_mode='{constraint_mode}'")

    free_cells = [tuple(cell) for cell in np.argwhere(true_map == FREE)]
    if len(free_cells) < n_targets:
        raise PlacementInfeasibleError("Not enough FREE cells to place all targets.")

    def valid_against_selected(
        cell: tuple[int, int],
        selected: list[tuple[int, int]],
    ) -> bool:
        return all(
            _euclidean_distance(cell, other) >= min_target_separation_cells
            for other in selected
        )

    start_positions = _normalize_start_positions(start_pos)

    def valid_against_start(cell: tuple[int, int]) -> bool:
        if not start_positions:
            return True
        return all(
            _euclidean_distance(cell, launch_pos) >= min_start_distance_cells
            for launch_pos in start_positions
        )

    selected: list[tuple[int, int]] = []
    permuted = rng.permutation(len(free_cells))

    _fill_targets(
        selected,
        free_cells,
        permuted,
        n_targets,
        valid_fn=lambda cell, chosen: (
            valid_against_start(cell) and valid_against_selected(cell, chosen)
        ),
    )

    placement_status = "satisfied"
    if len(selected) < n_targets:
        if constraint_mode == "hard":
            raise PlacementInfeasibleError(
                "Failed to place all targets under hard spacing constraints."
            )

        _fill_targets(
            selected,
            free_cells,
            permuted,
            n_targets,
            valid_fn=lambda cell, _chosen: valid_against_start(cell),
        )
        placement_status = "relaxed_once"

    if len(selected) < n_targets:
        _fill_targets(
            selected,
            free_cells,
            permuted,
            n_targets,
            valid_fn=lambda cell, _chosen: True,
        )
        placement_status = "relaxed_fully"

    if len(selected) < n_targets:
        raise PlacementInfeasibleError(
            "Failed to place all targets even after fully relaxing constraints."
        )

    target_positions = np.asarray(selected[:n_targets], dtype=int)
    target_ids = np.arange(n_targets, dtype=int)
    placement_info = {
        "constraint_mode": constraint_mode,
        "placement_status": placement_status,
        "actual_min_target_separation_cells": _actual_min_target_separation_cells(target_positions),
        "actual_min_start_distance_cells": _actual_min_start_distance_cells(
            target_positions,
            start_pos,
        ),
    }
    return target_positions, target_ids, placement_info


def sample_targets(*args, **kwargs):
    """Compatibility wrapper for the unified target-manager interface."""
    return generate_static_targets(*args, **kwargs)


def step_targets(
    target_positions: np.ndarray,
    motion_mode: str,
    occ_grid: np.ndarray,
    rng: np.random.Generator,
    found_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Advance unfound targets by one step under the requested motion model."""
    if motion_mode not in {"static", "random_walk"}:
        raise ValueError(f"Unsupported motion_mode='{motion_mode}'")

    updated = np.array(target_positions, dtype=int, copy=True)
    if motion_mode == "static" or updated.size == 0:
        return updated

    h, w = occ_grid.shape
    move_set = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
    for idx, target in enumerate(updated):
        if found_mask is not None and bool(found_mask[idx]):
            continue

        x, y = int(target[0]), int(target[1])
        valid_moves: list[tuple[int, int]] = []
        for dx, dy in move_set:
            nx, ny = x + dx, y + dy
            if 0 <= nx < h and 0 <= ny < w and occ_grid[nx, ny] == FREE:
                valid_moves.append((nx, ny))
        if not valid_moves:
            continue
        chosen = valid_moves[int(rng.integers(len(valid_moves)))]
        updated[idx] = np.asarray(chosen, dtype=int)
    return updated


def detection_probability(
    robot_pos: tuple[int, int],
    target_pos: tuple[int, int],
    sensor_range_cells: int,
) -> float:
    """Distance-based detection probability, reusing the old single-target idea."""
    dist = _euclidean_distance(robot_pos, target_pos)
    if dist > sensor_range_cells:
        return 0.0
    return float(np.exp(-dist / sensor_range_cells)) if dist > 0 else 1.0


def detect_targets(
    robot_pos: tuple[int, int],
    target_positions: np.ndarray,
    found_mask: np.ndarray,
    sensor_range_cells: int,
    detection_rng: np.random.Generator,
) -> np.ndarray:
    """Try to detect all unfound targets within the sensor footprint."""
    detected_mask = np.zeros_like(found_mask, dtype=bool)
    for idx, target in enumerate(target_positions):
        if found_mask[idx]:
            continue
        p_detect = detection_probability(
            robot_pos,
            (int(target[0]), int(target[1])),
            sensor_range_cells,
        )
        if p_detect <= 0.0:
            continue
        if detection_rng.random() < p_detect:
            detected_mask[idx] = True
    return detected_mask


def update_found_mask(
    found_mask: np.ndarray,
    detected_mask: np.ndarray,
    find_times: list[int | None],
    step: int,
) -> list[int]:
    """Latch newly detected targets and record their first detection step."""
    newly_found = detected_mask & ~found_mask
    new_indices = np.flatnonzero(newly_found).tolist()
    if not new_indices:
        return []

    found_mask[newly_found] = True
    for idx in new_indices:
        if find_times[idx] is None:
            find_times[idx] = int(step)
    return new_indices


def remaining_targets(
    target_positions: np.ndarray,
    found_mask: np.ndarray,
) -> np.ndarray:
    """Return the positions of currently unfound targets."""
    return target_positions[~found_mask]


def remove_found_targets(
    target_positions: np.ndarray,
    found_mask: np.ndarray,
) -> np.ndarray:
    """Return only the currently unfound targets."""
    return remaining_targets(target_positions, found_mask)


def summarize_detection_times(find_times: list[int | None]) -> dict:
    """Summarize multi-target detection timing metrics."""
    found_steps = [step for step in find_times if step is not None]
    found_count = len(found_steps)
    total_targets = len(find_times)
    miss_count = total_targets - found_count
    return {
        "found_count": found_count,
        "miss_count": miss_count,
        "time_to_first_detection": min(found_steps) if found_steps else None,
        "time_to_all_found": max(found_steps) if miss_count == 0 and found_steps else None,
    }
