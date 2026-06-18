"""Audit for Phase 5D-11 RGB/Range sync visual diagnostic."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d11_live_target_rgb_range_sync_diagnostic"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
DIAG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_diagnostic.json")
DIAG_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_diagnostic.csv")
PER_TICK_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_per_tick.csv")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d11_rgb_range_sync_diagnostic.md")
AUDIT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d11_rgb_range_sync_audit.json")
AUDIT_MD = os.path.join(PHASE_DIR, "reports", "phase5d11_rgb_range_sync_audit_summary.md")

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
        [
            sys.executable,
            "-m",
            "py_compile",
            os.path.join(PHASE_DIR, "scripts", "live_target_rgb_range_sync_visual_diagnostic.py"),
            os.path.join(PHASE_DIR, "scripts", "live_target_rgb_range_sync_visual_audit.py"),
        ],
        cwd=os.path.abspath("."),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def _visuals_exist(rows: List[Dict[str, Any]]) -> bool:
    keys = [
        "target_rgb_preview_path",
        "baseline_rgb_preview_path",
        "diff_preview_path",
        "white_neutral_mask_preview_path",
        "overlay_preview_path",
    ]
    for row in rows:
        for key in keys:
            path = row.get(key)
            if not isinstance(path, str) or not path or not os.path.exists(path):
                return False
    return True


def _build_audit() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    metrics: Dict[str, Any] = {}
    required = [DIAG_JSON, DIAG_CSV, PER_TICK_CSV, SUMMARY_MD]
    checks["required_paths_exist"] = all(os.path.exists(path) for path in required)
    summary: Dict[str, Any] = {}
    try:
        summary = _load_json(DIAG_JSON)
        checks["summary_parse_ok"] = True
    except Exception:
        checks["summary_parse_ok"] = False
    rows = summary.get("rows", []) if isinstance(summary, dict) else []
    checks["phase_name_matches"] = summary.get("phase_name") == PHASE_NAME
    checks["source_5d10_failed_as_expected"] = summary.get("source_5d10_audit_all_passed_false") is True
    checks["scope_boundaries_ok"] = bool(
        summary.get("target_agent_type") == "SphereAgent"
        and summary.get("observer_agent_type") == "SurfaceVessel"
        and summary.get("target_is_static") is True
        and summary.get("dynamic_target_tracking_enabled") is False
        and summary.get("non_sphere_like_target_expansion_enabled") is False
    )
    checks["recommended_rule_reused"] = summary.get("recommended_rule_id") == "sphere_blob_local_range_scaled_any_hit"
    checks["truth_flags_false"] = bool(
        summary.get("truth_used_for_detection") is False
        and summary.get("actor_truth_used_for_detection") is False
        and summary.get("target_truth_used_for_detection") is False
        and summary.get("teammate_truth_used_for_detection") is False
        and all(row.get("truth_used_for_detection") is False for row in rows)
        and all(row.get("target_truth_used_for_detection") is False for row in rows)
    )
    checks["control_case_accepted"] = summary.get("control_case_accepted") is True
    checks["target_failure_static_replay_has_acceptance"] = int(summary.get("target_failure_static_replay_accepted_count") or 0) >= 1
    checks["target_failure_range_hit_cases_replay_accepted"] = set(summary.get("target_failure_static_replay_accepted_cases") or []) == {
        "target_range_hit_failure_1",
        "target_range_hit_failure_2",
        "target_range_hit_failure_3",
    }
    checks["visual_previews_exist"] = _visuals_exist(rows)
    checks["diagnostic_not_claiming_search_closure"] = "phase_completed" not in summary and "all_found" not in summary
    checks["core_runtime_and_search_algorithm_not_modified"] = _git_status(CORE_PATHS) == []
    checks["py_compile_ok"] = _compile_ok()

    metrics.update(
        {
            "case_count": summary.get("case_count"),
            "control_case_accepted": summary.get("control_case_accepted"),
            "target_failure_case_count": summary.get("target_failure_case_count"),
            "target_failure_static_replay_accepted_count": summary.get("target_failure_static_replay_accepted_count"),
            "target_failure_static_replay_accepted_cases": summary.get("target_failure_static_replay_accepted_cases"),
            "per_tick_row_count": summary.get("per_tick_row_count"),
        }
    )
    all_passed = all(checks.values())
    return {
        "phase_name": PHASE_NAME,
        "diagnostic_audit_only": True,
        "checks": checks,
        "metrics": metrics,
        "all_passed": bool(all_passed),
    }


def _write_audit_md(audit: Dict[str, Any]) -> None:
    lines = [
        "# Phase 5D-11 RGB/Range Sync Visual Audit",
        "",
        "- Diagnostic Audit Only: `{0}`".format(audit.get("diagnostic_audit_only")),
        "- All Passed: `{0}`".format(audit.get("all_passed")),
        "- Target Failure Static Replay Accepted Count: `{0}`".format(
            audit.get("metrics", {}).get("target_failure_static_replay_accepted_count")
        ),
        "- Target Failure Static Replay Accepted Cases: `{0}`".format(
            audit.get("metrics", {}).get("target_failure_static_replay_accepted_cases")
        ),
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
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
