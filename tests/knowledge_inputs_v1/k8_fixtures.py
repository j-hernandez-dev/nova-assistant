"""Prospective synthetic K8 recipes; no observed ranks/model outputs as input."""
import io
import json
import zipfile
from base64 import b64decode
from pathlib import Path
from xml.sax.saxutils import escape
from tests.knowledge_inputs_v1.pdf_fixtures import pdf_bytes,CORRUPT_HEADER

FIXTURES=Path(__file__).parent/'fixtures'


def load():return json.loads((FIXTURES/'k8_core_v1.json').read_text(encoding='utf-8'))
def protocol():return json.loads((FIXTURES/'k8_protocol_v1.json').read_text(encoding='utf-8'))


def payload(row):
    text=row.get('text','');fmt=row.get('format');structure=row.get('structure')
    if row.get('base64'):return b64decode(row['base64'])
    if row.get('recipe')=='fake-pdf':return CORRUPT_HEADER
    if row.get('recipe')=='encrypted-pdf':return pdf_bytes(password='SYNTHETIC_TEST_ONLY')
    if row.get('recipe')=='image-pdf':return pdf_bytes(('image',))
    if row.get('recipe')=='truncated-pdf':return pdf_bytes()[:-40]
    if fmt=='txt':return text.encode(row.get('encoding','utf-8'))
    if fmt=='md':return ('# Synthetic station\n\n'+text+'\n').encode()
    if fmt=='py':return ('# Synthetic code source\nCALIBRATION = '+repr(text)+'\n').encode()
    if fmt=='json':
        obj=text if structure=='scalar' else {'nested':{'facts':[text]}} if structure=='nested' else \
            {'key/with~escape':text} if structure=='escaped-pointer' else {'record':text}
        return json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()
    if fmt=='csv':
        return ('name,note\nfirst,"'+text+'\ncontinued"\nsecond,tail' if structure=='multiline' else
                'name,note\nstation,"'+text+'"').encode()
    if fmt=='html':
        body='<h1>Synthetic station</h1><p>'+escape(text)+'</p>'
        if structure=='inline-link':body='<p><a href="https://synthetic.invalid/ref">'+escape(text)+'</a></p>'
        if structure=='script-style':body='<p>'+escape(text)+'<script>FORBIDDEN_SCRIPT_TEXT</script><style>FORBIDDEN_STYLE_TEXT</style></p>'
        if structure=='plain-div':body='<div>'+escape(text)+'</div>'
        if structure=='table':body='<table><tr><td>'+escape(text)+'</td></tr></table>'
        return ('<html><title>Synthetic</title><body>'+body+'</body></html>').encode()
    if fmt=='pdf':
        return pdf_bytes(((text,'Synthetic companion first page'),('Synthetic second page',))) if structure=='two-pages' else pdf_bytes(((text,),))
    if fmt=='docx':
        p='<w:p><w:r><w:t>'+escape(text)+'</w:t></w:r></w:p>'
        if structure=='heading':p='<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>'+escape(text)+'</w:t></w:r></w:p>'
        if structure=='table':p='<w:tbl><w:tr><w:tc>'+p+'</w:tc></w:tr></w:tbl>'
        if structure=='unicode':p='<w:p><w:r><w:t>Información sintética válida: '+escape(text)+'</w:t></w:r></w:p>'
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+p+'</w:body></w:document>'
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr(zipfile.ZipInfo('word/document.xml',(2026,1,1,0,0,0)),xml.encode())
            if structure=='external-relation':
                z.writestr(zipfile.ZipInfo('word/_rels/document.xml.rels',(2026,1,1,0,0,0)),
                    b'<Relationships><Relationship Target="https://uncontacted.invalid/" TargetMode="External"/></Relationships>')
        return out.getvalue()
    return text.encode('utf-8')
