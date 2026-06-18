"""Audit for Phase 5D-12 live raw-frame/baseline sync diagnostic."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d12_live_raw_frame_baseline_sync_diagnostic"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))

SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d12_summary.json")
DIAG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d12_raw_frame_sync_diagnostic.json")
DIAG_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d12_raw_frame_sync_diagnostic.csv")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d12_summary.md")
PROBE_SCRIPT = os.path.join(PHASE_DIR, "scripts", "live_raw_frame_baseline_sync_probe.py")

AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d12_raw_frame_sync_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d12_raw_frame_sync_audit_summary.md")

CORE_PATHS = [
    "baseline_GP/core_search_policy.py",
    "baseline_GP/core_execution.py",
    "baseline_GP/core_targets.py",
    "baseline_GP/core_intensity.py",
    "baseline_GP/core_safe_nav.py",
    "baseline_GP/marine_knownmap_runtime.py",
    "baseline_GP/marine_knownmap_runtime_2usv.py",
]

EXPECTED_RANGE_HIT_TICKS = [
    (16, 240, 5305, "sv0", (56,)),
    (16, 241, 5306, "sv0", (58,)),
    (16, 242, 5307, "sv0", (60,)),
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
        [
            sys.executable,
            "-m",
            "py_compile",
            PROBE_SCRIPT,
            os.path.join(PHASE_DIR, "scripts", "live_raw_frame_baseline_sync_audit.py"),
        ],
        cwd=os.path.abspath("."),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def _truth_flags_false(summary: Dict[str, Any], diagnostic: Dict[str, Any], rows: List[Dict[str, Any]]) -> bool:
    keys = [
        "truth_used_for_detection",
        "actor_truth_used_for_detection",
        "target_truth_used_for_detection",
        "teammate_truth_used_for_detection",
    ]
    return bool(
        summary.get("truth_flags_false") is True
        and all(summary.get(key) is False for key in keys)
        and all(diagnostic.get(key) is False for key in keys)
        and all(row.get(key) is False for row in rows for key in keys)
    )


def _row_key(row: Dict[str, Any]) -> tuple:
    return (
        row.get("policy_step"),
        row.get("tick_in_policy_step"),
        row.get("tick_global"),
        row.get("agent_id"),
        tuple(row.get("rangefinder_hit_beam_indices_recomputed") or row.get("source_event_rangefinder_hit_beam_indices") or []),
    )


def _range_hit_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected = set(EXPECTED_RANGE_HIT_TICKS)
    return [row for row in rows if _row_key(row) in expected]


def _has_required_visuals_for_rgb_rows(rows: List[Dict[str, Any]]) -> bool:
    keys = [
        "target_rgb_preview_path",
        "baseline_rgb_preview_path",
        "diff_preview_path",
        "white_neutral_mask_preview_path",
        "overlay_preview_path",
    ]
    rgb_rows = [row for row in rows if row.get("target_rgb_present") is True and row.get("baseline_rgb_present") is True]
    if not rgb_rows:
        return False
    for row in rgb_rows:
        for key in keys:
            path = row.get(key)
            if not isinstance(path, str) or not path or not os.path.exists(path):
                return False
    return True


def _build_audit() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    metrics: Dict[str, Any] = {}

    required_paths = [SUMMARY_JSON, DIAG_JSON, DIAG_CSV, SUMMARY_MD, PROBE_SCRIPT]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required_paths)

    summary: Dict[str, Any] = {}
    diagnostic: Dict[str, Any] = {}
    try:
        summary = _load_json(SUMMARY_JSON)
        diagnostic = _load_json(DIAG_JSON)
        checks["json_parse_ok"] = True
    except Exception:
        checks["json_parse_ok"] = False

    rows = diagnostic.get("rows", []) if isinstance(diagnostic, dict) else []
    range_hit_rows = _range_hit_rows(rows)

    checks["phase_name_matches"] = summary.get("phase_name") == PHASE_NAME and diagnostic.get("phase_name") == PHASE_NAME
    checks["diagnostic_audit_only"] = summary.get("diagnostic_audit_only") is True and diagnostic.get("diagnostic_audit_only") is True
    checks["phase_correctly_not_completed"] = (
        summary.get("phase_completed") is False
        and summary.get("phase_goal_completed") is False
        and summary.get("target_success_all_found") is False
        and summary.get("target_live_detection_success") is False
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
    checks["live_planner_callback_integrated"] = (
        summary.get("live_planner_callback_integrated") is True
        and summary.get("planned_path_source") == "baseline_GP_mainline_planner"
        and summary.get("preset_trajectory_used") is False
    )
    checks["mainline_update_found_mask_called_but_not_updated"] = (
        summary.get("mainline_update_found_mask_called") is True
        and int(summary.get("mainline_update_found_mask_called_count") or 0) > 0
        and summary.get("mainline_found_mask_updated_from_live_adapter") is False
        and summary.get("mainline_all_found_driven_by_live_adapter") is False
    )
    checks["expected_range_hit_case_count"] = (
        summary.get("raw_frame_sync_range_hit_case_count") == 3
        and diagnostic.get("range_hit_case_count") == 3
        and len(range_hit_rows) == 3
    )
    checks["range_hit_rows_are_expected_ticks"] = set(_row_key(row) for row in range_hit_rows) == set(EXPECTED_RANGE_HIT_TICKS)
    checks["range_hit_capture_containers_present"] = all(
        row.get("target_capture_present") is True
        and row.get("baseline_capture_present") is True
        and row.get("exact_baseline_capture_present") is True
        for row in range_hit_rows
    )
    checks["range_hit_rgb_frames_missing_on_both_sides"] = all(
        row.get("target_rgb_present") is False and row.get("baseline_rgb_present") is False for row in range_hit_rows
    )
    checks["range_hit_recomputed_rgb_zero"] = all(int(row.get("rgb_changed_pixels_recomputed") or 0) == 0 for row in range_hit_rows)
    checks["range_hit_pose_alignment_tight"] = all(
        abs(float(row.get("target_vs_baseline_observer_distance_m") or 999.0) - 0.0008793352987197211) <= 0.000001
        for row in range_hit_rows
    )
    checks["source_zero_rgb_not_recovered_by_recompute"] = (
        summary.get("raw_frame_sync_source_zero_rgb_recomputed_positive_count") == 0
        and summary.get("raw_frame_sync_source_zero_rgb_recomputed_positive_ticks") == []
        and diagnostic.get("source_zero_rgb_recomputed_positive_count") == 0
        and diagnostic.get("source_zero_rgb_recomputed_positive_ticks") == []
    )
    checks["rgb_positive_rows_have_visuals"] = _has_required_visuals_for_rgb_rows(rows)
    checks["teammate_negative_clean"] = (
        summary.get("teammate_false_positive_steps") == []
        and summary.get("teammate_only_false_positive_count") == 0
        and summary.get("teammate_events_accepted_count") == 0
    )
    checks["truth_flags_false"] = _truth_flags_false(summary, diagnostic, rows)
    checks["core_runtime_and_search_algorithm_not_modified"] = _git_status(CORE_PATHS) == []
    checks["summary_reports_core_unmodified"] = (
        summary.get("baseline_runtime_source_modified") is False
        and summary.get("search_decision_algorithm_modified") is False
    )
    checks["py_compile_ok"] = _compile_ok()

    metrics.update(
        {
            "phase_status": summary.get("phase_status"),
            "phase_completed": summary.get("phase_completed"),
            "phase_goal_completed": summary.get("phase_goal_completed"),
            "raw_frame_sync_case_count": summary.get("raw_frame_sync_case_count"),
            "raw_frame_sync_range_hit_case_count": summary.get("raw_frame_sync_range_hit_case_count"),
            "target_live_detection_success": summary.get("target_live_detection_success"),
            "target_all_found_step": summary.get("target_all_found_step"),
            "mainline_update_found_mask_called_count": summary.get("mainline_update_found_mask_called_count"),
            "mainline_found_mask_updated_from_live_adapter": summary.get("mainline_found_mask_updated_from_live_adapter"),
            "teammate_false_positive_steps": summary.get("teammate_false_positive_steps"),
            "range_hit_rows": [
                {
                    "policy_step": row.get("policy_step"),
                    "tick_in_policy_step": row.get("tick_in_policy_step"),
                    "tick_global": row.get("tick_global"),
                    "agent_id": row.get("agent_id"),
                    "rangefinder_hit_beam_indices": row.get("rangefinder_hit_beam_indices_recomputed"),
                    "target_capture_present": row.get("target_capture_present"),
                    "baseline_capture_present": row.get("baseline_capture_present"),
                    "exact_baseline_capture_present": row.get("exact_baseline_capture_present"),
                    "target_rgb_present": row.get("target_rgb_present"),
                    "baseline_rgb_present": row.get("baseline_rgb_present"),
                    "target_vs_baseline_observer_distance_m": row.get("target_vs_baseline_observer_distance_m"),
                    "rgb_changed_pixels_recomputed": row.get("rgb_changed_pixels_recomputed"),
                    "rangefinder_min_positive_range_m_recomputed": row.get("rangefinder_min_positive_range_m_recomputed"),
                }
                for row in range_hit_rows
            ],
        }
    )

    all_passed = all(checks.values())
    return {
        "phase_name": PHASE_NAME,
        "diagnostic_name": "phase5d12_raw_frame_baseline_sync_diagnostic",
        "diagnostic_audit_only": True,
        "phase_completed": False,
        "audit_conclusion": (
            "rangefinder_hit_ticks_have_capture_containers_and_tight_baseline_pose_alignment_"
            "but_front_rgb_camera_frames_are_missing_on_target_and_baseline_sides"
        ),
        "checks": checks,
        "metrics": metrics,
        "all_passed": bool(all_passed),
    }


def _write_audit_md(audit: Dict[str, Any]) -> None:
    metrics = audit.get("metrics", {})
    lines = [
        "# Phase 5D-12 Raw Frame/Baseline Sync Audit",
        "",
        "- Diagnostic Audit Only: `{0}`".format(audit.get("diagnostic_audit_only")),
        "- All Passed: `{0}`".format(audit.get("all_passed")),
        "- Phase Completed: `{0}`".format(audit.get("phase_completed")),
        "- Phase Status: `{0}`".format(metrics.get("phase_status")),
        "- Target Live Detection Success: `{0}`".format(metrics.get("target_live_detection_success")),
        "- Target All Found Step: `{0}`".format(metrics.get("target_all_found_step")),
        "- Mainline update_found_mask Calls: `{0}`".format(metrics.get("mainline_update_found_mask_called_count")),
        "- Mainline found_mask Updated From Live Adapter: `{0}`".format(
            metrics.get("mainline_found_mask_updated_from_live_adapter")
        ),
        "- Teammate False Positive Steps: `{0}`".format(metrics.get("teammate_false_positive_steps")),
        "",
        "## Conclusion",
        "",
        (
            "The 3 RangeFinder-hit ticks have target/baseline capture containers and tight pose alignment, "
            "but both target and baseline sides are missing FrontRGBCamera frames. "
            "The live search loop is therefore still not closed by perception; this audit only closes the diagnostic."
        ),
        "",
        "## Range-Hit Rows",
        "",
        "| policy_step | tick_in_policy_step | tick_global | agent | beams | target_rgb | baseline_rgb | pose_delta_m | recomputed_rgb |",
        "|---|---:|---:|---|---|---|---|---:|---:|",
    ]
    for row in metrics.get("range_hit_rows", []):
        lines.append(
            "| {0} | {1} | {2} | `{3}` | `{4}` | `{5}` | `{6}` | {7:.9f} | {8} |".format(
                row.get("policy_step"),
                row.get("tick_in_policy_step"),
                row.get("tick_global"),
                row.get("agent_id"),
                row.get("rangefinder_hit_beam_indices"),
                row.get("target_rgb_present"),
                row.get("baseline_rgb_present"),
                float(row.get("target_vs_baseline_observer_distance_m") or 0.0),
                row.get("rgb_changed_pixels_recomputed"),
            )
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Passed |",
            "|---|---|",
        ]
    )
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
