"""
core_gp_measurement.py
----------------------
把「机器人当前位置 / 传感器返回」转换成 GP 训练样本。
统一处理栅格坐标 ↔ 世界坐标转换，避免各模块各自换算。

坐标约定
--------
- 栅格坐标 (r, c)：r = 行（对应 y 轴），c = 列（对应 x 轴）
- 世界坐标 (x, y)：x = origin_x + (c + 0.5) * resolution
                   y = origin_y + (r + 0.5) * resolution
- GP 输入统一使用 [x, y] 世界坐标，shape (N, 2)
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# 1) 坐标转换
# ---------------------------------------------------------------------------

def grid_to_world(cell: tuple[int, int],
                  resolution: float = 1.0,
                  origin: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    """栅格格心 → 世界坐标 [x, y]。

    Parameters
    ----------
    cell : (row, col)
    resolution : 每格大小（米/格）
    origin : 地图左上角的世界坐标 (origin_x, origin_y)

    Returns
    -------
    np.ndarray shape (2,)，[x, y]
    """
    r, c = int(cell[0]), int(cell[1])
    x = origin[0] + (c + 0.5) * resolution
    y = origin[1] + (r + 0.5) * resolution
    return np.array([x, y], dtype=float)


def world_to_grid(xy,
                  resolution: float = 1.0,
                  origin: tuple[float, float] = (0.0, 0.0)) -> tuple[int, int]:
    """世界坐标 → 栅格索引 (row, col)（截断取整）。"""
    x, y = float(xy[0]), float(xy[1])
    c = int((x - origin[0]) / resolution)
    r = int((y - origin[1]) / resolution)
    return (r, c)


def make_grid_xy(h: int,
                 w: int,
                 resolution: float = 1.0,
                 origin: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    """构建整张栅格的世界坐标矩阵，供 GPSuspicionField.build_maps() 使用。

    Returns
    -------
    np.ndarray shape (H, W, 2)，每个元素是 [x, y] 世界坐标
    """
    rows = np.arange(h, dtype=float)
    cols = np.arange(w, dtype=float)
    C, R = np.meshgrid(cols, rows)          # (H, W)
    X = origin[0] + (C + 0.5) * resolution
    Y = origin[1] + (R + 0.5) * resolution
    return np.stack([X, Y], axis=-1)        # (H, W, 2)


# ---------------------------------------------------------------------------
# 2) 传感器盘内采样点生成
# ---------------------------------------------------------------------------

def sample_points_in_sensor_disk(robot_pos: tuple[int, int],
                                 sensor_range: float,
                                 resolution: float = 1.0,
                                 origin: tuple[float, float] = (0.0, 0.0),
                                 mode: str = "grid") -> np.ndarray:
    """生成传感器圆盘内的采样点（世界坐标）。

    Parameters
    ----------
    robot_pos : (row, col) 栅格坐标
    sensor_range : 传感器半径（格子数）
    mode : "grid" 取圆盘内所有整格格心；
           "random" 随机均匀采样（需额外传 rng）

    Returns
    -------
    np.ndarray shape (N, 2)，[x, y] 世界坐标
    """
    r0, c0 = int(robot_pos[0]), int(robot_pos[1])
    sr = int(np.ceil(sensor_range))
    points = []

    if mode == "grid":
        for dr in range(-sr, sr + 1):
            for dc in range(-sr, sr + 1):
                if dr * dr + dc * dc <= sensor_range * sensor_range:
                    xy = grid_to_world((r0 + dr, c0 + dc), resolution, origin)
                    points.append(xy)
    else:
        raise ValueError(f"不支持的 mode='{mode}'，请使用 'grid'。")

    return np.array(points, dtype=float) if points else np.empty((0, 2))


# ---------------------------------------------------------------------------
# 3) 从隐藏真值场采样训练对
# ---------------------------------------------------------------------------

def sample_suspicion_field(field_fn,
                           robot_pos: tuple[int, int],
                           sensor_range: float,
                           rng: np.random.Generator,
                           n_samples: int | None = None,
                           noise_std: float = 0.05,
                           resolution: float = 1.0,
                           origin: tuple[float, float] = (0.0, 0.0),
                           map_shape: tuple[int, int] | None = None
                           ) -> tuple[np.ndarray, np.ndarray]:
    """在传感器圆盘内采样隐藏真值场，加噪后返回 GP 训练对。

    Parameters
    ----------
    field_fn : callable(r, c) -> float
        隐藏真值可疑度场（栅格坐标输入）。
    robot_pos : (row, col)
    sensor_range : 半径（格子数）
    rng : numpy Generator
    n_samples : 若不为 None，从圆盘内随机选 n_samples 格
    noise_std : 观测高斯噪声标准差
    map_shape : (H, W)，用于边界裁剪；为 None 则不裁剪

    Returns
    -------
    X_local : np.ndarray shape (N, 2)，世界坐标
    y_local : np.ndarray shape (N,)，含噪观测
    """
    r0, c0 = int(robot_pos[0]), int(robot_pos[1])
    sr = int(np.ceil(sensor_range))
    disk_cells: list[tuple[int, int]] = []

    for dr in range(-sr, sr + 1):
        for dc in range(-sr, sr + 1):
            if dr * dr + dc * dc <= sensor_range * sensor_range:
                nr, nc = r0 + dr, c0 + dc
                if map_shape is not None:
                    if not (0 <= nr < map_shape[0] and 0 <= nc < map_shape[1]):
                        continue
                disk_cells.append((nr, nc))

    if not disk_cells:
        return np.empty((0, 2)), np.empty(0)

    if n_samples is not None and n_samples < len(disk_cells):
        indices = rng.choice(len(disk_cells), size=n_samples, replace=False)
        disk_cells = [disk_cells[i] for i in indices]

    X_local = np.array(
        [grid_to_world(cell, resolution, origin) for cell in disk_cells],
        dtype=float,
    )
    y_true = np.array([field_fn(r, c) for r, c in disk_cells], dtype=float)
    y_local = np.clip(y_true + rng.normal(0.0, noise_std, size=len(y_true)), 0.0, None)
    return X_local, y_local


# ---------------------------------------------------------------------------
# 4) 真值场评估辅助
# ---------------------------------------------------------------------------

def build_true_field_map(field_fn,
                         true_map: np.ndarray,
                         free_mask: np.ndarray | None = None) -> np.ndarray:
    """把 field_fn(r,c) 展开成 (H, W) numpy 数组。

    Parameters
    ----------
    free_mask : 若给出，在 OCCUPIED 格上置 0
    """
    h, w = true_map.shape
    field = np.zeros((h, w), dtype=float)
    for r in range(h):
        for c in range(w):
            field[r, c] = field_fn(r, c)
    if free_mask is not None:
        field[~free_mask] = 0.0
    return field


def compute_field_rmse(mu_map: np.ndarray,
                       true_field: np.ndarray,
                       free_mask: np.ndarray) -> float:
    """在所有 free 格上计算 GP 预测均值与真值的 RMSE。"""
    diff = (mu_map[free_mask] - true_field[free_mask]) ** 2
    return float(np.sqrt(np.mean(diff))) if diff.size > 0 else 0.0


def compute_top_region_recall(covered_mask: np.ndarray,
                               true_field: np.ndarray,
                               free_mask: np.ndarray,
                               top_frac: float = 0.2) -> float:
    """高值区命中率：真值 top_frac 的 free 格中，被 covered 的比例。"""
    vals = true_field[free_mask]
    if vals.size == 0:
        return 0.0
    threshold = np.percentile(vals, 100.0 * (1.0 - top_frac))
    top_mask = free_mask & (true_field >= threshold)
    if top_mask.sum() == 0:
        return 0.0
    return float(covered_mask[top_mask].sum() / top_mask.sum())
