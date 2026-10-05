"""A prepared S3 operation retains its root/ancestry and target handles."""
from contextlib import ExitStack
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import PureWindowsPath

from local_cli.core.filesystem import FilesystemError
from local_cli.core.security import _map, SecurityError
from local_cli.infrastructure.windows_filesystem import absolute_path


class WindowsFilesystemPlan:
    def __init__(self, api, root, invocation):
        invocation = replace(invocation, arguments=_map(dict(invocation.arguments)))
        self.api, self.root, self.invocation = api, root, invocation
        self.stack = ExitStack()
        self.closed = False
        self.created_parents = False
        self.target = None
        self.missing = ()
        try:
            args, ctx = invocation.arguments, invocation.context
            raw = args.get('file_path') if invocation.name in ('read', 'write', 'edit') else args.get('path', '.')
            self.path = absolute_path(raw, ctx.cwd)
            a, b = PureWindowsPath(root.path).parts, PureWindowsPath(self.path).parts
            if tuple(p.casefold() for p in b[:len(a)]) != tuple(p.casefold() for p in a):
                raise FilesystemError('RESOURCE_SCOPE_VIOLATION')
            self.root_handle = self.api.chain(root.path, self.stack)
            if self.api.identity(self.root_handle) != root.identity:
                raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')
            self.relative = b[len(a):]
            ancestry = [root.identity]
            self.parent = self.root_handle
            for index, part in enumerate(self.relative[:-1]):
                try:
                    self.parent = self.stack.enter_context(self.api.open(self.parent, part, directory=True))
                    ancestry.append(self.api.identity(self.parent))
                except FileNotFoundError:
                    if invocation.name != 'write':
                        raise FilesystemError('FILESYSTEM_NOT_FOUND') from None
                    self.missing = self.relative[index:-1]
                    break
            self.name = self.relative[-1] if self.relative else None
            if not self.relative:
                self.target = self.root_handle
            elif not self.missing:
                try:
                    self.target = self.stack.enter_context(self.api.open(self.parent, self.name,
                        read=invocation.name in ('read', 'edit', 'glob', 'grep')))
                except FileNotFoundError:
                    if invocation.name != 'write':
                        raise FilesystemError('FILESYSTEM_NOT_FOUND') from None
            self.target_snapshot = self.api.snapshot(self.target) if self.target else None
            if invocation.name in ('read', 'write', 'edit') and (
                    self.name is None or (self.target_snapshot and self.target_snapshot['attributes'] & 0x10)):
                raise FilesystemError('FILESYSTEM_TYPE_MISMATCH')
            if invocation.name == 'glob' and not self.target_snapshot['attributes'] & 0x10:
                raise FilesystemError('FILESYSTEM_TYPE_MISMATCH')
            self._binding = _map({'bindingVersion': 1, 'root': root.path.casefold(),
                'rootIdentity': root.identity, 'path': self.path.casefold(),
                'ancestry': tuple(ancestry), 'missingParents': tuple(self.missing),
                'target': self.target_snapshot, 'tool': invocation.name})
        except BaseException:
            self.close(); raise

    @property
    def binding(self):
        return self._binding

    def validate_current(self):
        if self.closed:
            raise FilesystemError('FILESYSTEM_PLAN_CLOSED')
        if self.api.identity(self.root_handle) != self.root.identity:
            raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')
        if self.missing:
            try:
                with self.api.open(self.parent, self.missing[0], directory=True):
                    raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')
            except FileNotFoundError:
                return
        if self.name is None:
            current = self.api.snapshot(self.root_handle)
            # Directory contents may change; the bound directory object may not.
            if current['identity'] != self.target_snapshot['identity']:
                raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')
            return
        try:
            with self.api.open(self.parent, self.name, share=7) as fresh:
                current = self.api.snapshot(fresh)
        except FileNotFoundError:
            current = None
        if self.target_snapshot and self.target_snapshot['attributes'] & 0x10:
            equal = current and current['identity'] == self.target_snapshot['identity']
        else:
            equal = current == self.target_snapshot
        if not equal:
            raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')

    def read(self, handle=None, guard=lambda: None):
        return self.api.read(handle or self.target, guard)

    def walk(self, *, recursive=True):
        def visit(directory, prefix):
            for name, attrs, timestamp in self.api.entries(directory):
                if attrs & 0x400:
                    raise FilesystemError('FILESYSTEM_REPARSE_DENIED')
                with self.api.open(directory, name, directory=bool(attrs & 0x10), read=True) as child:
                    yield prefix+(name,), child, bool(attrs & 0x10), timestamp
                    if recursive and attrs & 0x10:
                        yield from visit(child, prefix+(name,))
        yield from visit(self.target, ())

    def write(self, content, guard):
        guard()
        self.validate_current()
        for part in self.missing:
            guard()
            self.parent = self.stack.enter_context(self.api.open(self.parent, part, directory=True, create=True))
            self.created_parents = True
        # Replacement acts on the one directory ENTRY in the pinned parent,
        # never follows a leaf link. It is not a filesystem-wide CAS transaction.
        if self.target is not None:
            self.target.close()
        guard()
        return self.api.atomic_write(self.parent, self.name, content, guard)

    def execute(self, guard):
        from local_cli.infrastructure.filesystem_tools import execute_filesystem_tool
        ctx = self.invocation.context
        def live():
            guard()
            if ctx.cancellation_token.is_cancel_requested():
                raise FilesystemError('PROCESS_CANCELLED')
            if ctx.deadline and datetime.now(timezone.utc) >= ctx.deadline:
                raise FilesystemError('GRANT_EXPIRED')
        try:
            live()
            return execute_filesystem_tool(self, live)
        except SecurityError as exc:
            raise FilesystemError(exc.code.value, effect='partial' if self.created_parents else 'none') from None
        except FilesystemError as exc:
            if self.created_parents and exc.effect == 'none':
                raise FilesystemError(exc.code, effect='partial') from None
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            self.stack.close()
