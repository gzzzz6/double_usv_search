"""
Compatibility wrapper for the 2-USV known-map suspicious search runtime.
"""

from __future__ import annotations

try:
    from .phase7_anomaly_benchmark import run_phase7_anomaly_acquisition_benchmark
    from .marine_knownmap_runtime_2usv import (
        SUPPORTED_TWO_USV_KNOWNMAP_POLICIES,
        run_episode_two_usv_search_knownmap,
        run_evaluation_two_usv_search_knownmap,
        run_phase7_knownmap_comparison,
        run_visual_two_usv_search_knownmap,
    )
    from .two_usv_safe_nav_v1_smoke import run_two_usv_safe_nav_v1_smoke_benchmark
except ImportError:
    from phase7_anomaly_benchmark import run_phase7_anomaly_acquisition_benchmark
    from marine_knownmap_runtime_2usv import (
        SUPPORTED_TWO_USV_KNOWNMAP_POLICIES,
        run_episode_two_usv_search_knownmap,
        run_evaluation_two_usv_search_knownmap,
        run_phase7_knownmap_comparison,
        run_visual_two_usv_search_knownmap,
    )
    from two_usv_safe_nav_v1_smoke import run_two_usv_safe_nav_v1_smoke_benchmark

__all__ = [
    "SUPPORTED_TWO_USV_KNOWNMAP_POLICIES",
    "run_episode_two_usv_search_knownmap",
    "run_evaluation_two_usv_search_knownmap",
    "run_phase7_knownmap_comparison",
    "run_phase7_anomaly_acquisition_benchmark",
    "run_two_usv_safe_nav_v1_smoke_benchmark",
    "run_visual_two_usv_search_knownmap",
]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "eval_knownmap_2usv":
        run_evaluation_two_usv_search_knownmap()
    elif len(sys.argv) > 1 and sys.argv[1] == "eval_knownmap_2usv_phase7":
        run_phase7_knownmap_comparison()
    elif len(sys.argv) > 1 and sys.argv[1] == "eval_knownmap_2usv_phase7_anomaly_benchmark":
        run_phase7_anomaly_acquisition_benchmark()
    elif len(sys.argv) > 1 and sys.argv[1] == "eval_knownmap_2usv_safe_nav_v1_smoke":
        run_two_usv_safe_nav_v1_smoke_benchmark()
    else:
        policy_name = (
            sys.argv[1]
            if len(sys.argv) > 1
            else "marine_knownmap_path_v2_infosampled_2usv"
        )
        if policy_name not in SUPPORTED_TWO_USV_KNOWNMAP_POLICIES:
            raise ValueError(
                f"Unsupported 2-USV known-map policy_name='{policy_name}'. "
                f"Supported: {SUPPORTED_TWO_USV_KNOWNMAP_POLICIES}"
            )
        run_visual_two_usv_search_knownmap(policy_name=policy_name)
