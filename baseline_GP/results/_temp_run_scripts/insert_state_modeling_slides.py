from __future__ import annotations

import math
import sys
from pathlib import Path


def rgb(hex_value: str) -> int:
    value = hex_value.strip().lstrip("#")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r | (g << 8) | (b << 16)


NAVY = rgb("#2F5797")
NAVY_DARK = rgb("#1D3F78")
BLUE = rgb("#006FBE")
MID_BLUE = rgb("#5C96E8")
LIGHT_BLUE = rgb("#DCE9F9")
PALE_BLUE = rgb("#EEF5FF")
INK = rgb("#1C2E47")
MUTED = rgb("#5C6A7A")
LINE = rgb("#4F82C3")
GREEN = rgb("#2E7D58")
PALE_GREEN = rgb("#E8F4EC")
ORANGE = rgb("#D97706")
PALE_ORANGE = rgb("#FFF3E2")
GRAY_BG = rgb("#EEF2F7")
WHITE = rgb("#FFFFFF")
BLACK = rgb("#000000")


MsoTextOrientationHorizontal = 1
MsoShapeRectangle = 1
MsoShapeRoundedRectangle = 5
MsoShapeOval = 9
MsoShapeArc = 25
MsoShapeRightArrow = 33
MsoConnectorStraight = 1
MsoConnectorElbow = 2
MsoTriStateTrue = -1
MsoTriStateFalse = 0
PpLayoutBlank = 12
PpAlignLeft = 1
PpAlignCenter = 2
PpAlignRight = 3
MsoAnchorTop = 1
MsoAnchorMiddle = 3


def set_text_style(shape, size=16, color=INK, bold=False, align=PpAlignLeft, font="微软雅黑"):
    tr = shape.TextFrame.TextRange
    tr.Font.Name = font
    tr.Font.NameFarEast = font
    tr.Font.Size = size
    tr.Font.Color.RGB = color
    tr.Font.Bold = MsoTriStateTrue if bold else MsoTriStateFalse
    tr.ParagraphFormat.Alignment = align


def add_text(slide, text, x, y, w, h, size=16, color=INK, bold=False, align=PpAlignLeft):
    shape = slide.Shapes.AddTextbox(MsoTextOrientationHorizontal, x, y, w, h)
    shape.TextFrame.TextRange.Text = text
    shape.TextFrame.MarginLeft = 0
    shape.TextFrame.MarginRight = 0
    shape.TextFrame.MarginTop = 0
    shape.TextFrame.MarginBottom = 0
    shape.TextFrame.WordWrap = MsoTriStateTrue
    set_text_style(shape, size=size, color=color, bold=bold, align=align)
    return shape


def add_rect(slide, x, y, w, h, fill=WHITE, line=LINE, radius=True, weight=1.2, transparency=0):
    shape_type = MsoShapeRoundedRectangle if radius else MsoShapeRectangle
    shape = slide.Shapes.AddShape(shape_type, x, y, w, h)
    shape.Fill.ForeColor.RGB = fill
    shape.Fill.Transparency = transparency
    shape.Line.ForeColor.RGB = line
    shape.Line.Weight = weight
    return shape


def add_circle(slide, x, y, d, fill=LIGHT_BLUE, line=LINE, weight=1.2):
    shape = slide.Shapes.AddShape(MsoShapeOval, x, y, d, d)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.ForeColor.RGB = line
    shape.Line.Weight = weight
    return shape


def add_arrow(slide, x1, y1, x2, y2, color=LINE, weight=2.0, dashed=False):
    conn = slide.Shapes.AddConnector(MsoConnectorStraight, x1, y1, x2, y2)
    conn.Line.ForeColor.RGB = color
    conn.Line.Weight = weight
    conn.Line.EndArrowheadStyle = 3
    if dashed:
        conn.Line.DashStyle = 4
    return conn


def add_plain_line(slide, x1, y1, x2, y2, color=LINE, weight=1.2, dashed=False):
    conn = slide.Shapes.AddConnector(MsoConnectorStraight, x1, y1, x2, y2)
    conn.Line.ForeColor.RGB = color
    conn.Line.Weight = weight
    if dashed:
        conn.Line.DashStyle = 4
    return conn


def add_round_label(slide, text, x, y, w, h, fill=NAVY, color=WHITE, size=13, bold=True):
    rect = add_rect(slide, x, y, w, h, fill=fill, line=fill, radius=True, weight=0)
    rect.TextFrame.TextRange.Text = text
    rect.TextFrame.VerticalAnchor = MsoAnchorMiddle
    rect.TextFrame.MarginLeft = 5
    rect.TextFrame.MarginRight = 5
    rect.TextFrame.MarginTop = 1
    rect.TextFrame.MarginBottom = 1
    set_text_style(rect, size=size, color=color, bold=bold, align=PpAlignCenter)
    return rect


def add_header(slide, logo_path: Path | None, section_title: str, page_title: str):
    add_rect(slide, 0, 0, 960, 61.7, fill=NAVY, line=NAVY, radius=False, weight=0)
    if logo_path is not None and logo_path.exists():
        try:
            slide.Shapes.AddPicture(str(logo_path), False, True, 13.65, 7.8, 46.15, 46.15)
        except Exception:
            pass

    add_text(slide, section_title, 70, 12.5, 345, 38, size=25, color=WHITE, bold=True)
    nav_items = [
        ("背景和意义", 443.8),
        ("总体技术路线", 543.6),
        ("思路和内容", 643.5),
        ("过程和方法", 743.4),
        ("成果与展望", 843.3),
    ]
    for text, x in nav_items:
        add_text(slide, text, x, 18.0, 94, 24, size=13.5, color=WHITE, bold=True, align=PpAlignCenter)
    add_plain_line(slide, 646, 45.2, 733, 45.2, color=WHITE, weight=1.3)

    add_rect(slide, 0, 61.7, 960, 43.65, fill=GRAY_BG, line=GRAY_BG, radius=False, weight=0)
    add_text(slide, "➢", 32.8, 72.0, 24, 24, size=19, color=NAVY_DARK, bold=True)
    add_text(slide, page_title, 75, 67.5, 835, 34, size=24, color=NAVY_DARK, bold=True)


def add_card_header(slide, x, y, w, title, subtitle=None, accent=BLUE, icon_text=None):
    add_rect(slide, x, y, w, 76, fill=WHITE, line=LINE, radius=True, weight=1.2)
    add_rect(slide, x, y, 8, 76, fill=accent, line=accent, radius=False, weight=0)
    if icon_text:
        add_circle(slide, x + 18, y + 17, 42, fill=rgb("#EAF3FF"), line=accent)
        add_text(slide, icon_text, x + 27, y + 25, 24, 22, size=17, color=accent, bold=True, align=PpAlignCenter)
        tx = x + 72
        tw = w - 88
    else:
        tx = x + 20
        tw = w - 34
    add_text(slide, title, tx, y + 13, tw, 22, size=15.5, color=accent, bold=True)
    if subtitle:
        add_text(slide, subtitle, tx, y + 38, tw, 30, size=12.5, color=INK)


def add_mini_grid(slide, x, y, w, h, obstacle_color=rgb("#2D3748"), water_color=rgb("#A7D8F2")):
    cols, rows = 8, 6
    cw, ch = w / cols, h / rows
    for r in range(rows):
        for c in range(cols):
            cell = slide.Shapes.AddShape(MsoShapeRectangle, x + c * cw, y + r * ch, cw - 0.8, ch - 0.8)
            cell.Line.Visible = MsoTriStateFalse
            if (r, c) in {(1, 6), (2, 2), (4, 4), (4, 5)}:
                cell.Fill.ForeColor.RGB = obstacle_color
            else:
                cell.Fill.ForeColor.RGB = water_color
                cell.Fill.Transparency = 0.25
    add_circle(slide, x + 40, y + 38, 52, fill=rgb("#FFFFFF"), line=MID_BLUE)
    add_text(slide, "USV", x + 52, y + 55, 40, 16, size=8.5, color=NAVY_DARK, bold=True, align=PpAlignCenter)


def add_heatmap(slide, x, y, w, h, label=None, hot_bias=(0.65, 0.35), border=True):
    if border:
        add_rect(slide, x - 3, y - 3, w + 6, h + 6, fill=WHITE, line=rgb("#D5E2F0"), radius=True, weight=0.9)
    cols, rows = 12, 7
    cw, ch = w / cols, h / rows
    hx, hy = hot_bias
    for r in range(rows):
        for c in range(cols):
            px = (c + 0.5) / cols
            py = (r + 0.5) / rows
            v = math.exp(-((px - hx) ** 2 / 0.045 + (py - hy) ** 2 / 0.06))
            v += 0.55 * math.exp(-((px - 0.25) ** 2 / 0.035 + (py - 0.75) ** 2 / 0.04))
            v = max(0, min(1, v))
            # Blue-to-yellow ramp.
            rr = int(45 + 210 * v)
            gg = int(128 + 110 * v)
            bb = int(190 - 125 * v)
            cell = slide.Shapes.AddShape(MsoShapeRectangle, x + c * cw, y + r * ch, cw + 0.2, ch + 0.2)
            cell.Line.Visible = MsoTriStateFalse
            cell.Fill.ForeColor.RGB = rr | (gg << 8) | (bb << 16)
    if label:
        add_text(slide, label, x, y + h + 8, w, 14, size=8.5, color=MUTED, align=PpAlignCenter)


def slide_6(slide, logo_path):
    add_header(slide, logo_path, "多源搜索状态建模", "已知地图约束下的搜索状态表达")
    add_rect(slide, 48, 119, 864, 34, fill=rgb("#F7FAFF"), line=rgb("#B8CFEA"), radius=True, weight=1.1)
    add_text(slide, "核心问题：USV 每一步需要判断“哪些空间区域更值得搜索”，并把多源状态转化为后续路径规划可用的空间价值图。", 62, 127, 835, 18, size=12.6, color=INK)

    xs = [55, 345, 635]
    titles = ["known_map", "observation", "detect"]
    subs = ["已知静态地图", "局部带噪观测", "目标探测反馈"]
    descs = [
        ["障碍结构预先已知", "目标位置未知", "决定自由水域与路径约束"],
        ["传感器范围内采样 clue", "观测带有噪声", "为 GP 后验推断提供输入"],
        ["命中区域增强信念", "未命中区域衰减", "更新目标存在信念图"],
    ]
    icons = ["图", "观", "探"]
    accents = [NAVY, BLUE, GREEN]
    for i, x in enumerate(xs):
        add_rect(slide, x, 180, 270, 188, fill=PALE_BLUE, line=rgb("#6CA0FF"), radius=True, weight=1.5, transparency=0)
        add_circle(slide, x + 18, 201, 48, fill=WHITE, line=accents[i], weight=1.5)
        add_text(slide, icons[i], x + 29, 213, 28, 22, size=15.5, color=accents[i], bold=True, align=PpAlignCenter)
        add_text(slide, titles[i], x + 82, 197, 160, 23, size=17, color=accents[i], bold=True)
        add_text(slide, subs[i], x + 82, 224, 160, 21, size=13.8, color=INK, bold=True)
        for j, item in enumerate(descs[i]):
            add_circle(slide, x + 34, 267 + j * 25, 7, fill=accents[i], line=accents[i], weight=0)
            add_text(slide, item, x + 49, 260 + j * 25, 190, 19, size=12.2, color=INK)
        if i < 2:
            add_arrow(slide, x + 279, 274, x + 291, 274, color=rgb("#83AEEE"), weight=2.2)

    add_rect(slide, 95, 413, 770, 62, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
    add_text(slide, "建模目标", 125, 426, 120, 24, size=17, color=WHITE, bold=True)
    add_text(slide, "将局部观测、探测反馈和地图约束组织为空间搜索状态，支撑后续 Anchor / Viewpoint / 路径段评分。", 250, 427, 580, 24, size=13.5, color=WHITE)
    add_arrow(slide, 238, 444, 248, 444, color=WHITE, weight=1.7)


def slide_7(slide, logo_path):
    add_header(slide, logo_path, "多源搜索状态建模", "基于 GP 后验的线索场估计")
    add_text(slide, "真实 clue field 隐含存在，USV 只能获得有限、带噪的局部采样；GP 用已观测点推断未观测区域的后验均值与不确定性。", 55, 116, 850, 28, size=13, color=MUTED)

    cards = [
        (55, "局部 clue 采样", "传感器范围内观测\n采样点有限且带噪", BLUE),
        (365, "GP 后验推断", "得到均值 μ(x)\n与方差 σ(x)", GREEN),
        (675, "UCB 信息图", "兼顾高线索值\n与高不确定区域", NAVY),
    ]
    for x, title, body, accent in cards:
        add_rect(slide, x, 166, 230, 178, fill=WHITE, line=rgb("#B8CFEA"), radius=True, weight=1.3)
        add_round_label(slide, title, x + 18, 182, 140, 26, fill=accent, size=12.5)
        add_text(slide, body, x + 20, 220, 180, 45, size=12.5, color=INK)

    # Left sampling visual.
    add_mini_grid(slide, 82, 273, 120, 50)
    for dx, dy in [(32, 22), (72, 11), (86, 34), (105, 18), (18, 41)]:
        add_circle(slide, 82 + dx, 273 + dy, 8, fill=ORANGE, line=ORANGE, weight=0)

    # Middle posterior visual.
    add_heatmap(slide, 418, 266, 110, 58, label="posterior mean / variance", hot_bias=(0.55, 0.45))

    # Right UCB visual.
    add_heatmap(slide, 723, 263, 110, 62, label="UCB map", hot_bias=(0.72, 0.32))
    add_arrow(slide, 291, 250, 350, 250, color=LINE, weight=2.2)
    add_arrow(slide, 601, 250, 660, 250, color=LINE, weight=2.2)

    add_rect(slide, 146, 380, 668, 48, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
    add_text(slide, "UCB(x) = μ(x) + βσ(x)，β = 0.5", 175, 392, 610, 24, size=20, color=WHITE, bold=True, align=PpAlignCenter)

    add_rect(slide, 185, 447, 590, 45, fill=PALE_ORANGE, line=ORANGE, radius=True, weight=1.2)
    add_text(slide, "优化思路：anomaly 上尾加权", 210, 455, 210, 20, size=13.5, color=ORANGE, bold=True)
    add_text(slide, "强化 GP 后验高值区域的搜索倾向；它不是目标存在概率模型。", 423, 455, 330, 20, size=12.2, color=INK)


def slide_8(slide, logo_path):
    add_header(slide, logo_path, "多源搜索状态建模", "目标存在信念与观测时效建模")
    add_text(slide, "GP clue 反映线索场推断，Intensity 与 Recency 则分别补充“目标存在信念”和“观测是否过期”的状态信息。", 56, 116, 845, 28, size=13, color=MUTED)

    # Intensity panel.
    add_rect(slide, 55, 164, 400, 255, fill=rgb("#F9FCFF"), line=rgb("#8AB3E8"), radius=True, weight=1.4)
    add_round_label(slide, "Intensity", 80, 184, 118, 28, fill=GREEN, size=14)
    add_text(slide, "空间目标存在信念", 215, 186, 190, 24, size=16, color=GREEN, bold=True)
    add_text(slide, "由探测反馈更新：命中区域增强，未命中区域衰减；用于补充 GP clue 之外的搜索价值判断。", 86, 226, 330, 44, size=12.5, color=INK)
    add_rect(slide, 84, 293, 126, 58, fill=PALE_GREEN, line=GREEN, radius=True, weight=1)
    add_text(slide, "命中", 103, 303, 88, 19, size=14, color=GREEN, bold=True, align=PpAlignCenter)
    add_text(slide, "局部信念增强", 96, 327, 102, 16, size=10.5, color=INK, align=PpAlignCenter)
    add_rect(slide, 300, 293, 126, 58, fill=rgb("#EFF4FB"), line=LINE, radius=True, weight=1)
    add_text(slide, "未命中", 319, 303, 88, 19, size=14, color=NAVY, bold=True, align=PpAlignCenter)
    add_text(slide, "局部信念衰减", 312, 327, 102, 16, size=10.5, color=INK, align=PpAlignCenter)
    add_arrow(slide, 212, 322, 296, 322, color=GREEN, weight=2.0)

    # Recency panel.
    add_rect(slide, 505, 164, 400, 255, fill=rgb("#FFFCF7"), line=rgb("#E6B35F"), radius=True, weight=1.4)
    add_round_label(slide, "Recency", 530, 184, 118, 28, fill=ORANGE, size=14)
    add_text(slide, "观测时效性", 665, 186, 190, 24, size=16, color=ORANGE, bold=True)
    add_text(slide, "记录区域距离上次观测的时间。长时间未观测区域具有更高刷新价值，但不表示目标概率更高。", 536, 226, 330, 44, size=12.5, color=INK)
    add_circle(slide, 556, 294, 74, fill=WHITE, line=ORANGE, weight=1.5)
    add_plain_line(slide, 593, 331, 593, 306, color=ORANGE, weight=2)
    add_plain_line(slide, 593, 331, 612, 340, color=ORANGE, weight=2)
    add_text(slide, "t_now - t_last_obs", 659, 300, 170, 20, size=15, color=ORANGE, bold=True)
    add_text(slide, "进入路径评分中的\nrecency_bias", 659, 329, 170, 37, size=12.5, color=INK)

    add_rect(slide, 122, 450, 716, 42, fill=PALE_ORANGE, line=ORANGE, radius=True, weight=1.1)
    add_text(slide, "边界说明：Recency 不直接并入 search_info_map，而是在路径段评分阶段提供观测刷新收益。", 145, 461, 670, 18, size=12.5, color=INK, bold=True, align=PpAlignCenter)


def slide_9(slide, logo_path):
    add_header(slide, logo_path, "多源搜索状态建模", "多源状态融合形成综合信息价值场")
    add_text(slide, "将 GP clue 与 Intensity 归一化融合为综合信息价值场；Recency 作为旁路刷新收益进入路径段评分。", 56, 116, 840, 28, size=13, color=MUTED)

    add_card_header(slide, 58, 170, 220, "GP Clue", "GP 后验均值/方差 → UCB\n可扩展 anomaly 上尾加权", accent=BLUE, icon_text="G")
    add_card_header(slide, 58, 278, 220, "Intensity", "空间目标存在信念\n由命中/未命中反馈更新", accent=GREEN, icon_text="I")
    add_card_header(slide, 58, 386, 220, "Recency", "观测时效性\n进入 recency_bias", accent=ORANGE, icon_text="R")

    add_arrow(slide, 285, 209, 340, 253, color=BLUE, weight=2.0)
    add_arrow(slide, 285, 317, 340, 288, color=GREEN, weight=2.0)
    add_rect(slide, 345, 206, 330, 126, fill=NAVY_DARK, line=NAVY_DARK, radius=True, weight=0)
    add_text(slide, "综合信息价值场", 370, 222, 280, 22, size=17, color=WHITE, bold=True, align=PpAlignCenter)
    add_text(slide, "search_info_map", 372, 251, 278, 28, size=21, color=WHITE, bold=True, align=PpAlignCenter)
    add_text(slide, "0.5 × norm(GP Clue) + 0.5 × norm(Intensity)", 366, 288, 290, 18, size=12.8, color=rgb("#D8E8FF"), align=PpAlignCenter)

    add_rect(slide, 376, 377, 280, 48, fill=PALE_ORANGE, line=ORANGE, radius=True, weight=1.1)
    add_text(slide, "recency_bias", 396, 386, 110, 18, size=14, color=ORANGE, bold=True)
    add_text(slide, "路径段评分中的刷新收益", 507, 386, 130, 18, size=11.5, color=INK)
    add_arrow(slide, 285, 425, 373, 402, color=ORANGE, weight=1.8, dashed=True)
    add_text(slide, "旁路进入评分", 300, 395, 76, 16, size=10.5, color=ORANGE, bold=True)

    add_arrow(slide, 681, 270, 721, 270, color=LINE, weight=2.2)
    add_rect(slide, 725, 182, 182, 185, fill=rgb("#F7FAFF"), line=rgb("#B8CFEA"), radius=True, weight=1.2)
    add_round_label(slide, "规划输入", 758, 202, 116, 28, fill=NAVY, size=13)
    steps = ["Anchor 提取", "viewpoint 采样", "路径段评分", "segment 执行"]
    for i, step in enumerate(steps):
        add_rect(slide, 747, 248 + i * 27, 138, 20, fill=WHITE, line=rgb("#A7C0DD"), radius=True, weight=0.8)
        add_text(slide, step, 755, 251 + i * 27, 122, 13, size=10.5, color=INK, bold=True, align=PpAlignCenter)

    add_rect(slide, 168, 462, 624, 35, fill=rgb("#F2F6FC"), line=rgb("#D5E2F0"), radius=True, weight=1)
    add_text(slide, "结果：路径规划不再只依据距离或覆盖面积，而是优先指向当前更具搜索价值的区域。", 188, 471, 590, 16, size=12.3, color=INK, bold=True, align=PpAlignCenter)


INSERTED_TITLES = {
    "已知地图约束下的搜索状态表达",
    "基于 GP 后验的线索场估计",
    "目标存在信念与观测时效建模",
    "多源状态融合形成综合信息价值场",
}


def slide_has_any_text(slide, expected_texts: set[str]) -> bool:
    for idx in range(1, int(slide.Shapes.Count) + 1):
        shp = slide.Shapes(idx)
        try:
            if shp.HasTextFrame and shp.TextFrame.HasText:
                value = str(shp.TextFrame.TextRange.Text)
                if any(text in value for text in expected_texts):
                    return True
        except Exception:
            pass
    return False


def delete_previous_inserted_slides(presentation) -> int:
    deleted = 0
    upper = min(9, int(presentation.Slides.Count))
    for idx in range(upper, 5, -1):
        slide = presentation.Slides(idx)
        if slide_has_any_text(slide, INSERTED_TITLES):
            slide.Delete()
            deleted += 1
    return deleted


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: insert_state_modeling_slides.py <pptx_path>")

    pptx_path = Path(sys.argv[1])
    if not pptx_path.exists():
        raise FileNotFoundError(str(pptx_path))

    import win32com.client  # type: ignore

    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = 1
        presentation = app.Presentations.Open(str(pptx_path), ReadOnly=0, Untitled=0, WithWindow=0)
        opened_count = int(presentation.Slides.Count)
        deleted_count = delete_previous_inserted_slides(presentation)
        before_count = int(presentation.Slides.Count)
        logo_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
        makers = [slide_6, slide_7, slide_8, slide_9]
        for offset, maker in enumerate(makers):
            slide = presentation.Slides.Add(6 + offset, PpLayoutBlank)
            slide.FollowMasterBackground = MsoTriStateFalse
            try:
                slide.Background.Fill.ForeColor.RGB = WHITE
            except Exception:
                pass
            maker(slide, logo_path)
        after_count = int(presentation.Slides.Count)
        presentation.Save()
        print(
            f"OPENED={opened_count} DELETED_PREVIOUS={deleted_count} "
            f"INSERTED_SLIDES=4 BEFORE_INSERT={before_count} AFTER={after_count} PATH={pptx_path}"
        )
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()


if __name__ == "__main__":
    main()
