**交接式执行方法论**

核心原则是：我负责把任务拆清楚、把风险边界划清楚、把命令和验收标准写具体；DeepSeek 负责按阶段执行、跑代码、产出结果。这样可以减少它临场理解偏差，也避免它擅自扩大修改范围。

**1. 先定义任务边界**

每次交给 DeepSeek 前，先明确：

- 本次只做什么；
- 明确不做什么；
- 允许修改哪些文件；
- 禁止修改哪些文件；
- 结果输出到哪个目录；
- 是否允许覆盖旧结果。

例如：

```text
本阶段只运行 simple_ring_v1 主线实验，不修改搜索算法。
不得改动 core_search_policy.py、marine_knownmap_runtime.py、marine_knownmap_runtime_2usv.py。
所有输出写入 results/paper_simple_ring_mainline_20260505，不覆盖旧目录。
```

**2. 按阶段交付，而不是一次性给大任务**

把任务拆成：

```text
阶段 1：检查环境和代码状态
阶段 2：修改或新增 runner
阶段 3：小规模 smoke run
阶段 4：正式批量运行
阶段 5：完整性校验
阶段 6：汇总表格
阶段 7：给出结果路径和异常说明
```

每个阶段只给一个明确目标。上一阶段没确认，不进入下一阶段。

**3. 每个阶段都给可复制命令**

不要只说“检查一下”或“跑一下实验”，而是写成可直接执行的命令，例如：

```powershell
python -m py_compile baseline_GP/core_search_policy.py baseline_GP/marine_knownmap_runtime.py baseline_GP/marine_knownmap_runtime_2usv.py
```

如果需要写脚本，也指定：

```text
脚本路径：
baseline_GP/results/_temp_run_scripts/run_simple_ring_mainline.py

脚本必须支持：
--output_root
--maps open_water harbor_cove peninsula_passage
--seeds 0 1 2 3 4 5 6 7 8 9
```

**4. 每阶段都设置验收标准**

DeepSeek 执行完必须回报具体证据，而不是说“已完成”。

验收格式建议固定为：

```text
已完成：
1. 生成目录：
2. 生成文件：
3. episode 行数：
4. 配置校验：
5. 是否有异常：
```

例如：

```text
3 maps × 2 clue modes × 10 seeds = 60 行
viewpoint_generation_mode = simple_ring_v1
path_safety_mode = soft_clearance_astar_v1
anomaly_tail_quantile = 0.9
anomaly_weight_lambda = 1.25
```

**5. 明确代码口径必须来自 runtime，而不是猜测**

要求 DeepSeek 在修改或汇总前先用代码验证字段来源：

```text
必须从 episode_results.json / summary.json 中读取真实字段。
不得根据文件夹名推断配置。
不得手写实验结果。
不得把旧 infosampled_pool_v1 数据混入 simple_ring_v1 主线。
```

**6. 先 smoke run，再批量跑**

任何新 runner 或新配置都必须先跑最小样例：

```text
1 map × 1 seed × 20 iters
```

确认能跑通后，再执行完整实验：

```text
3 maps × 2 motion modes × 2 clue modes × 10 seeds
```

这样可以避免一上来跑几个小时后才发现参数错。

**7. 汇总数据时必须保留原始数据路径**

所有汇总表都要可追溯：

```text
raw_results/
summary/
paper_tables/
logs/
```

汇总脚本要输出：

- CSV 表；
- Markdown 预览；
- 配置校验报告；
- 异常值说明。

**8. 发现异常时不要自动修数据**

如果出现：

- 缺 seed；
- 某地图结果为空；
- `time_to_all_found` 大量 N/A；
- 配置字段不一致；
- episode 数不对；

DeepSeek 只能报告异常和可能原因，不能擅自补数据、删数据、改结果。

**9. 对论文写作任务也要阶段化**

写 Word 或论文内容时，流程是：

```text
1. 备份 my_report.docx
2. 阅读写论文方法论 readme/readme.md
3. 只修改指定章节
4. 使用 UTF-8 Python 脚本修改 docx，避免 PowerShell 中文乱码
5. 验证标题、图表、公式、引用编号
6. 汇报备份路径和修改范围
```

尤其要强调：

```text
不要用 PowerShell inline Python 写中文正文。
不要全局替换不确定文本。
不要擅自改其它章节。
```

**10. 给 DeepSeek 的指令模板**

以后可以按这个模板发：

```text
你现在执行第 X 阶段：{阶段名称}

目标：
{本阶段只完成什么}

允许修改：
{文件或目录}

禁止修改：
{文件或目录 / 算法逻辑}

输入：
{数据源 / 配置 / 参数}

输出：
{输出目录 / 文件名}

执行要求：
1. ...
2. ...
3. ...

验收标准：
1. ...
2. ...
3. ...

完成后只汇报：
1. 修改了哪些文件
2. 运行了哪些命令
3. 结果文件路径
4. 校验结果
5. 异常或未完成事项
```

这套方法的关键是：我把“不该出错的地方”提前写死，DeepSeek 只按清单执行。这样最适合长实验、论文数据汇总、Word 文档批量修改和 HoloOcean 迁移这种多阶段任务。