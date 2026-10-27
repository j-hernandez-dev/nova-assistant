"""Productive Browser contracts through the real Policy/Approval/Grant runtime."""
from dataclasses import replace
import json
from threading import get_ident

import pytest

from local_cli.application.browser import BrowserCloseReceipt, BrowserUnavailable
from local_cli.application.browser_navigation import BrowserExecutionService
from local_cli.application.interactions import ApprovalGate
from local_cli.application.policy import PolicyEngineV2, ToolPolicyAction, ToolPolicyDecision
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.browser import BrowserActionError
from local_cli.core.contracts import EffectState, ToolStatus, new_operation_id
from local_cli.core.security import SecurityError
from local_cli.tools.browser_tools import browser_tools
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s2_runtime import response


class Adapter:
    close_receipt = None

    def __init__(self):
        from types import SimpleNamespace
        self.page = SimpleNamespace(is_closed=lambda: False)
        self.epoch, self.calls, self.threads = 0, [], []
        self.fail = False

    def binding(self, name, args):
        self.threads.append(get_ident())
        return {'adapter': 'WEBVIEW2', 'page': 'owned', 'epoch': self.epoch}

    def perform(self, name, args, expected):
        self.calls.append((name, args))
        if self.fail:
            raise BrowserActionError('BROWSER_ACTION_UNKNOWN', 'Unknown effect.', started=True)
        return {'page': 'owned', 'text': 'Owned result', 'localActionObserved': name == 'browser_click'}

    def close(self):
        self.close_receipt = BrowserCloseReceipt(True, True, True, True)
        return self.close_receipt


def call(tmp_path, name='browser_navigate', args=None, **ctx):
    base = invocation(tmp_path, name=name, arguments={'placeholder': True})
    base = replace(base, arguments={'url': 'http://example.test/path?q=ok#part'} if args is None else args)
    op = new_operation_id()
    return replace(base, operation_id=op, context=replace(base.context, operation_id=op, **ctx))


def setup(tmp_path, *, approve=None, policy=None, after_approval=None):
    adapter = Adapter()
    service = BrowserExecutionService(lambda: adapter)
    gate = None
    if approve is not None:
        gate = ApprovalGate()
        actor = gate.register_actor('desktop_host', lambda: True)
        def required(req):
            if after_approval: after_approval(adapter)
            try: gate.resolve(**{**response(req, actor), 'approved': approve})
            except Exception: pass  # Stale approval wakes its denied operation.
        gate._on_required = required
    rt = ToolRuntime(ToolRegistry(browser_tools(service_factory=lambda: service)), approval_gate=gate, policy=policy)
    rt.install_authority(tmp_path, 'session')
    return rt, adapter, service


def test_navigation_is_bound_to_browser_grant_and_replay_does_not_dispatch(tmp_path):
    rt, adapter, service = setup(tmp_path)
    try:
        inv = call(tmp_path)
        result = rt.execute(inv)
        assert result.status is ToolStatus.COMPLETED
        assert result.metadata['grantId'] and result.metadata['policyDecision'] == 'ALLOW'
        grant = next(iter(rt._issuer._issued.values())).grant
        assert any(c.permission.name == 'browser.navigate' for c in grant.request.capabilities)
        assert not any(c.permission.name == 'network.fetch' for c in grant.request.capabilities)
        assert rt.execute(inv) is result and len(adapter.calls) == 1
        with pytest.raises(BrowserActionError, match='already'):
            service.execute(inv, grant, rt._issuer, lambda: None)
        with pytest.raises(SecurityError): rt._issuer.claim(grant, grant.request)
        with pytest.raises((SecurityError, BrowserActionError)):
            service.execute(inv, replace(grant), rt._issuer, lambda: None)
    finally: rt.close()


@pytest.mark.parametrize('approve,expected', [(None, ToolStatus.DENIED), (False, ToolStatus.DENIED), (True, ToolStatus.COMPLETED)])
def test_interaction_requires_actual_human_approval_even_with_auto_yes(tmp_path, approve, expected):
    rt, adapter, _ = setup(tmp_path, approve=approve)
    rt._auto_approve = True
    try:
        result = rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}))
        assert result.status is expected
        assert len(adapter.calls) == int(approve is True)
        if approve is True:
            assert result.effect_state is EffectState.UNKNOWN
            assert result.metadata['policyDecision'] == 'REQUIRE_APPROVAL'
    finally: rt.close()


def test_page_changes_during_approval_deny_before_effect(tmp_path):
    rt, adapter, _ = setup(tmp_path, approve=True, after_approval=lambda a: setattr(a, 'epoch', 1))
    try:
        result = rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}))
        assert result.status is ToolStatus.DENIED and not adapter.calls
    finally: rt.close()


def test_policy_denial_still_prevents_browser_effect(tmp_path):
    class Deny(PolicyEngineV2):
        def evaluate(self, *args, **kwargs):
            return ToolPolicyDecision(ToolPolicyAction.DENY, 'OWNED_TEST_DENY', self.revision)
    rt, adapter, _ = setup(tmp_path, approve=True, policy=Deny())
    try:
        result = rt.execute(call(tmp_path))
        assert result.status is ToolStatus.DENIED and not adapter.calls
        assert result.metadata['securityErrorCode'] == 'OWNED_TEST_DENY'
    finally: rt.close()


def test_browser_calls_from_different_turns_use_one_playwright_thread(tmp_path):
    rt, adapter, _ = setup(tmp_path)
    try:
        for turn in ('first', 'second'):
            assert rt.execute(call(tmp_path, turn_id=turn)).status is ToolStatus.COMPLETED
        assert len(set(adapter.threads)) == 1 and adapter.threads[0] != get_ident()
    finally: rt.close()


def test_action_loss_blocks_retry_until_new_human_turn_and_observation(tmp_path):
    rt, adapter, _ = setup(tmp_path, approve=True)
    try:
        adapter.fail = True
        result = rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}))
        assert result.status is ToolStatus.OUTCOME_UNKNOWN and result.effect_state is EffectState.UNKNOWN
        adapter.fail = False
        retry = rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}))
        assert retry.status is ToolStatus.DENIED and len(adapter.calls) == 1
        rt.execute(call(tmp_path, 'browser_observe', {}, turn_id='new-human-turn'))
        assert rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}, turn_id='new-human-turn')).status is ToolStatus.COMPLETED
    finally: rt.close()


def test_unavailable_runtime_returns_result_without_legacy_executor(tmp_path):
    rt, adapter, _ = setup(tmp_path)
    def missing(*_): raise BrowserUnavailable('RUNTIME_NOT_FOUND', 'The bundled runtime is missing.')
    adapter.perform = missing
    try:
        result = rt.execute(call(tmp_path))
        assert json.loads(result.legacy_text)['status'] == 'unavailable'
        assert result.effect_state is EffectState.NONE
    finally: rt.close()
    # A lost DOM/IPC must not be queried to release the owned browser session.
    from local_cli.infrastructure.browser.pages import PlaywrightPageSession
    from types import SimpleNamespace
    dead = PlaywrightPageSession(tmp_path / 'absent-package')
    dead.page = SimpleNamespace(is_closed=lambda: True)
    binding = dead.binding('browser_close', {})
    assert dead.perform('browser_close', {}, binding)['status'] == 'closed'


@pytest.mark.parametrize('args', [{'url': 'https://example.test/', 'selector': '#button'}, {'url': 'https://example.test/', 'javascript': 'alert(1)'}])
def test_model_cannot_add_generic_browser_commands(tmp_path, args):
    rt, adapter, _ = setup(tmp_path)
    try:
        assert rt.execute(call(tmp_path, args=args)).status is ToolStatus.FAILED
        assert not adapter.calls
    finally: rt.close()


def test_subagents_do_not_receive_a_browser_session_or_browser_tools(tmp_path):
    from local_cli.tools import get_sub_agent_tools
    from local_cli.core.browser import BROWSER_TOOLS
    assert not ({t.name for t in get_sub_agent_tools(cwd=tmp_path)} & BROWSER_TOOLS)
    rt, adapter, _ = setup(tmp_path)
    try:
        assert rt.execute(call(tmp_path, agent_id='child')).status is ToolStatus.DENIED
        assert not adapter.calls
    finally: rt.close()


def test_action_ceiling_is_checked_before_browser_effect(tmp_path):
    rt, adapter, service = setup(tmp_path)
    try:
        service._counts[('session', 'turn')] = (25, 0)
        result = rt.execute(call(tmp_path))
        assert result.status is ToolStatus.DENIED and not adapter.calls
        assert result.metadata['securityErrorCode'] == 'BROWSER_ACTION_LIMIT'
    finally: rt.close()


def test_cli_and_jsonl_use_same_plan_free_tool_runtime_and_approval(tmp_path, monkeypatch):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.application.events import EventBufferConfig
    from local_cli.core.contracts import new_command_id
    from local_cli.interfaces.cli_application import CliApplicationClient
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    from local_cli.interfaces.approval_proof import approval_proof
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    from tests.test_nova_core_phase7_session import _pending
    for root in ('cli', 'jsonl-desktop'):
        adapter = Adapter()
        catalogs = []
        class Provider(ScriptedProvider):
            def chat_stream(self, model, messages, **kwargs):
                catalogs.append([t['function']['name'] for t in kwargs.get('tools', [])])
                return super().chat_stream(model, messages, **kwargs)
        provider = Provider([{'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'browser_click', 'arguments': {'ref': 'opaque'}}}]}, 'Observed locally.'])
        service = BrowserExecutionService(lambda: adapter)
        app = AgentSessionCoordinator(provider=provider, model='fixture', event_config=EventBufferConfig(),
            prompt_factory=lambda tools, workspace: 'Use the available tools. Report observed results only.',
            tool_factory=lambda _: browser_tools(service_factory=lambda: service,
                selection=__import__('types').SimpleNamespace(state=lambda: {'available': True})))
        sid = start(app, tmp_path).session_id
        if root == 'cli':
            rendered = []
            monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
            client = CliApplicationClient(app, sid, read=lambda _: 'y', write=rendered.append, write_error=lambda _: None)
            client.submit_user_input('Haz clic ahí.')
        else:
            frames, key = [], 'ab' * 32
            client = JsonlApplicationAdapter(app, sid, frames.append, host_approval_key=key)
            turn = submit(app, sid, 'Haz clic ahí.')
            req = _pending(app._session.approval_gate)
            command = ApplicationCommand(new_command_id(), CommandKind.RESOLVE_APPROVAL,
                {'approvalId': req.approval_id, 'toolCallId': req.tool_call_id,
                 'requestDigest': req.request_digest, 'cwd': req.cwd, 'policyRevision': req.policy_revision, 'approved': True}, session_id=sid)
            frame = {'id': 'approved', 'type': 'application_command', 'command': command.to_dict()}
            client.handle(frame)  # Renderer JSON alone still lacks human proof.
            assert not adapter.calls
            client.handle({**frame, 'hostApprovalProof': approval_proof(key, command.to_dict())})
            assert app.wait_for_turn(turn.created_ids['turnId'], 3)
        try:
            assert len(adapter.calls) == 1, (root, app._session.transcript)
            assert all('browser_navigate' in catalog for catalog in catalogs)
            assert 'browser_click' not in catalogs[0] and 'browser_click' in catalogs[-1]
            assert app._session.tool_runtime.policy_for('browser_click', {'ref': 'opaque'}).action is ToolPolicyAction.REQUIRE_APPROVAL
        finally: client.close()


def test_browser_observation_context_projection_preserves_complete_refs_and_urls(tmp_path):
    from local_cli.core.browser import project_browser_observation
    from local_cli.core.context import ContextManager, ContextSelection, TokenCounter, ContextError
    from local_cli.tools import get_default_tools
    from local_cli.prompts import build_system_prompt
    tools = get_default_tools(cwd=tmp_path)
    if not any(t.name == 'browser_navigate' for t in tools): tools.extend(browser_tools())
    refs = ['el_' + digit * 32 for digit in ('1', '2', '3', '4')]
    observation = {'page': 'page_' + 'a' * 32, 'url': 'http://example.test/page?q=ok#detail', 'title': 'Owned page',
        'text': 'JavaScript active. Clicks: 1. ' + 'Long retrieved text. ' * 300,
        'elements': [{'ref': ref, 'tag': tag, 'name': name} for ref, tag, name in zip(refs,
            ('input', 'button', 'a', 'a'), ('Nombre', 'Aumentar', 'Next', 'Other'))]}
    tool_message = {'role': 'tool', 'tool_name': 'browser_navigate', 'content': json.dumps(observation)}
    messages = [{'role': 'system', 'content': build_system_prompt(tools, cwd=tmp_path)},
                {'role': 'user', 'content': 'Open the page and click Aumentar.'},
                {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'browser_navigate', 'arguments': {'url': observation['url']}}}]},
                tool_message]
    prepared = ContextManager(ContextSelection(8192)).prepare(messages, [tool.to_ollama_tool() for tool in tools])
    packet = json.loads(prepared.messages[-1]['content'])
    assert packet['url'] == observation['url']
    assert len(packet['elements']) >= 2
    assert all(e['ref'] in refs for e in packet['elements'])
    assert 'Clicks: 1' in packet['text'] and packet['truncated'] is True
    # A new turn and new browser result must displace older browser history,
    # rather than letting an older group's exhausted quota fail generation.
    messages.extend([{'role': 'assistant', 'content': 'Observed.'},
        {'role': 'user', 'content': 'Type Nova and press Enter on that page.'},
        {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'browser_type', 'arguments': {'ref': refs[0], 'text': 'Nova'}}}]},
        {**tool_message, 'tool_name': 'browser_type', 'content': json.dumps({**observation, 'localActionObserved': True, 'remoteOutcome': 'UNKNOWN'})}])
    prepared = ContextManager(ContextSelection(8192)).prepare(messages, [tool.to_ollama_tool() for tool in tools])
    assert json.loads(prepared.messages[-1]['content'])['elements'][0]['ref'] == refs[0]
    counter = lambda message: TokenCounter().count(message, message=True).tokens
    with pytest.raises(ContextError, match='minimum browser observation'):
        project_browser_observation(tool_message, 10, counter)
