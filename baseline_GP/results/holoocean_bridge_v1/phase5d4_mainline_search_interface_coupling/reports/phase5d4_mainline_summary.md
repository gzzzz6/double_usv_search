# Phase 5D-4 Mainline Search Interface Coupling Summary

- Recommended Rule: `sphere_blob_local_range_scaled_any_hit`
- Mainline Runtime: `baseline_GP.marine_knownmap_runtime_2usv`
- Adapter Strategy: `runtime detect_targets replacement plus update_found_mask trace wrapper`
- Target Terminated Reason: `all_found`
- Target Time To All Found: `1`
- Coexist Terminated Reason: `all_found`
- Teammate False Positive Steps: `[]`
- Duplicate Replay Detected Steps: `[3]`
- Duplicate Observation Fused: `True`
- Truth Used For Detection: `False`

Phase 5D-4 runs the original two-USV mainline search loop while a lightweight runtime adapter converts Phase 5D-3 HoloOcean sensor-event candidate fusion rows into the mainline detection mask interface.
