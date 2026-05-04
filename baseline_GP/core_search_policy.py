"""
Goal-selection policies for the single-USV marine search runner.
"""

from __future__ import annotations

from collections import deque
import math
import time

import numpy as np

try:
    from .core_map import FREE, OCCUPIED, UNKNOWN, find_frontiers, frontier_gain, neighbors4, sensor_cells
    from .core_nav import a_star_nav
    from .core_safe_nav import a_star_safe, evaluate_path_against_reservation
    from .core_switch_penalty import move_direction, u_turn_penalty_for_path
except ImportError:
    from core_map import FREE, OCCUPIED, UNKNOWN, find_frontiers, frontier_gain, neighbors4, sensor_cells
    from core_nav import a_star_nav
    from core_safe_nav import a_star_safe, evaluate_path_against_reservation
    from core_switch_penalty import move_direction, u_turn_penalty_for_path


LEGACY_POLICIES = ("frontier_greedy", "frontier_coverage", "gp_assisted_frontier")
MARINE_POLICIES = (
    "marine_search_fg",
    "marine_search_intensity",
    "marine_two_stage",
    "marine_search_soft",
)
KNOWNMAP_POLICIES = (
    "known_map_greedy_viewpoint",
    "marine_search_soft_knownmap",
    "marine_knownmap_path_v2",
    "marine_knownmap_path_v2_infofused",
    "marine_knownmap_path_v2_infosampled",
    "marine_knownmap_path_v2_infosampled_tree_d2",
)

# Registry split is explicit so the legacy unknown-map line and the known-static
# V2 line cannot silently drift back into a single ambiguous policy surface.
SUPPORTED_LEGACY_POLICIES = LEGACY_POLICIES
SUPPORTED_UNKNOWNMAP_POLICIES = LEGACY_POLICIES + MARINE_POLICIES
SUPPORTED_KNOWNMAP_POLICIES = KNOWNMAP_POLICIES
SUPPORTED_PATH_SAFETY_MODES = ("off", "soft_clearance_astar_v1")

# Backward-compatible alias for the historical unknown-map entrypoints.
SUPPORTED_POLICIES = SUPPORTED_UNKNOWNMAP_POLICIES

# Active tree line defaults. The m2_n1 budget is the primary maintained
# shallow-tree configuration; m2_n3 remains an explicit side branch only.
KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M = 2
KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N = 1
KNOWNMAP_SIDE_BRANCH_TREE_SECOND_LAYER_TOP_N = 3

SEARCH_MODE = "SEARCH"
REACQUIRE_MODE = "REACQUIRE"

ANCHOR_CLUSTER_REL_THR = 0.85
ANCHOR_CLUSTER_ABS_THR = 1e-6
ANCHOR_CLUSTER_CONNECTIVITY = 8


def _coverage_novelty(
    pos: tuple[int, int],
    known_map: np.ndarray,
    covered_mask: np.ndarray,
    sensor_range: int,
) -> float:
    total = 0
    unseen = 0
    for x, y in sensor_cells(pos, known_map.shape, sensor_range):
        if known_map[x, y] == OCCUPIED:
            continue
        total += 1
        if not covered_mask[x, y]:
            unseen += 1
    if total == 0:
        return 0.0
    return unseen / total


def _candidate_space_legacy(
    known_map: np.ndarray,
    visited_count: np.ndarray,
) -> list[tuple[int, int]]:
    frontiers = find_frontiers(known_map)
    if frontiers:
        return frontiers

    free_cells = np.argwhere(known_map == FREE)
    if free_cells.size == 0:
        return []

    min_visits = int(np.min(visited_count[known_map == FREE]))
    return [
        (int(cell[0]), int(cell[1]))
        for cell in free_cells
        if visited_count[int(cell[0]), int(cell[1])] == min_visits
    ]


def _gp_clue_reward(
    pos: tuple[int, int],
    known_map: np.ndarray,
    sensor_range: int,
    gp_reward_map: np.ndarray | None,
    covered_mask: np.ndarray | None = None,
) -> float:
    if gp_reward_map is None:
        return 0.0

    unseen_total = 0.0
    unseen_count = 0
    total = 0.0
    count = 0
    for x, y in sensor_cells(pos, known_map.shape, sensor_range):
        if known_map[x, y] == OCCUPIED:
            continue
        if covered_mask is not None and not covered_mask[x, y]:
            unseen_total += float(gp_reward_map[x, y])
            unseen_count += 1
        total += float(gp_reward_map[x, y])
        count += 1
    if unseen_count > 0:
        return unseen_total / unseen_count
    if count == 0:
        return 0.0
    return total / count


def _cheap_candidate_priority(
    policy_name: str,
    cell: tuple[int, int],
    known_map: np.ndarray,
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    gp_reward_map: np.ndarray | None = None,
) -> float:
    frontier_reward = float(frontier_gain(cell, known_map, radius=sensor_range))
    novelty_reward = _coverage_novelty(cell, known_map, covered_mask, sensor_range)
    visit_penalty = float(visited_count[cell])

    if policy_name == "frontier_greedy":
        return frontier_reward + 0.25 * novelty_reward - 0.05 * visit_penalty
    if policy_name == "frontier_coverage":
        return frontier_reward + 6.0 * novelty_reward - 0.45 * visit_penalty
    if policy_name == "gp_assisted_frontier":
        gp_reward = _gp_clue_reward(
            cell,
            known_map,
            sensor_range,
            gp_reward_map,
            covered_mask=covered_mask,
        )
        return frontier_reward + 4.0 * novelty_reward + 18.0 * gp_reward - 0.2 * visit_penalty
    raise ValueError(f"Unsupported policy_name='{policy_name}'")


def score_goal_frontier_greedy(
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    known_map: np.ndarray,
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    lambda_frontier: float = 1.0,
    lambda_dist: float = 0.3,
) -> float:
    frontier_reward = float(frontier_gain(goal, known_map, radius=sensor_range))
    novelty_reward = _coverage_novelty(goal, known_map, covered_mask, sensor_range)
    path_cost = len(path) - 1
    return lambda_frontier * (frontier_reward + 0.5 * novelty_reward) - lambda_dist * path_cost


def score_goal_frontier_coverage(
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    known_map: np.ndarray,
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    lambda_frontier: float = 1.0,
    lambda_novelty: float = 3.0,
    lambda_visit: float = 0.5,
    lambda_dist: float = 0.3,
) -> float:
    frontier_reward = float(frontier_gain(goal, known_map, radius=sensor_range))
    novelty_reward = _coverage_novelty(goal, known_map, covered_mask, sensor_range)
    visit_penalty = float(visited_count[goal])
    path_cost = len(path) - 1
    return (
        lambda_frontier * frontier_reward
        + lambda_novelty * novelty_reward
        - lambda_visit * visit_penalty
        - lambda_dist * path_cost
    )


def score_goal_gp_assisted_frontier(
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    known_map: np.ndarray,
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    gp_reward_map: np.ndarray | None,
    lambda_frontier: float = 1.0,
    lambda_novelty: float = 2.0,
    lambda_gp: float = 14.0,
    lambda_visit: float = 0.2,
    lambda_dist: float = 0.3,
) -> float:
    frontier_reward = float(frontier_gain(goal, known_map, radius=sensor_range))
    novelty_reward = _coverage_novelty(goal, known_map, covered_mask, sensor_range)
    gp_reward = _gp_clue_reward(
        goal,
        known_map,
        sensor_range,
        gp_reward_map,
        covered_mask=covered_mask,
    )
    visit_penalty = float(visited_count[goal])
    path_cost = len(path) - 1
    return (
        lambda_frontier * frontier_reward
        + lambda_novelty * novelty_reward
        + lambda_gp * gp_reward
        - lambda_visit * visit_penalty
        - lambda_dist * path_cost
    )


def _make_zero_details() -> dict[str, object]:
    return {
        "frontier_term_raw": 0.0,
        "frontier_term_norm": 0.0,
        "staleness_term_raw": 0.0,
        "staleness_term_norm": 0.0,
        "clue_term_raw": 0.0,
        "clue_term_norm": 0.0,
        "intensity_term_raw": 0.0,
        "intensity_term_norm": 0.0,
        "anchor_value_term_raw": 0.0,
        "anchor_value_term_norm": 0.0,
        "anchor_depth_term_raw": 0.0,
        "anchor_depth_term_norm": 0.0,
        "path_cost_term_raw": 0.0,
        "path_cost_term_norm": 0.0,
        "raw_path_length_penalty_term": 0.0,
        "goal_switch_penalty_term": 0.0,
        "winner_margin_term": 0.0,
        "u_turn_penalty_term": 0.0,
        "alpha_focus": 0.0,
        "kappa_commit": 0.0,
        "same_anchor_cluster": False,
        "gateway_drift_norm": 0.0,
        "retain_anchor_bonus": 0.0,
        "gateway_continuity_bonus": 0.0,
        "candidate_count": 0,
        "current_goal_score": 0.0,
        "best_alternative_score": 0.0,
        "anchor_cell": None,
        "anchor_source": None,
        "anchor_state": None,
        "gateway_rule": None,
        "anchor_path_length": 0,
        "gateway_path_length": 0,
        "anchor_cluster_size": 0,
        "anchor_cluster_peak": 0.0,
        "anchor_cluster_mean": 0.0,
        "anchor_centroid_cell": None,
        "total_score": -float("inf"),
    }


def _select_legacy_goal(
    policy_name: str,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    gp_reward_map: np.ndarray | None,
    current_goal: tuple[int, int] | None,
    lambda_switch: float,
    prev_move_dir: tuple[int, int] | None,
    lambda_u_turn: float,
    unknown_cost: int,
    top_k: int,
) -> tuple[tuple[int, int] | None, list[tuple[int, int]] | None, float, dict]:
    candidates = _candidate_space_legacy(known_map, visited_count)
    if not candidates:
        return None, None, -float("inf"), _make_zero_details()

    candidates = sorted(
        candidates,
        key=lambda cell: _cheap_candidate_priority(
            policy_name,
            cell,
            known_map,
            covered_mask,
            visited_count,
            sensor_range,
            gp_reward_map=gp_reward_map,
        ),
        reverse=True,
    )[:top_k]

    best_goal = None
    best_path = None
    best_score = -float("inf")
    best_details = _make_zero_details()
    best_details["candidate_count"] = len(candidates)

    for goal in candidates:
        if goal == robot_pos:
            continue
        path = a_star_nav(known_map, robot_pos, goal, unknown_cost=unknown_cost)
        if path is None:
            continue

        frontier_term = float(frontier_gain(goal, known_map, radius=sensor_range))
        novelty_term = _coverage_novelty(goal, known_map, covered_mask, sensor_range)
        clue_term = 0.0

        if policy_name == "frontier_greedy":
            score = score_goal_frontier_greedy(
                goal,
                path,
                known_map,
                covered_mask,
                visited_count,
                sensor_range,
            )
        elif policy_name == "frontier_coverage":
            score = score_goal_frontier_coverage(
                goal,
                path,
                known_map,
                covered_mask,
                visited_count,
                sensor_range,
            )
        else:
            clue_term = _gp_clue_reward(
                goal,
                known_map,
                sensor_range,
                gp_reward_map,
                covered_mask=covered_mask,
            )
            score = score_goal_gp_assisted_frontier(
                goal,
                path,
                known_map,
                covered_mask,
                visited_count,
                sensor_range,
                gp_reward_map=gp_reward_map,
            )

        goal_switch_penalty = 0.0
        if current_goal is not None and goal != current_goal:
            goal_switch_penalty = float(lambda_switch)
            score -= goal_switch_penalty
        u_turn_penalty, u_turn_applied, first_move_dir = u_turn_penalty_for_path(
            path,
            prev_move_dir,
            lambda_u_turn=lambda_u_turn,
        )
        score -= u_turn_penalty

        if score > best_score:
            best_score = score
            best_goal = goal
            best_path = path
            best_details = {
                "frontier_term_raw": frontier_term,
                "frontier_term_norm": 0.0,
                "staleness_term_raw": novelty_term,
                "staleness_term_norm": 0.0,
                "clue_term_raw": clue_term,
                "clue_term_norm": 0.0,
                "intensity_term_raw": 0.0,
                "intensity_term_norm": 0.0,
                "path_cost_term_raw": float(len(path) - 1),
                "path_cost_term_norm": 0.0,
                "goal_switch_penalty_term": float(goal_switch_penalty),
                "goal_switch_penalty_applied": bool(goal_switch_penalty > 0.0),
                "u_turn_penalty_term": float(u_turn_penalty),
                "u_turn_penalty_applied": bool(u_turn_applied),
                "first_move_dir": first_move_dir,
                "candidate_count": len(candidates),
                "total_score": float(score),
            }

    return best_goal, best_path, best_score, best_details


def _nms_hotspots(
    score_map: np.ndarray | None,
    candidate_mask: np.ndarray,
    top_k: int,
    radius: int,
) -> list[tuple[int, int]]:
    if score_map is None or top_k <= 0:
        return []

    values = np.asarray(score_map, dtype=float)
    valid_mask = candidate_mask & np.isfinite(values)
    if not np.any(valid_mask):
        return []

    flat_indices = np.argsort(values.reshape(-1))[::-1]
    chosen: list[tuple[int, int]] = []
    for flat_idx in flat_indices:
        cell = tuple(int(v) for v in np.unravel_index(int(flat_idx), values.shape))
        if not valid_mask[cell]:
            continue
        if values[cell] <= 0.0:
            break
        if any((cell[0] - px) ** 2 + (cell[1] - py) ** 2 <= radius * radius for px, py in chosen):
            continue
        chosen.append(cell)
        if len(chosen) >= top_k:
            break
    return chosen


def _high_value_mask(
    score_map: np.ndarray | None,
    candidate_mask: np.ndarray,
    rel_thr: float,
    abs_thr: float,
) -> tuple[np.ndarray, float] | tuple[None, float]:
    if score_map is None:
        return None, 0.0
    values = np.asarray(score_map, dtype=float)
    valid_mask = candidate_mask & np.isfinite(values)
    if not np.any(valid_mask):
        return None, 0.0
    peak_value = float(np.max(values[valid_mask]))
    if peak_value <= float(abs_thr):
        return None, peak_value
    threshold = max(float(abs_thr), float(rel_thr) * peak_value)
    high_mask = valid_mask & (values >= threshold)
    if not np.any(high_mask):
        return None, peak_value
    return high_mask, threshold


def _connected_components(
    mask: np.ndarray,
    connectivity: int = ANCHOR_CLUSTER_CONNECTIVITY,
) -> list[list[tuple[int, int]]]:
    if mask.size == 0 or not np.any(mask):
        return []
    if connectivity not in {4, 8}:
        raise ValueError("connectivity must be 4 or 8")

    if connectivity == 4:
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    else:
        neighbors = [
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]

    visited = np.zeros(mask.shape, dtype=bool)
    h, w = mask.shape
    components: list[list[tuple[int, int]]] = []
    for x in range(h):
        for y in range(w):
            if not mask[x, y] or visited[x, y]:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited[x, y] = True
            component: list[tuple[int, int]] = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for dx, dy in neighbors:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < h and 0 <= ny < w and mask[nx, ny] and not visited[nx, ny]:
                        visited[nx, ny] = True
                        queue.append((nx, ny))
            components.append(component)
    return components


def _component_anchor(
    component_cells: list[tuple[int, int]],
    score_map: np.ndarray,
    threshold: float,
) -> tuple[tuple[int, int], tuple[int, int], float, float, float]:
    coords = np.asarray(component_cells, dtype=float)
    values = np.asarray([float(score_map[cell]) for cell in component_cells], dtype=float)
    weights = np.clip(values - float(threshold), 0.0, None) + 1e-6
    centroid = np.average(coords, axis=0, weights=weights)
    distances = np.sum((coords - centroid) ** 2, axis=1)
    order = np.lexsort((
        coords[:, 1],
        coords[:, 0],
        -values,
        distances,
    ))
    anchor_idx = int(order[0])
    anchor_cell = tuple(int(v) for v in component_cells[anchor_idx])
    centroid_cell = tuple(int(v) for v in np.round(centroid).astype(int))
    peak_value = float(np.max(values))
    mean_value = float(np.mean(values))
    cluster_score = 0.6 * peak_value + 0.3 * mean_value + 0.1 * math.log1p(len(component_cells))
    return anchor_cell, centroid_cell, peak_value, mean_value, cluster_score


def _cluster_hotspots(
    score_map: np.ndarray | None,
    candidate_mask: np.ndarray,
    top_k: int,
    rel_thr: float = ANCHOR_CLUSTER_REL_THR,
    abs_thr: float = ANCHOR_CLUSTER_ABS_THR,
    connectivity: int = ANCHOR_CLUSTER_CONNECTIVITY,
) -> list[dict[str, object]]:
    if score_map is None or top_k <= 0:
        return []
    high_mask, threshold = _high_value_mask(score_map, candidate_mask, rel_thr=rel_thr, abs_thr=abs_thr)
    if high_mask is None:
        return []

    clusters: list[dict[str, object]] = []
    for component_cells in _connected_components(high_mask, connectivity=connectivity):
        if not component_cells:
            continue
        anchor_cell, centroid_cell, peak_value, mean_value, cluster_score = _component_anchor(
            component_cells,
            np.asarray(score_map, dtype=float),
            float(threshold),
        )
        clusters.append(
            {
                "anchor_cell": anchor_cell,
                "anchor_centroid_cell": centroid_cell,
                "anchor_cluster_size": int(len(component_cells)),
                "anchor_cluster_peak": float(peak_value),
                "anchor_cluster_mean": float(mean_value),
                "anchor_value": float(cluster_score),
            }
        )

    clusters.sort(
        key=lambda item: (
            float(item["anchor_value"]),
            float(item["anchor_cluster_peak"]),
            float(item["anchor_cluster_mean"]),
            int(item["anchor_cluster_size"]),
        ),
        reverse=True,
    )
    return clusters[:top_k]


def _project_to_known_free(
    cell: tuple[int, int],
    known_free_cells: np.ndarray,
) -> tuple[int, int] | None:
    if known_free_cells.size == 0:
        return None
    diffs = known_free_cells - np.asarray(cell, dtype=float)
    distances = np.sum(diffs * diffs, axis=1)
    idx = int(np.argmin(distances))
    return (int(known_free_cells[idx, 0]), int(known_free_cells[idx, 1]))


def _dedupe_cells(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen = set()
    deduped = []
    for cell in cells:
        if cell in seen:
            continue
        seen.add(cell)
        deduped.append(cell)
    return deduped


def _marine_frontier_candidates(
    known_map: np.ndarray,
    sensor_range: int,
    top_k_frontier: int,
) -> list[tuple[int, int]]:
    frontiers = find_frontiers(known_map)
    frontiers = sorted(
        frontiers,
        key=lambda cell: float(frontier_gain(cell, known_map, radius=sensor_range)),
        reverse=True,
    )
    return frontiers[:top_k_frontier]


def _known_cell_state(
    known_map: np.ndarray,
    cell: tuple[int, int] | None,
) -> str | None:
    if cell is None:
        return None
    if known_map[cell] == FREE:
        return "FREE"
    if known_map[cell] == UNKNOWN:
        return "UNKNOWN"
    if known_map[cell] == OCCUPIED:
        return "OCCUPIED"
    return None


def _marine_hotspot_candidates(
    score_map: np.ndarray | None,
    known_map: np.ndarray,
    top_k: int,
    nms_radius: int,
) -> list[tuple[int, int]]:
    if top_k <= 0:
        return []
    candidate_mask = known_map != OCCUPIED
    hotspots = _nms_hotspots(score_map, candidate_mask, top_k=top_k, radius=nms_radius)
    known_free_cells = np.argwhere(known_map == FREE)
    projected = []
    for hotspot in hotspots:
        projected_cell = _project_to_known_free(hotspot, known_free_cells)
        if projected_cell is not None:
            projected.append(projected_cell)
    return _dedupe_cells(projected)


def _path_prefix_to_cell(
    path: list[tuple[int, int]],
    target_cell: tuple[int, int],
) -> list[tuple[int, int]] | None:
    for idx, cell in enumerate(path):
        if cell == target_cell:
            return list(path[: idx + 1])
    return None


def _first_frontier_on_path(
    path: list[tuple[int, int]],
    frontier_set: set[tuple[int, int]],
    robot_pos: tuple[int, int],
) -> tuple[int, int] | None:
    for cell in path[1:]:
        if cell != robot_pos and cell in frontier_set:
            return cell
    return None


def _extract_gateway_from_anchor_path(
    path_to_anchor: list[tuple[int, int]],
    known_map: np.ndarray,
    frontier_set: set[tuple[int, int]],
    robot_pos: tuple[int, int],
) -> tuple[tuple[int, int] | None, str | None, list[tuple[int, int]] | None]:
    """Historical unknown-map gateway extraction helper.

    This function is retained for the legacy unknown-map baselines only.
    The known-static-map V2 mainline must not reuse these gateway rules.
    """
    if not path_to_anchor or path_to_anchor[0] != robot_pos:
        return None, None, None

    last_known_free = None
    first_unknown_idx = None
    for idx, cell in enumerate(path_to_anchor):
        if known_map[cell] == UNKNOWN:
            first_unknown_idx = idx
            break
        if known_map[cell] == FREE:
            last_known_free = cell

    if first_unknown_idx is None:
        anchor = path_to_anchor[-1]
        if known_map[anchor] == FREE:
            return anchor, "anchor_is_free", list(path_to_anchor)
        return None, None, None

    if last_known_free is not None and last_known_free != robot_pos:
        prefix = _path_prefix_to_cell(path_to_anchor, last_known_free)
        return last_known_free, "last_free_before_unknown", prefix

    frontier_gateway = _first_frontier_on_path(path_to_anchor, frontier_set, robot_pos)
    if frontier_gateway is None:
        return None, None, None
    prefix = _path_prefix_to_cell(path_to_anchor, frontier_gateway)
    return frontier_gateway, "direct_frontier", prefix


def _direct_frontier_candidate(
    frontier_cell: tuple[int, int],
    known_map: np.ndarray,
    sensor_range: int,
) -> dict[str, object]:
    """Historical unknown-map frontier candidate helper."""
    return {
        "anchor_cell": frontier_cell,
        "gateway_cell": frontier_cell,
        "anchor_source": "frontier",
        "anchor_state": _known_cell_state(known_map, frontier_cell),
        "gateway_rule": "direct_frontier",
        "path_to_anchor": None,
        "path_to_gateway": None,
        "anchor_value": float(frontier_gain(frontier_cell, known_map, radius=sensor_range)),
        "anchor_cluster_size": 1,
        "anchor_cluster_peak": float(frontier_gain(frontier_cell, known_map, radius=sensor_range)),
        "anchor_cluster_mean": float(frontier_gain(frontier_cell, known_map, radius=sensor_range)),
        "anchor_centroid_cell": frontier_cell,
        "is_current_goal": False,
        "is_current_anchor": False,
    }


def _direct_current_goal_candidate(
    current_goal: tuple[int, int],
    known_map: np.ndarray,
) -> dict[str, object] | None:
    if known_map[current_goal] != FREE:
        return None
    return {
        "anchor_cell": current_goal,
        "gateway_cell": current_goal,
        "anchor_source": "current_goal",
        "anchor_state": _known_cell_state(known_map, current_goal),
        "gateway_rule": "current_goal",
        "path_to_anchor": None,
        "path_to_gateway": None,
        "anchor_value": 0.0,
        "anchor_cluster_size": 1,
        "anchor_cluster_peak": 0.0,
        "anchor_cluster_mean": 0.0,
        "anchor_centroid_cell": current_goal,
        "is_current_goal": True,
        "is_current_anchor": False,
    }


def _anchor_gateway_candidate(
    anchor_cell: tuple[int, int],
    anchor_source: str,
    anchor_value: float,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    frontier_set: set[tuple[int, int]],
    unknown_cost: int,
    anchor_cluster_size: int = 1,
    anchor_cluster_peak: float | None = None,
    anchor_cluster_mean: float | None = None,
    anchor_centroid_cell: tuple[int, int] | None = None,
    is_current_anchor: bool = False,
) -> dict[str, object] | None:
    if known_map[anchor_cell] == OCCUPIED:
        return None
    path_to_anchor = a_star_nav(known_map, robot_pos, anchor_cell, unknown_cost=unknown_cost)
    if path_to_anchor is None or len(path_to_anchor) <= 1:
        return None
    gateway_cell, gateway_rule, path_to_gateway = _extract_gateway_from_anchor_path(
        path_to_anchor,
        known_map,
        frontier_set,
        robot_pos,
    )
    if gateway_cell is None or path_to_gateway is None:
        return None
    if known_map[gateway_cell] != FREE:
        return None
    return {
        "anchor_cell": anchor_cell,
        "gateway_cell": gateway_cell,
        "anchor_source": anchor_source,
        "anchor_state": _known_cell_state(known_map, anchor_cell),
        "gateway_rule": gateway_rule,
        "path_to_anchor": list(path_to_anchor),
        "path_to_gateway": list(path_to_gateway),
        "anchor_value": float(anchor_value),
        "anchor_cluster_size": int(anchor_cluster_size),
        "anchor_cluster_peak": float(
            anchor_cluster_peak if anchor_cluster_peak is not None else anchor_value
        ),
        "anchor_cluster_mean": float(
            anchor_cluster_mean if anchor_cluster_mean is not None else anchor_value
        ),
        "anchor_centroid_cell": anchor_centroid_cell if anchor_centroid_cell is not None else anchor_cell,
        "is_current_goal": False,
        "is_current_anchor": bool(is_current_anchor),
    }


def _search_candidate_exact_key(candidate: dict[str, object]) -> tuple[object, ...]:
    anchor_source = str(candidate.get("anchor_source"))
    gateway_rule = str(candidate.get("gateway_rule"))
    if anchor_source == "frontier" or gateway_rule == "current_goal":
        return ("gateway", candidate.get("gateway_cell"))
    return (
        "anchor_gateway",
        candidate.get("anchor_cell"),
        candidate.get("gateway_cell"),
        anchor_source,
    )


def _prefer_gateway_candidate(
    candidate: dict[str, object],
    incumbent: dict[str, object],
) -> bool:
    def _semantic_source_priority(item: dict[str, object]) -> int:
        source = str(item.get("anchor_source"))
        return 1 if source not in {"frontier", "current_goal"} else 0

    def _gateway_rule_priority(item: dict[str, object]) -> int:
        gateway_rule = str(item.get("gateway_rule"))
        return {
            "last_free_before_unknown": 3,
            "anchor_is_free": 2,
            "direct_frontier": 1,
            "current_goal": 0,
        }.get(gateway_rule, -1)

    def _anchor_state_priority(item: dict[str, object]) -> int:
        anchor_state = item.get("anchor_state")
        return {
            "UNKNOWN": 2,
            "FREE": 1,
            "OCCUPIED": 0,
        }.get(anchor_state, -1)

    def _anchor_depth(item: dict[str, object]) -> int:
        path_to_anchor = item.get("path_to_anchor")
        path_to_gateway = item.get("path_to_gateway")
        if not isinstance(path_to_anchor, list) or not isinstance(path_to_gateway, list):
            return 0
        return max(len(path_to_anchor) - len(path_to_gateway), 0)

    candidate_key = (
        1 if candidate.get("is_current_anchor") else 0,
        _semantic_source_priority(candidate),
        _gateway_rule_priority(candidate),
        _anchor_state_priority(candidate),
        _anchor_depth(candidate),
        1 if candidate.get("is_current_goal") else 0,
    )
    incumbent_key = (
        1 if incumbent.get("is_current_anchor") else 0,
        _semantic_source_priority(incumbent),
        _gateway_rule_priority(incumbent),
        _anchor_state_priority(incumbent),
        _anchor_depth(incumbent),
        1 if incumbent.get("is_current_goal") else 0,
    )
    if candidate_key != incumbent_key:
        return candidate_key > incumbent_key

    candidate_source = str(candidate.get("anchor_source"))
    incumbent_source = str(incumbent.get("anchor_source"))
    if candidate_source == incumbent_source:
        return float(candidate.get("anchor_value", 0.0)) > float(incumbent.get("anchor_value", 0.0))
    return False


def _dedupe_search_candidates(
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    exact_deduped: list[dict[str, object]] = []
    exact_seen: set[tuple[object, ...]] = set()
    for candidate in candidates:
        key = _search_candidate_exact_key(candidate)
        if key in exact_seen:
            continue
        exact_seen.add(key)
        exact_deduped.append(candidate)

    best_by_gateway: dict[tuple[int, int], dict[str, object]] = {}
    gateway_order: list[tuple[int, int]] = []
    for candidate in exact_deduped:
        gateway = candidate["gateway_cell"]
        incumbent = best_by_gateway.get(gateway)
        if incumbent is None:
            best_by_gateway[gateway] = candidate
            gateway_order.append(gateway)
            continue
        if _prefer_gateway_candidate(candidate, incumbent):
            best_by_gateway[gateway] = candidate

    return [best_by_gateway[gateway] for gateway in gateway_order]


def _marine_local_free_candidates(
    known_map: np.ndarray,
    center: tuple[int, int] | None,
    radius: int,
) -> list[tuple[int, int]]:
    if center is None:
        return []
    free_cells = np.argwhere(known_map == FREE)
    if free_cells.size == 0:
        return []
    selected = []
    cx, cy = center
    for x, y in free_cells:
        if (int(x) - cx) ** 2 + (int(y) - cy) ** 2 <= radius * radius:
            selected.append((int(x), int(y)))
    return selected


def _fallback_min_visit_candidates(
    known_map: np.ndarray,
    visited_count: np.ndarray,
    top_k: int,
) -> list[tuple[int, int]]:
    free_cells = np.argwhere(known_map == FREE)
    if free_cells.size == 0:
        return []
    values = visited_count[known_map == FREE]
    min_visits = int(np.min(values))
    candidates = [
        (int(cell[0]), int(cell[1]))
        for cell in free_cells
        if visited_count[int(cell[0]), int(cell[1])] == min_visits
    ]
    return candidates[:top_k]


def _marine_candidate_space(
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    visited_count: np.ndarray,
    sensor_range: int,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    current_goal: tuple[int, int] | None,
    current_anchor: tuple[int, int] | None,
    current_anchor_source: str | None,
    mode: str,
    unknown_cost: int,
    top_k_frontier: int,
    top_k_staleness: int,
    top_k_clue: int,
    top_k_intensity: int,
) -> list[object]:
    nms_radius = max(1, int(sensor_range))
    candidates: list[object] = []

    if mode == SEARCH_MODE:
        frontier_cells = _marine_frontier_candidates(known_map, sensor_range, top_k_frontier)
        frontier_set = set(frontier_cells)
        for frontier_cell in frontier_cells:
            candidates.append(_direct_frontier_candidate(frontier_cell, known_map, sensor_range))

        def add_hotspot_candidates(
            score_map: np.ndarray | None,
            anchor_source: str,
            top_k: int,
        ) -> None:
            if top_k <= 0 or score_map is None:
                return
            anchor_mask = (known_map != OCCUPIED) & np.isfinite(np.asarray(score_map, dtype=float))
            clusters = _cluster_hotspots(
                score_map,
                anchor_mask,
                top_k=top_k,
            )
            for cluster in clusters:
                candidate = _anchor_gateway_candidate(
                    anchor_cell=tuple(int(v) for v in cluster["anchor_cell"]),
                    anchor_source=anchor_source,
                    anchor_value=float(cluster["anchor_value"]),
                    known_map=known_map,
                    robot_pos=robot_pos,
                    frontier_set=frontier_set,
                    unknown_cost=unknown_cost,
                    anchor_cluster_size=int(cluster["anchor_cluster_size"]),
                    anchor_cluster_peak=float(cluster["anchor_cluster_peak"]),
                    anchor_cluster_mean=float(cluster["anchor_cluster_mean"]),
                    anchor_centroid_cell=tuple(int(v) for v in cluster["anchor_centroid_cell"]),
                )
                if candidate is not None:
                    candidates.append(candidate)

        add_hotspot_candidates(staleness_map, "staleness", top_k_staleness)
        add_hotspot_candidates(clue_map, "clue", top_k_clue)
        add_hotspot_candidates(intensity_map, "intensity", top_k_intensity)

        if current_goal is not None:
            candidate = _direct_current_goal_candidate(current_goal, known_map)
            if candidate is not None:
                candidates.append(candidate)
        if current_anchor is not None:
            candidate = _anchor_gateway_candidate(
                anchor_cell=current_anchor,
                anchor_source=(
                    current_anchor_source
                    if current_anchor_source in {"staleness", "clue", "intensity"}
                    else "current_goal"
                ),
                anchor_value=0.0,
                known_map=known_map,
                robot_pos=robot_pos,
                frontier_set=frontier_set,
                unknown_cost=unknown_cost,
                anchor_centroid_cell=current_anchor,
                is_current_anchor=True,
            )
            if candidate is not None:
                candidates.append(candidate)
        candidates = _dedupe_search_candidates(
            [candidate for candidate in candidates if isinstance(candidate, dict)]
        )
    else:
        intensity_hotspots = _nms_hotspots(
            intensity_map,
            candidate_mask=(known_map != OCCUPIED),
            top_k=top_k_intensity,
            radius=nms_radius,
        )
        known_free_cells = np.argwhere(known_map == FREE)
        for hotspot in intensity_hotspots:
            projected_cell = _project_to_known_free(hotspot, known_free_cells)
            if projected_cell is not None:
                candidates.append(projected_cell)
            candidates.extend(
                _marine_local_free_candidates(
                    known_map,
                    projected_cell if projected_cell is not None else hotspot,
                    radius=max(1, 2 * int(sensor_range)),
                )
            )
        if current_goal is not None:
            candidates.append(current_goal)

    if mode == SEARCH_MODE:
        if not candidates:
            candidates = [
                _direct_frontier_candidate(cell, known_map, sensor_range)
                for cell in _fallback_min_visit_candidates(
                    known_map,
                    visited_count,
                    top_k=max(top_k_frontier, top_k_staleness, top_k_clue, top_k_intensity, 10),
                )
            ]
        return candidates

    candidates = _dedupe_cells([cell for cell in candidates if isinstance(cell, tuple)])
    if not candidates:
        candidates = _fallback_min_visit_candidates(
            known_map,
            visited_count,
            top_k=max(top_k_frontier, top_k_staleness, top_k_clue, top_k_intensity, 10),
        )
    return [cell for cell in candidates if known_map[cell] == FREE]


def _visible_cells(
    pos: tuple[int, int],
    known_map: np.ndarray,
    sensor_range: int,
) -> list[tuple[int, int]]:
    return [
        (x, y)
        for x, y in sensor_cells(pos, known_map.shape, sensor_range)
        if known_map[x, y] != OCCUPIED
    ]


def _marine_path_score_breakdown(
    path: list[tuple[int, int]],
    known_map: np.ndarray,
    sensor_range: int,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    gamma: float,
) -> dict[str, float]:
    seen_unknown: set[tuple[int, int]] = set()
    frontier_total = 0.0
    staleness_total = 0.0
    clue_total = 0.0
    intensity_total = 0.0

    for step_idx, waypoint in enumerate(path[1:], start=0):
        discount = float(gamma) ** float(step_idx)
        visible_cells = _visible_cells(waypoint, known_map, sensor_range)
        if not visible_cells:
            continue

        new_unknown_count = 0
        staleness_values = []
        clue_values = []
        intensity_values = []

        for cell in visible_cells:
            if known_map[cell] == UNKNOWN and cell not in seen_unknown:
                seen_unknown.add(cell)
                new_unknown_count += 1
            if staleness_map is not None:
                staleness_values.append(float(staleness_map[cell]))
            if clue_map is not None:
                clue_values.append(float(clue_map[cell]))
            if intensity_map is not None:
                intensity_values.append(float(intensity_map[cell]))

        frontier_total += discount * float(new_unknown_count)
        if staleness_values:
            staleness_total += discount * float(np.mean(staleness_values))
        if clue_values:
            clue_total += discount * float(np.mean(clue_values))
        if intensity_values:
            intensity_total += discount * float(np.mean(intensity_values))

    return {
        "frontier_term_raw": frontier_total,
        "staleness_term_raw": staleness_total,
        "clue_term_raw": clue_total,
        "intensity_term_raw": intensity_total,
        "path_cost_term_raw": float(len(path) - 1),
    }


def _normalize_term(values: list[float]) -> list[float]:
    if not values:
        return []
    v_min = float(min(values))
    v_max = float(max(values))
    if math.isclose(v_min, v_max, rel_tol=1e-12, abs_tol=1e-12):
        return [0.0] * len(values)
    scale = v_max - v_min
    return [(float(value) - v_min) / scale for value in values]


def _marine_score_weights(policy_name: str, mode: str) -> dict[str, float]:
    if policy_name == "marine_search_fg":
        return {
            "frontier_term_norm": 6.0,
            "staleness_term_norm": 5.0,
            "clue_term_norm": 4.0,
            "intensity_term_norm": 0.0,
            "path_cost_term_norm": -0.3,
        }
    if policy_name == "marine_search_intensity":
        return {
            "frontier_term_norm": 5.5,
            "staleness_term_norm": 4.5,
            "clue_term_norm": 3.5,
            "intensity_term_norm": 2.0,
            "path_cost_term_norm": -0.3,
        }
    if policy_name == "marine_two_stage" and mode == SEARCH_MODE:
        return {
            "frontier_term_norm": 5.5,
            "staleness_term_norm": 4.5,
            "clue_term_norm": 3.5,
            "intensity_term_norm": 2.0,
            "path_cost_term_norm": -0.3,
        }
    if policy_name == "marine_two_stage" and mode == REACQUIRE_MODE:
        return {
            "frontier_term_norm": 0.0,
            "staleness_term_norm": 1.0,
            "clue_term_norm": 3.0,
            "intensity_term_norm": 8.0,
            "path_cost_term_norm": -0.25,
        }
    raise ValueError(f"Unsupported marine policy/mode combination: {policy_name} / {mode}")


def _marine_soft_weights() -> dict[str, float]:
    return {
        "frontier_term_norm": 6.0,
        "staleness_term_norm": 5.0,
        "clue_term_norm": 0.0,
        "intensity_term_norm": 0.0,
        "anchor_value_term_norm": 0.0,
        "anchor_depth_term_norm": 0.0,
        "path_cost_term_norm": -0.3,
    }


def _semantic_anchor_source(anchor_source: str | None) -> bool:
    return anchor_source in {"staleness", "clue", "intensity", "search_info"}


def _knownmap_uses_search_info_anchors(policy_name: str) -> bool:
    return policy_name in {
        "marine_knownmap_path_v2_infofused",
        "marine_knownmap_path_v2_infosampled",
        "marine_knownmap_path_v2_infosampled_tree_d2",
    }


def _knownmap_is_infosampled_family(policy_name: str) -> bool:
    return policy_name in {
        "marine_knownmap_path_v2_infosampled",
        "marine_knownmap_path_v2_infosampled_tree_d2",
    }


def _knownmap_anchor_source_or_fallback(
    anchor_source: str | None,
    fallback_source: str = "fallback_local",
) -> str:
    if anchor_source is None:
        return str(fallback_source)
    return str(anchor_source)


def _knownmap_continuation_anchor_source(
    policy_name: str,
    current_anchor_source: str | None,
    *,
    current_viewpoint: bool = False,
) -> str:
    if _knownmap_uses_search_info_anchors(policy_name):
        if current_viewpoint:
            return "current_viewpoint"
        if _semantic_anchor_source(current_anchor_source):
            return "search_info"
        return "fallback_local"
    return _knownmap_anchor_source_or_fallback(current_anchor_source)


def _knownmap_anchor_info_shares(
    anchor_cell: tuple[int, int] | None,
    clue_component_map: np.ndarray | None,
    intensity_component_map: np.ndarray | None,
) -> tuple[float, float]:
    if anchor_cell is None or clue_component_map is None or intensity_component_map is None:
        return 0.0, 0.0
    clue_value = max(0.0, float(clue_component_map[anchor_cell]))
    intensity_value = max(0.0, float(intensity_component_map[anchor_cell]))
    total = clue_value + intensity_value
    if total <= 1e-9:
        return 0.0, 0.0
    return float(clue_value / total), float(intensity_value / total)


def _same_anchor_cluster_candidate(
    candidate: dict[str, object],
    current_anchor_source: str | None,
    current_anchor_centroid: tuple[int, int] | None,
    sensor_range: int,
) -> bool:
    candidate_source = str(candidate.get("anchor_source"))
    candidate_centroid = candidate.get("anchor_centroid_cell")
    if (
        not _semantic_anchor_source(current_anchor_source)
        or not _semantic_anchor_source(candidate_source)
        or current_anchor_centroid is None
        or candidate_centroid is None
        or candidate_source != current_anchor_source
    ):
        return False
    candidate_centroid = tuple(int(v) for v in candidate_centroid)
    anchor_match_radius = max(2, int(sensor_range) // 2)
    return math.hypot(
        candidate_centroid[0] - current_anchor_centroid[0],
        candidate_centroid[1] - current_anchor_centroid[1],
    ) <= float(anchor_match_radius)


def _cells_distance(
    a: tuple[int, int] | None,
    b: tuple[int, int] | None,
) -> float:
    if a is None or b is None:
        return float("inf")
    return float(math.hypot(a[0] - b[0], a[1] - b[1]))


def _gateway_drift_norm(
    goal: tuple[int, int],
    current_goal: tuple[int, int] | None,
    sensor_range: int,
) -> float:
    if current_goal is None:
        return 0.0
    denom = max(1, int(sensor_range))
    drift = math.hypot(goal[0] - current_goal[0], goal[1] - current_goal[1]) / float(denom)
    return float(np.clip(drift, 0.0, 1.0))


def _soft_commit_terms(
    kappa_commit: float,
    same_anchor_cluster: bool,
    gateway_drift_norm: float,
    has_current_goal: bool,
    same_gateway: bool,
) -> tuple[float, float]:
    # Deprecated compatibility hook: kappa_commit is still accepted by callers,
    # but it no longer contributes continuity bonuses to goal scoring.
    return 0.0, 0.0


def _select_marine_goal(
    policy_name: str,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    current_goal: tuple[int, int] | None,
    current_anchor: tuple[int, int] | None,
    current_anchor_source: str | None,
    prev_move_dir: tuple[int, int] | None,
    mode: str,
    lambda_switch: float,
    winner_margin: float,
    lambda_dist_raw: float,
    lambda_u_turn: float,
    kappa_commit: float,
    current_anchor_centroid: tuple[int, int] | None,
    unknown_cost: int,
    gamma: float,
    top_k_frontier: int,
    top_k_staleness: int,
    top_k_clue: int,
    top_k_intensity: int,
) -> tuple[tuple[int, int] | None, list[tuple[int, int]] | None, float, dict]:
    candidates = _marine_candidate_space(
        known_map=known_map,
        robot_pos=robot_pos,
        visited_count=visited_count,
        sensor_range=sensor_range,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        current_goal=current_goal,
        current_anchor=current_anchor,
        current_anchor_source=current_anchor_source,
        mode=mode,
        unknown_cost=unknown_cost,
        top_k_frontier=top_k_frontier,
        top_k_staleness=top_k_staleness,
        top_k_clue=top_k_clue,
        top_k_intensity=top_k_intensity,
    )
    if not candidates:
        return None, None, -float("inf"), _make_zero_details()

    evaluations: list[dict] = []
    frontier_set = set(find_frontiers(known_map))
    for candidate in candidates:
        if isinstance(candidate, dict):
            goal = tuple(int(v) for v in candidate["gateway_cell"])
            if goal == robot_pos:
                continue
            path = candidate.get("path_to_gateway")
            if path is None:
                path = a_star_nav(known_map, robot_pos, goal, unknown_cost=unknown_cost)
            if path is None or len(path) <= 1:
                continue
            path_to_anchor = candidate.get("path_to_anchor")
            anchor_cell = tuple(int(v) for v in candidate["anchor_cell"])
            anchor_source = str(candidate["anchor_source"])
            anchor_state = candidate.get("anchor_state")
            gateway_rule = candidate.get("gateway_rule")
            anchor_path_length = (
                max(len(path_to_anchor) - 1, 0)
                if isinstance(path_to_anchor, list)
                else max(len(path) - 1, 0)
            )
            gateway_path_length = max(len(path) - 1, 0)
            anchor_cluster_size = int(candidate.get("anchor_cluster_size", 1))
            anchor_cluster_peak = float(candidate.get("anchor_cluster_peak", 0.0))
            anchor_cluster_mean = float(candidate.get("anchor_cluster_mean", 0.0))
            anchor_centroid_cell = candidate.get("anchor_centroid_cell")
            anchor_value_term_raw = float(
                candidate.get("anchor_value", 0.0)
                if _semantic_anchor_source(anchor_source)
                else 0.0
            )
        else:
            goal = tuple(int(v) for v in candidate)
            if goal == robot_pos:
                continue
            path = a_star_nav(known_map, robot_pos, goal, unknown_cost=unknown_cost)
            if path is None or len(path) <= 1:
                continue
            anchor_cell = goal
            anchor_source = "current_goal" if current_goal is not None and goal == current_goal else (
                "frontier" if goal in frontier_set else "current_goal"
            )
            anchor_state = _known_cell_state(known_map, goal)
            gateway_rule = "current_goal" if current_goal is not None and goal == current_goal else "direct_frontier"
            anchor_path_length = max(len(path) - 1, 0)
            gateway_path_length = max(len(path) - 1, 0)
            anchor_cluster_size = 1
            anchor_cluster_peak = 0.0
            anchor_cluster_mean = 0.0
            anchor_centroid_cell = goal
            anchor_value_term_raw = 0.0
        breakdown = _marine_path_score_breakdown(
            path,
            known_map,
            sensor_range,
            staleness_map=staleness_map,
            clue_map=clue_map,
            intensity_map=intensity_map,
            gamma=gamma,
        )
        evaluations.append(
            {
                "goal": goal,
                "path": path,
                "anchor_cell": anchor_cell,
                "anchor_source": anchor_source,
                "anchor_state": anchor_state,
                "gateway_rule": gateway_rule,
                "anchor_path_length": int(anchor_path_length),
                "gateway_path_length": int(gateway_path_length),
                "anchor_cluster_size": int(anchor_cluster_size),
                "anchor_cluster_peak": float(anchor_cluster_peak),
                "anchor_cluster_mean": float(anchor_cluster_mean),
                "anchor_centroid_cell": anchor_centroid_cell,
                "anchor_value_term_raw": float(anchor_value_term_raw),
                "anchor_depth_term_raw": float(
                    max(int(anchor_path_length) - int(gateway_path_length), 0)
                    if _semantic_anchor_source(anchor_source)
                    else 0.0
                ),
                **breakdown,
            }
        )

    if not evaluations:
        return None, None, -float("inf"), _make_zero_details()

    for term_name in (
        "frontier_term_raw",
        "staleness_term_raw",
        "clue_term_raw",
        "intensity_term_raw",
        "anchor_value_term_raw",
        "anchor_depth_term_raw",
        "path_cost_term_raw",
    ):
        norm_values = _normalize_term([item[term_name] for item in evaluations])
        norm_name = term_name.replace("_raw", "_norm")
        for item, norm_value in zip(evaluations, norm_values):
            item[norm_name] = norm_value

    weights = (
        _marine_soft_weights()
        if policy_name == "marine_search_soft"
        else _marine_score_weights(policy_name, mode)
    )
    for item in evaluations:
        total_score = 0.0
        for term_name, weight in weights.items():
            total_score += float(weight) * float(item.get(term_name, 0.0))
        raw_path_length_penalty = 0.0
        if mode == SEARCH_MODE:
            raw_path_length_penalty = float(lambda_dist_raw) * float(item["path_cost_term_raw"])
            total_score -= raw_path_length_penalty
        same_anchor_cluster = False
        gateway_drift_norm = 0.0
        retain_anchor_bonus = 0.0
        gateway_continuity_bonus = 0.0
        if policy_name == "marine_search_soft":
            same_anchor_cluster = _same_anchor_cluster_candidate(
                item,
                current_anchor_source=current_anchor_source,
                current_anchor_centroid=current_anchor_centroid,
                sensor_range=sensor_range,
            )
            gateway_drift_norm = _gateway_drift_norm(
                item["goal"],
                current_goal=current_goal,
                sensor_range=sensor_range,
            )
            retain_anchor_bonus, gateway_continuity_bonus = _soft_commit_terms(
                kappa_commit=kappa_commit,
                same_anchor_cluster=same_anchor_cluster,
                gateway_drift_norm=gateway_drift_norm,
                has_current_goal=current_goal is not None,
                same_gateway=current_goal is not None and item["goal"] == current_goal,
            )

        goal_switch_penalty = 0.0
        if policy_name != "marine_search_soft" and current_goal is not None and item["goal"] != current_goal:
            goal_switch_penalty = float(lambda_switch)
            total_score -= goal_switch_penalty
        u_turn_penalty, u_turn_applied, first_move_dir = u_turn_penalty_for_path(
            item["path"],
            prev_move_dir,
            lambda_u_turn=lambda_u_turn,
        )
        total_score -= u_turn_penalty
        item["raw_path_length_penalty_term"] = float(raw_path_length_penalty)
        item["goal_switch_penalty_term"] = float(goal_switch_penalty)
        item["goal_switch_penalty_applied"] = bool(goal_switch_penalty > 0.0)
        item["alpha_focus"] = 0.0
        item["kappa_commit"] = 0.0
        item["same_anchor_cluster"] = bool(same_anchor_cluster)
        item["gateway_drift_norm"] = float(gateway_drift_norm)
        item["retain_anchor_bonus"] = float(retain_anchor_bonus)
        item["gateway_continuity_bonus"] = float(gateway_continuity_bonus)
        item["u_turn_penalty_term"] = float(u_turn_penalty)
        item["u_turn_penalty_applied"] = bool(u_turn_applied)
        item["first_move_dir"] = first_move_dir
        item["total_score"] = total_score
        item["candidate_count"] = len(evaluations)

    best = max(evaluations, key=lambda item: item["total_score"])
    current_item = None
    winner_margin_applied = False
    best_alternative_score = float(best["total_score"])
    current_goal_score = 0.0
    if current_goal is not None:
        current_item = next((item for item in evaluations if item["goal"] == current_goal), None)
        if current_item is not None:
            current_goal_score = float(current_item["total_score"])

    if (
        mode == SEARCH_MODE
        and current_item is not None
        and best["goal"] != current_goal
        and best["total_score"] <= current_item["total_score"] + float(winner_margin)
    ):
        best = current_item
        winner_margin_applied = True

    details = {
        "frontier_term_raw": float(best["frontier_term_raw"]),
        "frontier_term_norm": float(best["frontier_term_norm"]),
        "staleness_term_raw": float(best["staleness_term_raw"]),
        "staleness_term_norm": float(best["staleness_term_norm"]),
        "clue_term_raw": float(best["clue_term_raw"]),
        "clue_term_norm": float(best["clue_term_norm"]),
        "intensity_term_raw": float(best["intensity_term_raw"]),
        "intensity_term_norm": float(best["intensity_term_norm"]),
        "anchor_value_term_raw": float(best.get("anchor_value_term_raw", 0.0)),
        "anchor_value_term_norm": float(best.get("anchor_value_term_norm", 0.0)),
        "anchor_depth_term_raw": float(best.get("anchor_depth_term_raw", 0.0)),
        "anchor_depth_term_norm": float(best.get("anchor_depth_term_norm", 0.0)),
        "path_cost_term_raw": float(best["path_cost_term_raw"]),
        "path_cost_term_norm": float(best["path_cost_term_norm"]),
        "raw_path_length_penalty_term": float(best.get("raw_path_length_penalty_term", 0.0)),
        "goal_switch_penalty_term": float(best.get("goal_switch_penalty_term", 0.0)),
        "goal_switch_penalty_applied": bool(best.get("goal_switch_penalty_applied", False)),
        "winner_margin_term": float(winner_margin) if winner_margin_applied else 0.0,
        "winner_margin_applied": bool(winner_margin_applied),
        "alpha_focus": float(best.get("alpha_focus", 0.0)),
        "kappa_commit": 0.0,
        "same_anchor_cluster": bool(best.get("same_anchor_cluster", False)),
        "gateway_drift_norm": float(best.get("gateway_drift_norm", 0.0)),
        "retain_anchor_bonus": float(best.get("retain_anchor_bonus", 0.0)),
        "gateway_continuity_bonus": float(best.get("gateway_continuity_bonus", 0.0)),
        "u_turn_penalty_term": float(best.get("u_turn_penalty_term", 0.0)),
        "u_turn_penalty_applied": bool(best.get("u_turn_penalty_applied", False)),
        "first_move_dir": best.get("first_move_dir"),
        "candidate_count": int(best["candidate_count"]),
        "current_goal_score": float(current_goal_score),
        "best_alternative_score": float(best_alternative_score),
        "anchor_cell": best.get("anchor_cell"),
        "anchor_source": best.get("anchor_source"),
        "anchor_state": best.get("anchor_state"),
        "gateway_rule": best.get("gateway_rule"),
        "anchor_path_length": int(best.get("anchor_path_length", 0)),
        "gateway_path_length": int(best.get("gateway_path_length", 0)),
        "anchor_cluster_size": int(best.get("anchor_cluster_size", 0)),
        "anchor_cluster_peak": float(best.get("anchor_cluster_peak", 0.0)),
        "anchor_cluster_mean": float(best.get("anchor_cluster_mean", 0.0)),
        "anchor_centroid_cell": best.get("anchor_centroid_cell"),
        "total_score": float(best["total_score"]),
    }
    return best["goal"], best["path"], float(best["total_score"]), details


def select_goal_search_policy(
    policy_name: str,
    known_map: np.ndarray,
    robot_pos: tuple[int, int],
    covered_mask: np.ndarray,
    visited_count: np.ndarray,
    sensor_range: int,
    gp_reward_map: np.ndarray | None = None,
    staleness_map: np.ndarray | None = None,
    intensity_map: np.ndarray | None = None,
    current_goal: tuple[int, int] | None = None,
    current_anchor: tuple[int, int] | None = None,
    current_anchor_source: str | None = None,
    current_anchor_centroid: tuple[int, int] | None = None,
    prev_move_dir: tuple[int, int] | None = None,
    mode: str = SEARCH_MODE,
    lambda_switch: float = 0.5,
    winner_margin: float = 0.5,
    lambda_dist_raw: float = 0.05,
    lambda_u_turn: float = 2.0,
    kappa_commit: float = 0.0,
    unknown_cost: int = 3,
    top_k: int = 25,
    gamma: float = 0.95,
    top_k_frontier: int = 10,
    top_k_staleness: int = 10,
    top_k_clue: int = 10,
    top_k_intensity: int = 10,
) -> tuple[tuple[int, int] | None, list[tuple[int, int]] | None, float, dict]:
    """Select the next navigation goal using either legacy or marine policies."""
    if policy_name not in SUPPORTED_POLICIES:
        raise ValueError(f"Unsupported policy_name='{policy_name}'")

    if policy_name in LEGACY_POLICIES:
        return _select_legacy_goal(
            policy_name=policy_name,
            known_map=known_map,
            robot_pos=robot_pos,
            covered_mask=covered_mask,
            visited_count=visited_count,
            sensor_range=sensor_range,
            gp_reward_map=gp_reward_map,
            current_goal=current_goal,
            lambda_switch=lambda_switch,
            prev_move_dir=prev_move_dir,
            lambda_u_turn=lambda_u_turn,
            unknown_cost=unknown_cost,
            top_k=top_k,
        )

    return _select_marine_goal(
        policy_name=policy_name,
        known_map=known_map,
        robot_pos=robot_pos,
        covered_mask=covered_mask,
        visited_count=visited_count,
        sensor_range=sensor_range,
        staleness_map=staleness_map,
        clue_map=gp_reward_map,
        intensity_map=intensity_map,
        current_goal=current_goal,
        current_anchor=current_anchor,
        current_anchor_source=current_anchor_source,
        prev_move_dir=prev_move_dir,
        mode=mode,
        lambda_switch=lambda_switch,
        winner_margin=winner_margin,
        lambda_dist_raw=lambda_dist_raw,
        lambda_u_turn=lambda_u_turn,
        kappa_commit=kappa_commit,
        current_anchor_centroid=current_anchor_centroid,
        unknown_cost=unknown_cost,
        gamma=gamma,
        top_k_frontier=top_k_frontier,
        top_k_staleness=top_k_staleness,
        top_k_clue=top_k_clue,
        top_k_intensity=top_k_intensity,
    )


def _make_knownmap_zero_details() -> dict[str, object]:
    return {
        "explore_utility_raw": 0.0,
        "explore_utility_norm": 0.0,
        "focus_utility_raw": 0.0,
        "focus_utility_norm": 0.0,
        "recency_utility_raw": 0.0,
        "recency_utility_norm": 0.0,
        "search_info_gain_raw": 0.0,
        "search_info_gain_norm": 0.0,
        "recency_bias_raw": 0.0,
        "recency_bias_norm": 0.0,
        "exec_cost_raw": 0.0,
        "exec_cost_norm": 0.0,
        "obstacle_proximity_raw": 0.0,
        "clearance_penalty_raw": 0.0,
        "reservation_soft_penalty_raw": 0.0,
        "reservation_same_cell_violation": False,
        "reservation_swap_violation": False,
        "reservation_near_neighbor_step_ratio": 0.0,
        "segment_min_clearance_cells": 0.0,
        "segment_mean_clearance_cells": 0.0,
        "near_obstacle_step_flag": False,
        "near_obstacle_step_ratio": 0.0,
        "segment_turn_count": 0,
        "path_safety_mode": "off",
        "safe_nav_lambda_clearance": 0.0,
        "team_reservation_lambda": 0.0,
        "alpha_focus": 0.0,
        "kappa_commit": 0.0,
        "same_anchor_cluster": False,
        "viewpoint_drift_norm": 0.0,
        "anchor_retention_bonus": 0.0,
        "viewpoint_retention_bonus": 0.0,
        "candidate_count": 0,
        "candidate_pool_size": 0,
        "reachable_pool_size": 0,
        "a_star_checked_pool_size": 0,
        "selected_viewpoint_rank": 0,
        "sampling_priority_raw": 0.0,
        "sampling_priority_norm": 0.0,
        "viewpoint_sampling_mode": None,
        "sampled_viewpoint_pool_cells": [],
        "selected_by_final_score": False,
        "sssp_build_time_ms": 0.0,
        "path_reconstruct_time_ms": 0.0,
        "sampling_pool_build_time_ms": 0.0,
        "priority_feature_time_ms": 0.0,
        "current_viewpoint_score": 0.0,
        "best_alternative_score": 0.0,
        "anchor_cell": None,
        "anchor_source": None,
        "anchor_centroid_cell": None,
        "anchor_cluster_size": 0,
        "anchor_cluster_peak": 0.0,
        "anchor_cluster_mean": 0.0,
        "anchor_info_clue_share": 0.0,
        "anchor_info_intensity_share": 0.0,
        "viewpoint_cell": None,
        "viewpoint_rule": None,
        "segment_endpoint_cell": None,
        "segment_path_length": 0,
        "planned_viewpoint_path_length": 0,
        "first_move_dir": None,
        "u_turn_penalty_term": 0.0,
        "u_turn_penalty_applied": False,
        "score_schema": "knownmap_legacy",
        "total_score": -float("inf"),
        "tree_depth": 1,
        "tree_first_layer_top_m": 0,
        "tree_second_layer_top_n": 0,
        "tree_discount_gamma": 0.0,
        "tree_enable_diminishing_returns": False,
        "tree_root_rank": 0,
        "tree_child_rank": 0,
        "tree_root_score_raw": 0.0,
        "tree_child_score_raw": 0.0,
        "tree_total_score": 0.0,
        "tree_conditional_gain_lvl2": 0.0,
        "tree_redundant_visible_ratio_lvl2": 0.0,
        "tree_unique_visible_count_lvl1": 0,
        "tree_unique_visible_count_lvl2": 0,
        "tree_expansion_count": 0,
        "tree_planning_time_ms": 0.0,
        "tree_child_viewpoint_cell": None,
        "tree_child_endpoint_cell": None,
        "tree_child_oracle_score_raw": 0.0,
        "tree_child_budget_score_raw": 0.0,
        "tree_child_oracle_gap_raw": 0.0,
        "tree_child_oracle_rank_of_budgeted": 0,
        "tree_child_budget_matches_oracle": False,
        "tree_child_oracle_viewpoint_cell": None,
        "tree_child_budget_viewpoint_cell": None,
        "tree_child_full_candidate_count": 0,
        "marginal_information_gain_raw": 0.0,
        "marginal_information_gain_norm": 0.0,
        "execution_cost_raw": 0.0,
        "execution_cost_norm": 0.0,
        "continuity_bonus_raw": 0.0,
        "continuity_bonus_anchor_raw": 0.0,
        "continuity_bonus_viewpoint_raw": 0.0,
        "marginal_information_gain_score_term": 0.0,
        "recency_bias_score_term": 0.0,
        "execution_cost_score_term": 0.0,
        "continuity_bonus_score_term": 0.0,
        "maneuver_penalty_raw": 0.0,
        "maneuver_penalty_score_term": 0.0,
        "score_formula_label": None,
    }


def _knownmap_visible_free_cells(
    pos: tuple[int, int],
    nav_map_prior: np.ndarray,
    sensor_range: int,
) -> list[tuple[int, int]]:
    return [
        (x, y)
        for x, y in sensor_cells(pos, nav_map_prior.shape, sensor_range)
        if nav_map_prior[x, y] == FREE
    ]


def _knownmap_neighbor_obstacle_count(
    nav_map_prior: np.ndarray,
    cell: tuple[int, int],
) -> int:
    x, y = cell
    h, w = nav_map_prior.shape
    total = 0
    for nx in range(max(0, x - 1), min(h, x + 2)):
        for ny in range(max(0, y - 1), min(w, y + 2)):
            if (nx, ny) == cell:
                continue
            if nav_map_prior[nx, ny] == OCCUPIED:
                total += 1
    return total


def _knownmap_precompute_viewpoint_geometry_cache(
    nav_map_prior: np.ndarray,
    sensor_range: int,
) -> dict[str, object]:
    obstacle_neighbor_count_map = np.zeros_like(nav_map_prior, dtype=np.int16)
    visible_free_flat_indices: dict[tuple[int, int], np.ndarray] = {}
    width = int(nav_map_prior.shape[1])
    free_cells = np.argwhere(nav_map_prior == FREE)
    for x, y in free_cells:
        cell = (int(x), int(y))
        obstacle_neighbor_count_map[cell] = _knownmap_neighbor_obstacle_count(nav_map_prior, cell)
        visible_cells = _knownmap_visible_free_cells(cell, nav_map_prior, sensor_range)
        visible_free_flat_indices[cell] = np.asarray(
            [int(cx) * width + int(cy) for cx, cy in visible_cells],
            dtype=np.int32,
        )
    return {
        "visible_free_flat_indices": visible_free_flat_indices,
        "obstacle_neighbor_count_map": obstacle_neighbor_count_map,
    }


def _knownmap_visible_flat_indices_for_cell(
    cell: tuple[int, int],
    nav_map_prior: np.ndarray,
    sensor_range: int,
    geometry_cache: dict[str, object] | None,
) -> np.ndarray:
    if geometry_cache is not None:
        visible_lookup = geometry_cache.get("visible_free_flat_indices")
        if isinstance(visible_lookup, dict) and cell in visible_lookup:
            return np.asarray(visible_lookup[cell], dtype=np.int32)
    width = int(nav_map_prior.shape[1])
    return np.asarray(
        [int(x) * width + int(y) for x, y in _knownmap_visible_free_cells(cell, nav_map_prior, sensor_range)],
        dtype=np.int32,
    )


def _knownmap_obstacle_proximity_penalty(
    nav_map_prior: np.ndarray,
    path: list[tuple[int, int]],
) -> float:
    if len(path) <= 1:
        return 0.0
    penalties = [
        float(_knownmap_neighbor_obstacle_count(nav_map_prior, cell))
        for cell in path[1:]
    ]
    return float(np.mean(penalties)) if penalties else 0.0


def _knownmap_nearest_free_cell(
    nav_map_prior: np.ndarray,
    cell: tuple[int, int],
) -> tuple[int, int] | None:
    free_cells = np.argwhere(nav_map_prior == FREE)
    if free_cells.size == 0:
        return None
    diffs = free_cells - np.asarray(cell, dtype=float)
    distances = np.sum(diffs * diffs, axis=1)
    idx = int(np.argmin(distances))
    return (int(free_cells[idx, 0]), int(free_cells[idx, 1]))


def _knownmap_viewpoint_cells_for_anchor(
    nav_map_prior: np.ndarray,
    anchor_cell: tuple[int, int],
    sensor_range: int,
    max_candidates: int,
) -> list[tuple[int, int]]:
    if max_candidates <= 0:
        return []
    free_cells = np.argwhere(nav_map_prior == FREE)
    if free_cells.size == 0:
        return []

    preferred_radius = max(1.0, 0.75 * float(sensor_range))
    min_radius = max(1.0, 0.35 * float(sensor_range))
    scored: list[tuple[float, int, int, tuple[int, int]]] = []
    for x, y in free_cells:
        cell = (int(x), int(y))
        dist = math.hypot(cell[0] - anchor_cell[0], cell[1] - anchor_cell[1])
        if dist > float(sensor_range) or dist < min_radius:
            continue
        ring_penalty = abs(dist - preferred_radius)
        obstacle_penalty = _knownmap_neighbor_obstacle_count(nav_map_prior, cell)
        scored.append((ring_penalty, obstacle_penalty, cell[0], cell[1], cell))

    if not scored:
        nearest_free = _knownmap_nearest_free_cell(nav_map_prior, anchor_cell)
        return [nearest_free] if nearest_free is not None else []

    scored.sort()
    candidates = []
    seen = set()
    for *_prefix, cell in scored:
        if cell in seen:
            continue
        seen.add(cell)
        candidates.append(cell)
        if len(candidates) >= max_candidates:
            break
    return candidates


def _knownmap_local_free_cells(
    nav_map_prior: np.ndarray,
    center: tuple[int, int],
    max_radius: float,
) -> list[tuple[int, int]]:
    h, w = nav_map_prior.shape
    radius_int = max(1, int(math.ceil(float(max_radius))))
    cells: list[tuple[int, int]] = []
    for x in range(max(0, center[0] - radius_int), min(h, center[0] + radius_int + 1)):
        for y in range(max(0, center[1] - radius_int), min(w, center[1] + radius_int + 1)):
            cell = (int(x), int(y))
            if nav_map_prior[cell] != FREE:
                continue
            if _cells_distance(center, cell) > float(max_radius):
                continue
            cells.append(cell)
    return cells


def _knownmap_single_source_shortest_path_tree(
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
) -> dict[str, object]:
    reachable_free_mask = np.zeros(nav_map_prior.shape, dtype=bool)
    distance_map = np.full(nav_map_prior.shape, np.inf, dtype=float)
    parent_row_map = np.full(nav_map_prior.shape, -1, dtype=np.int32)
    parent_col_map = np.full(nav_map_prior.shape, -1, dtype=np.int32)
    if nav_map_prior[robot_pos] != FREE:
        return {
            "reachable_free_mask": reachable_free_mask,
            "distance_map": distance_map,
            "parent_row_map": parent_row_map,
            "parent_col_map": parent_col_map,
        }

    queue: deque[tuple[int, int]] = deque([robot_pos])
    reachable_free_mask[robot_pos] = True
    distance_map[robot_pos] = 0.0
    while queue:
        current = queue.popleft()
        current_distance = float(distance_map[current])
        for nb in neighbors4(current, nav_map_prior):
            if nav_map_prior[nb] != FREE or reachable_free_mask[nb]:
                continue
            reachable_free_mask[nb] = True
            distance_map[nb] = current_distance + 1.0
            parent_row_map[nb] = int(current[0])
            parent_col_map[nb] = int(current[1])
            queue.append(nb)

    return {
        "reachable_free_mask": reachable_free_mask,
        "distance_map": distance_map,
        "parent_row_map": parent_row_map,
        "parent_col_map": parent_col_map,
    }


def _knownmap_reconstruct_path_from_tree(
    parent_row_map: np.ndarray,
    parent_col_map: np.ndarray,
    robot_pos: tuple[int, int],
    goal_cell: tuple[int, int],
) -> list[tuple[int, int]] | None:
    if goal_cell == robot_pos:
        return [tuple(int(v) for v in robot_pos)]
    if (
        int(parent_row_map[goal_cell]) < 0
        or int(parent_col_map[goal_cell]) < 0
    ):
        return None

    path = [tuple(int(v) for v in goal_cell)]
    current = tuple(int(v) for v in goal_cell)
    while current != robot_pos:
        parent = (
            int(parent_row_map[current]),
            int(parent_col_map[current]),
        )
        if parent[0] < 0 or parent[1] < 0:
            return None
        path.append(parent)
        current = parent
    path.reverse()
    return path


def _knownmap_reachable_free_mask(
    nav_map_prior: np.ndarray,
    start: tuple[int, int],
) -> np.ndarray:
    tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, start)
    return np.asarray(tree["reachable_free_mask"], dtype=bool)


def _anchor_sampling_rng(
    sampling_seed_base: int,
    anchor_centroid_cell: tuple[int, int],
    mode_tag: int,
) -> np.random.Generator:
    seed = (
        int(sampling_seed_base) * 2654435761
        + int(anchor_centroid_cell[0]) * 73856093
        + int(anchor_centroid_cell[1]) * 19349663
        + int(mode_tag) * 83492791
    ) & 0xFFFFFFFF
    return np.random.default_rng(seed)


def _weighted_sample_cells(
    cells: list[tuple[int, int]],
    weights: list[float],
    sample_count: int,
    rng: np.random.Generator,
) -> list[tuple[int, int]]:
    if sample_count <= 0 or not cells:
        return []
    if len(cells) <= sample_count:
        return list(cells)
    weight_arr = np.asarray(weights, dtype=float)
    weight_arr = np.where(np.isfinite(weight_arr), np.maximum(weight_arr, 0.0), 0.0)
    if float(np.sum(weight_arr)) <= 1e-12:
        probs = None
    else:
        probs = weight_arr / float(np.sum(weight_arr))
    indices = rng.choice(len(cells), size=int(sample_count), replace=False, p=probs)
    return [cells[int(idx)] for idx in indices]


def _visible_overlap_ratio(
    candidate_visible_cells: list[tuple[int, int]],
    current_visible_cells: set[tuple[int, int]],
) -> float:
    if not candidate_visible_cells or not current_visible_cells:
        return 0.0
    overlap = sum(1 for cell in candidate_visible_cells if cell in current_visible_cells)
    return float(overlap) / float(max(1, len(candidate_visible_cells)))


def _sample_viewpoint_pool_for_anchor(
    nav_map_prior: np.ndarray,
    anchor_cluster: dict[str, object],
    sensor_range: int,
    max_pool_size: int,
    sampling_seed_base: int,
    search_info_map: np.ndarray | None,
    current_viewpoint: tuple[int, int] | None,
    current_segment_endpoint: tuple[int, int] | None,
    geometry_cache: dict[str, object] | None,
) -> list[dict[str, object]]:
    if max_pool_size <= 0:
        return []
    anchor_cell = tuple(int(v) for v in anchor_cluster["anchor_cell"])
    anchor_centroid_cell = tuple(int(v) for v in anchor_cluster["anchor_centroid_cell"])
    preferred_radius = max(1.0, 0.75 * float(sensor_range))
    min_radius = max(1.0, 0.30 * float(sensor_range))
    max_radius = max(preferred_radius + 2.0, 1.5 * float(sensor_range))
    local_free_cells = [
        cell
        for cell in _knownmap_local_free_cells(nav_map_prior, anchor_centroid_cell, max_radius=max_radius)
        if _cells_distance(anchor_centroid_cell, cell) >= min_radius
    ]
    if not local_free_cells:
        nearest_free = _knownmap_nearest_free_cell(nav_map_prior, anchor_centroid_cell)
        if nearest_free is None:
            return []
        return [{"viewpoint_cell": nearest_free, "viewpoint_sampling_mode": "nearest_free"}]

    shell_count = max(4, int(math.ceil(max_pool_size / 3.0)))
    continuity_count = max(2, int(math.ceil(max_pool_size / 4.0)))
    info_count = max(4, max_pool_size - shell_count - continuity_count)

    shell_ranked = sorted(
        local_free_cells,
        key=lambda cell: (
            abs(_cells_distance(anchor_cell, cell) - preferred_radius),
            int(geometry_cache["obstacle_neighbor_count_map"][cell])
            if geometry_cache is not None
            else _knownmap_neighbor_obstacle_count(nav_map_prior, cell),
            cell[0],
            cell[1],
        ),
    )
    shell_samples = shell_ranked[:shell_count]

    info_weights = []
    for cell in local_free_cells:
        info_value = 0.0 if search_info_map is None else float(max(0.0, search_info_map[cell]))
        dist_match = max(0.0, 1.0 - abs(_cells_distance(anchor_cell, cell) - preferred_radius) / preferred_radius)
        info_weights.append(info_value + 0.05 * dist_match + 1e-6)
    info_rng = _anchor_sampling_rng(sampling_seed_base, anchor_centroid_cell, mode_tag=2)
    info_samples = _weighted_sample_cells(local_free_cells, info_weights, info_count, info_rng)

    continuity_samples: list[tuple[int, int]] = []
    if current_viewpoint is not None and nav_map_prior[current_viewpoint] == FREE:
        continuity_cells = [
            cell
            for cell in local_free_cells
            if _cells_distance(current_viewpoint, cell) <= max(2.0, 0.75 * float(sensor_range))
        ]
        continuity_weights = [
            max(0.0, 1.0 - _cells_distance(current_viewpoint, cell) / max(1.0, float(sensor_range)))
            + 1e-6
            for cell in continuity_cells
        ]
        continuity_rng = _anchor_sampling_rng(sampling_seed_base, anchor_centroid_cell, mode_tag=3)
        continuity_samples = _weighted_sample_cells(
            continuity_cells,
            continuity_weights,
            continuity_count,
            continuity_rng,
        )

    pool_by_cell: dict[tuple[int, int], str] = {}
    anchor_nearest_free = _knownmap_nearest_free_cell(nav_map_prior, anchor_centroid_cell)
    if anchor_nearest_free is not None:
        pool_by_cell.setdefault(anchor_nearest_free, "nearest_anchor_free")
    if current_segment_endpoint is not None and nav_map_prior[current_segment_endpoint] == FREE:
        pool_by_cell.setdefault(tuple(int(v) for v in current_segment_endpoint), "current_segment_endpoint")
    if current_viewpoint is not None and nav_map_prior[current_viewpoint] == FREE:
        pool_by_cell.setdefault(tuple(int(v) for v in current_viewpoint), "current_viewpoint")
    for cell in shell_samples:
        pool_by_cell.setdefault(cell, "shell")
    for cell in info_samples:
        pool_by_cell.setdefault(cell, "info_perturb")
    for cell in continuity_samples:
        pool_by_cell.setdefault(cell, "continuity_biased")

    mode_priority = {
        "current_viewpoint": 0,
        "current_segment_endpoint": 1,
        "nearest_anchor_free": 2,
        "continuity_biased": 3,
        "shell": 4,
        "info_perturb": 5,
        "nearest_free": 6,
    }
    ordered_cells = list(pool_by_cell.keys())
    ordered_cells.sort(
        key=lambda cell: (
            int(mode_priority.get(pool_by_cell[cell], 99)),
            cell[0],
            cell[1],
        )
    )
    return [
        {
            "viewpoint_cell": cell,
            "viewpoint_sampling_mode": pool_by_cell[cell],
        }
        for cell in ordered_cells[:max_pool_size]
    ]


def _infosampled_priority_breakdown(
    viewpoint_cell: tuple[int, int],
    *,
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    anchor_cell: tuple[int, int],
    sensor_range: int,
    search_info_flat: np.ndarray | None,
    staleness_flat: np.ndarray | None,
    current_viewpoint: tuple[int, int] | None,
    current_visible_flat_mask: np.ndarray | None,
    geometry_cache: dict[str, object] | None,
) -> dict[str, object] | None:
    visible_flat_indices = _knownmap_visible_flat_indices_for_cell(
        viewpoint_cell,
        nav_map_prior,
        sensor_range,
        geometry_cache,
    )
    if visible_flat_indices.size == 0:
        return None
    search_info_coverage = 0.0
    if search_info_flat is not None:
        search_info_coverage = float(np.mean(search_info_flat[visible_flat_indices]))
    stale_bias = 0.0
    if staleness_flat is not None:
        stale_bias = float(np.mean(staleness_flat[visible_flat_indices]))
    preferred_radius = max(1.0, 0.75 * float(sensor_range))
    anchor_dist = _cells_distance(anchor_cell, viewpoint_cell)
    anchor_distance_match = max(0.0, 1.0 - abs(anchor_dist - preferred_radius) / preferred_radius)
    continuity_bonus = 0.0
    if current_viewpoint is not None:
        continuity_bonus = max(
            0.0,
            1.0 - _cells_distance(current_viewpoint, viewpoint_cell) / max(1.0, float(sensor_range)),
        )
    if geometry_cache is not None:
        obstacle_penalty = float(geometry_cache["obstacle_neighbor_count_map"][viewpoint_cell])
    else:
        obstacle_penalty = float(_knownmap_neighbor_obstacle_count(nav_map_prior, viewpoint_cell))
    overlap_penalty = 0.0
    if current_visible_flat_mask is not None and current_visible_flat_mask.size > 0:
        overlap_penalty = float(np.mean(current_visible_flat_mask[visible_flat_indices]))
    path_cost_proxy = float(
        abs(int(viewpoint_cell[0]) - int(robot_pos[0]))
        + abs(int(viewpoint_cell[1]) - int(robot_pos[1]))
    )
    priority_raw = (
        1.80 * search_info_coverage
        + 0.60 * anchor_distance_match
        + 0.40 * continuity_bonus
        + 0.35 * stale_bias
        - 0.05 * path_cost_proxy
        - 0.10 * obstacle_penalty
        - 0.35 * overlap_penalty
    )
    return {
        "viewpoint_cell": viewpoint_cell,
        "sampling_priority_raw": float(priority_raw),
        "path_cost_proxy": float(path_cost_proxy),
        "search_info_coverage": float(search_info_coverage),
        "stale_bias": float(stale_bias),
        "anchor_distance_match": float(anchor_distance_match),
        "continuity_bonus": float(continuity_bonus),
        "overlap_penalty": float(overlap_penalty),
        "obstacle_penalty": float(obstacle_penalty),
    }


def _rank_infosampled_viewpoints(
    sample_pool: list[dict[str, object]],
    *,
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    anchor_cluster: dict[str, object],
    sensor_range: int,
    search_info_map: np.ndarray | None,
    staleness_map: np.ndarray | None,
    current_viewpoint: tuple[int, int] | None,
    sssp_tree: dict[str, object] | None,
    geometry_cache: dict[str, object] | None = None,
    top_k: int,
    inspected_limit_multiplier: float = 3.0,
    inspected_limit_floor: int = 4,
) -> tuple[list[dict[str, object]], dict[str, float]]:
    if top_k <= 0 or not sample_pool:
        return [], {"priority_feature_time_ms": 0.0, "path_reconstruct_time_ms": 0.0}
    current_visible_flat_mask = np.zeros(nav_map_prior.size, dtype=bool)
    if current_viewpoint is not None and nav_map_prior[current_viewpoint] == FREE:
        current_visible_flat_indices = _knownmap_visible_flat_indices_for_cell(
            current_viewpoint,
            nav_map_prior,
            sensor_range,
            geometry_cache,
        )
        current_visible_flat_mask[current_visible_flat_indices] = True
    search_info_flat = None if search_info_map is None else np.ravel(search_info_map)
    staleness_flat = None if staleness_map is None else np.ravel(staleness_map)
    ranked_pool: list[dict[str, object]] = []
    priority_feature_time_ms = 0.0
    for sampled in sample_pool:
        viewpoint_cell = tuple(int(v) for v in sampled["viewpoint_cell"])
        t0 = time.perf_counter()
        breakdown = _infosampled_priority_breakdown(
            viewpoint_cell,
            nav_map_prior=nav_map_prior,
            robot_pos=robot_pos,
            anchor_cell=tuple(int(v) for v in anchor_cluster["anchor_cell"]),
            sensor_range=sensor_range,
            search_info_flat=search_info_flat,
            staleness_flat=staleness_flat,
            current_viewpoint=current_viewpoint,
            current_visible_flat_mask=current_visible_flat_mask,
            geometry_cache=geometry_cache,
        )
        priority_feature_time_ms += (time.perf_counter() - t0) * 1000.0
        if breakdown is None:
            continue
        ranked_pool.append(
            {
                **sampled,
                **breakdown,
            }
        )
    if not ranked_pool:
        return [], {
            "priority_feature_time_ms": float(priority_feature_time_ms),
            "path_reconstruct_time_ms": 0.0,
        }
    norm_values = _normalize_term([float(item["sampling_priority_raw"]) for item in ranked_pool])
    for item, norm_value in zip(ranked_pool, norm_values):
        item["sampling_priority_norm"] = float(norm_value)
    ranked_pool.sort(
        key=lambda item: (
            float(item["sampling_priority_raw"]),
            -float(item["path_cost_proxy"]),
            -float(item["overlap_penalty"]),
        ),
        reverse=True,
    )
    pool_cells = [
        tuple(int(v) for v in sampled["viewpoint_cell"])
        for sampled in sample_pool
    ]
    if sssp_tree is None:
        sssp_tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
    reachable_free_mask = np.asarray(sssp_tree["reachable_free_mask"], dtype=bool)
    parent_row_map = np.asarray(sssp_tree["parent_row_map"])
    parent_col_map = np.asarray(sssp_tree["parent_col_map"])
    reachable_pool_size = int(
        sum(1 for cell in pool_cells if bool(reachable_free_mask[cell]))
    )
    reachable_ranked_pool: list[dict[str, object]] = []
    for rank_idx, item in enumerate(ranked_pool, start=1):
        viewpoint_cell = tuple(int(v) for v in item["viewpoint_cell"])
        if not bool(reachable_free_mask[viewpoint_cell]):
            continue
        reachable_ranked_pool.append(
            {
                **item,
                "selected_viewpoint_rank": int(rank_idx),
            }
        )
    inspected_limit = min(
        len(reachable_ranked_pool),
        max(int(inspected_limit_floor), int(math.ceil(float(inspected_limit_multiplier) * max(1, top_k)))),
    )
    reachable_ranked: list[dict[str, object]] = []
    reconstruct_time_ms = 0.0
    for item in reachable_ranked_pool[:inspected_limit]:
        t0 = time.perf_counter()
        full_path = _knownmap_reconstruct_path_from_tree(
            parent_row_map,
            parent_col_map,
            robot_pos,
            tuple(int(v) for v in item["viewpoint_cell"]),
        )
        reconstruct_time_ms += (time.perf_counter() - t0) * 1000.0
        if full_path is None or len(full_path) <= 1:
            continue
        reachable_ranked.append(
            {
                **item,
                "path_to_viewpoint": list(full_path),
            }
        )
    selected: list[dict[str, object]] = []
    for item in reachable_ranked[:top_k]:
        selected.append(
            {
                **item,
                "candidate_pool_size": int(len(sample_pool)),
                "reachable_pool_size": reachable_pool_size,
                "a_star_checked_pool_size": int(inspected_limit),
                "sampled_viewpoint_pool_cells": list(pool_cells),
            }
        )
    return selected, {
        "priority_feature_time_ms": float(priority_feature_time_ms),
        "path_reconstruct_time_ms": float(reconstruct_time_ms),
    }


def _truncate_segment_path(
    path: list[tuple[int, int]],
    segment_horizon: int,
) -> list[tuple[int, int]]:
    if not path:
        return []
    horizon = max(1, int(segment_horizon))
    end_idx = min(len(path) - 1, horizon)
    return list(path[: end_idx + 1])


def _path_turn_count(path: list[tuple[int, int]]) -> int:
    if len(path) <= 2:
        return 0
    turn_count = 0
    prev_dir = move_direction(path[0], path[1])
    for idx in range(1, len(path) - 1):
        curr_dir = move_direction(path[idx], path[idx + 1])
        if curr_dir != prev_dir:
            turn_count += 1
        prev_dir = curr_dir
    return int(turn_count)


def _path_last_move_dir(path: list[tuple[int, int]]) -> tuple[int, int] | None:
    if len(path) <= 1:
        return None
    return move_direction(path[-2], path[-1])


def _knownmap_clearance_diagnostics(
    segment_path: list[tuple[int, int]],
    obstacle_distance_map: np.ndarray | None,
    clearance_cost_map: np.ndarray | None,
    soft_clearance_radius_cells: int,
) -> dict[str, float | bool]:
    step_cells = list(segment_path[1:])
    if not step_cells or obstacle_distance_map is None:
        return {
            "clearance_penalty_raw": 0.0,
            "segment_min_clearance_cells": 0.0,
            "segment_mean_clearance_cells": 0.0,
            "near_obstacle_step_flag": False,
            "near_obstacle_step_ratio": 0.0,
        }

    raw_distances = []
    clearance_costs = []
    finite_fallback = float(max(obstacle_distance_map.shape))
    for cell in step_cells:
        raw_distance = float(obstacle_distance_map[cell])
        if not np.isfinite(raw_distance):
            raw_distance = finite_fallback
        raw_distances.append(raw_distance)
        if clearance_cost_map is not None:
            clearance_costs.append(float(clearance_cost_map[cell]))

    near_radius = max(0, int(soft_clearance_radius_cells))
    near_count = (
        sum(1 for distance in raw_distances if distance <= float(near_radius))
        if near_radius > 0
        else 0
    )
    return {
        "clearance_penalty_raw": float(np.mean(clearance_costs)) if clearance_costs else 0.0,
        "segment_min_clearance_cells": float(min(raw_distances)),
        "segment_mean_clearance_cells": float(np.mean(raw_distances)),
        "near_obstacle_step_flag": bool(near_count > 0),
        "near_obstacle_step_ratio": float(near_count) / float(len(step_cells)),
    }


def _knownmap_segment_score_breakdown(
    segment_path: list[tuple[int, int]],
    nav_map_prior: np.ndarray,
    sensor_range: int,
    last_seen_step: np.ndarray,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    anchor_cell: tuple[int, int],
    viewpoint_cell: tuple[int, int],
    gamma: float,
    search_info_map: np.ndarray | None = None,
    pre_seen_cells: set[tuple[int, int]] | None = None,
    geometry_cache: dict[str, object] | None = None,
    path_safety_mode: str = "off",
    obstacle_distance_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_soft_clearance_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> dict[str, float]:
    # Phase 5-lite semantic note:
    # `search_info_gain` is the implemented marginal-information proxy for the
    # infosampled/infofused line. It is still built from path-level visible-cell
    # evidence plus local progress shaping, while `recency_bias` remains a
    # revisit bias and continuity stays outside this breakdown.
    prior_seen_cells = set(pre_seen_cells or ())
    seen_cells: set[tuple[int, int]] = set(prior_seen_cells)
    segment_visible_cells: set[tuple[int, int]] = set()
    explore_total = 0.0
    focus_total = 0.0
    recency_total = 0.0
    width = int(nav_map_prior.shape[1])

    for step_idx, waypoint in enumerate(segment_path[1:], start=0):
        discount = float(gamma) ** float(step_idx)
        visible_flat_indices = _knownmap_visible_flat_indices_for_cell(
            waypoint,
            nav_map_prior,
            sensor_range,
            geometry_cache,
        )
        if visible_flat_indices.size == 0:
            continue

        new_unobserved_count = 0
        evidence_values = []
        recency_values = []
        for flat_idx in visible_flat_indices:
            flat_int = int(flat_idx)
            cell = (flat_int // width, flat_int % width)
            segment_visible_cells.add(cell)
            if cell in seen_cells:
                continue
            seen_cells.add(cell)
            if last_seen_step[cell] < 0:
                new_unobserved_count += 1
            evidence_value = 0.0
            if search_info_map is not None:
                evidence_value = float(search_info_map[cell])
            else:
                if clue_map is not None:
                    evidence_value += 0.5 * float(clue_map[cell])
                if intensity_map is not None:
                    evidence_value += 0.5 * float(intensity_map[cell])
            evidence_values.append(evidence_value)
            if staleness_map is not None and last_seen_step[cell] >= 0:
                recency_values.append(float(staleness_map[cell]))

        explore_total += discount * float(new_unobserved_count)
        if evidence_values:
            focus_total += discount * float(np.mean(evidence_values))
        if recency_values:
            recency_total += discount * float(np.mean(recency_values))

    segment_endpoint = segment_path[-1]
    anchor_dist = _cells_distance(segment_endpoint, anchor_cell)
    viewpoint_dist = _cells_distance(segment_endpoint, viewpoint_cell)
    anchor_progress = max(
        0.0,
        1.0 - anchor_dist / float(max(1, sensor_range + len(segment_path) - 1)),
    )
    viewpoint_progress = max(
        0.0,
        1.0 - viewpoint_dist / float(max(1, len(segment_path) - 1)),
    )
    focus_total += 0.50 * anchor_progress + 0.30 * viewpoint_progress
    if _cells_distance(viewpoint_cell, anchor_cell) <= float(sensor_range):
        focus_total += 0.20

    obstacle_proximity = _knownmap_obstacle_proximity_penalty(nav_map_prior, segment_path)
    turn_count = _path_turn_count(segment_path)
    clearance_terms = _knownmap_clearance_diagnostics(
        segment_path=segment_path,
        obstacle_distance_map=obstacle_distance_map,
        clearance_cost_map=clearance_cost_map,
        soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
    )
    reservation_terms = evaluate_path_against_reservation(segment_path, reservation_table)
    if path_safety_mode == "soft_clearance_astar_v1":
        exec_cost = (
            float(len(segment_path) - 1)
            + 0.25 * float(turn_count)
            + float(safe_nav_lambda_clearance) * float(clearance_terms["clearance_penalty_raw"])
            + float(team_reservation_lambda)
            * float(reservation_terms["reservation_soft_penalty_raw"])
        )
    else:
        exec_cost = (
            float(len(segment_path) - 1)
            + 0.35 * obstacle_proximity
            + 0.25 * float(turn_count)
            + float(team_reservation_lambda)
            * float(reservation_terms["reservation_soft_penalty_raw"])
        )
    search_info_gain = float(explore_total + focus_total)
    recency_bias = float(recency_total)
    unique_visible_count = int(len(segment_visible_cells - prior_seen_cells))
    redundant_visible_count = int(len(segment_visible_cells & prior_seen_cells))
    redundant_visible_ratio = (
        float(redundant_visible_count) / float(max(1, len(segment_visible_cells)))
        if segment_visible_cells
        else 0.0
    )
    return {
        "explore_utility_raw": float(explore_total),
        "focus_utility_raw": float(focus_total),
        "recency_utility_raw": float(recency_total),
        "search_info_gain_raw": float(search_info_gain),
        "recency_bias_raw": float(recency_bias),
        "exec_cost_raw": float(exec_cost),
        "obstacle_proximity_raw": float(obstacle_proximity),
        "clearance_penalty_raw": float(clearance_terms["clearance_penalty_raw"]),
        "reservation_soft_penalty_raw": float(
            reservation_terms["reservation_soft_penalty_raw"]
        ),
        "reservation_same_cell_violation": bool(
            reservation_terms["same_cell_violation"]
        ),
        "reservation_swap_violation": bool(reservation_terms["swap_violation"]),
        "reservation_near_neighbor_step_ratio": float(
            reservation_terms["near_neighbor_step_ratio"]
        ),
        "segment_min_clearance_cells": float(clearance_terms["segment_min_clearance_cells"]),
        "segment_mean_clearance_cells": float(clearance_terms["segment_mean_clearance_cells"]),
        "near_obstacle_step_flag": bool(clearance_terms["near_obstacle_step_flag"]),
        "near_obstacle_step_ratio": float(clearance_terms["near_obstacle_step_ratio"]),
        "segment_turn_count": int(turn_count),
        "segment_visible_cells": set(segment_visible_cells),
        "unique_visible_count": unique_visible_count,
        "redundant_visible_count": redundant_visible_count,
        "redundant_visible_ratio": float(redundant_visible_ratio),
    }


def _knownmap_anchor_clusters(
    score_map: np.ndarray | None,
    nav_map_prior: np.ndarray,
    anchor_source: str,
    top_k: int,
    clue_component_map: np.ndarray | None = None,
    intensity_component_map: np.ndarray | None = None,
) -> list[dict[str, object]]:
    if top_k <= 0 or score_map is None:
        return []
    anchor_mask = (nav_map_prior == FREE) & np.isfinite(np.asarray(score_map, dtype=float))
    clusters = _cluster_hotspots(score_map, anchor_mask, top_k=top_k)
    for cluster in clusters:
        cluster["anchor_source"] = anchor_source
        clue_share, intensity_share = _knownmap_anchor_info_shares(
            tuple(int(v) for v in cluster["anchor_cell"]),
            clue_component_map,
            intensity_component_map,
        )
        cluster["anchor_info_clue_share"] = float(clue_share)
        cluster["anchor_info_intensity_share"] = float(intensity_share)
    return clusters


def _knownmap_segment_candidate(
    anchor_cluster: dict[str, object],
    viewpoint_cell: tuple[int, int],
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    segment_horizon: int,
    viewpoint_rule: str,
    precomputed_path: list[tuple[int, int]] | None = None,
    candidate_metadata: dict[str, object] | None = None,
    path_safety_mode: str = "off",
    inflated_nav_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_inflation_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> dict[str, object] | None:
    use_safe_backend = bool(
        path_safety_mode == "soft_clearance_astar_v1" or reservation_table is not None
    )
    if use_safe_backend:
        resolved_inflated_nav_map = (
            np.asarray(nav_map_prior)
            if inflated_nav_map is None
            else np.asarray(inflated_nav_map)
        )
        resolved_clearance_cost_map = (
            np.zeros(nav_map_prior.shape, dtype=float)
            if clearance_cost_map is None
            else np.asarray(clearance_cost_map, dtype=float)
        )
        resolved_lambda_clearance = (
            float(safe_nav_lambda_clearance)
            if path_safety_mode == "soft_clearance_astar_v1"
            else 0.0
        )
        if (
            precomputed_path is not None
            and reservation_table is None
            and int(safe_nav_inflation_radius_cells) <= 0
            and abs(float(resolved_lambda_clearance)) <= 1e-12
        ):
            full_path = list(precomputed_path)
        else:
            full_path = a_star_safe(
                nav_map_prior,
                robot_pos,
                viewpoint_cell,
                inflated_nav_map=resolved_inflated_nav_map,
                clearance_cost_map=resolved_clearance_cost_map,
                lambda_clearance=resolved_lambda_clearance,
                reservation_table=reservation_table,
                team_reservation_lambda=team_reservation_lambda,
            )
    else:
        full_path = list(precomputed_path) if precomputed_path is not None else a_star_nav(
            nav_map_prior,
            robot_pos,
            viewpoint_cell,
            unknown_cost=1,
        )
    if full_path is None or len(full_path) <= 1:
        return None
    segment_path = _truncate_segment_path(full_path, segment_horizon=segment_horizon)
    if len(segment_path) <= 1:
        return None
    candidate = {
        "anchor_cell": tuple(int(v) for v in anchor_cluster["anchor_cell"]),
        "anchor_source": str(anchor_cluster["anchor_source"]),
        "anchor_centroid_cell": tuple(int(v) for v in anchor_cluster["anchor_centroid_cell"]),
        "anchor_cluster_size": int(anchor_cluster["anchor_cluster_size"]),
        "anchor_cluster_peak": float(anchor_cluster["anchor_cluster_peak"]),
        "anchor_cluster_mean": float(anchor_cluster["anchor_cluster_mean"]),
        "anchor_info_clue_share": float(anchor_cluster.get("anchor_info_clue_share", 0.0)),
        "anchor_info_intensity_share": float(anchor_cluster.get("anchor_info_intensity_share", 0.0)),
        "anchor_value": float(anchor_cluster["anchor_value"]),
        "viewpoint_cell": tuple(int(v) for v in viewpoint_cell),
        "viewpoint_rule": viewpoint_rule,
        "path_to_viewpoint": list(full_path),
        "segment_path": list(segment_path),
        "segment_endpoint_cell": tuple(int(v) for v in segment_path[-1]),
    }
    if candidate_metadata:
        candidate.update(candidate_metadata)
    return candidate


def _knownmap_fallback_local_segments(
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    sensor_range: int,
    segment_horizon: int,
    max_candidates: int,
    path_safety_mode: str = "off",
    inflated_nav_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_inflation_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> list[dict[str, object]]:
    free_cells = np.argwhere(nav_map_prior == FREE)
    if free_cells.size == 0:
        return []

    scored = []
    max_dist = max(1.0, float(segment_horizon))
    for x, y in free_cells:
        cell = (int(x), int(y))
        dist = _cells_distance(robot_pos, cell)
        if dist <= 0.0 or dist > max_dist:
            continue
        obstacle_penalty = _knownmap_neighbor_obstacle_count(nav_map_prior, cell)
        scored.append((-dist, obstacle_penalty, cell[0], cell[1], cell))
    scored.sort()

    fallback_anchor = {
        "anchor_cell": robot_pos,
        "anchor_centroid_cell": robot_pos,
        "anchor_cluster_size": 1,
        "anchor_cluster_peak": 0.0,
        "anchor_cluster_mean": 0.0,
        "anchor_value": 0.0,
        "anchor_source": "fallback_local",
    }
    candidates = []
    for *_prefix, cell in scored[:max_candidates]:
        candidate = _knownmap_segment_candidate(
            fallback_anchor,
            cell,
            nav_map_prior,
            robot_pos,
            segment_horizon=segment_horizon,
            viewpoint_rule="local_fallback",
            path_safety_mode=path_safety_mode,
            inflated_nav_map=inflated_nav_map,
            clearance_cost_map=clearance_cost_map,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
            reservation_table=reservation_table,
            team_reservation_lambda=team_reservation_lambda,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _knownmap_candidate_space(
    policy_name: str,
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    sensor_range: int,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    search_info_map: np.ndarray | None,
    search_info_clue_component: np.ndarray | None,
    search_info_intensity_component: np.ndarray | None,
    current_viewpoint: tuple[int, int] | None,
    current_anchor: tuple[int, int] | None,
    current_anchor_source: str | None,
    current_segment_endpoint: tuple[int, int] | None,
    segment_horizon: int,
    top_k_anchors: int,
    viewpoints_per_anchor: int,
    sampling_seed_base: int = 0,
    infosampled_inspected_limit_multiplier: float = 3.0,
    infosampled_inspected_limit_floor: int = 4,
    geometry_cache: dict[str, object] | None = None,
    path_safety_mode: str = "off",
    inflated_nav_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_inflation_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    anchor_clusters: list[dict[str, object]] = []
    sssp_tree: dict[str, object] | None = None
    sssp_build_time_ms = 0.0
    path_reconstruct_time_ms = 0.0
    sampling_pool_build_time_ms = 0.0
    priority_feature_time_ms = 0.0
    if _knownmap_is_infosampled_family(policy_name):
        t0 = time.perf_counter()
        sssp_tree = _knownmap_single_source_shortest_path_tree(nav_map_prior, robot_pos)
        sssp_build_time_ms = (time.perf_counter() - t0) * 1000.0

    if policy_name == "known_map_greedy_viewpoint":
        anchor_clusters.extend(
            _knownmap_anchor_clusters(
                staleness_map,
                nav_map_prior,
                anchor_source="staleness",
                top_k=max(1, top_k_anchors),
            )
        )
    elif _knownmap_uses_search_info_anchors(policy_name):
        anchor_clusters.extend(
            _knownmap_anchor_clusters(
                search_info_map,
                nav_map_prior,
                anchor_source="search_info",
                top_k=max(1, top_k_anchors),
                clue_component_map=search_info_clue_component,
                intensity_component_map=search_info_intensity_component,
            )
        )
    else:
        anchor_clusters.extend(
            _knownmap_anchor_clusters(
                clue_map,
                nav_map_prior,
                anchor_source="clue",
                top_k=max(1, top_k_anchors),
            )
        )
        anchor_clusters.extend(
            _knownmap_anchor_clusters(
                intensity_map,
                nav_map_prior,
                anchor_source="intensity",
                top_k=max(1, top_k_anchors),
            )
        )
        anchor_clusters.extend(
            _knownmap_anchor_clusters(
                staleness_map,
                nav_map_prior,
                anchor_source="staleness",
                top_k=max(1, top_k_anchors // 2),
            )
        )

    if current_anchor is not None:
        anchor_clusters.append(
            {
                "anchor_cell": current_anchor,
                "anchor_centroid_cell": current_anchor,
                "anchor_cluster_size": 1,
                "anchor_cluster_peak": 0.0,
                "anchor_cluster_mean": 0.0,
                "anchor_value": 0.0,
                "anchor_source": _knownmap_continuation_anchor_source(
                    policy_name,
                    current_anchor_source,
                ),
                "anchor_info_clue_share": _knownmap_anchor_info_shares(
                    current_anchor,
                    search_info_clue_component,
                    search_info_intensity_component,
                )[0],
                "anchor_info_intensity_share": _knownmap_anchor_info_shares(
                    current_anchor,
                    search_info_clue_component,
                    search_info_intensity_component,
                )[1],
            }
        )

    deduped_anchors: list[dict[str, object]] = []
    seen_anchor_keys: set[tuple[object, ...]] = set()
    for cluster in anchor_clusters:
        key = (
            cluster["anchor_source"],
            tuple(int(v) for v in cluster["anchor_centroid_cell"]),
        )
        if key in seen_anchor_keys:
            continue
        seen_anchor_keys.add(key)
        deduped_anchors.append(cluster)

    for anchor_cluster in deduped_anchors:
        if _knownmap_is_infosampled_family(policy_name):
            t0 = time.perf_counter()
            sample_pool = _sample_viewpoint_pool_for_anchor(
                nav_map_prior,
                anchor_cluster,
                sensor_range=sensor_range,
                max_pool_size=max(8, 4 * max(1, viewpoints_per_anchor)),
                sampling_seed_base=sampling_seed_base,
                search_info_map=search_info_map,
                current_viewpoint=current_viewpoint,
                current_segment_endpoint=current_segment_endpoint,
                geometry_cache=geometry_cache,
            )
            sampling_pool_build_time_ms += (time.perf_counter() - t0) * 1000.0
            ranked_viewpoints, ranking_profile = _rank_infosampled_viewpoints(
                sample_pool,
                nav_map_prior=nav_map_prior,
                robot_pos=robot_pos,
                anchor_cluster=anchor_cluster,
                sensor_range=sensor_range,
                search_info_map=search_info_map,
                staleness_map=staleness_map,
                current_viewpoint=current_viewpoint,
                sssp_tree=sssp_tree,
                geometry_cache=geometry_cache,
                top_k=max(1, viewpoints_per_anchor),
                inspected_limit_multiplier=infosampled_inspected_limit_multiplier,
                inspected_limit_floor=infosampled_inspected_limit_floor,
            )
            path_reconstruct_time_ms += float(ranking_profile.get("path_reconstruct_time_ms", 0.0))
            priority_feature_time_ms += float(ranking_profile.get("priority_feature_time_ms", 0.0))
            for ranked in ranked_viewpoints:
                candidate = _knownmap_segment_candidate(
                    anchor_cluster,
                    tuple(int(v) for v in ranked["viewpoint_cell"]),
                    nav_map_prior,
                    robot_pos,
                    segment_horizon=segment_horizon,
                    viewpoint_rule="infosampled_priority",
                    precomputed_path=list(ranked["path_to_viewpoint"]),
                    candidate_metadata={
                        "candidate_pool_size": int(ranked.get("candidate_pool_size", 0)),
                        "reachable_pool_size": int(ranked.get("reachable_pool_size", 0)),
                        "a_star_checked_pool_size": int(ranked.get("a_star_checked_pool_size", 0)),
                        "selected_viewpoint_rank": int(ranked.get("selected_viewpoint_rank", 0)),
                        "sampling_priority_raw": float(ranked.get("sampling_priority_raw", 0.0)),
                        "sampling_priority_norm": float(ranked.get("sampling_priority_norm", 0.0)),
                        "viewpoint_sampling_mode": ranked.get("viewpoint_sampling_mode"),
                        "sampled_viewpoint_pool_cells": list(
                            ranked.get("sampled_viewpoint_pool_cells", [])
                        ),
                        "sssp_build_time_ms": float(sssp_build_time_ms),
                        "path_reconstruct_time_ms": 0.0,
                        "sampling_pool_build_time_ms": 0.0,
                        "priority_feature_time_ms": 0.0,
                    },
                    path_safety_mode=path_safety_mode,
                    inflated_nav_map=inflated_nav_map,
                    clearance_cost_map=clearance_cost_map,
                    safe_nav_lambda_clearance=safe_nav_lambda_clearance,
                    safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
                    reservation_table=reservation_table,
                    team_reservation_lambda=team_reservation_lambda,
                )
                if candidate is not None:
                    candidates.append(candidate)
        else:
            viewpoint_cells = _knownmap_viewpoint_cells_for_anchor(
                nav_map_prior,
                tuple(int(v) for v in anchor_cluster["anchor_cell"]),
                sensor_range=sensor_range,
                max_candidates=max(1, viewpoints_per_anchor),
            )
            for viewpoint_cell in viewpoint_cells:
                candidate = _knownmap_segment_candidate(
                    anchor_cluster,
                    viewpoint_cell,
                    nav_map_prior,
                    robot_pos,
                    segment_horizon=segment_horizon,
                    viewpoint_rule="anchor_viewpoint_ring",
                    path_safety_mode=path_safety_mode,
                    inflated_nav_map=inflated_nav_map,
                    clearance_cost_map=clearance_cost_map,
                    safe_nav_lambda_clearance=safe_nav_lambda_clearance,
                    safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
                    reservation_table=reservation_table,
                    team_reservation_lambda=team_reservation_lambda,
                )
                if candidate is not None:
                    candidates.append(candidate)

    if current_viewpoint is not None and nav_map_prior[current_viewpoint] == FREE:
        current_anchor_cluster = {
            "anchor_cell": current_anchor if current_anchor is not None else current_viewpoint,
            "anchor_centroid_cell": current_anchor if current_anchor is not None else current_viewpoint,
            "anchor_cluster_size": 1,
            "anchor_cluster_peak": 0.0,
            "anchor_cluster_mean": 0.0,
            "anchor_value": 0.0,
            "anchor_source": _knownmap_continuation_anchor_source(
                policy_name,
                current_anchor_source,
                current_viewpoint=True,
            ),
            "anchor_info_clue_share": _knownmap_anchor_info_shares(
                current_anchor if current_anchor is not None else current_viewpoint,
                search_info_clue_component,
                search_info_intensity_component,
            )[0],
            "anchor_info_intensity_share": _knownmap_anchor_info_shares(
                current_anchor if current_anchor is not None else current_viewpoint,
                search_info_clue_component,
                search_info_intensity_component,
            )[1],
        }
        current_viewpoint_path = None
        if _knownmap_is_infosampled_family(policy_name) and sssp_tree is not None:
            t0 = time.perf_counter()
            current_viewpoint_path = _knownmap_reconstruct_path_from_tree(
                np.asarray(sssp_tree["parent_row_map"]),
                np.asarray(sssp_tree["parent_col_map"]),
                robot_pos,
                current_viewpoint,
            )
            path_reconstruct_time_ms += (time.perf_counter() - t0) * 1000.0
        candidate = _knownmap_segment_candidate(
            current_anchor_cluster,
            current_viewpoint,
            nav_map_prior,
            robot_pos,
            segment_horizon=segment_horizon,
            viewpoint_rule="current_viewpoint",
            precomputed_path=current_viewpoint_path,
            candidate_metadata={
                "candidate_pool_size": 0,
                "reachable_pool_size": 0,
                "a_star_checked_pool_size": 0,
                "selected_viewpoint_rank": 0,
                "sampling_priority_raw": 0.0,
                "sampling_priority_norm": 0.0,
                "viewpoint_sampling_mode": "current_viewpoint",
                "sampled_viewpoint_pool_cells": [],
                "sssp_build_time_ms": float(sssp_build_time_ms),
                "path_reconstruct_time_ms": 0.0,
                "sampling_pool_build_time_ms": 0.0,
                "priority_feature_time_ms": 0.0,
            },
            path_safety_mode=path_safety_mode,
            inflated_nav_map=inflated_nav_map,
            clearance_cost_map=clearance_cost_map,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
            reservation_table=reservation_table,
            team_reservation_lambda=team_reservation_lambda,
        )
        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        candidates.extend(
            _knownmap_fallback_local_segments(
                nav_map_prior,
                robot_pos,
                sensor_range=sensor_range,
                segment_horizon=segment_horizon,
                max_candidates=max(6, viewpoints_per_anchor),
                path_safety_mode=path_safety_mode,
                inflated_nav_map=inflated_nav_map,
                clearance_cost_map=clearance_cost_map,
                safe_nav_lambda_clearance=safe_nav_lambda_clearance,
                safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
                reservation_table=reservation_table,
                team_reservation_lambda=team_reservation_lambda,
            )
        )

    deduped_candidates: list[dict[str, object]] = []
    seen_candidate_keys: set[tuple[object, ...]] = set()
    for candidate in candidates:
        key = (
            candidate["anchor_source"],
            candidate["anchor_centroid_cell"],
            candidate["viewpoint_cell"],
            candidate["segment_endpoint_cell"],
        )
        if key in seen_candidate_keys:
            continue
        seen_candidate_keys.add(key)
        if _knownmap_is_infosampled_family(policy_name):
            candidate["sssp_build_time_ms"] = float(sssp_build_time_ms)
            candidate["path_reconstruct_time_ms"] = float(path_reconstruct_time_ms)
            candidate["sampling_pool_build_time_ms"] = float(sampling_pool_build_time_ms)
            candidate["priority_feature_time_ms"] = float(priority_feature_time_ms)
        deduped_candidates.append(candidate)
    return deduped_candidates


def _select_knownmap_infosampled_tree_d2(
    *,
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    sensor_range: int,
    last_seen_step: np.ndarray,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    search_info_map: np.ndarray | None,
    search_info_clue_component: np.ndarray | None,
    search_info_intensity_component: np.ndarray | None,
    current_viewpoint: tuple[int, int] | None,
    current_anchor: tuple[int, int] | None,
    current_anchor_source: str | None,
    current_anchor_centroid: tuple[int, int] | None,
    current_segment_endpoint: tuple[int, int] | None,
    prev_move_dir: tuple[int, int] | None,
    kappa_commit: float,
    lambda_u_turn: float,
    segment_horizon: int,
    top_k_anchors: int,
    viewpoints_per_anchor: int,
    gamma: float,
    sampling_seed_base: int,
    infosampled_inspected_limit_multiplier: float,
    infosampled_inspected_limit_floor: int,
    geometry_cache: dict[str, object] | None,
    tree_first_layer_top_m: int,
    tree_second_layer_top_n: int,
    tree_discount_gamma: float,
    tree_enable_diminishing_returns: bool,
    tree_enable_child_oracle_diagnostics: bool,
    path_safety_mode: str,
    inflated_nav_map: np.ndarray | None,
    obstacle_distance_map: np.ndarray | None,
    clearance_cost_map: np.ndarray | None,
    safe_nav_lambda_clearance: float,
    safe_nav_inflation_radius_cells: int,
    safe_nav_soft_clearance_radius_cells: int,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> tuple[list[tuple[int, int]] | None, dict]:
    root_candidates = _knownmap_candidate_space(
        policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
        nav_map_prior=nav_map_prior,
        robot_pos=robot_pos,
        sensor_range=sensor_range,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        search_info_clue_component=search_info_clue_component,
        search_info_intensity_component=search_info_intensity_component,
        current_viewpoint=current_viewpoint,
        current_anchor=current_anchor,
        current_anchor_source=current_anchor_source,
        current_segment_endpoint=current_segment_endpoint,
        segment_horizon=segment_horizon,
        top_k_anchors=top_k_anchors,
        viewpoints_per_anchor=viewpoints_per_anchor,
        sampling_seed_base=sampling_seed_base,
        infosampled_inspected_limit_multiplier=infosampled_inspected_limit_multiplier,
        infosampled_inspected_limit_floor=infosampled_inspected_limit_floor,
        geometry_cache=geometry_cache,
        path_safety_mode=path_safety_mode,
        inflated_nav_map=inflated_nav_map,
        clearance_cost_map=clearance_cost_map,
        safe_nav_lambda_clearance=safe_nav_lambda_clearance,
        safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
        reservation_table=reservation_table,
        team_reservation_lambda=team_reservation_lambda,
    )
    if not root_candidates:
        return None, _make_knownmap_zero_details()

    root_evaluations = _knownmap_evaluate_segment_candidates(
        "marine_knownmap_path_v2_infosampled_tree_d2",
        root_candidates,
        nav_map_prior=nav_map_prior,
        sensor_range=sensor_range,
        last_seen_step=last_seen_step,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        current_viewpoint=current_viewpoint,
        current_anchor_source=current_anchor_source,
        current_anchor_centroid=current_anchor_centroid,
        prev_move_dir=prev_move_dir,
        kappa_commit=kappa_commit,
        lambda_u_turn=lambda_u_turn,
        gamma=gamma,
        geometry_cache=geometry_cache,
        path_safety_mode=path_safety_mode,
        obstacle_distance_map=obstacle_distance_map,
        clearance_cost_map=clearance_cost_map,
        safe_nav_lambda_clearance=safe_nav_lambda_clearance,
        safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
        reservation_table=reservation_table,
        team_reservation_lambda=team_reservation_lambda,
    )
    if not root_evaluations:
        return None, _make_knownmap_zero_details()

    root_evaluations.sort(key=lambda item: float(item["total_score"]), reverse=True)
    for root_rank, item in enumerate(root_evaluations, start=1):
        item["tree_root_rank"] = int(root_rank)

    root_limit = min(len(root_evaluations), max(1, int(tree_first_layer_top_m)))
    child_limit = max(1, int(tree_second_layer_top_n))
    tree_entries: list[dict[str, object]] = []
    total_profile = _knownmap_candidate_space_profile(root_candidates)
    total_profile["tree_planning_time_ms"] = 0.0
    tree_expansion_count = 0

    for root in root_evaluations[:root_limit]:
        root_seen_cells = set(root.get("segment_visible_cells", set()))
        child_candidates = _knownmap_candidate_space(
            policy_name="marine_knownmap_path_v2_infosampled_tree_d2",
            nav_map_prior=nav_map_prior,
            robot_pos=tuple(int(v) for v in root["segment_endpoint_cell"]),
            sensor_range=sensor_range,
            staleness_map=staleness_map,
            clue_map=clue_map,
            intensity_map=intensity_map,
            search_info_map=search_info_map,
            search_info_clue_component=search_info_clue_component,
            search_info_intensity_component=search_info_intensity_component,
            current_viewpoint=tuple(int(v) for v in root["viewpoint_cell"]),
            current_anchor=tuple(int(v) for v in root["anchor_cell"]),
            current_anchor_source=str(root["anchor_source"]),
            current_segment_endpoint=tuple(int(v) for v in root["segment_endpoint_cell"]),
            segment_horizon=segment_horizon,
            top_k_anchors=top_k_anchors,
            viewpoints_per_anchor=viewpoints_per_anchor,
            sampling_seed_base=_knownmap_tree_sampling_seed(
                sampling_seed_base,
                tuple(int(v) for v in root["segment_endpoint_cell"]),
                int(root["tree_root_rank"]),
            ),
            infosampled_inspected_limit_multiplier=infosampled_inspected_limit_multiplier,
            infosampled_inspected_limit_floor=infosampled_inspected_limit_floor,
            geometry_cache=geometry_cache,
            path_safety_mode=path_safety_mode,
            inflated_nav_map=inflated_nav_map,
            clearance_cost_map=clearance_cost_map,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
            reservation_table=reservation_table,
            team_reservation_lambda=team_reservation_lambda,
        )
        child_profile = _knownmap_candidate_space_profile(child_candidates)
        for key, value in child_profile.items():
            total_profile[key] = float(total_profile.get(key, 0.0)) + float(value)
        total_profile["tree_planning_time_ms"] = (
            float(total_profile["sssp_build_time_ms"])
            + float(total_profile["path_reconstruct_time_ms"])
            + float(total_profile["sampling_pool_build_time_ms"])
            + float(total_profile["priority_feature_time_ms"])
        )

        budgeted_child_candidates = _budget_tree_child_candidates(
            child_candidates,
            top_n=child_limit,
            nav_map_prior=nav_map_prior,
            sensor_range=sensor_range,
            root_seen_cells=root_seen_cells,
            geometry_cache=geometry_cache,
        )
        full_child_evaluations: list[dict[str, object]] = []
        if tree_enable_child_oracle_diagnostics:
            full_child_evaluations = _knownmap_evaluate_segment_candidates(
                "marine_knownmap_path_v2_infosampled_tree_d2",
                child_candidates,
                nav_map_prior=nav_map_prior,
                sensor_range=sensor_range,
                last_seen_step=last_seen_step,
                staleness_map=staleness_map,
                clue_map=clue_map,
                intensity_map=intensity_map,
                search_info_map=search_info_map,
                current_viewpoint=tuple(int(v) for v in root["viewpoint_cell"]),
                current_anchor_source=str(root["anchor_source"]),
                current_anchor_centroid=tuple(int(v) for v in root["anchor_centroid_cell"]),
                prev_move_dir=_path_last_move_dir(list(root["segment_path"])),
                kappa_commit=kappa_commit,
                lambda_u_turn=lambda_u_turn,
                gamma=gamma,
                pre_seen_cells=root_seen_cells if tree_enable_diminishing_returns else None,
                geometry_cache=geometry_cache,
                path_safety_mode=path_safety_mode,
                obstacle_distance_map=obstacle_distance_map,
                clearance_cost_map=clearance_cost_map,
                safe_nav_lambda_clearance=safe_nav_lambda_clearance,
                safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
                reservation_table=reservation_table,
                team_reservation_lambda=team_reservation_lambda,
            )
            full_child_evaluations.sort(key=lambda item: float(item["total_score"]), reverse=True)
        child_evaluations = _knownmap_evaluate_segment_candidates(
            "marine_knownmap_path_v2_infosampled_tree_d2",
            budgeted_child_candidates,
            nav_map_prior=nav_map_prior,
            sensor_range=sensor_range,
            last_seen_step=last_seen_step,
            staleness_map=staleness_map,
            clue_map=clue_map,
            intensity_map=intensity_map,
            search_info_map=search_info_map,
            current_viewpoint=tuple(int(v) for v in root["viewpoint_cell"]),
            current_anchor_source=str(root["anchor_source"]),
            current_anchor_centroid=tuple(int(v) for v in root["anchor_centroid_cell"]),
            prev_move_dir=_path_last_move_dir(list(root["segment_path"])),
            kappa_commit=kappa_commit,
            lambda_u_turn=lambda_u_turn,
            gamma=gamma,
            pre_seen_cells=root_seen_cells if tree_enable_diminishing_returns else None,
            geometry_cache=geometry_cache,
            path_safety_mode=path_safety_mode,
            obstacle_distance_map=obstacle_distance_map,
            clearance_cost_map=clearance_cost_map,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
            reservation_table=reservation_table,
            team_reservation_lambda=team_reservation_lambda,
        )
        child_evaluations.sort(key=lambda item: float(item["total_score"]), reverse=True)
        for child_rank, item in enumerate(child_evaluations, start=1):
            item["tree_child_rank"] = int(child_rank)
        tree_expansion_count += len(child_evaluations)

        best_child = child_evaluations[0] if child_evaluations else None
        oracle_details = (
            _knownmap_tree_child_oracle_diagnostics(full_child_evaluations, best_child)
            if tree_enable_child_oracle_diagnostics
            else _knownmap_tree_child_oracle_diagnostics([], best_child)
        )
        child_total_score = float(best_child["total_score"]) if best_child is not None else 0.0
        tree_total_score = float(root["total_score"]) + float(tree_discount_gamma) * child_total_score
        tree_entries.append(
            {
                "root": root,
                "child": best_child,
                "root_total_score": float(root["total_score"]),
                "child_total_score": float(child_total_score),
                "tree_total_score": float(tree_total_score),
                "tree_root_rank": int(root["tree_root_rank"]),
                "tree_child_rank": int(best_child.get("tree_child_rank", 0)) if best_child is not None else 0,
                "tree_conditional_gain_lvl2": (
                    float(best_child.get("search_info_gain_raw", 0.0))
                    + float(best_child.get("recency_bias_raw", 0.0))
                    if best_child is not None
                    else 0.0
                ),
                "tree_redundant_visible_ratio_lvl2": (
                    float(best_child.get("redundant_visible_ratio", 0.0))
                    if best_child is not None
                    else 0.0
                ),
                "tree_unique_visible_count_lvl1": int(root.get("unique_visible_count", 0)),
                "tree_unique_visible_count_lvl2": (
                    int(best_child.get("unique_visible_count", 0))
                    if best_child is not None
                    else 0
                ),
                **oracle_details,
            }
        )

    if not tree_entries:
        return None, _make_knownmap_zero_details()

    best_entry = _select_best_tree_root_combination(tree_entries, tree_discount_gamma=tree_discount_gamma)
    best_root = dict(best_entry["root"])
    best_child = best_entry.get("child")
    current_tree_score = 0.0
    for entry in tree_entries:
        root = entry["root"]
        if (
            current_viewpoint is not None
            and tuple(int(v) for v in root["viewpoint_cell"]) == current_viewpoint
        ):
            current_tree_score = float(entry["tree_total_score"])
            break
    best_tree_score = max(float(entry["tree_total_score"]) for entry in tree_entries)

    details = {
        "explore_utility_raw": float(best_root.get("explore_utility_raw", 0.0)),
        "explore_utility_norm": float(best_root.get("explore_utility_norm", 0.0)),
        "focus_utility_raw": float(best_root.get("focus_utility_raw", 0.0)),
        "focus_utility_norm": float(best_root.get("focus_utility_norm", 0.0)),
        "recency_utility_raw": float(best_root.get("recency_utility_raw", 0.0)),
        "recency_utility_norm": float(best_root.get("recency_utility_norm", 0.0)),
        "search_info_gain_raw": float(best_root.get("search_info_gain_raw", 0.0)),
        "search_info_gain_norm": float(best_root.get("search_info_gain_norm", 0.0)),
        "recency_bias_raw": float(best_root.get("recency_bias_raw", 0.0)),
        "recency_bias_norm": float(best_root.get("recency_bias_norm", 0.0)),
        "exec_cost_raw": float(best_root.get("exec_cost_raw", 0.0)),
        "exec_cost_norm": float(best_root.get("exec_cost_norm", 0.0)),
        "obstacle_proximity_raw": float(best_root.get("obstacle_proximity_raw", 0.0)),
        "clearance_penalty_raw": float(best_root.get("clearance_penalty_raw", 0.0)),
        "segment_min_clearance_cells": float(best_root.get("segment_min_clearance_cells", 0.0)),
        "segment_mean_clearance_cells": float(best_root.get("segment_mean_clearance_cells", 0.0)),
        "near_obstacle_step_flag": bool(best_root.get("near_obstacle_step_flag", False)),
        "near_obstacle_step_ratio": float(best_root.get("near_obstacle_step_ratio", 0.0)),
        "segment_turn_count": int(best_root.get("segment_turn_count", 0)),
        "path_safety_mode": str(best_root.get("path_safety_mode", path_safety_mode)),
        "safe_nav_lambda_clearance": float(
            best_root.get("safe_nav_lambda_clearance", safe_nav_lambda_clearance)
        ),
        "alpha_focus": float(best_root.get("alpha_focus", 0.0)),
        "kappa_commit": 0.0,
        "same_anchor_cluster": bool(best_root.get("same_anchor_cluster", False)),
        "viewpoint_drift_norm": float(best_root.get("viewpoint_drift_norm", 0.0)),
        "anchor_retention_bonus": float(best_root.get("anchor_retention_bonus", 0.0)),
        "viewpoint_retention_bonus": float(best_root.get("viewpoint_retention_bonus", 0.0)),
        "candidate_count": int(best_root.get("candidate_count", 0)),
        "current_viewpoint_score": float(current_tree_score),
        "best_alternative_score": float(best_tree_score),
        "anchor_cell": best_root.get("anchor_cell"),
        "anchor_source": best_root.get("anchor_source"),
        "anchor_centroid_cell": best_root.get("anchor_centroid_cell"),
        "anchor_cluster_size": int(best_root.get("anchor_cluster_size", 0)),
        "anchor_cluster_peak": float(best_root.get("anchor_cluster_peak", 0.0)),
        "anchor_cluster_mean": float(best_root.get("anchor_cluster_mean", 0.0)),
        "anchor_info_clue_share": float(best_root.get("anchor_info_clue_share", 0.0)),
        "anchor_info_intensity_share": float(best_root.get("anchor_info_intensity_share", 0.0)),
        "viewpoint_cell": best_root.get("viewpoint_cell"),
        "viewpoint_rule": best_root.get("viewpoint_rule"),
        "candidate_pool_size": int(best_root.get("candidate_pool_size", 0)),
        "reachable_pool_size": int(best_root.get("reachable_pool_size", 0)),
        "a_star_checked_pool_size": int(best_root.get("a_star_checked_pool_size", 0)),
        "selected_viewpoint_rank": int(best_root.get("selected_viewpoint_rank", 0)),
        "sampling_priority_raw": float(best_root.get("sampling_priority_raw", 0.0)),
        "sampling_priority_norm": float(best_root.get("sampling_priority_norm", 0.0)),
        "viewpoint_sampling_mode": best_root.get("viewpoint_sampling_mode"),
        "sampled_viewpoint_pool_cells": list(best_root.get("sampled_viewpoint_pool_cells", [])),
        "selected_by_final_score": True,
        "sssp_build_time_ms": float(total_profile.get("sssp_build_time_ms", 0.0)),
        "path_reconstruct_time_ms": float(total_profile.get("path_reconstruct_time_ms", 0.0)),
        "sampling_pool_build_time_ms": float(total_profile.get("sampling_pool_build_time_ms", 0.0)),
        "priority_feature_time_ms": float(total_profile.get("priority_feature_time_ms", 0.0)),
        "segment_endpoint_cell": best_root.get("segment_endpoint_cell"),
        "segment_path_length": int(max(len(best_root.get("segment_path", [])) - 1, 0)),
        "planned_viewpoint_path_length": int(max(len(best_root.get("path_to_viewpoint", [])) - 1, 0)),
        "u_turn_penalty_term": float(best_root.get("u_turn_penalty_term", 0.0)),
        "u_turn_penalty_applied": bool(best_root.get("u_turn_penalty_applied", False)),
        "first_move_dir": best_root.get("first_move_dir"),
        "score_schema": "infosampled_tree_d2",
        "total_score": float(best_entry["tree_total_score"]),
        "tree_depth": 2,
        "tree_first_layer_top_m": int(root_limit),
        "tree_second_layer_top_n": int(child_limit),
        "tree_discount_gamma": float(tree_discount_gamma),
        "tree_enable_diminishing_returns": bool(tree_enable_diminishing_returns),
        "tree_root_rank": int(best_entry["tree_root_rank"]),
        "tree_child_rank": int(best_entry["tree_child_rank"]),
        "tree_root_score_raw": float(best_entry["root_total_score"]),
        "tree_child_score_raw": float(best_entry["child_total_score"]),
        "tree_total_score": float(best_entry["tree_total_score"]),
        "tree_conditional_gain_lvl2": float(best_entry["tree_conditional_gain_lvl2"]),
        "tree_redundant_visible_ratio_lvl2": float(best_entry["tree_redundant_visible_ratio_lvl2"]),
        "tree_unique_visible_count_lvl1": int(best_entry["tree_unique_visible_count_lvl1"]),
        "tree_unique_visible_count_lvl2": int(best_entry["tree_unique_visible_count_lvl2"]),
        "tree_expansion_count": int(tree_expansion_count),
        "tree_planning_time_ms": float(total_profile.get("tree_planning_time_ms", 0.0)),
        "tree_child_oracle_score_raw": float(best_entry["tree_child_oracle_score_raw"]),
        "tree_child_budget_score_raw": float(best_entry["tree_child_budget_score_raw"]),
        "tree_child_oracle_gap_raw": float(best_entry["tree_child_oracle_gap_raw"]),
        "tree_child_oracle_rank_of_budgeted": int(best_entry["tree_child_oracle_rank_of_budgeted"]),
        "tree_child_budget_matches_oracle": bool(best_entry["tree_child_budget_matches_oracle"]),
        "tree_child_oracle_viewpoint_cell": best_entry.get("tree_child_oracle_viewpoint_cell"),
        "tree_child_budget_viewpoint_cell": best_entry.get("tree_child_budget_viewpoint_cell"),
        "tree_child_full_candidate_count": int(best_entry["tree_child_full_candidate_count"]),
        "marginal_information_gain_raw": float(best_root.get("marginal_information_gain_raw", 0.0)),
        "marginal_information_gain_norm": float(best_root.get("marginal_information_gain_norm", 0.0)),
        "execution_cost_raw": float(best_root.get("execution_cost_raw", 0.0)),
        "execution_cost_norm": float(best_root.get("execution_cost_norm", 0.0)),
        "continuity_bonus_raw": float(best_root.get("continuity_bonus_raw", 0.0)),
        "continuity_bonus_anchor_raw": float(best_root.get("continuity_bonus_anchor_raw", 0.0)),
        "continuity_bonus_viewpoint_raw": float(
            best_root.get("continuity_bonus_viewpoint_raw", 0.0)
        ),
        "marginal_information_gain_score_term": float(
            best_root.get("marginal_information_gain_score_term", 0.0)
        ),
        "recency_bias_score_term": float(best_root.get("recency_bias_score_term", 0.0)),
        "execution_cost_score_term": float(best_root.get("execution_cost_score_term", 0.0)),
        "continuity_bonus_score_term": float(best_root.get("continuity_bonus_score_term", 0.0)),
        "maneuver_penalty_raw": float(best_root.get("maneuver_penalty_raw", 0.0)),
        "maneuver_penalty_score_term": float(best_root.get("maneuver_penalty_score_term", 0.0)),
        "score_formula_label": best_root.get("score_formula_label"),
    }
    if best_child is not None:
        details["tree_child_viewpoint_cell"] = best_child.get("viewpoint_cell")
        details["tree_child_endpoint_cell"] = best_child.get("segment_endpoint_cell")
    return list(best_root["segment_path"]), details


def _knownmap_viewpoint_drift_norm(
    viewpoint_cell: tuple[int, int],
    current_viewpoint: tuple[int, int] | None,
    sensor_range: int,
) -> float:
    if current_viewpoint is None:
        return 0.0
    denom = max(1, int(sensor_range))
    drift = _cells_distance(viewpoint_cell, current_viewpoint) / float(denom)
    return float(np.clip(drift, 0.0, 1.0))


def _knownmap_segment_weights(policy_name: str) -> dict[str, float]:
    # Phase 5-lite keeps the implemented policy behavior intact but makes the
    # infosampled/infofused family read as:
    # marginal_information_gain - lambda_cost * execution_cost + recency_bias
    # with continuity bonuses applied separately in the final scorer.
    if policy_name == "known_map_greedy_viewpoint":
        return {
            "explore_utility_norm": 7.0,
            "focus_utility_norm": 1.0,
            "recency_utility_norm": 4.0,
            "exec_cost_norm": -0.45,
        }
    if policy_name == "marine_search_soft_knownmap":
        return {
            "explore_utility_norm": 7.0,
            "focus_utility_norm": 2.0,
            "recency_utility_norm": 6.0,
            "exec_cost_norm": -0.40,
        }
    if policy_name == "marine_knownmap_path_v2":
        return {
            "explore_utility_norm": 5.5,
            "focus_utility_norm": 3.0,
            "recency_utility_norm": 3.5,
            "exec_cost_norm": -0.35,
        }
    if policy_name in {
        "marine_knownmap_path_v2_infofused",
        "marine_knownmap_path_v2_infosampled",
        "marine_knownmap_path_v2_infosampled_tree_d2",
    }:
        return {
            "search_info_gain_norm": 6.5,
            "recency_bias_norm": 2.0,
            "exec_cost_norm": -0.35,
        }
    raise ValueError(f"Unsupported known-map policy_name='{policy_name}'")


def _knownmap_commit_terms(
    kappa_commit: float,
    same_anchor_cluster: bool,
    viewpoint_drift_norm: float,
    same_viewpoint: bool,
) -> tuple[float, float]:
    # Deprecated compatibility hook: kappa_commit is still accepted by callers,
    # but it no longer contributes anchor/viewpoint retention to path scoring.
    return 0.0, 0.0


def _knownmap_phase5_lite_semantic_terms(
    item: dict[str, object],
    weights: dict[str, float],
) -> dict[str, object]:
    continuity_bonus = float(item.get("anchor_retention_bonus", 0.0)) + float(
        item.get("viewpoint_retention_bonus", 0.0)
    )
    maneuver_penalty = float(item.get("u_turn_penalty_term", 0.0))
    return {
        "marginal_information_gain_raw": float(item.get("search_info_gain_raw", 0.0)),
        "marginal_information_gain_norm": float(item.get("search_info_gain_norm", 0.0)),
        "execution_cost_raw": float(item.get("exec_cost_raw", 0.0)),
        "execution_cost_norm": float(item.get("exec_cost_norm", 0.0)),
        "continuity_bonus_raw": float(continuity_bonus),
        "continuity_bonus_anchor_raw": float(item.get("anchor_retention_bonus", 0.0)),
        "continuity_bonus_viewpoint_raw": float(item.get("viewpoint_retention_bonus", 0.0)),
        "marginal_information_gain_score_term": float(
            float(weights.get("search_info_gain_norm", 0.0))
            * float(item.get("search_info_gain_norm", 0.0))
        ),
        "recency_bias_score_term": float(
            float(weights.get("recency_bias_norm", 0.0))
            * float(item.get("recency_bias_norm", 0.0))
        ),
        "execution_cost_score_term": float(
            float(weights.get("exec_cost_norm", 0.0))
            * float(item.get("exec_cost_norm", 0.0))
        ),
        "continuity_bonus_score_term": float(continuity_bonus),
        "maneuver_penalty_raw": float(maneuver_penalty),
        "maneuver_penalty_score_term": float(-maneuver_penalty),
        "score_formula_label": (
            "marginal_information_gain - lambda_cost * execution_cost + "
            "recency_bias - maneuver_penalty"
        ),
    }


def _knownmap_evaluate_segment_candidates(
    policy_name: str,
    candidates: list[dict[str, object]],
    *,
    nav_map_prior: np.ndarray,
    sensor_range: int,
    last_seen_step: np.ndarray,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    search_info_map: np.ndarray | None,
    current_viewpoint: tuple[int, int] | None,
    current_anchor_source: str | None,
    current_anchor_centroid: tuple[int, int] | None,
    prev_move_dir: tuple[int, int] | None,
    kappa_commit: float,
    lambda_u_turn: float,
    gamma: float,
    pre_seen_cells: set[tuple[int, int]] | None = None,
    geometry_cache: dict[str, object] | None = None,
    path_safety_mode: str = "off",
    obstacle_distance_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_soft_clearance_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> list[dict[str, object]]:
    evaluations: list[dict[str, object]] = []
    for candidate in candidates:
        segment_path = list(candidate["segment_path"])
        if len(segment_path) <= 1:
            continue
        breakdown = _knownmap_segment_score_breakdown(
            segment_path=segment_path,
            nav_map_prior=nav_map_prior,
            sensor_range=sensor_range,
            last_seen_step=last_seen_step,
            staleness_map=staleness_map,
            clue_map=clue_map,
            intensity_map=intensity_map,
            search_info_map=search_info_map,
            anchor_cell=tuple(int(v) for v in candidate["anchor_cell"]),
            viewpoint_cell=tuple(int(v) for v in candidate["viewpoint_cell"]),
            gamma=gamma,
            pre_seen_cells=pre_seen_cells,
            geometry_cache=geometry_cache,
            path_safety_mode=path_safety_mode,
            obstacle_distance_map=obstacle_distance_map,
            clearance_cost_map=clearance_cost_map,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
            reservation_table=reservation_table,
            team_reservation_lambda=team_reservation_lambda,
        )
        evaluations.append(
            {
                **candidate,
                **breakdown,
                "path_safety_mode": str(path_safety_mode),
                "safe_nav_lambda_clearance": float(safe_nav_lambda_clearance),
                "team_reservation_lambda": float(team_reservation_lambda),
            }
        )

    if not evaluations:
        return []

    for term_name in (
        "explore_utility_raw",
        "focus_utility_raw",
        "recency_utility_raw",
        "search_info_gain_raw",
        "recency_bias_raw",
        "exec_cost_raw",
    ):
        norm_values = _normalize_term([float(item[term_name]) for item in evaluations])
        norm_name = term_name.replace("_raw", "_norm")
        for item, norm_value in zip(evaluations, norm_values):
            item[norm_name] = float(norm_value)

    weights = _knownmap_segment_weights(policy_name)
    for item in evaluations:
        total_score = 0.0
        for term_name, weight in weights.items():
            total_score += float(weight) * float(item.get(term_name, 0.0))

        same_anchor_cluster = _same_anchor_cluster_candidate(
            item,
            current_anchor_source=current_anchor_source,
            current_anchor_centroid=current_anchor_centroid,
            sensor_range=sensor_range,
        )
        viewpoint_drift_norm = _knownmap_viewpoint_drift_norm(
            tuple(int(v) for v in item["viewpoint_cell"]),
            current_viewpoint=current_viewpoint,
            sensor_range=sensor_range,
        )
        anchor_retention_bonus = 0.0
        viewpoint_retention_bonus = 0.0
        if policy_name in {
            "marine_search_soft_knownmap",
            "marine_knownmap_path_v2",
            "marine_knownmap_path_v2_infofused",
            "marine_knownmap_path_v2_infosampled",
            "marine_knownmap_path_v2_infosampled_tree_d2",
        }:
            anchor_retention_bonus, viewpoint_retention_bonus = _knownmap_commit_terms(
                kappa_commit=kappa_commit,
                same_anchor_cluster=same_anchor_cluster,
                viewpoint_drift_norm=viewpoint_drift_norm,
                same_viewpoint=(
                    current_viewpoint is not None
                    and tuple(int(v) for v in item["viewpoint_cell"]) == current_viewpoint
                ),
            )

        u_turn_penalty, u_turn_applied, first_move_dir = u_turn_penalty_for_path(
            list(item["segment_path"]),
            prev_move_dir,
            lambda_u_turn=lambda_u_turn,
        )
        total_score -= float(u_turn_penalty)
        item["alpha_focus"] = 0.0
        item["kappa_commit"] = 0.0
        item["same_anchor_cluster"] = bool(same_anchor_cluster)
        item["viewpoint_drift_norm"] = float(viewpoint_drift_norm)
        item["anchor_retention_bonus"] = float(anchor_retention_bonus)
        item["viewpoint_retention_bonus"] = float(viewpoint_retention_bonus)
        item["u_turn_penalty_term"] = float(u_turn_penalty)
        item["u_turn_penalty_applied"] = bool(u_turn_applied)
        item["first_move_dir"] = first_move_dir
        item["total_score"] = float(total_score)
        item["candidate_count"] = int(len(evaluations))
        item.update(_knownmap_phase5_lite_semantic_terms(item, weights))

    return evaluations


def _best_knownmap_evaluation(
    evaluations: list[dict[str, object]],
    current_viewpoint: tuple[int, int] | None,
) -> tuple[dict[str, object], float, float]:
    best = max(evaluations, key=lambda item: float(item["total_score"]))
    current_viewpoint_score = 0.0
    best_alternative_score = float(best["total_score"])
    if current_viewpoint is not None:
        current_item = next(
            (
                item
                for item in evaluations
                if tuple(int(v) for v in item["viewpoint_cell"]) == current_viewpoint
            ),
            None,
        )
        if current_item is not None:
            current_viewpoint_score = float(current_item["total_score"])
    return best, float(current_viewpoint_score), float(best_alternative_score)


def _knownmap_candidate_space_profile(candidates: list[dict[str, object]]) -> dict[str, float]:
    if not candidates:
        return {
            "sssp_build_time_ms": 0.0,
            "path_reconstruct_time_ms": 0.0,
            "sampling_pool_build_time_ms": 0.0,
            "priority_feature_time_ms": 0.0,
        }
    return {
        "sssp_build_time_ms": float(max(float(item.get("sssp_build_time_ms", 0.0)) for item in candidates)),
        "path_reconstruct_time_ms": float(
            max(float(item.get("path_reconstruct_time_ms", 0.0)) for item in candidates)
        ),
        "sampling_pool_build_time_ms": float(
            max(float(item.get("sampling_pool_build_time_ms", 0.0)) for item in candidates)
        ),
        "priority_feature_time_ms": float(
            max(float(item.get("priority_feature_time_ms", 0.0)) for item in candidates)
        ),
    }


def _knownmap_tree_sampling_seed(
    sampling_seed_base: int,
    endpoint_cell: tuple[int, int],
    root_rank: int,
) -> int:
    return (
        int(sampling_seed_base) * 1000003
        + int(root_rank) * 9176
        + int(endpoint_cell[0]) * 131
        + int(endpoint_cell[1]) * 173
    )


def _knownmap_segment_visible_flat_set(
    segment_path: list[tuple[int, int]],
    nav_map_prior: np.ndarray,
    sensor_range: int,
    geometry_cache: dict[str, object] | None,
) -> set[int]:
    visible_flat_set: set[int] = set()
    for waypoint in segment_path[1:]:
        visible_flat_indices = _knownmap_visible_flat_indices_for_cell(
            tuple(int(v) for v in waypoint),
            nav_map_prior,
            sensor_range,
            geometry_cache,
        )
        for flat_idx in visible_flat_indices:
            visible_flat_set.add(int(flat_idx))
    return visible_flat_set


def _knownmap_tree_candidate_key(candidate: dict[str, object]) -> tuple[object, ...]:
    return (
        tuple(int(v) for v in candidate.get("viewpoint_cell", ())),
        tuple(int(v) for v in candidate.get("segment_endpoint_cell", ())),
        str(candidate.get("viewpoint_rule")),
    )


def _budget_tree_child_candidates(
    child_candidates: list[dict[str, object]],
    *,
    top_n: int,
    nav_map_prior: np.ndarray,
    sensor_range: int,
    root_seen_cells: set[tuple[int, int]] | None,
    geometry_cache: dict[str, object] | None,
) -> list[dict[str, object]]:
    if top_n <= 0 or not child_candidates:
        return []
    if len(child_candidates) <= top_n:
        return list(child_candidates)
    width = int(nav_map_prior.shape[1])
    root_seen_flat = {
        int(cell[0]) * width + int(cell[1])
        for cell in (root_seen_cells or set())
    }
    enriched_children: list[dict[str, object]] = []

    seen_keys: set[tuple[object, ...]] = set()
    for candidate in child_candidates:
        key = _knownmap_tree_candidate_key(candidate)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        visible_flat_set = _knownmap_segment_visible_flat_set(
            list(candidate.get("segment_path", [])),
            nav_map_prior,
            sensor_range,
            geometry_cache,
        )
        if visible_flat_set:
            root_overlap = len(visible_flat_set & root_seen_flat)
            root_overlap_ratio = float(root_overlap) / float(len(visible_flat_set))
        else:
            root_overlap_ratio = 0.0
        root_novelty_ratio = 1.0 - root_overlap_ratio
        continuity_bias = 0.10 if str(candidate.get("viewpoint_rule")) == "current_viewpoint" else 0.0
        enriched_children.append(
            {
                **candidate,
                "_tree_visible_flat_set": visible_flat_set,
                "_tree_root_overlap_ratio": float(root_overlap_ratio),
                "_tree_root_novelty_ratio": float(root_novelty_ratio),
                "_tree_continuity_bias": float(continuity_bias),
            }
        )

    selected: list[dict[str, object]] = []
    selected_visible_union: set[int] = set()

    while enriched_children and len(selected) < top_n:
        best_idx = 0
        best_score = -float("inf")
        for idx, candidate in enumerate(enriched_children):
            visible_flat_set = set(candidate.get("_tree_visible_flat_set", set()))
            if visible_flat_set:
                selected_overlap_ratio = float(len(visible_flat_set & selected_visible_union)) / float(
                    len(visible_flat_set)
                )
            else:
                selected_overlap_ratio = 0.0
            selected_novelty_ratio = 1.0 - selected_overlap_ratio
            diversity_budget_score = (
                float(candidate.get("sampling_priority_raw", 0.0))
                + 1.20 * float(candidate.get("_tree_root_novelty_ratio", 0.0))
                + 0.80 * float(selected_novelty_ratio)
                - 0.60 * float(candidate.get("_tree_root_overlap_ratio", 0.0))
                - 0.85 * float(selected_overlap_ratio)
                + float(candidate.get("_tree_continuity_bias", 0.0))
            )
            tie_break = (
                -float(candidate.get("selected_viewpoint_rank", 0)),
                -float(candidate.get("candidate_pool_size", 0)),
                -float(candidate.get("segment_path_length", max(len(candidate.get("segment_path", [])) - 1, 0))),
            )
            if diversity_budget_score > best_score or (
                math.isclose(diversity_budget_score, best_score)
                and tie_break > (
                    -float(enriched_children[best_idx].get("selected_viewpoint_rank", 0)),
                    -float(enriched_children[best_idx].get("candidate_pool_size", 0)),
                    -float(
                        enriched_children[best_idx].get(
                            "segment_path_length",
                            max(len(enriched_children[best_idx].get("segment_path", [])) - 1, 0),
                        )
                    ),
                )
            ):
                best_idx = idx
                best_score = float(diversity_budget_score)
                candidate["_tree_selected_overlap_ratio"] = float(selected_overlap_ratio)
                candidate["_tree_selected_novelty_ratio"] = float(selected_novelty_ratio)

        chosen = enriched_children.pop(best_idx)
        selected_visible_union.update(set(chosen.get("_tree_visible_flat_set", set())))
        selected.append(
            {
                key: value
                for key, value in chosen.items()
                if not str(key).startswith("_tree_")
            }
        )
    return selected[:top_n]


def _knownmap_tree_child_oracle_diagnostics(
    full_child_evaluations: list[dict[str, object]],
    budgeted_best_child: dict[str, object] | None,
) -> dict[str, object]:
    if not full_child_evaluations:
        return {
            "tree_child_oracle_score_raw": 0.0,
            "tree_child_budget_score_raw": (
                float(budgeted_best_child.get("total_score", 0.0))
                if budgeted_best_child is not None
                else 0.0
            ),
            "tree_child_oracle_gap_raw": 0.0,
            "tree_child_oracle_rank_of_budgeted": 0,
            "tree_child_budget_matches_oracle": False,
            "tree_child_oracle_viewpoint_cell": None,
            "tree_child_budget_viewpoint_cell": (
                budgeted_best_child.get("viewpoint_cell")
                if budgeted_best_child is not None
                else None
            ),
            "tree_child_full_candidate_count": 0,
        }

    oracle_child = full_child_evaluations[0]
    oracle_key = _knownmap_tree_candidate_key(oracle_child)
    budget_key = (
        _knownmap_tree_candidate_key(budgeted_best_child)
        if budgeted_best_child is not None
        else None
    )
    oracle_rank_of_budgeted = 0
    if budget_key is not None:
        oracle_rank_of_budgeted = len(full_child_evaluations) + 1
        for rank_idx, candidate in enumerate(full_child_evaluations, start=1):
            if _knownmap_tree_candidate_key(candidate) == budget_key:
                oracle_rank_of_budgeted = int(rank_idx)
                break
    oracle_score = float(oracle_child.get("total_score", 0.0))
    budget_score = (
        float(budgeted_best_child.get("total_score", 0.0))
        if budgeted_best_child is not None
        else 0.0
    )
    return {
        "tree_child_oracle_score_raw": float(oracle_score),
        "tree_child_budget_score_raw": float(budget_score),
        "tree_child_oracle_gap_raw": float(max(oracle_score - budget_score, 0.0)),
        "tree_child_oracle_rank_of_budgeted": int(oracle_rank_of_budgeted),
        "tree_child_budget_matches_oracle": bool(budget_key is not None and budget_key == oracle_key),
        "tree_child_oracle_viewpoint_cell": oracle_child.get("viewpoint_cell"),
        "tree_child_budget_viewpoint_cell": (
            budgeted_best_child.get("viewpoint_cell")
            if budgeted_best_child is not None
            else None
        ),
        "tree_child_full_candidate_count": int(len(full_child_evaluations)),
    }


def _select_best_tree_root_combination(
    ranked_root_entries: list[dict[str, object]],
    tree_discount_gamma: float,
) -> dict[str, object]:
    if not ranked_root_entries:
        raise ValueError("ranked_root_entries must be non-empty")
    return max(
        ranked_root_entries,
        key=lambda entry: float(entry["root_total_score"]) + float(tree_discount_gamma) * float(entry["child_total_score"]),
    )


def select_knownmap_path_segment_policy(
    policy_name: str,
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    sensor_range: int,
    last_seen_step: np.ndarray,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    search_info_map: np.ndarray | None = None,
    search_info_clue_component: np.ndarray | None = None,
    search_info_intensity_component: np.ndarray | None = None,
    current_viewpoint: tuple[int, int] | None = None,
    current_anchor: tuple[int, int] | None = None,
    current_anchor_source: str | None = None,
    current_anchor_centroid: tuple[int, int] | None = None,
    current_segment_endpoint: tuple[int, int] | None = None,
    prev_move_dir: tuple[int, int] | None = None,
    kappa_commit: float = 0.0,
    lambda_u_turn: float = 2.0,
    segment_horizon: int = 8,
    top_k_anchors: int = 6,
    viewpoints_per_anchor: int = 6,
    gamma: float = 0.95,
    sampling_seed_base: int = 0,
    infosampled_inspected_limit_multiplier: float = 3.0,
    infosampled_inspected_limit_floor: int = 4,
    geometry_cache: dict[str, object] | None = None,
    tree_first_layer_top_m: int = KNOWNMAP_ACTIVE_TREE_FIRST_LAYER_TOP_M,
    tree_second_layer_top_n: int = KNOWNMAP_ACTIVE_TREE_SECOND_LAYER_TOP_N,
    tree_discount_gamma: float = 0.85,
    tree_enable_diminishing_returns: bool = True,
    tree_enable_child_oracle_diagnostics: bool = True,
    path_safety_mode: str = "off",
    inflated_nav_map: np.ndarray | None = None,
    obstacle_distance_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_inflation_radius_cells: int = 0,
    safe_nav_soft_clearance_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
) -> tuple[list[tuple[int, int]] | None, dict]:
    """Select a short-horizon path segment for the known-static-map baseline."""
    if policy_name not in KNOWNMAP_POLICIES:
        raise ValueError(f"Unsupported known-map policy_name='{policy_name}'")
    if path_safety_mode not in SUPPORTED_PATH_SAFETY_MODES:
        raise ValueError(
            f"path_safety_mode must be one of {SUPPORTED_PATH_SAFETY_MODES}, got '{path_safety_mode}'"
        )
    if path_safety_mode == "soft_clearance_astar_v1":
        if inflated_nav_map is None or clearance_cost_map is None:
            raise ValueError(
                "soft_clearance_astar_v1 requires inflated_nav_map and clearance_cost_map"
            )
    if reservation_table is not None:
        if inflated_nav_map is None:
            inflated_nav_map = np.asarray(nav_map_prior)
        if clearance_cost_map is None:
            clearance_cost_map = np.zeros(nav_map_prior.shape, dtype=float)

    if policy_name == "marine_knownmap_path_v2_infosampled_tree_d2":
        return _select_knownmap_infosampled_tree_d2(
            nav_map_prior=nav_map_prior,
            robot_pos=robot_pos,
            sensor_range=sensor_range,
            last_seen_step=last_seen_step,
            staleness_map=staleness_map,
            clue_map=clue_map,
            intensity_map=intensity_map,
            search_info_map=search_info_map,
            search_info_clue_component=search_info_clue_component,
            search_info_intensity_component=search_info_intensity_component,
            current_viewpoint=current_viewpoint,
            current_anchor=current_anchor,
            current_anchor_source=current_anchor_source,
            current_anchor_centroid=current_anchor_centroid,
            current_segment_endpoint=current_segment_endpoint,
            prev_move_dir=prev_move_dir,
            kappa_commit=kappa_commit,
            lambda_u_turn=lambda_u_turn,
            segment_horizon=segment_horizon,
            top_k_anchors=top_k_anchors,
            viewpoints_per_anchor=viewpoints_per_anchor,
            gamma=gamma,
            sampling_seed_base=sampling_seed_base,
            infosampled_inspected_limit_multiplier=infosampled_inspected_limit_multiplier,
            infosampled_inspected_limit_floor=infosampled_inspected_limit_floor,
            geometry_cache=geometry_cache,
            tree_first_layer_top_m=tree_first_layer_top_m,
            tree_second_layer_top_n=tree_second_layer_top_n,
            tree_discount_gamma=tree_discount_gamma,
            tree_enable_diminishing_returns=tree_enable_diminishing_returns,
            tree_enable_child_oracle_diagnostics=tree_enable_child_oracle_diagnostics,
            path_safety_mode=path_safety_mode,
            inflated_nav_map=inflated_nav_map,
            obstacle_distance_map=obstacle_distance_map,
            clearance_cost_map=clearance_cost_map,
            safe_nav_lambda_clearance=safe_nav_lambda_clearance,
            safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
            safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
            reservation_table=reservation_table,
            team_reservation_lambda=team_reservation_lambda,
        )

    candidates = _knownmap_candidate_space(
        policy_name=policy_name,
        nav_map_prior=nav_map_prior,
        robot_pos=robot_pos,
        sensor_range=sensor_range,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        search_info_clue_component=search_info_clue_component,
        search_info_intensity_component=search_info_intensity_component,
        current_viewpoint=current_viewpoint,
        current_anchor=current_anchor,
        current_anchor_source=current_anchor_source,
        current_segment_endpoint=current_segment_endpoint,
        segment_horizon=segment_horizon,
        top_k_anchors=top_k_anchors,
        viewpoints_per_anchor=viewpoints_per_anchor,
        sampling_seed_base=sampling_seed_base,
        infosampled_inspected_limit_multiplier=infosampled_inspected_limit_multiplier,
        infosampled_inspected_limit_floor=infosampled_inspected_limit_floor,
        geometry_cache=geometry_cache,
        path_safety_mode=path_safety_mode,
        inflated_nav_map=inflated_nav_map,
        clearance_cost_map=clearance_cost_map,
        safe_nav_lambda_clearance=safe_nav_lambda_clearance,
        safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
        reservation_table=reservation_table,
        team_reservation_lambda=team_reservation_lambda,
    )
    if not candidates:
        return None, _make_knownmap_zero_details()

    evaluations = _knownmap_evaluate_segment_candidates(
        policy_name,
        candidates,
        nav_map_prior=nav_map_prior,
        sensor_range=sensor_range,
        last_seen_step=last_seen_step,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        current_viewpoint=current_viewpoint,
        current_anchor_source=current_anchor_source,
        current_anchor_centroid=current_anchor_centroid,
        prev_move_dir=prev_move_dir,
        kappa_commit=kappa_commit,
        lambda_u_turn=lambda_u_turn,
        gamma=gamma,
        geometry_cache=geometry_cache,
        path_safety_mode=path_safety_mode,
        obstacle_distance_map=obstacle_distance_map,
        clearance_cost_map=clearance_cost_map,
        safe_nav_lambda_clearance=safe_nav_lambda_clearance,
        safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
        reservation_table=reservation_table,
        team_reservation_lambda=team_reservation_lambda,
    )
    if not evaluations:
        return None, _make_knownmap_zero_details()
    best, current_viewpoint_score, best_alternative_score = _best_knownmap_evaluation(
        evaluations,
        current_viewpoint,
    )

    details = {
        "explore_utility_raw": float(best.get("explore_utility_raw", 0.0)),
        "explore_utility_norm": float(best.get("explore_utility_norm", 0.0)),
        "focus_utility_raw": float(best.get("focus_utility_raw", 0.0)),
        "focus_utility_norm": float(best.get("focus_utility_norm", 0.0)),
        "recency_utility_raw": float(best.get("recency_utility_raw", 0.0)),
        "recency_utility_norm": float(best.get("recency_utility_norm", 0.0)),
        "search_info_gain_raw": float(best.get("search_info_gain_raw", 0.0)),
        "search_info_gain_norm": float(best.get("search_info_gain_norm", 0.0)),
        "recency_bias_raw": float(best.get("recency_bias_raw", 0.0)),
        "recency_bias_norm": float(best.get("recency_bias_norm", 0.0)),
        "exec_cost_raw": float(best.get("exec_cost_raw", 0.0)),
        "exec_cost_norm": float(best.get("exec_cost_norm", 0.0)),
        "obstacle_proximity_raw": float(best.get("obstacle_proximity_raw", 0.0)),
        "clearance_penalty_raw": float(best.get("clearance_penalty_raw", 0.0)),
        "reservation_soft_penalty_raw": float(best.get("reservation_soft_penalty_raw", 0.0)),
        "reservation_same_cell_violation": bool(
            best.get("reservation_same_cell_violation", False)
        ),
        "reservation_swap_violation": bool(best.get("reservation_swap_violation", False)),
        "reservation_near_neighbor_step_ratio": float(
            best.get("reservation_near_neighbor_step_ratio", 0.0)
        ),
        "segment_min_clearance_cells": float(best.get("segment_min_clearance_cells", 0.0)),
        "segment_mean_clearance_cells": float(best.get("segment_mean_clearance_cells", 0.0)),
        "near_obstacle_step_flag": bool(best.get("near_obstacle_step_flag", False)),
        "near_obstacle_step_ratio": float(best.get("near_obstacle_step_ratio", 0.0)),
        "segment_turn_count": int(best.get("segment_turn_count", 0)),
        "path_safety_mode": str(best.get("path_safety_mode", path_safety_mode)),
        "safe_nav_lambda_clearance": float(
            best.get("safe_nav_lambda_clearance", safe_nav_lambda_clearance)
        ),
        "team_reservation_lambda": float(best.get("team_reservation_lambda", 0.0)),
        "alpha_focus": float(best.get("alpha_focus", 0.0)),
        "kappa_commit": 0.0,
        "same_anchor_cluster": bool(best.get("same_anchor_cluster", False)),
        "viewpoint_drift_norm": float(best.get("viewpoint_drift_norm", 0.0)),
        "anchor_retention_bonus": float(best.get("anchor_retention_bonus", 0.0)),
        "viewpoint_retention_bonus": float(best.get("viewpoint_retention_bonus", 0.0)),
        "candidate_count": int(best.get("candidate_count", 0)),
        "current_viewpoint_score": float(current_viewpoint_score),
        "best_alternative_score": float(best_alternative_score),
        "anchor_cell": best.get("anchor_cell"),
        "anchor_source": best.get("anchor_source"),
        "anchor_centroid_cell": best.get("anchor_centroid_cell"),
        "anchor_cluster_size": int(best.get("anchor_cluster_size", 0)),
        "anchor_cluster_peak": float(best.get("anchor_cluster_peak", 0.0)),
        "anchor_cluster_mean": float(best.get("anchor_cluster_mean", 0.0)),
        "anchor_info_clue_share": float(best.get("anchor_info_clue_share", 0.0)),
        "anchor_info_intensity_share": float(best.get("anchor_info_intensity_share", 0.0)),
        "viewpoint_cell": best.get("viewpoint_cell"),
        "viewpoint_rule": best.get("viewpoint_rule"),
        "candidate_pool_size": int(best.get("candidate_pool_size", 0)),
        "reachable_pool_size": int(best.get("reachable_pool_size", 0)),
        "a_star_checked_pool_size": int(best.get("a_star_checked_pool_size", 0)),
        "selected_viewpoint_rank": int(best.get("selected_viewpoint_rank", 0)),
        "sampling_priority_raw": float(best.get("sampling_priority_raw", 0.0)),
        "sampling_priority_norm": float(best.get("sampling_priority_norm", 0.0)),
        "viewpoint_sampling_mode": best.get("viewpoint_sampling_mode"),
        "sampled_viewpoint_pool_cells": list(best.get("sampled_viewpoint_pool_cells", [])),
        "selected_by_final_score": True,
        "sssp_build_time_ms": float(best.get("sssp_build_time_ms", 0.0)),
        "path_reconstruct_time_ms": float(best.get("path_reconstruct_time_ms", 0.0)),
        "sampling_pool_build_time_ms": float(best.get("sampling_pool_build_time_ms", 0.0)),
        "priority_feature_time_ms": float(best.get("priority_feature_time_ms", 0.0)),
        "segment_endpoint_cell": best.get("segment_endpoint_cell"),
        "segment_path_length": int(max(len(best.get("segment_path", [])) - 1, 0)),
        "planned_viewpoint_path_length": int(max(len(best.get("path_to_viewpoint", [])) - 1, 0)),
        "u_turn_penalty_term": float(best.get("u_turn_penalty_term", 0.0)),
        "u_turn_penalty_applied": bool(best.get("u_turn_penalty_applied", False)),
        "first_move_dir": best.get("first_move_dir"),
        "score_schema": (
            "infosampled"
            if policy_name == "marine_knownmap_path_v2_infosampled"
            else (
                "infofused"
                if policy_name == "marine_knownmap_path_v2_infofused"
                else "knownmap_legacy"
            )
        ),
        "total_score": float(best.get("total_score", -float("inf"))),
        "marginal_information_gain_raw": float(best.get("marginal_information_gain_raw", 0.0)),
        "marginal_information_gain_norm": float(best.get("marginal_information_gain_norm", 0.0)),
        "execution_cost_raw": float(best.get("execution_cost_raw", 0.0)),
        "execution_cost_norm": float(best.get("execution_cost_norm", 0.0)),
        "continuity_bonus_raw": float(best.get("continuity_bonus_raw", 0.0)),
        "continuity_bonus_anchor_raw": float(best.get("continuity_bonus_anchor_raw", 0.0)),
        "continuity_bonus_viewpoint_raw": float(best.get("continuity_bonus_viewpoint_raw", 0.0)),
        "marginal_information_gain_score_term": float(
            best.get("marginal_information_gain_score_term", 0.0)
        ),
        "recency_bias_score_term": float(best.get("recency_bias_score_term", 0.0)),
        "execution_cost_score_term": float(best.get("execution_cost_score_term", 0.0)),
        "continuity_bonus_score_term": float(best.get("continuity_bonus_score_term", 0.0)),
        "maneuver_penalty_raw": float(best.get("maneuver_penalty_raw", 0.0)),
        "maneuver_penalty_score_term": float(best.get("maneuver_penalty_score_term", 0.0)),
        "score_formula_label": best.get("score_formula_label"),
    }
    return list(best["segment_path"]), details


def rebuild_knownmap_segment_to_fixed_viewpoint(
    *,
    policy_name: str,
    nav_map_prior: np.ndarray,
    robot_pos: tuple[int, int],
    fixed_viewpoint_cell: tuple[int, int],
    sensor_range: int,
    last_seen_step: np.ndarray,
    staleness_map: np.ndarray | None,
    clue_map: np.ndarray | None,
    intensity_map: np.ndarray | None,
    search_info_map: np.ndarray | None = None,
    current_viewpoint: tuple[int, int] | None = None,
    current_anchor_source: str | None = None,
    current_anchor_centroid: tuple[int, int] | None = None,
    prev_move_dir: tuple[int, int] | None = None,
    kappa_commit: float = 0.0,
    lambda_u_turn: float = 2.0,
    gamma: float = 0.95,
    segment_horizon: int = 8,
    geometry_cache: dict[str, object] | None = None,
    path_safety_mode: str = "off",
    inflated_nav_map: np.ndarray | None = None,
    obstacle_distance_map: np.ndarray | None = None,
    clearance_cost_map: np.ndarray | None = None,
    safe_nav_lambda_clearance: float = 1.0,
    safe_nav_inflation_radius_cells: int = 0,
    safe_nav_soft_clearance_radius_cells: int = 0,
    reservation_table: dict[str, object] | None = None,
    team_reservation_lambda: float = 1.0,
    anchor_cell: tuple[int, int] | None = None,
    anchor_source: str | None = None,
    anchor_centroid_cell: tuple[int, int] | None = None,
    candidate_metadata: dict[str, object] | None = None,
    viewpoint_rule: str = "fixed_viewpoint_reroute",
) -> tuple[list[tuple[int, int]] | None, dict[str, object]]:
    if path_safety_mode == "soft_clearance_astar_v1":
        if inflated_nav_map is None or clearance_cost_map is None:
            raise ValueError(
                "soft_clearance_astar_v1 requires inflated_nav_map and clearance_cost_map"
            )
    if reservation_table is not None:
        if inflated_nav_map is None:
            inflated_nav_map = np.asarray(nav_map_prior)
        if clearance_cost_map is None:
            clearance_cost_map = np.zeros(nav_map_prior.shape, dtype=float)

    resolved_anchor_cell = (
        tuple(int(v) for v in anchor_cell)
        if anchor_cell is not None
        else tuple(int(v) for v in fixed_viewpoint_cell)
    )
    resolved_anchor_centroid = (
        tuple(int(v) for v in anchor_centroid_cell)
        if anchor_centroid_cell is not None
        else resolved_anchor_cell
    )
    anchor_cluster = {
        "anchor_cell": resolved_anchor_cell,
        "anchor_centroid_cell": resolved_anchor_centroid,
        "anchor_cluster_size": 1,
        "anchor_cluster_peak": 0.0,
        "anchor_cluster_mean": 0.0,
        "anchor_value": 0.0,
        "anchor_source": str(anchor_source) if anchor_source is not None else "fixed_viewpoint",
        "anchor_info_clue_share": 0.0,
        "anchor_info_intensity_share": 0.0,
    }
    candidate = _knownmap_segment_candidate(
        anchor_cluster,
        tuple(int(v) for v in fixed_viewpoint_cell),
        nav_map_prior,
        tuple(int(v) for v in robot_pos),
        segment_horizon=segment_horizon,
        viewpoint_rule=viewpoint_rule,
        candidate_metadata=candidate_metadata,
        path_safety_mode=path_safety_mode,
        inflated_nav_map=inflated_nav_map,
        clearance_cost_map=clearance_cost_map,
        safe_nav_lambda_clearance=safe_nav_lambda_clearance,
        safe_nav_inflation_radius_cells=safe_nav_inflation_radius_cells,
        reservation_table=reservation_table,
        team_reservation_lambda=team_reservation_lambda,
    )
    if candidate is None:
        return None, _make_knownmap_zero_details()

    evaluations = _knownmap_evaluate_segment_candidates(
        policy_name,
        [candidate],
        nav_map_prior=nav_map_prior,
        sensor_range=sensor_range,
        last_seen_step=last_seen_step,
        staleness_map=staleness_map,
        clue_map=clue_map,
        intensity_map=intensity_map,
        search_info_map=search_info_map,
        current_viewpoint=current_viewpoint,
        current_anchor_source=current_anchor_source,
        current_anchor_centroid=current_anchor_centroid,
        prev_move_dir=prev_move_dir,
        kappa_commit=kappa_commit,
        lambda_u_turn=lambda_u_turn,
        gamma=gamma,
        geometry_cache=geometry_cache,
        path_safety_mode=path_safety_mode,
        obstacle_distance_map=obstacle_distance_map,
        clearance_cost_map=clearance_cost_map,
        safe_nav_lambda_clearance=safe_nav_lambda_clearance,
        safe_nav_soft_clearance_radius_cells=safe_nav_soft_clearance_radius_cells,
        reservation_table=reservation_table,
        team_reservation_lambda=team_reservation_lambda,
    )
    if not evaluations:
        return None, _make_knownmap_zero_details()

    best = evaluations[0]
    details = _make_knownmap_zero_details()
    details.update(
        {
            "explore_utility_raw": float(best.get("explore_utility_raw", 0.0)),
            "explore_utility_norm": float(best.get("explore_utility_norm", 0.0)),
            "focus_utility_raw": float(best.get("focus_utility_raw", 0.0)),
            "focus_utility_norm": float(best.get("focus_utility_norm", 0.0)),
            "recency_utility_raw": float(best.get("recency_utility_raw", 0.0)),
            "recency_utility_norm": float(best.get("recency_utility_norm", 0.0)),
            "search_info_gain_raw": float(best.get("search_info_gain_raw", 0.0)),
            "search_info_gain_norm": float(best.get("search_info_gain_norm", 0.0)),
            "recency_bias_raw": float(best.get("recency_bias_raw", 0.0)),
            "recency_bias_norm": float(best.get("recency_bias_norm", 0.0)),
            "exec_cost_raw": float(best.get("exec_cost_raw", 0.0)),
            "exec_cost_norm": float(best.get("exec_cost_norm", 0.0)),
            "obstacle_proximity_raw": float(best.get("obstacle_proximity_raw", 0.0)),
            "clearance_penalty_raw": float(best.get("clearance_penalty_raw", 0.0)),
            "reservation_soft_penalty_raw": float(
                best.get("reservation_soft_penalty_raw", 0.0)
            ),
            "reservation_same_cell_violation": bool(
                best.get("reservation_same_cell_violation", False)
            ),
            "reservation_swap_violation": bool(
                best.get("reservation_swap_violation", False)
            ),
            "reservation_near_neighbor_step_ratio": float(
                best.get("reservation_near_neighbor_step_ratio", 0.0)
            ),
            "segment_min_clearance_cells": float(
                best.get("segment_min_clearance_cells", 0.0)
            ),
            "segment_mean_clearance_cells": float(
                best.get("segment_mean_clearance_cells", 0.0)
            ),
            "near_obstacle_step_flag": bool(best.get("near_obstacle_step_flag", False)),
            "near_obstacle_step_ratio": float(best.get("near_obstacle_step_ratio", 0.0)),
            "segment_turn_count": int(best.get("segment_turn_count", 0)),
            "path_safety_mode": str(best.get("path_safety_mode", path_safety_mode)),
            "safe_nav_lambda_clearance": float(
                best.get("safe_nav_lambda_clearance", safe_nav_lambda_clearance)
            ),
            "team_reservation_lambda": float(best.get("team_reservation_lambda", 0.0)),
            "alpha_focus": 0.0,
            "kappa_commit": 0.0,
            "same_anchor_cluster": bool(best.get("same_anchor_cluster", False)),
            "viewpoint_drift_norm": float(best.get("viewpoint_drift_norm", 0.0)),
            "anchor_retention_bonus": float(best.get("anchor_retention_bonus", 0.0)),
            "viewpoint_retention_bonus": float(best.get("viewpoint_retention_bonus", 0.0)),
            "candidate_count": int(best.get("candidate_count", 1)),
            "current_viewpoint_score": float(best.get("total_score", 0.0)),
            "best_alternative_score": float(best.get("total_score", 0.0)),
            "anchor_cell": best.get("anchor_cell"),
            "anchor_source": best.get("anchor_source"),
            "anchor_centroid_cell": best.get("anchor_centroid_cell"),
            "anchor_cluster_size": int(best.get("anchor_cluster_size", 0)),
            "anchor_cluster_peak": float(best.get("anchor_cluster_peak", 0.0)),
            "anchor_cluster_mean": float(best.get("anchor_cluster_mean", 0.0)),
            "anchor_info_clue_share": float(best.get("anchor_info_clue_share", 0.0)),
            "anchor_info_intensity_share": float(
                best.get("anchor_info_intensity_share", 0.0)
            ),
            "viewpoint_cell": best.get("viewpoint_cell"),
            "viewpoint_rule": best.get("viewpoint_rule"),
            "candidate_pool_size": int(best.get("candidate_pool_size", 0)),
            "reachable_pool_size": int(best.get("reachable_pool_size", 0)),
            "a_star_checked_pool_size": int(best.get("a_star_checked_pool_size", 0)),
            "selected_viewpoint_rank": int(best.get("selected_viewpoint_rank", 0)),
            "sampling_priority_raw": float(best.get("sampling_priority_raw", 0.0)),
            "sampling_priority_norm": float(best.get("sampling_priority_norm", 0.0)),
            "viewpoint_sampling_mode": best.get("viewpoint_sampling_mode"),
            "sampled_viewpoint_pool_cells": list(
                best.get("sampled_viewpoint_pool_cells", [])
            ),
            "selected_by_final_score": True,
            "sssp_build_time_ms": float(best.get("sssp_build_time_ms", 0.0)),
            "path_reconstruct_time_ms": float(best.get("path_reconstruct_time_ms", 0.0)),
            "sampling_pool_build_time_ms": float(
                best.get("sampling_pool_build_time_ms", 0.0)
            ),
            "priority_feature_time_ms": float(best.get("priority_feature_time_ms", 0.0)),
            "segment_endpoint_cell": best.get("segment_endpoint_cell"),
            "segment_path_length": int(max(len(best.get("segment_path", [])) - 1, 0)),
            "planned_viewpoint_path_length": int(
                max(len(best.get("path_to_viewpoint", [])) - 1, 0)
            ),
            "u_turn_penalty_term": float(best.get("u_turn_penalty_term", 0.0)),
            "u_turn_penalty_applied": bool(best.get("u_turn_penalty_applied", False)),
            "first_move_dir": best.get("first_move_dir"),
            "score_schema": (
                "infosampled"
                if policy_name == "marine_knownmap_path_v2_infosampled"
                else (
                    "infofused"
                    if policy_name == "marine_knownmap_path_v2_infofused"
                    else "knownmap_legacy"
                )
            ),
            "total_score": float(best.get("total_score", -float("inf"))),
            "marginal_information_gain_raw": float(
                best.get("marginal_information_gain_raw", 0.0)
            ),
            "marginal_information_gain_norm": float(
                best.get("marginal_information_gain_norm", 0.0)
            ),
            "execution_cost_raw": float(best.get("execution_cost_raw", 0.0)),
            "execution_cost_norm": float(best.get("execution_cost_norm", 0.0)),
            "continuity_bonus_raw": float(best.get("continuity_bonus_raw", 0.0)),
            "continuity_bonus_anchor_raw": float(
                best.get("continuity_bonus_anchor_raw", 0.0)
            ),
            "continuity_bonus_viewpoint_raw": float(
                best.get("continuity_bonus_viewpoint_raw", 0.0)
            ),
            "marginal_information_gain_score_term": float(
                best.get("marginal_information_gain_score_term", 0.0)
            ),
            "recency_bias_score_term": float(best.get("recency_bias_score_term", 0.0)),
            "execution_cost_score_term": float(
                best.get("execution_cost_score_term", 0.0)
            ),
            "continuity_bonus_score_term": float(
                best.get("continuity_bonus_score_term", 0.0)
            ),
            "maneuver_penalty_raw": float(best.get("maneuver_penalty_raw", 0.0)),
            "maneuver_penalty_score_term": float(
                best.get("maneuver_penalty_score_term", 0.0)
            ),
            "score_formula_label": best.get("score_formula_label"),
        }
    )
    return list(best["segment_path"]), details
