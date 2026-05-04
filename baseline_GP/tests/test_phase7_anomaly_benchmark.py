from __future__ import annotations

import csv
import json
import runpy
import sys

import baseline_GP.phase7_anomaly_benchmark as anomaly_benchmark
import baseline_GP.runner_two_usv_search as runner_two_usv


def test_phase7_anomaly_benchmark_writes_required_tables(tmp_path) -> None:
    summary = anomaly_benchmark.run_phase7_anomaly_acquisition_benchmark(
        map_kinds=("open_water",),
        episode_seeds=(0,),
        max_iters=4,
        motion_modes=("static",),
        output_dir=str(tmp_path),
        save_raw_phase7_artifacts=True,
    )

    assert summary["output_dir"] == str(tmp_path)
    required_files = (
        "config_snapshot.json",
        "static_main_results_by_map.csv",
        "static_anomaly_aux_metrics_by_map.csv",
        "static_delta_anomaly_vs_ucb.csv",
        "static_delta_coordinated_vs_independent.csv",
        "suite_summary.json",
    )
    for filename in required_files:
        assert (tmp_path / filename).exists()

    with (tmp_path / "static_main_results_by_map.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 6
    assert {row["system_name"] for row in rows} == {
        "single_ucb",
        "single_anomaly_upper_tail",
        "two_usv_independent_ucb",
        "two_usv_independent_anomaly_upper_tail",
        "two_usv_coordinated_ucb",
        "two_usv_coordinated_anomaly_upper_tail",
    }

    raw_config = json.loads(
        (tmp_path / "raw_phase7" / "static" / "ucb" / "config_snapshot.json").read_text(encoding="utf-8")
    )
    assert raw_config["target_motion_mode"] == "static"


def test_phase7_anomaly_benchmark_cli_dispatch(monkeypatch) -> None:
    called = {"suite": False}

    def fake_run_phase7_anomaly_acquisition_benchmark() -> dict[str, object]:
        called["suite"] = True
        return {"output_dir": "dummy"}

    monkeypatch.setattr(
        anomaly_benchmark,
        "run_phase7_anomaly_acquisition_benchmark",
        fake_run_phase7_anomaly_acquisition_benchmark,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["baseline_GP/runner_two_usv_search.py", "eval_knownmap_2usv_phase7_anomaly_benchmark"],
    )

    runpy.run_module("baseline_GP.runner_two_usv_search", run_name="__main__")

    assert called["suite"] is True
