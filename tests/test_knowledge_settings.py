"""Persistent Knowledge controls and real document vectors, with synthetic embeddings."""
from copy import deepcopy
from dataclasses import replace
from threading import Event
from time import monotonic, sleep
from unittest.mock import Mock
import json
import pytest

from local_cli.knowledge_preferences import KnowledgePreferences, DEFAULTS
from local_cli.bootstrap_knowledge import build_knowledge_service, knowledge_factory
from local_cli.application.knowledge_indexing import KnowledgeIndexing
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.core.contracts import new_command_id
from local_cli.core.knowledge_retrieval import DocumentEmbeddingSpace
from local_cli.core.knowledge_chunking import CHUNK_PROFILE
from local_cli.core.knowledge_context import KnowledgeCapsule
from local_cli.infrastructure.knowledge_embeddings import LocalDocumentEmbeddings
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, OTHER_WORKSPACE, source
from tests.knowledge_inputs_v1.k4_helpers import publish_text
from tests.test_web_settings import app_for


class Selection:
    def __init__(self):
        self.value = dict(connected=True, selectedModel='synthetic-em', selectedTokens=8192, errorCode=None)
        self.usage = None
    def snapshot(self): return deepcopy(self.value)
    def runtime_options(self, model):
        assert model == self.value['selectedModel']
        return {'num_ctx':self.value['selectedTokens']}


class Adapter:
    calls = []
    def __init__(self, endpoint, model, **options):
        self.model, self.options = model, options
    def discover(self):
        self.space = DocumentEmbeddingSpace('synthetic:'+str(self.options['settings'].snapshot()['selectedTokens']),
            self.model, 'digest-'+self.model, 3, 'document-raw-v1', CHUNK_PROFILE)
        return self.space
    def embed_documents(self, texts, expected_space):
        self.calls.append((self.model, texts))
        return tuple((1.,0.,0.) for text in texts)
    def embed_query(self, text, expected_space): return (1.,0.,0.)


def settled(index):
    deadline = monotonic()+4
    while index.snapshot()['indexing'] and monotonic()<deadline: sleep(.005)
    assert not index.snapshot()['indexing'], index.snapshot()


@pytest.fixture
def indexed(tmp_path):
    preferences=KnowledgePreferences(tmp_path/'prefs')
    service=build_knowledge_service(state_dir=tmp_path/'state',workspace=tmp_path,
        workspace_id=ACCESS.workspace_id,session_id=ACCESS.session_id)
    selection=Selection();Adapter.calls=[]
    index=KnowledgeIndexing(service,preferences,selection,'http://127.0.0.1:11434',adapter_factory=Adapter)
    service.indexing=index
    yield service,preferences,selection,index
    index.close();service.close()


def test_preferences_persist_reset_validate_and_preserve_after_failed_write(tmp_path,monkeypatch):
    preferences=KnowledgePreferences(tmp_path)
    assert preferences.snapshot()==DEFAULTS and not preferences.path.exists()
    changed={**DEFAULTS,'lexicalRecall':False,'autoIndex':False,'autoRebuild':False}
    preferences.update(changed)
    assert KnowledgePreferences(tmp_path).snapshot()==changed
    before=preferences.path.read_bytes()
    monkeypatch.setattr('local_cli.knowledge_preferences.os.replace',Mock(side_effect=OSError('synthetic failure')))
    with pytest.raises(OSError):preferences.reset()
    assert preferences.snapshot()==changed and preferences.path.read_bytes()==before
    monkeypatch.undo();preferences.reset()
    assert KnowledgePreferences(tmp_path).snapshot()==DEFAULTS
    for invalid in ({},{**DEFAULTS,'lexicalRecall':1},{**DEFAULTS,'extra':True}):
        with pytest.raises(ValueError):preferences.update(invalid)
    preferences.path.write_text(json.dumps({'schemaVersion':True,**changed}))
    assert KnowledgePreferences(tmp_path).snapshot()==DEFAULTS


def test_application_gates_em_persists_reset_and_rejects_stale_or_busy_commands(tmp_path):
    factory=knowledge_factory(tmp_path/'state')
    app,sid,_=app_for(tmp_path,knowledge_factory=factory)
    def command(value,kind=CommandKind.SET_KNOWLEDGE_SETTINGS,revision=None):
        return app.handle(ApplicationCommand(new_command_id(),kind,value,sid,expected_revision=revision))
    try:
        original=app.get_snapshot(sid)
        assert original.services['knowledgeSettings']['semanticAvailable'] is False
        assert not command({**DEFAULTS,'semanticRecall':True}).accepted
        changed={**DEFAULTS,'lexicalRecall':False,'autoIndex':False,'autoRebuild':False}
        assert command(changed,revision=original.state_revision).accepted
        assert KnowledgePreferences(tmp_path/'state').snapshot()==changed
        assert command(changed,revision=original.state_revision).error.code=='REVISION_CONFLICT'
        assert command({},CommandKind.RESET_KNOWLEDGE_SETTINGS).accepted
        assert factory.preferences.snapshot()==DEFAULTS
        busy=Mock();busy.done.is_set.return_value=False
        app._session.agent_operations['test']=busy
        assert command(changed).error.code=='CONFLICT_ACTIVE_OPERATION'
        assert factory.preferences.snapshot()==DEFAULTS
    finally:
        app._session.agent_operations.clear();app.close_knowledge();app._session.tool_runtime.close()


def test_automatic_index_uses_current_project_only_and_retrieval_modes_are_real(indexed):
    service,preferences,selection,index=indexed
    local,prepared=publish_text(service.store,'Synthetic cobalt bicycle')
    publish_text(service.store,'Foreign secret material',src=source(access=OTHER_WORKSPACE),access=OTHER_WORKSPACE)
    preferences.update({**DEFAULTS,'semanticRecall':True,'lexicalRecall':False})
    index.refresh();settled(index)
    assert index.snapshot()['errorCode'] is None
    assert index.snapshot()['indexedSources']==1
    assert len(Adapter.calls)==1
    result=service.retriever.retrieve('unrelated synonym',ACCESS)
    assert result.mode=='semantic' and [r.source_id for r in result.candidates]==[local.source_id]
    from tests.knowledge_inputs_v1.k1_helpers import execution
    assert service.retrieve('unrelated synonym',context=execution(service.workspace)).mode=='semantic'
    preferences.update({**DEFAULTS,'semanticRecall':False,'lexicalRecall':False})
    index.refresh(schedule=False)
    assert not service.retriever.retrieve('cobalt bicycle',ACCESS).candidates
    preferences.update(DEFAULTS);index.refresh(schedule=False)
    assert service.retriever.retrieve('cobalt bicycle',ACCESS).mode=='lexical'
    assert len(Adapter.calls)==1


def test_index_and_rebuild_toggles_independently_control_new_and_existing_vectors(indexed):
    service,preferences,selection,index=indexed
    local,prepared=publish_text(service.store,'Synthetic cobalt bicycle')
    preferences.update({**DEFAULTS,'autoIndex':False})
    index.refresh();settled(index);assert Adapter.calls==[]
    preferences.update(DEFAULTS);index.refresh();settled(index);assert len(Adapter.calls)==1
    index.refresh();settled(index);assert len(Adapter.calls)==1,'already indexed revisions are not embedded again'
    preferences.update({**DEFAULTS,'autoRebuild':False})
    selection.value['selectedModel']='other-em'
    index.refresh();settled(index);assert len(Adapter.calls)==1
    preferences.update(DEFAULTS);index.refresh();settled(index)
    assert len(Adapter.calls)==2 and Adapter.calls[-1][0]=='other-em'
    assert service.retriever.space.model=='other-em'
    selection.value['selectedTokens']=4096
    index.refresh();settled(index);assert len(Adapter.calls)==3


def test_changed_selection_discards_inflight_vectors(indexed):
    service,preferences,selection,index=indexed
    local,prepared=publish_text(service.store,'Synthetic pending content')
    entered,release=Event(),Event()
    class Slow(Adapter):
        def embed_documents(self,texts,expected_space):
            entered.set();assert release.wait(3);return super().embed_documents(texts,expected_space)
    index.adapter_factory=Slow
    index.refresh();assert entered.wait(2)
    selection.value['connected']=False
    index.refresh(schedule=False);release.set();settled(index)
    assert not service.store._connection.execute('SELECT 1 FROM semantic_vectors').fetchone()
    assert service.retriever.retrieve('pending content',ACCESS).mode=='lexical'


def test_failed_embedding_is_observable_and_preserves_lexical_sources(indexed):
    service,preferences,selection,index=indexed
    local,prepared=publish_text(service.store,'Synthetic cobalt bicycle')
    class Broken(Adapter):
        def embed_documents(self,texts,expected_space):raise OSError('synthetic offline')
    index.adapter_factory=Broken
    index.refresh();settled(index)
    assert index.snapshot()['errorCode']=='KNOWLEDGE_INDEX_FAILED'
    assert service.store.get_source(local.source_id,ACCESS).current_revision_id==prepared.revision.revision_id
    assert service.retriever.retrieve('cobalt bicycle',ACCESS).mode=='lexical'


def test_document_adapter_uses_em_context_and_distinct_spaces_with_explicit_cold_inference():
    selection=Selection();calls=[]
    def transport(path,data,timeout):
        calls.append((path,data))
        if path=='/api/show':return {'capabilities':['embedding'],'model_info':{'test.embedding_length':3},'details':{'family':'bert'}}
        if path=='/api/tags':return {'models':[{'name':selection.value['selectedModel'],'digest':'owned-digest'}]}
        if path=='/api/ps':return {'models':[]}
        if path=='/api/embed':return {'embeddings':[[1,0,0] for _ in data['input']]}
        raise AssertionError(path)
    adapter=LocalDocumentEmbeddings('http://127.0.0.1:11434','synthetic-em',settings=selection,allow_cold=True,transport=transport)
    space=adapter.discover()
    adapter.embed_documents(('Synthetic text',),space)
    assert next(data for path,data in calls if path=='/api/embed')['options']=={'num_ctx':8192}
    from local_cli.core.knowledge import KnowledgeError
    assert adapter.embed_query('Synthetic question',space)==(1.,0.,0.)
    selection.value['selectedTokens']=4096
    newer=LocalDocumentEmbeddings('http://127.0.0.1:11434','synthetic-em',settings=selection,allow_cold=True,transport=transport)
    assert newer.discover().space_id!=space.space_id


def test_model_input_context_errors_are_specific_and_do_not_expose_response_text():
    from io import BytesIO
    from urllib.error import HTTPError
    from time import perf_counter
    from local_cli.core.knowledge import KnowledgeError
    adapter=LocalDocumentEmbeddings('http://127.0.0.1:11434','synthetic-em')
    failure=HTTPError('http://127.0.0.1:11434/api/embed',400,'bad request',{},
        BytesIO(b'{"error":"input length exceeds maximum context length; synthetic private body"}'))
    adapter._opener.open=Mock(side_effect=failure)
    with pytest.raises(KnowledgeError) as error:
        adapter._request('/api/embed',{},perf_counter()+1)
    assert error.value.code=='KNOWLEDGE_EMBEDDING_CONTEXT_EXCEEDED'
    assert 'private body' not in str(error.value)
