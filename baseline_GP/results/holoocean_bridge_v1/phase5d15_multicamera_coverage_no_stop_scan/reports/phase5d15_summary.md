# Phase 5D-15 Continuous Rolling RGB/RF Sync Summary

- Mainline Policy: `marine_knownmap_path_v2_infosampled_2usv`
- Production Adapter Module: `baseline_GP.holoocean_bridge.mainline_perception_adapter`
- Live Planner Callback Integrated: `True`
- RGB/RF Sync Fix Enabled: `True`
- RGB/RF Sync Strategy: `multicamera_continuous_rolling_detector_scored_nearest_pair`
- RGB Sync Window Ticks: `8`
- RGB Sync Applied Count: `490`
- Target Accepted Candidate From RGB Sync Count: `56`
- Diagnostic Audit Only: `True`
- Raw Frame Sync Case Count: `12`
- Raw Frame Sync Range-Hit Case Count: `12`
- Source-Zero RGB Recomputed-Positive Count: `0`
- Planned Path Source: `baseline_GP_mainline_planner`
- Preset Trajectory Used: `False`
- Bridge Fan RangeFinder Sensor Count: `244`
- Standoff Viewpoint Hold Enabled: `False`
- Target Accepted Candidate From Standoff Hold: `False`
- Post Arrival Scan Enabled: `False`
- Target Accepted Candidate From Scan: `False`
- Phase Status: `live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed`
- Phase Goal Completed: `True`
- Target Initial Grid Cell: `[18, 13]`
- Target Terminated Reason: `all_found`
- Target All Found Step: `20`
- Target Live Detection Success: `True`
- Mainline Found Mask Updated From Live Adapter: `True`
- Mainline All Found Driven By Live Adapter: `True`
- Teammate False Positive Steps: `[]`
- Update Found Mask Calls: `40`
- Max Observed Detection Distance: `17.656496047973633`

Phase 5D-15 closed the static SphereAgent live search chain without post-arrival stop-scan; rely on the separate audit before treating this as final evidence.
