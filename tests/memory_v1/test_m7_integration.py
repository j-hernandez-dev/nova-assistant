"""M7 integration with private real stores/audit; model fixtures are contracts."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from threading import Event
from types import SimpleNamespace
import pytest
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.application.memory_recall import MemoryRetriever,TurnMemorySnapshot
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.retrieval_context import delegated_snapshot
from local_cli.application.memory_children import persist_child_proposal,CHILD_HEADER
from local_cli.core.memory import MemoryError,MemoryAccessScope
from local_cli.core.contracts import new_command_id
from local_cli.sub_agent import SubAgentResult,SubAgentRunner
from tests.memory_v1.test_m4_application import make_app,remember,turn,close,CapturingProvider,command
from tests.memory_v1.m6_fixtures import extraction_input


def test_10k_history_not_10k_retrieval_hydration_or_duplicate_rag(tmp_path,monkeypatch):
    text='Synthetic cobalt preference: concise examples.'
    class Corpus:
        def __init__(self):self.queries=[]
        def index(self):return {'files':1,'chunks':3}
        def query(self,q,k):
            self.queries.append(q)
            return [dict(file_path='synthetic.txt',chunk_index=i,score=.9,content=t)
                for i,t in enumerate((text,'Distinct documentary cobalt data.','Distinct documentary cobalt data.'))]
    corpus=Corpus();rag=RAGService(corpus);rag.set_enabled(True)
    app,sid,actor,audit,p,work=make_app(tmp_path,rag=rag,context_selection=4096)
    try:
        mid=remember(app,sid,actor)['memoryId']
        app._session.transcript.extend({'role':'assistant' if i%2 else 'user','content':'Old synthetic irrelevant '+str(i)} for i in range(10000))
        calls=[];gets=[];index=app._memory.lexical;store=app._memory.store
        search=index.search;get=store.get
        monkeypatch.setattr(index,'search',lambda q:(calls.append(q.text),search(q))[1])
        monkeypatch.setattr(store,'get',lambda memory_id,scope:(gets.append(memory_id),get(memory_id,scope))[1])
        t=turn(app,sid)
        assert t.status.value=='completed' and len(calls)==1 and len(corpus.queries)==1 and len(gets)<=16
        prompt='\n'.join(m.get('content','') for m in p.captured[-1])
        assert prompt.count(text)==1 and prompt.count('Distinct documentary cobalt data.')<=1
        # RAG is evictable after required/current/working context. Prove exact
        # dedup before budget admission too, not pretend optional eviction is a bug.
        from local_cli.application.retrieval_context import rag_message
        response=SimpleNamespace(error=None,matches=tuple(corpus.query('synthetic render fixture',5)))
        rendered=rag_message(response,t.memory_snapshot,app.redactor)
        assert text not in rendered['content'] and rendered['content'].count('Distinct documentary cobalt data.')==1
        assert len(app._session.transcript)>10000 and not any(m.get('_context_kind')=='memory' for m in app._session.transcript)
        assert t.model_runtime._context.memory_source is None and not t.model_runtime._context.manager._counts
    finally:close(app,audit)


def test_external_delete_invalidates_next_generation_cached_memory(tmp_path):
    app,sid,actor,audit,p,work=make_app(tmp_path)
    try:
        mid=remember(app,sid,actor)['memoryId']
        from tests.memory_v1.m2_fixtures import open_store
        original=p.chat_stream;calls=0
        def stream(model,messages,**kwargs):
            nonlocal calls
            calls+=1
            if calls==1:
                p.captured.append(deepcopy(messages))
                with open_store(tmp_path/'state') as other:
                    scope=app._memory.maintenance.scope(work)
                    old=other.get(mid,scope);other.delete(mid,scope,expected_revision=old.revision)
                yield {'message':{'role':'assistant','content':'','tool_calls':[{'id':'echo','function':{'name':'echo','arguments':{'text':'synthetic'}}}]},'done':True}
            else:yield from original(model,messages,**kwargs)
        p.chat_stream=stream
        t=turn(app,sid)
        assert t.status.value=='completed' and calls==2
        assert 'MEMORY CONTEXT' in json.dumps(p.captured[0]) and 'MEMORY CONTEXT' not in json.dumps(p.captured[1])
        assert not t.memory_snapshot.records
    finally:close(app,audit)


def test_delegated_scope_subset_relevance_revision_no_global_query(tmp_path,monkeypatch):
    app,sid,actor,audit,p,work=make_app(tmp_path)
    try:
        cobalt=remember(app,sid,actor,text='A color preference: cobalt.',scope='WORKSPACE')['memoryId']
        unrelated=remember(app,sid,actor,text='unrelated coffee preference',scope='GLOBAL_PROFILE')['memoryId']
        snap=MemoryRetriever(app._memory).retrieve('cobalt coffee preference',workspace=work,at=datetime.now(timezone.utc))
        monkeypatch.setattr(app._memory.lexical,'search',lambda _:(_ for _ in ()).throw(AssertionError('child queried global store')))
        child=delegated_snapshot(app._memory,snap,workspace=work,task='cobalt',at=datetime.now(timezone.utc))
        assert [r.memory_id for r in child.records]==[cobalt] and unrelated not in child.capsule
        command(app,sid,actor,'forget',{'memoryId':cobalt,'revision':1})
        child=delegated_snapshot(app._memory,snap,workspace=work,task='cobalt',at=datetime.now(timezone.utc))
        assert child.records==() and child.capsule is None
    finally:close(app,audit)


def result(text='Synthetic child prefers cobalt examples.',**extra):
    payload={'schemaVersion':2,'candidates':[dict(kind='PREFERENCE',evidenceSpan=text,key='preference.examples',validFrom=None,validTo=None,**extra)]}
    return SubAgentResult('agent-synthetic','child',text+'\n'+CHILD_HEADER+json.dumps(payload),'success',.1,2,0)


def test_child_proposal_not_global_authoritative_idempotent_and_host_confirmable(tmp_path):
    app,sid,actor,audit,p,work=make_app(tmp_path)
    try:
        command(app,sid,actor,'status',{})
        before=app._memory.store.storage_stats()['records']
        options=dict(workspace=work,session_id=sid,turn_id='synthetic-parent',operation_id='synthetic-child-operation')
        first=persist_child_proposal(app._memory,result(),**options)
        second=persist_child_proposal(app._memory,result(),**options)
        assert first==second and first['accepted']==0 and first['proposed']==1
        assert app._memory.store.storage_stats()['records']==before
        pending=command(app,sid,actor,'proposals',{})['data']['proposals']
        assert len(pending)==1 and pending[0]['proposal']['scopeKind']=='WORKSPACE'
        assert pending[0]['proposal']['source']['source_class']=='SUBAGENT_PROPOSAL'
        item=pending[0]
        confirmed=command(app,sid,actor,'confirm',dict(jobId=item['jobId'],proposalId=item['proposal']['proposalId'],revision=item['revision']))
        assert confirmed['completed'] and app._memory.store.storage_stats()['records']==before+1
        record=app._memory.store.list(app._memory.maintenance.scope(work),limit=10).records[0]
        assert record.scope.kind.value=='WORKSPACE' and record.source_class.value=='USER_EXPLICIT_MEMORY'
    finally:close(app,audit)


@pytest.mark.parametrize('extra',[{'scopeKind':'GLOBAL_PROFILE'},{'confirmed':True},{'grant':'admin'},{'subjectId':'forged'}])
def test_child_cannot_bind_global_identity_confirmation_or_authority(tmp_path,extra):
    app,sid,actor,audit,p,work=make_app(tmp_path)
    try:
        command(app,sid,actor,'status',{})
        with pytest.raises(MemoryError):persist_child_proposal(app._memory,result(**extra),workspace=work,
            session_id=sid,turn_id='synthetic-parent',operation_id='synthetic-child')
        assert app._memory.store.storage_stats()['records']==0
        assert command(app,sid,actor,'proposals',{})['data']['proposals']==[]
    finally:close(app,audit)


def test_soft_capacity_pauses_auto_keeps_explicit_correction_and_forget(tmp_path):
    app,sid,actor,audit,p,work=make_app(tmp_path)
    try:
        mid=remember(app,sid,actor)['memoryId'];m=app._memory.maintenance
        m.soft_records=1;m.policy.mode='low_risk'
        scope=m.scope(work)
        assert command(app,sid,actor,'status',{})['data']['capturePaused']
        e=extraction_input('I prefer concise answers.',subject_id=scope.subject_id,workspace_id=scope.workspace_id)
        with pytest.raises(MemoryError) as exc:m.capture(e)
        assert exc.value.code=='MEMORY_CAPACITY_REACHED' and app._memory.store.storage_stats()['records']==1
        revised=command(app,sid,actor,'correct',{'memoryId':mid,'revision':1,'text':'Corrected synthetic preference'})
        assert revised['completed']
        new=revised['data']['memoryId'];assert command(app,sid,actor,'forget',{'memoryId':new,'revision':1})['completed']
        assert not command(app,sid,actor,'status',{})['data']['capturePaused']
    finally:close(app,audit)


def test_forget_clears_owned_terminal_snapshot_but_not_historical_context_report(tmp_path):
    app,sid,actor,audit,p,work=make_app(tmp_path)
    try:
        mid=remember(app,sid,actor)['memoryId'];t=turn(app,sid)
        reports=deepcopy(t.context_reports);terminal=(t.status,t.terminal_count,t.final_content)
        assert t.memory_snapshot.records
        assert command(app,sid,actor,'forget',{'memoryId':mid,'revision':1})['completed']
        assert t.memory_snapshot.records==() and t.memory_snapshot.capsule is None
        assert t.context_reports==reports and (t.status,t.terminal_count,t.final_content)==terminal
    finally:close(app,audit)


def test_busy_optional_retrieval_is_typed_not_late_payload_or_failed_turn(tmp_path):
    class Corpus:
        calls=0
        def index(self):return {}
        def query(self,*args):self.calls+=1;return []
    corpus=Corpus();rag=RAGService(corpus);rag.set_enabled(True)
    app,sid,actor,audit,p,work=make_app(tmp_path,rag=rag)
    try:
        remember(app,sid,actor)
        from local_cli.application.session import ServiceOperation
        from local_cli.core.contracts import new_operation_id
        op=ServiceOperation(new_operation_id(),new_command_id(),service='memory-maintenance')
        app._memory_worker=op  # Non-cooperating port fixture: capacity remains occupied.
        t=turn(app,sid)
        assert t.status.value=='completed' and t.memory_snapshot.records and corpus.calls==0
        rag_ops=[o for o in app._service_operations.values() if o.service=='rag']
        assert rag_ops[-1].status.value=='failed' and rag_ops[-1].result['error']['code']=='RAG_BUSY'
        assert not any('DOCUMENT CONTEXT' in x.get('content','') for x in p.captured[-1])
        op.done.set()
    finally:close(app,audit)


@pytest.mark.parametrize('remote',[False,True])
def test_normal_child_loop_only_delegated_memory_remote_denied_default(tmp_path,remote):
    # Scripted provider contract only; real Application/runner/SubAgent/ToolRuntime.
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.application.secrets import SecretRedactor
    from local_cli.memory_config import memory_factory
    from tests.test_nova_core_phase4_session import start,submit
    work=tmp_path/'workspace';work.mkdir()
    parent=CapturingProvider(endpoint='https://example.invalid' if remote else 'http://127.0.0.1:11434')
    children=[]
    def fresh():
        child=CapturingProvider(endpoint=parent.client.base_url,steps=[result().content]);children.append(child);return child
    manager=ProviderManager(parent,'old',clone_factory=lambda _:fresh);manager.redactor=SecretRedactor(source={})
    gate=Event();admitted=Event()
    def run(provider,model,tools,messages,**kw):
        admitted.set();gate.wait(5);return 'synthetic parent done'
    runner=SubAgentRunner(max_workers=1)
    from tests.test_nova_core_phase4_session import EchoTool
    app=AgentSessionCoordinator(provider=parent,model='old',provider_manager=manager,tool_factory=lambda _:[EchoTool()],
        prompt_factory=lambda *_:'Synthetic mandatory system',run_agent_fn=run,memory_factory=memory_factory(tmp_path/'state'),
        event_config=EventBufferConfig(),sub_agent_runner=runner,sub_agent_tool_factory=lambda _:[])
    sid=start(app,work).session_id;actor=app.register_memory_actor('cli_tty',lambda:True)
    try:
        remember(app,sid,actor,text='cobalt preference')
        receipt=submit(app,sid,'cobalt preference');assert admitted.wait(3)
        t=app._session.turns[-1]
        spawned=app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SUB_AGENT,
            {'parentTurnId':t.turn_id,'task':'cobalt','mode':'default'},session_id=sid))
        assert spawned.accepted,spawned.error
        op=app._session.agent_operations[spawned.created_ids['agentId']];assert op.done.wait(5)
        child_prompt=json.dumps(children[0].captured[0])
        assert ('MEMORY CONTEXT' in child_prompt) is (not remote)
        assert app._memory.store.storage_stats()['records']==1 and len(app._session.turns)==1
        gate.set();assert t.done.wait(5)
        proposals=command(app,sid,actor,'proposals',{})['data']['proposals']
        assert len(proposals)==1 and proposals[0]['proposal']['source']['operation_id']==spawned.created_ids['operationId']
        assert proposals[0]['proposal']['source']['source_class']=='SUBAGENT_PROPOSAL'
        assert proposals[0]['proposal']['scopeKind']=='WORKSPACE'
        operations=[o for o in app._service_operations.values() if o.service=='memory-proposal']
        assert len(operations)==1 and operations[0].status.value=='completed' and operations[0].deadline
    finally:gate.set();runner.shutdown();app._memory.store.close()


def test_agent_tool_route_uses_same_delegation_and_child_operation_provenance(tmp_path):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.application.secrets import SecretRedactor
    from local_cli.memory_config import memory_factory
    from local_cli.tools.agent_tool import AgentTool
    from tests.test_nova_core_phase4_session import start,submit
    work=tmp_path/'workspace';work.mkdir()
    call={'role':'assistant','content':'','tool_calls':[{'id':'delegate-tool','function':{
        'name':'agent','arguments':{'description':'cobalt child','prompt':'cobalt'}}}]}
    parent=CapturingProvider(steps=[call,'Synthetic parent final'])
    children=[]
    def fresh():
        child=CapturingProvider(steps=[result().content]);children.append(child);return child
    manager=ProviderManager(parent,'old',clone_factory=lambda _:fresh);manager.redactor=SecretRedactor(source={})
    runner=SubAgentRunner(max_workers=1);tool=AgentTool(runner,parent,'old',[],cwd=work);tool.environment={}
    app=AgentSessionCoordinator(provider=parent,model='old',provider_manager=manager,tool_factory=lambda _:[tool],
        prompt_factory=lambda *_:'Synthetic mandatory system',memory_factory=memory_factory(tmp_path/'state'),
        event_config=EventBufferConfig(),sub_agent_runner=runner,sub_agent_tool_factory=lambda _:[])
    sid=start(app,work).session_id;actor=app.register_memory_actor('cli_tty',lambda:True)
    try:
        remember(app,sid,actor,text='cobalt preference')
        t=turn(app,sid,'cobalt preference')
        assert t.status.value=='completed' and len(children)==1
        assert 'MEMORY CONTEXT' in json.dumps(children[0].captured[0])
        assert any(m.get('tool_call_id')=='delegate-tool' for m in app._session.transcript)
        proposals=command(app,sid,actor,'proposals',{})['data']['proposals']
        assert len(proposals)==1
        child=next(iter(app._session.agent_operations.values()))
        assert proposals[0]['proposal']['source']['operation_id']==child.operation_id
        assert app._memory.store.storage_stats()['records']==1
    finally:runner.shutdown();app._memory.store.close()
