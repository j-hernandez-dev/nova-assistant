"""S3 authority/runtime unit and in-process integration with a broker-port fake."""
from dataclasses import replace
from pathlib import Path
from threading import Thread, Event

import pytest

from local_cli.application.interactions import ApprovalGate, InteractionError
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime, LegacyToolAdapter
from local_cli.core.contracts import ToolResult, ToolStatus, EffectState, EventKind
from local_cli.core.filesystem import FilesystemError, FilesystemRoot
from local_cli.core.security import ResourceScope, ScopeKind, PathStyle, _map, SecurityError
from local_cli.tools.read_tool import ReadTool
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.edit_tool import EditTool
from local_cli.tools.glob_tool import GlobTool
from local_cli.tools.grep_tool import GrepTool
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s2_runtime import response


class FakePlan:
    def __init__(self, broker, root, inv):
        self.broker, self.inv = broker, inv
        self.closed, self.valid = False, True
        raw = inv.arguments.get('file_path', inv.arguments.get('path', '.'))
        path = Path(raw)
        path = path if path.is_absolute() else inv.context.cwd/path
        self.binding = _map({'rootIdentity': root.identity, 'root': root.path,
                             'path': str(path), 'tool': inv.name, 'target': {'identity': 'file-1'}})
    def validate_current(self):
        if not self.valid:
            raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')
    def execute(self, guard):
        guard()
        self.broker.effects.append(self.inv.name)
        if self.broker.error:
            raise self.broker.error
        return ToolResult(ToolStatus.COMPLETED,
            EffectState.APPLIED if self.inv.name in ('write', 'edit') else EffectState.NONE,
            legacy_text='fixture', metadata={'verificationWarning': 'fixture warning'})
    def close(self):
        self.closed = True


class FakeBroker:
    def __init__(self):
        self.plans, self.effects = [], []
        self.error = None
    def bind_root(self, path):
        return FilesystemRoot(str(path), 'root:'+str(path))
    def prepare(self, root, inv):
        style = PathStyle.POSIX if root.path.startswith('/') else PathStyle.WINDOWS
        raw = inv.arguments.get('file_path', inv.arguments.get('path', '.'))
        path = Path(raw)
        path = path if path.is_absolute() else inv.context.cwd/path
        if not ResourceScope(ScopeKind.DIRECTORY_TREE, root.path, style).covers(
                ResourceScope(ScopeKind.FILE, str(path), style)):
            raise FilesystemError('RESOURCE_SCOPE_VIOLATION')
        plan = FakePlan(self, root, inv); self.plans.append(plan)
        return plan
    def close(self):
        pass


def runtime(tmp_path, *, gate=None):
    broker = FakeBroker()
    tools = [cls(cwd=tmp_path) for cls in (ReadTool, WriteTool, EditTool, GlobTool, GrepTool)]
    for tool in tools:
        tool.execute = lambda **_: pytest.fail('direct legacy FS bypass')
    events = []
    rt = ToolRuntime(ToolRegistry(tools), filesystem_broker=broker,
                     approval_gate=gate, publish=events.append)
    rt.install_authority(tmp_path, 'session')
    return rt, broker, events


@pytest.mark.parametrize('name,args', [
    ('read', {'file_path': 'a'}), ('write', {'file_path': 'a', 'content': 'new'}),
    ('edit', {'file_path': 'a', 'old_text': 'old', 'new_text': 'new'}),
    ('glob', {'pattern': '*'}), ('grep', {'pattern': 'find'}),
])
def test_five_tools_use_claimed_broker_without_legacy_fallback(tmp_path, name, args):
    rt, broker, events = runtime(tmp_path)
    inv = invocation(tmp_path, name, args)
    result = rt.execute(inv)
    assert result.status is ToolStatus.COMPLETED, result
    assert broker.effects == [name]
    assert broker.plans[0].closed
    assert 'BROKER_ENFORCED' in result.metadata['controlClasses']
    grant = rt._issuer._issued[result.metadata['grantId']].grant
    assert grant.request.filesystem_binding['rootIdentity']
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED]
    assert rt.execute(inv) is result
    assert broker.effects == [name]
    with pytest.raises(SecurityError, match='GRANT_CONSUMED'):
        rt._issuer.claim(grant, grant.request)


@pytest.mark.parametrize('effect,status', [('none', ToolStatus.DENIED),
                                         ('partial', ToolStatus.FAILED),
                                         ('unknown', ToolStatus.OUTCOME_UNKNOWN)])
def test_broker_failure_never_retries_or_degrades(tmp_path, effect, status):
    rt, broker, events = runtime(tmp_path)
    broker.error = FilesystemError('FILESYSTEM_REPARSE_DENIED', effect=effect)
    inv = invocation(tmp_path, 'write', {'file_path': 'a', 'content': 'new'})
    result = rt.execute(inv)
    assert result.status is status and result.effect_state.value == effect
    assert rt.execute(inv) is result
    assert broker.effects == ['write']
    assert events[-1][0] is EventKind.TOOL_FAILED and broker.plans[0].closed


def test_external_root_is_exact_human_approved_one_operation(tmp_path):
    requested = []
    gate = ApprovalGate(on_required=requested.append)
    actor = gate.register_actor('desktop_host', lambda: True)
    rt, broker, _ = runtime(tmp_path, gate=gate)
    inv = invocation(tmp_path, 'read', {'file_path': str(tmp_path.parent/'external.txt')})
    rt.authorize_external_filesystem(inv, tmp_path.parent, ['filesystem.read'])
    result = []
    thread = Thread(target=lambda: result.append(rt.execute(inv)), daemon=True); thread.start()
    from tests.test_nova_core_phase7_session import _pending
    req = _pending(gate)
    assert not broker.effects
    gate.resolve(**response(req, actor)); thread.join(2)
    assert result[0].status is ToolStatus.COMPLETED
    assert result[0].metadata['requestDigest'] == req.request_digest
    again = replace(inv, operation_id='other', context=replace(inv.context, operation_id='other'))
    assert rt.execute(again).status is ToolStatus.DENIED
    assert broker.effects == ['read']


def test_binding_change_during_human_approval_is_stale(tmp_path):
    ready = Event()
    gate = ApprovalGate(on_required=lambda _: ready.set())
    actor = gate.register_actor('desktop_host', lambda: True)
    rt, broker, _ = runtime(tmp_path, gate=gate)
    inv = invocation(tmp_path, 'read', {'file_path': str(tmp_path.parent/'outside.txt')})
    rt.authorize_external_filesystem(inv, tmp_path.parent, ['filesystem.read'])
    results = []; worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start(); assert ready.wait(2)
    req = gate.pending()[0]; broker.plans[-1].valid = False
    with pytest.raises(InteractionError):
        gate.resolve(**response(req, actor))
    worker.join(2)
    assert results[0].status is ToolStatus.DENIED and not broker.effects
    assert broker.plans[-1].closed


def test_only_read_ceiling_cannot_write(tmp_path):
    rt, broker, _ = runtime(tmp_path)
    old = rt._issuer.ceiling
    rt._issuer.replace_ceiling(replace(old, revision=2, capabilities=tuple(
        c for c in old.capabilities if c.permission.name != 'filesystem.write')))
    inv = invocation(tmp_path, 'write', {'file_path': 'a', 'content': 'new'})
    assert rt.execute(inv).status is ToolStatus.DENIED
    assert not broker.effects and not broker.plans


def test_copied_grant_cannot_enter_broker(tmp_path):
    rt, broker, _ = runtime(tmp_path)
    result = rt.execute(invocation(tmp_path, 'read', {'file_path': 'a'}))
    grant = rt._issuer._issued[result.metadata['grantId']].grant
    with pytest.raises(SecurityError, match='GRANT_UNKNOWN'):
        rt._filesystem.execute(broker.plans[0], replace(grant), rt._issuer)
    assert broker.effects == ['read']


def test_post_write_verifier_uses_broker_result_not_pathname(tmp_path, monkeypatch):
    rt, broker, _ = runtime(tmp_path)
    inv = invocation(tmp_path, 'write', {'file_path': 'a.py', 'content': 'new'})
    wrapper = LegacyToolAdapter(rt.registry.tool('write'), rt, lambda: inv.context)
    assert wrapper.execute(**inv.arguments) == 'fixture'
    monkeypatch.setattr(Path, 'read_text', lambda *_, **__: pytest.fail('unmediated verifier'))
    assert wrapper.verify_file_write(dict(inv.arguments), 'fixture') == 'fixture warning'


def test_filesystem_binding_is_immutable_and_part_of_exact_digest(tmp_path):
    rt, broker, _ = runtime(tmp_path)
    result = rt.execute(invocation(tmp_path, 'read', {'file_path': 'a'}))
    request = rt._issuer._issued[result.metadata['grantId']].grant.request
    with pytest.raises(TypeError):
        request.filesystem_binding['target']['identity'] = 'different'
    changed = replace(request, filesystem_binding={**request.filesystem_binding,
                                                   'target': {'identity': 'different'}})
    assert changed.request_digest != request.request_digest
    assert replace(request, filesystem_binding={}).request_digest != request.request_digest
    assert broker.plans[0].binding == request.filesystem_binding


@pytest.mark.parametrize('mutation,code', [('unclaimed', 'GRANT_CONSUMED'),
    ('revoke', 'GRANT_REVOKED'), ('cancel', 'GRANT_CANCELLED'),
    ('expire', 'GRANT_EXPIRED'), ('revision', 'REVISION_MISMATCH')])
def test_broker_checks_claimed_liveness_without_reclaim_or_new_effect(tmp_path, mutation, code):
    from datetime import timedelta
    rt, broker, _ = runtime(tmp_path)
    inv = invocation(tmp_path, 'read', {'file_path': 'a'})
    result = rt.execute(inv)
    grant = rt._issuer._issued[result.metadata['grantId']].grant
    if mutation == 'unclaimed':
        rt._issuer._issued[grant.grant_id].claims = 0
    elif mutation == 'revoke':
        rt._issuer.revoke(grant)
    elif mutation == 'cancel':
        inv.context.cancellation_token.request()
    elif mutation == 'expire':
        rt._issuer._clock = lambda: grant.request.lifetime.expires_at + timedelta(seconds=1)
    else:
        old = rt._issuer.ceiling
        rt._issuer.replace_ceiling(replace(old, revision=old.revision+1))
    with pytest.raises(SecurityError, match=code):
        rt._filesystem.execute(broker.plans[0], grant, rt._issuer)
    assert broker.effects == ['read']


def test_missing_broker_fails_closed_without_direct_adapter(tmp_path, monkeypatch):
    tool = ReadTool(cwd=tmp_path)
    monkeypatch.setattr(tool, 'execute', lambda **_: pytest.fail('direct fallback'))
    def unavailable():
        raise FilesystemError('FILESYSTEM_PLATFORM_UNSUPPORTED')
    monkeypatch.setattr(tool, 'create_filesystem_broker', unavailable)
    rt = ToolRuntime(ToolRegistry([tool]))
    result = rt.execute(invocation(tmp_path, 'read', {'file_path': 'a'}))
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert result.metadata['securityErrorCode'] == 'FILESYSTEM_PLATFORM_UNSUPPORTED'


def test_child_shares_broker_authority_but_cannot_expand_to_worktree(tmp_path):
    rt, broker, _ = runtime(tmp_path)
    parent = rt.delegation_for(invocation(tmp_path, 'read', {'file_path': 'a'}).context)
    child = ToolRuntime(rt.registry, issuer=rt._issuer, policy=rt.policy,
                        parent_grant=parent, filesystem_authority=rt._filesystem)
    inv = invocation(tmp_path, 'read', {'file_path': 'a'}, session_id='child', agent_id='child')
    inv = replace(inv, operation_id='child-op', context=replace(inv.context, operation_id='child-op'))
    assert child.execute(inv).status is ToolStatus.COMPLETED
    outside = tmp_path.parent/'worktree'
    for name in child.registry.names:
        child.registry.tool(name).cwd = outside
    expanded = replace(inv, operation_id='outside', context=replace(inv.context,
        operation_id='outside', cwd=outside, workspace=outside))
    assert child.execute(expanded).status is ToolStatus.DENIED
    child.close()  # shared authority belongs to its main runtime
    assert broker.effects == ['read']
