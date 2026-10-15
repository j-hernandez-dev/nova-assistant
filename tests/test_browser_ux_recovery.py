"""Block 6: shared recovery, bounded calls and presentation, not intent routing."""
from dataclasses import replace
import json
from threading import Event, Thread
from types import SimpleNamespace
import time

import pytest

from local_cli.agent import run_agent
from local_cli.application.browser_navigation import BrowserExecutionService
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry, LegacyToolAdapter
from local_cli.core.contracts import EventKind, ToolStatus, EffectState
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.tools.browser_tools import browser_tools
from local_cli.tools.read_tool import ReadTool
from tests.test_browser_product import Adapter, call, setup
from tests.test_browser_selection import selection
from tests.test_nova_core_phase4_session import ScriptedProvider


def _response(name, args):
    return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': name, 'arguments': args}}]}


def test_catalog_is_host_derived_each_generation_and_not_an_authority(tmp_path):
    adapter = Adapter(); service = BrowserExecutionService(lambda: adapter)
    tools = browser_tools(selection=selection(), service_factory=lambda: service)
    rt = ToolRuntime(ToolRegistry(tools)); rt.install_authority(tmp_path, 'session')
    catalogs = []
    class Provider(ScriptedProvider):
        def chat_stream(self, model, messages, **kwargs):
            catalogs.append([t['function']['name'] for t in kwargs.get('tools', [])])
            return super().chat_stream(model, messages, **kwargs)
    provider = Provider([_response('browser_navigate', {'url': 'https://owned.test/'}),
                         _response('browser_click', {'ref': 'opaque'}), 'Approval was not granted.'])
    adapted = [LegacyToolAdapter(t, rt, lambda: call(tmp_path).context) for t in tools]
    try:
        answer = run_agent(provider, 'fixture', adapted, [{'role': 'user', 'content': 'Open the page and click.'}])
        assert 'browser_click' not in catalogs[0] and 'browser_click' in catalogs[1]
        assert [c[0] for c in adapter.calls] == ['browser_navigate']
        assert adapted[2].last_execution_result is not None
        assert 'Approval' in answer
    finally: rt.close()


def test_missing_runtime_is_structured_and_leaves_file_tools_available(tmp_path):
    (tmp_path / 'readme.txt').write_text('Local file still works')
    choice = selection(missing=('webview2',))
    rt = ToolRuntime(ToolRegistry([*browser_tools(selection=choice), ReadTool(cwd=tmp_path)]))
    rt.install_authority(tmp_path, 'session')
    try:
        assert not rt.model_available('browser_navigate') and rt.model_available('read')
        failure = rt.execute(call(tmp_path))
        payload = json.loads(failure.legacy_text)
        assert payload['status'] == 'unavailable' and payload['code'] == 'BROWSER_NOT_INSTALLED'
        assert failure.effect_state is EffectState.NONE
        assert rt.execute(call(tmp_path, 'read', {'file_path': 'readme.txt'})).status is ToolStatus.COMPLETED
    finally: rt.close()


def test_lost_page_gets_new_binding_before_new_grant(tmp_path):
    created = []
    class Owned(Adapter):
        def __init__(self):
            super().__init__(); self.closed_page = False; self.identity = str(len(created))
            self.page = SimpleNamespace(is_closed=lambda: self.closed_page)
        def binding(self, name, args): return {**super().binding(name, args), 'page': self.identity}
    def factory():
        a = Owned(); created.append(a); return a
    service = BrowserExecutionService(factory)
    rt = ToolRuntime(ToolRegistry(browser_tools(selection=selection(), service_factory=lambda: service)))
    rt.install_authority(tmp_path, 'session')
    try:
        assert rt.execute(call(tmp_path)).status is ToolStatus.COMPLETED
        created[0].closed_page = True
        assert service.public_state()['sessionState'] == 'lost'
        assert not rt.model_available('browser_click') and rt.model_available('browser_navigate')
        assert rt.execute(call(tmp_path)).status is ToolStatus.COMPLETED
        assert len(created) == 2 and created[0].close_receipt.profile_removed
        grant = list(rt._issuer._issued.values())[-1].grant
        assert grant.request.network_intent['page'] == created[1].identity
        assert service.public_state()['sessionState'] == 'ready'
    finally: rt.close()


@pytest.mark.parametrize('cancel', [False, True])
def test_timeout_or_cancellation_after_started_stays_unknown_no_retry_and_local_tools_work(tmp_path, cancel):
    (tmp_path / 'local.txt').write_text('Independent local read')
    entered, release = Event(), Event()
    adapter = Adapter()
    service = BrowserExecutionService(lambda: adapter, timeout=0.2 if not cancel else 2)
    from local_cli.application.interactions import ApprovalGate
    from tests.security_v12.test_s2_runtime import response
    gate = ApprovalGate(); actor = gate.register_actor('desktop_host', lambda: True)
    gate._on_required = lambda r: gate.resolve(**response(r, actor))
    rt = ToolRuntime(ToolRegistry([*browser_tools(selection=selection(), service_factory=lambda: service), ReadTool(cwd=tmp_path)]), approval_gate=gate)
    rt.install_authority(tmp_path, 'session')
    try:
        rt.execute(call(tmp_path))
        def slow(name, args, expected):
            adapter.calls.append((name, args)); entered.set(); release.wait(3); return {'localActionObserved': True}
        adapter.perform = slow
        inv = call(tmp_path, 'browser_click', {'ref': 'opaque'})
        results = []
        worker = Thread(target=lambda: results.append(rt.execute(inv))); worker.start()
        assert entered.wait(1)
        if cancel: inv.context.cancellation_token.request()
        worker.join(1)
        assert not worker.is_alive() and results[0].status is ToolStatus.OUTCOME_UNKNOWN
        assert results[0].effect_state is EffectState.UNKNOWN
        assert service.public_state()['sessionState'] == 'unresponsive'
        assert not rt.model_available('browser_click') and rt.model_available('read')
        blocked = rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}))
        assert blocked.status is ToolStatus.DENIED and len(adapter.calls) == 2
        assert rt.execute(call(tmp_path, 'read', {'file_path': 'local.txt'})).status is ToolStatus.COMPLETED
    finally:
        release.set(); rt.close()


def test_cancel_before_start_has_zero_effect_and_no_automatic_retry(tmp_path):
    rt, adapter, _ = setup(tmp_path)
    try:
        inv = call(tmp_path); inv.context.cancellation_token.request()
        result = rt.execute(inv)
        assert result.status is ToolStatus.CANCELLED and result.effect_state is EffectState.NONE
        assert not adapter.calls and json.loads(result.legacy_text)['retrySameAction'] is False
    finally: rt.close()


def test_three_distinct_failures_end_boundedly_without_executing_batch_remainder(tmp_path):
    adapter = Adapter(); service = BrowserExecutionService(lambda: adapter)
    tools = browser_tools(selection=selection(), service_factory=lambda: service)
    rt = ToolRuntime(ToolRegistry(tools)); rt.install_authority(tmp_path, 'session')
    invoked = []
    def broken(name, args, expected):
        from local_cli.core.browser import BrowserActionError
        invoked.append(args); raise BrowserActionError('SEARCH_SITE_BLOCKED', 'Owned rejection')
    adapter.perform = broken
    batch = {'role': 'assistant', 'content': '', 'tool_calls': [
        {'function': {'name': 'browser_navigate', 'arguments': {'url': f'https://owned.test/{i}'}}} for i in range(7)]}
    requests = []
    class Provider(ScriptedProvider):
        def chat_stream(self, model, messages, **kwargs):
            requests.append(kwargs.get('tools', [])); return super().chat_stream(model, messages, **kwargs)
    try:
        answer = run_agent(Provider([batch, 'The site rejected the requests.']), 'fixture',
            [LegacyToolAdapter(t, rt, lambda: call(tmp_path).context) for t in tools], [{'role': 'user', 'content': 'Read these pages.'}])
        assert len(invoked) == 3 and requests[-1] == [] and len(requests) == 2
        assert 'rejected' in answer
    finally: rt.close()


def test_success_clears_old_error_and_unknown_never_becomes_success(tmp_path):
    rt, adapter, service = setup(tmp_path, approve=True)
    try:
        rt.execute(call(tmp_path)); adapter.fail = True
        result = rt.execute(call(tmp_path, 'browser_click', {'ref': 'opaque'}))
        assert result.status is ToolStatus.OUTCOME_UNKNOWN
        assert json.loads(result.legacy_text)['status'] == 'unknown'
        adapter.fail = False
        assert rt.execute(call(tmp_path, 'browser_observe', {}, turn_id='new-human')).status is ToolStatus.COMPLETED
        assert service.public_state()['lastErrorCode'] is None
    finally: rt.close()


@pytest.mark.parametrize('cleanup_ok', [False, True])
def test_only_confirmed_close_releases_quarantine_and_permits_fresh_browser(tmp_path, cleanup_ok):
    from dataclasses import asdict
    from local_cli.application.browser import BrowserCloseReceipt
    created = []
    class Owned(Adapter):
        def close(self):
            self.close_receipt = BrowserCloseReceipt(True, True, cleanup_ok, cleanup_ok,
                errors=() if cleanup_ok else ('PROFILE_CLEANUP_UNCONFIRMED',))
            return self.close_receipt
        def perform(self, name, args, expected):
            if name == 'browser_close':
                receipt = self.close()
                return {'status': 'closed' if cleanup_ok else 'cleanup_unconfirmed', 'cleanup': asdict(receipt)}
            return super().perform(name, args, expected)
    def factory():
        adapter = Owned(); created.append(adapter); return adapter
    service = BrowserExecutionService(factory)
    rt = ToolRuntime(ToolRegistry(browser_tools(selection=selection(), service_factory=lambda: service)))
    rt.install_authority(tmp_path, 'session')
    try:
        assert rt.execute(call(tmp_path)).status is ToolStatus.COMPLETED
        service._unresponsive = True
        closed = rt.execute(call(tmp_path, 'browser_close', {}))
        assert closed.status is (ToolStatus.COMPLETED if cleanup_ok else ToolStatus.OUTCOME_UNKNOWN)
        if not cleanup_ok:
            payload = json.loads(closed.legacy_text)
            assert payload['allowedNextTools'] == []
            assert 'not confirmed closed' in payload['recovery']
        new = rt.execute(call(tmp_path))
        assert new.status is (ToolStatus.COMPLETED if cleanup_ok else ToolStatus.DENIED)
        assert len(created) == (2 if cleanup_ok else 1)
    finally: rt.close()


@pytest.mark.parametrize('debug', [False, True])
def test_cli_uses_one_normal_projection_preserves_model_language_and_hides_internals(debug):
    client = object.__new__(CliApplicationClient)
    out, err = [], []
    client._write, client._write_error, client._debug = out.append, err.append, debug
    client._on_event = lambda _: None
    client._turn_text, client._seen_events = {}, set()
    def event(kind, payload, key): return SimpleNamespace(kind=kind, payload=payload, event_id=key, turn_id='t')
    for e in [event(EventKind.TOOL_REQUESTED, {'name': 'web_search'}, 'one'),
              event(EventKind.HARNESS_INTERVENTION, {'rule': 'error_stop'}, 'two'),
              event(EventKind.LEGACY_AGENT_EVENT, {'legacyKind': 'tool_result', 'data': {'result': '{"code":"SEARCH_SITE_BLOCKED"}'}}, 'three'),
              event(EventKind.THINKING_DELTA, {'text': 'private model thinking'}, 'four')]: client._render(e)
    e = event(EventKind.ASSISTANT_DELTA, {'text': 'No pude consultar el sitio.'}, 'five')
    client._render(e); client._render(e)
    client._final_once('t', 'No pude consultar el sitio.')
    assert ''.join(out).count('No pude consultar el sitio.') == 1
    if not debug:
        assert ''.join(err) == 'Searching the web…\n'
        assert not any(t in ''.join(out + err) for t in ('SEARCH_SITE_BLOCKED', '[harness]', 'private model thinking'))
    else: assert 'SEARCH_SITE_BLOCKED' in ''.join(err)


def test_empty_model_response_ends_explained_instead_of_silently():
    events = []
    answer = run_agent(ScriptedProvider(['', '']), 'fixture', [], [{'role': 'user', 'content': 'Hello.'}], emit=events.append)
    assert answer and 'did not return an answer' in answer
    assert len([e for e in events if e.kind == 'llm_start']) == 2


@pytest.mark.parametrize('command', ['/web fetch on', '/quit'])
def test_redundant_commands_are_removed_without_effect(command, capsys):
    from local_cli.cli import _handle_application_slash_command
    from tests.test_cli_preferences import console_stub, context
    console = console_stub()
    assert _handle_application_slash_command(command, console, context())
    assert 'Unknown command' in capsys.readouterr().out
    console.command.assert_not_called()


def test_browser_status_is_readable_and_invalid_arguments_do_not_escape(capsys):
    from local_cli.cli import _handle_application_slash_command
    from tests.test_cli_preferences import console_stub, context
    console = console_stub()
    console.snapshot.return_value.services['browser'] = {'selected': 'webview2', 'available': True, 'controlState': 'agentActive', 'hasPage': False}
    assert _handle_application_slash_command('/browser status', console, context())
    text = capsys.readouterr().out
    assert 'Browser: webview2 (available)' in text and '"selected"' not in text
    for cmd in ('/browser resume extra', '/browser discard', '/browser use invalid', '/search engine invalid'):
        assert _handle_application_slash_command(cmd, console, context())
        assert 'Error:' in capsys.readouterr().out
    console.command.assert_not_called()
