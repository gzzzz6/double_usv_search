"""
Utilities for fitting and querying a continuous suspicion field with a GP.
"""

from __future__ import annotations

from copy import deepcopy

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel


def default_kernel(
    length_scale: float = 5.0,
    signal_var: float = 1.0,
    noise_level: float = 0.05,
    signal_var_bounds: tuple[float, float] = (1e-6, 10.0),
    length_scale_bounds: tuple[float, float] = (1.0, 120.0),
    noise_level_bounds: tuple[float, float] = (1e-6, 0.25),
) -> object:
    """Return a reasonable default kernel for the suspicion field."""
    return (
        ConstantKernel(signal_var, constant_value_bounds=signal_var_bounds)
        * RBF(length_scale=length_scale, length_scale_bounds=length_scale_bounds)
        + WhiteKernel(noise_level=noise_level, noise_level_bounds=noise_level_bounds)
    )


class GPSuspicionField:
    """Exact GP backend for a continuous suspicion field."""

    MIN_OBS_FOR_FIT = 3

    def __init__(
        self,
        kernel_cfg=None,
        noise_cfg=None,
        prior_mean: float = 0.0,
        n_restarts_optimizer: int = 0,
    ):
        kernel = kernel_cfg if kernel_cfg is not None else default_kernel()
        self.prior_mean = float(prior_mean)
        self.noise_cfg = noise_cfg
        self.n_restarts_optimizer = int(n_restarts_optimizer)

        self._base_kernel = deepcopy(kernel)
        self._optimized_kernel = deepcopy(kernel)
        self.gp = self._make_regressor(
            kernel=deepcopy(self._base_kernel),
            optimize_hyperparams=True,
        )

        self.X_obs: np.ndarray = np.empty((0, 2), dtype=float)
        self.y_obs: np.ndarray = np.empty(0, dtype=float)
        self.t_obs: np.ndarray = np.empty(0, dtype=float)
        self.w_obs: np.ndarray = np.empty(0, dtype=float)

        self._mu_map: np.ndarray | None = None
        self._var_map: np.ndarray | None = None
        self._acq_map: np.ndarray | None = None
        self._fitted: bool = False

    def _make_regressor(
        self,
        kernel,
        optimize_hyperparams: bool,
    ) -> GaussianProcessRegressor:
        kwargs = {
            "kernel": deepcopy(kernel),
            "normalize_y": False,
            "copy_X_train": False,
            "optimizer": "fmin_l_bfgs_b" if optimize_hyperparams else None,
            "n_restarts_optimizer": (
                self.n_restarts_optimizer if optimize_hyperparams else 0
            ),
        }
        if self.noise_cfg is not None:
            kwargs["alpha"] = float(self.noise_cfg)
        return GaussianProcessRegressor(**kwargs)

    def _invalidate_cache(self) -> None:
        self._mu_map = None
        self._var_map = None
        self._acq_map = None
        self._fitted = False

    def add_observation(
        self,
        xy,
        value: float,
        t: float,
        noise: float | None = None,
        weight: float = 1.0,
    ) -> None:
        _ = noise
        xy = np.asarray(xy, dtype=float).reshape(1, 2)
        self.X_obs = np.vstack([self.X_obs, xy])
        self.y_obs = np.append(self.y_obs, float(value))
        self.t_obs = np.append(self.t_obs, float(t))
        self.w_obs = np.append(self.w_obs, float(weight))
        self._invalidate_cache()

    def add_observations(
        self,
        X,
        y,
        t,
        noise=None,
        weight=None,
    ) -> None:
        _ = noise
        X = np.asarray(X, dtype=float).reshape(-1, 2)
        y = np.asarray(y, dtype=float).ravel()
        n = len(y)
        t_arr = (
            np.full(n, float(t), dtype=float)
            if np.isscalar(t)
            else np.asarray(t, dtype=float).ravel()
        )
        w_arr = (
            np.ones(n, dtype=float)
            if weight is None
            else np.full(n, float(weight))
            if np.isscalar(weight)
            else np.asarray(weight, dtype=float).ravel()
        )

        self.X_obs = np.vstack([self.X_obs, X])
        self.y_obs = np.append(self.y_obs, y)
        self.t_obs = np.append(self.t_obs, t_arr)
        self.w_obs = np.append(self.w_obs, w_arr)
        self._invalidate_cache()

    def prune_observations(
        self,
        current_time: float,
        window: float | None = None,
        max_points: int | None = None,
    ) -> None:
        mask = np.ones(len(self.t_obs), dtype=bool)
        if window is not None:
            mask &= (current_time - self.t_obs) <= window
        if max_points is not None:
            indices = np.where(mask)[0]
            if len(indices) > max_points:
                keep = indices[-max_points:]
                mask[:] = False
                mask[keep] = True

        self.X_obs = self.X_obs[mask]
        self.y_obs = self.y_obs[mask]
        self.t_obs = self.t_obs[mask]
        self.w_obs = self.w_obs[mask]
        self._invalidate_cache()

    def _refit(self, optimize_hyperparams: bool) -> bool:
        if len(self.X_obs) < self.MIN_OBS_FOR_FIT:
            self._fitted = False
            return False

        kernel = deepcopy(self._optimized_kernel)
        regressor = self._make_regressor(
            kernel=kernel,
            optimize_hyperparams=optimize_hyperparams,
        )
        y_centered = self.y_obs - self.prior_mean

        try:
            regressor.fit(self.X_obs, y_centered)
        except Exception as exc:  # noqa: BLE001
            print(f"[GPSuspicionField] refit failed: {exc}")
            self._fitted = False
            return False

        self.gp = regressor
        self._optimized_kernel = deepcopy(getattr(regressor, "kernel_", regressor.kernel))
        self._fitted = True
        return True

    def fit(self) -> bool:
        """Backward-compatible alias for a full refit."""
        return self.refit_full()

    def refit_fast(self) -> bool:
        """Rebuild the GP posterior using fixed hyperparameters."""
        return self._refit(optimize_hyperparams=False)

    def refit_full(self) -> bool:
        """Rebuild the GP posterior and allow kernel hyperparameter search."""
        return self._refit(optimize_hyperparams=True)

    def kernel_summary(self) -> str:
        """Return the current fitted kernel for lightweight diagnostics."""
        kernel = getattr(self.gp, "kernel_", self.gp.kernel)
        return str(kernel)

    def predict(self, X_query) -> tuple[np.ndarray, np.ndarray]:
        X_query = np.asarray(X_query, dtype=float).reshape(-1, 2)
        if not self._fitted:
            mu = np.full(len(X_query), self.prior_mean, dtype=float)
            var = np.ones(len(X_query), dtype=float)
            return mu, var

        mu_centered, std = self.gp.predict(X_query, return_std=True)
        mu = np.clip(mu_centered + self.prior_mean, 0.0, None)
        var = np.clip(std**2, 0.0, None)
        return mu, var

    def build_maps(
        self,
        grid_xy: np.ndarray,
        beta: float = 1.0,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        original_shape: tuple[int, int] | None = None
        if grid_xy.ndim == 3:
            original_shape = grid_xy.shape[:2]
            flat = grid_xy.reshape(-1, 2)
        else:
            flat = grid_xy

        mu, var = self.predict(flat)
        sigma = np.sqrt(np.clip(var, 0.0, None))
        acq = mu + beta * sigma

        if original_shape is not None:
            mu = mu.reshape(original_shape)
            var = var.reshape(original_shape)
            acq = acq.reshape(original_shape)

        self._mu_map = mu
        self._var_map = var
        self._acq_map = acq
        return mu, var, acq

    def acquisition(self, xy, beta: float = 1.0) -> float:
        xy = np.asarray(xy, dtype=float).reshape(1, 2)
        mu, var = self.predict(xy)
        return float(mu[0] + beta * np.sqrt(var[0]))

    def reset(self) -> None:
        self.X_obs = np.empty((0, 2), dtype=float)
        self.y_obs = np.empty(0, dtype=float)
        self.t_obs = np.empty(0, dtype=float)
        self.w_obs = np.empty(0, dtype=float)
        self._optimized_kernel = deepcopy(self._base_kernel)
        self.gp = self._make_regressor(
            kernel=deepcopy(self._base_kernel),
            optimize_hyperparams=True,
        )
        self._invalidate_cache()

    def get_state(self) -> dict:
        return {
            "X_obs": self.X_obs.copy(),
            "y_obs": self.y_obs.copy(),
            "t_obs": self.t_obs.copy(),
            "w_obs": self.w_obs.copy(),
            "fitted": self._fitted,
        }

    def load_state(self, state: dict) -> None:
        self.X_obs = state["X_obs"].copy()
        self.y_obs = state["y_obs"].copy()
        self.t_obs = state["t_obs"].copy()
        self.w_obs = state["w_obs"].copy()
        self._invalidate_cache()

    @property
    def mu_map(self) -> np.ndarray | None:
        return self._mu_map

    @property
    def var_map(self) -> np.ndarray | None:
        return self._var_map

    @property
    def acq_map(self) -> np.ndarray | None:
        return self._acq_map

    @property
    def n_obs(self) -> int:
        return len(self.y_obs)
