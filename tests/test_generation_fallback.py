"""Unsupported native tools adapt within one public response before any output."""
from threading import Event

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.harness import AgentEvent
from local_cli.providers.base import ProviderConnectionError, ProviderRequestError
from tests.test_nova_core_phase4_session import EchoTool, start, submit, snapshot
from tests.test_nova_core_phase9_integration import capabilities


class NoNativeTools:
    def __init__(self, entered, release, terminal='completed'):
        self.entered, self.release, self.terminal = entered, release, terminal
        self.requests = []

    def chat_stream(self, model, messages, **kwargs):
        self.requests.append(kwargs)
        if 'tools' in kwargs:
            raise ProviderRequestError('synthetic model does not support tools')
        self.entered.set()
        assert self.release.wait(5)
        if self.terminal == 'failed':
            raise ProviderConnectionError('synthetic connection lost')
        yield {'message': {'role': 'assistant', 'content': 'Synthetic response.'}, 'done': True}


def application(tmp_path, provider, **kwargs):
    app = AgentSessionCoordinator(provider=provider, model='synthetic',
        prompt_factory=lambda *_: 'Synthetic mandatory instructions.',
        tool_factory=lambda _: [EchoTool()], capability_factory=capabilities,
        event_config=EventBufferConfig(128, 128, 1), **kwargs)
    return app, start(app, tmp_path).session_id


def test_tool_format_adaptation_keeps_one_live_response_and_stable_identity(tmp_path):
    entered, release = Event(), Event()
    provider = NoNativeTools(entered, release)
    app, session = application(tmp_path, provider)
    receipt = submit(app, session, 'Synthetic greeting')
    assert entered.wait(5)
    try:
        current = snapshot(app, session).turns[-1]
        assert current['status'] == 'running'
        assert len(current['displayMessages']) == 1
        row = current['displayMessages'][0]
        assert row['status'] == 'streaming' and row['thinking']
        assert row['harnessEvents'] == ['tools_fallback']
        assert current['activeGenerationId'] == row['generationId']
        events = app.poll_events(app.subscribe_events(session, after_sequence=0))
        assert [e.kind for e in events].count(EventKind.GENERATION_STARTED) == 1
        assert EventKind.GENERATION_FAILED not in [e.kind for e in events]
        assert any(e.kind is EventKind.HARNESS_INTERVENTION and e.payload.get('rule') == 'tools_fallback' for e in events)
    finally:
        release.set()
        assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    final = snapshot(app, session).turns[-1]
    assert final['status'] == 'completed' and final['terminalCount'] == 1
    assert len(final['displayMessages']) == 1
    completed = final['displayMessages'][0]
    assert completed['status'] == 'completed'
    assert (completed['id'], completed['generationId'], completed['createdAt']) == (row['id'], row['generationId'], row['createdAt'])
    assert completed['completedAt'] and completed['content'] == 'Synthetic response.'
    assert 'tools' in provider.requests[0] and 'tools' not in provider.requests[1]
    events = app.poll_events(app.subscribe_events(session, after_sequence=0))
    terminals = [e for e in events if e.kind in (EventKind.GENERATION_COMPLETED, EventKind.GENERATION_FAILED, EventKind.GENERATION_CANCELLED)]
    assert len(terminals) == 1 and terminals[0].kind is EventKind.GENERATION_COMPLETED
    assert terminals[0].generation_id == row['generationId']


@pytest.mark.parametrize('terminal', ['failed', 'cancelled'])
def test_adaptation_does_not_hide_a_later_failure_or_cancellation(tmp_path, terminal):
    entered, release = Event(), Event()
    provider = NoNativeTools(entered, release, terminal)
    app, session = application(tmp_path, provider)
    receipt = submit(app, session, 'Synthetic greeting')
    assert entered.wait(5)
    try:
        if terminal == 'cancelled':
            assert app.handle(ApplicationCommand(new_command_id(), CommandKind.CANCEL_TURN,
                session_id=session, payload={'turnId': receipt.created_ids['turnId']})).accepted
    finally:
        release.set()
        assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    state = snapshot(app, session)
    assert state.turns[-1]['status'] == terminal
    rows = state.turns[-1]['displayMessages']
    assert len(rows) == 1 and rows[0]['status'] == terminal
    events = app.poll_events(app.subscribe_events(session, after_sequence=0))
    generation_terminal = EventKind.GENERATION_FAILED if terminal == 'failed' else EventKind.GENERATION_CANCELLED
    assert [e.kind for e in events].count(generation_terminal) == 1
    assert EventKind.GENERATION_COMPLETED not in [e.kind for e in events]
    assert len(provider.requests) == 2  # One adaptation, no replay after a real failure.


@pytest.mark.parametrize('delta', [None, 'content_delta', 'thinking_delta'])
def test_unexpected_restart_and_output_before_fallback_keep_the_failed_generation(tmp_path, delta):
    entered, release = Event(), Event()
    def runner(provider, model, tools, messages, **kwargs):
        emit = kwargs['emit']
        emit(AgentEvent('llm_start', {}))
        if delta:
            emit(AgentEvent(delta, {'text': 'Observed partial'}))
            emit(AgentEvent('tools_fallback', {}))
        emit(AgentEvent('llm_start', {}))
        entered.set()
        assert release.wait(5)
        message = {'role': 'assistant', 'content': 'Synthetic response.'}
        messages.append(message)
        emit(AgentEvent('assistant_message', {'message': message}))
        return message['content']
    app, session = application(tmp_path, object(), run_agent_fn=runner)
    receipt = submit(app, session, 'Synthetic greeting')
    assert entered.wait(5)
    try:
        rows = snapshot(app, session).turns[-1]['displayMessages']
        assert [r['status'] for r in rows] == ['failed', 'streaming']
        assert rows[0]['generationId'] != rows[1]['generationId']
        events = app.poll_events(app.subscribe_events(session, after_sequence=0))
        assert [e.kind for e in events].count(EventKind.GENERATION_FAILED) == 1
    finally:
        release.set()
        assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
