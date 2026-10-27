from copy import deepcopy
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest

from local_cli.embedding_settings import EmbeddingPreferences, EmbeddingSettings, EmbeddingSettingsError, EMPTY_SELECTION as DEFAULTS, STORE_DEFAULTS, PRESETS
from local_cli.model_inventory import ModelInventory
from local_cli.usage_ledger import UsageLedger
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.core.contracts import new_command_id

MODELS = [{'name':'em:small','size':10,'kind':'embedding','contextLength':512},
          {'name':'em:large','size':20,'kind':'embedding','contextLength':32768},
          {'name':'chat:small','size':30,'kind':'llm','contextLength':32768}]

def service(tmp_path):
    rows = deepcopy(MODELS)
    store = EmbeddingPreferences(tmp_path)
    result = EmbeddingSettings(store, inventory=lambda:deepcopy(rows))
    result.observe(rows)
    return result, store, rows

def enabled(name='em:large', tokens=0):
    return {'modelId':name,'requestedTokens':tokens,'enabledModels':[name]}

def test_default_and_reset_are_atomic_and_enable_new_models(tmp_path):
    settings, store, rows = service(tmp_path)
    assert store.load() == STORE_DEFAULTS and settings.snapshot()['selectedModel'] == 'em:small'
    assert settings.snapshot()['enabledModels'] == ['em:small','em:large']
    settings.update(enabled(tokens=16384))
    assert EmbeddingPreferences(tmp_path).load() == {'modelId':'em:large','requestedTokens':16384,'hiddenModels':['em:small']}
    rows.append({'name':'new:em','kind':'embedding','contextLength':8192})
    settings.observe(rows)
    assert 'new:em' in settings.snapshot()['enabledModels']
    assert 'em:small' not in settings.snapshot()['enabledModels']
    settings.reset()
    assert store.load() == STORE_DEFAULTS
    assert settings.snapshot()['enabledModels'] == ['em:small','em:large','new:em']
    assert settings.snapshot()['selectedModel'] == 'em:small'

@pytest.mark.parametrize('tokens',PRESETS)
def test_all_seven_manual_values_and_automatic_are_supported(tmp_path,tokens):
    settings, _, _ = service(tmp_path)
    assert settings.update(enabled(tokens=tokens))['requestedTokens'] == tokens
    assert settings.runtime_options('em:large') == {'num_ctx':tokens}
    assert settings.update(enabled())['requestedTokens'] == 0

@pytest.mark.parametrize('patch',[{'requestedTokens':True},{'requestedTokens':1000},{'requestedTokens':65536},
    {'modelId':None},{'enabledModels':['em:large','em:large']},{'enabledModels':'em:large'},{'extra':True}])
def test_exact_command_validation_rejects_malformed_values(patch):
    with pytest.raises(ValueError):
        ApplicationCommand(new_command_id(),CommandKind.SET_EMBEDDING_SETTINGS,{**DEFAULTS,**patch},'session')

def test_known_limit_rejected_without_persisting_and_unknown_limit_delegates(tmp_path):
    settings, store, rows = service(tmp_path)
    settings.update(enabled('em:small'))
    before = store.path.read_bytes()
    with pytest.raises(EmbeddingSettingsError,match='CONTEXT_LIMIT'):
        settings.update(enabled('em:small',8192))
    assert store.path.read_bytes() == before and settings.snapshot()['requestedTokens'] == 0
    rows[0]['contextLength'] = None
    assert settings.update(enabled('em:small',8192))['selectedTokens'] == 8192

def test_chat_and_unknown_models_cannot_be_enabled_as_embeddings(tmp_path):
    settings, _, rows = service(tmp_path)
    rows.append({'name':'unknown:em','kind':'unknown','contextLength':None})
    for name in ('chat:small','unknown:em','missing:em'):
        with pytest.raises(EmbeddingSettingsError,match='MODEL_UNAVAILABLE'):
            settings.update(enabled(name))

def test_hiding_selected_model_changes_selector_then_disables_it_when_all_off(tmp_path):
    settings, _, _ = service(tmp_path)
    settings.update({'modelId':'em:large','requestedTokens':0,'enabledModels':['em:small','em:large']})
    result = settings.update({'modelId':'em:small','requestedTokens':0,'enabledModels':['em:small']})
    assert result['selectedModel'] == 'em:small'
    assert settings.update(deepcopy(DEFAULTS))['selectedModel'] == ''

def test_uninstall_and_reinstall_do_not_reclassify_or_reenable_models(tmp_path):
    settings, _, rows = service(tmp_path)
    settings.update(enabled())
    rows[:] = [MODELS[0],MODELS[2]]; settings.observe(rows)
    assert settings.snapshot()['selectedModel'] == ''
    rows.append(deepcopy(MODELS[1]));settings.observe(rows)
    assert settings.snapshot()['selectedModel'] == 'em:large'

def test_failed_save_and_offline_validation_preserve_previous_values(tmp_path):
    settings, store, _ = service(tmp_path)
    settings.update(enabled())
    before = settings.snapshot()
    store.save = Mock(side_effect=OSError('owned failure'))
    with pytest.raises(EmbeddingSettingsError,match='SAVE_FAILED'):
        settings.update(deepcopy(DEFAULTS))
    assert settings.snapshot() == before
    settings.inventory = Mock(side_effect=OSError('offline'))
    with pytest.raises(EmbeddingSettingsError,match='CONNECTION_FAILED'):
        settings.update(enabled(tokens=1024))
    assert settings.snapshot() == before

@pytest.mark.parametrize('raw',['invalid','[]','{"schemaVersion":2}',json.dumps({'schemaVersion':1,**DEFAULTS,'requestedTokens':True})])
def test_invalid_store_fails_disabled_without_rewriting(tmp_path,raw):
    store = EmbeddingPreferences(tmp_path);store.path.write_text(raw)
    assert store.load() == STORE_DEFAULTS and store.path.read_text() == raw

def test_inventory_uses_capabilities_not_names_and_invalidates_digest_cache():
    info = {'deceptive-embedding:7b':{'capabilities':['completion'],'model_info':{'x.context_length':8192}},
            'plain:1':{'capabilities':['embedding'],'model_info':{'x.context_length':512}},
            'unknown:1':{'capabilities':None}}
    provider = SimpleNamespace(list_models=lambda:[{'name':n,'digest':'v1'} for n in info],
        get_model_info=Mock(side_effect=lambda n:info[n]))
    inventory = ModelInventory()
    result = inventory.read(provider)
    assert [m['kind'] for m in result] == ['llm','embedding','unknown']
    inventory.read(provider)
    assert provider.get_model_info.call_count == 4  # successful digests cached; unknown retried
    info['plain:1']['capabilities']=['completion']
    assert inventory.read(provider,[{'name':'plain:1','digest':'v2'}])[0]['kind'] == 'llm'

def test_embedding_usage_is_separate_and_has_input_tokens_without_text_output(tmp_path):
    now=datetime.now(timezone.utc);start=now-timedelta(hours=1);end=now+timedelta(hours=1)
    q={'start':start.isoformat(),'end':end.isoformat(),'buckets':[{'start':start.isoformat(),'end':end.isoformat()}]}
    llm=UsageLedger(tmp_path/'llm.sqlite3');em=UsageLedger(tmp_path/'em.sqlite3',kind='embedding')
    request=em.begin('em:large');em.finish(request,{'prompt_eval_count':42,'eval_count':0},'completed')
    assert em.query(q)['inputTokens']==42 and em.query(q)['outputTokens']==0
    assert em.query(q)['unreported']==0 and llm.query(q)['requests']==0


def test_adapter_applies_confirmed_context_and_records_only_actual_embedding_requests(tmp_path):
    from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
    from tests.memory_v1.test_m5_embeddings import transport
    rows=[{'name':'fixture:latest','kind':'embedding','contextLength':32768}]
    ledger=UsageLedger(tmp_path/'usage.sqlite3',kind='embedding')
    settings=EmbeddingSettings(EmbeddingPreferences(tmp_path),inventory=lambda:rows,usage=ledger)
    settings.observe(rows);settings.update(enabled('fixture:latest',1024))
    calls,base=transport()
    def request(path,data,timeout):
        result=base(path,data,timeout)
        return {**result,'prompt_eval_count':12} if path=='/api/embed' else result
    adapter=LocalOllamaEmbeddings('http://localhost:11434','fixture',settings=settings,transport=request)
    before=adapter.status()
    assert adapter.embed_query('owned synthetic query')==(1.,0.,0.)
    payload=next(data for path,data,_ in calls if path=='/api/embed')
    assert payload['options']=={'num_ctx':1024} and payload['truncate'] is False
    settings.update(enabled('fixture:latest',2048))
    assert adapter.status().embedding_space_id!=before.embedding_space_id
    now=datetime.now(timezone.utc);start=now-timedelta(hours=1);end=now+timedelta(hours=1)
    q={'start':start.isoformat(),'end':end.isoformat(),'buckets':[{'start':start.isoformat(),'end':end.isoformat()}]}
    usage=ledger.query(q)
    assert (usage['requests'],usage['inputTokens'],usage['outputTokens'])==(1,12,0)
    settings.update(deepcopy(DEFAULTS))
    from local_cli.core.memory import MemoryError
    with pytest.raises(MemoryError): adapter.embed_query('disabled')


@pytest.mark.parametrize('detail,code',[
    ('input length exceeds the context length','EMBEDDING_CONTEXT_LIMIT_EXCEEDED'),
    ('model requires more system memory','EMBEDDING_MEMORY_INSUFFICIENT'),
    ('invalid request','EMBEDDING_REQUEST_FAILED'),
])
def test_runtime_errors_are_distinguishable_without_leaking_response_text(tmp_path,detail,code):
    from io import BytesIO
    from urllib.error import HTTPError
    from time import perf_counter
    from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
    from local_cli.core.memory import MemoryError
    settings,_,_=service(tmp_path);settings.update(enabled())
    adapter=LocalOllamaEmbeddings('http://localhost:11434','em:large',settings=settings)
    adapter._opener=SimpleNamespace(open=Mock(side_effect=HTTPError('http://localhost',400,'Bad Request',{},BytesIO(json.dumps({'error':detail}).encode()))))
    with pytest.raises(MemoryError) as exc:
        adapter._request('/api/embed',perf_counter()+1,{'model':'em:large','input':['synthetic']})
    assert settings.snapshot()['errorCode']==code
    assert detail not in str(exc.value)
    # An overlong previous input does not permanently block shorter future inputs.
    assert settings.runtime_options('em:large')=={'num_ctx':8192}

def test_application_revision_busy_guards_and_snapshot_do_not_touch_memory_switches(tmp_path):
    from local_cli.application.session import AgentSessionCoordinator
    from tests.test_web_settings import app_for
    app,sid,_=app_for(tmp_path)
    settings,_,_=service(tmp_path/'em')
    app._embedding_settings=settings
    def command(value,revision=None):
        return app.handle(ApplicationCommand(new_command_id(),CommandKind.SET_EMBEDDING_SETTINGS,value,sid,revision))
    try:
        initial=app.get_snapshot(sid)
        assert command(enabled(),initial.state_revision).accepted
        snapshot=app.get_snapshot(sid)
        assert snapshot.services['embedding']['selectedModel']=='em:large'
        assert snapshot.services['memory']==initial.services['memory']
        assert not command(enabled(tokens=512),initial.state_revision).accepted
        active=Mock();active.done.is_set.return_value=False
        app._session.agent_operations['owned']=active
        result=command(deepcopy(DEFAULTS),snapshot.state_revision)
        assert not result.accepted and result.error.code=='CONFLICT_ACTIVE_OPERATION'
        assert settings.snapshot()['selectedModel']=='em:large'
    finally:
        app._session.agent_operations.clear();app._session.tool_runtime.close()


def test_previous_disabled_default_migrates_to_active_without_rewriting_the_file(tmp_path):
    store=EmbeddingPreferences(tmp_path)
    raw=json.dumps({'schemaVersion':1,**DEFAULTS})
    store.path.write_text(raw,encoding='utf-8')
    settings=EmbeddingSettings(store,inventory=lambda:deepcopy(MODELS));settings.observe(MODELS)
    assert settings.snapshot()['enabledModels']==['em:small','em:large']
    assert store.path.read_text(encoding='utf-8')==raw
    settings.update({'modelId':'em:large','requestedTokens':0,'enabledModels':['em:large']})
    restored=EmbeddingSettings(EmbeddingPreferences(tmp_path),inventory=lambda:deepcopy(MODELS));restored.observe(MODELS)
    assert restored.snapshot()['enabledModels']==['em:large']
    restored.reset()
    assert restored.snapshot()['enabledModels']==['em:small','em:large']


def test_reset_works_offline_and_keeps_context_automatic_for_future_installs(tmp_path):
    settings,store,rows=service(tmp_path)
    settings.update(enabled(tokens=8192))
    settings.inventory=Mock(side_effect=OSError('offline'))
    settings.observe([],False)
    settings.reset()
    assert store.load()==STORE_DEFAULTS and settings.snapshot()['requestedTokens']==0
    settings.observe(rows)
    assert settings.snapshot()['enabledModels']==['em:small','em:large']


def test_reset_command_rejects_extra_payload_fields():
    with pytest.raises(ValueError):
        ApplicationCommand(new_command_id(),CommandKind.RESET_EMBEDDING_SETTINGS,{'approve':True},'session')
