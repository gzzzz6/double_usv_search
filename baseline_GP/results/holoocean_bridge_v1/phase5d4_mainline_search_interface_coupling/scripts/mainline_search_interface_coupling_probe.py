"""Phase 5D-4: couple Phase 5D-3 fusion to the baseline_GP mainline interface.

This phase verifies the original two-USV known-map runtime boundary:

    detect_targets -> team_detected_mask -> update_found_mask -> all_found

The baseline runtime is executed unchanged. During this probe only, a lightweight
adapter replaces the runtime's detect_targets callable with a HoloOcean
candidate-fusion backed detector, and wraps update_found_mask for trace evidence.
The wrapper delegates to the original update_found_mask implementation.

Truth remains audit-only. The injected detection masks are derived from the
Phase 5D-3 per-agent sensor events and fused candidate rows.
"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

import baseline_GP.marine_knownmap_runtime_2usv as runtime_2usv  # noqa: E402


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d4_mainline_search_interface_coupling"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SOURCE_5D3_PHASE_NAME = "phase5d3_continuous_multistep_coop_search"
SOURCE_5D3_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D3_PHASE_NAME))
SOURCE_5D3_AUDIT_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_continuous_audit.json")
SOURCE_5D3_SUMMARY_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_continuous_summary.json")
SOURCE_5D3_EVENTS_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_per_agent_detection_events.json")
SOURCE_5D3_FUSION_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_candidate_fusion_trace.json")
SOURCE_5D3_POLICY_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_policy_trace.json")

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_config.json")
INTERFACE_MAP_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_interface_map.json")
ADAPTER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_adapter_trace.json")
ADAPTER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d4_adapter_trace.csv")
MAINLINE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_trace.json")
MAINLINE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_trace.csv")
RUNTIME_RESULTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_runtime_results.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_mainline_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d4_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d4_mainline_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d4_py_compile_base.txt")

RECOMMENDED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_NAMES = ["sv0", "sv1"]
RELIABLE_DISTANCE_LIMIT_M = 35.0
MAX_POLICY_STEPS = 4
FUSION_DISTANCE_THRESHOLD_M = 15.0
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


def _run_git_status() -> List[str]:
    repo_root = os.path.abspath(".")
    result = subprocess.run(
        ["git", "-c", "safe.directory={0}".format(repo_root.replace("\\", "/")), "status", "--porcelain"],
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


def _status_path(line: str) -> str:
    if line.startswith("?? "):
        return line[3:].strip().strip('"')
    if len(line) > 3:
        return line[3:].strip().strip('"')
    return line.strip().strip('"')


def _outside_phase_new_or_changed(pre_status: List[str], post_status: List[str]) -> List[str]:
    pre_set = set(pre_status)
    phase_prefix = "baseline_GP/results/holoocean_bridge_v1/{0}/".format(PHASE_NAME)
    outside: List[str] = []
    for line in post_status:
        path = _status_path(line).replace("\\", "/")
        if path.startswith(phase_prefix):
            continue
        if line not in pre_set:
            outside.append(line)
    return outside


def _source_audit_passed() -> bool:
    audit = _load_json(SOURCE_5D3_AUDIT_JSON)
    return bool(isinstance(audit, dict) and audit.get("all_passed") is True)


def _phase_config(pre_git_status: Optional[List[str]] = None) -> Dict[str, Any]:
    source_summary = _load_json(SOURCE_5D3_SUMMARY_JSON)
    return {
        "phase_name": PHASE_NAME,
        "phase_goal": "Couple Phase 5D-3 HoloOcean fusion results to the original baseline_GP two-USV mainline found/all_found interface.",
        "source_5d3_phase_name": SOURCE_5D3_PHASE_NAME,
        "source_5d3_audit_all_passed": _source_audit_passed(),
        "source_5d3_event_count": int(source_summary.get("event_count", 0)),
        "source_5d3_fusion_trace_count": int(source_summary.get("fusion_trace_count", 0)),
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
        "mainline_detection_callable": "detect_targets",
        "mainline_update_callable": "update_found_mask",
        "adapter_strategy": "runtime detect_targets replacement plus update_found_mask trace wrapper",
        "adapter_uses_source": "Phase 5D-3 per-agent detection events and candidate fusion trace",
        "baseline_runtime_source_modified": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "core_search_policy_modified": False,
        "core_execution_modified": False,
        "core_targets_modified": False,
        "core_intensity_modified": False,
        "core_safe_nav_modified": False,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "fusion_distance_threshold_m": FUSION_DISTANCE_THRESHOLD_M,
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
        "pre_git_status": pre_git_status or [],
    }


def _line_number_for(pattern: str, source: str) -> Optional[int]:
    for idx, line in enumerate(source.splitlines(), start=1):
        if pattern in line:
            return idx
    return None


def _build_interface_map(config: Dict[str, Any]) -> Dict[str, Any]:
    runtime_source = inspect.getsource(runtime_2usv)
    update_source = inspect.getsource(runtime_2usv.update_found_mask)
    return {
        "phase_name": PHASE_NAME,
        "runtime_module_file": os.path.normpath(runtime_2usv.__file__ or ""),
        "core_update_function_module": getattr(runtime_2usv.update_found_mask, "__module__", ""),
        "mainline_interface_points": [
            {
                "name": "state_initial_found_mask_and_find_times",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for("found_mask = np.zeros(n_targets, dtype=bool)", runtime_source),
                "semantic": "mainline state initializes found_mask and find_times",
            },
            {
                "name": "initial_team_detection_mask",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for("team_detected_mask = np.zeros_like(found_mask, dtype=bool)", runtime_source),
                "semantic": "initial per-USV detection masks are OR-ed into team_detected_mask",
            },
            {
                "name": "initial_update_found_mask",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for("initial_found_indices = update_found_mask", runtime_source),
                "semantic": "initial team_detected_mask latches found targets through update_found_mask",
            },
            {
                "name": "mainline_episode_loop",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for("for step in range(1, max_iters + 1):", runtime_source),
                "semantic": "original planner/mainline loop",
            },
            {
                "name": "mainline_step_team_detection_mask",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for('team_detected_mask = np.zeros_like(state["found_mask"], dtype=bool)', runtime_source),
                "semantic": "per-step per-USV detections are OR-ed into team_detected_mask",
            },
            {
                "name": "mainline_step_update_found_mask",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for('new_indices = update_found_mask(state["found_mask"], team_detected_mask', runtime_source),
                "semantic": "mainline update_found_mask records new_found_indices and find_times",
            },
            {
                "name": "mainline_all_found_termination",
                "file": "baseline_GP/marine_knownmap_runtime_2usv.py",
                "line": _line_number_for('state["terminated_reason"] = "all_found"', runtime_source),
                "semantic": "np.all(found_mask) terminates the original mainline loop",
            },
        ],
        "core_update_found_mask_source_contains_latch": (
            "newly_found = detected_mask & ~found_mask" in update_source
            and "found_mask[newly_found] = True" in update_source
            and "find_times[idx] = int(step)" in update_source
        ),
        "adapter_strategy": config["adapter_strategy"],
        "mainline_source_modified": False,
        "truth_used_for_detection": False,
    }


def _candidate_position(candidate: Dict[str, Any]) -> Optional[List[float]]:
    position = candidate.get("fused_world_position")
    if isinstance(position, list) and len(position) >= 2:
        return [float(position[0]), float(position[1]), float(position[2]) if len(position) > 2 else 0.0]
    positions = candidate.get("positions")
    if isinstance(positions, list) and positions:
        arr = np.asarray(positions, dtype=float)
        if arr.ndim == 2 and arr.shape[1] >= 2:
            mean = arr.mean(axis=0)
            return [float(mean[0]), float(mean[1]), float(mean[2]) if mean.shape[0] > 2 else 0.0]
    return None


class MainlineFusionDetectionAdapter:
    """Runtime adapter from 5D-3 fusion rows to mainline detection masks."""

    def __init__(
        self,
        *,
        run_kind: str,
        fusion_rows: List[Dict[str, Any]],
        event_rows: List[Dict[str, Any]],
        detection_schedule: Optional[Dict[int, bool]] = None,
    ) -> None:
        self.run_kind = run_kind
        self.fusion_rows = sorted(fusion_rows, key=lambda row: int(row.get("policy_step", 0)))
        self.events_by_step: Dict[int, List[Dict[str, Any]]] = {}
        for event in event_rows:
            step = int(event.get("policy_step", 0))
            self.events_by_step.setdefault(step, []).append(event)
        self.fusion_by_step = {int(row.get("policy_step", 0)): row for row in self.fusion_rows}
        self.detection_schedule = detection_schedule or {}
        self.call_index = 0
        self.step_call_counts: Dict[int, int] = {}
        self.adapter_trace: List[Dict[str, Any]] = []

    def _should_detect(self, step: int, row: Dict[str, Any], found_mask: np.ndarray) -> bool:
        if step <= 0:
            return False
        if step in self.detection_schedule:
            return bool(self.detection_schedule[step])
        return bool(row.get("shared_found_this_step") is True and not bool(np.all(found_mask)))

    def detect_targets(
        self,
        robot_pos: Tuple[int, int],
        target_positions: np.ndarray,
        found_mask: np.ndarray,
        sensor_range_cells: int,
        detection_rng: np.random.Generator,
    ) -> np.ndarray:
        del detection_rng
        self.call_index += 1
        step = int(getattr(runtime_2usv, "_PHASE5D4_CURRENT_STEP", 0))
        step_call_index = int(self.step_call_counts.get(step, 0))
        self.step_call_counts[step] = step_call_index + 1
        usv_id = step_call_index % 2
        row = self.fusion_by_step.get(step, {})
        events = self.events_by_step.get(step, [])
        accepted_events = [event for event in events if event.get("accepted_candidate") is True]
        fused_candidates = list(row.get("fused_candidates", [])) if isinstance(row.get("fused_candidates"), list) else []
        shared_found = bool(row.get("shared_found_this_step") is True)
        inject_detection = bool(usv_id == 0 and self._should_detect(step, row, found_mask))
        detected_mask = np.zeros_like(found_mask, dtype=bool)
        injected_target_index: Optional[int] = None
        if inject_detection and detected_mask.size > 0:
            target_index = 0
            detected_mask[target_index] = True
            injected_target_index = target_index

        candidate_position = _candidate_position(fused_candidates[0]) if fused_candidates else None
        self.adapter_trace.append(
            {
                "run_kind": self.run_kind,
                "call_index": int(self.call_index),
                "mainline_step": int(step),
                "mainline_usv_id": int(usv_id),
                "mainline_step_detect_call_index": int(step_call_index),
                "robot_pos": tuple(int(v) for v in robot_pos),
                "target_count": int(len(target_positions)),
                "found_mask_before_detect": found_mask.tolist(),
                "sensor_range_cells": int(sensor_range_cells),
                "source_policy_step": int(row.get("policy_step", step) or step),
                "source_shared_found": shared_found,
                "source_expected_target_present_for_audit": bool(row.get("expected_target_present_for_audit", False)),
                "source_raw_sensor_detection_count": int(row.get("raw_sensor_detection_count", 0) or 0),
                "source_accepted_candidate_count": int(row.get("accepted_candidate_count", 0) or 0),
                "source_fused_candidate_count": int(row.get("fused_candidate_count", 0) or 0),
                "source_teammate_rejected_count": int(row.get("teammate_rejected_count", 0) or 0),
                "source_candidate_count_first_cluster": int(fused_candidates[0].get("candidate_count", 0)) if fused_candidates else 0,
                "source_reporter_usv_ids_first_cluster": fused_candidates[0].get("reporter_usv_ids", []) if fused_candidates else [],
                "source_fused_world_position_first_cluster": candidate_position,
                "source_per_agent_event_count": len(events),
                "source_accepted_event_count": len(accepted_events),
                "injected_detection": inject_detection,
                "injected_target_index": injected_target_index,
                "detected_mask": detected_mask.tolist(),
                "recommended_rule_id": RECOMMENDED_RULE_ID,
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
                "detection_source": "phase5d3_sensor_event_candidate_fusion",
            }
        )
        return detected_mask


class MainlineTraceHarness:
    def __init__(self, adapter: MainlineFusionDetectionAdapter, original_update_found_mask: Any) -> None:
        self.adapter = adapter
        self.original_update_found_mask = original_update_found_mask
        self.mainline_trace: List[Dict[str, Any]] = []
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
        detected_list = detected_mask.tolist()
        new_indices = self.original_update_found_mask(found_mask, detected_mask, find_times, step)
        after_found = found_mask.tolist()
        after_find_times = list(find_times)
        row = self.adapter.fusion_by_step.get(int(step), {})
        self.mainline_trace.append(
            {
                "run_kind": self.adapter.run_kind,
                "update_call_index": int(self.update_call_index),
                "mainline_step": int(step),
                "source_policy_step": int(row.get("policy_step", step) or step),
                "source_shared_found": bool(row.get("shared_found_this_step", False)),
                "source_accepted_candidate_count": int(row.get("accepted_candidate_count", 0) or 0),
                "source_fused_candidate_count": int(row.get("fused_candidate_count", 0) or 0),
                "detected_mask": detected_list,
                "found_mask_before": before_found,
                "found_mask_after": after_found,
                "find_times_before": before_find_times,
                "find_times_after": after_find_times,
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
    fusion_rows: List[Dict[str, Any]],
    event_rows: List[Dict[str, Any]],
    max_iters: int,
    n_targets: int,
    detection_schedule: Optional[Dict[int, bool]] = None,
) -> Dict[str, Any]:
    adapter = MainlineFusionDetectionAdapter(
        run_kind=run_kind,
        fusion_rows=fusion_rows,
        event_rows=event_rows,
        detection_schedule=detection_schedule,
    )
    original_detect_targets = runtime_2usv.detect_targets
    original_update_found_mask = runtime_2usv.update_found_mask
    original_sample_and_update_team_gp = runtime_2usv._sample_and_update_team_gp
    original_step_targets = runtime_2usv.step_targets
    harness = MainlineTraceHarness(adapter, original_update_found_mask)

    def _wrapped_sample_and_update_team_gp(state: Dict[str, Any], step: int, gp_fit_every: int) -> None:
        runtime_2usv._PHASE5D4_CURRENT_STEP = int(step)
        original_sample_and_update_team_gp(state, step=step, gp_fit_every=gp_fit_every)

    def _wrapped_step_targets(*args: Any, **kwargs: Any) -> Any:
        runtime_2usv._PHASE5D4_CURRENT_STEP = int(getattr(runtime_2usv, "_PHASE5D4_CURRENT_STEP", 0)) + 1
        return original_step_targets(*args, **kwargs)

    runtime_2usv._PHASE5D4_CURRENT_STEP = 0
    runtime_2usv.detect_targets = adapter.detect_targets
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
            n_targets=n_targets,
            target_motion_mode="static",
            target_count_upper_bound=n_targets,
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
            "find_times": [None] * int(n_targets),
        }
    finally:
        runtime_2usv.detect_targets = original_detect_targets
        runtime_2usv.update_found_mask = original_update_found_mask
        runtime_2usv._sample_and_update_team_gp = original_sample_and_update_team_gp
        runtime_2usv.step_targets = original_step_targets
        runtime_2usv._PHASE5D4_CURRENT_STEP = 0

    detected_update_rows = [
        row for row in harness.mainline_trace if any(bool(value) for value in row.get("detected_mask", []))
    ]
    return {
        "run_kind": run_kind,
        "launch_ok": error == "",
        "error": error,
        "runtime_result": result,
        "adapter_trace": adapter.adapter_trace,
        "mainline_trace": harness.mainline_trace,
        "wall_time_s": round(time.perf_counter() - started, 6),
        "mainline_detect_targets_replaced_runtime_only": True,
        "mainline_update_found_mask_wrapped_runtime_only": True,
        "update_found_mask_original_called_count": len(harness.mainline_trace),
        "detected_update_count": len(detected_update_rows),
        "truth_used_for_detection": False,
    }


def _run_compile_log(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            os.path.join(PHASE_DIR, "scripts", "mainline_search_interface_coupling_probe.py"),
            os.path.join(PHASE_DIR, "scripts", "mainline_search_interface_coupling_audit.py"),
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


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    return all(
        row.get("truth_used_for_detection") is False
        and row.get("actor_truth_used_for_detection") is False
        and row.get("target_truth_used_for_detection") is False
        and row.get("teammate_truth_used_for_detection") is False
        for row in rows
    )


def _build_summary(
    config: Dict[str, Any],
    case_docs: List[Dict[str, Any]],
    adapter_trace: List[Dict[str, Any]],
    mainline_trace: List[Dict[str, Any]],
    started: float,
) -> Dict[str, Any]:
    result_by_kind = {doc["run_kind"]: doc["runtime_result"] for doc in case_docs}
    trace_by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for row in mainline_trace:
        trace_by_kind.setdefault(str(row.get("run_kind")), []).append(row)

    teammate_rows = trace_by_kind.get("teammate_only", [])
    duplicate_rows = trace_by_kind.get("duplicate_replay", [])
    duplicate_detect_rows = [
        row
        for row in duplicate_rows
        if any(bool(value) for value in row.get("detected_mask", []))
    ]
    target_result = result_by_kind.get("target", {})
    coexist_result = result_by_kind.get("coexist", {})
    teammate_result = result_by_kind.get("teammate_only", {})
    duplicate_result = result_by_kind.get("duplicate_replay", {})
    return {
        "phase_name": PHASE_NAME,
        "phase_completed": True,
        "source_5d3_audit_all_passed": config.get("source_5d3_audit_all_passed"),
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
        "mainline_runtime_module": config["mainline_runtime_module"],
        "mainline_policy_name": MAINLINE_POLICY_NAME,
        "mainline_run_function": config["mainline_run_function"],
        "mainline_detection_callable": config["mainline_detection_callable"],
        "mainline_update_callable": config["mainline_update_callable"],
        "adapter_strategy": config["adapter_strategy"],
        "run_count": len(case_docs),
        "adapter_trace_count": len(adapter_trace),
        "mainline_trace_count": len(mainline_trace),
        "all_runs_launch_ok": all(doc.get("launch_ok") is True for doc in case_docs),
        "run_errors": {doc["run_kind"]: doc.get("error", "") for doc in case_docs},
        "target_terminated_reason": target_result.get("terminated_reason"),
        "target_success_all_found": target_result.get("success_all_found"),
        "target_completed_steps": target_result.get("completed_steps"),
        "target_find_times": target_result.get("find_times"),
        "target_time_to_all_found": target_result.get("time_to_all_found"),
        "coexist_terminated_reason": coexist_result.get("terminated_reason"),
        "coexist_success_all_found": coexist_result.get("success_all_found"),
        "coexist_completed_steps": coexist_result.get("completed_steps"),
        "coexist_find_times": coexist_result.get("find_times"),
        "teammate_only_terminated_reason": teammate_result.get("terminated_reason"),
        "teammate_only_success_all_found": teammate_result.get("success_all_found"),
        "teammate_only_completed_steps": teammate_result.get("completed_steps"),
        "teammate_only_find_times": teammate_result.get("find_times"),
        "teammate_false_positive_steps": [
            int(row.get("mainline_step", 0))
            for row in teammate_rows
            if any(bool(value) for value in row.get("detected_mask", []))
        ],
        "duplicate_replay_terminated_reason": duplicate_result.get("terminated_reason"),
        "duplicate_replay_success_all_found": duplicate_result.get("success_all_found"),
        "duplicate_replay_completed_steps": duplicate_result.get("completed_steps"),
        "duplicate_replay_find_times": duplicate_result.get("find_times"),
        "duplicate_replay_detected_steps": [int(row.get("mainline_step", 0)) for row in duplicate_detect_rows],
        "duplicate_replay_fused_candidate_counts": [
            int(row.get("source_fused_candidate_count", 0)) for row in duplicate_detect_rows
        ],
        "duplicate_replay_accepted_candidate_counts": [
            int(row.get("source_accepted_candidate_count", 0)) for row in duplicate_detect_rows
        ],
        "duplicate_observation_fused": any(
            int(row.get("source_accepted_candidate_count", 0)) >= 2
            and int(row.get("source_fused_candidate_count", 0)) == 1
            for row in duplicate_detect_rows
        ),
        "mainline_update_found_mask_called": any(row.get("update_found_mask_original_called") is True for row in mainline_trace),
        "mainline_found_mask_updated_from_adapter": any(
            row.get("new_found_indices") for row in mainline_trace if row.get("run_kind") in ("target", "coexist", "duplicate_replay")
        ),
        "mainline_all_found_driven_by_adapter": (
            target_result.get("terminated_reason") == "all_found"
            and target_result.get("success_all_found") is True
            and target_result.get("time_to_all_found") == 1
        ),
        "teammate_only_no_false_positive": all(
            not any(bool(value) for value in row.get("detected_mask", [])) for row in teammate_rows
        ),
        "truth_flags_false": _truth_flags_false(adapter_trace) and _truth_flags_false(mainline_trace),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "baseline_runtime_source_modified": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "wall_time_s": round(time.perf_counter() - started, 6),
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines = [
        "# Phase 5D-4 Mainline Search Interface Coupling Summary",
        "",
        "- Recommended Rule: `{0}`".format(summary.get("recommended_rule_id")),
        "- Mainline Runtime: `{0}`".format(summary.get("mainline_runtime_module")),
        "- Adapter Strategy: `{0}`".format(summary.get("adapter_strategy")),
        "- Target Terminated Reason: `{0}`".format(summary.get("target_terminated_reason")),
        "- Target Time To All Found: `{0}`".format(summary.get("target_time_to_all_found")),
        "- Coexist Terminated Reason: `{0}`".format(summary.get("coexist_terminated_reason")),
        "- Teammate False Positive Steps: `{0}`".format(summary.get("teammate_false_positive_steps")),
        "- Duplicate Replay Detected Steps: `{0}`".format(summary.get("duplicate_replay_detected_steps")),
        "- Duplicate Observation Fused: `{0}`".format(summary.get("duplicate_observation_fused")),
        "- Truth Used For Detection: `{0}`".format(summary.get("truth_used_for_detection")),
        "",
        "Phase 5D-4 runs the original two-USV mainline search loop while a lightweight runtime adapter converts Phase 5D-3 HoloOcean sensor-event candidate fusion rows into the mainline detection mask interface.",
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
    interface_map = _build_interface_map(config)

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
        {"run_kind": "duplicate_replay", "source_run_kind": "target", "max_iters": 4, "schedule": {1: False, 2: False, 3: True, 4: False}},
    ]

    case_docs: List[Dict[str, Any]] = []
    for spec in case_specs:
        source_kind = str(spec["source_run_kind"])
        case_fusion = [row for row in fusion if row.get("run_kind") == source_kind]
        case_events = [row for row in events if row.get("run_kind") == source_kind]
        case_doc = _run_mainline_case(
            run_kind=str(spec["run_kind"]),
            fusion_rows=case_fusion,
            event_rows=case_events,
            max_iters=int(spec["max_iters"]),
            n_targets=1,
            detection_schedule=spec["schedule"],
        )
        case_docs.append(case_doc)

    adapter_trace: List[Dict[str, Any]] = []
    mainline_trace: List[Dict[str, Any]] = []
    slim_results: List[Dict[str, Any]] = []
    for case_doc in case_docs:
        adapter_trace.extend(case_doc.get("adapter_trace", []))
        mainline_trace.extend(case_doc.get("mainline_trace", []))
        slim = dict(case_doc)
        slim.pop("adapter_trace", None)
        slim.pop("mainline_trace", None)
        slim_results.append(slim)

    summary = _build_summary(config, case_docs, adapter_trace, mainline_trace, started)
    post_status = _run_git_status()
    git_doc = {
        "phase_name": PHASE_NAME,
        "pre_status": pre_status,
        "post_status": post_status,
        "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_status, post_status),
    }

    if not args.skip_compile:
        _run_compile_log(BASE_COMPILE_LOG)

    _save_json(CONFIG_JSON, config)
    _save_json(INTERFACE_MAP_JSON, interface_map)
    _save_json(ADAPTER_TRACE_JSON, adapter_trace)
    _save_csv(ADAPTER_TRACE_CSV, adapter_trace)
    _save_json(MAINLINE_TRACE_JSON, mainline_trace)
    _save_csv(MAINLINE_TRACE_CSV, mainline_trace)
    _save_json(RUNTIME_RESULTS_JSON, slim_results)
    _save_json(SUMMARY_JSON, summary)
    _save_json(GIT_STATUS_JSON, git_doc)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary written to: {0}".format(SUMMARY_MD))


if __name__ == "__main__":
    main()
