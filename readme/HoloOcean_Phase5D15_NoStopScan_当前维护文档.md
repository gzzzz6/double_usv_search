# HoloOcean Phase 5D-15 No-Stop-Scan 当前维护文档

维护日期：2026-06-18

本文档是当前任务状态的短交接版。旧长文档仍保留历史细节；后续接手优先读本文档。

## 当前结论

当前最新可运行闭环为：

```text
Phase 5D-15：multicamera RGB/RF coverage no-stop-scan
```

5D-15 已完成真实 HoloOcean live run 和正式 audit：

```text
audit.all_passed = true
phase_completed = true
phase_goal_completed = true
phase_status = live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed
target_all_found_step = 20
teammate_false_positive_steps = []
no_stop_scan_tick_audit_passed = true
```

这表示在当前限定范围内，USV 可以连续运动完成搜索，不再依赖 5D-13 的停船、standoff hold 或左右摆头 scan。

## 当前限定范围

5D-15 已验证范围：

```text
open_water
双 SurfaceVessel 观察者：sv0 / sv1
单静态 SphereAgent 目标
SurfaceVessel 队友 negative
baseline_GP 原始 planner callback
HoloOcean live movement / live capture
production adapter：baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter
原始 update_found_mask / found_mask / all_found 链
detection rule：sphere_blob_local_range_scaled_any_hit
truth_used_for_detection = false
```

5D-15 不代表以下内容已经完成：

```text
障碍物 / 2D occupancy grid 几何对齐
多目标 N=3
动态目标
非 sphere-like 目标类别
通用视觉检测器
sonar / semantic detector 路线
长期 production provider 模块化
```

## 为什么进入 5D-15

用户提出不希望 USV “走一段停一段、左右摆头”。因此先执行 5D-14，目标是只用 continuous rolling RGB/RF sync 取消 stop-scan。

5D-14 目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d14_continuous_rolling_rgb_rf_sync/
```

5D-14 关键结果：

```text
audit.all_passed = false
phase_completed = false
target_success_all_found = false
target_accepted_candidate_from_rgb_sync_count = 0
no_stop_scan_tick_audit_passed = true
scan_tick_count = 0
standoff_viewpoint_hold_tick_count = 0
teammate_false_positive_steps = []
```

5D-14 的关键诊断：

```text
target run:
  events = 3396
  rangefinder hit events = 0
  local RGB candidate events = 97
  accepted candidate events = 0

teammate-only run:
  rangefinder hit events = 224
  raw_found events = 17
  accepted candidate events = 0
```

结论：

```text
rolling RGB/RF sync 可以解决 RGB/RF 不同 tick 的异步问题，但单前向 RGBCamera + 前向 RF fan 在连续 planner 路径下覆盖不足。
target run 没有 RF hit，因此无法触发 accepted candidate。
```

所以继续执行 5D-15。

## 5D-15 方案

5D-15 目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/
```

5D-15 新增脚本：

```text
scripts/multicamera_coverage_no_stop_scan_probe.py
scripts/multicamera_coverage_no_stop_scan_audit.py
```

5D-15 在每艘 USV 上使用 4 个固定方向 camera channel：

```text
front: FrontRGBCamera, yaw = 0 deg
left:  LeftRGBCamera,  yaw = +90 deg
right: RightRGBCamera, yaw = -90 deg
rear:  RearRGBCamera,  yaw = 180 deg
```

每个 camera channel 配一组 61-beam local fan RangeFinder：

```text
local yaw = +30 deg 到 -30 deg，1 deg 间隔
bridge_fan_rangefinder_sensor_count = 244
```

检测原则：

```text
每个 camera channel 独立形成 RGB blob + 同 channel RF hit 证据
RF 不能单独触发 found
truth 不参与 detection
accepted candidate 仍必须经过 candidate fusion
fusion 后进入 production adapter
adapter 输出 detected_mask
原始 update_found_mask 更新 found_mask 并触发 all_found
```

## 5D-15 审计证据

关键产物：

```text
manifests/phase5d15_summary.json
manifests/phase5d15_audit.json
manifests/phase5d15_live_per_agent_detection_events.json
manifests/phase5d15_live_candidate_fusion_trace.json
manifests/phase5d15_adapter_observe_trace.json
manifests/phase5d15_mainline_update_found_trace.json
reports/phase5d15_summary.md
reports/phase5d15_audit_summary.md
```

5D-15 关键结果：

```text
audit.all_passed = true
target_success_all_found = true
target_all_found_step = 20
target_first_shared_found_step = 20
target_accepted_candidate_from_rgb_sync_count = 32
target_accepted_candidate_from_rgb_sync_steps = [20]
target_accepted_candidate_from_transit = true
mainline_found_mask_updated_from_live_adapter = true
mainline_all_found_driven_by_live_adapter = true
teammate_false_positive_steps = []
teammate_events_accepted_count = 0
truth_flags_false = true
```

No-stop-scan 审计字段：

```text
post_arrival_stabilization_tick_count = 0
standoff_viewpoint_hold_tick_count = 0
scan_tick_count = 0
post_scan_recenter_tick_count = 0
target_accepted_candidate_from_scan = false
target_accepted_candidate_from_standoff_viewpoint_hold = false
no_stop_scan_tick_audit_passed = true
```

5D-15 闭环发生在：

```text
policy_step = 20
target_all_found_step = 20
accepted_candidate_count = 32
duplicate_observation_fused = true
found_mask_after = [true]
all_found_after_update = true
```

## 运行命令

重新运行 5D-15 live probe：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/scripts/multicamera_coverage_no_stop_scan_probe.py --mode live --no-save-visuals
```

重新运行 5D-15 audit：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/scripts/multicamera_coverage_no_stop_scan_audit.py
```

如需实时窗口：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/scripts/multicamera_coverage_no_stop_scan_probe.py --mode live --display-live
```

实时窗口按键：

```text
Q / q：立即退出 HoloOcean 仿真并结束 Python 进程
```

注意：5D-15 使用 4 个 camera channel 和 244 个 RangeFinder sensor，运行比 5D-13/5D-14 更重。

## 当前代码边界

本次新增阶段产物：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d14_continuous_rolling_rgb_rf_sync/
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/
```

已更新旧长文档末尾：

```text
readme/HoloOcean_Phase5C_静态目标感知链维护文档.md
```

核心 runtime/planner 文件未修改：

```text
baseline_GP/core_search_policy.py
baseline_GP/core_execution.py
baseline_GP/core_targets.py
baseline_GP/core_intensity.py
baseline_GP/core_safe_nav.py
baseline_GP/marine_knownmap_runtime.py
baseline_GP/marine_knownmap_runtime_2usv.py
```

## 下一步建议

如果目标是继续“能稳定运行当前 open_water 单静态 SphereAgent 搜索”，下一步应做：

```text
Phase 5E-1：把 5D-15 的 multicamera no-stop-scan provider 从阶段脚本整理为正式 bridge/provider module，并补最小 replay/unit audit。
```

如果目标是扩展能力，建议顺序仍为：

```text
1. 障碍物场景 + 2D occupancy grid 几何对齐
2. 多目标 N=3 静态 SphereAgent
3. 动态目标
4. 非 sphere-like / 通用目标类别
```

不要直接把 5D-15 结论推广到障碍物、多目标、动态目标或通用视觉识别。

## 2026-06-18 新增：target-only demo 模式

已在 5D-15 probe 中增加显式参数：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/scripts/multicamera_coverage_no_stop_scan_probe.py --mode live --target-only-demo --display-live
```

该模式只运行：

```text
calibration/reference
target
```

并跳过：

```text
teammate_only
```

用途：只观察当前搜索任务是否能正常进行，减少一次 HoloOcean 启动。注意 calibration 仍然需要保留，因为当前 RGB blob 检测依赖 target 图像与 calibration 背景参考之间的差分。

target-only demo 不会覆盖正式 audit 产物，输出写入独立文件：

```text
manifests/phase5d15_target_only_demo_summary.json
reports/phase5d15_target_only_demo_summary.md
```

本次实跑验证结果：

```text
target_only_demo_goal_completed = true
phase_status = target_only_demo_all_found_no_stop_scan_closed
target_all_found_step = 20
audit_not_full = true
formal_audit_evidence = false
run_cases = [calibration, target]
skipped_run_cases = [teammate_only]
```

因此该模式适合演示和观察实时搜索；若要作为正式证据，仍需运行默认三段 full run 和 `phase5d15_audit.py`。
