"""Real local filesystem fixtures; no content is parsed or sent to a model."""
import os
from pathlib import Path
import subprocess
import pytest
from local_cli.core.knowledge import KnowledgeError
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition


def read(reader,path,cancelled=lambda:False,progress=lambda size:None):
    return b''.join(reader.read(str(path),cancelled=cancelled,progress=progress))


@pytest.mark.parametrize('size',[0,1,255,256,257,8192])
def test_real_bounded_reads_unicode_path_bytes_and_progress(tmp_path,size):
    file=tmp_path/'synthetic ñ 日本語.bin';payload=(b'\x00\xffsynthetic'*1000)[:size];file.write_bytes(payload)
    sizes=[];reader=LocalHostFileAcquisition(unit_bytes=256)
    blocks=list(reader.read(str(file),cancelled=lambda:False,progress=sizes.append))
    assert b''.join(blocks)==payload and all(len(b)<=256 for b in blocks)
    assert sizes==list(range(256,size+1,256))+([size] if size%256 else [])


@pytest.mark.parametrize('path_kind',['relative','missing','directory','nul'])
def test_real_invalid_targets_fail_closed_without_opening(tmp_path,path_kind):
    path={'relative':'relative.txt','missing':tmp_path/'missing','directory':tmp_path,'nul':'x\x00y'}[path_kind]
    with pytest.raises(KnowledgeError) as err: read(LocalHostFileAcquisition(),path)
    assert err.value.code=='SOURCE_NOT_AUTHORIZED'


def test_oversize_denied_and_read_growth_never_published(tmp_path):
    path=tmp_path/'synthetic';path.write_bytes(b'abcd')
    with pytest.raises(KnowledgeError) as err: read(LocalHostFileAcquisition(max_bytes=3),path)
    assert err.value.code=='SOURCE_TOO_LARGE'


@pytest.mark.parametrize('moment',['before','during'])
def test_real_cancel_before_or_between_units(tmp_path,moment):
    path=tmp_path/'synthetic';path.write_bytes(b'12345678');sizes=[]
    with pytest.raises(KnowledgeError) as err:
        read(LocalHostFileAcquisition(unit_bytes=2),path,
             cancelled=lambda:moment=='before' or len(sizes)>=1,progress=sizes.append)
    assert err.value.code=='IMPORT_CANCELLED'
    assert sizes==([] if moment=='before' else [2])


def test_real_file_modified_during_reads_is_stale(tmp_path):
    path=tmp_path/'synthetic';path.write_bytes(b'01234567')
    def mutate(size):
        if size==2: path.write_bytes(b'abcdefghijk')
    with pytest.raises(KnowledgeError) as err: read(LocalHostFileAcquisition(unit_bytes=2),path,progress=mutate)
    assert err.value.code=='STALE_SOURCE'


def test_real_hardlink_is_not_an_import_authority(tmp_path):
    target=tmp_path/'target';target.write_bytes(b'synthetic external bytes')
    link=tmp_path/'link';os.link(target,link)
    with pytest.raises(KnowledgeError) as err: read(LocalHostFileAcquisition(),link)
    assert err.value.code=='SOURCE_NOT_AUTHORIZED'
    assert target.read_bytes()==b'synthetic external bytes'


def test_real_directory_redirect_not_followed(tmp_path):
    external=tmp_path/'outside';external.mkdir();(external/'file').write_bytes(b'synthetic external bytes')
    link=tmp_path/'redirect'
    if os.name=='nt':
        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(external)],capture_output=True)
        assert result.returncode==0, result.stderr
    else: link.symlink_to(external,target_is_directory=True)
    with pytest.raises(KnowledgeError) as err: read(LocalHostFileAcquisition(),link/'file')
    assert err.value.code=='SOURCE_NOT_AUTHORIZED'
    assert (external/'file').read_bytes()==b'synthetic external bytes'
