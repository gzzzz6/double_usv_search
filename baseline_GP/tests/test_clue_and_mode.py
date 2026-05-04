from __future__ import annotations

import numpy as np

from baseline_GP.core_clue_field import build_clue_field_map, make_target_induced_clue_field, sample_clue_field
from baseline_GP.core_gp_measurement import world_to_grid
from baseline_GP.core_map import FREE, create_open_water_world
from baseline_GP.core_mode_switch import REACQUIRE_MODE, SEARCH_MODE, TwoStageModeSwitcher


def test_clue_hotspot_moves_with_target() -> None:
    true_map = create_open_water_world(h=16, w=16)
    field_a = make_target_induced_clue_field(true_map, np.asarray([[4, 4]], dtype=int), clue_sigma_cells=2.0)
    field_b = make_target_induced_clue_field(true_map, np.asarray([[10, 10]], dtype=int), clue_sigma_cells=2.0)
    map_a = build_clue_field_map(field_a, true_map)
    map_b = build_clue_field_map(field_b, true_map)
    peak_a = tuple(int(v) for v in np.unravel_index(int(np.argmax(map_a)), map_a.shape))
    peak_b = tuple(int(v) for v in np.unravel_index(int(np.argmax(map_b)), map_b.shape))
    assert peak_a == (4, 4)
    assert peak_b == (10, 10)


def test_clue_sampling_stays_local_to_sensor_footprint() -> None:
    true_map = create_open_water_world(h=16, w=16)
    field_fn = make_target_induced_clue_field(true_map, np.asarray([[8, 8]], dtype=int), clue_sigma_cells=2.0)
    rng = np.random.default_rng(0)
    X_local, y_local = sample_clue_field(
        field_fn,
        robot_pos=(4, 4),
        sensor_range=2,
        rng=rng,
        noise_std=0.0,
        resolution=1.0,
        map_shape=true_map.shape,
        n_samples=None,
    )
    assert len(X_local) == len(y_local)
    assert len(X_local) > 0
    sampled_cells = [world_to_grid(xy, resolution=1.0) for xy in X_local]
    for cell in sampled_cells:
        assert true_map[cell] == FREE
        assert (cell[0] - 4) ** 2 + (cell[1] - 4) ** 2 <= 4


def test_two_stage_mode_switcher_enters_and_exits() -> None:
    switcher = TwoStageModeSwitcher(
        peak_ratio_enter=4.0,
        peak_ratio_exit=2.5,
        enter_stable_steps=3,
        exit_stable_steps=2,
        reacquire_budget=6,
        m_enter=0.5,
    )
    for _ in range(2):
        decision = switcher.update(
            peak_ratio=4.5,
            peaks_aligned=True,
            local_intensity_mass=0.8,
            detected_count_this_step=0,
        )
        assert decision.mode == SEARCH_MODE
        assert not decision.switched

    decision = switcher.update(
        peak_ratio=4.5,
        peaks_aligned=True,
        local_intensity_mass=0.8,
        detected_count_this_step=0,
    )
    assert decision.mode == REACQUIRE_MODE
    assert decision.switched

    decision = switcher.update(
        peak_ratio=4.5,
        peaks_aligned=True,
        local_intensity_mass=0.8,
        detected_count_this_step=1,
    )
    assert decision.mode == SEARCH_MODE
    assert decision.switched
