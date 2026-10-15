"""Shared Application internal pipeline; prepared parser double, real store."""
import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from local_cli.application.knowledge import KnowledgeService
from local_cli.bootstrap_knowledge import build_knowledge_service
from local_cli.core.contracts import AgentId, OperationStatus
from local_cli.core.knowledge import KnowledgeError, KnowledgeScopeKind, SourceKind, SourceTrustClass
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, PAYLOAD, TEXT, Token, execution, projection


def invoke(service,context,prepare=projection,payload=(PAYLOAD,),**kwargs):
    return service.import_prepared(context=context,scope_kind=KnowledgeScopeKind.WORKSPACE,
        kind=SourceKind.LOCAL_FILE,origin='synthetic://pre-acquired',display_name='synthetic display',
        trust_class=SourceTrustClass.USER_SELECTED_LOCAL,payload=payload,prepare=prepare,**kwargs)


@pytest.fixture
def service(tmp_path):
    workspace=tmp_path/'workspace';workspace.mkdir()
    store=SQLiteKnowledgeStore(tmp_path/'private-state')
    events=[]
    service=KnowledgeService(store,workspace=workspace,access=ACCESS,event_sink=lambda k,p:events.append((k,p)))
    yield service,events
    store.close()


def test_internal_operation_core_correlation_single_terminal_safe_observability(service):
    svc,events=service
    context=execution(svc.workspace)
    result=invoke(svc,context)
    assert result.status is OperationStatus.COMPLETED
    assert result.operation_id==str(context.operation_id)
    assert [kind for kind,_ in events]==['knowledge.import.started','knowledge.import.completed']
    assert all(p['operationId']==result.operation_id and p['sourceId']==result.source.source_id for _,p in events)
    assert TEXT not in repr(events) and 'pre-acquired' not in repr(events)
    assert svc.store.operation(result.operation_id,ACCESS).status is OperationStatus.COMPLETED


@pytest.mark.parametrize('fault', ['cancel','deadline','parser','missing_projection'])
def test_application_failure_and_cancel_terminal_not_false_ready(service,fault):
    svc,events=service
    context=execution(svc.workspace,Token(fault=='cancel'))
    if fault=='deadline':context=replace(context,deadline=datetime.now(timezone.utc)-timedelta(seconds=1))
    def failed(*args):raise ValueError('synthetic parser failure')
    result=invoke(svc,context,prepare=failed if fault=='parser' else (lambda *args:None) if fault=='missing_projection' else projection)
    expected=OperationStatus.CANCELLED if fault in ('cancel','deadline') else OperationStatus.FAILED
    assert result.status is expected and result.source is None
    assert svc.store.operation(result.operation_id,ACCESS).status is expected
    assert len(events)==2 and events[-1][1]['status']==expected.value
    assert 'synthetic parser failure' not in repr(events)


@pytest.mark.parametrize('mismatch', ['workspace','session','child'])
def test_bound_host_scope_cannot_be_invented_by_caller_or_child(service,tmp_path,mismatch):
    svc,events=service
    context=execution(svc.workspace)
    context=replace(context,**{'workspace':tmp_path,'cwd':tmp_path} if mismatch=='workspace' else
                    {'session_id':'ses_foreign'} if mismatch=='session' else {'agent_id':AgentId('child_synthetic')})
    with pytest.raises(KnowledgeError) as error:invoke(svc,context)
    assert error.value.code=='SOURCE_NOT_AUTHORIZED'
    assert events==[] and svc.store.list_sources(ACCESS)==()


def test_application_refresh_failed_new_revision_preserves_old(service):
    svc,events=service
    original=invoke(svc,execution(svc.workspace))
    def failed(*args):raise ValueError()
    result=invoke(svc,execution(svc.workspace),prepare=failed,source_id=original.source.source_id)
    assert result.status is OperationStatus.FAILED
    assert svc.store.get_source(original.source.source_id,ACCESS)==original.source


def test_post_commit_event_failure_preserves_observed_result_no_retry(service):
    svc,events=service
    def event(kind,payload):
        events.append((kind,payload))
        if kind=='knowledge.import.completed':raise OSError('synthetic event gap')
    svc._events=event
    result=invoke(svc,execution(svc.workspace))
    assert result.status is OperationStatus.COMPLETED and result.notification_gap is True
    assert svc.store.get_source(result.source.source_id,ACCESS)==result.source
    assert svc.store._connection.execute('SELECT count(*) FROM import_operations').fetchone()[0]==1


def test_close_releases_lease_and_cleans_session_without_workspace_purge(service):
    svc,_=service
    invoke(svc,execution(svc.workspace))
    state=svc.store.files.root.parents[1]
    svc.close()
    with SQLiteKnowledgeStore(state) as store:
        assert len(store.list_sources(ACCESS))==1


def test_composition_root_explicit_private_store_recovery_no_legacy_adapter(tmp_path):
    work=tmp_path/'workspace';work.mkdir()
    svc=build_knowledge_service(state_dir=tmp_path/'state',workspace=work,
        workspace_id=ACCESS.workspace_id,session_id=ACCESS.session_id)
    try:
        assert svc.workspace==work and svc.store.list_sources(ACCESS)==()
        assert invoke(svc,execution(work)).status is OperationStatus.COMPLETED
    finally:svc.store.close()


def test_k1_dependency_and_scope_boundaries_no_parser_retrieval_ui_memory_or_authority():
    root=Path(__file__).resolve().parents[2]
    files=['local_cli/core/knowledge_store.py','local_cli/application/knowledge.py',
           'local_cli/infrastructure/knowledge_sqlite.py','local_cli/bootstrap_knowledge.py']
    for file in files:
        tree=ast.parse((root/file).read_text(encoding='utf-8'))
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module]
        imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        assert not any(x.startswith(('local_cli.core.memory','local_cli.application.memory','local_cli.rag',
            'local_cli.knowledge','local_cli.interfaces','local_cli.tools','local_cli.agent','ollama','electron')) for x in imports)
        if '/core/' in file:
            assert not any(x.startswith(('sqlite3','local_cli.infrastructure','local_cli.application')) for x in imports)
        calls=[n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        assert not {'run_agent','SandboxPort','CapabilityGrant','PolicyEngine'} & set(calls)
    # No second session/loop, public tool schema, UI DB, automatic prompt or
    # memory write. K2 activates only common trusted composition, not UI parsers.
    for file in ('local_cli/bootstrap_cli.py','local_cli/bootstrap_server.py'):
        code = (root/file).read_text(encoding='utf-8')
        assert 'knowledge_factory=' in code and 'local_cli.bootstrap_knowledge' in code
    assert 'bootstrap_knowledge' not in (root/'local_cli/application/session.py').read_text(encoding='utf-8')
