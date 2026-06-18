# HoloOcean Phase 5C 静态目标感知链维护文档

本文档用于交接当前窗口中 HoloOcean 静态目标迁移工作的阶段状态。它只记录已经完成和已经确认的事实，不替代后续 Phase spec。

维护日期：2026-06-17

**当前阶段**
当前迁移工作已经执行到 `Phase 5D-12`，但 5D-12 仍是 diagnostic-only，真实搜索闭环仍未闭合。5D-3 已在预设连续轨迹下验证 `found_mask / all_found` 更新链；5D-6 已把 adapter 固化为 production module；5D-7 已接通 live capture provider；5D-8 到 5D-10 已接通真实 baseline_GP planner callback / HoloOcean live movement / live capture / production adapter / original update_found_mask 调用链，但真实 planner 运动下仍未产生 target accepted candidate。5D-11 证明 5D-10 的 3 个 range-hit 失败 pose 在静态重放中可被现有规则识别。5D-12 已保存真实 live planner run 的关键 raw-frame/baseline 诊断数据，进一步发现关键 range-hit tick 上 target/baseline capture 存在且 pose 对齐，但 RGB frame 本身缺失，因此问题收窄到 live capture provider 的 FrontRGBCamera 帧输出/同步，而不是 found_mask、adapter 或几何规则。当前目标仍限定为静态 `SphereAgent`，队友为 `SurfaceVessel`，最大可靠识别距离边界仍按 `35 m`。

主线状态可以概括为：

```text
5C-1：双艇静态目标 runtime-only 多步闭环通过
5C-2：双艇静态目标 HoloOcean 4-step 短程物理闭环通过
5C-3：双艇静态目标 HoloOcean all_found 多步闭环通过
5C-4A-0：SemanticSegmentationCamera 本地可输出探针通过
5C-4A-1：Semantic/RGB/RangeFinder target-distractor 感知探针通过
5C-4B 至 5C-4H：SurfaceVessel-like 静态目标 fan area / distance boundary 审计完成
5C-4I：stronger RGB overlap + 多射线 RangeFinder 阈值校准完成，审计通过
5D-0：单艇静态 SphereAgent 感知校准完成，审计通过
5D-1：SurfaceVessel 队友排除验证已执行；teammate-only 0 误报，但 coexist 正例出现 2 个漏检，完整审计未通过
5D-1A：局部 range-scaled sphere blob 规则修正完成；target-only / target-with-teammate 全部识别，teammate-only 0 误报，审计通过
5D-2：双 SurfaceVessel 固定搜索位姿下的候选共享、队友排除和融合验证完成，审计通过
5D-3：连续多步 HoloOcean 搜索闭环完成；per-agent event / candidate fusion / found_mask / all_found 通过审计
5D-4：5D-3 event/fusion 接入 baseline_GP 原始 mainline found_mask/all_found 接口，审计通过
5D-5：phase-local 可复用 mainline perception adapter API 完成，审计通过
5D-6：production adapter 模块化完成，审计通过
5D-7：live capture provider 接入完成，审计通过
5D-8：真实 planner callback 连续搜索已接通，但 live detection/all_found 未闭合，审计未通过
5D-8b：post-arrival scan + 61-beam fan RangeFinder 尝试后仍未闭合，审计未通过
5D-9：standoff capture + RGB 几何诊断完成；固定几何可识别，真实 planner 运动仍未闭合，审计未通过
5D-10：planner-segment lookahead standoff viewpoint hold 尝试后仍未产生 target accepted candidate，审计未通过
5D-11：live target RGB/RangeFinder 同步 visual diagnostic 完成；诊断审计通过，但不代表 all_found 闭环
5D-12：live raw-frame/baseline 同步诊断已执行；发现关键 range-hit tick 的 RGB frame 缺失，阶段暂停待补 audit/下一步
```

目前仍不进入动态目标阶段。`Phase 5D` 的当前含义已经调整为“多艘 `SurfaceVessel` 协同搜索异类静态目标”，不是旧的动态目标路线。当前未闭合点不是 baseline_GP mainline 接口，而是真实 planner run 的 live FrontRGBCamera frame 在关键 RangeFinder hit tick 上没有稳定输出，导致无法形成可接受的 SphereAgent RGB blob evidence。下一步应继续在 HoloOcean bridge wrapper / capture provider 层定位并修复 target live detection 稳定性，而不是扩大目标类别、进入动态目标跟踪或重写 core planner/runtime。

**总体原则**
保留 `baseline_GP` 中二维栅格搜索决策主链，不把搜索算法改写成 HoloOcean 原生逻辑。

当前冻结边界：

- 不修改 `core_search_policy.py`。
- 不修改 `core_execution.py`。
- 不修改 `core_targets.py`。
- 不修改 `core_intensity.py`。
- 不修改 `core_safe_nav.py`。
- 不修改 `marine_knownmap_runtime.py`。
- 不修改 `marine_knownmap_runtime_2usv.py`。
- 不修改既有 `holoocean_bridge/*` 文件。

HoloOcean 在当前路线中的作用是：

```text
连续物理执行 + 世界坐标回投栅格 + 可视化 + 逐步增加传感器真实性
```

它不改变二维栅格地图上的 assignment、viewpoint、safe-nav、intensity、GP、search_info 等搜索决策定义。

**阶段事实**

**Phase 5C-1：Runtime-Only 多步闭环**
目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c1_res10_dual_usv_static_runtime_probe/
```

本阶段不启动 HoloOcean，只在 runtime 层复刻双艇静态目标多步主链。

关键结果：

- `policy_name = marine_knownmap_path_v2_infosampled_2usv`
- `assignment_mode = coordinated`
- `target_motion_mode = static`
- `episode_seed = 0`
- `map = 81x81`
- `resolution_m = 10.0`
- `max_steps = 240`
- `terminated_reason = all_found`
- `completed_steps = 32`
- `final_found_count = 1`
- `hit_branch_covered = True`
- `gp_n_obs: 48 -> 400`
- audit `all_passed = true`

阶段含义：

```text
双艇算法在不接 HoloOcean 的情况下，可以连续完成 assignment、wait/conflict、离散执行、team detection、found_mask、miss/hit intensity、GP、search_info 更新，并在第 32 步 all_found。
```

**Phase 5C-2：HoloOcean 4-step 短程 Smoke**
目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c2_res10_dual_usv_static_holoocean_multistep_smoke/
```

本阶段把 5C-1 的 runtime 多步链路接入 HoloOcean，但只跑 4 个 policy step，不要求命中目标。

关键结果：

- `max_policy_steps = 4`
- `terminated_reason = max_policy_steps`
- `completed_policy_steps = 4`
- `total_physical_ticks = 403`
- `final_found_count = 0`
- `hit_branch_covered = False`
- `gp_n_obs: 48 -> 240`
- `min_inter_vessel_distance_m = 100.00`
- `fallback_count_total = 0`
- audit `all_passed = true`

阶段含义：

```text
算法规划 -> HoloOcean 双艇物理执行 -> sensor 回读 -> world_to_grid 投影 -> runtime local/team belief update
```

这条短程物理闭环已经跑通。此阶段没有证明目标发现，只证明多步物理桥接和后置更新可以连续执行。

**Phase 5C-3：HoloOcean all_found 多步闭环**
目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c3_res10_dual_usv_static_holoocean_allfound_probe/
```

本阶段把 HoloOcean 静态目标闭环跑到真实 `all_found`，覆盖 hit 分支。

关键结果：

- `max_policy_steps = 40`
- `expected_runtime_all_found_step = 32`
- `terminated_reason = all_found`
- `completed_policy_steps = 32`
- `total_physical_ticks = 2728`
- `initial_target_positions = [[23, 21]]`
- `found_count_final = 1`
- `found_mask_final = [true]`
- `find_times_final = [32]`
- `hit_branch_covered = True`
- `remaining_intensity_mass_final = 0.0`
- `peak_intensity_ratio_final = 0.0`
- `gp_n_obs: 48 -> 400`
- `min_inter_vessel_distance_m = 99.99850441416972`
- `fallback_count_total = 0`
- audit `all_passed = true`

真实 found event：

```text
target_index = 0
found_step = 32
detected_usvs = [0]
target_position = [23, 21]
usv_projected_cells["0"] = [20, 25]
```

阶段含义：

```text
双艇静态目标搜索已经在 HoloOcean 里完成从初始状态到 all_found 的多步闭环验证。
```

但这里的目标 truth 仍来自 runtime `state["target_positions"]`。HoloOcean 负责 USV 物理执行和位置回投，不负责真实传感器目标识别。

本阶段还新增了 visual-only 变体，用于人工查看 HoloOcean 视角和 USV 运动过程。visual-only 变体服务于可视化，不作为替代 audit 的证据。

**Phase 5C-4A-0：SemanticSegmentationCamera 可用性探针**
目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4a0_semantic_camera_availability_probe/
```

本阶段只验证本地 HoloOcean 中 `SemanticSegmentationCamera` 能否启动、输出、保存和被审计。

关键结果：

- `probe_completed = true`
- `availability_conclusion = available`
- `semantic_camera_available = true`
- `semantic_scenario_launch_ok = true`
- `semantic_output_seen = true`
- `rgb_output_seen = true`
- semantic first frame shape: `[240, 320, 4]`
- semantic dtype: `uint8`
- semantic unique count: `2`
- semantic raw、semantic preview、RGB preview 均已保存
- audit `all_passed = true`

阶段含义：

```text
SemanticSegmentationCamera 在本地 HoloOcean 2.2.2 环境中可以返回数组和图像产物。
```

注意：这只证明它能输出，不证明它能区分可疑目标、普通物体或障碍物。

**Phase 5C-4A-1：Semantic/RGB/RangeFinder Target-Distractor 探针**
目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4a1_semantic_rgb_rangefinder_target_distractor_probe/
```

本阶段独立测试三个 perception sensors：

- `SemanticSegmentationCamera`
- `RGBCamera`
- `RangeFinderSensor`

场景包含四类：

- `baseline`
- `target_only`
- `distractor_only`
- `target_and_distractor`

关键结果：

- `probe_completed = true`
- `semantic_can_distinguish_target_from_distractor = false`
- `rgb_can_distinguish_target_from_distractor = true`
- `rangefinder_object_presence_supported = true`
- `composite_sensor_detection_supported = true`
- `rgb_available_as_visual_evidence = true`
- `rangefinder_available_as_range_evidence = true`
- `truth_used_for_detection = false`
- `runtime_imported = false`
- `sonar_used = false`
- audit `all_passed = true`

Semantic 结果：

```text
Semantic Target Signature Colors = []
Semantic Distractor Signature Colors = []
Semantic Target/Distractor Disjoint = False
```

RGB 结果：

```text
RGB Target Signature Colors 非空
RGB Distractor Signature Colors = ["224,192,192,255"]
RGB Target/Distractor Disjoint = True
```

RangeFinder 结果：

```text
baseline: no hit
target_only: hit, min_positive_range_m = 9.808594703674316
distractor_only: hit, min_positive_range_m = 11.555341720581055
target_and_distractor: hit, min_positive_range_m = 9.831196784973145
```

阶段含义：

```text
当前本地 HoloOcean 场景中，SemanticSegmentationCamera 能输出，但不能作为目标身份识别依据。
RGBCamera 可以在简化场景里提供目标身份差异证据。
RangeFinderSensor 可以提供物体存在/距离证据，但不能判断物体身份。
```

因此，当前可用的最小感知链是：

```text
RGBCamera 身份证据 + RangeFinderSensor 距离/存在证据
```

SemanticSegmentationCamera 暂时只能作为记录项，不接入 `found_mask`。

**已经完成的工作**
- 建立了双艇静态目标 runtime-only 多步闭环。
- 建立了双艇 HoloOcean 物理多步桥接。
- 验证了 HoloOcean all_found 闭环可以跑到第 32 个 policy step 并发现目标。
- 新增了可视化变体，便于人工观察 USV 运动过程。
- 验证了 `SemanticSegmentationCamera` 本地可输出。
- 验证了 `SemanticSegmentationCamera` 当前不能区分 target/distractor。
- 验证了 `RGBCamera + RangeFinderSensor` 在简化场景中可以形成可审计的 sensor evidence detection event。
- 明确了声呐暂时禁用。

**尚未完成的工作**
- 尚未把 `RGBCamera + RangeFinderSensor` 的 detection event 接入 5C-3 的 `found_mask` 闭环。
- 尚未定义可长期使用的 HoloOcean target visual marker / target actor 规范。
- 尚未定义障碍物场景。
- 尚未把障碍物几何与二维 occupancy grid 对齐。
- 尚未验证遮挡、视角、距离、光照变化下 RGB signature 是否稳定。
- 尚未实现真实图像目标检测模型。
- 尚未引入动态目标。
- 尚未使用声呐。
- 尚未让 HoloOcean 场景几何完全替代 runtime known map。

**注意事项**
1. 不要把 5C-3 说成“已经完成真实传感器搜索”。

   5C-3 证明的是：

   ```text
   HoloOcean 物理执行 + 栅格回投 + runtime detection/found/intensity/GP/search_info 更新可以闭环到 all_found
   ```

   但目标发现仍由 runtime target truth 驱动。

2. 不要把 5C-4A-0 说成“SemanticSegmentationCamera 可用于目标识别”。

   5C-4A-0 只证明 semantic camera 可输出。

3. 不要把 5C-4A-1 说成“真实感知问题已经解决”。

   5C-4A-1 证明的是简化场景中：

   ```text
   RGB 可提供目标身份差异证据
   RangeFinder 可提供物体存在/距离证据
   ```

   它还没有证明复杂场景、遮挡、障碍物、背景变化下的鲁棒性。

4. `RangeFinderSensor` 不能单独触发目标发现。

   它只能说明前方或指定方向存在物体，并给出距离。target、distractor、obstacle 都可能产生 range hit。

5. `RGBCamera` 当前使用的是审计化颜色差异 signature。

   这适合简化场景的最小探针，但还不是通用视觉检测器。

6. `SemanticSegmentationCamera` 暂时不接入 `found_mask`。

   当前本地结果中 target signature 和 distractor signature 都为空，无法作为身份判断来源。

7. 任何 sensor evidence 必须记录来源。

   detection event 中至少应保留：

   ```text
   sensor name
   evidence type
   identity decision source
   range hit / min range
   RGB signature overlap
   whether truth was used for detection
   ```

8. 禁止为了通过审计使用 target truth 直接生成 sensor detection event。

   target truth 可以用于 audit 对照，但不能作为 detection 触发源。

**难以解决的问题**
1. Semantic label 链路不完善。

   本地 HoloOcean 2.2.2 中，`SemanticSegmentationCamera` 可以输出 RGBA 数组，但在 OpenWater/Ocean 简化测试中没有给 target 和 distractor 形成可区分的 semantic signature。此前对官方仓库的只读核对也显示 v2.2.2 的 semantic camera 文档和测试都不充分，后续版本才补充了更多 semantic 相关内容。

2. RGB identity 当前依赖简化外观差异。

   如果目标、障碍物、普通物体在 RGB 图像里颜色或形状接近，当前 signature 方法可能不可靠。

3. RangeFinder 不能区分物体类别。

   加入障碍物后，RangeFinder 的 hit 只能说明“有东西”，不能说明“是目标”。

4. 障碍物会同时影响规划和感知。

   如果只在 HoloOcean 里加障碍物，但二维 occupancy grid 不更新，safe-nav 与物理世界会不一致。

5. 声呐暂时不能作为路线依赖。

   用户设备上使用声呐会出现严重卡顿和内存占用暴涨，因此当前阶段不把 sonar 作为必需能力。

**已定决策**
- 暂时不做动态目标，不进入 Phase 5D。
- 先完善静态目标的 HoloOcean 感知链。
- 声呐继续禁用。
- HoloOcean perception sensors 必须明确指定，不能笼统写“sensor”。
- 当前指定的 perception sensors 为：

```text
SemanticSegmentationCamera
RGBCamera
RangeFinderSensor
```

- navigation / pose sensors 与 perception sensors 分开记录。
- `LocationSensor`、`GPSSensor`、`OrientationSensor` 只服务于位姿、控制和回投，不作为目标身份识别证据。
- `SemanticSegmentationCamera` 暂不作为目标身份识别来源。
- `RGBCamera + RangeFinderSensor` 是当前可继续推进的最小感知链。
- 不修改二维栅格搜索决策算法。
- 新增代码继续放在独立阶段目录中。

**沉淀的方法论**
1. 先 runtime-only，再 HoloOcean。

   先证明算法主链在 runtime 层连续正确，再接入 HoloOcean 物理执行。5C-1 到 5C-3 已按这个顺序执行。

2. 先短程 smoke，再 all_found。

   5C-2 只跑 4 个 policy step，先验证桥接不会崩；5C-3 再跑到第 32 步 all_found。

3. 物理执行结果以 HoloOcean sensor 回读后的投影格为准。

   不用 runtime `execute_next_step(...)` 伪造 HoloOcean 后的位置。

4. 传感器引入必须先做最小探针。

   不能因为某个 sensor 能返回数组，就认为它可用于目标发现。必须单独测试：

   ```text
   能否启动
   能否输出
   输出 shape/dtype 是否稳定
   是否能区分 target/distractor
   是否能形成不依赖 truth 的 detection event
   ```

5. target truth 只用于审计对照。

   detection event 的触发必须来自 sensor evidence，不来自 runtime truth 或 HoloOcean actor 名称。

6. 正例和反例必须同时出现。

   5C-4A-1 使用 baseline、target_only、distractor_only、target_and_distractor 四类场景，是为了同时验证：

   ```text
   没目标时不误报
   有目标时能检测
   只有干扰物时不误报目标
   目标和干扰物同时存在时仍能识别目标
   ```

7. 审计口径要分阶段变化。

   5B-2 禁止后置 belief update，因为当时只做 one-step bridge。

   5C-1 之后必须正向审计：

   ```text
   detect_targets
   update_found_mask
   miss update
   hit_update_intensity
   GP update
   search_info update
   ```

8. 可视化不是审计替代品。

   visual-only 变体用于人工观察和调试，不替代 JSON、trace、audit。

**下一步边界**
如果继续完善静态目标，下一步不应直接做动态目标，也不应直接加复杂障碍物。

更稳的下一步是设计一个新的阶段，将 `RGBCamera + RangeFinderSensor` 形成的 detection event 接到静态目标闭环中，但仍不修改核心算法文件。

这个阶段需要先明确：

- HoloOcean target marker 或 target actor 采用什么资产。
- RGB 身份证据采用固定 signature、模板匹配，还是后续视觉模型。
- RangeFinder 的检测方向、距离阈值和采样频率。
- detection event 如何映射回 runtime 中的 target index。
- sensor detection 与 runtime `detect_targets(...)` 的替代关系。
- audit 如何证明没有使用 truth 直接触发发现。

在这些前提确认前，不建议把 5C-4A-1 的探针逻辑直接接入 `found_mask`。

**建议阶段名**
后续如继续推进，可考虑：

```text
Phase 5C-4B：RGBCamera + RangeFinderSensor 静态目标 detection adapter 最小闭环
```

该阶段的目标应限定为：

```text
在简化静态场景中，用可审计 sensor evidence 触发 found event，并接入 runtime found_mask / hit update / GP / search_info 后置更新。
```

它仍然不应修改 `baseline_GP` 中二维栅格搜索决策算法。

**2026-06-14 补充更新：5C-4B 至 5C-4H 当前进度**

本节是 2026-06-14 对 Phase 5C 静态目标感知链的最新维护记录。上文早期“下一步 5C-4B”的表述已经被后续阶段推进覆盖；后续窗口应以本节为最新状态。

当前仍保持以下边界：

```text
不修改 baseline_GP 核心二维栅格搜索算法
不修改既有 holoocean_bridge/* 文件
不把 HoloOcean actor truth 作为 detection 触发源
truth 只用于 audit 对照
RangeFinder 只提供物体存在/距离证据，不能单独证明物体身份
RGBCamera 当前不是 YOLO，也不是通用图像识别模型，只是 RGB 颜色差分 signature
```

当前最小感知链仍为：

```text
RGBCamera 提供 target-like RGB signature
RangeFinderSensor 提供方向/距离上的物体存在证据
found = rgb_has_target_signature AND rangefinder_hit
```

其中 `rgb_has_target_signature` 来自 RGB 图像与 baseline 图像的差分区域颜色 signature 重叠；它不是深度学习目标识别。

**Phase 5C-4B：RGB + RangeFinder 静态目标最小感知链**

阶段含义：

```text
验证 HoloOcean 内置 RGBCamera 与 RangeFinderSensor 是否可以形成不依赖 truth 的最小 target detection event。
```

关键结论：

- `RGBCamera` 只能返回图像，本身不会自动识别目标。
- 当前 RGB 目标证据来自手写的颜色差分 signature。
- `RangeFinderSensor` 可以证明某方向有物体，但不能判断是 target、distractor 还是 obstacle。
- 因此必须组合使用：

```text
RGB target-like evidence + RangeFinder object/range evidence
```

**Phase 5C-4C：正反例闭环**

阶段含义：

```text
用 target-only / distractor-only / baseline 等简化场景，验证 RGB signature + RangeFinder 是否能区分有目标和无目标。
```

关键结论：

- 简化正前方 target 场景可以触发 detection。
- 当前方法仍是弱 RGB signature，不是可靠视觉分类器。
- 颜色相似、视角变化、遮挡、距离增大时可能失效或误报。

**Phase 5C-4D：鲁棒性边界测试**

阶段含义：

```text
测试左右偏移、FOV 边缘、远距离、朝向变化、干扰物等条件。
```

关键结论：

- 单条或未扩展 RangeFinder 会漏掉左右偏移目标。
- 远距离场景中 RangeFinder 能打到目标，但 RGB signature 可能不命中。
- 因此“RangeFinder 打到”不能等价于“识别出 target”。
- 5C-4D 暴露的核心问题是：

```text
左右偏移漏检
远距离 RGB signature 不稳定
target/distractor 仍可能混淆
```

**Phase 5C-4E：多射线扇形 RangeFinder 验证**

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4e_rgb_multiray_rangefinder_fan_boundary/
```

阶段含义：

```text
验证多条 yaw-rotated 单射线 RangeFinder 是否能把探测范围扩展成水平扇形，从而解决 5C-4D 的左右偏移漏检。
```

关键实现：

```text
FAN_YAW_DEGREES = [30, 22.5, 15, 7.5, 0, -7.5, -15, -22.5, -30]
```

关键结论：

- HoloOcean 原生 `LaserCount=9, LaserAngle=60` 不是水平扇形；`LaserAngle` 在当前文档语义中更接近 elevation。
- 水平扇形通过 9 条 yaw-rotated 单射线 `RangeFinderSensor` 实现。
- 多射线 any-hit 规则可以改善近距离左右偏移漏检。
- 但 direction matching 还没有校准好，不能直接升为最终规则。

**Phase 5C-4F：正前方 10-30 m 距离扫描**

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4f_distance_sweep_rgb_multiray_fan/
```

测试距离：

```text
10 m, 15 m, 20 m, 25 m, 30 m
```

判定规则：

```text
found = rgb_has_target_signature AND any_rangefinder_hit
```

关键结果：

- `10/15/20/25/30 m` 全部识别成功。
- baseline 无目标场景没有误报。
- 结论不是“最大距离是 30 m”，而是：

```text
在正前方、无遮挡、无干扰条件下，当前方法至少到 30 m 可触发 target-like detection。
```

**Phase 5C-4G：正前方 35-50 m 远距离扫描**

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4g_front_far_distance_boundary/
```

测试距离：

```text
35 m, 40 m, 45 m, 50 m
```

关键结果：

- `35/40/45/50 m` 正前方目标全部识别成功。
- 50 m 成功是 RGBCamera 与 RangeFinder 共同作用的结果：

```text
rgb_has_target_signature = true
any_rangefinder_hit = true
found = true
```

- 这不是只靠 RangeFinder。
- 但 45-50 m 时 RGB changed pixels 已经很少，说明远距离 RGB signature 很脆弱。
- 结论必须限定为：

```text
在理想正前方、无遮挡、无干扰条件下，当前弱 RGB signature + 多射线 RangeFinder 可以触发到 50 m。
```

不能推广为：

```text
50 m 内任意方向、任意干扰条件下都能稳定识别 target。
```

**Phase 5C-4H：扇形区域有效距离测试**

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4h_fan_area_distance_boundary/
```

阶段目标：

```text
验证当前 RGB signature + 多射线扇形 RangeFinder 在扇形区域内的有效距离，而不是只测 camera 正前方。
```

测试 target 距离：

```text
20 m, 35 m, 50 m
```

测试角度：

```text
left_outer  = +25 deg
left_inner  = +15 deg
center      = 0 deg
right_inner = -15 deg
right_outer = -25 deg
```

干扰物测试：

```text
distractor-only at 20 m and 50 m across the same 5 angles
```

主判定规则仍为：

```text
found = rgb_has_target_signature AND any_rangefinder_hit
```

方向匹配字段只作为诊断：

```text
matched_rangefinder_beam_hit is diagnostic only
direction_matching_used_for_detection = false
```

关键结果：

```text
audit.all_passed = true
```

target 结果：

```text
20 m: 5/5 angles success
35 m: 5/5 angles success
50 m: center / left_inner / right_inner success
50 m: left_outer / right_outer failed
```

因此：

```text
max_fan_reliable_distance_m = 35.0
```

各方向最大有效距离：

```text
left_outer  = 35 m
left_inner  = 50 m
center      = 50 m
right_inner = 50 m
right_outer = 35 m
```

干扰物误报：

```text
distractor_false_positive_scenes = 6
```

误报场景：

```text
distractor_only_left_inner_20m
distractor_only_center_20m
distractor_only_right_inner_20m
distractor_only_left_inner_50m
distractor_only_center_50m
distractor_only_right_inner_50m
```

方向匹配诊断：

```text
direction_mismatch_count = 10
```

主要集中在：

```text
left_inner
right_inner
```

5C-4H 的直白结论：

```text
多射线扇形 RangeFinder 可以把 target 探测范围扩展到扇形区域。
在当前规则下，20 m 和 35 m 可以认为是扇形全区域有效。
50 m 只能在中心和内侧角度有效，外侧角度失败。
当前规则会把部分 distractor-only 场景误报为 target。
方向匹配还没有校准好，不能直接作为最终 detection rule。
```

**当前问题总结**

当前规则：

```text
found = rgb_has_target_signature AND any_rangefinder_hit
```

优点：

- 简单。
- 能证明 RGBCamera 与 RangeFinder 的最小组合链路可用。
- 能在正前方和部分扇形区域触发 target-like detection。

问题：

- `any_rangefinder_hit` 太宽松，任意 beam 打到物体都可能帮助触发 found。
- `rgb_has_target_signature` 太宽松，目前 `target_overlap_min = 1`，很容易因为少量颜色重叠误判。
- 没有明确排除 distractor。
- RGB 图像区域和 RangeFinder beam 区域还没有完成校准。

因此当前不能说：

```text
已经实现可靠 target recognition
```

只能说：

```text
已经实现可审计的弱 target-like sensor evidence detection，并明确暴露了距离、方向和误报边界。
```

---

**下一步计划：Phase 5C-4I**

建议阶段名：

```text
Phase 5C-4I：Direction-Matched RGB + RangeFinder with Distractor Rejection Calibration
```

建议目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4i_direction_matched_distractor_rejection_calibration/
```

5C-4I 不应推倒重来，而应在现有规则上改进。

从当前规则：

```text
found = rgb_has_target_signature AND any_rangefinder_hit
```

升级为候选规则：

```text
found_candidate =
    stronger_rgb_target_signature
    AND matched_rangefinder_beam_hit
    AND NOT distractor_like
```

---


---

**2026-06-14 补充更新：Phase 5C-4I 已完成**

当前最新阶段已推进到 `Phase 5C-4I`。

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5c4i_direction_matched_distractor_rejection_calibration/
```

5C-4I 已完成离线规则校准、HoloOcean 复跑验证和审计：

```text
audit.all_passed = true
```

关键产物：

```text
manifests/candidate_rule_matrix.json
manifests/candidate_rule_summary.json
manifests/recommended_candidate_rule.json
manifests/old_direction_match_failure_reference.json
manifests/phase5c4i_summary.json
manifests/phase5c4i_audit.json
reports/offline_rule_calibration_summary.md
reports/old_direction_match_failure_reference.md
reports/phase5c4i_validation_summary.md
reports/phase5c4i_audit_summary.md
visuals/*_rgb_raw.npy
visuals/*_rgb.png
```

5C-4I 的输入文件名已按 5C-4H 真实产物对齐：

```text
5C-4H manifests/rgb_multiray_fan_area_distance_boundary_matrix.json
5C-4H manifests/rgb_multiray_fan_area_distance_scene_results.json
5C-4H manifests/rgb_multiray_fan_area_distance_detection_events.json
5C-4H visuals/*_rgb_raw.npy
```

注意：5C-4H 的 `scene_results.json` 中 `first_rgb_raw` 已被 strip，5C-4I-1 重算 RGB signature 时读取的是 `visuals/*_rgb_raw.npy`，不是 `scene_results.json`。

5C-4I-1 离线校准结论：

```text
recommended_rule_id = stronger_rgb_any_hit_overlap7_px0
recommended rule =
    rgb_signature_overlap_count >= 7
    AND rgb_changed_pixels >= 0
    AND any_rangefinder_hit
```

本次推荐规则没有把方向匹配和 distractor rejection 接入最终 detection：

```text
direction_matching_used_for_detection = false
distractor_rejection_enabled = false
old_direction_matching_used_for_detection = false
```

原因是 5C-4H 旧的 `matched_rangefinder_beam_hit` 字段已被确认不能直接作为 detection 条件。旧字段使用 RGB 图像三等分和 RangeFinder beam 索引三等分，二者角度区间不对应。若直接使用，会把 6 个 inner-angle 真目标误判为 false negative：

```text
target_left_inner_20m
target_right_inner_20m
target_left_inner_35m
target_right_inner_35m
target_left_inner_50m
target_right_inner_50m
```

因此旧方向匹配只保留为 failure reference。5C-4I 脚本同时记录了基于 RGB target-overlap 像素方位角和真实 fan yaw 的 recalibrated direction diagnostics，但本阶段推荐规则未启用方向匹配。

5C-4I-2 HoloOcean 复跑验证结果：

```text
target_outcome_counts = {"true_positive": 12, "false_negative": 3}
distractor_outcome_counts = {"true_negative": 10}
distractor_false_positive_scenes = []
fan_reliable_distances_m = [20.0, 35.0]
max_fan_reliable_distance_m = 35.0
old_direction_inner_failure_reference_count = 6
truth_used_for_detection = false
```

相对 5C-4H 的变化：

```text
distractor-only false positives: 6 -> 0
20 m target: 5/5 保持 true positive
35 m target: 5/5 保持 true positive
50 m center: 由 true positive 变为 false negative
50 m left_inner/right_inner: 保持 true positive
50 m left_outer/right_outer: 仍为 false negative，原因是 RangeFinder 未命中
```

5C-4I 的结论应表述为：

```text
在当前 5C-4H 场景矩阵上，提升 RGB overlap 阈值到 7 可以消除 distractor-only false positives，并保持 20 m / 35 m 扇形全区域 true positive。
代价是牺牲 50 m center 远距离目标。
这仍不是通用 target recognition，只是对当前弱 RGB signature + 多射线 RangeFinder 规则的可审计阈值校准。
```

后续阶段建议：

```text
不要直接把 5C-4H 旧 matched_rangefinder_beam_hit 接入 found_mask。
如需使用方向匹配，应基于 RGB 像素方位角与真实 beam yaw 容差重新校准，并在 HoloOcean 中单独验证。
如需进一步恢复 50 m center，需要引入更稳健的 RGB 目标证据，而不是降低 overlap 阈值回到 1。
```

5C-4I 的核心目标：

```text
减少 5C-4H 中 distractor-only 的 false positive
尽量保留 target 场景的 true positive
明确代价：是否牺牲远距离或边缘 target 的识别率
```

5C-4I 必须同时评估三类能力：

1. target true positive 是否保留。

   ```text
   场景里真的有 target，系统也正确 found。
   ```

2. distractor-only false positive 是否降低。

   ```text
   场景里没有 target，只有 distractor，系统不应 found。
   ```

3. 规则变严格后的代价。

   ```text
   误报减少后，是否导致真正 target 漏检增加。
   特别关注 35 m 扇形全区域 target、50 m center/inner target。
   ```

建议 5C-4I 分两步做：

**5C-4I-1：离线规则校准**

输入：

```text
5C-4H boundary_matrix.json
5C-4H scene_results.json
5C-4H RGB raw/preview artifacts
```

候选规则至少包含：

```text
baseline_any_hit:
    rgb_has_target_signature AND any_rangefinder_hit

direction_matched:
    rgb_has_target_signature AND matched_rangefinder_beam_hit

stronger_rgb_any_hit:
    stronger_rgb_target_signature AND any_rangefinder_hit

stronger_rgb_direction_matched:
    stronger_rgb_target_signature AND matched_rangefinder_beam_hit

stronger_rgb_direction_matched_distractor_rejected:
    stronger_rgb_target_signature
    AND matched_rangefinder_beam_hit
    AND NOT distractor_like
```

其中 `stronger_rgb_target_signature` 可以先用参数扫描实现：

```text
target_overlap_min in [1, 2, 3, 4]
rgb_changed_pixels_min in [0, 10, 20, 40, 80]
```

`distractor_like` 可以先用 5C-4H 的 distractor-only RGB signature 建立拒绝条件：

```text
如果 distractor_signature_overlap 过高，则拒绝 target
```

5C-4I-1 输出：

```text
candidate_rule_matrix.json/csv
candidate_rule_summary.json
推荐候选规则
保留/损失的 target true positives
减少的 distractor false positives
新增的 false negatives
```

**5C-4I-2：HoloOcean 复跑验证**

使用 5C-4I-1 推荐的候选规则，在 HoloOcean 中复跑与 5C-4H 相同的场景矩阵：

```text
baseline
calibration_target_front_center_10m
target: 20/35/50 m x 5 angles
distractor-only: 20/50 m x 5 angles
```

审计要求：

```text
truth_used_for_detection = false
direction_matching_used_for_detection = true
distractor_rejection_enabled = true
audit.all_passed = true
```

建议成功标准：

```text
20 m target: 5/5 保持 true positive
35 m target: 尽量保持 5/5 true positive
50 m center/left_inner/right_inner: 尽量保持 true positive
50 m left_outer/right_outer: 不强制成功，因为 5C-4H 已经显示 RangeFinder 未命中
distractor-only false positives: 必须明显少于 5C-4H 的 6 个，目标是 0
```

如果方向匹配导致 35 m target 明显漏检，则说明方向匹配边界仍需校准，不应接入 found_mask。

如果 distractor rejection 降低误报但严重牺牲 target true positive，则需要记录 tradeoff，不应宣称已解决识别问题。

---


**2026-06-15 补充更新：下一阶段大目标调整**

经进一步梳理，后续阶段不再把“同一种 `SurfaceVessel` 模型既作为队友又作为目标”作为主线问题。

后续大目标调整为：

```text
多艘 SurfaceVessel 协同搜索异类静态目标。
队友保持为 SurfaceVessel。
目标改为静态 SphereAgent。
```

这样调整的原因：

```text
1. 当前真正需要先跑通的是多艇协同搜索闭环，而不是同模型视觉身份识别。
2. 如果同一种 SurfaceVessel 既作为队友又作为目标，问题本质会转成身份识别 / 数据关联 / 友方排除，不适合继续仅靠 RGB 阈值推进。
3. 使用静态 SphereAgent 作为目标，可以先把多艇协同、候选共享、目标融合、队友排除的主链跑通。
4. 这样不会推翻 5C-4I 的结论：35 m 仍是当前可审计的可靠距离上限，只是后续目标类别需要重新校准自己的感知边界。
```

新的阶段理解应为：

```text
5C-4I 结束了“SurfaceVessel-like 静态目标”的单艇阈值校准阶段。
后续不继续把同模型 USV 识别当作近期主线。
下一步优先转入多艇协同搜索异类静态目标。
```

新的建议路线：

```text
Phase 5D-0：单艇静态 SphereAgent 感知校准
Phase 5D-1：SurfaceVessel 队友排除验证
Phase 5D-2：多艘 SurfaceVessel 协同搜索静态 SphereAgent
```

各阶段目标说明：

```text
Phase 5D-0：
重新建立 SphereAgent 的 RGB / RangeFinder 感知规则。
不能直接套用 5C-4I 针对 SurfaceVessel-like 目标得到的 overlap 阈值。
应重新校准 20 m / 35 m / 50 m 的识别表现，并重新审计 reliable distance。

Phase 5D-1：
构造 teammate-only 场景，确认 SurfaceVessel 队友不会被 SphereAgent-target 检测规则误判为目标。
这一步不是做同模型身份识别，而是证明“异类静态目标规则”对队友没有误报。

Phase 5D-2：
在多艇场景中让多艘 SurfaceVessel 共享各自的目标候选，进行静态目标融合与重复观测去重。
目标仍保持静态，不进入动态目标跟踪或运动预测。
```

新的工程边界：

```text
1. 近期不再尝试用纯视觉语义去解决“同模型 SurfaceVessel 的敌我识别”。
2. 近期不把同一种 SurfaceVessel 同时设为队友和目标。
3. 近期目标仍然是静态目标，不进入动态跟踪。
4. 如需继续利用 5C-4I 的结论，只能继承“审计方法、阈值校准方法、35 m 可靠距离思路”，不能直接继承其目标 RGB signature。
```

---

**2026-06-15 补充更新：Phase 5D-0 已完成**

当前最新阶段已推进到 `Phase 5D-0`。

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d0_sphereagent_static_target_calibration/
```

5D-0 已完成离线校准、HoloOcean 复跑验证和审计：

```text
audit.all_passed = true
```

5D-0 的关键结论：

1. 目标为静态 `SphereAgent`，队友负例为 `SurfaceVessel`。
2. 没有继续把同一种模型同时作为队友和目标。
3. 推荐规则为 `sphere_blob_any_hit`。
4. HoloOcean 复跑规则为 `sphere_blob_any_hit and any_rangefinder_hit`。
5. 5D-0 不再直接套用 5C-4I 的 SurfaceVessel-like RGB signature / overlap 阈值。
6. `teammate_only` 场景中 `SurfaceVessel` 队友误报为 0。
7. 校准轮推荐规则的最大扇形全区域可靠距离为 `35 m`。
8. 验证轮 20 m / 35 m / 50 m 均为 5/5 target true positive，但 50 m 仍按校准轮与验证轮交集采用保守口径，不作为下一阶段工程边界。
9. 后续工程中最远可识别距离先设为 `35 m`。

5D-0 的实现侧要点：

```text
found = sphere_blob_any_hit AND any_rangefinder_hit
```

其中 `sphere_blob_any_hit` 来自 RGBCamera 相对 baseline 的亮色中性紧凑 blob 证据；`any_rangefinder_hit` 来自多射线 RangeFinder 的物体命中证据。二者都不使用 HoloOcean truth 触发 detection，truth 只用于 audit 对照。

5D-0 期间还修正了一个验证稳定性问题：

```text
SphereAgent 在中心 20 m 场景中偶尔会被 RGB mask 分裂成上下两个小 blob。
当前规则对 sphere blob mask 增加 1x3 竖向闭运算，用于连接这类分裂。
该修正后 validation 中 target_sphere_center_20m 恢复为 true positive，SurfaceVessel teammate-only 仍保持 0 false positive。
```

5D-1 已按该目标执行。队友排除主项通过，但完整审计暴露了目标与队友共存时的远距离漏检问题，见后续 5D-1 补充更新。

---

**2026-06-15 补充更新：Phase 5D-1 已执行，完整审计未通过**

当前最新执行阶段已推进到 `Phase 5D-1`。

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d1_surfacevessel_teammate_exclusion_validation/
```

5D-1 已完成脚本编译、HoloOcean calibration、HoloOcean validation 和 audit：

```text
audit.all_passed = false
```

5D-1 的关键事实：

1. 5D-1 没有推翻 5D-0 的固定规则，仍验证 `sphere_blob_any_hit and any_rangefinder_hit`。
2. 目标仍为静态 `SphereAgent`，队友负例仍为 `SurfaceVessel`。
3. validation 共 42 个场景：baseline 1，calibration 1，target-only 10，teammate-only 27，target-with-teammate 3。
4. `teammate-only` 结果为 `27/27 true_negative`，`SurfaceVessel` 队友误报为目标的数量为 0。
5. target-only 结果为 `10/10 true_positive`，20 m 与 35 m 的 5 个扇形角度均识别成功。
6. 最大扇形全区域可靠距离仍为 `35 m`。
7. target-with-teammate 结果为 `1/3 true_positive`，有 2 个 35 m 共存正例漏检。

漏检场景：

```text
coexist_sphere_center_35m_teammate_right_inner_20m
coexist_sphere_left_inner_35m_teammate_right_outer_35m
```

漏检根因不是 RangeFinder 没命中。两个漏检场景中 RangeFinder 均有命中，问题集中在 `sphere_blob_any_hit` 的 RGB blob 判据：

```text
当前 sphere blob 判据包含 best_blob_area_ratio >= 0.6
best_blob_area_ratio = best sphere-like blob area / all white-neutral changed pixels
```

当 `SurfaceVessel` 队友与 `SphereAgent` 目标同框时，队友也会贡献 white-neutral changed pixels，导致分母变大。35 m 的 `SphereAgent` 局部 blob 仍存在，但面积占比被稀释，因此 `sphere_blob_present` 变为 false。

离线复核显示：

```text
如果仅使用局部 sphere-like blob 形状 + RangeFinder，而不使用全局 white-neutral 面积占比：
target-present 可以恢复为 14/14 true_positive
teammate-only 仍保持 0 false_positive
```

但这属于规则修正，不能把 5D-1 包装为已通过。因此 5D-1 的阶段结论应写为：

```text
SurfaceVessel teammate-only exclusion passed.
Full teammate coexistence validation failed due to 35 m target false negatives.
Do not enter Phase 5D-2 until the sphere blob coexistence rule is repaired and audited.
```

建议下一步先进入：

```text
Phase 5D-1A：SphereAgent 与 SurfaceVessel 队友共存场景下的 sphere blob 判据修正验证
```

5D-1A 的目标：

1. 保持目标为静态 `SphereAgent`，队友为 `SurfaceVessel`。
2. 不使用 truth 触发 detection。
3. 不修改核心搜索算法和既有 bridge。
4. 将 `sphere_blob_any_hit` 的“全局 white-neutral 面积占比”约束替换或降级为更局部的 blob 形状约束。
5. 必须同时满足：
   - teammate-only false positive = 0；
   - target-only 20 m / 35 m = 10/10 true positive；
   - target-with-teammate = 3/3 true positive；
   - max reliable distance remains 35 m。

---

**2026-06-15 补充更新：Phase 5D-1A 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-1A`。

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d1a_sphere_blob_local_range_scaled_validation/
```

5D-1A 已完成脚本编译、HoloOcean calibration、HoloOcean validation 和 audit：

```text
audit.all_passed = true
```

5D-1A 的推荐规则为：

```text
found = sphere_blob_local_range_scaled_any_hit
```

该规则没有继续使用 5D-1 中容易被队友稀释的全局 `best_blob_area_ratio` 作为主判据，而是使用：

```text
local sphere-like blob candidate
AND matched RangeFinder beam hit
AND distance-scaled blob area threshold
```

阶段边界保持不变：

1. 目标仍为静态 `SphereAgent`。
2. 队友仍为 `SurfaceVessel`。
3. 不使用 truth 触发 detection，truth 只用于 audit。
4. 不修改核心搜索算法。
5. 不修改既有 `baseline_GP/holoocean_bridge/*` 文件。

validation 共 53 个场景，审计关键结果：

```text
target-only:           20/20 true_positive
target-with-teammate:   9/9 true_positive
teammate-only:         22/22 true_negative
target false negative:  0
teammate false positive: 0
max reliable distance: 35.0 m
```

5D-1A 的阶段结论：

```text
The 5D-1 teammate coexistence false negatives are repaired.
SurfaceVessel teammate-only exclusion remains clean.
Static SphereAgent target recognition remains reliable over the full fan area up to 35 m.
Phase 5D can proceed to multi-SurfaceVessel cooperative search under the static SphereAgent target boundary.
```

注意：5D-1A 解决的是“`SphereAgent` 目标 + `SurfaceVessel` 队友”的异类静态目标识别问题。当前规则会把目标形态限定为 sphere-like blob，不代表已经具备通用未知物体语义识别能力。后续如果要支持箱体、浮标、船体或其他未知静态目标，应另行引入 `target_profile` 或更高层语义分类。

建议下一步进入：

```text
Phase 5D-2：多艘 SurfaceVessel 协同搜索静态 SphereAgent
```

---

**2026-06-16 补充更新：Phase 5D-2 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-2`。

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d2_multi_surfacevessel_static_sphereagent_coop_search/
```

5D-2 已完成脚本编译、HoloOcean capture 和 audit：

```text
audit.all_passed = true
```

5D-2 沿用 5D-1A 的推荐感知规则：

```text
per-agent found_candidate = sphere_blob_local_range_scaled_any_hit
```

阶段新增验证的是多艇协同层：

```text
每艘 SurfaceVessel 独立产生 detection event
每个 event 携带 reporter_usv_id / sensor_id / estimated_world_position / range / bearing
候选事件共享到 team 层
已知 teammate 身份与位置用于 candidate exclusion
空间相近的 target candidates 融合为单个 shared target candidate
```

阶段边界：

1. 观察者为两艘 `SurfaceVessel`：`sv0`, `sv1`。
2. 目标仍为静态 `SphereAgent`。
3. 队友仍为 `SurfaceVessel`。
4. 目标和队友不是同一种模型。
5. 可靠识别距离仍按 `35 m`。
6. truth 不触发 detection，只用于 audit。
7. 不修改核心搜索算法。
8. 不修改既有 `baseline_GP/holoocean_bridge/*` 文件。
9. 5D-2 当前是固定多艇搜索位姿下的候选共享 / 融合验证，不是完整连续路径搜索闭环。

HoloOcean validation 共 5 个场景、10 条 per-agent detection events：

```text
baseline:              1 scene -> true_negative
target-only:           1 scene -> true_positive
target-with-teammate:  1 scene -> true_positive
teammate-only:         2 scenes -> true_negative
```

审计关键结果：

```text
observer_count = 2
event_count = 10
fusion_outcome_counts = {"true_negative": 3, "true_positive": 2}
target_fusion_outcome_counts = {"true_positive": 2}
teammate_fusion_outcome_counts = {"true_negative": 2}
target_false_negative_scenes = []
teammate_false_positive_scenes = []
duplicate_merge_scenes = ["target_sphere_duplicate_20m_two_observers"]
shared_target_found = true
```

5D-2 的直白结论：

```text
两艘 SurfaceVessel 可以各自产生 5D-1A 感知事件。
20 m target 被两艘艇重复观测时，team 层可以融合成 1 个 shared target candidate。
35 m target 与 SurfaceVessel 队友共存时仍可被 shared found。
SurfaceVessel teammate-only 场景没有被误判为 SphereAgent 目标。
```

5D-2 尚未完成的内容：

```text
尚未把 candidate fusion 接入 baseline_GP 的连续多步搜索执行循环。
尚未验证多艇沿规划路径移动时的 found_mask / all_found 终止链。
尚未进入动态目标跟踪。
尚未扩展到非 sphere-like blob 的未知目标类别。
```

建议下一步进入：

```text
Phase 5D-3：将 5D-2 per-agent detection event / candidate fusion 接入 baseline_GP 多艇连续搜索闭环
```

---

**2026-06-17 补充更新：Phase 5D-3 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-3`。

目录：

```text
baseline_GP/results/holoocean_bridge_v1/phase5d3_continuous_multistep_coop_search/
```

5D-3 已完成脚本编译、HoloOcean 连续多步 capture 和 audit：

```text
audit.all_passed = true
```

5D-3 沿用 5D-1A / 5D-2 的推荐感知规则：

```text
per-agent found_candidate = sphere_blob_local_range_scaled_any_hit
```

阶段新增验证的是连续搜索闭环：

```text
两艘 SurfaceVessel 在预设连续轨迹中按 step/tick 推进
每个 tick 产生 per-agent detection event
candidate fusion 接收每步的候选事件
fusion 结果更新 shared_found / found_mask / all_found
重复观测的同一 SphereAgent 目标被融合为单个 shared target candidate
```

阶段边界：

1. 观察者仍为两艘 `SurfaceVessel`：`sv0`, `sv1`。
2. 目标仍为静态 `SphereAgent`。
3. 队友仍为 `SurfaceVessel`。
4. 目标和队友不是同一种模型。
5. 可靠识别距离仍按 `35 m`。
6. truth 不触发 detection，只用于 audit。
7. 不修改核心搜索算法。
8. 不修改既有 `baseline_GP/holoocean_bridge/*` 文件。
9. 5D-3 使用预设连续轨迹验证闭环，不是完整接入 `baseline_GP` 原始规划器回调 / 主执行接口。

审计关键结果：

```text
recommended_rule_id = sphere_blob_local_range_scaled_any_hit
event_count = 288
policy_trace_count = 12
fusion_trace_count = 12
target_found_steps = [1, 2, 3, 4]
coexist_found_steps = [1, 2, 3, 4]
teammate_false_positive_steps = []
duplicate_observation_fused_steps = [3]
all_found_step = 1
truth_used_for_detection = false
search_decision_algorithm_modified = false
existing_holoocean_bridge_modified = false
```

5D-3 的直白结论：

```text
5D-2 的 per-agent event / candidate fusion 可以在连续多步 HoloOcean 循环中工作。
target-only 与 target-with-teammate 在 4 个连续搜索 step 中均能 shared found。
teammate-only 场景没有出现 SurfaceVessel 被误判为 SphereAgent 目标。
同一目标被两艘艇重复观测时，可以融合为一个 shared target candidate。
fusion 结果可以驱动 found_mask / all_found 更新，当前 all_found_step = 1。
```

5D-3 尚未完成的内容：

```text
尚未完整耦合 baseline_GP 原始多步搜索执行接口。
尚未替换原始 planner callback / mainline 中的搜索执行链。
尚未进入动态目标跟踪。
尚未扩展到非 sphere-like blob 的未知目标类别。
```

建议下一步进入：

```text
Phase 5D-4：将 5D-3 连续闭环进一步耦合到 baseline_GP 原始多步搜索执行接口
```

---


**当前接力指令：5D-3 已完成并通过审计，下一步耦合 baseline_GP 原始多步搜索执行接口**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C 静态目标感知链工作。

请先阅读：
F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档中的“2026-06-16 补充更新：Phase 5D-2 已完成，完整审计通过”和“2026-06-17 补充更新：Phase 5D-3 已完成，完整审计通过”。

当前最新执行阶段是 5D-3，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d3_continuous_multistep_coop_search/

5D-3 已完成 HoloOcean 连续多步 capture / candidate fusion / found_mask / all_found audit，完整审计通过：
audit.all_passed = true

5D-3 的关键结论：
1. 观察者为两艘 SurfaceVessel：sv0 / sv1。
2. 目标为静态 SphereAgent，队友为 SurfaceVessel。
3. 沿用 5D-1A / 5D-2 推荐规则 sphere_blob_local_range_scaled_any_hit。
4. 5D-3 验证的是预设连续轨迹下的 per-agent event、candidate fusion、found_mask 和 all_found 更新链。
5. validation 共 288 条 per-agent detection events。
6. target-only 与 target-with-teammate 在 4 个连续搜索 step 中均能 shared found。
7. teammate-only false positive steps = []。
8. 同一 SphereAgent 被两艘艇重复观测时，候选被融合为 1 个 shared target candidate。
9. all_found_step = 1。
10. 最大可靠识别距离仍为 35 m。
11. 5D-3 没有使用 truth 触发 detection，truth 只用于 audit。
12. 5D-3 尚未完整接入 baseline_GP 原始 planner callback / mainline 搜索执行接口。

下一步执行 Phase 5D-4：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 将 5D-3 的连续多步 HoloOcean 闭环进一步耦合到 baseline_GP 原始多步搜索执行接口。
4. 验证 planner callback / mainline 执行链中的 found_mask / shared_found / all_found 终止链。
5. 继续保持最大可靠识别距离 35 m。
6. 继续保证 truth 只用于 audit，不触发 detection。
7. 不进入动态目标跟踪，不扩展到非 sphere-like blob 目标类别。
```

---

**2026-06-17 补充更新：Phase 5D-4 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-4`。
目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d4_mainline_search_interface_coupling/
```

5D-4 已完成脚本编译、baseline_GP 原始双艇 mainline 搜索执行接口耦合验证和 audit：
```text
audit.all_passed = true
```

5D-4 沿用 5D-1A / 5D-2 / 5D-3 的推荐感知规则：
```text
per-agent found_candidate = sphere_blob_local_range_scaled_any_hit
```

本阶段新增验证的是 `baseline_GP.marine_knownmap_runtime_2usv` 原始主线接口链：
```text
detect_targets -> team_detected_mask -> update_found_mask -> found_mask/find_times -> np.all(found_mask) -> terminated_reason = all_found
```

5D-4 的实现方式为轻量 runtime adapter：
```text
使用 5D-3 的 per-agent sensor detection events 和 candidate fusion trace 作为输入；
运行期替换 mainline detect_targets callable；
运行期包裹 update_found_mask 只做 trace，并委托原始 update_found_mask 执行；
run_episode_two_usv_search_knownmap 原始双艇 mainline loop 照常执行；
脚本结束后恢复原始 callable；
不修改 baseline_GP 核心搜索算法文件。
```

审计定位到的原始 mainline 接口位置包括：
```text
state_initial_found_mask_and_find_times: marine_knownmap_runtime_2usv.py:1873
initial_team_detection_mask:             marine_knownmap_runtime_2usv.py:1879
initial_update_found_mask:               marine_knownmap_runtime_2usv.py:1889
mainline_episode_loop:                   marine_knownmap_runtime_2usv.py:2964
mainline_step_team_detection_mask:       marine_knownmap_runtime_2usv.py:3103
mainline_step_update_found_mask:         marine_knownmap_runtime_2usv.py:3115
mainline_all_found_termination:          marine_knownmap_runtime_2usv.py:2961
```

审计关键结果：
```text
recommended_rule_id = sphere_blob_local_range_scaled_any_hit
target_terminated_reason = all_found
target_time_to_all_found = 1
coexist_terminated_reason = all_found
teammate_false_positive_steps = []
duplicate_replay_detected_steps = [3]
duplicate_observation_fused = true
adapter_trace_count = 26
mainline_trace_count = 13
truth_used_for_detection = false
baseline_runtime_source_modified = false
search_decision_algorithm_modified = false
existing_holoocean_bridge_modified = false
```

5D-4 的直白结论：
```text
5D-3 的 HoloOcean per-agent event / candidate fusion 结果可以通过轻量 adapter 驱动 baseline_GP 原始双艇 mainline 搜索接口。
target-only 场景中，adapter 产生的 detection mask 通过原始 update_found_mask 更新 found_mask/find_times，并触发 terminated_reason = all_found，time_to_all_found = 1。
target-with-teammate/coexist 场景中，同样可以通过原始 mainline 链完成 all_found。
teammate-only 场景中，SurfaceVessel 队友没有被误判为 SphereAgent 目标，false positive steps = []。
duplicate replay 场景中，5D-3 第 3 步两艇重复观测同一 SphereAgent 后融合为 1 个 shared target candidate，并能驱动原始 mainline found_mask/all_found 链，duplicate_replay_detected_steps = [3]。
truth 仍只用于 audit，不参与 detection。
```

阶段边界保持不变：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 core_search_policy.py、core_execution.py、core_targets.py、core_intensity.py、core_safe_nav.py。
7. 不修改 marine_knownmap_runtime.py、marine_knownmap_runtime_2usv.py。
8. 不修改既有 baseline_GP/holoocean_bridge/* 文件。
9. 最大可靠识别距离继续按 35 m。
10. truth 只用于 audit，不触发 detection。
```

5D-4 仍未完成或不包含的内容：
```text
尚未把 adapter 固化为正式 production API。
尚未把 HoloOcean capture 本身直接嵌入 baseline_GP planner callback 的长期接口。
尚未进入动态目标跟踪。
尚未扩展到非 sphere-like blob 未知目标类别。
尚未处理复杂障碍物、遮挡、光照变化或通用视觉检测模型。
```

建议下一步进入：
```text
Phase 5D-5：将 5D-4 的 runtime adapter 口径整理为可复用的正式 mainline perception adapter 接口设计，但仍保持静态 SphereAgent / SurfaceVessel 队友 / 35 m / truth audit-only 边界。
```

---


**当前接力指令：5D-4 已完成并通过审计，下一步整理可复用 mainline perception adapter 接口**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-4 已完成，完整审计通过”
以及
“当前接力指令：5D-4 已完成并通过审计，下一步整理可复用 mainline perception adapter 接口”。

当前最新完成阶段是 Phase 5D-4，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d4_mainline_search_interface_coupling/

5D-4 已完成 5D-3 HoloOcean per-agent detection events / candidate fusion trace 到 baseline_GP 原始双艇 mainline 搜索执行接口的轻量耦合验证，完整审计通过：
audit.all_passed = true

5D-4 的关键结论：
1. 观察者仍为两艘 SurfaceVessel：sv0 / sv1。
2. 目标仍为静态 SphereAgent，队友仍为 SurfaceVessel。
3. 继续沿用推荐规则 sphere_blob_local_range_scaled_any_hit。
4. 5D-4 验证的是 5D-3 sensor event / candidate fusion 结果能驱动 baseline_GP 原始 mainline found_mask / find_times / all_found 终止链。
5. 原始接口链为 detect_targets -> team_detected_mask -> update_found_mask -> found_mask/find_times -> np.all(found_mask) -> terminated_reason = all_found。
6. target-only 通过原始 mainline 链 all_found，target_time_to_all_found = 1。
7. target-with-teammate/coexist 通过原始 mainline 链 all_found。
8. teammate-only false positive steps = []。
9. duplicate replay 中第 3 步两艇重复观测同一 SphereAgent 后融合为 1 个 shared target candidate，并驱动原始 mainline all_found。
10. 最大可靠识别距离仍为 35 m。
11. truth 没有触发 detection，只用于 audit。
12. 5D-4 没有修改 baseline_GP 核心搜索算法文件，也没有修改既有 baseline_GP/holoocean_bridge/* 文件。

下一步执行 Phase 5D-5：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 将 5D-4 的 runtime adapter 口径整理为可复用的正式 mainline perception adapter 接口设计。
6. 优先明确 adapter API 的输入输出：per-agent event、candidate fusion result、detected_mask、shared_found、found_mask update trace。
7. 继续保证 SurfaceVessel 队友不会被误判为 SphereAgent 目标。
8. 继续保证 truth 只用于 audit，不参与 detection。
9. 所有 5D-5 产物放入独立目录，不覆盖 5D-4 结果。
```
---

**2026-06-17 补充更新：Phase 5D-5 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-5`。
目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d5_reusable_mainline_perception_adapter/
```

5D-5 已完成脚本编译、可复用 mainline perception adapter API 设计、离线 replay 验证、mainline wrapper 验证和 audit：
```text
audit.all_passed = true
```

5D-5 继续沿用 5D-1A / 5D-2 / 5D-3 / 5D-4 的推荐感知规则：
```text
per-agent found_candidate = sphere_blob_local_range_scaled_any_hit
```

本阶段新增的是 phase-local 可复用 adapter API，而不是 production 模块迁移：
```text
adapter_class = ReusableMainlinePerceptionAdapter
api_methods = [reset_episode, observe_step, build_detected_mask, fusion_trace]
production_module_created = false
```

API 输入字段：
```text
per_agent_events
candidate_fusion_result
step_index
target_count
found_mask_before
known_teammates
```

API 输出字段：
```text
detected_mask
shared_found
new_found_candidate_count
found_update_trace
truth_used_for_detection
```

5D-5 的双层验证：
```text
1. Offline replay：使用 5D-3 per-agent events 和 candidate fusion rows，直接通过 ReusableMainlinePerceptionAdapter 生成 detected_mask / shared_found / found_update_trace。
2. Mainline wrapper：用同一个 adapter API 作为 runtime detect_targets provider，接入 baseline_GP 原始 two-USV mainline loop，并继续由原始 update_found_mask 负责 found_mask / find_times / all_found。
```

审计关键结果：
```text
adapter_class = ReusableMainlinePerceptionAdapter
offline_target_all_found_step = 1
offline_coexist_all_found_step = 1
offline_teammate_false_positive_steps = []
offline_duplicate_all_found_step = 3
mainline_target_time_to_all_found = 1
mainline_coexist_time_to_all_found = 1
mainline_teammate_false_positive_steps = []
mainline_duplicate_detected_steps = [3]
duplicate_observation_fused = true
offline_trace_count = 16
mainline_trace_count = 65
truth_used_for_detection = false
search_decision_algorithm_modified = false
existing_holoocean_bridge_modified = false
production_module_created = false
```

5D-5 的直白结论：
```text
5D-4 的 runtime-only adapter 口径已经被整理为明确的 phase-local 可复用 mainline perception adapter API。
该 API 可以从 5D-3 的 per-agent sensor events 和 candidate fusion result 生成 baseline_GP mainline 所需的 detected_mask / shared_found / found_update_trace。
离线 replay 能复现 target、coexist、teammate-only、duplicate replay 的 5D-4 关键语义。
mainline wrapper 能继续驱动原始 update_found_mask / found_mask / find_times / all_found 链。
SurfaceVessel teammate-only 场景仍无 false positive。
第 3 步 duplicate replay 仍证明两艇重复观测同一 SphereAgent 可融合为 1 个 shared target candidate 并驱动 mainline all_found。
truth 仍只用于 audit，不参与 detection。
```

阶段边界保持不变：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 core_search_policy.py、core_execution.py、core_targets.py、core_intensity.py、core_safe_nav.py。
7. 不修改 marine_knownmap_runtime.py、marine_knownmap_runtime_2usv.py。
8. 不修改既有 baseline_GP/holoocean_bridge/* 文件。
9. 最大可靠识别距离继续按 35 m。
10. truth 只用于 audit，不触发 detection。
```

5D-5 仍未完成或不包含的内容：
```text
尚未把 phase-local adapter 迁移为正式 production module。
尚未把 HoloOcean live capture 直接嵌入 baseline_GP planner callback 的长期接口。
尚未进入动态目标跟踪。
尚未扩展到非 sphere-like blob 未知目标类别。
尚未处理复杂障碍物、遮挡、光照变化或通用视觉检测模型。
```

建议下一步进入：
```text
Phase 5D-6：在不改变算法边界的前提下，评估是否将 5D-5 的 phase-local adapter API 迁移为正式模块或继续接入 live HoloOcean capture；若迁移，必须先冻结接口 contract 和 regression audit。
```

---


**当前接力指令：5D-5 已完成并通过审计，下一步评估 adapter 正式模块化或 live capture 接入**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-5 已完成，完整审计通过”
以及
“当前接力指令：5D-5 已完成并通过审计，下一步评估 adapter 正式模块化或 live capture 接入”。

当前最新完成阶段是 Phase 5D-5，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d5_reusable_mainline_perception_adapter/

5D-5 已完成可复用 mainline perception adapter API 的 phase-local 设计、offline replay 验证、mainline wrapper 验证和完整审计：
audit.all_passed = true

5D-5 的关键结论：
1. 观察者仍为两艘 SurfaceVessel：sv0 / sv1。
2. 目标仍为静态 SphereAgent，队友仍为 SurfaceVessel。
3. 继续沿用推荐规则 sphere_blob_local_range_scaled_any_hit。
4. 新增 adapter class 为 ReusableMainlinePerceptionAdapter。
5. API 方法为 reset_episode / observe_step / build_detected_mask / fusion_trace。
6. API 输入包括 per_agent_events、candidate_fusion_result、step_index、target_count、found_mask_before、known_teammates。
7. API 输出包括 detected_mask、shared_found、new_found_candidate_count、found_update_trace、truth_used_for_detection。
8. offline replay 复现 target all_found step = 1、coexist all_found step = 1、teammate false positives = []、duplicate all_found step = 3。
9. mainline wrapper 复现 target time_to_all_found = 1、coexist time_to_all_found = 1、teammate false positives = []、duplicate detected steps = [3]。
10. duplicate replay 继续证明两艇重复观测同一 SphereAgent 会融合为 1 个 shared target candidate 并驱动 mainline all_found。
11. 最大可靠识别距离仍为 35 m。
12. truth 没有触发 detection，只用于 audit。
13. 5D-5 没有修改 baseline_GP 核心搜索算法文件，也没有修改既有 baseline_GP/holoocean_bridge/* 文件。
14. 5D-5 仍是 phase-local API 验证，production_module_created = false。

下一步执行 Phase 5D-6：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 优先评估是否将 5D-5 的 phase-local adapter API 迁移为正式模块，或继续接入 live HoloOcean capture。
6. 若迁移为正式模块，必须先冻结 adapter API contract 和 regression audit。
7. 继续保证 SurfaceVessel 队友不会被误判为 SphereAgent 目标。
8. 继续保证 truth 只用于 audit，不参与 detection。
9. 所有 5D-6 产物放入独立目录，不覆盖 5D-5 结果。
```

---

**2026-06-17 补充更新：Phase 5D-6 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-6`。目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d6_production_mainline_perception_adapter/
```

5D-6 已完成 5D-5 phase-local adapter API 到正式 production module 的迁移、package export、offline regression、mainline wrapper regression 和完整审计：
```text
audit.all_passed = true
```

本阶段新增正式模块：
```text
baseline_GP/holoocean_bridge/mainline_perception_adapter.py
```

并在 package 初始化中导出正式 API：
```text
baseline_GP/holoocean_bridge/__init__.py
```

正式 adapter API：
```text
adapter_module = baseline_GP.holoocean_bridge.mainline_perception_adapter
adapter_class = ReusableMainlinePerceptionAdapter
api_methods = [reset_episode, observe_step, build_detected_mask, fusion_trace]
production_module_created = true
phase_local_only = false
package_export_ok = true
```

5D-6 继续沿用推荐感知规则：
```text
sphere_blob_local_range_scaled_any_hit
```

5D-6 的双层回归验证：
```text
1. Offline regression：从正式 production adapter module import ReusableMainlinePerceptionAdapter，使用 5D-3 per-agent events 和 candidate fusion rows 复现 5D-5 离线语义。
2. Mainline wrapper regression：从正式 production adapter module import 同一 adapter API，作为 runtime detect_targets provider 接入 baseline_GP 原始 two-USV mainline loop，并继续由原始 update_found_mask 负责 found_mask / find_times / all_found。
```

审计关键结果：
```text
adapter_module = baseline_GP.holoocean_bridge.mainline_perception_adapter
production_module_created = true
package_export_ok = true
offline_target_all_found_step = 1
offline_coexist_all_found_step = 1
offline_teammate_false_positive_steps = []
offline_duplicate_all_found_step = 3
mainline_target_time_to_all_found = 1
mainline_coexist_time_to_all_found = 1
mainline_teammate_false_positive_steps = []
mainline_duplicate_detected_steps = [3]
mainline_duplicate_accepted_candidate_counts = [2]
mainline_duplicate_fused_candidate_counts = [1]
duplicate_observation_fused = true
offline_trace_count = 16
mainline_trace_count = 65
truth_used_for_detection = false
reliable_distance_limit_m = 35.0
baseline_runtime_source_modified = false
search_decision_algorithm_modified = false
existing_holoocean_bridge_modified = true
live_capture_long_term_callback_integrated = false
live_capture_deferred_to_next_phase = true
```

5D-6 的直白结论：
```text
5D-5 的 phase-local ReusableMainlinePerceptionAdapter 已迁移为正式 baseline_GP.holoocean_bridge production module。
正式模块可以从 5D-3 的 per-agent sensor events 和 candidate fusion result 生成 baseline_GP mainline 所需的 detected_mask / shared_found / found_update_trace。
正式模块已通过 package export，可从 baseline_GP.holoocean_bridge 直接导入。
离线 regression 保持 target、coexist、teammate-only、duplicate replay 的 5D-5 关键语义。
mainline wrapper regression 继续证明正式 adapter 能驱动原始 update_found_mask / found_mask / find_times / all_found 链。
SurfaceVessel teammate-only 场景仍无 false positive。
第 3 步 duplicate replay 仍证明两艇重复观测同一 SphereAgent 可融合为 1 个 shared target candidate 并驱动 mainline all_found。
truth 仍只用于 audit，不参与 detection。
```

阶段边界保持不变：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 core_search_policy.py、core_execution.py、core_targets.py、core_intensity.py、core_safe_nav.py。
7. 不修改 marine_knownmap_runtime.py、marine_knownmap_runtime_2usv.py。
8. 仅新增/导出 baseline_GP/holoocean_bridge/mainline_perception_adapter.py 正式 adapter API。
9. 最大可靠识别距离继续按 35 m。
10. truth 只用于 audit，不触发 detection。
```

5D-6 仍未完成或不包含的内容：
```text
尚未把 HoloOcean live capture 直接长期嵌入 baseline_GP planner callback。
尚未把每一步真实 HoloOcean sensor capture 自动转成 adapter observe_step 输入。
尚未进入动态目标跟踪。
尚未扩展到非 sphere-like blob 未知目标类别。
尚未处理复杂障碍物、遮挡、光照变化或通用视觉检测模型。
```

建议下一步进入：
```text
Phase 5D-7：在不改变算法边界的前提下，将 HoloOcean live capture provider 接到正式 production adapter API，验证真实每步 capture -> per-agent event -> candidate fusion -> detected_mask -> 原始 update_found_mask -> all_found 的长期 callback 链。
```

---


**当前接力指令：5D-6 已完成并通过审计，下一步接入 live HoloOcean capture provider**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-6 已完成，完整审计通过”
以及
“当前接力指令：5D-6 已完成并通过审计，下一步接入 live HoloOcean capture provider”。

当前最新完成阶段是 Phase 5D-6，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d6_production_mainline_perception_adapter/

5D-6 已完成 5D-5 phase-local adapter API 到正式 production module 的迁移、offline regression、mainline wrapper regression 和完整审计：
audit.all_passed = true

5D-6 的关键结论：
1. 观察者仍为两艘 SurfaceVessel：sv0 / sv1。
2. 目标仍为静态 SphereAgent，队友仍为 SurfaceVessel。
3. 继续沿用推荐规则 sphere_blob_local_range_scaled_any_hit。
4. 正式 adapter module 为 baseline_GP.holoocean_bridge.mainline_perception_adapter。
5. 正式 adapter class 为 ReusableMainlinePerceptionAdapter。
6. API 方法为 reset_episode / observe_step / build_detected_mask / fusion_trace。
7. production_module_created = true，phase_local_only = false，package_export_ok = true。
8. offline regression 复现 target all_found step = 1、coexist all_found step = 1、teammate false positives = []、duplicate all_found step = 3。
9. mainline wrapper regression 复现 target time_to_all_found = 1、coexist time_to_all_found = 1、teammate false positives = []、duplicate detected steps = [3]。
10. duplicate replay 继续证明两艇重复观测同一 SphereAgent 会融合为 1 个 shared target candidate 并驱动 mainline all_found。
11. 最大可靠识别距离仍为 35 m。
12. truth 没有触发 detection，只用于 audit。
13. 5D-6 没有修改 baseline_GP 核心搜索算法文件，也没有修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
14. 5D-6 修改 baseline_GP/holoocean_bridge 的范围仅为新增 mainline_perception_adapter.py 并在 __init__.py 导出 API。
15. live_capture_long_term_callback_integrated = false，live capture 接入留到 5D-7。

下一步执行 Phase 5D-7：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 使用 5D-6 正式 adapter API，而不是重新复制 phase-local adapter。
6. 设计 live HoloOcean capture provider，将每步 HoloOcean sensor capture 转为 per-agent event 和 candidate fusion result。
7. 将 live provider 接入 baseline_GP planner callback / mainline search loop，验证真实每步 capture 能驱动原始 found_mask / all_found 终止链。
8. 继续保证 SurfaceVessel 队友不会被误判为 SphereAgent 目标。
9. 继续保证 truth 只用于 audit，不参与 detection。
10. 所有 5D-7 产物放入独立目录，不覆盖 5D-6 结果。
```

---

**当前迁移目标收口定义：核心闭合路径与扩展路径**

核心路径用于判断“当前限定范围内的 HoloOcean 真实搜索闭环”是否成立：
```text
Phase 5D-7：live capture provider 接入。
把每步真实 HoloOcean capture -> per-agent detection event -> candidate fusion result -> 5D-6 production adapter.observe_step 接通，替换 5D-3/5D-5 replay events 作为主 detection 来源。

Phase 5D-8：真实 planner 回调下的连续路径搜索。
让两艘 SurfaceVessel 按 baseline_GP mainline planner 实时决定的 viewpoint/segment 移动，边走边 live capture，边 detect，边通过原始 update_found_mask 更新 found_mask/find_times，并最终触发 all_found。
```

到 5D-8 通过时，核心迁移目标才算闭合：
```text
静态 SphereAgent
双 SurfaceVessel
真实 HoloOcean live capture
真实 baseline_GP planner 路径
candidate fusion
原始 update_found_mask
found_mask / all_found 终止链
```

5D-7 的关键风险与审计口径：
```text
1. 之前 all_found 建立在录制好的、已知会命中的 events 上。
2. 5D-7 换成实时 capture 后，35 m 距离边界、sphere blob 判据稳定性、连续运动视角和光照变化会第一次进入主链验证。
3. 因此 5D-7 不把 all_found_step = 1 作为硬指标。
4. 5D-7 记录 first_live_detection_step、first_shared_found_step、live_detection_success、false_positive_steps、max_reliable_detection_distance_observed_m。
5. truth 仍只用于 audit，不参与 detection。
```

扩展路径全部放在核心闭合之后，是否执行取决于迁移终点定义：
```text
1. 障碍物场景 + 二维 occupancy grid 几何对齐。
2. 多目标 N=3。
3. 动态目标。
4. 通用目标类别 / 真实视觉检测器。
```

推荐顺序：
```text
5D-7 live capture
-> 5D-8 真实 planner 回调连续搜索
-> 障碍+grid 几何对齐
-> 多目标 N=3
-> 动态目标
-> 通用检测器
```

---

**2026-06-17 补充更新：Phase 5D-7 已完成，完整审计通过**

当前最新执行阶段已推进到 `Phase 5D-7`。目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d7_live_capture_provider_coupling/
```

5D-7 已完成 live HoloOcean capture provider 到 5D-6 production adapter API 的接入验证：
```text
audit.all_passed = true
```

5D-7 的主链不再使用 5D-3 已录制 JSON events 作为 detection 输入，而是本阶段重新运行 HoloOcean：
```text
baseline live capture
target live capture
coexist live capture
teammate-only live capture
```

实时主链为：
```text
HoloOcean env.tick live sensor arrays
-> live per-agent detection event
-> live candidate fusion result
-> baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter.observe_step
-> detected_mask / shared_found
```

审计关键结果：
```text
production_adapter_module = baseline_GP.holoocean_bridge.mainline_perception_adapter
live_capture_primary_detection_source = true
replay_events_used_for_detection = false
phase5d3_json_events_used_for_detection = false
first_live_detection_step = 1
first_shared_found_step = 1
target_adapter_all_found_step = 1
coexist_adapter_all_found_step = 1
teammate_false_positive_steps = []
teammate_only_false_positive_count = 0
duplicate_observation_fused_steps = [3]
max_reliable_detection_distance_observed_m = 28.330398559570312
live_event_count = 288
live_fusion_trace_count = 12
live_provider_trace_count = 12
adapter_trace_count = 12
truth_used_for_detection = false
live_planner_callback_integrated = false
```

5D-7 暴露并修正的关键 live 问题：
```text
第一次 live capture 审计中，teammate-only 在第 4 步出现 false positive。
原因不是 adapter，也不是 truth 泄漏，而是候选世界坐标投影沿用了 5D-3 的预设轨迹 _path_at(tick)，没有使用本次 HoloOcean live run 的 LocationSensor 实际位置。
真实船体运动没有完全追上预设路径时，observer position 偏差会导致 teammate exclusion 距离计算错误，从而把 SurfaceVessel 队友误判为 SphereAgent candidate。
已修正为：live event 构建必须使用每 tick 的 LocationSensor 实际 observer_world_location；预设路径只可作为缺失传感器时的 fallback。
修正后 teammate_false_positive_steps = []，audit.all_passed = true。
```

5D-7 的直白结论：
```text
live HoloOcean capture provider 已能把本阶段实时采集到的 RGB/RangeFinder sensor arrays 转成 per-agent detection events 和 candidate fusion result。
5D-6 production adapter API 可直接消费 live provider 输出，不再依赖 5D-3 replay JSON events。
target 与 coexist 场景均能产生 live shared_found 并驱动 adapter detected_mask。
teammate-only 场景在使用 live LocationSensor 位置修正后无 false positive。
第 3 步 duplicate observation 仍可融合为 1 个 shared target candidate。
truth 仍只用于 audit，不参与 detection。
```

阶段边界保持不变：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
7. 使用 5D-6 production adapter API，不复制 phase-local adapter。
8. 最大可靠识别距离继续按 35 m；本阶段 live 实测最大 accepted detection distance 约 28.33 m。
9. truth 只用于 audit，不触发 detection。
```

5D-7 仍未完成或不包含的内容：
```text
尚未把 live capture provider 嵌入 baseline_GP 真实 planner callback。
尚未让两艇按 baseline_GP mainline planner 实时决定的 viewpoint/segment 运动。
尚未完成真实 planner 路径下的 live capture -> original update_found_mask -> all_found 闭环。
尚未进入障碍物 grid 对齐、多目标、动态目标或通用检测器扩展。
```

建议下一步进入：
```text
Phase 5D-8：真实 planner 回调下的连续路径搜索。将 5D-7 live capture provider 接入 baseline_GP mainline planner callback，让两艘 SurfaceVessel 按原始 planner 实时路径运动，边走边 capture，边 detect，边通过原始 update_found_mask 更新 found_mask/find_times，并最终触发 all_found。
```

---


**当前接力指令：5D-7 已完成并通过审计，下一步执行真实 planner 回调连续搜索**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-7 已完成，完整审计通过”
以及
“当前接力指令：5D-7 已完成并通过审计，下一步执行真实 planner 回调连续搜索”。

当前最新完成阶段是 Phase 5D-7，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d7_live_capture_provider_coupling/

5D-7 已完成 live HoloOcean capture provider 到 5D-6 production adapter API 的接入验证：
audit.all_passed = true

5D-7 的关键结论：
1. 观察者仍为两艘 SurfaceVessel：sv0 / sv1。
2. 目标仍为静态 SphereAgent，队友仍为 SurfaceVessel。
3. 继续沿用推荐规则 sphere_blob_local_range_scaled_any_hit。
4. 正式 adapter module 为 baseline_GP.holoocean_bridge.mainline_perception_adapter。
5. live_capture_primary_detection_source = true。
6. replay_events_used_for_detection = false。
7. target / coexist live capture 均能 shared_found，first_shared_found_step = 1。
8. teammate-only false positive steps = []。
9. duplicate_observation_fused_steps = [3]。
10. max_reliable_detection_distance_observed_m = 28.330398559570312。
11. truth 没有触发 detection，只用于 audit。
12. 5D-7 没有修改 baseline_GP 核心搜索算法文件，也没有修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
13. 5D-7 尚未接入真实 baseline_GP planner callback，live_planner_callback_integrated = false。
14. live event 构建必须使用 HoloOcean LocationSensor 实际 observer_world_location；不得用预设路径位置替代实时位置做候选投影和 teammate exclusion。

下一步执行 Phase 5D-8：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 使用 5D-6 production adapter API 和 5D-7 live capture provider 语义。
6. 将 live provider 接入 baseline_GP planner callback / mainline search loop。
7. 两艇运动路径必须来自 baseline_GP mainline planner 实时决策，而不是 5D-3 预设连续轨迹。
8. 每步执行链应为 planner decision -> HoloOcean SurfaceVessel movement -> live capture -> per-agent event -> candidate fusion -> adapter.observe_step -> detected_mask -> original update_found_mask -> found_mask/find_times -> all_found。
9. 继续保证 SurfaceVessel 队友不会被误判为 SphereAgent 目标。
10. 继续保证 truth 只用于 audit，不参与 detection。
11. 所有 5D-8 产物放入独立目录，不覆盖 5D-7 结果。
```

---

**2026-06-17 补充更新：Phase 5D-8 已执行，但未通过完整审计**

当前最新执行阶段已推进到 `Phase 5D-8`。目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d8_live_planner_callback_continuous_search/
```

5D-8 的目标是验证真实 baseline_GP planner callback 下的连续路径搜索：
```text
planner decision
-> HoloOcean SurfaceVessel movement
-> live capture
-> per-agent event
-> candidate fusion
-> production adapter.observe_step
-> detected_mask
-> original update_found_mask
-> found_mask/find_times
-> all_found
```

本阶段已经跑通的部分：
```text
live_planner_callback_integrated = true
planned_path_source = baseline_GP_mainline_planner
preset_trajectory_used = false
live_capture_primary_detection_source = true
replay_events_used_for_detection = false
phase5d3_json_events_used_for_detection = false
production_adapter_module = baseline_GP.holoocean_bridge.mainline_perception_adapter
mainline_update_found_mask_original_called = true
mainline_update_found_mask_called_count = 40
teammate_false_positive_steps = []
truth_used_for_detection = false
core_runtime_and_search_algorithm_not_modified = true
```

本阶段未通过的核心闭环项：
```text
audit.all_passed = false
phase_completed = false
phase_status = planner_live_callback_integrated_but_live_detection_all_found_not_closed
phase_goal_completed = false
target_terminated_reason = max_policy_steps
target_success_all_found = false
target_all_found_step = null
target_live_detection_success = false
target_live_accepted_candidate_present = false
target_shared_found_fusion_present = false
mainline_found_mask_updated_from_live_adapter = false
mainline_all_found_driven_by_live_adapter = false
max_reliable_detection_distance_observed_m = null
```

5D-8 的直白结论：
```text
真实 planner callback、HoloOcean 实时运动、live capture、production adapter、原始 update_found_mask 调用链已经接通。
但在 planner 实时决定的连续运动路径下，live RGB blob 与单射线扇形 RangeFinder hit 没有稳定形成 accepted SphereAgent candidate。
因此 adapter 没有输出 shared found，原始 found_mask 没有被 live detection 更新，all_found 没有触发。
teammate-only 场景仍无 false positive，SurfaceVessel 队友没有被误判为 SphereAgent。
truth 仍只用于 audit，不参与 detection。
所以 5D-8 不能写成核心迁移闭合；当前只能写成接口链已接通、真实 planner 运动下的 live detection/all_found 闭环未闭合。
```

5D-8 暴露的主要技术问题：
```text
5D-3 / 5D-7 的成功建立在预设轨迹或已知会命中的 live capture 姿态上。
5D-8 换成 baseline_GP mainline planner 实时路径后，船体姿态、目标相对方位、RGB 可见 blob、RangeFinder 单射线 fan hit 不再稳定同步。
旧规则 sphere_blob_local_range_scaled_any_hit 需要 RGB sphere blob 与 fan range hit 在同一 live event 中同时成立。
在真实 planner 运动轨迹下，该条件没有产生 accepted candidate。
这不是 truth 泄漏问题，也不是 teammate false positive 问题；阻塞点是静态 SphereAgent 在真实 planner 轨迹下的 live sensor geometry / capture timing 稳定性。
```

阶段边界保持不变：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
7. 继续使用 5D-6 production adapter API。
8. 继续使用 live LocationSensor / OrientationSensor 做 observer pose 与世界坐标投影。
9. truth 只用于 audit，不触发 detection。
```

建议下一步进入：
```text
Phase 5D-9 或 Phase 5D-8b：真实 planner 轨迹下的静态 SphereAgent live detection 稳定化。

目标不是改写 baseline_GP 核心 planner，也不是扩展动态目标或通用目标类别。
目标是在保持 SphereAgent + SurfaceVessel + production adapter + 原始 update_found_mask 的边界内，解决 planner 运动下 RGB blob 与 fan RangeFinder hit 不稳定同步的问题。

可优先评估：
1. 到达 planner cell 后增加轻量 heading stabilization / scan capture window，作为 HoloOcean bridge wrapper 行为，不改 core planner。
2. 记录每个 planner step 的相对方位、RangeFinder 命中射线、RGB blob frame、observer heading，定位未 accepted 的具体门限。
3. 校准 planner target cell 周边的物理放置偏移与 capture timing，但 truth 仍只能用于 audit，不能作为 detection 输入。
4. 审计目标仍为：target live accepted candidate -> shared_found -> original update_found_mask 更新 found_mask -> all_found；同时 teammate-only false positives = []。
```

---

**当前接力指令：5D-8 已执行但未通过完整审计，下一步稳定真实 planner 轨迹下的 live SphereAgent detection**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-8 已执行，但未通过完整审计”
以及
“当前接力指令：5D-8 已执行但未通过完整审计，下一步稳定真实 planner 轨迹下的 live SphereAgent detection”。

当前最新执行阶段是 Phase 5D-8，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d8_live_planner_callback_continuous_search/

5D-8 已经接通真实 planner callback / HoloOcean live movement / live capture / production adapter / original update_found_mask 调用链，但没有完成 all_found 闭环：
audit.all_passed = false

5D-8 的关键结论：
1. 观察者仍为两艘 SurfaceVessel：sv0 / sv1。
2. 目标仍为静态 SphereAgent，队友仍为 SurfaceVessel。
3. 继续沿用推荐规则 sphere_blob_local_range_scaled_any_hit。
4. 运动路径来自 baseline_GP mainline planner 实时决策，不是 5D-3 预设连续轨迹。
5. live_capture_primary_detection_source = true，replay_events_used_for_detection = false。
6. production adapter module 为 baseline_GP.holoocean_bridge.mainline_perception_adapter。
7. original update_found_mask 已被调用，mainline_update_found_mask_called_count = 40。
8. target live detection 没有产生 accepted candidate，target_live_detection_success = false。
9. found_mask 没有被 live adapter 更新，mainline_found_mask_updated_from_live_adapter = false。
10. all_found 没有触发，target_terminated_reason = max_policy_steps，target_all_found_step = null。
11. teammate-only false positive steps = []。
12. truth 没有触发 detection，只用于 audit。
13. 5D-8 没有修改 baseline_GP 核心搜索算法文件，也没有修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。

下一步执行 Phase 5D-9 或 Phase 5D-8b：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 不把 truth 接入 detection。
6. 优先定位 planner 运动下 RGB blob 与 fan RangeFinder hit 不稳定同步的原因。
7. 可以在 HoloOcean bridge wrapper 层评估到达 cell 后的短时 heading stabilization / scan capture window，但不得改 core planner。
8. 审计必须证明 target live accepted candidate -> shared_found -> original update_found_mask 更新 found_mask -> all_found。
9. 继续保证 SurfaceVessel 队友不会被误判为 SphereAgent 目标。
10. 所有 5D-9 / 5D-8b 产物放入独立目录，不覆盖 5D-8 结果。
```

---

**2026-06-17 补充更新：Phase 5D-8b 已执行，但仍未通过完整审计**

5D-8b 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d8b_live_planner_callback_scan_capture_search/
```

5D-8b 的目的：
```text
在不修改 baseline_GP core planner/runtime 的前提下，尝试通过 HoloOcean bridge 层的 post-arrival scan capture 与更密集 bridge fan RangeFinder 采样，解决 5D-8 真实 planner 运动下 RGB blob 与 RangeFinder hit 不同步的问题。
```

5D-8b 已经执行的 bridge 层尝试：
```text
post_arrival_scan_enabled = true
post_arrival_scan_ticks = 96
post_scan_recenter_ticks = 24
bridge_fan_rangefinder_sensor_count = 61
bridge_fan_yaw_degrees = [-30, +30] 之间 1 度间隔
recommended_rule_id = sphere_blob_local_range_scaled_any_hit
planned_path_source = baseline_GP_mainline_planner
preset_trajectory_used = false
live_capture_primary_detection_source = true
replay_events_used_for_detection = false
truth_used_for_detection = false
```

5D-8b 审计结果：
```text
audit.all_passed = false
phase_completed = false
phase_status = planner_live_callback_integrated_but_live_detection_all_found_not_closed
target_terminated_reason = max_policy_steps
target_all_found_step = null
target_live_detection_success = false
target_live_accepted_candidate_present = false
target_shared_found_fusion_present = false
mainline_update_found_mask_original_called = true
mainline_found_mask_updated_from_live_adapter = false
teammate_false_positive_steps = []
core_runtime_and_search_algorithm_not_modified = true
```

5D-8b 的关键实测统计：
```text
target events = 10486
target rangefinder hit events = 5
target sphere blob events = 147
target local candidate blob events = 204
target matched blob-range events = 0
target accepted candidate events = 0

teammate-only events = 10492
teammate-only rangefinder hit events = 272
teammate-only sphere blob events = 94
teammate-only matched blob-range events = 10
teammate-only accepted candidate events = 0
```

5D-8b 的直白结论：
```text
5D-8b 证明问题不是 baseline_GP 原始 planner callback、production adapter、update_found_mask 调用、truth 泄漏或 teammate false positive。
post-arrival scan capture 与 61 条密集 fan RangeFinder 后，target run 仍没有形成 matched blob-range event，因此没有 accepted SphereAgent candidate。
原始 update_found_mask 已被调用，但由于 detected_mask 始终未被 live target candidate 置真，found_mask/all_found 仍未触发。
teammate-only 仍保持 false positive = []。
核心迁移闭环仍未完成。
```

进一步定位：
```text
5D-8b 之前的 5D-8 trace 显示 sv0 能到达目标 cell 附近，最近约 3 m。
5D-8b 的 micro-check 显示固定几何下 RangeFinder 能命中 SphereAgent；但真实 planner 运动路径下 target run 仍无法稳定获得 RGB blob 与 RangeFinder hit 同步匹配。
当前阻塞点已经收窄到真实 planner 运动/姿态/相机背景差分/近距可见性共同作用下的 sphere_blob_local_range_scaled_any_hit 稳定性，而不是 mainline 搜索接口。
```

下一步建议：
```text
不要宣布 HoloOcean 真实搜索闭环已经成立。

Phase 5D-9 应专门做真实 planner 运动下的视觉候选稳定性修复：
1. 不改 baseline_GP core planner/runtime。
2. 不扩展动态目标。
3. 不扩展非 sphere-like 目标类别。
4. 不让 truth 参与 detection。
5. 优先分析 RGB sphere blob 在 planner live run 中为何弱于 5D-7 预设轨迹场景。
6. 可考虑把 bridge 层的 capture waypoint 从“压到目标 cell 附近”改成“保留 20-35 m 观察距离的感知驻点”，但这必须作为 HoloOcean bridge execution wrapper，而不是 core planner 改写。
7. 若继续调整检测门限，必须保持 teammate-only false positives = []，并单独审计 target / teammate-only / coexist。
```

---

**2026-06-17 补充更新：Phase 5D-9 已执行，但仍未通过完整审计**

5D-9 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d9_live_planner_standoff_capture_search/
```

5D-9 的目的：
```text
在不修改 baseline_GP core planner/runtime 的前提下，继续尝试通过 HoloOcean bridge wrapper 的 standoff capture / post-arrival scan / dense fan RangeFinder，稳定真实 planner 运动下的静态 SphereAgent live detection。
```

本阶段新增了一个 RGB 几何诊断：
```text
scripts/live_planner_standoff_rgb_geometry_diagnostic.py
manifests/phase5d9_rgb_geometry_diagnostic.json
reports/phase5d9_rgb_geometry_diagnostic.md
```

RGB 几何诊断结论：
```text
accepted_case_count = 7 / 7
origin_5d7_like_accepted = true
planner_translated_5d7_like_accepted = true
planner_front_center_30m_accepted = true

accepted cases:
- origin_5d7_sv0_like
- origin_5d1a_front_30m
- planner_translated_5d7_sv0_like
- planner_front_center_30m
- planner_front_center_20m
- planner_front_center_10m
- map_center_front_30m
```

该诊断说明：
```text
SphereAgent 静态目标在 planner 世界坐标区并非不可见。
在固定 standoff 几何下，10 m / 20 m / 30 m 正面观察都能形成 sphere_blob_local_range_scaled_any_hit。
因此 5D-8 / 5D-8b / 5D-9 的失败不能简单归因于“远离原点坐标导致 RGB blob 失效”。
当前主要问题是：真实 planner 运动过程中，船体姿态、目标相对方位、RGB baseline 差分、RangeFinder 命中时刻没有稳定配对。
```

5D-9 对完整 live planner callback search 做了以下 bridge wrapper 尝试：
```text
bridge_fan_rangefinder_sensor_count = 61
post_arrival_scan_enabled = true
post_arrival_scan_ticks = 96
post_scan_recenter_ticks = 24
scan_turn_force = 1200.0
post_arrival_zero_thrust_stabilization_enabled = true
post_arrival_stabilization_ticks = 48
recommended_rule_id = sphere_blob_local_range_scaled_any_hit
planned_path_source = baseline_GP_mainline_planner
preset_trajectory_used = false
live_capture_primary_detection_source = true
replay_events_used_for_detection = false
truth_used_for_detection = false
```

5D-9 完整 live planner callback search 审计结果：
```text
audit.all_passed = false
phase_completed = false
phase_status = planner_live_callback_integrated_but_live_detection_all_found_not_closed
phase_goal_completed = false
target_terminated_reason = max_policy_steps
target_all_found_step = null
target_live_detection_success = false
target_live_accepted_candidate_present = false
target_shared_found_fusion_present = false
mainline_update_found_mask_original_called = true
mainline_update_found_mask_called_count = 40
mainline_found_mask_updated_from_live_adapter = false
mainline_all_found_driven_by_live_adapter = false
teammate_false_positive_steps = []
core_runtime_and_search_algorithm_not_modified = true
```

5D-9 关键实测统计：
```text
target events = 10966
target rangefinder hit events = 7
target local candidate blob events = 193
target matched blob-range events = 0
target raw found events = 0
target accepted candidate events = 0

teammate-only events = 10934
teammate-only rangefinder hit events = 291
teammate-only local candidate blob events = 200
teammate-only matched blob-range events = 0
teammate-only raw found events = 1
teammate-only accepted candidate events = 0
teammate_false_positive_steps = []
```

5D-9 的直白结论：
```text
真实 planner callback、HoloOcean live movement、live capture、production adapter、original update_found_mask 调用链仍然是接通的。
固定 standoff 几何证明当前 SphereAgent 目标和既有规则本身仍可产生 accepted candidate。
但完整 planner 运动搜索中，target run 仍没有形成 matched blob-range event，因此没有 accepted SphereAgent candidate。
由于 detected_mask 始终没有被 live target candidate 置真，found_mask/all_found 仍未触发。
teammate-only 没有 accepted candidate，SurfaceVessel 队友仍未被误判为 SphereAgent 目标。
truth 仍只用于 audit，不参与 detection。
所以 HoloOcean 真实搜索闭环仍不能宣布成立。
```

当前阻塞点重新收窄为：
```text
不是 baseline_GP mainline planner callback 接口。
不是 production adapter 接口。
不是 original update_found_mask 调用。
不是 HoloOcean 坐标区导致 SphereAgent 完全不可见。
不是 teammate false positive。

而是：真实 planner 连续运动下，capture pose 没有稳定进入“可被 sphere_blob_local_range_scaled_any_hit 接受”的观察几何。
```

下一步建议进入 Phase 5D-10：
```text
目标：在不改 baseline_GP core planner/runtime 的前提下，在 HoloOcean bridge execution wrapper 层加入近目标感知驻点 / standoff viewpoint 控制，使真实 planner 路径到达目标附近后，不是继续压到目标 cell 或围绕目标漂移，而是保留 20-35 m 的前视观察距离并稳定朝向目标区采样。

必须保持：
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不扩展动态目标。
4. 不扩展非 sphere-like 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
7. 不让 truth 参与 detection；truth 只能用于 audit。
8. 继续使用 production adapter：baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter。
9. 继续使用推荐规则：sphere_blob_local_range_scaled_any_hit。
10. 继续要求 teammate-only false positives = []。

5D-10 审计闭合条件：
target live accepted candidate -> shared_found -> adapter detected_mask -> original update_found_mask 更新 found_mask/find_times -> all_found。
```

---

**当前接力指令：5D-9 已执行但未通过完整审计，下一步做 5D-10 近目标 standoff viewpoint 控制**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-9 已执行，但仍未通过完整审计”
以及
“当前接力指令：5D-9 已执行但未通过完整审计，下一步做 5D-10 近目标 standoff viewpoint 控制”。

当前最新执行阶段是 Phase 5D-9，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d9_live_planner_standoff_capture_search/

5D-9 已经证明：
1. 固定 standoff 几何下，planner 世界坐标区的 SphereAgent 可以被现有规则识别。
2. 完整真实 planner 运动搜索仍没有产生 target accepted candidate。
3. audit.all_passed = false。
4. target accepted candidate events = 0。
5. target matched blob-range events = 0。
6. teammate_false_positive_steps = []。
7. original update_found_mask 已被调用，但 found_mask/all_found 没有被 live detection 触发。
8. truth 没有触发 detection，只用于 audit。
9. baseline_GP 核心搜索算法和 runtime 文件未修改。

下一步执行 Phase 5D-10：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
6. 不把 truth 接入 detection。
7. 在 HoloOcean bridge execution wrapper 层实现近目标 standoff viewpoint / sensing hold。
8. 当 planner 路径进入目标附近或高概率区域时，让 USV 保留 20-35 m 前视观察距离，稳定朝向目标区 capture，而不是继续压到目标 cell。
9. 验证 target live accepted candidate -> shared_found -> original update_found_mask -> found_mask -> all_found 是否闭合。
10. 继续验证 teammate-only false positives = []。
11. 所有 5D-10 产物放入独立目录，不覆盖 5D-9 结果。
```

---

**2026-06-17 补充更新：Phase 5D-10 已执行，但仍未通过完整审计**

5D-10 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d10_live_planner_standoff_viewpoint_search/
```

5D-10 的目的：
```text
在不修改 baseline_GP core planner/runtime 的前提下，在 HoloOcean bridge execution wrapper 层加入 planner-segment lookahead standoff viewpoint hold。
目标是让真实 planner 路径执行过程中，USV 在 planner committed segment 的前瞻锚点附近保持朝向和采样窗口，尝试让 live RGB blob 与 61-beam fan RangeFinder 在同一 capture pose 下稳定配对。
```

5D-10 已执行的 bridge wrapper 尝试：
```text
standoff_viewpoint_hold_enabled = true
standoff_viewpoint_hold_ticks = 96
standoff_lookahead_segment_index = 4
standoff_turn_force = 1200.0
standoff_heading_tolerance_deg = 2.0
standoff_viewpoint_anchor_source = baseline_GP_planner_committed_segment_lookahead_not_target_truth
post_arrival_scan_enabled = true
post_arrival_scan_ticks = 96
post_scan_recenter_ticks = 24
bridge_fan_rangefinder_sensor_count = 61
recommended_rule_id = sphere_blob_local_range_scaled_any_hit
planned_path_source = baseline_GP_mainline_planner
preset_trajectory_used = false
production_adapter_module = baseline_GP.holoocean_bridge.mainline_perception_adapter
live_capture_primary_detection_source = true
replay_events_used_for_detection = false
truth_used_for_detection = false
```

5D-10 完整 live planner callback search 审计结果：
```text
audit.all_passed = false
phase_completed = false
phase_status = planner_live_callback_integrated_but_live_detection_all_found_not_closed
phase_goal_completed = false
target_terminated_reason = max_policy_steps
target_completed_steps = 20
target_all_found_step = null
target_live_detection_success = false
target_first_live_detection_step = null
target_first_shared_found_step = null
target_accepted_candidate_from_standoff_viewpoint_hold = false
target_accepted_candidate_from_scan = false
mainline_update_found_mask_called = true
mainline_update_found_mask_called_count = 40
mainline_found_mask_updated_from_live_adapter = false
mainline_all_found_driven_by_live_adapter = false
teammate_false_positive_steps = []
teammate_only_false_positive_count = 0
truth_flags_false = true
baseline_runtime_source_modified = false
search_decision_algorithm_modified = false
```

5D-10 关键实测统计：
```text
event_count = 27114
target_event_count = 13522
teammate_event_count = 13592
fusion_trace_count = 40
adapter_trace_count = 40
mainline_update_trace_count = 40
tick_trace_count = 40786

target_standoff_viewpoint_hold_tick_count = 3840
target_scan_tick_count = 3840
teammate_standoff_viewpoint_hold_tick_count = 3840
teammate_scan_tick_count = 3840

target candidate_count_positive rows = 504
target rangefinder hit rows = 3
target local_range_scaled_blob_present rows = 0
target raw_sensor_found rows = 0
target accepted_candidate rows = 0

teammate-only candidate_count_positive rows = 267
teammate-only rangefinder hit rows = 516
teammate-only blob_and_hit rows = 15
teammate-only raw_sensor_found rows = 15
teammate-only teammate_rejected rows = 15
teammate-only accepted_candidate rows = 0
```

5D-10 的关键定位：
```text
target run 中确实出现了少量 RangeFinder hit，但没有任何 local_range_scaled_blob_present。
target run 中 504 条 local candidate 多数是弱候选或大面积背景变化，未通过 sphere_blob_local_range_scaled_any_hit。
teammate-only 中出现 15 条 raw blob-range，但全部被 teammate exclusion 拦截，因此 SurfaceVessel 队友仍没有被误判为 SphereAgent。
original update_found_mask 被调用，但 adapter detected_mask 始终没有被 target live accepted candidate 置真，found_mask/all_found 不可能更新。
```

5D-10 的直白结论：
```text
真实 planner callback、HoloOcean live movement、live capture、production adapter、candidate fusion、original update_found_mask 调用链仍然是接通的。
planner-segment lookahead standoff viewpoint hold 没有解决 target run 的 live RGB blob / RangeFinder 同步观测问题。
5D-10 没有形成 target accepted candidate，因此没有 shared_found，没有 found_mask 更新，也没有 all_found。
teammate-only 仍无 false positive。
truth 仍只用于 audit，不参与 detection。
baseline_GP 核心搜索算法和 runtime 文件仍未修改。
所以 HoloOcean 真实搜索闭环仍不能宣布成立。
```

当前阻塞点进一步收窄为：
```text
不是 baseline_GP mainline planner callback 接口。
不是 production adapter 接口。
不是 original update_found_mask 调用。
不是 candidate fusion 接口。
不是 teammate false positive。
不是固定几何下 SphereAgent 完全不可见。

而是：真实 planner live target run 中，capture provider 没有稳定产生可被 sphere_blob_local_range_scaled_any_hit 接受的 target RGB blob evidence。
具体表现是 target run 的 RangeFinder hit 很少，且 local_range_scaled_blob_present 始终为 0。
```

下一步建议进入 Phase 5D-11：
```text
目标：专门修复真实 planner live target run 中的 SphereAgent RGB blob evidence / RangeFinder 同步观测问题。

优先方向：
1. 不再优先改 found_mask / all_found 接口，因为该链已证明接通。
2. 不重写 baseline_GP core planner/runtime。
3. 不扩展动态目标。
4. 不扩展非 sphere-like 目标类别。
5. 不让 truth 参与 detection；truth 只能用于 audit。
6. 使用 5D-9 固定 standoff 几何通过的 case 作为 live target run 的 capture-pose 对照基线。
7. 在独立 5D-11 目录中增加 target run 的 RGB frame / diff mask / local candidate blob / RangeFinder beam overlay 取样图，确认 target run 中候选为什么没有通过 local_range_scaled_blob_present。
8. 分开审计 target-only、teammate-only、必要时 coexist；继续要求 teammate-only false positives = []。
9. 审计闭合条件仍为 target live accepted candidate -> shared_found -> adapter detected_mask -> original update_found_mask 更新 found_mask/find_times -> all_found。
```

---

**当前接力指令：5D-10 已执行但未通过完整审计，下一步做 5D-11 live target RGB/RangeFinder 同步观测修复**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-10 已执行，但仍未通过完整审计”
以及
“当前接力指令：5D-10 已执行但未通过完整审计，下一步做 5D-11 live target RGB/RangeFinder 同步观测修复”。

当前最新执行阶段是 Phase 5D-10，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d10_live_planner_standoff_viewpoint_search/

5D-10 已经证明：
1. 真实 planner callback / HoloOcean live movement / live capture / production adapter / original update_found_mask 调用链仍然接通。
2. planner-segment lookahead standoff viewpoint hold 已执行，但没有产生 target accepted candidate。
3. audit.all_passed = false。
4. target accepted candidate events = 0。
5. target local_range_scaled_blob_present rows = 0。
6. target rangefinder hit rows = 3。
7. teammate-only raw blob-range rows = 15，但全部被 teammate exclusion 拦截。
8. teammate_false_positive_steps = []。
9. original update_found_mask 已被调用 40 次，但 found_mask/all_found 没有被 live detection 触发。
10. truth 没有触发 detection，只用于 audit。
11. baseline_GP 核心搜索算法和 runtime 文件未修改。

下一步执行 Phase 5D-11：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
6. 不把 truth 接入 detection。
7. 继续使用 production adapter：baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter。
8. 继续使用推荐规则：sphere_blob_local_range_scaled_any_hit，除非以独立审计证明门限微调不会引入 teammate false positive。
9. 优先对比 5D-9 固定 standoff 几何通过 case 与 5D-10 live target run 失败 case，输出 RGB frame / diff mask / local candidate blob / RangeFinder beam overlay 证据。
10. 验证 target live accepted candidate -> shared_found -> original update_found_mask -> found_mask -> all_found 是否闭合。
11. 继续验证 teammate-only false positives = []。
12. 所有 5D-11 产物放入独立目录，不覆盖 5D-10 结果。
```

---

**2026-06-17 补充更新：Phase 5D-11 已执行，诊断审计通过但真实搜索闭环仍未闭合**

5D-11 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d11_live_target_rgb_range_sync_diagnostic/
```

5D-11 的目的：
```text
不是再次运行完整 planner search，也不是宣布 all_found 闭环。
本阶段只做 visual diagnostic：从 5D-10 target run 中选取失败 observer pose，构造独立静态 HoloOcean target/baseline 对照场景，保存 RGB frame / diff mask / white-neutral mask / local candidate overlay / RangeFinder beam overlay，并用原始推荐规则 sphere_blob_local_range_scaled_any_hit 复算。
```

新增产物：
```text
scripts/live_target_rgb_range_sync_visual_diagnostic.py
scripts/live_target_rgb_range_sync_visual_audit.py
manifests/phase5d11_rgb_range_sync_diagnostic.json
manifests/phase5d11_rgb_range_sync_diagnostic.csv
manifests/phase5d11_rgb_range_sync_per_tick.csv
manifests/phase5d11_rgb_range_sync_audit.json
reports/phase5d11_rgb_range_sync_diagnostic.md
reports/phase5d11_rgb_range_sync_audit_summary.md
visuals/*.png
```

5D-11 audit 结果：
```text
diagnostic_audit_only = true
audit.all_passed = true
source_5d10_audit_all_passed_false = true
control_case_accepted = true
target_failure_static_replay_accepted_count = 3
target_failure_static_replay_accepted_cases = [
  target_range_hit_failure_1,
  target_range_hit_failure_2,
  target_range_hit_failure_3
]
visual_previews_exist = true
truth_flags_false = true
diagnostic_not_claiming_search_closure = true
core_runtime_and_search_algorithm_not_modified = true
```

5D-11 关键对照结果：
```text
control_5d9_planner_front_center_30m:
  accepted = true
  replay_range_m = 30.000
  replay_rel_bearing = 0.000

target_range_hit_failure_1:
  5D-10 live source: src_rgb = 0, src_local_candidates = 0, hit_beams = [56]
  5D-11 static replay: accepted = true, replay_rgb = 56, white_neutral = 38, local_candidates = 1, hit_beams = [55, 56, 57]

target_range_hit_failure_2:
  5D-10 live source: src_rgb = 0, src_local_candidates = 0, hit_beams = [58]
  5D-11 static replay: accepted = true, replay_rgb = 56, white_neutral = 40, local_candidates = 1, hit_beams = [57, 58, 59]

target_range_hit_failure_3:
  5D-10 live source: src_rgb = 0, src_local_candidates = 0, hit_beams = [60]
  5D-11 static replay: accepted = true, replay_rgb = 68, white_neutral = 42, local_candidates = 1, hit_beams = [60]

target_best_candidate_failure / target_standoff_candidate_failure:
  replay_range_m = 8.469
  replay_rel_bearing = -139.507
  accepted = false
  说明该类近距/背向 pose 本身不适合当前前视 sphere blob 规则。

target_large_diff_failure:
  replay_range_m = 2.909
  replay_rel_bearing = 93.220
  accepted = false
  说明该类极近距/侧向 pose 本身也不适合当前前视 sphere blob 规则。
```

5D-11 的直白结论：
```text
5D-10 中 3 个 target RangeFinder 命中但 RGB diff/local blob 为 0 的失败 pose，在 5D-11 独立静态重放中全部能被现有规则识别。
因此，这 3 个失败 pose 的几何与规则本身不是问题；它们在正确 target/baseline 成对帧下可以形成 accepted candidate。
问题进一步收窄到完整 live planner run 中的 RGB frame / calibration baseline reference / tick 对齐 / capture timing。

另一方面，5D-10 的近距背向或侧向 pose 在 5D-11 静态重放中仍失败，说明 standoff viewpoint hold 仍可能把船带入不适合前视相机的几何；但这不是 3 个 range-hit 失败 pose 的主因。

5D-11 没有运行原始 update_found_mask，也没有触发 found_mask/all_found。
5D-11 只能声明“诊断审计通过”，不能声明 HoloOcean 真实搜索闭环成立。
```

当前阻塞点进一步收窄为：
```text
不是 mainline found_mask/all_found 接口。
不是 production adapter 接口。
不是推荐规则在静态几何下无法识别。
不是 5D-10 的三个 range-hit pose 几何不可识别。
不是 teammate false positive。

而是：完整 live planner run 中，target capture 与 calibration baseline/reference 的 RGB 成对帧在关键 range-hit tick 上没有产生应有的 sphere blob diff。
具体表现是 5D-10 source tick 5305/5306/5307 的 target live events 中 RangeFinder 命中，但 rgb_changed_pixels = 0、local_candidate_count = 0；同一 observer pose 静态重放则能 accepted。
```

下一步建议进入 Phase 5D-12：
```text
目标：在真实 planner live run 中保存关键 tick 的原始 target RGB frame、calibration baseline RGB frame、diff mask 和 RangeFinder beams，直接验证为何 5D-10 的 range-hit tick 产生 rgb_changed_pixels = 0。

优先方向：
1. 不改 baseline_GP core planner/runtime。
2. 不改 production adapter。
3. 不扩展动态目标。
4. 不扩展非 sphere-like 目标类别。
5. 不把 truth 接入 detection；truth 只能用于选择 audit/diagnostic 保存窗口和标注。
6. 在完整 live planner run 或短程复现实验中，保留 raw_captures_by_step_tick 中关键窗口，不再 strip 掉 RGB 原始帧。
7. 专门保存 5D-10 类似的 policy_step=16 / post_arrival_scan / RangeFinder hit tick 的 target RGB、baseline RGB、diff、white-neutral mask、overlay。
8. 检查 baseline_capture 选择逻辑：同 step/tick、earlier tick fallback、calibration run 与 target run 的 pose 是否一致。
9. 检查 HoloOcean RGB frame 是否存在传感器延迟、tick 错位、目标刚出现但 RGB frame 仍为旧帧等现象。
10. 审计仍要求 teammate-only false positives = []；最终闭合条件仍是 target live accepted candidate -> shared_found -> original update_found_mask -> found_mask -> all_found。
```

---

**当前接力指令：5D-11 诊断审计通过但真实闭环未闭合，下一步做 5D-12 live raw frame/baseline 同步诊断**

```text
你正在接手 F:\pythonprojects 中的 HoloOcean Phase 5C/5D 静态目标感知链工作。
请先阅读：F:\pythonprojects\readme\HoloOcean_Phase5C_静态目标感知链维护文档.md

重点阅读文档末尾的：
“2026-06-17 补充更新：Phase 5D-11 已执行，诊断审计通过但真实搜索闭环仍未闭合”
以及
“当前接力指令：5D-11 诊断审计通过但真实闭环未闭合，下一步做 5D-12 live raw frame/baseline 同步诊断”。

当前最新执行阶段是 Phase 5D-11，目录为：
baseline_GP/results/holoocean_bridge_v1/phase5d11_live_target_rgb_range_sync_diagnostic/

5D-11 已经证明：
1. 5D-11 是 diagnostic-only，audit.all_passed = true 不代表搜索闭环通过。
2. control_5d9_planner_front_center_30m 静态对照 accepted = true。
3. 5D-10 的 target_range_hit_failure_1/2/3 在原 live run 中分别是 RangeFinder hit 但 rgb_changed_pixels = 0、local_candidate_count = 0。
4. 同三组 observer pose 在 5D-11 静态重放中全部 accepted = true。
5. 因此这三组失败不是几何或推荐规则本身不可识别，而是 live planner run 中 RGB frame / calibration baseline reference / tick 对齐 / capture timing 的问题。
6. 近距背向/侧向 pose 在静态重放中仍失败，说明 standoff viewpoint 仍会产生不适合前视相机的采样姿态。
7. truth 没有触发 detection，只用于 audit/diagnostic 构造与标注。
8. baseline_GP 核心搜索算法和 runtime 文件未修改。

下一步执行 Phase 5D-12：
1. 保持目标为静态 SphereAgent。
2. 保持队友为 SurfaceVessel。
3. 不扩展到动态目标，不扩展到非 sphere-like blob 目标类别。
4. 不重写 baseline_GP 核心搜索算法。
5. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
6. 不把 truth 接入 detection。
7. 继续使用 production adapter：baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter。
8. 继续使用推荐规则：sphere_blob_local_range_scaled_any_hit。
9. 在真实 planner live run 或短程复现实验中保存关键 RangeFinder hit tick 的 target RGB / calibration baseline RGB / diff mask / white-neutral mask / overlay，不再只保存统计值。
10. 优先验证 5D-10 中 source tick 5305/5306/5307 类似场景为何 source rgb_changed_pixels = 0。
11. 检查 baseline_capture 选择逻辑和 tick 对齐：同 step/tick、earlier tick fallback、calibration run 与 target run pose 差异。
12. 继续验证 teammate-only false positives = []。
13. 所有 5D-12 产物放入独立目录，不覆盖 5D-11 结果。
```

---

**2026-06-18 暂停交接：Phase 5D-12 live raw-frame/baseline 同步诊断已执行，尚未完成 audit 收口**

本次暂停前已经执行了 Phase 5D-12，但还没有完成 5D-12 audit 脚本、正式审计报告和下一阶段最终接力指令。

5D-12 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d12_live_raw_frame_baseline_sync_diagnostic/
```

已新增并运行的脚本：
```text
scripts/live_raw_frame_baseline_sync_probe.py
```

已生成的主要产物：
```text
manifests/phase5d12_summary.json
manifests/phase5d12_raw_frame_sync_diagnostic.json
manifests/phase5d12_raw_frame_sync_diagnostic.csv
manifests/phase5d12_live_per_agent_detection_events.json
manifests/phase5d12_live_per_agent_detection_events.csv
manifests/phase5d12_live_tick_trace.json
manifests/phase5d12_live_tick_trace.csv
manifests/phase5d12_live_policy_trace.json
manifests/phase5d12_live_policy_trace.csv
manifests/phase5d12_live_candidate_fusion_trace.json
manifests/phase5d12_adapter_observe_trace.json
manifests/phase5d12_mainline_update_found_trace.json
reports/phase5d12_summary.md
visuals/phase5d12_step*_*.png
```

5D-12 summary 关键字段：
```text
phase_completed = false
phase_goal_completed = false
phase_status = planner_live_callback_integrated_but_live_detection_all_found_not_closed
diagnostic_name = phase5d12_raw_frame_baseline_sync_diagnostic
diagnostic_audit_only = true
raw_frame_sync_case_count = 11
raw_frame_sync_range_hit_case_count = 3
raw_frame_sync_source_zero_rgb_recomputed_positive_count = 0
raw_frame_sync_source_zero_rgb_recomputed_positive_ticks = []
target_live_detection_success = false
target_all_found_step = null
mainline_update_found_mask_called_count = 40
mainline_found_mask_updated_from_live_adapter = false
teammate_false_positive_steps = []
truth_flags_false = true
baseline_runtime_source_modified = false
search_decision_algorithm_modified = false
```

5D-12 的关键新发现：
```text
5D-12 直接保存并复算了真实 live planner run 中选中的 raw capture。
对 3 个关键 RangeFinder hit tick：

policy_step = 16, tick_in_policy_step = 240, tick_global = 5305, agent = sv0
  rangefinder_hit_beam_indices = [56]
  target_capture_present = true
  baseline_capture_present = true
  exact_baseline_capture_present = true
  target_rgb_present = false
  baseline_rgb_present = false
  target_vs_baseline_observer_distance_m = 0.000879
  target/baseline heading 基本一致
  rgb_changed_pixels_recomputed = 0

policy_step = 16, tick_in_policy_step = 241, tick_global = 5306, agent = sv0
  rangefinder_hit_beam_indices = [58]
  target_capture_present = true
  baseline_capture_present = true
  exact_baseline_capture_present = true
  target_rgb_present = false
  baseline_rgb_present = false
  target_vs_baseline_observer_distance_m = 0.000879
  target/baseline heading 基本一致
  rgb_changed_pixels_recomputed = 0

policy_step = 16, tick_in_policy_step = 242, tick_global = 5307, agent = sv0
  rangefinder_hit_beam_indices = [60]
  target_capture_present = true
  baseline_capture_present = true
  exact_baseline_capture_present = true
  target_rgb_present = false
  baseline_rgb_present = false
  target_vs_baseline_observer_distance_m = 0.000879
  target/baseline heading 基本一致
  rgb_changed_pixels_recomputed = 0
```

5D-12 的直白结论：
```text
5D-11 证明上述 3 个 range-hit pose 的几何和现有规则本身可以识别 SphereAgent。
5D-12 进一步证明，在完整 live planner run 中，上述 3 个关键 tick 的 target/baseline capture 容器都存在，且 target/baseline pose 高度对齐；但 FrontRGBCamera RGB frame 本身在 target 和 baseline 两侧都是缺失的。
因此这 3 个关键 tick 不能形成 RGB diff/local blob，不是因为 baseline pose 不对齐，也不是因为 update_found_mask、adapter、candidate fusion 或几何规则失效，而是因为 live capture provider 在这些 RangeFinder 命中 tick 没有拿到 FrontRGBCamera frame。

其它 high-diff 诊断行有 RGB frame 和 PNG 输出，但没有 RangeFinder hit，仍不能形成 sphere_blob_local_range_scaled_any_hit。
当前核心阻塞点收窄为：RangeFinder hit 与 FrontRGBCamera frame 输出不同步 / RGB sensor 在关键 tick 缺帧。
```

暂停时尚未完成的任务：
```text
1. 还没有为 5D-12 编写 live_raw_frame_baseline_sync_audit.py。
2. 还没有生成 phase5d12_raw_frame_sync_audit.json / audit_summary.md。
3. 还没有把 5D-12 写成完整“补充更新”段落，只写了本暂停交接段。
4. 还没有设计下一阶段 5D-13。
5. 还没有尝试修复 FrontRGBCamera 缺帧 / RGB 与 RangeFinder tick 同步问题。
6. 还没有重新运行闭环验证，因此 HoloOcean 真实搜索闭环仍不能宣布成立。
```

明天继续执行建议：
```text
第一步：补 5D-12 audit。
  - 检查 required paths。
  - 检查 phase_completed=false、diagnostic_audit_only=true。
  - 检查 3 个 range-hit case 的 target_capture_present / baseline_capture_present / exact_baseline_capture_present 全为 true。
  - 检查 3 个 range-hit case 的 target_rgb_present=false 且 baseline_rgb_present=false。
  - 检查 target_vs_baseline_observer_distance_m 约 0.000879，说明不是 baseline pose 错位。
  - 检查 teammate_false_positive_steps=[]。
  - 检查 truth flags false。
  - 检查 core runtime/planner 文件未修改。

第二步：把 5D-12 正式写入本文档。
  - 明确 5D-12 是 diagnostic-only。
  - 明确 5D-12 没有 all_found。
  - 明确阻塞点是 RangeFinder hit tick 缺 FrontRGBCamera frame。

第三步：设计 Phase 5D-13。
  - 目标不是改 found_mask/all_found，也不是改 adapter。
  - 目标是修 live capture provider 的 RGB/RF 同步：在每个 RangeFinder hit tick 附近增加 RGB frame wait/nearest-frame lookup/短窗口 RGB sampling。
  - 仍保持静态 SphereAgent、SurfaceVessel 队友、推荐规则 sphere_blob_local_range_scaled_any_hit、truth audit-only。
  - 5D-13 审计必须同时证明：target live accepted candidate -> shared_found -> original update_found_mask -> found_mask/all_found，以及 teammate-only false positives = []。

第四步：若 5D-13 只做同步修复实验，所有产物必须放入独立目录：
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/
```

当前冻结边界继续保持：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不扩展动态目标。
4. 不扩展非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
7. 不把 truth 接入 detection。
8. 继续使用 production adapter：baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter。
9. 继续使用推荐规则：sphere_blob_local_range_scaled_any_hit。
10. 继续要求 teammate-only false positives = []。
```

明天接手时优先读取：
```text
readme/HoloOcean_Phase5C_静态目标感知链维护文档.md
baseline_GP/results/holoocean_bridge_v1/phase5d12_live_raw_frame_baseline_sync_diagnostic/manifests/phase5d12_summary.json
baseline_GP/results/holoocean_bridge_v1/phase5d12_live_raw_frame_baseline_sync_diagnostic/manifests/phase5d12_raw_frame_sync_diagnostic.json
baseline_GP/results/holoocean_bridge_v1/phase5d12_live_raw_frame_baseline_sync_diagnostic/reports/phase5d12_summary.md
baseline_GP/results/holoocean_bridge_v1/phase5d12_live_raw_frame_baseline_sync_diagnostic/scripts/live_raw_frame_baseline_sync_probe.py
```

---

**2026-06-18 补充更新：Phase 5D-12 live raw-frame/baseline 同步诊断 audit 已完成，但真实搜索闭环仍未闭合**

Phase 5D-12 已完成正式 audit 收口。注意：这里的 `audit.all_passed = true` 只表示 raw-frame/baseline 同步诊断本身审计通过，不表示 HoloOcean 真实搜索闭环已经通过。

5D-12 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d12_live_raw_frame_baseline_sync_diagnostic/
```

5D-12 新增并已运行的 audit 脚本：
```text
scripts/live_raw_frame_baseline_sync_audit.py
```

5D-12 新增 audit 产物：
```text
manifests/phase5d12_raw_frame_sync_audit.json
reports/phase5d12_raw_frame_sync_audit_summary.md
```

5D-12 audit 关键结论：
```text
diagnostic_audit_only = true
audit.all_passed = true
phase_completed = false
phase_goal_completed = false
target_live_detection_success = false
target_all_found_step = null
mainline_update_found_mask_called_count = 40
mainline_found_mask_updated_from_live_adapter = false
teammate_false_positive_steps = []
truth_flags_false = true
core_runtime_and_search_algorithm_not_modified = true
```

5D-12 审计确认的 3 个关键 RangeFinder hit tick：
```text
policy_step = 16, tick_in_policy_step = 240, tick_global = 5305, agent = sv0, beams = [56]
policy_step = 16, tick_in_policy_step = 241, tick_global = 5306, agent = sv0, beams = [58]
policy_step = 16, tick_in_policy_step = 242, tick_global = 5307, agent = sv0, beams = [60]
```

这 3 个 tick 的共同特征：
```text
target_capture_present = true
baseline_capture_present = true
exact_baseline_capture_present = true
target_rgb_present = false
baseline_rgb_present = false
target_vs_baseline_observer_distance_m ≈ 0.000879335
rgb_changed_pixels_recomputed = 0
```

5D-12 的直接结论：
```text
1. 5D-11 已证明这 3 个 range-hit pose 在静态 replay 中可被现有规则识别。
2. 5D-12 进一步证明，完整 live planner run 中这些 tick 的 target/baseline capture 容器存在，且 baseline pose 与 target pose 高度对齐。
3. 失败不是 found_mask/all_found 接口问题。
4. 失败不是 production adapter 或 candidate fusion 问题。
5. 失败不是推荐规则在这些几何 pose 下不可识别。
6. 失败不是 teammate false positive。
7. 当前阻塞点是 live capture provider 在 RangeFinder 命中 tick 没有同步拿到 FrontRGBCamera frame。
8. 因为 RF 命中 tick 缺 RGB frame，所以无法形成 RGB diff/local sphere blob，也就无法形成 accepted candidate -> shared_found -> original update_found_mask -> found_mask/all_found。
```

5D-12 保持的边界：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不重写 baseline_GP 核心搜索算法。
6. 不修改 marine_knownmap_runtime.py / marine_knownmap_runtime_2usv.py。
7. 不把 truth 接入 detection。
8. 继续使用 production adapter：baseline_GP.holoocean_bridge.mainline_perception_adapter.ReusableMainlinePerceptionAdapter。
9. 继续使用推荐规则：sphere_blob_local_range_scaled_any_hit。
10. 继续要求 teammate-only false positives = []。
```

**当前接力指令：5D-12 诊断 audit 已通过，下一步进入 Phase 5D-13 live RGB/RF 同步修复**

下一步不要回到 5D-8/5D-9/5D-10 重跑同类失败实验；这些阶段已经证明 mainline planner callback、live movement/capture、production adapter、原始 update_found_mask 调用链已经接通，但 perception 没有在 live RF 命中 tick 产出 accepted candidate。

Phase 5D-13 建议目录：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/
```

5D-13 的目标：
```text
修复或绕过 live capture provider 中 RangeFinder hit tick 与 FrontRGBCamera frame 不同步/缺帧的问题，让真实 live planner run 中的 RF 命中 tick 能拿到可用于 sphere_blob_local_range_scaled_any_hit 的 RGB target/baseline 成对帧。
```

5D-13 优先候选方案：
```text
1. 在 RangeFinder hit tick 附近增加短窗口 RGB sampling。
2. 对 RF hit tick 使用 nearest valid RGB frame lookup。
3. 在 RF hit 后等待少量 HoloOcean ticks，直到 FrontRGBCamera frame 出现，再组装 detection event。
4. 记录 RF tick 与 RGB tick 的偏移量，audit 中必须保存 offset 分布，不能只保存最终 accepted 结果。
```

5D-13 不应做的事：
```text
1. 不修改 baseline_GP 核心 planner/search/runtime。
2. 不绕过 production adapter 直接写 found_mask。
3. 不用 truth 生成 detection event。
4. 不降低 teammate negative 要求。
5. 不把非 RF 命中的高 RGB diff blob 当作 target accepted candidate。
6. 不进入动态目标或通用目标类别。
```

5D-13 最终 audit 必须证明：
```text
1. live capture provider 在 RF hit tick 或短窗口内拿到 target/baseline RGB 成对帧。
2. sphere_blob_local_range_scaled_any_hit 在 live run 中产出至少 1 个 target accepted candidate。
3. accepted candidate 经 production adapter 进入 shared_found。
4. shared_found 驱动原始 baseline_GP update_found_mask。
5. found_mask 更新并触发 all_found。
6. target_all_found_step 不为 null。
7. teammate-only false positives = []。
8. truth_used_for_detection = false。
9. baseline_GP 核心 planner/search/runtime 文件仍未修改。
10. 所有 5D-13 产物放入独立目录，不覆盖 5D-12。
```

---

**2026-06-18 补充更新：Phase 5D-13 live RGB/RF 同步修复已完成，真实 planner callback 静态目标搜索闭环通过审计**

Phase 5D-13 已完成 HoloOcean live RGB/RF 同步修复实验，并通过正式 audit。与 5D-12 不同，5D-13 的 `audit.all_passed = true` 表示真实 planner callback + live HoloOcean movement/capture + production adapter + 原始 `update_found_mask/all_found` 静态目标闭环已经通过。

5D-13 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/
```

5D-13 新增脚本：
```text
scripts/live_rgb_range_sync_fix_probe.py
scripts/live_rgb_range_sync_fix_audit.py
```

5D-13 关键产物：
```text
manifests/phase5d13_summary.json
manifests/phase5d13_audit.json
manifests/phase5d13_live_per_agent_detection_events.json
manifests/phase5d13_live_candidate_fusion_trace.json
manifests/phase5d13_adapter_observe_trace.json
manifests/phase5d13_mainline_update_found_trace.json
manifests/phase5d13_raw_frame_sync_diagnostic.json
reports/phase5d13_summary.md
reports/phase5d13_audit_summary.md
```

5D-13 audit 关键结论：
```text
audit.all_passed = true
phase_completed = true
phase_goal_completed = true
phase_status = live_planner_callback_standoff_viewpoint_all_found_closed
target_success_all_found = true
target_all_found_step = 16
target_live_detection_success = true
target_first_shared_found_step = 16
mainline_found_mask_updated_from_live_adapter = true
mainline_all_found_driven_by_live_adapter = true
teammate_false_positive_steps = []
truth_flags_false = true
core_runtime_and_search_algorithm_not_modified = true
```

5D-13 的同步修复方式：
```text
rgb_range_sync_fix_enabled = true
rgb_range_sync_strategy = short_window_detector_scored_nearest_pair
rgb_sync_window_ticks = 8
rgb_sync_max_pose_drift_m = 4.0
```

修复原则：
```text
1. RangeFinder hit tick 仍提供 range 与 observer pose。
2. 若 RF hit tick 缺 FrontRGBCamera frame，则只在同一 policy step 的短窗口内查找 target/baseline 成对 RGB frame。
3. RGB 成对帧选择只使用 live RGB、baseline RGB 与 RF beams，不使用 truth。
4. truth 仍只用于 audit 标注，不参与 detection。
5. 不改 baseline_GP planner/search/runtime。
6. 不绕过 production adapter，不直接写 found_mask。
```

5D-13 闭环发生在 policy step 16。3 条 target accepted candidate 均来自 RGB/RF 同步补帧：
```text
policy_step = 16, tick_in_policy_step = 240, agent = sv0
  RF beams = [56]
  target_rgb_tick = 245, baseline_rgb_tick = 245
  target_offset = +5 ticks, baseline_offset = +5 ticks
  matched_range_m = 23.052574
  rgb_changed_pixels = 81

policy_step = 16, tick_in_policy_step = 241, agent = sv0
  RF beams = [58]
  target_rgb_tick = 245, baseline_rgb_tick = 245
  target_offset = +4 ticks, baseline_offset = +4 ticks
  matched_range_m = 22.930021
  rgb_changed_pixels = 81

policy_step = 16, tick_in_policy_step = 242, agent = sv0
  RF beams = [60]
  target_rgb_tick = 245, baseline_rgb_tick = 245
  target_offset = +3 ticks, baseline_offset = +3 ticks
  matched_range_m = 22.860334
  rgb_changed_pixels = 81
```

5D-13 candidate fusion 结果：
```text
policy_step = 16
accepted_candidate_count = 3
fused_candidate_count = 1
shared_found_this_step = true
new_found_this_step = true
fused_world_position = [-270.1713759335762, 221.0223185369824, 0.0]
target_position_error_m = 0.1728231110186046
```

5D-13 mainline update_found_mask 结果：
```text
mainline_step = 16
source_shared_found = true
source_accepted_candidate_count = 3
new_found_indices = [0]
found_mask_after = [true]
all_found_after_update = true
target_all_found_step = 16
```

teammate-only negative 仍通过：
```text
teammate_false_positive_steps = []
teammate_only_false_positive_count = 0
teammate_events_accepted_count = 0
teammate_accepted_candidate_from_rgb_sync_count = 0
```

本阶段保持的边界：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 观察者仍为 sv0 / sv1 两艘 SurfaceVessel。
4. 检测规则仍为 sphere_blob_local_range_scaled_any_hit。
5. 不进入动态目标跟踪。
6. 不扩展到非 sphere-like blob 目标类别。
7. 不引入语义检测器、sonar 或通用视觉检测器。
8. 不修改 baseline_GP 核心 planner/search/runtime。
9. 不把 truth 接入 detection。
10. 5D-13 是 open_water 单静态 SphereAgent 的真实 planner callback 闭环，不代表 obstacle/grid 对齐、多目标 N=3、动态目标或通用目标类别已经完成。
```

**当前接力指令：5D-13 已完成并通过审计，静态 SphereAgent HoloOcean 真实搜索闭环核心迁移已闭合**

如果后续继续做迁移扩展，建议按以下顺序进入独立阶段：
```text
1. Phase 5E-1：把 5D-13 的 RGB/RF 短窗口同步逻辑从实验脚本整理为正式 bridge/provider module，并补最小单元/回放测试。
2. Phase 5E-2：障碍物场景 + 2D occupancy grid 几何对齐，先做 open_water 以外的 obstacle_field / peninsula_passage 对齐审计。
3. Phase 5E-3：多目标 N=3 静态 SphereAgent，验证 candidate fusion 去重和 all_found 多目标终止。
4. Phase 5E-4：再考虑动态目标跟踪。
5. Phase 5E-5：再考虑非 sphere-like / 通用目标类别或真实视觉检测器。
```

若只要求“静态 SphereAgent + SurfaceVessel 队友 + baseline_GP 原始 planner callback + HoloOcean live movement/capture + production adapter + 原始 found_mask/all_found”，则 5D-13 已经给出通过审计的闭环证据。

---

**2026-06-18 补充更新：运行搜索任务时的实时双艇观察窗口已接入**

本窗口内新增的工作不是新的搜索闭环阶段，也没有改变 5D-13 的审计结论。它是在 5D-13 已完成的真实 planner callback 搜索脚本上，增加一个可选实时显示窗口，便于运行任务时直接观察两艘 SurfaceVessel 的搜索过程。

修改文件：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/scripts/live_rgb_range_sync_fix_probe.py
```

新增能力：
```text
1. 新增 LiveSearchViewer。
2. 使用 OpenCV 弹出独立窗口，显示 top-down 双艇搜索过程。
3. 显示 sv0 / sv1 当前格点位置、运动轨迹、目标位置、found_mask、RF hit、detected 状态。
4. 只在 target 搜索段显示；calibration/reference run 和 teammate-only negative run 不弹窗。
5. 按 q 只关闭观察窗口，不中断搜索任务本身。
6. 默认不启用，必须显式加 --display-live。
7. 不保存帧，不保存录像。
8. --display-live 模式下同时默认跳过 5D-13 原有的诊断 PNG preview 保存。
9. JSON/CSV audit 产物仍按 5D-13 原脚本逻辑生成，因为该脚本仍是审计型运行入口。
```

新增 CLI 参数：
```text
--display-live
--display-fps
--display-every-ticks
--no-save-visuals
```

实时观察运行命令：
```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/scripts/live_rgb_range_sync_fix_probe.py --mode live --display-live
```

如只想显式表达“不保存诊断 PNG preview”，也可以运行：
```powershell
C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/scripts/live_rgb_range_sync_fix_probe.py --mode live --display-live --no-save-visuals
```

本窗口已完成的验证：
```text
1. py_compile 通过：
   C:\Users\32022\.conda\envs\holo\python.exe -m py_compile baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/scripts/live_rgb_range_sync_fix_probe.py

2. CLI help 通过：
   C:\Users\32022\.conda\envs\holo\python.exe baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/scripts/live_rgb_range_sync_fix_probe.py --help
```

本窗口没有执行完整 HoloOcean live run；原因是本次需求是为后续运行提供实时观察入口，不是重新审计 5D-13。下一窗口如果要确认实际窗口效果，应在具备 HoloOcean/UE 图形环境时运行上面的 `--display-live` 命令。

仍需保持的边界：
```text
1. 不修改 baseline_GP 核心 planner/search/runtime。
2. 不改变 5D-13 的 detection rule：sphere_blob_local_range_scaled_any_hit。
3. 不把 truth 接入 detection。
4. 不扩展到动态目标。
5. 不扩展到非 sphere-like blob 目标类别。
6. 不把观察窗口结果作为 audit 判据；它只是运行时可视化辅助。
7. 不保存实时窗口帧或录像。
```

**当前接力指令：5D-13 闭环审计已完成，实时双艇观察窗口已接入；下一窗口等待用户给出新的改进方向**

下一窗口接手时优先读取：
```text
readme/HoloOcean_Phase5C_静态目标感知链维护文档.md
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/scripts/live_rgb_range_sync_fix_probe.py
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/manifests/phase5d13_audit.json
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/manifests/phase5d13_summary.json
baseline_GP/results/holoocean_bridge_v1/phase5d13_live_rgb_range_sync_fix/reports/phase5d13_audit_summary.md
```

---

**2026-06-18 补充更新：Phase 5D-14 continuous rolling RGB/RF sync 已执行，但无停顿连续运动搜索未闭合**

本阶段回应运行观察中的问题：5D-13 虽然闭合真实搜索链，但依赖 post-arrival stabilization / standoff hold / post-arrival scan，表现为 USV 走一段后停下并左右摆头。5D-14 的目标是验证只靠连续运动中的 rolling RGB/RF 异步时间窗口融合，能否取消停船扫描。

5D-14 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d14_continuous_rolling_rgb_rf_sync/
```

5D-14 新增脚本：
```text
scripts/continuous_rolling_rgb_rf_sync_probe.py
scripts/continuous_rolling_rgb_rf_sync_audit.py
```

5D-14 关键配置：
```text
post_arrival_stabilization_ticks = 0
standoff_viewpoint_hold_ticks = 0
post_arrival_scan_ticks = 0
post_scan_recenter_ticks = 0
rgb_range_sync_strategy = continuous_rolling_detector_scored_nearest_pair
rgb_sync_window_ticks = 8
```

5D-14 audit 结果：
```text
audit.all_passed = false
phase_completed = false
phase_goal_completed = false
phase_status = planner_live_callback_integrated_but_live_detection_all_found_not_closed
no_stop_scan_tick_audit_passed = true
post_arrival_stabilization_tick_count = 0
standoff_viewpoint_hold_tick_count = 0
scan_tick_count = 0
post_scan_recenter_tick_count = 0
target_success_all_found = false
target_all_found_step = null
target_accepted_candidate_from_rgb_sync_count = 0
mainline_found_mask_updated_from_live_adapter = false
mainline_all_found_driven_by_live_adapter = false
teammate_false_positive_steps = []
truth_flags_false = true
```

5D-14 的关键定位：
```text
target run:
  event_count = 3396
  rangefinder hit events = 0
  local RGB candidate events = 97
  accepted candidate events = 0

teammate-only run:
  rangefinder hit events = 224
  raw_found events = 17
  accepted candidate events = 0
  teammate_false_positive_steps = []
```

5D-14 的直白结论：
```text
连续 rolling RGB/RF sync 本身可以消除同 tick RGB/RF 缺帧假设，但在当前单前向相机 + 前向 fan RF 配置下，USV 无停顿连续运动时 target run 没有获得 RangeFinder hit。
因此 5D-14 未闭合的主因不是 adapter、found_mask 或 rolling sync 代码，而是传感器覆盖方向不足：目标在连续 planner 路径中未稳定落入前向 RF/RGB 覆盖。
由于 5D-14 未完成搜索任务，按用户目标继续进入 5D-15。
```

---

**2026-06-18 补充更新：Phase 5D-15 multicamera RGB/RF coverage no-stop-scan 已完成，真实搜索闭环通过审计**

Phase 5D-15 在保持无停顿、无摆头、无 post-arrival scan 的前提下，通过多方向 RGB/RF 固定传感器覆盖完成真实 planner callback 静态目标搜索闭环。与 5D-13 不同，5D-15 不再依赖 USV 停下后左右扫描。

5D-15 目录为：
```text
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/
```

5D-15 新增脚本：
```text
scripts/multicamera_coverage_no_stop_scan_probe.py
scripts/multicamera_coverage_no_stop_scan_audit.py
```

5D-15 关键产物：
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

5D-15 传感器覆盖方案：
```text
camera_channel_count = 4
camera_channels:
  front: FrontRGBCamera, yaw = 0 deg
  left:  LeftRGBCamera,  yaw = +90 deg
  right: RightRGBCamera, yaw = -90 deg
  rear:  RearRGBCamera,  yaw = 180 deg

每个 camera channel 配一组 61-beam local fan RangeFinder：
  local yaw = +30 deg 到 -30 deg，1 deg 间隔

bridge_fan_rangefinder_sensor_count = 244
```

检测原则：
```text
1. USV 仍按 baseline_GP planner 连续运动。
2. 不执行 post-arrival stabilization。
3. 不执行 standoff viewpoint hold。
4. 不执行 post-arrival scan。
5. 不执行 recenter。
6. 每个 camera channel 独立形成 RGB blob + 同 channel RF hit 证据。
7. RF 不能单独触发 found。
8. truth 不参与 detection。
9. accepted candidate 仍经 production adapter 和原始 update_found_mask。
```

5D-15 audit 关键结论：
```text
audit.all_passed = true
phase_completed = true
phase_goal_completed = true
phase_status = live_planner_callback_continuous_rolling_no_stop_scan_all_found_closed
target_success_all_found = true
target_all_found_step = 20
target_live_detection_success = true
target_first_shared_found_step = 20
target_accepted_candidate_from_rgb_sync_count = 32
target_accepted_candidate_from_rgb_sync_steps = [20]
target_accepted_candidate_from_transit = true
mainline_found_mask_updated_from_live_adapter = true
mainline_all_found_driven_by_live_adapter = true
teammate_false_positive_steps = []
teammate_only_false_positive_count = 0
teammate_events_accepted_count = 0
truth_flags_false = true
```

5D-15 no-stop-scan 审计字段：
```text
no_stop_scan_tick_audit_passed = true
post_arrival_stabilization_tick_count = 0
standoff_viewpoint_hold_tick_count = 0
scan_tick_count = 0
post_scan_recenter_tick_count = 0
target_accepted_candidate_from_scan = false
target_accepted_candidate_from_standoff_viewpoint_hold = false
```

5D-15 目标闭环：
```text
policy_step = 20
accepted_candidate_count = 32
duplicate_observation_fused = true
shared_found_this_step = true
original update_found_mask called
found_mask_after = [true]
all_found_after_update = true
target_all_found_step = 20
```

5D-15 的直白结论：
```text
在 open_water 单静态 SphereAgent / 双 SurfaceVessel / baseline_GP 原始 planner callback / HoloOcean live movement-capture / production adapter / 原始 update_found_mask 边界内，已经实现不停车、不左右摆头的真实搜索闭环。
5D-14 证明 rolling RGB/RF sync 单独不足以解决连续运动中的前向覆盖问题。
5D-15 通过多方向固定 RGB/RF 覆盖解决了该问题。
因此当前不需要继续做新的 5D-15 之后补救阶段。
```

仍需保持的边界：
```text
1. 目标仍为静态 SphereAgent。
2. 队友仍为 SurfaceVessel。
3. 不进入动态目标跟踪。
4. 不扩展到非 sphere-like blob 目标类别。
5. 不引入 semantic、sonar 或通用视觉检测器。
6. 不修改 baseline_GP 核心 planner/search/runtime。
7. 不把 truth 接入 detection。
8. 5D-15 是 open_water 单静态 SphereAgent 的 no-stop-scan 闭环，不代表 obstacle/grid 对齐、多目标 N=3、动态目标或通用类别已完成。
```

当前接手优先读取：
```text
readme/HoloOcean_Phase5C_静态目标感知链维护文档.md
baseline_GP/results/holoocean_bridge_v1/phase5d14_continuous_rolling_rgb_rf_sync/manifests/phase5d14_audit.json
baseline_GP/results/holoocean_bridge_v1/phase5d14_continuous_rolling_rgb_rf_sync/manifests/phase5d14_summary.json
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/scripts/multicamera_coverage_no_stop_scan_probe.py
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/manifests/phase5d15_audit.json
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/manifests/phase5d15_summary.json
baseline_GP/results/holoocean_bridge_v1/phase5d15_multicamera_coverage_no_stop_scan/reports/phase5d15_audit_summary.md
```
