"""Required S3 host-real tests. Only files in pytest's private temporary tree."""
from contextlib import ExitStack
from pathlib import Path
import os
import subprocess
from dataclasses import replace

import pytest

from local_cli.core.filesystem import FilesystemError
from local_cli.infrastructure.windows_filesystem import WindowsFilesystemBroker
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.core.contracts import ToolStatus, EffectState
from local_cli.tools.read_tool import ReadTool
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.edit_tool import EditTool
from local_cli.tools.glob_tool import GlobTool
from local_cli.tools.grep_tool import GrepTool
from tests.security_v12.test_s2_policy import invocation

pytestmark = pytest.mark.skipif(os.name != 'nt' or os.environ.get('NOVA_S3_HOST_REAL') != '1',
                              reason='explicit private Windows S3 host-real gate required')


def test_native_relative_read_and_atomic_replace(tmp_path):
    broker = WindowsFilesystemBroker()
    try:
        root = broker.bind_root(tmp_path)
        assert root.identity
        with ExitStack() as stack:
            parent = broker.api.chain(str(tmp_path), stack)
            identity = broker.api.atomic_write(parent, 'fixture.txt', 'native fixture\n')
            with broker.api.open(parent, 'fixture.txt', directory=False, read=True) as handle:
                assert broker.api.identity(handle) == identity
                assert broker.api.read(handle) == b'native fixture\n'
            assert [entry[0] for entry in broker.api.entries(parent)] == ['fixture.txt']
            broker.api.atomic_write(parent, 'fixture.txt', 'replaced\n')
        assert (tmp_path/'fixture.txt').read_bytes() == b'replaced\n'
        assert not list(tmp_path.glob('.nova-s3-*.tmp'))
    finally:
        broker.close()


def test_native_active_parent_cannot_be_renamed(tmp_path):
    directory = tmp_path/'pinned'; directory.mkdir()
    broker = WindowsFilesystemBroker()
    try:
        with ExitStack() as stack:
            broker.api.chain(str(directory), stack)
            with pytest.raises(OSError):
                directory.rename(tmp_path/'moved')
        directory.rename(tmp_path/'moved')
    finally:
        broker.close()


def test_native_create_parent_directory_and_hardlink_deny(tmp_path):
    broker = WindowsFilesystemBroker()
    try:
        with ExitStack() as stack:
            parent = broker.api.chain(str(tmp_path), stack)
            child = stack.enter_context(broker.api.open(parent, 'created', directory=True, create=True))
            broker.api.atomic_write(child, 'one.txt', 'private')
        os.link(tmp_path/'created/one.txt', tmp_path/'two.txt')
        with ExitStack() as stack:
            parent = broker.api.chain(str(tmp_path), stack)
            with pytest.raises(FilesystemError, match='HARDLINK'):
                broker.api.open(parent, 'two.txt', read=True, directory=False)
    finally:
        broker.close()


def runtime(workspace, *, gate=None):
    tools = [cls(cwd=workspace) for cls in (ReadTool, WriteTool, EditTool, GlobTool, GrepTool)]
    for tool in tools:
        tool.execute = lambda **_: pytest.fail('host-real legacy FS fallback')
    rt = ToolRuntime(ToolRegistry(tools), approval_gate=gate)
    rt.install_authority(workspace, 'session')
    assert rt._filesystem is not None, rt._filesystem_error
    return rt


def invoke(rt, workspace, name, args, number):
    inv = invocation(workspace, name, args)
    inv = replace(inv, operation_id=str(number), context=replace(inv.context, operation_id=str(number)))
    return rt.execute(inv)


def test_host_five_tools_read_write_edit_glob_grep_and_verifier(tmp_path):
    rt = runtime(tmp_path)
    try:
        wrote = invoke(rt, tmp_path, 'write', {'file_path': 'nested/a.py', 'content': 'value = 1\n'}, 1)
        assert wrote.status is ToolStatus.COMPLETED, wrote
        assert wrote.effect_state is EffectState.APPLIED
        read = invoke(rt, tmp_path, 'read', {'file_path': 'nested/a.py'}, 2)
        assert read.status is ToolStatus.COMPLETED and 'value = 1' in read.legacy_text
        edited = invoke(rt, tmp_path, 'edit', {'file_path': 'nested/a.py', 'old_text': 'value = 1', 'new_text': 'value = 2'}, 3)
        assert edited.status is ToolStatus.COMPLETED, edited
        glob = invoke(rt, tmp_path, 'glob', {'pattern': '**/*.py'}, 4)
        assert glob.status is ToolStatus.COMPLETED and 'nested\\a.py' in glob.legacy_text, glob
        grep = invoke(rt, tmp_path, 'grep', {'pattern': 'value', 'include': '*.py'}, 5)
        assert grep.status is ToolStatus.COMPLETED and 'a.py:1:value = 2' in grep.legacy_text, grep
        bad = invoke(rt, tmp_path, 'write', {'file_path': 'bad.py', 'content': 'if (\n'}, 6)
        assert bad.status is ToolStatus.COMPLETED and 'syntax error' in bad.metadata['verificationWarning']
        assert (tmp_path/'nested/a.py').read_text() == 'value = 2\n'
        assert not list(tmp_path.rglob('.nova-s3-*.tmp'))
    finally:
        rt.close()


@pytest.mark.parametrize('name,args', [
    ('read', {'file_path': '../outside/secret.txt'}),
    ('write', {'file_path': '../outside/secret.txt', 'content': 'changed'}),
    ('edit', {'file_path': '../outside/secret.txt', 'old_text': 'secret', 'new_text': 'changed'}),
    ('glob', {'pattern': '*', 'path': '../outside'}),
    ('grep', {'pattern': 'secret', 'path': '../outside'}),
])
def test_host_traversal_never_reads_or_changes_external_fixture(tmp_path, name, args):
    workspace = tmp_path/'workspace'; workspace.mkdir()
    outside = tmp_path/'outside'; outside.mkdir(); target = outside/'secret.txt'; target.write_text('secret')
    rt = runtime(workspace)
    try:
        result = invoke(rt, workspace, name, args, 1)
        assert result.status is ToolStatus.DENIED
        assert 'secret' not in result.legacy_text
        assert target.read_text() == 'secret'
    finally:
        rt.close()


@pytest.mark.parametrize('bad', ['absolute', 'unc', 'ads', 'device', 'short_alias', 'trailing_dot'])
def test_host_unsupported_names_and_absolute_external(tmp_path, bad):
    workspace = tmp_path/'workspace'; workspace.mkdir()
    outside = tmp_path/'outside.txt'; outside.write_text('external sentinel')
    raw = {'absolute': str(outside), 'unc': '\\\\localhost\\C$\\outside.txt',
           'ads': 'normal.txt:secret', 'device': '\\\\?\\C:\\outside.txt',
           'short_alias': 'SHORT~1.TXT', 'trailing_dot': 'normal.txt.'}[bad]
    rt = runtime(workspace)
    try:
        assert invoke(rt, workspace, 'read', {'file_path': raw}, 1).status is ToolStatus.DENIED
        assert outside.read_text() == 'external sentinel'
    finally:
        rt.close()


def test_host_case_alias_is_same_object_and_read_does_not_grant_write(tmp_path):
    (tmp_path/'Report.txt').write_text('inside')
    rt = runtime(tmp_path)
    try:
        result = invoke(rt, tmp_path, 'read', {'file_path': 'REPORT.TXT'}, 1)
        assert result.status is ToolStatus.COMPLETED and 'inside' in result.legacy_text
        old = rt._issuer.ceiling
        rt._issuer.replace_ceiling(replace(old, revision=2, capabilities=tuple(
            c for c in old.capabilities if c.permission.name != 'filesystem.write')))
        denied = invoke(rt, tmp_path, 'write', {'file_path': 'Report.txt', 'content': 'wrong'}, 2)
        assert denied.status is ToolStatus.DENIED and (tmp_path/'Report.txt').read_text() == 'inside'
    finally:
        rt.close()


@pytest.mark.parametrize('kind', ['junction', 'directory_symlink', 'file_symlink'])
def test_host_link_to_external_fixture_is_denied_for_all_tools(tmp_path, kind):
    workspace = tmp_path/'workspace'; workspace.mkdir()
    outside = tmp_path/'outside'; outside.mkdir(); (outside/'secret.txt').write_text('external sentinel')
    link = workspace/'link'
    if kind == 'junction':
        made = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(outside)],
                cwd=tmp_path, capture_output=True, timeout=10)
        assert made.returncode == 0, 'junction fixture creation unavailable'
    else:
        target = outside if kind == 'directory_symlink' else outside/'secret.txt'
        try:
            os.symlink(target, link, target_is_directory=kind == 'directory_symlink')
        except OSError as exc:
            pytest.fail(f'Required symlink fixture unavailable (Windows error {exc.winerror}); gate not certified')
    rt = runtime(workspace)
    try:
        leaf = 'link' if kind == 'file_symlink' else 'link/secret.txt'
        for number, (name, args) in enumerate([
            ('read', {'file_path': leaf}), ('write', {'file_path': leaf, 'content': 'wrong'}),
            ('edit', {'file_path': leaf, 'old_text': 'external', 'new_text': 'wrong'}),
            ('glob', {'pattern': '**/*'}), ('grep', {'pattern': 'external'}),
        ]):
            result = invoke(rt, workspace, name, args, number)
            assert result.status is ToolStatus.DENIED, (kind, name, result)
            assert 'external sentinel' not in result.legacy_text
        assert (outside/'secret.txt').read_text() == 'external sentinel'
    finally:
        rt.close()


def test_host_root_replaced_between_requests_is_rejected(tmp_path):
    workspace = tmp_path/'workspace'; workspace.mkdir(); (workspace/'a.txt').write_text('old')
    rt = runtime(workspace)
    try:
        assert invoke(rt, workspace, 'read', {'file_path': 'a.txt'}, 1).status is ToolStatus.COMPLETED
        workspace.rename(tmp_path/'moved')
        workspace.mkdir(); (workspace/'a.txt').write_text('replacement sentinel')
        result = invoke(rt, workspace, 'read', {'file_path': 'a.txt'}, 2)
        assert result.status is ToolStatus.DENIED and result.metadata['securityErrorCode'] == 'FILESYSTEM_RESOURCE_CHANGED'
        assert 'replacement sentinel' not in result.legacy_text
    finally:
        rt.close()


def test_host_deterministic_toctou_parent_cannot_redirect_write(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'; workspace.mkdir(); parent = workspace/'pinned'; parent.mkdir()
    outside = tmp_path/'outside'; outside.mkdir(); (outside/'a.txt').write_text('external sentinel')
    rt = runtime(workspace)
    api = rt._filesystem.broker.api
    original = api.atomic_write
    attempts = []
    def race(handle, name, content, guard):
        try:
            parent.rename(workspace/'moved')
            attempts.append('unexpected rename')
        except OSError:
            attempts.append('rename denied')
        return original(handle, name, content, guard)
    monkeypatch.setattr(api, 'atomic_write', race)
    try:
        result = invoke(rt, workspace, 'write', {'file_path': 'pinned/a.txt', 'content': 'authorized'}, 1)
        assert result.status is ToolStatus.COMPLETED, result
        assert attempts == ['rename denied']
        assert (outside/'a.txt').read_text() == 'external sentinel'
        assert (parent/'a.txt').read_text() == 'authorized'
    finally:
        rt.close()


def test_host_external_root_one_shot_requires_exact_human_approval(tmp_path):
    from threading import Thread, Event
    from local_cli.application.interactions import ApprovalGate
    from tests.security_v12.test_s2_runtime import response
    workspace = tmp_path/'workspace'; workspace.mkdir()
    outside = tmp_path/'outside'; outside.mkdir()
    target = outside/'secret.txt'; target.write_text('external authorized fixture')
    ready = Event()
    gate = ApprovalGate(on_required=lambda _: ready.set())
    actor = gate.register_actor('desktop_host', lambda: True)
    rt = runtime(workspace, gate=gate)
    inv = invocation(workspace, 'read', {'file_path': str(target)})
    results = []
    try:
        rt.authorize_external_filesystem(inv, outside, ['filesystem.read'])
        worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
        worker.start(); assert ready.wait(2)
        request = gate.pending()[0]
        assert not results and not rt._issuer._issued
        gate.resolve(**response(request, actor)); worker.join(2)
        assert results and results[0].status is ToolStatus.COMPLETED, results
        assert 'external authorized fixture' in results[0].legacy_text
        assert results[0].metadata['requestDigest'] == request.request_digest
        assert rt.execute(inv) is results[0]  # correlation replay, no new I/O
        assert invoke(rt, workspace, 'read', {'file_path': str(target)}, 2).status is ToolStatus.DENIED
        assert invoke(rt, workspace, 'write', {'file_path': str(target), 'content': 'wrong'}, 3).status is ToolStatus.DENIED
        assert target.read_text() == 'external authorized fixture'
    finally:
        inv.context.cancellation_token.request()
        rt.close()


@pytest.mark.parametrize('nested', [False, True])
def test_host_cancel_after_temp_flush_does_not_replace_and_cleans_temp(tmp_path, monkeypatch, nested):
    rt = runtime(tmp_path)
    path = tmp_path/'nested/a.txt' if nested else tmp_path/'a.txt'
    if not nested:
        path.write_text('original fixture')
    inv = invocation(tmp_path, 'write', {'file_path': str(path), 'content': 'cancelled content'})
    api = rt._filesystem.broker.api
    flush = api.kernel.FlushFileBuffers
    def cancel_after_flush(handle):
        result = flush(handle)
        inv.context.cancellation_token.request()
        return result
    monkeypatch.setattr(api.kernel, 'FlushFileBuffers', cancel_after_flush)
    try:
        result = rt.execute(inv)
        assert result.status is ToolStatus.CANCELLED, result
        assert result.effect_state is (EffectState.PARTIAL if nested else EffectState.NONE)
        assert (not path.exists()) if nested else path.read_text() == 'original fixture'
        assert not list(tmp_path.rglob('.nova-s3-*.tmp'))
        assert rt.execute(inv) is result
    finally:
        rt.close()


def test_host_leaf_entry_replace_is_atomic_not_external_link_following(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'; workspace.mkdir()
    outside = tmp_path/'outside'; outside.mkdir(); (outside/'a.txt').write_text('external sentinel')
    target = workspace/'a.txt'; target.write_text('original')
    rt = runtime(workspace)
    api = rt._filesystem.broker.api
    write = api.atomic_write
    attempts = []
    def replace_leaf(parent, name, content, guard):
        # The original read guard is deliberately released for atomic replace.
        # Try redirecting the LEAF to an external directory at that exact point.
        target.unlink()
        made = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(target), str(outside)],
                              cwd=tmp_path, capture_output=True, timeout=10)
        assert made.returncode == 0
        attempts.append('leaf replaced with junction')
        return write(parent, name, content, guard)
    monkeypatch.setattr(api, 'atomic_write', replace_leaf)
    try:
        result = invoke(rt, workspace, 'write', {'file_path': 'a.txt', 'content': 'authorized'}, 1)
        # Replacing a directory entry with a file fails on NTFS, with no follow.
        assert result.status is ToolStatus.FAILED and result.effect_state is EffectState.NONE, result
        assert attempts == ['leaf replaced with junction']
        assert (outside/'a.txt').read_text() == 'external sentinel'
        assert not list(workspace.glob('.nova-s3-*.tmp'))
    finally:
        rt.close()
