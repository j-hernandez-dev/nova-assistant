"""M1 identity is not Core session/cwd and scope is an explicit host value."""

from dataclasses import FrozenInstanceError, replace
import hashlib
from unittest.mock import Mock

import pytest

from local_cli.core.contracts import new_session_id
from local_cli.core.memory import (MemoryAccessScope, MemoryError, MemoryIdentityPort,
    MemoryScope, MemoryScopeKind, SubjectId, WorkspaceId, new_subject_id,
    workspace_id_from_canonical_path)
from tests.memory_v1.m1_fixtures import (ACCESS_A, ALPHA, BETA, GLOBAL,
    SUBJECT_A, SUBJECT_B, WORKSPACE_A, WORKSPACE_B, AT, record)


@pytest.mark.parametrize('value', ['synthetic-session-1', new_session_id(), 'fixture-user',
    'fixture@example.invalid', '', None, True, 7, '11111111-1111-1111-8111-111111111111'])
def test_subject_rejects_session_os_user_email_and_non_uuid4(value):
    with pytest.raises(MemoryError) as error:
        SubjectId(value)
    assert error.value.code == 'MEMORY_INVALID_IDENTITY'


def test_subject_uuid_creation_is_opaque_and_not_a_session_identity():
    one, two = new_subject_id(), new_subject_id()
    assert isinstance(one, SubjectId) and one != two
    assert one != one.value and one.value != new_session_id()
    assert SubjectId(one.value) == one  # Trusted reload representation, not IO.


def test_identity_port_contract_is_stable_across_sessions_and_provider_changes():
    identity = Mock(spec=MemoryIdentityPort)
    identity.load_or_create_subject.return_value = SUBJECT_A
    identity.resolve_workspace.return_value = WORKSPACE_A
    observed = []
    for session, provider in [('synthetic-session-1', 'ollama'), ('synthetic-session-2', 'llama-server')]:
        observed.append((identity.load_or_create_subject(), identity.resolve_workspace('/synthetic/projects/alpha')))
    assert observed == [(SUBJECT_A, WORKSPACE_A)] * 2
    assert all(call.args == () for call in identity.load_or_create_subject.call_args_list)
    # The stub proves the port inputs; it does NOT prove durable storage/restart.


@pytest.mark.parametrize('canonical', ['/synthetic/projects/alpha', r'C:\Synthetic\Alpha',
    r'\\synthetic-server\synthetic-share\Alpha', '/synthetic/acción/🙂'])
def test_workspace_hash_is_deterministic_versioned_and_collision_resistant(canonical):
    result = workspace_id_from_canonical_path(canonical)
    assert result.value == hashlib.sha256(('nova-memory-workspace:v1\0' + canonical).encode('utf-8')).hexdigest()
    assert result == workspace_id_from_canonical_path(canonical)
    assert result != workspace_id_from_canonical_path(canonical + '-other')
    assert result != workspace_id_from_canonical_path(canonical, identity_version=2)
    assert result.identity_version == 1


@pytest.mark.parametrize('canonical', ['relative', 'fixture-user', '', '.', '../alpha',
    '/synthetic/../alpha', r'C:\Synthetic\..\Alpha', None, True, '/synthetic/\x00'])
def test_workspace_hash_rejects_noncanonical_shapes_without_resolving_os_paths(canonical):
    with pytest.raises(MemoryError) as error:
        workspace_id_from_canonical_path(canonical)
    assert error.value.code == 'MEMORY_INVALID_IDENTITY'


@pytest.mark.parametrize('kind,scope_id', [(MemoryScopeKind.GLOBAL_PROFILE, WORKSPACE_A),
    (MemoryScopeKind.WORKSPACE, None), (MemoryScopeKind.WORKSPACE, '/synthetic/alpha'),
    ('WORKSPACE', WORKSPACE_A)])
def test_scope_is_explicit_typed_and_unambiguous(kind, scope_id):
    with pytest.raises(MemoryError):
        MemoryScope(kind, scope_id)


@pytest.mark.parametrize('subject,scope,allowed', [(SUBJECT_A, GLOBAL, True),
    (SUBJECT_A, ALPHA, True), (SUBJECT_A, BETA, False),
    (SUBJECT_B, GLOBAL, False), (SUBJECT_B, ALPHA, False), (SUBJECT_B, BETA, False)])
def test_read_scope_has_no_cross_subject_or_workspace_leak(subject, scope, allowed):
    assert ACCESS_A.allows(subject, scope) is allowed
    assert record(subject_id=subject, scope=scope).eligible(ACCESS_A, at=AT) is allowed


def test_cwd_rebind_and_attenuation_do_not_mutate_or_widen_prior_scope():
    after = replace(ACCESS_A, workspace_id=WORKSPACE_B)
    assert not after.allows(SUBJECT_A, ALPHA) and after.allows(SUBJECT_A, BETA)
    assert ACCESS_A.workspace_id == WORKSPACE_A
    child = replace(ACCESS_A, include_global=False)
    assert not child.allows(SUBJECT_A, GLOBAL) and child.allows(SUBJECT_A, ALPHA)
    with pytest.raises(FrozenInstanceError):
        ACCESS_A.workspace_id = WORKSPACE_B
    assert 'cwd' not in ACCESS_A.__dataclass_fields__


@pytest.mark.parametrize('value,version', [('a' * 63, 1), ('A' * 64, 1), ('g' * 64, 1),
    ('a' * 64, True), ('a' * 64, 0)])
def test_workspace_identity_requires_digest_and_explicit_valid_version(value, version):
    with pytest.raises(MemoryError) as error:
        WorkspaceId(value, version)
    assert error.value.code == 'MEMORY_INVALID_IDENTITY'
