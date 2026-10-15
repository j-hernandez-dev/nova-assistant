"""S3 authority coordination; depends only on Core contracts and broker ports."""
from pathlib import Path
import json

from local_cli.core.filesystem import FilesystemBrokerPort, FilesystemError
from local_cli.core.security import Capability, ControlClass, Permission, ResourceScope, ScopeKind, PathStyle


def fingerprint(invocation):
    ctx = invocation.context
    return json.dumps([ctx.session_id, ctx.turn_id, ctx.agent_id, invocation.operation_id,
        invocation.tool_call_id, invocation.name, dict(invocation.arguments), str(ctx.workspace),
        str(ctx.cwd), dict(ctx.environment), ctx.policy_revision,
        ctx.deadline.isoformat() if ctx.deadline else None], sort_keys=True, ensure_ascii=False)


class FilesystemAuthority:
    def __init__(self, broker: FilesystemBrokerPort, workspace: Path):
        self.broker = broker
        self.root = broker.bind_root(workspace)
        self.external = {}

    def authorize_external(self, invocation, root_path, permissions):
        """Host-only exact operation selection, NOT human approval.

        Caller separately installs these finite capabilities into the host
        ceiling. No public command/model argument reaches this hook.
        """
        permissions = tuple(sorted(set(permissions)))
        if not permissions or any(p not in ('filesystem.read', 'filesystem.write') for p in permissions):
            raise FilesystemError('PERMISSION_DENIED')
        raw = invocation.arguments.get('file_path') if invocation.name in ('read', 'write', 'edit') else invocation.arguments.get('path', '.')
        style = PathStyle.WINDOWS if not str(invocation.context.workspace).startswith('/') else PathStyle.POSIX
        path = Path(raw)
        path = path if path.is_absolute() else invocation.context.cwd/path
        scope = ResourceScope(ScopeKind.FILE if invocation.name in ('read', 'write', 'edit')
                              else ScopeKind.DIRECTORY_TREE, str(path), style)
        root = self.broker.bind_root(Path(root_path))
        root_scope = ResourceScope(ScopeKind.DIRECTORY_TREE, root.path, style)
        if not root_scope.covers(scope):
            raise FilesystemError('RESOURCE_SCOPE_VIOLATION')
        key = (invocation.context.session_id, invocation.operation_id)
        if key in self.external:
            raise FilesystemError('FILESYSTEM_AUTHORIZATION_CONSUMED')
        self.external[key] = (fingerprint(invocation), root, permissions, False)
        return tuple(Capability(Permission(p), scope, ControlClass.BROKER_ENFORCED) for p in permissions)

    def prepare(self, invocation):
        try:
            return self.broker.prepare(self.root, invocation), False
        except FilesystemError as exc:
            if exc.code != 'RESOURCE_SCOPE_VIOLATION':
                raise
        key = (invocation.context.session_id, invocation.operation_id)
        ticket = self.external.get(key)
        if ticket is None or ticket[3] or ticket[0] != fingerprint(invocation):
            raise FilesystemError('RESOURCE_SCOPE_VIOLATION')
        needed = {'filesystem.read', 'filesystem.write'} if invocation.name == 'edit' else {
            'filesystem.write'} if invocation.name == 'write' else {'filesystem.read'}
        if not needed.issubset(ticket[2]):
            raise FilesystemError('PERMISSION_DENIED')
        self.external[key] = (*ticket[:3], True)
        return self.broker.prepare(ticket[1], invocation), True

    def execute(self, plan, grant, issuer):
        issuer.validate_claimed(grant, getattr(grant, 'request', None))
        request = grant.request
        if not request.filesystem_binding or dict(request.filesystem_binding) != dict(plan.binding):
            raise FilesystemError('REQUEST_MISMATCH')
        fs_caps = [cap for cap in request.capabilities if cap.permission.name.startswith('filesystem.')]
        if (not fs_caps or plan.binding['tool'] != request.tool_name
                or any(cap.control_class is not ControlClass.BROKER_ENFORCED for cap in fs_caps)):
            raise FilesystemError('PERMISSION_DENIED')
        needed = ('filesystem.read', 'filesystem.write') if request.tool_name == 'edit' else (
            'filesystem.write',) if request.tool_name == 'write' else ('filesystem.read',)
        style = PathStyle.WINDOWS if not request.workspace.startswith('/') else PathStyle.POSIX
        scope = ResourceScope(ScopeKind.FILE if request.tool_name in ('read', 'write', 'edit')
                              else ScopeKind.DIRECTORY_TREE, plan.binding['path'], style)
        for name in needed:
            if not any(cap.covers(Capability(Permission(name), scope, ControlClass.BROKER_ENFORCED)) for cap in fs_caps):
                raise FilesystemError('PERMISSION_DENIED')
        def guard():
            issuer.validate_claimed(grant, request)
        guard()
        plan.validate_current()
        return plan.execute(guard)

    def close(self):
        self.broker.close()
