from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

from insert_state_modeling_slides import (
    BLUE,
    GREEN,
    INK,
    LINE,
    MUTED,
    NAVY,
    NAVY_DARK,
    ORANGE,
    PALE_BLUE,
    PALE_GREEN,
    PALE_ORANGE,
    WHITE,
    add_arrow,
    add_circle,
    add_header,
    add_plain_line,
    add_rect,
    add_round_label,
    add_text,
    rgb,
)


PpLayoutBlank = 12
MsoTriStateFalse = 0
PpAlignCenter = 2


def clear_slide(slide) -> None:
    for idx in range(int(slide.Shapes.Count), 0, -1):
        slide.Shapes(idx).Delete()


def add_step_box(slide, x, y, w, h, label, title, body, accent):
    add_rect(slide, x, y, w, h, fill=WHITE, line=rgb("#B8CFEA"), radius=True, weight=1.05)
    add_circle(slide, x + 12, y + 12, 28, fill=rgb("#F7FAFF"), line=accent, weight=1.2)
    add_text(slide, label, x + 20, y + 18, 12, 12, size=9.5, color=accent, bold=True, align=PpAlignCenter)
    add_text(slide, title, x + 50, y + 9, w - 62, 18, size=12.2, color=accent, bold=True)
    add_text(slide, body, x + 50, y + 31, w - 64, h - 38, size=9.4, color=INK)


def add_small_badge(slide, text, x, y, fill, width=72):
    add_round_label(slide, text, x, y, width, 22, fill=fill, size=9.5)


def rebuild_slide7(pptx_path: Path, logo_path: Path | None) -> Path:
    import win32com.client  # type: ignore

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = pptx_path.with_name(f"{pptx_path.stem}_backup_before_slide7_gp_anomaly_{timestamp}.pptx")
    shutil.copy2(pptx_path, backup_path)

    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = 1
        presentation = app.Presentations.Open(str(pptx_path), ReadOnly=0, Untitled=0, WithWindow=0)
        slide = presentation.Slides(7)
        clear_slide(slide)
        slide.Layout = PpLayoutBlank
        slide.FollowMasterBackground = MsoTriStateFalse
        slide.Background.Fill.ForeColor.RGB = WHITE

        add_header(slide, logo_path, "多源搜索状态建模", "基于 GP 的线索场估计与 anomaly-aware 加权")
        add_text(
            slide,
            "用局部带噪 clue 观测构建 GP 后验，再以 UCB 平衡线索强度与不确定性；anomaly-aware 作为上尾加权优化方案。",
            56,
            116,
            850,
            18,
            size=12.4,
            color=MUTED,
        )

        # Left panel: GP algorithm details.
        add_rect(slide, 48, 150, 552, 276, fill=rgb("#F8FBFF"), line=rgb("#B5CBE8"), radius=True, weight=1.25)
        add_round_label(slide, "1. 高斯过程后验估计 GP Clue", 76, 168, 214, 25, fill=NAVY, size=11.6)
        add_text(
            slide,
            "目标：由有限观测点推断整张自由水域上的 clue 后验场",
            308,
            171,
            250,
            16,
            size=10.2,
            color=MUTED,
        )

        add_step_box(
            slide,
            72,
            207,
            154,
            82,
            "D",
            "局部带噪观测",
            "D = {(x_i, y_i)}\nx_i：空间位置\ny_i：clue 观测值",
            BLUE,
        )
        add_step_box(
            slide,
            255,
            207,
            154,
            82,
            "K",
            "GP 先验假设",
            "f(x) ~ GP(0, k)\nRBF 核：相近位置相关\n白噪声项：观测误差",
            GREEN,
        )
        add_step_box(
            slide,
            438,
            207,
            134,
            82,
            "P",
            "后验输出",
            "μ(x)：线索强度估计\nσ(x)：未观测不确定性",
            NAVY_DARK,
        )
        add_arrow(slide, 229, 248, 252, 248, color=LINE, weight=1.8)
        add_arrow(slide, 412, 248, 435, 248, color=LINE, weight=1.8)

        add_rect(slide, 92, 319, 468, 48, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
        add_text(slide, "UCB(x) = μ(x) + βσ(x)，β = 0.5", 118, 331, 416, 22, size=18.5, color=WHITE, bold=True, align=PpAlignCenter)
        add_text(slide, "μ(x) 高：已观测线索强", 116, 377, 160, 15, size=10.2, color=BLUE, bold=True)
        add_text(slide, "σ(x) 高：区域仍不确定", 302, 377, 160, 15, size=10.2, color=GREEN, bold=True)
        add_text(slide, "UCB 同时兼顾利用与探索", 450, 377, 120, 15, size=10.2, color=NAVY_DARK, bold=True, align=PpAlignCenter)

        # Right panel: anomaly-aware.
        add_rect(slide, 622, 150, 290, 276, fill=rgb("#FFFCF7"), line=rgb("#E4B363"), radius=True, weight=1.25)
        add_round_label(slide, "2. anomaly-aware 上尾加权", 650, 168, 176, 25, fill=ORANGE, size=11.4)
        add_text(
            slide,
            "在 GP-UCB 基础上，进一步强化后验高值区域的搜索倾向。",
            652,
            204,
            220,
            29,
            size=10.8,
            color=INK,
        )

        add_small_badge(slide, "上尾区域", 652, 249, ORANGE, width=72)
        add_text(slide, "按 UCB 分布选取 quantile = 0.90 的高值区域", 736, 251, 145, 22, size=9.2, color=INK)
        add_plain_line(slide, 688, 277, 688, 295, color=ORANGE, weight=1.4)
        add_small_badge(slide, "权重图", 652, 300, ORANGE, width=72)
        add_text(slide, "构造 anomaly_weight_map，强度 λ = 1.25", 736, 302, 145, 22, size=9.2, color=INK)
        add_plain_line(slide, 688, 328, 688, 346, color=ORANGE, weight=1.4)
        add_rect(slide, 652, 351, 226, 39, fill=PALE_ORANGE, line=ORANGE, radius=True, weight=1.0)
        add_text(slide, "anomaly_acq_map = UCB × anomaly_weight_map", 662, 361, 206, 16, size=9.8, color=ORANGE, bold=True, align=PpAlignCenter)

        add_rect(slide, 652, 397, 226, 18, fill=WHITE, line=rgb("#E9C992"), radius=True, weight=0.8)
        add_text(slide, "不是目标存在概率，而是 GP 后验上尾启发式加权", 660, 402, 210, 8, size=7.8, color=INK, bold=True, align=PpAlignCenter)

        # Bottom takeaway.
        add_rect(slide, 86, 451, 790, 46, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
        add_text(slide, "页面结论", 112, 463, 90, 18, size=13.2, color=WHITE, bold=True)
        add_text(
            slide,
            "GP-UCB 提供“线索强度 + 不确定性”的基础信息图；anomaly-aware 在其上强化后验高值区域，用作对比优化方案。",
            205,
            463,
            640,
            18,
            size=11.1,
            color=WHITE,
            bold=True,
        )
        add_rect(slide, 170, 505, 620, 20, fill=PALE_BLUE, line=rgb("#C6D9F2"), radius=True, weight=0.8)
        add_text(
            slide,
            "边界：该页只描述 GP clue 信息图的构建；目标存在信念由 Intensity 建模，观测时效由 Recency 建模。",
            188,
            510,
            584,
            8,
            size=7.8,
            color=INK,
            bold=True,
            align=PpAlignCenter,
        )

        presentation.Save()
        return backup_path
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: rebuild_slide7_gp_anomaly.py <pptx_path> [logo_path]")
    pptx_path = Path(sys.argv[1])
    logo_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    backup_path = rebuild_slide7(pptx_path, logo_path)
    print(f"UPDATED_SLIDE=7 PPTX={pptx_path} BACKUP={backup_path}")


if __name__ == "__main__":
    main()
