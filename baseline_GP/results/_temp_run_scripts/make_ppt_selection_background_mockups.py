from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(r"F:\pythonprojects")
GENERATED_DIR = Path(
    r"C:\Users\32022\.codex\generated_images\019e3ade-e4cf-7ca0-a1c3-2b1d2f8d4c1f"
)
OUT_DIR = ROOT / "baseline_GP" / "results" / "ppt_draft_assets" / "selection_background_significance"
COPY_DIR = ROOT / "images" / "ppt_selection_background_significance"

W, H = 1920, 1080


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\Dengb.ttf" if bold else r"C:\Windows\Fonts\Deng.ttf"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT_TITLE = font(56, bold=True)
FONT_SUBTITLE = font(30)
FONT_BODY = font(30)
FONT_BODY_BOLD = font(31, bold=True)
FONT_SMALL = font(22)
FONT_TAG = font(24, bold=True)


def draw_round_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int] | tuple[int, int, int],
    outline: tuple[int, int, int, int] | tuple[int, int, int] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def wrap_text(text: str, max_width: int, fnt: ImageFont.FreeTypeFont) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if fnt.getlength(candidate) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    line_gap: int = 8,
) -> int:
    x, y = xy
    for line in wrap_text(text, max_width, fnt):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def add_bullet_list(
    draw: ImageDraw.ImageDraw,
    bullets: Iterable[str],
    start: tuple[int, int],
    max_width: int,
    fnt: ImageFont.FreeTypeFont = FONT_BODY,
    fill: tuple[int, int, int] = (38, 48, 58),
    bullet_fill: tuple[int, int, int] = (18, 131, 123),
    line_gap: int = 8,
    item_gap: int = 19,
) -> int:
    x, y = start
    for item in bullets:
        draw.ellipse((x, y + 13, x + 10, y + 23), fill=bullet_fill)
        y = draw_wrapped(draw, item, (x + 28, y), max_width - 28, fnt, fill, line_gap)
        y += item_gap
    return y


def add_top_bar(draw: ImageDraw.ImageDraw, section: str, title: str, subtitle: str | None = None) -> None:
    draw.text((90, 54), section, font=FONT_TAG, fill=(18, 131, 123))
    draw.rectangle((90, 91, 162, 96), fill=(18, 131, 123))
    draw.text((90, 126), title, font=FONT_TITLE, fill=(24, 31, 38))
    if subtitle:
        draw.text((94, 198), subtitle, font=FONT_SUBTITLE, fill=(91, 103, 112))


def crop_cover(path: Path, size: tuple[int, int]) -> Image.Image:
    src = Image.open(path).convert("RGB")
    sw, sh = src.size
    tw, th = size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def paste_shadow_card(
    base: Image.Image,
    xy: tuple[int, int, int, int],
    radius: int = 14,
    fill: tuple[int, int, int, int] = (255, 255, 255, 235),
) -> ImageDraw.ImageDraw:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx1, sy1, sx2, sy2 = xy
    sd.rounded_rectangle((sx1 + 10, sy1 + 14, sx2 + 10, sy2 + 14), radius=radius, fill=(28, 48, 62, 38))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    base.alpha_composite(shadow)
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(xy, radius=radius, fill=fill, outline=(226, 232, 236, 255), width=2)
    base.alpha_composite(overlay)
    return ImageDraw.Draw(base)


def make_slide_1(bg_path: Path) -> Image.Image:
    img = Image.new("RGBA", (W, H), (247, 250, 251, 255))
    right = crop_cover(bg_path, (1030, 650)).convert("RGBA")
    right = right.filter(ImageFilter.GaussianBlur(0.2))
    img.alpha_composite(right, dest=(800, 250))
    draw = ImageDraw.Draw(img)
    wash = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wash)
    wd.rectangle((760, 0, 1920, 1080), fill=(255, 255, 255, 34))
    wd.rounded_rectangle((795, 240, 1840, 930), radius=24, fill=(255, 255, 255, 16), outline=(218, 232, 235, 190), width=2)
    img.alpha_composite(wash)
    draw = ImageDraw.Draw(img)

    add_top_bar(
        draw,
        "01  选题背景和意义",
        "海上可疑目标搜索面临复杂环境与信息不确定性",
        "背景页建议：先讲任务需求，再讲为什么不能只做最短路或简单覆盖。",
    )

    bullets = [
        "近岸安防、海上交通监管、应急搜救等任务需要无人化、持续化搜索能力。",
        "USV 具备机动部署、低人员风险和长时巡航优势，适合承担海上搜索任务。",
        "可疑目标位置未知，线索观测稀疏且带噪，单次传感器覆盖范围有限。",
        "已知障碍、岸线和狭窄通道会约束路径，搜索路径不能只追求几何距离最短。",
        "多艇场景中还会出现重复搜索、区域分工和路径冲突等协同问题。",
    ]
    y = add_bullet_list(draw, bullets, (106, 300), 650)

    draw_round_rect(draw, (105, y + 20, 725, y + 105), 12, fill=(231, 246, 244, 255), outline=(182, 223, 218, 255), width=2)
    draw.text((132, y + 43), "本页结论：搜索决策应围绕“哪里更值得搜、如何安全过去”。", font=FONT_SMALL, fill=(29, 95, 91))
    return img


def make_slide_2(bg_path: Path) -> Image.Image:
    img = Image.new("RGBA", (W, H), (248, 250, 251, 255))
    add_top_bar(
        ImageDraw.Draw(img),
        "01  选题背景和意义",
        "国内外研究现状：从地图探索到信息采集与协同搜索",
        "这一页建议按研究方向归纳，不要在 PPT 上堆文献列表。",
    )
    draw = ImageDraw.Draw(img)

    visual = crop_cover(bg_path, (1680, 220)).convert("RGBA")
    visual.putalpha(110)
    img.alpha_composite(visual, dest=(120, 815))

    cards = [
        (
            "移动机器人探索",
            "占据栅格、Frontier 探索",
            ["用未知区域边界驱动建图", "适合未知地图探索"],
            "与本文区别：本文地图结构已知，重点不是发现障碍，而是搜索目标相关信息。",
            (18, 131, 123),
        ),
        (
            "信息型路径规划",
            "IPP、GP-UCB、主动采样",
            ["在运动预算下最大化信息收益", "兼顾探索与利用"],
            "与本文关系：为 GP clue、综合信息价值场和路径段评分提供方法基础。",
            (214, 144, 37),
        ),
        (
            "多机器人协同搜索",
            "任务分配、覆盖互补、路径冲突",
            ["多平台共享状态与互补覆盖", "处理同格、换位等冲突"],
            "与本文关系：支撑双艇协同模式与独立模式的对照实验。",
            (54, 100, 172),
        ),
    ]

    x0s = [105, 675, 1245]
    for x0, (title, subtitle, points, relation, color) in zip(x0s, cards):
        paste_shadow_card(img, (x0, 290, x0 + 505, 745), radius=18)
        draw = ImageDraw.Draw(img)
        draw_round_rect(draw, (x0 + 28, 320, x0 + 82, 374), 12, fill=color)
        draw.text((x0 + 108, 319), title, font=FONT_BODY_BOLD, fill=(24, 31, 38))
        draw_wrapped(draw, subtitle, (x0 + 108, 366), 345, FONT_SMALL, (93, 103, 112), line_gap=4)
        y = 445
        for p in points:
            draw.ellipse((x0 + 38, y + 10, x0 + 48, y + 20), fill=color)
            y = draw_wrapped(draw, p, (x0 + 62, y), 390, FONT_SMALL, (46, 56, 65), line_gap=4) + 10
        draw.line((x0 + 35, 573, x0 + 470, 573), fill=(226, 232, 236), width=2)
        draw_wrapped(draw, relation, (x0 + 38, 602), 410, FONT_SMALL, (37, 74, 90), line_gap=6)

    draw = ImageDraw.Draw(img)
    draw_round_rect(draw, (220, 910, 1700, 1000), 14, fill=(239, 247, 249, 238), outline=(202, 224, 229), width=2)
    draw.text(
        (260, 937),
        "研究空白：已知静态地图 + 目标/线索未知 + 单艇/双艇可解释搜索基线，仍需要一条完整整合方案。",
        font=FONT_BODY,
        fill=(24, 68, 82),
    )
    return img


def make_slide_3(bg_path: Path) -> Image.Image:
    img = Image.new("RGBA", (W, H), (247, 250, 251, 255))
    add_top_bar(
        ImageDraw.Draw(img),
        "01  选题背景和意义",
        "本文切入：已知静态地图下的可解释信息驱动搜索基线",
        "这一页用于收束意义，并自然过渡到后面的总体技术路线。",
    )
    draw = ImageDraw.Draw(img)

    visual = crop_cover(bg_path, (620, 360)).convert("RGBA")
    visual.putalpha(235)
    img.alpha_composite(visual, dest=(1235, 245))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((1220, 230, 1870, 625), radius=20, fill=None, outline=(220, 232, 235, 190), width=2)

    draw_round_rect(draw, (115, 285, 1125, 415), 16, fill=(231, 246, 244, 255), outline=(178, 222, 217), width=2)
    draw.text((150, 319), "核心定位", font=FONT_BODY_BOLD, fill=(18, 131, 123))
    draw_wrapped(
        draw,
        "在已知静态障碍地图中，让 USV 根据线索、目标强度和观测时效持续选择高价值且安全可达的搜索路径段。",
        (310, 314),
        760,
        FONT_BODY,
        (29, 54, 64),
        line_gap=8,
    )

    modules = [
        ("已知静态地图\n局部观测", "任务边界明确"),
        ("多源信息场\n线索 / 强度 / 时效", "判断哪里值得搜"),
        ("单艇安全路径\n视点 + A*", "生成可执行路径段"),
        ("双艇协同搜索\n剩余图 + 预约", "减少重复与冲突"),
    ]
    x_positions = [120, 545, 970, 1395]
    y0, card_w, card_h = 520, 330, 210
    colors = [(18, 131, 123), (214, 144, 37), (67, 112, 172), (98, 118, 60)]
    for idx, (x0, (main, sub), color) in enumerate(zip(x_positions, modules, colors)):
        paste_shadow_card(img, (x0, y0, x0 + card_w, y0 + card_h), radius=18)
        draw = ImageDraw.Draw(img)
        draw_round_rect(draw, (x0 + 28, y0 + 28, x0 + 72, y0 + 72), 10, fill=color)
        yy = y0 + 28
        for line in main.split("\n"):
            draw.text((x0 + 92, yy), line, font=FONT_BODY_BOLD, fill=(24, 31, 38))
            yy += 42
        draw.text((x0 + 32, y0 + 145), sub, font=FONT_SMALL, fill=(82, 96, 106))
        if idx < len(modules) - 1:
            ax = x0 + card_w + 18
            ay = y0 + card_h // 2
            draw.line((ax, ay, ax + 64, ay), fill=(128, 150, 158), width=5)
            draw.polygon([(ax + 64, ay), (ax + 48, ay - 12), (ax + 48, ay + 12)], fill=(128, 150, 158))

    draw_round_rect(draw, (118, 805, 1228, 958), 16, fill=(255, 255, 255, 238), outline=(221, 230, 235), width=2)
    draw.text((150, 830), "选题意义", font=FONT_BODY_BOLD, fill=(24, 31, 38))
    meaning = [
        "方法上：把信息场建模、候选视点、安全路径和路径段评分连成闭环。",
        "协同上：在单艇基础上构造双艇集中式协同搜索基线。",
        "工程上：不依赖大量训练数据，决策过程可解释、可复现、便于实验分析。",
    ]
    add_bullet_list(draw, meaning, (160, 884), 990, fnt=FONT_SMALL, item_gap=6, line_gap=4)

    draw_round_rect(draw, (1280, 805, 1815, 958), 16, fill=(251, 245, 236, 255), outline=(232, 208, 171), width=2)
    draw.text((1310, 830), "答辩边界", font=FONT_BODY_BOLD, fill=(126, 83, 25))
    boundary = ["不讲 RL/MARL 主线", "不讲通信约束或分布式一致性", "双艇是最小协同实现"]
    add_bullet_list(draw, boundary, (1320, 880), 430, fnt=font(20), bullet_fill=(214, 144, 37), item_gap=1, line_gap=2)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    COPY_DIR.mkdir(parents=True, exist_ok=True)
    generated = sorted(GENERATED_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if len(generated) < 3:
        raise RuntimeError(f"Expected at least 3 generated images in {GENERATED_DIR}, got {len(generated)}")

    slides = [
        ("01_选题背景_任务需求.png", make_slide_1(generated[0])),
        ("02_国内外研究现状_三类研究脉络.png", make_slide_2(generated[1])),
        ("03_选题意义_本文切入点.png", make_slide_3(generated[2])),
    ]
    for name, image in slides:
        out = OUT_DIR / name
        copy = COPY_DIR / name
        rgb = image.convert("RGB")
        rgb.save(out, quality=96)
        rgb.save(copy, quality=96)
        print(out)
        print(copy)


if __name__ == "__main__":
    main()
