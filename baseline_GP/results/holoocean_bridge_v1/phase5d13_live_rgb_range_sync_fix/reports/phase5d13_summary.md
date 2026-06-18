# Phase 5D-13 Live Raw Frame/Baseline Sync Summary

- Mainline Policy: `marine_knownmap_path_v2_infosampled_2usv`
- Production Adapter Module: `baseline_GP.holoocean_bridge.mainline_perception_adapter`
- Live Planner Callback Integrated: `True`
- RGB/RF Sync Fix Enabled: `True`
- RGB/RF Sync Strategy: `short_window_detector_scored_nearest_pair`
- RGB Sync Window Ticks: `8`
- RGB Sync Applied Count: `508`
- Target Accepted Candidate From RGB Sync Count: `3`
- Diagnostic Audit Only: `True`
- Raw Frame Sync Case Count: `11`
- Raw Frame Sync Range-Hit Case Count: `3`
- Source-Zero RGB Recomputed-Positive Count: `0`
- Planned Path Source: `baseline_GP_mainline_planner`
- Preset Trajectory Used: `False`
- Bridge Fan RangeFinder Sensor Count: `61`
- Standoff Viewpoint Hold Enabled: `True`
- Target Accepted Candidate From Standoff Hold: `False`
- Post Arrival Scan Enabled: `True`
- Target Accepted Candidate From Scan: `True`
- Phase Status: `live_planner_callback_standoff_viewpoint_all_found_closed`
- Phase Goal Completed: `True`
- Target Initial Grid Cell: `[18, 13]`
- Target Terminated Reason: `all_found`
- Target All Found Step: `16`
- Target Live Detection Success: `True`
- Mainline Found Mask Updated From Live Adapter: `True`
- Mainline All Found Driven By Live Adapter: `True`
- Teammate False Positive Steps: `[]`
- Update Found Mask Calls: `36`
- Max Observed Detection Distance: `23.052574157714844`

Phase 5D-13 unexpectedly closed the static SphereAgent live search chain. Treat this as requiring a separate full closure audit before claiming migration completion.
