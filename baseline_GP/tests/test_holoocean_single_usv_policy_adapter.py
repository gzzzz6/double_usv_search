"""Static unit tests for single USV search policy adapter."""

from __future__ import annotations

import sys
import os
import pytest
import numpy as np


from baseline_GP.holoocean_bridge.single_usv_policy_adapter import (
    load_openwater_policy_state,
    plan_next_policy_cell,
    finalize_policy_step_after_holoocean,
)




@pytest.fixture
def openwater_npz_path() -> str:
    # Resolve absolute path to maps/openwater_open_v1.npz
    current_dir = os.path.dirname(os.path.abspath(__file__))
    npz_path = os.path.join(
        current_dir, "..", "holoocean_bridge", "maps", "openwater_open_v1.npz"
    )
    return os.path.normpath(npz_path)


def test_load_openwater_policy_state_success(openwater_npz_path: str) -> None:
    """Verify state initialization, (1, 1) starting position constraint, and map integrity."""
    state, config, nav_map = load_openwater_policy_state(openwater_npz_path, episode_seed=0)

    assert state["robot_pos"] == (1, 1)
    assert state["nav_map_prior"].shape == (81, 81)
    assert np.array_equal(state["nav_map_prior"], nav_map)
    assert config.cell_size_m == 5.0
    assert config.origin_world_xy == (-200.0, 200.0)


def test_plan_next_policy_cell_neighbor(openwater_npz_path: str) -> None:
    """Verify that plan_next_policy_cell selects an adjacent cell (4/8 connectivity)."""
    state, config, nav_map = load_openwater_policy_state(openwater_npz_path, episode_seed=0)

    # Trigger a planning step
    next_cell, segment_path, commit_remaining, plan_details = plan_next_policy_cell(
        state=state,
        step=1,
        commit_remaining=0,
        episode_seed=0,
    )

    # Next cell must be one step away from starting position (1, 1)
    dx = abs(next_cell[0] - 1)
    dy = abs(next_cell[1] - 1)
    assert max(dx, dy) <= 1
    assert (dx + dy) > 0  # Robot shouldn't plan to stand still unless constrained
    assert len(segment_path) > 1
    assert segment_path[0] == (1, 1)
    assert segment_path[1] == next_cell


def test_finalize_policy_step_chebyshev_validation(openwater_npz_path: str) -> None:
    """Verify that Chebyshev distance validation strictly triggers ValueErrors when drift limits are breached."""
    state, config, nav_map = load_openwater_policy_state(openwater_npz_path, episode_seed=0)

    robot_pos_before = state["robot_pos"]
    next_cell, segment_path, commit_remaining, plan_details = plan_next_policy_cell(
        state=state,
        step=1,
        commit_remaining=0,
        episode_seed=0,
    )

    # 1. Valid step (projected cell matches next_cell)
    state = finalize_policy_step_after_holoocean(
        state=state,
        step=1,
        robot_pos_before=robot_pos_before,
        next_cell=next_cell,
        final_projected_cell=next_cell,
    )
    assert state["robot_pos"] == next_cell
    assert state["path_length"] == 1
    assert state["trajectory"][-1] == next_cell

    # 2. Invalid step (drift is > 1 cell)
    bad_projected_cell = (next_cell[0] + 2, next_cell[1])
    with pytest.raises(ValueError, match="CRITICAL DRIFT EXCEEDED"):
        finalize_policy_step_after_holoocean(
            state=state,
            step=2,
            robot_pos_before=next_cell,
            next_cell=next_cell,
            final_projected_cell=bad_projected_cell,
        )


def test_load_openwater_policy_state_res10() -> None:
    """Verify loading policy state with res10 NPZ defaults."""
    state, config, nav_map = load_openwater_policy_state(None, episode_seed=0)

    assert state["robot_pos"] == (1, 1)
    assert state["nav_map_prior"].shape == (81, 81)
    assert np.array_equal(state["nav_map_prior"], nav_map)
    assert config.cell_size_m == 10.0
    assert config.origin_world_xy == (-400.0, 400.0)

    # Assert grid scale mappings under 10m grid and 10m params
    assert state["sensor_range_cells"] == 5
    assert state["min_target_separation_cells"] == 6
    assert state["min_start_distance_cells"] == 8
    assert state["gp_length_scale_m"] == 40.0
    assert state["clue_sigma_m"] == 40.0
    assert state["clue_sigma_cells"] == 4
    assert state["resolution_m"] == 10.0

