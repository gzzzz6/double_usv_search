可以按“先桥接、再验证、最后提高仿真真实度”的路线迁移。不要一开始就把现有算法重写成 HoloOcean 原生逻辑，否则容易把论文主线搞乱。

**总体原则**
保留 `baseline_GP` 的搜索决策主链：

`GP clue / intensity / recency / 综合信息价值场 -> anchor -> simple_ring_v1 viewpoint -> safe-nav A* segment_path -> commit / replan -> two-USV coordination`

HoloOcean 只先承担：

`连续仿真环境 + USV 运动执行 + 可视化 + 后续传感器 realism`

官方文档中，HoloOcean 支持用 `holoocean.make()` 创建场景，单智能体可用 `step()`，多智能体通常采用多次 `act()` 后统一 `tick()` 的方式推进；`SurfaceVessel` 支持 PD 位置控制和自定义动力学控制，因此第一阶段建议先用 PD 位置控制，不直接上复杂动力学。具体 API 细节以本地安装版本和 v2.2.x 官方文档为准，尤其是 `env.act()` 的参数顺序应在本地 smoke run 中确认，并在工程中通过统一封装函数适配。参考：HoloOcean Environments 文档、Control Schemes 文档、SurfaceVessel 文档。  
来源：  
https://byu-holoocean.github.io/holoocean-docs/v2.0.1/usage/environments.html  
https://byu-holoocean.github.io/holoocean-docs/v2.2.1/agents/docs/control-schemes.html  
https://byu-holoocean.github.io/holoocean-docs/UE4.27_archival_develop/agents/surface-vessel-agent.html

**阶段 0：冻结当前主线**
目标：先把当前 Python 栅格仿真主线固定为可对照基准。

保留配置：

- `viewpoint_generation_mode="simple_ring_v1"`
- `path_safety_mode="soft_clearance_astar_v1"`
- `team_path_avoidance_mode="reservation_v1"`
- `anomaly_tail_quantile=0.90`
- `anomaly_weight_lambda=1.25`
- single / two-USV 的现有实验结果不重算、不覆盖

验收标准：

- 当前 `simple_ring_v1` 数据、论文表格、summary 文件保持不变。
- 后续 HoloOcean 结果单独放新目录，例如 `results/holoocean_bridge_v1/`。

**阶段 1：HoloOcean 最小可运行验证**
目标：不接入算法，只确认 HoloOcean 能启动 USV 并执行 waypoint。

做法：

- 创建一个最小 `SurfaceVessel` scenario。
- 使用 `control_scheme=1`，即 PD 位置控制。
- 给 USV 发送 `[x, y]` 目标点。
- 单艇先用 `env.step(command)`。
- 双艇以后通过统一封装函数 `send_action(agent_name, command)` 调用 HoloOcean 的 `env.act()`，再使用 `env.tick()` 同步推进。`send_action` 内部负责适配本地 HoloOcean 版本中 `env.act()` 的参数顺序。
- scenario 中必须加入可读取 USV 位姿的传感器。第一阶段优先使用真实位姿类传感器，暂不引入传感器噪声。

验收标准：

- 单艇能从起点移动到若干指定位置。
- 能读取 USV 当前位姿。
- 能保存一段轨迹图或日志。

**阶段 2：建立坐标桥接层**
目标：让现有栅格坐标能映射到 HoloOcean 世界坐标。

建议新增模块：

```text
baseline_GP/holoocean_bridge/
    coordinate_adapter.py
    scenario_builder.py
    execution_backend.py
    observation_adapter.py
```

核心映射：

```text
grid cell: (row, col)
HoloOcean: [x, y, z]
```

建议先定义：

```text
x = col * cell_size_m
y = -row * cell_size_m
z = water_surface_z
```

也就是说：

- 栅格列数对应 HoloOcean 的 x 方向；
- 栅格行数对应 HoloOcean 的负 y 方向；
- `cell_size_m` 初始可设为 `1.0` 或 `2.0`。
- `water_surface_z` 初始可设为 `0`，但需要通过阶段 1 的 smoke run 校正。如果具体 HoloOcean 场景的水面高度不是 0，则以场景中 `SurfaceVessel` 稳定漂浮时的高度为准。

验收标准：

- `(row, col)` 到 `[x, y]` 可双向转换。
- 起点 `((25, 2), (35, 2))` 能正确映射到 HoloOcean 两艘艇初始位置。
- 轨迹从 HoloOcean 回投到栅格后，与原算法期望路径大致一致。
- 设置连续运动到栅格目标的到达阈值，例如 `arrival_radius_m = 0.5 * cell_size_m`。当 USV 进入该半径时，认为已经到达当前目标栅格。
- 设置 `max_ticks_per_cell`，避免 PD 控制无法精确到达目标点时执行过程卡死。

**阶段 3：单艇算法闭环接入**
目标：让现有单艇规划器驱动 HoloOcean 中的 USV。

执行逻辑：

1. 从 HoloOcean 获取当前 USV 位姿。
2. 转回栅格位置。
3. 调用现有 single-USV known-map runtime 中 `policy="marine_knownmap_path_v2_infosampled"` 的一步规划接口，或封装 `plan_next_step(...)` 适配层。
4. 得到 `committed_segment` 的下一格。
5. 把下一格转换为 HoloOcean `[x, y]` waypoint。
6. 用 PD 控制让 USV 朝该点运动。
7. 当 USV 进入 `arrival_radius_m`，或当前目标格执行超过 `max_ticks_per_cell` 后，进入下一步规划/执行。

注意：这一阶段不要改 GP、intensity、recency、search_info、safe-nav、评分公式。

验收标准：

- 单艇能在 HoloOcean 中按现有路径规划结果移动。
- `segment_path`、`committed_segment`、`replan_reason` 等 trace 字段仍能记录。
- 同一个 seed 下，HoloOcean 回投轨迹与原栅格仿真趋势一致。
- 如果 HoloOcean 连续执行导致 USV 偏离栅格中心，应由坐标桥接层负责回投到最近自由栅格，不能直接修改搜索评分或候选路径生成逻辑。

**阶段 4：known static map 对齐**
目标：解决“论文地图”和“HoloOcean 世界”的对应关系。

短期方案：

- 仍然使用项目中的 known static occupancy grid 作为决策地图。
- HoloOcean 只是承载 USV 连续运动和可视化。
- 不要求 HoloOcean 场景几何与 `open_water / harbor_cove / peninsula_passage` 完全一致。

中期方案：

- 在 HoloOcean 中选择接近的世界，例如 OpenWater 或 harbor 类场景。
- 将障碍物语义仍以项目地图为准。
- 如果 HoloOcean 物理碰撞与项目地图不一致，先以项目地图的 safe-nav 为准。

长期方案：

- 自定义 Unreal / HoloOcean 场景，使 `harbor_cove`、`peninsula_passage` 等地图有真实几何对应。

验收标准：

- 论文主线实验仍基于原 known static map。
- HoloOcean 迁移实验不混淆“算法地图”和“仿真渲染场景”。

**阶段 5：双艇 coordinated 接入**
目标：让双艇协同搜索在 HoloOcean 中跑通。

保留现有双艇逻辑：

- shared team state
- soft responsibility prior 的 per-USV ranking bias
- sequential allocation-lite
- residual_map
- overlap penalty
- same-viewpoint penalty
- `reservation_v1`

执行逻辑：

1. 每一帧读取两艘艇的 HoloOcean 位姿。
2. 转为两个栅格位置。
3. 调用现有双艇 runtime。
4. 得到两艘艇各自下一步目标格。
5. 转成两个 HoloOcean waypoint。
6. 分别通过 `send_action("usv0", cmd0)`、`send_action("usv1", cmd1)` 发送控制指令。该封装函数内部适配 `env.act()` 的参数顺序。
7. `env.tick()` 同步推进。

验收标准：

- 双艇能同时移动。
- 不改变 coordinated / independent 的算法定义。
- `reservation_v1` 仍在算法层起作用。
- trace 中能看到两艇各自路径、visible cells、overlap 等字段。

**阶段 6：目标、线索和观测机制迁移**
目标：逐步把“目标和观测”从纯 Python 逻辑扩展到 HoloOcean 仿真语义。

建议分三步：

第一步：目标仍由 Python 管理。  
HoloOcean 只负责 USV 运动，目标位置仍是栅格坐标。

第二步：目标可视化到 HoloOcean。  
把目标映射成 HoloOcean 中的简单 actor 或 marker，但探测逻辑仍按项目传感器半径判断。

第三步：引入 HoloOcean 传感器。  
如果以后需要声呐、相机、噪声观测，再把 clue observation 与 HoloOcean sensor output 绑定。

验收标准：

- 第一版 HoloOcean 不改变论文实验定义。
- 后续 sensor realism 作为扩展实验，不覆盖当前主线结论。

**阶段 7：实验与论文口径**
目标：明确 HoloOcean 结果在论文中的位置。

建议论文中这样定位：

- 当前第 3-6 章主线仍是 known static map 下的信息驱动搜索算法。
- HoloOcean 可作为“高保真仿真验证平台扩展”。
- 不把 HoloOcean 结果与原栅格仿真结果直接混成同一组主实验。
- 可新增一节：“HoloOcean 仿真迁移验证”或放入展望。

验收标准：

- 不破坏已有 `6.2 / 6.3 / 6.4` 数据口径。
- HoloOcean 只验证算法可迁移性、运动执行合理性和可视化效果。

**推荐迁移顺序**
1. 先跑通 HoloOcean 单艇 waypoint 控制。
2. 再做坐标桥接。
3. 再接单艇主线。
4. 再接双艇 coordinated。
5. 最后再考虑真实传感器、真实障碍物和自定义场景。

关键判断：HoloOcean 不是替代当前算法，而是给当前算法加一个更真实的执行外壳。这样风险最小，也最符合你现在的论文主线。
