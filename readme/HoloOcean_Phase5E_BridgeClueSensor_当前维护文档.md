# HoloOcean Phase 5E Bridge Clue Sensor 当前维护文档

维护日期：2026-06-20

本文档记录 Phase 5E 的当前目标、阶段性执行情况、正式审计结果和后续限制。5E 独立于 5D-15，不再继续加长 5D-15 维护文档。

## Goal 模式建议目标

如果将 Phase 5E 设置为 goal 模式运行，建议 goal 写为：

```text
Phase 5E：不改 baseline 核心算法，分阶段实现 HoloOcean bridge 局部 clue sensor，使 GP clue 来自 HoloOcean 位姿驱动的局部观测而非 baseline 目标真值场；保持 RGB/RF 为唯一 found_mask 触发源，并在最终报告中逐阶段汇报 5E-0 至 5E-4 的完成情况、证据和剩余限制。
```

这个 goal 的核心含义是：

- 不改 baseline 的搜索决策核心，只在 HoloOcean bridge 层补一个局部 clue 观测接口。
- baseline GP 仍然接收 clue，但 clue 不再来自 baseline 的目标真值场直接采样。
- clue 只影响 GP 信息场和后续规划倾向，不能直接把目标标记为 found。
- found_mask 仍然只能由 HoloOcean RGB/RF 感知链触发。
- 每个阶段必须有可审计产物，而不是只看窗口里是否找到了目标。

## 当前目录

Phase 5E 独立目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/
```

主要脚本：

```text
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_probe.py
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_audit.py
```

正式输出：

```text
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/manifests/phase5e_summary.json
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/manifests/phase5e_audit.json
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/manifests/phase5e_bridge_clue_observation_trace.json
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/reports/phase5e_summary.md
baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/reports/phase5e_audit_summary.md
```

## 当前结论

Phase 5E 已完成正式 live run 和 audit。

关键结论：

```text
phase_completed = true
phase_goal_completed = true
audit.all_passed = true
target_all_found_step = 20
target_live_detection_success = true
teammate_only_no_false_positive = true
bridge_clue_observation_count = 756
bridge_clue_rows_used_for_gp_count = 756
bridge_clue_rows_used_for_detection_count = 0
baseline_target_induced_clue_used_for_gp = false
clue_directly_updates_found_mask = false
rgb_rf_detection_updates_found_mask = true
truth_flags_false = true
```

这说明当前 5E 已做到：

- GP clue 由 HoloOcean bridge 局部观测链输入。
- baseline 目标真值诱导 clue 在 5E 中禁用。
- clue 没有直接触发 found_mask。
- 目标发现仍由 RGB/RF 检测链完成。
- 队友负例没有误报。
- baseline 核心运行逻辑和搜索决策算法没有被修改。

## Clue Sensor 定义

Phase 5E 中的 clue sensor 不是 HoloOcean 原生传感器，而是 HoloOcean bridge 层定义的“局部被动异常 clue 观测器”。

配置含义：

```text
sensor_id = phase5e_passive_anomaly_clue_sensor
sensor_role = local_passive_anomaly_observation_for_gp_only
footprint = local_grid_disk_from_holoocean_location_sensor_pose
source_model = scene_registered_static_passive_anomaly_source_not_detection_truth
```

它的工作方式：

1. 使用 HoloOcean 中 USV 的 LocationSensor / GPSSensor 位姿，得到当前世界坐标。
2. 将 USV 世界坐标映射到 baseline 的二维栅格。
3. 在 USV 周围局部圆盘栅格内采样少量候选格子。
4. 根据场景中注册的静态异常源生成 clue 数值，并加入噪声。
5. 将这些局部 clue 观测写入 GP field。
6. 刷新 baseline 的 team GP state 和 search_info。

注意：这里的 clue 不是 detection。它只是“这个局部区域更可疑”的连续观测值，不等于“发现目标”。

## 与 found_mask 的关系

5E 明确切断 clue 到 found_mask 的直接路径：

```text
used_for_gp_observation = true
used_for_detection = false
directly_updates_found_mask = false
found_mask_from_clue = false
```

found_mask 的唯一触发源仍然是 HoloOcean RGB/RF 感知链：

```text
rgb_rf_detection_updates_found_mask = true
```

这点很重要，因为它保证 5E 不是用 clue 作弊发现目标，而是让 clue 只影响搜索规划倾向。

## 阶段性执行结果

| 阶段 | 目标 | 当前结果 | 证据 |
|---|---|---|---|
| 5E-0 | 建立独立阶段目录，保护 baseline 核心文件 | 完成 | `outputs_in_independent_phase_dir=true`，`core_runtime_and_search_algorithm_not_modified=true` |
| 5E-1 | 定义 bridge clue sensor 和输出 trace | 完成 | `bridge_clue_sensor_enabled_and_traced=true` |
| 5E-2 | 禁用 baseline 目标真值诱导 clue，让 GP 使用 bridge clue | 完成 | `baseline_target_induced_clue_used_for_gp=false`，`bridge_clue_rows_used_for_gp_count=756` |
| 5E-3 | 保持 RGB/RF 为唯一 found_mask 触发源 | 完成 | `bridge_clue_rows_used_for_detection_count=0`，`clue_directly_updates_found_mask=false`，`rgb_rf_detection_updates_found_mask=true` |
| 5E-4 | 运行正式 live/audit 并生成阶段报告 | 完成 | `audit.all_passed=true`，`stage_report` 中 5E-0 至 5E-4 全为 `true` |

正式 audit 的 stage report：

```text
5E-0 = true
5E-1 = true
5E-2 = true
5E-3 = true
5E-4 = true
```

## 已执行命令

语法验证：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe -m py_compile baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_probe.py baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_audit.py
```

target-only 快速演示：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_probe.py --mode live --target-only-demo --no-save-visuals
```

正式完整运行：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_probe.py --mode live --no-save-visuals
```

正式审计：

```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5e_bridge_clue_sensor_realized_search/scripts/bridge_clue_sensor_search_audit.py
```

## 运行表现

target-only demo：

```text
target_completed_steps = 20
target_all_found_step = 20
target_only_demo_goal_completed = true
bridge_clue_observation_count = 504
bridge_clue_rows_used_for_gp_count = 504
```

正式完整运行：

```text
target_completed_steps = 20
target_all_found_step = 20
teammate_only_completed_steps = 20
teammate_only_no_false_positive = true
bridge_clue_observation_count = 756
bridge_clue_rows_used_for_gp_count = 756
```

5E 仍然继承 5D-15 的 no-stop-scan 行为：

```text
post_arrival_scan_enabled = false
no_stop_scan_enabled = true
standoff_viewpoint_hold_enabled = false
target_accepted_candidate_from_transit = true
```

## 本次修复记录

初次运行 target-only demo 时，5E 在第一次 HoloOcean tick 后出现：

```text
KeyError: 'location'
```

原因是 `_select_sensor()` 返回字段为 `curr_pos`，不是 `location`。

已在 5E 独立脚本中修复：

```text
selected_initial["location"] -> selected_initial["curr_pos"]
```

修复范围只限 5E probe 脚本，没有修改 baseline 核心文件。

## 仍然需要注意的限制

5E 解决的是“baseline GP clue 不再直接采样 baseline 目标真值场”的问题，但它还不是 HoloOcean 原生物理 clue 场。

原因是当前可疑目标只是一个静态 SphereAgent。它自身没有运动、辐射、声学、热源或电磁源，因此严格依靠 HoloOcean 原生场景不会自动产生 clue。5E 的做法是在 bridge 层注册一个静态被动异常源，用 HoloOcean 位姿驱动局部观测，再将观测输入 baseline GP。

因此 5E 的严谨表述应为：

```text
HoloOcean bridge-local clue observation realized search
```

而不是：

```text
HoloOcean native physical clue field search
```

如果后续论文或实验要求更强物理真实性，下一阶段应考虑：

- 在仿真平台或 HoloOcean 场景中加入真正可观测的异常场。
- 将 clue sensor 实现为对异常场的局部测量，而不是 bridge 层注册源。
- 保持 baseline 核心算法不变，只替换观测提供层。

## 当前建议

如果当前目标是“用 HoloOcean 仿真验证 baseline 多 USV 搜索决策链，并避免直接使用 baseline 目标真值 clue”，Phase 5E 已经可以作为当前闭环版本。

如果下一步目标是“论文级真实物理 clue 建模”，Phase 5E 应作为过渡版本，后续进入 Phase 5F：真实异常场 / 外部仿真平台 / 可观测 clue 物理源评估。
