# SurfaceVessel PD Waypoint Smoke Summary

**Run time:** 2026-05-10T01:04:05.196371
**Elapsed:** 187.2s

## Environment

| Item | Value |
|------|-------|
| Conda Python | `C:\Users\32022\.conda\envs\holo\python.exe` |
| HoloOcean version | `2.2.2` |
| World | `SimpleUnderwater` |
| Package | `Ocean` |
| Agent | `SurfaceVessel` (`sv`) |
| Sensor | `GPSSensor` |
| Control scheme | `1` (PD) |
| Start location | `[0, 0, 2]` |
| Arrival radius | 1.0m |
| Max ticks/waypoint | 2000 |
| Sonar used | **No** |

## Waypoint Results

| WP | Target | Arrived | Timeout | Ticks | Final Dist (m) |
|----|--------|---------|---------|-------|----------------|
| 0 | [25.0, 25.0] | True | False | 999 | 0.9978 |
| 1 | [-25.0, 25.0] | True | False | 1356 | 0.9962 |
| 2 | [-25.0, -25.0] | True | False | 1310 | 0.9965 |
| 3 | [25.0, -25.0] | True | False | 1311 | 0.9966 |

**Arrived: 4/4**

## Performance

- Total ticks: 4976
- Elapsed: 187.2s
- Ticks/sec: 26.6
- Mean tick interval: 35.6ms
- Max tick interval: 85.4ms
- Obvious stutter: **No**

## Conclusions

- `control_scheme=1` (PD) is usable for SurfaceVessel waypoint navigation.
- 4/4 waypoints arrived within 1.0m radius.
- No sonar used.
- No baseline_GP algorithm files modified.