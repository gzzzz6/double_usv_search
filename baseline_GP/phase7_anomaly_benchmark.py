"""
Formal result-production harness for Phase 7 + anomaly acquisition comparisons.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    from .marine_knownmap_runtime import _json_safe, _make_output_dir, _write_csv
    from .marine_knownmap_runtime_2usv import (
        PHASE7_SYSTEM_SINGLE,
        PHASE7_SYSTEM_TWO_USV_COORDINATED,
        PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
        _summarize_phase7_pairwise_results,
        load_knownmap_experiment_contract_2usv,
        run_phase7_knownmap_comparison,
        summarize_phase7_knownmap_comparison,
    )
except ImportError:
    from marine_knownmap_runtime import _json_safe, _make_output_dir, _write_csv
    from marine_knownmap_runtime_2usv import (
        PHASE7_SYSTEM_SINGLE,
        PHASE7_SYSTEM_TWO_USV_COORDINATED,
        PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
        _summarize_phase7_pairwise_results,
        load_knownmap_experiment_contract_2usv,
        run_phase7_knownmap_comparison,
        summarize_phase7_knownmap_comparison,
    )


PHASE7_FORMAL_MAP_KINDS = ("open_water", "obstacle_field", "peninsula_passage")
PHASE7_FORMAL_EPISODE_SEEDS = tuple(range(10))
PHASE7_FORMAL_MOTION_MODES = ("static", "random_walk")
PHASE7_FORMAL_CLUE_MODES = ("ucb", "anomaly_upper_tail")
PHASE7_FORMAL_SYSTEM_ORDER = (
    PHASE7_SYSTEM_SINGLE,
    PHASE7_SYSTEM_TWO_USV_INDEPENDENT,
    PHASE7_SYSTEM_TWO_USV_COORDINATED,
)
PHASE7_SHARED_METRICS = (
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "planning_time_ms_mean",
)
PHASE7_AUX_METRICS = (
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
)
PHASE7_TWO_USV_METRICS = (
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "conflict_intervention_count",
    "wait_count_total",
)
PHASE7_RESULT_KEEP_KEYS = (
    "episode_seed",
    "map_kind",
    "policy_name",
    "assignment_mode",
    "clue_acquisition_mode",
    "success_all_found",
    "time_to_first_detection",
    "time_to_all_found",
    "detection_rate",
    "found_count",
    "known_free_observation_ratio_final",
    "planning_time_ms_mean",
    "anomaly_top_band_selection_ratio_pre_first_detection",
    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection",
    "duplicate_viewpoint_ratio",
    "cross_region_assignment_ratio",
    "conflict_intervention_count",
    "wait_count_total",
    "wait_count_by_usv",
)


def _raw_phase7_output_dir(
    suite_output_dir: Path,
    motion_mode: str,
    clue_acquisition_mode: str,
) -> Path:
    return suite_output_dir / "raw_phase7" / motion_mode / clue_acquisition_mode


def _system_family_label(system_name: str) -> str:
    if system_name == PHASE7_SYSTEM_SINGLE:
        return "single"
    if system_name == PHASE7_SYSTEM_TWO_USV_INDEPENDENT:
        return "two_usv_independent"
    if system_name == PHASE7_SYSTEM_TWO_USV_COORDINATED:
        return "two_usv_coordinated"
    raise ValueError(f"Unsupported Phase 7 system_name='{system_name}'")


def _formal_system_name(system_name: str, clue_acquisition_mode: str) -> str:
    family = _system_family_label(system_name)
    if family == "single":
        return f"single_{clue_acquisition_mode}"
    return f"{family}_{clue_acquisition_mode}"


def _assignment_mode_for_system(system_name: str) -> str | None:
    if system_name == PHASE7_SYSTEM_SINGLE:
        return None
    if system_name == PHASE7_SYSTEM_TWO_USV_INDEPENDENT:
        return "independent"
    if system_name == PHASE7_SYSTEM_TWO_USV_COORDINATED:
        return "coordinated"
    raise ValueError(f"Unsupported Phase 7 system_name='{system_name}'")


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(np.asarray(values, dtype=float)))


def _std_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.std(np.asarray(values, dtype=float), ddof=0))


def _metric_values(
    results: list[dict[str, object]],
    metric_name: str,
) -> list[float]:
    return [
        float(result[metric_name])
        for result in results
        if result.get(metric_name) is not None
    ]


def _slim_phase7_run(comparison_run: dict[str, object]) -> dict[str, object]:
    slim_results_by_system: dict[str, dict[str, list[dict[str, object]]]] = {}
    for system_name, results_by_map in comparison_run["results_by_system"].items():
        slim_results_by_system[system_name] = {}
        for map_kind, map_results in results_by_map.items():
            slim_results_by_system[system_name][map_kind] = [
                {key: result.get(key) for key in PHASE7_RESULT_KEEP_KEYS}
                for result in map_results
            ]
    return {
        "config_snapshot": dict(comparison_run["config_snapshot"]),
        "results_by_system": slim_results_by_system,
    }


def _load_phase7_run_from_dir(raw_output_dir: Path) -> dict[str, object]:
    config_snapshot = json.loads((raw_output_dir / "config_snapshot.json").read_text(encoding="utf-8"))
    map_kinds = tuple(str(map_kind) for map_kind in config_snapshot["map_kinds"])
    results_by_system: dict[str, dict[str, list[dict[str, object]]]] = {}
    for system_name in PHASE7_FORMAL_SYSTEM_ORDER:
        results_by_system[system_name] = {}
        for map_kind in map_kinds:
            episode_results_path = raw_output_dir / system_name / map_kind / "episode_results.json"
            episode_results = json.loads(episode_results_path.read_text(encoding="utf-8"))
            results_by_system[system_name][map_kind] = [
                {key: result.get(key) for key in PHASE7_RESULT_KEEP_KEYS}
                for result in episode_results
            ]
    return {
        "config_snapshot": config_snapshot,
        "results_by_system": results_by_system,
    }


def _flatten_results_by_map(
    results_by_map: dict[str, list[dict[str, object]]],
    map_kinds: tuple[str, ...],
) -> list[dict[str, object]]:
    return [
        result
        for map_kind in map_kinds
        for result in results_by_map.get(map_kind, [])
    ]


def _summary_row_for_system_map(
    *,
    map_kind: str,
    system_name: str,
    clue_acquisition_mode: str,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": _formal_system_name(system_name, clue_acquisition_mode),
        "assignment_mode": _assignment_mode_for_system(system_name),
        "clue_acquisition_mode": clue_acquisition_mode,
    }
    shared_field_map = {
        "time_to_first_detection": "time_to_first_detection",
        "time_to_all_found": "time_to_all_found",
        "detection_rate": "detection_rate",
        "found_count": "found_count",
        "known_free_observation_ratio_final": "known_free_observation_ratio_final",
        "planning_time_ms_mean": "planning_time_ms_mean",
    }
    for metric_name, field_prefix in shared_field_map.items():
        values = _metric_values(results, metric_name)
        row[f"{field_prefix}_mean"] = _mean_or_none(values)
        row[f"{field_prefix}_std"] = _std_or_none(values)
    for metric_name in PHASE7_TWO_USV_METRICS:
        values = (
            _metric_values(results, metric_name)
            if system_name != PHASE7_SYSTEM_SINGLE
            else []
        )
        row[f"{metric_name}_mean"] = _mean_or_none(values)
        row[f"{metric_name}_std"] = _std_or_none(values)
    return row


def _aux_row_for_system_map(
    *,
    map_kind: str,
    system_name: str,
    clue_acquisition_mode: str,
    results: list[dict[str, object]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "map_kind": map_kind,
        "system_name": _formal_system_name(system_name, clue_acquisition_mode),
        "assignment_mode": _assignment_mode_for_system(system_name),
        "clue_acquisition_mode": clue_acquisition_mode,
    }
    for metric_name in PHASE7_AUX_METRICS:
        values = _metric_values(results, metric_name)
        row[f"{metric_name}_mean"] = _mean_or_none(values)
        row[f"{metric_name}_std"] = _std_or_none(values)
    return row


def _paired_delta_summary(
    *,
    baseline_results_by_map: dict[str, list[dict[str, object]]],
    challenger_results_by_map: dict[str, list[dict[str, object]]],
    map_kinds: tuple[str, ...],
    baseline_system_name: str,
    challenger_system_name: str,
) -> dict[str, object]:
    return _summarize_phase7_pairwise_results(
        _flatten_results_by_map(baseline_results_by_map, map_kinds),
        _flatten_results_by_map(challenger_results_by_map, map_kinds),
        baseline_system_name=baseline_system_name,
        challenger_system_name=challenger_system_name,
    )


def _write_motion_mode_tables(
    *,
    output_dir: Path,
    motion_mode: str,
    map_kinds: tuple[str, ...],
    runs_by_clue_mode: dict[str, dict[str, object]],
) -> dict[str, str]:
    main_rows: list[dict[str, object]] = []
    aux_rows: list[dict[str, object]] = []
    for map_kind in map_kinds:
        for clue_acquisition_mode in PHASE7_FORMAL_CLUE_MODES:
            comparison_run = runs_by_clue_mode[clue_acquisition_mode]
            for system_name in PHASE7_FORMAL_SYSTEM_ORDER:
                results = comparison_run["results_by_system"][system_name].get(map_kind, [])
                main_rows.append(
                    _summary_row_for_system_map(
                        map_kind=map_kind,
                        system_name=system_name,
                        clue_acquisition_mode=clue_acquisition_mode,
                        results=results,
                    )
                )
                aux_rows.append(
                    _aux_row_for_system_map(
                        map_kind=map_kind,
                        system_name=system_name,
                        clue_acquisition_mode=clue_acquisition_mode,
                        results=results,
                    )
                )

    anomaly_vs_ucb_rows: list[dict[str, object]] = []
    for system_name in PHASE7_FORMAL_SYSTEM_ORDER:
        pairwise = _paired_delta_summary(
            baseline_results_by_map=runs_by_clue_mode["ucb"]["results_by_system"][system_name],
            challenger_results_by_map=runs_by_clue_mode["anomaly_upper_tail"]["results_by_system"][system_name],
            map_kinds=map_kinds,
            baseline_system_name=f"{_system_family_label(system_name)}_ucb",
            challenger_system_name=f"{_system_family_label(system_name)}_anomaly_upper_tail",
        )
        for map_kind in map_kinds:
            delta_means = pairwise["mapwise"][map_kind]["delta_means"]
            anomaly_vs_ucb_rows.append(
                {
                    "map_kind": map_kind,
                    "system_family": _system_family_label(system_name),
                    "time_to_first_detection_delta_mean": delta_means.get("time_to_first_detection_delta_mean"),
                    "time_to_all_found_delta_mean": delta_means.get("time_to_all_found_delta_mean"),
                    "detection_rate_delta_mean": delta_means.get("detection_rate_delta_mean"),
                    "found_count_delta_mean": delta_means.get("found_count_delta_mean"),
                    "known_free_observation_ratio_final_delta_mean": delta_means.get(
                        "known_free_observation_ratio_final_delta_mean"
                    ),
                    "planning_time_ms_mean_delta_mean": delta_means.get("planning_time_ms_mean_delta_mean"),
                    "anomaly_top_band_selection_ratio_pre_first_detection_delta_mean": delta_means.get(
                        "anomaly_top_band_selection_ratio_pre_first_detection_delta_mean"
                    ),
                    "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection_delta_mean": delta_means.get(
                        "unfound_target_neighborhood_anomaly_mass_ratio_pre_first_detection_delta_mean"
                    ),
                }
            )

    coordinated_vs_independent_rows: list[dict[str, object]] = []
    for clue_acquisition_mode in PHASE7_FORMAL_CLUE_MODES:
        phase7_summary = summarize_phase7_knownmap_comparison(runs_by_clue_mode[clue_acquisition_mode])
        pair_label = f"{PHASE7_SYSTEM_TWO_USV_COORDINATED}__vs__{PHASE7_SYSTEM_TWO_USV_INDEPENDENT}"
        pairwise = phase7_summary["pairwise"][pair_label]
        for map_kind in map_kinds:
            delta_means = pairwise["mapwise"][map_kind]["delta_means"]
            coordinated_vs_independent_rows.append(
                {
                    "map_kind": map_kind,
                    "clue_acquisition_mode": clue_acquisition_mode,
                    "time_to_first_detection_delta_mean": delta_means.get("time_to_first_detection_delta_mean"),
                    "time_to_all_found_delta_mean": delta_means.get("time_to_all_found_delta_mean"),
                    "detection_rate_delta_mean": delta_means.get("detection_rate_delta_mean"),
                    "found_count_delta_mean": delta_means.get("found_count_delta_mean"),
                    "known_free_observation_ratio_final_delta_mean": delta_means.get(
                        "known_free_observation_ratio_final_delta_mean"
                    ),
                    "duplicate_viewpoint_ratio_delta_mean": delta_means.get("duplicate_viewpoint_ratio_delta_mean"),
                    "cross_region_assignment_ratio_delta_mean": delta_means.get(
                        "cross_region_assignment_ratio_delta_mean"
                    ),
                    "conflict_intervention_count_delta_mean": delta_means.get(
                        "conflict_intervention_count_delta_mean"
                    ),
                    "wait_count_total_delta_mean": delta_means.get("wait_count_total_delta_mean"),
                }
            )

    main_path = _write_csv(output_dir / f"{motion_mode}_main_results_by_map.csv", main_rows)
    aux_path = _write_csv(output_dir / f"{motion_mode}_anomaly_aux_metrics_by_map.csv", aux_rows)
    anomaly_delta_path = _write_csv(
        output_dir / f"{motion_mode}_delta_anomaly_vs_ucb.csv",
        anomaly_vs_ucb_rows,
    )
    coord_delta_path = _write_csv(
        output_dir / f"{motion_mode}_delta_coordinated_vs_independent.csv",
        coordinated_vs_independent_rows,
    )
    return {
        f"{motion_mode}_main_results_by_map.csv": str(main_path),
        f"{motion_mode}_anomaly_aux_metrics_by_map.csv": str(aux_path),
        f"{motion_mode}_delta_anomaly_vs_ucb.csv": str(anomaly_delta_path),
        f"{motion_mode}_delta_coordinated_vs_independent.csv": str(coord_delta_path),
    }


def finalize_phase7_anomaly_acquisition_benchmark(
    *,
    output_dir: str,
    map_kinds: tuple[str, ...] | list[str] = PHASE7_FORMAL_MAP_KINDS,
    episode_seeds: tuple[int, ...] | list[int] = PHASE7_FORMAL_EPISODE_SEEDS,
    max_iters: int | None = None,
    motion_modes: tuple[str, ...] | list[str] = PHASE7_FORMAL_MOTION_MODES,
) -> dict[str, object]:
    suite_output_dir = Path(output_dir)
    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
    resolved_motion_modes = tuple(str(mode) for mode in motion_modes)

    contract = load_knownmap_experiment_contract_2usv()
    resolved_max_iters = (
        int(max_iters)
        if max_iters is not None
        else int(contract["frozen_config"]["max_iters"])
    )

    runs_by_motion_and_clue: dict[str, dict[str, dict[str, object]]] = {}
    raw_phase7_dirs: dict[str, dict[str, str | None]] = {}
    output_files: dict[str, str] = {}

    for motion_mode in resolved_motion_modes:
        runs_by_motion_and_clue[motion_mode] = {}
        raw_phase7_dirs[motion_mode] = {}
        for clue_acquisition_mode in PHASE7_FORMAL_CLUE_MODES:
            raw_output_dir = _raw_phase7_output_dir(
                suite_output_dir,
                motion_mode,
                clue_acquisition_mode,
            )
            if not (raw_output_dir / "config_snapshot.json").exists():
                raise FileNotFoundError(
                    f"Missing raw Phase 7 output for motion_mode='{motion_mode}', "
                    f"clue_acquisition_mode='{clue_acquisition_mode}': {raw_output_dir}"
                )
            runs_by_motion_and_clue[motion_mode][clue_acquisition_mode] = _load_phase7_run_from_dir(
                raw_output_dir
            )
            raw_phase7_dirs[motion_mode][clue_acquisition_mode] = str(raw_output_dir)

        output_files.update(
            _write_motion_mode_tables(
                output_dir=suite_output_dir,
                motion_mode=motion_mode,
                map_kinds=resolved_map_kinds,
                runs_by_clue_mode=runs_by_motion_and_clue[motion_mode],
            )
        )

    config_snapshot = {
        "map_kinds": list(resolved_map_kinds),
        "episode_seeds": list(resolved_episode_seeds),
        "max_iters": int(resolved_max_iters),
        "motion_modes": list(resolved_motion_modes),
        "clue_acquisition_modes": list(PHASE7_FORMAL_CLUE_MODES),
        "system_names": [
            "single_ucb",
            "single_anomaly_upper_tail",
            "two_usv_independent_ucb",
            "two_usv_independent_anomaly_upper_tail",
            "two_usv_coordinated_ucb",
            "two_usv_coordinated_anomaly_upper_tail",
        ],
        "two_usv_contract_revision_id": contract["baseline_revision_id"],
        "two_usv_contract_schema_version": contract["schema_version"],
        "raw_phase7_dirs": raw_phase7_dirs,
    }
    config_path = suite_output_dir / "config_snapshot.json"
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(config_snapshot), f, indent=2, ensure_ascii=False)
    output_files["config_snapshot.json"] = str(config_path)

    summary_payload = {
        "output_dir": str(suite_output_dir),
        "config_snapshot": config_snapshot,
        "output_files": output_files,
    }
    with (suite_output_dir / "suite_summary.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(summary_payload), f, indent=2, ensure_ascii=False)
    output_files["suite_summary.json"] = str(suite_output_dir / "suite_summary.json")

    return summary_payload


def run_phase7_anomaly_acquisition_benchmark(
    *,
    map_kinds: tuple[str, ...] | list[str] = PHASE7_FORMAL_MAP_KINDS,
    episode_seeds: tuple[int, ...] | list[int] = PHASE7_FORMAL_EPISODE_SEEDS,
    max_iters: int | None = None,
    motion_modes: tuple[str, ...] | list[str] = PHASE7_FORMAL_MOTION_MODES,
    output_dir: str | None = None,
    save_raw_phase7_artifacts: bool = True,
    resume_if_available: bool = True,
) -> dict[str, object]:
    resolved_map_kinds = tuple(str(map_kind) for map_kind in map_kinds)
    resolved_episode_seeds = tuple(int(seed) for seed in episode_seeds)
    resolved_motion_modes = tuple(str(mode) for mode in motion_modes)
    suite_output_dir = _make_output_dir(
        output_dir,
        default_leaf="phase7_anomaly_acquisition_benchmark",
    )

    for motion_mode in resolved_motion_modes:
        for clue_acquisition_mode in PHASE7_FORMAL_CLUE_MODES:
            raw_output_dir = _raw_phase7_output_dir(
                suite_output_dir,
                motion_mode,
                clue_acquisition_mode,
            )
            if (
                save_raw_phase7_artifacts
                and resume_if_available
                and (raw_output_dir / "config_snapshot.json").exists()
            ):
                continue
            run_phase7_knownmap_comparison(
                map_kinds=resolved_map_kinds,
                episode_seeds=resolved_episode_seeds,
                max_iters=max_iters,
                target_motion_mode=motion_mode,
                clue_acquisition_mode=clue_acquisition_mode,
                output_dir=str(raw_output_dir),
                save_artifacts=save_raw_phase7_artifacts,
            )

    return finalize_phase7_anomaly_acquisition_benchmark(
        output_dir=str(suite_output_dir),
        map_kinds=resolved_map_kinds,
        episode_seeds=resolved_episode_seeds,
        max_iters=max_iters,
        motion_modes=resolved_motion_modes,
    )


if __name__ == "__main__":
    result = run_phase7_anomaly_acquisition_benchmark()
    print(f"Phase 7 anomaly benchmark output_dir={result['output_dir']}")
