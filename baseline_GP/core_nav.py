"""
Current-only grid navigation helpers for the known-map search mainline.
"""

from __future__ import annotations

import heapq

try:
    from .core_map import FREE, OCCUPIED, neighbors4
except ImportError:
    from core_map import FREE, OCCUPIED, neighbors4


def heuristic(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def a_star(
    known_map,
    start: tuple[int, int],
    goal: tuple[int, int],
):
    if known_map[start] != FREE or known_map[goal] != FREE:
        return None
    open_heap = []
    heapq.heappush(open_heap, (0, start))
    came_from = {}
    g_score = {start: 0}
    closed = set()
    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        for nb in neighbors4(current, known_map):
            if known_map[nb] != FREE:
                continue
            tentative_g = g_score[current] + 1
            if tentative_g < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative_g
                f = tentative_g + heuristic(nb, goal)
                heapq.heappush(open_heap, (f, nb))
    return None


def a_star_nav(
    known_map,
    start: tuple[int, int],
    goal: tuple[int, int],
    unknown_cost: int = 3,
):
    if known_map[start] == OCCUPIED or known_map[goal] == OCCUPIED:
        return None

    def step_cost(cell: tuple[int, int]) -> int:
        return 1 if known_map[cell] == FREE else int(unknown_cost)

    open_heap = []
    heapq.heappush(open_heap, (0, start))
    came_from = {}
    g_score = {start: 0}
    closed = set()
    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        for nb in neighbors4(current, known_map):
            if known_map[nb] == OCCUPIED:
                continue
            tentative_g = g_score[current] + step_cost(nb)
            if tentative_g < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative_g
                f = tentative_g + heuristic(nb, goal)
                heapq.heappush(open_heap, (f, nb))
    return None


__all__ = ["heuristic", "a_star", "a_star_nav"]
