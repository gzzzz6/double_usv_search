from __future__ import annotations

import json

import numpy as np
import pytest

from baseline_GP import core_map
from baseline_GP.core_anomaly_acquisition import build_knownmap_anomaly_acquisition_maps
from baseline_GP.core_intensity import remaining_intensity_mass
from baseline_GP.core_map import FREE, OCCUPIED, UNKNOWN
from baseline_GP.core_planner import a_star_nav
from baseline_GP.core_search_policy import (
    SUPPORTED_KNOWNMAP_POLICIES,
    SUPPORTED_UNKNOWNMAP_POLICIES,
    _budget_tree_child_candidates,
    _knownmap_fallback_local_segments,
    _knownmap_neighbor_obstacle_count,
    _knownmap_precompute_viewpoint_geometry_cache,
    _rank_infosampled_viewpoints,
    _knownmap_reconstruct_path_from_tree,
    _knownmap_segment_score_breakdown,
    _knownmap_single_source_shortest_path_tree,
    _knownmap_tree_child_oracle_diagnostics,
    _knownmap_visible_free_cells,
    _select_best_tree_root_combination,
    select_knownmap_path_segment_policy,
)
from baseline_GP.core_staleness import build_staleness_map, init_last_seen
from baseline_GP.marine_knownmap_runtime import (
    KNOWNMAP_EXPERIMENT_CONTRACT_PATH,
    _init_knownmap_state,
    _semantic_anchor_source,
    load_knownmap_experiment_contract,
    run_episode_single_usv_search_knownmap,
    run_evaluation_single_usv_search_knownmap,
    summarize_knownmap_policy_comparison_matrix,
)
try:
    from baseline_GP.runner_single_usv_belief import run_episode_single_usv_belief
except ModuleNotFoundError:
    run_episode_single_usv_belief = None
from baseline_GP.viz_search import _draw_main_map


def _scale_interval(start: int, end: int, base_extent: int, target_extent: int) -> tuple[int, int]:
    scaled_start = int(round((float(start) / float(base_extent)) * float(target_extent)))
    scaled_end = int(round((float(end) / float(base_extent)) * float(target_extent)))
    if end > start and scaled_end <= scaled_start:
        scaled_end = min(int(target_extent), scaled_start + 1)
    return scaled_start, scaled_end


def _scaled_rect(
    rect: tuple[int, int, int, int],
    h: int,
    w: int,
    *,
    base_h: int = 40,
    base_w: int = 60,
) -> tuple[int, int, int, int]:
    r0, r1, c0, c1 = rect
    sr0, sr1 = _scale_interval(r0, r1, base_h, h)
    sc0, sc1 = _scale_interval(c0, c1, base_w, w)
    return sr0, sr1, sc0, sc1


def test_knownmap_init_exposes_full_static_nav_prior() -> None:
    state = _init_knownmap_state(
        episode_seed=0,
        policy_name="marine_search_soft_knownmap",
        n_targets=2,
        map_kind="harbor_cove",
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
        clue_sigma_m=20.0,
        clue_amplitude=2.0,
        clue_noise_std=0.03,
        constraint_mode="hard",
        r_hit=1,
        clue_samples_per_step=8,
    )

    assert "nav_map_prior" in state
    assert "known_map" not in state
    assert np.array_equal(state["nav_map_prior"], state["true_map"])
    assert not np.any(state["nav_map_prior"] == UNKNOWN)


def test_knownmap_init_respects_explicit_large_grid_shape() -> None:
    state = _init_knownmap_state(
        episode_seed=0,
        policy_name="marine_search_soft_knownmap",
        n_targets=2,
        map_kind="harbor_cove",
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
        map_height_cells=60,
        map_width_cells=80,
        constraint_mode="hard",
        r_hit=1,
        clue_samples_per_step=8,
    )

    assert state["true_map"].shape == (60, 80)
    assert state["nav_map_prior"].shape == (60, 80)
    assert state["map_height_cells"] == 60
    assert state["map_width_cells"] == 80


def test_structured_knownmap_worlds_scale_to_large_grid() -> None:
    cases = {
        "benchmark": (
            (
                (8, 12, 10, 25),
                (18, 22, 30, 45),
                (26, 34, 20, 24),
                (10, 18, 48, 52),
            ),
            (20, 10),
        ),
        "harbor_cove": (
            (
                (6, 12, 34, 59),
                (28, 34, 34, 59),
                (12, 28, 51, 59),
            ),
            (20, 20),
        ),
        "peninsula_passage": (
            (
                (14, 39, 18, 24),
                (8, 19, 33, 40),
                (24, 30, 40, 47),
            ),
            (8, 8),
        ),
    }

    for map_kind, (base_rects, free_probe) in cases.items():
        large_world = core_map.create_world(h=60, w=80, map_kind=map_kind)
        assert large_world.shape == (60, 80)
        assert large_world[free_probe] == FREE
        for rect in base_rects:
            sr0, sr1, sc0, sc1 = _scaled_rect(rect, 60, 80)
            center = ((sr0 + sr1 - 1) // 2, (sc0 + sc1 - 1) // 2)
            assert large_world[center] == OCCUPIED


def test_knownmap_runtime_does_not_use_reveal_cells(monkeypatch) -> None:
    def _fail_reveal(*args, **kwargs):
        raise AssertionError("known-map runtime should not call reveal_cells")

    monkeypatch.setattr(core_map, "reveal_cells", _fail_reveal)

    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=4,
        policy_name="known_map_greedy_viewpoint",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=2,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["map_prior_mode"] == "known_static"


def test_knownmap_runtime_reports_explicit_map_dimensions() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=4,
        policy_name="known_map_greedy_viewpoint",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_count_upper_bound=2,
        clue_sigma_m=15.0,
        clue_samples_per_step=6,
        gp_max_points=32,
    )

    assert result["map_height_cells"] == 60
    assert result["map_width_cells"] == 80
    assert result["map_kind"] == "open_water"


def test_knownmap_viewpoint_selector_uses_viewpoint_fields() -> None:
    nav_map_prior = np.full((7, 7), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)

    segment, details = select_knownmap_path_segment_policy(
        policy_name="known_map_greedy_viewpoint",
        nav_map_prior=nav_map_prior,
        robot_pos=(1, 1),
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=None,
        intensity_map=None,
        segment_horizon=4,
        top_k_anchors=3,
        viewpoints_per_anchor=3,
    )

    assert segment is not None
    assert details["viewpoint_rule"] in {"anchor_viewpoint_ring", "local_fallback", "current_viewpoint"}
    assert "gateway_rule" not in details
    assert "anchor_state" not in details


def test_knownmap_anomaly_acquisition_map_properties() -> None:
    nav_map_prior = np.full((4, 5), FREE, dtype=np.int8)
    nav_map_prior[0, 0] = OCCUPIED
    gp_mu_map = np.asarray(
        [
            [0.0, 0.1, 0.2, 0.8, 0.9],
            [0.1, 0.2, 0.3, 0.7, 0.8],
            [0.0, 0.1, 0.2, 0.4, 0.5],
            [0.0, 0.0, 0.1, 0.2, 0.3],
        ],
        dtype=float,
    )
    gp_var_map = np.asarray(
        [
            [0.0, 0.02, 0.03, 0.10, 0.16],
            [0.01, 0.03, 0.04, 0.09, 0.12],
            [0.01, 0.02, 0.03, 0.04, 0.05],
            [0.01, 0.01, 0.02, 0.02, 0.03],
        ],
        dtype=float,
    )
    gp_acq_map = gp_mu_map + 0.5 * np.sqrt(np.clip(gp_var_map, 0.0, None))

    maps = build_knownmap_anomaly_acquisition_maps(
        gp_mu_map=gp_mu_map,
        gp_var_map=gp_var_map,
        gp_acq_map=gp_acq_map,
        nav_map_prior=nav_map_prior,
        clue_acquisition_mode="anomaly_upper_tail",
        anomaly_tail_quantile=0.90,
        anomaly_weight_lambda=1.0,
    )

    assert maps["gp_anomaly_prob_map"].shape == gp_mu_map.shape
    assert maps["gp_anomaly_prob_map"][0, 4] > maps["gp_anomaly_prob_map"][3, 0]
    assert maps["gp_anomaly_weight_map"][nav_map_prior == FREE].min() >= 1.0
    assert np.all(
        maps["gp_anomaly_acq_map"][nav_map_prior == FREE]
        >= gp_acq_map[nav_map_prior == FREE] - 1e-9
    )
    assert maps["gp_anomaly_prob_map"][0, 0] == 0.0
    assert maps["gp_clue_planner_map"][0, 4] == maps["gp_anomaly_acq_map"][0, 4]


def test_knownmap_init_defaults_to_ucb_clue_planner_map() -> None:
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
        map_height_cells=60,
        map_width_cells=80,
        clue_samples_per_step=6,
    )

    assert np.array_equal(state["gp_clue_planner_map"], state["gp_acq_map"])


def test_knownmap_init_intensity_tracks_remaining_target_count_not_upper_bound() -> None:
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
        clue_samples_per_step=6,
    )

    expected_remaining = float(state["target_positions"].shape[0] - int(np.sum(state["found_mask"])))
    assert np.isclose(remaining_intensity_mass(state["intensity_map"]), expected_remaining)


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
        clue_sigma_m=15.0,
        clue_samples_per_step=6,
        gp_max_points=32,
        clue_acquisition_mode="anomaly_upper_tail",
    )

    assert result["clue_acquisition_mode"] == "anomaly_upper_tail"
    assert "anomaly_top_band_selection_ratio_pre_first_detection" in result
    assert (
        "selected_in_anomaly_top_band" in result["trace_rows"][0]
        if result["trace_rows"]
        else True
    )


def test_knownmap_segment_score_accumulates_along_path() -> None:
    nav_map_prior = np.full((7, 7), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)

    straight_path = [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5)]
    detour_path = [(3, 1), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 5)]
    straight = _knownmap_segment_score_breakdown(
        segment_path=straight_path,
        nav_map_prior=nav_map_prior,
        sensor_range=1,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=None,
        intensity_map=None,
        anchor_cell=(3, 5),
        viewpoint_cell=(3, 5),
        gamma=0.95,
    )
    detour = _knownmap_segment_score_breakdown(
        segment_path=detour_path,
        nav_map_prior=nav_map_prior,
        sensor_range=1,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=None,
        intensity_map=None,
        anchor_cell=(3, 5),
        viewpoint_cell=(3, 5),
        gamma=0.95,
    )

    assert straight["explore_utility_raw"] != detour["explore_utility_raw"]


def test_knownmap_sssp_tree_and_reconstruct_path_are_consistent() -> None:
    nav_map_prior = np.full((7, 7), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    nav_map_prior[1:6, 3] = OCCUPIED

    robot_pos = (1, 1)
    tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
    reachable = tree["reachable_free_mask"]
    distance_map = tree["distance_map"]

    assert bool(reachable[1, 2])
    assert not bool(reachable[3, 4])
    assert float(distance_map[1, 2]) == 1.0
    assert np.isinf(distance_map[3, 4])

    reachable_goal = (5, 2)
    path = _knownmap_reconstruct_path_from_tree(
        tree["parent_row_map"],
        tree["parent_col_map"],
        robot_pos,
        reachable_goal,
    )
    assert path is not None
    assert path[0] == robot_pos
    assert path[-1] == reachable_goal
    assert len(path) - 1 == int(distance_map[reachable_goal])

    unreachable_goal = (3, 4)
    assert _knownmap_reconstruct_path_from_tree(
        tree["parent_row_map"],
        tree["parent_col_map"],
        robot_pos,
        unreachable_goal,
    ) is None


def test_knownmap_sssp_path_lengths_match_repeated_astar() -> None:
    nav_map_prior = np.full((8, 8), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    nav_map_prior[2:6, 3] = OCCUPIED
    nav_map_prior[4, 3] = FREE

    robot_pos = (1, 1)
    tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
    goals = [(1, 5), (5, 5), (6, 2), (3, 6)]
    for goal in goals:
        path_from_tree = _knownmap_reconstruct_path_from_tree(
            tree["parent_row_map"],
            tree["parent_col_map"],
            robot_pos,
            goal,
        )
        path_from_astar = a_star_nav(nav_map_prior, robot_pos, goal, unknown_cost=1)
        if path_from_astar is None:
            assert path_from_tree is None
            continue
        assert path_from_tree is not None
        assert len(path_from_tree) == len(path_from_astar)
        for cell in path_from_tree:
            assert nav_map_prior[cell] == FREE


def test_knownmap_geometry_cache_matches_visibility_and_obstacle_helpers() -> None:
    nav_map_prior = np.full((8, 8), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    nav_map_prior[3, 3] = OCCUPIED
    nav_map_prior[4, 5] = OCCUPIED

    cache = _knownmap_precompute_viewpoint_geometry_cache(nav_map_prior, sensor_range=2)
    width = nav_map_prior.shape[1]
    for cell in ((2, 2), (2, 5), (5, 2), (5, 5)):
        expected_visible = _knownmap_visible_free_cells(cell, nav_map_prior, sensor_range=2)
        expected_flat = np.asarray([x * width + y for x, y in expected_visible], dtype=np.int32)
        cached_flat = np.asarray(cache["visible_free_flat_indices"][cell], dtype=np.int32)
        assert np.array_equal(cached_flat, expected_flat)
        assert int(cache["obstacle_neighbor_count_map"][cell]) == _knownmap_neighbor_obstacle_count(
            nav_map_prior,
            cell,
        )


def test_infosampled_reachable_pool_size_counts_raw_pool_connectivity() -> None:
    nav_map_prior = np.full((9, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    nav_map_prior[1:8, 4] = OCCUPIED

    robot_pos = (2, 2)
    tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
    sample_pool = [
        {"viewpoint_cell": (2, 3), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (3, 2), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (2, 6), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (6, 6), "viewpoint_sampling_mode": "shell"},
    ]
    search_info_map = np.zeros((9, 9), dtype=float)
    search_info_map[2, 3] = 1.0
    search_info_map[3, 2] = 0.8
    search_info_map[2, 6] = 0.9
    search_info_map[6, 6] = 0.7

    ranked, _ = _rank_infosampled_viewpoints(
        sample_pool,
        nav_map_prior=nav_map_prior,
        robot_pos=robot_pos,
        anchor_cluster={
            "anchor_cell": (2, 3),
            "anchor_centroid_cell": (2, 3),
        },
        sensor_range=2,
        search_info_map=search_info_map,
        staleness_map=None,
        current_viewpoint=None,
        sssp_tree=tree,
        top_k=1,
    )

    assert ranked
    selected = ranked[0]
    assert selected["candidate_pool_size"] == 4
    assert selected["reachable_pool_size"] == 2
    assert selected["a_star_checked_pool_size"] == 2


def test_infosampled_inspected_limit_shrink_reduces_checked_pool_size() -> None:
    nav_map_prior = np.full((9, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED

    robot_pos = (2, 2)
    tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
    sample_pool = [
        {"viewpoint_cell": (2, 3), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (3, 2), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (2, 4), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (4, 2), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (3, 4), "viewpoint_sampling_mode": "shell"},
        {"viewpoint_cell": (4, 3), "viewpoint_sampling_mode": "shell"},
    ]
    search_info_map = np.zeros((9, 9), dtype=float)
    for idx, sampled in enumerate(sample_pool, start=1):
        search_info_map[tuple(sampled["viewpoint_cell"])] = float(10 - idx)

    wide_ranked, _ = _rank_infosampled_viewpoints(
        sample_pool,
        nav_map_prior=nav_map_prior,
        robot_pos=robot_pos,
        anchor_cluster={
            "anchor_cell": (3, 3),
            "anchor_centroid_cell": (3, 3),
        },
        sensor_range=2,
        search_info_map=search_info_map,
        staleness_map=None,
        current_viewpoint=None,
        sssp_tree=tree,
        top_k=1,
        inspected_limit_multiplier=3.0,
        inspected_limit_floor=4,
    )
    tight_ranked, _ = _rank_infosampled_viewpoints(
        sample_pool,
        nav_map_prior=nav_map_prior,
        robot_pos=robot_pos,
        anchor_cluster={
            "anchor_cell": (3, 3),
            "anchor_centroid_cell": (3, 3),
        },
        sensor_range=2,
        search_info_map=search_info_map,
        staleness_map=None,
        current_viewpoint=None,
        sssp_tree=tree,
        top_k=1,
        inspected_limit_multiplier=1.0,
        inspected_limit_floor=1,
    )

    assert wide_ranked and tight_ranked
    assert wide_ranked[0]["candidate_pool_size"] == tight_ranked[0]["candidate_pool_size"]
    assert wide_ranked[0]["reachable_pool_size"] == tight_ranked[0]["reachable_pool_size"]
    assert wide_ranked[0]["a_star_checked_pool_size"] > tight_ranked[0]["a_star_checked_pool_size"]


def test_knownmap_fallback_anchor_source_is_not_semantic_staleness() -> None:
    nav_map_prior = np.full((7, 7), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED

    candidates = _knownmap_fallback_local_segments(
        nav_map_prior=nav_map_prior,
        robot_pos=(3, 3),
        sensor_range=2,
        segment_horizon=3,
        max_candidates=3,
    )

    assert candidates
    assert all(candidate["anchor_source"] == "fallback_local" for candidate in candidates)
    assert not _semantic_anchor_source("fallback_local")


def test_policy_registries_are_explicitly_split() -> None:
    assert "marine_search_soft" in SUPPORTED_UNKNOWNMAP_POLICIES
    assert "marine_search_soft_knownmap" not in SUPPORTED_UNKNOWNMAP_POLICIES
    assert "marine_search_soft_knownmap" in SUPPORTED_KNOWNMAP_POLICIES
    assert "marine_knownmap_path_v2_infofused" in SUPPORTED_KNOWNMAP_POLICIES
    assert "marine_knownmap_path_v2_infosampled" in SUPPORTED_KNOWNMAP_POLICIES


def test_knownmap_contract_file_freezes_expected_surface() -> None:
    contract = load_knownmap_experiment_contract()

    assert KNOWNMAP_EXPERIMENT_CONTRACT_PATH.exists()
    assert contract["schema_version"] == "knownmap_phase0_v1"
    assert tuple(contract["frozen_policy_set"]) == (
        "known_map_greedy_viewpoint",
        "marine_search_soft_knownmap",
        "marine_knownmap_path_v2",
    )
    assert set(contract["frozen_policy_set"]).issubset(set(SUPPORTED_KNOWNMAP_POLICIES))
    assert contract["frozen_config"]["episode_seeds"] == [0, 1, 2, 3, 4]
    assert "time_to_first_detection" in contract["frozen_summary_keys"]
    assert "planning_time_ms_mean" in contract["frozen_summary_keys"]
    assert "alpha_focus_mean" in contract["frozen_policy_summary_keys"]
    assert "fraction_of_path_executed_before_replan_mean" in contract["frozen_policy_summary_keys"]
    assert "viewpoint_cell" in contract["frozen_trace_keys"]
    assert "time_to_first_detection_delta" in contract["frozen_paired_comparison_keys"]


def test_knownmap_summary_and_trace_drop_unknown_map_fields() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_soft_knownmap",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=8,
        gp_max_points=64,
    )

    assert result["policy_name"] == "marine_search_soft_knownmap"
    assert "known_free_observation_ratio_final" in result
    assert "stale_region_refresh_rate" in result
    assert "same_anchor_segment_ratio" in result
    assert "path_invalidations_per_episode" in result
    assert "online_known_free_ratio_final" not in result
    assert "opened_unknown_count_total" not in result
    assert "eval_free_coverage_rate" not in result

    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "viewpoint_cell" in row
    assert "viewpoint_rule" in row
    assert "known_free_observation_ratio" in row
    assert "opened_unknown_count" not in row
    assert "online_known_free_ratio" not in row
    assert "gateway_rule" not in row
    assert "anchor_state" not in row


def test_infofused_knownmap_policy_uses_search_info_anchor_source() -> None:
    nav_map_prior = np.full((9, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)
    staleness_map[1:4, 1:4] = 1.0
    clue_map = np.zeros((9, 9), dtype=float)
    clue_map[6, 6] = 2.0
    intensity_map = np.zeros((9, 9), dtype=float)
    intensity_map[6, 5] = 2.5
    search_info_map = np.zeros((9, 9), dtype=float)
    search_info_map[6:8, 5:8] = np.array([[0.6, 0.9, 0.7], [0.4, 0.8, 0.5]])

    segment, details = select_knownmap_path_segment_policy(
        policy_name="marine_knownmap_path_v2_infofused",
        nav_map_prior=nav_map_prior,
        robot_pos=(2, 2),
        sensor_range=3,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        search_info_clue_component=0.4 * search_info_map,
        search_info_intensity_component=0.6 * search_info_map,
        segment_horizon=5,
        top_k_anchors=3,
        viewpoints_per_anchor=4,
    )

    assert segment is not None
    assert details["anchor_source"] in {"search_info", "current_viewpoint", "fallback_local"}
    assert details["anchor_source"] != "staleness"
    assert "search_info_gain_raw" in details
    assert "recency_bias_raw" in details


def test_knownmap_contract_eval_is_repeatable_and_writes_comparison_matrix(tmp_path) -> None:
    contract = load_knownmap_experiment_contract()
    contract["frozen_config"]["episode_seeds"] = [0, 1]
    contract["frozen_config"]["map_kind"] = "open_water"
    contract["frozen_config"]["max_iters"] = 12
    contract["frozen_config"]["n_targets"] = 2
    contract["frozen_config"]["target_motion_mode"] = "static"
    contract["frozen_config"]["target_count_upper_bound"] = 3
    contract["frozen_config"]["clue_samples_per_step"] = 6
    contract["frozen_config"]["gp_max_points"] = 32
    contract_path = tmp_path / "knownmap_contract.json"
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    output_dir_a = tmp_path / "eval_a"
    output_dir_b = tmp_path / "eval_b"
    results_a = run_evaluation_single_usv_search_knownmap(
        contract_path=str(contract_path),
        output_dir=str(output_dir_a),
        save_artifacts=True,
    )
    results_b = run_evaluation_single_usv_search_knownmap(
        contract_path=str(contract_path),
        output_dir=str(output_dir_b),
        save_artifacts=True,
    )

    deterministic_summary_keys = tuple(
        key for key in contract["frozen_summary_keys"] if key != "planning_time_ms_mean"
    )
    frozen_trace_keys = tuple(contract["frozen_trace_keys"])
    for policy_name in contract["frozen_policy_set"]:
        policy_results_a = results_a[policy_name]
        policy_results_b = results_b[policy_name]
        assert len(policy_results_a) == 2
        assert len(policy_results_b) == 2
        for result_a, result_b in zip(policy_results_a, policy_results_b):
            assert set(result_a.keys()) == set(result_b.keys())
            assert {key: result_a[key] for key in deterministic_summary_keys} == {
                key: result_b[key] for key in deterministic_summary_keys
            }
            assert result_a["planning_time_ms_mean"] >= 0.0
            assert result_b["planning_time_ms_mean"] >= 0.0
            if result_a["trace_rows"] and result_b["trace_rows"]:
                assert set(result_a["trace_rows"][0].keys()) == set(result_b["trace_rows"][0].keys())
                assert {key: result_a["trace_rows"][0][key] for key in frozen_trace_keys} == {
                    key: result_b["trace_rows"][0][key] for key in frozen_trace_keys
                }

    matrix = summarize_knownmap_policy_comparison_matrix(
        results_a,
        episode_seeds=[0, 1],
        contract_path=str(contract_path),
    )
    assert len(matrix["pair_labels"]) == 3

    summary_payload = json.loads((output_dir_a / "summary.json").read_text(encoding="utf-8"))
    assert summary_payload["knownmap_contract_schema_version"] == "knownmap_phase0_v1"
    assert len(summary_payload["knownmap_policy_comparison_matrix"]["pair_labels"]) == 3
    assert (output_dir_a / "paired_outcomes.csv").exists()
    assert (output_dir_a / "comparison_matrix.json").exists()


def test_infofused_policy_can_run_outside_phase0_frozen_policy_set() -> None:
    results = run_evaluation_single_usv_search_knownmap(
        policy_names=("marine_knownmap_path_v2_infofused",),
        episode_seeds=(0,),
        max_iters=8,
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
    )

    assert "marine_knownmap_path_v2_infofused" in results
    result = results["marine_knownmap_path_v2_infofused"][0]
    assert result["policy_name"] == "marine_knownmap_path_v2_infofused"
    assert "search_info_gain_mean" in result
    assert "recency_bias_mean" in result


def test_infosampled_policy_is_deterministic_for_same_sampling_seed() -> None:
    nav_map_prior = np.full((9, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)
    staleness_map[1:4, 1:4] = 0.9
    clue_map = np.zeros((9, 9), dtype=float)
    clue_map[6:8, 5:8] = np.array([[0.4, 1.0, 0.7], [0.2, 0.8, 0.5]])
    intensity_map = np.zeros((9, 9), dtype=float)
    intensity_map[5:8, 5:8] = np.array([[0.1, 0.3, 0.2], [0.4, 1.2, 0.6], [0.2, 0.7, 0.4]])
    search_info_map = 0.45 * clue_map + 0.55 * intensity_map

    kwargs = dict(
        policy_name="marine_knownmap_path_v2_infosampled",
        nav_map_prior=nav_map_prior,
        robot_pos=(2, 2),
        sensor_range=3,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        search_info_clue_component=0.45 * search_info_map,
        search_info_intensity_component=0.55 * search_info_map,
        current_viewpoint=(3, 3),
        current_segment_endpoint=(4, 4),
        segment_horizon=5,
        top_k_anchors=3,
        viewpoints_per_anchor=4,
        sampling_seed_base=20260405,
        viewpoint_generation_mode="infosampled_pool_v1",
    )
    segment_a, details_a = select_knownmap_path_segment_policy(**kwargs)
    segment_b, details_b = select_knownmap_path_segment_policy(**kwargs)

    assert segment_a == segment_b
    assert details_a["viewpoint_cell"] == details_b["viewpoint_cell"]
    assert details_a["sampled_viewpoint_pool_cells"] == details_b["sampled_viewpoint_pool_cells"]
    assert details_a["selected_viewpoint_rank"] == details_b["selected_viewpoint_rank"]
    assert details_a["sampling_priority_raw"] == details_b["sampling_priority_raw"]
    assert details_a["reachable_pool_size"] >= details_a["a_star_checked_pool_size"]
    assert (3, 3) in details_a["sampled_viewpoint_pool_cells"]
    assert (4, 4) in details_a["sampled_viewpoint_pool_cells"]


def test_infosampled_policy_exposes_sampling_trace_fields() -> None:
    results = run_evaluation_single_usv_search_knownmap(
        policy_names=("marine_knownmap_path_v2_infosampled",),
        episode_seeds=(0,),
        max_iters=8,
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
    )

    result = results["marine_knownmap_path_v2_infosampled"][0]
    assert result["policy_name"] == "marine_knownmap_path_v2_infosampled"
    assert result["viewpoint_generation_mode"] == "simple_ring_v1"
    assert "candidate_pool_size_mean" in result
    assert "reachable_pool_size_mean" in result
    assert "a_star_checked_pool_size_mean" in result
    assert "selected_viewpoint_rank_mean" in result
    assert "sampling_priority_mean" in result
    assert "sssp_build_time_ms_mean" in result
    assert "path_reconstruct_time_ms_mean" in result
    assert "sampling_pool_build_time_ms_mean" in result
    assert "priority_feature_time_ms_mean" in result

    assert result["trace_rows"]
    trace_keys = set(result["trace_rows"][0].keys())
    assert "candidate_pool_size" in trace_keys
    assert "reachable_pool_size" in trace_keys
    assert "a_star_checked_pool_size" in trace_keys
    assert "selected_viewpoint_rank" in trace_keys
    assert "sampling_priority_raw" in trace_keys
    assert "sampling_priority_norm" in trace_keys
    assert "viewpoint_sampling_mode" in trace_keys
    assert "selected_by_final_score" in trace_keys
    assert "sssp_build_time_ms" in trace_keys
    assert "path_reconstruct_time_ms" in trace_keys
    assert "sampling_pool_build_time_ms" in trace_keys
    assert "priority_feature_time_ms" in trace_keys
    assert "marginal_information_gain_raw" in trace_keys
    assert "marginal_information_gain_norm" in trace_keys
    assert "execution_cost_raw" in trace_keys
    assert "execution_cost_norm" in trace_keys
    assert "continuity_bonus_raw" in trace_keys
    assert "maneuver_penalty_raw" in trace_keys

    anchor_sources = {
        row["anchor_source"]
        for row in result["trace_rows"]
        if row.get("replanned_this_step", False)
    }
    assert anchor_sources.issubset({"search_info", "current_viewpoint", "fallback_local"})
    first_row = result["trace_rows"][0]
    assert first_row["candidate_pool_size"] >= first_row["reachable_pool_size"]
    assert first_row["reachable_pool_size"] >= first_row["a_star_checked_pool_size"]
    assert first_row["sssp_build_time_ms"] >= 0.0
    assert first_row["path_reconstruct_time_ms"] >= 0.0
    assert first_row["sampling_pool_build_time_ms"] >= 0.0
    assert first_row["priority_feature_time_ms"] >= 0.0
    assert first_row["marginal_information_gain_raw"] == first_row["search_info_gain_raw"]
    assert first_row["marginal_information_gain_norm"] == first_row["search_info_gain_norm"]
    assert first_row["execution_cost_raw"] == first_row["exec_cost_raw"]
    assert first_row["execution_cost_norm"] == first_row["exec_cost_norm"]
    assert first_row["continuity_bonus_raw"] == (
        first_row["anchor_retention_bonus"] + first_row["viewpoint_retention_bonus"]
    )
    assert first_row["maneuver_penalty_raw"] == first_row["u_turn_penalty_term"]


def test_infosampled_details_expose_phase5_lite_semantic_aliases() -> None:
    nav_map_prior = np.full((9, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)
    clue_map = np.zeros((9, 9), dtype=float)
    clue_map[5:8, 4:7] = np.array([[0.3, 0.6, 0.4], [0.5, 0.9, 0.7], [0.2, 0.5, 0.4]])
    intensity_map = np.zeros((9, 9), dtype=float)
    intensity_map[5:8, 4:7] = np.array([[0.4, 0.7, 0.5], [0.6, 1.0, 0.8], [0.3, 0.6, 0.5]])
    search_info_map = 0.45 * clue_map + 0.55 * intensity_map

    segment, details = select_knownmap_path_segment_policy(
        policy_name="marine_knownmap_path_v2_infosampled",
        nav_map_prior=nav_map_prior,
        robot_pos=(2, 2),
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        search_info_clue_component=0.45 * search_info_map,
        search_info_intensity_component=0.55 * search_info_map,
        current_viewpoint=None,
        current_anchor=None,
        current_anchor_source=None,
        current_anchor_centroid=None,
        current_segment_endpoint=None,
        prev_move_dir=None,
        kappa_commit=0.25,
        lambda_u_turn=2.0,
        segment_horizon=4,
        top_k_anchors=3,
        viewpoints_per_anchor=4,
        gamma=0.95,
        sampling_seed_base=20260407,
        infosampled_inspected_limit_multiplier=2.0,
        infosampled_inspected_limit_floor=4,
        geometry_cache=_knownmap_precompute_viewpoint_geometry_cache(nav_map_prior, sensor_range=2),
    )

    assert segment is not None
    assert details["marginal_information_gain_raw"] == details["search_info_gain_raw"]
    assert details["marginal_information_gain_norm"] == details["search_info_gain_norm"]
    assert details["execution_cost_raw"] == details["exec_cost_raw"]
    assert details["execution_cost_norm"] == details["exec_cost_norm"]
    assert details["continuity_bonus_raw"] == (
        details["anchor_retention_bonus"] + details["viewpoint_retention_bonus"]
    )
    assert details["maneuver_penalty_raw"] == details["u_turn_penalty_term"]
    assert (
        details["score_formula_label"]
        == "marginal_information_gain - lambda_cost * execution_cost + recency_bias - maneuver_penalty"
    )


def test_knownmap_online_viz_can_hide_true_targets() -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    known_map = np.full((7, 7), FREE, dtype=np.int8)
    known_map[0, :] = OCCUPIED
    known_map[-1, :] = OCCUPIED
    known_map[:, 0] = OCCUPIED
    known_map[:, -1] = OCCUPIED

    fig, ax = plt.subplots(1, 1, figsize=(4, 4))
    _draw_main_map(
        ax,
        known_map=known_map,
        robot_pos=(2, 2),
        target_positions=np.asarray([[3, 3], [4, 4]], dtype=int),
        found_mask=np.asarray([False, True], dtype=bool),
        trajectory=[(2, 2), (2, 3)],
        path=[(2, 2), (2, 3), (3, 3)],
        goal=(3, 3),
        anchor=(4, 3),
        show_true_targets=False,
    )

    _, labels = ax.get_legend_handles_labels()
    assert "Robot" in labels
    assert "Plan" in labels
    assert "Unfound Target" not in labels
    assert "Found Target" not in labels
    plt.close(fig)


def test_largegrid_contract_template_loads_with_new_map_shape() -> None:
    contract_path = KNOWNMAP_EXPERIMENT_CONTRACT_PATH.with_name(
        "knownmap_experiment_contract_largegrid_v1.json"
    )
    contract = load_knownmap_experiment_contract(str(contract_path))

    assert contract["baseline_revision_id"] == "knownmap_largegrid_mainline_sigma15_60x80_20260408"
    assert contract["frozen_config"]["map_height_cells"] == 60
    assert contract["frozen_config"]["map_width_cells"] == 80
    assert contract["frozen_config"]["clue_sigma_m"] == 15.0
    assert contract["frozen_config"]["max_iters"] == 440
    assert tuple(contract["frozen_policy_set"]) == (
        "known_map_greedy_viewpoint",
        "marine_search_soft_knownmap",
        "marine_knownmap_path_v2_infofused",
        "marine_knownmap_path_v2_infosampled",
    )

    results = run_evaluation_single_usv_search_knownmap(
        policy_names=("marine_knownmap_path_v2_infosampled",),
        contract_path=str(contract_path),
        episode_seeds=(0,),
        max_iters=4,
        save_artifacts=False,
    )
    result = results["marine_knownmap_path_v2_infosampled"][0]
    assert result["map_height_cells"] == 60
    assert result["map_width_cells"] == 80


def test_two_usv_largegrid_contract_template_is_parseable() -> None:
    template_path = KNOWNMAP_EXPERIMENT_CONTRACT_PATH.with_name(
        "knownmap_experiment_contract_2usv_largegrid_template.json"
    )
    with template_path.open("r", encoding="utf-8") as f:
        template = json.load(f)

    assert template["template_only"] is True
    assert template["template_status"] == "phase1_phase2_runtime_skeleton"
    assert template["frozen_config"]["n_usvs"] == 2
    assert template["frozen_config"]["map_height_cells"] == 60
    assert template["frozen_config"]["map_width_cells"] == 80
    assert template["frozen_config"]["clue_sigma_m"] == 15.0
    assert template["frozen_config"]["max_iters"] == 240
    assert template["official_entrypoints"]["wrapper_file"] == "baseline_GP/runner_two_usv_search.py"
    assert tuple(template["frozen_policy_set"]) == (
        "known_map_greedy_viewpoint_2usv",
        "marine_search_soft_knownmap_2usv",
        "marine_knownmap_path_v2_infofused_2usv",
        "marine_knownmap_path_v2_infosampled_2usv",
    )


def test_infosampled_tree_d2_policy_runs_without_changing_frozen_contract() -> None:
    contract = load_knownmap_experiment_contract()

    assert "marine_knownmap_path_v2_infosampled_tree_d2" in SUPPORTED_KNOWNMAP_POLICIES
    assert "marine_knownmap_path_v2_infosampled_tree_d2" not in tuple(contract["frozen_policy_set"])

    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
    )

    assert result["policy_name"] == "marine_knownmap_path_v2_infosampled_tree_d2"
    assert result["trace_rows"]
    first_replan = next(row for row in result["trace_rows"] if row["replanned_this_step"])
    assert first_replan["tree_depth"] == 2
    assert first_replan["tree_first_layer_top_m"] == 2
    assert first_replan["tree_second_layer_top_n"] == 1
    assert first_replan["tree_expansion_count"] >= 0
    assert first_replan["tree_total_score"] >= first_replan["tree_root_score_raw"]
    assert first_replan["tree_child_oracle_gap_raw"] >= 0.0
    assert first_replan["tree_child_full_candidate_count"] >= first_replan["tree_second_layer_top_n"]


def test_tree_diminishing_returns_reduces_second_layer_gain() -> None:
    nav_map_prior = np.full((9, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    search_info_map = np.zeros((9, 9), dtype=float)
    search_info_map[2:7, 2:7] = 1.0

    root_path = [(4, 2), (4, 3), (4, 4)]
    child_path = [(4, 4), (4, 5), (4, 6)]

    root_breakdown = _knownmap_segment_score_breakdown(
        segment_path=root_path,
        nav_map_prior=nav_map_prior,
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=None,
        clue_map=None,
        intensity_map=None,
        search_info_map=search_info_map,
        anchor_cell=(4, 4),
        viewpoint_cell=(4, 4),
        gamma=0.95,
    )
    unconditional = _knownmap_segment_score_breakdown(
        segment_path=child_path,
        nav_map_prior=nav_map_prior,
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=None,
        clue_map=None,
        intensity_map=None,
        search_info_map=search_info_map,
        anchor_cell=(4, 6),
        viewpoint_cell=(4, 6),
        gamma=0.95,
    )
    conditional = _knownmap_segment_score_breakdown(
        segment_path=child_path,
        nav_map_prior=nav_map_prior,
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=None,
        clue_map=None,
        intensity_map=None,
        search_info_map=search_info_map,
        anchor_cell=(4, 6),
        viewpoint_cell=(4, 6),
        gamma=0.95,
        pre_seen_cells=set(root_breakdown["segment_visible_cells"]),
    )

    assert conditional["search_info_gain_raw"] <= unconditional["search_info_gain_raw"]
    assert conditional["unique_visible_count"] <= unconditional["unique_visible_count"]
    assert conditional["redundant_visible_ratio"] > 0.0
    assert conditional["search_info_gain_raw"] < unconditional["search_info_gain_raw"]


def test_tree_winner_is_chosen_by_tree_total_score() -> None:
    ranked_root_entries = [
        {
            "root": {"viewpoint_cell": (2, 2)},
            "child": None,
            "root_total_score": 10.0,
            "child_total_score": 0.0,
            "tree_total_score": 10.0,
            "tree_root_rank": 1,
            "tree_child_rank": 0,
            "tree_conditional_gain_lvl2": 0.0,
            "tree_redundant_visible_ratio_lvl2": 0.0,
            "tree_unique_visible_count_lvl1": 8,
            "tree_unique_visible_count_lvl2": 0,
        },
        {
            "root": {"viewpoint_cell": (3, 3)},
            "child": {"viewpoint_cell": (5, 5)},
            "root_total_score": 9.0,
            "child_total_score": 4.0,
            "tree_total_score": 12.4,
            "tree_root_rank": 2,
            "tree_child_rank": 1,
            "tree_conditional_gain_lvl2": 3.0,
            "tree_redundant_visible_ratio_lvl2": 0.1,
            "tree_unique_visible_count_lvl1": 7,
            "tree_unique_visible_count_lvl2": 5,
        },
    ]

    best = _select_best_tree_root_combination(ranked_root_entries, tree_discount_gamma=0.85)

    assert best["tree_root_rank"] == 2
    assert best["tree_total_score"] > ranked_root_entries[0]["root_total_score"]


def test_tree_budget_controls_expansion_count() -> None:
    nav_map_prior = np.full((11, 11), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)
    search_info_map = np.zeros((11, 11), dtype=float)
    search_info_map[3:8, 3:8] = 1.0
    geometry_cache = _knownmap_precompute_viewpoint_geometry_cache(nav_map_prior, sensor_range=2)

    common_kwargs = dict(
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        nav_map_prior=nav_map_prior,
        robot_pos=(2, 2),
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=None,
        intensity_map=search_info_map,
        search_info_map=search_info_map,
        current_viewpoint=None,
        current_anchor=None,
        current_anchor_source=None,
        current_anchor_centroid=None,
        current_segment_endpoint=None,
        prev_move_dir=None,
        kappa_commit=0.3,
        lambda_u_turn=2.0,
        segment_horizon=4,
        top_k_anchors=4,
        viewpoints_per_anchor=4,
        gamma=0.95,
        sampling_seed_base=1234,
        geometry_cache=geometry_cache,
    )
    _, wide_details = select_knownmap_path_segment_policy(
        **common_kwargs,
        tree_first_layer_top_m=3,
        tree_second_layer_top_n=3,
    )
    _, medium_details = select_knownmap_path_segment_policy(
        **common_kwargs,
        tree_first_layer_top_m=3,
        tree_second_layer_top_n=1,
    )
    _, tight_details = select_knownmap_path_segment_policy(
        **common_kwargs,
        tree_first_layer_top_m=1,
        tree_second_layer_top_n=1,
    )

    assert wide_details["score_schema"] == "infosampled_tree_d2"
    assert medium_details["score_schema"] == "infosampled_tree_d2"
    assert tight_details["score_schema"] == "infosampled_tree_d2"
    assert wide_details["tree_expansion_count"] >= medium_details["tree_expansion_count"]
    assert wide_details["tree_expansion_count"] >= tight_details["tree_expansion_count"]


def test_tree_child_oracle_diagnostics_are_additive_only() -> None:
    nav_map_prior = np.full((11, 11), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    last_seen = init_last_seen(nav_map_prior)
    staleness_map = build_staleness_map(last_seen, nav_map_prior, current_step=0, tau_stale=12)
    search_info_map = np.zeros((11, 11), dtype=float)
    search_info_map[3:8, 3:8] = 1.0
    geometry_cache = _knownmap_precompute_viewpoint_geometry_cache(nav_map_prior, sensor_range=2)

    common_kwargs = dict(
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        nav_map_prior=nav_map_prior,
        robot_pos=(2, 2),
        sensor_range=2,
        last_seen_step=last_seen,
        staleness_map=staleness_map,
        clue_map=None,
        intensity_map=search_info_map,
        search_info_map=search_info_map,
        current_viewpoint=None,
        current_anchor=None,
        current_anchor_source=None,
        current_anchor_centroid=None,
        current_segment_endpoint=None,
        prev_move_dir=None,
        kappa_commit=0.3,
        lambda_u_turn=2.0,
        segment_horizon=4,
        top_k_anchors=4,
        viewpoints_per_anchor=4,
        gamma=0.95,
        sampling_seed_base=1234,
        geometry_cache=geometry_cache,
        tree_first_layer_top_m=2,
        tree_second_layer_top_n=2,
    )
    path_without_oracle, details_without_oracle = select_knownmap_path_segment_policy(
        **common_kwargs,
        tree_enable_child_oracle_diagnostics=False,
    )
    path_with_oracle, details_with_oracle = select_knownmap_path_segment_policy(
        **common_kwargs,
        tree_enable_child_oracle_diagnostics=True,
    )

    assert path_without_oracle == path_with_oracle
    assert details_without_oracle["viewpoint_cell"] == details_with_oracle["viewpoint_cell"]
    assert details_without_oracle["tree_root_rank"] == details_with_oracle["tree_root_rank"]
    assert details_without_oracle["tree_child_rank"] == details_with_oracle["tree_child_rank"]
    assert details_without_oracle["tree_total_score"] == details_with_oracle["tree_total_score"]
    assert details_with_oracle["tree_child_full_candidate_count"] >= common_kwargs["tree_second_layer_top_n"]


def test_tree_side_branch_budget_remains_explicitly_runnable() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        tree_first_layer_top_m=2,
        tree_second_layer_top_n=3,
    )

    first_replan = next(row for row in result["trace_rows"] if row["replanned_this_step"])
    assert first_replan["tree_first_layer_top_m"] == 2
    assert first_replan["tree_second_layer_top_n"] == 3
    assert result["policy_name"] == "marine_knownmap_path_v2_infosampled_tree_d2"


def test_tree_runtime_can_disable_child_oracle_diagnostics() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        tree_enable_child_oracle_diagnostics=False,
    )

    first_replan = next(row for row in result["trace_rows"] if row["replanned_this_step"])
    assert first_replan["tree_child_oracle_score_raw"] == 0.0
    assert first_replan["tree_child_budget_score_raw"] >= 0.0
    assert first_replan["tree_child_oracle_gap_raw"] == 0.0
    assert first_replan["tree_child_oracle_rank_of_budgeted"] == 0
    assert first_replan["tree_child_budget_matches_oracle"] is False
    assert first_replan["tree_child_full_candidate_count"] == 0


def test_tree_child_oracle_matches_best_full_child_score() -> None:
    full_child_evaluations = [
        {
            "viewpoint_cell": (6, 6),
            "segment_endpoint_cell": (6, 6),
            "viewpoint_rule": "infosampled_priority",
            "total_score": 8.5,
        },
        {
            "viewpoint_cell": (5, 5),
            "segment_endpoint_cell": (5, 5),
            "viewpoint_rule": "current_viewpoint",
            "total_score": 7.0,
        },
        {
            "viewpoint_cell": (4, 4),
            "segment_endpoint_cell": (4, 4),
            "viewpoint_rule": "infosampled_priority",
            "total_score": 5.5,
        },
    ]
    diagnostics = _knownmap_tree_child_oracle_diagnostics(
        full_child_evaluations,
        budgeted_best_child=full_child_evaluations[1],
    )

    assert diagnostics["tree_child_oracle_viewpoint_cell"] == (6, 6)
    assert diagnostics["tree_child_budget_viewpoint_cell"] == (5, 5)
    assert diagnostics["tree_child_oracle_score_raw"] == 8.5
    assert diagnostics["tree_child_budget_score_raw"] == 7.0
    assert diagnostics["tree_child_oracle_gap_raw"] == 1.5
    assert diagnostics["tree_child_oracle_rank_of_budgeted"] == 2
    assert diagnostics["tree_child_full_candidate_count"] == 3
    assert diagnostics["tree_child_budget_matches_oracle"] is False


def test_tree_child_oracle_gap_is_zero_when_budget_matches_oracle() -> None:
    full_child_evaluations = [
        {
            "viewpoint_cell": (3, 3),
            "segment_endpoint_cell": (3, 3),
            "viewpoint_rule": "infosampled_priority",
            "total_score": 4.0,
        },
        {
            "viewpoint_cell": (4, 4),
            "segment_endpoint_cell": (4, 4),
            "viewpoint_rule": "current_viewpoint",
            "total_score": 3.2,
        },
    ]
    diagnostics = _knownmap_tree_child_oracle_diagnostics(
        full_child_evaluations,
        budgeted_best_child=full_child_evaluations[0],
    )

    assert diagnostics["tree_child_oracle_gap_raw"] == 0.0
    assert diagnostics["tree_child_oracle_rank_of_budgeted"] == 1
    assert diagnostics["tree_child_budget_matches_oracle"] is True


def test_tree_child_budget_prefers_candidates_novel_to_lvl1_seen_cells() -> None:
    nav_map_prior = np.full((11, 11), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    geometry_cache = _knownmap_precompute_viewpoint_geometry_cache(nav_map_prior, sensor_range=1)

    overlapping_candidate = {
        "viewpoint_cell": (3, 4),
        "segment_endpoint_cell": (3, 4),
        "viewpoint_rule": "infosampled_priority",
        "sampling_priority_raw": 5.0,
        "selected_viewpoint_rank": 1,
        "candidate_pool_size": 8,
        "segment_path": [(3, 3), (3, 4)],
        "segment_path_length": 1,
    }
    novel_candidate = {
        "viewpoint_cell": (7, 7),
        "segment_endpoint_cell": (7, 7),
        "viewpoint_rule": "infosampled_priority",
        "sampling_priority_raw": 4.8,
        "selected_viewpoint_rank": 2,
        "candidate_pool_size": 8,
        "segment_path": [(7, 6), (7, 7)],
        "segment_path_length": 1,
    }
    root_seen_cells = set(_knownmap_visible_free_cells((3, 4), nav_map_prior, sensor_range=1))

    selected = _budget_tree_child_candidates(
        [overlapping_candidate, novel_candidate],
        top_n=1,
        nav_map_prior=nav_map_prior,
        sensor_range=1,
        root_seen_cells=root_seen_cells,
        geometry_cache=geometry_cache,
    )

    assert len(selected) == 1
    assert selected[0]["viewpoint_cell"] == (7, 7)


def test_tree_child_budget_reduces_overlap_among_selected_children() -> None:
    nav_map_prior = np.full((12, 12), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    geometry_cache = _knownmap_precompute_viewpoint_geometry_cache(nav_map_prior, sensor_range=1)

    child_a = {
        "viewpoint_cell": (3, 3),
        "segment_endpoint_cell": (3, 3),
        "viewpoint_rule": "infosampled_priority",
        "sampling_priority_raw": 5.0,
        "selected_viewpoint_rank": 1,
        "candidate_pool_size": 9,
        "segment_path": [(3, 2), (3, 3)],
        "segment_path_length": 1,
    }
    child_b = {
        "viewpoint_cell": (3, 4),
        "segment_endpoint_cell": (3, 4),
        "viewpoint_rule": "infosampled_priority",
        "sampling_priority_raw": 4.9,
        "selected_viewpoint_rank": 2,
        "candidate_pool_size": 9,
        "segment_path": [(3, 3), (3, 4)],
        "segment_path_length": 1,
    }
    child_c = {
        "viewpoint_cell": (8, 8),
        "segment_endpoint_cell": (8, 8),
        "viewpoint_rule": "infosampled_priority",
        "sampling_priority_raw": 4.8,
        "selected_viewpoint_rank": 3,
        "candidate_pool_size": 9,
        "segment_path": [(8, 7), (8, 8)],
        "segment_path_length": 1,
    }

    selected = _budget_tree_child_candidates(
        [child_a, child_b, child_c],
        top_n=2,
        nav_map_prior=nav_map_prior,
        sensor_range=1,
        root_seen_cells=set(),
        geometry_cache=geometry_cache,
    )

    selected_viewpoints = {tuple(item["viewpoint_cell"]) for item in selected}
    assert selected_viewpoints == {(3, 3), (8, 8)}


def test_tree_policy_is_deterministic_for_same_seed_and_config() -> None:
    kwargs = dict(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        tree_first_layer_top_m=2,
        tree_second_layer_top_n=2,
        tree_discount_gamma=0.85,
    )
    result_a = run_episode_single_usv_search_knownmap(**kwargs)
    result_b = run_episode_single_usv_search_knownmap(**kwargs)

    assert result_a["found_count"] == result_b["found_count"]
    assert result_a["time_to_first_detection"] == result_b["time_to_first_detection"]
    assert len(result_a["trace_rows"]) == len(result_b["trace_rows"])

    replan_a = [row for row in result_a["trace_rows"] if row["replanned_this_step"]]
    replan_b = [row for row in result_b["trace_rows"] if row["replanned_this_step"]]
    assert len(replan_a) == len(replan_b)
    for row_a, row_b in zip(replan_a, replan_b):
        assert row_a["viewpoint_cell"] == row_b["viewpoint_cell"]
        assert row_a["tree_root_rank"] == row_b["tree_root_rank"]
        assert row_a["tree_child_rank"] == row_b["tree_child_rank"]
        assert row_a["tree_total_score"] == row_b["tree_total_score"]
        assert row_a["tree_expansion_count"] == row_b["tree_expansion_count"]
        assert row_a["tree_child_oracle_score_raw"] == row_b["tree_child_oracle_score_raw"]
        assert row_a["tree_child_budget_score_raw"] == row_b["tree_child_budget_score_raw"]
        assert row_a["tree_child_oracle_gap_raw"] == row_b["tree_child_oracle_gap_raw"]
        assert (
            row_a["tree_child_oracle_rank_of_budgeted"]
            == row_b["tree_child_oracle_rank_of_budgeted"]
        )
        assert (
            row_a["tree_child_budget_matches_oracle"]
            == row_b["tree_child_budget_matches_oracle"]
        )


@pytest.mark.skipif(
    run_episode_single_usv_belief is None,
    reason="legacy belief runner is not present in the known-map-only workspace",
)
def test_legacy_belief_runner_still_runs_as_historical_baseline() -> None:
    result = run_episode_single_usv_belief(
        episode_seed=0,
        max_iters=4,
        map_kind="open_water",
        planner_mode="posterior",
    )

    assert result["policy_name"] == "belief_posterior"
    assert result["completed_steps"] <= 4
