from pathlib import Path
from docx import Document
p=Path(r'F:\pythonprojects\my_report.docx')
doc=Document(p)
for i, para in enumerate(doc.paragraphs):
    t=para.text.strip()
    if 490 <= i <= 505 or t.startswith('4.5'):
        print(f'{i}: style={para.style.name!r} text={t}')
