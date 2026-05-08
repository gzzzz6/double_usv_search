from pathlib import Path
from docx import Document
import re
p=Path(r'F:\pythonprojects\my_report.docx')
doc=Document(p)
for i,para in enumerate(doc.paragraphs):
    t=para.text.strip()
    if re.fullmatch(r'（\d+）', t) or re.search(r'（\d+）', t):
        print(i, para.style.name, t)
