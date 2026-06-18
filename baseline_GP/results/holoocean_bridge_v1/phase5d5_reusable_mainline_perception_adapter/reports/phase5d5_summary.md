# Phase 5D-5 Reusable Mainline Perception Adapter Summary

- Adapter Class: `ReusableMainlinePerceptionAdapter`
- API Methods: `['reset_episode', 'observe_step', 'build_detected_mask', 'fusion_trace']`
- Offline Target All Found Step: `1`
- Mainline Target Time To All Found: `1`
- Mainline Coexist Time To All Found: `1`
- Mainline Teammate False Positive Steps: `[]`
- Mainline Duplicate Detected Steps: `[3]`
- Duplicate Observation Fused: `True`
- Truth Used For Detection: `False`

Phase 5D-5 defines an explicit phase-local adapter API and verifies that it reproduces the Phase 5D-4 mainline found/all_found behavior through both offline replay and runtime mainline wrapping.
