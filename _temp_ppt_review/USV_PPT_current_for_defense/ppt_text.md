# PPT summary
path: E:\毕设PPT\USV_PPT.pptx
slides: 21
size: 13.333 x 7.5 in

## Slide 01: 面向海上可疑目标搜索任务的
chars=44, text_blocks=3, pictures=2, tables=0, charts=0, groups=6
面向海上可疑目标搜索任务的
多USV决策优化方法研究
2026年5月
自强不息，独树一帜

## Slide 02: 自强不息，独树一帜
chars=301, text_blocks=22, pictures=2, tables=0, charts=0, groups=4
自强不息，独树一帜
目录
CONTENTS
选题背景和综述
Background and Literature Review
1
多源搜索状态建模
Multi-Source Search State Modeling
2
单艇信息驱动路径规划
Single-USV Informative Path Planning
3
双艇集中式协同搜索决策
Dual-USV Coordinated Search Decision
4
2
实验设计和结果分析
Experimental Design and Results Analysis
5
总结与展望
Conclusion and Future Work
6

## Slide 03: 选题背景和意义
chars=180, text_blocks=8, pictures=3, tables=0, charts=0, groups=0
选题背景和意义
海上可疑目标搜索面临复杂环境和信息不确定性难题
3
近岸安防、海上搜索等任务需要无人化、持续化搜索能力
USV 可持续巡航、降低人员风险，适合承担海上搜索任务
搜索任务中，目标位置通常未知，且USV观测范围有限
海上环境存在障碍、岸线、狭窄通道等空间约束，搜索路径不能只追求距离最短
多 USV 协同时，会出现重复搜索、区域分工和路径冲突等问题

## Slide 04: 相关研究的发展脉络
chars=233, text_blocks=15, pictures=2, tables=0, charts=0, groups=0
相关研究的发展脉络
1
2
3
4
未知地图探索阶段
已知地图下的信息型路径规划
多机器人协同搜索
早期的探索围绕未知地图建模，代表思路是frontier-based exploration，机器人不知道环境结构，需要边运动边建图
当地图结构已知后，USV不需要再去探索障碍和自由空间，问题变为：判断哪些区域更可能带来目标相关观测？
单机器人在搜索任务上会略显乏力，所以现有研究大多为多机器人协同，这也会进一步带来一系列问题：
任务分配
协同收益
重复覆盖
路径冲突

## Slide 05: 本项目工作
chars=361, text_blocks=32, pictures=17, tables=0, charts=0, groups=0
本项目工作
已知静态地图下的信息驱动搜索基线
5
本文聚焦已知静态障碍地图中目标位置未知的搜索任务，构建单艇与双艇条件下的信息驱动搜索基线。
感知与状态更新
已知静态地图
障碍结构已知
目标位置未知
observation 
传感器范围内
局部带噪观测
detect
命中更新/
未命中更新
信息场的建模
GP Clue
高斯过程后验
Anomaly变式
Intensity 
空间目标存在信念
Recency
观测时效性
单艇路径规划
Anchor 
提取
Viewpoint
选取
A* 寻路
截取
短路径段
路径段评分
信息收益
刷新收益
执行代价
双艇协同
Coordinated顺序规划
Residual map规划
责任区偏置
抑制重复覆盖
双艇冲突校验
双艇执行
执行路径段
获得新观测
更新信息场
重新决策

## Slide 06: 多源搜索状态建模
chars=283, text_blocks=22, pictures=1, tables=0, charts=0, groups=0
多源搜索状态建模
➢
三维互补的信息场
海上搜索中观测有限且带噪，单一信息源难以同时表达线索强度、目标存在信念与观测刷新需求。
单一信息源的局限
GP Clue
可推断线索热点，但受采样稀疏和观测噪声限制。
Intensity
能反应目标存在信念，但更新质量受探测范围、漏检和历史反馈累积影响。
Recency
可提示长期未观测区域，但只描述时间新鲜度，无法区分区域本身的重要程度。
三维互补建模
GP Clue
线索场估计
哪里有线索，哪里不确定
Intensity
目标存在信念
探测反馈后哪里仍值得搜索
Recency
观测时效性
哪里太久没看，需要刷新
互补

## Slide 07: 多源搜索状态建模
chars=326, text_blocks=19, pictures=1, tables=0, charts=0, groups=0
多源搜索状态建模
➢
基于 GP 的线索场估计与 anomaly-aware 加权
高斯过程后验估计
目标：由有限观测点推断整张地图上的 clue 后验场
局部带噪观测
GP 后验推断
后验输出
μ(x)：线索强度估计
σ(x)：未观测不确定性
μ(x) 高：已观测线索强
σ(x) 高：区域仍不确定
UCB 同时兼顾利用与探索
anomaly-aware 异常上尾加权
在 GP-UCB 基础上，进一步强化后验高值区域的搜索倾向。
上尾区域
异常率
路径决策引入置信上限(Upper Confidence Bound)作为动作选择准则
乘性加权
保留了UCB在“高均值利用”与“不确定性探索”之间的基本平衡，同时对更可能属于高值上尾的区域给予额外强调

## Slide 08: 多源搜索状态建模
chars=237, text_blocks=15, pictures=2, tables=0, charts=0, groups=0
多源搜索状态建模
➢
目标存在信念与观测时效建模
Intensity：剩余目标存在信念
运动预测
可疑目标存在两种运动情况：static 保持分布；random_walk 向相邻自由格扩散。
未命中更新
传感器覆盖区域的目标质量降低，随后归一化保持总目标质量不变。
命中更新
探测到目标后，将传感器覆盖区域清零，减少总目标质量，再归一化实现质量再分配。
Recency：观测时效性
状态记录
USV 传感器覆盖到自由格 x 时，记录该格最近一次被观测的仿真步。
时效计算
8

## Slide 09: 单艇信息驱动路径规划
chars=180, text_blocks=7, pictures=2, tables=0, charts=0, groups=0
单艇信息驱动路径规划
➢
单艇路径规划框架
9
滚动决策控制模型
单艇自主规划决策状态转移闭环流程
滚动时域控制思想
由于多源信息场（强度场/Recency/GP线索场）随着USV的实时探测与环境演化而不断动态刷新，不适合进行一次性长期静态规划。
算法采用“决策-滚动执行-实时探测-更新场模型-再次重规划”的闭环控制模式，能灵敏应对突发目标或局部线索的出现。

## Slide 10: 单艇信息驱动路径规划
chars=288, text_blocks=12, pictures=3, tables=0, charts=0, groups=0
单艇信息驱动路径规划
➢
从信息价值场到安全候选路径段
10
综合信息价值场
search_info_map = 0.5·norm(GP Clue) + 0.5·norm(Intensity)
Anchor / Viewpoint 候选生成
将热点区域聚类，对热点簇评分，同时兼顾热度峰值、均值及区域尺度大小。
Anchor：从高价值区域聚类中提取，表示“哪里值得被观察”。
Viewpoint：在 Anchor 周围自由格中生成候选观测点。
A* 安全路径与短段截断
避障：障碍物附近可通行，但路径代价会增大。
对完整路径截取前 8 步，形成候选 segment_path。

## Slide 11: 单艇信息驱动路径规划
chars=207, text_blocks=26, pictures=1, tables=0, charts=0, groups=0
单艇信息驱动路径规划
➢
路径段评分与最优 segment 选择
11
评分公式
Score =
- u_turn_penalty
1
信息收益
覆盖高信息值区域。
2
刷新收益
鼓励路径段覆盖长期未观测区域。
3
执行代价
由路径长度、转向与 贴近障碍代价共同构成。
4
掉头惩罚
抑制频繁反向移动，使短时路径更稳定。
重规划机制
最优短路径段选择
执行下一步
是否执行完固定步数
获得新观测，更新信息场
是
否

## Slide 12: 12
chars=243, text_blocks=15, pictures=1, tables=0, charts=0, groups=0
12
集中式共享团队状态
双艇集中式协同搜索决策
➢
双艇协同搜索的问题定义
在共享地图与共享信息场下，两艘 USV 需要同时规划短时路径段；核心问题是减少重复覆盖，并保证执行过程不发生路径冲突。
known_map
GP Clue
Intensity
Recency
U0
U1
独立规划风险
若两艇看到相同的信息场，且各自独立规划，就容易同时选择相近高价值区域，造成重复搜索和观测浪费。
两艇能获取相同的线索场、目标强度场、观测时效性场。
但路径规划和观测点选择改为团队协同式执行。

## Slide 13: 双艇集中式协同搜索决策
chars=187, text_blocks=19, pictures=2, tables=0, charts=0, groups=0
双艇集中式协同搜索决策
➢
责任区偏置与路径冲突安全
13
责任区偏置
本项目中责任区偏置仅作用于信息场评分，没有完全阻碍USV跨区。若存在强热点区域，USV可跨区执行搜索任务。
双艇冲突安全
U0
U1
检查同格占用与对向换位
1
同格冲突
同一时刻两艇不能占据同一网格。
2
对向换位
相邻时刻不能沿同一边相向交换位置。
3
近邻代价
近邻区域不硬禁止，但增加通行代价。

## Slide 14: 双艇集中式协同搜索决策
chars=472, text_blocks=24, pictures=2, tables=0, charts=0, groups=0
双艇集中式协同搜索决策
➢
顺序分配与团队评分
14
核心思想
先规划的一艇占用其可观测信息价值，后规划的一艇在剩余信息图上重新选择路径段。
1
枚举顺序
尝试 (U0→U1) 与 (U1→U0)，比较团队总得分。
2
第一艇规划
第一艘艇先规划，得到短路径段，并求出 visible cells。
3
残差信息图
将第一艇可见区域visible cells置零。
4
第二艇规划
第二艘艇在 residual_map 上规划，降低重复覆盖同一热点的倾向。
图中蓝色路径先规划并移除可见区域；橙色路径随后在 residual_map 上选择剩余高价值区域。
团队联合评分与最优双路径段
沿用单艇路径规划评分，包含综合信息价值覆盖收益、刷新收益、几何代价与掉头惩罚项。


若双艇最终决策了相同 viewpoint，扣除 same-viewpoint penalty；若重合重叠交集多，则扣除重复覆盖惩罚。


计算两种分配顺序下的团队总得分并比对大小，选择最高分对应的双艇路径分配，下发两艇同步执行。
同点及重复惩罚
团队最优决策
沿用单艇评分

## Slide 15: 实验设计与结果分析
chars=444, text_blocks=33, pictures=2, tables=0, charts=0, groups=0
实验设计与结果分析
➢
实验设置与评价指标
15
三类实验地图
open_water
obstacle_field
peninsula_passage
变量控制与运行条件
目标模式
static / random_walk
线索采集
UCB ；anomaly-aware
重复实验
seeds = 0–9，最大步数 240
目标数量
每个场景3个目标，数量已知
评价指标
T_first
首次发现目标所需步数
T_all
完成全部目标搜索所需步数
success(%)
发现全部目标的成功率
detection(%)
最终目标探测覆盖比例
duplicate(%)
cross(%)
wait
两艇选择同一个观测点的比例
两艇偏离各自软责任区的探索比例
两艇路径执行中触发等待回退的次数
开阔水域 (open_water)：仅包含边界约束。
离散障碍 (obstacle_field)：离散矩形障碍，用于检验局部绕行。
半岛通道 (peninsula_passage)：包含半岛和窄通道。

## Slide 16: 实验设计与结果分析
chars=272, text_blocks=7, pictures=2, tables=1, charts=0, groups=0
实验设计与结果分析
➢
单艇搜索实验结果
16
六组单艇 UCB 轨迹示例（三地图 × 两目标模式）
目标模式 | 地图 | T_first | T_all | success
静态 | 总体 | 47.0 | 153.7 | 50.0%
静态 | 离散障碍 | 38.5 | 117.3 | 60.0%
随机游走 | 总体 | 60.5 | 145.6 | 63.3%
随机游走 | 离散障碍 | 54.7 | 138.0 | 60.0%
基础可行性证明：单 USV 能依靠本文算法在有限步长内完成全部目标搜索，体现了本闭环控制算法的可行性。

## Slide 17: 实验设计与结果分析
chars=467, text_blocks=8, pictures=3, tables=1, charts=0, groups=0
实验设计与结果分析
➢
双艇协同搜索结果
17
图中蓝色为 independent，橙色为 coordinated。
模式 | 指标 | 总体平均 | 开阔水域 | 离散障碍
静态 | ΔT_first | -22.6 | -23.0 | -4.6
静态 | Δsuccess | +20.0% | 0.0% | +20.0%
静态 | Δcross | -30.5% | -25.1% | -25.8%
动态 | ΔT_first | -9.2 | -25.4 | +4.6
动态 | Δsuccess | +10.0% | +10.0% | +20.0%
动态 | Δcross | -33.5% | -27.1% | -41.0%
协同机制性能增益 (Coordinated-Independent)
责任区分工见效：跨区探索比例 (Δcross) 在两类目标模式下分别降低30.5%与 33.5%。

重复搜索显著降低：相同观测点比例 (Δduplicate) 降低了 4%~8%，整体效率和发现全部目标的成功率得到明显改善。

## Slide 18: 实验设计与结果分析
chars=333, text_blocks=8, pictures=2, tables=1, charts=0, groups=0
实验设计与结果分析
➢
anomaly-aware 消融实验
18
：比较GP-UCB与anomaly-aware上尾加权策略，检验“强化GP后验高值区域”是否能改善目标搜索效率。
红线为 anomaly-aware，蓝线为 UCB。
目标模式 | ΔT_first | ΔT_all | Δsuccess | Δobs (观测开销)
静态目标 | -5.2 | +1.8 | -3.3% | -5.9%
随机游走 | +4.9 | -29.4 | +13.3% | -8.9%
在随机游走目标下，anomaly-aware的优势更明显：T_all平均减少29.4步，成功率提升13.3%。在双艇静态目标下，两种策略表现接近，说明上尾加权并不总是稳定优于 UCB。

## Slide 19: 总结与展望
chars=367, text_blocks=24, pictures=2, tables=0, charts=0, groups=0
总结与展望
➢
项目总结
19
本项目围绕“已知静态障碍地图下目标位置未知”的 USV 搜索任务，构建了单艇与双艇条件下的信息驱动搜索方法。
1
状态建模
GP clue、intensity、recency 分别刻画线索强度、目标存在信念与观测时效。
2
单艇规划
从高价值区域提取 anchor / viewpoint，经 A* 生成安全短路径段并滚动重规划。
3
双艇协同
在共享状态下进行顺序分配，用 residual_map 抑制重复覆盖。
4
实验验证
在三类正式地图、两类目标运动模式下评估完成效率、成功率与协同行为。
状态层
多源状态互补
将 GP clue、intensity、recency 分开建模，三场互补
消融层
anomaly-aware 优化
在 GP-UCB 基础上引入后验上尾区域加权。
本文主要创新点

## Slide 20: 总结与展望
chars=274, text_blocks=19, pictures=2, tables=0, charts=0, groups=0
总结与展望
➢
本项目的不足
20
地图假设
仅考虑已知静态障碍地图；动态障碍、潮流风浪等环境变化未纳入主线。
团队状态
双艇没有建模通信延迟。
规模验证
当前只实现双艇协同基线；三艇及以上的调度复杂度与收益没有验证。
实验平台
实验在二维栅格仿真中完成，尚未接入真实USV船体、传感器误差和海况约束。
后续研究展望
真实环境
加入动态障碍、海况扰动，检验已知静态地图假设放宽后的表现。
更多艇协同
在保持可解释性的前提下扩展到多艇规模，研究任务分配、冲突处理和计算效率。
仿真验证
接入更接近实船控制的仿真或硬件平台，验证路径执行与感知更新闭环。

## Slide 21: 23
chars=30, text_blocks=4, pictures=2, tables=0, charts=0, groups=3
23
2025年5月
自强不息，独树一帜
恳请老师批评指正！
