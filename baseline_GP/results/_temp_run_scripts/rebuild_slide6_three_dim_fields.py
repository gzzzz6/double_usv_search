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


def add_limitation_card(slide, x, y, title, body, accent):
    add_rect(slide, x, y, 318, 64, fill=WHITE, line=rgb("#C8D8EE"), radius=True, weight=1.1)
    add_rect(slide, x, y, 7, 64, fill=accent, line=accent, radius=False, weight=0)
    add_text(slide, title, x + 20, y + 8, 270, 17, size=12.8, color=accent, bold=True)
    add_text(slide, body, x + 20, y + 30, 278, 24, size=10.2, color=INK)


def add_dimension_card(slide, x, y, title, subtitle, question, accent, letter):
    add_rect(slide, x, y, 230, 102, fill=rgb("#F7FAFF"), line=rgb("#AFC9EA"), radius=True, weight=1.2)
    add_circle(slide, x + 18, y + 17, 44, fill=WHITE, line=accent, weight=1.4)
    add_text(slide, letter, x + 29, y + 26, 22, 18, size=16, color=accent, bold=True, align=PpAlignCenter)
    add_text(slide, title, x + 76, y + 16, 130, 21, size=15.5, color=accent, bold=True)
    add_text(slide, subtitle, x + 76, y + 43, 130, 18, size=11.8, color=INK, bold=True)
    add_text(slide, question, x + 22, y + 72, 188, 20, size=10.5, color=MUTED)


def add_dimension_row(slide, x, y, title, subtitle, question, accent, letter):
    add_rect(slide, x, y, 306, 52, fill=WHITE, line=rgb("#AFC9EA"), radius=True, weight=1.05)
    add_circle(slide, x + 12, y + 9, 34, fill=rgb("#F7FAFF"), line=accent, weight=1.25)
    add_text(slide, letter, x + 21, y + 16, 16, 16, size=13.5, color=accent, bold=True, align=PpAlignCenter)
    add_text(slide, title, x + 58, y + 8, 95, 17, size=13.5, color=accent, bold=True)
    add_text(slide, subtitle, x + 162, y + 8, 118, 17, size=11.2, color=INK, bold=True)
    add_text(slide, question, x + 58, y + 31, 225, 13, size=9.2, color=MUTED)


def rebuild_slide6(pptx_path: Path, logo_path: Path | None) -> Path:
    import win32com.client  # type: ignore

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = pptx_path.with_name(f"{pptx_path.stem}_backup_before_slide6_three_dim_{timestamp}.pptx")
    shutil.copy2(pptx_path, backup_path)

    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = 1
        presentation = app.Presentations.Open(str(pptx_path), ReadOnly=0, Untitled=0, WithWindow=0)
        slide = presentation.Slides(6)
        clear_slide(slide)
        slide.Layout = PpLayoutBlank
        slide.FollowMasterBackground = MsoTriStateFalse
        slide.Background.Fill.ForeColor.RGB = WHITE

        add_header(slide, logo_path, "多源搜索状态建模", "为什么需要三维互补的信息场体系？")
        add_text(
            slide,
            "海上搜索中观测有限且带噪，单一信息源难以同时表达线索强度、目标存在信念与观测刷新需求。",
            56,
            116,
            848,
            20,
            size=13.2,
            color=MUTED,
        )

        # Left panel: why one field is not enough.
        add_rect(slide, 58, 160, 378, 252, fill=rgb("#F8FBFF"), line=rgb("#B5CBE8"), radius=True, weight=1.3)
        add_round_label(slide, "单一信息源的局限", 92, 177, 150, 28, fill=NAVY, size=13)
        add_limitation_card(
            slide,
            78,
            216,
            "仅依赖 GP Clue",
            "可推断线索热点，但受采样稀疏、观测噪声和 GP 平滑影响。",
            BLUE,
        )
        add_limitation_card(
            slide,
            78,
            286,
            "仅依赖 Intensity",
            "可利用命中/未命中反馈，但难以表达未观测区域的线索外推。",
            GREEN,
        )
        add_limitation_card(
            slide,
            78,
            356,
            "仅依赖 Recency",
            "可提示长期未观测区域，但不表示目标概率或线索强度。",
            ORANGE,
        )

        # Right panel: three complementary dimensions.
        add_rect(slide, 524, 160, 378, 252, fill=rgb("#F8FBFF"), line=rgb("#B5CBE8"), radius=True, weight=1.3)
        add_round_label(slide, "三维互补建模", 558, 177, 138, 28, fill=NAVY_DARK, size=13)
        add_dimension_row(
            slide,
            560,
            222,
            "GP Clue",
            "线索场估计",
            "哪里有线索，哪里不确定？",
            BLUE,
            "G",
        )
        add_dimension_row(
            slide,
            560,
            288,
            "Intensity",
            "目标存在信念",
            "探测反馈后哪里仍值得搜索？",
            GREEN,
            "I",
        )
        add_dimension_row(
            slide,
            560,
            354,
            "Recency",
            "观测时效性",
            "哪里太久没看，需要刷新？",
            ORANGE,
            "R",
        )
        add_arrow(slide, 442, 286, 515, 286, color=LINE, weight=2.0)
        add_text(slide, "互补", 466, 258, 44, 16, size=11.5, color=LINE, bold=True, align=PpAlignCenter)

        # Bottom: implementation relationship.
        add_rect(slide, 120, 428, 720, 65, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
        add_text(slide, "代码实现中的融合关系", 150, 443, 178, 22, size=14.5, color=WHITE, bold=True)
        add_text(
            slide,
            "GP Clue + Intensity → search_info_map",
            330,
            439,
            245,
            18,
            size=11.8,
            color=WHITE,
            bold=True,
        )
        add_text(slide, "Recency → recency_bias → 路径段评分", 590, 439, 220, 18, size=11.8, color=WHITE, bold=True)
        add_text(
            slide,
            "search_info_map = 0.5 × norm(GP Clue) + 0.5 × norm(Intensity)",
            330,
            467,
            470,
            14,
            size=10.8,
            color=rgb("#D8E8FF"),
        )
        add_rect(slide, 120, 501, 720, 24, fill=PALE_ORANGE, line=ORANGE, radius=True, weight=0.8)
        add_text(
            slide,
            "注意：Recency 不直接并入 search_info_map，而是在路径段评分中体现观测刷新收益。",
            148,
            507,
            660,
            11,
            size=9.2,
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
        raise SystemExit("Usage: rebuild_slide6_three_dim_fields.py <pptx_path> [logo_path]")
    pptx_path = Path(sys.argv[1])
    logo_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    backup_path = rebuild_slide6(pptx_path, logo_path)
    print(f"UPDATED_SLIDE=6 PPTX={pptx_path} BACKUP={backup_path}")


if __name__ == "__main__":
    main()
