"""Browser discovery reuses the Browser runtime; HTTP fetch stays independent."""
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from local_cli.core.browser_search import BrowserSearchSettings, bounded_results
from local_cli.tools.browser_search_tool import BrowserSearchTool
from local_cli.application.browser_navigation import BrowserExecutionService
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.contracts import ToolStatus, new_command_id
from local_cli.application.commands import ApplicationCommand, CommandKind
from tests.test_browser_product import Adapter, call


@pytest.mark.parametrize('engine', ['bing', 'google', 'duckduckgo'])
def test_host_engine_builds_encoded_query_and_model_cannot_supply_endpoint(engine, tmp_path):
    settings = BrowserSearchSettings(engine)
    from urllib.parse import urlsplit, parse_qs
    url = settings.request({'query': 'México ayer & ciencia', 'max_results': 3})
    assert parse_qs(urlsplit(url).query)['q'] == ['México ayer & ciencia']
    tool = BrowserSearchTool(settings=settings)
    rt = ToolRuntime(ToolRegistry([tool]))
    rt.install_authority(tmp_path, 'session')
    try:
        result = rt.execute(call(tmp_path, 'web_search', {'query': 'news', 'endpoint': 'http://other/'}))
        assert result.status is ToolStatus.FAILED and rt._browser_service is None
    finally: rt.close()


def runtime(tmp_path, *, policy=None):
    class SearchAdapter(Adapter):
        def binding(self, name, args):
            return {**super().binding(name, args), 'destination': self.search_settings.request(args)}
        def perform(self, name, args, expected):
            self.calls.append((name, args))
            return {'status': 'results', 'results': [], 'sourceType': 'SEARCH_SNIPPET'}
    adapter = SearchAdapter()
    service = BrowserExecutionService(lambda: adapter)
    rt = ToolRuntime(ToolRegistry([BrowserSearchTool(service_factory=lambda: service)]), policy=policy, fetch_enabled=False)
    rt.install_authority(tmp_path, 'session')
    return rt, adapter


def test_search_uses_browser_policy_grant_without_http_or_fetch_opt_in(tmp_path):
    rt, adapter = runtime(tmp_path)
    try:
        inv = call(tmp_path, 'web_search', {'query': 'México noticias'})
        result = rt.execute(inv)
        assert result.status is ToolStatus.COMPLETED and len(adapter.calls) == 1
        assert result.metadata['policyDecision'] == 'ALLOW'
        grant = next(iter(rt._issuer._issued.values())).grant
        assert grant.request.effect_classification == 'browser.DATA_DISCLOSURE'
        assert any(c.permission.name == 'browser.navigate' for c in grant.request.capabilities)
        assert not any(c.permission.name == 'network.fetch' for c in grant.request.capabilities)
        assert rt._network_service is None
        assert rt.execute(inv) is result and len(adapter.calls) == 1
        assert 'google.com/search?' in grant.request.network_intent['destination']
    finally: rt.close()


def test_search_policy_denial_has_zero_browser_effect(tmp_path):
    from local_cli.application.policy import PolicyEngineV2, ToolPolicyAction, ToolPolicyDecision
    class Deny(PolicyEngineV2):
        def evaluate(self, *args, **kwargs):
            return ToolPolicyDecision(ToolPolicyAction.DENY, 'OWNED_DENY', self.revision)
    rt, adapter = runtime(tmp_path, policy=Deny())
    try:
        assert rt.execute(call(tmp_path, 'web_search', {'query': 'news'})).status is ToolStatus.DENIED
        assert not adapter.calls
    finally: rt.close()
    # Existing Browser names cannot fall through to a generic legacy executor,
    # even when another real Browser tool installed the same permission family.
    from local_cli.tools.base import Tool
    from local_cli.tools.browser_tools import BrowserTool
    effects = []
    class Fake(Tool):
        name, description = 'browser_navigate', 'Untrusted implementation'
        parameters = {'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': ['url']}
        def execute(self, **kwargs): effects.append(kwargs); return 'effect'
    rt = ToolRuntime(ToolRegistry([Fake(), BrowserTool('browser_back')]))
    rt.install_authority(tmp_path, 'session')
    try:
        result = rt.execute(call(tmp_path))
        assert result.status is ToolStatus.DENIED and not effects
        assert 'BROWSER_COMPOSITION_UNAVAILABLE' in result.legacy_text
    finally: rt.close()


@pytest.mark.parametrize('arguments', [{'query': ''}, {'query': 'x' * 501}, {'query': 'x\nsecret'}, {'query': 'ok', 'max_results': 6}])
def test_query_limits_are_bounded(arguments):
    from local_cli.core.browser import BrowserActionError
    with pytest.raises(BrowserActionError): BrowserSearchSettings().request(arguments)


def test_results_are_bounded_deduplicated_and_never_article_receipts():
    rows = [{'url': 'javascript:alert(1)', 'title': 'bad'}, {'url': 'https://u:p@host/', 'title': 'bad'},
            {'url': 'https://example.test/?a=1#part', 'title': 'A' * 300, 'snippet': 'B' * 900}] * 10
    result = bounded_results(rows, 5)
    assert len(result) == 1 and result[0]['url'].endswith('?a=1#part')
    assert len(result[0]['title']) == 180 and len(result[0]['snippet']) == 500
    assert result[0]['pageRead'] is False


def test_preference_defaults_without_migration_and_changes_only_explicitly(tmp_path):
    from local_cli.browser_search_config import load_settings, save_settings, FILENAME
    from local_cli.bootstrap_passive_web import passive_web_tools
    assert load_settings(tmp_path / 'missing').engine == 'google'
    assert not (tmp_path / 'missing').exists()
    legacy = tmp_path / 'old-config'; legacy.write_text('web_search_endpoint=private')
    tool = BrowserSearchTool()
    tools = passive_web_tools([tool], SimpleNamespace(state_dir=tmp_path, web_search_enabled=True, web_search_endpoint='https://old/'))
    assert tools == [tool] and tool.settings.engine == 'google'
    tool.set_engine('google')
    assert load_settings(tmp_path).engine == 'google'
    assert legacy.read_text() == 'web_search_endpoint=private'
    with pytest.raises(ValueError): save_settings(tmp_path, 'arbitrary')
    assert json.loads((tmp_path / FILENAME).read_text())['engine'] == 'google'


def test_application_roots_share_search_settings_and_invalid_command_is_bounded(tmp_path, capsys):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from tests.test_nova_core_phase4_session import ScriptedProvider, start
    from local_cli.cli import _handle_application_slash_command, _SLASH_COMMANDS
    tool = BrowserSearchTool()
    tool.configure(tmp_path)
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model='fixture', tool_factory=lambda _: [tool], event_config=EventBufferConfig())
    sid = start(app, tmp_path).session_id
    command = ApplicationCommand(new_command_id(), CommandKind.SET_SEARCH_ENGINE, {'engine': 'duckduckgo'}, sid)
    assert app.handle(command).accepted
    assert app.get_snapshot(sid).services['search']['engine'] == 'duckduckgo'
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    from local_cli.interfaces.cli_application import CliApplicationClient
    frames = []
    backend = JsonlApplicationAdapter(app, sid, send=frames.append, host_approval_key='ab' * 32)
    cli = CliApplicationClient(app, sid, write=lambda _: None, write_error=lambda _: None)
    try:
        changed = ApplicationCommand(new_command_id(), CommandKind.SET_SEARCH_ENGINE, {'engine': 'google'}, sid)
        assert backend.handle({'id': 'search-config', 'type': 'application_command', 'command': changed.to_dict()})
        assert frames[-1]['data']['accepted']
        assert cli.snapshot().services['search']['engine'] == 'google'
        malformed = {**changed.to_dict(), 'commandId': str(new_command_id()), 'payload': {'engine': 'bad'}}
        backend.handle({'id': 'invalid-search', 'type': 'application_command', 'command': malformed})
        assert frames[-1]['code'] == 'INVALID_APPLICATION_COMMAND'
    finally:
        cli.close(); backend.close()
    console = Mock()
    _handle_application_slash_command('/search engine arbitrary', console, SimpleNamespace())
    assert 'Error:' in capsys.readouterr().out
    console.command.assert_not_called()
    assert any(key.startswith('/search ') for key in _SLASH_COMMANDS)
    with pytest.raises(ValueError):
        ApplicationCommand(new_command_id(), CommandKind.SET_SEARCH_ENGINE, {'engine': 'bing', 'endpoint': 'http://other'}, sid)


def test_search_projection_keeps_whole_source_urls():
    from local_cli.core.browser import project_browser_observation
    url = 'https://example.test/article?' + 'x' * 150 + '#part'
    message = {'role': 'tool', 'tool_name': 'web_search', 'content': json.dumps({
        'status': 'results', 'engine': 'bing', 'results': [{'url': url, 'title': 'Title', 'snippet': 's' * 1000}]})}
    result = project_browser_observation(message, 650, lambda m: len(m['content']))
    assert json.loads(result['content'])['results'][0]['url'] == url
