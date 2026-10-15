"""Owned JSONL segments. Local durability, NOT OS tamper resistance/isolation.

Each live segment has a native advisory writer lock; another backend never
purges it. Orphan segments are synced and sealed on reopen, without modifying
their bytes (including damaged tails). Readers admit complete validated rows
only and return diagnostics, never synthetic execution outcomes.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from threading import RLock
from uuid import uuid4

from local_cli.core.security_audit import SecurityAuditError, SecurityAuditRecord


OWNER = 'nova-security-audit-v1'
SEGMENT = re.compile(r'^nova-audit-([0-9a-f]{32})\.(active|closed)\.jsonl$')


def _lock(stream):
    stream.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream):
    stream.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class JsonlSecurityAudit:
    def __init__(self, directory, *, workspace=None, segment_bytes=10*1024*1024,
                 retention_bytes=100*1024*1024, retention_days=30, clock=None):
        self.directory = Path(directory).absolute()
        self.workspace = Path(workspace).resolve() if workspace is not None else None
        if (type(segment_bytes) is not int or segment_bytes < 1024
                or type(retention_bytes) is not int or retention_bytes < segment_bytes
                or type(retention_days) is not int or retention_days < 1):
            raise SecurityAuditError('SECURITY_AUDIT_CONFIG_INVALID')
        self.segment_bytes, self.retention_bytes = segment_bytes, retention_bytes
        self.retention_days = retention_days
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._mutex = RLock()
        self._stream = self._lease = self._active = None
        self._size = 0
        self._failed = False
        self._closed = False
        self.gaps = []

    def _gap(self, code, path=None, offset=None):
        item = {'code': code, 'segment': path.name if path else None, 'offset': offset}
        if item not in self.gaps:
            self.gaps.append(item)

    def _check_directory(self):
        for part in (self.directory, *self.directory.parents):
            if part.exists():
                info = part.lstat()
                if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0)
                        & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                    raise SecurityAuditError('SECURITY_AUDIT_PATH_UNSAFE')
        if self.workspace and self.directory.resolve().is_relative_to(self.workspace):
            raise SecurityAuditError('SECURITY_AUDIT_INSIDE_WORKSPACE')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def validate_workspace(self, workspace):
        # Called again at admission, including after host workspace rebinding.
        if self.directory.resolve().is_relative_to(Path(workspace).resolve()):
            raise SecurityAuditError('SECURITY_AUDIT_INSIDE_WORKSPACE')

    @staticmethod
    def _regular(path):
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_nlink == 1

    def _open_lock(self, path):
        # Persistent tiny coordination files contain no records or secrets.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            if not self._regular(path):
                raise SecurityAuditError('SECURITY_AUDIT_PATH_UNSAFE')
            fd = os.open(path, os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
        stream = os.fdopen(fd, 'r+b', buffering=0)
        try:
            if os.fstat(fd).st_size == 0:
                stream.write(b'0')
            _lock(stream)
            return stream
        except BaseException:
            stream.close()
            raise

    @contextmanager
    def _transaction(self):
        self._check_directory()
        try:
            lease = self._open_lock(self.directory/'rotation.lock')
        except OSError:
            raise SecurityAuditError('SECURITY_AUDIT_WRITER_BUSY') from None
        try:
            yield
        finally:
            _unlock(lease)
            lease.close()

    def _segments(self):
        result = []
        for path in sorted(self.directory.iterdir()):
            match = SEGMENT.fullmatch(path.name)
            if not match:
                continue
            try:
                if not self._regular(path):
                    self._gap('AUDIT_UNSAFE_SEGMENT_IGNORED', path)
                    continue
                with path.open('rb') as stream:
                    row = stream.readline(1025)
                header = json.loads(row)
                if (not row.endswith(b'\n') or set(header) != {'owner','version','segmentId','createdAt'}
                        or header['owner'] != OWNER or header['version'] != 1
                        or header['segmentId'] != match[1]):
                    continue  # Not an owned segment: never purge it.
                created = datetime.fromisoformat(header['createdAt'])
                if created.tzinfo is None:
                    continue
                result.append((path, match[2], created, path.stat().st_size))
            except (OSError, ValueError, TypeError, KeyError):
                self._gap('AUDIT_INVALID_SEGMENT_HEADER', path)
        return result

    def _sync_directory(self):
        # POSIX can additionally sync rename/create metadata. Windows fsync
        # acknowledges file buffers only; no claim against power-loss hardware.
        if os.name != 'nt':
            fd = os.open(self.directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def _recover(self):
        for path, state, _, _ in self._segments():
            if state != 'active' or path == self._active:
                continue
            try:
                lease = self._open_lock(path.with_suffix('.lease'))
            except OSError:
                continue  # Live writer: neither close nor purge its active file.
            try:
                with path.open('r+b') as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
                path.rename(path.with_name(path.name.replace('.active.', '.closed.')))
                self._sync_directory()
                self._gap('AUDIT_UNCLEAN_SEGMENT_RECOVERED', path)
            finally:
                _unlock(lease)
                lease.close()

    def _new_segment(self):
        ident = uuid4().hex
        path = self.directory/f'nova-audit-{ident}.active.jsonl'
        lease = self._open_lock(path.with_suffix('.lease'))
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            stream = os.fdopen(fd, 'wb')
            header = {'owner': OWNER, 'version': 1, 'segmentId': ident,
                      'createdAt': self._clock().isoformat()}
            row = json.dumps(header, separators=(',', ':')).encode('utf-8')+b'\n'
            stream.write(row)
            stream.flush()
            os.fsync(stream.fileno())
            self._sync_directory()
        except BaseException:
            _unlock(lease); lease.close()
            if 'stream' in locals():
                stream.close()
            raise
        self._stream, self._active, self._lease = stream, path, lease
        self._size = len(row)

    def _seal(self):
        if self._stream is None:
            return
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._stream.close()
        self._stream = None
        self._active.rename(self._active.with_name(self._active.name.replace('.active.', '.closed.')))
        self._sync_directory()
        _unlock(self._lease); self._lease.close()
        self._lease = self._active = None

    def _retain(self, reserve=0):
        segments = self._segments()
        total = sum(s[3] for s in segments)
        now = self._clock()
        removed = False
        for path, state, created, size in sorted(segments, key=lambda s: (s[2], s[0].name)):
            if state != 'closed':
                continue
            if (now-created).total_seconds() < self.retention_days*86400 and total+reserve <= self.retention_bytes:
                continue
            # Recheck the exact target and ownership before deleting it. Never
            # recurse; no user files, historical fixtures or active segments.
            if not self._regular(path) or not any(s[0] == path and s[1] == 'closed' for s in self._segments()):
                raise SecurityAuditError('SECURITY_AUDIT_PATH_UNSAFE')
            path.unlink()
            removed = True
            total -= size
            self._gap('AUDIT_RETENTION_GAP', path)
        if total+reserve > self.retention_bytes:
            self._gap('AUDIT_RETENTION_ACTIVE_CAPACITY')
            raise SecurityAuditError('SECURITY_AUDIT_RETENTION_CAPACITY')
        if removed:
            self._sync_directory()

    def append(self, record):
        with self._mutex:
            if self._failed or self._closed:
                raise SecurityAuditError('SECURITY_AUDIT_UNAVAILABLE')
            try:
                row = json.dumps(SecurityAuditRecord.from_dict(record.to_dict()).to_dict(),
                    ensure_ascii=False, separators=(',', ':')).encode('utf-8')+b'\n'
                if len(row)+256 > self.segment_bytes:
                    raise SecurityAuditError('AUDIT_RECORD_TOO_LARGE')
                with self._transaction():
                    self._recover()
                    if self._stream is not None and self._size+len(row) > self.segment_bytes:
                        self._seal()
                    self._retain(reserve=len(row)+(256 if self._stream is None else 0))
                    if self._stream is None:
                        self._new_segment()
                    self._stream.write(row)
                    self._stream.flush()  # Visibility, no fsync for each internal event.
                    self._size += len(row)
                    self._retain()
            except Exception:
                self._failed = True
                raise SecurityAuditError('SECURITY_AUDIT_WRITE_FAILED') from None

    def flush(self):
        with self._mutex:
            if self._failed or self._closed or self._stream is None:
                raise SecurityAuditError('SECURITY_AUDIT_UNAVAILABLE')
            try:
                self._stream.flush()
                os.fsync(self._stream.fileno())
            except Exception:
                self._failed = True
                raise SecurityAuditError('SECURITY_AUDIT_SYNC_FAILED') from None

    def close(self):
        with self._mutex:
            try:
                if self._stream is not None:
                    with self._transaction():
                        self._seal()
                        self._retain()
            except Exception:
                self._failed = True
                raise SecurityAuditError('SECURITY_AUDIT_CLOSE_FAILED') from None
            finally:
                if self._stream is not None:
                    self._stream.close(); self._stream = None
                if self._lease is not None:
                    _unlock(self._lease); self._lease.close(); self._lease = None
                self._closed = True

    def read_operation(self, session_id, operation_id):
        with self._mutex:
            with self._transaction():
                self._recover()
                self._retain()
                records = []
                sequences = {}
                for path, _, _, _ in self._segments():
                    with path.open('rb') as stream:
                        stream.readline(1025)
                        while True:
                            offset = stream.tell()
                            row = stream.readline(65538)
                            if not row:
                                break
                            if not row.endswith(b'\n'):
                                while row and not row.endswith(b'\n'):
                                    row = stream.readline(65538)
                                self._gap('AUDIT_INCOMPLETE_OR_OVERSIZED_ROW', path, offset)
                                continue
                            try:
                                record = SecurityAuditRecord.from_dict(json.loads(row))
                            except (ValueError, TypeError, UnicodeError):
                                self._gap('AUDIT_INVALID_ROW', path, offset)
                                continue
                            sequences.setdefault(record.audit_stream_id, set()).add(record.audit_sequence)
                            if record.session_id == session_id and record.operation_id == operation_id:
                                records.append(record)
                ordered = sorted(records, key=lambda r: (r.audit_stream_id, r.audit_sequence))
                seen = set()
                for numbers in sequences.values():
                    previous = 0
                    for number in sorted(numbers):
                        if number != previous+1:
                            self._gap('AUDIT_SEQUENCE_GAP')
                        previous = number
                for record in ordered:
                    key = (record.audit_stream_id, record.audit_sequence)
                    if key in seen:
                        self._gap('AUDIT_DUPLICATE_SEQUENCE')
                    seen.add(key)
                if not any(r.kind.value in ('terminal', 'agent_terminal') for r in ordered):
                    self._gap('AUDIT_TERMINAL_NOT_OBSERVED')
                if ordered and not any(r.kind.value in ('request', 'agent_started') for r in ordered):
                    self._gap('AUDIT_REQUEST_NOT_OBSERVED')
                return tuple(ordered)
