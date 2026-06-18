# Phase 5D-9 RGB Geometry Diagnostic

- Accepted Case Count: `7`
- Accepted Cases: `['origin_5d7_sv0_like', 'origin_5d1a_front_30m', 'planner_translated_5d7_sv0_like', 'planner_front_center_30m', 'planner_front_center_20m', 'planner_front_center_10m', 'map_center_front_30m']`
- Origin 5D-7-like Accepted: `True`
- Planner-translated 5D-7-like Accepted: `True`
- Planner Front Center 30m Accepted: `True`

| case | accepted | range_m | rgb_changed | white_neutral | local_candidates | matched_range | preview |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| origin_5d7_sv0_like | True | 29.614 | 18 | 19 | 1 | 29.37546157836914 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_origin_5d7_sv0_like_target_tick13.png |
| origin_5d1a_front_30m | True | 30.000 | 18 | 19 | 1 | 29.61880111694336 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_origin_5d1a_front_30m_target_tick7.png |
| planner_translated_5d7_sv0_like | True | 29.614 | 25 | 20 | 1 | 29.37909698486328 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_planner_translated_5d7_sv0_like_target_tick13.png |
| planner_front_center_30m | True | 30.000 | 347 | 28 | 1 | 29.617090225219727 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_planner_front_center_30m_target_tick7.png |
| planner_front_center_20m | True | 20.000 | 58 | 52 | 1 | 19.60897445678711 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_planner_front_center_20m_target_tick7.png |
| planner_front_center_10m | True | 10.000 | 338 | 201 | 1 | 9.568195343017578 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_planner_front_center_10m_target_tick13.png |
| map_center_front_30m | True | 30.000 | 46 | 20 | 1 | 29.611974716186523 | baseline_GP\results\holoocean_bridge_v1\phase5d9_live_planner_standoff_capture_search\visuals\phase5d9_rgb_diag_map_center_front_30m_target_tick7.png |

This diagnostic is audit-only. It uses static SphereAgent geometry to identify why live planner capture did or did not produce the existing sphere_blob_local_range_scaled_any_hit evidence.
