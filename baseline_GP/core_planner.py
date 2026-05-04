"""
Compatibility wrapper for current-only grid navigation helpers.

The historical belief / unknown-map planner surface has been retired from the
active ``baseline_GP`` root. The known-map mainline only keeps the navigation
utilities needed by ``core_search_policy.py``.
"""

from __future__ import annotations

try:
    from .core_nav import a_star, a_star_nav, heuristic
except ImportError:
    from core_nav import a_star, a_star_nav, heuristic

__all__ = ["heuristic", "a_star", "a_star_nav"]
