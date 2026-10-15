"""Exact upload snapshots and retained, owned downloads. Neither is a Grant."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from local_cli.core.browser import BrowserActionError

MAX_BYTES = 32 * 1024 * 1024


class BrowserFiles:
    def __init__(self, root, snapshotter=None):
        self.root = Path(root).expanduser().resolve()
        if snapshotter is None:
            from local_cli.infrastructure.browser.files import snapshot_file
            snapshotter = snapshot_file
        self.snapshotter = snapshotter
        self.selected = {}

    def select(self, path, owner):
        path = Path(path).expanduser().absolute()
        _, metadata = self.snapshotter(path)
        ref = 'file_' + uuid4().hex
        self.selected[ref] = (owner, path, metadata, time.monotonic() + 300)
        return {'fileRef': ref, 'name': metadata['name'], 'size': metadata['size'], 'digest': metadata['digest'], 'expiresInSeconds': 300}

    def upload(self, args, context):
        owner = (context.session_id, str(context.workspace))
        if bool(args.get('file_ref')) == bool(args.get('file_path')):
            raise BrowserActionError('INVALID_UPLOAD_SOURCE', 'Supply exactly one file_path or host-selected file_ref.')
        if args.get('file_ref'):
            selected = self.selected.get(args['file_ref'])
            if selected is None or selected[0] != owner or selected[3] <= time.monotonic():
                raise BrowserActionError('BROWSER_FILE_REF_STALE', 'Select the upload file again with /browser file <path>.')
            path = selected[1]
        else:
            path = Path(args['file_path']).expanduser()
            path = path if path.is_absolute() else context.cwd / path
            if not path.is_relative_to(context.workspace) or '..' in path.parts:
                raise BrowserActionError('BROWSER_UPLOAD_OUTSIDE_WORKSPACE', 'For a file outside the workspace, explicitly select it with /browser file <path>.')
            selected = None
        data, metadata = self.snapshotter(path)
        if selected is not None and metadata != selected[2]:
            raise BrowserActionError('BROWSER_UPLOAD_CHANGED', 'The selected upload file changed. Select it again.')
        return data, metadata

    def consumed(self, args):
        if args.get('file_ref'): self.selected.pop(args['file_ref'], None)

    def allocate(self, context, url):
        self.root.mkdir(parents=True, exist_ok=True)
        operation = uuid4().hex
        folder = self.root / ('download_' + operation)
        folder.mkdir()
        return {'operation': operation, 'folder': folder, 'part': folder / 'payload.part',
                'owner': str(context.workspace), 'session': context.session_id, 'url': url}

    def complete(self, ticket, engine):
        path = ticket['part']
        if (engine.get('state') != 'COMPLETE' or not path.is_file() or path.is_symlink()
                or path.resolve() != path or path.stat().st_size > MAX_BYTES
                or path.stat().st_size != engine.get('received')):
            raise BrowserActionError('BROWSER_DOWNLOAD_UNCONFIRMED', 'The browser did not confirm a complete bounded download.', started=True)
        size = path.stat().st_size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        final = ticket['folder'] / 'payload.bin'
        path.rename(final)
        receipt = {'downloadId': ticket['operation'], 'state': 'COMPLETE', 'owner': ticket['owner'],
                   'session': ticket['session'], 'url': ticket['url'], 'size': size, 'digest': digest,
                   'mime': str(engine.get('mime', ''))[:160], 'path': str(final), 'retained': True,
                   'createdAt': datetime.now(timezone.utc).isoformat(),
                   'expiresAt': (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()}
        with (ticket['folder'] / 'receipt.json').open('x', encoding='utf-8') as stream: json.dump(receipt, stream)
        return receipt

    def discard_partial(self, ticket):
        folder = ticket['folder']
        if folder.parent != self.root or folder.resolve() != folder: return False
        try:
            # Only fixed owned filenames; no recursive deletion of remote paths.
            for name in ('payload.part', 'payload.bin'):
                (folder / name).unlink(missing_ok=True)
            folder.rmdir()
            return True
        except OSError: return False

    def downloads(self, workspace):
        result = []
        if not self.root.is_dir(): return result
        for folder in sorted(self.root.glob('download_*'))[:100]:
            try:
                if folder.resolve() != folder or folder.is_symlink(): continue
                raw = folder / 'receipt.json'
                if raw.stat().st_size > 16384: continue
                value = json.loads(raw.read_text(encoding='utf-8'))
                if value.get('owner') != str(workspace) or folder.name != 'download_' + value['downloadId']: continue
                path = folder / 'payload.bin'
                value['path'] = str(path)
                if (not path.is_file() or path.is_symlink() or path.stat().st_size != value['size']
                        or path.stat().st_size > MAX_BYTES or hashlib.sha256(path.read_bytes()).hexdigest() != value['digest']):
                    value['state'] = 'LOST_OR_CHANGED'
                elif datetime.now(timezone.utc) >= datetime.fromisoformat(value['expiresAt']): value['state'] = 'EXPIRED'
                result.append(value)
            except (OSError, ValueError, KeyError, TypeError): continue
        return result

    def discard(self, download_id, workspace):
        if not isinstance(download_id, str) or len(download_id) != 32 or any(c not in '0123456789abcdef' for c in download_id):
            raise BrowserActionError('INVALID_DOWNLOAD_ID', 'Use a downloadId from /browser downloads.')
        if not any(r['downloadId'] == download_id for r in self.downloads(workspace)):
            raise BrowserActionError('DOWNLOAD_NOT_OWNED', 'That retained download is not owned by this workspace.')
        folder = self.root / ('download_' + download_id)
        if folder.resolve() != folder: raise BrowserActionError('DOWNLOAD_NOT_OWNED', 'The download location changed.')
        (folder / 'payload.bin').unlink(missing_ok=True)
        (folder / 'receipt.json').unlink()
        folder.rmdir()
        return {'downloadId': download_id, 'state': 'DISCARDED'}
