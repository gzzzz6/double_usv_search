# -*- coding: utf-8 -*-
"""Write anomaly literature grounding into section 3.1.6 of my_report.docx."""

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


def find_section(paragraphs, start_prefix: str, end_prefix: str) -> tuple[int, int]:
    start = None
    for idx, paragraph in enumerate(paragraphs):
        if paragraph.text.strip().startswith(start_prefix):
            start = idx
            break
    if start is None:
        raise RuntimeError(f"Section {start_prefix!r} not found.")
    for idx in range(start + 1, len(paragraphs)):
        if paragraphs[idx].text.strip().startswith(end_prefix):
            return start, idx
    raise RuntimeError(f"Section end {end_prefix!r} not found.")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_PATH.with_name(
        f"my_report_backup_before_anomaly_literature_{stamp}.docx"
    )
    shutil.copy2(REPORT_PATH, backup)

    doc = Document(REPORT_PATH)
    paragraphs = doc.paragraphs
    sec_start, sec_end = find_section(paragraphs, "3.1.6", "3.2")
    section = paragraphs[sec_start:sec_end]
    if len(section) < 14:
        raise RuntimeError(f"Unexpected 3.1.6 paragraph count: {len(section)}")

    # Keep existing formula paragraphs intact: section[4], [6], [9], [11], [12].
    set_paragraph_text(
        section[1],
        "在基于高斯过程（GP）的环境建模中，标准采集函数通常根据后验均值与后验不确定性构造，如上置信界形式（UCB）。此类方法能够在高均值区域利用与高不确定区域探索之间取得平衡。然而，在可疑目标搜索任务中，系统关注的并不只是整体线索场的平滑估计，也包括对异常偏高线索区域、局部高响应区域和潜在可疑热点的敏感性。在环境探索与监测任务中，Blanchard和Sapsis指出，信息型路径规划可以显式面向异常检测目标，而不只是最大化一般意义上的环境信息收益[4]。受此思想启发，本文在标准UCB采集函数基础上引入anomaly-aware变体，用于提高搜索策略对高值上尾区域的响应能力。"
    )
    set_paragraph_text(
        section[2],
        "高值上尾区域可通过分位数进行刻画。Rayas Fernández等在面向环境分析的信息路径规划研究中指出，当任务关注环境变量的高响应或极端区域时，高分位数可以作为重要估计对象[5]。因此，本文不采用固定绝对阈值定义异常区域，而是在当前自由区域内根据GP后验均值分布自适应确定上尾阈值。这种相对分位阈值能够随当前环境线索估计状态变化，更适合不同地图和不同搜索阶段下的可疑线索场建模。"
    )
    set_paragraph_text(
        section[3],
        "设自由区域为Ωfree，上尾分位参数为q。为了识别当前后验分布中的高值上尾区域，本文首先在自由区域内根据GP后验均值分布定义上尾阈值："
    )
    set_paragraph_text(
        section[5],
        "其中，q为上尾分位参数。与此相关，Fossum等在自主海洋采样研究中关注高斯随机场超过阈值的excursion set学习问题[6]，Gotovos等则研究了高斯过程模型下通过主动采样识别函数值超过给定阈值区域的level set estimation问题[7]。这类研究表明，在空间环境建模中，超过某一阈值的区域本身可以成为主动观测和路径规划关注的对象。基于这一思想，本文计算每个自由位置属于当前高值上尾区域的概率："
    )
    set_paragraph_text(
        section[7],
        "其中，p_anom(x)表示位置x处属于当前高值上尾区域的概率，其值越大，说明该位置越可能属于当前后验分布中的异常偏高区域。需要说明的是，本文并不直接求解excursion set或level set分类问题，也未直接采用已有异常检测型信息路径规划中的采集函数。本文将上述思想转化为GP线索采集层的空间加权机制，即将异常上尾概率转化为UCB采集图的加权因子："
    )
    set_paragraph_text(
        section[8],
        "下一步则在此基础上构造anomaly权重："
    )
    set_paragraph_text(
        section[10],
        "其中，λ为异常强调系数。本文实验中设置q=0.90、λ=1.0，即将当前自由区域内GP后验均值的前10%高值区域作为异常上尾参照，并使异常权重保持在相对温和的范围内。最终得到的anomaly-aware采集函数为："
    )
    set_paragraph_text(
        section[13],
        "用此方法构造的anomaly权重保留了UCB在“高均值利用”与“不确定性探索”之间的基本平衡，同时对更可能属于高值上尾的区域给予额外强调。由此得到的anomaly-aware采集图随后进入综合信息价值场，并由后续路径规划模块使用。该机制只改变GP clue planner map的生成方式，不改变目标强度场、recency场、路径评分函数、避障约束和双艇协同分配逻辑。因此，本文的anomaly-aware acquisition不是对已有anomaly IPP、quantile estimation、excursion set estimation或level set estimation方法的直接复现，而是在这些研究思想启发下，面向本文可疑目标搜索任务构造的线索采集层加权机制。"
    )

    # Shift existing citations after 3.1.6 by four slots because [4]-[7] are new.
    for idx, paragraph in enumerate(paragraphs):
        if idx <= sec_end:
            continue
        text = paragraph.text
        new_text = text
        new_text = new_text.replace("[8-10]", "[12-14]")
        new_text = new_text.replace("[11]", "[15]")
        new_text = new_text.replace("[10]", "[14]")
        new_text = new_text.replace("[9]", "[13]")
        new_text = new_text.replace("[8]", "[12]")
        new_text = new_text.replace("[7]", "[11]")
        new_text = new_text.replace("[6]", "[10]")
        new_text = new_text.replace("[5]", "[9]")
        new_text = new_text.replace("[4]", "[8]")
        if new_text != text:
            set_paragraph_text(paragraph, new_text)

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
