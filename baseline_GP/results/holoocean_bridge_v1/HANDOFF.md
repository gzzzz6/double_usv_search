# HoloOcean Migration — 高保真迁移文档 v3.0
# 更新于：2026-05-30

---

## 1. 核心上下文 (The Core Context)

* **项目定义：**
  广州大学本科毕业设计——将 `baseline_GP` 多 USV 协同信息驱动搜索算法（已发表主线实验）迁移至 HoloOcean v2.2.2 高保真仿真器作为"执行外壳"，保证算法层完全不变，验证算法在连续物理仿真环境中的可迁移性。毕业论文主文件：`信息科学与工程学院_320220938891_郭一泽.docx`。

* **当前进度（Phase 4C-found 已完成）：**

  | 阶段 | 内容 | 状态 |
  |------|------|------|
  | Phase 0 | 算法主线冻结审计 | ✅ 完成 |
  | Phase 1B | SurfaceVessel PD smoke | ✅ 完成 |
  | Phase 2 / 2B / 2C | 坐标桥接层 + OpenWater 5m 场景地图 | ✅ 完成 |
  | Phase 3A | 单艇算法步进接入 | ✅ 完成 |
  | Phase 3C-1 | 单艇 + 动态目标搜索（foundrun / catchable） | ✅ 完成 |
  | Phase 3D-0 | control_scheme=0 fast controller smoke（坐标修正版） | ✅ 完成 |
  | Phase 3D-1 | fastsv：动态目标搜索 fast controller 接入，step 63 发现目标 | ✅ 完成 |
  | Phase 4A | 10m OpenWater 桥接层同步静态审计 | ✅ 完成 |
  | Phase 4B | 10m fast controller waypoint smoke | ✅ 完成 |
  | Phase 4C | 10m 单艇静态目标搜索闭环（120 步，未发现目标） | ✅ 完成 |
  | Phase 4C-fix | 审计脚本条件分支修正 + 坐标报告纠错 | ✅ 完成 |
  | Phase 4C-found | 10m 单艇静态目标发现 E2E 闭环（step 51 发现目标） | ✅ 完成 |
  | **Phase 5** | **双 USV coordinated 协同接入** | 🔜 **待执行** |

* **关键约束（硬边界）：**
  - **绝对禁止修改**：`core_search_policy.py`, `marine_knownmap_runtime.py`, `marine_knownmap_runtime_2usv.py`, `core_targets.py`, `core_intensity.py`, `core_safe_nav.py`, `core_execution.py`
  - **禁止引入任何 sonar**（ImagingSonar / SidescanSonar / ProfilingSonar / SinglebeamSonar）
  - **禁止引入 camera 传感器**
  - **禁止修改**：`my_report.docx`, `holo1.py`, `paper_simple_ring_mainline_20260505/*`, `readme/HoloOcean_Plan.md`
  - **禁止覆盖旧阶段结果**（phase0 ~ phase4c 目录均为只读对照）
  - conda 环境：`holo`，Python 路径：`C:\Users\32022\.conda\envs\holo\python.exe`
  - HoloOcean world（单艇迁移后用）：**`OpenWater`**，package：**`Ocean`**
  - 不运行 baseline_GP 原始实验
  - 用户母语中文，偏好代码证据先行

---

## 2. CEO 认知档案 (User Profile Update)

* **偏好：**
  - 中文沟通，但代码/变量名/日志全部保留英文
  - **代码验证优先于口头承诺**——"先跑通再说"
  - 厌恶过度解释和泛泛之谈，要求引用具体文件路径:行号作为证据
  - 接受务实的技术妥协（如 max_ticks 从 500 → 2000，承认 PD 控制器物理限制）
  - 关注"为什么这样做"多于"做了什么"——决策逻辑要有记录
  - 对已确认结论（如"fast controller 已验证"）不需要再二次确认，直接推进
  - 审计通过的结论要具体：列出 checkpoints 数量、audit JSON 路径、all_passed 状态

* **雷区：**
  - 不要在没有代码证据的情况下断言"没问题"
  - 不要修改已冻结的 baseline_GP 算法文件
  - 不要擅自运行 baseline_GP 原始实验
  - 不要泛泛解释概念——用代码引用说话
  - 不要替用户下判断结论、不要做价值升华收尾
  - 不要使用引导式/安抚式语言（"我接住你"之类）

---

## 3. 关键知识库 (The Knowledge Base)

### 3.1 已确定的决策

1. **HoloOcean world 选择**：从旧的 `SimpleUnderwater` 迁移到 **`OpenWater`**（package：`Ocean`）。
2. **控制方案**：SurfaceVessel 使用 **`control_scheme=0`**（双螺旋桨直接力命令），已比 scheme=1 快 2.7~7.5x。
3. **地图规格**：Phase 4 起全部使用 **10m 栅格**（openwater_open_res10_v1，81×81，origin=[-400, 400]）。
4. **坐标系映射**（10m 地图）：
   ```
   world_x = origin_x + col * cell_size_m  = -400 + col * 10
   world_y = origin_y - row * cell_size_m  = 400 - row * 10
   grid 中心 (40, 40) -> World [0.0, 0.0, 0.0]
   ```
5. **adapter 默认路径**：`single_usv_policy_adapter.py` 的 `load_openwater_policy_state()` 在 `map_spec_npz_path=None` 时，自动默认加载 `openwater_open_res10_v1.npz`（Phase 4A 已写入）。
6. **主线配置不变**：
   - `viewpoint_generation_mode = simple_ring_v1`
   - `path_safety_mode = soft_clearance_astar_v1`
   - `clue_acquisition_mode = ucb`
   - `anomaly_tail_quantile = 0.90`
7. **发现半径**：`sensor_range_cells = 5`（即 50.0m），与算法层一致。
8. **fast controller 调参（已验证）**：
   ```python
   MAX_FORCE = 8000.0
   MIN_FORCE = 1500.0
   TURN_GAIN = 0.8
   DIST_SLOW_RADIUS_M = 12.0
   ARRIVAL_RADIUS_M = 5.0
   MAX_TICKS_PER_CELL = 400
   ```
9. **Phase 4C-found 已验证**：10m OpenWater 下，baseline_GP 原生 `found_mask / intensity_mass / found_events hit-update` 链路可以被正确触发（step 51 发现目标，intensity_mass 从 1.0 → 0.0000，43/43 审计通过）。

### 3.2 桥接层架构（已稳定，Phase 4 开始使用）

```
baseline_GP/holoocean_bridge/
    coordinate_adapter.py          # grid_to_world / world_to_grid
    scene_map_adapter.py           # load_scene_map_npz / scene_map_config_from_spec
    single_usv_policy_adapter.py   # load_openwater_policy_state / plan_next_policy_cell / finalize_policy_step_after_holoocean
    execution_backend.py           # get_sensor_vector
    scenario_builder.py
    maps/
        openwater_open_v1.json     # 5m 旧地图（只读）
        openwater_open_v1.npz      # 5m 旧地图（只读）
        openwater_open_res10_v1.json  # 10m 新地图 ✅
        openwater_open_res10_v1.npz   # 10m 新地图 ✅
```

**三大核心函数调用范式（Phase 4C-found 已验证稳定）：**

```python
# 1. 初始化策略状态（默认加载 10m 地图）
state, adapter_config, nav_map_prior = load_openwater_policy_state(None, episode_seed=0)

# 2. 规划下一步格子
next_cell, segment_path, commit_remaining, plan_details = plan_next_policy_cell(
    state=state, step=step, commit_remaining=commit_remaining, episode_seed=0
)

# 3. 仿真执行后更新信念
state = finalize_policy_step_after_holoocean(
    state=state, step=step,
    robot_pos_before=robot_pos_before,
    next_cell=next_cell,
    final_projected_cell=final_projected_cell,
)
```

### 3.3 HoloOcean 多艇 API（Phase 5 关键知识，尚未实战验证）

```python
# 单艇 step（已有 Phase 4 确认）：
state_env = env.step(command)  # 只适用于 main_agent

# 双艇 act + tick（Phase 5 需切换到此模式）：
env.act("sv0", command_0)
env.act("sv1", command_1)
state_env = env.tick()  # 返回所有 agent 的 state dict

# 传感器读取：
loc = state_env["sv0"]["LocationSensor"]
gps = state_env["sv1"]["GPSSensor"]
```

### 3.4 Phase 4 10m adapter 参数（已写入 `single_usv_policy_adapter.py`）

```python
sensor_range_m = 50.0
min_target_separation_m = 60.0
min_start_distance_m = 80.0
gp_length_scale_m = 40.0
clue_sigma_m = 40.0
```

### 3.5 测试套件状态

```powershell
$env:PYTHONPATH='.'; pytest .\baseline_GP\tests\test_holoocean_scene_map_adapter.py .\baseline_GP\tests\test_holoocean_single_usv_policy_adapter.py
# 输出：13 passed in 4.15s ✅
```

（另有 3 个旧测试文件因依赖已删除模块而无法 import，属于已知存量问题，与 HoloOcean 迁移无关）

### 3.6 关键性能基准（对照用）

| 阶段 | 控制方案 | 场景 | 平均 ticks/step | 发现结果 |
|------|----------|------|-----------------|---------|
| Phase 3C-1-catchable | scheme=1 | 动态目标 5m 100步 | 204.2 | 未发现（min 7 格） |
| Phase 3D-1-fastsv | scheme=0 | 动态目标 5m 63步 | **59.8** | **发现（step 63）** |
| Phase 4B | scheme=0 | 10m waypoint smoke | **63.5** | — |
| Phase 4C | scheme=0 | 10m 静态目标 120步 | **81.7** | 未发现（min 5 格） |
| Phase 4C-found | scheme=0 | 10m 静态目标 51步 | **82.8** | **发现（step 51）** |

---

## 4. 待办与接力 (Next Steps)

### 挂起任务（按优先级排序）

1. **🔜 Phase 5：双 USV Coordinated 协同搜索接入**
   - 在 HoloOcean 中同时启动两个 `SurfaceVessel`（`sv0` + `sv1`）
   - 接入 `marine_knownmap_runtime_2usv.py` 的双艇策略规划接口
   - 使用 `env.act() + env.tick()` 替换 `env.step()`
   - 需要设计双艇桥接 adapter（类比 `single_usv_policy_adapter.py`）
   - **关键决策待用户确认**（见下文）：地图规格与初始位置策略

2. **地图规格决策（Phase 5 开始前必须确认）**：
   - **选项 A**：保持 10m 规格（OpenWater 81×81），自定义双艇初始格子（如 `(40,40)` 与 `(40,41)` 或对称位置），不与 baseline_GP 双艇默认起点 `((25,2),(35,2))` 对齐
   - **选项 B**：制作 10m 规格的 60×80 地图（高 60 格 × 宽 80 格，对应 600m × 800m 区域），使双艇起点 `((25,2),(35,2))` 与 baseline 基准完全对齐

3. **Phase 5 关键风险点**：
   - 双艇物理碰撞：`reservation_v1` 只在算法层保证时空预约，`control_scheme=0` 物理执行存在抖动，两艇靠近时可能发生真实碰撞
   - `env.act()` 参数顺序在本地 holo 版本中需 smoke run 确认
   - 双艇 shared team state 在 2usv runtime 中的 step 推进接口需要适配封装

4. **论文写作（并行）**：
   - `my_report.docx` / `信息科学与工程学院_320220938891_郭一泽.docx` 的 HoloOcean 迁移验证章节需要根据 Phase 4 结果（已完成）填写
   - 参考格式规范：`readme/论文写作规范.docx`

### 接力指令

> 给下一个 AI 的接力指令：
>
> **请读取以上信息，立刻进入"HoloOcean 迁移工程师"角色。**
> 当前已完成 Phase 4C-found（10m OpenWater 单艇静态目标发现 E2E 闭环），下一步是 **Phase 5：双 USV Coordinated 协同接入**。
>
> 执行前必须先向用户确认以下两点：
> 1. **地图规格**：10m 81×81 自定义起点（选项 A），还是 10m 60×80 对齐基准起点（选项 B）？
> 2. **Phase 5 正式启动权限**：是否立即开始详细技术设计与代码实现？
>
> 硬性约束：绝对不修改 `marine_knownmap_runtime_2usv.py` 本体，所有双艇状态读取与控制命令下发都必须在新建的桥接 adapter 层中完成。代码证据优先，禁止泛泛表态。

---

## 5. 关键文件路径索引

| 类别 | 路径 |
|------|------|
| 主线结果 | `baseline_GP/results/paper_simple_ring_mainline_20260505/` |
| Phase 0 冻结 | `baseline_GP/results/holoocean_bridge_v1/phase0_freeze/` |
| Phase 4A（10m 地图构建） | `baseline_GP/results/holoocean_bridge_v1/phase4a_res10_bridge_sync/` |
| Phase 4B（10m fast controller）| `baseline_GP/results/holoocean_bridge_v1/phase4b_res10_fast_controller_smoke/` |
| Phase 4C（10m 120步未发现） | `baseline_GP/results/holoocean_bridge_v1/phase4c_res10_static_target_search/` |
| Phase 4C-found（10m 51步发现）| `baseline_GP/results/holoocean_bridge_v1/phase4c_res10_static_target_found/` |
| 10m 地图 spec JSON | `baseline_GP/holoocean_bridge/maps/openwater_open_res10_v1.json` |
| 10m 地图 NPZ | `baseline_GP/holoocean_bridge/maps/openwater_open_res10_v1.npz` |
| 单艇 adapter（已稳定） | `baseline_GP/holoocean_bridge/single_usv_policy_adapter.py` |
| 坐标 adapter | `baseline_GP/holoocean_bridge/coordinate_adapter.py` |
| 场景地图 adapter | `baseline_GP/holoocean_bridge/scene_map_adapter.py` |
| 双艇 runtime（禁止修改） | `baseline_GP/marine_knownmap_runtime_2usv.py` |
| 论文 | `信息科学与工程学院_320220938891_郭一泽.docx` |
| 论文规范 | `readme/论文写作规范.docx` |
| HoloOcean 迁移计划 | `readme/HoloOcean_Plan.md` |
| conda Python | `C:\Users\32022\.conda\envs\holo\python.exe` |
