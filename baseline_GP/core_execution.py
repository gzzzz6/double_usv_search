"""
Execution-step helpers for single-step motion under partial observability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from .core_map import OCCUPIED
except ImportError:
    from core_map import OCCUPIED


@dataclass(frozen=True)
class ExecutionStepResult:
    move_success: bool
    collision: bool
    collision_cell: tuple[int, int] | None
    new_robot_pos: tuple[int, int]


def execute_next_step(
    true_map: np.ndarray,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    path: list[tuple[int, int]],
) -> ExecutionStepResult:
    """Advance one step if feasible under planner-visible map knowledge and world physics.

    This helper intentionally stays generic so both baselines can use the same
    execution boundary:
    - legacy unknown-map search may still encounter hidden static obstacles
    - known-static-map search can pass its static navigation prior as `known_map`
      and use this function as a uniform planner/simulator interface

    The planner/execution layer may invalidate a step early only when the next
    cell is already blocked in `known_map`. Any mismatch against `true_map`
    remains a simulator-side collision event.
    """

    if len(path) <= 1:
        return ExecutionStepResult(
            move_success=False,
            collision=False,
            collision_cell=None,
            new_robot_pos=robot_pos,
        )

    next_step = tuple(path[1])
    if known_map[next_step] == OCCUPIED:
        return ExecutionStepResult(
            move_success=False,
            collision=False,
            collision_cell=None,
            new_robot_pos=robot_pos,
        )

    if true_map[next_step] == OCCUPIED:
        return ExecutionStepResult(
            move_success=False,
            collision=True,
            collision_cell=next_step,
            new_robot_pos=robot_pos,
        )

    return ExecutionStepResult(
        move_success=True,
        collision=False,
        collision_cell=None,
        new_robot_pos=next_step,
    )
