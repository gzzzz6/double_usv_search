def is_frontier(cell, known_map):
    x, y = cell
    if known_map[x, y] != FREE:
        return False
    for nx, ny in neighbors4(cell, known_map):
        if known_map[nx, ny] == UNKNOWN:
            return True
    return False


def find_frontiers(known_map):
    frontiers = []
    h, w = known_map.shape
    for x in range(h):
        for y in range(w):
            if is_frontier((x, y), known_map):
                frontiers.append((x, y))
    return frontiers


def frontier_gain(pos, known_map, radius=3):
    fx, fy = pos
    h, w = known_map.shape
    gain = 0
    for x in range(max(0, fx - radius), min(h, fx + radius + 1)):
        for y in range(max(0, fy - radius), min(w, fy + radius + 1)):
            if (x - fx) ** 2 + (y - fy) ** 2 <= radius**2:
                if known_map[x, y] == UNKNOWN:
                    gain += 1
    return gain

def reveal_cells(true_map, known_map, robot_pos, sensor_range=4):
    rx, ry = robot_pos
    h, w = true_map.shape
    for x in range(max(0, rx - sensor_range), min(h, rx + sensor_range + 1)):
        for y in range(max(0, ry - sensor_range), min(w, ry + sensor_range + 1)):
            if (x - rx) ** 2 + (y - ry) ** 2 <= sensor_range**2:
                known_map[x, y] = true_map[x, y]

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
    