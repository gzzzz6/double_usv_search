from __future__ import annotations

import pytest

from baseline_GP.runner_single_usv_search import (
    run_episode_single_usv_search,
    summarize_marine_policy_comparison,
)
from baseline_GP.runner_two_usv_search import run_episode_two_usv_search_knownmap


@pytest.mark.parametrize("policy_name", ["frontier_coverage", "gp_assisted_frontier"])
def test_legacy_policies_still_run(policy_name: str) -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=10,
        policy_name=policy_name,
        map_kind="open_water",
        n_targets=2,
        target_count_upper_bound=2,
        clue_samples_per_step=8,
        gp_max_points=64,
    )
    assert result["policy_name"] == policy_name
    assert result["completed_steps"] <= 10
    assert len(result["trace_rows"]) == result["completed_steps"]


def test_marine_search_fg_smoke() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=10,
        policy_name="marine_search_fg",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=8,
        gp_max_points=64,
    )
    assert result["policy_name"] == "marine_search_fg"
    assert len(result["trace_rows"]) == result["completed_steps"]
    assert len(result["mode_history"]) == result["completed_steps"]
    assert "eval_free_coverage_rate" in result
    assert "online_known_free_ratio_final" in result
    assert "coverage_rate" not in result
    assert "mean_gp_uncertainty" not in result
    assert "mean_gp_reward" not in result


def test_marine_search_intensity_smoke() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=10,
        policy_name="marine_search_intensity",
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="random_walk",
        target_count_upper_bound=3,
        clue_samples_per_step=8,
        gp_max_points=64,
    )
    assert result["policy_name"] == "marine_search_intensity"
    assert len(result["remaining_intensity_mass_curve"]) == result["completed_steps"] + 1
    assert len(result["peak_intensity_ratio_curve"]) == result["completed_steps"] + 1


def test_marine_two_stage_smoke() -> None:
    result = run_episode_single_usv_search(
        episode_seed=0,
        max_iters=10,
        policy_name="marine_two_stage",
        map_kind="harbor_cove",
        n_targets=2,
        target_motion_mode="random_walk",
        target_count_upper_bound=3,
        clue_samples_per_step=8,
        gp_max_points=64,
    )
    assert result["policy_name"] == "marine_two_stage"
    assert len(result["mode_history"]) == result["completed_steps"]
    assert set(result["mode_history"]).issubset({"SEARCH", "REACQUIRE"})


def test_marine_policy_comparison_summary_smoke() -> None:
    common_kwargs = dict(
        episode_seed=0,
        max_iters=8,
        map_kind="open_water",
        n_targets=2,
        target_motion_mode="random_walk",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
    )
    results_by_policy = {
        "marine_two_stage": [
            run_episode_single_usv_search(policy_name="marine_two_stage", **common_kwargs)
        ],
        "marine_search_soft": [
            run_episode_single_usv_search(policy_name="marine_search_soft", **common_kwargs)
        ],
    }

    summary = summarize_marine_policy_comparison(results_by_policy)

    assert summary["baseline_policy"] == "marine_two_stage"
    assert summary["challenger_policy"] == "marine_search_soft"
    assert summary["n_episodes"] == 1
    assert "switch_count_delta_mean" in summary["paired_delta_summary"]
    assert "eval_free_coverage_rate_mean" in summary["baseline_summary"]
    assert "online_known_free_ratio_final_mean" in summary["baseline_summary"]
    assert "fraction_of_path_executed_before_replan_mean" in summary["challenger_summary"]
    assert len(summary["paired_episode_rows"]) == 1


def test_two_usv_knownmap_runner_smoke() -> None:
    result = run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=4,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
    )

    assert result["policy_name"] == "marine_knownmap_path_v2_infosampled_2usv"
    assert result["n_usvs"] == 2
    assert len(result["team_trace_rows"]) == result["completed_steps"]
