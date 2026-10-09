"""Adversarial parser contracts, not changing the frozen K8 quality corpus."""
import io
import zipfile
import pytest
from local_cli.infrastructure.knowledge_extraction import extract_bytes
from local_cli.core.knowledge import KnowledgeError


@pytest.mark.parametrize('value',['"Synthetic scalar ARC7777"','17','true','null'])
def test_json_scalar_is_one_root_value_not_character_array(value):
    result=extract_bytes(value.encode(),'scalar.json')
    assert len(result.blocks)==1 and result.blocks[0][2].coordinates['pointer']==''


def test_csv_multiline_locators_use_real_physical_lines():
    result=extract_bytes(b'a,b\nfirst,"one\ntwo"\nlast,three','sample.csv')
    assert [dict(b[2].coordinates) for b in result.blocks]==[
        dict(lineStart=1,lineEnd=1),dict(lineStart=2,lineEnd=3),dict(lineStart=4,lineEnd=4)]


def test_html_hidden_code_removed_and_visible_div_links_retained_as_metadata():
    result=extract_bytes(b'<div>A<a href="https://example.test/">Visible</a><script>HIDDEN</script><style>HIDDEN2</style>Z</div>','page.html')
    assert all('HIDDEN' not in b[1] for b in result.blocks)
    assert 'Visible' in '\n'.join(b[1] for b in result.blocks)
    assert any('example.test' in str(b[3]) for b in result.blocks)


def test_docx_container_entry_limit_enforced_before_expansion():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>safe</w:t></w:r></w:p></w:body></w:document>')
        for n in range(2000):z.writestr('synthetic/'+str(n),'')
    with pytest.raises(KnowledgeError) as error:extract_bytes(out.getvalue(),'large.docx')
    assert error.value.code=='SOURCE_TOO_LARGE'


@pytest.mark.parametrize('name',['../escape','/absolute','word\\escape','C:/escape'])
def test_docx_container_names_cannot_be_used_as_paths(name):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('word/document.xml','<document/>');z.writestr(name,'ignored')
    with pytest.raises(KnowledgeError) as error:extract_bytes(out.getvalue(),'sample.docx')
    assert error.value.code=='CORRUPT_DOCUMENT'


def test_docx_container_ratio_bound_before_expansion():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('word/document.xml','A'*200000)
    with pytest.raises(KnowledgeError) as error:extract_bytes(out.getvalue(),'ratio.docx')
    assert error.value.code=='SOURCE_TOO_LARGE'
