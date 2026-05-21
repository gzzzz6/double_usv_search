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


def add_formula_box(slide, x, y, w, h, title, formula, note, accent):
    add_rect(slide, x, y, w, h, fill=WHITE, line=rgb("#B8CFEA"), radius=True, weight=1.0)
    add_round_label(slide, title, x + 10, y + 9, 104, 21, fill=accent, size=9.8)
    add_text(slide, formula, x + 124, y + 8, w - 136, 24, size=13.3, color=accent, bold=True)
    add_text(slide, note, x + 16, y + 38, w - 28, h - 44, size=9.2, color=INK)


def add_update_step(slide, x, y, w, h, num, title, body, accent, fill):
    add_rect(slide, x, y, w, h, fill=fill, line=accent, radius=True, weight=1.0)
    add_circle(slide, x + 11, y + 11, 25, fill=WHITE, line=accent, weight=1.2)
    add_text(slide, num, x + 18, y + 17, 10, 10, size=8.8, color=accent, bold=True, align=PpAlignCenter)
    add_text(slide, title, x + 45, y + 9, w - 56, 17, size=11.2, color=accent, bold=True)
    add_text(slide, body, x + 45, y + 31, w - 58, h - 38, size=8.8, color=INK)


def add_update_row(slide, x, y, w, h, num, title, formula, note, accent, fill):
    add_rect(slide, x, y, w, h, fill=fill, line=accent, radius=True, weight=1.0)
    add_circle(slide, x + 12, y + 10, 24, fill=WHITE, line=accent, weight=1.2)
    add_text(slide, num, x + 19, y + 16, 10, 10, size=8.5, color=accent, bold=True, align=PpAlignCenter)
    add_text(slide, title, x + 45, y + 8, 76, 15, size=10.5, color=accent, bold=True)
    add_text(slide, formula, x + 127, y + 8, w - 138, 15, size=10.1, color=accent, bold=True)
    add_text(slide, note, x + 45, y + 26, w - 58, h - 31, size=8.2, color=INK)


def add_vertical_flow(slide, x, y1, y2, color):
    add_arrow(slide, x, y1, x, y2, color=color, weight=1.4)


def rebuild_slide8(pptx_path: Path, logo_path: Path | None) -> Path:
    import win32com.client  # type: ignore

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = pptx_path.with_name(f"{pptx_path.stem}_backup_before_slide8_intensity_recency_{timestamp}.pptx")
    shutil.copy2(pptx_path, backup_path)

    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = 1
        presentation = app.Presentations.Open(str(pptx_path), ReadOnly=0, Untitled=0, WithWindow=0)
        slide = presentation.Slides(8)
        clear_slide(slide)
        slide.Layout = PpLayoutBlank
        slide.FollowMasterBackground = MsoTriStateFalse
        slide.Background.Fill.ForeColor.RGB = WHITE

        add_header(slide, logo_path, "多源搜索状态建模", "目标存在信念与观测时效建模")
        add_text(
            slide,
            "本页说明两类非 GP 状态场：Intensity 维护“剩余未发现目标还可能在哪里”，Recency/Staleness 维护“哪些区域太久没有被观测”。",
            56,
            116,
            850,
            18,
            size=12.1,
            color=MUTED,
        )

        # Left panel: Intensity.
        add_rect(slide, 47, 149, 415, 302, fill=rgb("#F8FFFB"), line=rgb("#93C7AA"), radius=True, weight=1.25)
        add_round_label(slide, "1. Intensity：剩余目标存在信念", 72, 166, 190, 25, fill=GREEN, size=11.4)
        add_text(slide, "语义：空间格 x 上仍存在未发现目标的相对可能性", 280, 171, 145, 15, size=9.2, color=MUTED)

        add_formula_box(
            slide,
            72,
            204,
            346,
            58,
            "总质量约束",
            "Σ I_t(x) = N_remain",
            "N_remain = N_total - N_found；发现目标后，信念总量随剩余目标数减少。",
            GREEN,
        )

        add_update_row(
            slide,
            72,
            278,
            346,
            38,
            "A",
            "运动预测",
            "I_t → I_t+1",
            "static 保持分布；random_walk 向相邻自由格扩散。",
            GREEN,
            rgb("#EAF6EF"),
        )
        add_update_row(
            slide,
            72,
            323,
            346,
            38,
            "B",
            "未命中更新",
            "I(x) ← I(x)·(1-p_detect)",
            "传感器覆盖区域信念下降，随后保持剩余目标总质量一致。",
            BLUE,
            rgb("#EEF5FF"),
        )
        add_update_row(
            slide,
            72,
            368,
            346,
            38,
            "C",
            "命中更新",
            "hit 邻域置零",
            "已发现目标从剩余信念中剔除，N_remain 减少后重归一化。",
            ORANGE,
            rgb("#FFF5E8"),
        )
        add_vertical_flow(slide, 245, 317, 322, GREEN)
        add_vertical_flow(slide, 245, 362, 367, GREEN)

        add_rect(slide, 72, 416, 346, 22, fill=PALE_GREEN, line=GREEN, radius=True, weight=1.0)
        add_text(slide, "澄清：命中不是增强该区域，而是剔除已发现目标并重分配剩余质量。", 91, 422, 306, 10, size=8.0, color=GREEN, bold=True, align=PpAlignCenter)

        # Right panel: Recency / staleness.
        add_rect(slide, 498, 149, 415, 302, fill=rgb("#FFFCF7"), line=rgb("#E4B363"), radius=True, weight=1.25)
        add_round_label(slide, "2. Recency / Staleness：观测时效", 523, 166, 206, 25, fill=ORANGE, size=11.4)
        add_text(slide, "语义：区域距离上一次被观测已经过去多久", 748, 171, 130, 15, size=9.2, color=MUTED)

        add_formula_box(
            slide,
            523,
            204,
            346,
            58,
            "状态记录",
            "last_seen(x) ← t",
            "USV 传感器覆盖到自由格 x 时，记录该格最近一次被观测的仿真步。",
            ORANGE,
        )

        add_rect(slide, 523, 279, 346, 80, fill=WHITE, line=rgb("#E9C992"), radius=True, weight=1.0)
        add_round_label(slide, "时效计算", 538, 291, 78, 21, fill=ORANGE, size=9.8)
        add_text(slide, "S_t(x)=clip(Δt/τ, 0, 1)", 631, 290, 208, 21, size=12.5, color=ORANGE, bold=True)
        add_text(slide, "Δt = t-last_seen(x)，τ = 12；越久未观测，S_t(x) 越接近 1；障碍格为 0，未观测过的自由格保持最高刷新价值。", 540, 322, 305, 22, size=8.4, color=INK)

        add_rect(slide, 523, 377, 346, 50, fill=PALE_ORANGE, line=ORANGE, radius=True, weight=1.0)
        add_text(slide, "进入决策", 540, 391, 74, 14, size=10.7, color=ORANGE, bold=True)
        add_text(
            slide,
            "Recency 不直接并入 search_info_map，而是在路径段评分中形成 recency_bias，鼓励覆盖长期未观测区域。",
            615,
            386,
            230,
            28,
            size=8.8,
            color=INK,
        )

        # A compact visual bridge between the two panels.
        add_plain_line(slide, 480, 188, 480, 421, color=rgb("#D1DBEA"), weight=1.0, dashed=True)
        add_circle(slide, 468, 256, 24, fill=rgb("#F7FAFF"), line=LINE, weight=1.0)
        add_text(slide, "≠", 474, 260, 12, 10, size=10.5, color=NAVY_DARK, bold=True, align=PpAlignCenter)
        add_text(slide, "概率语义不同", 455, 286, 52, 12, size=7.8, color=MUTED, bold=True, align=PpAlignCenter)

        # Bottom conclusion.
        add_rect(slide, 84, 469, 792, 45, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
        add_text(slide, "页面结论", 112, 482, 82, 17, size=12.8, color=WHITE, bold=True)
        add_text(
            slide,
            "Intensity 回答“剩余目标可能在哪里”；Recency 回答“哪里需要重新看”。本文最终以 GP Clue + Intensity 构成 search_info_map，并把 Recency 作为路径段刷新收益。",
            198,
            479,
            640,
            21,
            size=10.3,
            color=WHITE,
            bold=True,
        )
        add_text(slide, "8", 895, 506, 20, 12, size=9.0, color=rgb("#808080"), align=PpAlignCenter)

        presentation.Save()
        return backup_path
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: rebuild_slide8_intensity_recency.py <pptx_path> [logo_path]")
    pptx_path = Path(sys.argv[1])
    logo_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    backup_path = rebuild_slide8(pptx_path, logo_path)
    print(f"UPDATED_SLIDE=8 PPTX={pptx_path} BACKUP={backup_path}")


if __name__ == "__main__":
    main()
