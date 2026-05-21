"""
Rebuild Slide 8 (index 7) of USV_PPT_gemini.pptx.
Corrected content: hit_update_intensity = target clearance + redistribution (NOT Bayesian upward).
Visual style: matches the template (Source Han Sans CN, Microsoft YaHei, #385894 borders, #0070C0 text, #64A0FF containers).
"""
import sys
import shutil
sys.stdout.reconfigure(encoding='utf-8')

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

PPT_PATH = r"E:\毕设PPT\USV_PPT_gemini.pptx"
BAK_PATH = r"E:\毕设PPT\USV_PPT_gemini_bak2.pptx"
shutil.copy2(PPT_PATH, BAK_PATH)
print(f"Backup → {BAK_PATH}")

prs = Presentation(PPT_PATH)
slide = prs.slides[7]  # Index 7 = Slide 8

# ---- Template Color Constants ----
C_CONTAINER_BORDER = RGBColor(0x64, 0xA0, 0xFF)  # #64A0FF  big container border
C_CARD_BORDER      = RGBColor(0x38, 0x58, 0x94)  # #385894  card border
C_CARD_TEXT        = RGBColor(0x00, 0x70, 0xC0)  # #0070C0  card text (blue)
C_BG_FILL          = RGBColor(0xEC, 0xF4, 0xFC)  # #ECF4FC  light info box fill
C_BG_BORDER        = RGBColor(0xBD, 0xD1, 0xE5)  # #BDD1E5  light info box border
C_ARROW            = RGBColor(0x64, 0x96, 0xFF)  # #6496FF  arrow fill
C_BODY_TEXT        = RGBColor(0x20, 0x2A, 0x34)  # #202A34  dark body text
C_SECTION_BG       = RGBColor(0x00, 0x70, 0xC0)  # blue section header bg
C_WHITE            = RGBColor(0xFF, 0xFF, 0xFF)
C_SECTION_BG_GREEN = RGBColor(0x00, 0x8B, 0x5A)  # dark green for miss section header
C_GREEN_CARD       = RGBColor(0x38, 0x7E, 0x5A)  # green card border
C_GREEN_TEXT       = RGBColor(0x00, 0x6B, 0x3C)  # dark green text

# ---- Font Constants ----
F_NAV  = "Source Han Sans CN"
F_BODY = "Microsoft YaHei"

# ---- Slide dimensions ----
SW = prs.slide_width   # 12192000 EMU = 13.333 in
SH = prs.slide_height  # 6858000  EMU = 7.5 in

# Helper: EMU from inches
def I(x): return int(x * 914400)

# ============================================================
# Step 1: Retain template shapes (0-14), delete body (15+)
# ============================================================
n_template = 15  # Keep first 15 shapes (background, nav, title placeholders)
original = len(slide.shapes)
for j in range(original - 1, n_template - 1, -1):
    slide.shapes._spTree.remove(slide.shapes[j]._element)
print(f"Deleted {original - n_template} body shapes. Remaining: {len(slide.shapes)}")

# ============================================================
# Step 2: Fill placeholders
# ============================================================
for shape in slide.shapes:
    if shape.is_placeholder:
        idx = shape.placeholder_format.idx
        if idx == 16:
            shape.text = "多源搜索状态建模"
            for para in shape.text_frame.paragraphs:
                para.font.name = F_NAV
        elif idx == 14:
            shape.text = "Intensity 信念场更新——目标清障与质量再分配机制"
            for para in shape.text_frame.paragraphs:
                para.font.name = "思源宋体"
        elif idx in (1, 2):
            shape.text = "8"
    elif hasattr(shape, 'text_frame'):
        for para in shape.text_frame.paragraphs:
            if para.text.strip() in ("综述和评述", "思路和内容", "过程和方法", "成果与展望", "背景和意义"):
                pass  # keep nav text as-is

# ============================================================
# Drawing Helpers (all matching template style)
# ============================================================

def add_container(slide, left, top, width, height):
    """Large rounded rect container with #64A0FF border (matches Slide 5 columns)."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.fill.background()
    s.line.color.rgb = C_CONTAINER_BORDER
    s.line.width = Pt(1.5)
    return s

def add_section_header(slide, text, left, top, width, height, bg_color=None):
    """Colored header bar with white text, matching template section style."""
    bg = bg_color or C_SECTION_BG
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.fill.solid()
    s.fill.fore_color.rgb = bg
    s.line.fill.background()
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = I(0.08)
    tf.margin_top = tf.margin_bottom = I(0.03)
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = PP_ALIGN.CENTER
    p.font.name = F_BODY
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = C_WHITE
    return s

def add_info_box(slide, left, top, width, height):
    """Light blue background box (#ECF4FC fill, #BDD1E5 border)."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.fill.solid()
    s.fill.fore_color.rgb = C_BG_FILL
    s.line.color.rgb = C_BG_BORDER
    s.line.width = Pt(1.1)
    return s

def add_card(slide, title, body_lines, left, top, width, height,
             border_color=None, text_color=None, body_sz=9.5, title_sz=11):
    """Template-style rounded card: #385894 border, #0070C0 title, dark body."""
    bc = border_color or C_CARD_BORDER
    tc = text_color or C_CARD_TEXT

    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.fill.background()
    s.line.color.rgb = bc
    s.line.width = Pt(1.0)

    tb = slide.shapes.add_textbox(left + I(0.1), top + I(0.08), width - I(0.2), height - I(0.16))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = I(0)

    # Title paragraph
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = F_BODY
    p.font.size = Pt(title_sz)
    p.font.bold = True
    p.font.color.rgb = tc
    p.space_after = Pt(5)

    # Body paragraphs
    for line in body_lines:
        pb = tf.add_paragraph()
        pb.text = line
        pb.font.name = F_BODY
        pb.font.size = Pt(body_sz)
        pb.font.color.rgb = C_BODY_TEXT
        pb.space_before = Pt(3)
        pb.line_spacing = 1.2

    return s

def add_step_card(slide, label, text, left, top, width, height,
                  border_color=None, text_color=None):
    """Small step card with bold label and description, template style."""
    bc = border_color or C_CARD_BORDER
    tc = text_color or C_CARD_TEXT

    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.fill.background()
    s.line.color.rgb = bc
    s.line.width = Pt(1.0)

    tb = slide.shapes.add_textbox(left + I(0.08), top + I(0.06), width - I(0.16), height - I(0.12))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = I(0)

    p = tf.paragraphs[0]
    p.text = label
    p.font.name = F_BODY
    p.font.size = Pt(10.5)
    p.font.bold = True
    p.font.color.rgb = tc

    pb = tf.add_paragraph()
    pb.text = text
    pb.font.name = F_BODY
    pb.font.size = Pt(9)
    pb.font.color.rgb = C_BODY_TEXT
    pb.space_before = Pt(3)
    pb.line_spacing = 1.2

def add_textbox(slide, text, left, top, width, height,
                sz=11, bold=False, color=None, align=PP_ALIGN.LEFT):
    """Simple textbox, template style."""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = I(0)
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.name = F_BODY
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = color or C_BODY_TEXT

def add_arrow_right(slide, left, top, w=I(0.18), h=I(0.1)):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left, top, w, h)
    a.fill.solid()
    a.fill.fore_color.rgb = C_ARROW
    a.line.fill.background()

def add_arrow_down(slide, left, top, w=I(0.1), h=I(0.18)):
    a = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, left, top, w, h)
    a.fill.solid()
    a.fill.fore_color.rgb = C_ARROW
    a.line.fill.background()

def add_formula_card(slide, formula, left, top, width, height, label=None):
    """Code/formula display matching template info box style."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.fill.solid()
    s.fill.fore_color.rgb = RGBColor(0xF0, 0xF6, 0xFF)
    s.line.color.rgb = C_BG_BORDER
    s.line.width = Pt(1.1)

    tb = slide.shapes.add_textbox(left + I(0.12), top + I(0.07), width - I(0.24), height - I(0.14))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = I(0)

    if label:
        pl = tf.paragraphs[0]
        pl.text = label
        pl.font.name = F_BODY
        pl.font.size = Pt(8.5)
        pl.font.bold = True
        pl.font.color.rgb = C_CARD_TEXT
        pl.space_after = Pt(4)

        pf = tf.add_paragraph()
        pf.text = formula
        pf.font.name = "Consolas"
        pf.font.size = Pt(11)
        pf.font.bold = True
        pf.font.color.rgb = C_BODY_TEXT
    else:
        pf = tf.paragraphs[0]
        pf.text = formula
        pf.font.name = "Consolas"
        pf.font.size = Pt(11)
        pf.font.bold = True
        pf.font.color.rgb = C_BODY_TEXT

# ============================================================
# Step 3: Build Slide 8 Content
# ============================================================
#
# Layout (13.33" × 7.5"):
#   - Y=1.3"~1.65": Intro info box (full width)
#   - Y=1.75"~6.1": Two containers side-by-side
#       Left  [0.45", 1.75"] 5.65" wide: Miss Update (空扫未命中，贝叶斯衰减)
#       Right [6.25", 1.75"] 6.45" wide: Hit Update (确证命中，清障+再分配)
#   - Y=6.15"~6.75": Bottom summary bar
# ============================================================

# --- Intro box ---
ib = add_info_box(slide, I(0.45), I(1.28), I(12.42), I(0.38))
add_textbox(slide,
    "本系统的 Intensity 信念场包含两种性质截然不同的更新机制，分别对应"传感器空扫未命中"和"目标被确证捕获"两种物理事件，不可混淆。",
    I(0.57), I(1.32), I(12.18), I(0.30),
    sz=10, color=C_BODY_TEXT)

# --- Left container: Miss Update ---
L_LEFT = I(0.45)
T_COL  = I(1.76)
W_LEFT = I(5.65)
H_COL  = I(4.35)
add_container(slide, L_LEFT, T_COL, W_LEFT, H_COL)

# Section header
add_section_header(slide, "Miss Update — 空扫未命中 → 贝叶斯概率衰减",
                   L_LEFT + I(0.08), T_COL + I(0.08),
                   W_LEFT - I(0.16), I(0.36))

# Mechanism card
add_card(slide,
    "物理事件",
    ["USV 传感器完整扫描了网格 x，但未探测到目标信号（返回空扫结果）。",
     "此时说明目标在该网格的概率应当降低。"],
    L_LEFT + I(0.12), T_COL + I(0.54),
    W_LEFT - I(0.24), I(0.74))

# Formula
add_formula_card(slide,
    "updated[x, y]  *=  (1.0 − p_detect(x))",
    L_LEFT + I(0.12), T_COL + I(1.38),
    W_LEFT - I(0.24), I(0.52),
    label="核心操作：对传感器视场内每个网格，按探测概率做乘法衰减")

# Key properties
add_card(slide,
    "关键属性",
    ["• 目标概率不归零：因为传感器存在漏检率（p_detect < 1），空扫后仍保留残余概率，防止错误地丢弃真实目标。",
     "• 全局质量守恒选项：preserve_total_mass=True 时，衰减后的质量被重归一化，维持全场期望目标总数不变（适用于信念场整体重调）。",
     "• 越扫越收敛：同一网格被反复空扫后，概率趋向于 0，排除低概率区域，引导 USV 转向高价值位置。"],
    L_LEFT + I(0.12), T_COL + I(2.0),
    W_LEFT - I(0.24), I(1.45),
    body_sz=9)

# ---- Comparison label ---
add_textbox(slide, "对比：与标准贝叶斯更新一致",
            L_LEFT + I(0.12), T_COL + I(3.58),
            W_LEFT - I(0.24), I(0.24),
            sz=9, bold=False, color=RGBColor(0x55, 0x88, 0x44))

# --- Right container: Hit Update ---
L_RIGHT = I(6.25)
W_RIGHT = I(6.45)
add_container(slide, L_RIGHT, T_COL, W_RIGHT, H_COL)

# Section header
add_section_header(slide, "Hit Update — 确证命中 → 目标清障 + 质量再分配",
                   L_RIGHT + I(0.08), T_COL + I(0.08),
                   W_RIGHT - I(0.16), I(0.36),
                   bg_color=C_GREEN_CARD)

# Physical event
add_card(slide,
    "物理事件",
    ["传感器在网格 (hx, hy) 处确证探测到目标（触发 Hit 事件），目标被锁定、计入统计，该位置搜索价值归零。",
     "这不是"疑似信号使概率上升"，而是"已发现目标，此处清账"。"],
    L_RIGHT + I(0.12), T_COL + I(0.54),
    W_RIGHT - I(0.24), I(0.8),
    border_color=C_GREEN_CARD, text_color=C_GREEN_TEXT)

# Three-step flow
T_STEPS = T_COL + I(1.44)
STEP_W = (W_RIGHT - I(0.24)) / 3 - I(0.05)

add_step_card(slide, "① 清零探测区",
    "命中点邻域 r_hit 范围内所有格子强制清零\nupdated[x, y] = 0\n标记 excluded_mask = True",
    L_RIGHT + I(0.12), T_STEPS, STEP_W, I(1.55),
    border_color=C_GREEN_CARD, text_color=C_GREEN_TEXT)

add_arrow_right(slide, L_RIGHT + I(0.12) + STEP_W + I(0.02), T_STEPS + I(0.65))

add_step_card(slide, "② 减少剩余目标数",
    "全场期望目标总量扣减：\nresolved = mass_before\n         − hit_count\n表示已发现 k 个目标后，剩余期望目标减少。",
    L_RIGHT + I(0.12) + STEP_W + I(0.22), T_STEPS, STEP_W, I(1.55),
    border_color=C_GREEN_CARD, text_color=C_GREEN_TEXT)

add_arrow_right(slide, L_RIGHT + I(0.12) + STEP_W * 2 + I(0.24), T_STEPS + I(0.65))

add_step_card(slide, "③ 全场质量再分配",
    "将剩余目标质量等比例重新分配至非排除网格：\nupdated *= resolved / current_mass\n驱动 USV 转向新的高价值区域继续搜索。",
    L_RIGHT + I(0.12) + STEP_W * 2 + I(0.44), T_STEPS, STEP_W, I(1.55),
    border_color=C_GREEN_CARD, text_color=C_GREEN_TEXT)

# Formula
add_formula_card(slide,
    "resolved_mass = max(mass_before − hit_count, 0.0)\n"
    "updated       = renormalize( updated, resolved_mass, exclude=hit_area )",
    L_RIGHT + I(0.12), T_COL + I(3.1),
    W_RIGHT - I(0.24), I(0.65),
    label="核心操作代码逻辑（core_intensity.py: hit_update_intensity）")

# Design intent note
add_card(slide,
    "设计意图",
    ["将已捕获目标的"概率质量"从其探测区抹去，剩余质量重新扩散至全场其他未排除区域，使整个信念场的期望值精确反映"已发现N个、还有M个目标未知"的状态，逻辑自洽且数值稳健。"],
    L_RIGHT + I(0.12), T_COL + I(3.88),
    W_RIGHT - I(0.24), I(0.35),
    border_color=C_GREEN_CARD, text_color=C_GREEN_TEXT, body_sz=8.5, title_sz=0)

# --- Bottom summary bar ---
sum_ib = add_info_box(slide, I(0.45), I(6.17), I(12.42), I(0.55))
add_textbox(slide,
    "核心区别摘要：Miss Update 保留概率但向下衰减（典型贝叶斯），Hit Update 直接清除目标区域并重新分配全局质量（目标注销 + 场重归一化）。两种机制共同维护 Intensity 信念场的数值一致性与物理可解释性。",
    I(0.57), I(6.21), I(12.18), I(0.47),
    sz=9.5, color=C_BODY_TEXT)

# ============================================================
# Step 4: Save
# ============================================================
prs.save(PPT_PATH)
print(f"Saved → {PPT_PATH}")
print(f"Slide 8 rebuilt with {len(slide.shapes)} total shapes.")
