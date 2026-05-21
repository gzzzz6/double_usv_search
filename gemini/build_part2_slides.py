"""
Insert 4 slides for '多源搜索状态建模' after slide 5 in USV_PPT_gemini.pptx.
Academic style with quality finish. No specific code parameters.
"""
import copy
import shutil
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

SRC = r"E:\毕设PPT\USV_PPT_gemini.pptx"
BAK = r"E:\毕设PPT\USV_PPT_gemini_bak.pptx"

shutil.copy2(SRC, BAK)
print(f"Backup: {BAK}")

prs = Presentation(SRC)

# ================================================================
# Step 1: Get layout from slide 6 (index 5) and create 4 new slides
# ================================================================
ref_slide = prs.slides[5]
layout = ref_slide.slide_layout

# Print layout placeholder info for debugging
print("Layout placeholders:")
for ph in layout.placeholders:
    print(f"  idx={ph.placeholder_format.idx}, name={ph.name}, text='{ph.text.strip()}'")

slides_new = []
for _ in range(4):
    s = prs.slides.add_slide(layout)
    slides_new.append(s)
print(f"Created 4 new slides. Total now: {len(prs.slides)}")

# ================================================================
# Step 2: Reorder — move last 4 slides to after slide 5
# ================================================================
sldIdLst = prs.presentation.sldIdLst
ids = list(sldIdLst)
new_ids = ids[-4:]
remaining = ids[:-4]
reordered = remaining[:5] + new_ids + remaining[5:]
for el in list(sldIdLst):
    sldIdLst.remove(el)
for el in reordered:
    sldIdLst.append(el)
print("Reordered: new slides at positions 6-9")

# ================================================================
# Design System
# ================================================================
# Blues (GP Clue theme)
C_BLUE_DEEP   = RGBColor(30, 64, 175)
C_BLUE_MID    = RGBColor(37, 99, 235)
C_BLUE_LIGHT  = RGBColor(219, 234, 254)
C_BLUE_BORDER = RGBColor(147, 197, 253)

# Greens (Intensity theme)
C_GREEN_DEEP   = RGBColor(6, 95, 70)
C_GREEN_MID    = RGBColor(5, 150, 105)
C_GREEN_LIGHT  = RGBColor(209, 250, 229)
C_GREEN_BORDER = RGBColor(110, 231, 183)

# Ambers (Recency theme)
C_AMBER_DEEP   = RGBColor(146, 64, 14)
C_AMBER_MID    = RGBColor(217, 119, 6)
C_AMBER_LIGHT  = RGBColor(254, 243, 199)
C_AMBER_BORDER = RGBColor(252, 211, 77)

# Neutrals
C_SLATE       = RGBColor(71, 85, 105)
C_GRAY_TEXT   = RGBColor(100, 116, 139)
C_DARK        = RGBColor(30, 41, 59)
C_WHITE       = RGBColor(255, 255, 255)
C_CARD_BG     = RGBColor(248, 250, 252)
C_CARD_BORDER = RGBColor(226, 232, 240)

# ================================================================
# Helper Functions
# ================================================================
def set_ph(slide, page_title, subtitle_text, page_num):
    """Set placeholder texts for nav bar, title, subtitle, page number."""
    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        try:
            if idx == 16:
                ph.text = page_title
                for para in ph.text_frame.paragraphs:
                    para.font.name = "Microsoft YaHei"
                    para.font.bold = True
            elif idx == 14:
                ph.text = subtitle_text
                for para in ph.text_frame.paragraphs:
                    para.font.name = "Microsoft YaHei"
            elif idx in (1, 2):
                ph.text = str(page_num)
            elif idx == 34:
                ph.text = "综述和评述"
            elif idx == 35:
                ph.text = "思路和内容"
            elif idx == 36:
                ph.text = "过程和方法"
            elif idx == 37:
                ph.text = "成果与展望"
            elif idx == 33:
                ph.text = "背景和意义"
        except Exception:
            pass

    # Also remove any "文字" placeholder content shapes that came from the layout
    shapes_to_remove = []
    for shape in slide.shapes:
        if not shape.is_placeholder and hasattr(shape, 'text') and shape.text.strip() == "文字":
            shapes_to_remove.append(shape)
    for s in shapes_to_remove:
        s.element.getparent().remove(s.element)


def section_bar(slide, text, left, top, width, color):
    """Colored section header bar with white text."""
    bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, Inches(0.36))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    tf = bar.text_frame
    tf.margin_left = Inches(0.12)
    tf.margin_top = Inches(0.03)
    tf.margin_bottom = Inches(0.03)
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = "Microsoft YaHei"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = C_WHITE


def card(slide, title, body, left, top, width, height,
         accent=None, bg=None, border=None,
         tsz=10, bsz=8.5, tc=None):
    """Academic card with optional left accent bar."""
    bg_c = bg or C_WHITE
    bd_c = border or C_CARD_BORDER
    tc_c = tc or C_DARK

    rect = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    rect.fill.solid()
    rect.fill.fore_color.rgb = bg_c
    rect.line.color.rgb = bd_c
    rect.line.width = Pt(1)

    if accent:
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            left + Inches(0.02), top + Inches(0.06),
            Inches(0.04), height - Inches(0.12))
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()

    inset = Inches(0.16) if accent else Inches(0.10)
    tb = slide.shapes.add_textbox(
        left + inset, top + Inches(0.06),
        width - inset - Inches(0.08), height - Inches(0.12))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.margin_left = tf.margin_right = Inches(0.04)

    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Microsoft YaHei"
    p.font.size = Pt(tsz)
    p.font.bold = True
    p.font.color.rgb = tc_c

    if body:
        p2 = tf.add_paragraph()
        p2.text = body
        p2.font.name = "Microsoft YaHei"
        p2.font.size = Pt(bsz)
        p2.font.color.rgb = C_GRAY_TEXT
        p2.space_before = Pt(4)


def formula(slide, text, left, top, width, height, label=None):
    """Formula display box."""
    rect = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    rect.fill.solid()
    rect.fill.fore_color.rgb = RGBColor(241, 245, 249)
    rect.line.color.rgb = RGBColor(203, 213, 225)
    rect.line.width = Pt(1)

    tb = slide.shapes.add_textbox(
        left + Inches(0.1), top + Inches(0.05),
        width - Inches(0.2), height - Inches(0.1))
    tf = tb.text_frame
    tf.word_wrap = True

    if label:
        p = tf.paragraphs[0]
        p.text = label
        p.font.name = "Microsoft YaHei"
        p.font.size = Pt(8)
        p.font.color.rgb = C_SLATE
        p.font.bold = True

        p2 = tf.add_paragraph()
        p2.text = text
        p2.font.name = "Consolas"
        p2.font.size = Pt(12)
        p2.font.color.rgb = C_DARK
        p2.font.bold = True
        p2.space_before = Pt(5)
    else:
        p = tf.paragraphs[0]
        p.text = text
        p.font.name = "Consolas"
        p.font.size = Pt(12)
        p.font.color.rgb = C_DARK
        p.font.bold = True


def arrow_r(slide, left, top, w=Inches(0.28), h=Inches(0.14), color=None):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left, top, w, h)
    a.fill.solid()
    a.fill.fore_color.rgb = color or C_CARD_BORDER
    a.line.fill.background()


def arrow_d(slide, left, top, w=Inches(0.14), h=Inches(0.28), color=None):
    a = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, left, top, w, h)
    a.fill.solid()
    a.fill.fore_color.rgb = color or C_CARD_BORDER
    a.line.fill.background()


def note_text(slide, text, left, top, width, height, sz=9, color=None):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = "Microsoft YaHei"
    p.font.size = Pt(sz)
    p.font.color.rgb = color or C_GRAY_TEXT


# ================================================================
# Content area constants
# ================================================================
Y0 = Inches(1.15)    # Content starts below nav bar
X0 = Inches(0.5)     # Left margin
FULL_W = Inches(12.3) # Full content width

# ================================================================
# SLIDE 6: 总体框架与要素定义
# ================================================================
s6 = slides_new[0]
set_ph(s6, "多源搜索状态建模", "三源状态融合驱动搜索价值判断", 6)

note_text(s6,
    "搜索过程中，USV 需同时刻画三类互补的空间信息维度，并将其融合为统一的信息价值场，指导路径规划中的价值判断。",
    X0, Y0, FULL_W, Inches(0.28), sz=10, color=C_SLATE)

# ---- Three columns ----
COL_W = Inches(3.85)
GAP = Inches(0.35)
COL_TOP = Y0 + Inches(0.4)
COL_H = Inches(3.0)

# Column 1: GP Clue
x1 = X0
section_bar(s6, "① 线索估计场  GP Clue", x1, COL_TOP, COL_W, C_BLUE_MID)
card(s6, "基于高斯过程回归（GPR）",
     "将 USV 局部带噪观测作为稀疏训练集，通过高斯过程推断全局线索分布的后验均值与方差。\n\n通过 UCB 策略权衡"开发"（走向高线索区域）与"探索"（走向高不确定区域），实现自适应搜索引导。",
     x1, COL_TOP + Inches(0.42), COL_W, COL_H - Inches(0.42),
     accent=C_BLUE_MID, bg=C_BLUE_LIGHT, border=C_BLUE_BORDER, tc=C_BLUE_DEEP)

# Column 2: Intensity
x2 = x1 + COL_W + GAP
section_bar(s6, "② 目标存在信念场  Intensity", x2, COL_TOP, COL_W, C_GREEN_MID)
card(s6, "基于贝叶斯递推更新",
     "对每个搜索网格维护目标存在概率。传感器扫描后依据贝叶斯法则更新：\n\n• 命中（Hit）→ 后验概率上调\n• 未命中（Miss）→ 后验概率下调\n\n使信念场逐步收敛，为规划提供"剩余搜索价值"信号。",
     x2, COL_TOP + Inches(0.42), COL_W, COL_H - Inches(0.42),
     accent=C_GREEN_MID, bg=C_GREEN_LIGHT, border=C_GREEN_BORDER, tc=C_GREEN_DEEP)

# Column 3: Recency
x3 = x2 + COL_W + GAP
section_bar(s6, "③ 观测时效场  Recency", x3, COL_TOP, COL_W, C_AMBER_MID)
card(s6, "基于时间戳累加的时效衰减",
     "记录每个网格距上次被扫描所经过的步数。长期未复扫区域的时效值持续回升。\n\n本维度不直接参与信息价值场构建，而是作为独立评分项进入路径段评分，驱动 USV 周期性复扫高价值区域。",
     x3, COL_TOP + Inches(0.42), COL_W, COL_H - Inches(0.42),
     accent=C_AMBER_MID, bg=C_AMBER_LIGHT, border=C_AMBER_BORDER, tc=C_AMBER_DEEP)

# ---- Fusion section ----
FUSION_Y = COL_TOP + COL_H + Inches(0.15)
arrow_d(s6, x1 + COL_W / 2 - Inches(0.07), FUSION_Y, color=C_BLUE_MID)
arrow_d(s6, x2 + COL_W / 2 - Inches(0.07), FUSION_Y, color=C_GREEN_MID)

formula(s6, "search_info_map(x) = 0.5 × norm( GP_Clue ) + 0.5 × norm( Intensity )",
        Inches(0.8), FUSION_Y + Inches(0.35), Inches(8.0), Inches(0.55),
        label="▼ 综合信息价值场构建")

card(s6, "⚠ 设计要点：Recency 独立于融合",
     "时效维度通过路径评分中的 recency_bias 项独立施加约束，避免稀释线索与目标信念的信息浓度。",
     Inches(9.1), FUSION_Y + Inches(0.35), Inches(3.55), Inches(0.55),
     accent=C_AMBER_MID, border=C_AMBER_BORDER, tsz=9, bsz=7.5, tc=C_AMBER_DEEP)

print("Slide 6 done: 总体框架")

# ================================================================
# SLIDE 7: GP Clue — 高斯过程线索推断
# ================================================================
s7 = slides_new[1]
set_ph(s7, "多源搜索状态建模", "线索估计场 GP Clue —— 基于高斯过程的空间推断", 7)

# Left column: Input
LW = Inches(3.85)
RW = Inches(4.0)
MW = Inches(4.0)

section_bar(s7, "建模输入：稀疏带噪局部观测", X0, Y0, LW, C_BLUE_MID)
card(s7, "观测数据特征",
     "USV 在传感器视场范围内采集的线索样本值，受噪声干扰，仅覆盖已巡航区域的部分网格。\n\nGPR 的任务：基于有限的局部观测，推断全搜索区域上的连续线索分布及其不确定性。",
     X0, Y0 + Inches(0.42), LW, Inches(1.8),
     accent=C_BLUE_MID, bg=C_BLUE_LIGHT, border=C_BLUE_BORDER, tc=C_BLUE_DEEP)

card(s7, "核函数选择",
     "采用径向基核函数（RBF Kernel），通过长度尺度参数控制空间相关性的衰减速度。邻近区域高度相关，远距离推断回归先验。",
     X0, Y0 + Inches(2.4), LW, Inches(1.0),
     accent=C_BLUE_MID, tc=C_BLUE_DEEP)

# Middle column: Formulas
mx = X0 + LW + GAP
section_bar(s7, "高斯过程后验推断", mx, Y0, MW, C_BLUE_DEEP)

formula(s7, "μ(x*) = k*ᵀ (K + σₙ²I)⁻¹ y",
        mx, Y0 + Inches(0.5), MW, Inches(0.6),
        label="后验均值（线索强度最优估计）")

formula(s7, "σ²(x*) = k(x*,x*) - k*ᵀ (K + σₙ²I)⁻¹ k*",
        mx, Y0 + Inches(1.25), MW, Inches(0.6),
        label="后验方差（认知不确定性度量）")

card(s7, "物理含义",
     "μ(x) 表征该位置的线索强度估计值；σ²(x) 度量 USV 对该位置认知的不足程度。两者共同构成高斯过程推断的核心输出。",
     mx, Y0 + Inches(2.05), MW, Inches(1.0),
     accent=C_BLUE_MID, bg=C_CARD_BG, tc=C_BLUE_DEEP)

# Right column: UCB
rx = mx + MW + GAP
section_bar(s7, "UCB 探索-利用平衡", rx, Y0, RW, C_BLUE_DEEP)

formula(s7, "GP_Clue(x) = μ(x) + β · σ(x)",
        rx, Y0 + Inches(0.5), RW, Inches(0.6),
        label="Upper Confidence Bound")

card(s7, "μ(x) → 开发（Exploitation）",
     "后验均值高的区域线索浓度估计大，USV 优先前往以提高搜索效率。",
     rx, Y0 + Inches(1.25), RW, Inches(0.85),
     accent=C_BLUE_MID, bg=C_BLUE_LIGHT, border=C_BLUE_BORDER, tc=C_BLUE_DEEP, tsz=9)

card(s7, "β·σ(x) → 探索（Exploration）",
     "后验方差高的区域认知不足，权重参数 β 鼓励 USV 前往陌生区域获取新信息。",
     rx, Y0 + Inches(2.25), RW, Inches(0.85),
     accent=C_AMBER_MID, bg=C_AMBER_LIGHT, border=C_AMBER_BORDER, tc=C_AMBER_DEEP, tsz=9)

# Bottom: engineering note
card(s7, "工程处理",
     "为控制 GP 拟合的 O(N³) 计算复杂度，系统设置了观测点滑动窗口上限与周期性重拟合策略，在推断精度与实时性之间取得平衡。",
     X0, Y0 + Inches(3.6), FULL_W, Inches(0.5),
     accent=C_SLATE, tsz=9, bsz=8, tc=C_SLATE)

print("Slide 7 done: GP Clue")

# ================================================================
# SLIDE 8: Intensity — 贝叶斯目标信念
# ================================================================
s8 = slides_new[2]
set_ph(s8, "多源搜索状态建模", "目标存在信念场 Intensity —— 贝叶斯递推更新", 8)

# Top: Sensor model
section_bar(s8, "传感器观测模型", X0, Y0, FULL_W, C_SLATE)
card(s8, "不完美传感器假设",
     "传感器存在两类不完美性：目标存在时有一定概率未能检出（漏检），目标不存在时有一定概率产生误报（虚警）。这一物理约束是贝叶斯更新公式的前提基础。",
     X0, Y0 + Inches(0.42), FULL_W, Inches(0.7),
     accent=C_SLATE, tc=C_DARK)

# Two columns
HIT_TOP = Y0 + Inches(1.25)
HALF_W = Inches(5.9)

# Hit Update
section_bar(s8, "命中更新（Hit Update）", X0, HIT_TOP, HALF_W, C_GREEN_MID)
card(s8, "目标概率上调",
     "传感器在某网格探测到疑似目标信号时，利用贝叶斯公式将该格的目标存在后验概率向上更新。\n\n直觉：传感器报告"有目标" → 我们更有理由相信该格存在目标。更新幅度取决于检测概率与先验的比值。",
     X0, HIT_TOP + Inches(0.42), HALF_W, Inches(1.6),
     accent=C_GREEN_MID, bg=C_GREEN_LIGHT, border=C_GREEN_BORDER, tc=C_GREEN_DEEP)

formula(s8, "P(target | hit) = P(hit|target)·P(target) / P(hit)",
        X0, HIT_TOP + Inches(2.1), HALF_W, Inches(0.55),
        label="贝叶斯后验 — 命中条件")

# Miss Update
mx2 = X0 + HALF_W + Inches(0.5)
section_bar(s8, "未命中更新（Miss Update）", mx2, HIT_TOP, HALF_W, C_AMBER_MID)
card(s8, "目标概率下调",
     "传感器扫描了某网格但未检出目标时，贝叶斯公式将该格目标概率向下衰减。\n\n直觉：传感器报告"无目标" → 该格概率应更低。但因存在漏检可能，概率不会降为零，仍保留后续复扫价值。",
     mx2, HIT_TOP + Inches(0.42), HALF_W, Inches(1.6),
     accent=C_AMBER_MID, bg=C_AMBER_LIGHT, border=C_AMBER_BORDER, tc=C_AMBER_DEEP)

formula(s8, "P(target | miss) = P(miss|target)·P(target) / P(miss)",
        mx2, HIT_TOP + Inches(2.1), HALF_W, Inches(0.55),
        label="贝叶斯后验 — 未命中条件")

# Bottom note
card(s8, "收敛特性",
     "随着 USV 反复扫描，Intensity 场逐步收敛：持续未命中的区域概率趋近于零，曾命中的区域概率维持高值。这一收敛性为路径规划提供动态的"剩余搜索价值"信号。",
     X0, HIT_TOP + Inches(2.85), FULL_W, Inches(0.55),
     accent=C_GREEN_MID, tsz=9, bsz=8, tc=C_GREEN_DEEP)

print("Slide 8 done: Intensity")

# ================================================================
# SLIDE 9: Recency + 综合信息价值场构建
# ================================================================
s9 = slides_new[3]
set_ph(s9, "多源搜索状态建模", "观测时效场 Recency 与综合信息价值场构建", 9)

# Left: Recency mechanism
section_bar(s9, "观测时效场 Recency", X0, Y0, HALF_W, C_AMBER_MID)
card(s9, "时间戳累加机制",
     "系统为每个自由网格维护一个整数时间戳。当某格处于传感器视场内被观测时，计数器归零；否则每步累加 1。\n\n• 刚被扫描的区域 → Recency ≈ 0（刷新收益低）\n• 长期未扫描的区域 → Recency 持续增大（刷新收益高）",
     X0, Y0 + Inches(0.42), HALF_W, Inches(1.6),
     accent=C_AMBER_MID, bg=C_AMBER_LIGHT, border=C_AMBER_BORDER, tc=C_AMBER_DEEP)

card(s9, "时效衰减函数",
     "通过指数衰减函数将原始时间戳映射为归一化的时效权重。衰减时间常数 τ 控制遗忘速度—— τ 大则容忍旧信息更久，τ 小则倾向频繁复扫。",
     X0, Y0 + Inches(2.15), HALF_W, Inches(0.9),
     accent=C_AMBER_MID, tc=C_AMBER_DEEP)

# Right: Fusion
rx = X0 + HALF_W + Inches(0.5)
section_bar(s9, "综合信息价值场构建", rx, Y0, HALF_W, C_SLATE)

formula(s9,
        "search_info_map(x)\n  = w₁ × norm( GP_Clue(x) )\n  + w₂ × norm( Intensity(x) )",
        rx, Y0 + Inches(0.5), HALF_W, Inches(1.0),
        label="信息价值场融合公式")

card(s9, "归一化处理",
     "GP Clue 场和 Intensity 场的数值范围与量纲不同，系统对两者分别进行空间归一化（Min-Max），映射到 [0,1] 后加权融合，确保贡献可比。",
     rx, Y0 + Inches(1.65), HALF_W, Inches(0.8),
     accent=C_BLUE_MID, tc=C_BLUE_DEEP)

card(s9, "设计决策：Recency 独立于融合",
     "Recency 刻画的是"时效性"而非"搜索价值本身"。将时效注入路径段评分（recency_bias 乘积项），可避免时效维度过度稀释线索证据与目标信念的浓度。",
     rx, Y0 + Inches(2.6), HALF_W, Inches(0.8),
     accent=C_AMBER_MID, bg=C_AMBER_LIGHT, border=C_AMBER_BORDER, tc=C_AMBER_DEEP)

# Bottom: Chapter summary
SUM_Y = Y0 + Inches(3.35)
section_bar(s9, "本章小结", X0, SUM_Y, FULL_W, RGBColor(55, 65, 81))
card(s9, "多源互补的信息场体系",
     "GP Clue（线索空间推断）、Intensity（目标概率信念）、Recency（时效约束）三者从不同物理维度描述搜索价值。前两者融合为统一的 search_info_map 驱动路径规划，时效维度通过路径评分机制独立施加周期复扫约束。分层融合设计确保各信息维度间的解耦与可调节性。",
     X0, SUM_Y + Inches(0.42), FULL_W, Inches(0.7),
     accent=RGBColor(55, 65, 81), tc=C_DARK, tsz=10, bsz=8.5)

print("Slide 9 done: Recency + 融合")

# ================================================================
# Save
# ================================================================
prs.save(SRC)
print(f"\nSaved to {SRC}")
print(f"Total slides: {len(prs.slides)}")
