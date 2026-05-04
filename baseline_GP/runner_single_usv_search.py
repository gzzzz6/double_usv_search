"""
Known-map-only compatibility wrapper for single-USV search.
"""

from __future__ import annotations

try:
    from .marine_knownmap_runtime import (
        KNOWNMAP_EXPERIMENT_CONTRACT_PATH,
        SUPPORTED_KNOWNMAP_POLICIES,
        load_knownmap_experiment_contract,
        run_episode_single_usv_search_knownmap,
        run_evaluation_single_usv_search_knownmap,
        run_knownmap_tree_budget_oracle_validation,
        summarize_knownmap_policy_comparison,
        summarize_knownmap_policy_comparison_matrix,
        run_visual_single_usv_search_knownmap,
    )
except ImportError:
    from marine_knownmap_runtime import (
        KNOWNMAP_EXPERIMENT_CONTRACT_PATH,
        SUPPORTED_KNOWNMAP_POLICIES,
        load_knownmap_experiment_contract,
        run_episode_single_usv_search_knownmap,
        run_evaluation_single_usv_search_knownmap,
        run_knownmap_tree_budget_oracle_validation,
        summarize_knownmap_policy_comparison,
        summarize_knownmap_policy_comparison_matrix,
        run_visual_single_usv_search_knownmap,
    )


SUPPORTED_POLICIES = SUPPORTED_KNOWNMAP_POLICIES
SUPPORTED_UNKNOWNMAP_POLICIES: tuple[str, ...] = ()
GP_ASSISTED_POLICIES: tuple[str, ...] = ()

# Backward-compatible aliases for callers that still use the generic single-USV
# wrapper names. They now resolve to the known-map V2 mainline only.
run_episode_single_usv_search = run_episode_single_usv_search_knownmap
run_evaluation_single_usv_search = run_evaluation_single_usv_search_knownmap
summarize_marine_policy_comparison = summarize_knownmap_policy_comparison
run_visual_single_usv_search = run_visual_single_usv_search_knownmap

__all__ = [
    "GP_ASSISTED_POLICIES",
    "SUPPORTED_POLICIES",
    "SUPPORTED_UNKNOWNMAP_POLICIES",
    "SUPPORTED_KNOWNMAP_POLICIES",
    "KNOWNMAP_EXPERIMENT_CONTRACT_PATH",
    "load_knownmap_experiment_contract",
    "run_episode_single_usv_search",
    "run_episode_single_usv_search_knownmap",
    "run_evaluation_single_usv_search",
    "run_evaluation_single_usv_search_knownmap",
    "run_knownmap_tree_budget_oracle_validation",
    "summarize_marine_policy_comparison",
    "summarize_knownmap_policy_comparison",
    "summarize_knownmap_policy_comparison_matrix",
    "run_visual_single_usv_search",
    "run_visual_single_usv_search_knownmap",
]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in {"eval", "eval_knownmap"}:
        run_evaluation_single_usv_search_knownmap()
    else:
        policy_name = (
            sys.argv[1]
            if len(sys.argv) > 1
            else "marine_knownmap_path_v2_infosampled"
        )
        if policy_name not in SUPPORTED_KNOWNMAP_POLICIES:
            raise ValueError(
                f"Unsupported known-map policy_name='{policy_name}'. "
                f"Supported: {SUPPORTED_KNOWNMAP_POLICIES}"
            )
        run_visual_single_usv_search_knownmap(policy_name=policy_name)
