from pathlib import Path
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

p=Path(r'F:\pythonprojects\my_report.docx')
doc=Document(p)
body=doc.element.body
blocks=[]
for child in body.iterchildren():
    if isinstance(child, CT_P):
        para=Paragraph(child, doc)
        text=para.text.strip()
        has_pic=bool(child.xpath('.//pic:pic'))
        blocks.append(('P', text, para.style.name, has_pic, para))
    elif isinstance(child, CT_Tbl):
        blocks.append(('T', '<TABLE>', '', False, Table(child, doc)))

print('BODY_BLOCKS', len(blocks))
for idx,(kind,text,style,has_pic,obj) in enumerate(blocks):
    if has_pic or text.startswith(('图','表')) or kind=='T':
        prev = blocks[idx-1][1][:60] if idx>0 else ''
        nxt = blocks[idx+1][1][:60] if idx+1<len(blocks) else ''
        print(f'{idx}: kind={kind} style={style!r} pic={has_pic} text={text[:100]}')
        print('   prev:', prev)
        print('   next:', nxt)
