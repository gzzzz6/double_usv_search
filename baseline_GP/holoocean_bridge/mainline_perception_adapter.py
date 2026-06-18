"""Adapter from HoloOcean perception evidence to baseline_GP mainline masks.

This module contains only the reusable conversion API. It does not call
HoloOcean, read target truth, or modify baseline_GP search decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


RECOMMENDED_RULE_ID = "sphere_blob_local_range_scaled_any_hit"
TARGET_AGENT_TYPE = "SphereAgent"
TEAMMATE_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_TYPE = "SurfaceVessel"
OBSERVER_AGENT_NAMES = ["sv0", "sv1"]
RELIABLE_DISTANCE_LIMIT_M = 35.0


def _candidate_position(candidate: Dict[str, Any]) -> Optional[List[float]]:
    position = candidate.get("fused_world_position")
    if isinstance(position, list) and len(position) >= 2:
        return [
            float(position[0]),
            float(position[1]),
            float(position[2]) if len(position) > 2 else 0.0,
        ]
    positions = candidate.get("positions")
    if isinstance(positions, list) and positions:
        arr = np.asarray(positions, dtype=float)
        if arr.ndim == 2 and arr.shape[1] >= 2:
            mean = arr.mean(axis=0)
            return [
                float(mean[0]),
                float(mean[1]),
                float(mean[2]) if mean.shape[0] > 2 else 0.0,
            ]
    return None


@dataclass
class MainlineAdapterStepInput:
    """Input contract for one adapter step."""

    run_kind: str
    step_index: int
    target_count: int
    found_mask_before: List[bool]
    per_agent_events: List[Dict[str, Any]]
    candidate_fusion_result: Dict[str, Any]
    known_teammates: List[Dict[str, Any]] = field(default_factory=list)
    force_detect: Optional[bool] = None


@dataclass
class MainlineAdapterStepOutput:
    """Output contract consumed by baseline_GP mainline detection/update paths."""

    run_kind: str
    step_index: int
    detected_mask: List[bool]
    shared_found: bool
    accepted_candidate_count: int
    fused_candidate_count: int
    fused_candidates: List[Dict[str, Any]]
    new_found_candidate_count: int
    found_update_trace: Dict[str, Any]
    truth_used_for_detection: bool = False
    actor_truth_used_for_detection: bool = False
    target_truth_used_for_detection: bool = False
    teammate_truth_used_for_detection: bool = False

    def asdict(self) -> Dict[str, Any]:
        return {
            "run_kind": self.run_kind,
            "step_index": int(self.step_index),
            "detected_mask": list(self.detected_mask),
            "shared_found": bool(self.shared_found),
            "accepted_candidate_count": int(self.accepted_candidate_count),
            "fused_candidate_count": int(self.fused_candidate_count),
            "fused_candidates": self.fused_candidates,
            "new_found_candidate_count": int(self.new_found_candidate_count),
            "found_update_trace": dict(self.found_update_trace),
            "truth_used_for_detection": bool(self.truth_used_for_detection),
            "actor_truth_used_for_detection": bool(self.actor_truth_used_for_detection),
            "target_truth_used_for_detection": bool(self.target_truth_used_for_detection),
            "teammate_truth_used_for_detection": bool(self.teammate_truth_used_for_detection),
        }


class ReusableMainlinePerceptionAdapter:
    """Reusable adapter from fused HoloOcean perception evidence to mainline masks."""

    def __init__(
        self,
        *,
        adapter_id: str,
        recommended_rule_id: str = RECOMMENDED_RULE_ID,
        reliable_distance_limit_m: float = RELIABLE_DISTANCE_LIMIT_M,
    ) -> None:
        self.adapter_id = str(adapter_id)
        self.recommended_rule_id = str(recommended_rule_id)
        self.reliable_distance_limit_m = float(reliable_distance_limit_m)
        self.episode_id: Optional[str] = None
        self.outputs_by_step: Dict[int, MainlineAdapterStepOutput] = {}
        self.output_trace: List[Dict[str, Any]] = []

    def reset_episode(self, episode_id: str) -> None:
        self.episode_id = str(episode_id)
        self.outputs_by_step = {}
        self.output_trace = []

    def observe_step(self, step_input: MainlineAdapterStepInput) -> MainlineAdapterStepOutput:
        fusion = step_input.candidate_fusion_result
        fused_candidates = (
            list(fusion.get("fused_candidates", []))
            if isinstance(fusion.get("fused_candidates"), list)
            else []
        )
        accepted_candidate_count = int(fusion.get("accepted_candidate_count", 0) or 0)
        fused_candidate_count = int(fusion.get("fused_candidate_count", len(fused_candidates)) or 0)
        source_shared_found = bool(fusion.get("shared_found_this_step") is True)
        found_before = [bool(value) for value in step_input.found_mask_before]
        should_detect = source_shared_found and any(not value for value in found_before)
        if step_input.force_detect is not None:
            should_detect = bool(step_input.force_detect)

        detected_mask = [False for _ in range(int(step_input.target_count))]
        if should_detect and detected_mask:
            detected_mask[0] = True
        new_found_candidate_count = 1 if any(detected_mask) else 0
        candidate_position = _candidate_position(fused_candidates[0]) if fused_candidates else None
        output = MainlineAdapterStepOutput(
            run_kind=step_input.run_kind,
            step_index=int(step_input.step_index),
            detected_mask=detected_mask,
            shared_found=bool(any(detected_mask)),
            accepted_candidate_count=accepted_candidate_count,
            fused_candidate_count=fused_candidate_count,
            fused_candidates=fused_candidates,
            new_found_candidate_count=new_found_candidate_count,
            found_update_trace={
                "adapter_id": self.adapter_id,
                "episode_id": self.episode_id,
                "recommended_rule_id": self.recommended_rule_id,
                "source_policy_step": int(
                    fusion.get("policy_step", step_input.step_index) or step_input.step_index
                ),
                "source_shared_found": source_shared_found,
                "source_raw_sensor_detection_count": int(
                    fusion.get("raw_sensor_detection_count", 0) or 0
                ),
                "source_accepted_candidate_count": accepted_candidate_count,
                "source_fused_candidate_count": fused_candidate_count,
                "source_teammate_rejected_count": int(fusion.get("teammate_rejected_count", 0) or 0),
                "source_per_agent_event_count": len(step_input.per_agent_events),
                "source_accepted_event_count": sum(
                    1 for event in step_input.per_agent_events if event.get("accepted_candidate") is True
                ),
                "source_fused_world_position_first_cluster": candidate_position,
                "source_reporter_usv_ids_first_cluster": (
                    fused_candidates[0].get("reporter_usv_ids", []) if fused_candidates else []
                ),
                "known_teammate_count": len(step_input.known_teammates),
                "found_mask_before_adapter": found_before,
                "detected_mask_from_adapter": detected_mask,
                "truth_used_for_detection": False,
                "actor_truth_used_for_detection": False,
                "target_truth_used_for_detection": False,
                "teammate_truth_used_for_detection": False,
                "detection_source": "holoocean_sensor_event_candidate_fusion",
            },
        )
        self.outputs_by_step[int(step_input.step_index)] = output
        self.output_trace.append(output.asdict())
        return output

    def build_detected_mask(self, step_index: int, target_count: int) -> np.ndarray:
        output = self.outputs_by_step.get(int(step_index))
        if output is None:
            return np.zeros(int(target_count), dtype=bool)
        mask = np.asarray(output.detected_mask, dtype=bool)
        if mask.size == int(target_count):
            return mask
        resized = np.zeros(int(target_count), dtype=bool)
        limit = min(resized.size, mask.size)
        resized[:limit] = mask[:limit]
        return resized

    def fusion_trace(self) -> List[Dict[str, Any]]:
        return list(self.output_trace)


def mainline_perception_adapter_contract() -> Dict[str, Any]:
    """Return the stable API contract for audit and integration checks."""

    return {
        "module": "baseline_GP.holoocean_bridge.mainline_perception_adapter",
        "adapter_class": "ReusableMainlinePerceptionAdapter",
        "input_dataclass": "MainlineAdapterStepInput",
        "output_dataclass": "MainlineAdapterStepOutput",
        "methods": [
            {
                "name": "reset_episode",
                "inputs": ["episode_id"],
                "outputs": [],
                "semantic": "clear per-episode adapter state",
            },
            {
                "name": "observe_step",
                "inputs": [
                    "run_kind",
                    "step_index",
                    "target_count",
                    "found_mask_before",
                    "per_agent_events",
                    "candidate_fusion_result",
                    "known_teammates",
                    "force_detect",
                ],
                "outputs": ["MainlineAdapterStepOutput"],
                "semantic": "convert per-agent events and fusion result into mainline detected_mask/shared_found fields",
            },
            {
                "name": "build_detected_mask",
                "inputs": ["step_index", "target_count"],
                "outputs": ["np.ndarray[bool]"],
                "semantic": "return the detected_mask expected by baseline_GP mainline detect_targets",
            },
            {
                "name": "fusion_trace",
                "inputs": [],
                "outputs": ["list[dict]"],
                "semantic": "return adapter output trace for audit",
            },
        ],
        "adapter_input_fields": [
            "per_agent_events",
            "candidate_fusion_result",
            "step_index",
            "target_count",
            "found_mask_before",
            "known_teammates",
        ],
        "adapter_output_fields": [
            "detected_mask",
            "shared_found",
            "new_found_candidate_count",
            "found_update_trace",
            "truth_used_for_detection",
        ],
        "truth_policy": "truth is audit-only and is not an adapter input needed for detection",
        "target_agent_type": TARGET_AGENT_TYPE,
        "teammate_agent_type": TEAMMATE_AGENT_TYPE,
        "observer_agent_type": OBSERVER_AGENT_TYPE,
        "observer_agent_names": list(OBSERVER_AGENT_NAMES),
        "recommended_rule_id": RECOMMENDED_RULE_ID,
        "reliable_distance_limit_m": RELIABLE_DISTANCE_LIMIT_M,
        "production_module_created": True,
        "phase_local_only": False,
    }


__all__ = [
    "MainlineAdapterStepInput",
    "MainlineAdapterStepOutput",
    "OBSERVER_AGENT_NAMES",
    "OBSERVER_AGENT_TYPE",
    "RECOMMENDED_RULE_ID",
    "RELIABLE_DISTANCE_LIMIT_M",
    "ReusableMainlinePerceptionAdapter",
    "TARGET_AGENT_TYPE",
    "TEAMMATE_AGENT_TYPE",
    "mainline_perception_adapter_contract",
]
