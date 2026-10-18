"""GUI project selection reuses Application and renews workspace authority."""

from threading import Event
from types import SimpleNamespace

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.events import EventBufferConfig
from local_cli.application.interactions import ApprovalRequest
from local_cli.application.session import AgentSessionCoordinator, ServiceOperation
from local_cli.core.contracts import (ExecutionContext, ToolInvocation, ToolStatus,
    new_approval_id, new_command_id, new_operation_id, new_tool_call_id, new_turn_id)
from local_cli.core.security import SecurityError
from local_cli.harness import AgentEvent
from local_cli.tools.read_tool import ReadTool
from local_cli.tools.write_tool import WriteTool
from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit


def application(tmp_path, *, run_agent_fn=None):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    for directory in (first, second):
        (directory / 'note.txt').write_text(directory.name, encoding='utf-8')
    prepared = []

    def prepare(target):
        prepared.append(target)
        return {'base_messages': [{'role': 'system', 'content': f'Project {target}'}],
            'persistence': None, 'rag': None, 'data': {'path': str(target)}}

    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model='local',
        tool_factory=lambda folder: [ReadTool(cwd=folder), WriteTool(cwd=folder)],
        workspace_rebinder=prepare, run_agent_fn=run_agent_fn,
        event_config=EventBufferConfig())
    sid = start(app, first).session_id
    return app, sid, first, second, prepared


def invocation(app, workspace, name='read', **arguments):
    context = ExecutionContext(workspace=workspace, cwd=workspace,
        environment=app._session.environment, session_id=app._session.session_id,
        turn_id=new_turn_id(), operation_id=new_operation_id(),
        cancellation_token=CancellationController(), deadline=None,
        capabilities=app._session.capabilities,
        policy_revision=app._session.tool_runtime.policy.revision)
    return ToolInvocation(name, arguments, new_tool_call_id(), context.operation_id, context)


def test_project_selection_preserves_conversation_and_presentation_identity(tmp_path):
    def runner(_provider, _model, _tools, messages, *, emit, **_kwargs):
        emit(AgentEvent('llm_start', {}))
        response = {'role': 'assistant', 'content': 'Existing answer'}
        messages.append(response)
        emit(AgentEvent('assistant_message', {'message': response}))
        return response['content']

    app, sid, first, second, prepared = application(tmp_path, run_agent_fn=runner)
    receipt = submit(app, sid, 'Existing question')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    before = app.get_snapshot(sid)
    old_runtime = app._session.tool_runtime
    result = app.change_workspace(sid, str(second))
    after = app.get_snapshot(sid)
    assert result == {'path': str(second)} and prepared == [second]
    assert after.session_id == before.session_id and after.workspace == str(second)
    assert after.transcript[1:] == before.transcript[1:]
    assert after.turns[0]['displayMessages'] == before.turns[0]['displayMessages']
    assert after.turns[0]['userMessage'] == before.turns[0]['userMessage']
    assert app._session.tool_runtime is not old_runtime
    assert old_runtime.registry.tool('read').cwd == first
    assert app._session.tool_runtime.registry.tool('read').cwd == second
    assert after.last_sequence > before.last_sequence
    app._session.tool_runtime.close()


def test_new_project_runtime_reads_writes_new_root_and_rejects_old_context_and_grant(tmp_path):
    app, sid, first, second, _prepared = application(tmp_path)
    previous = app._session.tool_runtime
    old_invocation = invocation(app, first, file_path='note.txt')
    old_grant = previous.delegation_for(old_invocation.context)
    app.change_workspace(sid, str(second))
    current = app._session.tool_runtime
    assert current._security_workspace == second and current._filesystem.root.path == str(second)
    assert current._issuer is not previous._issuer
    with pytest.raises(SecurityError, match='GRANT_UNKNOWN'):
        current._issuer.validate_claimed(old_grant, old_grant.request)
    with pytest.raises(SecurityError, match='GRANT_CANCELLED'):
        previous._issuer.claim(old_grant, old_grant.request)
    current._publish = lambda _event: None  # This case isolates the ToolRuntime boundary.
    denied = current.execute(old_invocation)
    assert denied.status is ToolStatus.DENIED
    assert denied.metadata.get('securityErrorCode') == 'REQUEST_MISMATCH'
    read = current.execute(invocation(app, second, file_path='note.txt'))
    assert read.status is ToolStatus.COMPLETED and 'second' in read.legacy_text
    write = current.execute(invocation(app, second, 'write', file_path='new.txt', content='new root'))
    assert write.status is ToolStatus.COMPLETED
    assert (second / 'new.txt').read_text(encoding='utf-8') == 'new root'
    assert not (first / 'new.txt').exists()
    current.close()


def test_next_model_turn_uses_new_workspace_through_application_runtime(tmp_path):
    observed = []

    def runner(_provider, _model, tools, messages, *, emit, **_kwargs):
        emit(AgentEvent('llm_start', {}))
        observed.append(next(tool for tool in tools if tool.name == 'read').execute(file_path='note.txt'))
        response = {'role': 'assistant', 'content': 'Read receipt observed'}
        messages.append(response)
        emit(AgentEvent('assistant_message', {'message': response}))
        return response['content']

    app, sid, _first, second, _prepared = application(tmp_path, run_agent_fn=runner)
    app.change_workspace(sid, str(second))
    receipt = submit(app, sid, 'Inspect note.txt in the selected project')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    assert len(observed) == 1 and 'second' in observed[0]
    activity = app.get_snapshot(sid).turns[-1]['toolActivities'][0]
    assert activity['status'] == 'completed' and activity['cwd'] == str(second)
    assert 'errorCode' not in activity
    app._session.tool_runtime.close()


@pytest.mark.parametrize('invalid', ['', 'missing', 'not-a-folder', 'bad\x00path'])
def test_invalid_project_does_not_change_effective_workspace(tmp_path, invalid):
    app, sid, first, second, prepared = application(tmp_path)
    (first / 'not-a-folder').write_text('file', encoding='utf-8')
    before = app.get_snapshot(sid)
    previous = app._session.tool_runtime
    with pytest.raises(ValueError):
        app.change_workspace(sid, invalid)
    after = app.get_snapshot(sid)
    assert after == before and app._session.tool_runtime is previous and not prepared
    previous.close()


def test_active_turn_prevents_project_change_until_finished(tmp_path):
    entered, release = Event(), Event()

    def runner(*_args, **_kwargs):
        entered.set()
        assert release.wait(5)
        return 'done'

    app, sid, first, second, prepared = application(tmp_path, run_agent_fn=runner)
    receipt = submit(app, sid, 'A running task')
    try:
        assert entered.wait(5)
        with pytest.raises(ValueError) as error:
            app.change_workspace(sid, str(second))
        assert error.value.code == 'CONFLICT_ACTIVE_OPERATION'
        assert app._session.workspace == first and not prepared
    finally:
        release.set()
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    assert app.change_workspace(sid, str(second)) == {'path': str(second)}
    app._session.tool_runtime.close()


def test_active_service_and_pending_approval_prevent_project_change(tmp_path, monkeypatch):
    app, sid, first, second, prepared = application(tmp_path)
    operation = ServiceOperation(new_operation_id(), new_command_id())
    app._service_operations[operation.operation_id] = operation
    with pytest.raises(ValueError) as error:
        app.change_workspace(sid, str(second))
    assert error.value.code == 'CONFLICT_ACTIVE_OPERATION'
    operation.done.set()
    request = ApprovalRequest(new_approval_id(), sid, None, new_operation_id(),
        new_tool_call_id(), 'write', {'file_path': 'pending.txt'}, str(first),
        1, 'request-digest', None)
    monkeypatch.setattr(app._session.approval_gate, 'pending', lambda: (request,))
    with pytest.raises(ValueError) as error:
        app.change_workspace(sid, str(second))
    assert error.value.code == 'CONFLICT_ACTIVE_OPERATION'
    assert app._session.workspace == first and not prepared
    app._session.tool_runtime.close()


def test_browser_human_control_prevents_project_rebinding(tmp_path):
    app, _sid, _first, _second, _prepared = application(tmp_path)
    runtime = app._session.tool_runtime
    for phase in ('humanActive', 'resumePending', 'blocked'):
        runtime._browser_service = SimpleNamespace(human_phase=phase)
        assert app.can_rebind_workspace() is False
    runtime._browser_service = None
    assert app.can_rebind_workspace() is True
    runtime.close()


def test_failed_runtime_preparation_preserves_project_transcript_and_authority(tmp_path, monkeypatch):
    app, sid, first, second, prepared = application(tmp_path)
    previous = app._session.tool_runtime
    before = app.get_snapshot(sid)
    monkeypatch.setattr(app, '_create_tool_runtime', lambda *_args, **_kwargs:
        (_ for _ in ()).throw(ValueError('Fixture preparation failed')))
    with pytest.raises(ValueError, match='Fixture preparation failed'):
        app.change_workspace(sid, str(second))
    assert prepared == [second]
    assert app.get_snapshot(sid) == before and app._session.tool_runtime is previous
    assert previous.registry.tool('read').cwd == first
    previous.close()


def test_jsonl_folder_selection_commits_fresh_runtime_and_keeps_old_tools_immutable(tmp_path, monkeypatch):
    from local_cli.config import Config
    from local_cli.server import JsonLineServer
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    (second / 'note.txt').write_text('JSONL new workspace', encoding='utf-8')
    monkeypatch.chdir(first)
    monkeypatch.setattr('local_cli.bootstrap_server.Config', lambda: Config(
        cli_args=SimpleNamespace(state_dir=str(tmp_path / 'state'))))
    frames = []
    monkeypatch.setattr('local_cli.server._send', frames.append)
    from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
    audit = JsonlSecurityAudit(tmp_path / 'audit', workspace=first)
    monkeypatch.setattr('local_cli.bootstrap_server.create_security_audit', lambda _workspace: audit)
    server = JsonLineServer()
    try:
        sid = server._app_adapter.session_id
        app = server._application
        previous = app._session.tool_runtime
        old_tools = list(server._tools)
        old_grant = previous.delegation_for(invocation(app, first, file_path='note.txt').context)
        server._handle_set_cwd(123, str(second))
        assert frames[-1]['type'] == 'cwd_changed'
        assert server._cwd == second == app._session.workspace
        assert all(tool.cwd == first for tool in old_tools if hasattr(tool, 'cwd'))
        current = app._session.tool_runtime
        assert current._issuer is not previous._issuer
        with pytest.raises(SecurityError, match='GRANT_UNKNOWN'):
            current._issuer.validate_claimed(old_grant, old_grant.request)
        current._publish = lambda _event: None
        result = current.execute(invocation(app, second, file_path='note.txt'))
        assert result.status is ToolStatus.COMPLETED and 'JSONL new workspace' in result.legacy_text
        agent = next((tool for tool in server._tools if tool.name == 'agent'), None)
        if agent is not None:
            assert agent.cwd == second
            assert all(tool.cwd == second for tool in agent._sub_agent_tools if hasattr(tool, 'cwd'))
        app._session.tool_runtime.close()
    finally:
        server._app_adapter.close()
        server._session_log.close()
        audit.close()


@pytest.mark.parametrize('error_type,error_code', [(ValueError, 'INVALID_WORKSPACE'),
    (OSError, 'WORKSPACE_SETUP_FAILED'), (RuntimeError, 'WORKSPACE_SETUP_FAILED')])
def test_jsonl_preparation_failure_keeps_server_projection_and_runtime(tmp_path, monkeypatch,
                                                                   error_type, error_code):
    from local_cli.config import Config
    from local_cli.server import JsonLineServer
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    monkeypatch.setattr('local_cli.bootstrap_server.Config', lambda: Config(
        cli_args=SimpleNamespace(state_dir=str(tmp_path / 'state'))))
    frames = []
    monkeypatch.setattr('local_cli.server._send', frames.append)
    from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
    audit = JsonlSecurityAudit(tmp_path / 'audit', workspace=first)
    monkeypatch.setattr('local_cli.bootstrap_server.create_security_audit', lambda _workspace: audit)
    server = JsonLineServer()
    try:
        app = server._application
        previous, previous_log = app._session.tool_runtime, server._session_log
        old_tools = server._tools
        monkeypatch.setattr(app, '_create_tool_runtime', lambda *_args, **_kwargs:
            (_ for _ in ()).throw(error_type('Cannot prepare fixture runtime')))
        server._handle_set_cwd(124, str(second))
        assert frames[-1]['type'] == 'error' and frames[-1]['code'] == error_code
        if error_type is not ValueError:
            assert 'fixture runtime' not in frames[-1]['message']
        assert server._cwd == first == app._session.workspace
        assert server._tools is old_tools and server._session_log is previous_log
        assert app._session.tool_runtime is previous
        assert all(tool.cwd == first for tool in old_tools if hasattr(tool, 'cwd'))
        previous.close()
    finally:
        server._app_adapter.close()
        server._session_log.close()
        audit.close()
