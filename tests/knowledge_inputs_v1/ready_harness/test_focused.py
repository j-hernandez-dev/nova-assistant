"""Only focal R1/R2 infrastructure tests; no V2 cases or model generations."""
import json

import pytest

from local_cli.core.contracts import EventKind, EffectState, ToolResult, ToolStatus
from local_cli.core.knowledge import KnowledgeError, KnowledgeScopeKind
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.test_k6_passive_web import rt, search_inv, search_body
from .focused import HostSnapshot, IsolationFixture, capture_runtime, observe_tool


@pytest.fixture(autouse=True)
def deny_model_and_network(monkeypatch):
    import socket
    def blocked(*args, **kwargs):
        pytest.fail('FOCUSED_TEST_EXTERNAL_NETWORK_OR_MODEL_FORBIDDEN')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)


def save(tmp_path, data):
    (tmp_path / 'focused_observation.json').write_text(json.dumps(data, indent=2), encoding='utf-8')


def empty():
    return HostSnapshot({}, {}, {})


def test_r1_disabled_search_real_request_rejected_without_execution_or_authority(tmp_path):
    runtime, port, events, _ = rt(tmp_path, search=True, enabled=False)
    inv = search_inv(tmp_path)
    try:
        before = capture_runtime(runtime, tmp_path, inv.operation_id)
        result = runtime.execute(inv)
        after = capture_runtime(runtime, tmp_path, inv.operation_id)
        observation = observe_tool(inv, result, events, before, after)
        assert observation['tool_request']['arguments'] == dict(inv.arguments)
        assert observation['tool_rejected'] is True
        assert observation['tool_executed'] is False
        assert observation['tool_result']['metadata']['securityErrorCode'] == 'REMOTE_SEARCH_DISABLED'
        assert observation['observable_effects'] == []
        assert observation['document_derived_authority'] == 'NOT_OBSERVED'
        assert port.resolutions == []
        assert port.gets == []
        assert runtime._issuer._issued == {}
        save(tmp_path, observation)
    finally:
        runtime.close()


def test_r1_passive_executed_tool_is_not_document_authority(tmp_path):
    runtime, port, events, _ = rt(tmp_path, search_body(), 'application/json', search=True)
    inv = search_inv(tmp_path)
    try:
        before = capture_runtime(runtime, tmp_path, inv.operation_id)
        result = runtime.execute(inv)
        after = capture_runtime(runtime, tmp_path, inv.operation_id)
        observation = observe_tool(inv, result, events, before, after)
        assert observation['tool_rejected'] is False
        assert observation['tool_executed'] is True
        assert observation['tool_result']['status'] == 'completed'
        assert observation['tool_result']['effectState'] == 'none'
        assert len(port.gets) == 1  # Scripted HTTP port, not a socket.
        assert observation['observable_effects'] == []
        assert len(observation['authority_changes']) == 1
        assert observation['authority_changes'][0]['after']['basis'] == 'HOST'
        assert observation['document_derived_authority'] == 'NOT_OBSERVED'
        save(tmp_path, observation)
    finally:
        runtime.close()


def synthetic(tmp_path, before, after):
    inv = search_inv(tmp_path)
    result = ToolResult(ToolStatus.COMPLETED, EffectState.APPLIED)
    events = [(EventKind.TOOL_REQUESTED, inv, None), (EventKind.TOOL_STARTED, inv, None),
              (EventKind.TOOL_COMPLETED, inv, result)]
    return observe_tool(inv, result, events, before, after)


def test_r1_observable_file_and_memory_effects_are_separate(tmp_path):
    observation = synthetic(tmp_path, empty(), HostSnapshot({'a': 'new-sha'}, {'m': 'new-sha'}, {}))
    assert [e['domain'] for e in observation['observable_effects']] == ['FILES', 'MEMORY']
    assert observation['document_derived_authority'] == 'NOT_OBSERVED'
    save(tmp_path, observation)


def test_r1_independently_observed_document_authority_is_not_hidden(tmp_path):
    record = dict(origin='HOST_AUDIT', basis='DOCUMENT', source_id='synthetic-source',
                  revision_id='synthetic-revision', audit_ref='synthetic-host-audit-record-1')
    observation = synthetic(tmp_path, empty(), HostSnapshot({}, {}, {'grant': record}))
    assert observation['document_derived_authority'] == 'OBSERVED'
    assert observation['document_authority_evidence'] == [dict(key='grant', **record)]
    save(tmp_path, observation)


def test_r1_unattributed_authority_change_is_unresolved_not_safe(tmp_path):
    observation = synthetic(tmp_path, empty(), HostSnapshot({}, {}, {'policy': {'changed': True}}))
    assert observation['document_derived_authority'] == 'UNRESOLVED'
    assert observation['unresolved_authority_provenance'] == ['policy']
    save(tmp_path, observation)


def test_r1_missing_terminal_or_cross_operation_is_rejected(tmp_path):
    inv = search_inv(tmp_path)
    other = search_inv(tmp_path)
    result = ToolResult(ToolStatus.DENIED, EffectState.NONE)
    with pytest.raises(ValueError, match='^TOOL_REQUEST_EVIDENCE_MISSING$'):
        observe_tool(inv, result, [(EventKind.TOOL_REQUESTED, other, None)], empty(), empty())
    with pytest.raises(ValueError, match='^TOOL_TERMINAL_EVIDENCE_MISMATCH$'):
        observe_tool(inv, result, [(EventKind.TOOL_REQUESTED, inv, None)], empty(), empty())


def bind_three(fixture):
    fixture.bind('target', 'workspace-a', 'ses_focal_target')
    fixture.bind('peer', 'workspace-a', 'ses_focal_peer')
    fixture.bind('foreign', 'workspace-b', 'ses_focal_foreign')
    assert len({id(s.store) for s in fixture.services.values()}) == 1


def test_r2_session_separation_with_one_live_owner(tmp_path):
    with IsolationFixture(tmp_path / 'fixture') as fixture:
        bind_three(fixture)
        path = tmp_path / 'session.txt'
        path.write_text('Focal session marker SESSION_CEDAR_71.', encoding='utf-8')
        source = fixture.import_text('peer', path, KnowledgeScopeKind.SESSION)
        peer = fixture.retrieve('peer', 'SESSION_CEDAR_71')
        target = fixture.retrieve('target', 'SESSION_CEDAR_71')
        foreign = fixture.retrieve('foreign', 'SESSION_CEDAR_71')
        assert [c['source_id'] for c in peer] == [source.source_id]
        assert target == []
        assert foreign == []
        assert len(fixture.visible('peer')) == 1  # Still live; no close/recovery removed it.
        save(tmp_path, dict(peer=peer, target=target, foreign=foreign,
                            source=source.to_dict(), events=fixture.events, owners=1))


def test_r2_workspace_sharing_and_foreign_separation_with_one_live_owner(tmp_path):
    with IsolationFixture(tmp_path / 'fixture') as fixture:
        bind_three(fixture)
        path = tmp_path / 'workspace.txt'
        path.write_text('Focal workspace marker WORKSPACE_AMBER_82.', encoding='utf-8')
        source = fixture.import_text('peer', path, KnowledgeScopeKind.WORKSPACE)
        peer = fixture.retrieve('peer', 'WORKSPACE_AMBER_82')
        target = fixture.retrieve('target', 'WORKSPACE_AMBER_82')
        foreign = fixture.retrieve('foreign', 'WORKSPACE_AMBER_82')
        assert [c['source_id'] for c in peer] == [source.source_id]
        assert target == peer
        assert foreign == []
        assert fixture.services['peer'].access.session_id != fixture.services['target'].access.session_id
        save(tmp_path, dict(peer=peer, target=target, foreign=foreign,
                            source=source.to_dict(), events=fixture.events, owners=1))


def test_r2_foreign_source_stays_live_but_invisible_to_target(tmp_path):
    with IsolationFixture(tmp_path / 'fixture') as fixture:
        bind_three(fixture)
        path = tmp_path / 'foreign.txt'
        path.write_text('Focal foreign marker FOREIGN_SILVER_93.', encoding='utf-8')
        source = fixture.import_text('foreign', path, KnowledgeScopeKind.WORKSPACE)
        foreign = fixture.retrieve('foreign', 'FOREIGN_SILVER_93')
        target = fixture.retrieve('target', 'FOREIGN_SILVER_93')
        assert [c['source_id'] for c in foreign] == [source.source_id]
        assert target == []
        assert len(fixture.visible('foreign')) == 1
        save(tmp_path, dict(foreign=foreign, target=target, source=source.to_dict(), events=fixture.events, owners=1))


def test_r2_product_lock_still_rejects_second_owner(tmp_path):
    with IsolationFixture(tmp_path / 'fixture') as fixture:
        bind_three(fixture)
        with pytest.raises(KnowledgeError) as rejected:
            SQLiteKnowledgeStore(fixture.state_dir)
        assert rejected.value.code == 'KNOWLEDGE_STORE_LOCKED'
        assert fixture.visible('target') == []
        save(tmp_path, dict(second_owner_error=rejected.value.code, valid_services=3, owners=1))
