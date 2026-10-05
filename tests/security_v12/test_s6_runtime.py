"""S6 real Application/grants/approvals with mocked launcher/provider."""
from dataclasses import replace
from threading import Event, Thread
import json
import pytest

from local_cli.core.environment import EnvironmentSelection, EnvironmentError
from local_cli.core.contracts import ToolStatus, EventKind
from local_cli.application.interactions import ApprovalGate
from tests.security_v12.test_s2_runtime import runtime, response
from tests.security_v12.test_s2_policy import invocation


def start_selected(tmp_path, *, values=None, **kwargs):
    requested, ready = [], Event()
    gate = ApprovalGate(on_required=lambda r: (requested.append(r), ready.set()))
    actor = gate.register_actor('desktop_host', lambda: True)
    rt, exe, events = runtime(tmp_path, gate=gate, **kwargs)
    inv = invocation(tmp_path)
    rt.select_operation_environment(inv, EnvironmentSelection(values or {'PROJECT_TOKEN':'project-dummy-123'}))
    results = []
    worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start(); assert ready.wait(2)
    return rt, exe, events, inv, gate, actor, requested[0], results, worker


def test_exact_approval_pass_and_no_automatic_reuse(tmp_path):
    rt, exe, events, inv, gate, actor, req, results, worker = start_selected(tmp_path)
    try:
        assert req.arguments['environment']['names'] == ('PROJECT_TOKEN',)
        assert 'project-dummy-123' not in json.dumps(dict(req.arguments), default=list)
        gate.resolve(**response(req, actor)); worker.join(2)
        assert results[0].status is ToolStatus.COMPLETED
        grant = next(iter(rt._issuer._issued.values())).grant
        assert grant.request.environment_intent['PROJECT_TOKEN'] == 'project-dummy-123'
        assert grant.request.request_digest == req.request_digest
        assert any(c.permission.name == 'environment.pass' for c in grant.request.capabilities)
        assert rt._environment_selections == {}
        assert rt.execute(inv) is results[0]
        inv2 = replace(inv, operation_id='next', context=replace(inv.context, operation_id='next'))
        assert rt.execute(inv2).status is ToolStatus.COMPLETED
        grants = [s.grant for s in rt._issuer._issued.values()]
        assert 'PROJECT_TOKEN' not in grants[-1].request.environment_intent
        with pytest.raises(EnvironmentError):
            rt.select_operation_environment(inv, EnvironmentSelection({'PROJECT_TOKEN':'changed'}))
    finally:
        inv.context.cancellation_token.request(); worker.join(2)


@pytest.mark.parametrize('change', ['policy','cancel','arguments','selection'])
def test_pending_change_denies_before_launcher_and_consumes_selection(tmp_path, change):
    rt, exe, events, inv, gate, actor, req, results, worker = start_selected(tmp_path)
    if change == 'policy':
        rt.update_policy_revision(2)
    elif change == 'cancel':
        inv.context.cancellation_token.request()
    elif change == 'arguments':
        object.__setattr__(inv, 'arguments', {'command':'echo other'})
    else:
        with pytest.raises(EnvironmentError):
            rt.select_operation_environment(inv, EnvironmentSelection({'PROJECT_TOKEN':'other'}))
        inv.context.cancellation_token.request()
    worker.join(3)
    assert results and results[0].status in (ToolStatus.DENIED, ToolStatus.CANCELLED)
    assert rt._environment_selections == {}
    exe.run.assert_not_called()
    assert len([e for e in events if e[0] is EventKind.TOOL_FAILED]) == 1


def test_pass_without_human_approval_fails_even_yes(tmp_path):
    rt, exe, _ = runtime(tmp_path, auto_approve=True)
    inv = invocation(tmp_path)
    rt.select_operation_environment(inv, EnvironmentSelection({'PROJECT_TOKEN':'project-dummy-123'}))
    assert rt.execute(inv).status is ToolStatus.DENIED
    assert rt._environment_selections == {}
    exe.run.assert_not_called()


def test_public_requested_started_and_result_never_carry_private_env(tmp_path):
    from local_cli.application.secrets import SecretRedactor
    rt, exe, events = runtime(tmp_path, redactor=SecretRedactor(source={'UNUSED_SECRET':'dummy-secret-789'}))
    exe.run.return_value.stdout = 'dummy-secret-789'
    inv = invocation(tmp_path, arguments={'command':'echo dummy-secret-789'})
    result = rt.execute(inv)
    assert 'dummy-secret-789' not in json.dumps(result.to_dict())
    assert all(e[1].context.environment == {} for e in events)
    assert 'dummy-secret-789' not in json.dumps([dict(e[1].arguments) for e in events])


def test_invalid_host_selector_still_has_one_terminal_and_no_effect(tmp_path):
    rt, exe, events = runtime(tmp_path, environment_selector=lambda _: EnvironmentSelection({'NODE_OPTIONS':'dummy'}))
    result = rt.execute(invocation(tmp_path))
    assert result.status is ToolStatus.DENIED
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_FAILED]
    exe.run.assert_not_called()


def test_selector_failure_is_bounded_before_any_dispatch(tmp_path):
    def select(_):
        raise ValueError('private-configuration-dummy')
    rt, exe, events = runtime(tmp_path, environment_selector=select)
    result = rt.execute(invocation(tmp_path))
    assert result.status is ToolStatus.DENIED
    assert result.metadata['securityErrorCode'] == 'ENVIRONMENT_SELECTION_FAILED'
    assert 'private-configuration-dummy' not in json.dumps(result.to_dict())
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_FAILED]
    exe.run.assert_not_called()


def test_child_base_does_not_auto_receive_root_operation_pass(tmp_path):
    from local_cli.sub_agent import SubAgent
    from tests.test_nova_core_phase4_session import ScriptedProvider
    child = SubAgent(ScriptedProvider(['done']), 'fixture', [], 'task', cwd=tmp_path,
        environment={'HOME':str(tmp_path), 'PROJECT_TOKEN':'project-dummy-789', 'NODE_OPTIONS':'unsafe'})
    assert child._environment == {'HOME':str(tmp_path)}
    assert child.run().status == 'success'


def test_child_cannot_select_new_environment_scope_beyond_parent(tmp_path):
    root, _, _ = runtime(tmp_path)
    parent = root.delegation_for(invocation(tmp_path).context)
    child, exe, _ = runtime(tmp_path)
    child._issuer = root._issuer; child._parent_grant = parent
    with pytest.raises(EnvironmentError, match='ENVIRONMENT_AUTHORITY_EXCEEDED'):
        child.select_operation_environment(invocation(tmp_path), EnvironmentSelection({'PROJECT_TOKEN':'project-dummy-789'}))
    exe.run.assert_not_called()


def test_common_application_cli_exact_pass_names_risk_redacted_and_backend_once(tmp_path, monkeypatch):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.interfaces.cli_application import CliApplicationClient
    from tests.test_nova_core_phase4_session import ScriptedProvider, start
    rt, exe, _ = runtime(tmp_path)
    shell = rt.registry.tool('bash')
    call = {'role':'assistant','content':'','tool_calls':[{'function':{'name':'bash','arguments':{'command':'echo ok'}}}]}
    selections = []
    def select(inv):
        selections.append(inv.operation_id)
        return EnvironmentSelection({'PROJECT_TOKEN':'project-dummy-789'}) if len(selections) == 1 else None
    app = AgentSessionCoordinator(provider=ScriptedProvider([call,'done']), model='fixture',
        tool_factory=lambda _: [shell], environment_selector=select, event_config=EventBufferConfig())
    sid = start(app, tmp_path).session_id
    shown = []
    monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
    cli = CliApplicationClient(app, sid, read=lambda _: 'yes', write=shown.append, write_error=shown.append)
    try:
        cli.submit_user_input('fixture')
        exe.run.assert_called_once()
        text = ''.join(shown)
        assert 'PROJECT_TOKEN' in text and 'HOST_UNISOLATED' in text
        assert 'project-dummy-789' not in text
        assert app.get_snapshot(sid).turns[0]['terminalCount'] == 1
    finally:
        cli.close()


def test_application_transcript_snapshot_events_and_persistence_known_provider_secret(tmp_path):
    from unittest.mock import Mock
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.application.persistence import PersistenceService
    from tests.test_nova_core_phase4_session import start, submit
    secret = 'provider-dummy-123456'
    received = []
    class Provider:
        def __init__(self):
            self._api_key = secret
        def chat_stream(self, model, messages, **kwargs):
            received.append(json.dumps(messages))
            yield {'message':{'content':'provider-dummy-'}}
            yield {'message':{'content':'123456'}, 'done':True}
    conversation, snapshots = Mock(), Mock()
    persistence = PersistenceService(workspace=tmp_path, conversation=conversation, snapshots=snapshots)
    app = AgentSessionCoordinator(provider=Provider(), model='fixture', tool_factory=lambda _: [],
        persistence_factory=lambda _: persistence, event_config=EventBufferConfig(delta_batch_count=1))
    sid = start(app, tmp_path).session_id
    result = submit(app, sid, secret)
    assert app.wait_for_turn(result.created_ids['turnId'], 5)
    state = app.get_snapshot(sid).to_dict()
    assert secret not in json.dumps(state)
    assert secret not in json.dumps([e.to_dict() for e in app._events._journal.read_after(0)])
    assert secret not in str(conversation.save.call_args_list)
    assert secret not in ''.join(received)
    assert state['turns'][0]['status'] == 'completed' and state['turns'][0]['terminalCount'] == 1


