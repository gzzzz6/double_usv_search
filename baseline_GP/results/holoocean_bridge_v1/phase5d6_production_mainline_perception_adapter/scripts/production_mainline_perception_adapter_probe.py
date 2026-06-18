"""Phase 5D-6: production mainline perception adapter regression probe.

This phase promotes the Phase 5D-5 adapter API into
baseline_GP.holoocean_bridge.mainline_perception_adapter and verifies that the
production module preserves the static SphereAgent -> baseline_GP found_mask /
all_found behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.append(os.path.abspath("."))

import baseline_GP.marine_knownmap_runtime_2usv as runtime_2usv  # noqa: E402
from baseline_GP.holoocean_bridge import (  # noqa: E402
    MainlineAdapterStepInput as ExportedMainlineAdapterStepInput,
    ReusableMainlinePerceptionAdapter as ExportedReusableMainlinePerceptionAdapter,
    mainline_perception_adapter_contract as exported_adapter_contract,
)
from baseline_GP.holoocean_bridge.mainline_perception_adapter import (  # noqa: E402
    MainlineAdapterStepInput,
    ReusableMainlinePerceptionAdapter,
    mainline_perception_adapter_contract,
)


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d6_production_mainline_perception_adapter"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SOURCE_5D3_PHASE_NAME = "phase5d3_continuous_multistep_coop_search"
SOURCE_5D3_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D3_PHASE_NAME))
SOURCE_5D3_AUDIT_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_continuous_audit.json")
SOURCE_5D3_SUMMARY_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_continuous_summary.json")
SOURCE_5D3_EVENTS_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_per_agent_detection_events.json")
SOURCE_5D3_FUSION_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_candidate_fusion_trace.json")

SOURCE_5D5_PHASE_NAME = "phase5d5_reusable_mainline_perception_adapter"
SOURCE_5D5_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D5_PHASE_NAME))
SOURCE_5D5_AUDIT_JSON = os.path.join(SOURCE_5D5_DIR, "manifests", "phase5d5_audit.json")
SOURCE_5D5_SUMMARY_JSON = os.path.join(SOURCE_5D5_DIR, "manifests", "phase5d5_summary.json")
SOURCE_5D5_CONTRACT_JSON = os.path.join(SOURCE_5D5_DIR, "manifests", "phase5d5_adapter_api_contract.json")

PRODUCTION_MODULE_PATH = os.path.join(BASE_DIR, "holoocean_bridge", "mainline_perception_adapter.py")
PRODUCTION_INIT_PATH = os.path.join(BASE_DIR, "holoocean_bridge", "__init__.py")

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_config.json")
PRODUCTION_CONTRACT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_production_adapter_contract.json")
MIGRATION_MANIFEST_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_migration_manifest.json")
OFFLINE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_offline_regression_trace.json")
OFFLINE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d6_offline_regression_trace.csv")
MAINLINE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_mainline_wrapper_trace.json")
MAINLINE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d6_mainline_wrapper_trace.csv")
MAINLINE_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_mainline_runtime_results.json")
LIVE_CAPTURE_EVAL_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_live_capture_interface_evaluation.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d6_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d6_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d6_py_compile_base.txt")

RECOMMENDED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_NAMES = ["sv0", "sv1"]
RELIABLE_DISTANCE_LIMIT_M = 35.0
MAX_POLICY_STEPS = 4
MAINLINE_POLICY_NAME = "marine_knownmap_path_v2_infosampled_2usv"


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    return obj


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(data), f, indent=2)
    print("JSON saved to: {0}".format(path))


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set, np.ndarray)):
        return json.dumps(_json_safe(value), sort_keys=True)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    return value


def _save_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten_for_csv(row.get(key)) for key in keys})
    print("CSV saved to: {0}".format(path))


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _run_git_status(paths: Optional[List[str]] = None) -> List[str]:
    repo_root = os.path.abspath(".")
    cmd = ["git", "-c", "safe.directory={0}".format(repo_root.replace("\\", "/")), "status", "--porcelain"]
    if paths:
        cmd.append("--")
        cmd.extend(paths)
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if result.stderr.strip():
        lines.append("STDERR: {0}".format(result.stderr.strip()))
    return lines


def _audit_passed(path: str) -> bool:
    data = _load_json(path)
    return bool(isinstance(data, dict) and data.get("all_passed") is True)


def _case_sources(
    run_kind: str,
    source_run_kind: str,
    events: List[Dict[str, Any]],
    fusion: List[Dict[str, Any]],
) -> tuple:
    del run_kind
    return (
        [row for row in events if row.get("run_kind") == source_run_kind],
        [row for row in fusion if row.get("run_kind") == source_run_kind],
    )


def _known_teammates(run_kind: str) -> List[Dict[str, Any]]:
    teammates = [
        {"agent_name": "sv0", "agent_type": TEAMMATE_AGENT_TYPE, "is_observer": True},
        {"agent_name": "sv1", "agent_type": TEAMMATE_AGENT_TYPE, "is_observer": True},
    ]
    if run_kind == "coexist":
        teammates.append({"agent_name": "teammate_extra0", "agent_type": TEAMMATE_AGENT_TYPE, "is_observer": False})
    return teammates


def _offline_replay_case(
    *,
    run_kind: str,
    source_run_kind: str,
    event_rows: List[Dict[str, Any]],
    fusion_rows: List[Dict[str, Any]],
    force_schedule: Optional[Dict[int, bool]] = None,
) -> Dict[str, Any]:
    adapter = ReusableMainlinePerceptionAdapter(adapter_id="phase5d6_offline_{0}".format(run_kind))
    adapter.reset_episode("phase5d6_offline_{0}".format(run_kind))
    found_mask = [False]
    find_times: List[Optional[int]] = [None]
    trace: List[Dict[str, Any]] = []
    fusion_by_step = {int(row.get("policy_step", 0)): row for row in fusion_rows}
    for step in range(1, MAX_POLICY_STEPS + 1):
        events_for_step = [row for row in event_rows if int(row.get("policy_step", 0)) == step]
        force_detect = force_schedule.get(step) if force_schedule else None
        output = adapter.observe_step(
            MainlineAdapterStepInput(
                run_kind=run_kind,
                step_index=step,
                target_count=1,
                found_mask_before=list(found_mask),
                per_agent_events=events_for_step,
                candidate_fusion_result=fusion_by_step.get(step, {"policy_step": step}),
                known_teammates=_known_teammates(source_run_kind),
                force_detect=force_detect,
            )
        )
        new_found_indices: List[int] = []
        for idx, detected in enumerate(output.detected_mask):
            if detected and not found_mask[idx]:
                found_mask[idx] = True
                find_times[idx] = step
                new_found_indices.append(idx)
        trace_row = output.asdict()
        trace_row.update(
            {
                "source_run_kind": source_run_kind,
                "found_mask_after_replay": list(found_mask),
                "find_times_after_replay": list(find_times),
                "new_found_indices": new_found_indices,
                "all_found_after_replay": all(found_mask),
                "offline_replay_update_applied": True,
                "adapter_module": ReusableMainlinePerceptionAdapter.__module__,
            }
        )
        trace.append(trace_row)
    return {
        "run_kind": run_kind,
        "source_run_kind": source_run_kind,
        "trace": trace,
        "found_mask_final": found_mask,
        "find_times_final": find_times,
        "all_found": all(found_mask),
        "all_found_step": next((row["step_index"] for row in trace if row["all_found_after_replay"]), None),
        "false_positive_steps": [
            int(row["step_index"])
            for row in trace
            if run_kind == "teammate_only" and any(bool(v) for v in row.get("detected_mask", []))
        ],
    }


class MainlineAdapterRuntimeProvider:
    """Expose the production adapter as baseline_GP detect_targets."""

    def __init__(
        self,
        *,
        run_kind: str,
        source_run_kind: str,
        event_rows: List[Dict[str, Any]],
        fusion_rows: List[Dict[str, Any]],
        force_schedule: Optional[Dict[int, bool]] = None,
    ) -> None:
        self.run_kind = run_kind
        self.source_run_kind = source_run_kind
        self.event_rows = event_rows
        self.fusion_by_step = {int(row.get("policy_step", 0)): row for row in fusion_rows}
        self.force_schedule = force_schedule or {}
        self.adapter = ReusableMainlinePerceptionAdapter(adapter_id="phase5d6_mainline_{0}".format(run_kind))
        self.adapter.reset_episode("phase5d6_mainline_{0}".format(run_kind))
        self.call_index = 0
        self.step_call_counts: Dict[int, int] = {}
        self.detect_trace: List[Dict[str, Any]] = []

    def detect_targets(
        self,
        robot_pos: tuple,
        target_positions: np.ndarray,
        found_mask: np.ndarray,
        sensor_range_cells: int,
        detection_rng: np.random.Generator,
    ) -> np.ndarray:
        del detection_rng
        self.call_index += 1
        step = int(getattr(runtime_2usv, "_PHASE5D6_CURRENT_STEP", 0))
        step_call_index = int(self.step_call_counts.get(step, 0))
        self.step_call_counts[step] = step_call_index + 1
        usv_id = step_call_index % 2
        events_for_step = [row for row in self.event_rows if int(row.get("policy_step", 0)) == step]
        force_detect = self.force_schedule.get(step)
        if usv_id != 0 and force_detect is not True:
            force_detect = False
        output = self.adapter.observe_step(
            MainlineAdapterStepInput(
                run_kind=self.run_kind,
                step_index=step,
                target_count=int(len(target_positions)),
                found_mask_before=[bool(v) for v in found_mask.tolist()],
                per_agent_events=events_for_step,
                candidate_fusion_result=self.fusion_by_step.get(step, {"policy_step": step}),
                known_teammates=_known_teammates(self.source_run_kind),
                force_detect=force_detect,
            )
        )
        mask = self.adapter.build_detected_mask(step, int(len(target_positions)))
        if usv_id != 0:
            mask = np.zeros_like(mask, dtype=bool)
        trace_row = output.asdict()
        trace_row.update(
            {
                "call_index": int(self.call_index),
                "mainline_step": int(step),
                "mainline_usv_id": int(usv_id),
                "mainline_step_detect_call_index": int(step_call_index),
                "robot_pos": tuple(int(v) for v in robot_pos),
                "sensor_range_cells": int(sensor_range_cells),
                "found_mask_before_detect": found_mask.tolist(),
                "detected_mask_returned_to_mainline": mask.tolist(),
                "detection_source": "production_mainline_perception_adapter",
                "adapter_module": ReusableMainlinePerceptionAdapter.__module__,
            }
        )
        self.detect_trace.append(trace_row)
        return mask


class MainlineUpdateTraceHarness:
    def __init__(self, provider: MainlineAdapterRuntimeProvider, original_update_found_mask: Any) -> None:
        self.provider = provider
        self.original_update_found_mask = original_update_found_mask
        self.update_trace: List[Dict[str, Any]] = []
        self.update_call_index = 0

    def update_found_mask(
        self,
        found_mask: np.ndarray,
        detected_mask: np.ndarray,
        find_times: List[Optional[int]],
        step: int,
    ) -> List[int]:
        self.update_call_index += 1
        before_found = found_mask.tolist()
        before_find_times = list(find_times)
        new_indices = self.original_update_found_mask(found_mask, detected_mask, find_times, step)
        fusion = self.provider.fusion_by_step.get(int(step), {})
        self.update_trace.append(
            {
                "run_kind": self.provider.run_kind,
                "update_call_index": int(self.update_call_index),
                "mainline_step": int(step),
                "source_policy_step": int(fusion.get("policy_step", step) or step),
                "source_shared_found": bool(fusion.get("shared_found_this_step", False)),
                "source_accepted_candidate_count": int(fusion.get("accepted_candidate_count", 0) or 0),
                "source_fused_candidate_count": int(fusion.get("fused_candidate_count", 0) or 0),
                "detected_mask": detected_mask.tolist(),
                "found_mask_before": before_found,
                "found_mask_after": found_mask.tolist(),
                "find_times_before": before_find_times,
                "find_times_after": list(find_times),
                "new_found_indices": list(new_indices),
                "shared_found": bool(np.any(detected_mask)),
                "all_found_after_update": bool(np.all(found_mask)),
                "update_found_mask_original_called": True,
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
            }
        )
        return new_indices


def _run_mainline_case(
    *,
    run_kind: str,
    source_run_kind: str,
    event_rows: List[Dict[str, Any]],
    fusion_rows: List[Dict[str, Any]],
    max_iters: int,
    force_schedule: Optional[Dict[int, bool]] = None,
) -> Dict[str, Any]:
    provider = MainlineAdapterRuntimeProvider(
        run_kind=run_kind,
        source_run_kind=source_run_kind,
        event_rows=event_rows,
        fusion_rows=fusion_rows,
        force_schedule=force_schedule,
    )
    original_detect_targets = runtime_2usv.detect_targets
    original_update_found_mask = runtime_2usv.update_found_mask
    original_sample_and_update_team_gp = runtime_2usv._sample_and_update_team_gp
    original_step_targets = runtime_2usv.step_targets
    harness = MainlineUpdateTraceHarness(provider, original_update_found_mask)

    def _wrapped_sample_and_update_team_gp(state: Dict[str, Any], step: int, gp_fit_every: int) -> None:
        runtime_2usv._PHASE5D6_CURRENT_STEP = int(step)
        original_sample_and_update_team_gp(state, step=step, gp_fit_every=gp_fit_every)

    def _wrapped_step_targets(*args: Any, **kwargs: Any) -> Any:
        runtime_2usv._PHASE5D6_CURRENT_STEP = int(getattr(runtime_2usv, "_PHASE5D6_CURRENT_STEP", 0)) + 1
        return original_step_targets(*args, **kwargs)

    runtime_2usv._PHASE5D6_CURRENT_STEP = 0
    runtime_2usv.detect_targets = provider.detect_targets
    runtime_2usv.update_found_mask = harness.update_found_mask
    runtime_2usv._sample_and_update_team_gp = _wrapped_sample_and_update_team_gp
    runtime_2usv.step_targets = _wrapped_step_targets
    started = time.perf_counter()
    error = ""
    result: Dict[str, Any]
    try:
        result = runtime_2usv.run_episode_two_usv_search_knownmap(
            episode_seed=0,
            max_iters=max_iters,
            policy_name=MAINLINE_POLICY_NAME,
            assignment_mode="coordinated",
            map_kind="open_water",
            map_height_cells=60,
            map_width_cells=80,
            n_targets=1,
            target_motion_mode="static",
            target_count_upper_bound=1,
            resolution_m=10.0,
            sensor_range_m=50.0,
            min_target_separation_m=60.0,
            min_start_distance_m=80.0,
            clue_samples_per_step=6,
            gp_max_points=48,
            gp_fit_every=5,
            render=False,
            show_true_targets_in_viz=False,
        )
    except Exception as exc:  # pragma: no cover - captured as audit evidence.
        error = repr(exc)
        result = {
            "terminated_reason": "exception",
            "success_all_found": False,
            "completed_steps": 0,
            "found_count": 0,
            "find_times": [None],
        }
    finally:
        runtime_2usv.detect_targets = original_detect_targets
        runtime_2usv.update_found_mask = original_update_found_mask
        runtime_2usv._sample_and_update_team_gp = original_sample_and_update_team_gp
        runtime_2usv.step_targets = original_step_targets
        runtime_2usv._PHASE5D6_CURRENT_STEP = 0

    return {
        "run_kind": run_kind,
        "source_run_kind": source_run_kind,
        "launch_ok": error == "",
        "error": error,
        "runtime_result": result,
        "adapter_detect_trace": provider.detect_trace,
        "adapter_output_trace": provider.adapter.fusion_trace(),
        "mainline_update_trace": harness.update_trace,
        "wall_time_s": round(time.perf_counter() - started, 6),
        "mainline_detect_targets_replaced_runtime_only": True,
        "mainline_update_found_mask_wrapped_runtime_only": True,
        "update_found_mask_original_called_count": len(harness.update_trace),
        "truth_used_for_detection": False,
    }


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    return all(
        row.get("truth_used_for_detection") is False
        and row.get("actor_truth_used_for_detection") is False
        and row.get("target_truth_used_for_detection") is False
        and row.get("teammate_truth_used_for_detection") is False
        for row in rows
    )


def _run_compile_log(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            PRODUCTION_MODULE_PATH,
            os.path.join(PHASE_DIR, "scripts", "production_mainline_perception_adapter_probe.py"),
            os.path.join(PHASE_DIR, "scripts", "production_mainline_perception_adapter_audit.py"),
        ],
        cwd=os.path.abspath("."),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(result.stdout)
        f.write(result.stderr)
        if result.returncode == 0:
            f.write("\nBASE_PY_COMPILE_OK\n")
        else:
            f.write("\nBASE_PY_COMPILE_FAILED\n")


def _production_migration_manifest() -> Dict[str, Any]:
    module_text = _read_text(PRODUCTION_MODULE_PATH)
    init_text = _read_text(PRODUCTION_INIT_PATH)
    production_contract = mainline_perception_adapter_contract()
    exported_contract = exported_adapter_contract()
    source_contract = _load_json(SOURCE_5D5_CONTRACT_JSON)
    return {
        "phase_name": PHASE_NAME,
        "migration_decision": "promote_5d5_phase_local_adapter_to_formal_holoocean_bridge_module",
        "production_module_path": PRODUCTION_MODULE_PATH.replace("\\", "/"),
        "production_module_exists": os.path.exists(PRODUCTION_MODULE_PATH),
        "production_init_path": PRODUCTION_INIT_PATH.replace("\\", "/"),
        "production_init_exports_adapter": "ReusableMainlinePerceptionAdapter" in init_text,
        "production_init_exports_contract": "mainline_perception_adapter_contract" in init_text,
        "direct_import_module": ReusableMainlinePerceptionAdapter.__module__,
        "package_export_module": ExportedReusableMainlinePerceptionAdapter.__module__,
        "package_export_ok": (
            ExportedReusableMainlinePerceptionAdapter is ReusableMainlinePerceptionAdapter
            and ExportedMainlineAdapterStepInput is MainlineAdapterStepInput
            and exported_contract == production_contract
        ),
        "source_5d5_adapter_class": source_contract.get("adapter_class"),
        "source_5d5_phase_local_only": source_contract.get("phase_local_only"),
        "source_5d5_production_module_created": source_contract.get("production_module_created"),
        "production_adapter_class": production_contract.get("adapter_class"),
        "production_phase_local_only": production_contract.get("phase_local_only"),
        "production_module_created": production_contract.get("production_module_created"),
        "module_contains_runtime_or_planner_rewrite": (
            "run_episode_two_usv_search_knownmap" in module_text
            or "select_knownmap_path_segment_policy" in module_text
            or "sample_targets" in module_text
        ),
        "production_files_intentionally_changed": [
            PRODUCTION_MODULE_PATH.replace("\\", "/"),
            PRODUCTION_INIT_PATH.replace("\\", "/"),
        ],
        "truth_policy": production_contract.get("truth_policy"),
    }


def _live_capture_interface_evaluation() -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "phase_decision": "complete production adapter module first",
        "long_term_live_capture_callback_integrated": False,
        "live_capture_deferred_to_next_phase": True,
        "adapter_ready_for_live_capture_provider": True,
        "required_live_capture_provider_inputs": [
            "run_kind",
            "step_index",
            "target_count",
            "found_mask_before",
            "per_agent_events",
            "candidate_fusion_result",
            "known_teammates",
        ],
        "required_callback_chain": [
            "baseline_GP planner step",
            "HoloOcean SurfaceVessel movement",
            "HoloOcean live sensor capture",
            "per-agent SphereAgent detection event",
            "candidate fusion",
            "ReusableMainlinePerceptionAdapter.observe_step",
            "build_detected_mask",
            "baseline_GP update_found_mask",
            "found_mask/all_found termination",
        ],
        "current_regression_source": "phase5d3_recorded_per_agent_events_and_candidate_fusion",
        "truth_policy": "truth audit-only; truth is not a live detection input",
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
    }


def _phase_config(pre_git_status: List[str]) -> Dict[str, Any]:
    source_5d3_summary = _load_json(SOURCE_5D3_SUMMARY_JSON)
    source_5d5_summary = _load_json(SOURCE_5D5_SUMMARY_JSON)
    return {
        "phase_name": PHASE_NAME,
        "phase_goal": "Promote the Phase 5D-5 phase-local adapter API into a formal holoocean_bridge production module and regression-test it against offline and mainline-wrapper semantics.",
        "source_5d3_phase_name": SOURCE_5D3_PHASE_NAME,
        "source_5d3_audit_all_passed": _audit_passed(SOURCE_5D3_AUDIT_JSON),
        "source_5d3_event_count": int(source_5d3_summary.get("event_count", 0)),
        "source_5d3_fusion_trace_count": int(source_5d3_summary.get("fusion_trace_count", 0)),
        "source_5d5_phase_name": SOURCE_5D5_PHASE_NAME,
        "source_5d5_audit_all_passed": _audit_passed(SOURCE_5D5_AUDIT_JSON),
        "source_5d5_offline_target_all_found_step": source_5d5_summary.get("offline_target_all_found_step"),
        "source_5d5_mainline_target_time_to_all_found": source_5d5_summary.get("mainline_target_time_to_all_found"),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "observer_count": 2,
        "observer_agent_names": list(OBSERVER_AGENT_NAMES),
        "observer_agent_type": OBSERVER_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "mainline_runtime_module": "baseline_GP.marine_knownmap_runtime_2usv",
        "mainline_policy_name": MAINLINE_POLICY_NAME,
        "mainline_run_function": "run_episode_two_usv_search_knownmap",
        "adapter_strategy": "formal production module plus offline/mainline regression",
        "adapter_class": "ReusableMainlinePerceptionAdapter",
        "api_methods": ["reset_episode", "observe_step", "build_detected_mask", "fusion_trace"],
        "production_module_created": True,
        "phase_local_only": False,
        "baseline_runtime_source_modified": False,
        "search_decision_algorithm_modified": False,
        "core_search_policy_modified": False,
        "core_execution_modified": False,
        "core_targets_modified": False,
        "core_intensity_modified": False,
        "core_safe_nav_modified": False,
        "existing_holoocean_bridge_modified": True,
        "holoocean_bridge_modification_scope": "add mainline_perception_adapter.py and export API from __init__.py",
        "live_capture_long_term_callback_integrated": False,
        "live_capture_deferred_to_next_phase": True,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "perception_sensors": ["RGBCamera", "RangeFinderSensor"],
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "truth_role": "audit_only",
        "max_policy_steps": MAX_POLICY_STEPS,
        "run_cases": ["target", "coexist", "teammate_only", "duplicate_replay"],
        "pre_git_status": pre_git_status,
    }


def _build_summary(
    config: Dict[str, Any],
    migration: Dict[str, Any],
    live_capture_eval: Dict[str, Any],
    offline_cases: List[Dict[str, Any]],
    mainline_cases: List[Dict[str, Any]],
    offline_trace: List[Dict[str, Any]],
    mainline_trace: List[Dict[str, Any]],
    started: float,
) -> Dict[str, Any]:
    offline_by_kind = {doc["run_kind"]: doc for doc in offline_cases}
    mainline_by_kind = {doc["run_kind"]: doc["runtime_result"] for doc in mainline_cases}
    mainline_update_by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for row in mainline_trace:
        if row.get("trace_type") == "mainline_update":
            mainline_update_by_kind.setdefault(str(row.get("run_kind")), []).append(row)

    duplicate_update_rows = [
        row
        for row in mainline_update_by_kind.get("duplicate_replay", [])
        if any(bool(value) for value in row.get("detected_mask", []))
    ]
    teammate_update_rows = mainline_update_by_kind.get("teammate_only", [])
    target_result = mainline_by_kind.get("target", {})
    coexist_result = mainline_by_kind.get("coexist", {})
    teammate_result = mainline_by_kind.get("teammate_only", {})
    duplicate_result = mainline_by_kind.get("duplicate_replay", {})
    return {
        "phase_name": PHASE_NAME,
        "phase_completed": True,
        "phase_goal_completed": "production_adapter_module_promoted_and_regression_audited",
        "source_5d3_audit_all_passed": config.get("source_5d3_audit_all_passed"),
        "source_5d5_audit_all_passed": config.get("source_5d5_audit_all_passed"),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "observer_count": 2,
        "observer_agent_names": list(OBSERVER_AGENT_NAMES),
        "observer_agent_type": OBSERVER_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "same_model_teammate_and_target": False,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "adapter_class": config["adapter_class"],
        "adapter_module": ReusableMainlinePerceptionAdapter.__module__,
        "api_methods": list(config["api_methods"]),
        "production_module_created": True,
        "phase_local_only": False,
        "package_export_ok": migration.get("package_export_ok"),
        "offline_replay_case_count": len(offline_cases),
        "mainline_case_count": len(mainline_cases),
        "offline_trace_count": len(offline_trace),
        "mainline_trace_count": len(mainline_trace),
        "offline_target_all_found_step": offline_by_kind.get("target", {}).get("all_found_step"),
        "offline_coexist_all_found_step": offline_by_kind.get("coexist", {}).get("all_found_step"),
        "offline_teammate_false_positive_steps": offline_by_kind.get("teammate_only", {}).get("false_positive_steps"),
        "offline_duplicate_all_found_step": offline_by_kind.get("duplicate_replay", {}).get("all_found_step"),
        "mainline_target_terminated_reason": target_result.get("terminated_reason"),
        "mainline_target_time_to_all_found": target_result.get("time_to_all_found"),
        "mainline_coexist_terminated_reason": coexist_result.get("terminated_reason"),
        "mainline_coexist_time_to_all_found": coexist_result.get("time_to_all_found"),
        "mainline_teammate_terminated_reason": teammate_result.get("terminated_reason"),
        "mainline_teammate_find_times": teammate_result.get("find_times"),
        "mainline_teammate_false_positive_steps": [
            int(row.get("mainline_step", 0))
            for row in teammate_update_rows
            if any(bool(value) for value in row.get("detected_mask", []))
        ],
        "mainline_duplicate_terminated_reason": duplicate_result.get("terminated_reason"),
        "mainline_duplicate_time_to_all_found": duplicate_result.get("time_to_all_found"),
        "mainline_duplicate_detected_steps": [int(row.get("mainline_step", 0)) for row in duplicate_update_rows],
        "mainline_duplicate_accepted_candidate_counts": [
            int(row.get("source_accepted_candidate_count", 0)) for row in duplicate_update_rows
        ],
        "mainline_duplicate_fused_candidate_counts": [
            int(row.get("source_fused_candidate_count", 0)) for row in duplicate_update_rows
        ],
        "duplicate_observation_fused": any(
            int(row.get("source_accepted_candidate_count", 0)) >= 2
            and int(row.get("source_fused_candidate_count", 0)) == 1
            for row in duplicate_update_rows
        ),
        "mainline_update_found_mask_called": any(
            row.get("update_found_mask_original_called") is True for row in mainline_trace
        ),
        "mainline_found_mask_updated_from_adapter": any(
            row.get("new_found_indices") for row in mainline_trace if row.get("trace_type") == "mainline_update"
        ),
        "truth_flags_false": _truth_flags_false(offline_trace) and _truth_flags_false(mainline_trace),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "baseline_runtime_source_modified": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": True,
        "holoocean_bridge_modification_scope": config.get("holoocean_bridge_modification_scope"),
        "live_capture_long_term_callback_integrated": live_capture_eval.get("long_term_live_capture_callback_integrated"),
        "live_capture_deferred_to_next_phase": live_capture_eval.get("live_capture_deferred_to_next_phase"),
        "wall_time_s": round(time.perf_counter() - started, 6),
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-6 Production Mainline Perception Adapter Summary",
        "",
        "- Adapter Module: `{0}`".format(summary.get("adapter_module")),
        "- Production Module Created: `{0}`".format(summary.get("production_module_created")),
        "- Package Export OK: `{0}`".format(summary.get("package_export_ok")),
        "- Offline Target All Found Step: `{0}`".format(summary.get("offline_target_all_found_step")),
        "- Mainline Target Time To All Found: `{0}`".format(summary.get("mainline_target_time_to_all_found")),
        "- Mainline Coexist Time To All Found: `{0}`".format(summary.get("mainline_coexist_time_to_all_found")),
        "- Mainline Teammate False Positive Steps: `{0}`".format(summary.get("mainline_teammate_false_positive_steps")),
        "- Mainline Duplicate Detected Steps: `{0}`".format(summary.get("mainline_duplicate_detected_steps")),
        "- Duplicate Observation Fused: `{0}`".format(summary.get("duplicate_observation_fused")),
        "- Live Capture Long Term Callback Integrated: `{0}`".format(
            summary.get("live_capture_long_term_callback_integrated")
        ),
        "",
        "Phase 5D-6 promotes the reusable adapter API into a formal holoocean_bridge module and verifies the same static SphereAgent mainline found/all_found semantics as Phase 5D-5.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-compile", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    pre_status = _run_git_status()
    config = _phase_config(pre_status)
    production_contract = mainline_perception_adapter_contract()
    migration = _production_migration_manifest()
    live_capture_eval = _live_capture_interface_evaluation()
    events = _load_json(SOURCE_5D3_EVENTS_JSON)
    fusion = _load_json(SOURCE_5D3_FUSION_JSON)
    if not isinstance(events, list):
        raise RuntimeError("Phase 5D-3 events manifest is not a list")
    if not isinstance(fusion, list):
        raise RuntimeError("Phase 5D-3 fusion manifest is not a list")

    case_specs = [
        {"run_kind": "target", "source_run_kind": "target", "max_iters": 4, "schedule": None},
        {"run_kind": "coexist", "source_run_kind": "coexist", "max_iters": 4, "schedule": None},
        {"run_kind": "teammate_only", "source_run_kind": "teammate_only", "max_iters": 4, "schedule": None},
        {
            "run_kind": "duplicate_replay",
            "source_run_kind": "target",
            "max_iters": 4,
            "schedule": {1: False, 2: False, 3: True, 4: False},
        },
    ]

    offline_cases: List[Dict[str, Any]] = []
    mainline_cases: List[Dict[str, Any]] = []
    for spec in case_specs:
        event_rows, fusion_rows = _case_sources(
            str(spec["run_kind"]),
            str(spec["source_run_kind"]),
            events,
            fusion,
        )
        offline_cases.append(
            _offline_replay_case(
                run_kind=str(spec["run_kind"]),
                source_run_kind=str(spec["source_run_kind"]),
                event_rows=event_rows,
                fusion_rows=fusion_rows,
                force_schedule=spec["schedule"],
            )
        )
        mainline_cases.append(
            _run_mainline_case(
                run_kind=str(spec["run_kind"]),
                source_run_kind=str(spec["source_run_kind"]),
                event_rows=event_rows,
                fusion_rows=fusion_rows,
                max_iters=int(spec["max_iters"]),
                force_schedule=spec["schedule"],
            )
        )

    offline_trace: List[Dict[str, Any]] = []
    for case in offline_cases:
        offline_trace.extend(case.get("trace", []))

    mainline_trace: List[Dict[str, Any]] = []
    slim_mainline_cases: List[Dict[str, Any]] = []
    for case in mainline_cases:
        for row in case.get("adapter_detect_trace", []):
            trace_row = dict(row)
            trace_row["trace_type"] = "adapter_detect"
            mainline_trace.append(trace_row)
        for row in case.get("adapter_output_trace", []):
            trace_row = dict(row)
            trace_row["trace_type"] = "adapter_output"
            mainline_trace.append(trace_row)
        for row in case.get("mainline_update_trace", []):
            trace_row = dict(row)
            trace_row["trace_type"] = "mainline_update"
            mainline_trace.append(trace_row)
        slim = dict(case)
        slim.pop("adapter_detect_trace", None)
        slim.pop("adapter_output_trace", None)
        slim.pop("mainline_update_trace", None)
        slim_mainline_cases.append(slim)

    summary = _build_summary(
        config,
        migration,
        live_capture_eval,
        offline_cases,
        slim_mainline_cases,
        offline_trace,
        mainline_trace,
        started,
    )
    post_status = _run_git_status()
    protected_core_paths = [
        "baseline_GP/core_search_policy.py",
        "baseline_GP/core_execution.py",
        "baseline_GP/core_targets.py",
        "baseline_GP/core_intensity.py",
        "baseline_GP/core_safe_nav.py",
        "baseline_GP/marine_knownmap_runtime.py",
        "baseline_GP/marine_knownmap_runtime_2usv.py",
    ]
    git_doc = {
        "phase_name": PHASE_NAME,
        "pre_status": pre_status,
        "post_status": post_status,
        "protected_core_path_status": _run_git_status(protected_core_paths),
        "production_path_status": _run_git_status([PRODUCTION_MODULE_PATH, PRODUCTION_INIT_PATH]),
    }

    if not args.skip_compile:
        _run_compile_log(BASE_COMPILE_LOG)

    _save_json(CONFIG_JSON, config)
    _save_json(PRODUCTION_CONTRACT_JSON, production_contract)
    _save_json(MIGRATION_MANIFEST_JSON, migration)
    _save_json(OFFLINE_TRACE_JSON, offline_trace)
    _save_csv(OFFLINE_TRACE_CSV, offline_trace)
    _save_json(MAINLINE_TRACE_JSON, mainline_trace)
    _save_csv(MAINLINE_TRACE_CSV, mainline_trace)
    _save_json(MAINLINE_RESULTS_JSON, slim_mainline_cases)
    _save_json(LIVE_CAPTURE_EVAL_JSON, live_capture_eval)
    _save_json(SUMMARY_JSON, summary)
    _save_json(GIT_STATUS_JSON, git_doc)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary written to: {0}".format(SUMMARY_MD))


if __name__ == "__main__":
    main()
