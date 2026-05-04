from __future__ import annotations

import numpy as np
import pytest

from baseline_GP.core_map import FREE, OCCUPIED
from baseline_GP.core_nav import a_star_nav
from baseline_GP.core_safe_nav import (
    a_star_safe,
    build_clearance_cost_map,
    build_obstacle_distance_map,
    build_reservation_table,
    evaluate_path_against_reservation,
    inflate_occupancy_map,
)
from baseline_GP.marine_knownmap_runtime import run_episode_single_usv_search_knownmap


def _toy_nav_map() -> np.ndarray:
    nav_map_prior = np.full((7, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    return nav_map_prior


def test_build_obstacle_distance_map_matches_4_neighbor_distance() -> None:
    nav_map_prior = _toy_nav_map()
    distance_map = build_obstacle_distance_map(nav_map_prior)

    assert distance_map[0, 0] == 0.0
    assert distance_map[1, 1] == 1.0
    assert distance_map[2, 2] == 2.0
    assert distance_map[3, 4] == 3.0


def test_inflate_occupancy_radius_zero_is_identity() -> None:
    nav_map_prior = _toy_nav_map()
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = inflate_occupancy_map(
        nav_map_prior,
        inflation_radius_cells=0,
        obstacle_distance_map=distance_map,
    )

    assert np.array_equal(inflated, nav_map_prior)


def test_clearance_cost_map_uses_raw_obstacle_distance() -> None:
    nav_map_prior = _toy_nav_map()
    distance_map = build_obstacle_distance_map(nav_map_prior)
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
    )

    assert clearance_cost_map[1, 4] > 0.0
    assert clearance_cost_map[2, 4] == 0.0


def test_a_star_safe_lambda_zero_matches_a_star_nav() -> None:
    nav_map_prior = _toy_nav_map()
    start = (1, 1)
    goal = (1, 7)
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = inflate_occupancy_map(
        nav_map_prior,
        inflation_radius_cells=0,
        obstacle_distance_map=distance_map,
    )
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
        inflated_nav_map=inflated,
    )

    vanilla_path = a_star_nav(nav_map_prior, start, goal, unknown_cost=1)
    safe_path = a_star_safe(
        nav_map_prior,
        start,
        goal,
        inflated_nav_map=inflated,
        clearance_cost_map=clearance_cost_map,
        lambda_clearance=0.0,
    )

    assert safe_path == vanilla_path
    assert safe_path is not None
    assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(safe_path, safe_path[1:]))


def test_a_star_safe_prefers_longer_clearer_route() -> None:
    nav_map_prior = _toy_nav_map()
    start = (1, 1)
    goal = (1, 7)
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = inflate_occupancy_map(
        nav_map_prior,
        inflation_radius_cells=0,
        obstacle_distance_map=distance_map,
    )
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
        inflated_nav_map=inflated,
    )

    safe_path = a_star_safe(
        nav_map_prior,
        start,
        goal,
        inflated_nav_map=inflated,
        clearance_cost_map=clearance_cost_map,
        lambda_clearance=1.0,
    )

    assert safe_path is not None
    assert safe_path[0] == start
    assert safe_path[-1] == goal
    assert any(cell[0] == 2 for cell in safe_path[1:-1])
    assert len(safe_path) - 1 > 6


def test_a_star_safe_returns_none_when_goal_is_blocked() -> None:
    nav_map_prior = _toy_nav_map()
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = np.array(nav_map_prior, copy=True)
    inflated[1, 7] = OCCUPIED
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
        inflated_nav_map=inflated,
    )

    assert (
        a_star_safe(
            nav_map_prior,
            (1, 1),
            (1, 7),
            inflated_nav_map=inflated,
            clearance_cost_map=clearance_cost_map,
            lambda_clearance=1.0,
        )
        is None
    )


def test_build_reservation_table_tracks_same_cell_swap_and_halo() -> None:
    reservation = build_reservation_table(
        [(2, 2), (2, 3), (2, 4)],
        safety_distance_cells=1.5,
    )

    occupied = reservation["occupied"]
    swap_edges = reservation["swap_edges"]
    soft_halo = reservation["soft_halo"]
    assert ((2, 3), 1) in occupied
    assert ((2, 4), 2) in occupied
    assert ((2, 3), (2, 2), 1) in swap_edges
    assert ((2, 4), (2, 3), 2) in swap_edges
    assert soft_halo[((1, 3), 1)] > 0.0
    assert soft_halo[((3, 4), 2)] > 0.0


def test_a_star_safe_hard_rejects_same_cell_reservation_conflict() -> None:
    nav_map_prior = np.full((3, 5), OCCUPIED, dtype=np.int8)
    nav_map_prior[1, 1:4] = FREE
    start = (1, 1)
    goal = (1, 3)
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = inflate_occupancy_map(
        nav_map_prior,
        inflation_radius_cells=0,
        obstacle_distance_map=distance_map,
    )
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
        inflated_nav_map=inflated,
    )
    reservation = build_reservation_table(
        [(1, 1), (1, 2), (1, 3)],
        safety_distance_cells=1.5,
    )

    assert (
        a_star_safe(
            nav_map_prior,
            start,
            goal,
            inflated_nav_map=inflated,
            clearance_cost_map=clearance_cost_map,
            lambda_clearance=0.0,
            reservation_table=reservation,
            team_reservation_lambda=1.0,
        )
        is None
    )


def test_a_star_safe_hard_rejects_swap_reservation_conflict() -> None:
    nav_map_prior = np.full((3, 4), OCCUPIED, dtype=np.int8)
    nav_map_prior[1, 1:3] = FREE
    start = (1, 1)
    goal = (1, 2)
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = inflate_occupancy_map(
        nav_map_prior,
        inflation_radius_cells=0,
        obstacle_distance_map=distance_map,
    )
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
        inflated_nav_map=inflated,
    )
    reservation = build_reservation_table(
        [(1, 2), (1, 1)],
        safety_distance_cells=1.5,
    )

    assert (
        a_star_safe(
            nav_map_prior,
            start,
            goal,
            inflated_nav_map=inflated,
            clearance_cost_map=clearance_cost_map,
            lambda_clearance=0.0,
            reservation_table=reservation,
            team_reservation_lambda=1.0,
        )
        is None
    )


def test_a_star_safe_reservation_prefers_less_crowded_route_and_reports_diagnostics() -> None:
    nav_map_prior = np.full((6, 9), FREE, dtype=np.int8)
    nav_map_prior[0, :] = OCCUPIED
    nav_map_prior[-1, :] = OCCUPIED
    nav_map_prior[:, 0] = OCCUPIED
    nav_map_prior[:, -1] = OCCUPIED
    start = (3, 1)
    goal = (3, 7)
    distance_map = build_obstacle_distance_map(nav_map_prior)
    inflated = inflate_occupancy_map(
        nav_map_prior,
        inflation_radius_cells=0,
        obstacle_distance_map=distance_map,
    )
    clearance_cost_map = build_clearance_cost_map(
        nav_map_prior,
        inflation_radius_cells=0,
        soft_clearance_radius_cells=1,
        obstacle_distance_map=distance_map,
        inflated_nav_map=inflated,
    )
    reservation = build_reservation_table(
        [(2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7)],
        safety_distance_cells=1.5,
    )

    path = a_star_safe(
        nav_map_prior,
        start,
        goal,
        inflated_nav_map=inflated,
        clearance_cost_map=clearance_cost_map,
        lambda_clearance=0.0,
        reservation_table=reservation,
        team_reservation_lambda=4.0,
    )

    assert path is not None
    assert any(cell[0] == 4 for cell in path[1:-1])
    diagnostics = evaluate_path_against_reservation(path, reservation)
    assert not diagnostics["same_cell_violation"]
    assert not diagnostics["swap_violation"]
    assert diagnostics["reservation_soft_penalty_raw"] == 0.0
    assert diagnostics["near_neighbor_step_ratio"] == 0.0


def test_single_usv_safe_nav_off_mode_matches_default_runtime() -> None:
    common_kwargs = dict(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        map_height_cells=60,
        map_width_cells=80,
        clue_sigma_m=15.0,
    )
    default_result = run_episode_single_usv_search_knownmap(**common_kwargs)
    explicit_off_result = run_episode_single_usv_search_knownmap(
        **common_kwargs,
        path_safety_mode="off",
    )

    assert explicit_off_result["path_length"] == default_result["path_length"]
    assert explicit_off_result["find_times"] == default_result["find_times"]
    assert explicit_off_result["terminated_reason"] == default_result["terminated_reason"]
    assert explicit_off_result["trace_rows"][0]["viewpoint_cell"] == default_result["trace_rows"][0]["viewpoint_cell"]


def test_single_usv_safe_nav_lambda_zero_matches_off_runtime() -> None:
    common_kwargs = dict(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        map_height_cells=60,
        map_width_cells=80,
        clue_sigma_m=15.0,
    )
    off_result = run_episode_single_usv_search_knownmap(
        **common_kwargs,
        path_safety_mode="off",
    )
    lambda_zero_result = run_episode_single_usv_search_knownmap(
        **common_kwargs,
        path_safety_mode="soft_clearance_astar_v1",
        safe_nav_lambda_clearance=0.0,
    )

    assert lambda_zero_result["path_length"] == off_result["path_length"]
    assert lambda_zero_result["find_times"] == off_result["find_times"]
    assert lambda_zero_result["trace_rows"][0]["viewpoint_cell"] == off_result["trace_rows"][0]["viewpoint_cell"]


def test_single_usv_safe_nav_runtime_exposes_clearance_fields() -> None:
    result = run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled",
        map_kind="harbor_cove",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        map_height_cells=60,
        map_width_cells=80,
        clue_sigma_m=15.0,
        path_safety_mode="soft_clearance_astar_v1",
        safe_nav_lambda_clearance=1.0,
    )

    assert result["path_safety_mode"] == "soft_clearance_astar_v1"
    assert "near_obstacle_step_ratio" in result
    assert "min_clearance_cells_mean" in result
    assert result["trace_rows"]
    first_row = result["trace_rows"][0]
    assert "segment_min_clearance_cells" in first_row
    assert "segment_mean_clearance_cells" in first_row
    assert "clearance_penalty_raw" in first_row
    assert "near_obstacle_step_ratio" in first_row


def test_single_usv_safe_nav_no_path_waits_instead_of_terminating(monkeypatch: pytest.MonkeyPatch) -> None:
    import baseline_GP.marine_knownmap_runtime as knownmap_runtime

    def _always_fail(*args, **kwargs):
        return None, {"path_safety_mode": "soft_clearance_astar_v1"}

    monkeypatch.setattr(knownmap_runtime, "select_knownmap_path_segment_policy", _always_fail)
    result = knownmap_runtime.run_episode_single_usv_search_knownmap(
        episode_seed=0,
        max_iters=3,
        policy_name="marine_knownmap_path_v2_infosampled",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        map_height_cells=60,
        map_width_cells=80,
        clue_sigma_m=15.0,
        path_safety_mode="soft_clearance_astar_v1",
        safe_nav_lambda_clearance=1.0,
    )

    assert result["terminated_reason"] == "max_iters"
    assert result["path_length"] == 0
    assert result["trace_rows"]
    replans = [row for row in result["trace_rows"] if row.get("replanned_this_step")]
    assert replans
    assert all(row["viewpoint_rule"] == "safe_nav_wait_fallback" for row in replans)
