"""Atomic explicit table edits on private SQLite, with retrieval and scope checks."""
import pytest
from local_cli.core.memory import MemoryError
from tests.memory_v1.test_m3_service import service,call


def row(record,**patch):
    return dict(memoryId=record['memoryId'],revision=record['revision'],text=record['canonicalText'],kind=record['kind'],scope=record['scopeKind'],sensitive=record['sensitivityClass']=='SENSITIVE',consentSensitive=False)|patch


def setup(tmp_path):
    work=tmp_path/'alpha';work.mkdir();other=tmp_path/'beta';other.mkdir()
    return service(tmp_path/'state'),work,other


def remember(s,work,text='Synthetic preference for brief examples',**args):
    result=call(s,work,'remember',kind='PREFERENCE',text=text,**args)
    return call(s,work,'show',memoryId=result['memoryId'],includeSensitive=True)['record']


def test_edit_preserves_id_overwrites_fields_and_reprojects_search_after_reopen(tmp_path):
    s,work,other=setup(tmp_path)
    try:
        original=remember(s,work)
        call(s,work,'edit',records=[row(original,text='Synthetic instructions with diagrams',kind='PROCEDURE',scope='GLOBAL_PROFILE')])
        shown=call(s,other,'show',memoryId=original['memoryId'])['record']
        assert shown['revision']==2 and shown['kind']=='PROCEDURE' and shown['scopeKind']=='GLOBAL_PROFILE'
        assert call(s,work,'search',query='brief')['records']==[]
        assert call(s,other,'search',scope='ALL',query='diagrams')['records'][0]['memoryId']==original['memoryId']
        s.store.close();s=service(tmp_path/'state')
        call(s,other,'edit',records=[row(shown,scope='WORKSPACE')])
        with pytest.raises(MemoryError):call(s,work,'show',memoryId=original['memoryId'])
        assert call(s,other,'show',memoryId=original['memoryId'])['record']['revision']==3
    finally:s.store.close()


def test_invalid_or_stale_second_row_rolls_back_entire_batch(tmp_path):
    s,work,_=setup(tmp_path)
    try:
        a=remember(s,work);b=remember(s,work,'Synthetic other preference')
        for bad in [row(b,revision=99),row(b,kind='WORKSPACE_FACT',scope='GLOBAL_PROFILE')]:
            with pytest.raises(MemoryError):call(s,work,'edit',records=[row(a,text='Must not commit'),bad])
            assert call(s,work,'show',memoryId=a['memoryId'])['record']==a
        with pytest.raises(MemoryError):call(s,work,'edit',records=[row(a),row(a)])
    finally:s.store.close()


def test_sensitive_reclassification_requires_consent_and_detected_data_stays_protected(tmp_path):
    s,work,_=setup(tmp_path)
    try:
        original=remember(s,work)
        with pytest.raises(MemoryError):call(s,work,'edit',records=[row(original,sensitive=True)])
        call(s,work,'edit',records=[row(original,sensitive=True,consentSensitive=True)])
        hidden=call(s,work,'show',memoryId=original['memoryId'])['record']
        assert hidden['canonicalText'].startswith('[SENSITIVE')
        sensitive=call(s,work,'show',memoryId=original['memoryId'],includeSensitive=True)['record']
        with pytest.raises(MemoryError):call(s,work,'edit',records=[row(sensitive,sensitive=False)])
        call(s,work,'edit',records=[row(sensitive,sensitive=False,consentSensitive=True)])
        normal=call(s,work,'show',memoryId=original['memoryId'])['record'];assert normal['sensitivityClass']=='NORMAL'
        with pytest.raises(MemoryError):call(s,work,'edit',records=[row(normal,text='My medical diagnosis is diabetes',sensitive=False,consentSensitive=True)])
        assert call(s,work,'show',memoryId=original['memoryId'])['record']==normal
    finally:s.store.close()


def test_cannot_edit_another_projects_private_record(tmp_path):
    s,work,other=setup(tmp_path)
    try:
        private=remember(s,work)
        with pytest.raises(MemoryError):call(s,other,'edit',records=[row(private,scope='GLOBAL_PROFILE')])
    finally:s.store.close()
