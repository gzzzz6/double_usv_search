from __future__ import annotations

import inspect
import json

import matplotlib
import numpy as np

from baseline_GP.core_intensity import remaining_intensity_mass
from baseline_GP.core_nav import a_star_nav
from baseline_GP.marine_knownmap_runtime_2usv import (
    KNOWNMAP_EXPERIMENT_2USV_CONTRACT_PATH,
    SUPPORTED_TWO_USV_KNOWNMAP_POLICIES,
    _assign_two_usv_segments_independent,
    _init_two_usv_knownmap_state,
    _joint_assign_two_usv_segments,
    _resolve_execution_conflict,
    load_knownmap_experiment_contract_2usv,
    run_episode_two_usv_search_knownmap,
    run_evaluation_two_usv_search_knownmap,
)
from baseline_GP.core_search_policy import select_knownmap_path_segment_policy
from baseline_GP.viz_search import _draw_team_main_map, plot_team_search_state
from baseline_GP.core_map import FREE, OCCUPIED


def test_two_usv_knownmap_init_uses_shared_world_state() -> None:
    state = _init_two_usv_knownmap_state(
        episode_seed=0,
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

    assert state["nav_map_prior"].shape == (60, 80)
    assert len(state["usv_states"]) == 2
    assert state["usv_states"][0]["robot_pos"] != state["usv_states"][1]["robot_pos"]
    assert state["usv_states"][0]["robot_pos"] == (25, 2)
    assert state["usv_states"][1]["robot_pos"] == (35, 2)
    assert state["gp_field"].n_obs > 0
    assert np.array_equal(state["gp_clue_planner_map"], state["gp_acq_map"])
    assert "responsibility_owner_map" in state
    assert "responsibility_score_map" in state
    assert "buffer_band_mask" in state
    for local in state["usv_states"]:
        assert state["last_seen_step"][local["robot_pos"]] == 0


def test_two_usv_init_intensity_tracks_remaining_target_count_not_upper_bound() -> None:
    state = _init_two_usv_knownmap_state(
        episode_seed=0,
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

    expected_remaining = float(state["target_positions"].shape[0] - int(np.sum(state["found_mask"])))
    assert np.isclose(remaining_intensity_mass(state["intensity_map"]), expected_remaining)


def test_two_usv_responsibility_maps_follow_fixed_starts_and_buffer_band() -> None:
    state = _init_two_usv_knownmap_state(
        episode_seed=0,
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

    owner_map = np.asarray(state["responsibility_owner_map"], dtype=int)
    score_map_0 = np.asarray(state["responsibility_score_map"][0], dtype=float)
    score_map_1 = np.asarray(state["responsibility_score_map"][1], dtype=float)
    buffer_band_mask = np.asarray(state["buffer_band_mask"], dtype=bool)

    assert owner_map.shape == (60, 80)
    assert score_map_0.shape == (60, 80)
    assert score_map_1.shape == (60, 80)
    assert owner_map[(25, 2)] == 0
    assert owner_map[(35, 2)] == 1
    assert owner_map[(15, 2)] == 0
    assert owner_map[(45, 2)] == 1
    assert bool(buffer_band_mask[(30, 2)])
    assert score_map_0[(25, 2)] > 0.0
    assert score_map_1[(35, 2)] > 0.0
    assert score_map_0[(45, 2)] < 0.0
    assert score_map_0[(30, 2)] == 0.0
    occ_mask = state["nav_map_prior"] == OCCUPIED
    assert np.all(owner_map[occ_mask] == -1)
    assert np.all(score_map_0[occ_mask] == 0.0)
    assert np.all(score_map_1[occ_mask] == 0.0)


def test_two_usv_target_placement_respects_both_start_positions() -> None:
    state = _init_two_usv_knownmap_state(
        episode_seed=0,
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

    start_positions = [tuple(int(v) for v in local["robot_pos"]) for local in state["usv_states"]]
    actual_min_distance = min(
        float(np.hypot(int(target[0]) - sx, int(target[1]) - sy))
        for target in state["target_positions"]
        for sx, sy in start_positions
    )

    assert actual_min_distance >= 8.0 - 1e-9
    assert float(state["actual_min_start_distance_cells"]) >= 8.0 - 1e-9


def test_two_usv_conflict_resolution_waits_both_on_swap() -> None:
    team_state = {
        "usv_states": [
            {"usv_id": 0, "robot_pos": (2, 2), "commit_remaining": 3},
            {"usv_id": 1, "robot_pos": (2, 3), "commit_remaining": 2},
        ]
    }
    assignments = {
        0: {"segment_path": [(2, 2), (2, 3)], "adjusted_total_score": 5.0},
        1: {"segment_path": [(2, 3), (2, 2)], "adjusted_total_score": 4.0},
    }

    wait_map, conflict_type, conflict_penalty = _resolve_execution_conflict(team_state, assignments)

    assert conflict_type == "swap"
    assert wait_map == {0: True, 1: True}
    assert conflict_penalty > 0.0


def test_two_usv_responsibility_prior_can_cross_region_without_feasibility_gate() -> None:
    state = _init_two_usv_knownmap_state(
        episode_seed=0,
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
    state["search_info_map"] = np.zeros_like(state["search_info_map"], dtype=float)
    state["search_info_map"][44:47, 16:19] = np.asarray(
        [[4.5, 5.0, 4.2], [5.2, 6.0, 5.1], [4.3, 5.1, 4.4]],
        dtype=float,
    )
    state["search_info_map"][50:53, 24:27] = np.asarray(
        [[4.2, 4.8, 4.1], [4.9, 5.5, 4.7], [4.1, 4.6, 4.0]],
        dtype=float,
    )
    state["search_info_clue_component_map"] = np.asarray(state["search_info_map"], dtype=float)
    state["search_info_intensity_component_map"] = np.zeros_like(state["search_info_map"], dtype=float)
    state["lambda_u_turn"] = 2.0
    state["gamma"] = 0.95
    state["segment_horizon"] = 8
    state["top_k_anchors"] = 6
    state["viewpoints_per_anchor"] = 6
    state["infosampled_inspected_limit_multiplier"] = 3.0
    state["infosampled_inspected_limit_floor"] = 4

    assignments, joint_summary = _joint_assign_two_usv_segments(
        team_state=state,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        predicted_intensity=np.zeros_like(state["intensity_map"], dtype=float),
        step=1,
    )

    assert joint_summary["cross_region_count"] >= 1
    assert any(bool(item["cross_region_selected"]) for item in assignments.values())
    assert all(float(item["responsibility_regularizer"]) == 0.0 for item in assignments.values())
    assert any(
        abs(float(item["responsibility_visible_mean"])) > 0.0
        for item in assignments.values()
    )


def test_two_usv_responsibility_does_not_enter_feasibility_codepaths() -> None:
    assert "responsibility" not in inspect.getsource(a_star_nav)
    selector_source = inspect.getsource(select_knownmap_path_segment_policy)
    assert "responsibility" not in selector_source
    assert "region_feasibility" not in selector_source
    assert "forbid_cross_region" not in selector_source


def test_two_usv_knownmap_episode_smoke() -> None:
    result = run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=8,
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
    assert result["completed_steps"] <= 8
    assert len(result["team_trace_rows"]) == result["completed_steps"]
    assert len(result["trace_rows"]) == 2 * result["completed_steps"]
    assert result["map_height_cells"] == 60
    assert result["map_width_cells"] == 80
    assert "cross_region_assignment_ratio" in result
    assert "wait_count_total" in result
    assert "wait_count_by_usv" in result
    assert result["trace_rows"]
    assert result["team_trace_rows"]
    first_trace = result["trace_rows"][0]
    first_team_trace = result["team_trace_rows"][0]
    assert "cross_region_selected" in first_trace
    assert "selected_in_buffer_band" in first_trace
    assert "responsibility_regularizer_term" in first_trace
    assert first_trace["responsibility_regularizer_term"] == 0.0
    assert "cross_region_count" in first_team_trace
    assert "responsibility_regularizer_0" in first_team_trace
    assert first_team_trace["responsibility_regularizer_0"] == 0.0
    assert first_team_trace["responsibility_regularizer_1"] == 0.0


def test_two_usv_default_off_modes_match_explicit_off_runtime() -> None:
    common_kwargs = dict(
        episode_seed=0,
        max_iters=6,
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
    default_result = run_episode_two_usv_search_knownmap(**common_kwargs)
    explicit_off_result = run_episode_two_usv_search_knownmap(
        **common_kwargs,
        path_safety_mode="off",
        team_path_avoidance_mode="off",
    )

    assert explicit_off_result["path_length_total"] == default_result["path_length_total"]
    assert explicit_off_result["find_times"] == default_result["find_times"]
    assert explicit_off_result["terminated_reason"] == default_result["terminated_reason"]
    assert (
        explicit_off_result["trace_rows"][0]["viewpoint_cell"]
        == default_result["trace_rows"][0]["viewpoint_cell"]
    )


def test_two_usv_coordinated_reservation_v1_episode_smoke() -> None:
    result = run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        assignment_mode="coordinated",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        path_safety_mode="soft_clearance_astar_v1",
        team_path_avoidance_mode="reservation_v1",
    )

    assert result["team_path_avoidance_mode"] == "reservation_v1"
    assert result["path_safety_mode"] == "soft_clearance_astar_v1"
    assert result["completed_steps"] <= 6
    assert result["trace_rows"]
    assert result["team_trace_rows"]
    first_trace = result["trace_rows"][0]
    first_team_trace = result["team_trace_rows"][0]
    assert "team_path_avoidance_mode" in first_trace
    assert "reservation_priority_rank" in first_trace
    assert "reservation_soft_penalty_raw" in first_trace
    assert "reservation_same_cell_violation" in first_trace
    assert "reservation_priority_order" in first_team_trace
    assert "reservation_wait_fallback_count" in first_team_trace


def test_two_usv_independent_reservation_v1_keeps_viewpoint_selection_semantics() -> None:
    init_kwargs = dict(
        episode_seed=0,
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
        path_safety_mode="soft_clearance_astar_v1",
    )
    state_off = _init_two_usv_knownmap_state(**init_kwargs, team_path_avoidance_mode="off")
    state_on = _init_two_usv_knownmap_state(
        **init_kwargs,
        team_path_avoidance_mode="reservation_v1",
    )
    for state in (state_off, state_on):
        state["lambda_u_turn"] = 2.0
        state["gamma"] = 0.95
        state["segment_horizon"] = 8
        state["top_k_anchors"] = 6
        state["viewpoints_per_anchor"] = 6
        state["infosampled_inspected_limit_multiplier"] = 3.0
        state["infosampled_inspected_limit_floor"] = 4

    predicted_off = np.asarray(state_off["intensity_map"], dtype=float)
    predicted_on = np.asarray(state_on["intensity_map"], dtype=float)
    assignment_off, _ = _assign_two_usv_segments_independent(
        team_state=state_off,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        predicted_intensity=predicted_off,
        step=1,
    )
    assignment_on, summary_on = _assign_two_usv_segments_independent(
        team_state=state_on,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        predicted_intensity=predicted_on,
        step=1,
    )

    assert assignment_on[0]["plan_details"]["viewpoint_cell"] == assignment_off[0]["plan_details"]["viewpoint_cell"]
    assert assignment_on[1]["plan_details"]["viewpoint_cell"] == assignment_off[1]["plan_details"]["viewpoint_cell"]
    assert summary_on["team_path_avoidance_mode"] == "reservation_v1"
    assert summary_on["reservation_priority_order"] is not None
    assert {
        int(assignment_on[usv_id]["plan_details"].get("reservation_priority_rank", -1))
        for usv_id in (0, 1)
    } == {0, 1}


def test_two_usv_independent_reroute_failure_waits_instead_of_terminating(
    monkeypatch,
) -> None:
    import baseline_GP.marine_knownmap_runtime_2usv as runtime_2usv

    def _always_fail_reroute(*args, **kwargs):
        return None, {}

    def _force_reroute(*args, **kwargs):
        return {
            "same_cell_violation": False,
            "swap_violation": False,
            "near_neighbor_step_ratio": 1.0,
            "reservation_soft_penalty_raw": 1.0,
        }

    monkeypatch.setattr(runtime_2usv, "rebuild_knownmap_segment_to_fixed_viewpoint", _always_fail_reroute)
    monkeypatch.setattr(runtime_2usv, "evaluate_path_against_reservation", _force_reroute)
    result = runtime_2usv.run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=3,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        assignment_mode="independent",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        path_safety_mode="soft_clearance_astar_v1",
        team_path_avoidance_mode="reservation_v1",
    )

    assert result["terminated_reason"] == "max_iters"
    assert result["trace_rows"]
    assert any(
        row.get("viewpoint_rule") == "fixed_viewpoint_wait_fallback"
        for row in result["trace_rows"]
    )


def test_two_usv_coordinated_all_candidate_fail_falls_back_to_wait(
    monkeypatch,
) -> None:
    import baseline_GP.marine_knownmap_runtime_2usv as runtime_2usv

    def _always_fail_selector(*args, **kwargs):
        return None, {}

    def _always_fail_reroute(*args, **kwargs):
        return None, {}

    monkeypatch.setattr(runtime_2usv, "select_knownmap_path_segment_policy", _always_fail_selector)
    monkeypatch.setattr(runtime_2usv, "rebuild_knownmap_segment_to_fixed_viewpoint", _always_fail_reroute)
    result = runtime_2usv.run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=3,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        assignment_mode="coordinated",
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        path_safety_mode="soft_clearance_astar_v1",
        team_path_avoidance_mode="reservation_v1",
    )

    assert result["terminated_reason"] == "max_iters"
    assert result["trace_rows"]
    assert any(
        row.get("viewpoint_rule")
        in {"hold_position", "team_reservation_wait_fallback", "fixed_viewpoint_wait_fallback"}
        for row in result["trace_rows"]
    )


def test_two_usv_anomaly_upper_tail_episode_smoke() -> None:
    result = run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
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
    if result["trace_rows"]:
        first_trace = result["trace_rows"][0]
        assert "selected_in_anomaly_top_band" in first_trace
        assert "anomaly_viewpoint_prob" in first_trace
        assert "anomaly_visible_mean" in first_trace
    if result["team_trace_rows"]:
        first_team_trace = result["team_trace_rows"][0]
        assert first_team_trace["clue_acquisition_mode"] == "anomaly_upper_tail"


def test_two_usv_conditional_anomaly_episode_smoke() -> None:
    result = run_episode_two_usv_search_knownmap(
        episode_seed=0,
        max_iters=6,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
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
    if result["team_trace_rows"]:
        first_team_trace = result["team_trace_rows"][0]
        assert first_team_trace["clue_acquisition_mode"] == "ucb_anomaly_conditional"
        assert "anomaly_conditional_alpha" in first_team_trace
        assert "anomaly_gate_reason" in first_team_trace
    if result["trace_rows"]:
        first_trace = result["trace_rows"][0]
        assert "anomaly_conditional_alpha" in first_trace
        assert "anomaly_gate_reason" in first_trace


def test_two_usv_knownmap_eval_smoke() -> None:
    assert "marine_knownmap_path_v2_infosampled_2usv" in SUPPORTED_TWO_USV_KNOWNMAP_POLICIES

    results = run_evaluation_two_usv_search_knownmap(
        n_episodes=1,
        max_iters=4,
        policy_names=("marine_knownmap_path_v2_infosampled_2usv",),
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        save_artifacts=False,
    )

    result = results["marine_knownmap_path_v2_infosampled_2usv"][0]
    assert result["n_usvs"] == 2
    assert result["planning_time_ms_mean"] >= 0.0


def test_two_usv_eval_artifacts_include_cross_region_and_wait_metrics(tmp_path) -> None:
    results = run_evaluation_two_usv_search_knownmap(
        n_episodes=1,
        max_iters=4,
        policy_names=("marine_knownmap_path_v2_infosampled_2usv",),
        map_kind="open_water",
        map_height_cells=60,
        map_width_cells=80,
        n_targets=2,
        target_motion_mode="static",
        target_count_upper_bound=3,
        clue_samples_per_step=6,
        gp_max_points=32,
        path_safety_mode="soft_clearance_astar_v1",
        team_path_avoidance_mode="reservation_v1",
        save_artifacts=True,
        output_dir=str(tmp_path),
    )

    result = results["marine_knownmap_path_v2_infosampled_2usv"][0]
    assert "cross_region_assignment_ratio" in result
    assert "wait_count_total" in result
    team_results_csv = (tmp_path / "team_results.csv").read_text(encoding="utf-8")
    assert "cross_region_assignment_ratio" in team_results_csv
    assert "wait_count_total" in team_results_csv
    assert "path_safety_mode" in team_results_csv
    assert "team_path_avoidance_mode" in team_results_csv
    assert "reservation_wait_fallback_count" in team_results_csv
    summary_payload = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    policy_summary = summary_payload["policy_summary"]["marine_knownmap_path_v2_infosampled_2usv"]
    assert "cross_region_assignment_ratio_mean" in policy_summary
    assert "wait_count_total_mean" in policy_summary
    assert "path_safety_modes" in policy_summary
    assert "team_path_avoidance_modes" in policy_summary
    assert "reservation_same_cell_violation_count_mean" in policy_summary


def test_two_usv_team_main_map_can_hide_true_targets() -> None:
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    known_map = np.full((7, 7), FREE, dtype=np.int8)
    known_map[0, :] = OCCUPIED
    known_map[-1, :] = OCCUPIED
    known_map[:, 0] = OCCUPIED
    known_map[:, -1] = OCCUPIED
    responsibility_owner_map = np.full((7, 7), -1, dtype=int)
    responsibility_owner_map[1:3, 1:6] = 0
    responsibility_owner_map[4:6, 1:6] = 1
    buffer_band_mask = np.zeros((7, 7), dtype=bool)
    buffer_band_mask[3, 1:6] = True

    fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    _draw_team_main_map(
        ax,
        known_map=known_map,
        usv_states=[
            {
                "robot_pos": (2, 2),
                "trajectory": [(2, 2), (2, 3)],
                "committed_segment": [(2, 2), (2, 3), (3, 3)],
                "committed_viewpoint": (3, 3),
                "committed_anchor": (4, 3),
                "current_plan_details": {"cross_region_selected": False},
            },
            {
                "robot_pos": (4, 4),
                "trajectory": [(4, 4), (4, 3)],
                "committed_segment": [(4, 4), (4, 3)],
                "committed_viewpoint": (4, 3),
                "committed_anchor": (3, 4),
                "current_plan_details": {"cross_region_selected": True},
            },
        ],
        target_positions=np.asarray([[3, 3], [4, 4]], dtype=int),
        found_mask=np.asarray([False, True], dtype=bool),
        wait_applied_map={0: False, 1: True},
        conflict_type="same_cell",
        responsibility_owner_map=responsibility_owner_map,
        buffer_band_mask=buffer_band_mask,
        show_true_targets=False,
    )

    _, labels = ax.get_legend_handles_labels()
    assert "USV 0" in labels
    assert "USV 1" in labels
    assert "Wait U1" in labels
    assert "Conflict" in labels
    assert "Resp U0" in labels
    assert "Resp U1" in labels
    assert "Buffer Band" in labels
    assert "Cross-region U1" in labels
    assert "Unfound Target" not in labels
    assert "Found Target" not in labels
    plt.close(fig)


def test_two_usv_team_plot_uses_separate_legend_panel() -> None:
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    known_map = np.full((7, 7), FREE, dtype=np.int8)
    known_map[0, :] = OCCUPIED
    known_map[-1, :] = OCCUPIED
    known_map[:, 0] = OCCUPIED
    known_map[:, -1] = OCCUPIED
    responsibility_owner_map = np.full((7, 7), -1, dtype=int)
    responsibility_owner_map[1:3, 1:6] = 0
    responsibility_owner_map[4:6, 1:6] = 1
    buffer_band_mask = np.zeros((7, 7), dtype=bool)
    buffer_band_mask[3, 1:6] = True

    plt.figure(figsize=(8, 5))
    plot_team_search_state(
        known_map=known_map,
        usv_states=[
            {
                "robot_pos": (2, 2),
                "trajectory": [(2, 2), (2, 3)],
                "committed_segment": [(2, 2), (2, 3), (3, 3)],
                "committed_viewpoint": (3, 3),
                "committed_anchor": (4, 3),
                "current_plan_details": {"cross_region_selected": False},
            },
            {
                "robot_pos": (4, 4),
                "trajectory": [(4, 4), (4, 3)],
                "committed_segment": [(4, 4), (4, 3)],
                "committed_viewpoint": (4, 3),
                "committed_anchor": (3, 4),
                "current_plan_details": {"cross_region_selected": True},
            },
        ],
        target_positions=np.asarray([[3, 3], [4, 4]], dtype=int),
        found_mask=np.asarray([False, True], dtype=bool),
        step=1,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        clue_map=np.zeros((7, 7), dtype=float),
        search_info_map=np.zeros((7, 7), dtype=float),
        intensity_map=np.zeros((7, 7), dtype=float),
        staleness_map=np.zeros((7, 7), dtype=float),
        wait_applied_map={0: False, 1: True},
        conflict_type="same_cell",
        joint_summary={
            "joint_assignment_score": 1.0,
            "joint_overlap_penalty": 0.2,
            "cross_region_selected_0": False,
            "cross_region_selected_1": True,
        },
        responsibility_owner_map=responsibility_owner_map,
        buffer_band_mask=buffer_band_mask,
        show_true_targets=False,
    )

    fig = plt.gcf()
    legend_axes = [ax for ax in fig.axes if ax.get_title() == "Legend"]
    main_axes = [ax for ax in fig.axes if ax.get_title() == "Main Map"]
    assert len(legend_axes) == 1
    assert len(main_axes) == 1
    assert main_axes[0].get_legend() is None
    assert legend_axes[0].get_legend() is not None
    plt.close(fig)


def test_two_usv_contract_file_freezes_expected_surface() -> None:
    contract = load_knownmap_experiment_contract_2usv()

    assert KNOWNMAP_EXPERIMENT_2USV_CONTRACT_PATH.exists()
    assert contract["schema_version"] == "knownmap_2usv_v1"
    assert contract["frozen_config"]["map_height_cells"] == 60
    assert contract["frozen_config"]["map_width_cells"] == 80
    assert contract["frozen_config"]["clue_sigma_m"] == 15.0
    assert contract["frozen_config"]["fixed_launch_positions"] == [[25, 2], [35, 2]]
    assert "cross_region_assignment_ratio" in contract["frozen_summary_keys"]
    assert "wait_count_total" in contract["frozen_summary_keys"]
    assert "cross_region_selected" in contract["frozen_trace_keys"]
    assert "template_only" not in contract
    assert (
        "summarize_two_usv_knownmap_policy_comparison"
        in contract["not_yet_implemented"]
    )
    assert "phase7_benchmark_comparison_framework" not in contract["not_yet_implemented"]


def test_two_usv_knownmap_episode_render_smoke() -> None:
    matplotlib.use("Agg", force=True)

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
        render=True,
        show_true_targets_in_viz=False,
    )

    assert result["n_usvs"] == 2
    assert result["completed_steps"] <= 4
