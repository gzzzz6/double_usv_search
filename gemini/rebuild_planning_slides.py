import sys
import json
import shutil
import os
sys.stdout.reconfigure(encoding='utf-8')

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from PIL import Image

# Load planning content
with open(r"F:\pythonprojects\gemini\slides_planning_content.json", "r", encoding="utf-8") as f:
    T = json.load(f)

# Reset from the clean codex template to get rid of any historical misalignments or dirtied slides!
CODEX_TEMPLATE = r"E:\毕设PPT\USV_PPT_codex.pptx"
PPT_PATH = r"E:\毕设PPT\USV_PPT_gemini.pptx"
BAK_PATH = r"E:\毕设PPT\USV_PPT_gemini_bak4.pptx"

if os.path.exists(PPT_PATH):
    shutil.copy2(PPT_PATH, BAK_PATH)
    print("Backup created at:", BAK_PATH)

shutil.copy2(CODEX_TEMPLATE, PPT_PATH)
print("Copied clean template from USV_PPT_codex.pptx to USV_PPT_gemini.pptx")

prs = Presentation(PPT_PATH)

# Common styling constants
C_CONTAINER = RGBColor(0x64, 0xA0, 0xFF) # #64A0FF (Subtle sky blue border)
C_CARD_BD   = RGBColor(0x38, 0x58, 0x94) # #385894 (Steel blue card border)
C_CARD_TX   = RGBColor(0x00, 0x70, 0xC0) # #0070C0 (Professional title blue)
C_BG_FILL   = RGBColor(0xEC, 0xF4, 0xFC) # #ECF4FC
C_BG_BD     = RGBColor(0xBD, 0xD1, 0xE5) # #BDD1E5
C_DARK      = RGBColor(0x20, 0x2A, 0x34) # #202A34 (Charcoal gray text)
C_WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
C_BLUE_HDR  = RGBColor(0x00, 0x70, 0xC0)
C_GREEN_HDR = RGBColor(0x00, 0x7A, 0x50)
C_GREEN_BD  = RGBColor(0x2E, 0x7D, 0x50)
C_GREEN_TX  = RGBColor(0x00, 0x60, 0x3A)

F_BODY = "Microsoft YaHei"

def I(x): return int(x * 914400)

# Delete existing body shapes (keep 0-13 indices, i.e. first 14 background/header shapes)
def clean_slide_body(slide):
    orig = len(slide.shapes)
    for j in range(orig - 1, 13, -1):
        slide.shapes._spTree.remove(slide.shapes[j]._element)
    print(f"Cleaned body. Slide has {len(slide.shapes)} shapes left.")

# Proactively recreate Left-Top Subtitle and Main Title with precise original coordinate and clean TextBoxes
def setup_slide_headers(slide, nav_text, title_text):
    # 1. Detect and delete existing left-top nav and title shapes to avoid duplicate or legacy text overlapping
    shapes_to_delete = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            # Detect left-top Nav (T < 0.5 in, L < 3.0 in)
            if shape.top < I(0.5) and shape.left < I(3.0):
                shapes_to_delete.append(shape)
            # Detect Main Title (0.5 in <= T < 1.1 in, L < 3.0 in)
            elif I(0.5) <= shape.top < I(1.1) and shape.left < I(3.0):
                shapes_to_delete.append(shape)
                
    for shape in shapes_to_delete:
        try:
            slide.shapes._spTree.remove(shape._element)
        except Exception as e:
            print(f"Error removing header shape {shape.name}: {e}")
            
    # 2. Add brand-new, perfectly clean TextBoxes with correct styling, sizes and 0-margin formatting
    # Left-Top Nav TextBox (precise template coordinate: L=0.97 in, T=0.17 in)
    nav_box = slide.shapes.add_textbox(I(0.97), I(0.17), I(5.0), I(0.42))
    tf_nav = nav_box.text_frame
    tf_nav.word_wrap = True
    tf_nav.margin_left = tf_nav.margin_right = tf_nav.margin_top = tf_nav.margin_bottom = 0
    p_nav = tf_nav.paragraphs[0]
    p_nav.text = nav_text
    p_nav.font.name = "Source Han Sans CN"
    p_nav.font.size = Pt(27) # EXACT correct size from the LZU template!
    p_nav.font.bold = True
    p_nav.font.color.rgb = C_WHITE
    
    # Main Title TextBox (precise template coordinate: L=1.04 in, T=0.93 in)
    title_box = slide.shapes.add_textbox(I(1.04), I(0.93), I(11.0), I(0.40))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    tf_title.margin_left = tf_title.margin_right = tf_title.margin_top = tf_title.margin_bottom = 0
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.name = "Microsoft YaHei"
    p_title.font.size = Pt(21)
    p_title.font.bold = True
    p_title.font.color.rgb = RGBColor(0x20, 0x2A, 0x34)
    
    print(f"Perfectly recreated headers: Nav='{nav_text}' (27Pt), Title='{title_text}' (21Pt)")

# Proportionate image resizing inside container bounding box
def add_fit_picture(slide, img_path, left, top, max_w, max_h):
    if not os.path.exists(img_path):
        print(f"Warning: Image not found at {img_path}")
        return None
    try:
        with Image.open(img_path) as img:
            img_w, img_h = img.size
        
        ratio = img_w / img_h
        target_ratio = max_w / max_h
        
        if ratio > target_ratio:
            width = max_w
            height = int(max_w / ratio)
            top = top + (max_h - height) // 2
        else:
            height = max_h
            width = int(max_h * ratio)
            left = left + (max_w - width) // 2
            
        print(f"Adding picture: {os.path.basename(img_path)} at L={left}, T={top}, W={width}, H={height}")
        return slide.shapes.add_picture(img_path, left, top, width, height)
    except Exception as e:
        print(f"Error adding picture {img_path}: {e}")
        return None

# Shape Helpers
def container(slide, left, top, w, h):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.fill.background()
    s.line.color.rgb = C_CONTAINER
    s.line.width = Pt(1.5)

def hdr(slide, text, left, top, w, h, bg):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = bg
    s.line.fill.background()
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = I(0.08)
    tf.margin_top = tf.margin_bottom = I(0.02)
    p = tf.paragraphs[0]
    p.text = text; p.alignment = PP_ALIGN.CENTER
    p.font.name = F_BODY; p.font.size = Pt(12); p.font.bold = True
    p.font.color.rgb = C_WHITE

def infobox(slide, left, top, w, h):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = C_BG_FILL
    s.line.color.rgb = C_BG_BD; s.line.width = Pt(1.1)

def card(slide, title, body_lines, left, top, w, h,
         bd=None, tx=None, title_sz=10.5, body_sz=8.5):
    bd = bd or C_CARD_BD; tx = tx or C_CARD_TX
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = C_WHITE
    s.line.color.rgb = bd; s.line.width = Pt(1.0)
    
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = 3 # MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.22)
    tf.margin_right = Inches(0.22)
    tf.margin_top = Inches(0.16)
    tf.margin_bottom = Inches(0.16)
    
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = F_BODY
    p.font.size = Pt(title_sz)
    p.font.bold = True
    p.font.color.rgb = tx
    p.space_after = Pt(5)
    
    for line in body_lines:
        pb = tf.add_paragraph()
        pb.text = line
        pb.font.name = F_BODY
        pb.font.size = Pt(body_sz)
        pb.font.bold = False
        pb.font.color.rgb = C_DARK
        pb.space_before = Pt(3.5)
        pb.line_spacing = 1.15

def formula_box(slide, formula, left, top, w, h, label=None, label_color=None):
    label_color = label_color or C_CARD_TX
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = RGBColor(0xF0, 0xF6, 0xFF)
    s.line.color.rgb = C_BG_BD; s.line.width = Pt(1.1)
    
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = 3 # MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.22)
    tf.margin_right = Inches(0.22)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.12)
    
    if label:
        pl = tf.paragraphs[0]
        pl.text = label
        pl.font.name = F_BODY
        pl.font.size = Pt(8.5)
        pl.font.bold = True
        pl.font.color.rgb = label_color
        pl.space_after = Pt(4)
        pf = tf.add_paragraph()
    else:
        pf = tf.paragraphs[0]
        
    pf.text = formula
    pf.font.name = "Consolas"
    pf.font.size = Pt(10.5)
    pf.font.bold = True
    pf.font.color.rgb = C_DARK

def txtbox(slide, text, left, top, w, h, sz=10, bold=False, color=None):
    tb = slide.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = I(0)
    p = tf.paragraphs[0]
    p.text = text; p.font.name = F_BODY
    p.font.size = Pt(sz); p.font.bold = bold
    p.font.color.rgb = color or C_DARK

# ===============================================================
# GLOBAL NAVBAR REBUILD MECHANISM
# ===============================================================
def clean_navbar_shapes(slide):
    shapes_to_delete = []
    for shape in slide.shapes:
        # Match shapes in the navbar bounding zone (expanded down to 0.68 inches to thoroughly catch outlines/underlines)
        if shape.top < I(0.68) and shape.left > I(5.0):
            shapes_to_delete.append(shape)
            
    for shape in shapes_to_delete:
        try:
            slide.shapes._spTree.remove(shape._element)
        except Exception as e:
            print(f"Error removing navbar shape {shape.name}: {e}")

def add_navbar(slide, active_index):
    # Equal distance L-coords for the 5 navigation headers
    lefts = [I(6.16), I(7.55), I(8.94), I(10.33), I(11.71)]
    texts = ["背景和意义", "综述和评述", "思路和内容", "过程和方法", "成果与展望"]
    W = I(1.30)
    H = I(0.39)
    T = I(0.25)
    
    for i in range(5):
        tb = slide.shapes.add_textbox(lefts[i], T, W, H)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        
        p = tf.paragraphs[0]
        p.text = texts[i]
        p.alignment = PP_ALIGN.CENTER
        p.font.name = "Source Han Sans CN"
        p.font.size = Pt(10.5)
        p.font.bold = True
        
        if i == active_index - 1:
            # Active Highlight (pure white)
            p.font.color.rgb = RGBColor(255, 255, 255)
            # Add premium thick white underline shape
            line = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                lefts[i] + I(0.12), 
                T + H - I(0.06), 
                W - I(0.24), 
                I(0.02)
            )
            line.fill.solid()
            line.fill.fore_color.rgb = RGBColor(255, 255, 255)
            line.line.fill.background()
        else:
            # Inactive (semi-dark steel blue for contrast)
            p.font.color.rgb = RGBColor(0x8D, 0xAA, 0xD4)

# ===============================================================
# BUILD Slide 9 (Single-USV Planning Framework)
# ===============================================================
print("\n--- Generating Slide 9 ---")
slide9 = prs.slides[8] # index 8
clean_slide_body(slide9)
setup_slide_headers(slide9, T["s10_nav"], T["s10_title"])

# Subtitle info box
infobox(slide9, I(0.45), I(1.28), I(12.42), I(0.38))
txtbox(slide9, T["s10_subtitle"], I(0.57), I(1.33), I(12.18), I(0.30), sz=9.8, bold=True, color=C_CARD_TX)

# Left Column
T_COL = I(1.76); H_COL = I(4.90)
L_L = I(0.45); W_L = I(4.8)
container(slide9, L_L, T_COL, W_L, H_COL)
hdr(slide9, "滚动决策控制模型", L_L+I(0.08), T_COL+I(0.08), W_L-I(0.16), I(0.36), C_BLUE_HDR)

card(slide9, T["s10_card1_title"], T["s10_card1_body"],
     L_L+I(0.12), T_COL+I(0.54), W_L-I(0.24), I(1.95), body_sz=8.2)

card(slide9, T["s10_card2_title"], T["s10_card2_body"],
     L_L+I(0.12), T_COL+I(2.60), W_L-I(0.24), I(1.95), body_sz=8.2)

# Right Column
L_R = I(5.35); W_R = I(7.52)
container(slide9, L_R, T_COL, W_R, H_COL)
hdr(slide9, "单艇自主规划决策状态转移闭环流程", L_R+I(0.08), T_COL+I(0.08), W_R-I(0.16), I(0.36), C_GREEN_HDR)

add_fit_picture(slide9, r"F:\pythonprojects\images\单艇流程图.png",
                L_R+I(0.15), T_COL+I(0.54), W_R-I(0.30), H_COL-I(0.66))

clean_navbar_shapes(slide9)
add_navbar(slide9, 4) # Section 4 (过程和方法)


# ===============================================================
# BUILD Slide 10 (Hotspot clustering and viewpoints)
# ===============================================================
print("\n--- Generating Slide 10 ---")
slide10 = prs.slides[9] # index 9
clean_slide_body(slide10)
setup_slide_headers(slide10, T["s11_nav"], T["s11_title"])

# Subtitle info box
infobox(slide10, I(0.45), I(1.28), I(12.42), I(0.38))
txtbox(slide10, T["s11_subtitle"], I(0.57), I(1.33), I(12.18), I(0.30), sz=9.8, bold=True, color=C_CARD_TX)

# Left Column
L_L = I(0.45); W_L = I(6.1)
container(slide10, L_L, T_COL, W_L, H_COL)
hdr(slide10, "高价值热力聚类与视点生成算法", L_L+I(0.08), T_COL+I(0.08), W_L-I(0.16), I(0.36), C_BLUE_HDR)

card(slide10, T["s11_card1_title"], T["s11_card1_body"],
     L_L+I(0.12), T_COL+I(0.54), W_L-I(0.24), I(1.70), body_sz=8.2)

formula_box(slide10, T["s11_formula"],
            L_L+I(0.12), T_COL+I(2.32), W_L-I(0.24), I(0.65),
            label=T["s11_formula_label"])

card(slide10, T["s11_card2_title"], T["s11_card2_body"],
     L_L+I(0.12), T_COL+I(3.05), W_L-I(0.24), I(1.70), body_sz=8.2)

# Right Column
L_R = I(6.65); W_R = I(6.22)
container(slide10, L_R, T_COL, W_R, H_COL)
hdr(slide10, "几何投影语义与局部流程对应", L_R+I(0.08), T_COL+I(0.08), W_R-I(0.16), I(0.36), C_GREEN_HDR)

add_fit_picture(slide10, r"F:\pythonprojects\images\ch4_3_anchor_viewpoint_semantics.png",
                L_R+I(0.12), T_COL+I(0.54), W_R-I(0.24), I(2.40))

card(slide10, "空间几何与障碍约束说明",
     ["• 黄色边界圈定高斯过程(GP)中检测出的高价值热力聚类区域。",
      "• 橙点为加权计算出的聚类锚点(Anchor)，若位于障碍内则通过欧氏距离近邻法投影至自由栅格。",
      "• 白色斑点表示最终选定的候选视点(Viewpoint)，确保传感器扫射射程能覆盖锚点，避免近身碰撞。"],
     L_R+I(0.12), T_COL+I(3.05), W_R-I(0.24), I(1.70),
     bd=C_GREEN_BD, tx=C_GREEN_TX, body_sz=8.0)

clean_navbar_shapes(slide10)
add_navbar(slide10, 4) # Section 4 (过程和方法)


# ===============================================================
# BUILD Slide 11 (Utility optimization and evaluation)
# ===============================================================
print("\n--- Generating Slide 11 ---")
slide11 = prs.slides[10] # index 10
clean_slide_body(slide11)
setup_slide_headers(slide11, T["s12_nav"], T["s12_title"])

# Subtitle info box
infobox(slide11, I(0.45), I(1.28), I(12.42), I(0.38))
txtbox(slide11, T["s12_subtitle"], I(0.57), I(1.33), I(12.18), I(0.30), sz=9.8, bold=True, color=C_CARD_TX)

# Left Column
L_L = I(0.45); W_L = I(6.1)
container(slide11, L_L, T_COL, W_L, H_COL)
hdr(slide11, "局部避障A*与多目标决策博弈机制", L_L+I(0.08), T_COL+I(0.08), W_L-I(0.16), I(0.36), C_BLUE_HDR)

card(slide11, T["s12_card1_title"], T["s12_card1_body"],
     L_L+I(0.12), T_COL+I(0.54), W_L-I(0.24), I(1.55), body_sz=8.2)

formula_box(slide11, T["s12_formula"],
            L_L+I(0.12), T_COL+I(2.18), W_L-I(0.24), I(0.68),
            label=T["s12_formula_label"])

card(slide11, T["s12_card2_title"], T["s12_card2_body"],
     L_L+I(0.12), T_COL+I(2.95), W_L-I(0.24), I(1.80), body_sz=8.2)

# Right Column
L_R = I(6.65); W_R = I(6.22)
container(slide11, L_R, T_COL, W_R, H_COL)
hdr(slide11, "多路博弈评估与最优路径选取", L_R+I(0.08), T_COL+I(0.08), W_R-I(0.16), I(0.36), C_GREEN_HDR)

add_fit_picture(slide11, r"F:\pythonprojects\images\候选路径段评分与最优路径段选择.png",
                L_R+I(0.12), T_COL+I(0.54), W_R-I(0.24), I(2.40))

card(slide11, "多路决策博弈机制说明",
     ["• 搜索信息增益(R_info)和时效增益(R_novel)分别拉扯着USV的搜索偏好：前者驱使艇前往高概率区捕获目标，后者驱使艇前往边缘盲区排除漏检。",
      "• 代价因子(C_path)和转向惩罚则起到了“稳定器”的作用，过滤掉那些虽然收益稍高但需要频繁大角度掉头、能耗极高且不安全的突变路径段。",
      "• 三者博弈得出最优短路径段(图中红色高亮)，保障了搜索综合效能最优。"],
     L_R+I(0.12), T_COL+I(3.05), W_R-I(0.24), I(1.70),
     bd=C_GREEN_BD, tx=C_GREEN_TX, body_sz=8.0)

clean_navbar_shapes(slide11)
add_navbar(slide11, 4) # Section 4 (过程和方法)


# ===============================================================
# REBUILD ALL TOP NAV BARS ON OTHER SLIDES FOR 100% ALIGNMENT
# ===============================================================
print("\n--- Rebuilding Navbars for All Other Slides ---")
for idx in range(2, 24): # Slide 3 (idx=2) to Slide 24 (idx=23)
    # Skip our generated Slides 9, 10, 11 because they are already handled!
    if idx in [8, 9, 10]:
        continue
        
    slide = prs.slides[idx]
    
    # Identify Section index for the active section highlighting:
    # 1 -> 背景和意义 (Slide 3)
    # 2 -> 综述和评述 (Slide 4)
    # 3 -> 思路和内容 (Slide 5-8)
    # 4 -> 过程和方法 (Slide 12-22, idx 11-21)
    # 5 -> 成果与展望 (Slide 23-24, idx 22-23)
    if idx == 2:
        sect = 1
    elif idx == 3:
        sect = 2
    elif idx in [4, 5, 6, 7]:
        sect = 3
    elif idx in range(11, 22):
        sect = 4
        setup_slide_headers(slide, "过程和方法", "文字")
    elif idx in [22, 23]:
        sect = 5
        setup_slide_headers(slide, "成果与展望", "文字")
    else:
        continue
        
    print(f"Rebuilding navbar on Slide {idx+1} to highlight Section {sect}")
    clean_navbar_shapes(slide)
    add_navbar(slide, sect)

# Save the PowerPoint presentation
prs.save(PPT_PATH)
print("\nAll tasks completed successfully!")
