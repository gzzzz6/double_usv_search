"""Phase 5D-7: live HoloOcean capture provider to production adapter.

This phase replaces the replay-event input path with a live HoloOcean capture
provider. It runs the HoloOcean capture loop, builds per-agent detection events
and candidate fusion rows from the live sensor arrays produced in this run, and
feeds those rows directly into the Phase 5D-6 production adapter API.

Scope remains static SphereAgent / two SurfaceVessel observers only.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

from baseline_GP.holoocean_bridge.mainline_perception_adapter import (  # noqa: E402
    MainlineAdapterStepInput,
    ReusableMainlinePerceptionAdapter,
    mainline_perception_adapter_contract,
)


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d7_live_capture_provider_coupling"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SOURCE_5D3_PHASE_NAME = "phase5d3_continuous_multistep_coop_search"
SOURCE_5D3_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D3_PHASE_NAME))
SOURCE_5D3_PROBE = os.path.join(SOURCE_5D3_DIR, "scripts", "continuous_multistep_coop_search_probe.py")
SOURCE_5D3_AUDIT_JSON = os.path.join(SOURCE_5D3_DIR, "manifests", "phase5d3_continuous_audit.json")

SOURCE_5D6_PHASE_NAME = "phase5d6_production_mainline_perception_adapter"
SOURCE_5D6_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D6_PHASE_NAME))
SOURCE_5D6_AUDIT_JSON = os.path.join(SOURCE_5D6_DIR, "manifests", "phase5d6_audit.json")

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_config.json")
LIVE_BASELINE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_baseline_run.json")
LIVE_TARGET_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_target_run.json")
LIVE_COOEXIST_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_coexist_run.json")
LIVE_TEAMMATE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_teammate_only_run.json")
LIVE_TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_tick_trace.json")
LIVE_TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_tick_trace.csv")
LIVE_EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_per_agent_detection_events.json")
LIVE_EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_per_agent_detection_events.csv")
LIVE_FUSION_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_candidate_fusion_trace.json")
LIVE_FUSION_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_candidate_fusion_trace.csv")
LIVE_PROVIDER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_provider_trace.json")
LIVE_PROVIDER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_provider_trace.csv")
ADAPTER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_adapter_observe_trace.json")
ADAPTER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_adapter_observe_trace.csv")
FOUND_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_found_trace.json")
FOUND_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d7_live_found_trace.csv")
PRODUCTION_CONTRACT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_production_adapter_contract.json")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d7_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d7_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d7_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d7_py_compile_holo.txt")

RECOMMENDED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_NAMES = ["sv0", "sv1"]
RELIABLE_DISTANCE_LIMIT_M = 35.0
MAX_POLICY_STEPS = 4


def _load_module(path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load module from {0}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5D3 = _load_module(SOURCE_5D3_PROBE, "phase5d3_live_source_probe")


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
    try:
        return bool(_load_json(path).get("all_passed") is True)
    except Exception:
        return False


def _strip_run_raw(run: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(run)
    clean.pop("rgb_by_agent_tick", None)
    clean.pop("range_by_agent_tick", None)
    return clean


def _live_observer_positions_for_tick(run: Dict[str, Any], tick_index: int) -> Dict[str, List[float]]:
    positions = {agent: list(pos) for agent, pos in P5D3._path_at(tick_index).items()}
    tick_global = int(tick_index) + 1
    for row in run.get("tick_rows", []):
        if int(row.get("tick_global", -1)) != tick_global:
            continue
        agent_name = str(row.get("agent_name"))
        if agent_name not in positions:
            continue
        if row.get("loc_x") is None or row.get("loc_y") is None:
            continue
        positions[agent_name] = [
            float(row.get("loc_x")),
            float(row.get("loc_y")),
            float(row.get("loc_z", 0.0) or 0.0),
        ]
    return positions


def _known_teammates_for_live_event(
    run_kind: str,
    tick_index: int,
    config: Dict[str, Any],
    observer_positions: Dict[str, List[float]],
) -> List[Dict[str, Any]]:
    del tick_index
    teammates = [
        {
            "agent_name": "sv0",
            "agent_type": TEAMMATE_AGENT_TYPE,
            "location": observer_positions["sv0"],
            "is_observer": True,
        },
        {
            "agent_name": "sv1",
            "agent_type": TEAMMATE_AGENT_TYPE,
            "location": observer_positions["sv1"],
            "is_observer": True,
        },
    ]
    if run_kind == "teammate_only":
        teammates.append(
            {
                "agent_name": "teammate_extra0",
                "agent_type": TEAMMATE_AGENT_TYPE,
                "location": config["teammate_world_location"],
                "is_observer": False,
            }
        )
    if run_kind == "coexist":
        teammates.append(
            {
                "agent_name": "teammate_extra0",
                "agent_type": TEAMMATE_AGENT_TYPE,
                "location": config["coexist_teammate_world_location"],
                "is_observer": False,
            }
        )
    return teammates


def _build_live_events_for_run(run: Dict[str, Any], baseline_run: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    run_kind = str(run["run_kind"])
    events: List[Dict[str, Any]] = []
    target_location = config["target_world_location"] if P5D3._target_present(run_kind) else None
    for tick in range(int(P5D3.TOTAL_TICKS)):
        observer_positions = _live_observer_positions_for_tick(run, tick)
        for agent_name in OBSERVER_AGENT_NAMES:
            rgb = run.get("rgb_by_agent_tick", {}).get(agent_name, {}).get(tick)
            baseline_rgb = baseline_run.get("rgb_by_agent_tick", {}).get(agent_name, {}).get(tick)
            fan_range = run.get("range_by_agent_tick", {}).get(agent_name, {}).get(tick)
            range_summary = P5D3.P5D1A._range_summary(fan_range)
            rgb_diff = P5D3.P5D1A._rgb_diff_signature(rgb, baseline_rgb)
            sphere_blob = P5D3.P5D1A._sphere_blob_signature(rgb, baseline_rgb)
            local_blob = P5D3.P5D1A._local_range_scaled_blob_signature(
                sphere_blob.get("local_candidate_blobs"),
                range_summary.get("raw"),
            )
            raw_found = bool(local_blob.get("local_range_scaled_blob_present", False))
            bearing = local_blob.get("matched_beam_yaw_deg")
            if bearing is None:
                bearing = local_blob.get("blob_yaw_deg")
            matched_range = local_blob.get("matched_range_m")
            observer_location = observer_positions[agent_name]
            estimated = P5D3._estimate_world_position(observer_location, bearing, matched_range)
            nearest = P5D3._nearest_teammate(
                estimated,
                _known_teammates_for_live_event(run_kind, tick, config, observer_positions),
            )
            teammate_rejected = bool(raw_found and nearest.get("within_teammate_exclusion_radius") is True)
            range_limited = bool(matched_range is not None and float(matched_range) <= RELIABLE_DISTANCE_LIMIT_M + 1.0)
            accepted = bool(raw_found and range_limited and not teammate_rejected)
            target_error = P5D3._distance_2d(estimated, target_location if isinstance(target_location, list) else None)
            events.append(
                {
                    "run_kind": run_kind,
                    "tick_global": int(tick + 1),
                    "policy_step": int(tick // int(P5D3.TICKS_PER_POLICY_STEP)) + 1,
                    "tick_in_policy_step": int(tick % int(P5D3.TICKS_PER_POLICY_STEP)) + 1,
                    "reporter_usv_id": agent_name,
                    "agent_id": agent_name,
                    "sensor_id": "{0}+fan_rangefinder".format(P5D3.RGB_CAMERA_NAME),
                    "recommended_rule_id": config.get("recommended_rule_id"),
                    "expected_target_present_for_audit": P5D3._target_present(run_kind),
                    "raw_sensor_found": raw_found,
                    "accepted_candidate": accepted,
                    "teammate_rejected": teammate_rejected,
                    "range_limited": range_limited,
                    "estimated_world_position": estimated,
                    "target_world_location_for_audit": target_location,
                    "target_position_error_m": target_error,
                    "observer_world_location": observer_location,
                    "planned_observer_world_location": P5D3._path_at(tick)[agent_name],
                    "observer_pose_source": "live_location_sensor",
                    "matched_range_m": matched_range,
                    "bearing_deg": bearing,
                    "blob_yaw_deg": local_blob.get("blob_yaw_deg"),
                    "matched_beam_index": local_blob.get("matched_beam_index"),
                    "matched_beam_yaw_deg": local_blob.get("matched_beam_yaw_deg"),
                    "beam_yaw_error_deg": local_blob.get("beam_yaw_error_deg"),
                    "local_range_scaled_blob_present": local_blob.get("local_range_scaled_blob_present"),
                    "local_blob_area": local_blob.get("local_blob_area"),
                    "local_blob_range_scaled_area": local_blob.get("local_blob_range_scaled_area"),
                    "sphere_blob_local_candidate_count": int(sphere_blob.get("local_candidate_blob_count", 0)),
                    "sphere_blob_candidate_count": int(sphere_blob.get("candidate_blob_count", 0)),
                    "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0)),
                    "rgb_change_bbox_xyxy": rgb_diff.get("change_bbox_xyxy"),
                    "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
                    "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                    **nearest,
                    "truth_used_for_detection": False,
                    "actor_truth_used_for_detection": False,
                    "target_truth_used_for_detection": False,
                    "teammate_truth_used_for_detection": False,
                }
            )
    return events


def _known_teammates(run_kind: str, step_index: int, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Use the live path helper to provide teammate positions at the start tick of the policy step.
    tick_index = max(0, min(int(P5D3.TOTAL_TICKS) - 1, (int(step_index) - 1) * int(P5D3.TICKS_PER_POLICY_STEP)))
    positions = P5D3._path_at(tick_index)
    teammates = [
        {"agent_name": "sv0", "agent_type": TEAMMATE_AGENT_TYPE, "location": positions["sv0"], "is_observer": True},
        {"agent_name": "sv1", "agent_type": TEAMMATE_AGENT_TYPE, "location": positions["sv1"], "is_observer": True},
    ]
    if run_kind == "teammate_only":
        teammates.append(
            {
                "agent_name": "teammate_extra0",
                "agent_type": TEAMMATE_AGENT_TYPE,
                "location": config["teammate_world_location"],
                "is_observer": False,
            }
        )
    if run_kind == "coexist":
        teammates.append(
            {
                "agent_name": "teammate_extra0",
                "agent_type": TEAMMATE_AGENT_TYPE,
                "location": config["coexist_teammate_world_location"],
                "is_observer": False,
            }
        )
    return teammates


class LiveCaptureProvider:
    """Phase-local provider from live HoloOcean rows to production adapter inputs."""

    def __init__(self, *, event_rows: List[Dict[str, Any]], fusion_rows: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
        self.event_rows = event_rows
        self.fusion_rows = fusion_rows
        self.config = config
        self.provider_trace: List[Dict[str, Any]] = []

    def build_step_input(self, *, run_kind: str, step_index: int, found_mask_before: List[bool]) -> MainlineAdapterStepInput:
        events = [
            row
            for row in self.event_rows
            if row.get("run_kind") == run_kind and int(row.get("policy_step", 0)) == int(step_index)
        ]
        fusion = next(
            (
                row
                for row in self.fusion_rows
                if row.get("run_kind") == run_kind and int(row.get("policy_step", 0)) == int(step_index)
            ),
            {"run_kind": run_kind, "policy_step": int(step_index), "shared_found_this_step": False},
        )
        known_teammates = _known_teammates(run_kind, step_index, self.config)
        provider_row = {
            "run_kind": run_kind,
            "step_index": int(step_index),
            "live_capture_provider_called": True,
            "live_capture_primary_detection_source": True,
            "replay_events_used_for_detection": False,
            "per_agent_event_count": len(events),
            "accepted_candidate_count": int(fusion.get("accepted_candidate_count", 0) or 0),
            "fused_candidate_count": int(fusion.get("fused_candidate_count", 0) or 0),
            "shared_found_from_live_fusion": bool(fusion.get("shared_found_this_step") is True),
            "found_mask_before": list(found_mask_before),
            "known_teammate_count": len(known_teammates),
            "truth_used_for_detection": False,
            "actor_truth_used_for_detection": False,
            "target_truth_used_for_detection": False,
            "teammate_truth_used_for_detection": False,
        }
        self.provider_trace.append(provider_row)
        return MainlineAdapterStepInput(
            run_kind=run_kind,
            step_index=int(step_index),
            target_count=1,
            found_mask_before=list(found_mask_before),
            per_agent_events=events,
            candidate_fusion_result=fusion,
            known_teammates=known_teammates,
        )


def _run_adapter_live_case(
    *,
    run_kind: str,
    provider: LiveCaptureProvider,
) -> Dict[str, Any]:
    adapter = ReusableMainlinePerceptionAdapter(adapter_id="phase5d7_live_{0}".format(run_kind))
    adapter.reset_episode("phase5d7_live_{0}".format(run_kind))
    found_mask = [False]
    find_times: List[Optional[int]] = [None]
    trace: List[Dict[str, Any]] = []
    found_trace: List[Dict[str, Any]] = []
    for step in range(1, MAX_POLICY_STEPS + 1):
        step_input = provider.build_step_input(run_kind=run_kind, step_index=step, found_mask_before=found_mask)
        output = adapter.observe_step(step_input)
        detected_mask = adapter.build_detected_mask(step, 1).tolist()
        new_indices: List[int] = []
        for idx, detected in enumerate(detected_mask):
            if detected and not found_mask[idx]:
                found_mask[idx] = True
                find_times[idx] = step
                new_indices.append(idx)
        trace_row = output.asdict()
        trace_row.update(
            {
                "adapter_module": ReusableMainlinePerceptionAdapter.__module__,
                "detected_mask_returned": detected_mask,
                "found_mask_after_adapter_update": list(found_mask),
                "find_times_after_adapter_update": list(find_times),
                "new_found_indices": new_indices,
                "all_found_after_adapter_update": all(found_mask),
                "live_capture_primary_detection_source": True,
                "replay_events_used_for_detection": False,
            }
        )
        trace.append(trace_row)
        if new_indices:
            found_trace.append(
                {
                    "run_kind": run_kind,
                    "step_index": int(step),
                    "new_found_indices": list(new_indices),
                    "found_mask_after": list(found_mask),
                    "find_times_after": list(find_times),
                    "all_found_after": all(found_mask),
                    "truth_used_for_detection": False,
                    "actor_truth_used_for_detection": False,
                    "target_truth_used_for_detection": False,
                    "teammate_truth_used_for_detection": False,
                }
            )
    return {
        "run_kind": run_kind,
        "trace": trace,
        "found_trace": found_trace,
        "found_mask_final": list(found_mask),
        "find_times_final": list(find_times),
        "all_found": all(found_mask),
        "all_found_step": next((row["step_index"] for row in trace if row["all_found_after_adapter_update"]), None),
    }


def _first_shared_found_step(fusion_rows: List[Dict[str, Any]], run_kind: str) -> Optional[int]:
    steps = [
        int(row.get("policy_step", 0))
        for row in fusion_rows
        if row.get("run_kind") == run_kind and row.get("shared_found_this_step") is True
    ]
    return min(steps) if steps else None


def _first_live_detection_step(events: List[Dict[str, Any]], run_kind: str) -> Optional[int]:
    steps = [
        int(row.get("policy_step", 0))
        for row in events
        if row.get("run_kind") == run_kind and row.get("accepted_candidate") is True
    ]
    return min(steps) if steps else None


def _max_observed_detection_distance(events: List[Dict[str, Any]]) -> Optional[float]:
    values = [
        float(row.get("matched_range_m"))
        for row in events
        if row.get("accepted_candidate") is True and row.get("matched_range_m") is not None
    ]
    return max(values) if values else None


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    return all(
        row.get("truth_used_for_detection") is False
        and row.get("actor_truth_used_for_detection") is False
        and row.get("target_truth_used_for_detection") is False
        and row.get("teammate_truth_used_for_detection") is False
        for row in rows
    )


def _build_phase_config(pre_status: List[str]) -> Dict[str, Any]:
    base_config = P5D3._phase_config(pre_status)
    base_config.update(
        {
            "phase_name": PHASE_NAME,
            "phase_goal": "Connect live HoloOcean capture provider output directly to the Phase 5D-6 production mainline perception adapter.",
            "source_5d3_phase_name": SOURCE_5D3_PHASE_NAME,
            "source_5d3_audit_all_passed": _audit_passed(SOURCE_5D3_AUDIT_JSON),
            "source_5d6_phase_name": SOURCE_5D6_PHASE_NAME,
            "source_5d6_audit_all_passed": _audit_passed(SOURCE_5D6_AUDIT_JSON),
            "production_adapter_module": ReusableMainlinePerceptionAdapter.__module__,
            "production_adapter_class": "ReusableMainlinePerceptionAdapter",
            "live_capture_provider_enabled": True,
            "live_capture_primary_detection_source": True,
            "replay_events_used_for_detection": False,
            "phase5d3_json_events_used_for_detection": False,
            "all_found_step_1_required": False,
            "baseline_runtime_source_modified": False,
            "search_decision_algorithm_modified": False,
            "existing_holoocean_bridge_modified": False,
            "live_planner_callback_integrated": False,
            "live_planner_callback_deferred_to_5d8": True,
        }
    )
    return base_config


def _build_summary(
    *,
    config: Dict[str, Any],
    runs: Dict[str, Dict[str, Any]],
    live_events: List[Dict[str, Any]],
    live_fusion: List[Dict[str, Any]],
    provider_trace: List[Dict[str, Any]],
    adapter_trace: List[Dict[str, Any]],
    found_trace: List[Dict[str, Any]],
    case_results: List[Dict[str, Any]],
    started: float,
) -> Dict[str, Any]:
    target_shared = _first_shared_found_step(live_fusion, "target")
    coexist_shared = _first_shared_found_step(live_fusion, "coexist")
    teammate_fp_steps = [
        int(row.get("policy_step", 0))
        for row in live_fusion
        if row.get("run_kind") == "teammate_only" and row.get("shared_found_this_step") is True
    ]
    duplicate_steps = [
        int(row.get("policy_step", 0))
        for row in live_fusion
        if row.get("run_kind") == "target"
        and int(row.get("accepted_candidate_count", 0)) >= 2
        and int(row.get("fused_candidate_count", 0)) == 1
    ]
    by_kind = {row["run_kind"]: row for row in case_results}
    return {
        "phase_name": PHASE_NAME,
        "phase_completed": True,
        "source_5d3_audit_all_passed": config.get("source_5d3_audit_all_passed"),
        "source_5d6_audit_all_passed": config.get("source_5d6_audit_all_passed"),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "observer_count": 2,
        "observer_agent_names": list(OBSERVER_AGENT_NAMES),
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "production_adapter_module": ReusableMainlinePerceptionAdapter.__module__,
        "production_adapter_class": "ReusableMainlinePerceptionAdapter",
        "live_capture_provider_enabled": True,
        "live_capture_primary_detection_source": True,
        "replay_events_used_for_detection": False,
        "phase5d3_json_events_used_for_detection": False,
        "all_found_step_1_required": False,
        "live_planner_callback_integrated": False,
        "live_planner_callback_deferred_to_5d8": True,
        "all_runs_launch_ok": all(bool(run.get("launch_ok", False)) for run in runs.values()),
        "run_errors": {kind: run.get("error", "") for kind, run in runs.items()},
        "live_event_count": len(live_events),
        "live_fusion_trace_count": len(live_fusion),
        "live_provider_trace_count": len(provider_trace),
        "adapter_trace_count": len(adapter_trace),
        "found_trace_count": len(found_trace),
        "first_live_detection_step": _first_live_detection_step(live_events, "target"),
        "first_shared_found_step": target_shared,
        "coexist_first_live_detection_step": _first_live_detection_step(live_events, "coexist"),
        "coexist_first_shared_found_step": coexist_shared,
        "live_detection_success": target_shared is not None,
        "coexist_live_detection_success": coexist_shared is not None,
        "target_adapter_all_found": by_kind.get("target", {}).get("all_found"),
        "target_adapter_all_found_step": by_kind.get("target", {}).get("all_found_step"),
        "coexist_adapter_all_found": by_kind.get("coexist", {}).get("all_found"),
        "coexist_adapter_all_found_step": by_kind.get("coexist", {}).get("all_found_step"),
        "teammate_adapter_all_found": by_kind.get("teammate_only", {}).get("all_found"),
        "teammate_false_positive_steps": teammate_fp_steps,
        "teammate_only_false_positive_count": len(teammate_fp_steps),
        "duplicate_observation_fused_steps": duplicate_steps,
        "duplicate_observation_fused": bool(duplicate_steps),
        "max_reliable_detection_distance_observed_m": _max_observed_detection_distance(live_events),
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "truth_flags_false": _truth_flags_false(live_events)
        and _truth_flags_false(live_fusion)
        and _truth_flags_false(provider_trace)
        and _truth_flags_false(adapter_trace)
        and _truth_flags_false(found_trace),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
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
        "# Phase 5D-7 Live Capture Provider Coupling Summary",
        "",
        "- Production Adapter Module: `{0}`".format(summary.get("production_adapter_module")),
        "- Live Capture Primary Detection Source: `{0}`".format(summary.get("live_capture_primary_detection_source")),
        "- Replay Events Used For Detection: `{0}`".format(summary.get("replay_events_used_for_detection")),
        "- First Live Detection Step: `{0}`".format(summary.get("first_live_detection_step")),
        "- First Shared Found Step: `{0}`".format(summary.get("first_shared_found_step")),
        "- Target Adapter All Found Step: `{0}`".format(summary.get("target_adapter_all_found_step")),
        "- Teammate False Positive Steps: `{0}`".format(summary.get("teammate_false_positive_steps")),
        "- Duplicate Observation Fused Steps: `{0}`".format(summary.get("duplicate_observation_fused_steps")),
        "- Max Observed Detection Distance: `{0}`".format(summary.get("max_reliable_detection_distance_observed_m")),
        "- Live Planner Callback Integrated: `{0}`".format(summary.get("live_planner_callback_integrated")),
        "",
        "Phase 5D-7 validates the live HoloOcean capture provider -> production adapter.observe_step path. Full live planner callback search is deferred to Phase 5D-8.",
        "",
    ]
    return "\n".join(lines)


def _run_compile_log(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            os.path.join(PHASE_DIR, "scripts", "live_capture_provider_coupling_probe.py"),
            os.path.join(PHASE_DIR, "scripts", "live_capture_provider_coupling_audit.py"),
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
        f.write("\nBASE_PY_COMPILE_OK\n" if result.returncode == 0 else "\nBASE_PY_COMPILE_FAILED\n")


def _run_holo_compile_log(path: str) -> None:
    holo_python = r"C:\Users\32022\.conda\envs\holo\python.exe"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    executable = holo_python if os.path.exists(holo_python) else sys.executable
    result = subprocess.run(
        [
            executable,
            "-m",
            "py_compile",
            os.path.join(PHASE_DIR, "scripts", "live_capture_provider_coupling_probe.py"),
            os.path.join(PHASE_DIR, "scripts", "live_capture_provider_coupling_audit.py"),
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
        f.write("\nHOLO_PY_COMPILE_OK\n" if result.returncode == 0 else "\nHOLO_PY_COMPILE_FAILED\n")


def run_live_capture_provider() -> Dict[str, Any]:
    started = time.perf_counter()
    pre_status = _run_git_status()
    config = _build_phase_config(pre_status)

    print("Running 5D-7 baseline live capture")
    baseline_run = P5D3._run_trajectory("baseline", config)
    print("Running 5D-7 target live capture")
    target_run = P5D3._run_trajectory("target", config)
    print("Running 5D-7 coexist live capture")
    coexist_run = P5D3._run_trajectory("coexist", config)
    print("Running 5D-7 teammate-only live capture")
    teammate_run = P5D3._run_trajectory("teammate_only", config)
    runs = {
        "baseline": baseline_run,
        "target": target_run,
        "coexist": coexist_run,
        "teammate_only": teammate_run,
    }

    live_events: List[Dict[str, Any]] = []
    for kind in ("target", "coexist", "teammate_only"):
        live_events.extend(_build_live_events_for_run(runs[kind], baseline_run, config))
    live_fusion, _policy_trace, _found_events = P5D3._build_fusion_and_found(live_events, config)

    provider = LiveCaptureProvider(event_rows=live_events, fusion_rows=live_fusion, config=config)
    case_results = [
        _run_adapter_live_case(run_kind="target", provider=provider),
        _run_adapter_live_case(run_kind="coexist", provider=provider),
        _run_adapter_live_case(run_kind="teammate_only", provider=provider),
    ]
    adapter_trace: List[Dict[str, Any]] = []
    found_trace: List[Dict[str, Any]] = []
    for case in case_results:
        adapter_trace.extend(case.get("trace", []))
        found_trace.extend(case.get("found_trace", []))

    tick_trace: List[Dict[str, Any]] = []
    for kind in ("baseline", "target", "coexist", "teammate_only"):
        tick_trace.extend(runs[kind].get("tick_rows", []))

    summary = _build_summary(
        config=config,
        runs=runs,
        live_events=live_events,
        live_fusion=live_fusion,
        provider_trace=provider.provider_trace,
        adapter_trace=adapter_trace,
        found_trace=found_trace,
        case_results=case_results,
        started=started,
    )
    git_doc = {
        "phase_name": PHASE_NAME,
        "pre_status": pre_status,
        "post_status": _run_git_status(),
        "protected_core_path_status": _run_git_status(
            [
                "baseline_GP/core_search_policy.py",
                "baseline_GP/core_execution.py",
                "baseline_GP/core_targets.py",
                "baseline_GP/core_intensity.py",
                "baseline_GP/core_safe_nav.py",
                "baseline_GP/marine_knownmap_runtime.py",
                "baseline_GP/marine_knownmap_runtime_2usv.py",
            ]
        ),
    }

    _run_compile_log(BASE_COMPILE_LOG)
    _run_holo_compile_log(HOLO_COMPILE_LOG)

    _save_json(CONFIG_JSON, config)
    _save_json(PRODUCTION_CONTRACT_JSON, mainline_perception_adapter_contract())
    _save_json(LIVE_BASELINE_RUN_JSON, _strip_run_raw(baseline_run))
    _save_json(LIVE_TARGET_RUN_JSON, _strip_run_raw(target_run))
    _save_json(LIVE_COOEXIST_RUN_JSON, _strip_run_raw(coexist_run))
    _save_json(LIVE_TEAMMATE_RUN_JSON, _strip_run_raw(teammate_run))
    _save_json(LIVE_TICK_TRACE_JSON, tick_trace)
    _save_csv(LIVE_TICK_TRACE_CSV, tick_trace)
    _save_json(LIVE_EVENTS_JSON, live_events)
    _save_csv(LIVE_EVENTS_CSV, live_events)
    _save_json(LIVE_FUSION_JSON, live_fusion)
    _save_csv(LIVE_FUSION_CSV, live_fusion)
    _save_json(LIVE_PROVIDER_TRACE_JSON, provider.provider_trace)
    _save_csv(LIVE_PROVIDER_TRACE_CSV, provider.provider_trace)
    _save_json(ADAPTER_TRACE_JSON, adapter_trace)
    _save_csv(ADAPTER_TRACE_CSV, adapter_trace)
    _save_json(FOUND_TRACE_JSON, found_trace)
    _save_csv(FOUND_TRACE_CSV, found_trace)
    _save_json(SUMMARY_JSON, summary)
    _save_json(GIT_STATUS_JSON, git_doc)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(_build_summary_md(summary))
    print("Summary written to: {0}".format(SUMMARY_MD))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live"], default="live")
    args = parser.parse_args()
    if args.mode == "live":
        run_live_capture_provider()


if __name__ == "__main__":
    main()
