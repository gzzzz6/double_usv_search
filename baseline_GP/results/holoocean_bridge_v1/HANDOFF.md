## 1. 核心上下文 (The Core Context)

* **项目定义：** baseline_GP 多 USV 协同搜索算法，从纯 Python 仿真迁移到 HoloOcean v2.2.2 高保真仿真器。同时维护一篇中文毕业论文（my_report.docx）。
* **当前进度：**
  - **Phase 0（主线冻结）已完成**：`paper_simple_ring_mainline_20260505` 主线配置审计通过，18 个 config_snapshot 全部一致，hash manifest 已生成。
  - **Phase 1B（SurfaceVessel PD smoke）已完成**：SurfaceVessel + PD Controller (control_scheme=1) + GPSSensor 可运行，4/4 waypoints 到达，逐 tick 轨迹可记录。
  - **论文 my_report.docx**：格式修复完成（页边距、Normal 样式、章节标题、图表标题、参考文献、公式编号与 tab 结构），4.7 节已替换为新内容。
* **关键约束：**
  - conda 环境：`holo`，Python 路径：`C:\Users\32022\.conda\envs\holo\python.exe`
  - HoloOcean world: `SimpleUnderwater`，package: `Ocean`
  - **禁止使用任何 sonar**（ImagingSonar/SidescanSonar/ProfilingSonar/SinglebeamSonar）
  - **禁止修改 baseline_GP 算法文件**：core_search_policy.py, marine_knownmap_runtime.py, marine_knownmap_runtime_2usv.py, core_safe_nav.py, core_execution.py
  - **禁止修改**：my_report.docx, holo1.py, paper_simple_ring_mainline_20260505/*, readme/HoloOcean_Plan.md
  - 不接入 GP clue / intensity / recency / search_info_map
  - 不修改搜索评分、simple_ring_v1、safe-nav、reservation_v1
  - 不运行 baseline_GP 实验
  - 论文格式规范文档：`F:\pythonprojects\论文写作规范.docx`
  - 用户母语中文，偏好代码证据先行、不泛泛解释

## 2. CEO 认知档案 (User Profile Update)

* **偏好：**
  - 中文沟通，但代码/变量名/日志保留英文
  - 代码验证优先于口头承诺——"先跑通再说"
  - 厌恶过度解释和泛泛之谈，要求引用具体文件路径:行号作为证据
  - 接受务实的技术妥协（如 max_ticks 从 500 → 2000，承认 PD 控制器物理限制）
  - 关注"为什么这样做"多于"做了什么"——决策逻辑要记录
  - 用户身份：广州大学本科毕业设计学生
* **雷区：**
  - 不要在没有代码证据的情况下断言"没问题"
  - 不要修改已冻结的 baseline_GP 算法文件
  - 不要擅自运行 baseline_GP 实验
  - 不要泛泛解释概念——用代码引用说话

## 3. 关键知识库 (The Knowledge Base)

### 已确定的决策

1. **主线配置（mainline）**：
   - `viewpoint_generation_mode`: `simple_ring_v1`（已从 infosampled_pool_v1 切换）
   - `path_safety_mode`: `soft_clearance_astar_v1`
   - `team_path_avoidance_mode`: `reservation_v1`
   - `anomaly_tail_quantile`: 0.90
   - `anomaly_weight_lambda`: 1.25（运行时默认 1.0，主线实验用 1.25）
   - `assignment_mode`: coordinated（coordinated 目录）；independent（independent 目录，合法变体）
   - single-USV map: 40×60；two-USV map: 60×80
   - two-USV start positions: ((25, 2), (35, 2))

2. **HoloOcean 迁移策略**：
   - 分阶段推进：Phase 0（冻结）→ Phase 1（smoke）→ 后续 Phase
   - Phase 0：只读审计 + 文件 hash + git 状态
   - Phase 1B：先验证单艇 PD 控制可用，再接搜索算法
   - surfacevessel 控制方式：`env.step([target_x, target_y])` 返回 state dict
   - GPS 读取：`state["GPSSensor"][0:2]`

3. **论文格式规范**（已写入论文写作规范.docx）：
   - 公式 tab 结构：居中对齐 tab（4153 EMU）+ 右对齐 tab（8306 EMU），公式在中间，编号在右侧
   - 公式编号必须在公式**之后**（tab→公式→tab→(N)）
   - 本章节标题用样式 ID 而非中文名：一级标题=af7，二级标题=af7（正文中的节）

### 沉淀的方法论/代码片段

**HoloOcean SurfaceVessel PD 最小可运行配置：**
```python
config = {
    "name": "SurfaceNavigator",
    "world": "SimpleUnderwater",
    "package_name": "Ocean",
    "main_agent": "sv",
    "agents": [{
        "agent_name": "sv",
        "agent_type": "SurfaceVessel",
        "sensors": [{"sensor_type": "GPSSensor"}],
        "control_scheme": 1,  # PD Control
        "location": [0, 0, 2],
        "rotation": [0, 0, 0],
    }],
}
env = holoocean.make(scenario_cfg=config)
state = env.step([target_x, target_y])
p = state["GPSSensor"][0:2]
```

**SurfaceVessel 运动特性（实测）：**
- 从 [0,0] 到 [25,25]（~35m 距离）：~999 ticks，~187s wall time
- 平均速度：~0.04–0.05 m/tick
- Tick rate：~26.6 ticks/sec（均值 35.6ms/tick，max 85.4ms/tick）
- PD 控制器到达精度：~1.0m 半径内
- max_ticks_per_waypoint 需要 ≥ 2000 才可靠覆盖 35m 距离

**python-docx 中文字体设置（关键模式）：**
```python
from docx.oxml.ns import qn
from lxml.etree import OxmlElement
rPr = run._r.get_or_add_rPr()
rFonts = rPr.find(qn('w:rFonts'))
if rFonts is None:
    rFonts = OxmlElement('w:rFonts')
    rPr.insert(0, rFonts)
rFonts.set(qn('w:eastAsia'), '黑体')  # 或 '宋体'
rFonts.set(qn('w:ascii'), 'Times New Roman')
```

**公式 tab 停靠位设置（XML）：**
```python
# 居中 tab @4153 EMU，右对齐 tab @8306 EMU
tabs = OxmlElement('w:tabs')
tab_center = OxmlElement('w:tab')
tab_center.set(qn('w:val'), 'center')
tab_center.set(qn('w:pos'), '4153')
tab_right = OxmlElement('w:tab')
tab_right.set(qn('w:val'), 'right')
tab_right.set(qn('w:pos'), '8306')
tabs.append(tab_center); tabs.append(tab_right)
pPr.append(tabs)
```

**TOC 公式目录项（field code）：**
```python
BS = chr(92)  # backslash
fldChar = OxmlElement('w:fldChar')
instrText = OxmlElement('w:instrText')
instrText.set(qn('xml:space'), 'preserve')
instrText.text = f' TC "公式（{num}）" {BS}f E {BS}l 1'
```

**Phase 0 审计结论关键发现：**
- `path_safety_mode`/`anomaly_tail_quantile`/`anomaly_weight_lambda` 在 config_snapshot 中均为 null——这些是运行时参数，默认值在源码中，非异常
- `policy_name` 在 two_usv 目录的 config 中为 null——is_two_usv 检测需改用目录名而非 policy_name

### 关键文件路径索引

| 类别 | 路径 |
|------|------|
| 主线结果 | `baseline_GP/results/paper_simple_ring_mainline_20260505/` |
| Phase 0 冻结 | `baseline_GP/results/holoocean_bridge_v1/phase0_freeze/` |
| Phase 1B smoke | `baseline_GP/results/holoocean_bridge_v1/phase1_surfacevessel_smoke/` |
| HoloOcean 示例 | `holo1.py` |
| 论文 | `my_report.docx` |
| 论文规范 | `论文写作规范.docx` |
| 论文 4.7 节源 | `ch4_7_restructured.md` |
| 格式修复脚本 | `baseline_GP/results/_temp_run_scripts/fix_report_format.py` |
| 4.7 替换脚本 | `baseline_GP/results/_temp_run_scripts/replace_sec47.py` |
| Hash manifest | `phase0_freeze/manifests/phase0_file_hashes.csv` |
| 配置审计报告 | `phase0_freeze/reports/phase0_config_audit.md` |

