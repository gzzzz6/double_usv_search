from pathlib import Path
from docx import Document
p=Path(r'F:\pythonprojects\my_report.docx')
doc=Document(p)
for i, para in enumerate(doc.paragraphs):
    t=para.text.strip()
    if t.startswith('4.4') or 472 <= i <= 489:
        print(f'{i}: style={para.style.name!r} text={t}')
