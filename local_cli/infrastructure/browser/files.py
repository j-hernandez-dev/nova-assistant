"""Bounded host file snapshots using the existing NTFS handle primitives."""
from contextlib import ExitStack
import hashlib
import mimetypes
from pathlib import Path

from local_cli.core.browser import BrowserActionError

MAX_BYTES = 32 * 1024 * 1024


def snapshot_file(path):
    from local_cli.infrastructure.windows_filesystem import WindowsApi, absolute_path
    api = WindowsApi()
    path = Path(absolute_path(str(path)))
    with ExitStack() as stack:
        parent = api.chain(str(path.parent), stack)
        source = stack.enter_context(api.open(parent, path.name, directory=False, read=True))
        before = api.snapshot(source)
        def bounded():
            if before['size'] > MAX_BYTES or api.snapshot(source) != before:
                raise BrowserActionError('BROWSER_UPLOAD_CHANGED', 'The upload file changed or exceeds 32 MiB. Select it again.')
        bounded()
        data = api.read(source, bounded)
        bounded()
        if len(data) != before['size']: raise BrowserActionError('BROWSER_UPLOAD_CHANGED', 'The upload file changed.')
        return data, {**before, 'digest': hashlib.sha256(data).hexdigest(), 'name': path.name,
                      'mime': mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}
