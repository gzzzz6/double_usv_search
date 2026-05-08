from pathlib import Path
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
p=Path(r'F:\pythonprojects\my_report.docx')
doc=Document(p)
blocks=[]
for child in doc.element.body.iterchildren():
    if isinstance(child, CT_P):
        para=Paragraph(child, doc)
        txt=para.text.strip()
        if txt.startswith('表6-') or isinstance(child, CT_P):
            blocks.append(('P', txt, para.style.name))
    elif isinstance(child, CT_Tbl):
        blocks.append(('T','<TABLE>',''))
for i,b in enumerate(blocks):
    if 720 <= i <= 775:
        print(i,b)
