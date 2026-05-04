"""
Helpers for switch penalties based on movement direction.
"""

from __future__ import annotations


def move_direction(
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[int, int]:
    return (int(end[0]) - int(start[0]), int(end[1]) - int(start[1]))


def first_path_move_dir(
    path: list[tuple[int, int]] | tuple[tuple[int, int], ...] | None,
) -> tuple[int, int] | None:
    if path is None or len(path) < 2:
        return None
    return move_direction(path[0], path[1])


def is_u_turn(
    prev_move_dir: tuple[int, int] | None,
    next_move_dir: tuple[int, int] | None,
) -> bool:
    if prev_move_dir is None or next_move_dir is None:
        return False
    prev = (int(prev_move_dir[0]), int(prev_move_dir[1]))
    nxt = (int(next_move_dir[0]), int(next_move_dir[1]))
    if prev == (0, 0) or nxt == (0, 0):
        return False
    return nxt == (-prev[0], -prev[1])


def u_turn_penalty_for_path(
    path: list[tuple[int, int]] | tuple[tuple[int, int], ...] | None,
    prev_move_dir: tuple[int, int] | None,
    lambda_u_turn: float = 0.0,
) -> tuple[float, bool, tuple[int, int] | None]:
    first_move_dir = first_path_move_dir(path)
    applied = is_u_turn(prev_move_dir, first_move_dir)
    penalty = float(lambda_u_turn) if applied else 0.0
    return penalty, applied, first_move_dir
