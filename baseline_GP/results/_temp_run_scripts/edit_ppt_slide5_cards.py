from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import win32com.client  # type: ignore


PPTX = Path(r"E:\毕设PPT\USV_PPT.pptx")
ASSET_DIR = Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\slide5_assets")
PREVIEW_DIR = Path(r"F:\pythonprojects\baseline_GP\results\ppt_draft_assets\ppt_progress_preview")


def rgb(r: int, g: int, b: int) -> int:
    return int(r) + int(g) * 256 + int(b) * 65536


def make_thumb(src: Path, dst: Path, size: tuple[int, int] = (640, 300), fit: bool = False) -> None:
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
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, tw - 1, th - 1), radius=22, fill=255)
    out = Image.new("RGBA", size, (255, 255, 255, 0))
    out.alpha_composite(cropped)
    out.putalpha(mask)

    border = Image.new("RGBA", size, (255, 255, 255, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle((1, 1, tw - 2, th - 2), radius=22, outline=(210, 220, 230, 255), width=3)
    out.alpha_composite(border)
    out.save(dst)


def set_textbox_text(shape, text: str, font_size: float, color: int, font_name: str = "Microsoft YaHei", bold: bool = False) -> None:
    shape.TextFrame.TextRange.Text = text
    tr = shape.TextFrame.TextRange
    tr.Font.Name = font_name
    tr.Font.Size = font_size
    tr.Font.Color.RGB = color
    tr.Font.Bold = -1 if bold else 0
    shape.TextFrame.MarginLeft = 0
    shape.TextFrame.MarginRight = 0
    shape.TextFrame.MarginTop = 0
    shape.TextFrame.MarginBottom = 0


def add_text(slide, text: str, x: float, y: float, w: float, h: float, font_size: float, color: int, bold: bool = False, align: int = 1):
    msoTextOrientationHorizontal = 1
    shape = slide.Shapes.AddTextbox(msoTextOrientationHorizontal, x, y, w, h)
    set_textbox_text(shape, text, font_size, color, bold=bold)
    shape.TextFrame.TextRange.ParagraphFormat.Alignment = align
    return shape


def add_round_rect(slide, x: float, y: float, w: float, h: float, fill: int, line: int, radius_adjust: float = 0.12):
    msoShapeRoundedRectangle = 5
    shape = slide.Shapes.AddShape(msoShapeRoundedRectangle, x, y, w, h)
    shape.Fill.Visible = -1
    shape.Fill.ForeColor.RGB = fill
    shape.Line.Visible = -1
    shape.Line.ForeColor.RGB = line
    shape.Line.Weight = 1.1
    # PowerPoint exposes rounded-rectangle radius through Adjustments, but the
    # COM setter is inconsistent across versions. The default radius is stable
    # enough for this template, so leave it unchanged.
    return shape


def add_tag(slide, text: str, x: float, y: float, w: float, color: int) -> None:
    tag = add_round_rect(slide, x, y, w, 15, rgb(242, 247, 250), color, radius_adjust=0.22)
    tag.Line.Weight = 0.7
    t = add_text(slide, text, x + 4, y + 2.0, w - 8, 10, 6.8, color, bold=False, align=2)
    t.TextFrame.TextRange.ParagraphFormat.Alignment = 2


def clear_slide_body(slide) -> None:
    # Preserve the template header, section title, and page number. Remove any
    # content accidentally placed in the body area during previous edits.
    for idx in range(slide.Shapes.Count, 0, -1):
        shape = slide.Shapes(idx)
        top = float(shape.Top)
        name = str(shape.Name)
        if top >= 108 and "Slide Number" not in name:
            shape.Delete()


def main() -> None:
    thumbs = {
        "map": ASSET_DIR / "thumb_map.png",
        "info": ASSET_DIR / "thumb_info.png",
        "single": ASSET_DIR / "thumb_single.png",
        "team": ASSET_DIR / "thumb_team.png",
    }
    make_thumb(ASSET_DIR / "map_overview.png", thumbs["map"], fit=True)
    make_thumb(ASSET_DIR / "info_fields.png", thumbs["info"])
    make_thumb(ASSET_DIR / "anchor_viewpoint.png", thumbs["single"])
    make_thumb(ASSET_DIR / "residual_map.png", thumbs["team"])

    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = 1
    pres = app.Presentations.Open(str(PPTX), ReadOnly=0, Untitled=0, WithWindow=0)
    try:
        slide = pres.Slides(5)
        clear_slide_body(slide)

        # Palette matched to the existing Lanzhou University blue template.
        deep_blue = rgb(45, 86, 154)
        mid_blue = rgb(67, 112, 184)
        teal = rgb(14, 139, 132)
        amber = rgb(217, 145, 31)
        moss = rgb(92, 119, 53)
        text_dark = rgb(32, 42, 52)
        text_muted = rgb(95, 107, 118)
        line_gray = rgb(214, 224, 232)
        light_blue = rgb(236, 244, 252)
        light_teal = rgb(232, 246, 244)
        light_amber = rgb(253, 247, 235)

        # Core positioning sentence.
        add_round_rect(slide, 48, 119, 864, 54, light_blue, rgb(189, 209, 229), radius_adjust=0.08)
        add_text(slide, "核心定位", 68, 132, 80, 18, 13.5, deep_blue, bold=True)
        add_text(
            slide,
            "本文聚焦已知静态障碍地图中目标位置与线索状态未知的搜索任务，构建单艇与双艇条件下的可解释信息驱动搜索基线。",
            158,
            128,
            720,
            28,
            13.2,
            text_dark,
            bold=False,
        )

        card_y = 196
        card_w = 205
        card_h = 210
        gap = 18
        start_x = 43
        cards = [
            {
                "title": "已知静态地图",
                "desc": "障碍结构已知，目标位置未知",
                "tags": [("known map", 58), ("static", 43)],
                "img": thumbs["map"],
                "color": mid_blue,
            },
            {
                "title": "多源搜索状态",
                "desc": "线索、目标强度和观测时效共同刻画搜索价值",
                "tags": [("GP clue", 51), ("intensity", 52), ("recency", 50)],
                "img": thumbs["info"],
                "color": teal,
            },
            {
                "title": "单艇路径规划",
                "desc": "从候选观测点生成安全可执行路径段",
                "tags": [("viewpoint", 60), ("A*", 27), ("segment", 54)],
                "img": thumbs["single"],
                "color": amber,
            },
            {
                "title": "双艇协同搜索",
                "desc": "共享状态下减少重复搜索与路径冲突",
                "tags": [("residual", 50), ("reservation", 70)],
                "img": thumbs["team"],
                "color": moss,
            },
        ]

        for i, card in enumerate(cards):
            x = start_x + i * (card_w + gap)
            card_shape = add_round_rect(slide, x, card_y, card_w, card_h, rgb(255, 255, 255), line_gray, radius_adjust=0.08)
            try:
                card_shape.Shadow.Visible = -1
                card_shape.Shadow.Transparency = 0.70
                card_shape.Shadow.Blur = 8
                card_shape.Shadow.OffsetX = 1.5
                card_shape.Shadow.OffsetY = 2.0
            except Exception:
                pass
            accent = slide.Shapes.AddShape(1, x, card_y, card_w, 5)
            accent.Fill.ForeColor.RGB = card["color"]
            accent.Line.Visible = 0

            slide.Shapes.AddPicture(str(card["img"]), 0, -1, x + 12, card_y + 14, card_w - 24, 82)
            add_text(slide, card["title"], x + 15, card_y + 106, card_w - 30, 20, 14.3, text_dark, bold=True)
            add_text(slide, card["desc"], x + 15, card_y + 132, card_w - 30, 36, 10.8, text_muted)
            tx = x + 15
            for tag_text, tag_w in card["tags"]:
                if tx + tag_w > x + card_w - 12:
                    break
                add_tag(slide, tag_text, tx, card_y + 176, tag_w, card["color"])
                tx += tag_w + 6

            if i < len(cards) - 1:
                # Lightweight arrow between cards.
                x1 = x + card_w + 3
                x2 = x + card_w + gap - 4
                y = card_y + 102
                conn = slide.Shapes.AddConnector(1, x1, y, x2, y)
                conn.Line.ForeColor.RGB = rgb(132, 154, 166)
                conn.Line.Weight = 1.6
                try:
                    conn.Line.EndArrowheadStyle = 3
                except Exception:
                    pass

        # Bottom meaning and boundary blocks.
        add_round_rect(slide, 48, 425, 650, 66, rgb(248, 251, 253), line_gray, radius_adjust=0.06)
        add_text(slide, "选题意义", 68, 440, 82, 16, 12.8, deep_blue, bold=True)
        add_text(
            slide,
            "将信息场建模、单艇安全路径规划和双艇协同分配连接为一条可解释、可复现的搜索决策主线。",
            152,
            438,
            515,
            34,
            11.5,
            text_dark,
        )

        add_round_rect(slide, 720, 425, 162, 66, light_amber, rgb(232, 201, 147), radius_adjust=0.06)
        add_text(slide, "研究边界", 737, 437, 65, 14, 11.8, rgb(145, 91, 22), bold=True)
        add_text(slide, "非 RL/MARL 主线\n非硬责任区\n非通信约束问题", 737, 456, 126, 28, 8.4, rgb(100, 78, 48))

        pres.Save()
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        slide.Export(str(PREVIEW_DIR / "slide_05_after_edit.png"), "PNG", 1920, 1080)
    finally:
        pres.Close()
        app.Quit()


if __name__ == "__main__":
    main()
