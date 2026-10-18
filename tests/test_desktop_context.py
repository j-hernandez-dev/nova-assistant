"""Desktop preset changes use the common inference boundary and atomic persistence."""
from copy import deepcopy
from threading import Event
import pytest
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.context import ContextPolicy
from local_cli.core.contracts import new_command_id
from local_cli.desktop_context_preferences import DesktopContextPreferences
from tests.test_context_64k import CapacityProvider, state_for
from tests.test_nova_core_phase4_session import start, submit, snapshot
from tests.test_nova_core_phase9_integration import capabilities


def setup_app(tmp_path, **kwargs):
    provider = CapacityProvider()
    app = AgentSessionCoordinator(provider=provider, model='old', provider_manager=state_for(provider),
        tool_factory=lambda _: [], prompt_factory=lambda *_: 'Synthetic safety instructions.',
        context_policy=ContextPolicy(resource_limit=65536), capability_factory=capabilities, **kwargs)
    session = start(app, tmp_path).session_id
    return app, session, provider


def change(app, session, tokens, **kwargs):
    return app.handle(ApplicationCommand(new_command_id(), CommandKind.SET_CONTEXT_WINDOW,
        session_id=session, payload={'requestedTokens': tokens}, **kwargs))


def test_context_setter_accepts_only_exact_supported_numeric_payloads():
    for value in (True, False, -1, 1, 8193, 131072, '64K', None, [], {}):
        with pytest.raises(ValueError):
            ApplicationCommand(new_command_id(), CommandKind.SET_CONTEXT_WINDOW,
                session_id='synthetic', payload={'requestedTokens': value})
    with pytest.raises(ValueError):
        ApplicationCommand(new_command_id(), CommandKind.SET_CONTEXT_WINDOW,
            session_id='synthetic', payload={'requestedTokens': 65536, 'permission': 'all'})


def test_preset_persists_across_fresh_store_and_corruption_preserves_default(tmp_path, monkeypatch):
    store = DesktopContextPreferences(tmp_path)
    assert store.load(8192) == 8192
    for value in (0, 4096, 8192, 16384, 32768, 65536):
        store.save(value)
        assert DesktopContextPreferences(tmp_path).load() == value
    old = store.path.read_bytes()
    monkeypatch.setattr('local_cli.desktop_context_preferences.os.replace', lambda *_: (_ for _ in ()).throw(OSError('owned failure')))
    with pytest.raises(OSError):
        store.save(4096)
    assert store.path.read_bytes() == old
    assert not list(tmp_path.glob('.desktop-context-*.tmp'))
    for invalid in ('{}', '{"schemaVersion":1,"requestedTokens":true}', '{"schemaVersion":1,"requestedTokens":131072}', 'invalid', ' ' * 4097):
        store.path.write_text(invalid)
        assert store.load(16384) == 16384


def test_change_reaches_next_inference_preserves_transcript_and_is_idempotent(tmp_path):
    store = DesktopContextPreferences(tmp_path / 'settings')
    app, session, provider = setup_app(tmp_path, context_selection_save=store.save)
    first = submit(app, session, 'Synthetic first turn')
    assert app.wait_for_turn(first.created_ids['turnId'], 5)
    before = deepcopy(snapshot(app, session).transcript)
    command = ApplicationCommand(new_command_id(), CommandKind.SET_CONTEXT_WINDOW,
        session_id=session, payload={'requestedTokens': 65536}, expected_revision=snapshot(app, session).state_revision)
    receipt = app.handle(command)
    assert receipt.accepted and app.handle(command) == receipt
    assert snapshot(app, session).transcript == before
    assert snapshot(app, session).services['context'] == {'requestedTokens': 65536, 'selectedTokens': 65536, 'errorCode': None}
    second = submit(app, session, 'Synthetic second turn')
    assert app.wait_for_turn(second.created_ids['turnId'], 5)
    assert provider.requests[-1][1]['options']['num_ctx'] == 65536
    assert store.load() == 65536
    fresh, fresh_session, _ = setup_app(tmp_path, context_selection=DesktopContextPreferences(tmp_path / 'settings').load())
    assert snapshot(fresh, fresh_session).services['context']['requestedTokens'] == 65536
    assert change(app, session, 0).accepted
    assert snapshot(app, session).services['context']['requestedTokens'] == 0
    assert snapshot(app, session).services['context']['selectedTokens'] == 32768


def test_rejected_limit_revision_and_save_failure_leave_previous_selection(tmp_path):
    def fail(_):
        raise OSError('owned save error')
    app, session, _ = setup_app(tmp_path, context_selection=8192, context_selection_save=fail)
    before = snapshot(app, session)
    assert change(app, session, 16384, expected_revision=0).error.code == 'REVISION_CONFLICT'
    assert change(app, session, 16384).error.code == 'CONTEXT_PREFERENCES_SAVE_FAILED'
    app._context_policy = ContextPolicy(resource_limit=8192)
    assert change(app, session, 65536).error.code == 'CONTEXT_LIMIT_EXCEEDED'
    after = snapshot(app, session)
    assert after.services['context']['requestedTokens'] == 8192
    assert after.state_revision == before.state_revision and after.transcript == before.transcript


def test_active_turn_cannot_change_context(tmp_path):
    entered, release = Event(), Event()
    def running(provider, model, tools, messages, **kwargs):
        entered.set()
        assert release.wait(5)
        messages.append({'role': 'assistant', 'content': 'synthetic response'})
        return 'synthetic response'
    app, session, _ = setup_app(tmp_path, context_selection=8192, run_agent_fn=running)
    receipt = submit(app, session, 'Synthetic active turn')
    assert entered.wait(5)
    try:
        assert change(app, session, 65536).error.code == 'CONFLICT_ACTIVE_OPERATION'
        assert app._context_selection == 8192
    finally:
        release.set()
        assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
