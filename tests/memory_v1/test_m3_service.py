"""M3 explicit control on real private SQLite; no model or user data."""
import json
from uuid import uuid4
import pytest

from local_cli.application.memory import MemoryService, MemoryCommand
from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryError, MemoryKind
from tests.memory_v1.m2_fixtures import open_store, index, LIMITS


def service(state, **kwargs):
    redactor=kwargs.pop('redactor',SecretRedactor(source={}))
    store=open_store(state,redactor=redactor)
    return MemoryService(store=store,lexical=index(store),identity=store,export=store,
                         redactor=redactor,content_limits=LIMITS)


def call(s,workspace,name,**arguments):
    return s.execute('memory_'+name,arguments,workspace=str(workspace),session_id='synthetic-session',
                     operation_id='op-'+str(uuid4()),explicit_user_action=True)


@pytest.mark.parametrize('kind',list(MemoryKind))
def test_explicit_remember_reopen_search_and_inspect_all_types(tmp_path,kind):
    work=tmp_path/'workspace'; work.mkdir()
    s=service(tmp_path/'state')
    remembered=call(s,work,'remember',kind=kind.value,text='Synthetic prefers Unicode ñ 🧠',key='fixture.preference')
    subject=s.subject
    s.store.close()
    s=service(tmp_path/'state')
    assert s.subject==subject
    found=call(s,work,'search',query='prefers Unicode')['records']
    assert len(found)==1 and found[0]['memoryId']==remembered['memoryId']
    shown=call(s,work,'show',memoryId=remembered['memoryId'])['record']
    assert shown['kind']==kind.value and shown['canonicalText']=='Synthetic prefers Unicode ñ 🧠'
    assert shown['explicit'] and shown['sources'][0]['operationId'].startswith('op-')
    assert shown['subjectId']!='synthetic-session' and shown['status']=='ACTIVE'
    s.store.close()


def test_explicit_correction_lineage_stale_revision_and_key_ambiguity(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    old=call(s,work,'remember',kind='PREFERENCE',text='Synthetic uses C sharp',key='example.language')
    with pytest.raises(MemoryError) as conflict:
        call(s,work,'remember',kind='PREFERENCE',text='Synthetic uses Python',key='example.language')
    assert conflict.value.code=='MEMORY_CONFLICT'
    new=call(s,work,'correct',memoryId=old['memoryId'],revision=1,text='Synthetic uses Python')
    assert new['supersedesMemoryId']==old['memoryId']
    assert call(s,work,'show',memoryId=old['memoryId'])['record']['status']=='SUPERSEDED'
    assert call(s,work,'search',query='C sharp')['records']==[]
    assert call(s,work,'search',query='Python')['records'][0]['memoryId']==new['memoryId']
    with pytest.raises(MemoryError): call(s,work,'correct',memoryId=old['memoryId'],revision=1,text='stale')
    s.store.close()


def test_same_exact_explicit_fact_adds_source_not_truth_or_record(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    arguments=dict(kind='PREFERENCE',text='Synthetic likes short examples',key='examples.style')
    first=call(s,work,'remember',**arguments)
    second=call(s,work,'remember',**arguments)
    assert second['memoryId']==first['memoryId'] and second['deduplicated']
    listed=call(s,work,'list')['records']
    assert len(listed)==1 and len(listed[0]['sources'])==2
    assert 'confidence' not in listed[0]
    s.store.close()


def test_workspace_scope_and_global_selection_do_not_cross_leak(tmp_path):
    left=tmp_path/'left'; right=tmp_path/'right'; left.mkdir(); right.mkdir()
    s=service(tmp_path/'state')
    local=call(s,left,'remember',kind='WORKSPACE_FACT',text='Synthetic local convention')
    global_=call(s,left,'remember',kind='PREFERENCE',text='Synthetic global preference',scope='GLOBAL_PROFILE')
    assert call(s,right,'list')['records']==[]
    assert [r['memoryId'] for r in call(s,right,'list',scope='ALL')['records']]==[global_['memoryId']]
    with pytest.raises(MemoryError) as hidden: call(s,right,'show',memoryId=local['memoryId'])
    assert hidden.value.code=='MEMORY_NOT_FOUND'
    for action,args in [('correct',dict(text='cross',revision=1)),('forget',dict(revision=1))]:
        with pytest.raises(MemoryError): call(s,right,action,memoryId=local['memoryId'],**args)
    s.store.close()


def test_explicit_forget_export_rebuild_and_legacy_sources_untouched(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); legacy=tmp_path/'legacy.jsonl'; legacy.write_text('SYNTHETIC_KEEP')
    s=service(tmp_path/'state')
    first=call(s,work,'remember',kind='SEMANTIC_FACT',text='Synthetic unique removable fact')
    exported=call(s,work,'export'); assert exported['exportVersion']==1 and len(exported['records'])==1
    deleted=call(s,work,'forget',memoryId=first['memoryId'],revision=1)
    assert deleted['deleted'] and 'not secure erase' in deleted['notice']
    s.lexical.rebuild()
    assert call(s,work,'search',query='removable')['records']==[]
    exported=call(s,work,'export')
    assert not exported['records'] and len(exported['tombstones'])==1
    assert legacy.read_text()=='SYNTHETIC_KEEP'
    s.store.close()


@pytest.mark.parametrize('text,key',[('Synthetic secret dummy-provider-xyz',None),
    ('api_key=synthetic-unregistered-key',None),('Bearer synthetic-token',None),
    ('Synthetic value','password'),('password=synthetic-pass',None),
    ('{"api_key": "synthetic-unregistered-key"}',None),
    ('AWS_SECRET_ACCESS_KEY=synthetic-unregistered-key',None)])
def test_known_secret_and_obvious_credentials_denied_before_write(tmp_path,text,key):
    work=tmp_path/'workspace'; work.mkdir()
    redactor=SecretRedactor(source={'UNUSED_SECRET':'dummy-provider-xyz'})
    s=service(tmp_path/'state',redactor=redactor)
    with pytest.raises(MemoryError) as error:
        call(s,work,'remember',kind='SEMANTIC_FACT',text=text,key=key,consentSensitive=True)
    assert error.value.code=='MEMORY_SECRET_DENIED'
    assert text not in str(error.value) and not call(s,work,'export')['records']
    s.store.close()


@pytest.mark.parametrize('text,extra',[('Synthetic personal datum',{'sensitive':True}),
                                    ('Synthetic medical diagnosis',{})])
def test_sensitive_requires_same_explicit_action_consent_and_inspection(tmp_path,text,extra):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    with pytest.raises(MemoryError) as error: call(s,work,'remember',kind='SEMANTIC_FACT',text=text,**extra)
    assert error.value.code=='MEMORY_SENSITIVE_DENIED'
    remembered=call(s,work,'remember',kind='SEMANTIC_FACT',text=text,consentSensitive=True,**extra)
    assert call(s,work,'show',memoryId=remembered['memoryId'])['record']['canonicalText']!=text
    assert call(s,work,'show',memoryId=remembered['memoryId'],includeSensitive=True)['record']['canonicalText']==text
    assert call(s,work,'export')['records']==[]
    assert len(call(s,work,'export',includeSensitive=True)['records'])==1
    with pytest.raises(MemoryError): call(s,work,'correct',memoryId=remembered['memoryId'],revision=1,text='Synthetic corrected datum')
    s.store.close()


@pytest.mark.parametrize('field',['subjectId','workspaceId','sourceClass','sources','grant','trusted','autoCapture'])
def test_ui_cannot_assign_identity_provenance_or_authority(tmp_path,field):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    with pytest.raises(MemoryError) as error:
        call(s,work,'remember',kind='PREFERENCE',text='Synthetic safe',**{field:'forged'})
    assert error.value.code=='MEMORY_UNTRUSTED_INPUT'
    s.store.close()


def test_model_like_call_not_explicit_and_command_schema_strict(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    with pytest.raises(MemoryError):
        s.execute('memory_remember',{},workspace=str(work),session_id='fixture',operation_id='fixture')
    command=MemoryCommand('fixture','fixture','memory_status',{})
    assert MemoryCommand.from_dict(command.to_dict())==command
    for extra in ('actor','subjectId','approval'):
        with pytest.raises(MemoryError): MemoryCommand.from_dict({**command.to_dict(),extra:'forged'})
    status=call(s,work,'status')
    # M4 now authorizes lexical prompt injection; capture remains explicit-only.
    assert status['lexical'] and not status['autoCapture'] and status['promptInjection']
    s.store.close()


def test_long_explicit_content_dedup_is_not_an_fts_query_and_sensitivity_can_only_increase(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    text=' '.join('syntheticword'+str(i) for i in range(80))
    first=call(s,work,'remember',kind='SEMANTIC_FACT',text=text)
    second=call(s,work,'remember',kind='SEMANTIC_FACT',text=text,sensitive=True,consentSensitive=True)
    assert second['deduplicated'] and first['memoryId']==second['memoryId']
    assert call(s,work,'show',memoryId=first['memoryId'])['record']['sensitivityClass']=='SENSITIVE'
    assert text not in json.dumps(call(s,work,'list'))
    assert call(s,work,'show',memoryId=first['memoryId'],includeSensitive=True)['record']['canonicalText']==text
    s.store.close()


def test_key_matching_is_exact_scoped_and_not_limited_by_fts_word_syntax(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    call(s,work,'remember',kind='PREFERENCE',text='Synthetic same phrase',key='first')
    target=call(s,work,'remember',kind='PREFERENCE',text='Synthetic second phrase',key='Synthetic same phrase')
    duplicate=call(s,work,'remember',kind='PREFERENCE',text='Synthetic second phrase',key='Synthetic same phrase')
    assert duplicate['memoryId']==target['memoryId']
    assert len(call(s,work,'list')['records'])==2
    with pytest.raises(MemoryError) as error: call(s,tmp_path,'status')
    assert error.value.code=='MEMORY_SCOPE_MISMATCH'
    s.store.close()


def test_export_is_read_only_even_for_previously_unregistered_workspace(tmp_path):
    left=tmp_path/'left'; right=tmp_path/'right'; left.mkdir(); right.mkdir(); s=service(tmp_path/'state')
    call(s,left,'remember',kind='PREFERENCE',text='Synthetic global',scope='GLOBAL_PROFILE')
    before=s.store._connection.total_changes
    export=call(s,right,'export')
    assert export['exportVersion']==1 and len(export['records'])==1
    assert s.store._connection.total_changes==before
    s.store.close()


def test_competing_explicit_insert_cannot_commit_a_second_exact_copy(tmp_path,monkeypatch):
    work=tmp_path/'workspace'; work.mkdir()
    first=service(tmp_path/'state'); second=service(tmp_path/'state')
    arguments=dict(kind='PREFERENCE',text='Synthetic racing preference',key='race.preference')
    original=first.store.find_exact
    committed=[]
    def interleaved(*args,**kwargs):
        matches=original(*args,**kwargs)
        assert not matches
        committed.append(call(second,work,'remember',**arguments))
        return matches
    monkeypatch.setattr(first.store,'find_exact',interleaved)
    with pytest.raises(MemoryError) as conflict: call(first,work,'remember',**arguments)
    assert conflict.value.code=='MEMORY_CONFLICT'
    records=call(second,work,'list')['records']
    assert len(records)==1 and records[0]['memoryId']==committed[0]['memoryId']
    first.store.close(); second.store.close()


def test_exact_content_fallback_deduplicates_without_creating_a_key_alias(tmp_path):
    work=tmp_path/'workspace'; work.mkdir(); s=service(tmp_path/'state')
    first=call(s,work,'remember',kind='PREFERENCE',text='Synthetic same exact fact',key='original.key')
    same=call(s,work,'remember',kind='PREFERENCE',text='Synthetic same exact fact',key='new.key')
    assert same['deduplicated'] and same['memoryId']==first['memoryId']
    records=call(s,work,'list')['records']
    assert len(records)==1 and records[0]['canonicalKey']=='original.key'
    assert len(records[0]['sources'])==2
    s.store.close()
