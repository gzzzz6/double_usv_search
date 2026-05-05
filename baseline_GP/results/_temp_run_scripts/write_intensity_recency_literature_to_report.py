# -*- coding: utf-8 -*-
"""Add literature grounding to sections 3.2 and 3.3 of my_report.docx."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document


REPORT_PATH = Path(r"F:\pythonprojects\my_report.docx")


REFERENCES = [
    "Rasmussen C E, Williams C K I. Gaussian Processes for Machine Learning[M]. Cambridge, MA: MIT Press, 2006.",
    "Auer, P., Cesa-Bianchi, N., & Fischer, P. (2002). Finite-time analysis of the multiarmed bandit problem. Machine Learning, 47(2-3), 235-256.",
    "Srinivas, N., Krause, A., Kakade, S. M., & Seeger, M. (2010). Gaussian process optimization in the bandit setting: No regret and experimental design. In Proceedings of the 27th International Conference on Machine Learning (ICML) (pp. 1015-1022).",
    "Blanchard A, Sapsis T. Informative path planning for anomaly detection in environment exploration and monitoring[J]. Ocean Engineering, 2022, 243: 110242.",
    "Rayas Fernández I M, Denniston C E, Caron D A, Sukhatme G S. Informative Path Planning to Estimate Quantiles for Environmental Analysis[J]. IEEE Robotics and Automation Letters, 2022, 7(4): 10280-10287.",
    "Fossum T O, Travelletti C, Eidsvik J, Ginsbourger D, Rajan K. Learning excursion sets of vector-valued Gaussian random fields for autonomous ocean sampling[J]. The Annals of Applied Statistics, 2021, 15(2).",
    "Gotovos A, Casati N, Hitz G, Krause A. Active Learning for Level Set Estimation[C]//IJCAI. 2013: 1344-1350.",
    "Mahler R P S. Multitarget Bayes filtering via first-order multitarget moments[J]. IEEE Transactions on Aerospace and Electronic Systems, 2003, 39(4): 1152-1178.",
    "Stone L D. Theory of Optimal Search[M]. New York: Academic Press, 1975.",
    "Särkkä S. Bayesian Filtering and Smoothing[M]. Cambridge: Cambridge University Press, 2013.",
    "Smith S L, Schwager M, Rus D. Persistent robotic tasks: Monitoring and sweeping in changing environments[J]. IEEE Transactions on Robotics, 2012, 28(2): 410-426.",
    "Nigam N. The multiple unmanned air vehicle persistent surveillance problem: A review[J]. Machines, 2014, 2(1): 13-72.",
    "Bai, S., Shan, T., Chen, F., Liu, L., & Englot, B. (2021). Information-driven path planning. Current Robotics Reports, 2, 177-188.",
    "Vivaldini, K. C. T., Pěnička, R., & Saska, M. (2025). Decision-making-based path planning for autonomous UAVs: A survey. arXiv:2508.09304.",
    "Popović, M., Ott, J., Rückin, J., & Kochenderfer, M. J. (2024). Learning-based methods for adaptive informative path planning. Robotics and Autonomous Systems, 179, 104727.",
    "Cortes, J., Martinez, S., Karatas, T., & Bullo, F. (2004). Coverage control for mobile sensing networks. IEEE Transactions on Robotics and Automation, 20(2), 243-255.",
    "Zeng, R., Wen, Y., Zhao, W., & Liu, Y.-J. (2020). View planning in robot active vision: A survey of systems, algorithms, and applications. Computational Visual Media, 6, 225-245.",
    "Chen, S., Li, Y. F., Zhang, J., & Wang, W. (Eds.). (2008). Active Sensor Planning for Multiview Vision Tasks. Springer Berlin, Heidelberg.",
    "Potthast, C., & Sukhatme, G. S. (2014). A probabilistic framework for next best view estimation in a cluttered environment. Journal of Visual Communication and Image Representation, 25(1), 148-164.",
    "Bircher, A., Kamel, M., Alexis, K., Oleynikova, H., & Siegwart, R. (2016). Receding horizon Next-Best-View planner for 3D exploration. In Proc. IEEE International Conference on Robotics and Automation (ICRA) (pp. 1462-1468).",
    "Thrun, S., Burgard, W., & Fox, D. (2005). Probabilistic Robotics. MIT Press. (Chapter 6: Path Planning)",
    "Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths. IEEE Transactions on Systems Science and Cybernetics, 4(2), 100-107.",
    "Russell, S. J., & Norvig, P. (2021). Artificial Intelligence: A Modern Approach (4th ed.). Pearson. (Section 3.5: Informed Search Strategies)",
    "Binney, J., & Sukhatme, G. S. (2012). Branch and bound for informative path planning. In Proc. IEEE International Conference on Robotics and Automation (ICRA) (pp. 2147-2154).",
    "Hollinger, G. A., & Sukhatme, G. S. (2014). Sampling-based robotic information gathering algorithms. The International Journal of Robotics Research, 33(9), 1271-1287.",
    "Krause, A., & Guestrin, C. (2011). Submodularity and its applications in optimized information gathering. ACM Transactions on Intelligent Systems and Technology, 2(4), Article 32.",
    "Marchant, R., & Ramos, F. (2014). Bayesian optimisation for informative continuous path planning. In Proc. IEEE International Conference on Robotics and Automation (ICRA) (pp. 6136-6143).",
]


def set_paragraph_text(paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def append_sentence(paragraph, text: str) -> None:
    paragraph.add_run(text)


def find_section(paragraphs, start_prefix: str, end_prefix: str) -> tuple[int, int]:
    start = None
    for idx, paragraph in enumerate(paragraphs):
        if paragraph.text.strip().startswith(start_prefix):
            start = idx
            break
    if start is None:
        raise RuntimeError(f"Section {start_prefix!r} not found.")
    for idx in range(start + 1, len(paragraphs)):
        stripped = paragraphs[idx].text.strip()
        if stripped.startswith(end_prefix) or stripped.startswith("第四章") or stripped.startswith("4."):
            return start, idx
    raise RuntimeError(f"Section end {end_prefix!r} not found.")


def shift_existing_later_citations(text: str) -> str:
    # Longer/range patterns first.
    replacements = [
        ("[12-14]", "[17-19]"),
        ("[15]", "[20]"),
        ("[11]", "[16]"),
        ("[10]", "[15]"),
        ("[9]", "[14]"),
        ("[8]", "[13]"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_PATH.with_name(
        f"my_report_backup_before_intensity_recency_refs_{stamp}.docx"
    )
    shutil.copy2(REPORT_PATH, backup)

    doc = Document(REPORT_PATH)
    paragraphs = doc.paragraphs
    sec32_start, sec32_end = find_section(paragraphs, "3.2", "3.3")
    sec33_start, sec33_end = find_section(paragraphs, "3.3", "3.4")
    ref_start = None
    for idx, paragraph in enumerate(paragraphs):
        if re.match(r"^\[\d+\]\s+", paragraph.text.strip()):
            ref_start = idx
            break
    if ref_start is None:
        raise RuntimeError("No numbered reference list found.")

    sec32 = paragraphs[sec32_start:sec32_end]
    sec33 = paragraphs[sec33_start:sec33_end]
    if len(sec32) < 31 or len(sec33) < 6:
        raise RuntimeError(
            f"Unexpected section sizes: 3.2={len(sec32)}, 3.3={len(sec33)}"
        )

    # 3.2 text replacement. Formula paragraphs remain unchanged.
    set_paragraph_text(
        sec32[1],
        "除基于高斯过程的clue场外，本文还引入目标强度场（Intensity Field）来显式表示剩余未发现目标在空间上的分布性信念。与clue场不同，clue场描述的是目标诱导环境线索的连续强弱，而强度场则直接描述“某位置仍可能存在多少剩余目标”的期望分布。这种以空间强度函数表示目标存在期望数的思想，与多目标贝叶斯滤波中的probability hypothesis density（PHD）或一阶多目标矩思想具有相似性；PHD在某一区域上的积分可解释为该区域内目标数量的期望值[8]。不同的是，本文并不求解完整的多目标跟踪问题，也不处理复杂数据关联，而是将该思想简化为已知离散地图上的剩余目标强度场，用于为搜索路径规划提供空间优先级。"
    )
    set_paragraph_text(
        sec32[5],
        "与GP clue场主要依赖带噪观测进行回归不同，Intensity场的更新依赖于搜索过程中的行为与观测结果，即目标运动预测、未命中观测更新以及命中后质量移除。因而，Intensity场承担的是“剩余目标空间分布信念”的建模角色，而不是环境线索的统计回归角色。"
    )
    set_paragraph_text(
        sec32[7],
        "在搜索任务开始前，系统已知目标总数N，但对目标的具体位置无任何先验信息。在贝叶斯搜索理论中，目标位置通常首先由先验概率分布描述，并根据搜索过程中的观测结果逐步更新；当缺乏额外空间先验时，在可搜索区域内采用均匀先验是一种自然的初始化方式[9]。因此，本文将强度场初始化为在所有已知自由栅格上的均匀分布："
    )
    set_paragraph_text(
        sec32[11],
        "从递推贝叶斯滤波角度看，目标状态估计通常由预测和更新两个步骤组成：预测步骤依据运动模型传播先验分布，更新步骤则利用新观测修正预测分布[10]。在本文中，目标运动状态分为静态和随机游走；其中在动态目标场景下，系统会进一步对强度场执行一步运动预测。若目标运动模式为静态，则有"
    )
    set_paragraph_text(
        sec32[17],
        "在得到一步预测强度场后，系统根据当前时刻USV的观测结果对其进行更新。若USV在当前传感器覆盖范围内未发现目标，则意味着该区域内目标存在的可能性应当下降。在贝叶斯搜索问题中，未发现目标并不等价于目标不存在，但会根据传感器探测概率降低被搜索区域的后验目标存在概率；本文的未命中更新正是对这一负观测信息的离散栅格化实现[9]。为此，本文对传感器覆盖区域内的强度质量进行衰减更新。"
    )
    set_paragraph_text(
        sec32[23],
        "但公式（28）会导致强度场总质量的压缩，于是需要在衰减之后对强度场重新归一化，使其总质量仍保持为当前剩余目标数。"
    )
    set_paragraph_text(
        sec32[30],
        "随后，对命中邻域之外的强度场重新归一化，得到更新后的剩余目标强度分布。Intensity场的观测更新包含两类互补机制：未命中更新负责抑制已搜索但未发现目标的区域，命中更新负责移除已确认目标邻域并同步减少剩余目标总质量，二者共同构造了“剩余未发现目标”的动态空间分布。命中更新后强度场总质量随剩余目标数量同步减少，这也与强度函数总质量表示期望目标数量的解释保持一致。"
    )

    # 3.3 text replacement. Formula paragraph remains unchanged.
    set_paragraph_text(
        sec33[1],
        "在可疑目标搜索过程中，USV的传感器观测并不能被视为永久有效。持续监测与持久覆盖研究通常指出，机器人在动态或不确定环境中并非只需一次性完成区域覆盖，而是需要根据环境变化和信息陈旧程度反复刷新观测；长期未被访问的区域往往具有更高的不确定性或更低的信息可靠性[11]。一方面，传感器存在漏检可能，即某一区域虽然被传感器覆盖，但目标仍可能未被发现；另一方面，在动态目标场景中，目标位置会随时间发生变化，使得早期观测结果对当前状态的解释能力逐渐下降。因此，仅记录某一区域“是否曾被观测”是不充分的，还需要描述观测信息随时间衰减的特性。"
    )
    append_sentence(
        sec33[2],
        " 与persistent surveillance中常用的重访时间思想类似，本文通过记录每个自由栅格最近一次被传感器覆盖的时间，构造观测时效性场，用于衡量该区域观测信息的陈旧程度。"
    )
    append_sentence(
        sec33[4],
        " 持续监视问题通常将重访时间或观测间隔作为衡量监视质量的重要因素[12]，本文的观测时效性场则将这一思想转化为路径规划阶段可使用的局部刷新收益。"
    )
    set_paragraph_text(
        sec33[5],
        "在候选路径评价中，系统根据路径传感器覆盖范围内的观测时效性场计算刷新收益。若一条路径能够覆盖较长时间未被观测的区域，则其观测时效性收益较高；若路径主要覆盖刚刚观测过的区域，则该项收益较低。通过该机制，USV不会机械地重复访问刚搜索过的位置，也不会长期忽略旧观测已经失效的区域，从而在局部线索追踪、剩余目标分布维护和区域刷新之间形成更稳定的搜索行为。需要说明的是，本文并不求解完整的persistent monitoring或Age of Information优化问题，观测时效性仅作为路径评分阶段的刷新收益项使用，不改变GP clue场、目标强度场和综合信息价值场的定义。"
    )

    # Shift citations after section 3.3 and before the reference list.
    for idx in range(sec33_end, ref_start):
        text = paragraphs[idx].text
        new_text = shift_existing_later_citations(text)
        if new_text != text:
            set_paragraph_text(paragraphs[idx], new_text)

    ref_paragraphs = [
        paragraph
        for paragraph in paragraphs
        if re.match(r"^\[\d+\]\s+", paragraph.text.strip())
    ]
    while len(ref_paragraphs) < len(REFERENCES):
        ref_paragraphs.append(doc.add_paragraph())
    for num, entry in enumerate(REFERENCES, start=1):
        set_paragraph_text(ref_paragraphs[num - 1], f"[{num}] {entry}")

    doc.save(REPORT_PATH)
    print(f"backup={backup}")
    print(f"updated={REPORT_PATH}")


if __name__ == "__main__":
    main()
