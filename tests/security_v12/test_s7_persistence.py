"""OD-05 real local storage fixtures; no user-state writes or external service."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit, OWNER
from local_cli.core.security_audit import AuditKind, SecurityAuditError
from local_cli.application.security_audit import reconstruct_operation, SecurityAuditService
from local_cli.application.secrets import SecretRedactor
from tests.security_v12.test_s7_contracts import entry
from tests.security_v12.test_s2_runtime import runtime
from tests.security_v12.test_s2_policy import invocation
from local_cli.core.contracts import ToolStatus, EffectState, EventKind, ToolResult


def test_defaults_and_workspace_exclusion(tmp_path):
    port = JsonlSecurityAudit(tmp_path/'state')
    assert (port.segment_bytes, port.retention_bytes, port.retention_days) == (10*1024**2, 100*1024**2, 30)
    forbidden = JsonlSecurityAudit(tmp_path/'workspace/state', workspace=tmp_path/'workspace')
    with pytest.raises(SecurityAuditError):
        forbidden.append(entry())
    assert not (tmp_path/'workspace').exists()


def test_real_jsonl_roundtrip_and_terminal_reconstruction(tmp_path):
    port = JsonlSecurityAudit(tmp_path/'state')
    port.append(entry()); port.flush()
    port.append(entry(record_id='end', audit_sequence=2, kind=AuditKind.TERMINAL,
        data={'outcome': 'completed', 'effectState': 'unknown'}))
    port.flush(); port.close()
    assert not list(port.directory.glob('*.active.jsonl'))
    reopened = JsonlSecurityAudit(port.directory)
    rows = reopened.read_operation('session', 'operation')
    assert len(rows) == 2
    assert reconstruct_operation(rows)['completeObservedLifecycle']
    assert not reconstruct_operation(rows)['processInternalEffectsKnown']
    reopened.close()


def test_fsync_at_barriers_close_rotation_not_every_internal_append(tmp_path, monkeypatch):
    real = os.fsync
    calls = []
    monkeypatch.setattr(os, 'fsync', lambda fd: (calls.append(fd), real(fd))[1])
    port = JsonlSecurityAudit(tmp_path/'state', segment_bytes=2048)
    port.append(entry())
    initial = len(calls)
    port.append(entry(record_id='other', audit_sequence=2))
    assert len(calls) == initial
    port.flush(); assert len(calls) == initial+1
    for number in range(3, 12):
        port.append(entry(record_id=str(number), audit_sequence=number))
    assert list(port.directory.glob('*.closed.jsonl'))
    assert all(p.stat().st_size <= 2048 for p in port.directory.glob('*.jsonl'))
    before = len(calls); port.close(); assert len(calls) > before


@pytest.mark.parametrize('reason', ['bytes', 'age'])
def test_retention_only_closed_owned_segments_no_historical_manual_files(tmp_path, reason):
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    port = JsonlSecurityAudit(tmp_path/'state', segment_bytes=2048,
        retention_bytes=4096, clock=lambda: now)
    port.append(entry()); port.flush()
    historical = port.directory/'manual-evidence.jsonl'
    historical.write_bytes(b'WinError 1314 historical evidence\n')
    fake = port.directory/('nova-audit-'+'f'*32+'.closed.jsonl')
    fake.write_bytes(b'{"owner":"other"}\n')
    active = port._active
    if reason == 'age':
        now += timedelta(days=31)
        port.append(entry(record_id='still-active', audit_sequence=2))
        assert active.exists()  # Age never purges an active file.
    for number in range(3, 35):
        port.append(entry(record_id=str(number), audit_sequence=number))
    assert historical.read_bytes() == b'WinError 1314 historical evidence\n'
    assert fake.read_bytes() == b'{"owner":"other"}\n'
    assert port._active.exists()
    own = port._segments()
    assert sum(s[3] for s in own) <= 4096
    assert any(g['code'] == 'AUDIT_RETENTION_GAP' for g in port.gaps)
    port.close()
    reopened = JsonlSecurityAudit(port.directory)
    reopened.read_operation('session','operation')
    assert any(g['code'] == 'AUDIT_SEQUENCE_GAP' for g in reopened.gaps)
    reopened.close()


def test_live_other_writer_active_segment_is_never_sealed_or_purged(tmp_path):
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    first = JsonlSecurityAudit(tmp_path/'state', segment_bytes=2048, retention_bytes=2048, clock=lambda: now)
    first.append(entry()); first.flush(); active = first._active
    second = JsonlSecurityAudit(first.directory, segment_bytes=2048, retention_bytes=2048,
                                clock=lambda: now+timedelta(days=31))
    try:
        failed = False
        for number in range(2, 20):
            try:
                second.append(entry(record_id=str(number), audit_stream_id='other', audit_sequence=number))
            except SecurityAuditError:
                failed = True
                break
        assert failed  # Full of live active files: fail closed, never purge them.
        assert sum(s[3] for s in first._segments()) <= 2048
        assert active.exists()
        assert active.read_bytes().endswith(b'\n')
    finally:
        second.close(); first.close()


def test_actual_crash_reopen_valid_complete_rows_no_fabricated_terminal(tmp_path):
    state = tmp_path/'state'
    code = """import os,sys
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from tests.security_v12.test_s7_contracts import entry
port=JsonlSecurityAudit(sys.argv[1])
port.append(entry()); port.flush()
with port._active.open('ab') as f:
 f.write(b'{"unfinished":"dummy-private-tail"'); f.flush(); os.fsync(f.fileno())
os._exit(37)
"""
    result = subprocess.run([sys.executable, '-B', '-c', code, str(state)], timeout=15, capture_output=True)
    assert result.returncode == 37, result.stderr.decode(errors='replace')
    raw = next(state.glob('*.active.jsonl')).read_bytes()
    reopened = JsonlSecurityAudit(state)
    rows = reopened.read_operation('session', 'operation')
    assert len(rows) == 1
    assert reconstruct_operation(rows)['outcome'] == 'not_observed'
    assert reconstruct_operation(rows)['effectState'] == 'unknown'
    assert next(state.glob('*.closed.jsonl')).read_bytes() == raw
    assert {'AUDIT_UNCLEAN_SEGMENT_RECOVERED', 'AUDIT_INCOMPLETE_OR_OVERSIZED_ROW',
            'AUDIT_TERMINAL_NOT_OBSERVED'} <= {g['code'] for g in reopened.gaps}
    assert 'dummy-private-tail' not in json.dumps(reopened.gaps)
    reopened.append(entry(record_id='fresh', audit_stream_id='fresh'))
    reopened.flush(); reopened.close()


def test_corrupt_complete_rows_skipped_raw_bytes_preserved(tmp_path):
    port = JsonlSecurityAudit(tmp_path/'state')
    port.append(entry()); port.close()
    path = next(port.directory.glob('*.closed.jsonl'))
    with path.open('ab') as stream:
        stream.write(b'{"schemaVersion":999,"secret":"dummy-corrupt-value"}\nnot-json\n')
        stream.write(json.dumps(entry(record_id='valid', audit_sequence=4).to_dict()).encode()+b'\n')
    before = path.read_bytes()
    reopened = JsonlSecurityAudit(port.directory)
    assert len(reopened.read_operation('session','operation')) == 2
    assert path.read_bytes() == before
    assert 'dummy-corrupt-value' not in json.dumps(reopened.gaps)
    assert {'AUDIT_INVALID_ROW','AUDIT_SEQUENCE_GAP'} <= {g['code'] for g in reopened.gaps}
    reopened.close()


@pytest.mark.parametrize('phase', ['append', 'before_sync', 'terminal_sync'])
def test_runtime_fail_closed_before_effect_preserves_observation_after(tmp_path, phase):
    disk = JsonlSecurityAudit(tmp_path/'state')
    class FailingPort:
        flushes = 0
        def append(self, row):
            if phase == 'append':
                raise OSError('dummy-private-error')
            disk.append(row)
        def flush(self):
            self.flushes += 1
            if (phase == 'before_sync' and self.flushes == 1 or
                    phase == 'terminal_sync' and self.flushes == 2):
                raise OSError('dummy-private-error')
            disk.flush()
    audit = SecurityAuditService(FailingPort(), redactor=SecretRedactor(source={}))
    rt, exe, events = runtime(tmp_path, security_audit=audit)
    inv = invocation(tmp_path)
    try:
        result = rt.execute(inv)
        if phase == 'terminal_sync':
            exe.run.assert_called_once()
            assert result.status is ToolStatus.COMPLETED
            assert result.effect_state is EffectState.UNKNOWN  # S4 observed shell result.
        else:
            exe.run.assert_not_called()
            assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
            assert result.metadata['securityErrorCode'] == 'SECURITY_AUDIT_PRE_EFFECT_FAILED'
        assert result.metadata['securityAudit']['gap']
        assert result.metadata['securityAudit']['retryAllowed'] is False
        assert 'dummy-private-error' not in json.dumps(dict(result.metadata))
        assert rt.execute(inv) is result
        assert sum(e[0] in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED) for e in events) == 1
    finally:
        rt.close(); disk.close()


def test_post_effect_audit_failure_preserves_applied_fs_result(tmp_path):
    class Port:
        def append(self, row):
            if row.kind is AuditKind.TERMINAL:
                raise OSError()
        def flush(self):
            pass
    audit = SecurityAuditService(Port(), redactor=SecretRedactor(source={}))
    inv = invocation(tmp_path)
    result = ToolResult(ToolStatus.COMPLETED, EffectState.APPLIED, legacy_text='done', exit_code=0)
    assert not audit.terminal(inv, result)
    actual = audit.annotate_result(inv, result)
    assert actual.status is result.status and actual.effect_state is EffectState.APPLIED
    assert actual.exit_code == 0 and actual.metadata['securityAudit']['gap']


def test_actual_fsync_failure_latches_adapter_no_silent_recovery(tmp_path, monkeypatch):
    disk = JsonlSecurityAudit(tmp_path/'state')
    disk.append(entry())
    real = os.fsync
    monkeypatch.setattr(os, 'fsync', lambda _: (_ for _ in ()).throw(OSError('dummy-error')))
    with pytest.raises(SecurityAuditError, match='SYNC_FAILED'):
        disk.flush()
    monkeypatch.setattr(os, 'fsync', real)
    with pytest.raises(SecurityAuditError, match='UNAVAILABLE'):
        disk.append(entry(record_id='later', audit_sequence=2))
    disk.close()


def test_durable_redaction_before_real_file(tmp_path):
    work = tmp_path/'work'; work.mkdir()
    disk = JsonlSecurityAudit(tmp_path/'state', workspace=work)
    audit = SecurityAuditService(disk, redactor=SecretRedactor(source={'API_KEY':'dummy-provider-123'}))
    inv = invocation(work, arguments={'command':'echo dummy-provider-123'})
    audit.request(inv); audit.before_effect(inv)
    disk.close()
    raw = b''.join(p.read_bytes() for p in disk.directory.glob('*.jsonl'))
    assert b'dummy-provider-123' not in raw and b'[REDACTED]' in raw


def test_rebound_workspace_cannot_absorb_audit_directory(tmp_path):
    work = tmp_path/'work'; work.mkdir()
    disk = JsonlSecurityAudit(tmp_path/'state', workspace=work)
    audit = SecurityAuditService(disk,redactor=SecretRedactor(source={}))
    inv = invocation(work)
    inv = replace(inv,context=replace(inv.context,workspace=tmp_path))
    audit.request(inv)
    try:
        with pytest.raises(SecurityAuditError,match='PRE_EFFECT_FAILED'):
            audit.before_effect(inv)
        assert AuditKind.DISPATCH not in [r.kind for r in disk.read_operation('session','operation')]
    finally:
        disk.close()


def test_unowned_hardlinked_segment_never_purged(tmp_path):
    source = tmp_path/'manual.jsonl'; source.write_bytes(b'manual evidence')
    state = tmp_path/'state'; state.mkdir()
    target = state/('nova-audit-'+'a'*32+'.closed.jsonl')
    os.link(source,target)
    port = JsonlSecurityAudit(state,segment_bytes=1024,retention_bytes=1024)
    try:
        port.append(entry()); port.flush()
        assert source.read_bytes() == target.read_bytes() == b'manual evidence'
        assert any(g['code'] == 'AUDIT_UNSAFE_SEGMENT_IGNORED' for g in port.gaps)
    finally:
        port.close()
