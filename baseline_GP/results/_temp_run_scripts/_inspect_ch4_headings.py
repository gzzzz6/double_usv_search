from pathlib import Path
from docx import Document
p=Path(r'F:\pythonprojects\my_report.docx')
doc=Document(p)
for i, para in enumerate(doc.paragraphs):
    t=para.text.strip()
    if t.startswith(('4 ', '4.', '第四章')):
        print(i, t)
