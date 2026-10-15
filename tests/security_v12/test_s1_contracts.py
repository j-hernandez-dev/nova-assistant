"""S1 logical authority contracts; no filesystem or process enforcement claim.

Pure unit/contract checks against fresh SECURITY V1.2 implementation. No
deprecated implementation, network, subprocess or host resource is exercised.
"""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ast

import pytest

from local_cli.core.security import (
    AuthorityCeiling, Capability, CapabilityGrant, ControlClass, GrantLifetime, GrantRequest,
    GrantSubject, PathStyle, Permission, ResourceScope, ScopeKind,
    SecurityError, SecurityErrorCode,
)


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def path_scope(path='/workspace', *, tree=True, style=PathStyle.POSIX):
    return ResourceScope(ScopeKind.DIRECTORY_TREE if tree else ScopeKind.FILE,
                         path, path_style=style)


def capability(scope=None, *, restrictions=None, control=None, permission=None):
    return Capability(permission or Permission('filesystem.read'),
                      scope or path_scope(),
                      control or ControlClass.BROKER_ENFORCED,
                      restrictions or {})


def request(**changes):
    cap = capability()
    ceiling = AuthorityCeiling('ceiling-fixture', 1, (cap,))
    data = dict(
        subject=GrantSubject('session-fixture', 'turn-fixture', 'operation-fixture',
                             'call-fixture'),
        tool_name='read', arguments={'file_path': '/workspace/canary.txt'},
        capabilities=(cap,), workspace='/workspace', cwd='/workspace',
        action='read', policy_revision=1, ceiling_id=ceiling.ceiling_id,
        ceiling_revision=ceiling.revision, ceiling_fingerprint=ceiling.fingerprint,
        lifetime=GrantLifetime(NOW, NOW + timedelta(minutes=1)),
        environment_intent={'allowed': []}, network_intent={'mode': 'none'},
        effect_classification='read',
    )
    data.update(changes)
    return GrantRequest(**data)


@pytest.mark.parametrize('invalid', ['', None, 0, True])
def test_permission_rejects_non_permissions(invalid):
    with pytest.raises((ValueError, TypeError)):
        Permission(invalid)


def test_permission_is_extensible_and_immutable():
    item = Permission('application.state.write')
    assert item == Permission('application.state.write')
    assert item != Permission('filesystem.write')
    with pytest.raises(FrozenInstanceError):
        item.name = 'filesystem.write'


@pytest.mark.parametrize('style,parent,child,sibling', [
    (PathStyle.POSIX, '/workspace', '/workspace/sub/file.txt', '/workspace2/file.txt'),
    (PathStyle.WINDOWS, r'C:\Workspace', r'C:\Workspace\sub\file.txt', r'C:\Workspace2\file.txt'),
])
def test_path_scope_segment_boundaries(style, parent, child, sibling):
    root = capability(path_scope(parent, style=style))
    permitted = capability(path_scope(child, tree=False, style=style))
    unrelated = capability(path_scope(sibling, tree=False, style=style))
    assert root.covers(permitted)
    assert not permitted.covers(root)
    assert not root.covers(unrelated)
    assert root.intersect(permitted) == permitted
    assert root.intersect(unrelated) is None


@pytest.mark.parametrize('style,invalid', [
    (PathStyle.POSIX, 'workspace/file.txt'),
    (PathStyle.POSIX, '/workspace/../outside/file.txt'),
    (PathStyle.POSIX, '/workspace/\x00file.txt'),
    (PathStyle.WINDOWS, r'C:workspace\file.txt'),
    (PathStyle.WINDOWS, r'C:\workspace\..\outside\file.txt'),
    (PathStyle.WINDOWS, r'\\?\C:\workspace\file.txt'),
])
def test_path_scope_ambiguous_and_unsupported_inputs_rejected(style, invalid):
    with pytest.raises((ValueError, TypeError)):
        path_scope(invalid, style=style)


def test_path_flavors_never_cross_cover():
    windows = capability(path_scope(r'C:\workspace', style=PathStyle.WINDOWS))
    posix = capability(path_scope('/workspace'))
    assert not windows.covers(posix)
    assert windows.intersect(posix) is None


def test_file_scope_does_not_cover_its_descendants():
    file = capability(path_scope('/workspace/item', tree=False))
    descendant = capability(path_scope('/workspace/item/child', tree=False))
    assert not file.covers(descendant)
    assert file.intersect(descendant) is None


def test_windows_logical_paths_are_case_insensitive_and_posix_paths_are_not():
    first = path_scope(r'C:\WORKSPACE\File.txt', tree=False, style=PathStyle.WINDOWS)
    other = path_scope(r'c:\workspace\file.TXT', tree=False, style=PathStyle.WINDOWS)
    assert first == other
    assert path_scope('/Workspace/File.txt', tree=False) != path_scope('/workspace/file.txt', tree=False)


def test_origin_covers_only_its_own_scheme_host_and_effective_port():
    origin = ResourceScope(ScopeKind.ORIGIN, 'https://example.test:443/')
    permitted = ResourceScope(ScopeKind.URL, 'https://EXAMPLE.test/resource?q=dummy')
    assert origin.covers(permitted)
    assert not permitted.covers(origin)
    for url in ('http://example.test/resource', 'https://example.test:444/resource',
                'https://example.test.evil/resource', 'https://other.test/resource'):
        assert not origin.covers(ResourceScope(ScopeKind.URL, url))


def test_url_scope_is_exact_not_path_prefix_authority():
    item = ResourceScope(ScopeKind.URL, 'https://example.test/a')
    assert item.covers(ResourceScope(ScopeKind.URL, 'https://example.test:443/a'))
    assert not item.covers(ResourceScope(ScopeKind.URL, 'https://example.test/a/b'))
    assert not item.covers(ResourceScope(ScopeKind.URL, 'https://example.test/a?q=dummy'))


@pytest.mark.parametrize('kind,url', [
    (ScopeKind.URL, 'file:///fixture/canary.txt'),
    (ScopeKind.URL, 'https://user:password@example.test/resource'),
    (ScopeKind.URL, 'https://example.test/resource#fragment'),
    (ScopeKind.URL, 'https://example.test:0/resource'),
    (ScopeKind.URL, 'https://example.test:65536/resource'),
    (ScopeKind.URL, 'https://example.test./resource'),
    (ScopeKind.URL, 'https://example.test\\resource'),
    (ScopeKind.ORIGIN, 'https://example.test/resource'),
    (ScopeKind.ORIGIN, 'https://example.test/?query=dummy'),
])
def test_url_scope_rejects_unsupported_and_ambiguous_forms(kind, url):
    with pytest.raises((ValueError, TypeError)):
        ResourceScope(kind, url)


def test_process_scope_binds_action_cwd_and_executable_exactly():
    def process(cwd='/workspace', action='fixture-action', executable='/bin/fixture'):
        return ResourceScope(ScopeKind.PROCESS_REQUEST, cwd,
                             path_style=PathStyle.POSIX, action=action, executable=executable)
    base = process()
    assert base.covers(process())
    for variant in (process(cwd='/workspace/sub'), process(action='other-action'),
                    process(executable='/bin/other-fixture')):
        assert not base.covers(variant)
    Capability(Permission('process.execute'), base, ControlClass.HOST_UNISOLATED)
    with pytest.raises((ValueError, TypeError)):
        Capability(Permission('process.execute'), base, ControlClass.BROKER_ENFORCED)


def test_multiline_process_action_is_preserved_without_parsing_or_execution():
    action = "fixture-action\n\tsecond-fixture\r\nthird-fixture"
    scope = ResourceScope(ScopeKind.PROCESS_REQUEST, '/workspace',
                          path_style=PathStyle.POSIX, executable='/bin/fixture', action=action)
    assert scope.action == action
    assert request(action=action).action == action
    assert request(action=action).request_digest != request(action=action.replace('\n', ';')).request_digest


@pytest.mark.parametrize('action', ['fixture\x00action', 'fixture\x01action', 'x' * 65537],
                         ids=['nul', 'control', 'oversized'])
def test_action_rejects_nul_other_control_and_oversize(action):
    with pytest.raises((ValueError, TypeError)):
        request(action=action)
    with pytest.raises((ValueError, TypeError)):
        ResourceScope(ScopeKind.PROCESS_REQUEST, '/workspace', path_style=PathStyle.POSIX,
                      executable='/bin/fixture', action=action)


def test_environment_name_comparison_is_platform_explicit():
    def env(name, style):
        return ResourceScope(ScopeKind.ENVIRONMENT_VARIABLE, name, path_style=style)
    assert env('DUMMY_FIXTURE', PathStyle.WINDOWS) == env('dummy_fixture', PathStyle.WINDOWS)
    assert env('DUMMY_FIXTURE', PathStyle.POSIX) != env('dummy_fixture', PathStyle.POSIX)
    assert not env('DUMMY_FIXTURE', PathStyle.WINDOWS).covers(env('OTHER', PathStyle.WINDOWS))
    with pytest.raises((ValueError, TypeError)):
        ResourceScope(ScopeKind.ENVIRONMENT_VARIABLE, 'DUMMY_FIXTURE')


@pytest.mark.parametrize('kind', [ScopeKind.REPOSITORY, ScopeKind.SESSION])
def test_identity_scopes_are_exact(kind):
    own = ResourceScope(kind, 'fixture-id')
    assert own.covers(ResourceScope(kind, 'fixture-id'))
    assert not own.covers(ResourceScope(kind, 'fixture-id-child'))
    assert not own.covers(ResourceScope(kind, 'other-fixture'))


def test_control_class_cannot_be_upgraded_by_narrowing_resource():
    host = capability(control=ControlClass.HOST_UNISOLATED)
    broker = capability(path_scope('/workspace/item', tree=False))
    assert not host.covers(broker)
    assert host.intersect(broker) is None
    assert 'HOST_UNISOLATED' in {value.value for value in ControlClass}


def test_permissions_are_not_inferred_from_related_words():
    read = capability()
    write = capability(permission=Permission('filesystem.write'))
    assert not read.covers(write)
    assert read.intersect(write) is None


def test_restrictions_are_exact_conjunctions_and_intersect():
    parent = capability(restrictions={'mode': 'read'})
    child = capability(restrictions={'mode': 'read', 'fixture': True})
    conflict = capability(restrictions={'mode': 'write'})
    assert parent.covers(child)
    assert not child.covers(parent)
    assert parent.intersect(child) == child
    assert parent.intersect(conflict) is None


def test_numeric_constraints_do_not_imply_ordering():
    one = capability(restrictions={'limit': 1})
    two = capability(restrictions={'limit': 2})
    assert not two.covers(one)
    assert two.intersect(one) is None


def test_restriction_equality_does_not_coerce_json_boolean_into_integer():
    boolean = capability(restrictions={'flag': True})
    integer = capability(restrictions={'flag': 1})
    assert not boolean.covers(integer)
    assert not integer.covers(boolean)
    assert boolean.intersect(integer) is None


def test_restriction_equality_preserves_nested_array_order():
    first = capability(restrictions={'fixture': {'names': ['one', 'two']}})
    reordered_map = capability(restrictions={'fixture': {'names': ['one', 'two']}})
    reversed_values = capability(restrictions={'fixture': {'names': ['two', 'one']}})
    assert first.covers(reordered_map)
    assert not first.covers(reversed_values)
    assert first.intersect(reversed_values) is None


def test_capability_deep_snapshot_is_not_mutable_input_alias():
    source = {'fixture': {'names': ['one', 'two']}}
    cap = capability(restrictions=source)
    original = capability(restrictions={'fixture': {'names': ['one', 'two']}})
    source['fixture']['names'].append('three')
    assert cap == original
    with pytest.raises(TypeError):
        cap.restrictions['new'] = 1
    with pytest.raises(TypeError):
        cap.restrictions['fixture']['new'] = 1
    with pytest.raises((AttributeError, TypeError)):
        cap.restrictions['fixture']['names'].append('three')


def test_ceiling_intersection_cannot_expand_either_input():
    broad = AuthorityCeiling('parent', 1, (capability(),))
    narrowed_cap = capability(path_scope('/workspace/item', tree=False))
    narrow = AuthorityCeiling('child-host', 2, (narrowed_cap,))
    result = broad.intersect(narrow)
    assert result.covers(narrowed_cap)
    assert not result.covers(capability())
    assert all(broad.covers(cap) and narrow.covers(cap) for cap in result.capabilities)


def test_ceiling_fingerprint_binds_identity_revision_and_content():
    base = AuthorityCeiling('ceiling', 1, (capability(),))
    variants = (
        AuthorityCeiling('other', 1, base.capabilities),
        AuthorityCeiling('ceiling', 2, base.capabilities),
        AuthorityCeiling('ceiling', 1,
                         (capability(path_scope('/workspace/item', tree=False)),)),
    )
    assert all(item.fingerprint != base.fingerprint for item in variants)


def test_capability_order_is_not_ceiling_authority():
    read = capability()
    write = capability(permission=Permission('filesystem.write'))
    first = AuthorityCeiling('ceiling', 1, (read, write))
    second = AuthorityCeiling('ceiling', 1, (write, read))
    assert first.fingerprint == second.fingerprint


def test_ceiling_intersection_fingerprint_is_commutative():
    broad = AuthorityCeiling('broad', 1, (capability(),))
    narrow = AuthorityCeiling('narrow', 2,
                              (capability(path_scope('/workspace/item', tree=False)),))
    first, second = broad.intersect(narrow), narrow.intersect(broad)
    assert first.fingerprint == second.fingerprint
    assert first.capabilities == second.capabilities


@pytest.mark.parametrize('field,new_value', [
    ('tool_name', 'glob'), ('arguments', {'file_path': '/workspace/other.txt'}),
    ('workspace', '/'), ('cwd', '/workspace/sub'),
    ('action', 'enumerate'), ('policy_revision', 2),
    ('ceiling_id', 'other-ceiling'), ('ceiling_revision', 2),
    ('ceiling_fingerprint', 'a' * 64),
    ('environment_intent', {'allowed': ['DUMMY_VALUE']}),
    ('network_intent', {'mode': 'fetch'}), ('effect_classification', 'write'),
])
def test_request_digest_binds_relevant_fields(field, new_value):
    base = request()
    changed = replace(base, **{field: new_value})
    assert base.request_digest != changed.request_digest


@pytest.mark.parametrize('field', [
    'session_id', 'turn_id', 'operation_id', 'tool_call_id', 'agent_id',
    'parent_operation_id', 'parent_agent_id',
])
def test_request_digest_binds_subject_ids(field):
    base = request()
    changes = {field: f'changed-{field}'}
    if field == 'parent_agent_id':
        changes['parent_operation_id'] = 'parent-operation-fixture'
    subject = replace(base.subject, **changes)
    assert replace(base, subject=subject).request_digest != base.request_digest


def test_digest_binds_parent_id_and_authority_as_separate_fields():
    base = request(parent_grant_id='parent-grant-fixture',
                   parent_authority_fingerprint='b' * 64)
    assert replace(base, parent_grant_id='other-parent').request_digest != base.request_digest
    assert replace(base, parent_authority_fingerprint='c' * 64).request_digest != base.request_digest
    assert request().request_digest != base.request_digest


@pytest.mark.parametrize('changes', [
    {'parent_grant_id': 'parent-without-authority'},
    {'parent_authority_fingerprint': 'b' * 64},
])
def test_parent_binding_cannot_be_partially_specified(changes):
    with pytest.raises((ValueError, TypeError)):
        request(**changes)


@pytest.mark.parametrize('field,new_value', [
    ('parent_session_id', 'other-parent-session'),
    ('parent_turn_id', 'other-parent-turn'),
])
def test_digest_binds_parent_session_and_turn_lineage(field, new_value):
    subject = replace(request().subject, parent_operation_id='parent-operation',
                      parent_agent_id='parent-agent', parent_session_id='parent-session',
                      parent_turn_id='parent-turn')
    base = request(subject=subject)
    changed = replace(subject, **{field: new_value})
    assert request(subject=changed).request_digest != base.request_digest


def test_digest_binds_capability_control_and_lifetime():
    base = request()
    different_cap = capability(control=ControlClass.HOST_UNISOLATED)
    assert replace(base, capabilities=(different_cap,)).request_digest != base.request_digest
    later = replace(base.lifetime, expires_at=base.lifetime.expires_at + timedelta(seconds=1))
    assert replace(base, lifetime=later).request_digest != base.request_digest


def test_digest_canonicalizes_mapping_order_but_preserves_types_and_sequences():
    first = request(arguments={'a': 1, 'b': ['x', 'y']})
    reorder = request(arguments={'b': ['x', 'y'], 'a': 1})
    boolean = request(arguments={'a': True, 'b': ['x', 'y']})
    reverse = request(arguments={'a': 1, 'b': ['y', 'x']})
    assert first.request_digest == reorder.request_digest
    assert first.request_digest != boolean.request_digest
    assert first.request_digest != reverse.request_digest


def test_request_deep_snapshots_all_untrusted_input_values():
    args = {'a': {'names': ['x']}}
    env = {'names': ['DUMMY']}
    req = request(arguments=args, environment_intent=env)
    digest = req.request_digest
    args['a']['names'].append('y')
    env['names'].append('OTHER_DUMMY')
    assert req.request_digest == digest
    with pytest.raises(TypeError):
        req.arguments['new'] = 'bad'
    with pytest.raises((AttributeError, TypeError)):
        req.arguments['a']['names'].append('z')


@pytest.mark.parametrize('changes', [
    {'request_version': 0}, {'request_version': 2},
    {'arguments': {'not_json': object()}},
    {'arguments': {'not_finite': float('nan')}},
    {'arguments': {1: 'numeric-key'}},
    {'policy_revision': True}, {'ceiling_revision': -1},
])
def test_request_rejects_unsupported_unsafe_or_unversioned_inputs(changes):
    with pytest.raises((ValueError, TypeError)):
        request(**changes)


@pytest.mark.parametrize('changes', [
    {'workspace': 'relative-workspace'}, {'cwd': 'relative-cwd'},
    {'cwd': '/outside'}, {'cwd': '/workspace2'},
    {'cwd': '/workspace/../outside'},
])
def test_request_binds_only_unambiguous_lexical_workspace_containment(changes):
    with pytest.raises((ValueError, TypeError)):
        request(**changes)


def invocation_fixture():
    from local_cli.core.contracts import ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation

    class NotCancelled:
        def is_cancel_requested(self):
            return False

    # Existing test directory spelling gives a platform-absolute path. No file
    # is opened, changed, resolved through a broker, or used as execution cwd.
    workspace = Path(__file__).resolve().parent
    context = ExecutionContext(workspace=workspace, cwd=workspace,
        environment={'DUMMY_FIXTURE': 'not-a-secret'}, session_id='child-session',
        operation_id='child-operation', cancellation_token=NotCancelled(),
        deadline=NOW + timedelta(seconds=30),
        capabilities=RuntimeCapabilitySnapshot(captured_at=NOW, source='s1-unit-fixture'),
        turn_id='child-turn', agent_id='child-agent', policy_revision=7)
    return ToolInvocation('read', {'fixture': {'names': ['one']}},
                          'child-call', 'child-operation', context)


def build_from_invocation(invocation, **changes):
    cap = capability()
    ceiling = AuthorityCeiling('builder-ceiling', 3, (cap,))
    data = dict(capabilities=(cap,), ceiling=ceiling,
                lifetime=GrantLifetime(NOW, NOW + timedelta(seconds=20)),
                action='read', effect_classification='read')
    data.update(changes)
    return GrantRequest.from_invocation(invocation, **data)


def test_from_invocation_preserves_core_ids_revisions_context_and_input_snapshot():
    invocation = invocation_fixture()
    derived = build_from_invocation(invocation)
    ctx = invocation.context
    assert derived.subject == GrantSubject(ctx.session_id, ctx.turn_id, invocation.operation_id,
                                          invocation.tool_call_id, ctx.agent_id)
    assert derived.tool_name == invocation.name
    assert derived.policy_revision == 7
    assert derived.ceiling_revision == 3
    assert derived.workspace == str(ctx.workspace)
    assert derived.cwd == str(ctx.cwd)
    assert dict(derived.environment_intent) == dict(ctx.environment)
    digest = derived.request_digest
    invocation.arguments['fixture']['names'].append('two')
    assert derived.request_digest == digest
    assert derived.arguments['fixture']['names'] == ('one',)


def test_from_invocation_rejects_operation_policy_and_deadline_mismatch():
    invocation = invocation_fixture()
    with pytest.raises((ValueError, TypeError)):
        build_from_invocation(replace(invocation, operation_id='other-operation'))
    with pytest.raises((ValueError, TypeError)):
        build_from_invocation(invocation, policy_revision=8)
    with pytest.raises((ValueError, TypeError)):
        build_from_invocation(invocation,
            lifetime=GrantLifetime(NOW, NOW + timedelta(seconds=31)))


def test_from_invocation_binds_explicit_parent_lineage_for_new_child_session():
    parent_subject = GrantSubject('parent-session', 'parent-turn', 'parent-operation',
                                 'parent-call', agent_id='parent-agent')
    parent = CapabilityGrant('parent-grant', 'fixture-issuer', request(subject=parent_subject))
    invocation = invocation_fixture()
    child = build_from_invocation(invocation, parent=parent)
    assert child.subject.session_id == 'child-session'
    assert child.subject.turn_id == 'child-turn'
    assert child.subject.parent_session_id == 'parent-session'
    assert child.subject.parent_turn_id == 'parent-turn'
    assert child.subject.parent_operation_id == 'parent-operation'
    assert child.subject.parent_agent_id == 'parent-agent'
    assert child.parent_grant_id == parent.grant_id
    assert child.parent_authority_fingerprint == parent.authority_fingerprint


@pytest.mark.parametrize('field,value', [
    ('arguments', {'surrogate': '\ud800'}),
    ('arguments', {'\udfff': 'value'}),
    ('tool_name', '\ud800'),
    ('action', '\ud800'),
    ('environment_intent', {'dummy': '\ud800'}),
])
def test_invalid_unicode_fails_with_typed_contract_error(field, value):
    with pytest.raises(SecurityError) as rejected:
        request(**{field: value})
    assert rejected.value.code is SecurityErrorCode.INVALID_CONTRACT


def test_invalid_parent_handle_is_typed_and_not_a_bearer():
    with pytest.raises(SecurityError) as rejected:
        build_from_invocation(invocation_fixture(), parent=object())
    assert rejected.value.code is SecurityErrorCode.INVALID_CONTRACT


def test_grants_are_not_public_payloads_or_issuance_commands():
    from local_cli.application.commands import CommandKind
    from local_cli.core.contracts import json_safe_copy
    grant = CapabilityGrant('grant-fixture', 'issuer-fixture', request())
    with pytest.raises(ValueError):
        json_safe_copy(grant)
    assert all('grant' not in kind.value.lower() for kind in CommandKind)
    metadata = grant.correlation_metadata()
    assert set(metadata) == {'grantId', 'operationId', 'sessionId', 'controlClasses'}
    assert 'requestDigest' not in metadata
    assert 'DUMMY' not in repr(grant)


@pytest.mark.parametrize('not_before,expires_at', [
    (NOW.replace(tzinfo=None), NOW + timedelta(minutes=1)),
    (NOW, NOW.replace(tzinfo=None)),
    (NOW, NOW), (NOW, NOW - timedelta(seconds=1)),
])
def test_lifetime_is_explicit_aware_and_positive(not_before, expires_at):
    with pytest.raises((ValueError, TypeError)):
        GrantLifetime(not_before, expires_at)


def test_lifetime_one_shot_is_not_optional_implicit_truthiness():
    with pytest.raises((ValueError, TypeError)):
        GrantLifetime(NOW, NOW + timedelta(minutes=1), one_shot='yes')


def test_core_security_has_only_inward_dependencies_and_no_issuer_endpoint():
    from local_cli.core import security
    source = Path(security.__file__).read_text(encoding='utf-8')
    imports = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name.startswith(('local_cli.application', 'local_cli.interfaces',
                                    'local_cli.infrastructure', 'local_cli.cli',
                                    'local_cli.server')) for name in imports)
    assert not hasattr(security, 'GrantIssuer')
    assert not hasattr(security, 'SandboxPort')
