"""Audit for Phase 5D-15 multicamera RGB/RangeFinder coverage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d15_multicamera_coverage_no_stop_scan"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_summary.json")
EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_live_per_agent_detection_events.json")
FUSION_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_live_candidate_fusion_trace.json")
ADAPTER_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_adapter_observe_trace.json")
UPDATE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_mainline_update_found_trace.json")
RAW_FRAME_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_raw_frame_sync_diagnostic.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_git_status.json")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d15_summary.md")
PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "multicamera_coverage_no_stop_scan_probe.py")
AUDIT_SCRIPT = os.path.join(PHASE_DIR, "scripts", "multicamera_coverage_no_stop_scan_audit.py")

AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d15_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d15_audit_summary.md")

CORE_PATHS = [
    "baseline_GP/core_search_policy.py",
    "baseline_GP/core_execution.py",
    "baseline_GP/core_targets.py",
    "baseline_GP/core_intensity.py",
    "baseline_GP/core_safe_nav.py",
    "baseline_GP/marine_knownmap_runtime.py",
    "baseline_GP/marine_knownmap_runtime_2usv.py",
]


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("JSON saved to: {0}".format(path))


def _git_status(paths: List[str]) -> List[str]:
    repo_root = os.path.abspath(".")
    result = subprocess.run(
        ["git", "-c", "safe.directory={0}".format(repo_root.replace("\\", "/")), "status", "--porcelain", "--"] + paths,
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if result.stderr.strip():
        rows.append("STDERR: {0}".format(result.stderr.strip()))
    return rows


def _compile_ok() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", PROBE_SCRIPT, AUDIT_SCRIPT],
        cwd=os.path.abspath("."),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    keys = [
        "truth_used_for_detection",
        "actor_truth_used_for_detection",
        "target_truth_used_for_detection",
        "teammate_truth_used_for_detection",
    ]
    return all(all(row.get(key) is False for key in keys) for row in rows)


def _build_audit() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    metrics: Dict[str, Any] = {}

    required = [
        SUMMARY_JSON,
        EVENTS_JSON,
        FUSION_JSON,
        ADAPTER_JSON,
        UPDATE_JSON,
        RAW_FRAME_JSON,
        GIT_STATUS_JSON,
        SUMMARY_MD,
        PROBE_SCRIPT,
    ]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required)

    summary: Dict[str, Any] = {}
    events: List[Dict[str, Any]] = []
    fusion: List[Dict[str, Any]] = []
    adapter: List[Dict[str, Any]] = []
    updates: List[Dict[str, Any]] = []
    raw_frame: Dict[str, Any] = {}
    git_doc: Dict[str, Any] = {}
    try:
        summary = _load_json(SUMMARY_JSON)
        events = _load_json(EVENTS_JSON)
        fusion = _load_json(FUSION_JSON)
        adapter = _load_json(ADAPTER_JSON)
        updates = _load_json(UPDATE_JSON)
        raw_frame = _load_json(RAW_FRAME_JSON)
        git_doc = _load_json(GIT_STATUS_JSON)
        checks["json_parse_ok"] = True
    except Exception:
        checks["json_parse_ok"] = False

    target_events = [row for row in events if row.get("run_kind") == "target"]
    teammate_events = [row for row in events if row.get("run_kind") == "teammate_only"]
    target_accepted_sync = [
        row
        for row in target_events
        if row.get("accepted_candidate") is True and row.get("rgb_range_sync_applied") is True
    ]
    teammate_accepted = [row for row in teammate_events if row.get("accepted_candidate") is True]
    target_shared = [
        row
        for row in fusion
        if row.get("run_kind") == "target" and row.get("shared_found_this_step") is True
    ]
    teammate_shared = [
        row
        for row in fusion
        if row.get("run_kind") == "teammate_only" and row.get("shared_found_this_step") is True
    ]
    target_updates = [row for row in updates if row.get("run_kind") == "target"]
    closing_updates = [row for row in target_updates if row.get("all_found_after_update") is True]
    adapter_detected = [
        row
        for row in adapter
        if row.get("run_kind") == "target"
        and any(bool(v) for v in row.get("detected_mask_returned_to_mainline", []))
    ]

    checks["phase_name_matches"] = summary.get("phase_name") == PHASE_NAME and raw_frame.get("phase_name") == PHASE_NAME
    checks["phase_goal_completed"] = (
        summary.get("phase_completed") is True
        and summary.get("phase_goal_completed") is True
        and summary.get("phase_status") == "live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed"
    )
    checks["scope_boundaries_ok"] = bool(
        summary.get("target_agent_type") == "SphereAgent"
        and summary.get("teammate_agent_type") == "SurfaceVessel"
        and summary.get("observer_agent_type") == "SurfaceVessel"
        and summary.get("target_is_static") is True
        and summary.get("dynamic_target_tracking_enabled") is False
        and summary.get("non_sphere_like_target_expansion_enabled") is False
    )
    checks["recommended_rule_reused"] = summary.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
    checks["live_planner_mainline_path"] = (
        summary.get("live_planner_callback_integrated") is True
        and summary.get("planned_path_source") == "baseline_GP_mainline_planner"
        and summary.get("preset_trajectory_used") is False
    )
    checks["rgb_sync_fix_enabled_and_used"] = (
        summary.get("rgb_range_sync_fix_enabled") is True
        and summary.get("rgb_range_sync_strategy") == "multicamera_continuous_rolling_detector_scored_nearest_pair"
        and int(summary.get("rgb_sync_applied_count") or 0) > 0
    )
    checks["multicamera_coverage_enabled"] = (
        int(summary.get("camera_channel_count") or 0) >= 3
        and int(summary.get("bridge_fan_rangefinder_sensor_count") or 0) > 61
        and all(row.get("camera_channel_id") for row in target_accepted_sync)
    )
    checks["no_stop_scan_used"] = (
        summary.get("post_arrival_scan_enabled") is False
        and summary.get("standoff_viewpoint_hold_enabled") is False
        and summary.get("no_stop_scan_tick_audit_passed") is True
        and int(summary.get("post_arrival_stabilization_tick_count") or 0) == 0
        and int(summary.get("standoff_viewpoint_hold_tick_count") or 0) == 0
        and int(summary.get("scan_tick_count") or 0) == 0
        and int(summary.get("post_scan_recenter_tick_count") or 0) == 0
        and summary.get("target_accepted_candidate_from_scan") is False
        and summary.get("target_accepted_candidate_from_standoff_viewpoint_hold") is False
        and summary.get("target_accepted_candidate_from_transit") is True
        and all(row.get("capture_phase") == "transit" for row in target_accepted_sync)
    )
    checks["target_accepted_candidates_from_rgb_sync"] = (
        int(summary.get("target_accepted_candidate_from_rgb_sync_count") or 0) >= 1
        and len(target_accepted_sync) >= 1
        and all(row.get("rangefinder_hit_beam_indices") for row in target_accepted_sync)
        and all(row.get("rgb_sync_target_tick") is not None for row in target_accepted_sync)
        and all(row.get("rgb_sync_baseline_tick") is not None for row in target_accepted_sync)
    )
    checks["candidate_fusion_shared_found"] = (
        len(target_shared) >= 1
        and any(int(row.get("accepted_candidate_count") or 0) >= 1 for row in target_shared)
        and any(int(row.get("fused_candidate_count") or 0) >= 1 for row in target_shared)
    )
    checks["adapter_returned_mainline_detected_mask"] = len(adapter_detected) >= 1
    checks["original_update_found_mask_closed_all_found"] = (
        summary.get("mainline_update_found_mask_called") is True
        and int(summary.get("mainline_update_found_mask_called_count") or 0) > 0
        and summary.get("mainline_found_mask_updated_from_live_adapter") is True
        and summary.get("mainline_all_found_driven_by_live_adapter") is True
        and summary.get("target_success_all_found") is True
        and summary.get("target_all_found_step") is not None
        and len(closing_updates) >= 1
    )
    checks["teammate_negative_clean"] = (
        summary.get("teammate_false_positive_steps") == []
        and summary.get("teammate_only_false_positive_count") == 0
        and summary.get("teammate_events_accepted_count") == 0
        and summary.get("teammate_accepted_candidate_from_rgb_sync_count") == 0
        and teammate_accepted == []
        and teammate_shared == []
    )
    checks["truth_flags_false"] = (
        summary.get("truth_flags_false") is True
        and summary.get("truth_used_for_detection") is False
        and _truth_flags_false(events)
        and _truth_flags_false(fusion)
        and _truth_flags_false(adapter)
        and _truth_flags_false(updates)
    )
    checks["core_runtime_and_search_algorithm_not_modified"] = (
        git_doc.get("protected_core_path_status") == [] and _git_status(CORE_PATHS) == []
    )
    checks["outputs_in_independent_phase_dir"] = git_doc.get("outside_phase_new_or_changed") == []
    checks["py_compile_ok"] = _compile_ok()

    metrics.update(
        {
            "phase_status": summary.get("phase_status"),
            "target_all_found_step": summary.get("target_all_found_step"),
            "target_completed_steps": summary.get("target_completed_steps"),
            "target_accepted_candidate_from_rgb_sync_count": summary.get(
                "target_accepted_candidate_from_rgb_sync_count"
            ),
            "target_accepted_candidate_from_rgb_sync_steps": summary.get(
                "target_accepted_candidate_from_rgb_sync_steps"
            ),
            "rgb_sync_window_ticks": summary.get("rgb_sync_window_ticks"),
            "rgb_sync_max_abs_target_offset_ticks": summary.get("rgb_sync_max_abs_target_offset_ticks"),
            "rgb_sync_max_abs_baseline_offset_ticks": summary.get("rgb_sync_max_abs_baseline_offset_ticks"),
            "no_stop_scan_tick_audit_passed": summary.get("no_stop_scan_tick_audit_passed"),
            "post_arrival_stabilization_tick_count": summary.get("post_arrival_stabilization_tick_count"),
            "standoff_viewpoint_hold_tick_count": summary.get("standoff_viewpoint_hold_tick_count"),
            "scan_tick_count": summary.get("scan_tick_count"),
            "post_scan_recenter_tick_count": summary.get("post_scan_recenter_tick_count"),
            "target_accepted_candidate_from_transit": summary.get("target_accepted_candidate_from_transit"),
            "mainline_update_found_mask_called_count": summary.get("mainline_update_found_mask_called_count"),
            "teammate_false_positive_steps": summary.get("teammate_false_positive_steps"),
            "max_reliable_detection_distance_observed_m": summary.get("max_reliable_detection_distance_observed_m"),
            "accepted_sync_events": [
                {
                    "policy_step": row.get("policy_step"),
                    "tick_in_policy_step": row.get("tick_in_policy_step"),
                    "agent_id": row.get("agent_id"),
                    "rgb_sync_target_tick": row.get("rgb_sync_target_tick"),
                    "rgb_sync_baseline_tick": row.get("rgb_sync_baseline_tick"),
                    "rgb_sync_target_offset_ticks": row.get("rgb_sync_target_offset_ticks"),
                    "rgb_sync_baseline_offset_ticks": row.get("rgb_sync_baseline_offset_ticks"),
                    "matched_range_m": row.get("matched_range_m"),
                    "rgb_changed_pixels": row.get("rgb_changed_pixels"),
                    "rangefinder_hit_beam_indices": row.get("rangefinder_hit_beam_indices"),
                }
                for row in target_accepted_sync
            ],
            "closing_update_steps": [row.get("mainline_step") for row in closing_updates],
        }
    )

    return {
        "phase_name": PHASE_NAME,
        "phase_completed": bool(summary.get("phase_completed") is True),
        "audit_conclusion": "live_rgb_range_sync_fix_closed_target_shared_found_update_found_mask_all_found",
        "checks": checks,
        "metrics": metrics,
        "all_passed": all(checks.values()),
    }


def _write_audit_md(audit: Dict[str, Any]) -> None:
    metrics = audit.get("metrics", {})
    lines = [
        "# Phase 5D-15 Continuous Rolling RGB/RF Sync Audit",
        "",
        "- All Passed: `{0}`".format(audit.get("all_passed")),
        "- Phase Completed: `{0}`".format(audit.get("phase_completed")),
        "- Phase Status: `{0}`".format(metrics.get("phase_status")),
        "- Target All Found Step: `{0}`".format(metrics.get("target_all_found_step")),
        "- Target Accepted Candidate From RGB Sync Count: `{0}`".format(
            metrics.get("target_accepted_candidate_from_rgb_sync_count")
        ),
        "- Teammate False Positive Steps: `{0}`".format(metrics.get("teammate_false_positive_steps")),
        "",
        "## Accepted RGB Sync Events",
        "",
        "| step | tick | agent | target_rgb_tick | baseline_rgb_tick | target_offset | baseline_offset | range_m | beams |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in metrics.get("accepted_sync_events", []):
        lines.append(
            "| {0} | {1} | `{2}` | {3} | {4} | {5} | {6} | {7:.3f} | `{8}` |".format(
                row.get("policy_step"),
                row.get("tick_in_policy_step"),
                row.get("agent_id"),
                row.get("rgb_sync_target_tick"),
                row.get("rgb_sync_baseline_tick"),
                row.get("rgb_sync_target_offset_ticks"),
                row.get("rgb_sync_baseline_offset_ticks"),
                float(row.get("matched_range_m") or 0.0),
                row.get("rangefinder_hit_beam_indices"),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Passed |", "|---|---|"])
    for key in sorted(audit.get("checks", {}).keys()):
        lines.append("| `{0}` | `{1}` |".format(key, audit["checks"][key]))
    lines.append("")
    os.makedirs(os.path.dirname(AUDIT_MD), exist_ok=True)
    with open(AUDIT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Audit written to: {0}".format(AUDIT_MD))


def main() -> None:
    audit = _build_audit()
    _save_json(AUDIT_JSON, audit)
    _write_audit_md(audit)
    print("all_passed={0}".format(audit["all_passed"]))


if __name__ == "__main__":
    main()


