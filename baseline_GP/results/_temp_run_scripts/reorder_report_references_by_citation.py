# -*- coding: utf-8 -*-
"""Reorder my_report references and fix body citation numbers by citation order."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document


REPORT_PATH = Path(r"F:\pythonprojects\my_report.docx")


REFERENCES_BY_NEW_NUMBER = [
    "Rasmussen C E, Williams C K I. Gaussian Processes for Machine Learning[M]. Cambridge, MA: MIT Press, 2006.",
    "Auer, P., Cesa-Bianchi, N., & Fischer, P. (2002). Finite-time analysis of the multiarmed bandit problem. Machine Learning, 47(2-3), 235-256.",
    "Srinivas, N., Krause, A., Kakade, S. M., & Seeger, M. (2010). Gaussian process optimization in the bandit setting: No regret and experimental design. In Proceedings of the 27th International Conference on Machine Learning (ICML) (pp. 1015-1022).",
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


def replace_once(text: str, old: str, new: str) -> str:
    idx = text.find(old)
    if idx < 0:
        return text
    return text[:idx] + new + text[idx + len(old) :]


def set_paragraph_text(paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def main() -> None:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(REPORT_PATH)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_PATH.with_name(
        f"my_report_backup_before_reference_reorder_{stamp}.docx"
    )
    shutil.copy2(REPORT_PATH, backup)

    doc = Document(REPORT_PATH)
    ref_start = None
    for idx, paragraph in enumerate(doc.paragraphs):
        if re.match(r"^\[\d+\]\s+", paragraph.text.strip()):
            ref_start = idx
            break
    if ref_start is None:
        raise RuntimeError("No numbered reference list found.")

    # Fix body citation semantics before rebuilding the reference list.
    for idx, paragraph in enumerate(doc.paragraphs[:ref_start]):
        text = paragraph.text
        if idx == 64 and "[1]" in text:
            # Rasmussen remains the first cited reference.
            continue
        if idx == 89:
            text = text.replace("平衡[1]。在高斯过程", "平衡[2]。在高斯过程")
            text = text.replace("不确定性[2]。本文", "不确定性[3]。本文")
        elif idx == 165:
            text = text.replace("[8]", "[4]")
        elif idx == 168:
            text = text.replace("[9]", "[5]")
        elif idx in (175, 178):
            text = text.replace("[10]", "[6]")
        elif idx == 215:
            text = text.replace("[11]", "[7]")
        elif idx == 224:
            text = text.replace("[12-14]", "[8-10]")
            text = text.replace("[15]", "[11]")
        if text != paragraph.text:
            set_paragraph_text(paragraph, text)

    ref_paragraphs = []
    for paragraph in doc.paragraphs[ref_start:]:
        if re.match(r"^\[\d+\]\s+", paragraph.text.strip()):
            ref_paragraphs.append(paragraph)
    if len(ref_paragraphs) < len(REFERENCES_BY_NEW_NUMBER):
        raise RuntimeError(
            f"Expected at least {len(REFERENCES_BY_NEW_NUMBER)} reference paragraphs, "
            f"found {len(ref_paragraphs)}."
        )

    for new_num, entry in enumerate(REFERENCES_BY_NEW_NUMBER, start=1):
        set_paragraph_text(ref_paragraphs[new_num - 1], f"[{new_num}] {entry}")

    doc.save(REPORT_PATH)
    print(f"backup={backup}")
    print(f"updated={REPORT_PATH}")


if __name__ == "__main__":
    main()
