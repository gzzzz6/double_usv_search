"""Phase 5D-14: continuous rolling RGB/RF sync without stop-scan.

This phase connects the baseline_GP two-USV planner callback to live HoloOcean
movement and live SphereAgent perception.  The search planner decides the next
grid step, HoloOcean executes that step, live RGB/range observations are
converted to candidate-fusion evidence, the production perception adapter emits
the mainline detected_mask, and the original update_found_mask is called.

Compared with 5D-13, this phase removes the post-arrival stabilization,
standoff hold, scan, and recenter windows. RGB/RF evidence is paired with a
continuous rolling tick buffer while the USVs keep executing baseline_GP
planner movement.

Scope is intentionally limited to one static SphereAgent target and two
SurfaceVessel observers.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.append(os.path.abspath("."))

import baseline_GP.marine_knownmap_runtime_2usv as runtime_2usv  # noqa: E402
from baseline_GP.core_execution import ExecutionStepResult  # noqa: E402
from baseline_GP.holoocean_bridge.coordinate_adapter import grid_to_world, world_to_grid  # noqa: E402
from baseline_GP.holoocean_bridge.execution_backend import get_sensor_vector  # noqa: E402
from baseline_GP.holoocean_bridge.mainline_perception_adapter import (  # noqa: E402
    MainlineAdapterStepInput,
    ReusableMainlinePerceptionAdapter,
    mainline_perception_adapter_contract,
)
from baseline_GP.holoocean_bridge.scene_map_adapter import (  # noqa: E402
    load_scene_map_npz,
    scene_map_config_from_spec,
)


BASE_DIR = r"baseline_GP"
PHASE_NAME = "phase5d14_continuous_rolling_rgb_rf_sync"
PHASE_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", PHASE_NAME))
MAP_NPZ = os.path.normpath(os.path.join(BASE_DIR, "holoocean_bridge", "maps", "openwater_open_res10_v1.npz"))

SOURCE_5D3_PHASE_NAME = "phase5d3_continuous_multistep_coop_search"
SOURCE_5D3_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D3_PHASE_NAME))
SOURCE_5D3_PROBE = os.path.join(SOURCE_5D3_DIR, "scripts", "continuous_multistep_coop_search_probe.py")

SOURCE_5D6_PHASE_NAME = "phase5d6_production_mainline_perception_adapter"
SOURCE_5D6_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D6_PHASE_NAME))
SOURCE_5D6_AUDIT_JSON = os.path.join(SOURCE_5D6_DIR, "manifests", "phase5d6_audit.json")

SOURCE_5D7_PHASE_NAME = "phase5d7_live_capture_provider_coupling"
SOURCE_5D7_DIR = os.path.normpath(os.path.join(BASE_DIR, "results", "holoocean_bridge_v1", SOURCE_5D7_PHASE_NAME))
SOURCE_5D7_AUDIT_JSON = os.path.join(SOURCE_5D7_DIR, "manifests", "phase5d7_audit.json")

CONFIG_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_config.json")
PRODUCTION_CONTRACT_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_production_adapter_contract.json")
CALIBRATION_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_calibration_run.json")
TARGET_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_target_run.json")
TEAMMATE_RUN_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_teammate_only_run.json")
TICK_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_tick_trace.json")
TICK_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_tick_trace.csv")
POLICY_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_policy_trace.json")
POLICY_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_policy_trace.csv")
EVENTS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_per_agent_detection_events.json")
EVENTS_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_per_agent_detection_events.csv")
FUSION_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_candidate_fusion_trace.json")
FUSION_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_live_candidate_fusion_trace.csv")
ADAPTER_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_adapter_observe_trace.json")
ADAPTER_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_adapter_observe_trace.csv")
MAINLINE_UPDATE_TRACE_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_mainline_update_found_trace.json")
MAINLINE_UPDATE_TRACE_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_mainline_update_found_trace.csv")
SUMMARY_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_summary.json")
GIT_STATUS_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_git_status.json")
RAW_FRAME_SYNC_JSON = os.path.join(PHASE_DIR, "manifests", "phase5d14_raw_frame_sync_diagnostic.json")
RAW_FRAME_SYNC_CSV = os.path.join(PHASE_DIR, "manifests", "phase5d14_raw_frame_sync_diagnostic.csv")
SUMMARY_MD = os.path.join(PHASE_DIR, "reports", "phase5d14_summary.md")
BASE_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d14_py_compile_base.txt")
HOLO_COMPILE_LOG = os.path.join(PHASE_DIR, "logs", "phase5d14_py_compile_holo.txt")

RECOMMENDED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_NAMES = ["sv0", "sv1"]
MAINLINE_POLICY_NAME = "marine_knownmap_path_v2_infosampled_2usv"
RELIABLE_DISTANCE_LIMIT_M = 35.0
TEAMMATE_EXCLUSION_RADIUS_M = 10.0
TARGET_AUDIT_DISTANCE_THRESHOLD_M = 15.0

MAX_POLICY_STEPS = 20
ARRIVAL_RADIUS_M = 5.0
MAX_TICKS_PER_ONE_STEP = 320
POST_ARRIVAL_STABILIZATION_TICKS = 0
STANDOFF_VIEWPOINT_HOLD_TICKS = 0
STANDOFF_LOOKAHEAD_SEGMENT_INDEX = 4
STANDOFF_TURN_FORCE = 1200.0
STANDOFF_HEADING_TOLERANCE_DEG = 2.0
POST_ARRIVAL_SCAN_TICKS = 0
POST_SCAN_RECENTER_TICKS = 0
SCAN_TURN_FORCE = 1200.0
MAX_FORCE = 8000.0
MIN_FORCE = 1500.0
TURN_GAIN = 0.8
DIST_SLOW_RADIUS_M = 12.0
COLLISION_WARNING_M = 30.0
COLLISION_FAIL_M = 20.0
BRIDGE_FAN_YAW_DEGREES = [float(v) for v in range(30, -31, -1)]
RAW_FRAME_MAX_EVENTS = 12
RGB_SYNC_WINDOW_TICKS = 8
RGB_SYNC_MAX_POSE_DRIFT_M = 4.0
RGB_SYNC_STRATEGY = "continuous_rolling_detector_scored_nearest_pair"
DEFAULT_DISPLAY_FPS = 20.0
DEFAULT_DISPLAY_EVERY_TICKS = 4


def _load_module(path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load module from {0}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5D3 = _load_module(SOURCE_5D3_PROBE, "phase5d14_p5d3_detection_source")


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


class LiveSearchViewer:
    def __init__(
        self,
        *,
        enabled: bool,
        adapter_config: Any,
        map_shape: Tuple[int, int],
        title: str,
        fps: float = DEFAULT_DISPLAY_FPS,
        every_ticks: int = DEFAULT_DISPLAY_EVERY_TICKS,
    ) -> None:
        self.enabled = bool(enabled)
        self.adapter_config = adapter_config
        self.map_shape = (int(map_shape[0]), int(map_shape[1]))
        self.title = title
        self.fps = max(float(fps), 1.0)
        self.every_ticks = max(int(every_ticks), 1)
        self.scale = 8
        self.margin = 44
        self.closed = False
        self.tick_counter = 0
        self.trails: Dict[str, List[Tuple[int, int]]] = {"sv0": [], "sv1": []}
        self.last_status = "initializing"
        self.last_found_mask: List[bool] = []
        self.last_detected = False
        self.last_rf_hit = False
        self.target_cell: Optional[Tuple[int, int]] = None
        if self.enabled:
            try:
                import cv2  # noqa: F401

                cv2.namedWindow(self.title, cv2.WINDOW_NORMAL)
            except Exception as exc:
                print("[WARN] live display disabled: {0}".format(exc))
                self.enabled = False

    def _cell_from_world(self, world: Any) -> Optional[Tuple[int, int]]:
        if world is None:
            return None
        try:
            cell = world_to_grid(world, config=self.adapter_config, map_shape=self.map_shape, clamp=True)
            return (int(cell[0]), int(cell[1]))
        except Exception:
            return None

    def _px(self, cell: Tuple[int, int]) -> Tuple[int, int]:
        row, col = int(cell[0]), int(cell[1])
        return (
            int(self.margin + col * self.scale + self.scale // 2),
            int(self.margin + row * self.scale + self.scale // 2),
        )

    def update_tick(
        self,
        *,
        run_kind: str,
        policy_step: int,
        tick_in_policy_step: int,
        tick_global: int,
        captures_by_agent: Dict[str, Dict[str, Any]],
        target_world: Optional[List[float]],
        rf_hit: bool,
    ) -> None:
        if not self.enabled or self.closed:
            return
        self.tick_counter += 1
        self.last_rf_hit = bool(rf_hit)
        self.last_status = "{0} | step {1} tick {2} global {3}".format(
            run_kind,
            int(policy_step),
            int(tick_in_policy_step),
            int(tick_global),
        )
        self.target_cell = self._cell_from_world(target_world)
        for agent_name in ("sv0", "sv1"):
            capture = captures_by_agent.get(agent_name, {})
            cell = self._cell_from_world(capture.get("observer_world_location"))
            if cell is not None:
                trail = self.trails.setdefault(agent_name, [])
                if not trail or trail[-1] != cell:
                    trail.append(cell)
                    if len(trail) > 1200:
                        del trail[: len(trail) - 1200]
        if self.tick_counter % self.every_ticks == 0 or rf_hit:
            self.render()

    def update_step_result(
        self,
        *,
        found_mask: List[bool],
        detected: bool,
        all_found: bool,
        status: str,
    ) -> None:
        if not self.enabled or self.closed:
            return
        self.last_found_mask = [bool(v) for v in found_mask]
        self.last_detected = bool(detected)
        self.last_status = status
        self.render(force_wait_ms=int(max(1.0, 1000.0 / self.fps)))
        if bool(all_found):
            self.render(force_wait_ms=1000)

    def render(self, force_wait_ms: Optional[int] = None) -> None:
        if not self.enabled or self.closed:
            return
        try:
            import cv2

            h = self.margin * 2 + self.map_shape[0] * self.scale
            w = self.margin * 2 + self.map_shape[1] * self.scale
            img = np.full((h, w, 3), 245, dtype=np.uint8)
            grid_color = (220, 220, 220)
            for row in range(self.map_shape[0] + 1):
                y = self.margin + row * self.scale
                cv2.line(img, (self.margin, y), (w - self.margin, y), grid_color, 1)
            for col in range(self.map_shape[1] + 1):
                x = self.margin + col * self.scale
                cv2.line(img, (x, self.margin), (x, h - self.margin), grid_color, 1)

            if self.target_cell is not None:
                tx, ty = self._px(self.target_cell)
                cv2.drawMarker(img, (tx, ty), (40, 40, 220), markerType=cv2.MARKER_TILTED_CROSS, markerSize=16, thickness=2)
                cv2.putText(img, "target", (tx + 8, ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 40, 220), 1)

            colors = {"sv0": (30, 120, 240), "sv1": (30, 170, 80)}
            for agent_name in ("sv0", "sv1"):
                trail = self.trails.get(agent_name, [])
                if len(trail) >= 2:
                    for a, b in zip(trail[:-1], trail[1:]):
                        cv2.line(img, self._px(a), self._px(b), colors[agent_name], 1, lineType=cv2.LINE_AA)
                if trail:
                    x, y = self._px(trail[-1])
                    cv2.circle(img, (x, y), 6, colors[agent_name], -1, lineType=cv2.LINE_AA)
                    cv2.putText(img, agent_name, (x + 8, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[agent_name], 1)

            status_color = (40, 40, 40)
            if self.last_detected:
                status_color = (30, 130, 30)
            elif self.last_rf_hit:
                status_color = (0, 120, 220)
            cv2.putText(img, self.last_status[:120], (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
            cv2.putText(
                img,
                "found_mask={0}  RF_hit={1}  detected={2}  q: close viewer".format(
                    self.last_found_mask,
                    self.last_rf_hit,
                    self.last_detected,
                ),
                (12, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (40, 40, 40),
                1,
            )
            cv2.imshow(self.title, img)
            wait_ms = int(force_wait_ms) if force_wait_ms is not None else int(max(1.0, 1000.0 / self.fps))
            key = cv2.waitKey(wait_ms) & 0xFF
            if key == ord("q"):
                self.closed = True
                cv2.destroyWindow(self.title)
        except Exception as exc:
            print("[WARN] live display disabled after render error: {0}".format(exc))
            self.enabled = False

    def close(self) -> None:
        if not self.enabled:
            return
        try:
            import cv2

            cv2.destroyWindow(self.title)
        except Exception:
            pass
        self.closed = True


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
    try:
        return bool(_load_json(path).get("all_passed") is True)
    except Exception:
        return False


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


def _phase_config(pre_git_status: List[str]) -> Dict[str, Any]:
    return {
        "phase_name": PHASE_NAME,
        "phase_goal": "Run baseline_GP mainline planner callback with continuous HoloOcean movement/capture, rolling RGB/RF sync, no post-arrival stop-scan, and production adapter driven update_found_mask/all_found.",
        "source_5d6_phase_name": SOURCE_5D6_PHASE_NAME,
        "source_5d6_audit_all_passed": _audit_passed(SOURCE_5D6_AUDIT_JSON),
        "source_5d7_phase_name": SOURCE_5D7_PHASE_NAME,
        "source_5d7_audit_all_passed": _audit_passed(SOURCE_5D7_AUDIT_JSON),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "observer_agent_names": list(OBSERVER_AGENT_NAMES),
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "mainline_runtime_module": "baseline_GP.marine_knownmap_runtime_2usv",
        "mainline_policy_name": MAINLINE_POLICY_NAME,
        "mainline_planner_callback_functions": [
            "_joint_assign_two_usv_segments",
            "_apply_joint_assignment_to_locals",
            "_resolve_execution_conflict",
            "execute_next_step",
        ],
        "mainline_update_callable": "update_found_mask",
        "production_adapter_module": ReusableMainlinePerceptionAdapter.__module__,
        "production_adapter_class": "ReusableMainlinePerceptionAdapter",
        "planned_path_source": "baseline_GP_mainline_planner",
        "preset_trajectory_used": False,
        "live_planner_callback_integrated": True,
        "live_capture_primary_detection_source": True,
        "rgb_range_sync_fix_enabled": True,
        "rgb_range_sync_strategy": RGB_SYNC_STRATEGY,
        "rgb_sync_window_ticks": RGB_SYNC_WINDOW_TICKS,
        "rgb_sync_max_pose_drift_m": RGB_SYNC_MAX_POSE_DRIFT_M,
        "rgb_sync_scope": "continuous_rolling_target_and_calibration_rgb_pair_by_global_tick_rangefinder_tick_keeps_range_and_pose",
        "replay_events_used_for_detection": False,
        "phase5d3_json_events_used_for_detection": False,
        "live_calibration_reference_used": True,
        "live_calibration_reference_role": "rgb_background_reference_only_not_detection_event_replay",
        "observer_pose_source": "live_location_sensor_and_orientation_sensor",
        "orientation_sensor_used_for_world_projection": True,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "truth_role": "audit_only_not_detection_input",
        "semantic_sensor_used_for_detection": False,
        "sonar_used": False,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "teammate_exclusion_radius_m": TEAMMATE_EXCLUSION_RADIUS_M,
        "target_audit_distance_threshold_m": TARGET_AUDIT_DISTANCE_THRESHOLD_M,
        "episode_seed": 90,
        "fixed_target_grid_cell": [18, 13],
        "physical_target_world_offset_m": [0.0, 1.0, 0.0],
        "expected_initial_target_cell": [18, 13],
        "target_placement_source": "phase5d14_fixed_openwater_cell_on_baseline_planner_forward_fan_path",
        "physical_target_offset_role": "cell_local_holoocean_rangefinder_geometry_calibration_not_detection_input",
        "map_kind": "open_water",
        "map_height_cells": 81,
        "map_width_cells": 81,
        "resolution_m": 10.0,
        "sensor_range_m": 50.0,
        "bridge_fan_rangefinder_sensor_count": len(BRIDGE_FAN_YAW_DEGREES),
        "bridge_fan_yaw_degrees": list(BRIDGE_FAN_YAW_DEGREES),
        "bridge_fan_geometry_role": "dense_bridge_rangefinder_sampling_for_live_planner_motion_not_detection_rule_change",
        "max_policy_steps": MAX_POLICY_STEPS,
        "arrival_radius_m": ARRIVAL_RADIUS_M,
        "max_ticks_per_one_step": MAX_TICKS_PER_ONE_STEP,
        "post_arrival_stabilization_ticks": POST_ARRIVAL_STABILIZATION_TICKS,
        "post_arrival_stabilization_role": "disabled_no_stop_scan_phase",
        "post_arrival_zero_thrust_stabilization_enabled": False,
        "standoff_viewpoint_hold_enabled": False,
        "standoff_viewpoint_hold_ticks": STANDOFF_VIEWPOINT_HOLD_TICKS,
        "standoff_lookahead_segment_index": STANDOFF_LOOKAHEAD_SEGMENT_INDEX,
        "standoff_turn_force": STANDOFF_TURN_FORCE,
        "standoff_heading_tolerance_deg": STANDOFF_HEADING_TOLERANCE_DEG,
        "standoff_viewpoint_anchor_source": "baseline_GP_planner_committed_segment_lookahead_not_target_truth",
        "standoff_viewpoint_role": "disabled_no_stop_scan_phase",
        "post_arrival_scan_enabled": False,
        "post_arrival_scan_ticks": POST_ARRIVAL_SCAN_TICKS,
        "post_scan_recenter_ticks": POST_SCAN_RECENTER_TICKS,
        "scan_turn_force": SCAN_TURN_FORCE,
        "post_arrival_scan_role": "disabled_no_stop_scan_phase",
        "gp_fit_every": 5,
        "gp_max_points": 48,
        "clue_samples_per_step": 6,
        "baseline_runtime_source_modified": False,
        "search_decision_algorithm_modified": False,
        "existing_holoocean_bridge_modified": False,
        "run_cases": ["calibration", "target", "teammate_only"],
        "pre_git_status": pre_git_status,
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _load_adapter_config() -> Tuple[Any, np.ndarray, Dict[str, Any]]:
    nav_map_prior, spec = load_scene_map_npz(MAP_NPZ)
    adapter_config = scene_map_config_from_spec(spec)
    return adapter_config, nav_map_prior, spec


def _initialize_state(config: Dict[str, Any]) -> Dict[str, Any]:
    state = runtime_2usv._init_two_usv_knownmap_state(
        episode_seed=int(config["episode_seed"]),
        n_targets=1,
        map_kind=str(config["map_kind"]),
        target_motion_mode="static",
        target_count_upper_bound=1,
        staleness_tau_steps=12,
        resolution_m=float(config["resolution_m"]),
        sensor_range_m=float(config["sensor_range_m"]),
        min_target_separation_m=60.0,
        min_start_distance_m=80.0,
        gp_length_scale_m=40.0,
        gp_noise_std=0.03,
        gp_prior_mean=0.0,
        gp_beta=0.5,
        gp_optimize_hyperparams=False,
        clue_sigma_m=30.0,
        clue_amplitude=2.0,
        clue_noise_std=0.03,
        map_height_cells=int(config["map_height_cells"]),
        map_width_cells=int(config["map_width_cells"]),
        search_info_clue_weight=0.5,
        search_info_intensity_weight=0.5,
        clue_acquisition_mode="ucb",
        anomaly_tail_quantile=0.90,
        anomaly_weight_lambda=1.0,
        anomaly_warmup_steps=20,
        anomaly_min_gp_points=64,
        anomaly_top_quantile=0.90,
        anomaly_top_mass_min=0.18,
        anomaly_entropy_max=0.85,
        anomaly_stability_min=0.30,
        anomaly_alpha_max=0.40,
        anomaly_pre_first_alpha_cap=0.15,
        path_safety_mode="off",
        safe_nav_inflation_radius_cells=0,
        safe_nav_soft_clearance_radius_cells=1,
        safe_nav_lambda_clearance=1.0,
        team_path_avoidance_mode="off",
        team_reservation_safety_distance_cells=1.5,
        team_reservation_lambda=1.0,
        constraint_mode="hard",
        r_hit=1,
        clue_samples_per_step=int(config["clue_samples_per_step"]),
    )
    state["gp_max_points"] = int(config["gp_max_points"])
    state["lambda_u_turn"] = 2.0
    state["gamma"] = 0.95
    state["segment_horizon"] = 8
    state["top_k_anchors"] = 6
    state["viewpoints_per_anchor"] = 6
    state["infosampled_inspected_limit_multiplier"] = 3.0
    state["infosampled_inspected_limit_floor"] = 4
    state["viewpoint_generation_mode"] = runtime_2usv.DEFAULT_VIEWPOINT_GENERATION_MODE
    state["assignment_mode"] = "coordinated"
    state["planner_adaptation_mode"] = "adaptive"
    fixed_cell = tuple(int(v) for v in config.get("fixed_target_grid_cell", []))
    if len(fixed_cell) == 2:
        state["target_positions"] = np.asarray([fixed_cell], dtype=int)
        state["target_ids"] = np.arange(1, dtype=int)
        state["found_mask"] = np.zeros(1, dtype=bool)
        state["find_times"] = [None]
        state["time_since_last_detection"] = 20
        start_positions = [tuple(int(v) for v in local["robot_pos"]) for local in state["usv_states"]]
        state["placement_status"] = str(config.get("target_placement_source"))
        state["actual_min_start_distance_cells"] = min(
            float(math.hypot(fixed_cell[0] - start[0], fixed_cell[1] - start[1]))
            for start in start_positions
        )
        state["actual_min_target_separation_cells"] = None
        state["intensity_map"] = runtime_2usv.init_intensity_map(state["nav_map_prior"], total_mass=1.0)
        state["intensity_map"] = runtime_2usv._apply_team_miss_updates(
            state["intensity_map"],
            [local["robot_pos"] for local in state["usv_states"]],
            state["sensor_range_cells"],
            known_map=state["nav_map_prior"],
            target_total_mass=1.0,
        )
        state["gp_field"].reset()
        runtime_2usv._update_team_clue_truth_map(state)
        runtime_2usv._sample_and_update_team_gp(state, step=0, gp_fit_every=1)
        runtime_2usv._update_team_search_info_state(state, state["intensity_map"])
    return state


def _agent_name(usv_id: int) -> str:
    return "sv{0}".format(int(usv_id))


def _fan_rangefinder_names() -> List[str]:
    return [
        "{0}_{1:02d}".format(P5D3.FAN_RANGEFINDER_PREFIX, index)
        for index in range(len(BRIDGE_FAN_YAW_DEGREES))
    ]


def _surface_vessel_sensors() -> List[Dict[str, Any]]:
    return [
        {"sensor_type": "LocationSensor", "socket": "COM"},
        {"sensor_type": "GPSSensor", "socket": "COM"},
        {"sensor_type": "OrientationSensor", "socket": "COM"},
        P5D3._camera_sensor(),
    ] + _bridge_fan_rangefinder_sensors()


def _bridge_fan_rangefinder_sensors() -> List[Dict[str, Any]]:
    sensors: List[Dict[str, Any]] = []
    for index, yaw_deg in enumerate(BRIDGE_FAN_YAW_DEGREES):
        sensors.append(
            {
                "sensor_type": "RangeFinderSensor",
                "sensor_name": "{0}_{1:02d}".format(P5D3.FAN_RANGEFINDER_PREFIX, index),
                "location": P5D3.P5D1A.RANGEFINDER_LOCATION,
                "rotation": [0.0, 0.0, float(yaw_deg)],
                "configuration": {
                    "LaserMaxDistance": P5D3.P5D1A.RANGEFINDER_MAX_DISTANCE_M,
                    "LaserCount": 1,
                    "LaserAngle": 0.0,
                    "LaserDebug": False,
                },
            }
        )
    return sensors


def _scenario_config(
    *,
    run_kind: str,
    start_world: Dict[int, List[float]],
    target_world: List[float],
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    agents: List[Dict[str, Any]] = []
    for usv_id in (0, 1):
        agents.append(
            {
                "agent_name": _agent_name(usv_id),
                "agent_type": TEAMMATE_AGENT_TYPE,
                "sensors": _surface_vessel_sensors(),
                "control_scheme": 0,
                "location": [float(v) for v in start_world[usv_id]],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    if run_kind == "target":
        agents.append(
            {
                "agent_name": "target",
                "agent_type": TARGET_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": P5D3._control_scheme(TARGET_AGENT_TYPE),
                "location": [float(target_world[0]), float(target_world[1]), 0.5],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    if run_kind == "teammate_only":
        agents.append(
            {
                "agent_name": "teammate_extra0",
                "agent_type": TEAMMATE_AGENT_TYPE,
                "sensors": [{"sensor_type": "LocationSensor", "socket": "COM"}],
                "control_scheme": 0,
                "location": [float(target_world[0]), float(target_world[1]), 0.0],
                "rotation": [0.0, 0.0, 0.0],
            }
        )
    return {
        "name": "phase5d14_{0}".format(run_kind),
        "world": spec.get("world", "OpenWater"),
        "package_name": spec.get("package_name", "Ocean"),
        "main_agent": "sv0",
        "agents": agents,
    }


def _physical_state(start_world: Dict[int, List[float]]) -> Dict[str, Any]:
    return {
        "last_known": {
            0: [float(v) for v in start_world[0]],
            1: [float(v) for v in start_world[1]],
        },
        "global_tick": 0,
        "min_inter_vessel_distance_m": 999999.0,
        "collision_warning_ticks": 0,
        "collision_fail_ticks": 0,
        "fallback_counts": {0: 0, 1: 0},
    }


def _heading_from_orientation(orient_sensor: Optional[np.ndarray]) -> Optional[float]:
    if orient_sensor is None:
        return None
    try:
        matrix = np.reshape(orient_sensor, (3, 3))
        forward = matrix[:, 0]
        return float(np.degrees(np.arctan2(float(forward[1]), float(forward[0]))) % 360.0)
    except Exception:
        return None


def _select_sensor(state_env: Dict[str, Any], agent_name: str, fallback: List[float]) -> Dict[str, Any]:
    loc = get_sensor_vector(state_env, agent_name, "LocationSensor")
    gps = get_sensor_vector(state_env, agent_name, "GPSSensor")
    orient = get_sensor_vector(state_env, agent_name, "OrientationSensor")
    if loc is not None:
        curr = [float(loc[0]), float(loc[1]), float(loc[2])]
        return {
            "selected_sensor": "LocationSensor",
            "curr_pos": curr,
            "orient": orient,
            "heading_deg": _heading_from_orientation(orient),
            "loc_avail": True,
            "gps_avail": gps is not None,
            "fallback_used": False,
        }
    if gps is not None:
        curr = [float(gps[0]), float(gps[1]), float(gps[2])]
        return {
            "selected_sensor": "GPSSensor",
            "curr_pos": curr,
            "orient": orient,
            "heading_deg": _heading_from_orientation(orient),
            "loc_avail": False,
            "gps_avail": True,
            "fallback_used": False,
        }
    return {
        "selected_sensor": "last_known",
        "curr_pos": [float(v) for v in fallback],
        "orient": orient,
        "heading_deg": _heading_from_orientation(orient),
        "loc_avail": False,
        "gps_avail": False,
        "fallback_used": True,
    }


def _compute_controller_cmd(
    tx: float,
    ty: float,
    curr_pos: List[float],
    orient_sensor: Optional[np.ndarray],
) -> Tuple[float, float, float, float, float, float]:
    dx = tx - float(curr_pos[0])
    dy = ty - float(curr_pos[1])
    dist = math.hypot(dx, dy)
    target_heading_deg = np.degrees(np.arctan2(dy, dx)) % 360.0
    heading_deg = _heading_from_orientation(orient_sensor)
    if heading_deg is None:
        heading_deg = 0.0
    heading_error_deg = (target_heading_deg - heading_deg + 180.0) % 360.0 - 180.0
    heading_error_rad = np.radians(heading_error_deg)
    turn = TURN_GAIN * heading_error_rad * MAX_FORCE
    if dist < DIST_SLOW_RADIUS_M:
        forward = MIN_FORCE + (MAX_FORCE - MIN_FORCE) * (dist / DIST_SLOW_RADIUS_M)
    else:
        forward = MAX_FORCE
    forward_factor = np.cos(heading_error_rad)
    if forward_factor < 0.0:
        forward_factor = 0.0
    forward *= forward_factor
    left = np.clip(forward - turn, -MAX_FORCE, MAX_FORCE)
    right = np.clip(forward + turn, -MAX_FORCE, MAX_FORCE)
    return float(left), float(right), float(dist), float(heading_deg), float(target_heading_deg), float(heading_error_deg)


def _aggregate_fan_range(state_env: Dict[str, Any], agent_name: str) -> List[float]:
    values: List[float] = []
    for name in _fan_rangefinder_names():
        value = get_sensor_vector(state_env, agent_name, name)
        if value is None:
            values.append(-1.0)
            continue
        arr = np.asarray(value).astype(float).reshape(-1)
        values.append(float(arr[0]) if arr.size else -1.0)
    return values


def _capture_agent(
    state_env: Dict[str, Any],
    agent_name: str,
    selected: Dict[str, Any],
) -> Dict[str, Any]:
    rgb = get_sensor_vector(state_env, agent_name, P5D3.RGB_CAMERA_NAME)
    fan_range = _aggregate_fan_range(state_env, agent_name)
    return {
        "agent_name": agent_name,
        "rgb": None if rgb is None else np.asarray(rgb).copy(),
        "fan_range": np.asarray(fan_range, dtype=float).copy(),
        "observer_world_location": list(selected["curr_pos"]),
        "observer_heading_deg": selected.get("heading_deg"),
        "selected_sensor": selected.get("selected_sensor"),
        "loc_avail": bool(selected.get("loc_avail")),
        "gps_avail": bool(selected.get("gps_avail")),
        "fallback_used": bool(selected.get("fallback_used")),
    }


def _capture_reference_at(
    reference: Optional[Dict[str, Any]],
    step: int,
    tick_in_step: int,
    agent_name: str,
) -> Optional[Dict[str, Any]]:
    if reference is None:
        return None
    by_step = reference.get("raw_captures_by_step_tick", {})
    step_dict = by_step.get(int(step), {})
    if not isinstance(step_dict, dict) or not step_dict:
        return None
    capture = step_dict.get(int(tick_in_step), {}).get(agent_name)
    if capture is not None:
        return capture
    earlier_ticks = [int(k) for k in step_dict.keys() if int(k) <= int(tick_in_step)]
    if earlier_ticks:
        return step_dict[max(earlier_ticks)].get(agent_name)
    first_tick = min(int(k) for k in step_dict.keys())
    return step_dict[first_tick].get(agent_name)


def _nearest_rgb_capture_in_step(
    run: Optional[Dict[str, Any]],
    step: int,
    tick_in_step: int,
    agent_name: str,
    *,
    max_offset_ticks: int = RGB_SYNC_WINDOW_TICKS,
) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[int]]:
    if run is None:
        return None, None, None
    by_step = run.get("raw_captures_by_step_tick", {})
    step_dict = by_step.get(int(step), {})
    if not isinstance(step_dict, dict) or not step_dict:
        return None, None, None
    best_capture = None
    best_tick = None
    best_abs_offset = None
    for tick_key, captures_by_agent in step_dict.items():
        try:
            tick = int(tick_key)
        except Exception:
            continue
        offset = tick - int(tick_in_step)
        abs_offset = abs(offset)
        if abs_offset > int(max_offset_ticks):
            continue
        if not isinstance(captures_by_agent, dict):
            continue
        capture = captures_by_agent.get(agent_name)
        if not isinstance(capture, dict) or capture.get("rgb") is None:
            continue
        if best_abs_offset is None or (abs_offset, tick) < (best_abs_offset, int(best_tick)):
            best_capture = capture
            best_tick = tick
            best_abs_offset = abs_offset
    if best_capture is None or best_tick is None:
        return None, None, None
    return best_capture, int(best_tick), int(best_tick) - int(tick_in_step)


def _iter_rolling_rgb_captures(
    run: Optional[Dict[str, Any]],
    *,
    rf_tick_global: Optional[int],
    agent_name: str,
    max_offset_ticks: int = RGB_SYNC_WINDOW_TICKS,
) -> List[Dict[str, Any]]:
    if run is None or rf_tick_global is None:
        return []
    by_step = run.get("raw_captures_by_step_tick", {})
    if not isinstance(by_step, dict):
        return []
    rows: List[Dict[str, Any]] = []
    for step_key, step_dict in by_step.items():
        if not isinstance(step_dict, dict):
            continue
        try:
            step = int(step_key)
        except Exception:
            continue
        for tick_key, captures_by_agent in step_dict.items():
            if not isinstance(captures_by_agent, dict):
                continue
            try:
                tick = int(tick_key)
            except Exception:
                continue
            capture = captures_by_agent.get(agent_name)
            if not isinstance(capture, dict) or capture.get("rgb") is None:
                continue
            capture_tick_global = capture.get("tick_global")
            if capture_tick_global is None:
                continue
            offset = int(capture_tick_global) - int(rf_tick_global)
            if abs(offset) > int(max_offset_ticks):
                continue
            rows.append(
                {
                    "step": step,
                    "tick_in_step": tick,
                    "tick_global": int(capture_tick_global),
                    "offset": int(offset),
                    "capture": capture,
                }
            )
    return rows


def _select_synced_rgb_pair(
    *,
    target_run: Optional[Dict[str, Any]],
    calibration_reference: Optional[Dict[str, Any]],
    step: int,
    tick_in_step: int,
    tick_global: Optional[int],
    agent_name: str,
    fan_range: Any,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "rgb_range_sync_attempted": False,
        "rgb_range_sync_applied": False,
        "rgb_range_sync_strategy": RGB_SYNC_STRATEGY,
        "rgb_sync_window_ticks": int(RGB_SYNC_WINDOW_TICKS),
        "rgb_sync_target_tick": None,
        "rgb_sync_baseline_tick": None,
        "rgb_sync_target_step": None,
        "rgb_sync_baseline_step": None,
        "rgb_sync_target_global_tick": None,
        "rgb_sync_baseline_global_tick": None,
        "rgb_sync_target_offset_ticks": None,
        "rgb_sync_baseline_offset_ticks": None,
        "rgb_sync_target_pose_drift_m": None,
        "rgb_sync_baseline_pose_drift_m": None,
        "rgb_sync_candidate_count": 0,
        "rgb_sync_candidate_score": None,
        "rgb_sync_failure_reason": None,
        "synced_target_capture": None,
        "synced_baseline_capture": None,
    }
    range_summary = P5D3.P5D1A._range_summary(fan_range)
    if not bool(range_summary.get("any_hit", False)):
        result["rgb_sync_failure_reason"] = "no_rangefinder_hit"
        return result
    result["rgb_range_sync_attempted"] = True
    if target_run is None or calibration_reference is None:
        result["rgb_sync_failure_reason"] = "missing_target_or_baseline_run"
        return result

    target_origin = (
        target_run.get("raw_captures_by_step_tick", {})
        .get(int(step), {})
        .get(int(tick_in_step), {})
        .get(agent_name)
    )
    baseline_origin = (
        calibration_reference.get("raw_captures_by_step_tick", {})
        .get(int(step), {})
        .get(int(tick_in_step), {})
        .get(agent_name)
    )
    if tick_global is None and isinstance(target_origin, dict):
        tick_global = target_origin.get("tick_global")
    target_candidates = _iter_rolling_rgb_captures(
        target_run,
        rf_tick_global=tick_global,
        agent_name=agent_name,
        max_offset_ticks=RGB_SYNC_WINDOW_TICKS,
    )
    baseline_candidates = _iter_rolling_rgb_captures(
        calibration_reference,
        rf_tick_global=tick_global,
        agent_name=agent_name,
        max_offset_ticks=RGB_SYNC_WINDOW_TICKS,
    )
    if not target_candidates or not baseline_candidates:
        result["rgb_sync_failure_reason"] = "missing_rolling_capture_window"
        return result

    candidates: List[Dict[str, Any]] = []
    for target_row in target_candidates:
        target_capture = target_row["capture"]
        target_offset = int(target_row["offset"])
        for baseline_row in baseline_candidates:
            baseline_capture = baseline_row["capture"]
            baseline_offset = int(baseline_row["offset"])
            rgb_diff = P5D3.P5D1A._rgb_diff_signature(target_capture.get("rgb"), baseline_capture.get("rgb"))
            sphere_blob = P5D3.P5D1A._sphere_blob_signature(target_capture.get("rgb"), baseline_capture.get("rgb"))
            local_blob = _local_range_scaled_blob_signature(
                sphere_blob.get("local_candidate_blobs"),
                range_summary.get("raw"),
            )
            target_pose_drift = _distance_2d(
                target_capture.get("observer_world_location"),
                target_origin.get("observer_world_location") if isinstance(target_origin, dict) else None,
            )
            baseline_pose_drift = _distance_2d(
                baseline_capture.get("observer_world_location"),
                baseline_origin.get("observer_world_location") if isinstance(baseline_origin, dict) else None,
            )
            max_drift = max(float(target_pose_drift or 0.0), float(baseline_pose_drift or 0.0))
            if max_drift > float(RGB_SYNC_MAX_POSE_DRIFT_M):
                continue
            score = (
                (1000000 if bool(local_blob.get("local_range_scaled_blob_present", False)) else 0)
                + int(sphere_blob.get("local_candidate_blob_count", 0) or 0) * 10000
                + int(rgb_diff.get("changed_pixels", 0) or 0)
                - (abs(target_offset) + abs(baseline_offset)) * 100
                - int(round(max_drift * 100.0))
            )
            candidates.append(
                {
                    "score": int(score),
                    "target_step": int(target_row["step"]),
                    "baseline_step": int(baseline_row["step"]),
                    "target_tick": int(target_row["tick_in_step"]),
                    "baseline_tick": int(baseline_row["tick_in_step"]),
                    "target_global_tick": int(target_row["tick_global"]),
                    "baseline_global_tick": int(baseline_row["tick_global"]),
                    "target_offset": int(target_offset),
                    "baseline_offset": int(baseline_offset),
                    "target_pose_drift_m": target_pose_drift,
                    "baseline_pose_drift_m": baseline_pose_drift,
                    "rgb_changed_pixels": int(rgb_diff.get("changed_pixels", 0) or 0),
                    "local_candidate_count": int(sphere_blob.get("local_candidate_blob_count", 0) or 0),
                    "local_range_scaled_blob_present": bool(local_blob.get("local_range_scaled_blob_present", False)),
                    "target_capture": target_capture,
                    "baseline_capture": baseline_capture,
                }
            )

    result["rgb_sync_candidate_count"] = len(candidates)
    if not candidates:
        result["rgb_sync_failure_reason"] = "no_valid_rgb_pair_in_window"
        return result
    candidates.sort(
        key=lambda row: (
            int(row["score"]),
            -abs(int(row["target_offset"])),
            -abs(int(row["baseline_offset"])),
        ),
        reverse=True,
    )
    best = candidates[0]
    result.update(
        {
            "rgb_range_sync_applied": True,
            "rgb_sync_target_step": int(best["target_step"]),
            "rgb_sync_baseline_step": int(best["baseline_step"]),
            "rgb_sync_target_tick": int(best["target_tick"]),
            "rgb_sync_baseline_tick": int(best["baseline_tick"]),
            "rgb_sync_target_global_tick": int(best["target_global_tick"]),
            "rgb_sync_baseline_global_tick": int(best["baseline_global_tick"]),
            "rgb_sync_target_offset_ticks": int(best["target_offset"]),
            "rgb_sync_baseline_offset_ticks": int(best["baseline_offset"]),
            "rgb_sync_target_pose_drift_m": best["target_pose_drift_m"],
            "rgb_sync_baseline_pose_drift_m": best["baseline_pose_drift_m"],
            "rgb_sync_candidate_score": int(best["score"]),
            "rgb_sync_failure_reason": None,
            "synced_target_capture": best["target_capture"],
            "synced_baseline_capture": best["baseline_capture"],
        }
    )
    return result


def _standoff_anchor_from_segment(segment: Any) -> Optional[Tuple[int, int]]:
    if not isinstance(segment, list) or not segment:
        return None
    index = min(int(STANDOFF_LOOKAHEAD_SEGMENT_INDEX), len(segment) - 1)
    try:
        cell = segment[index]
        return (int(cell[0]), int(cell[1]))
    except Exception:
        return None


def _drive_policy_step(
    *,
    env: Any,
    state_env: Dict[str, Any],
    run_kind: str,
    adapter_config: Any,
    nav_map_prior: np.ndarray,
    phys_state: Dict[str, Any],
    policy_step: int,
    target_cells: Dict[int, Tuple[int, int]],
    standoff_anchor_cells: Dict[int, Optional[Tuple[int, int]]],
    wait_applied_map: Dict[int, bool],
    moving_actor_names: List[str],
    live_viewer: Optional[LiveSearchViewer] = None,
    physical_target_world: Optional[List[float]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[int, Dict[str, Dict[str, Any]]], List[Dict[str, Any]]]:
    target_world: Dict[int, List[float]] = {}
    standoff_anchor_world: Dict[int, Optional[List[float]]] = {}
    for usv_id in (0, 1):
        world = list(grid_to_world(target_cells[usv_id], config=adapter_config))
        target_world[usv_id] = [float(world[0]), float(world[1]), float(world[2])]
        anchor_cell = standoff_anchor_cells.get(usv_id)
        if anchor_cell is None:
            standoff_anchor_world[usv_id] = None
        else:
            anchor_world = list(grid_to_world(anchor_cell, config=adapter_config))
            standoff_anchor_world[usv_id] = [float(anchor_world[0]), float(anchor_world[1]), float(anchor_world[2])]

    arrived = {0: False, 1: False}
    final_projected = {0: None, 1: None}
    final_distance = {0: None, 1: None}
    raw_captures: Dict[int, Dict[str, Dict[str, Any]]] = {}
    tick_rows: List[Dict[str, Any]] = []
    step_tick_count = 0
    timeout = False
    per_step_fallback = {0: 0, 1: 0}
    selected_after = {
        0: _select_sensor(state_env, "sv0", phys_state["last_known"][0]),
        1: _select_sensor(state_env, "sv1", phys_state["last_known"][1]),
    }

    def _act_and_capture(
        stabilization_tick: bool = False,
        standoff_hold_tick: bool = False,
        scan_tick: bool = False,
        recenter_tick: bool = False,
        scan_direction: int = 1,
    ) -> None:
        nonlocal state_env, step_tick_count, timeout, selected_after
        commands: Dict[int, Dict[str, Any]] = {}
        for usv_id in (0, 1):
            selected_before = _select_sensor(state_env, _agent_name(usv_id), phys_state["last_known"][usv_id])
            phys_state["last_known"][usv_id] = list(selected_before["curr_pos"])
            if selected_before["fallback_used"]:
                phys_state["fallback_counts"][usv_id] += 1
                per_step_fallback[usv_id] += 1
            if standoff_hold_tick and standoff_anchor_world.get(usv_id) is not None:
                anchor = standoff_anchor_world[usv_id]
                assert anchor is not None
                dx = float(anchor[0]) - float(selected_before["curr_pos"][0])
                dy = float(anchor[1]) - float(selected_before["curr_pos"][1])
                target_heading = float(np.degrees(np.arctan2(dy, dx)) % 360.0)
                heading = selected_before.get("heading_deg")
                if heading is None:
                    heading = _heading_from_orientation(selected_before["orient"])
                if heading is None:
                    heading = 0.0
                err = float((target_heading - float(heading) + 180.0) % 360.0 - 180.0)
                if abs(err) <= float(STANDOFF_HEADING_TOLERANCE_DEG):
                    turn = 0.0
                else:
                    turn = float(np.clip(err / 30.0, -1.0, 1.0) * float(STANDOFF_TURN_FORCE))
                left = -turn
                right = turn
                dist = float(math.hypot(dx, dy))
            elif stabilization_tick or recenter_tick:
                left = 0.0
                right = 0.0
                dist = 0.0
                heading = selected_before.get("heading_deg")
                if heading is None:
                    heading = _heading_from_orientation(selected_before["orient"])
                if heading is None:
                    heading = 0.0
                target_heading = float(heading)
                err = 0.0
            elif scan_tick:
                direction = 1.0 if int(scan_direction) >= 0 else -1.0
                left = -SCAN_TURN_FORCE * direction
                right = SCAN_TURN_FORCE * direction
                dist = 0.0
                heading = selected_before.get("heading_deg")
                if heading is None:
                    heading = _heading_from_orientation(selected_before["orient"])
                if heading is None:
                    heading = 0.0
                target_heading = float(heading)
                err = 0.0
            elif wait_applied_map[usv_id]:
                target = phys_state["last_known"][usv_id]
                left, right, dist, heading, target_heading, err = _compute_controller_cmd(
                    float(target[0]),
                    float(target[1]),
                    selected_before["curr_pos"],
                    selected_before["orient"],
                )
            else:
                target = target_world[usv_id]
                left, right, dist, heading, target_heading, err = _compute_controller_cmd(
                    float(target[0]),
                    float(target[1]),
                    selected_before["curr_pos"],
                    selected_before["orient"],
                )
            commands[usv_id] = {
                "cmd_l": left,
                "cmd_r": right,
                "distance_to_waypoint_m": dist,
                "heading_deg": heading,
                "target_heading_deg": target_heading,
                "heading_error_deg": err,
            }

        env.act("sv0", np.array([commands[0]["cmd_l"], commands[0]["cmd_r"]], dtype=np.float32))
        env.act("sv1", np.array([commands[1]["cmd_l"], commands[1]["cmd_r"]], dtype=np.float32))
        for actor in moving_actor_names:
            env.act(actor, np.zeros(2, dtype=np.float32))
        state_env = env.tick()

        step_tick_count += 1
        phys_state["global_tick"] += 1
        tick_global = int(phys_state["global_tick"])
        raw_captures[step_tick_count] = {}
        projected: Dict[int, Tuple[int, int]] = {}
        selected_after = {}
        for usv_id in (0, 1):
            agent_name = _agent_name(usv_id)
            selected = _select_sensor(state_env, agent_name, phys_state["last_known"][usv_id])
            selected_after[usv_id] = selected
            phys_state["last_known"][usv_id] = list(selected["curr_pos"])
            if selected["fallback_used"]:
                phys_state["fallback_counts"][usv_id] += 1
                per_step_fallback[usv_id] += 1
            projected_cell = world_to_grid(
                selected["curr_pos"],
                config=adapter_config,
                map_shape=nav_map_prior.shape,
                clamp=True,
            )
            projected[usv_id] = (int(projected_cell[0]), int(projected_cell[1]))
            final_projected[usv_id] = projected[usv_id]
            target = phys_state["last_known"][usv_id] if wait_applied_map[usv_id] else target_world[usv_id]
            dist_after = math.hypot(float(selected["curr_pos"][0]) - float(target[0]), float(selected["curr_pos"][1]) - float(target[1]))
            final_distance[usv_id] = float(dist_after)
            if wait_applied_map[usv_id]:
                arrived[usv_id] = True
            elif dist_after < ARRIVAL_RADIUS_M and projected[usv_id] == target_cells[usv_id]:
                arrived[usv_id] = True
            capture = _capture_agent(state_env, agent_name, selected)
            capture.update(
                {
                    "post_arrival_stabilization_tick": bool(stabilization_tick),
                    "standoff_viewpoint_hold_tick": bool(standoff_hold_tick),
                    "post_arrival_scan_tick": bool(scan_tick),
                    "post_scan_recenter_tick": bool(recenter_tick),
                    "scan_direction": int(scan_direction) if scan_tick else 0,
                    "policy_step": int(policy_step),
                    "tick_in_policy_step": int(step_tick_count),
                    "tick_global": int(tick_global),
                    "capture_phase": (
                        "standoff_viewpoint_hold"
                        if standoff_hold_tick
                        else (
                            "post_arrival_scan"
                            if scan_tick
                            else ("post_scan_recenter" if recenter_tick else ("post_arrival_stabilization" if stabilization_tick else "transit"))
                        )
                    ),
                    "standoff_anchor_cell": None
                    if standoff_anchor_cells.get(usv_id) is None
                    else list(standoff_anchor_cells[usv_id]),
                    "standoff_anchor_world": standoff_anchor_world.get(usv_id),
                }
            )
            raw_captures[step_tick_count][agent_name] = capture

        sep = math.hypot(
            float(phys_state["last_known"][0][0]) - float(phys_state["last_known"][1][0]),
            float(phys_state["last_known"][0][1]) - float(phys_state["last_known"][1][1]),
        )
        phys_state["min_inter_vessel_distance_m"] = min(float(phys_state["min_inter_vessel_distance_m"]), float(sep))
        if sep < COLLISION_WARNING_M:
            phys_state["collision_warning_ticks"] += 1
        if sep < COLLISION_FAIL_M:
            phys_state["collision_fail_ticks"] += 1

        for usv_id in (0, 1):
            agent_name = _agent_name(usv_id)
            capture = raw_captures[step_tick_count][agent_name]
            range_summary = P5D3.P5D1A._range_summary(capture["fan_range"])
            if live_viewer is not None and usv_id == 0:
                live_viewer.update_tick(
                    run_kind=run_kind,
                    policy_step=int(policy_step),
                    tick_in_policy_step=int(step_tick_count),
                    tick_global=tick_global,
                    captures_by_agent=raw_captures[step_tick_count],
                    target_world=physical_target_world,
                    rf_hit=any(
                        bool(
                            P5D3.P5D1A._range_summary(raw_captures[step_tick_count][_agent_name(idx)]["fan_range"]).get(
                                "any_hit",
                                False,
                            )
                        )
                        for idx in (0, 1)
                    ),
                )
            tick_rows.append(
                {
                    "run_kind": run_kind,
                    "policy_step": int(policy_step),
                    "tick_in_policy_step": int(step_tick_count),
                    "tick_global": tick_global,
                    "post_arrival_stabilization_tick": bool(stabilization_tick),
                    "standoff_viewpoint_hold_tick": bool(standoff_hold_tick),
                    "post_arrival_scan_tick": bool(scan_tick),
                    "post_scan_recenter_tick": bool(recenter_tick),
                    "scan_direction": int(scan_direction) if scan_tick else 0,
                    "capture_phase": (
                        "standoff_viewpoint_hold"
                        if standoff_hold_tick
                        else (
                            "post_arrival_scan"
                            if scan_tick
                            else ("post_scan_recenter" if recenter_tick else ("post_arrival_stabilization" if stabilization_tick else "transit"))
                        )
                    ),
                    "agent_name": agent_name,
                    "planner_callback_step": True,
                    "planned_path_source": "baseline_GP_mainline_planner",
                    "preset_trajectory_used": False,
                    "target_cell": list(target_cells[usv_id]),
                    "target_world": list(target_world[usv_id]),
                    "standoff_anchor_cell": None
                    if standoff_anchor_cells.get(usv_id) is None
                    else list(standoff_anchor_cells[usv_id]),
                    "standoff_anchor_world": standoff_anchor_world.get(usv_id),
                    "standoff_anchor_source": "baseline_GP_planner_committed_segment_lookahead",
                    "wait_applied": bool(wait_applied_map[usv_id]),
                    "loc_x": float(phys_state["last_known"][usv_id][0]),
                    "loc_y": float(phys_state["last_known"][usv_id][1]),
                    "loc_z": float(phys_state["last_known"][usv_id][2]),
                    "projected_row": int(projected[usv_id][0]),
                    "projected_col": int(projected[usv_id][1]),
                    "projection_matches_target": bool(projected[usv_id] == target_cells[usv_id]),
                    "arrived": bool(arrived[usv_id]),
                    "distance_to_waypoint_m": float(final_distance[usv_id] or 0.0),
                    "heading_deg": capture.get("observer_heading_deg"),
                    "selected_sensor": capture.get("selected_sensor"),
                    "fallback_used": bool(capture.get("fallback_used")),
                    "rgb_present": capture.get("rgb") is not None,
                    "rangefinder_present": bool(range_summary.get("present", False)),
                    "any_rangefinder_hit": bool(range_summary.get("any_hit", False)),
                    "rangefinder_hit_beam_indices": range_summary.get("hit_beam_indices"),
                    "rangefinder_min_positive_range_m": range_summary.get("min_positive_range_m"),
                    "cmd_l": float(commands[usv_id]["cmd_l"]),
                    "cmd_r": float(commands[usv_id]["cmd_r"]),
                    "target_heading_deg": float(commands[usv_id]["target_heading_deg"]),
                    "heading_error_deg": float(commands[usv_id]["heading_error_deg"]),
                    "inter_vessel_distance_m": float(sep),
                }
            )

        if step_tick_count >= MAX_TICKS_PER_ONE_STEP and not (arrived[0] and arrived[1]):
            timeout = True

    while not (arrived[0] and arrived[1]) and not timeout:
        _act_and_capture(stabilization_tick=False)

    if not timeout:
        for _ in range(int(POST_ARRIVAL_STABILIZATION_TICKS)):
            _act_and_capture(stabilization_tick=True)
        for _ in range(int(STANDOFF_VIEWPOINT_HOLD_TICKS)):
            _act_and_capture(standoff_hold_tick=True)
        for scan_index in range(int(POST_ARRIVAL_SCAN_TICKS)):
            direction = 1 if scan_index < int(POST_ARRIVAL_SCAN_TICKS) // 2 else -1
            _act_and_capture(scan_tick=True, scan_direction=direction)
        for _ in range(int(POST_SCAN_RECENTER_TICKS)):
            _act_and_capture(recenter_tick=True)

    final_by_usv: Dict[str, Any] = {}
    for usv_id in (0, 1):
        final_by_usv[str(usv_id)] = {
            "target_cell": list(target_cells[usv_id]),
            "target_world": list(target_world[usv_id]),
            "standoff_anchor_cell": None
            if standoff_anchor_cells.get(usv_id) is None
            else list(standoff_anchor_cells[usv_id]),
            "standoff_anchor_world": standoff_anchor_world.get(usv_id),
            "last_known_world": list(phys_state["last_known"][usv_id]),
            "final_projected_cell": None if final_projected[usv_id] is None else list(final_projected[usv_id]),
            "final_distance_to_target_m": final_distance[usv_id],
            "arrived": bool(arrived[usv_id]),
            "projection_matches_target": bool(final_projected[usv_id] == target_cells[usv_id]),
            "observer_pose_source": "live_location_sensor",
            "orientation_source": "live_orientation_sensor",
        }

    return (
        state_env,
        {
            "run_kind": run_kind,
            "policy_step": int(policy_step),
            "step_ticks": int(step_tick_count),
            "timeout": bool(timeout),
            "arrived": {str(k): bool(v) for k, v in arrived.items()},
            "target_cells": {str(k): list(v) for k, v in target_cells.items()},
            "target_world": {str(k): list(v) for k, v in target_world.items()},
            "standoff_anchor_cells": {
                str(k): None if v is None else list(v) for k, v in standoff_anchor_cells.items()
            },
            "standoff_anchor_world": {
                str(k): None if v is None else list(v) for k, v in standoff_anchor_world.items()
            },
            "per_step_fallback_counts": {str(k): int(v) for k, v in per_step_fallback.items()},
            "final_by_usv": final_by_usv,
            "step_min_inter_vessel_distance_m": float(
                min([row["inter_vessel_distance_m"] for row in tick_rows] or [999999.0])
            ),
        },
        raw_captures,
        tick_rows,
    )


def _distance_2d(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    return P5D3._distance_2d(a, b)


def _estimate_world_position(
    observer_location: List[float],
    observer_heading_deg: Optional[float],
    bearing_deg: Optional[float],
    range_m: Optional[float],
) -> Optional[List[float]]:
    if observer_heading_deg is None or bearing_deg is None or range_m is None:
        return None
    yaw = math.radians(float(observer_heading_deg) + float(bearing_deg))
    return [
        float(observer_location[0]) + float(range_m) * math.cos(yaw),
        float(observer_location[1]) + float(range_m) * math.sin(yaw),
        0.0,
    ]


def _known_teammates(
    *,
    run_kind: str,
    live_positions: Dict[str, List[float]],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    teammates = [
        {
            "agent_name": "sv0",
            "agent_type": TEAMMATE_AGENT_TYPE,
            "location": list(live_positions["sv0"]),
            "is_observer": True,
        },
        {
            "agent_name": "sv1",
            "agent_type": TEAMMATE_AGENT_TYPE,
            "location": list(live_positions["sv1"]),
            "is_observer": True,
        },
    ]
    if run_kind == "teammate_only":
        teammates.append(
            {
                "agent_name": "teammate_extra0",
                "agent_type": TEAMMATE_AGENT_TYPE,
                "location": list(config["target_world_location"]),
                "is_observer": False,
            }
        )
    return teammates


def _nearest_teammate(candidate_position: Optional[List[float]], teammates: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = {
        "nearest_teammate_agent_name": None,
        "nearest_teammate_distance_m": None,
        "within_teammate_exclusion_radius": False,
    }
    for teammate in teammates:
        loc = teammate.get("location")
        distance = _distance_2d(candidate_position, loc if isinstance(loc, list) else None)
        if distance is None:
            continue
        if best["nearest_teammate_distance_m"] is None or distance < float(best["nearest_teammate_distance_m"]):
            best = {
                "nearest_teammate_agent_name": str(teammate.get("agent_name")),
                "nearest_teammate_distance_m": float(distance),
                "within_teammate_exclusion_radius": bool(distance <= TEAMMATE_EXCLUSION_RADIUS_M),
            }
    return best


def _blob_yaw_deg(blob: Optional[Dict[str, Any]]) -> Optional[float]:
    return P5D3.P5D1A._blob_yaw_deg(blob)


def _matched_blob_range(blob: Optional[Dict[str, Any]], raw_beams: Any) -> Dict[str, Any]:
    yaw = _blob_yaw_deg(blob)
    if yaw is None or raw_beams is None:
        return {
            "matched": False,
            "blob_yaw_deg": yaw,
            "matched_beam_index": None,
            "matched_beam_yaw_deg": None,
            "matched_range_m": None,
            "beam_yaw_error_deg": None,
        }
    arr = np.asarray(raw_beams).astype(float).reshape(-1)
    candidates: List[Tuple[float, int, float, float]] = []
    for index, value in enumerate(arr.tolist()):
        if index >= len(BRIDGE_FAN_YAW_DEGREES):
            continue
        range_m = float(value)
        if range_m <= 0.0:
            continue
        beam_yaw = float(BRIDGE_FAN_YAW_DEGREES[index])
        error = abs(beam_yaw - float(yaw))
        if error <= float(P5D3.P5D1A.LOCAL_BLOB_BEAM_YAW_TOLERANCE_DEG):
            candidates.append((error, int(index), beam_yaw, range_m))
    if not candidates:
        return {
            "matched": False,
            "blob_yaw_deg": yaw,
            "matched_beam_index": None,
            "matched_beam_yaw_deg": None,
            "matched_range_m": None,
            "beam_yaw_error_deg": None,
        }
    error, index, beam_yaw, range_m = sorted(candidates)[0]
    return {
        "matched": True,
        "blob_yaw_deg": yaw,
        "matched_beam_index": index,
        "matched_beam_yaw_deg": beam_yaw,
        "matched_range_m": range_m,
        "beam_yaw_error_deg": error,
    }


def _local_range_scaled_blob_signature(blobs: Any, raw_beams: Any) -> Dict[str, Any]:
    if isinstance(blobs, dict):
        candidate_blobs = [blobs]
    elif isinstance(blobs, list):
        candidate_blobs = [blob for blob in blobs if isinstance(blob, dict)]
    else:
        candidate_blobs = []
    evaluated: List[Dict[str, Any]] = []
    for blob in candidate_blobs:
        match = _matched_blob_range(blob, raw_beams)
        area = int(blob.get("area", 0)) if isinstance(blob, dict) else 0
        matched_range = match.get("matched_range_m")
        scaled_area = None if matched_range is None else float(area) * float(matched_range) * float(matched_range)
        evaluated.append(
            {
                "blob": blob,
                "local_blob_area": area,
                "local_blob_range_scaled_area": scaled_area,
                **match,
            }
        )
    viable = [
        item
        for item in evaluated
        if item.get("matched") is True
        and int(item.get("local_blob_area") or 0) >= int(P5D3.P5D1A.LOCAL_BLOB_MIN_AREA)
        and item.get("local_blob_range_scaled_area") is not None
    ]
    best = None
    if viable:
        best = sorted(viable, key=lambda item: float(item.get("local_blob_range_scaled_area") or 0.0), reverse=True)[0]
    blob = best.get("blob") if isinstance(best, dict) else None
    match = best if isinstance(best, dict) else _matched_blob_range(None, raw_beams)
    area = int(blob.get("area", 0)) if isinstance(blob, dict) else 0
    scaled_area = match.get("local_blob_range_scaled_area") if isinstance(best, dict) else None
    present = bool(
        isinstance(blob, dict)
        and area >= int(P5D3.P5D1A.LOCAL_BLOB_MIN_AREA)
        and match.get("matched") is True
        and scaled_area is not None
        and scaled_area >= float(P5D3.P5D1A.LOCAL_BLOB_MIN_RANGE_SCALED_AREA)
    )
    return {
        "local_range_scaled_blob_present": present,
        "local_range_scaled_best_blob": blob,
        "local_range_scaled_evaluated_blobs": evaluated[:8],
        "local_blob_area": area,
        "local_blob_min_area": int(P5D3.P5D1A.LOCAL_BLOB_MIN_AREA),
        "local_blob_min_fill": float(P5D3.P5D1A.LOCAL_BLOB_MIN_FILL),
        "local_blob_range_scaled_area": scaled_area,
        "local_blob_min_range_scaled_area": float(P5D3.P5D1A.LOCAL_BLOB_MIN_RANGE_SCALED_AREA),
        "matched": match.get("matched"),
        "blob_yaw_deg": match.get("blob_yaw_deg"),
        "matched_beam_index": match.get("matched_beam_index"),
        "matched_beam_yaw_deg": match.get("matched_beam_yaw_deg"),
        "matched_range_m": match.get("matched_range_m"),
        "beam_yaw_error_deg": match.get("beam_yaw_error_deg"),
    }


def _event_from_capture(
    *,
    run_kind: str,
    policy_step: int,
    tick_in_policy_step: int,
    tick_global: int,
    agent_name: str,
    capture: Dict[str, Any],
    baseline_capture: Optional[Dict[str, Any]],
    config: Dict[str, Any],
    live_positions: Dict[str, List[float]],
    rgb_sync_target_reference: Optional[Dict[str, Any]] = None,
    rgb_sync_calibration_reference: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fan_range = capture.get("fan_range")
    range_summary = P5D3.P5D1A._range_summary(fan_range)
    rgb_sync = _select_synced_rgb_pair(
        target_run=rgb_sync_target_reference,
        calibration_reference=rgb_sync_calibration_reference,
        step=policy_step,
        tick_in_step=tick_in_policy_step,
        tick_global=tick_global,
        agent_name=agent_name,
        fan_range=fan_range,
    )
    rgb = capture.get("rgb")
    baseline_rgb = None if baseline_capture is None else baseline_capture.get("rgb")
    if rgb_sync.get("rgb_range_sync_applied") is True:
        synced_target_capture = rgb_sync.get("synced_target_capture")
        synced_baseline_capture = rgb_sync.get("synced_baseline_capture")
        if isinstance(synced_target_capture, dict) and synced_target_capture.get("rgb") is not None:
            rgb = synced_target_capture.get("rgb")
        if isinstance(synced_baseline_capture, dict) and synced_baseline_capture.get("rgb") is not None:
            baseline_rgb = synced_baseline_capture.get("rgb")
    rgb_sync_event = {
        key: value
        for key, value in rgb_sync.items()
        if key not in ("synced_target_capture", "synced_baseline_capture")
    }
    rgb_diff = P5D3.P5D1A._rgb_diff_signature(rgb, baseline_rgb)
    sphere_blob = P5D3.P5D1A._sphere_blob_signature(rgb, baseline_rgb)
    local_blob = _local_range_scaled_blob_signature(
        sphere_blob.get("local_candidate_blobs"),
        range_summary.get("raw"),
    )
    raw_found = bool(local_blob.get("local_range_scaled_blob_present", False))
    bearing = local_blob.get("matched_beam_yaw_deg")
    if bearing is None:
        bearing = local_blob.get("blob_yaw_deg")
    matched_range = local_blob.get("matched_range_m")
    observer_location = list(capture["observer_world_location"])
    observer_heading = capture.get("observer_heading_deg")
    estimated = _estimate_world_position(observer_location, observer_heading, bearing, matched_range)
    known_teammates = _known_teammates(run_kind=run_kind, live_positions=live_positions, config=config)
    nearest = _nearest_teammate(estimated, known_teammates)
    teammate_rejected = bool(raw_found and nearest.get("within_teammate_exclusion_radius") is True)
    range_limited = bool(matched_range is not None and float(matched_range) <= RELIABLE_DISTANCE_LIMIT_M + 1.0)
    accepted = bool(raw_found and range_limited and not teammate_rejected)
    target_present = run_kind == "target"
    target_location = config["target_world_location"] if target_present else None
    target_error = _distance_2d(estimated, target_location if isinstance(target_location, list) else None)
    return {
        "run_kind": run_kind,
        "tick_global": int(tick_global),
        "policy_step": int(policy_step),
        "tick_in_policy_step": int(tick_in_policy_step),
        "reporter_usv_id": agent_name,
        "agent_id": agent_name,
        "sensor_id": "{0}+fan_rangefinder".format(P5D3.RGB_CAMERA_NAME),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "expected_target_present_for_audit": bool(target_present),
        "raw_sensor_found": bool(raw_found),
        "accepted_candidate": bool(accepted),
        "teammate_rejected": bool(teammate_rejected),
        "range_limited": bool(range_limited),
        "estimated_world_position": estimated,
        "target_world_location_for_audit": target_location,
        "target_position_error_m": target_error,
        "observer_world_location": observer_location,
        "observer_heading_deg": observer_heading,
        "post_arrival_stabilization_tick": bool(capture.get("post_arrival_stabilization_tick", False)),
        "standoff_viewpoint_hold_tick": bool(capture.get("standoff_viewpoint_hold_tick", False)),
        "post_arrival_scan_tick": bool(capture.get("post_arrival_scan_tick", False)),
        "post_scan_recenter_tick": bool(capture.get("post_scan_recenter_tick", False)),
        "scan_direction": int(capture.get("scan_direction", 0) or 0),
        "capture_phase": str(capture.get("capture_phase", "unknown")),
        "standoff_anchor_cell": capture.get("standoff_anchor_cell"),
        "standoff_anchor_world": capture.get("standoff_anchor_world"),
        "standoff_anchor_source": "baseline_GP_planner_committed_segment_lookahead",
        "observer_pose_source": "live_location_sensor",
        "observer_orientation_source": "live_orientation_sensor",
        "world_projection_uses_observer_heading": True,
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
        "live_capture_primary_detection_source": True,
        "replay_events_used_for_detection": False,
        "calibration_reference_used": baseline_capture is not None or rgb_sync.get("rgb_range_sync_applied") is True,
        "calibration_reference_role": "rgb_background_reference_only_not_detection_event_replay",
        "rgb_range_sync_fix_enabled": True,
        "continuous_rolling_rgb_rf_sync_enabled": True,
        "stop_scan_used_for_detection": False,
        **rgb_sync_event,
        **nearest,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
    }


def _fusion_for_step(
    *,
    run_kind: str,
    policy_step: int,
    step_events: List[Dict[str, Any]],
    config: Dict[str, Any],
    found_mask_before: List[bool],
) -> Dict[str, Any]:
    accepted = [event for event in step_events if event.get("accepted_candidate") is True]
    clusters = P5D3._cluster_candidates(accepted)
    target_present = run_kind == "target"
    target_location = config["target_world_location"] if target_present else None
    confirmed_clusters: List[Dict[str, Any]] = []
    for cluster in clusters:
        error = _distance_2d(cluster.get("fused_world_position"), target_location if isinstance(target_location, list) else None)
        cluster["target_position_error_m"] = error
        cluster["confirmed_static_target_candidate_for_audit"] = bool(
            target_present and error is not None and error <= TARGET_AUDIT_DISTANCE_THRESHOLD_M
        )
        if int(cluster.get("candidate_count", 0)) > 0:
            confirmed_clusters.append(cluster)
    shared_found = bool(confirmed_clusters)
    new_found = bool(shared_found and any(not bool(v) for v in found_mask_before))
    if target_present and shared_found:
        outcome = "true_positive"
    elif target_present and not shared_found:
        outcome = "false_negative"
    elif shared_found:
        outcome = "false_positive"
    else:
        outcome = "true_negative"
    return {
        "run_kind": run_kind,
        "policy_step": int(policy_step),
        "expected_target_present_for_audit": bool(target_present),
        "raw_sensor_detection_count": sum(1 for event in step_events if event.get("raw_sensor_found") is True),
        "accepted_candidate_count": len(accepted),
        "teammate_rejected_count": sum(1 for event in step_events if event.get("teammate_rejected") is True),
        "fused_candidate_count": len(confirmed_clusters),
        "fused_candidates": confirmed_clusters,
        "shared_found_this_step": bool(shared_found),
        "new_found_this_step": bool(new_found),
        "found_mask_before": list(found_mask_before),
        "outcome": outcome,
        "candidate_fusion_called": True,
        "live_capture_primary_detection_source": True,
        "replay_events_used_for_detection": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
    }


def _truth_flags_false(rows: List[Dict[str, Any]]) -> bool:
    return all(
        row.get("truth_used_for_detection") is False
        and row.get("actor_truth_used_for_detection") is False
        and row.get("target_truth_used_for_detection") is False
        and row.get("teammate_truth_used_for_detection") is False
        for row in rows
    )


def _update_mainline_after_detection(
    *,
    state: Dict[str, Any],
    step: int,
    predicted_intensity: np.ndarray,
    robot_positions: List[Tuple[int, int]],
    team_detected_mask: np.ndarray,
    detected_by_usv: Dict[int, int],
    local_observation_terms: Dict[int, Tuple[float, float]],
    assignments: Dict[int, Dict[str, Any]],
    joint_summary: Dict[str, Any],
    wait_applied_map: Dict[int, bool],
    conflict_type: Optional[str],
    conflict_penalty: float,
    config: Dict[str, Any],
) -> Tuple[List[int], Dict[str, Any]]:
    before_found = state["found_mask"].tolist()
    before_find_times = list(state["find_times"])
    new_indices = runtime_2usv.update_found_mask(
        state["found_mask"],
        team_detected_mask,
        state["find_times"],
        step,
    )
    team_detected_count = len(new_indices)
    if team_detected_count > 0:
        state["time_since_last_detection"] = 0
    else:
        state["time_since_last_detection"] += 1

    predicted_intensity = runtime_2usv.apply_known_occupancy_constraints(
        predicted_intensity,
        state["nav_map_prior"],
        preserve_mass=True,
    )
    remaining_target_mass_before = runtime_2usv._remaining_target_intensity_mass(state)
    updated_intensity = runtime_2usv._apply_team_miss_updates(
        predicted_intensity,
        robot_positions,
        state["sensor_range_cells"],
        known_map=state["nav_map_prior"],
        target_total_mass=remaining_target_mass_before,
    )
    if team_detected_count > 0:
        hit_positions = [
            tuple(int(v) for v in state["target_positions"][idx])
            for idx in new_indices
        ]
        updated_intensity = runtime_2usv.hit_update_intensity(
            updated_intensity,
            hit_positions=hit_positions,
            hit_count=team_detected_count,
            r_hit=state["r_hit"],
            known_map=state["nav_map_prior"],
            target_total_mass=runtime_2usv._remaining_target_intensity_mass(state),
        )
    state["intensity_map"] = updated_intensity
    runtime_2usv._sample_and_update_team_gp(state, step=step, gp_fit_every=int(config["gp_fit_every"]))
    runtime_2usv._update_team_search_info_state(state, state["intensity_map"])
    runtime_2usv._append_anomaly_target_neighborhood_metric(state, step=step)

    state["found_count_curve"].append(int(state["found_mask"].sum()))
    state["remaining_intensity_mass_curve"].append(runtime_2usv.remaining_intensity_mass(state["intensity_map"]))
    state["peak_intensity_ratio_curve"].append(
        runtime_2usv.peak_intensity_ratio(state["intensity_map"], state["nav_map_prior"])
    )
    state["known_free_observation_ratio_curve"].append(
        runtime_2usv.known_free_observation_ratio(state["last_seen_step"], state["nav_map_prior"])
    )
    state["completed_steps"] = int(step)
    state["team_trace_rows"].append(
        runtime_2usv._team_trace_row(
            team_step=step,
            assignments=assignments,
            joint_summary=joint_summary,
            conflict_type=conflict_type,
            conflict_penalty=conflict_penalty,
            wait_applied_map=wait_applied_map,
            team_detected_count=team_detected_count,
        )
    )
    for usv_id, local in enumerate(state["usv_states"]):
        effective_gain, stale_ratio = local_observation_terms[usv_id]
        runtime_2usv._append_trimmed(local["recent_effective_observation_gains"], effective_gain, max_len=10)
        state["trace_rows"].append(
            runtime_2usv._local_trace_row(
                team_step=step,
                usv_id=usv_id,
                local=local,
                clue_acquisition_mode=str(state.get("clue_acquisition_mode", "ucb")),
                responsibility_owner_map=state.get("responsibility_owner_map"),
                assignment=assignments[usv_id],
                wait_applied=wait_applied_map[usv_id],
                conflict_type=conflict_type,
                conflict_penalty=conflict_penalty,
                detected_count_this_step=detected_by_usv[usv_id],
                effective_observation_gain=effective_gain,
                stale_refresh_ratio=stale_ratio,
                joint_assignment_score=float(joint_summary["joint_assignment_score"]),
            )
        )
    return new_indices, {
        "mainline_step": int(step),
        "detected_mask": team_detected_mask.tolist(),
        "found_mask_before": before_found,
        "found_mask_after": state["found_mask"].tolist(),
        "find_times_before": before_find_times,
        "find_times_after": list(state["find_times"]),
        "new_found_indices": list(new_indices),
        "shared_found": bool(np.any(team_detected_mask)),
        "all_found_after_update": bool(np.all(state["found_mask"])),
        "update_found_mask_original_called": True,
        "update_found_mask_module": runtime_2usv.update_found_mask.__module__,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
    }


def _run_live_case(
    *,
    run_kind: str,
    config: Dict[str, Any],
    calibration_reference: Optional[Dict[str, Any]] = None,
    detection_enabled: bool,
    display_live: bool = False,
    display_fps: float = DEFAULT_DISPLAY_FPS,
    display_every_ticks: int = DEFAULT_DISPLAY_EVERY_TICKS,
) -> Dict[str, Any]:
    import holoocean

    adapter_config, nav_map_prior, spec = _load_adapter_config()
    live_viewer: Optional[LiveSearchViewer] = None
    if display_live and run_kind == "target":
        live_viewer = LiveSearchViewer(
            enabled=True,
            adapter_config=adapter_config,
            map_shape=nav_map_prior.shape,
            title="Phase 5D-14 Live Dual-USV Search",
            fps=display_fps,
            every_ticks=display_every_ticks,
        )
    state = _initialize_state(config)
    target_cell = tuple(int(v) for v in np.asarray(state["target_positions"])[0].tolist())
    target_world_arr = grid_to_world(target_cell, config=adapter_config)
    target_offset = config.get("physical_target_world_offset_m", [0.0, 0.0, 0.0])
    target_world = [
        float(target_world_arr[0]) + float(target_offset[0]),
        float(target_world_arr[1]) + float(target_offset[1]),
        0.5 + float(target_offset[2]),
    ]
    config["target_world_location"] = list(target_world)
    config["target_grid_cell"] = [int(target_cell[0]), int(target_cell[1])]
    start_world: Dict[int, List[float]] = {}
    for usv_id, local in enumerate(state["usv_states"]):
        world = list(grid_to_world(tuple(int(v) for v in local["robot_pos"]), config=adapter_config))
        world[2] = 0.0
        start_world[usv_id] = [float(v) for v in world]

    scenario_cfg = _scenario_config(run_kind=run_kind, start_world=start_world, target_world=target_world, spec=spec)
    phys_state = _physical_state(start_world)
    raw_captures_by_step_tick: Dict[int, Dict[int, Dict[str, Dict[str, Any]]]] = {}
    tick_trace: List[Dict[str, Any]] = []
    policy_trace: List[Dict[str, Any]] = []
    event_rows: List[Dict[str, Any]] = []
    fusion_rows: List[Dict[str, Any]] = []
    adapter_rows: List[Dict[str, Any]] = []
    update_rows: List[Dict[str, Any]] = []
    moving_actor_names: List[str] = []
    if run_kind == "target":
        moving_actor_names.append("target")
    if run_kind == "teammate_only":
        moving_actor_names.append("teammate_extra0")
    adapter = ReusableMainlinePerceptionAdapter(adapter_id="phase5d14_{0}".format(run_kind))
    adapter.reset_episode("phase5d14_{0}".format(run_kind))
    launch_ok = False
    error = ""
    terminated_reason = "max_policy_steps"
    physical_failure = False
    started = time.perf_counter()

    try:
        with holoocean.make(scenario_cfg=scenario_cfg) as env:
            launch_ok = True
            env.act("sv0", np.zeros(2, dtype=np.float32))
            env.act("sv1", np.zeros(2, dtype=np.float32))
            for actor in moving_actor_names:
                env.act(actor, np.zeros(2, dtype=np.float32))
            state_env = env.tick()

            for step in range(1, int(config["max_policy_steps"]) + 1):
                step_start = time.perf_counter()
                state["target_positions"] = runtime_2usv.step_targets(
                    state["target_positions"],
                    motion_mode="static",
                    occ_grid=state["true_map"],
                    rng=state["scenario_rng"],
                    found_mask=state["found_mask"],
                )
                predicted_intensity = runtime_2usv.predict_intensity(
                    state["intensity_map"],
                    state["nav_map_prior"],
                    motion_mode="static",
                )
                t0 = time.perf_counter()
                assignments, joint_summary = runtime_2usv._joint_assign_two_usv_segments(
                    team_state=state,
                    policy_name=MAINLINE_POLICY_NAME,
                    predicted_intensity=predicted_intensity,
                    step=step,
                )
                joint_summary["clue_acquisition_mode"] = str(state.get("clue_acquisition_mode", "ucb"))
                anomaly_conditional_diag = {
                    "anomaly_conditional_alpha": float(state.get("anomaly_conditional_alpha", 0.0)),
                    "anomaly_conditional_triggered": bool(state.get("anomaly_conditional_triggered", False)),
                    "anomaly_gate_reason": str(state.get("anomaly_gate_reason", "mode_not_conditional")),
                    "anomaly_top_mass_ratio": float(state.get("anomaly_top_mass_ratio", 0.0)),
                    "anomaly_entropy_norm": float(state.get("anomaly_entropy_norm", 0.0)),
                    "anomaly_hotspot_stability": float(state.get("anomaly_hotspot_stability", 1.0)),
                    "anomaly_pre_first_alpha_capped": bool(state.get("anomaly_pre_first_alpha_capped", False)),
                }
                joint_summary.update(anomaly_conditional_diag)
                for assignment in assignments.values():
                    assignment["plan_details"].update(anomaly_conditional_diag)
                runtime_2usv._apply_joint_assignment_to_locals(
                    state,
                    MAINLINE_POLICY_NAME,
                    assignments,
                    search_commit_window=4,
                    search_commit_max_window=10,
                    search_commit_path_divisor=2,
                )
                state["planning_time_ms"].append((time.perf_counter() - t0) * 1000.0)
                wait_applied_map, conflict_type, conflict_penalty = runtime_2usv._resolve_execution_conflict(
                    state,
                    assignments,
                    safety_distance_cells=float(state.get("team_reservation_safety_distance_cells", 1.5)),
                )
                wait_applied_map = {int(k): bool(v) for k, v in wait_applied_map.items()}

                local_before: Dict[int, Dict[str, Any]] = {}
                target_cells: Dict[int, Tuple[int, int]] = {}
                standoff_anchor_cells: Dict[int, Optional[Tuple[int, int]]] = {}
                expected_exec_results: Dict[int, Optional[ExecutionStepResult]] = {}
                local_observation_terms: Dict[int, Tuple[float, float]] = {}
                for usv_id, local in enumerate(state["usv_states"]):
                    local_before[usv_id] = {
                        "robot_pos": list(local["robot_pos"]),
                        "committed_segment": [list(c) for c in local.get("committed_segment", [])],
                        "commit_remaining": int(local.get("commit_remaining", 0)),
                    }
                    local_observation_terms[usv_id] = runtime_2usv._observation_progress_for_robot(state, local["robot_pos"])
                    if wait_applied_map[usv_id]:
                        target_cells[usv_id] = tuple(int(v) for v in local["robot_pos"])
                        expected_exec_results[usv_id] = None
                    else:
                        segment = local.get("committed_segment", [])
                        target_cells[usv_id] = tuple(int(v) for v in segment[1]) if len(segment) > 1 else tuple(int(v) for v in local["robot_pos"])
                        expected_exec_results[usv_id] = runtime_2usv.execute_next_step(
                            state["true_map"],
                            state["nav_map_prior"],
                            tuple(int(v) for v in local["robot_pos"]),
                            [tuple(int(c) for c in cell) for cell in local["committed_segment"]],
                        )
                    standoff_anchor_cells[usv_id] = _standoff_anchor_from_segment(local.get("committed_segment", []))

                state_env, physical_result, raw_step_captures, step_tick_rows = _drive_policy_step(
                    env=env,
                    state_env=state_env,
                    run_kind=run_kind,
                    adapter_config=adapter_config,
                    nav_map_prior=nav_map_prior,
                    phys_state=phys_state,
                    policy_step=step,
                    target_cells=target_cells,
                    standoff_anchor_cells=standoff_anchor_cells,
                    wait_applied_map=wait_applied_map,
                    moving_actor_names=moving_actor_names,
                    live_viewer=live_viewer,
                    physical_target_world=target_world,
                )
                raw_captures_by_step_tick[step] = raw_step_captures
                tick_trace.extend(step_tick_rows)

                exec_results: Dict[int, Optional[ExecutionStepResult]] = {}
                step_physical_success = not bool(physical_result.get("timeout"))
                for usv_id, local in enumerate(state["usv_states"]):
                    final_info = physical_result["final_by_usv"][str(usv_id)]
                    final_cell_raw = final_info["final_projected_cell"]
                    final_cell = (
                        tuple(int(v) for v in final_cell_raw)
                        if final_cell_raw is not None
                        else tuple(int(v) for v in local["robot_pos"])
                    )
                    success = bool(
                        final_info["arrived"]
                        and final_info["projection_matches_target"]
                        and not physical_result.get("timeout")
                    )
                    if wait_applied_map[usv_id]:
                        exec_results[usv_id] = None
                    else:
                        exec_results[usv_id] = ExecutionStepResult(
                            move_success=success,
                            collision=False,
                            collision_cell=None,
                            new_robot_pos=final_cell,
                        )
                    step_physical_success = bool(step_physical_success and (success or wait_applied_map[usv_id]))

                if not step_physical_success:
                    physical_failure = True
                    terminated_reason = "physical_failure"
                    if live_viewer is not None:
                        live_viewer.update_step_result(
                            found_mask=state["found_mask"].tolist(),
                            detected=False,
                            all_found=False,
                            status="{0} | step {1} | physical_failure".format(run_kind, int(step)),
                        )
                    policy_trace.append(
                        {
                            "run_kind": run_kind,
                            "policy_step": int(step),
                            "planner_callback_called": True,
                            "physical_step_success": False,
                            "physical_result": physical_result,
                            "terminated_reason_after_step": terminated_reason,
                        }
                    )
                    break

                for usv_id, local in enumerate(state["usv_states"]):
                    runtime_2usv._update_local_after_execution(local, wait_applied_map[usv_id], exec_results[usv_id])

                robot_positions = []
                local_after: Dict[int, Dict[str, Any]] = {}
                for usv_id, local in enumerate(state["usv_states"]):
                    robot_cell = tuple(int(v) for v in local["robot_pos"])
                    robot_positions.append(robot_cell)
                    local_after[usv_id] = {
                        "robot_pos": list(robot_cell),
                        "committed_segment": [list(c) for c in local.get("committed_segment", [])],
                        "commit_remaining": int(local.get("commit_remaining", 0)),
                    }
                    runtime_2usv.refresh_last_seen(
                        state["last_seen_step"],
                        state["nav_map_prior"],
                        robot_cell,
                        state["sensor_range_cells"],
                        step=step,
                    )
                state["staleness_map"] = runtime_2usv.build_staleness_map(
                    state["last_seen_step"],
                    state["nav_map_prior"],
                    current_step=step,
                    tau_stale=12,
                )

                step_events: List[Dict[str, Any]] = []
                if detection_enabled:
                    for tick_in_step, captures_by_agent in raw_step_captures.items():
                        live_positions = {
                            agent: list(captures_by_agent[agent]["observer_world_location"])
                            for agent in OBSERVER_AGENT_NAMES
                        }
                        tick_global = next(
                            (
                                int(row["tick_global"])
                                for row in step_tick_rows
                                if int(row["tick_in_policy_step"]) == int(tick_in_step)
                            ),
                            int(phys_state["global_tick"]),
                        )
                        for agent_name in OBSERVER_AGENT_NAMES:
                            baseline_capture = _capture_reference_at(
                                calibration_reference,
                                step,
                                int(tick_in_step),
                                agent_name,
                            )
                            event = _event_from_capture(
                                run_kind=run_kind,
                                policy_step=step,
                                tick_in_policy_step=int(tick_in_step),
                                tick_global=tick_global,
                                agent_name=agent_name,
                                capture=captures_by_agent[agent_name],
                                baseline_capture=baseline_capture,
                                config=config,
                                live_positions=live_positions,
                                rgb_sync_target_reference={"raw_captures_by_step_tick": raw_captures_by_step_tick},
                                rgb_sync_calibration_reference=calibration_reference,
                            )
                            step_events.append(event)
                    event_rows.extend(step_events)

                found_mask_before_adapter = [bool(v) for v in state["found_mask"].tolist()]
                fusion = _fusion_for_step(
                    run_kind=run_kind,
                    policy_step=step,
                    step_events=step_events,
                    config=config,
                    found_mask_before=found_mask_before_adapter,
                )
                fusion_rows.append(fusion)

                if detection_enabled:
                    step_input = MainlineAdapterStepInput(
                        run_kind=run_kind,
                        step_index=step,
                        target_count=int(state["found_mask"].size),
                        found_mask_before=found_mask_before_adapter,
                        per_agent_events=step_events,
                        candidate_fusion_result=fusion,
                        known_teammates=_known_teammates(
                            run_kind=run_kind,
                            live_positions={
                                "sv0": list(phys_state["last_known"][0]),
                                "sv1": list(phys_state["last_known"][1]),
                            },
                            config=config,
                        ),
                    )
                    output = adapter.observe_step(step_input)
                    team_detected_mask = adapter.build_detected_mask(step, int(state["found_mask"].size))
                    adapter_row = output.asdict()
                    adapter_row.update(
                        {
                            "adapter_module": ReusableMainlinePerceptionAdapter.__module__,
                            "mainline_step": int(step),
                            "detected_mask_returned_to_mainline": team_detected_mask.tolist(),
                            "live_capture_primary_detection_source": True,
                            "replay_events_used_for_detection": False,
                            "planned_path_source": "baseline_GP_mainline_planner",
                        }
                    )
                    adapter_rows.append(adapter_row)
                else:
                    team_detected_mask = np.zeros_like(state["found_mask"], dtype=bool)

                detected_by_usv = {0: 0, 1: 0}
                if np.any(team_detected_mask):
                    for event in step_events:
                        if event.get("accepted_candidate") is True:
                            usv_id = int(str(event.get("reporter_usv_id", "sv0")).replace("sv", ""))
                            detected_by_usv[usv_id] = 1

                new_indices, update_row = _update_mainline_after_detection(
                    state=state,
                    step=step,
                    predicted_intensity=predicted_intensity,
                    robot_positions=robot_positions,
                    team_detected_mask=team_detected_mask,
                    detected_by_usv=detected_by_usv,
                    local_observation_terms=local_observation_terms,
                    assignments=assignments,
                    joint_summary=joint_summary,
                    wait_applied_map=wait_applied_map,
                    conflict_type=conflict_type,
                    conflict_penalty=conflict_penalty,
                    config=config,
                )
                update_row.update(
                    {
                        "run_kind": run_kind,
                        "source_shared_found": bool(fusion.get("shared_found_this_step")),
                        "source_accepted_candidate_count": int(fusion.get("accepted_candidate_count", 0)),
                        "source_fused_candidate_count": int(fusion.get("fused_candidate_count", 0)),
                        "live_capture_primary_detection_source": detection_enabled,
                        "replay_events_used_for_detection": False,
                    }
                )
                update_rows.append(update_row)

                all_found_after = bool(np.all(state["found_mask"]))
                if all_found_after:
                    terminated_reason = "all_found"
                    state["terminated_reason"] = "all_found"
                if live_viewer is not None:
                    live_viewer.update_step_result(
                        found_mask=state["found_mask"].tolist(),
                        detected=bool(np.any(team_detected_mask)),
                        all_found=all_found_after,
                        status="{0} | step {1} | detected={2} | all_found={3}".format(
                            run_kind,
                            int(step),
                            bool(np.any(team_detected_mask)),
                            all_found_after,
                        ),
                    )
                policy_trace.append(
                    {
                        "run_kind": run_kind,
                        "policy_step": int(step),
                        "planner_callback_called": True,
                        "planner_decision_source": "baseline_GP.marine_knownmap_runtime_2usv._joint_assign_two_usv_segments",
                        "planned_path_source": "baseline_GP_mainline_planner",
                        "preset_trajectory_used": False,
                        "joint_assignment_score": float(joint_summary.get("joint_assignment_score", 0.0)),
                        "assignment_order": list(joint_summary.get("assignment_order", [])),
                        "same_viewpoint_selected": bool(joint_summary.get("same_viewpoint_selected", False)),
                        "sv0_viewpoint_cell": assignments[0]["plan_details"].get("viewpoint_cell"),
                        "sv1_viewpoint_cell": assignments[1]["plan_details"].get("viewpoint_cell"),
                        "sv0_segment_path": [list(cell) for cell in assignments[0].get("segment_path", [])],
                        "sv1_segment_path": [list(cell) for cell in assignments[1].get("segment_path", [])],
                        "sv0_next_target_cell": list(target_cells[0]),
                        "sv1_next_target_cell": list(target_cells[1]),
                        "sv0_standoff_anchor_cell": None
                        if standoff_anchor_cells.get(0) is None
                        else list(standoff_anchor_cells[0]),
                        "sv1_standoff_anchor_cell": None
                        if standoff_anchor_cells.get(1) is None
                        else list(standoff_anchor_cells[1]),
                        "standoff_anchor_source": "baseline_GP_planner_committed_segment_lookahead",
                        "standoff_viewpoint_hold_enabled": True,
                        "local_before": {str(k): v for k, v in local_before.items()},
                        "local_after": {str(k): v for k, v in local_after.items()},
                        "expected_execute_next_step": {
                            str(k): None
                            if v is None
                            else {
                                "move_success": bool(v.move_success),
                                "collision": bool(v.collision),
                                "collision_cell": None if v.collision_cell is None else list(v.collision_cell),
                                "new_robot_pos": list(v.new_robot_pos),
                            }
                            for k, v in expected_exec_results.items()
                        },
                        "physical_result": physical_result,
                        "candidate_fusion_called": True,
                        "adapter_observe_step_called": bool(detection_enabled),
                        "update_found_mask_original_called": True,
                        "new_found_indices": list(new_indices),
                        "found_mask_after": state["found_mask"].tolist(),
                        "find_times_after": list(state["find_times"]),
                        "all_found_after_update": all_found_after,
                        "terminated_reason_after_step": terminated_reason if all_found_after else "running",
                        "step_wall_time_s": round(time.perf_counter() - step_start, 6),
                        "truth_used_for_detection": False,
                        "actor_truth_used_for_detection": False,
                        "target_truth_used_for_detection": False,
                        "teammate_truth_used_for_detection": False,
                    }
                )
                if all_found_after:
                    break
            else:
                state["completed_steps"] = int(config["max_policy_steps"])
    except Exception as exc:
        error = "{0}: {1}".format(type(exc).__name__, exc)
        terminated_reason = "exception"
        policy_trace.append(
            {
                "run_kind": run_kind,
                "policy_step": 0,
                "scenario_error": error,
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        if live_viewer is not None:
            live_viewer.close()

    return {
        "run_kind": run_kind,
        "launch_ok": bool(launch_ok),
        "error": error,
        "terminated_reason": terminated_reason,
        "physical_failure": bool(physical_failure),
        "initial_target_cell": config.get("target_grid_cell"),
        "target_world_location": config.get("target_world_location"),
        "found_mask_final": state["found_mask"].tolist(),
        "find_times_final": list(state["find_times"]),
        "all_found": bool(np.all(state["found_mask"])),
        "all_found_step": next((int(row["mainline_step"]) for row in update_rows if row.get("all_found_after_update") is True), None),
        "completed_steps": int(state.get("completed_steps", 0)),
        "raw_captures_by_step_tick": raw_captures_by_step_tick,
        "tick_trace": tick_trace,
        "policy_trace": policy_trace,
        "event_rows": event_rows,
        "fusion_rows": fusion_rows,
        "adapter_rows": adapter_rows,
        "update_rows": update_rows,
        "team_trace_rows": list(state.get("team_trace_rows", [])),
        "local_trace_rows": list(state.get("trace_rows", [])),
        "planning_time_ms": [float(v) for v in state.get("planning_time_ms", [])],
        "min_inter_vessel_distance_m": (
            0.0
            if float(phys_state.get("min_inter_vessel_distance_m", 999999.0)) == 999999.0
            else float(phys_state["min_inter_vessel_distance_m"])
        ),
        "collision_warning_ticks": int(phys_state.get("collision_warning_ticks", 0)),
        "collision_fail_ticks": int(phys_state.get("collision_fail_ticks", 0)),
        "wall_time_s": round(time.perf_counter() - started, 6),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
    }


def _strip_run_raw(run: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(run)
    clean.pop("raw_captures_by_step_tick", None)
    return clean


def _rgb_image(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim >= 3:
        img = arr[..., :3]
        if np.issubdtype(img.dtype, np.floating) and float(np.nanmax(img)) <= 1.0:
            img = img * 255.0
        return np.clip(img, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        finite = np.nan_to_num(arr.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
        maxv = float(np.max(finite)) if finite.size else 0.0
        if maxv > 0.0:
            finite = finite / maxv * 255.0
        return np.clip(finite, 0, 255).astype(np.uint8)
    return np.zeros((16, 16, 3), dtype=np.uint8)


def _save_image(path: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        from PIL import Image

        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(_rgb_image(value)).save(path)
        return path
    except Exception as exc:
        print("[WARN] image save failed for {0}: {1}".format(path, exc))
        return None


def _diff_image(rgb_value: Any, baseline_value: Any) -> Optional[np.ndarray]:
    if rgb_value is None or baseline_value is None:
        return None
    rgb = np.asarray(rgb_value)[..., :3].astype(np.int16)
    baseline = np.asarray(baseline_value)[..., :3].astype(np.int16)
    if rgb.shape[:2] != baseline.shape[:2]:
        return None
    diff = np.max(np.abs(rgb - baseline), axis=-1)
    return np.clip(diff * 4, 0, 255).astype(np.uint8)


def _white_neutral_mask_image(rgb_value: Any, baseline_value: Any) -> Optional[np.ndarray]:
    if rgb_value is None or baseline_value is None:
        return None
    rgb = np.asarray(rgb_value)[..., :3].astype(np.int16)
    baseline = np.asarray(baseline_value)[..., :3].astype(np.int16)
    if rgb.shape[:2] != baseline.shape[:2]:
        return None
    diff = np.max(np.abs(rgb - baseline), axis=-1)
    height, width = diff.shape[:2]
    roi = np.zeros_like(diff, dtype=bool)
    roi[int(height * 0.18) : int(height * 0.82), int(width * 0.08) : int(width * 0.92)] = True
    max_channel = np.max(rgb, axis=-1)
    min_channel = np.min(rgb, axis=-1)
    mask = (
        (diff >= float(P5D3.P5D1A.SPHERE_BLOB_DIFF_THRESHOLD))
        & (max_channel >= int(P5D3.P5D1A.SPHERE_BLOB_MIN_RGB))
        & ((max_channel - min_channel) <= int(P5D3.P5D1A.SPHERE_BLOB_NEUTRAL_TOLERANCE))
        & roi
    )
    return np.where(mask, 255, 0).astype(np.uint8)


def _overlay_image(
    *,
    rgb_value: Any,
    sphere_blob: Dict[str, Any],
    local_blob: Dict[str, Any],
    range_summary: Dict[str, Any],
) -> Optional[np.ndarray]:
    if rgb_value is None:
        return None
    try:
        from PIL import Image, ImageDraw

        img = Image.fromarray(_rgb_image(rgb_value)).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        draw.rectangle(
            [int(width * 0.08), int(height * 0.18), int(width * 0.92), int(height * 0.82)],
            outline=(80, 160, 255),
            width=1,
        )
        for blob in sphere_blob.get("local_candidate_blobs", []) or []:
            x = int(blob.get("x", 0))
            y = int(blob.get("y", 0))
            w = int(blob.get("w", 0))
            h = int(blob.get("h", 0))
            draw.rectangle([x, y, x + w, y + h], outline=(255, 220, 0), width=2)
        best = local_blob.get("local_range_scaled_best_blob")
        if isinstance(best, dict):
            x = int(best.get("x", 0))
            y = int(best.get("y", 0))
            w = int(best.get("w", 0))
            h = int(best.get("h", 0))
            color = (0, 255, 0) if local_blob.get("local_range_scaled_blob_present") else (255, 80, 0)
            draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        hit_indices = set(range_summary.get("hit_beam_indices") or [])
        for index, yaw in enumerate(BRIDGE_FAN_YAW_DEGREES):
            x = int(width * (0.5 - float(yaw) / 70.0))
            color = (255, 60, 60) if index in hit_indices else (80, 80, 80)
            draw.line([x, height - 1, x, int(height * 0.86)], fill=color, width=1)
        return np.asarray(img)
    except Exception as exc:
        print("[WARN] overlay failed: {0}".format(exc))
        return None


def _capture_at(
    run: Dict[str, Any],
    step: int,
    tick_in_step: int,
    agent_name: str,
) -> Optional[Dict[str, Any]]:
    by_step = run.get("raw_captures_by_step_tick", {})
    step_dict = by_step.get(int(step), {})
    if not isinstance(step_dict, dict):
        return None
    tick_dict = step_dict.get(int(tick_in_step), {})
    if not isinstance(tick_dict, dict):
        return None
    return tick_dict.get(agent_name)


def _capture_at_event_sync(
    run: Dict[str, Any],
    event: Dict[str, Any],
    agent_name: str,
    *,
    sync_prefix: str,
) -> Optional[Dict[str, Any]]:
    step = event.get("{0}_step".format(sync_prefix))
    tick = event.get("{0}_tick".format(sync_prefix))
    if step is not None and tick is not None:
        capture = _capture_at(run, int(step), int(tick), agent_name)
        if capture is not None:
            return capture
    global_tick = event.get("{0}_global_tick".format(sync_prefix))
    if global_tick is None:
        return None
    by_step = run.get("raw_captures_by_step_tick", {})
    if not isinstance(by_step, dict):
        return None
    for step_dict in by_step.values():
        if not isinstance(step_dict, dict):
            continue
        for tick_dict in step_dict.values():
            if not isinstance(tick_dict, dict):
                continue
            capture = tick_dict.get(agent_name)
            if isinstance(capture, dict) and capture.get("tick_global") == global_tick:
                return capture
    return None


def _event_has_range_hit(event: Dict[str, Any]) -> bool:
    hits = event.get("rangefinder_hit_beam_indices")
    return isinstance(hits, list) and len(hits) > 0


def _selected_raw_frame_events(target_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for event in target_events:
        if _event_has_range_hit(event):
            selected.append(event)
    large_diff = sorted(
        target_events,
        key=lambda row: int(row.get("rgb_changed_pixels", 0) or 0),
        reverse=True,
    )
    selected.extend(large_diff[:4])
    local_candidates = sorted(
        [row for row in target_events if int(row.get("sphere_blob_local_candidate_count", 0) or 0) > 0],
        key=lambda row: (
            int(row.get("sphere_blob_local_candidate_count", 0) or 0),
            int(row.get("rgb_changed_pixels", 0) or 0),
        ),
        reverse=True,
    )
    selected.extend(local_candidates[:4])
    unique: List[Dict[str, Any]] = []
    seen = set()
    for event in selected:
        key = (event.get("policy_step"), event.get("tick_in_policy_step"), event.get("agent_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
        if len(unique) >= RAW_FRAME_MAX_EVENTS:
            break
    return unique


def _raw_frame_case_row(
    *,
    event: Dict[str, Any],
    target_run: Dict[str, Any],
    calibration_run: Dict[str, Any],
    save_visuals: bool = True,
) -> Dict[str, Any]:
    step = int(event.get("policy_step", 0))
    tick = int(event.get("tick_in_policy_step", 0))
    agent_name = str(event.get("agent_id"))
    target_capture = _capture_at(target_run, step, tick, agent_name)
    baseline_capture = _capture_reference_at(calibration_run, step, tick, agent_name)
    exact_baseline_capture = _capture_at(calibration_run, step, tick, agent_name)
    synced_target_capture = None
    synced_baseline_capture = None
    if event.get("rgb_range_sync_applied") is True:
        synced_target_capture = _capture_at_event_sync(
            target_run,
            event,
            agent_name,
            sync_prefix="rgb_sync_target",
        )
        synced_baseline_capture = _capture_at_event_sync(
            calibration_run,
            event,
            agent_name,
            sync_prefix="rgb_sync_baseline",
        )
    target_rgb = (
        synced_target_capture.get("rgb")
        if isinstance(synced_target_capture, dict) and synced_target_capture.get("rgb") is not None
        else (None if target_capture is None else target_capture.get("rgb"))
    )
    baseline_rgb = (
        synced_baseline_capture.get("rgb")
        if isinstance(synced_baseline_capture, dict) and synced_baseline_capture.get("rgb") is not None
        else (None if baseline_capture is None else baseline_capture.get("rgb"))
    )
    fan_range = None if target_capture is None else target_capture.get("fan_range")
    range_summary = P5D3.P5D1A._range_summary(fan_range)
    rgb_diff = P5D3.P5D1A._rgb_diff_signature(target_rgb, baseline_rgb)
    sphere_blob = P5D3.P5D1A._sphere_blob_signature(target_rgb, baseline_rgb)
    local_blob = _local_range_scaled_blob_signature(sphere_blob.get("local_candidate_blobs"), range_summary.get("raw"))
    base = os.path.join(
        PHASE_DIR,
        "visuals",
        "phase5d14_step{0:02d}_tick{1:03d}_{2}".format(step, tick, agent_name),
    )
    if save_visuals:
        visuals = {
            "target_rgb_preview_path": _save_image(base + "_target_rgb.png", target_rgb),
            "baseline_rgb_preview_path": _save_image(base + "_baseline_rgb.png", baseline_rgb),
            "diff_preview_path": _save_image(base + "_diff.png", _diff_image(target_rgb, baseline_rgb)),
            "white_neutral_mask_preview_path": _save_image(
                base + "_white_neutral_mask.png",
                _white_neutral_mask_image(target_rgb, baseline_rgb),
            ),
            "overlay_preview_path": _save_image(
                base + "_overlay.png",
                _overlay_image(
                    rgb_value=target_rgb,
                    sphere_blob=sphere_blob,
                    local_blob=local_blob,
                    range_summary=range_summary,
                ),
            ),
        }
    else:
        visuals = {
            "target_rgb_preview_path": None,
            "baseline_rgb_preview_path": None,
            "diff_preview_path": None,
            "white_neutral_mask_preview_path": None,
            "overlay_preview_path": None,
        }
    exact_rgb_diff = {}
    if exact_baseline_capture is not None:
        exact_rgb_diff = P5D3.P5D1A._rgb_diff_signature(target_rgb, exact_baseline_capture.get("rgb"))
    return {
        "run_kind": "target",
        "policy_step": step,
        "tick_in_policy_step": tick,
        "tick_global": int(event.get("tick_global", 0)),
        "agent_id": agent_name,
        "capture_phase": event.get("capture_phase"),
        "source_event_rgb_changed_pixels": int(event.get("rgb_changed_pixels", 0) or 0),
        "source_event_local_candidate_count": int(event.get("sphere_blob_local_candidate_count", 0) or 0),
        "source_event_rangefinder_hit_beam_indices": event.get("rangefinder_hit_beam_indices"),
        "source_event_rgb_range_sync_attempted": bool(event.get("rgb_range_sync_attempted", False)),
        "source_event_rgb_range_sync_applied": bool(event.get("rgb_range_sync_applied", False)),
        "source_event_rgb_sync_target_tick": event.get("rgb_sync_target_tick"),
        "source_event_rgb_sync_baseline_tick": event.get("rgb_sync_baseline_tick"),
        "source_event_rgb_sync_target_offset_ticks": event.get("rgb_sync_target_offset_ticks"),
        "source_event_rgb_sync_baseline_offset_ticks": event.get("rgb_sync_baseline_offset_ticks"),
        "source_event_rgb_sync_candidate_count": event.get("rgb_sync_candidate_count"),
        "source_event_rgb_sync_failure_reason": event.get("rgb_sync_failure_reason"),
        "target_capture_present": target_capture is not None,
        "baseline_capture_present": baseline_capture is not None,
        "exact_baseline_capture_present": exact_baseline_capture is not None,
        "exact_target_rgb_present": None if target_capture is None else target_capture.get("rgb") is not None,
        "exact_baseline_rgb_present": None if exact_baseline_capture is None else exact_baseline_capture.get("rgb") is not None,
        "synced_target_capture_present": synced_target_capture is not None,
        "synced_baseline_capture_present": synced_baseline_capture is not None,
        "synced_target_rgb_present": None if synced_target_capture is None else synced_target_capture.get("rgb") is not None,
        "synced_baseline_rgb_present": None if synced_baseline_capture is None else synced_baseline_capture.get("rgb") is not None,
        "target_rgb_present": target_rgb is not None,
        "baseline_rgb_present": baseline_rgb is not None,
        "target_observer_world_location": None if target_capture is None else target_capture.get("observer_world_location"),
        "baseline_observer_world_location": None if baseline_capture is None else baseline_capture.get("observer_world_location"),
        "target_observer_heading_deg": None if target_capture is None else target_capture.get("observer_heading_deg"),
        "baseline_observer_heading_deg": None if baseline_capture is None else baseline_capture.get("observer_heading_deg"),
        "target_vs_baseline_observer_distance_m": _distance_2d(
            None if target_capture is None else target_capture.get("observer_world_location"),
            None if baseline_capture is None else baseline_capture.get("observer_world_location"),
        ),
        "rgb_changed_pixels_recomputed": int(rgb_diff.get("changed_pixels", 0)),
        "rgb_change_bbox_xyxy_recomputed": rgb_diff.get("change_bbox_xyxy"),
        "exact_tick_rgb_changed_pixels": exact_rgb_diff.get("changed_pixels"),
        "sphere_blob_candidate_count_recomputed": int(sphere_blob.get("candidate_blob_count", 0)),
        "sphere_blob_local_candidate_count_recomputed": int(sphere_blob.get("local_candidate_blob_count", 0)),
        "sphere_blob_white_neutral_changed_pixels_recomputed": int(
            sphere_blob.get("white_neutral_changed_pixels", 0)
        ),
        "local_range_scaled_blob_present_recomputed": bool(local_blob.get("local_range_scaled_blob_present", False)),
        "local_blob_area_recomputed": int(local_blob.get("local_blob_area", 0) or 0),
        "local_blob_range_scaled_area_recomputed": local_blob.get("local_blob_range_scaled_area"),
        "matched_range_m_recomputed": local_blob.get("matched_range_m"),
        "matched_beam_index_recomputed": local_blob.get("matched_beam_index"),
        "rangefinder_hit_beam_indices_recomputed": range_summary.get("hit_beam_indices"),
        "rangefinder_min_positive_range_m_recomputed": range_summary.get("min_positive_range_m"),
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        **visuals,
    }


def _build_raw_frame_sync_diagnostic(
    *,
    calibration_run: Dict[str, Any],
    target_run: Dict[str, Any],
    save_visuals: bool = True,
) -> Dict[str, Any]:
    target_events = [row for row in target_run.get("event_rows", []) if row.get("run_kind") == "target"]
    selected = _selected_raw_frame_events(target_events)
    rows = [
        _raw_frame_case_row(
            event=event,
            target_run=target_run,
            calibration_run=calibration_run,
            save_visuals=save_visuals,
        )
        for event in selected
    ]
    range_hit_rows = [row for row in rows if row.get("source_event_rangefinder_hit_beam_indices")]
    source_zero_recomputed_positive = [
        row
        for row in rows
        if row.get("source_event_rangefinder_hit_beam_indices")
        and int(row.get("source_event_rgb_changed_pixels", 0) or 0) == 0
        and int(row.get("rgb_changed_pixels_recomputed", 0) or 0) > 0
    ]
    return {
        "phase_name": PHASE_NAME,
        "diagnostic_name": "phase5d14_raw_frame_baseline_sync_diagnostic",
        "diagnostic_audit_only": True,
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "target_agent_type": TARGET_AGENT_TYPE,
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "truth_used_for_detection": False,
        "actor_truth_used_for_detection": False,
        "target_truth_used_for_detection": False,
        "teammate_truth_used_for_detection": False,
        "case_count": len(rows),
        "range_hit_case_count": len(range_hit_rows),
        "source_zero_rgb_recomputed_positive_count": len(source_zero_recomputed_positive),
        "source_zero_rgb_recomputed_positive_ticks": [
            [row.get("policy_step"), row.get("tick_in_policy_step"), row.get("agent_id")]
            for row in source_zero_recomputed_positive
        ],
        "rows": rows,
    }


def _max_observed_detection_distance(events: List[Dict[str, Any]]) -> Optional[float]:
    values = [
        float(row.get("matched_range_m"))
        for row in events
        if row.get("accepted_candidate") is True and row.get("matched_range_m") is not None
    ]
    return max(values) if values else None


def _first_step(rows: List[Dict[str, Any]], predicate_key: str) -> Optional[int]:
    steps = [int(row.get("policy_step", 0)) for row in rows if row.get(predicate_key) is True]
    return min(steps) if steps else None


def _run_compile_log(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            os.path.join(PHASE_DIR, "scripts", "continuous_rolling_rgb_rf_sync_probe.py"),
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
    executable = holo_python if os.path.exists(holo_python) else sys.executable
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(
        [
            executable,
            "-m",
            "py_compile",
            os.path.join(PHASE_DIR, "scripts", "continuous_rolling_rgb_rf_sync_probe.py"),
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


def _build_summary(
    *,
    config: Dict[str, Any],
    calibration_run: Dict[str, Any],
    target_run: Dict[str, Any],
    teammate_run: Dict[str, Any],
    raw_frame_sync: Dict[str, Any],
    events: List[Dict[str, Any]],
    fusion_rows: List[Dict[str, Any]],
    adapter_rows: List[Dict[str, Any]],
    update_rows: List[Dict[str, Any]],
    policy_rows: List[Dict[str, Any]],
    tick_rows: List[Dict[str, Any]],
    started: float,
) -> Dict[str, Any]:
    target_events = [row for row in events if row.get("run_kind") == "target"]
    teammate_events = [row for row in events if row.get("run_kind") == "teammate_only"]
    target_fusion = [row for row in fusion_rows if row.get("run_kind") == "target"]
    teammate_fusion = [row for row in fusion_rows if row.get("run_kind") == "teammate_only"]
    target_updates = [row for row in update_rows if row.get("run_kind") == "target"]
    teammate_updates = [row for row in update_rows if row.get("run_kind") == "teammate_only"]
    teammate_false_positive_steps = [
        int(row.get("policy_step", 0))
        for row in teammate_fusion
        if row.get("shared_found_this_step") is True
    ]
    duplicate_steps = [
        int(row.get("policy_step", 0))
        for row in target_fusion
        if int(row.get("accepted_candidate_count", 0)) >= 2
        and int(row.get("fused_candidate_count", 0)) == 1
    ]
    dual_reporter_steps = [
        int(row.get("policy_step", 0))
        for row in target_fusion
        for candidate in row.get("fused_candidates", [])
        if len(set(candidate.get("reporter_usv_ids", []))) >= 2
    ]
    target_live_detection_success = any(row.get("shared_found_this_step") is True for row in target_fusion)
    mainline_found_mask_updated = any(row.get("new_found_indices") for row in target_updates)
    mainline_all_found_driven = bool(
        target_run.get("terminated_reason") == "all_found"
        and target_run.get("all_found") is True
        and any(row.get("all_found_after_update") is True for row in target_updates)
    )
    teammate_only_no_false_positive = bool(
        teammate_false_positive_steps == []
        and all(not any(bool(v) for v in row.get("detected_mask", [])) for row in teammate_updates)
    )
    rgb_sync_attempts = [row for row in events if row.get("rgb_range_sync_attempted") is True]
    rgb_sync_applied = [row for row in events if row.get("rgb_range_sync_applied") is True]
    target_rgb_sync_applied = [row for row in target_events if row.get("rgb_range_sync_applied") is True]
    target_accepted_from_rgb_sync = [
        row
        for row in target_events
        if row.get("accepted_candidate") is True and row.get("rgb_range_sync_applied") is True
    ]
    teammate_accepted_from_rgb_sync = [
        row
        for row in teammate_events
        if row.get("accepted_candidate") is True and row.get("rgb_range_sync_applied") is True
    ]
    rgb_sync_target_offsets = [
        int(row.get("rgb_sync_target_offset_ticks"))
        for row in rgb_sync_applied
        if row.get("rgb_sync_target_offset_ticks") is not None
    ]
    rgb_sync_baseline_offsets = [
        int(row.get("rgb_sync_baseline_offset_ticks"))
        for row in rgb_sync_applied
        if row.get("rgb_sync_baseline_offset_ticks") is not None
    ]
    phase_goal_completed = bool(
        target_live_detection_success
        and mainline_found_mask_updated
        and mainline_all_found_driven
        and teammate_only_no_false_positive
    )
    no_stop_scan_ticks = bool(
        sum(1 for row in tick_rows if row.get("post_arrival_stabilization_tick") is True) == 0
        and sum(1 for row in tick_rows if row.get("standoff_viewpoint_hold_tick") is True) == 0
        and sum(1 for row in tick_rows if row.get("post_arrival_scan_tick") is True) == 0
        and sum(1 for row in tick_rows if row.get("post_scan_recenter_tick") is True) == 0
    )
    phase_goal_completed = bool(phase_goal_completed and no_stop_scan_ticks)
    phase_status = (
        "live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed"
        if phase_goal_completed
        else "planner_live_callback_integrated_but_live_detection_all_found_not_closed"
    )
    return {
        "phase_name": PHASE_NAME,
        "phase_completed": phase_goal_completed,
        "phase_status": phase_status,
        "phase_goal": "live_holoocean_capture_drives_baseline_gp_planner_callback_found_mask_all_found",
        "phase_goal_completed": phase_goal_completed,
        "diagnostic_name": raw_frame_sync.get("diagnostic_name"),
        "diagnostic_audit_only": True,
        "raw_frame_sync_case_count": raw_frame_sync.get("case_count"),
        "raw_frame_sync_range_hit_case_count": raw_frame_sync.get("range_hit_case_count"),
        "raw_frame_sync_source_zero_rgb_recomputed_positive_count": raw_frame_sync.get(
            "source_zero_rgb_recomputed_positive_count"
        ),
        "raw_frame_sync_source_zero_rgb_recomputed_positive_ticks": raw_frame_sync.get(
            "source_zero_rgb_recomputed_positive_ticks"
        ),
        "source_5d6_audit_all_passed": config.get("source_5d6_audit_all_passed"),
        "source_5d7_audit_all_passed": config.get("source_5d7_audit_all_passed"),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "observer_count": 2,
        "observer_agent_names": list(OBSERVER_AGENT_NAMES),
        "observer_agent_type": TEAMMATE_AGENT_TYPE,
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "target_is_static": True,
        "dynamic_target_tracking_enabled": False,
        "non_sphere_like_target_expansion_enabled": False,
        "mainline_runtime_module": config.get("mainline_runtime_module"),
        "mainline_policy_name": MAINLINE_POLICY_NAME,
        "production_adapter_module": ReusableMainlinePerceptionAdapter.__module__,
        "production_adapter_class": "ReusableMainlinePerceptionAdapter",
        "live_planner_callback_integrated": True,
        "planned_path_source": "baseline_GP_mainline_planner",
        "preset_trajectory_used": False,
        "bridge_fan_rangefinder_sensor_count": len(BRIDGE_FAN_YAW_DEGREES),
        "bridge_fan_yaw_degrees": list(BRIDGE_FAN_YAW_DEGREES),
        "bridge_fan_geometry_role": config.get("bridge_fan_geometry_role"),
        "post_arrival_scan_enabled": bool(config.get("post_arrival_scan_enabled")),
        "no_stop_scan_enabled": True,
        "no_stop_scan_tick_audit_passed": no_stop_scan_ticks,
        "post_arrival_stabilization_tick_count": sum(
            1 for row in tick_rows if row.get("post_arrival_stabilization_tick") is True
        ),
        "standoff_viewpoint_hold_enabled": bool(config.get("standoff_viewpoint_hold_enabled")),
        "standoff_viewpoint_hold_ticks": config.get("standoff_viewpoint_hold_ticks"),
        "standoff_lookahead_segment_index": config.get("standoff_lookahead_segment_index"),
        "standoff_turn_force": config.get("standoff_turn_force"),
        "standoff_heading_tolerance_deg": config.get("standoff_heading_tolerance_deg"),
        "standoff_viewpoint_anchor_source": config.get("standoff_viewpoint_anchor_source"),
        "standoff_viewpoint_role": config.get("standoff_viewpoint_role"),
        "standoff_viewpoint_hold_tick_count": sum(
            1 for row in tick_rows if row.get("standoff_viewpoint_hold_tick") is True
        ),
        "target_standoff_viewpoint_hold_tick_count": sum(
            1
            for row in tick_rows
            if row.get("run_kind") == "target" and row.get("standoff_viewpoint_hold_tick") is True
        ),
        "teammate_standoff_viewpoint_hold_tick_count": sum(
            1
            for row in tick_rows
            if row.get("run_kind") == "teammate_only" and row.get("standoff_viewpoint_hold_tick") is True
        ),
        "target_accepted_candidate_from_standoff_viewpoint_hold": any(
            row.get("accepted_candidate") is True and row.get("standoff_viewpoint_hold_tick") is True
            for row in target_events
        ),
        "post_arrival_scan_ticks": config.get("post_arrival_scan_ticks"),
        "post_scan_recenter_ticks": config.get("post_scan_recenter_ticks"),
        "scan_turn_force": config.get("scan_turn_force"),
        "scan_capture_role": config.get("post_arrival_scan_role"),
        "scan_tick_count": sum(1 for row in tick_rows if row.get("post_arrival_scan_tick") is True),
        "post_scan_recenter_tick_count": sum(1 for row in tick_rows if row.get("post_scan_recenter_tick") is True),
        "target_scan_tick_count": sum(
            1 for row in tick_rows if row.get("run_kind") == "target" and row.get("post_arrival_scan_tick") is True
        ),
        "teammate_scan_tick_count": sum(
            1 for row in tick_rows if row.get("run_kind") == "teammate_only" and row.get("post_arrival_scan_tick") is True
        ),
        "target_accepted_candidate_from_scan": any(
            row.get("accepted_candidate") is True and row.get("post_arrival_scan_tick") is True
            for row in target_events
        ),
        "target_accepted_candidate_from_transit": any(
            row.get("accepted_candidate") is True and row.get("capture_phase") == "transit"
            for row in target_events
        ),
        "planner_callback_step_count": len([row for row in policy_rows if row.get("planner_callback_called") is True]),
        "planner_callback_functions_called": list(config.get("mainline_planner_callback_functions", [])),
        "live_capture_provider_enabled": True,
        "live_capture_primary_detection_source": True,
        "rgb_range_sync_fix_enabled": True,
        "rgb_range_sync_strategy": RGB_SYNC_STRATEGY,
        "rgb_sync_window_ticks": RGB_SYNC_WINDOW_TICKS,
        "rgb_sync_max_pose_drift_m": RGB_SYNC_MAX_POSE_DRIFT_M,
        "rgb_sync_attempt_count": len(rgb_sync_attempts),
        "rgb_sync_applied_count": len(rgb_sync_applied),
        "target_rgb_sync_applied_count": len(target_rgb_sync_applied),
        "target_accepted_candidate_from_rgb_sync_count": len(target_accepted_from_rgb_sync),
        "target_accepted_candidate_from_rgb_sync_steps": sorted(
            set(int(row.get("policy_step", 0)) for row in target_accepted_from_rgb_sync)
        ),
        "teammate_accepted_candidate_from_rgb_sync_count": len(teammate_accepted_from_rgb_sync),
        "rgb_sync_target_offset_ticks": rgb_sync_target_offsets,
        "rgb_sync_baseline_offset_ticks": rgb_sync_baseline_offsets,
        "rgb_sync_max_abs_target_offset_ticks": (
            max(abs(v) for v in rgb_sync_target_offsets) if rgb_sync_target_offsets else None
        ),
        "rgb_sync_max_abs_baseline_offset_ticks": (
            max(abs(v) for v in rgb_sync_baseline_offsets) if rgb_sync_baseline_offsets else None
        ),
        "replay_events_used_for_detection": False,
        "phase5d3_json_events_used_for_detection": False,
        "live_calibration_reference_used": True,
        "live_calibration_reference_role": config.get("live_calibration_reference_role"),
        "orientation_sensor_used_for_world_projection": True,
        "all_runs_launch_ok": bool(
            calibration_run.get("launch_ok") and target_run.get("launch_ok") and teammate_run.get("launch_ok")
        ),
        "run_errors": {
            "calibration": calibration_run.get("error", ""),
            "target": target_run.get("error", ""),
            "teammate_only": teammate_run.get("error", ""),
        },
        "target_initial_grid_cell": target_run.get("initial_target_cell"),
        "target_world_location": target_run.get("target_world_location"),
        "target_terminated_reason": target_run.get("terminated_reason"),
        "target_completed_steps": target_run.get("completed_steps"),
        "target_success_all_found": target_run.get("all_found"),
        "target_all_found_step": target_run.get("all_found_step"),
        "target_find_times": target_run.get("find_times_final"),
        "target_live_detection_success": target_live_detection_success,
        "target_first_live_detection_step": _first_step(target_events, "accepted_candidate"),
        "target_first_shared_found_step": _first_step(target_fusion, "shared_found_this_step"),
        "teammate_only_terminated_reason": teammate_run.get("terminated_reason"),
        "teammate_only_completed_steps": teammate_run.get("completed_steps"),
        "teammate_only_success_all_found": teammate_run.get("all_found"),
        "teammate_only_find_times": teammate_run.get("find_times_final"),
        "teammate_false_positive_steps": teammate_false_positive_steps,
        "teammate_only_false_positive_count": len(teammate_false_positive_steps),
        "teammate_events_accepted_count": sum(1 for row in teammate_events if row.get("accepted_candidate") is True),
        "event_count": len(events),
        "target_event_count": len(target_events),
        "teammate_event_count": len(teammate_events),
        "fusion_trace_count": len(fusion_rows),
        "adapter_trace_count": len(adapter_rows),
        "mainline_update_trace_count": len(update_rows),
        "policy_trace_count": len(policy_rows),
        "tick_trace_count": len(tick_rows),
        "mainline_update_found_mask_called": all(row.get("update_found_mask_original_called") is True for row in update_rows),
        "mainline_update_found_mask_called_count": len(update_rows),
        "mainline_found_mask_updated_from_live_adapter": mainline_found_mask_updated,
        "mainline_all_found_driven_by_live_adapter": mainline_all_found_driven,
        "teammate_only_no_false_positive": teammate_only_no_false_positive,
        "duplicate_observation_fused": bool(duplicate_steps),
        "duplicate_observation_fused_steps": duplicate_steps,
        "dual_reporter_fused_steps": sorted(set(dual_reporter_steps)),
        "candidate_fusion_called": all(row.get("candidate_fusion_called") is True for row in fusion_rows),
        "max_reliable_detection_distance_observed_m": _max_observed_detection_distance(target_events),
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "min_inter_vessel_distance_m": min(
            float(calibration_run.get("min_inter_vessel_distance_m", 0.0) or 0.0),
            float(target_run.get("min_inter_vessel_distance_m", 0.0) or 0.0),
            float(teammate_run.get("min_inter_vessel_distance_m", 0.0) or 0.0),
        ),
        "truth_flags_false": _truth_flags_false(events)
        and _truth_flags_false(fusion_rows)
        and _truth_flags_false(adapter_rows)
        and _truth_flags_false(update_rows)
        and _truth_flags_false(policy_rows),
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
        "# Phase 5D-14 Continuous Rolling RGB/RF Sync Summary",
        "",
        "- Mainline Policy: `{0}`".format(summary.get("mainline_policy_name")),
        "- Production Adapter Module: `{0}`".format(summary.get("production_adapter_module")),
        "- Live Planner Callback Integrated: `{0}`".format(summary.get("live_planner_callback_integrated")),
        "- RGB/RF Sync Fix Enabled: `{0}`".format(summary.get("rgb_range_sync_fix_enabled")),
        "- RGB/RF Sync Strategy: `{0}`".format(summary.get("rgb_range_sync_strategy")),
        "- RGB Sync Window Ticks: `{0}`".format(summary.get("rgb_sync_window_ticks")),
        "- RGB Sync Applied Count: `{0}`".format(summary.get("rgb_sync_applied_count")),
        "- Target Accepted Candidate From RGB Sync Count: `{0}`".format(
            summary.get("target_accepted_candidate_from_rgb_sync_count")
        ),
        "- Diagnostic Audit Only: `{0}`".format(summary.get("diagnostic_audit_only")),
        "- Raw Frame Sync Case Count: `{0}`".format(summary.get("raw_frame_sync_case_count")),
        "- Raw Frame Sync Range-Hit Case Count: `{0}`".format(summary.get("raw_frame_sync_range_hit_case_count")),
        "- Source-Zero RGB Recomputed-Positive Count: `{0}`".format(
            summary.get("raw_frame_sync_source_zero_rgb_recomputed_positive_count")
        ),
        "- Planned Path Source: `{0}`".format(summary.get("planned_path_source")),
        "- Preset Trajectory Used: `{0}`".format(summary.get("preset_trajectory_used")),
        "- Bridge Fan RangeFinder Sensor Count: `{0}`".format(
            summary.get("bridge_fan_rangefinder_sensor_count")
        ),
        "- Standoff Viewpoint Hold Enabled: `{0}`".format(summary.get("standoff_viewpoint_hold_enabled")),
        "- Target Accepted Candidate From Standoff Hold: `{0}`".format(
            summary.get("target_accepted_candidate_from_standoff_viewpoint_hold")
        ),
        "- Post Arrival Scan Enabled: `{0}`".format(summary.get("post_arrival_scan_enabled")),
        "- Target Accepted Candidate From Scan: `{0}`".format(summary.get("target_accepted_candidate_from_scan")),
        "- Phase Status: `{0}`".format(summary.get("phase_status")),
        "- Phase Goal Completed: `{0}`".format(summary.get("phase_goal_completed")),
        "- Target Initial Grid Cell: `{0}`".format(summary.get("target_initial_grid_cell")),
        "- Target Terminated Reason: `{0}`".format(summary.get("target_terminated_reason")),
        "- Target All Found Step: `{0}`".format(summary.get("target_all_found_step")),
        "- Target Live Detection Success: `{0}`".format(summary.get("target_live_detection_success")),
        "- Mainline Found Mask Updated From Live Adapter: `{0}`".format(
            summary.get("mainline_found_mask_updated_from_live_adapter")
        ),
        "- Mainline All Found Driven By Live Adapter: `{0}`".format(
            summary.get("mainline_all_found_driven_by_live_adapter")
        ),
        "- Teammate False Positive Steps: `{0}`".format(summary.get("teammate_false_positive_steps")),
        "- Update Found Mask Calls: `{0}`".format(summary.get("mainline_update_found_mask_called_count")),
        "- Max Observed Detection Distance: `{0}`".format(summary.get("max_reliable_detection_distance_observed_m")),
        "",
        (
            "Phase 5D-14 closed the static SphereAgent live search chain without post-arrival stop-scan; rely on the separate audit before treating this as final evidence."
            if summary.get("phase_goal_completed") is True
            else "Phase 5D-14 exercises the real planner callback and continuous HoloOcean capture path without post-arrival stop-scan. If it does not close all_found, proceed to the 5D-15 sensor coverage fallback."
        ),
        "",
    ]
    return "\n".join(lines)


def run_live_planner_callback_search(
    *,
    display_live: bool = False,
    display_fps: float = DEFAULT_DISPLAY_FPS,
    display_every_ticks: int = DEFAULT_DISPLAY_EVERY_TICKS,
    save_visuals: bool = True,
) -> Dict[str, Any]:
    os.makedirs(os.path.join(PHASE_DIR, "manifests"), exist_ok=True)
    os.makedirs(os.path.join(PHASE_DIR, "reports"), exist_ok=True)
    os.makedirs(os.path.join(PHASE_DIR, "logs"), exist_ok=True)
    started = time.perf_counter()
    pre_status = _run_git_status()
    config = _phase_config(pre_status)

    print("Running 5D-14 live calibration/reference planner callback run")
    calibration_run = _run_live_case(
        run_kind="calibration",
        config=config,
        calibration_reference=None,
        detection_enabled=False,
    )
    print("Running 5D-14 live target planner callback run")
    target_run = _run_live_case(
        run_kind="target",
        config=config,
        calibration_reference=calibration_run,
        detection_enabled=True,
        display_live=display_live,
        display_fps=display_fps,
        display_every_ticks=display_every_ticks,
    )
    print("Running 5D-14 live teammate-only planner callback run")
    teammate_run = _run_live_case(
        run_kind="teammate_only",
        config=config,
        calibration_reference=calibration_run,
        detection_enabled=True,
    )

    raw_frame_sync = _build_raw_frame_sync_diagnostic(
        calibration_run=calibration_run,
        target_run=target_run,
        save_visuals=save_visuals,
    )

    all_events = list(target_run.get("event_rows", [])) + list(teammate_run.get("event_rows", []))
    all_fusion = list(target_run.get("fusion_rows", [])) + list(teammate_run.get("fusion_rows", []))
    all_adapter = list(target_run.get("adapter_rows", [])) + list(teammate_run.get("adapter_rows", []))
    all_updates = list(target_run.get("update_rows", [])) + list(teammate_run.get("update_rows", []))
    all_policy = (
        list(calibration_run.get("policy_trace", []))
        + list(target_run.get("policy_trace", []))
        + list(teammate_run.get("policy_trace", []))
    )
    all_ticks = (
        list(calibration_run.get("tick_trace", []))
        + list(target_run.get("tick_trace", []))
        + list(teammate_run.get("tick_trace", []))
    )
    summary = _build_summary(
        config=config,
        calibration_run=calibration_run,
        target_run=target_run,
        teammate_run=teammate_run,
        raw_frame_sync=raw_frame_sync,
        events=all_events,
        fusion_rows=all_fusion,
        adapter_rows=all_adapter,
        update_rows=all_updates,
        policy_rows=all_policy,
        tick_rows=all_ticks,
        started=started,
    )

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
        "post_status": _run_git_status(),
        "outside_phase_new_or_changed": _outside_phase_new_or_changed(pre_status, _run_git_status()),
        "protected_core_path_status": _run_git_status(protected_core_paths),
    }

    _run_compile_log(BASE_COMPILE_LOG)
    _run_holo_compile_log(HOLO_COMPILE_LOG)

    _save_json(CONFIG_JSON, config)
    _save_json(PRODUCTION_CONTRACT_JSON, mainline_perception_adapter_contract())
    _save_json(CALIBRATION_RUN_JSON, _strip_run_raw(calibration_run))
    _save_json(TARGET_RUN_JSON, _strip_run_raw(target_run))
    _save_json(TEAMMATE_RUN_JSON, _strip_run_raw(teammate_run))
    _save_json(TICK_TRACE_JSON, all_ticks)
    _save_csv(TICK_TRACE_CSV, all_ticks)
    _save_json(POLICY_TRACE_JSON, all_policy)
    _save_csv(POLICY_TRACE_CSV, all_policy)
    _save_json(EVENTS_JSON, all_events)
    _save_csv(EVENTS_CSV, all_events)
    _save_json(FUSION_JSON, all_fusion)
    _save_csv(FUSION_CSV, all_fusion)
    _save_json(ADAPTER_TRACE_JSON, all_adapter)
    _save_csv(ADAPTER_TRACE_CSV, all_adapter)
    _save_json(MAINLINE_UPDATE_TRACE_JSON, all_updates)
    _save_csv(MAINLINE_UPDATE_TRACE_CSV, all_updates)
    _save_json(RAW_FRAME_SYNC_JSON, raw_frame_sync)
    _save_csv(RAW_FRAME_SYNC_CSV, list(raw_frame_sync.get("rows", [])))
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
    parser.add_argument(
        "--display-live",
        action="store_true",
        help="Show a live top-down dual-USV search window during the target run. No frames or videos are saved.",
    )
    parser.add_argument("--display-fps", type=float, default=DEFAULT_DISPLAY_FPS)
    parser.add_argument("--display-every-ticks", type=int, default=DEFAULT_DISPLAY_EVERY_TICKS)
    parser.add_argument(
        "--no-save-visuals",
        action="store_true",
        help="Do not write diagnostic PNG previews. This does not affect JSON/CSV audit artifacts.",
    )
    args = parser.parse_args()
    if args.mode == "live":
        summary = run_live_planner_callback_search(
            display_live=args.display_live,
            display_fps=args.display_fps,
            display_every_ticks=args.display_every_ticks,
            save_visuals=not (args.no_save_visuals or args.display_live),
        )
        print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()







