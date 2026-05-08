# -*- coding: utf-8 -*-
"""
Replace section 4.7 in my_report.docx with content from ch4_7_restructured.md.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import re
import shutil

REPORT_PATH = r'F:\pythonprojects\my_report.docx'
BACKUP_PATH = r'F:\pythonprojects\my_report_sec47_backup_20260507.docx'
shutil.copy2(REPORT_PATH, BACKUP_PATH)
print('Backup:', BACKUP_PATH)

doc = Document(REPORT_PATH)
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
BS = chr(92)

body = doc.element.body

# ========================================
# STEP 1: Remove old P540-P552
# ========================================
all_paras = body.findall('{%s}p' % W)
print('Total paragraphs before:', len(all_paras))

p_elements = [c for c in list(body) if c.tag == '{%s}p' % W]
to_remove = p_elements[540:553]
for p in reversed(to_remove):
    body.remove(p)

all_paras = body.findall('{%s}p' % W)
print('Total paragraphs after:', len(all_paras))

# ========================================
# STEP 2: Helper functions
# ========================================

def make_run(text, font_name='Times New Roman', ea_font='宋体',
             size_pt=12, bold=False, italic=False):
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:eastAsia'), ea_font)
    rFonts.set(qn('w:cs'), font_name)
    rPr.append(rFonts)

    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), str(int(size_pt * 2)))
    rPr.append(sz)

    szCs = OxmlElement('w:szCs')
    szCs.set(qn('w:val'), str(int(size_pt * 2)))
    rPr.append(szCs)

    if bold:
        rPr.append(OxmlElement('w:b'))
    if italic:
        rPr.append(OxmlElement('w:i'))

    r.append(rPr)

    t = OxmlElement('w:t')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    r.append(t)
    return r


def make_empty_tab_run():
    r = OxmlElement('w:r')
    r.append(OxmlElement('w:tab'))
    return r


def make_pPr(style_name, spacing_before=None, spacing_after=None,
             first_line_indent='720', alignment=None, line_spacing=None):
    pPr = OxmlElement('w:pPr')
    ps = OxmlElement('w:pStyle')
    ps.set(qn('w:val'), style_name)
    pPr.append(ps)

    ind = OxmlElement('w:ind')
    if first_line_indent is not None:
        ind.set(qn('w:firstLine'), first_line_indent)
    pPr.append(ind)

    sp = OxmlElement('w:spacing')
    if spacing_before is not None:
        sp.set(qn('w:before'), spacing_before)
    if spacing_after is not None:
        sp.set(qn('w:after'), spacing_after)
    if line_spacing is not None:
        sp.set(qn('w:line'), line_spacing)
        sp.set(qn('w:lineRule'), 'auto')
    else:
        sp.set(qn('w:line'), '300')
        sp.set(qn('w:lineRule'), 'auto')
    pPr.append(sp)

    if alignment is not None:
        jc = OxmlElement('w:jc')
        jc.set(qn('w:val'), alignment)
        pPr.append(jc)

    return pPr


def make_body_paragraph(text):
    p = OxmlElement('w:p')
    p.append(make_pPr('Normal'))
    p.append(make_run(text))
    return p


def make_body_paragraph_mixed(segments):
    """segments: list of (text, is_italic) tuples."""
    p = OxmlElement('w:p')
    p.append(make_pPr('Normal'))
    for text, is_italic in segments:
        p.append(make_run(text, italic=is_italic))
    return p


def make_heading_paragraph(text):
    p = OxmlElement('w:p')
    p.append(make_pPr('二级标题', spacing_before='240', spacing_after='120',
                       first_line_indent='0', alignment='left',
                       line_spacing='240'))
    p.append(make_run(text, ea_font='黑体', size_pt=14, bold=True))
    return p


def make_displayed_var_paragraph(var_text):
    p = OxmlElement('w:p')
    p.append(make_pPr('Normal', first_line_indent='0',
                       alignment='center'))
    p.append(make_run(var_text, italic=True))
    return p


def make_formula_paragraph(eq_text, num):
    p = OxmlElement('w:p')

    pPr = OxmlElement('w:pPr')
    ps = OxmlElement('w:pStyle')
    ps.set(qn('w:val'), 'aff4')
    pPr.append(ps)
    ind = OxmlElement('w:ind')
    ind.set(qn('w:firstLine'), '0')
    pPr.append(ind)

    tabs = OxmlElement('w:tabs')
    ct = OxmlElement('w:tab')
    ct.set(qn('w:val'), 'center')
    ct.set(qn('w:pos'), '4153')
    tabs.append(ct)
    rt = OxmlElement('w:tab')
    rt.set(qn('w:val'), 'right')
    rt.set(qn('w:pos'), '8306')
    tabs.append(rt)
    pPr.append(tabs)
    p.append(pPr)

    # Tab before math
    p.append(make_empty_tab_run())

    # Bookmark
    bm_id = str(700 + int(num))
    bm_name = '_Toc_S47_F' + num
    bm_start = OxmlElement('w:bookmarkStart')
    bm_start.set(qn('w:id'), bm_id)
    bm_start.set(qn('w:name'), bm_name)
    p.append(bm_start)

    # Equation text
    eq_run = OxmlElement('w:r')
    eq_rPr = OxmlElement('w:rPr')
    eq_rFonts = OxmlElement('w:rFonts')
    eq_rFonts.set(qn('w:ascii'), 'Cambria Math')
    eq_rFonts.set(qn('w:hAnsi'), 'Cambria Math')
    eq_rPr.append(eq_rFonts)
    eq_sz = OxmlElement('w:sz')
    eq_sz.set(qn('w:val'), '24')
    eq_rPr.append(eq_sz)
    eq_run.append(eq_rPr)
    eq_t = OxmlElement('w:t')
    eq_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    eq_t.text = eq_text
    eq_run.append(eq_t)
    p.append(eq_run)

    # Tab + number
    num_run = OxmlElement('w:r')
    num_run.append(OxmlElement('w:tab'))
    num_t = OxmlElement('w:t')
    num_t.text = '（%s）' % num
    num_run.append(num_t)
    p.append(num_run)

    # Bookmark end
    bm_end = OxmlElement('w:bookmarkEnd')
    bm_end.set(qn('w:id'), bm_id)
    p.append(bm_end)

    # TOC field (hidden)
    def _fld(typ):
        r = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')
        rPr.append(OxmlElement('w:vanish'))
        r.append(rPr)
        fc = OxmlElement('w:fldChar')
        fc.set(qn('w:fldCharType'), typ)
        r.append(fc)
        return r

    p.append(_fld('begin'))
    instr_r = OxmlElement('w:r')
    instr_rPr = OxmlElement('w:rPr')
    instr_rPr.append(OxmlElement('w:vanish'))
    instr_r.append(instr_rPr)
    instr = OxmlElement('w:instrText')
    insns = 'http://www.w3.org/XML/1998/namespace'
    instr.set('{%s}space' % insns, 'preserve')
    instr.text = ' TC "公式（%s）" %sf E %sl 1 ' % (num, BS, BS)
    instr_r.append(instr)
    p.append(instr_r)
    p.append(_fld('end'))

    return p


# ========================================
# STEP 3: Build new paragraphs
# ========================================
new_paras = []

# 1. Heading
new_paras.append(make_heading_paragraph('4.7 在线滚动执行与重规划机制'))

# 2. Body paragraph 1
new_paras.append(make_body_paragraph_mixed([
    ('本文的单艇路径规划不是一次性生成完整全局搜索路线，而是采用在线滚动执行与重规划机制。每次规划器根据当前综合信息价值场、观测时效性状态、USV 当前位置和已知静态地图生成一段短时域候选路径，并从中选择当前最优的 ', False),
    ('segment_path', True),
    ('。该路径段被提交后，USV 不会立即长期锁定整条搜索路线，而是在一个较短的提交窗口内逐步执行，并在执行过程中持续更新场模型和重规划条件。', False),
]))

# 3. Body paragraph 2
new_paras.append(make_body_paragraph_mixed([
    ('每次重规划得到的 ', False),
    ('segment_path', True),
    (' 最长为 8 步，但系统并不要求 USV 必须完整执行这 8 步。为了在路径连续性和在线适应性之间取得平衡，本文引入基于路径段长度的短期提交窗口。设本轮规划得到的路径段长度为：', False),
]))

# 4-7. Displayed variables
for var_name in ['L_seg', 'W_min', 'W_max', 'd']:
    new_paras.append(make_displayed_var_paragraph(var_name))

# 8. Lead-in to formulas
new_paras.append(make_body_paragraph('则本轮提交执行窗口可表示为：'))

# 9-10. Two formulas, both numbered (54)
new_paras.append(make_formula_paragraph(
    'W_base = max(W_min, floor(L_seg / d))', '54'))
new_paras.append(make_formula_paragraph(
    'W_commit = min(W_max, W_base)', '54'))

# 11. Default values
new_paras.append(make_body_paragraph(
    '本文实现中，默认基础提交窗口 W_min = 4，最大提交窗口 W_max = 10，路径长度折减因子 d = 2。由于单艇主线的路径段最大长度为 8 步，因此当 L_seg = 8 时，提交窗口通常为：'))

# 12. W_commit = 4
new_paras.append(make_displayed_var_paragraph('W_commit = 4'))

# 13. Body paragraph 3
new_paras.append(make_body_paragraph(
    '也就是说，USV 通常只承诺执行当前路径段中的前若干步，而不会把完整路径段视为不可改变的长期计划。这样既避免每一步都重新规划造成的路径抖动，也避免在信息场已经变化时继续执行过时路径。'))

# 14. Body paragraph 4
new_paras.append(make_body_paragraph_mixed([
    ('在执行过程中，系统将选中的路径段写入当前状态中的 ', False),
    ('committed_segment', True),
    ('，并记录对应的 ', False),
    ('committed_viewpoint', True),
    ('、', False),
    ('committed_anchor', True),
    (' 和当前路径评分诊断信息。每个仿真时间步内，USV 只执行 ', False),
    ('committed_segment', True),
    (' 的下一格，而不是一次性执行完整路径段。完成单步移动后，系统会更新 USV 轨迹、传感器观测结果、目标发现状态、GP clue 场、target intensity 场、recency / staleness 状态以及综合信息价值场。也就是说，路径执行与场模型更新是交替发生的，而不是先规划完整路线再一次性执行到底。', False),
]))

# 15. Body paragraph 5
new_paras.append(make_body_paragraph_mixed([
    ('当提交窗口尚未用尽且路径段仍然有效时，USV 会继续沿当前 ', False),
    ('committed_segment', True),
    (' 执行下一步；当满足重规划条件时，系统才重新调用路径规划器。本文中的重规划触发条件主要包括：初始时刻尚无已提交路径段、当前提交窗口已经用尽、', False),
    ('committed_segment', True),
    (' 已经为空或只剩当前位置、下一步路径因地图约束或安全约束被判定无效等情况。若触发重规划，系统会基于最新的综合信息价值场、观测时效性状态和当前位置重新生成候选路径段，并选择新的最优路径段提交执行。', False),
]))

# 16. Body paragraph 6
new_paras.append(make_body_paragraph(
    '因此，本文的单艇搜索过程可以概括为"规划一段、提交几步、单步执行、观测更新、必要时重规划"的闭环过程。该机制使 USV 能够在保持一定路径连续性的同时，根据新的观测信息及时调整搜索方向。路径段提交窗口保证了短期执行稳定性，重规划触发机制保证了信息场变化或路径失效时的在线适应能力。需要强调的是，提交窗口仅控制路径执行节奏，不改变候选路径段评分函数，也不改变 GP clue、target intensity、recency 或综合信息价值场的语义。'))

# ========================================
# STEP 4: Insert after P539
# ========================================
all_paras = body.findall('{%s}p' % W)
insert_after = all_paras[539]
insert_idx = list(body).index(insert_after)

for j, p in enumerate(new_paras):
    body.insert(insert_idx + 1 + j, p)

print('Inserted %d paragraphs' % len(new_paras))

# Save
doc.save(REPORT_PATH)
print('Saved.')
