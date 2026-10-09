"""Owned Knowledge artifacts, not a model filesystem tool or an S3 claim.

Only Nova-generated flat IDs are accepted. No origin/locator/metadata paths are
opened. Reject reparse points, links, nonregular files and hard-linked artifacts;
validate again after open. This is not OS/process isolation and makes no claim
against a hostile same-user process concurrently replacing trusted state.
"""
import os
from pathlib import Path
import re
import stat

from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode


UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
OP = r'op_[0-9a-f]{32}'


def denied():
    raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)


def plain(path, *, directory=False, missing=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return
        denied()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400
            or (not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1))
            or (directory and not stat.S_ISDIR(info.st_mode))):
        denied()
    return info


class KnowledgeFiles:
    def __init__(self, state_dir):
        state = Path(state_dir)
        if not state.is_absolute() or '..' in state.parts:
            denied()
        # Inspect lexical ancestry before resolve() can hide a junction/link.
        for part in reversed((state, *state.parents)):
            if part.exists() or part.is_symlink():
                plain(part, directory=True)
        state.mkdir(parents=True, exist_ok=True)
        self.root = state / 'knowledge' / 'v1'
        for part in (state / 'knowledge', self.root):
            plain(part, directory=True, missing=True)
            part.mkdir(exist_ok=True)
        self.identity = (self.root.stat().st_dev, self.root.stat().st_ino)
        for name in ('blobs', 'staging', 'cache'):
            path = self.root / name
            plain(path, directory=True, missing=True)
            path.mkdir(exist_ok=True)

    def path(self, area, key):
        patterns = {'blobs': UUID + r'\.bin', 'staging': OP + r'\.part',
                    'cache': UUID + r'\.[0-9a-f]{64}\.cache'}
        if area not in patterns or not isinstance(key, str) or not re.fullmatch(patterns[area], key):
            denied()
        self.check_root()
        folder = self.root / area
        plain(folder, directory=True)
        path = folder / key
        plain(path, missing=True)
        if path.resolve().parent != folder.resolve():
            denied()
        return path

    def check_root(self):
        for part in reversed((self.root, *self.root.parents)):
            info = plain(part, directory=True)
            if part == self.root and (info.st_dev, info.st_ino) != self.identity:
                denied()
        for suffix in ('', '-wal', '-shm', '-journal'):
            plain(self.root / ('knowledge.db' + suffix), missing=True)

    def open(self, area, key, *, write=False):
        path = self.path(area, key)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL if write else os.O_RDONLY
        flags |= getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags, 0o600)
        try:
            actual = os.fstat(fd)
            check = plain(path)
            if ((check.st_dev, check.st_ino) != (actual.st_dev, actual.st_ino)
                    or actual.st_nlink != 1 or not stat.S_ISREG(actual.st_mode)):
                denied()
            self.check_root()
            return os.fdopen(fd, 'wb' if write else 'rb')
        except BaseException:
            os.close(fd)
            raise

    def remove(self, area, key):
        path = self.path(area, key)
        if path.exists():
            path.unlink()

    def move_to_blob(self, operation_id, revision_id):
        src = self.path('staging', operation_id + '.part')
        dst = self.path('blobs', revision_id + '.bin')
        if dst.exists():
            denied()
        # A UUID is never reused, and the lifetime writer lease excludes Nova
        # peers. Bytes were fsynced before rename; DB publication comes after it.
        os.rename(src, dst)


class KnowledgeLease:
    """Single Nova owner: crash releases the OS lock; recovery cannot cancel peers."""
    def __init__(self, files):
        path = files.root / 'writer.lock'
        plain(path, missing=True)
        self.stream = path.open('a+b')
        try:
            plain(path)
            if path.stat().st_size == 0:
                self.stream.write(b'1')
                self.stream.flush()
            self.stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.stream.close()
            raise

    def close(self):
        if not self.stream.closed:
            self.stream.close()
