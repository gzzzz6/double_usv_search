# Phase 5D-14 Continuous Rolling RGB/RF Sync Summary

- Mainline Policy: `marine_knownmap_path_v2_infosampled_2usv`
- Production Adapter Module: `baseline_GP.holoocean_bridge.mainline_perception_adapter`
- Live Planner Callback Integrated: `True`
- RGB/RF Sync Fix Enabled: `True`
- RGB/RF Sync Strategy: `continuous_rolling_detector_scored_nearest_pair`
- RGB Sync Window Ticks: `8`
- RGB Sync Applied Count: `224`
- Target Accepted Candidate From RGB Sync Count: `0`
- Diagnostic Audit Only: `True`
- Raw Frame Sync Case Count: `4`
- Raw Frame Sync Range-Hit Case Count: `0`
- Source-Zero RGB Recomputed-Positive Count: `0`
- Planned Path Source: `baseline_GP_mainline_planner`
- Preset Trajectory Used: `False`
- Bridge Fan RangeFinder Sensor Count: `61`
- Standoff Viewpoint Hold Enabled: `False`
- Target Accepted Candidate From Standoff Hold: `False`
- Post Arrival Scan Enabled: `False`
- Target Accepted Candidate From Scan: `False`
- Phase Status: `planner_live_callback_integrated_but_live_detection_all_found_not_closed`
- Phase Goal Completed: `False`
- Target Initial Grid Cell: `[18, 13]`
- Target Terminated Reason: `max_policy_steps`
- Target All Found Step: `None`
- Target Live Detection Success: `False`
- Mainline Found Mask Updated From Live Adapter: `False`
- Mainline All Found Driven By Live Adapter: `False`
- Teammate False Positive Steps: `[]`
- Update Found Mask Calls: `40`
- Max Observed Detection Distance: `None`

Phase 5D-14 exercises the real planner callback and continuous HoloOcean capture path without post-arrival stop-scan. If it does not close all_found, proceed to the 5D-15 sensor coverage fallback.
