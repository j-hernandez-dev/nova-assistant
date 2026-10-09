"""Real scoped store, frozen parent evidence and numeric Core budgeting."""
from dataclasses import replace
import json
import pytest
from local_cli.application.context import WorkingMessages
from local_cli.application.knowledge_children import child_knowledge_source,ChildKnowledgeAdmission
from local_cli.application.knowledge_context import KNOWLEDGE_GUARD
from local_cli.core.context import ContextManager,ContextSelection,ContextPolicy
from local_cli.core.knowledge import KnowledgeError,SourceRemotePolicy
from tests.knowledge_inputs_v1.test_k5_integration import case,finish,run
from tests.knowledge_inputs_v1.k2_helpers import invoke,refs


@pytest.mark.parametrize('window',[4096,8192,16384,32768,65536])
def test_child_only_admitted_data_bounded_no_global_query_and_current_task_priority(tmp_path,window,monkeypatch):
    c=case(tmp_path,context_selection=window)
    try:
        invoke(c);t=run(c)
        svc=c.app._knowledge.service
        monkeypatch.setattr(svc.retriever,'retrieve',lambda *a,**kw:pytest.fail('child global recall'))
        monkeypatch.setattr(svc.store,'list_sources',lambda *a:pytest.fail('child corpus scan'))
        monkeypatch.setattr(svc.store,'read_blob',lambda *a:pytest.fail('child blob read'))
        source=child_knowledge_source(t.knowledge_admission,local_destination=True,selected_ids=['K1'])
        current='Synthetic child task zircon'
        working=WorkingMessages([{'role':'system','content':'Synthetic mandatory system'}, {'role':'user','content':current}])
        manager=ContextManager(ContextSelection(window),model_limit=window,provider_limit=window,
            policy=ContextPolicy(resource_limit=window),current_message=current)
        child=ChildKnowledgeAdmission(source,working,manager,[],c.app.redactor);child.refresh()
        prepared=manager.prepare(working,[])
        assert current in [m['content'] for m in prepared.messages]
        assert child.capsule.evidence and child.capsule.evidence[0].target.source_id==refs(c)[0]['sourceId']
        assert child.capsule.token_cost<=t.knowledge_admission.capsule.token_cost
        assert prepared.budget.retrieval_tokens<=prepared.budget.shared_retrieval_cap
        assert child.receipt('Synthetic child [K1] [K999]')['invalid']==['K999']
        assert child.receipt('Synthetic child [K1]')['valid'][0]['revisionId']==refs(c)[0]['revisionId']
        monkeypatch.undo()
    finally:finish(c)


def test_child_delete_revoke_and_unknown_ids_cannot_refill_or_increase_authority(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);t=run(c);svc=c.app._knowledge.service;ref=refs(c)[0]
        with pytest.raises(KnowledgeError):child_knowledge_source(t.knowledge_admission,local_destination=True,selected_ids=['K999'])
        callback=child_knowledge_source(t.knowledge_admission,local_destination=False)
        assert callback()[0].selected_evidence_refs==()
        svc.store.set_remote_policy(ref['sourceId'],svc.access,SourceRemotePolicy(True))
        assert callback()[0].selected_evidence_refs
        working=WorkingMessages([{'role':'system','content':'Synthetic security'},{'role':'user','content':'child zircon'}])
        manager=ContextManager(ContextSelection(4096),model_limit=4096,provider_limit=4096,current_message='child zircon')
        child=ChildKnowledgeAdmission(callback,working,manager,[],c.app.redactor);child.refresh()
        assert child.capsule.evidence
        svc.store.set_remote_policy(ref['sourceId'],svc.access,SourceRemotePolicy(False));child.refresh()
        assert child.capsule is None and child.receipt('[K1]')['invalid']==['K1']
        assert not any(m.get('_context_kind')=='knowledge' for m in working)
        svc.store.delete(ref['sourceId'],svc.access);child.refresh()
        assert child.capsule is None
    finally:finish(c)


def test_unknown_child_destination_never_inherits_search_or_memory_opt_in(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);t=run(c)
        callback=child_knowledge_source(t.knowledge_admission,local_destination=False)
        delegated,sources=callback()
        assert delegated.selected_evidence_refs==() and sources==()
        assert not hasattr(delegated,'store') and not hasattr(delegated,'grant')
    finally:finish(c)


@pytest.mark.parametrize('window',[4096,8192,16384])
def test_real_subagent_loop_with_memory_and_knowledge_callbacks_not_scripted_quality(tmp_path,window):
    from local_cli.sub_agent import SubAgent
    from local_cli.application.providers import ProviderManager
    from local_cli.application.context import bind_context
    from tests.memory_v1.test_m4_application import CapturingProvider
    from local_cli.application.memory_recall import TurnMemorySnapshot,MemoryCapsule
    from tests.memory_v1.m1_fixtures import record
    c=case(tmp_path,context_selection=window)
    try:
        invoke(c);t=run(c)
        p=CapturingProvider(steps=['Synthetic child [K1]']);manager=ProviderManager(p,'old',clone_factory=lambda _:lambda:p)
        manager.redactor=c.app.redactor
        bound=bind_context(manager.snapshot(),workspace=c.work,tools=[],requested=window,policy=ContextPolicy(resource_limit=window))
        child=SubAgent(bound,'old',[],'Synthetic child task zircon',cwd=c.work,environment={},redactor=c.app.redactor)
        child.bind_knowledge_delegate(child_knowledge_source(t.knowledge_admission,local_destination=True))
        r=record(canonical_text='Synthetic zircon memory context preference.')
        snapshot=TurnMemorySnapshot(records=(r,),capsule=MemoryCapsule.render((r,),c.app.redactor))
        child.bind_memory_delegate(lambda:snapshot)
        result=child.run()
        assert result.status=='success'
        prompt=p.captured[0]
        admitted=any(m['role']=='user' and 'KNOWLEDGE EVIDENCE' in m['content'] for m in prompt)
        if admitted:
            assert result.knowledge_citations['valid'][0]['revisionId']==refs(c)[0]['revisionId']
        else:
            # KI-INV-028 permits zero under Core caps. A scripted guess is NOT
            # certified recall: the host must mark its unadmitted ID invalid.
            assert result.knowledge_citations['valid']==[] and result.knowledge_citations['invalid']==['K1']
            budget=child._provider._context.manager.prepare(child._messages,[]).budget
            assert budget.retrieval_tokens<=budget.shared_retrieval_cap
        assert any(m['role']=='user' and 'MEMORY CONTEXT' in m['content'] for m in prompt)
        assert {'role':'user','content':'Synthetic child task zircon'} in prompt
        assert not any(m['role']=='system' and 'reference value: 72.' in m['content'] for m in prompt)
        assert child._provider._context.knowledge_source is None
    finally:finish(c)


def test_child_callback_data_failure_typed_empty_no_stale_source_or_global_fallback(tmp_path):
    c=case(tmp_path)
    try:
        invoke(c);t=run(c)
        state=[child_knowledge_source(t.knowledge_admission,local_destination=True)()]
        def callback():
            if state[0] is None:raise OSError('Synthetic private failure')
            return state[0]
        working=WorkingMessages([{'role':'system','content':'Synthetic security'},{'role':'user','content':'zircon child'}])
        manager=ContextManager(ContextSelection(4096),model_limit=4096,provider_limit=4096,current_message='zircon child')
        child=ChildKnowledgeAdmission(callback,working,manager,[],c.app.redactor);child.refresh();assert child.capsule.evidence
        state[0]=None;child.refresh()
        assert child.capsule is None and child.receipt('[K1]')['invalid']==['K1']
        assert all(m.get('_context_kind')!='knowledge' for m in working)
    finally:finish(c)


def test_normal_coordinator_startsubagent_delegates_selected_data_and_rejects_unadmitted_ids(tmp_path):
    from threading import Event
    from dataclasses import replace
    from local_cli.sub_agent import SubAgentRunner
    from local_cli.application.commands import ApplicationCommand,CommandKind
    from local_cli.core.contracts import new_command_id
    from tests.test_nova_core_phase4_session import submit
    from tests.memory_v1.test_m4_application import CapturingProvider
    class Parent(CapturingProvider):
        def __init__(self):super().__init__(steps=['Synthetic parent done']);self.entered=Event();self.release=Event()
        def chat_stream(self,*a,**kw):
            self.entered.set();assert self.release.wait(15)
            return super().chat_stream(*a,**kw)
    p=Parent();cp=CapturingProvider(steps=['Synthetic child [K1]']);runner=SubAgentRunner(max_workers=1)
    c=case(tmp_path,provider=p,sub_agent_runner=runner,sub_agent_tool_factory=lambda _:[],context_selection=8192)
    c.app.provider_manager._current=replace(c.app.provider_manager.snapshot(),_fresh_factory=lambda:cp)
    try:
        invoke(c);receipt=submit(c.app,c.sid,'zircon');assert receipt.accepted and p.entered.wait(5)
        parent=c.app._session.turns[-1];assert parent.knowledge_admission.capsule.evidence
        def request(ids):return ApplicationCommand(new_command_id(),CommandKind.START_SUB_AGENT,
            {'parentTurnId':parent.turn_id,'task':'Synthetic child task zircon','mode':'default','knowledgeCitationIds':ids},c.sid)
        invalid=c.app.handle(request(['K999']));assert not invalid.accepted and invalid.error.code=='SOURCE_NOT_AUTHORIZED'
        receipt=c.app.handle(request(['K1']));assert receipt.accepted,receipt
        agent_id=receipt.created_ids['agentId'];operation=c.app._session.agent_operations[agent_id]
        assert operation.done.wait(10)
        assert operation.status.value=='completed' and cp.captured
        assert any('KNOWLEDGE EVIDENCE' in m.get('content','') for m in cp.captured[0])
        assert len(c.app._session.turns)==1  # No second principal Turn/session.
        assert not any('KnowledgeStore' in str(m) for m in cp.captured[0])
    finally:
        p.release.set()
        for t in c.app._session.turns:assert t.done.wait(5)
        runner.shutdown();finish(c)


def test_child_admission_once_shrink_only_never_refills_unadmitted_parent_row(tmp_path):
    from local_cli.application.knowledge_context import message,_cost
    from local_cli.core.context import TokenCounter
    c=case(tmp_path,context_selection=8192)
    try:
        invoke(c);c.file.write_text('Synthetic zircon other value: 42.',encoding='utf-8');invoke(c)
        t=run(c);parent=t.knowledge_admission.capsule;assert len(parent.evidence)==2
        base=child_knowledge_source(t.knowledge_admission,local_destination=True)
        first=parent.evidence[0];src=next(s for s in parent.source_registry if s.source_id==first.target.source_id)
        cap=_cost(TokenCounter(),message((first,),(src,)))
        def callback():
            data,sources=base();return replace(data,token_budget=cap),sources
        working=WorkingMessages([{'role':'system','content':'Synthetic safety'},{'role':'user','content':'Synthetic child zircon'}])
        manager=ContextManager(ContextSelection(8192),model_limit=8192,provider_limit=8192,current_message='Synthetic child zircon')
        child=ChildKnowledgeAdmission(callback,working,manager,[],c.app.redactor);child.refresh()
        assert [e.citation_id for e in child.capsule.evidence]==[first.citation_id]
        c.app._knowledge.service.store.delete(first.target.source_id,c.app._knowledge.service.access)
        child.refresh();assert child.capsule is None
        assert not any(m.get('_context_kind')=='knowledge' for m in working)
    finally:finish(c)


def test_guard_literal_user_and_mandatory_system_not_removed_by_document_cleanup(tmp_path):
    from local_cli.application.knowledge_context import KnowledgeAdmission,KNOWLEDGE_GUARD
    c=case(tmp_path)
    try:
        user={'role':'user','content':KNOWLEDGE_GUARD};system={'role':'system','content':KNOWLEDGE_GUARD}
        working=WorkingMessages([system,user,{'role':'system','content':KNOWLEDGE_GUARD,'_context_knowledge_guard':True}])
        admission=KnowledgeAdmission('synthetic-turn',None,c.app.redactor);admission._remove(working)
        assert working==[system,user]
        invoke(c);t=run(c)
        data=[child_knowledge_source(t.knowledge_admission,local_destination=True)()]
        manager=ContextManager(ContextSelection(8192),model_limit=8192,provider_limit=8192,current_message=KNOWLEDGE_GUARD)
        working=WorkingMessages([system,user]);child=ChildKnowledgeAdmission(lambda:data[0],working,manager,[],c.app.redactor)
        child.refresh();assert user in working and system in working
        data[0]=(replace(data[0][0],selected_evidence_refs=(),allowed_source_revision_ids=()),())
        child.refresh();assert user in working and system in working
        prepared=manager.prepare(working,[]);assert user in prepared.messages
        assert all(not any(k.startswith('_context_') for k in m) for m in prepared.messages)
    finally:finish(c)
