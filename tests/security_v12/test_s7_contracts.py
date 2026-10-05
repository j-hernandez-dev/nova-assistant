"""S7 independent contracts. Ephemeral port is a fixture, not a policy choice."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import pytest

from local_cli.core.security_audit import AuditKind, SecurityAuditRecord, SecurityAuditError
from local_cli.application.security_audit import SecurityAuditService, reconstruct_operation, safe_url
from local_cli.application.secrets import SecretRedactor
from tests.security_v12.test_s2_policy import invocation


class FixtureAuditPort:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)

    def read_operation(self, session_id, operation_id):
        return tuple(r for r in self.records if r.session_id == session_id and r.operation_id == operation_id)

    def flush(self):
        pass

    def close(self):
        pass

    def validate_workspace(self, workspace):
        pass


def entry(**changes):
    return replace(SecurityAuditRecord('record', 'stream', 1,
        datetime.now(timezone.utc).isoformat(), AuditKind.REQUEST,
        'session', 'operation', 'bash', 'agent_runtime', {'cwd': 'fixture'}), **changes)


def test_record_is_deep_immutable_and_serializable():
    raw = {'permissions': [{'permission': 'filesystem.read', 'resource': 'fixture'}]}
    record = entry(data=raw)
    raw['permissions'][0]['resource'] = 'changed'
    assert record.data['permissions'][0]['resource'] == 'fixture'
    with pytest.raises(TypeError):
        record.data['permissions'][0]['resource'] = 'changed'
    assert json.loads(json.dumps(record.to_dict()))['schemaVersion'] == 1


@pytest.mark.parametrize('changes', [
    {'schema_version': 2}, {'audit_sequence': 0}, {'audit_sequence': True},
    {'origin': 'renderer_authority'}, {'timestamp': 'bad'},
    {'timestamp': '2026-10-04T10:00:00'}, {'session_id': ''},
    {'kind': 'request'}, {'data': {'bearerGrant': 'forbidden'}},
    {'data': {'environment': {'TOKEN': 'forbidden'}}},
    {'data': {'resource': object()}}, {'data': {'resource': b'bytes'}},
    {'data': {'permissions': [{'grantRequest': {'environment': 'forbidden'}}]}},
    {'data': {'hops': [{'credential': 'forbidden'}]}},
])
def test_invalid_records_rejected(changes):
    with pytest.raises(SecurityAuditError):
        entry(**changes)


def test_record_size_bounded_before_adapter():
    with pytest.raises(SecurityAuditError, match='AUDIT_RECORD_TOO_LARGE'):
        entry(data={'command': 'x' * 65536})


def test_versioned_codec_roundtrip_and_unknown_fields_rejected():
    record = entry()
    assert SecurityAuditRecord.from_dict(record.to_dict()) == record
    for value in ({**record.to_dict(), 'bearerGrant': 'forbidden'},
                  {**record.to_dict(), 'schemaVersion': 2}):
        with pytest.raises(SecurityAuditError):
            SecurityAuditRecord.from_dict(value)


def test_service_redacts_before_port_and_retains_no_output_or_environment(tmp_path):
    port = FixtureAuditPort()
    audit = SecurityAuditService(port, redactor=SecretRedactor(source={'API_KEY': 'dummy-provider-secret-123'}))
    inv = invocation(tmp_path, arguments={'command': 'echo dummy-provider-secret-123'})
    assert audit.request(inv)
    raw = json.dumps(port.records[0].to_dict())
    assert 'dummy-provider-secret-123' not in raw
    assert '[REDACTED]' in raw
    assert 'environment' not in port.records[0].data
    assert 'stdout' not in port.records[0].data


def test_failed_delivery_observable_no_private_exception_reemitted(tmp_path):
    class Broken:
        def append(self, _):
            raise RuntimeError('dummy-adapter-private-value')
    audit = SecurityAuditService(Broken(), redactor=SecretRedactor(source={}))
    assert audit.request(invocation(tmp_path)) is False
    assert audit.last_error == 'SECURITY_AUDIT_DELIVERY_FAILED'
    assert audit.delivery_failures == 1


def test_invalid_payload_is_delivery_failure_not_sent_to_adapter(tmp_path):
    port = FixtureAuditPort()
    audit = SecurityAuditService(port, redactor=SecretRedactor(source={}))
    assert audit.record(invocation(tmp_path), AuditKind.REQUEST, {'grant': object()}) is False
    assert not port.records


def test_missing_terminal_is_unknown_not_success():
    result = reconstruct_operation([entry()])
    assert not result['completeObservedLifecycle']
    assert result['outcome'] == 'not_observed'
    assert result['effectState'] == 'unknown'


def test_reconstruction_sorts_different_sequence_from_event_journal():
    requested = entry()
    terminal = entry(record_id='terminal', audit_sequence=2, kind=AuditKind.TERMINAL,
        data={'outcome': 'outcome_unknown', 'effectState': 'unknown'})
    result = reconstruct_operation([terminal, requested])
    assert result['records'][0]['kind'] == 'request'
    assert result['completeObservedLifecycle']
    assert result['outcome'] == 'outcome_unknown'
    assert result['processInternalEffectsKnown'] is False


def test_subject_and_terminal_conflicts_not_silently_merged():
    with pytest.raises(ValueError, match='AUDIT_SUBJECT_CONFLICT'):
        reconstruct_operation([entry(), entry(session_id='other')])
    terminal = entry(kind=AuditKind.TERMINAL, data={'outcome': 'completed', 'effectState': 'none'})
    with pytest.raises(ValueError, match='AUDIT_TERMINAL_CONFLICT'):
        reconstruct_operation([terminal, replace(terminal, record_id='second')])


@pytest.mark.parametrize('url,expected', [
    ('https://user:password@example.com/a?token=secret#secret', 'https://example.com/a'),
    ('https://[2606:4700::1111]:443/a?secret=value', 'https://[2606:4700::1111]:443/a'),
    (None, None), ('https://example.com:bad/a', None),
])
def test_url_privacy(url, expected):
    assert safe_url(url) == expected
