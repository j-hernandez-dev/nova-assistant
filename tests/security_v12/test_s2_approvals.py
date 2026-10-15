"""S2 CLI/JSONL/Application trust boundaries: unit/mock and in-process integration."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import subprocess
import io
import json
import sys

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.events import EventBufferConfig
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.security import get_sanitized_env
from tests.security_v12.test_s2_runtime import pending_runtime, response
from tests.test_nova_core_phase4_session import ScriptedProvider
from tests.test_nova_core_phase7_session import _pending
from tests.security_v12.process_fixtures import bind_mock_shell


def setup(tmp_path):
    from local_cli.tools.bash_tool import BashTool
    from local_cli.shell_executor import ShellDescriptor
    exe = Mock()
    exe.run.return_value = subprocess.CompletedProcess([], 0, 'ok', '')
    shell = BashTool(descriptor=ShellDescriptor('Windows', 'powershell', str(tmp_path/'pwsh.exe'), '7'),
                     executor=exe, cwd=tmp_path, environment={})
    bind_mock_shell(shell, exe)
    provider = ScriptedProvider([{'role': 'assistant', 'content': '', 'tool_calls': [
        {'function': {'name': 'bash', 'arguments': {'command': 'npm install'}}} ]}, 'done'])
    app = AgentSessionCoordinator(provider=provider, model='fixture', tool_factory=lambda _: [shell],
                                  event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
                        {'workspace': str(tmp_path)}))
    return app, started.session_id, exe


def command(req, session_id):
    return ApplicationCommand(new_command_id(), CommandKind.RESOLVE_APPROVAL,
        {'approvalId': req.approval_id, 'toolCallId': req.tool_call_id,
         'requestDigest': req.request_digest, 'cwd': req.cwd, 'policyRevision': 1, 'approved': True},
        session_id=session_id)


def start(app, sid):
    return app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
                      {'content': 'fixture'}, session_id=sid))


def test_application_command_json_cannot_supply_actor(tmp_path):
    app, sid, exe = setup(tmp_path)
    turn = start(app, sid)
    try:
        req = _pending(app._session.approval_gate)
        raw = command(req, sid).to_dict()
        raw['approval_actor'] = {'kind': 'desktop_host'}
        result = app.handle(ApplicationCommand.from_dict(raw))
        assert not result.accepted
        assert result.error.code == 'APPROVAL_ACTOR_INVALID'
        exe.run.assert_not_called()
    finally:
        app.handle(ApplicationCommand(new_command_id(), CommandKind.CANCEL_TURN,
                   {'turnId': turn.created_ids['turnId']}, session_id=sid))
        assert app.wait_for_turn(turn.created_ids['turnId'], 3)


def test_private_desktop_proof_required_and_exact_positive_response(tmp_path):
    app, sid, exe = setup(tmp_path)
    sent, key = [], 'ab' * 32
    adapter = JsonlApplicationAdapter(app, sid, sent.append, host_approval_key=key)
    turn = start(app, sid)
    try:
        req = _pending(app._session.approval_gate)
        cmd = command(req, sid)
        frame = {'id': 'response', 'type': 'application_command', 'command': cmd.to_dict()}
        adapter.handle(frame)
        assert sent[-1]['code'] == 'APPROVAL_ACTOR_INVALID'
        exe.run.assert_not_called()
        wrong = {**frame, 'hostApprovalProof': approval_proof(key, replace(cmd,
                 payload={**cmd.payload, 'approved': False}).to_dict())}
        adapter.handle(wrong)
        assert sent[-1]['code'] == 'APPROVAL_ACTOR_INVALID'
        adapter.handle({**frame, 'hostApprovalProof': approval_proof(key, cmd.to_dict())})
        assert sent[-1]['data']['accepted']
        assert app.wait_for_turn(turn.created_ids['turnId'], 3)
        exe.run.assert_called_once()
        adapter.handle({**frame, 'hostApprovalProof': approval_proof(key, cmd.to_dict())})
        exe.run.assert_called_once()
    finally:
        app._session.turns[0].cancellation.request()
        app.wait_for_turn(turn.created_ids['turnId'], 3)
        adapter.close()


def test_cli_redirected_yes_is_denied_without_reading_input(tmp_path, monkeypatch):
    app, sid, exe = setup(tmp_path)
    monkeypatch.setattr(sys, 'stdin', io.StringIO('yes\n'))
    cli = CliApplicationClient(app, sid, read=lambda _: pytest.fail('headless input read'),
                                write=lambda _: None, write_error=lambda _: None)
    try:
        cli.submit_user_input('fixture')
        exe.run.assert_not_called()
        assert not app._session.approval_gate.pending()
    finally:
        cli.close()


def test_cli_verified_tty_positive_is_bound_to_current_request(tmp_path, monkeypatch):
    app, sid, exe = setup(tmp_path)
    monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
    cli = CliApplicationClient(app, sid, read=lambda _: 'yes',
                                write=lambda _: None, write_error=lambda _: None)
    try:
        cli.submit_user_input('fixture')
        exe.run.assert_called_once()
    finally:
        cli.close()


def test_legacy_confirm_frame_cannot_authorize(tmp_path):
    app, sid, exe = setup(tmp_path)
    sent = []
    adapter = JsonlApplicationAdapter(app, sid, sent.append)
    adapter.handle({'type': 'confirm_response', 'confirm_id': 1, 'approved': True})
    assert sent[-1]['code'] == 'APPROVAL_ACTOR_INVALID'
    exe.run.assert_not_called()
    adapter.close()


def test_host_credential_is_excluded_from_child_environment(monkeypatch):
    monkeypatch.setenv('NOVA_APPROVAL_HOST_KEY', 'dummy-not-a-real-key')
    assert 'NOVA_APPROVAL_HOST_KEY' not in get_sanitized_env()


def test_node_and_python_agree_on_private_proof_without_desktop_dependencies():
    import shutil
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    root = Path(__file__).resolve().parents[2]
    cmd = {'schemaVersion': 1, 'commandId': 'cmd', 'sessionId': 'session', 'expectedRevision': None,
           'kind': 'ResolveApproval', 'payload': {'approved': True, 'cwd': 'C:/ñ'}}
    script = "const {signApproval}=require('./desktop/electron/approval_host.cjs'); " \
             "process.stdout.write(signApproval('ab'.repeat(32),JSON.parse(process.argv[1])))"
    actual = subprocess.check_output([node, '-e', script, json.dumps(cmd, ensure_ascii=False)],
                                     cwd=root, text=True, timeout=10)
    assert actual == approval_proof('ab' * 32, cmd)


def test_desktop_sender_and_native_confirmation_are_on_both_ipc_paths():
    root = Path(__file__).resolve().parents[2]
    source = (root/'desktop/electron/main.ts').read_text(encoding='utf-8')
    assert 'event.sender === mainWindow.webContents' in source
    assert 'event.senderFrame === mainWindow.webContents.mainFrame' in source
    assert "data.command?.kind === 'ResolveApproval'" in source
    assert "kind === 'ResolveApproval'" in source and 'dialog.showMessageBox' in source
    assert "crypto.randomBytes(32)" in source
