"""Five public tool adapters over a prepared handle plan, no direct file I/O."""
from pathlib import PurePosixPath, PureWindowsPath
import fnmatch
import hashlib
import os
import re

from local_cli.core.contracts import EffectState, ToolResult, ToolStatus
from local_cli.core.filesystem import FilesystemError
from local_cli.tools.edit_tool import _not_found_error, _make_diff_output


def pattern(value):
    if not isinstance(value, str) or not value.strip():
        raise FilesystemError('INVALID_TOOL_ARGUMENTS')
    value = value.replace('\\', '/')
    if value.startswith('/') or ':' in value or '..' in value.split('/'):
        raise FilesystemError('FILESYSTEM_PATTERN_UNSUPPORTED')
    return value.removeprefix('./')


def matches(parts, value, *, anywhere=False):
    path = PurePosixPath(*parts)
    if anywhere and '/' not in value:
        return fnmatch.fnmatchcase(path.name.casefold(), value.casefold())
    return path.full_match(value, case_sensitive=False)


def display(plan, parts=()):
    raw = plan.invocation.arguments.get('file_path', plan.invocation.arguments.get('path', '.'))
    path = PureWindowsPath(plan.path, *parts)
    if PureWindowsPath(raw).is_absolute():
        return str(path)
    return str(path.relative_to(PureWindowsPath(plan.invocation.context.cwd)))


def text(raw):
    try:
        return raw.decode('utf-8'), False
    except UnicodeDecodeError:
        return raw.decode('latin-1'), True


def execute_filesystem_tool(plan, guard):
    name, args = plan.invocation.name, plan.invocation.arguments
    metadata = {'cached': False, 'filesystemControlClass': 'BROKER_ENFORCED',
                'filesystemRootIdentity': plan.root.identity}
    def result(body, *, applied=False, failed=False):
        return ToolResult(ToolStatus.FAILED if failed else ToolStatus.COMPLETED,
            EffectState.APPLIED if applied else EffectState.NONE,
            legacy_text=body, metadata=metadata)
    if name in ('read', 'edit'):
        guard()
        raw = plan.read(guard=guard)
        if name == 'read' and b'\0' in raw[:8192]:
            return result(f"Error: {args['file_path']} appears to be a binary file.", failed=True)
        content, latin = text(raw)
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        metadata['filesystemBeforeHash'] = hashlib.sha256(raw).hexdigest()
        if name == 'read':
            offset = max(1, args.get('offset', 1))
            lines = content.splitlines(); selected = lines[offset-1:]
            if args.get('limit') is not None:
                selected = selected[:max(1, args['limit'])]
            if not selected and lines:
                return result(f'Error: offset {offset} is beyond end of file ({len(lines)} lines).', failed=True)
            body = '\n'.join(f'{i:6d}\t{line}' for i, line in enumerate(selected, offset))
            if latin:
                body = f"[note: {args['file_path']} is not valid UTF-8; decoded as latin-1, some characters may be wrong]\n" + body
            return result(body)
        old, new = args['old_text'], args['new_text']
        if not old:
            return result("Error: 'old_text' must not be empty.", failed=True)
        if old == new:
            return result('Error: old_text and new_text are identical, so this edit changes nothing.', failed=True)
        count = content.count(old)
        if not count:
            normalized = content.replace('\r\n', '\n').replace('\r', '\n')
            norm_old = old.replace('\r\n', '\n').replace('\r', '\n')
            count = normalized.count(norm_old)
            if not count:
                return result(_not_found_error(args['file_path'], content, old), failed=True)
            content, old = normalized, norm_old
        output = content.replace(old, new) if args.get('replace_all', False) else content.replace(old, new, 1)
        body = _make_diff_output(args['file_path'], old, new, count if args.get('replace_all', False) else 1)
    elif name == 'write':
        output = args['content']
        body = f"Successfully wrote {len(output.encode('utf-8'))} bytes ({len(output.splitlines())} lines) to {args['file_path']}"
    elif name == 'glob':
        glob = pattern(args['pattern'])
        records = []
        for parts, handle, directory, timestamp in plan.walk(recursive='/' in glob or '**' in glob):
            guard()
            if matches(parts, glob):
                records.append((timestamp, display(plan, parts)))
        records.sort(key=lambda row: (-row[0], row[1]))
        return result('\n'.join(row[1] for row in records) if records else f"No files matched pattern: {args['pattern']}")
    elif name == 'grep':
        try:
            regex = re.compile(args['pattern'], re.IGNORECASE if args.get('case_insensitive') else 0)
        except re.error:
            return result('Error: invalid regex pattern.', failed=True)
        include = pattern(args['include']) if args.get('include') else None
        directory = bool(plan.target_snapshot['attributes'] & 0x10)
        files = plan.walk() if directory else [((), plan.target, False, 0)]
        rows = []
        for parts, handle, is_dir, timestamp in files:
            guard()
            if is_dir or (include and not matches(parts, include, anywhere=True)):
                continue
            raw = plan.read(handle, guard)
            if b'\0' in raw[:8192]:
                continue
            try:
                content = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
            for line_num, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    rows.append(f'{display(plan, parts)}:{line_num}:{line}')
                    if len(rows) >= 500:
                        return result('\n'.join(rows+['... truncated (500 matches shown)']))
        return result('\n'.join(rows) if rows else f"No matches found for pattern: {args['pattern']}")
    else:
        raise FilesystemError('FILESYSTEM_TOOL_UNSUPPORTED')
    committed_text = output.replace('\n', os.linesep)
    metadata['filesystemObjectIdentity'] = plan.write(committed_text, guard)
    metadata['filesystemAfterHash'] = hashlib.sha256(committed_text.encode('utf-8')).hexdigest()
    # Verify the exact bytes committed by this broker; no legacy pathname read.
    from local_cli.harness import verify_file_write
    metadata['verificationWarning'] = verify_file_write(name, dict(args), body, content=committed_text)
    return result(body, applied=True)
