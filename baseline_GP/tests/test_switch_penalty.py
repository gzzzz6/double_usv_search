from __future__ import annotations

import numpy as np
import pytest

import baseline_GP.core_search_policy as core_search_policy
from baseline_GP.core_map import FREE, UNKNOWN
from baseline_GP.core_switch_penalty import is_u_turn, move_direction, u_turn_penalty_for_path
from baseline_GP.core_search_policy import select_goal_search_policy
from baseline_GP.marine_search_runtime import (
    _compute_alpha_focus,
    _compute_kappa_commit,
    _policy_commit_window,
    _same_anchor_cluster_state,
)
from baseline_GP.runner_single_usv_search import run_episode_single_usv_search


def test_u_turn_penalty_helper_detects_exact_reverse_only() -> None:
    assert move_direction((3, 4), (3, 5)) == (0, 1)
    assert is_u_turn((0, 1), (0, -1))
    assert not is_u_turn((0, 1), (1, 0))
    penalty, applied, first_move_dir = u_turn_penalty_for_path(
        [(3, 4), (3, 3), (3, 2)],
        prev_move_dir=(0, 1),
        lambda_u_turn=2.0,
    )
    assert applied
    assert penalty == 2.0
    assert first_move_dir == (0, -1)


def test_search_trace_exposes_u_turn_penalty_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        lambda_u_turn=2.0,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "u_turn_penalty_term" in row
    assert "u_turn_penalty_applied" in row
    assert "planned_first_move_dir" in row


def test_marine_goal_switch_penalty_can_preserve_current_goal() -> None:
    known_map = np.zeros((12, 12), dtype=int)
    covered_mask = np.zeros_like(known_map, dtype=bool)
    visited_count = np.zeros_like(known_map, dtype=int)
    robot_pos = (3, 3)
    current_goal = (4, 4)
    clue_map = np.zeros_like(known_map, dtype=float)
    staleness_map = np.zeros_like(known_map, dtype=float)
    clue_map[9, 9] = 1.0
    staleness_map[9, 9] = 1.0

    goal_no_penalty, *_ = select_goal_search_policy(
        policy_name="marine_search_fg",
        known_map=known_map,
        robot_pos=robot_pos,
        covered_mask=covered_mask,
        visited_count=visited_count,
        sensor_range=1,
        gp_reward_map=clue_map,
        staleness_map=staleness_map,
        intensity_map=None,
        current_goal=current_goal,
        lambda_switch=0.0,
        top_k_frontier=0,
        top_k_staleness=10,
        top_k_clue=10,
        top_k_intensity=0,
    )
    goal_with_penalty, _, _, details = select_goal_search_policy(
        policy_name="marine_search_fg",
        known_map=known_map,
        robot_pos=robot_pos,
        covered_mask=covered_mask,
        visited_count=visited_count,
        sensor_range=1,
        gp_reward_map=clue_map,
        staleness_map=staleness_map,
        intensity_map=None,
        current_goal=current_goal,
        lambda_switch=9.0,
        top_k_frontier=0,
        top_k_staleness=10,
        top_k_clue=10,
        top_k_intensity=0,
    )

    assert goal_no_penalty != current_goal
    assert goal_with_penalty == current_goal
    assert details["goal_switch_penalty_term"] == 0.0


def test_search_trace_exposes_goal_switch_penalty_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        lambda_switch=2.0,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "goal_switch_penalty_term" in row
    assert "goal_switch_penalty_applied" in row


def test_marine_winner_margin_preserves_current_goal_for_small_score_gap(
    monkeypatch,
) -> None:
    robot_pos = (3, 3)
    current_goal = (4, 4)
    alternative_goal = (8, 8)

    def fake_candidate_space(**kwargs):
        return [current_goal, alternative_goal]

    def fake_a_star_nav(_known_map, _robot_pos, goal, unknown_cost=3):
        return [robot_pos, goal]

    def fake_breakdown(path, *_args, **_kwargs):
        goal = path[-1]
        if goal == current_goal:
            return {
                "frontier_term_raw": 0.0,
                "staleness_term_raw": 0.0,
                "clue_term_raw": 0.0,
                "intensity_term_raw": 0.0,
                "path_cost_term_raw": 0.0,
            }
        return {
            "frontier_term_raw": 1.0,
            "staleness_term_raw": 0.0,
            "clue_term_raw": 0.0,
            "intensity_term_raw": 0.0,
            "path_cost_term_raw": 1.0,
        }

    norm_outputs = iter(
        [
            [0.90, 1.00],  # frontier
            [0.90, 1.00],  # staleness
            [0.90, 1.00],  # clue
            [0.00, 0.00],  # intensity
            [0.00, 0.00],  # anchor value
            [0.00, 0.00],  # anchor depth
            [0.00, 1.00],  # path cost
        ]
    )

    def fake_normalize_term(_values):
        return next(norm_outputs)

    monkeypatch.setattr(core_search_policy, "_marine_candidate_space", fake_candidate_space)
    monkeypatch.setattr(core_search_policy, "a_star_nav", fake_a_star_nav)
    monkeypatch.setattr(core_search_policy, "_marine_path_score_breakdown", fake_breakdown)
    monkeypatch.setattr(core_search_policy, "_normalize_term", fake_normalize_term)

    goal_no_margin, _, _, details_no_margin = select_goal_search_policy(
        policy_name="marine_search_fg",
        known_map=np.zeros((10, 10), dtype=int),
        robot_pos=robot_pos,
        covered_mask=np.zeros((10, 10), dtype=bool),
        visited_count=np.zeros((10, 10), dtype=int),
        sensor_range=1,
        gp_reward_map=np.zeros((10, 10), dtype=float),
        staleness_map=np.zeros((10, 10), dtype=float),
        intensity_map=None,
        current_goal=current_goal,
        lambda_switch=0.0,
        winner_margin=0.0,
        lambda_dist_raw=0.0,
    )

    norm_outputs = iter(
        [
            [0.90, 1.00],
            [0.90, 1.00],
            [0.90, 1.00],
            [0.00, 0.00],
            [0.00, 0.00],
            [0.00, 0.00],
            [0.00, 1.00],
        ]
    )
    monkeypatch.setattr(core_search_policy, "_normalize_term", fake_normalize_term)

    goal_with_margin, _, _, details_with_margin = select_goal_search_policy(
        policy_name="marine_search_fg",
        known_map=np.zeros((10, 10), dtype=int),
        robot_pos=robot_pos,
        covered_mask=np.zeros((10, 10), dtype=bool),
        visited_count=np.zeros((10, 10), dtype=int),
        sensor_range=1,
        gp_reward_map=np.zeros((10, 10), dtype=float),
        staleness_map=np.zeros((10, 10), dtype=float),
        intensity_map=None,
        current_goal=current_goal,
        lambda_switch=0.0,
        winner_margin=1.5,
        lambda_dist_raw=0.0,
    )

    assert goal_no_margin == alternative_goal
    assert not details_no_margin["winner_margin_applied"]
    assert goal_with_margin == current_goal
    assert details_with_margin["winner_margin_applied"]
    assert details_with_margin["winner_margin_term"] == 1.5
    assert details_with_margin["current_goal_score"] == pytest.approx(13.5)
    assert details_with_margin["best_alternative_score"] == pytest.approx(14.7)


def test_search_trace_exposes_winner_margin_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        winner_margin=0.5,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "winner_margin_term" in row
    assert "winner_margin_applied" in row
    assert "current_goal_score" in row
    assert "best_alternative_score" in row


def test_marine_raw_path_length_penalty_can_flip_choice(
    monkeypatch,
) -> None:
    robot_pos = (3, 3)
    short_goal = (4, 4)
    long_goal = (8, 8)

    def fake_candidate_space(**kwargs):
        return [short_goal, long_goal]

    def fake_a_star_nav(_known_map, _robot_pos, goal, unknown_cost=3):
        return [robot_pos, goal]

    def fake_breakdown(path, *_args, **_kwargs):
        goal = path[-1]
        if goal == short_goal:
            return {
                "frontier_term_raw": 0.0,
                "staleness_term_raw": 0.0,
                "clue_term_raw": 0.0,
                "intensity_term_raw": 0.0,
                "path_cost_term_raw": 2.0,
            }
        return {
            "frontier_term_raw": 1.0,
            "staleness_term_raw": 0.0,
            "clue_term_raw": 0.0,
            "intensity_term_raw": 0.0,
            "path_cost_term_raw": 10.0,
        }

    norm_outputs = iter(
        [
            [0.90, 1.00],  # frontier
            [0.90, 1.00],  # staleness
            [0.90, 1.00],  # clue
            [0.00, 0.00],  # intensity
            [0.00, 0.00],  # anchor value
            [0.00, 0.00],  # anchor depth
            [0.00, 0.00],  # path cost norm stays neutral
        ]
    )

    def fake_normalize_term(_values):
        return next(norm_outputs)

    monkeypatch.setattr(core_search_policy, "_marine_candidate_space", fake_candidate_space)
    monkeypatch.setattr(core_search_policy, "a_star_nav", fake_a_star_nav)
    monkeypatch.setattr(core_search_policy, "_marine_path_score_breakdown", fake_breakdown)
    monkeypatch.setattr(core_search_policy, "_normalize_term", fake_normalize_term)

    goal_no_raw_penalty, _, _, details_no_raw_penalty = select_goal_search_policy(
        policy_name="marine_search_fg",
        known_map=np.zeros((10, 10), dtype=int),
        robot_pos=robot_pos,
        covered_mask=np.zeros((10, 10), dtype=bool),
        visited_count=np.zeros((10, 10), dtype=int),
        sensor_range=1,
        gp_reward_map=np.zeros((10, 10), dtype=float),
        staleness_map=np.zeros((10, 10), dtype=float),
        intensity_map=None,
        lambda_switch=0.0,
        winner_margin=0.0,
        lambda_dist_raw=0.0,
    )

    norm_outputs = iter(
        [
            [0.90, 1.00],
            [0.90, 1.00],
            [0.90, 1.00],
            [0.00, 0.00],
            [0.00, 0.00],
            [0.00, 0.00],
            [0.00, 0.00],
        ]
    )
    monkeypatch.setattr(core_search_policy, "_normalize_term", fake_normalize_term)

    goal_with_raw_penalty, _, _, details_with_raw_penalty = select_goal_search_policy(
        policy_name="marine_search_fg",
        known_map=np.zeros((10, 10), dtype=int),
        robot_pos=robot_pos,
        covered_mask=np.zeros((10, 10), dtype=bool),
        visited_count=np.zeros((10, 10), dtype=int),
        sensor_range=1,
        gp_reward_map=np.zeros((10, 10), dtype=float),
        staleness_map=np.zeros((10, 10), dtype=float),
        intensity_map=None,
        lambda_switch=0.0,
        winner_margin=0.0,
        lambda_dist_raw=0.2,
    )

    assert goal_no_raw_penalty == long_goal
    assert details_no_raw_penalty["raw_path_length_penalty_term"] == 0.0
    assert goal_with_raw_penalty == short_goal
    assert details_with_raw_penalty["raw_path_length_penalty_term"] == pytest.approx(0.4)


def test_search_trace_exposes_raw_path_length_penalty_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        lambda_dist_raw=0.05,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "raw_path_length_penalty_term" in row


def test_policy_commit_window_scales_search_with_path_length() -> None:
    short_commit, short_policy = _policy_commit_window(
        policy_name="marine_search_fg",
        current_mode="SEARCH",
        commit_window=5,
        search_commit_window=5,
        reacquire_commit_window=3,
        planned_path_length=6,
        search_commit_max_window=12,
        search_commit_path_divisor=2,
    )
    long_commit, long_policy = _policy_commit_window(
        policy_name="marine_search_fg",
        current_mode="SEARCH",
        commit_window=5,
        search_commit_window=5,
        reacquire_commit_window=3,
        planned_path_length=20,
        search_commit_max_window=12,
        search_commit_path_divisor=2,
    )
    reacquire_commit, reacquire_policy = _policy_commit_window(
        policy_name="marine_two_stage",
        current_mode="REACQUIRE",
        commit_window=5,
        search_commit_window=5,
        reacquire_commit_window=3,
        planned_path_length=20,
        search_commit_max_window=12,
        search_commit_path_divisor=2,
    )

    assert short_commit == 5
    assert short_policy == "adaptive_search"
    assert long_commit == 10
    assert long_policy == "adaptive_search"
    assert reacquire_commit == 3
    assert reacquire_policy == "fixed_reacquire"


def test_search_trace_exposes_adaptive_commit_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        search_commit_window=5,
        search_commit_max_window=12,
        search_commit_path_divisor=2,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "planned_commit_window" in row
    assert "commit_policy" in row
    assert "planned_path_length" in row


def test_marine_soft_weights_endpoints() -> None:
    explore = core_search_policy._marine_soft_weights(0.0)
    focus = core_search_policy._marine_soft_weights(1.0)

    assert explore["frontier_term_norm"] == pytest.approx(6.0)
    assert explore["staleness_term_norm"] == pytest.approx(5.0)
    assert explore["clue_term_norm"] == pytest.approx(0.0)
    assert explore["intensity_term_norm"] == pytest.approx(0.0)
    assert focus["frontier_term_norm"] == pytest.approx(0.0)
    assert focus["staleness_term_norm"] == pytest.approx(0.0)
    assert focus["clue_term_norm"] == pytest.approx(4.0)
    assert focus["intensity_term_norm"] == pytest.approx(8.0)


def test_same_anchor_cluster_state_requires_same_source_and_close_centroid() -> None:
    assert _same_anchor_cluster_state("clue", (5, 5), "clue", (6, 6), sensor_range=6)
    assert not _same_anchor_cluster_state("clue", (5, 5), "intensity", (6, 6), sensor_range=6)
    assert not _same_anchor_cluster_state("frontier", (5, 5), "frontier", (6, 6), sensor_range=6)
    assert not _same_anchor_cluster_state("clue", (5, 5), "clue", (12, 12), sensor_range=6)


def test_compute_alpha_focus_increases_for_recent_detection_and_concentrated_intensity() -> None:
    known_map = np.zeros((10, 10), dtype=int)
    concentrated = np.zeros((10, 10), dtype=float)
    concentrated[5, 5] = 2.0

    base_state = {
        "same_anchor_steps": 8,
        "last_anchor_source": "clue",
        "intensity_enabled": True,
        "recent_gateway_drifts": [0.1, 0.2],
        "time_since_last_detection": 0,
        "recent_unknown_openings": [0.0] * 10,
    }
    stale_state = dict(base_state)
    stale_state["time_since_last_detection"] = 20
    diffuse = np.zeros((10, 10), dtype=float)

    focused = _compute_alpha_focus(base_state, concentrated, known_map, sensor_range=5)
    stale = _compute_alpha_focus(stale_state, diffuse, known_map, sensor_range=5)

    assert 0.0 <= focused <= 1.0
    assert 0.0 <= stale <= 1.0
    assert focused > stale


def test_compute_kappa_commit_rewards_stability_and_execution() -> None:
    stable_state = {
        "same_anchor_steps": 10,
        "steps_since_replan": 8,
        "last_planned_path_length": 10,
        "recent_goal_flips": [0.0, 0.0, 0.0],
        "recent_gateway_drifts": [0.1, 0.0],
    }
    unstable_state = {
        "same_anchor_steps": 1,
        "steps_since_replan": 1,
        "last_planned_path_length": 10,
        "recent_goal_flips": [1.0, 1.0, 1.0],
        "recent_gateway_drifts": [1.0, 0.8],
    }

    stable = _compute_kappa_commit(stable_state)
    unstable = _compute_kappa_commit(unstable_state)

    assert 0.0 <= stable <= 1.0
    assert 0.0 <= unstable <= 1.0
    assert stable > unstable


def test_marine_search_soft_uses_anchor_retention_bonus(monkeypatch) -> None:
    robot_pos = (3, 3)
    current_goal = (4, 4)

    same_anchor = {
        "anchor_cell": (6, 6),
        "gateway_cell": (4, 4),
        "anchor_source": "clue",
        "anchor_state": "UNKNOWN",
        "gateway_rule": "last_free_before_unknown",
        "path_to_anchor": [(3, 3), (4, 4), (5, 5), (6, 6)],
        "path_to_gateway": [(3, 3), (4, 4)],
        "anchor_value": 1.0,
        "anchor_cluster_size": 4,
        "anchor_cluster_peak": 1.0,
        "anchor_cluster_mean": 0.8,
        "anchor_centroid_cell": (6, 6),
        "is_current_goal": False,
        "is_current_anchor": False,
    }
    different_anchor = {
        "anchor_cell": (8, 8),
        "gateway_cell": (5, 4),
        "anchor_source": "clue",
        "anchor_state": "UNKNOWN",
        "gateway_rule": "last_free_before_unknown",
        "path_to_anchor": [(3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8)],
        "path_to_gateway": [(3, 3), (4, 4), (5, 4)],
        "anchor_value": 1.0,
        "anchor_cluster_size": 5,
        "anchor_cluster_peak": 1.0,
        "anchor_cluster_mean": 0.8,
        "anchor_centroid_cell": (8, 8),
        "is_current_goal": False,
        "is_current_anchor": False,
    }

    monkeypatch.setattr(
        core_search_policy,
        "_marine_candidate_space",
        lambda **kwargs: [same_anchor, different_anchor],
    )
    monkeypatch.setattr(
        core_search_policy,
        "_marine_path_score_breakdown",
        lambda *args, **kwargs: {
            "frontier_term_raw": 0.0,
            "staleness_term_raw": 0.0,
            "clue_term_raw": 0.0,
            "intensity_term_raw": 0.0,
            "path_cost_term_raw": 0.0,
        },
    )

    goal, _, _, details = select_goal_search_policy(
        policy_name="marine_search_soft",
        known_map=np.zeros((10, 10), dtype=int),
        robot_pos=robot_pos,
        covered_mask=np.zeros((10, 10), dtype=bool),
        visited_count=np.zeros((10, 10), dtype=int),
        sensor_range=6,
        gp_reward_map=np.zeros((10, 10), dtype=float),
        staleness_map=np.zeros((10, 10), dtype=float),
        intensity_map=np.zeros((10, 10), dtype=float),
        current_goal=current_goal,
        current_anchor=(6, 6),
        current_anchor_source="clue",
        current_anchor_centroid=(6, 6),
        kappa_commit=1.0,
        winner_margin=0.0,
        lambda_dist_raw=0.0,
    )

    assert goal == (4, 4)
    assert details["same_anchor_cluster"]
    assert details["retain_anchor_bonus"] == pytest.approx(1.5)
    assert details["gateway_continuity_bonus"] > 1.0


def test_policy_commit_window_uses_soft_search_commit() -> None:
    commit_steps, commit_policy = _policy_commit_window(
        policy_name="marine_search_soft",
        current_mode="SEARCH",
        commit_window=5,
        search_commit_window=5,
        reacquire_commit_window=3,
        planned_path_length=10,
        search_commit_max_window=12,
        search_commit_path_divisor=2,
        kappa_commit=0.75,
    )

    assert commit_steps == 8
    assert commit_policy == "adaptive_soft_search"


def test_anchor_unknown_candidate_extracts_last_free_gateway() -> None:
    known_map = np.full((7, 7), UNKNOWN, dtype=int)
    known_map[3, 1] = FREE
    known_map[3, 2] = FREE
    known_map[3, 3] = FREE
    frontier_set = set(core_search_policy.find_frontiers(known_map))

    candidate = core_search_policy._anchor_gateway_candidate(
        anchor_cell=(3, 5),
        anchor_source="clue",
        anchor_value=1.0,
        known_map=known_map,
        robot_pos=(3, 1),
        frontier_set=frontier_set,
        unknown_cost=3,
    )

    assert candidate is not None
    assert candidate["anchor_state"] == "UNKNOWN"
    assert candidate["gateway_cell"] == (3, 3)
    assert candidate["gateway_rule"] == "last_free_before_unknown"
    assert candidate["path_to_gateway"][-1] == (3, 3)
    assert known_map[candidate["gateway_cell"]] == FREE


def test_anchor_free_candidate_keeps_anchor_as_gateway() -> None:
    known_map = np.full((7, 7), UNKNOWN, dtype=int)
    known_map[3, 1:6] = FREE
    frontier_set = set(core_search_policy.find_frontiers(known_map))

    candidate = core_search_policy._anchor_gateway_candidate(
        anchor_cell=(3, 5),
        anchor_source="staleness",
        anchor_value=0.8,
        known_map=known_map,
        robot_pos=(3, 1),
        frontier_set=frontier_set,
        unknown_cost=3,
    )

    assert candidate is not None
    assert candidate["anchor_state"] == "FREE"
    assert candidate["gateway_cell"] == (3, 5)
    assert candidate["gateway_rule"] == "anchor_is_free"


def test_anchor_candidate_falls_back_to_first_frontier_on_path() -> None:
    known_map = np.full((7, 7), UNKNOWN, dtype=int)
    known_map[3, 1] = FREE
    known_map[3, 5] = FREE
    frontier_set = set(core_search_policy.find_frontiers(known_map))

    candidate = core_search_policy._anchor_gateway_candidate(
        anchor_cell=(3, 5),
        anchor_source="intensity",
        anchor_value=0.6,
        known_map=known_map,
        robot_pos=(3, 1),
        frontier_set=frontier_set,
        unknown_cost=3,
    )

    assert candidate is not None
    assert candidate["gateway_cell"] == (3, 5)
    assert candidate["gateway_rule"] == "direct_frontier"


def test_cluster_hotspots_prefers_center_of_flat_high_value_block() -> None:
    score_map = np.zeros((10, 10), dtype=float)
    score_map[3:7, 4:8] = 1.0
    candidate_mask = np.ones_like(score_map, dtype=bool)

    clusters = core_search_policy._cluster_hotspots(
        score_map,
        candidate_mask,
        top_k=1,
    )

    assert len(clusters) == 1
    anchor_cell = clusters[0]["anchor_cell"]
    assert anchor_cell in {(4, 5), (4, 6), (5, 5), (5, 6)}
    assert anchor_cell not in {(3, 4), (3, 7), (6, 4), (6, 7)}
    assert clusters[0]["anchor_centroid_cell"] == (4, 6)
    assert clusters[0]["anchor_cluster_size"] == 16


def test_cluster_hotspots_returns_separate_components() -> None:
    score_map = np.zeros((12, 12), dtype=float)
    score_map[2:5, 2:5] = 1.0
    score_map[7:10, 8:11] = 0.95
    candidate_mask = np.ones_like(score_map, dtype=bool)

    clusters = core_search_policy._cluster_hotspots(
        score_map,
        candidate_mask,
        top_k=2,
    )

    assert len(clusters) == 2
    anchors = {tuple(cluster["anchor_cell"]) for cluster in clusters}
    assert any(cell in anchors for cell in {(3, 3), (3, 4), (4, 3), (4, 4)})
    assert any(cell in anchors for cell in {(8, 9), (8, 10), (9, 9), (9, 10)})


def test_search_candidate_weak_dedupe_prefers_higher_anchor_value_with_same_source() -> None:
    lower_value = {
        "anchor_cell": (2, 5),
        "gateway_cell": (2, 3),
        "anchor_source": "clue",
        "anchor_state": "UNKNOWN",
        "gateway_rule": "last_free_before_unknown",
        "path_to_anchor": None,
        "path_to_gateway": None,
        "anchor_value": 0.4,
        "is_current_goal": False,
        "is_current_anchor": False,
    }
    higher_value = {
        "anchor_cell": (4, 5),
        "gateway_cell": (2, 3),
        "anchor_source": "clue",
        "anchor_state": "UNKNOWN",
        "gateway_rule": "last_free_before_unknown",
        "path_to_anchor": None,
        "path_to_gateway": None,
        "anchor_value": 0.9,
        "is_current_goal": False,
        "is_current_anchor": False,
    }

    deduped = core_search_policy._dedupe_search_candidates([lower_value, higher_value])

    assert len(deduped) == 1
    assert deduped[0]["anchor_cell"] == (4, 5)


def test_search_candidate_weak_dedupe_prefers_unknown_anchor_over_direct_frontier() -> None:
    direct_frontier = {
        "anchor_cell": (2, 3),
        "gateway_cell": (2, 3),
        "anchor_source": "frontier",
        "anchor_state": "FREE",
        "gateway_rule": "direct_frontier",
        "path_to_anchor": None,
        "path_to_gateway": None,
        "anchor_value": 25.0,
        "is_current_goal": False,
        "is_current_anchor": False,
    }
    unknown_anchor = {
        "anchor_cell": (2, 5),
        "gateway_cell": (2, 3),
        "anchor_source": "clue",
        "anchor_state": "UNKNOWN",
        "gateway_rule": "last_free_before_unknown",
        "path_to_anchor": [(2, 1), (2, 2), (2, 3), (2, 4), (2, 5)],
        "path_to_gateway": [(2, 1), (2, 2), (2, 3)],
        "anchor_value": 0.2,
        "is_current_goal": False,
        "is_current_anchor": False,
    }

    deduped = core_search_policy._dedupe_search_candidates([direct_frontier, unknown_anchor])

    assert len(deduped) == 1
    assert deduped[0]["anchor_cell"] == (2, 5)
    assert deduped[0]["gateway_cell"] == (2, 3)
    assert deduped[0]["anchor_state"] == "UNKNOWN"


def test_search_trace_exposes_anchor_gateway_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "anchor_cell" in row
    assert "anchor_source" in row
    assert "anchor_state" in row
    assert "gateway_rule" in row
    assert "anchor_path_length" in row
    assert "gateway_path_length" in row
    assert "anchor_cluster_size" in row
    assert "anchor_cluster_peak" in row
    assert "anchor_cluster_mean" in row
    assert "anchor_centroid_cell" in row


def test_marine_search_soft_smoke_exposes_soft_trace_fields() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=8,
        policy_name="marine_search_soft",
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=3,
        mode_switch_policy="two_stage",
        clue_samples_per_step=6,
        gp_max_points=32,
    )

    assert result["mode_switch_count"] == 0
    assert result["mode_history"]
    assert set(result["mode_history"]) == {"SEARCH"}
    assert len(result["alpha_focus_curve"]) == result["completed_steps"]
    assert len(result["kappa_commit_curve"]) == result["completed_steps"]
    assert result["trace_rows"]
    row = result["trace_rows"][0]
    assert "alpha_focus" in row
    assert "kappa_commit" in row
    assert "same_anchor_cluster" in row
    assert "gateway_drift_norm" in row
    assert "retain_anchor_bonus" in row
    assert "gateway_continuity_bonus" in row
    assert "anchor_value_term_raw" in row
    assert "anchor_value_term_norm" in row
    assert "anchor_depth_term_raw" in row
    assert "anchor_depth_term_norm" in row
    assert "collision_this_step" in row
    assert "collision_cell" in row
    assert "opened_unknown_count" in row
    assert "online_known_free_ratio" in row
    assert "coverage_rate" not in row
