# HoloOcean Phase 5C 静态目标感知链维护文档

本文档用于交接当前窗口中 HoloOcean 静态目标迁移工作的阶段状态。它只记录已经完成和已经确认的事实，不替代后续 Phase spec。

维护日期：2026-06-17

**当前阶段**
当前迁移工作已经执行到 `Phase 5D-3`。5D-3 已把 5D-2 的候选共享/融合接入连续多步 HoloOcean 搜索闭环，并在预设连续轨迹下验证了 `found_mask / all_found` 更新链。当前目标仍限定为静态 `SphereAgent`，队友为 `SurfaceVessel`，最大扇形全区域可靠识别距离维持 `35 m`。

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
```

目前仍不进入动态目标阶段。`Phase 5D` 的当前含义已经调整为“多艘 `SurfaceVessel` 协同搜索异类静态目标”，不是旧的动态目标路线。5D-3 已把 5D-2 的 per-agent detection event / candidate fusion 接入连续多步搜索闭环；下一步应继续完善更贴近 `baseline_GP` 原始搜索策略的闭环接入与路径规划耦合，而不是扩大目标类别或进入动态目标跟踪。

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
