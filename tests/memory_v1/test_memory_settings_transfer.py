"""Real Memory stores/coordinator; scripted inference and synthetic memories only."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from datetime import datetime,timezone
from pathlib import Path
from threading import Event
from unittest.mock import patch
import json
import pytest
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.memory import MemoryCommand
from local_cli.application.memory_recall import MemoryRetriever
from local_cli.application.memory_transfer import export_memories,import_memories
from local_cli.application.providers import ProviderManager
from local_cli.application.secrets import SecretRedactor
from local_cli.application.events import EventBufferConfig
from local_cli.core.contracts import new_command_id
from local_cli.core.memory import MemoryError,MemoryErrorCode,MemoryAccessScope
from local_cli.memory_preferences import MemoryPreferences,DEFAULTS
from local_cli.memory_config import memory_factory
from tests.test_nova_core_phase4_session import start
from tests.memory_v1.test_m4_application import CapturingProvider,turn


def build(tmp_path,*,prefs=None,state=None,workspace=None,em=None):
    state=state or tmp_path/'state';workspace=workspace or tmp_path/'work';workspace.mkdir(exist_ok=True)
    prefs=prefs or MemoryPreferences(state)
    provider=CapturingProvider();manager=ProviderManager(provider,'old');manager.redactor=SecretRedactor(source={})
    app=AgentSessionCoordinator(provider=provider,model='old',provider_manager=manager,tool_factory=lambda _:[],
        prompt_factory=lambda *_:'Synthetic instructions.',memory_factory=memory_factory(state,preferences=prefs,embedding_settings=em),
        memory_preferences=prefs,embedding_settings=em,event_config=EventBufferConfig())
    sid=start(app,workspace).session_id;actor=app.register_memory_actor('cli_tty',lambda:True)
    def call(name,args={}):
        return app.execute_memory(MemoryCommand(str(new_command_id()),str(sid),name,args),actor=actor)
    return SimpleNamespace(app=app,sid=sid,actor=actor,prefs=prefs,call=call,state=state,work=workspace,provider=provider)


def add(c,text='Synthetic cobalt preference',scope='WORKSPACE',sensitive=False):
    result=c.call('memory_remember',{'kind':'PREFERENCE','text':text,'scope':scope,
        **({'sensitive':True,'consentSensitive':True} if sensitive else {})})
    assert result['completed'],result
    return result['data']['memoryId']


def configure(c,**patches):
    values={k:v for k,v in c.prefs.snapshot().items() if k!='sensitiveProjects'}|patches
    return c.call('memory_configure',values)


def close(*cases):
    for c in cases:
        if c.app._memory:c.app._memory.store.close()


def test_settings_are_authoritative_reset_preserves_memories_and_revokes_access(tmp_path):
    c=build(tmp_path)
    try:
        assert c.app.get_snapshot(c.sid).services['memory']['autoCapture'] is True
        saved=add(c)
        assert configure(c,lexicalRecall=False,autoCapture=False,captureMode='propose_only')['completed']
        assert c.call('memory_project_access',{'projectPath':str(c.work),'enabled':True})['completed']
        before=c.app.get_snapshot(c.sid).services['memory'];assert not before['lexicalRecall'] and not before['autoCapture']
        assert c.call('memory_reset_settings')['completed']
        after=c.app.get_snapshot(c.sid).services['memory']
        assert after['lexicalRecall'] and after['autoCapture'] and after['captureMode']=='low_risk'
        assert after['sensitiveProjects']==[] and not after['semantic']
        assert c.call('memory_show',{'memoryId':saved})['data']['record']['memoryId']==saved
    finally:close(c)


def test_semantic_requires_enabled_available_em_and_no_unauthenticated_settings(tmp_path):
    c=build(tmp_path)
    try:
        result=configure(c,semanticRecall=True)
        assert result['error']['code']=='MEMORY_EMBEDDING_REQUIRED' and not c.prefs.snapshot()['semanticRecall']
        command=MemoryCommand(str(new_command_id()),str(c.sid),'memory_configure',DEFAULTS)
        assert c.app.execute_memory(command)['error']['code']=='MEMORY_UNTRUSTED_INPUT'
        command=MemoryCommand(str(new_command_id()),str(c.sid),'memory_reset_settings',{},expected_revision=999)
        assert c.app.execute_memory(command,actor=c.actor)['error']['code']=='REVISION_CONFLICT'
    finally:close(c)


def test_lexical_toggle_controls_real_llm_memory_context(tmp_path):
    c=build(tmp_path)
    try:
        add(c);assert configure(c,autoCapture=False,lexicalRecall=False)['completed']
        first=turn(c.app,c.sid,'cobalt preference')
        assert first.status.value=='completed' and first.memory_snapshot.records==()
        assert not any('MEMORY CONTEXT' in m.get('content','') for m in c.provider.captured[-1])
        assert configure(c,lexicalRecall=True)['completed']
        assert turn(c.app,c.sid,'cobalt preference').memory_snapshot.records
    finally:close(c)


def test_sensitive_permission_admits_only_global_and_current_project_then_revokes(tmp_path):
    a=build(tmp_path);other=tmp_path/'other';b=build(tmp_path,workspace=other,state=a.state,prefs=a.prefs)
    try:
        normal=add(a,'Synthetic cobalt normal')
        own=add(a,'Synthetic cobalt personal condition',sensitive=True)
        global_id=add(a,'Synthetic cobalt profile condition','GLOBAL_PROFILE',True)
        foreign=add(b,'Synthetic cobalt foreign condition',sensitive=True)
        assert configure(a,autoCapture=False)['completed']
        assert {r.memory_id for r in turn(a.app,a.sid,'cobalt').memory_snapshot.records}=={normal}
        assert a.call('memory_project_access',{'projectPath':str(a.work),'enabled':True})['completed']
        ids={r.memory_id for r in turn(a.app,a.sid,'cobalt').memory_snapshot.records}
        assert ids=={normal,own,global_id} and foreign not in ids
        assert not a.prefs.allows_sensitive(b.work)
        assert a.call('memory_project_access',{'projectPath':str(a.work),'enabled':False})['completed']
        assert {r.memory_id for r in turn(a.app,a.sid,'cobalt').memory_snapshot.records}=={normal}
    finally:close(a,b)


def test_profile_export_replace_roundtrip_all_projects_and_sensitive_choice(tmp_path):
    a=build(tmp_path);b=build(tmp_path,workspace=tmp_path/'other',state=a.state,prefs=a.prefs)
    try:
        ids={add(a),add(a,'Synthetic profile preference','GLOBAL_PROFILE'),add(b,'Synthetic other project preference')}
        private=add(a,'Synthetic private preference',sensitive=True)
        plain=export_memories(a.app._memory,False);assert {r['memoryId'] for r in plain['records']}==ids
        backup=export_memories(a.app._memory,True)
        assert {r['memoryId'] for r in backup['records']}==ids|{private} and len(backup['projects'])==2
        assert set(backup)=={'format','exportVersion','schemaVersion','subjectId','records','tombstones','projects'}
        a.prefs.set_sensitive(str(a.work),True);permissions=a.prefs.snapshot()
        extra=add(a,'Synthetic later preference')
        result=a.call('memory_import',{'backup':backup});assert result['completed'],result
        assert {r['memoryId'] for r in export_memories(a.app._memory,True)['records']}==ids|{private}
        assert a.prefs.snapshot()==permissions
        assert not a.call('memory_show',{'memoryId':extra})['completed']
        assert export_memories(b.app._memory,True)['records']==export_memories(a.app._memory,True)['records']
    finally:close(a,b)


@pytest.mark.parametrize('mutate',[lambda b:b.update(sensitiveProjects=['forged']),
    lambda b:b['records'][0].update(canonicalText='tampered'),
    lambda b:b['records'].append(deepcopy(b['records'][0])),lambda b:b.update(exportVersion=999),
    lambda b:b['projects'][0].update(path='relative/path'),lambda b:b.update(schemaVersion=True)])
def test_invalid_import_is_atomic_and_preserves_saved_memories(tmp_path,mutate):
    c=build(tmp_path)
    try:
        saved=add(c);backup=export_memories(c.app._memory,True);mutate(backup)
        result=c.call('memory_import',{'backup':backup})
        assert not result['completed'] and result['error']['code']=='MEMORY_IMPORT_INVALID'
        assert c.call('memory_show',{'memoryId':saved})['completed']
        assert len(export_memories(c.app._memory,True)['records'])==1
    finally:close(c)


def test_import_write_failure_rolls_back_previous_records_and_search_index(tmp_path):
    c=build(tmp_path)
    try:
        saved=add(c);backup=export_memories(c.app._memory,True)
        original=c.app._memory.store._insert
        def fail(record):original(record);raise MemoryError(MemoryErrorCode.WRITE_FAILED)
        with patch.object(c.app._memory.store,'_insert',fail):result=c.call('memory_import',{'backup':backup})
        assert not result['completed'] and result['error']['code']=='MEMORY_WRITE_FAILED'
        assert c.call('memory_show',{'memoryId':saved})['completed']
        assert c.call('memory_search',{'query':'cobalt'})['data']['records'][0]['memoryId']==saved
    finally:close(c)


def test_legacy_export_import_and_cross_profile_identity_rebinding(tmp_path):
    a=build(tmp_path);new=tmp_path/'destination';new.mkdir();b=build(new)
    try:
        add(a);a.app._memory.identity.resolve_workspace(str(a.work))
        scope=MemoryAccessScope(a.app._memory.subject,a.app._memory.identity.resolve_workspace(str(a.work)))
        old=a.app._memory.store.export_fixture(scope)
        add(b,'Synthetic existing destination')
        assert b.call('memory_import',{'backup':old})['completed']
        exported=export_memories(b.app._memory,True)
        assert len(exported['records'])==1
        assert exported['subjectId']!=old['subjectId']
        assert exported['records'][0]['subjectId']==exported['subjectId']
        assert b.call('memory_search',{'query':'cobalt'})['data']['records']
    finally:close(a,b)


def test_import_cancels_derived_work_before_replacing_records(tmp_path):
    from threading import Lock,Thread
    c=build(tmp_path)
    try:
        add(c);backup=export_memories(c.app._memory,True)
        from concurrent.futures import Future
        pending=Future();pending.set_result(None)
        admission=SimpleNamespace(_lock=Lock(),_stop=Event(),_pending=pending)
        admission._lock.acquire()
        stopped=Event()
        def worker():
            assert admission._stop.wait(3)
            stopped.set();admission._lock.release()
        job=Thread(target=worker);job.start()
        c.app._memory._semantic_history=[admission]
        assert c.call('memory_import',{'backup':backup})['completed']
        job.join(3);assert stopped.is_set() and not job.is_alive()
    finally:close(c)


def test_selected_em_builds_real_index_and_sensitive_semantic_recall_obeys_project_permission(tmp_path,monkeypatch):
    import importlib.util
    if importlib.util.find_spec('numpy') is None:
        pytest.skip('Positive semantic contract requires the installed NumPy runtime')
    from local_cli.embedding_settings import EmbeddingSettings,EmbeddingPreferences
    from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
    rows=[{'name':'synthetic-embedding:latest','kind':'embedding','contextLength':32768}]
    em=EmbeddingSettings(EmbeddingPreferences(tmp_path/'state'),inventory=lambda:rows);em.observe(rows)
    calls=[]
    def request(self,path,deadline,data=None):
        calls.append((path,data))
        if path=='/api/tags':return {'models':[{'name':'synthetic-embedding:latest','digest':'synthetic-v1'}]}
        if path=='/api/ps':return {'models':[]}  # Enable can prepare an installed cold model outside Turn recall.
        if path=='/api/show':return {'capabilities':['embedding'],'model_info':{'synthetic.embedding_length':3}}
        if path=='/api/embed':return {'embeddings':[[1.,0.,0.] for _ in data['input']],'prompt_eval_count':len(data['input'])}
        raise AssertionError(path)
    monkeypatch.setattr(LocalOllamaEmbeddings,'_request',request)
    c=build(tmp_path,em=em)
    try:
        normal=add(c,'Synthetic cobalt ordinary preference')
        private=add(c,'Synthetic cobalt private preference',sensitive=True)
        assert configure(c,autoCapture=False,lexicalRecall=False,semanticRecall=True)['completed']
        c.app._memory.semantic._pending.result(10)
        first=turn(c.app,c.sid,'cobalt')
        assert first.memory_snapshot.retrieval_mode=='semantic'
        assert {r.memory_id for r in first.memory_snapshot.records}=={normal}
        assert c.call('memory_project_access',{'projectPath':str(c.work),'enabled':True})['completed']
        c.app._memory.semantic._pending.result(10)
        assert {r.memory_id for r in turn(c.app,c.sid,'cobalt').memory_snapshot.records}=={normal,private}
        assert c.call('memory_project_access',{'projectPath':str(c.work),'enabled':False})['completed']
        c.app._memory.semantic._pending.result(10)
        assert {r.memory_id for r in turn(c.app,c.sid,'cobalt').memory_snapshot.records}=={normal}
        em.observe([],connected=True)
        assert c.app.get_snapshot(c.sid).services['memory']['semanticAvailable'] is False
        assert configure(c,lexicalRecall=True)['completed']
        assert c.app._memory.semantic is None
        assert calls and all(not path.endswith('/api/generate') for path,_ in calls)
    finally:close(c)
