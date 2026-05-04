"""
Staleness state for single-USV marine suspicious target search.
"""

from __future__ import annotations

import numpy as np

try:
    from .core_map import FREE, OCCUPIED, UNKNOWN, sensor_cells
except ImportError:
    from core_map import FREE, OCCUPIED, UNKNOWN, sensor_cells


UNSEEN_STEP = -1


def init_last_seen(map_template: np.ndarray) -> np.ndarray:
    """Initialize the per-cell last-seen step map."""
    return np.full(map_template.shape, UNSEEN_STEP, dtype=int)


def refresh_last_seen(
    last_seen_step: np.ndarray,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    sensor_range: int,
    step: int,
) -> None:
    """Refresh known-FREE cells inside the current geometric footprint."""
    for x, y in sensor_cells(robot_pos, known_map.shape, sensor_range):
        if known_map[x, y] != FREE:
            continue
        last_seen_step[x, y] = int(step)


def build_staleness_map(
    last_seen_step: np.ndarray,
    known_map: np.ndarray,
    current_step: int,
    tau_stale: int = 12,
) -> np.ndarray:
    """Convert the integer last-seen state into a [0, 1] observation-staleness map.

    This helper still supports the legacy unknown-map baseline, but it also works
    for the known-static-map baseline where `known_map` contains only FREE/OCCUPIED
    cells and staleness is interpreted purely as observation recency over known
    navigable space.
    """
    if tau_stale <= 0:
        raise ValueError("tau_stale must be positive")

    staleness = np.ones(known_map.shape, dtype=float)
    staleness[known_map == OCCUPIED] = 0.0

    known_free_mask = known_map == FREE
    seen_free_mask = known_free_mask & (last_seen_step >= 0)
    if np.any(seen_free_mask):
        delta = (
            float(current_step) - last_seen_step[seen_free_mask].astype(float)
        ) / float(tau_stale)
        staleness[seen_free_mask] = np.clip(delta, 0.0, 1.0)
    # UNKNOWN and known-FREE-but-never-seen cells stay at 1.0.
    return staleness


def online_known_free_ratio(known_map: np.ndarray) -> float:
    """Fraction of the grid currently confirmed as FREE."""
    total_cells = int(known_map.size)
    if total_cells == 0:
        return 0.0
    known_free = int(np.count_nonzero(known_map == FREE))
    return float(known_free) / float(total_cells)


def eval_free_coverage_rate(last_seen_step: np.ndarray, true_map: np.ndarray) -> float:
    """Offline evaluation metric: fraction of true FREE cells observed at least once."""
    free_mask = true_map == FREE
    total_free = int(np.count_nonzero(free_mask))
    if total_free == 0:
        return 0.0
    seen_free = int(np.count_nonzero(free_mask & (last_seen_step >= 0)))
    return float(seen_free) / float(total_free)


def known_free_observation_ratio(
    last_seen_step: np.ndarray,
    nav_map_prior: np.ndarray,
) -> float:
    """Fraction of known-FREE cells observed at least once under the static prior."""
    known_free_mask = nav_map_prior == FREE
    total_free = int(np.count_nonzero(known_free_mask))
    if total_free == 0:
        return 0.0
    observed_free = int(np.count_nonzero(known_free_mask & (last_seen_step >= 0)))
    return float(observed_free) / float(total_free)
