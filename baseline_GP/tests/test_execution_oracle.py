from __future__ import annotations

import numpy as np

from baseline_GP.core_execution import execute_next_step
from baseline_GP.core_map import FREE, OCCUPIED, UNKNOWN, reveal_cells


def test_execute_next_step_does_not_prewrite_hidden_obstacle() -> None:
    true_map = np.array(
        [
            [FREE, FREE, FREE],
            [FREE, OCCUPIED, FREE],
            [FREE, FREE, FREE],
        ],
        dtype=np.int8,
    )
    known_map = np.full((3, 3), UNKNOWN, dtype=np.int8)
    known_map[(1, 0)] = FREE
    known_map[(1, 1)] = UNKNOWN
    robot_pos = (1, 0)
    path = [robot_pos, (1, 1)]

    result = execute_next_step(true_map, known_map, robot_pos, path)

    assert not result.move_success
    assert result.collision
    assert result.collision_cell == (1, 1)
    assert result.new_robot_pos == robot_pos
    assert known_map[(1, 1)] == UNKNOWN


def test_execute_next_step_blocks_known_obstacle_without_collision_event() -> None:
    true_map = np.array(
        [
            [FREE, FREE, FREE],
            [FREE, OCCUPIED, FREE],
            [FREE, FREE, FREE],
        ],
        dtype=np.int8,
    )
    known_map = np.full((3, 3), UNKNOWN, dtype=np.int8)
    known_map[(1, 0)] = FREE
    known_map[(1, 1)] = OCCUPIED
    robot_pos = (1, 0)
    path = [robot_pos, (1, 1)]

    result = execute_next_step(true_map, known_map, robot_pos, path)

    assert not result.move_success
    assert not result.collision
    assert result.collision_cell is None
    assert result.new_robot_pos == robot_pos


def test_execute_next_step_moves_into_free_cell() -> None:
    true_map = np.array(
        [
            [FREE, FREE, FREE],
            [FREE, FREE, FREE],
            [FREE, FREE, FREE],
        ],
        dtype=np.int8,
    )
    known_map = np.full((3, 3), UNKNOWN, dtype=np.int8)
    known_map[(1, 0)] = FREE
    known_map[(1, 1)] = UNKNOWN
    robot_pos = (1, 0)
    path = [robot_pos, (1, 1)]

    result = execute_next_step(true_map, known_map, robot_pos, path)

    assert result.move_success
    assert not result.collision
    assert result.collision_cell is None
    assert result.new_robot_pos == (1, 1)


def test_collision_cell_is_only_revealed_after_reveal_cells() -> None:
    true_map = np.array(
        [
            [FREE, FREE, FREE],
            [FREE, OCCUPIED, FREE],
            [FREE, FREE, FREE],
        ],
        dtype=np.int8,
    )
    known_map = np.full((3, 3), UNKNOWN, dtype=np.int8)
    known_map[(1, 0)] = FREE
    robot_pos = (1, 0)
    path = [robot_pos, (1, 1)]

    result = execute_next_step(true_map, known_map, robot_pos, path)

    assert result.collision
    assert known_map[(1, 1)] == UNKNOWN

    reveal_cells(true_map, known_map, robot_pos, sensor_range=1)

    assert known_map[(1, 1)] == OCCUPIED
