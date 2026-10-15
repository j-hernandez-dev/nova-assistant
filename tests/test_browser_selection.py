"""Optional Browser configuration, shared composition and effect boundaries."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from local_cli.application.browser import BrowserCloseReceipt, BrowserUnavailable
from local_cli.application.browser_selection import BrowserSelection
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.browser_config import load_browser, save_browser, FILENAME
from local_cli.core.browser import BrowserActionError
from local_cli.core.contracts import ToolStatus, new_command_id
from local_cli.tools.browser_tools import browser_tools
from local_cli.tools.browser_search_tool import BrowserSearchTool
from tests.test_browser_product import Adapter, call
from tests.test_nova_core_phase4_session import ScriptedProvider, start


def selection(*, missing=(), created=None):
    created = [] if created is None else created
    def choices():
        return [{'browser': b, 'adapter': b.upper(), 'available': b not in missing,
                 'installed': b not in missing, 'reason': 'BROWSER_NOT_INSTALLED' if b in missing else None,
                 'message': 'Not installed' if b in missing else '', 'executable': None}
                for b in ('webview2', 'chrome', 'edge')]
    class Selected(Adapter):
        def __init__(self, kind):
            super().__init__(); self.kind, self.identity = kind, uuid4().hex
        def binding(self, name, args):
            if 'ref' in args and args['ref'] != self.identity:
                raise BrowserActionError('BROWSER_REF_STALE', 'Observe the new page.')
            return {'adapter': self.kind.upper(), 'page': self.identity, 'epoch': 0}
    def create(choice):
        adapter = Selected(choice['browser']); created.append(adapter); return adapter
    return BrowserSelection(choices, create)


def app_for(tmp_path, choice):
    tools = [*browser_tools(selection=choice), BrowserSearchTool(selection=choice)]
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model='fixture',
        tool_factory=lambda _: tools, event_config=EventBufferConfig())
    return app, start(app, tmp_path).session_id


def change(app, sid, browser):
    return app.handle(ApplicationCommand(new_command_id(), CommandKind.SET_BROWSER, {'browser': browser}, sid))


def dispatch(app, inv):
    # Synchronous recorded Turn fixture for direct-runtime boundary tests.
    from local_cli.application.session import Turn
    turn = next((t for t in app._session.turns if t.turn_id == inv.context.turn_id), None)
    if turn is None:
        turn = Turn(inv.context.turn_id, inv.operation_id, new_command_id())
        app._session.turns.append(turn)
    try: return app._session.tool_runtime.execute(inv)
    finally: turn.done.set()


@pytest.mark.parametrize('browser', ['webview2', 'chrome', 'edge'])
def test_explicit_choice_persists_without_changing_search_or_other_preferences(tmp_path, browser):
    assert load_browser(tmp_path / 'new') == 'webview2' and not (tmp_path / 'new').exists()
    old = tmp_path / 'browser-search.json'; old.write_text('unchanged')
    save_browser(tmp_path, browser)
    assert load_browser(tmp_path) == browser and old.read_text() == 'unchanged'
    assert set(json.loads((tmp_path / FILENAME).read_text())) == {'schema', 'browser'}


def test_missing_saved_browser_never_falls_back_or_rewrites_preferences(tmp_path):
    save_browser(tmp_path, 'chrome')
    choice = selection(missing=('chrome',)); choice.configure(tmp_path)
    assert choice.state()['selected'] == 'chrome' and not choice.state()['available']
    with pytest.raises(BrowserUnavailable, match='Not installed'): choice.create()
    assert load_browser(tmp_path) == 'chrome'
    choice.select('webview2')
    assert load_browser(tmp_path) == 'webview2'


def test_discovery_uses_only_registered_or_known_installed_locations(tmp_path):
    from local_cli.infrastructure.browser.discovery import installed_executable
    program = tmp_path / 'Program Files'
    for kind, relative in [('chrome', 'Google/Chrome/Application/chrome.exe'), ('edge', 'Microsoft/Edge/Application/msedge.exe')]:
        path = program / relative; path.parent.mkdir(parents=True); path.write_bytes(b'owned test file, never executed')
        assert installed_executable(kind, environment={'ProgramFiles': str(program)}, registered=[]) == path.resolve()
    assert installed_executable('chrome', environment={'PATH': str(program)}, registered=[]) is None
    fake = tmp_path / 'not-a-browser.exe'; fake.write_bytes(b'fixture')
    assert installed_executable('chrome', environment={}, registered=[fake]) is None


def test_shared_tools_and_search_use_the_same_host_choice(tmp_path):
    from local_cli.bootstrap_passive_web import passive_web_tools
    choice = selection()
    tools = [*browser_tools(selection=choice), BrowserSearchTool(selection=choice)]
    save_browser(tmp_path, 'edge')
    assert passive_web_tools(tools, SimpleNamespace(state_dir=tmp_path)) == tools
    assert all(t.selection is choice for t in tools) and choice.selected == 'edge'
    assert tools[-1].state()['adapter'] == 'EDGE'
    assert all('browser' not in t.parameters['properties'] for t in tools)


def test_switch_closes_old_session_and_rejects_old_refs_and_grant_before_effect(tmp_path):
    created = []
    choice = selection(created=created)
    app, sid = app_for(tmp_path, choice)
    rt = app._session.tool_runtime
    try:
        inv = call(tmp_path, session_id=sid)
        assert dispatch(app, inv).status is ToolStatus.COMPLETED
        old = created[-1]
        grant = next(iter(rt._issuer._issued.values())).grant
        assert change(app, sid, 'edge').accepted and old.close_receipt.profile_removed
        assert rt._browser_service is None
        assert dispatch(app, call(tmp_path, session_id=sid, turn_id='fresh')).status is ToolStatus.COMPLETED
        new = created[-1]
        assert new is not old and new.kind == 'edge'
        stale = dispatch(app, call(tmp_path, 'browser_click', {'ref': old.identity}, session_id=sid))
        assert stale.status is ToolStatus.DENIED and len(new.calls) == 1
        with pytest.raises(BrowserActionError, match='changed'):
            rt._browser_service.execute(inv, grant, rt._issuer, lambda: None)
        assert len(new.calls) == 1
        assert app.get_snapshot(sid).services['browser']['selected'] == 'edge'
    finally: rt.close()

    from local_cli.infrastructure.browser.windows_installed import InstalledBrowserSession
    unconfirmed = InstalledBrowserSession(tmp_path, 'edge', tmp_path / 'msedge.exe')
    def failed_stop(): raise OSError('owned simulated failure')
    unconfirmed._playwright = SimpleNamespace(stop=failed_stop)
    receipt = unconfirmed.close()
    assert not receipt.job_empty and 'PLAYWRIGHT_STOP_UNCONFIRMED' in receipt.errors


def test_missing_browser_is_structured_and_never_starts_another_engine(tmp_path):
    choice = selection(missing=('chrome',)); choice.selected = 'chrome'
    rt = ToolRuntime(ToolRegistry(browser_tools(selection=choice)))
    rt.install_authority(tmp_path, 'session')
    try:
        result = rt.execute(call(tmp_path))
        assert json.loads(result.legacy_text)['status'] == 'unavailable'
        assert result.error == 'BROWSER_NOT_INSTALLED' and choice.selected == 'chrome'
    finally: rt.close()
    # A missing installation at launch preserves its actionable typed reason,
    # rather than turning it into a generic page error or trying another engine.
    from local_cli.infrastructure.browser.windows_installed import InstalledPageSession
    dead = InstalledPageSession(tmp_path, 'chrome', tmp_path / 'absent/chrome.exe')
    expected = dead.binding('browser_navigate', {'url': 'http://example.test/'})
    with pytest.raises(BrowserUnavailable) as rejected:
        dead.perform('browser_navigate', {'url': 'http://example.test/'}, expected)
    assert rejected.value.code in ('BROWSER_NOT_INSTALLED', 'UNSUPPORTED_PLATFORM')
    assert dead.profile_directory is None and dead.close_receipt.profile_removed


def test_failed_cleanup_is_not_relabelled_or_bypassed_by_another_switch(tmp_path):
    created = []; choice = selection(created=created)
    app, sid = app_for(tmp_path, choice)
    rt = app._session.tool_runtime
    try:
        dispatch(app, call(tmp_path, session_id=sid))
        created[0].close = lambda: BrowserCloseReceipt(True, False, False, False, errors=('OWNED_CLEANUP_FAILED',))
        for browser in ('edge', 'chrome'):
            result = change(app, sid, browser)
            assert not result.accepted and result.error.code == 'BROWSER_CLEANUP_UNCONFIRMED'
            assert choice.selected == 'webview2' and len(created) == 1
    finally: rt.close()


def test_cli_and_jsonl_desktop_backend_change_one_application_choice(tmp_path, capsys):
    from local_cli.cli import _handle_application_slash_command, _SLASH_COMMANDS
    from local_cli.interfaces.cli_application import CliApplicationClient
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    choice = selection(missing=('chrome',)); choice.configure(tmp_path)
    app, sid = app_for(tmp_path, choice)
    frames = []
    backend = JsonlApplicationAdapter(app, sid, send=frames.append)
    cli = CliApplicationClient(app, sid, write=lambda _: None, write_error=lambda _: None)
    try:
        _handle_application_slash_command('/browser use edge', cli, SimpleNamespace())
        assert load_browser(tmp_path) == 'edge' and 'Browser set to edge' in capsys.readouterr().out
        command = ApplicationCommand(new_command_id(), CommandKind.SET_BROWSER, {'browser': 'webview2'}, sid)
        backend.handle({'id': 'choice', 'type': 'application_command', 'command': command.to_dict()})
        assert frames[-1]['data']['accepted'] and cli.snapshot().services['browser']['selected'] == 'webview2'
        _handle_application_slash_command('/browser use chrome', cli, SimpleNamespace())
        assert 'Not installed' in capsys.readouterr().out and choice.selected == 'webview2'
        _handle_application_slash_command('/browser use anything', cli, SimpleNamespace())
        assert 'Error:' in capsys.readouterr().out
        assert any(k.startswith('/browser ') for k in _SLASH_COMMANDS)
        from local_cli.application.session import Turn
        busy = Turn('busy', 'owned-operation', new_command_id())
        app._session.turns.append(busy)
        try:
            result = change(app, sid, 'edge')
            assert not result.accepted and result.error.code == 'CONFLICT_ACTIVE_OPERATION'
            assert choice.selected == 'webview2'
        finally: busy.done.set()
    finally: cli.close(); backend.close()


@pytest.mark.parametrize('payload', [{'browser': 'firefox'}, {'browser': 'edge', 'executable': 'C:/other.exe'}, {'browser': 'edge', 'profile': 'personal'}])
def test_configuration_cannot_supply_executable_profile_or_unsupported_browser(payload):
    with pytest.raises(ValueError):
        ApplicationCommand(new_command_id(), CommandKind.SET_BROWSER, payload, 'session')
