from __future__ import annotations

import runpy
import sys

import numpy as np

import baseline_GP.marine_knownmap_runtime_2usv as runtime_2usv


def _make_two_usv_state() -> dict[str, object]:
    state = runtime_2usv._init_two_usv_knownmap_state(
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
    state["lambda_u_turn"] = 2.0
    state["gamma"] = 0.95
    state["segment_horizon"] = 8
    state["top_k_anchors"] = 6
    state["viewpoints_per_anchor"] = 6
    state["infosampled_inspected_limit_multiplier"] = 3.0
    state["infosampled_inspected_limit_floor"] = 4
    return state


def _phase7_result(
    *,
    episode_seed: int,
    map_kind: str,
    policy_name: str,
    found_count: int,
    time_to_first_detection: int | None,
    time_to_all_found: int | None,
    detection_rate: float,
    known_free_observation_ratio_final: float,
    planning_time_ms_mean: float,
    assignment_mode: str | None = None,
    clue_acquisition_mode: str | None = "ucb",
    duplicate_viewpoint_ratio: float | None = None,
    cross_region_assignment_ratio: float | None = None,
    conflict_intervention_count: int | None = None,
    wait_count_total: int | None = None,
    wait_count_by_usv: list[int] | None = None,
    anomaly_top_band_selection_ratio_pre_first_detection: float | None = None,
    unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection: float | None = None,
) -> dict[str, object]:
    return {
        "episode_seed": int(episode_seed),
        "map_kind": map_kind,
        "policy_name": policy_name,
        "assignment_mode": assignment_mode,
        "clue_acquisition_mode": clue_acquisition_mode,
        "success_all_found": found_count >= 2,
        "found_count": int(found_count),
        "detection_rate": float(detection_rate),
        "time_to_first_detection": time_to_first_detection,
        "time_to_all_found": time_to_all_found,
        "known_free_observation_ratio_final": float(known_free_observation_ratio_final),
        "planning_time_ms_mean": float(planning_time_ms_mean),
        "anomaly_top_band_selection_ratio_pre_first_detection": anomaly_top_band_selection_ratio_pre_first_detection,
        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection": unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection,
        "duplicate_viewpoint_ratio": duplicate_viewpoint_ratio,
        "cross_region_assignment_ratio": cross_region_assignment_ratio,
        "conflict_intervention_count": conflict_intervention_count,
        "wait_count_total": wait_count_total,
        "wait_count_by_usv": wait_count_by_usv,
    }


def test_independent_assignment_disables_responsibility_and_residual_zeroing(monkeypatch) -> None:
    state = _make_two_usv_state()
    state["search_info_map"] = np.arange(state["search_info_map"].size, dtype=float).reshape(
        state["search_info_map"].shape
    )
    original_search_info_map = np.asarray(state["search_info_map"], dtype=float)
    captured_calls: list[dict[str, object]] = []

    def fake_plan_for_usv(
        *,
        team_state: dict,
        local: dict,
        predicted_intensity: np.ndarray,
        search_info_map: np.ndarray,
        policy_name: str,
        step: int,
        use_responsibility_prior: bool = True,
    ) -> tuple[list[tuple[int, int]], dict[str, object], set[tuple[int, int]]]:
        captured_calls.append(
            {
                "usv_id": int(local["usv_id"]),
                "use_responsibility_prior": bool(use_responsibility_prior),
                "search_info_map": np.array(search_info_map, copy=True),
            }
        )
        viewpoint_cell = (20 + int(local["usv_id"]), 10 + int(local["usv_id"]))
        details = runtime_2usv._zero_assignment_details(
            local["robot_pos"],
            kappa_commit=0.0,
        )
        details["viewpoint_cell"] = viewpoint_cell
        details["segment_endpoint_cell"] = viewpoint_cell
        details["total_score"] = 5.0 + float(local["usv_id"])
        return [tuple(local["robot_pos"]), viewpoint_cell], details, {viewpoint_cell}

    monkeypatch.setattr(runtime_2usv, "_plan_for_usv", fake_plan_for_usv)

    assignments, summary = runtime_2usv._assign_two_usv_segments_independent(
        team_state=state,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        predicted_intensity=np.zeros_like(state["intensity_map"], dtype=float),
        step=1,
    )

    assert len(captured_calls) == 2
    assert all(not call["use_responsibility_prior"] for call in captured_calls)
    assert np.array_equal(captured_calls[0]["search_info_map"], original_search_info_map)
    assert np.array_equal(captured_calls[1]["search_info_map"], original_search_info_map)
    assert summary["assignment_mode"] == "independent"
    assert summary["assignment_order"] is None
    assert summary["joint_overlap_penalty"] == 0.0
    assert summary["same_viewpoint_selected"] is False
    assert assignments[0]["responsibility_regularizer"] == 0.0
    assert assignments[1]["responsibility_regularizer"] == 0.0


def test_coordinated_assignment_retains_coordinated_summary_fields() -> None:
    state = _make_two_usv_state()
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

    assignments, summary = runtime_2usv._joint_assign_two_usv_segments(
        team_state=state,
        policy_name="marine_knownmap_path_v2_infosampled_2usv",
        predicted_intensity=np.zeros_like(state["intensity_map"], dtype=float),
        step=1,
    )

    assert summary["assignment_mode"] == "coordinated"
    assert "same_viewpoint_selected" in summary
    assert "responsibility_regularizer_0" in summary
    assert "responsibility_regularizer_1" in summary
    assert all("responsibility_regularizer" in item for item in assignments.values())
    assert summary["responsibility_regularizer_0"] == 0.0
    assert summary["responsibility_regularizer_1"] == 0.0
    assert all(item["responsibility_regularizer"] == 0.0 for item in assignments.values())


def test_run_phase7_knownmap_comparison_outputs_three_systems_and_artifacts(tmp_path) -> None:
    comparison_run = runtime_2usv.run_phase7_knownmap_comparison(
        map_kinds=("open_water",),
        episode_seeds=(0,),
        max_iters=4,
        output_dir=str(tmp_path),
        save_artifacts=True,
    )

    assert set(comparison_run["results_by_system"].keys()) == {
        runtime_2usv.PHASE7_SYSTEM_SINGLE,
        runtime_2usv.PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
        runtime_2usv.PHASE7_SYSTEM_TWO_USV_COORDINATED,
    }
    assert len(comparison_run["results_by_system"][runtime_2usv.PHASE7_SYSTEM_SINGLE]["open_water"]) == 1
    assert len(
        comparison_run["results_by_system"][runtime_2usv.PHASE7_SYSTEM_TWO_USV_INDEPENDENT]["open_water"]
    ) == 1
    assert len(
        comparison_run["results_by_system"][runtime_2usv.PHASE7_SYSTEM_TWO_USV_COORDINATED]["open_water"]
    ) == 1
    assert (tmp_path / "config_snapshot.json").exists()
    assert (tmp_path / runtime_2usv.PHASE7_SYSTEM_SINGLE / "open_water" / "episode_results.json").exists()
    assert (tmp_path / "pairwise" / "coordinated_vs_independent.json").exists()
    assert (tmp_path / "pairwise" / "phase7_overall_summary.json").exists()


def test_run_phase7_knownmap_comparison_supports_anomaly_mode() -> None:
    comparison_run = runtime_2usv.run_phase7_knownmap_comparison(
        map_kinds=("open_water",),
        episode_seeds=(0,),
        max_iters=4,
        clue_acquisition_mode="anomaly_upper_tail",
        save_artifacts=False,
    )

    assert comparison_run["config_snapshot"]["clue_acquisition_mode"] == "anomaly_upper_tail"
    single_result = comparison_run["results_by_system"][runtime_2usv.PHASE7_SYSTEM_SINGLE]["open_water"][0]
    coordinated_result = comparison_run["results_by_system"][
        runtime_2usv.PHASE7_SYSTEM_TWO_USV_COORDINATED
    ]["open_water"][0]
    assert single_result["clue_acquisition_mode"] == "anomaly_upper_tail"
    assert coordinated_result["clue_acquisition_mode"] == "anomaly_upper_tail"
    assert "anomaly_top_band_selection_ratio_pre_first_detection" in coordinated_result


def test_phase7_pairwise_aligns_by_seed_and_single_missing_dual_deltas_are_none() -> None:
    comparison_run = {
        "config_snapshot": {
            "map_kinds": ["open_water"],
            "episode_seeds": [0, 1],
            "max_iters": 240,
        },
        "results_by_system": {
            runtime_2usv.PHASE7_SYSTEM_SINGLE: {
                "open_water": [
                    _phase7_result(
                        episode_seed=1,
                        map_kind="open_water",
                        policy_name="marine_knownmap_path_v2_infosampled",
                        found_count=2,
                        time_to_first_detection=9,
                        time_to_all_found=30,
                        detection_rate=1.0,
                        known_free_observation_ratio_final=0.35,
                        planning_time_ms_mean=12.0,
                    ),
                    _phase7_result(
                        episode_seed=0,
                        map_kind="open_water",
                        policy_name="marine_knownmap_path_v2_infosampled",
                        found_count=1,
                        time_to_first_detection=12,
                        time_to_all_found=None,
                        detection_rate=0.5,
                        known_free_observation_ratio_final=0.25,
                        planning_time_ms_mean=10.0,
                    ),
                ]
            },
            runtime_2usv.PHASE7_SYSTEM_TWO_USV_INDEPENDENT: {
                "open_water": [
                    _phase7_result(
                        episode_seed=0,
                        map_kind="open_water",
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode="independent",
                        found_count=2,
                        time_to_first_detection=10,
                        time_to_all_found=28,
                        detection_rate=1.0,
                        known_free_observation_ratio_final=0.45,
                        planning_time_ms_mean=20.0,
                        duplicate_viewpoint_ratio=0.30,
                        cross_region_assignment_ratio=0.10,
                        conflict_intervention_count=1,
                        wait_count_total=1,
                        wait_count_by_usv=[1, 0],
                    ),
                    _phase7_result(
                        episode_seed=1,
                        map_kind="open_water",
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode="independent",
                        found_count=2,
                        time_to_first_detection=8,
                        time_to_all_found=24,
                        detection_rate=1.0,
                        known_free_observation_ratio_final=0.50,
                        planning_time_ms_mean=18.0,
                        duplicate_viewpoint_ratio=0.25,
                        cross_region_assignment_ratio=0.15,
                        conflict_intervention_count=2,
                        wait_count_total=2,
                        wait_count_by_usv=[1, 1],
                    ),
                ]
            },
            runtime_2usv.PHASE7_SYSTEM_TWO_USV_COORDINATED: {
                "open_water": [
                    _phase7_result(
                        episode_seed=0,
                        map_kind="open_water",
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode="coordinated",
                        found_count=3,
                        time_to_first_detection=7,
                        time_to_all_found=20,
                        detection_rate=1.0,
                        known_free_observation_ratio_final=0.60,
                        planning_time_ms_mean=22.0,
                        duplicate_viewpoint_ratio=0.05,
                        cross_region_assignment_ratio=0.20,
                        conflict_intervention_count=0,
                        wait_count_total=0,
                        wait_count_by_usv=[0, 0],
                    ),
                    _phase7_result(
                        episode_seed=1,
                        map_kind="open_water",
                        policy_name="marine_knownmap_path_v2_infosampled_2usv",
                        assignment_mode="coordinated",
                        found_count=4,
                        time_to_first_detection=6,
                        time_to_all_found=18,
                        detection_rate=1.0,
                        known_free_observation_ratio_final=0.65,
                        planning_time_ms_mean=21.0,
                        duplicate_viewpoint_ratio=0.04,
                        cross_region_assignment_ratio=0.22,
                        conflict_intervention_count=0,
                        wait_count_total=0,
                        wait_count_by_usv=[0, 0],
                    ),
                ]
            },
        },
    }

    summary = runtime_2usv.summarize_phase7_knownmap_comparison(comparison_run)
    pair_rows = summary["pairwise"][
        f"{runtime_2usv.PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{runtime_2usv.PHASE7_SYSTEM_SINGLE}"
    ]["paired_episode_rows"]

    assert [row["episode_seed"] for row in pair_rows] == [0, 1]
    assert [row["found_count_delta"] for row in pair_rows] == [2, 2]
    assert all(row["duplicate_viewpoint_ratio_delta"] is None for row in pair_rows)
    assert all(row["cross_region_assignment_ratio_delta"] is None for row in pair_rows)
    assert all(row["conflict_intervention_count_delta"] is None for row in pair_rows)
    assert all(row["wait_count_total_delta"] is None for row in pair_rows)


def test_phase7_cli_dispatch_calls_phase7_runner(monkeypatch) -> None:
    called = {"phase7": False}

    def fake_run_phase7_knownmap_comparison() -> dict[str, object]:
        called["phase7"] = True
        return {"config_snapshot": {}, "results_by_system": {}}

    monkeypatch.setattr(
        runtime_2usv,
        "run_phase7_knownmap_comparison",
        fake_run_phase7_knownmap_comparison,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["baseline_GP/runner_two_usv_search.py", "eval_knownmap_2usv_phase7"],
    )

    runpy.run_module("baseline_GP.runner_two_usv_search", run_name="__main__")

    assert called["phase7"] is True
