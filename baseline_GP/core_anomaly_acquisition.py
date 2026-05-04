"""
Helpers for anomaly-aware GP acquisition maps on known static maps.
"""

from __future__ import annotations

import math

import numpy as np

try:
    from .core_map import FREE, OCCUPIED
except ImportError:
    from core_map import FREE, OCCUPIED


SUPPORTED_CLUE_ACQUISITION_MODES = (
    "ucb",
    "anomaly_upper_tail",
    "ucb_anomaly_conditional",
)


DEFAULT_ANOMALY_CONDITIONAL_DIAGNOSTICS = {
    "anomaly_conditional_alpha": 0.0,
    "anomaly_conditional_triggered": False,
    "anomaly_gate_reason": "mode_not_conditional",
    "anomaly_top_mass_ratio": 0.0,
    "anomaly_entropy_norm": 0.0,
    "anomaly_hotspot_stability": 1.0,
    "anomaly_pre_first_alpha_capped": False,
}


def _normal_survival_function(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    return 0.5 * np.vectorize(math.erfc)(z / math.sqrt(2.0))


def _normalize01_free(score_map: np.ndarray, free_mask: np.ndarray) -> np.ndarray:
    raw_map = np.asarray(score_map, dtype=float)
    mask = np.asarray(free_mask, dtype=bool)
    normalized = np.zeros_like(raw_map, dtype=float)
    if raw_map.shape != mask.shape or not np.any(mask):
        return normalized

    finite_mask = mask & np.isfinite(raw_map)
    values = raw_map[finite_mask]
    if values.size == 0:
        return normalized
    lower = float(np.min(values))
    upper = float(np.max(values))
    if not np.isfinite(lower) or not np.isfinite(upper) or upper <= lower + 1e-12:
        return normalized

    normalized[finite_mask] = (raw_map[finite_mask] - lower) / (upper - lower)
    normalized[~mask] = 0.0
    normalized[~np.isfinite(normalized)] = 0.0
    return normalized


def _jaccard_stability(
    prev_top_mask: np.ndarray | None,
    top_mask: np.ndarray,
) -> float:
    if prev_top_mask is None:
        return 1.0
    prev = np.asarray(prev_top_mask, dtype=bool)
    curr = np.asarray(top_mask, dtype=bool)
    if prev.shape != curr.shape:
        return 1.0
    union = np.logical_or(prev, curr)
    union_count = int(np.count_nonzero(union))
    if union_count == 0:
        return 1.0
    intersection_count = int(np.count_nonzero(np.logical_and(prev, curr)))
    return float(intersection_count) / float(union_count)


def build_conditional_anomaly_clue_map(
    *,
    gp_acq_map: np.ndarray,
    gp_anomaly_acq_map: np.ndarray,
    free_mask: np.ndarray,
    step: int,
    gp_num_points: int,
    found_count: int,
    prev_anomaly_top_mask: np.ndarray | None = None,
    anomaly_warmup_steps: int = 20,
    anomaly_min_gp_points: int = 64,
    anomaly_top_quantile: float = 0.90,
    anomaly_top_mass_min: float = 0.18,
    anomaly_entropy_max: float = 0.85,
    anomaly_stability_min: float = 0.30,
    anomaly_alpha_max: float = 0.40,
    anomaly_pre_first_alpha_cap: float = 0.15,
) -> tuple[np.ndarray, dict[str, float | bool | str], np.ndarray]:
    """Build a gated UCB/anomaly clue map without changing downstream planner semantics."""
    mask = np.asarray(free_mask, dtype=bool)
    ucb_norm = _normalize01_free(gp_acq_map, mask)
    anomaly_norm = _normalize01_free(gp_anomaly_acq_map, mask)
    top_mask = np.zeros_like(mask, dtype=bool)
    eps = 1e-12

    if np.any(mask):
        free_values = anomaly_norm[mask & np.isfinite(anomaly_norm)]
        if free_values.size > 0:
            resolved_quantile = float(np.clip(anomaly_top_quantile, 0.0, 1.0))
            top_threshold = float(np.quantile(free_values, resolved_quantile))
            top_mask = (anomaly_norm >= top_threshold) & mask
    anomaly_mass = float(np.sum(anomaly_norm[mask]))
    if anomaly_mass <= eps:
        top_mask = np.zeros_like(mask, dtype=bool)
    top_mass_ratio = (
        float(np.sum(anomaly_norm[top_mask])) / (anomaly_mass + eps)
        if anomaly_mass > eps
        else 0.0
    )

    free_count = int(np.count_nonzero(mask))
    if anomaly_mass > eps and free_count > 1:
        p = np.asarray(anomaly_norm[mask], dtype=float)
        p = p / (float(np.sum(p)) + eps)
        entropy_norm = float(-np.sum(p * np.log(p + eps)) / np.log(float(len(p))))
    else:
        entropy_norm = 0.0
    if not np.isfinite(entropy_norm):
        entropy_norm = 0.0

    stability = _jaccard_stability(prev_anomaly_top_mask, top_mask)
    if not np.isfinite(stability):
        stability = 1.0

    triggered = False
    gate_reason = "triggered"
    if int(step) < int(anomaly_warmup_steps):
        gate_reason = "warmup"
    elif int(gp_num_points) < int(anomaly_min_gp_points):
        gate_reason = "insufficient_gp_points"
    elif top_mass_ratio < float(anomaly_top_mass_min):
        gate_reason = "low_top_mass"
    elif entropy_norm > float(anomaly_entropy_max):
        gate_reason = "high_entropy"
    elif stability < float(anomaly_stability_min):
        gate_reason = "low_stability"
    else:
        triggered = True

    alpha = 0.0
    pre_first_capped = False
    if triggered:
        alpha = float(np.clip(anomaly_alpha_max, 0.0, 1.0))
        if int(found_count) == 0:
            capped_alpha = min(alpha, float(np.clip(anomaly_pre_first_alpha_cap, 0.0, 1.0)))
            pre_first_capped = capped_alpha < alpha - 1e-12
            alpha = capped_alpha

    if alpha <= 1e-12:
        planner_map = np.asarray(ucb_norm, dtype=float)
        alpha = 0.0
    else:
        planner_map = _normalize01_free(
            (1.0 - alpha) * ucb_norm + alpha * anomaly_norm,
            mask,
        )
    planner_map[~mask] = 0.0
    planner_map[~np.isfinite(planner_map)] = 0.0

    diagnostics = {
        "anomaly_conditional_alpha": float(alpha),
        "anomaly_conditional_triggered": bool(triggered),
        "anomaly_gate_reason": str(gate_reason),
        "anomaly_top_mass_ratio": float(top_mass_ratio),
        "anomaly_entropy_norm": float(entropy_norm),
        "anomaly_hotspot_stability": float(stability),
        "anomaly_pre_first_alpha_capped": bool(pre_first_capped),
    }
    return planner_map, diagnostics, top_mask


def build_knownmap_anomaly_acquisition_maps(
    *,
    gp_mu_map: np.ndarray,
    gp_var_map: np.ndarray,
    gp_acq_map: np.ndarray,
    nav_map_prior: np.ndarray,
    clue_acquisition_mode: str,
    anomaly_tail_quantile: float,
    anomaly_weight_lambda: float,
    step: int = 0,
    gp_num_points: int = 0,
    found_count: int = 0,
    prev_anomaly_top_mask: np.ndarray | None = None,
    anomaly_warmup_steps: int = 20,
    anomaly_min_gp_points: int = 64,
    anomaly_top_quantile: float = 0.90,
    anomaly_top_mass_min: float = 0.18,
    anomaly_entropy_max: float = 0.85,
    anomaly_stability_min: float = 0.30,
    anomaly_alpha_max: float = 0.40,
    anomaly_pre_first_alpha_cap: float = 0.15,
) -> dict[str, object]:
    if clue_acquisition_mode not in SUPPORTED_CLUE_ACQUISITION_MODES:
        raise ValueError(
            "clue_acquisition_mode must be one of "
            f"{SUPPORTED_CLUE_ACQUISITION_MODES}, got '{clue_acquisition_mode}'"
        )

    mu_map = np.asarray(gp_mu_map, dtype=float)
    var_map = np.asarray(gp_var_map, dtype=float)
    acq_map = np.asarray(gp_acq_map, dtype=float)
    occ_mask = np.asarray(nav_map_prior) == OCCUPIED
    free_mask = np.asarray(nav_map_prior) == FREE

    anomaly_prob_map = np.zeros_like(mu_map, dtype=float)
    anomaly_weight_map = np.ones_like(mu_map, dtype=float)
    anomaly_acq_map = np.asarray(acq_map, dtype=float)
    clue_planner_map = np.asarray(acq_map, dtype=float)
    conditional_top_mask = np.zeros_like(mu_map, dtype=bool)
    conditional_diag = dict(DEFAULT_ANOMALY_CONDITIONAL_DIAGNOSTICS)

    free_mu = mu_map[free_mask & np.isfinite(mu_map)]
    if free_mu.size == 0:
        tail_threshold = 0.0
        anomaly_top_band_threshold = 0.0
    else:
        resolved_quantile = float(np.clip(anomaly_tail_quantile, 0.0, 1.0))
        tail_threshold = float(np.quantile(free_mu, resolved_quantile))
        sigma_map = np.sqrt(np.clip(var_map, 0.0, None))
        tiny_sigma_mask = free_mask & (sigma_map <= 1e-9)
        finite_sigma_mask = free_mask & (sigma_map > 1e-9) & np.isfinite(sigma_map)
        if np.any(finite_sigma_mask):
            z = (float(tail_threshold) - mu_map[finite_sigma_mask]) / sigma_map[finite_sigma_mask]
            anomaly_prob_map[finite_sigma_mask] = _normal_survival_function(z)
        if np.any(tiny_sigma_mask):
            anomaly_prob_map[tiny_sigma_mask] = (
                mu_map[tiny_sigma_mask] > float(tail_threshold)
            ).astype(float)
        anomaly_prob_map[free_mask] = np.clip(anomaly_prob_map[free_mask], 0.0, 1.0)
        anomaly_weight_map[free_mask] = 1.0 + float(max(0.0, anomaly_weight_lambda)) * anomaly_prob_map[free_mask]
        anomaly_acq_map = acq_map * anomaly_weight_map
        anomaly_acq_map[occ_mask] = 0.0
        if clue_acquisition_mode == "anomaly_upper_tail":
            clue_planner_map = np.asarray(anomaly_acq_map, dtype=float)
        elif clue_acquisition_mode == "ucb_anomaly_conditional":
            clue_planner_map, conditional_diag, conditional_top_mask = (
                build_conditional_anomaly_clue_map(
                    gp_acq_map=acq_map,
                    gp_anomaly_acq_map=anomaly_acq_map,
                    free_mask=free_mask,
                    step=step,
                    gp_num_points=gp_num_points,
                    found_count=found_count,
                    prev_anomaly_top_mask=prev_anomaly_top_mask,
                    anomaly_warmup_steps=anomaly_warmup_steps,
                    anomaly_min_gp_points=anomaly_min_gp_points,
                    anomaly_top_quantile=anomaly_top_quantile,
                    anomaly_top_mass_min=anomaly_top_mass_min,
                    anomaly_entropy_max=anomaly_entropy_max,
                    anomaly_stability_min=anomaly_stability_min,
                    anomaly_alpha_max=anomaly_alpha_max,
                    anomaly_pre_first_alpha_cap=anomaly_pre_first_alpha_cap,
                )
            )
        else:
            clue_planner_map = np.asarray(acq_map, dtype=float)
        free_probs = anomaly_prob_map[free_mask & np.isfinite(anomaly_prob_map)]
        anomaly_top_band_threshold = (
            float(np.quantile(free_probs, resolved_quantile))
            if free_probs.size > 0
            else 0.0
        )

    anomaly_prob_map[occ_mask] = 0.0
    anomaly_weight_map[occ_mask] = 0.0
    anomaly_acq_map[occ_mask] = 0.0
    clue_planner_map[occ_mask] = 0.0

    for array in (anomaly_prob_map, anomaly_weight_map, anomaly_acq_map, clue_planner_map):
        array[~np.isfinite(array)] = 0.0

    return {
        "anomaly_tail_threshold": float(tail_threshold),
        "anomaly_top_band_threshold": float(anomaly_top_band_threshold),
        "gp_anomaly_prob_map": anomaly_prob_map,
        "gp_anomaly_weight_map": anomaly_weight_map,
        "gp_anomaly_acq_map": anomaly_acq_map,
        "gp_clue_planner_map": clue_planner_map,
        "anomaly_conditional_top_mask": conditional_top_mask,
        **conditional_diag,
    }
