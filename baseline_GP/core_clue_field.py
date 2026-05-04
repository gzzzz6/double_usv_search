"""
Hidden clue-field generation for GP-assisted target search.
"""

from __future__ import annotations

import numpy as np

try:
    from .core_gp_measurement import build_true_field_map, sample_suspicion_field
    from .core_map import FREE
except ImportError:
    from core_gp_measurement import build_true_field_map, sample_suspicion_field
    from core_map import FREE


def make_target_induced_clue_field(
    true_map: np.ndarray,
    target_positions: np.ndarray,
    clue_sigma_cells: float = 6.0,
    clue_amplitude: float = 1.0,
):
    """Build a hidden clue field induced by the discrete target set."""

    targets = np.asarray(target_positions, dtype=float)

    def field_fn(r: int, c: int) -> float:
        if true_map[r, c] != FREE:
            return 0.0
        val = 0.0
        for tr, tc in targets:
            dist2 = (r - tr) ** 2 + (c - tc) ** 2
            val += clue_amplitude * np.exp(-dist2 / (2.0 * clue_sigma_cells**2))
        return float(val)

    return field_fn


def build_clue_field_map(
    field_fn,
    true_map: np.ndarray,
) -> np.ndarray:
    """Expand a hidden clue field callable into a full map for debugging only."""
    free_mask = true_map == FREE
    return build_true_field_map(field_fn, true_map, free_mask=free_mask)


def sample_clue_field(
    field_fn,
    robot_pos: tuple[int, int],
    sensor_range: float,
    rng: np.random.Generator,
    noise_std: float = 0.05,
    resolution: float = 1.0,
    origin: tuple[float, float] = (0.0, 0.0),
    map_shape: tuple[int, int] | None = None,
    n_samples: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample noisy clue observations in the robot sensor footprint."""
    return sample_suspicion_field(
        field_fn,
        robot_pos,
        sensor_range,
        rng,
        n_samples=n_samples,
        noise_std=noise_std,
        resolution=resolution,
        origin=origin,
        map_shape=map_shape,
    )
