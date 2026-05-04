"""
Safety-aware grid navigation helpers for the known-map search runtime.
"""

from __future__ import annotations

from collections import deque
import heapq
import math

import numpy as np

try:
    from .core_map import OCCUPIED, neighbors4
    from .core_nav import heuristic
except ImportError:
    from core_map import OCCUPIED, neighbors4
    from core_nav import heuristic


def build_obstacle_distance_map(nav_map_prior: np.ndarray) -> np.ndarray:
    """Return 4-neighbor distances from every cell to the nearest raw obstacle."""
    distance_map = np.full(nav_map_prior.shape, np.inf, dtype=float)
    queue: deque[tuple[int, int]] = deque()

    obstacle_cells = np.argwhere(nav_map_prior == OCCUPIED)
    for row, col in obstacle_cells:
        cell = (int(row), int(col))
        distance_map[cell] = 0.0
        queue.append(cell)

    while queue:
        current = queue.popleft()
        current_distance = float(distance_map[current])
        for neighbor in neighbors4(current, nav_map_prior):
            if distance_map[neighbor] <= current_distance + 1.0:
                continue
            distance_map[neighbor] = current_distance + 1.0
            queue.append(neighbor)

    return distance_map


def inflate_occupancy_map(
    nav_map_prior: np.ndarray,
    inflation_radius_cells: int,
    obstacle_distance_map: np.ndarray | None = None,
) -> np.ndarray:
    inflation_radius_cells = max(0, int(inflation_radius_cells))
    if inflation_radius_cells == 0:
        return np.array(nav_map_prior, copy=True)

    distance_map = (
        build_obstacle_distance_map(nav_map_prior)
        if obstacle_distance_map is None
        else np.asarray(obstacle_distance_map, dtype=float)
    )
    inflated = np.array(nav_map_prior, copy=True)
    inflated[distance_map <= float(inflation_radius_cells)] = OCCUPIED
    return inflated


def build_clearance_cost_map(
    nav_map_prior: np.ndarray,
    inflation_radius_cells: int,
    soft_clearance_radius_cells: int,
    obstacle_distance_map: np.ndarray,
    inflated_nav_map: np.ndarray | None = None,
) -> np.ndarray:
    soft_radius = max(0, int(soft_clearance_radius_cells))
    inflated = (
        inflate_occupancy_map(
            nav_map_prior,
            inflation_radius_cells=inflation_radius_cells,
            obstacle_distance_map=obstacle_distance_map,
        )
        if inflated_nav_map is None
        else np.asarray(inflated_nav_map)
    )
    clearance_cost_map = np.zeros(nav_map_prior.shape, dtype=float)
    if soft_radius <= 0:
        return clearance_cost_map

    free_mask = inflated != OCCUPIED
    active_mask = free_mask & (obstacle_distance_map >= 1.0) & (
        obstacle_distance_map <= float(soft_radius)
    )
    if np.any(active_mask):
        clearance_cost_map[active_mask] = np.square(
            (float(soft_radius) - obstacle_distance_map[active_mask] + 1.0) / float(soft_radius)
        )
    return clearance_cost_map


def build_reservation_table(
    segment_path: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    safety_distance_cells: float,
) -> dict[str, object]:
    """Build per-step teammate occupancy / swap / halo reservations from a path."""
    path = [tuple(int(v) for v in cell) for cell in segment_path]
    reservation_horizon = max(len(path) - 1, 0)
    occupied: set[tuple[tuple[int, int], int]] = set()
    swap_edges: set[tuple[tuple[int, int], tuple[int, int], int]] = set()
    soft_halo: dict[tuple[tuple[int, int], int], float] = {}
    safety_distance_cells = max(0.0, float(safety_distance_cells))
    halo_radius = int(math.ceil(safety_distance_cells))

    for time_idx in range(1, len(path)):
        prev_cell = path[time_idx - 1]
        curr_cell = path[time_idx]
        occupied.add((curr_cell, int(time_idx)))
        swap_edges.add((curr_cell, prev_cell, int(time_idx)))
        if safety_distance_cells <= 0.0:
            continue
        for dx in range(-halo_radius, halo_radius + 1):
            for dy in range(-halo_radius, halo_radius + 1):
                if dx == 0 and dy == 0:
                    continue
                halo_cell = (int(curr_cell[0] + dx), int(curr_cell[1] + dy))
                distance = float(math.hypot(dx, dy))
                if distance <= 0.0 or distance >= safety_distance_cells:
                    continue
                soft_cost = ((safety_distance_cells - distance) / safety_distance_cells) ** 2
                key = (halo_cell, int(time_idx))
                soft_halo[key] = max(float(soft_halo.get(key, 0.0)), float(soft_cost))

    return {
        "occupied": occupied,
        "swap_edges": swap_edges,
        "soft_halo": soft_halo,
        "horizon": int(reservation_horizon),
        "safety_distance_cells": float(safety_distance_cells),
    }


def _reservation_soft_cost(
    reservation_table: dict[str, object] | None,
    cell: tuple[int, int],
    time_idx: int,
) -> float:
    if reservation_table is None or time_idx <= 0:
        return 0.0
    if int(time_idx) > int(reservation_table.get("horizon", 0)):
        return 0.0
    soft_halo = reservation_table.get("soft_halo")
    if not isinstance(soft_halo, dict):
        return 0.0
    return float(soft_halo.get((tuple(int(v) for v in cell), int(time_idx)), 0.0))


def _reservation_same_cell_conflict(
    reservation_table: dict[str, object] | None,
    cell: tuple[int, int],
    time_idx: int,
) -> bool:
    if reservation_table is None or time_idx <= 0:
        return False
    if int(time_idx) > int(reservation_table.get("horizon", 0)):
        return False
    occupied = reservation_table.get("occupied")
    if not isinstance(occupied, set):
        return False
    return (tuple(int(v) for v in cell), int(time_idx)) in occupied


def _reservation_swap_conflict(
    reservation_table: dict[str, object] | None,
    prev_cell: tuple[int, int],
    next_cell: tuple[int, int],
    time_idx: int,
) -> bool:
    if reservation_table is None or time_idx <= 0:
        return False
    if int(time_idx) > int(reservation_table.get("horizon", 0)):
        return False
    swap_edges = reservation_table.get("swap_edges")
    if not isinstance(swap_edges, set):
        return False
    return (
        tuple(int(v) for v in prev_cell),
        tuple(int(v) for v in next_cell),
        int(time_idx),
    ) in swap_edges


def evaluate_path_against_reservation(
    path: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    reservation_table: dict[str, object] | None,
) -> dict[str, float | bool]:
    """Return path-level teammate-conflict diagnostics under a reservation table."""
    step_cells = [tuple(int(v) for v in cell) for cell in path[1:]]
    if not step_cells or reservation_table is None:
        return {
            "same_cell_violation": False,
            "swap_violation": False,
            "near_neighbor_step_ratio": 0.0,
            "reservation_soft_penalty_raw": 0.0,
        }

    same_cell_violation = False
    swap_violation = False
    near_neighbor_count = 0
    soft_costs: list[float] = []
    full_path = [tuple(int(v) for v in cell) for cell in path]
    for time_idx, cell in enumerate(step_cells, start=1):
        prev_cell = full_path[time_idx - 1]
        same_cell_violation = (
            same_cell_violation
            or _reservation_same_cell_conflict(reservation_table, cell, time_idx)
        )
        swap_violation = (
            swap_violation
            or _reservation_swap_conflict(reservation_table, prev_cell, cell, time_idx)
        )
        soft_cost = _reservation_soft_cost(reservation_table, cell, time_idx)
        if soft_cost > 0.0:
            near_neighbor_count += 1
        soft_costs.append(float(soft_cost))

    return {
        "same_cell_violation": bool(same_cell_violation),
        "swap_violation": bool(swap_violation),
        "near_neighbor_step_ratio": float(near_neighbor_count) / float(len(step_cells)),
        "reservation_soft_penalty_raw": float(np.mean(soft_costs)) if soft_costs else 0.0,
    }


def a_star_safe(
    nav_map_prior: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    inflated_nav_map: np.ndarray,
    clearance_cost_map: np.ndarray,
    lambda_clearance: float,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> list[tuple[int, int]] | None:
    """Run A* with the same 4-neighbor / Manhattan semantics as a_star_nav."""
    if inflated_nav_map[start] == OCCUPIED or inflated_nav_map[goal] == OCCUPIED:
        return None

    lambda_clearance = float(lambda_clearance)
    if reservation_table is None:
        open_heap: list[tuple[float, tuple[int, int]]] = []
        heapq.heappush(open_heap, (0.0, start))
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start: 0.0}
        closed: set[tuple[int, int]] = set()

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
            for neighbor in neighbors4(current, nav_map_prior):
                if inflated_nav_map[neighbor] == OCCUPIED:
                    continue
                step_cost = 1.0 + lambda_clearance * float(clearance_cost_map[neighbor])
                tentative_g = float(g_score[current]) + float(step_cost)
                if tentative_g < float(g_score.get(neighbor, float("inf"))):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    priority = tentative_g + float(heuristic(neighbor, goal))
                    heapq.heappush(open_heap, (priority, neighbor))
        return None

    team_reservation_lambda = float(team_reservation_lambda)
    reservation_horizon = max(0, int(reservation_table.get("horizon", 0)))
    post_horizon_time = reservation_horizon + 1
    start_state = (tuple(int(v) for v in start), 0)
    open_heap: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_heap, (0.0, start_state))
    came_from: dict[
        tuple[tuple[int, int], int],
        tuple[tuple[int, int], int],
    ] = {}
    g_score: dict[tuple[tuple[int, int], int], float] = {start_state: 0.0}
    closed: set[tuple[tuple[int, int], int]] = set()

    while open_heap:
        _, current_state = heapq.heappop(open_heap)
        if current_state in closed:
            continue
        closed.add(current_state)
        current, current_time = current_state
        if current == goal:
            path = [current]
            while current_state in came_from:
                current_state = came_from[current_state]
                path.append(current_state[0])
            path.reverse()
            return path
        for neighbor in neighbors4(current, nav_map_prior):
            if inflated_nav_map[neighbor] == OCCUPIED:
                continue
            arrival_time = int(current_time) + 1
            if _reservation_same_cell_conflict(reservation_table, neighbor, arrival_time):
                continue
            if _reservation_swap_conflict(
                reservation_table,
                current,
                neighbor,
                arrival_time,
            ):
                continue
            reservation_soft_cost = _reservation_soft_cost(
                reservation_table,
                neighbor,
                arrival_time,
            )
            step_cost = (
                1.0
                + lambda_clearance * float(clearance_cost_map[neighbor])
                + team_reservation_lambda * float(reservation_soft_cost)
            )
            next_time = min(arrival_time, post_horizon_time)
            next_state = (neighbor, int(next_time))
            tentative_g = float(g_score[current_state]) + float(step_cost)
            if tentative_g < float(g_score.get(next_state, float("inf"))):
                came_from[next_state] = current_state
                g_score[next_state] = tentative_g
                priority = tentative_g + float(heuristic(neighbor, goal))
                heapq.heappush(open_heap, (priority, next_state))
    return None


__all__ = [
    "a_star_safe",
    "build_clearance_cost_map",
    "build_obstacle_distance_map",
    "build_reservation_table",
    "evaluate_path_against_reservation",
    "inflate_occupancy_map",
]
