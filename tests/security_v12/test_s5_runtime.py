"""Real Application/issuer/runtime, explicitly mocked HTTP port. No host network."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from local_cli.application.network import NetworkFetchService
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.contracts import EffectState, EventKind, ToolStatus
from local_cli.core.network import HttpHop, NetworkError
from local_cli.core.security import Capability, ControlClass, GrantLifetime, GrantRequest, Permission, ResourceScope, ScopeKind
from local_cli.network_config import DEFAULT_FETCH_LIMITS
from local_cli.tools.web_fetch_tool import WebFetchTool
from tests.security_v12.network_fixtures import ScriptedHTTPPort
from tests.security_v12.test_s2_policy import invocation


def runtime(tmp_path, port=None, **kwargs):
    port = port or ScriptedHTTPPort()
    service = NetworkFetchService(port, DEFAULT_FETCH_LIMITS)
    events = []
    rt = ToolRuntime(ToolRegistry([WebFetchTool()]), network_service=service, publish=events.append, **kwargs)
    if rt._issuer is None:
        rt.install_authority(tmp_path, 'session')
    return rt, port, events


def fetch(tmp_path, url='https://example.test/a', **args):
    return invocation(tmp_path, 'web_fetch', {'url':url, **args})


def test_productive_composition_claims_once_before_controlled_port_and_never_legacy(tmp_path, monkeypatch):
    port = ScriptedHTTPPort()
    tool = WebFetchTool(http_broker=port)
    monkeypatch.setattr(tool, 'execute', lambda **_: pytest.fail('legacy fallback'))
    events = []
    rt = ToolRuntime(ToolRegistry([tool]), publish=events.append)
    inv = fetch(tmp_path)
    result = rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED and result.legacy_text == 'fixture'
    assert rt.execute(inv) is result and len(port.gets) == 1
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED]
    assert result.metadata['controlClasses'] == ['APPLICATION_ENFORCED', 'BROKER_ENFORCED']
    grant = rt._issuer._issued[result.metadata['grantId']].grant
    assert grant.request.network_intent['destinationPolicy'] == 'PUBLIC_ONLY'
    assert grant.request.network_intent['limits']['body_bytes'] == 2097152
    assert not grant.request.environment_intent
    assert rt._issuer._issued[grant.grant_id].claims == 1


@pytest.mark.parametrize('url', ['http://127.0.0.1/', 'http://10.0.0.1/', 'http://169.254.169.254/',
    'http://100.64.0.1/', 'http://[::1]/', 'http://[fd00::1]/', 'http://[fe80::1]/',
    'http://[::ffff:127.0.0.1]/'])
def test_literal_special_destinations_never_resolve_or_dispatch(tmp_path, url):
    rt, port, events = runtime(tmp_path)
    result = rt.execute(fetch(tmp_path, url))
    assert result.status is ToolStatus.DENIED
    assert result.metadata['securityErrorCode'] == 'NETWORK_DESTINATION_DENIED'
    assert not port.gets and not port.resolutions
    assert sum(e[0] is EventKind.TOOL_FAILED for e in events) == 1


@pytest.mark.parametrize('ips', [('127.0.0.1',), ('10.0.0.1',), ('fd00::1',),
    ('169.254.169.254',), ('8.8.8.8', '10.0.0.1'), ('2606:4700:4700::1111', '::1')])
def test_dns_resolving_special_or_mixed_answers_is_denied(tmp_path, ips):
    rt, port, _ = runtime(tmp_path, ScriptedHTTPPort(addresses={'example.test':ips}))
    result = rt.execute(fetch(tmp_path))
    assert result.status is ToolStatus.DENIED and not port.gets


@pytest.mark.parametrize('location', ['http://127.0.0.1/', 'https://10.0.0.1/',
    'https://[fd00::1]/', 'https://private.test/', 'file:///fixture', 'data:text/plain,fixture'])
def test_redirect_cannot_expand_into_private_or_alternate_scheme(tmp_path, location):
    port = ScriptedHTTPPort([HttpHop(302, '', location, b''), HttpHop(200, '', None, b'forbidden')],
                            addresses={'private.test':('192.168.1.1',)})
    rt, _, events = runtime(tmp_path, port)
    result = rt.execute(fetch(tmp_path))
    assert result.status is ToolStatus.OUTCOME_UNKNOWN and result.effect_state is EffectState.UNKNOWN
    assert len(port.gets) == 1
    assert result.metadata['effectiveUrl'] == 'https://example.test/a'
    assert result.metadata['networkAudit'][-1]['kind'] == 'fetch_denied_or_failed'
    assert rt.execute(fetch(tmp_path)) is result and len(port.gets) == 1
    assert sum(e[0] is EventKind.TOOL_FAILED for e in events) == 1


def test_cross_host_public_redirect_is_checked_audited_and_ip_pinned_per_hop(tmp_path):
    port = ScriptedHTTPPort([HttpHop(302, '', 'https://second.test/final', b''),
                            HttpHop(200, 'text/html', None, b'<p>done</p>')],
        addresses={'example.test':('8.8.8.8',), 'second.test':('2606:4700:4700::1111',)})
    rt, _, _ = runtime(tmp_path, port)
    result = rt.execute(fetch(tmp_path))
    assert result.status is ToolStatus.COMPLETED and result.legacy_text == 'done'
    assert len(port.resolutions) == len(port.gets) == 2
    assert result.metadata['requestedUrl'] == 'https://example.test/a'
    assert result.metadata['effectiveUrl'] == 'https://second.test/final'
    assert [r['address'] for r in result.metadata['networkAudit']] == ['8.8.8.8', '2606:4700:4700::1111']


def test_fresh_dns_at_same_host_redirect_cannot_rebind_to_private(tmp_path):
    port = ScriptedHTTPPort([HttpHop(302, '', '/b', b'')])
    def flip():
        port.addresses['example.test'] = ('127.0.0.1',)
    port.before_get = flip
    rt, _, _ = runtime(tmp_path, port)
    result = rt.execute(fetch(tmp_path))
    assert result.metadata['securityErrorCode'] == 'NETWORK_DESTINATION_DENIED'
    assert len(port.gets) == 1 and len(port.resolutions) == 2


@pytest.mark.parametrize('hops,code,count', [
    ([HttpHop(302, '', '/repeat', b'')]*6, 'NETWORK_REDIRECT_LIMIT', 6),
    ([HttpHop(302, '', 'http://example.test/a', b'')], 'NETWORK_REDIRECT_DOWNGRADE_DENIED', 1),
    ([HttpHop(302, '', None, b'')], 'NETWORK_REDIRECT_INVALID', 1),
    ([HttpHop(404, '', None, b'')], 'NETWORK_HTTP_ERROR', 1),
    ([NetworkError('NETWORK_TIMEOUT', dispatched=True)], 'NETWORK_TIMEOUT', 1),
    ([NetworkError('NETWORK_RESPONSE_INCOMPLETE', dispatched=True)], 'NETWORK_RESPONSE_INCOMPLETE', 1)])
def test_typed_errors_unknown_no_retries_and_one_terminal(tmp_path, hops, code, count):
    rt, port, events = runtime(tmp_path, ScriptedHTTPPort(hops))
    result = rt.execute(fetch(tmp_path))
    assert result.metadata['securityErrorCode'] == code
    assert result.status is ToolStatus.OUTCOME_UNKNOWN
    assert len(port.gets) == count and rt.execute(fetch(tmp_path)) is result
    assert len([e for e in events if e[0] in (EventKind.TOOL_FAILED, EventKind.TOOL_COMPLETED)]) == 1


@pytest.mark.parametrize('mutation', ['revoked', 'revision', 'ceiling', 'cancelled', 'limits'])
def test_last_boundary_revalidation_prevents_dispatch(tmp_path, mutation):
    rt, port, _ = runtime(tmp_path)
    inv = fetch(tmp_path)
    def change():
        if mutation == 'revoked':
            rt._issuer.revoke(next(iter(rt._issuer._issued.values())).grant)
        elif mutation == 'revision':
            rt.update_policy_revision(2)
        elif mutation == 'ceiling':
            rt._issuer.replace_ceiling(replace(rt._issuer.ceiling, revision=2))
        elif mutation == 'limits':
            rt._network_service.limits = replace(DEFAULT_FETCH_LIMITS, redirects=10)
        else:
            inv.context.cancellation_token.request()
    port.before_get = change
    result = rt.execute(inv)
    assert result.status in (ToolStatus.DENIED, ToolStatus.CANCELLED, ToolStatus.FAILED)
    assert not port.gets


def test_child_uses_same_service_and_narrow_parent_does_not_authorize_redirect(tmp_path):
    root, port, _ = runtime(tmp_path, ScriptedHTTPPort([HttpHop(302, '', '/b', b'')]))
    inv = fetch(tmp_path)
    now = datetime.now(timezone.utc)
    exact = Capability(Permission('network.fetch'), ResourceScope(ScopeKind.URL, inv.arguments['url']),
                       ControlClass.BROKER_ENFORCED)
    parent_inv = replace(inv, name='agent', arguments={}, operation_id='delegate',
                         context=replace(inv.context, operation_id='delegate'))
    caps = tuple(c for c in root._issuer.ceiling.capabilities if c.permission.name != 'network.fetch') + (exact,)
    req = GrantRequest.from_invocation(parent_inv, capabilities=caps, ceiling=root._issuer.ceiling,
        lifetime=GrantLifetime(now, now+timedelta(minutes=1), one_shot=False), policy_revision=1,
        action='fixture delegation', effect_classification='application.delegation')
    parent = root._issuer.issue(req, inv.context.cancellation_token)
    root._issuer.claim(parent, req)
    child, _, _ = runtime(tmp_path, port, issuer=root._issuer, policy=root.policy,
                          parent_grant=parent)
    child._network_service = root._network_service
    result = child.execute(replace(inv, context=replace(inv.context, session_id='child', agent_id='child')))
    assert result.metadata['securityErrorCode'] == 'NETWORK_REDIRECT_AUTHORITY_DENIED'
    assert len(port.gets) == 1


def test_direct_facade_is_also_brokered_and_denies_file_data_loopback(monkeypatch):
    port = ScriptedHTTPPort()
    tool = WebFetchTool(http_broker=port)
    for url in ('file:///fixture', 'data:text/plain,fixture', 'http://127.0.0.1/'):
        assert tool.execute(url=url).startswith('Error:')
    assert not port.gets
    assert tool.execute(url='https://example.test/a') == 'fixture'
    assert len(port.gets) == 1


def test_audit_has_no_query_values_and_request_digest_still_binds_query(tmp_path):
    rt, _, _ = runtime(tmp_path)
    inv = fetch(tmp_path, 'https://example.test/a?fixture_token=DUMMY_ONLY')
    result = rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED
    assert 'DUMMY_ONLY' not in repr(result.metadata)
    grant = rt._issuer._issued[result.metadata['grantId']].grant
    assert grant.request.network_intent['requestedUrl'].endswith('DUMMY_ONLY')
    assert result.metadata['requestDigest'] == grant.request.request_digest


def test_grant_revoke_after_first_hop_prevents_next_hop(tmp_path):
    rt, port, _ = runtime(tmp_path, ScriptedHTTPPort([HttpHop(302, '', '/second', b'')]))
    inv = fetch(tmp_path)
    def revoke():
        rt._issuer.revoke(next(iter(rt._issuer._issued.values())).grant)
    # Simulate revocation after the first admitted request's final validation.
    original_get = port.get
    def admitted_then_revoked(*args, **kwargs):
        report = original_get(*args, **kwargs)
        revoke()
        return report
    port.get = admitted_then_revoked
    result = rt.execute(inv)
    assert result.status is ToolStatus.OUTCOME_UNKNOWN and len(port.gets) == 1
    assert result.metadata['securityErrorCode'] == 'GRANT_REVOKED'


def test_public_http_to_https_upgrade_is_checked_against_ceiling(tmp_path):
    rt, port, _ = runtime(tmp_path, ScriptedHTTPPort([
        HttpHop(302, '', 'https://second.test/final', b''), HttpHop(200, 'text/plain', None, b'done')]))
    result = rt.execute(fetch(tmp_path, 'http://example.test/start'))
    assert result.status is ToolStatus.COMPLETED and len(port.gets) == 2
    assert result.metadata['effectiveUrl'] == 'https://second.test/final'


def test_default_common_application_backend_and_correlated_single_terminal(tmp_path):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    port = ScriptedHTTPPort()
    call = {'role':'assistant', 'content':'', 'tool_calls':[
        {'function':{'name':'web_fetch', 'arguments':{'url':'https://example.test/'}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call, 'done']), model='fixture',
        tool_factory=lambda cwd:[WebFetchTool(http_broker=port)], event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    receipt = submit(app, session_id, 'fetch fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], timeout=5)
    rt = app._session.tool_runtime
    assert rt._network_service.broker is port
    result = next(iter(rt._outcomes.values()))[1]
    assert result.status is ToolStatus.COMPLETED and len(port.gets) == 1
    events = app.poll_events(app.subscribe_events(session_id, after_sequence=0))
    terminals = [e for e in events if e.kind in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED)]
    assert len(terminals) == 1 and terminals[0].operation_id


def test_actual_agent_child_uses_shared_network_service_and_own_grant(tmp_path, monkeypatch):
    from local_cli.tools.agent_tool import AgentTool
    from local_cli.sub_agent import SubAgentRunner
    from tests.test_nova_core_phase4_session import ScriptedProvider
    provider = ScriptedProvider([{'role':'assistant', 'content':'', 'tool_calls':[
        {'function':{'name':'web_fetch', 'arguments':{'url':'https://example.test/'}}}]}, 'done'])
    port = ScriptedHTTPPort()
    fetch_tool = WebFetchTool(http_broker=port)
    runner = SubAgentRunner(max_workers=1)
    agent = AgentTool(runner=runner, provider=provider, model='fixture', sub_agent_tools=[fetch_tool], cwd=tmp_path)
    monkeypatch.setattr(agent, '_create_fresh_provider', lambda:provider)
    children = []
    rt = ToolRuntime(ToolRegistry([fetch_tool, agent]), on_agent_started=lambda child,*_:children.append(child))
    try:
        result = rt.execute(invocation(tmp_path, 'agent', {'description':'fixture', 'prompt':'fetch child'}))
        assert result.status is ToolStatus.COMPLETED and len(children) == 1 and len(port.gets) == 1
        child = children[0]
        assert child._network_service is rt._network_service
        adapter = next(t for t in child._tools if t.name == 'web_fetch')
        assert adapter._runtime._network_service is rt._network_service
        actual = adapter._last_result
        assert actual.status is ToolStatus.COMPLETED
        grant = rt._issuer._issued[actual.metadata['grantId']].grant
        assert grant.request.parent_grant_id and grant.request.subject.agent_id == child.agent_id
    finally:
        runner.shutdown()


def test_start_sub_agent_command_shares_network_service(tmp_path, monkeypatch):
    from threading import Event
    import time
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.providers import ProviderManager
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.application.events import EventBufferConfig
    from local_cli.core.contracts import new_command_id
    from local_cli.sub_agent import SubAgent, SubAgentRunner
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    entered, release = Event(), Event()
    class ParentProvider:
        def chat_stream(self, *args, **kwargs):
            entered.set()
            assert release.wait(10)
            return iter([{'message':{'role':'assistant','content':'done'}, 'done':True}])
    call = {'role':'assistant', 'content':'', 'tool_calls':[
        {'function':{'name':'web_fetch', 'arguments':{'url':'https://example.test/'}}}]}
    parent = ParentProvider()
    manager = ProviderManager(parent, 'fixture', clone_factory=lambda _:lambda:ScriptedProvider([call,'done']))
    port = ScriptedHTTPPort()
    service = NetworkFetchService(port, DEFAULT_FETCH_LIMITS)
    children = []
    def child_factory(**kwargs):
        child = SubAgent(**kwargs); children.append(child); return child
    monkeypatch.setattr('local_cli.application.session.SubAgent', child_factory)
    runner = SubAgentRunner(max_workers=1)
    app = AgentSessionCoordinator(provider=parent, model='fixture', provider_manager=manager,
        tool_factory=lambda cwd:[WebFetchTool()], sub_agent_tool_factory=lambda cwd:[WebFetchTool()],
        sub_agent_runner=runner, network_service=service, event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    turn = submit(app, session_id, 'parent fixture')
    try:
        assert entered.wait(3)
        receipt = app.handle(ApplicationCommand(command_id=new_command_id(), kind=CommandKind.START_SUB_AGENT,
            session_id=session_id, payload={'parentTurnId':turn.created_ids['turnId'], 'task':'fetch fixture','mode':'default'}))
        assert receipt.accepted
        end = time.monotonic()+5
        op = app._session.agent_operations[receipt.created_ids['agentId']]
        while op.status.value not in ('completed', 'failed', 'cancelled', 'outcome_unknown') and time.monotonic()<end:
            Event().wait(.01)
        assert op.status.value == 'completed' and len(port.gets) == 1
        assert children[0]._network_service is service is app._session.tool_runtime._network_service
        assert next(t for t in children[0]._tools if t.name == 'web_fetch')._last_result.status is ToolStatus.COMPLETED
    finally:
        release.set()
        assert app.wait_for_turn(turn.created_ids['turnId'], timeout=5)
        runner.shutdown()
