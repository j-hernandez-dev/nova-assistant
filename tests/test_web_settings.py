"""Web preferences and execution boundaries; synthetic browsers and HTTP only."""
from dataclasses import replace
import json
from unittest.mock import Mock

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.tools.browser_tools import browser_tools
from local_cli.tools.browser_search_tool import BrowserSearchTool
from local_cli.tools.web_fetch_tool import WebFetchTool
from local_cli.core.contracts import new_command_id
from local_cli.web_config import DEFAULTS, FILENAME, load_web_settings, save_web_settings
from tests.test_browser_selection import selection
from tests.test_browser_product import call
from tests.test_nova_core_phase4_session import ScriptedProvider, start


def app_for(tmp_path, **kwargs):
    state_dir = tmp_path / 'preferences'
    preferences = load_web_settings(state_dir)
    choice = selection()
    tools = [*browser_tools(selection=choice), BrowserSearchTool(selection=choice), WebFetchTool()]
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model='fixture',
        tool_factory=lambda _: tools, prompt_factory=lambda tools, _: ','.join(tool.name for tool in tools),
        fetch_enabled=preferences['fetchEnabled'], search_enabled=preferences['searchEnabled'],
        browser_enabled=preferences['browserEnabled'],
        web_settings_save=kwargs.pop('save', lambda value: save_web_settings(state_dir, value)), **kwargs)
    return app, start(app, tmp_path).session_id, state_dir


def change(app, sid, patch, *, revision=None):
    state = app.get_snapshot(sid).services
    value = dict(fetchEnabled=state['fetch']['enabled'], searchEnabled=state['search']['enabled'],
        browserEnabled=state['browser']['enabled'], engine=state['search']['engine'], browser=state['browser']['selected'])
    return app.handle(ApplicationCommand(new_command_id(), CommandKind.SET_WEB_SETTINGS,
        {**value, **patch}, sid, expected_revision=revision))


def test_defaults_and_existing_individual_preferences_are_read_without_writes(tmp_path):
    assert load_web_settings(tmp_path) == DEFAULTS
    assert not list(tmp_path.iterdir())
    from local_cli.fetch_config import save_fetch_enabled
    from local_cli.browser_config import save_browser
    from local_cli.browser_search_config import save_settings
    save_fetch_enabled(tmp_path, False); save_browser(tmp_path, 'edge'); save_settings(tmp_path, 'bing')
    assert load_web_settings(tmp_path) == {**DEFAULTS, 'fetchEnabled': False, 'browser': 'edge', 'engine': 'bing'}
    assert not (tmp_path / FILENAME).exists()


def test_one_atomic_preference_owner_stays_compatible_with_existing_cli_setters(tmp_path):
    from local_cli.fetch_config import load_fetch_enabled, save_fetch_enabled
    from local_cli.browser_config import load_browser, save_browser
    from local_cli.browser_search_config import load_settings, save_settings
    save_web_settings(tmp_path, {**DEFAULTS, 'searchEnabled': False})
    save_fetch_enabled(tmp_path, False); save_browser(tmp_path, 'edge'); save_settings(tmp_path, 'duckduckgo')
    assert load_fetch_enabled(tmp_path) is False
    assert load_browser(tmp_path) == 'edge' and load_settings(tmp_path).engine == 'duckduckgo'
    assert load_web_settings(tmp_path)['searchEnabled'] is False
    assert [p.name for p in tmp_path.iterdir()] == [FILENAME]


@pytest.mark.parametrize('payload', ['bad', '{}', json.dumps({'schema':'unknown', **DEFAULTS}),
    json.dumps({'schema':'NOVA_WEB_PREFERENCES_V1', **DEFAULTS, 'searchEnabled':'true'})])
def test_invalid_preferences_disable_web_permissions_without_rewriting(tmp_path, payload):
    (tmp_path / FILENAME).write_text(payload, encoding='utf8')
    value = load_web_settings(tmp_path)
    assert not any(value[key] for key in ('fetchEnabled','searchEnabled','browserEnabled'))
    assert (tmp_path / FILENAME).read_text(encoding='utf8') == payload


@pytest.mark.parametrize('patch', [{'searchEnabled':0}, {'browserEnabled':'false'}, {'engine':'other'},
    {'browser':'firefox'}, {'extra':True}])
def test_full_command_has_an_exact_typed_schema(patch):
    with pytest.raises(ValueError):
        ApplicationCommand(new_command_id(), CommandKind.SET_WEB_SETTINGS, {**DEFAULTS, **patch}, 'session')


def test_permissions_are_independent_and_reset_restores_the_catalog_without_touching_conversation(tmp_path):
    app, sid, state_dir = app_for(tmp_path)
    try:
        app._session.transcript.append({'role':'user', 'content':'Keep this conversation'})
        original = list(app._session.transcript[1:])
        assert change(app, sid, {'browserEnabled':False}).accepted
        names = [tool.name for tool in app._session.tools]
        assert 'web_search' in names and 'web_fetch' in names and not any(n.startswith('browser_') for n in names)
        assert change(app, sid, {'searchEnabled':False, 'fetchEnabled':False, 'engine':'bing', 'browser':'edge'}).accepted
        assert not app._session.tools
        assert load_web_settings(state_dir)['engine'] == 'bing'
        assert change(app, sid, DEFAULTS).accepted
        assert {'web_fetch','web_search','browser_navigate'} <= {t.name for t in app._session.tools}
        assert load_web_settings(state_dir) == DEFAULTS and app._session.transcript[1:] == original
    finally: app._session.tool_runtime.close()


@pytest.mark.parametrize('name,patch,code', [
    ('web_fetch',{'fetch_enabled':False},'FETCH_DISABLED'),
    ('web_search',{'search_enabled':False},'SEARCH_DISABLED'),
    ('browser_navigate',{'browser_enabled':False},'BROWSER_DISABLED'),
    ('browser_click',{'browser_enabled':False},'BROWSER_DISABLED'),
])
def test_disabled_tools_cannot_bypass_the_runtime_even_when_called_directly(tmp_path, name, patch, code):
    choice = selection()
    runtime = ToolRuntime(ToolRegistry([*browser_tools(selection=choice), BrowserSearchTool(selection=choice), WebFetchTool()]), **patch)
    try:
        assert runtime.model_available(name) is False
        result = runtime.execute(call(tmp_path, name=name))
        assert code in str(result.error) or code in result.stderr
        assert runtime._browser_service is None
    finally: runtime.close()


def test_failed_atomic_save_and_conflicts_preserve_all_confirmed_values(tmp_path):
    save = Mock(side_effect=OSError('owned disk failure'))
    app, sid, state_dir = app_for(tmp_path, save=save)
    try:
        initial = app.get_snapshot(sid)
        receipt = change(app, sid, {'searchEnabled':False,'fetchEnabled':False})
        assert not receipt.accepted and receipt.error.code == 'WEB_CONFIGURATION_FAILED'
        assert app._search_enabled and app._fetch_enabled and app._session.tool_runtime.search_enabled
        assert app.get_snapshot(sid).state_revision == initial.state_revision
        assert not state_dir.exists()
        save.reset_mock()
        assert not change(app, sid, {'browserEnabled':False}, revision=initial.state_revision+1).accepted
        save.assert_not_called()
    finally: app._session.tool_runtime.close()


def test_active_execution_rejects_preference_changes_without_saving(tmp_path):
    save = Mock()
    app, sid, _ = app_for(tmp_path, save=save)
    active = Mock(); active.done.is_set.return_value = False
    try:
        app._session.agent_operations['active'] = active
        result = change(app, sid, {'browserEnabled':False})
        assert not result.accepted and result.error.code == 'CONFLICT_ACTIVE_OPERATION'
        save.assert_not_called()
    finally:
        app._session.agent_operations.clear(); app._session.tool_runtime.close()


def test_permissions_and_selections_are_observable_without_a_browser_installation(tmp_path):
    state_dir = tmp_path/'preferences'
    initial = {**DEFAULTS, 'searchEnabled':False, 'engine':'bing', 'browser':'edge'}
    save_web_settings(state_dir, initial)
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model='fixture',
        tool_factory=lambda _: [WebFetchTool()], search_enabled=False, web_engine='bing', web_browser='edge',
        web_settings_save=lambda value:save_web_settings(state_dir,value))
    sid = start(app, tmp_path).session_id
    try:
        state = app.get_snapshot(sid).services
        assert not state['search']['enabled'] and state['search']['engine'] == 'bing'
        assert state['browser']['selected'] == 'edge' and not state['browser']['available']
        assert change(app, sid, {'fetchEnabled':False}).accepted
        assert load_web_settings(state_dir) == {**initial, 'fetchEnabled':False}
    finally: app._session.tool_runtime.close()


def test_rebind_and_subagent_runtime_keep_permissions_and_never_reenable_hidden_tools(tmp_path):
    from local_cli.sub_agent import SubAgent
    app, sid, _ = app_for(tmp_path)
    try:
        assert change(app, sid, {'searchEnabled':False,'browserEnabled':False}).accepted
        tools = app._session.installed_tools
        child = SubAgent(provider=ScriptedProvider([]), model='fixture', tools=tools, prompt='Synthetic task',
            cwd=tmp_path, search_enabled=False, browser_enabled=False)
        assert {tool.name for tool in child._source_tools} == {'web_fetch'}
        other=tmp_path/'other';other.mkdir()
        app.rebind_legacy_workspace(other, base_messages=[{'role':'system','content':'base'}], persistence=None, rag=None)
        assert {tool.name for tool in app._session.tools} == {'web_fetch'}
        assert not app._session.tool_runtime.search_enabled and not app._session.tool_runtime.browser_enabled
    finally: app._session.tool_runtime.close()
