import numpy as np

UNKNOWN = -1
FREE = 0
OCCUPIED = 1
DEFAULT_MAP_HEIGHT_CELLS = 40
DEFAULT_MAP_WIDTH_CELLS = 60

SEA_STYLE_MAP_KINDS = (
    "open_water",
    "sparse_platforms",
    "island_channel",
    "harbor_cove",
    "breakwater_inlet",
    "peninsula_passage",
)
STRUCTURED_MAP_KINDS = ("obstacle_field", "benchmark") + SEA_STYLE_MAP_KINDS
SUPPORTED_MAP_KINDS = ("obstacle_field", "benchmark", "random") + SEA_STYLE_MAP_KINDS

_BENCHMARK_RECTS = (
    (8, 12, 10, 25),
    (18, 22, 30, 45),
    (26, 34, 20, 24),
    (10, 18, 48, 52),
)
_SPARSE_PLATFORMS_RECTS = (
    (8, 11, 14, 17),
    (12, 15, 42, 45),
    (19, 23, 28, 32),
    (27, 30, 10, 13),
    (29, 33, 45, 49),
)
_ISLAND_CHANNEL_RECTS = (
    (10, 29, 24, 37),
    (5, 11, 42, 50),
    (29, 35, 41, 50),
)
_HARBOR_COVE_RECTS = (
    (6, 12, 34, 59),
    (28, 34, 34, 59),
    (12, 28, 51, 59),
)
_BREAKWATER_INLET_RECTS = (
    (8, 10, 10, 43),
    (30, 32, 10, 43),
    (15, 25, 42, 45),
)
_PENINSULA_PASSAGE_RECTS = (
    (14, 39, 18, 24),
    (8, 19, 33, 40),
    (24, 30, 40, 47),
)


def _fill_rect(grid: np.ndarray, r0: int, r1: int, c0: int, c1: int) -> None:
    r0 = max(0, r0)
    c0 = max(0, c0)
    r1 = min(grid.shape[0], r1)
    c1 = min(grid.shape[1], c1)
    if r0 < r1 and c0 < c1:
        grid[r0:r1, c0:c1] = OCCUPIED


def _empty_bounded_world(h: int, w: int) -> np.ndarray:
    true_map = np.zeros((h, w), dtype=int)
    true_map[0, :] = OCCUPIED
    true_map[-1, :] = OCCUPIED
    true_map[:, 0] = OCCUPIED
    true_map[:, -1] = OCCUPIED
    return true_map


def _validate_world_shape(h: int, w: int) -> tuple[int, int]:
    h = int(h)
    w = int(w)
    if h < 3 or w < 3:
        raise ValueError(f"World shape must be at least 3x3 cells, got h={h}, w={w}")
    return h, w


def _scale_interval(start: int, end: int, base_extent: int, target_extent: int) -> tuple[int, int]:
    scaled_start = int(round((float(start) / float(base_extent)) * float(target_extent)))
    scaled_end = int(round((float(end) / float(base_extent)) * float(target_extent)))
    if end > start and scaled_end <= scaled_start:
        scaled_end = min(int(target_extent), scaled_start + 1)
    return scaled_start, scaled_end


def _scaled_rect(
    rect: tuple[int, int, int, int],
    h: int,
    w: int,
    *,
    base_h: int = DEFAULT_MAP_HEIGHT_CELLS,
    base_w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> tuple[int, int, int, int]:
    r0, r1, c0, c1 = rect
    sr0, sr1 = _scale_interval(r0, r1, base_h, h)
    sc0, sc1 = _scale_interval(c0, c1, base_w, w)
    return sr0, sr1, sc0, sc1


def _fill_scaled_rects(
    true_map: np.ndarray,
    rects: tuple[tuple[int, int, int, int], ...],
) -> None:
    h, w = true_map.shape
    for rect in rects:
        _fill_rect(true_map, *_scaled_rect(rect, h, w))


def create_benchmark_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """Create the fixed benchmark map used by the baseline experiments."""
    h, w = _validate_world_shape(h, w)
    true_map = _empty_bounded_world(h, w)
    _fill_scaled_rects(true_map, _BENCHMARK_RECTS)
    return true_map


def create_obstacle_field_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """Create the obstacle_field map (identical to the legacy benchmark map)."""
    return create_benchmark_world(h=h, w=w)


def create_open_water_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """Open sea with only the outer boundary occupied."""
    h, w = _validate_world_shape(h, w)
    return _empty_bounded_world(h, w)


def create_sparse_platforms_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """Sparse isolated obstacles, similar to buoys or small offshore structures."""
    h, w = _validate_world_shape(h, w)
    true_map = _empty_bounded_world(h, w)
    _fill_scaled_rects(true_map, _SPARSE_PLATFORMS_RECTS)
    return true_map


def create_island_channel_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """One dominant island plus secondary land that creates meaningful rerouting."""
    h, w = _validate_world_shape(h, w)
    true_map = _empty_bounded_world(h, w)
    _fill_scaled_rects(true_map, _ISLAND_CHANNEL_RECTS)
    return true_map


def create_harbor_cove_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """Concave shoreline geometry, leaving a harbor-like cove open to the west."""
    h, w = _validate_world_shape(h, w)
    true_map = _empty_bounded_world(h, w)
    _fill_scaled_rects(true_map, _HARBOR_COVE_RECTS)
    return true_map


def create_breakwater_inlet_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """Long sparse barriers that form an inlet with a narrow entrance."""
    h, w = _validate_world_shape(h, w)
    true_map = _empty_bounded_world(h, w)
    _fill_scaled_rects(true_map, _BREAKWATER_INLET_RECTS)
    return true_map


def create_peninsula_passage_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
) -> np.ndarray:
    """A peninsula and nearby shoals that create asymmetric passages."""
    h, w = _validate_world_shape(h, w)
    true_map = _empty_bounded_world(h, w)
    _fill_scaled_rects(true_map, _PENINSULA_PASSAGE_RECTS)
    return true_map


def create_random_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
    obstacle_prob: float = 0.18,
    seed: int = 1,
) -> np.ndarray:
    """Create a simple random occupancy map."""
    h, w = _validate_world_shape(h, w)
    rng = np.random.default_rng(seed)
    true_map = (rng.random((h, w)) < obstacle_prob).astype(int)
    true_map[0, :] = OCCUPIED
    true_map[-1, :] = OCCUPIED
    true_map[:, 0] = OCCUPIED
    true_map[:, -1] = OCCUPIED

    # Keep the default launch corner navigable.
    true_map[1:3, 1:3] = FREE
    return true_map


def create_world(
    h: int = DEFAULT_MAP_HEIGHT_CELLS,
    w: int = DEFAULT_MAP_WIDTH_CELLS,
    obstacle_prob: float = 0.18,
    seed: int = 1,
    map_kind: str = "obstacle_field",
) -> np.ndarray:
    """Backward-compatible wrapper around the explicit map constructors."""
    builders = {
        "obstacle_field": create_obstacle_field_world,
        "benchmark": create_benchmark_world,
        "open_water": create_open_water_world,
        "sparse_platforms": create_sparse_platforms_world,
        "island_channel": create_island_channel_world,
        "harbor_cove": create_harbor_cove_world,
        "breakwater_inlet": create_breakwater_inlet_world,
        "peninsula_passage": create_peninsula_passage_world,
    }
    if map_kind in builders:
        return builders[map_kind](h=h, w=w)
    if map_kind == "random":
        return create_random_world(
            h=h,
            w=w,
            obstacle_prob=obstacle_prob,
            seed=seed,
        )
    raise ValueError(
        f"Unknown map_kind='{map_kind}'. Supported values: {SUPPORTED_MAP_KINDS}"
    )


def find_free_start(true_map):
    h, w = true_map.shape
    for i in range(1, h - 1):
        for j in range(1, w - 1):
            if true_map[i, j] == FREE:
                return (i, j)
    raise ValueError("No free start cell found in the map.")


def find_target_start(true_map, robot_pos, min_dist=8, seed=7):
    rng = np.random.default_rng(seed)
    free_cells = np.argwhere(true_map == FREE)
    candidates = []
    for x, y in free_cells:
        if abs(x - robot_pos[0]) + abs(y - robot_pos[1]) >= min_dist:
            candidates.append((x, y))
    if not candidates:
        for x, y in free_cells:
            candidates.append((x, y))
    return candidates[rng.integers(len(candidates))]


def in_bounds(pos, grid):
    x, y = pos
    return 0 <= x < grid.shape[0] and 0 <= y < grid.shape[1]


def neighbors4(pos, grid):
    x, y = pos
    cands = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
    return [p for p in cands if in_bounds(p, grid)]


def reveal_cells(true_map, known_map, robot_pos, sensor_range=4):
    rx, ry = robot_pos
    h, w = true_map.shape
    for x in range(max(0, rx - sensor_range), min(h, rx + sensor_range + 1)):
        for y in range(max(0, ry - sensor_range), min(w, ry + sensor_range + 1)):
            if (x - rx) ** 2 + (y - ry) ** 2 <= sensor_range**2:
                known_map[x, y] = true_map[x, y]


def sensor_cells(center, shape, sensor_range):
    cx, cy = center
    h, w = shape
    cells = []
    for x in range(max(0, cx - sensor_range), min(h, cx + sensor_range + 1)):
        for y in range(max(0, cy - sensor_range), min(w, cy + sensor_range + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= sensor_range**2:
                cells.append((x, y))
    return cells


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
