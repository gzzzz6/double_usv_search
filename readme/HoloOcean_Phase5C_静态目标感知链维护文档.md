# HoloOcean Phase 5C 静态目标感知链维护文档

本文档用于交接当前窗口中 HoloOcean 静态目标迁移工作的阶段状态。它只记录已经完成和已经确认的事实，不替代后续 Phase spec。

维护日期：2026-06-10

**当前阶段**
当前迁移工作已经完成到 `Phase 5C-4A-1`。

主线状态可以概括为：

```text
5C-1：双艇静态目标 runtime-only 多步闭环通过
5C-2：双艇静态目标 HoloOcean 4-step 短程物理闭环通过
5C-3：双艇静态目标 HoloOcean all_found 多步闭环通过
5C-4A-0：SemanticSegmentationCamera 本地可输出探针通过
5C-4A-1：Semantic/RGB/RangeFinder target-distractor 感知探针通过
```

目前没有进入动态目标阶段。`Phase 5D` 暂缓，当前优先完善静态目标的 HoloOcean 感知链和场景真实性。

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

