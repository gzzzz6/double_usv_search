from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import win32com.client  # type: ignore


PPTX = Path(r"E:\毕设PPT\USV_PPT.pptx")
ASSET_DIR = Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\slide5_assets")
OUT_DIR = Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\ppt_progress_preview_after_route")


def rgb(r: int, g: int, b: int) -> int:
    return int(r) + int(g) * 256 + int(b) * 65536


def make_thumb(src: Path, dst: Path, size: tuple[int, int] = (520, 280), fit: bool = False) -> None:
    im = Image.open(src).convert("RGB")
    sw, sh = im.size
    tw, th = size
    scale = min(tw / sw, th / sh) if fit else max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    if fit:
        canvas = Image.new("RGB", size, (250, 252, 253))
        canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
        cropped = canvas.convert("RGBA")
    else:
        left = max(0, (nw - tw) // 2)
        top = max(0, (nh - th) // 2)
        cropped = resized.crop((left, top, left + tw, top + th)).convert("RGBA")

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, tw - 1, th - 1), radius=18, fill=255)
    out = Image.new("RGBA", size, (255, 255, 255, 0))
    out.alpha_composite(cropped)
    out.putalpha(mask)
    border = Image.new("RGBA", size, (255, 255, 255, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle((1, 1, tw - 2, th - 2), radius=18, outline=(210, 220, 230, 255), width=2)
    out.alpha_composite(border)
    out.save(dst)


def set_text(shape, text: str, font_size: float, color: int, bold: bool = False, align: int = 1) -> None:
    shape.TextFrame.TextRange.Text = text
    tr = shape.TextFrame.TextRange
    tr.Font.Name = "Microsoft YaHei"
    tr.Font.Size = font_size
    tr.Font.Color.RGB = color
    tr.Font.Bold = -1 if bold else 0
    tr.ParagraphFormat.Alignment = align
    shape.TextFrame.MarginLeft = 0
    shape.TextFrame.MarginRight = 0
    shape.TextFrame.MarginTop = 0
    shape.TextFrame.MarginBottom = 0


def add_text(slide, text: str, x: float, y: float, w: float, h: float, size: float, color: int, bold: bool = False, align: int = 1):
    shape = slide.Shapes.AddTextbox(1, x, y, w, h)
    set_text(shape, text, size, color, bold=bold, align=align)
    return shape


def add_rect(slide, x: float, y: float, w: float, h: float, fill: int, line: int, radius: bool = True):
    shape_type = 5 if radius else 1
    shape = slide.Shapes.AddShape(shape_type, x, y, w, h)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.ForeColor.RGB = line
    shape.Line.Weight = 1.0
    return shape


def add_card_shadow(shape) -> None:
    try:
        shape.Shadow.Visible = -1
        shape.Shadow.Transparency = 0.78
        shape.Shadow.Blur = 8
        shape.Shadow.OffsetX = 1.2
        shape.Shadow.OffsetY = 1.8
    except Exception:
        pass


def clear_body(slide) -> None:
    for idx in range(slide.Shapes.Count, 0, -1):
        shape = slide.Shapes(idx)
        name = str(shape.Name)
        if float(shape.Top) >= 104 and "Slide Number" not in name:
            shape.Delete()


def replace_header_text(slide, section_title: str) -> None:
    for shape in slide.Shapes:
        try:
            if shape.HasTextFrame and shape.TextFrame.HasText:
                text = str(shape.TextFrame.TextRange.Text).strip()
                if text == "文字" and float(shape.Top) < 55 and float(shape.Left) < 220:
                    set_text(shape, section_title, 24, rgb(255, 255, 255), bold=True)
        except Exception:
            continue


def remove_gray_band_title_text(slide) -> None:
    for idx in range(slide.Shapes.Count, 0, -1):
        shape = slide.Shapes(idx)
        try:
            if (
                shape.HasTextFrame
                and shape.TextFrame.HasText
                and 58 <= float(shape.Top) <= 105
                and float(shape.Left) < 420
            ):
                shape.Delete()
        except Exception:
            continue


def add_arrow(slide, x1: float, y1: float, x2: float, y2: float, color: int, weight: float = 1.5) -> None:
    conn = slide.Shapes.AddConnector(1, x1, y1, x2, y2)
    conn.Line.ForeColor.RGB = color
    conn.Line.Weight = weight
    try:
        conn.Line.EndArrowheadStyle = 3
    except Exception:
        pass


def add_small_tag(slide, text: str, x: float, y: float, w: float, color: int) -> None:
    add_rect(slide, x, y, w, 13, rgb(244, 248, 251), color)
    add_text(slide, text, x + 3, y + 1.6, w - 6, 8.5, 6.2, color, align=2)


def build_assets() -> dict[str, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    thumbs = {
        "map": OUT_DIR / "route_thumb_map.png",
        "fields": OUT_DIR / "route_thumb_fields.png",
        "single": OUT_DIR / "route_thumb_single.png",
        "team": OUT_DIR / "route_thumb_team.png",
        "astar": OUT_DIR / "route_thumb_astar.png",
    }
    make_thumb(ASSET_DIR / "map_overview.png", thumbs["map"], fit=True)
    make_thumb(ASSET_DIR / "info_fields.png", thumbs["fields"])
    make_thumb(ASSET_DIR / "anchor_viewpoint.png", thumbs["single"])
    make_thumb(ASSET_DIR / "residual_map.png", thumbs["team"])
    make_thumb(ASSET_DIR / "astar.png", thumbs["astar"])
    return thumbs


def edit_slide6(slide, thumbs: dict[str, Path]) -> None:
    clear_body(slide)
    replace_header_text(slide, "总体技术路线")
    remove_gray_band_title_text(slide)

    deep_blue = rgb(45, 86, 154)
    blue = rgb(70, 112, 183)
    teal = rgb(14, 139, 132)
    amber = rgb(217, 145, 31)
    moss = rgb(92, 119, 53)
    purple = rgb(91, 94, 168)
    text_dark = rgb(31, 42, 52)
    muted = rgb(88, 102, 113)
    line = rgb(210, 222, 232)
    light = rgb(248, 251, 253)

    add_text(slide, "总体技术路线：从已知地图与局部观测到搜索路径决策", 45, 118, 850, 24, 21, deep_blue, bold=True)
    add_text(slide, "系统以已知静态地图和局部观测为输入，经由多源信息场建模、单艇路径规划和双艇协同扩展，形成在线滚动搜索决策。", 48, 149, 820, 16, 10.5, muted)

    modules = [
        ("任务输入", "已知静态地图\nUSV 状态\n局部观测", "map", blue, ["known map", "observation"]),
        ("多源状态建模", "GP clue\nintensity\nrecency", "fields", teal, ["clue", "belief"]),
        ("综合信息价值场", "融合线索证据\n与剩余目标信念", "fields", purple, ["search_info_map"]),
        ("单艇路径规划", "viewpoint 生成\n安全 A*\n路径段评分", "single", amber, ["viewpoint", "segment"]),
        ("双艇协同扩展", "residual_map\n重叠抑制\nreservation", "team", moss, ["coordinated"]),
        ("滚动执行反馈", "执行短路径段\n更新观测\n重新规划", "astar", deep_blue, ["replanning"]),
    ]

    start_x = 38
    top = 200
    card_w = 136
    card_h = 232
    gap = 19
    for i, (title, desc, img_key, color, tags) in enumerate(modules):
        x = start_x + i * (card_w + gap)
        card = add_rect(slide, x, top, card_w, card_h, rgb(255, 255, 255), line)
        add_card_shadow(card)
        bar = slide.Shapes.AddShape(1, x, top, card_w, 5)
        bar.Fill.ForeColor.RGB = color
        bar.Line.Visible = 0
        slide.Shapes.AddPicture(str(thumbs[img_key]), 0, -1, x + 10, top + 15, card_w - 20, 54)
        add_text(slide, title, x + 10, top + 80, card_w - 20, 16, 11.8, text_dark, bold=True, align=2)
        add_text(slide, desc, x + 13, top + 110, card_w - 26, 56, 8.3, muted, align=2)
        ty = top + 181
        for tag in tags[:2]:
            add_small_tag(slide, tag, x + 14, ty, min(108, 10 + len(tag) * 4.7), color)
            ty += 17
        if i < len(modules) - 1:
            add_arrow(slide, x + card_w + 4, top + 116, x + card_w + gap - 5, top + 116, rgb(135, 156, 169), 1.6)

    add_rect(slide, 48, 455, 610, 48, light, line)
    add_text(slide, "滚动机制", 68, 468, 68, 14, 11.5, deep_blue, bold=True)
    add_text(slide, "每轮执行短时域路径段后，根据新观测更新信息场并重新决策。", 148, 468, 420, 14, 10.6, text_dark)
    add_text(slide, "信息价值判断", 584, 459, 70, 12, 8.5, teal, bold=True, align=2)
    add_text(slide, "+ 安全可执行路径", 584, 476, 74, 12, 8.5, amber, bold=True, align=2)

    add_rect(slide, 686, 455, 226, 48, rgb(239, 246, 252), rgb(188, 208, 226))
    add_text(slide, "边界说明", 704, 468, 62, 14, 11, deep_blue, bold=True)
    add_text(slide, "避障与 reservation 属于安全执行层，不写入目标搜索信念。", 772, 465, 118, 26, 8.4, text_dark)


def edit_slide7(slide, thumbs: dict[str, Path]) -> None:
    clear_body(slide)
    replace_header_text(slide, "总体技术路线")
    remove_gray_band_title_text(slide)

    deep_blue = rgb(45, 86, 154)
    teal = rgb(14, 139, 132)
    amber = rgb(217, 145, 31)
    moss = rgb(92, 119, 53)
    text_dark = rgb(31, 42, 52)
    muted = rgb(88, 102, 113)
    line = rgb(210, 222, 232)

    # Title band.
    add_text(slide, "Runtime 主链：每轮搜索决策如何发生", 45, 118, 650, 24, 21, deep_blue, bold=True)
    add_text(slide, "这一页对应代码运行时的主循环：观测更新信息场，信息场驱动路径段选择，执行后继续滚动重规划。", 48, 149, 720, 16, 10.5, muted)

    # Left-side loop nodes.
    nodes = [
        ("1", "初始化已知地图与目标状态"),
        ("2", "局部观测与 clue 采样"),
        ("3", "更新 GP clue / intensity / recency"),
        ("4", "构造综合信息价值场 search_info_map"),
        ("5", "生成 Anchor 与候选 viewpoint"),
        ("6", "A* 安全路径并截断 segment_path"),
        ("7", "按信息收益、刷新收益和执行代价评分"),
        ("8", "执行路径段，进入下一轮重规划"),
    ]
    x_left = 54
    y0 = 197
    step_h = 34
    for i, (num, text) in enumerate(nodes):
        y = y0 + i * step_h
        circ = slide.Shapes.AddShape(9, x_left, y, 21, 21)
        circ.Fill.ForeColor.RGB = deep_blue if i not in {2, 3, 4} else teal
        circ.Line.Visible = 0
        add_text(slide, num, x_left + 5.3, y + 1.1, 10, 9, 7.8, rgb(255, 255, 255), bold=True, align=2)
        add_text(slide, text, x_left + 32, y - 1, 350, 18, 10.2, text_dark, bold=False)
        if i < len(nodes) - 1:
            add_arrow(slide, x_left + 10.5, y + 24, x_left + 10.5, y + step_h - 4, rgb(142, 160, 172), 1.2)

    # Right-side visual evidence strip.
    panel = add_rect(slide, 455, 198, 430, 195, rgb(255, 255, 255), line)
    add_card_shadow(panel)
    slide.Shapes.AddPicture(str(thumbs["fields"]), 0, -1, 472, 214, 183, 82)
    slide.Shapes.AddPicture(str(thumbs["single"]), 0, -1, 683, 214, 183, 82)
    slide.Shapes.AddPicture(str(thumbs["team"]), 0, -1, 472, 307, 183, 66)
    slide.Shapes.AddPicture(str(thumbs["astar"]), 0, -1, 683, 307, 183, 66)
    add_text(slide, "信息场更新", 504, 296, 86, 10, 7.5, teal, bold=True, align=2)
    add_text(slide, "单艇路径段", 723, 296, 86, 10, 7.5, amber, bold=True, align=2)
    add_text(slide, "双艇分配", 520, 374, 70, 10, 7.5, moss, bold=True, align=2)
    add_text(slide, "安全路径", 738, 374, 70, 10, 7.5, deep_blue, bold=True, align=2)

    # Two-USV coordinated supplement.
    box = add_rect(slide, 455, 415, 430, 86, rgb(239, 247, 246), rgb(174, 218, 214))
    add_card_shadow(box)
    add_text(slide, "双艇 coordinated 补充", 474, 428, 128, 14, 11.5, teal, bold=True)
    items = [
        "共享团队状态",
        "residual_map 顺序扣减",
        "overlap / same-viewpoint 抑制",
        "reservation_v1 冲突处理",
    ]
    positions = [(474, 454), (606, 454), (474, 477), (674, 477)]
    for item, (x, y) in zip(items, positions):
        bullet = slide.Shapes.AddShape(9, x, y + 3, 5.5, 5.5)
        bullet.Fill.ForeColor.RGB = teal
        bullet.Line.Visible = 0
        add_text(slide, item, x + 10, y, 170, 10, 7.9, text_dark)

    # Bottom summary.
    add_rect(slide, 48, 500, 842, 33, rgb(248, 251, 253), line)
    add_text(slide, "主链特征", 68, 510, 65, 12, 10.5, deep_blue, bold=True)
    add_text(slide, "所有决策都围绕当前信息场滚动更新，viewpoint 是观测目标，真正执行的是短时域路径段。", 146, 510, 650, 12, 9.8, text_dark)


def main() -> None:
    thumbs = build_assets()
    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = 1
    pres = app.Presentations.Open(str(PPTX), ReadOnly=0, Untitled=0, WithWindow=0)
    try:
        edit_slide6(pres.Slides(6), thumbs)
        edit_slide7(pres.Slides(7), thumbs)
        pres.Save()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        pres.Slides(6).Export(str(OUT_DIR / "slide_06_after_edit.png"), "PNG", 1920, 1080)
        pres.Slides(7).Export(str(OUT_DIR / "slide_07_after_edit.png"), "PNG", 1920, 1080)
    finally:
        pres.Close()
        app.Quit()


if __name__ == "__main__":
    main()
