"""Block 5 bounded contracts; real engine coverage is a separate Windows job."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from local_cli.application.browser_files import BrowserFiles
from local_cli.application.secrets import SecretRedactor
from local_cli.core.browser import BrowserActionError
from local_cli.core.contracts import ToolStatus, EffectState
from tests.test_browser_product import Adapter, call, setup


def _snapshot(path):
    data = Path(path).read_bytes(); stat = Path(path).stat()
    return data, {'identity': str(stat.st_ino), 'size': len(data), 'write': stat.st_mtime_ns,
                  'digest': hashlib.sha256(data).hexdigest(), 'name': Path(path).name, 'mime': 'text/plain'}


def test_selected_file_ref_is_exact_owner_bound_expiring_and_one_use(tmp_path):
    files = BrowserFiles(tmp_path / 'staging', _snapshot)
    path = tmp_path / 'source.txt'; path.write_text('Original')
    ctx = call(tmp_path).context
    selected = files.select(path, (ctx.session_id, str(ctx.workspace)))
    args = {'file_ref': selected['fileRef']}
    assert files.upload(args, ctx)[0] == b'Original'
    with pytest.raises(BrowserActionError): files.upload(args, replace(ctx, session_id='other'))
    old = files.selected[args['file_ref']]
    files.selected[args['file_ref']] = (*old[:3], time.monotonic() - 1)
    with pytest.raises(BrowserActionError): files.upload(args, ctx)
    files.selected[args['file_ref']] = old
    path.write_text('Changed')
    with pytest.raises(BrowserActionError, match='changed'): files.upload(args, ctx)
    path.unlink(); path.write_text('Original')
    with pytest.raises(BrowserActionError): files.upload(args, ctx)
    files.consumed(args)
    with pytest.raises(BrowserActionError): files.upload(args, ctx)


def test_workspace_upload_and_explicit_external_selection_do_not_expand_scope(tmp_path):
    files = BrowserFiles(tmp_path / 'staging', _snapshot); ctx = call(tmp_path).context
    path = tmp_path / 'source.txt'; path.write_text('Owned')
    assert files.upload({'file_path': 'source.txt'}, ctx)[0] == b'Owned'
    with pytest.raises(BrowserActionError): files.upload({'file_path': '../private.txt'}, ctx)
    with pytest.raises(BrowserActionError): files.upload({'file_path': str(tmp_path.parent / 'private.txt')}, ctx)
    with pytest.raises(BrowserActionError): files.upload({'file_path': str(path), 'file_ref': 'fabricated'}, ctx)
    with pytest.raises(BrowserActionError): files.upload({}, ctx)


def test_completed_staging_retention_integrity_and_discard(tmp_path):
    files = BrowserFiles(tmp_path / 'staging', _snapshot); ctx = call(tmp_path).context
    ticket = files.allocate(ctx, 'https://owned.test/file'); ticket['part'].write_bytes(b'Owned')
    result = files.complete(ticket, {'state': 'COMPLETE', 'received': 5, 'mime': 'text/plain'})
    assert result['digest'] == hashlib.sha256(b'Owned').hexdigest()
    assert result['retained'] and Path(result['path']).name == 'payload.bin'
    assert files.downloads(ctx.workspace)[0]['state'] == 'COMPLETE'
    assert files.downloads(tmp_path.parent) == []
    Path(result['path']).write_bytes(b'Wrong')
    assert files.downloads(ctx.workspace)[0]['state'] == 'LOST_OR_CHANGED'
    with pytest.raises(BrowserActionError): files.discard(result['downloadId'], tmp_path.parent)
    assert files.discard(result['downloadId'], ctx.workspace)['state'] == 'DISCARDED'
    assert not list(files.root.iterdir())


@pytest.mark.parametrize('state,size', [('PARTIAL', 5), ('STARTED', 5), ('UNKNOWN', 5), ('COMPLETE', 6)])
def test_incomplete_or_wrong_size_never_issues_complete_artifact(tmp_path, state, size):
    files = BrowserFiles(tmp_path / 'staging', _snapshot)
    ticket = files.allocate(call(tmp_path).context, 'https://owned.test/file'); ticket['part'].write_bytes(b'Owned')
    with pytest.raises(BrowserActionError): files.complete(ticket, {'state': state, 'received': size})
    assert files.downloads(tmp_path) == []
    assert files.discard_partial(ticket) and not ticket['folder'].exists()


def _human_adapter(adapter):
    adapter._current = lambda: None
    adapter.invalidate_context = lambda: setattr(adapter, 'epoch', adapter.epoch + 1)
    adapter.install_sensitive_capture = lambda redactor: None
    adapter.checkpoint_sensitive = lambda: None
    adapter.set_visible = lambda visible: None
    adapter.page = SimpleNamespace(wait_for_timeout=lambda _: time.sleep(0.01), is_closed=lambda: False)
    adapter.observe = lambda: {'text': 'Fresh', 'epoch': adapter.epoch}


def test_takeover_pauses_agent_and_two_resumes_derive_fresh_epochs(tmp_path):
    rt, adapter, service = setup(tmp_path, approve=True); _human_adapter(adapter)
    try:
        assert rt.execute(call(tmp_path)).status is ToolStatus.COMPLETED
        for previous in (0, 2):
            assert adapter.epoch == previous
            assert service.begin_human()['controlState'] == 'humanActive'
            assert rt.execute(call(tmp_path, 'browser_observe', {})).status is ToolStatus.DENIED
            assert service.finish_human()['controlState'] == 'agentActive'
            assert adapter.epoch == previous + 2
            assert rt.execute(call(tmp_path)).status is ToolStatus.COMPLETED
        grants = [v.grant for v in rt._issuer._issued.values()]
        assert grants[-1].request.network_intent['epoch'] == 4
    finally: rt.close()


def test_takeover_checkpoint_loss_stays_blocked_without_public_observation(tmp_path):
    rt, adapter, service = setup(tmp_path, approve=True); _human_adapter(adapter)
    observed = []
    adapter.observe = lambda: observed.append(True)
    def lost(): raise RuntimeError('private failure')
    adapter.checkpoint_sensitive = lost
    try:
        rt.execute(call(tmp_path)); service.begin_human()
        with pytest.raises(BrowserActionError, match='sensitive-input'): service.finish_human()
        assert service.human_phase == 'blocked' and not observed
        assert rt.execute(call(tmp_path)).status is ToolStatus.DENIED
    finally: rt.close()


def test_upload_requires_approval_and_rechecks_file_after_approval(tmp_path):
    path = tmp_path / 'source.txt'; path.write_text('Original')
    for approval in (None, False, True):
        rt, adapter, service = setup(tmp_path, approve=approval)
        adapter.upload_bytes = lambda ref, data, meta: adapter.calls.append(data) or {'localFileAttached': True, 'remoteOutcome': 'UNKNOWN'}
        try:
            rt.execute(call(tmp_path))
            service.files.snapshotter = _snapshot
            selected = service.files.select(path, ('session', str(tmp_path)))
            before = len(adapter.calls)
            result = rt.execute(call(tmp_path, 'browser_upload', {'ref': 'opaque', 'file_ref': selected['fileRef']}))
            assert result.status is (ToolStatus.COMPLETED if approval else ToolStatus.DENIED)
            assert len(adapter.calls) == before + int(approval is True)
            if approval: assert result.effect_state is EffectState.UNKNOWN
        finally: rt.close()
    rt, adapter, service = setup(tmp_path, approve=True, after_approval=lambda _: path.write_text('Replaced'))
    adapter.upload_bytes = lambda *args: adapter.calls.append('DISALLOWED')
    try:
        rt.execute(call(tmp_path)); service.files.snapshotter = _snapshot
        selected = service.files.select(path, ('session', str(tmp_path))); before = len(adapter.calls)
        result = rt.execute(call(tmp_path, 'browser_upload', {'ref': 'opaque', 'file_ref': selected['fileRef']}))
        assert result.status is ToolStatus.DENIED and len(adapter.calls) == before
    finally: rt.close()


def test_sensitive_capture_retirement_is_monotonic_and_not_resume_authority():
    from local_cli.infrastructure.browser.sensitive import SensitiveCapture
    callbacks = {}
    context = SimpleNamespace(expose_binding=lambda name, cb: callbacks.update(receive=cb),
                              add_init_script=lambda _: None, pages=[])
    redactor = SecretRedactor(source={}); capture = SensitiveCapture(context, redactor); capture.install()
    value = 'synthetic-fixture-value-93874'
    callbacks['receive'](None, 'draft', 'retired-world:1', value)
    page = SimpleNamespace(frames=[SimpleNamespace(evaluate=lambda *args: None)])
    with pytest.raises(BrowserActionError): capture.checkpoint(page)
    assert value not in redactor.text(value)  # Seal preserves knowledge, never grants resume.
    callbacks['receive'](None, 'commit', 'late-world:1', value + '-late')
    assert value + '-late' not in redactor.text(value + '-late')


def test_browser_control_is_one_shared_authenticated_application_contract(tmp_path, monkeypatch):
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.application.events import EventBufferConfig
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.core.contracts import new_command_id
    from local_cli.interfaces.cli_application import CliApplicationClient
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
    from local_cli.interfaces.approval_proof import approval_proof
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    from local_cli.tools.browser_tools import browser_tools
    for root in ('cli', 'jsonl-desktop'):
        rt, adapter, service = setup(tmp_path); rt.close()
        # New service owned by this Application; no frontend manages epoch.
        from local_cli.application.browser_navigation import BrowserExecutionService
        adapter = Adapter(); _human_adapter(adapter); service = BrowserExecutionService(lambda: adapter)
        provider = ScriptedProvider([{'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'browser_navigate', 'arguments': {'url': 'https://owned.test/'}}}]}, 'Ready.'])
        app = AgentSessionCoordinator(provider=provider, model='fixture', event_config=EventBufferConfig(),
             tool_factory=lambda _: browser_tools(service_factory=lambda: service))
        sid = start(app, tmp_path).session_id
        turn = submit(app, sid, 'Open the owned fixture.')
        assert app.wait_for_turn(turn.created_ids['turnId'], 5)
        denied = app.handle(ApplicationCommand(new_command_id(), CommandKind.BROWSER_CONTROL,
                           {'action': 'takeover'}, session_id=sid))
        assert not denied.accepted
        if root == 'cli':
            monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
            client = CliApplicationClient(app, sid, read=lambda _: 'n', write=lambda _: None, write_error=lambda _: None)
            assert client.command(CommandKind.BROWSER_CONTROL, {'action': 'takeover'}).accepted
            assert app.get_snapshot(sid).services['browser']['controlState'] == 'humanActive'
            assert client.command(CommandKind.BROWSER_CONTROL, {'action': 'resume'}).accepted
            client.close()
        else:
            sent = []; key = '01' * 32
            client = JsonlApplicationAdapter(app, sid, send=sent.append, host_approval_key=key)
            for action in ('takeover', 'resume'):
                command = ApplicationCommand(new_command_id(), CommandKind.BROWSER_CONTROL, {'action': action}, session_id=sid)
                request = {'id': action, 'type': 'application_command', 'command': command.to_dict()}
                client.handle(request)
                assert sent[-1]['type'] == 'error'
                request['hostBrowserProof'] = approval_proof(key, command.to_dict())
                client.handle(request)
                assert app.get_snapshot(sid).services['browser']['controlState'] == ('humanActive' if action == 'takeover' else 'agentActive')
            client.close()
        assert adapter.epoch == 2
        app.close_browser()


def test_transient_download_target_never_replaces_current_document(tmp_path):
    from local_cli.infrastructure.browser.windows_installed import InstalledPageSession
    session = InstalledPageSession(tmp_path, 'edge', tmp_path / 'edge.exe')
    closed = []
    current = SimpleNamespace(is_closed=lambda: False, close=lambda: closed.append('current'))
    handlers = {}
    popup = SimpleNamespace(url='', is_closed=lambda: False, on=lambda name, fn: handlers.setdefault(name, []).append(fn))
    session.page = current
    session._prepare_page = lambda _: None
    session.set_visible = lambda _: None
    session._popup(popup)
    assert session.page is current and closed == [] and session.epoch == 0
    # A real document popup still becomes current and invalidates old refs.
    popup.url = 'https://owned.test/next'
    handlers['framenavigated'][0](None)
    assert session.page is popup and closed == ['current'] and session.epoch == 1
    handlers['framenavigated'][0](None)
    assert session.epoch == 1
