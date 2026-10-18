"""GUI activity is a private projection of typed receipts and bounded real output."""
from dataclasses import replace
from datetime import datetime
import json
import sys
from threading import Event, Thread

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.process import ProcessExecutionService, TOOL_OUTPUT_BYTES, _OutputProgress
from local_cli.application.secrets import SecretRedactor
from local_cli.application.session import AgentSessionCoordinator, TOOL_ARGUMENT_BYTES
from local_cli.core.contracts import EventKind, Visibility, new_command_id
from local_cli.core.process import ProcessLaunchRequest, ProcessLimits, ProcessReport
from local_cli.harness import AgentEvent
from local_cli.infrastructure.host_process import HostProcessLauncher
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.shell_tool import ShellTool
from local_cli.tools.write_tool import WriteTool
from tests.test_gui_conversation import MemoryPersistence
from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
from tests.security_v12.test_s2_runtime import response


def limits(**changes):
    return replace(ProcessLimits(100 * 1024, 100 * 1024, 100 * 1024, 10, 20, 2, 1), **changes)


class StreamingLauncher:
    supports_output_progress = True

    def __init__(self, *, outcome='completed', code=None):
        self.entered, self.release = Event(), Event()
        self.calls = 0
        self.outcome, self.code = outcome, code

    def launch(self, request, *, on_output, validate_launch, **_kwargs):
        validate_launch()
        self.calls += 1
        on_output('stdout', b'live output\n', False)
        self.entered.set()
        assert self.release.wait(5)
        on_output('stderr', b'live warning\n', False)
        # The final receipt replaces live publication, even when its text differs.
        return ProcessReport(321, 0, 'authoritative output\n', 'authoritative warning\n',
            self.outcome, self.code, ('running', 'root_exited', 'cleanup_confirmed'),
            cleanup_confirmed=True)


def app_with_shell(tmp_path, launcher, *, command='echo fixture', journal_capacity=8, **kwargs):
    shell = ShellTool(descriptor=ShellDescriptor('Windows', 'powershell',
        str(tmp_path / 'fixture_pwsh.exe'), 'fixture'), cwd=tmp_path, environment={})
    captured = []

    def runner(_provider, _model, tools, messages, *, emit, **_kwargs):
        emit(AgentEvent('llm_start', {}))
        message = {'role': 'assistant', 'content': 'preamble'}
        messages.append(message)
        emit(AgentEvent('assistant_message', {'message': message}))
        captured.append(tools[0].execute(command=command))
        final = {'role': 'assistant', 'content': 'done'}
        messages.append(final)
        return 'done'

    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model='local',
        tool_factory=lambda _cwd: [shell], run_agent_fn=runner,
        process_service=ProcessExecutionService(launcher, limits()),
        event_config=EventBufferConfig(journal_capacity=journal_capacity), **kwargs)
    session_id = start(app, tmp_path).session_id
    return app, session_id, captured


def test_live_activity_receipt_ids_reconnect_and_authoritative_terminal(tmp_path):
    launcher = StreamingLauncher()
    app, session_id, _captured = app_with_shell(tmp_path, launcher)
    cursor = app.subscribe_events(session_id)
    app.poll_events(cursor)
    receipt = submit(app, session_id, 'run fixture')
    try:
        assert launcher.entered.wait(5)
        live = app.get_snapshot(session_id).turns[0]
        activity = live['toolActivities'][0]
        assert activity['messageId'] == live['displayMessages'][-1]['id']
        assert activity['turnId'] == receipt.created_ids['turnId']
        assert activity['status'] == activity['operationStatus'] == 'running'
        assert activity['output'] == activity['stdout'] == 'live output\n'
        assert activity['outputSequence'] == 2 and 'completedAt' not in activity
        assert datetime.fromisoformat(activity['startedAt']).utcoffset() is not None
        events = app.poll_events(cursor)
        chunks = [e for e in events if e.kind is EventKind.OPERATION_PROGRESS and e.payload.get('channel')]
        assert len(chunks) == 1 and chunks[0].payload['text'] == 'live output\n'
        assert chunks[0].visibility is Visibility.SENSITIVE
        # Cursor eviction recovers the aggregate projection from its snapshot.
        reconnect = app.subscribe_events(session_id, after_sequence=0)
        recovered = app.poll_events(reconnect)
        snapshots = [e for e in recovered if e.kind is EventKind.SESSION_SNAPSHOT]
        assert snapshots and snapshots[-1].payload['turns'][0]['toolActivities'][0] == activity
    finally:
        launcher.release.set()
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    snapshot = app.get_snapshot(session_id)
    final = snapshot.turns[0]['toolActivities'][0]
    assert final['operationId'] == activity['operationId'] and final['toolCallId'] == activity['toolCallId']
    assert final['status'] == final['operationStatus'] == 'completed'
    assert final['stdout'] == 'authoritative output\n'
    assert final['stderr'] == 'authoritative warning\n' and final['exitCode'] == 0
    assert final['output'] == final['stdout'] + final['stderr']
    assert final['outputSequence'] > activity['outputSequence']
    assert final['completedAt'] >= final['startedAt']
    assert all('toolActivities' not in message for message in snapshot.transcript)
    # Late output cannot revive or append to a terminal activity.
    invocation = next(iter(app._session.tool_runtime._outcomes))
    assert invocation == final['operationId'] and launcher.calls == 1


@pytest.mark.parametrize('command,approval', [('Format-Volume D:', False), ('Remove-Item fixture', True)])
def test_typed_policy_and_approval_denial_never_start(tmp_path, command, approval):
    launcher = StreamingLauncher()
    app, session_id, _ = app_with_shell(tmp_path, launcher, command=command)
    if approval:
        gate = app._session.approval_gate
        actor = gate.register_actor('desktop_host', lambda: True)
        def deny(request):
            answer = response(request, actor)
            answer['approved'] = False
            gate.resolve(**answer)
        gate._on_required = deny
    receipt = submit(app, session_id, 'run fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    activity = app.get_snapshot(session_id).turns[0]['toolActivities'][0]
    assert activity['status'] == 'denied' and activity['operationStatus'] == 'failed'
    assert activity['effectState'] == 'none' and activity['errorCode']
    assert 'startedAt' not in activity and 'completedAt' in activity
    assert launcher.calls == 0


def test_unknown_cancelled_process_is_never_success_or_retried(tmp_path):
    launcher = StreamingLauncher(outcome='outcome_unknown', code='PROCESS_CANCELLED')
    app, session_id, _ = app_with_shell(tmp_path, launcher, journal_capacity=128)
    invocations = []
    runtime = app._session.tool_runtime
    original_publish = runtime._publish_progress
    def capture(invocation, *args):
        invocations.append(invocation)
        original_publish(invocation, *args)
    runtime._publish_progress = capture
    receipt = submit(app, session_id, 'run fixture')
    try:
        assert launcher.entered.wait(5)
        turn = app._session.turns[0]
        turn.cancellation.request()
    finally:
        launcher.release.set()
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    activity = app.get_snapshot(session_id).turns[0]['toolActivities'][0]
    assert activity['status'] == activity['operationStatus'] == 'outcome_unknown'
    assert activity['effectState'] == 'unknown' and activity['errorCode'] == 'PROCESS_CANCELLED'
    assert launcher.calls == 1
    fingerprint, typed = app._session.tool_runtime._outcomes[activity['operationId']]
    assert typed.status.value == 'outcome_unknown' and fingerprint
    assert runtime.execute(invocations[0]) is typed
    assert launcher.calls == 1
    app._publish_tool_progress(app._session, invocations[0], 'stdout', 'late output', False)
    assert app.get_snapshot(session_id).turns[0]['toolActivities'][0] == activity


def test_public_tool_events_never_include_activity_arguments_cwd_or_output(tmp_path):
    launcher = StreamingLauncher()
    app, session_id, _ = app_with_shell(tmp_path, launcher, journal_capacity=128)
    public_cursor = app._events.subscribe(include_sensitive=False)
    owner_cursor = app.subscribe_events(session_id)
    app.poll_events(public_cursor)
    app.poll_events(owner_cursor)
    receipt = submit(app, session_id, 'run fixture')
    try:
        assert launcher.entered.wait(5)
    finally:
        launcher.release.set()
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    public = app.poll_events(public_cursor)
    assert not any(e.kind is EventKind.OPERATION_PROGRESS and e.payload.get('service') == 'tool' for e in public)
    tools = [e for e in public if e.kind in (EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED,
        EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED)]
    assert tools and all(not {'activity', 'arguments', 'cwd', 'output', 'stdout', 'stderr'} & e.payload.keys() for e in tools)
    owner = app.poll_events(owner_cursor)
    projections = [e for e in owner if e.payload.get('activity')]
    assert projections and all(e.visibility is Visibility.SENSITIVE for e in projections)


def test_progress_redacts_split_secrets_utf8_and_bounds_bytes_and_frequency(monkeypatch):
    redactor = SecretRedactor(source={})
    redactor.register('private-secret-value')
    observed = []
    monkeypatch.setattr('local_cli.application.process.time.monotonic', lambda: 0.0)
    class PausedTimer:
        def __init__(self, *_args): pass
        def start(self): pass
        def cancel(self): pass
    monkeypatch.setattr('local_cli.application.process.Timer', PausedTimer)
    progress = _OutputProgress(redactor, lambda *args: observed.append(args), TOOL_OUTPUT_BYTES)
    for chunk in (b'safe private-', b'secret-', b'value \xe2', b'\x82', b'\xac tail\n'):
        progress.feed('stdout', chunk)
    for _ in range(200):
        progress.feed('stderr', b'x' * 4096)
    progress.finish()
    text = ''.join(row[1] for row in observed)
    assert 'private' not in text and 'secret' not in text and '[REDACTED]' in text
    assert '€ tail' in text and len(text.encode('utf-8')) <= TOOL_OUTPUT_BYTES
    assert any(row[2] for row in observed)
    assert len(observed) <= 3  # One immediate batch plus one terminal flush per channel.


def test_snapshot_final_outputs_and_error_are_redacted_and_bounded(tmp_path):
    launcher = StreamingLauncher(outcome='failed', code='PROCESS_EXIT_NONZERO')
    app, session_id, _ = app_with_shell(tmp_path, launcher)
    app.redactor.register('known-credential')
    original = launcher.launch
    def launch(*args, **kwargs):
        report = original(*args, **kwargs)
        return replace(report, exit_code=7, stdout='known-credential ' + '€' * TOOL_OUTPUT_BYTES,
            stderr='warning ' * TOOL_OUTPUT_BYTES)
    launcher.launch = launch
    receipt = submit(app, session_id, 'run fixture')
    try:
        assert launcher.entered.wait(5)
    finally:
        launcher.release.set()
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    activity = app.get_snapshot(session_id).turns[0]['toolActivities'][0]
    assert activity['status'] == 'failed' and activity['exitCode'] == 7
    assert activity['outputTruncated'] and activity['errorCode'] == 'PROCESS_EXIT_NONZERO'
    for key in ('output', 'stdout', 'stderr'):
        assert len(activity[key].encode('utf-8')) <= TOOL_OUTPUT_BYTES
        assert 'known-credential' not in activity[key]


def test_activity_structure_survives_secret_equal_to_status_and_split_chunks(tmp_path):
    launcher = StreamingLauncher()
    def launch(_request, *, on_output, validate_launch, **_kwargs):
        validate_launch()
        for chunk in (b'completed private-', b'secret-', b'value done\n'):
            on_output('stdout', chunk, False)
        return ProcessReport(123, 0, 'completed private-secret-value done\n', '',
            'completed', None, ('running', 'root_exited', 'cleanup_confirmed'))
    launcher.launch = launch
    app, session_id, _ = app_with_shell(tmp_path, launcher, journal_capacity=128)
    app.redactor.register('completed')
    app.redactor.register('private-secret-value')
    cursor = app.subscribe_events(session_id)
    app.poll_events(cursor)
    receipt = submit(app, session_id, 'run fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    activity = app.get_snapshot(session_id).turns[0]['toolActivities'][0]
    assert activity['status'] == activity['operationStatus'] == 'completed'
    assert activity['stdout'] == '[REDACTED] [REDACTED] done\n'
    projections = [e.payload['activity'] for e in app.poll_events(cursor) if e.payload.get('activity')]
    assert projections[-1]['status'] == projections[-1]['operationStatus'] == 'completed'
    for projection in projections:
        assert 'private-secret' not in projection['output']
        assert 'completed' not in projection['output']


def test_large_write_arguments_are_only_bounded_in_activity_preview(tmp_path):
    content = '\\"' * TOOL_ARGUMENT_BYTES + 'Ω'
    call = {'role': 'assistant', 'content': '', 'tool_calls': [{
        'function': {'name': 'write', 'arguments': {'file_path': 'owned.txt', 'content': content}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call, 'done']), model='local',
        tool_factory=lambda cwd: [WriteTool(cwd=cwd)], event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    receipt = submit(app, session_id, 'write the owned fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    activity = app.get_snapshot(session_id).turns[0]['toolActivities'][0]
    assert activity['status'] == 'completed'
    assert activity['arguments']['truncated'] is True
    assert len(json.dumps(activity['arguments'], ensure_ascii=False).encode('utf-8')) <= TOOL_ARGUMENT_BYTES
    assert (tmp_path / 'owned.txt').read_text(encoding='utf-8') == content


def test_resume_clears_only_presentation_activity_and_retains_execution_receipts(tmp_path):
    persistence = MemoryPersistence(tmp_path)
    launcher = StreamingLauncher()
    launcher.release.set()
    app, session_id, _ = app_with_shell(tmp_path, launcher,
        persistence_factory=lambda _workspace: persistence)
    receipt = submit(app, session_id, 'run fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
    turn = app._session.turns[0]
    assert turn.tool_activities
    operations = dict(turn.tool_operations)
    outcomes = dict(app._session.tool_runtime._outcomes)
    persistence.restore_messages = [{'role': 'user', 'content': 'old question'},
                                    {'role': 'assistant', 'content': 'old answer'}]
    resumed = app.handle(ApplicationCommand(new_command_id(), CommandKind.EXECUTE_COMMAND,
        session_id=session_id, payload={'name': 'resume'}))
    assert resumed.accepted
    assert app.get_snapshot(session_id).turns[0]['toolActivities'] == []
    assert turn.tool_operations == operations and app._session.tool_runtime._outcomes == outcomes


def test_pending_progress_flushes_while_process_is_silent_and_still_running():
    observed, delivered = [], Event()
    def callback(channel, text, cut):
        observed.append((channel, text, cut))
        if 'second' in text:
            delivered.set()
    progress = _OutputProgress(SecretRedactor(source={}), callback, TOOL_OUTPUT_BYTES)
    try:
        progress.feed('stdout', b'first')
        progress.feed('stdout', b'second')
        assert delivered.wait(1)
        assert ''.join(row[1] for row in observed) == 'firstsecond'
    finally:
        progress.finish()


def test_native_host_output_callback_arrives_while_process_is_running(tmp_path):
    """An owned Python process proves the callback reads pipes before final report."""
    ready, release = Event(), tmp_path / 'release-owned-fixture'
    script = tmp_path / 'output_fixture.py'
    script.write_text("import pathlib,sys,time\nprint('first',flush=True)\n"
        "release=pathlib.Path(sys.argv[1])\nend=time.monotonic()+5\n"
        "while not release.exists() and time.monotonic()<end: time.sleep(.01)\n"
        "print('second',flush=True)\n", encoding='utf-8')
    process_limits = limits()
    request = ProcessLaunchRequest('owned output fixture',
        (sys.executable, '-B', str(script), str(release)), str(tmp_path), {}, 10, process_limits)
    chunks, result = [], []
    def observe(channel, text, cut):
        chunks.append((channel, text, cut))
        if 'first' in text:
            ready.set()
    service = ProcessExecutionService(HostProcessLauncher(), process_limits)
    worker = Thread(target=lambda: result.append(service.execute(request,
        cancellation_token=CancellationController(), deadline=None, validate_launch=lambda: None,
        on_output=observe)), daemon=True)
    worker.start()
    try:
        assert ready.wait(5)
        assert worker.is_alive() and not result
        assert ''.join(row[1] for row in chunks).replace('\r\n', '\n') == 'first\n'
    finally:
        release.touch()
        worker.join(5)
    assert not worker.is_alive()
    assert result[0][0].outcome == 'completed'
    assert ''.join(row[1] for row in chunks).replace('\r\n', '\n') == 'first\nsecond\n'
