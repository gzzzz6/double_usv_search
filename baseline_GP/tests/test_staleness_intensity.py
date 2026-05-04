from __future__ import annotations

import numpy as np

from baseline_GP.core_intensity import (
    apply_known_occupancy_constraints,
    hit_update_intensity,
    init_intensity_map,
    miss_update_intensity,
    predict_intensity,
    remaining_intensity_mass,
)
from baseline_GP.core_map import FREE, OCCUPIED, UNKNOWN, create_open_water_world
from baseline_GP.core_staleness import (
    build_staleness_map,
    eval_free_coverage_rate,
    init_last_seen,
    online_known_free_ratio,
    refresh_last_seen,
)


def test_staleness_updates_and_coverage_are_monotone() -> None:
    true_map = create_open_water_world(h=12, w=12)
    known_map = np.full_like(true_map, UNKNOWN)
    last_seen = init_last_seen(known_map)

    staleness_0 = build_staleness_map(last_seen, known_map, current_step=0, tau_stale=4)
    assert np.all(staleness_0 == 1.0)
    assert online_known_free_ratio(known_map) == 0.0
    assert eval_free_coverage_rate(last_seen, true_map) == 0.0

    known_map[5, 5] = FREE
    known_map[5, 6] = OCCUPIED
    refresh_last_seen(last_seen, known_map, robot_pos=(5, 5), sensor_range=2, step=0)
    staleness_after_seen = build_staleness_map(last_seen, known_map, current_step=0, tau_stale=4)
    assert staleness_after_seen[5, 5] == 0.0
    assert staleness_after_seen[5, 6] == 0.0
    covered_once = eval_free_coverage_rate(last_seen, true_map)
    assert covered_once > 0.0

    staleness_later = build_staleness_map(last_seen, known_map, current_step=3, tau_stale=4)
    assert staleness_later[5, 5] > staleness_after_seen[5, 5]
    assert staleness_later[5, 5] <= 1.0
    assert eval_free_coverage_rate(last_seen, true_map) == covered_once


def test_intensity_init_predict_miss_and_hit_obey_mass_semantics() -> None:
    known_map = np.full((12, 12), UNKNOWN, dtype=int)
    known_map[0, :] = OCCUPIED
    known_map[-1, :] = OCCUPIED
    known_map[:, 0] = OCCUPIED
    known_map[:, -1] = OCCUPIED
    known_map[6, 6] = OCCUPIED
    intensity = init_intensity_map(known_map, total_mass=3.0)
    active_mask = known_map != OCCUPIED
    assert np.isclose(remaining_intensity_mass(intensity), 3.0)
    assert np.all(intensity[~active_mask] == 0.0)

    predicted = predict_intensity(intensity, known_map, motion_mode="random_walk")
    assert np.isclose(remaining_intensity_mass(predicted), 3.0)
    assert float(np.min(predicted)) >= 0.0
    assert predicted[6, 6] == 0.0

    before_local = float(predicted[5, 5])
    missed = miss_update_intensity(
        predicted,
        robot_pos=(5, 5),
        sensor_range_cells=2,
        known_map=known_map,
    )
    assert np.isclose(
        remaining_intensity_mass(missed),
        remaining_intensity_mass(predicted),
    )
    assert missed[5, 5] < before_local

    hit = hit_update_intensity(
        predicted,
        hit_positions=[(5, 5)],
        hit_count=1,
        r_hit=1,
        known_map=known_map,
    )
    assert np.isclose(remaining_intensity_mass(hit), 2.0)
    assert hit[5, 5] == 0.0


def test_hit_update_respects_explicit_remaining_mass_after_low_mass_prior() -> None:
    known_map = np.full((9, 9), UNKNOWN, dtype=int)
    known_map[0, :] = OCCUPIED
    known_map[-1, :] = OCCUPIED
    known_map[:, 0] = OCCUPIED
    known_map[:, -1] = OCCUPIED
    predicted = np.zeros((9, 9), dtype=float)
    predicted[4, 4] = 0.35

    hit = hit_update_intensity(
        predicted,
        hit_positions=[(4, 4)],
        hit_count=1,
        r_hit=1,
        known_map=known_map,
        target_total_mass=1.0,
    )

    assert np.isclose(remaining_intensity_mass(hit), 1.0)
    assert hit[4, 4] == 0.0


def test_intensity_redistributes_mass_when_new_obstacle_becomes_known() -> None:
    known_map = np.full((10, 10), UNKNOWN, dtype=int)
    intensity = init_intensity_map(known_map, total_mass=2.0)
    mass_before = remaining_intensity_mass(intensity)
    known_map[4, 4] = OCCUPIED
    constrained = apply_known_occupancy_constraints(intensity, known_map, preserve_mass=True)
    assert constrained[4, 4] == 0.0
    assert np.isclose(remaining_intensity_mass(constrained), mass_before)
