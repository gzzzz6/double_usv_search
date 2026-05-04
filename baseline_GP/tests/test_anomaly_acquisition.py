from __future__ import annotations

import numpy as np

from baseline_GP.core_anomaly_acquisition import (
    build_conditional_anomaly_clue_map,
    build_knownmap_anomaly_acquisition_maps,
)
from baseline_GP.core_map import FREE, OCCUPIED
from baseline_GP.marine_knownmap_runtime import (
    _init_knownmap_state,
    run_episode_single_usv_search_knownmap,
)


def _normalize01_for_test(score_map: np.ndarray, free_mask: np.ndarray) -> np.ndarray:
    result = np.zeros_like(score_map, dtype=float)
    values = np.asarray(score_map, dtype=float)[free_mask]
    if values.size == 0:
        return result
    lower = float(np.min(values))
    upper = float(np.max(values))
    if upper <= lower + 1e-12:
        return result
    result[free_mask] = (np.asarray(score_map, dtype=float)[free_mask] - lower) / (upper - lower)
    return result


def test_knownmap_anomaly_acquisition_map_properties() -> None:
    nav_map_prior = np.asarray(
        [
            [FREE, FREE, FREE],
            [OCCUPIED, FREE, FREE],
        ],
        dtype=np.int8,
    )
    gp_mu_map = np.asarray(
        [
            [0.0, 1.0, 3.0],
            [0.0, 2.0, 0.5],
        ],
        dtype=float,
    )
    gp_var_map = np.asarray(
        [
            [0.25, 0.25, 0.25],
            [0.0, 1.00, 0.10],
        ],
        dtype=float,
    )
    gp_acq_map = gp_mu_map + 0.5 * np.sqrt(gp_var_map)

    maps = build_knownmap_anomaly_acquisition_maps(
        gp_mu_map=gp_mu_map,
        gp_var_map=gp_var_map,
        gp_acq_map=gp_acq_map,
        nav_map_prior=nav_map_prior,
        clue_acquisition_mode="anomaly_upper_tail",
        anomaly_tail_quantile=0.80,
        anomaly_weight_lambda=1.0,
    )

    prob_map = np.asarray(maps["gp_anomaly_prob_map"], dtype=float)
    weight_map = np.asarray(maps["gp_anomaly_weight_map"], dtype=float)
    acq_map = np.asarray(maps["gp_anomaly_acq_map"], dtype=float)

    free_mask = nav_map_prior == FREE
    occ_mask = nav_map_prior == OCCUPIED

    assert prob_map[(0, 2)] > prob_map[(0, 0)]
    assert prob_map[(1, 1)] > prob_map[(0, 1)]
    assert np.all(weight_map[free_mask] >= 1.0)
    assert np.all(acq_map[free_mask] >= gp_acq_map[free_mask])
    assert np.all(prob_map[occ_mask] == 0.0)
    assert np.all(weight_map[occ_mask] == 0.0)
    assert np.all(acq_map[occ_mask] == 0.0)


def test_conditional_anomaly_alpha_zero_matches_normalized_ucb() -> None:
    free_mask = np.ones((6, 6), dtype=bool)
    gp_acq_map = np.arange(36, dtype=float).reshape(6, 6)
    gp_anomaly_acq_map = np.zeros((6, 6), dtype=float)
    gp_anomaly_acq_map[1:3, 1:3] = 10.0

    planner_map, diagnostics, top_mask = build_conditional_anomaly_clue_map(
        gp_acq_map=gp_acq_map,
        gp_anomaly_acq_map=gp_anomaly_acq_map,
        free_mask=free_mask,
        step=3,
        gp_num_points=128,
        found_count=1,
        anomaly_warmup_steps=20,
    )

    assert diagnostics["anomaly_conditional_alpha"] == 0.0
    assert diagnostics["anomaly_conditional_triggered"] is False
    assert diagnostics["anomaly_gate_reason"] == "warmup"
    assert np.allclose(planner_map, _normalize01_for_test(gp_acq_map, free_mask))
    assert top_mask.shape == free_mask.shape


def test_conditional_anomaly_triggered_blends_ucb_and_anomaly() -> None:
    free_mask = np.ones((10, 10), dtype=bool)
    gp_acq_map = np.linspace(0.0, 1.0, 100, dtype=float).reshape(10, 10)
    gp_anomaly_acq_map = np.zeros((10, 10), dtype=float)
    gp_anomaly_acq_map[2, 2] = 10.0
    gp_anomaly_acq_map[2, 3] = 8.0
    gp_anomaly_acq_map[3, 2] = 7.0
    gp_anomaly_acq_map[3, 3] = 6.0

    planner_map, diagnostics, _ = build_conditional_anomaly_clue_map(
        gp_acq_map=gp_acq_map,
        gp_anomaly_acq_map=gp_anomaly_acq_map,
        free_mask=free_mask,
        step=25,
        gp_num_points=128,
        found_count=1,
    )

    alpha = float(diagnostics["anomaly_conditional_alpha"])
    ucb_norm = _normalize01_for_test(gp_acq_map, free_mask)
    anomaly_norm = _normalize01_for_test(gp_anomaly_acq_map, free_mask)
    expected = _normalize01_for_test((1.0 - alpha) * ucb_norm + alpha * anomaly_norm, free_mask)

    assert diagnostics["anomaly_conditional_triggered"] is True
    assert diagnostics["anomaly_gate_reason"] == "triggered"
    assert alpha > 0.0
    assert np.allclose(planner_map, expected)


def test_conditional_anomaly_uniform_map_does_not_trigger() -> None:
    free_mask = np.ones((8, 8), dtype=bool)
    gp_acq_map = np.linspace(0.0, 1.0, 64, dtype=float).reshape(8, 8)
    gp_anomaly_acq_map = np.ones((8, 8), dtype=float)

    planner_map, diagnostics, _ = build_conditional_anomaly_clue_map(
        gp_acq_map=gp_acq_map,
        gp_anomaly_acq_map=gp_anomaly_acq_map,
        free_mask=free_mask,
        step=25,
        gp_num_points=128,
        found_count=1,
    )

    assert diagnostics["anomaly_conditional_triggered"] is False
    assert diagnostics["anomaly_gate_reason"] in {"high_entropy", "low_top_mass"}
    assert np.allclose(planner_map, _normalize01_for_test(gp_acq_map, free_mask))


def test_conditional_anomaly_output_is_numerically_safe() -> None:
    free_mask = np.ones((5, 5), dtype=bool)
    free_mask[0, 0] = False
    gp_acq_map = np.full((5, 5), 2.0, dtype=float)
    gp_acq_map[2, 2] = np.nan
    gp_anomaly_acq_map = np.full((5, 5), np.inf, dtype=float)

    planner_map, diagnostics, top_mask = build_conditional_anomaly_clue_map(
        gp_acq_map=gp_acq_map,
        gp_anomaly_acq_map=gp_anomaly_acq_map,
        free_mask=free_mask,
        step=25,
        gp_num_points=128,
        found_count=1,
    )

    assert planner_map.shape == gp_acq_map.shape
    assert top_mask.shape == gp_acq_map.shape
    assert np.all(np.isfinite(planner_map))
    assert planner_map[0, 0] == 0.0
    assert np.isfinite(float(diagnostics["anomaly_top_mass_ratio"]))
    assert np.isfinite(float(diagnostics["anomaly_entropy_norm"]))


def test_single_knownmap_init_defaults_to_ucb_clue_planner_map() -> None:
    state = _init_knownmap_state(
        episode_seed=0,
        policy_name="marine_knownmap_path_v2_infosampled",
        n_targets=2,
        map_kind="open_water",
        target_motion_mode="static",
        target_count_upper_bound=3,
        staleness_tau_steps=12,
        resolution_m=5.0,
        sensor_range_m=25.0,
        min_target_separation_m=30.0,
        min_start_distance_m=40.0,
        gp_length_scale_m=20.0,
        gp_noise_std=0.03,
        gp_prior_mean=0.0,
        gp_beta=0.5,
        gp_optimize_hyperparams=False,
        clue_sigma_m=15.0,
        clue_amplitude=2.0,
        clue_noise_std=0.03,
        constraint_mode="hard",
        r_hit=1,
        clue_samples_per_step=6,
    )

    assert state["clue_acquisition_mode"] == "ucb"
    assert np.array_equal(state["gp_clue_planner_map"], state["gp_acq_map"])
    assert np.all(np.asarray(state["gp_anomaly_weight_map"])[state["nav_map_prior"] == FREE] >= 1.0)


def test_single_usv_anomaly_upper_tail_runtime_smoke() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        clue_acquisition_mode="anomaly_upper_tail",
    )

    assert result["clue_acquisition_mode"] == "anomaly_upper_tail"
    assert "anomaly_top_band_selection_ratio_pre_first_detection" in result
    assert "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection" in result
    if result["trace_rows"]:
        first_trace = result["trace_rows"][0]
        assert "anomaly_viewpoint_prob" in first_trace
        assert "anomaly_viewpoint_weight" in first_trace
        assert "selected_in_anomaly_top_band" in first_trace


def test_single_usv_conditional_anomaly_runtime_smoke() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        clue_acquisition_mode="ucb_anomaly_conditional",
        anomaly_warmup_steps=1,
        anomaly_min_gp_points=1,
    )

    assert result["clue_acquisition_mode"] == "ucb_anomaly_conditional"
    assert "anomaly_conditional_alpha_final" in result
    assert "anomaly_conditional_trigger_rate" in result
    if result["trace_rows"]:
        first_trace = result["trace_rows"][0]
        assert "anomaly_conditional_alpha" in first_trace
        assert "anomaly_gate_reason" in first_trace
