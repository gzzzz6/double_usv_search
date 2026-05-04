from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


OUT = Path(r"F:\pythonprojects\py_try\python_learn.docx")


def set_font(run, name="Microsoft YaHei", size=None, color=None, bold=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    if bold is not None:
        run.bold = bold


def shade(paragraph, fill):
    p_pr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    p_pr.append(shd)


def add_heading(doc, text, level=1, color=(31, 78, 121)):
    paragraph = doc.add_heading(level=level)
    run = paragraph.add_run(text)
    set_font(run, size=15 if level == 1 else 13, color=color, bold=True)
    return paragraph


def add_body(doc, text, color=(0, 0, 0), bold=False):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    set_font(run, color=color, bold=bold)
    return paragraph


def add_code(doc, text):
    paragraph = doc.add_paragraph(style="CodeBlock")
    shade(paragraph, "F2F2F2")
    run = paragraph.add_run(text)
    set_font(run, name="Consolas", size=10, color=(64, 64, 64))
    return paragraph


def add_key(doc, text):
    paragraph = doc.add_paragraph(style="KeyPoint")
    shade(paragraph, "FFF2CC")
    run = paragraph.add_run(text)
    set_font(run, color=(192, 80, 77), bold=True)
    return paragraph


def build_doc():
    doc = Document()

    styles = doc.styles
    styles["Normal"].font.name = "Microsoft YaHei"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    styles["Normal"].font.size = Pt(11)

    for style_name in ["Title", "Heading 1", "Heading 2"]:
        style = styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    code_style = styles.add_style("CodeBlock", WD_STYLE_TYPE.PARAGRAPH)
    code_style.font.name = "Consolas"
    code_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    code_style.font.size = Pt(10)

    key_style = styles.add_style("KeyPoint", WD_STYLE_TYPE.PARAGRAPH)
    key_style.font.name = "Microsoft YaHei"
    key_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    key_style.font.size = Pt(11)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Python 学习笔记：第一阶段 · 第一节")
    set_font(run, size=20, color=(31, 78, 121), bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("主题：Python 程序如何运行、print 输出、变量与基础数据类型")
    set_font(run, size=11, color=(89, 89, 89))

    add_heading(doc, "一、Python 程序如何运行")
    add_body(
        doc,
        "Python 文件通常以 .py 结尾。运行程序时，Python 解释器会从文件第一行开始，按照从上到下的顺序逐行执行代码。",
    )
    add_key(doc, "核心理解：Python 是解释执行的语言。你写好代码后，通常不需要手动编译，直接交给 Python 解释器运行。")
    add_code(doc, 'print("第一行")\nprint("第二行")\nprint("第三行")')
    add_body(doc, "上面的代码会依次输出“第一行”“第二行”“第三行”。代码顺序会直接影响程序运行结果。", color=(89, 89, 89))

    add_heading(doc, "二、print() 输出")
    add_body(doc, "print() 用来把内容显示到屏幕上。它是初学 Python 时最常用的函数之一。")
    add_code(doc, 'print("Hello, Python!")\nprint(123)\nprint(3.14)')
    add_key(doc, "注意：字符串需要加引号，数字通常不需要加引号。")
    add_code(doc, 'print(100)     # 这是数字 100\nprint("100")   # 这是字符串 "100"')
    add_body(doc, "两行代码显示出来都像 100，但它们的类型不同：数字可以直接参与数学运算，字符串本质上是文本。", color=(89, 89, 89))

    add_heading(doc, "三、变量是什么")
    add_body(doc, "变量可以理解为“给一个值起名字”。程序后续可以通过这个名字继续使用这个值。")
    add_code(doc, 'age = 18\nname = "Alice"\nheight = 1.68')
    add_body(doc, '这里 age 表示 18，name 表示 "Alice"，height 表示 1.68。')
    add_key(doc, "核心理解：变量名是给人和程序看的标签，变量中保存的是具体的值。")
    add_code(doc, "price = 10\ncount = 3\ntotal = price * count\nprint(total)")
    add_body(doc, "这段程序会输出 30，因为 total 保存了 price * count 的计算结果。", color=(89, 89, 89))

    add_heading(doc, "四、基础数据类型")
    add_body(doc, "第一阶段先重点掌握 4 种基础类型：int、float、str、bool。")

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for i, text in enumerate(["类型", "含义", "示例", "说明"]):
        paragraph = table.rows[0].cells[i].paragraphs[0]
        run = paragraph.add_run(text)
        set_font(run, color=(255, 255, 255), bold=True)
        shade(paragraph, "4472C4")

    rows = [
        ("int", "整数", "18", "没有小数部分的数字"),
        ("float", "小数", "1.75", "带小数部分的数字"),
        ("str", "字符串", '"Python"', "文本，需要加引号"),
        ("bool", "布尔值", "True / False", "表示真或假，首字母必须大写"),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            run = cells[i].paragraphs[0].add_run(text)
            set_font(run)

    add_code(doc, 'age = 18              # int\nheight = 1.75         # float\nname = "Tom"          # str\nis_student = True     # bool')
    add_key(doc, '注意：True 和 False 是布尔值；"True" 和 "False" 是字符串。它们不是同一种东西。')

    add_heading(doc, "五、使用 type() 查看类型")
    add_body(doc, "type() 可以查看一个值或变量的数据类型。")
    add_code(doc, 'print(type(18))\nprint(type(3.14))\nprint(type("hello"))\nprint(type(True))')
    add_body(doc, "输出结果类似 <class 'int'>、<class 'float'>、<class 'str'>、<class 'bool'>。")
    add_key(doc, "学习建议：遇到不确定的数据时，可以先用 type() 看它到底是什么类型。")

    add_heading(doc, "六、字符串拼接与类型转换")
    add_body(doc, "字符串可以用 + 进行拼接。")
    add_code(doc, 'first_name = "Tom"\nlast_name = "Smith"\nfull_name = first_name + " " + last_name\nprint(full_name)')
    add_body(doc, "但是字符串不能直接和数字相加。")
    add_code(doc, 'age = 18\nprint("年龄是" + age)   # 这会报错')
    add_body(doc, "如果确实要拼接，需要先把数字转换成字符串。")
    add_code(doc, 'age = 18\nprint("年龄是" + str(age))')
    add_key(doc, 'str(age) 的作用是把数字 18 转成字符串 "18"。')

    add_heading(doc, "七、f-string：推荐的格式化输出方式")
    add_body(doc, "f-string 是 Python 中非常常用的字符串格式化方式。它可以把变量自然地放进字符串中。")
    add_code(doc, 'name = "张三"\nage = 20\nheight = 1.75\nprint(f"大家好，我叫{name}，今年{age}岁，身高{height}米。")')
    add_key(doc, "推荐习惯：需要把变量放进句子里输出时，优先使用 f-string。")

    add_heading(doc, "八、本节小结")
    for item in [
        "Python 程序从上到下逐行执行。",
        "print() 用于输出内容。",
        "变量是给值起的名字，可以保存数字、文本、布尔值等。",
        "基础类型包括 int、float、str、bool。",
        "type() 可以查看数据类型。",
        "字符串和数字不能直接用 + 拼接，需要类型转换。",
        "f-string 是更推荐的变量输出方式。",
    ]:
        paragraph = doc.add_paragraph(style="List Bullet")
        run = paragraph.add_run(item)
        set_font(run)

    add_heading(doc, "九、复习题")
    for question in [
        'print(100) 和 print("100") 的区别是什么？',
        'True 和 "True" 的区别是什么？',
        '"年龄是" + age 为什么会报错？',
        'f"我的年龄是{age}" 中的大括号有什么作用？',
        "变量 total = price * count 中，total 保存的是什么？",
    ]:
        paragraph = doc.add_paragraph(style="List Number")
        run = paragraph.add_run(question)
        set_font(run)

    doc.add_page_break()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Python 学习笔记：第二阶段 · 第一节")
    set_font(run, size=20, color=(31, 78, 121), bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("主题：核心数据结构入门与列表 list")
    set_font(run, size=11, color=(89, 89, 89))

    add_heading(doc, "一、为什么需要数据结构")
    add_body(
        doc,
        "第一阶段主要处理单个值，比如一个姓名、一个年龄、一个成绩。但真实程序经常需要处理一组数据，例如多个学生、多个成绩、多个商品。",
    )
    add_code(doc, 'name = "张三"\nage = 20\n\nstudents = ["张三", "李四", "王五"]\nscores = [88, 92, 75]')
    add_key(doc, "核心理解：数据结构就是组织数据的方式。列表适合保存一组有顺序的数据。")

    add_heading(doc, "二、Python 常见核心数据结构")
    add_body(doc, "第二阶段会逐步学习 4 种常见结构：list、tuple、dict、set。")

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for i, text in enumerate(["结构", "中文名", "基本写法", "典型用途"]):
        paragraph = table.rows[0].cells[i].paragraphs[0]
        run = paragraph.add_run(text)
        set_font(run, color=(255, 255, 255), bold=True)
        shade(paragraph, "4472C4")

    rows = [
        ("list", "列表", "[1, 2, 3]", "保存一组有顺序、可修改的数据"),
        ("tuple", "元组", "(1, 2, 3)", "保存一组有顺序、通常不修改的数据"),
        ("dict", "字典", '{"name": "张三"}', "保存键值对，适合描述对象信息"),
        ("set", "集合", "{1, 2, 3}", "保存不重复的数据，适合去重"),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            run = cells[i].paragraphs[0].add_run(text)
            set_font(run)

    add_heading(doc, "三、列表 list 是什么")
    add_body(doc, "列表用中括号 [] 表示，可以在一个变量中保存多个元素。列表中的元素有固定顺序。")
    add_code(doc, 'names = ["张三", "李四", "王五"]\nscores = [88, 92, 75, 60]')
    add_body(doc, "列表中的每一项叫做元素。names 这个列表有 3 个元素，scores 这个列表有 4 个元素。")
    add_key(doc, "核心理解：列表不是一个值，而是一组值的容器。")

    add_heading(doc, "四、下标 index")
    add_body(doc, "列表中的每个元素都有位置编号，这个编号叫下标。Python 的下标从 0 开始。")
    add_code(doc, 'names = ["张三", "李四", "王五"]\n\nprint(names[0])  # 张三\nprint(names[1])  # 李四\nprint(names[2])  # 王五')
    add_key(doc, "注意：第一个元素的下标是 0，不是 1。")
    add_body(doc, "如果访问不存在的下标，例如 names[3]，程序会报错，因为这个列表只有 0、1、2 三个有效下标。", color=(89, 89, 89))

    add_heading(doc, "五、修改列表元素")
    add_body(doc, "列表是可变的。可以通过下标找到某个位置，然后给它重新赋值。")
    add_code(doc, 'names = ["张三", "李四", "王五"]\nnames[1] = "赵六"\nprint(names)')
    add_body(doc, '输出结果是 ["张三", "赵六", "王五"]。原来的 "李四" 被替换成了 "赵六"。')

    add_heading(doc, "六、添加元素 append()")
    add_body(doc, "append() 用来在列表末尾添加一个新元素。")
    add_code(doc, 'fruits = ["苹果", "香蕉", "橘子"]\nfruits.append("西瓜")\nprint(fruits)')
    add_key(doc, "append() 会修改原来的列表，而不是创建一个全新的列表。")

    add_heading(doc, "七、删除元素 remove() 和 pop()")
    add_body(doc, "remove() 按元素的值删除，pop() 按下标删除。")
    add_code(doc, 'fruits = ["苹果", "香蕉", "橘子"]\nfruits.remove("香蕉")\nprint(fruits)')
    add_code(doc, 'names = ["张三", "李四", "王五"]\nnames.pop(1)\nprint(names)')
    add_body(doc, "如果 pop() 不写下标，默认删除最后一个元素。")
    add_key(doc, "选择方法时先想清楚：你是知道要删除的值，还是知道它的位置。")

    add_heading(doc, "八、列表长度 len()")
    add_body(doc, "len() 可以得到列表中元素的数量。")
    add_code(doc, 'names = ["张三", "李四", "王五"]\nprint(len(names))  # 3')
    add_body(doc, "len() 常用于统计数量，也经常和 sum() 一起计算平均值。")

    add_heading(doc, "九、遍历列表 for")
    add_body(doc, "遍历就是把列表中的元素一个一个取出来处理。for 循环是遍历列表最常用的方式。")
    add_code(doc, 'names = ["张三", "李四", "王五"]\n\nfor name in names:\n    print(name)')
    add_key(doc, "核心理解：for name in names 的意思是：每次从 names 里取出一个元素，临时叫它 name。")

    add_heading(doc, "十、带编号遍历 enumerate()")
    add_body(doc, "如果遍历时既需要元素，也需要它是第几个，可以使用 enumerate()。")
    add_code(doc, 'scores = [88, 92, 75]\n\nfor i, score in enumerate(scores, start=1):\n    print(f"第{i}个成绩是：{score}")')
    add_body(doc, "start=1 表示编号从 1 开始，更适合输出给用户看。")

    add_heading(doc, "十一、列表统计")
    add_body(doc, "对于数字列表，可以使用 sum()、max()、min()、len() 做常见统计。")
    add_code(doc, 'scores = [88, 92, 75, 60, 100]\n\ntotal = sum(scores)\nhighest = max(scores)\nlowest = min(scores)\naverage = total / len(scores)\n\nprint(f"总分：{total}")\nprint(f"最高分：{highest}")\nprint(f"最低分：{lowest}")\nprint(f"平均分：{average}")')
    add_key(doc, "平均值的基本公式：总和 / 数量，也就是 sum(scores) / len(scores)。")

    add_heading(doc, "十二、循环累加与计数")
    add_body(doc, "除了使用内置函数，也可以用循环自己统计。这样能帮助理解程序是如何一步步计算结果的。")
    add_code(doc, 'scores = [88, 45, 92, 59, 76, 100]\ncount = 0\n\nfor score in scores:\n    if score >= 60:\n        count = count + 1\n\nprint(f"及格人数：{count}")')
    add_body(doc, "count 初始为 0。每遇到一个及格成绩，就让 count 增加 1。循环结束后，count 中保存的就是及格人数。")

    add_heading(doc, "十三、本节小结")
    for item in [
        "列表 list 用于保存一组有顺序的数据。",
        "列表下标从 0 开始。",
        "可以通过 names[0] 访问元素，也可以通过 names[1] = 新值 修改元素。",
        "append() 用于添加元素，remove() 和 pop() 用于删除元素。",
        "len() 可以统计列表长度。",
        "for 循环可以遍历列表。",
        "enumerate() 可以在遍历时同时得到编号和元素。",
        "sum()、max()、min() 常用于数字列表统计。",
    ]:
        paragraph = doc.add_paragraph(style="List Bullet")
        run = paragraph.add_run(item)
        set_font(run)

    add_heading(doc, "十四、复习题")
    for question in [
        "为什么 names[0] 表示第一个元素？",
        "append() 和 remove() 分别有什么作用？",
        "remove() 和 pop() 的区别是什么？",
        "len(scores) 得到的是什么？",
        "for score in scores 中，score 每次代表什么？",
        "enumerate(scores, start=1) 为什么适合输出“第几个成绩”？",
        "如何计算成绩列表的平均分？",
    ]:
        paragraph = doc.add_paragraph(style="List Number")
        run = paragraph.add_run(question)
        set_font(run)

    section = doc.sections[0]
    section.top_margin = Pt(54)
    section.bottom_margin = Pt(54)
    section.left_margin = Pt(60)
    section.right_margin = Pt(60)

    doc.save(OUT)


if __name__ == "__main__":
    build_doc()
    print(OUT)
