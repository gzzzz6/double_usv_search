# Dynamic Target Search Audit Report - Phase 3D-1 (fastsv)
 
## Audit Summary
- **Overall Result**: `PASSED`
- **Failures Count**: `0`
- **Mean Ticks/Step**: `59.9` (Reference: `204.2` ticks)

## Detailed Checks
| Compliance Rule | Status | Note |
| :--- | :---: | :--- |
| Decisions JSON Exists | `PASSED` | |
| Decisions CSV Exists | `PASSED` | |
| Tick Telemetry CSV Exists | `PASSED` | |
| Target Trace JSON Exists | `PASSED` | |
| Target Trace CSV Exists | `PASSED` | |
| Found Events JSON Exists | `PASSED` | |
| Route Map PNG Exists | `PASSED` | |
| Summary MD Exists | `PASSED` | |
| Active Agents OK | `PASSED` | sv and target present |
| Offline Physical Sensors Only | `PASSED` | No camera/sonar |
| Single USV Decision Model | `PASSED` | No 2-USV reservation active |
| Dynamic Target Mode OK | `PASSED` | holoocean_agent_proxy & static policy |
| Run Label OK | `PASSED` | run_label is dynamic_target_search_fastsv |
| World is OpenWater | `PASSED` | World is OpenWater |
| Grid Coordinate Projection OK | `PASSED` | Grid projections aligned |
| Three-fold A* Planning Compliance | `PASSED` | Strict segment validations |
| Telemetry Success Integrity | `PASSED` | 100% arrival rate |
| Suspicion updates monotone curves | `PASSED` | Suspicion feedback |
| Import Hooks / Meta Interceptors absent | `PASSED` | Clear source |
| Core Files Unmodified | `PASSED` | Rigid structural isolation |
| Max Steps Compliant (<= 100) | `PASSED` | Steps within bounds |
| Catchable Schedule Compliance | `PASSED` | Target moves to (25,30) |
| SV Control Scheme is Zero | `PASSED` | control_scheme = 0 |
| Target Control Scheme is One | `PASSED` | control_scheme = 1 |
| Fast Controller Enabled | `PASSED` | sv fast controller active |
| All ticks within limit (<= 400) | `PASSED` | Max ticks per cell limited |
