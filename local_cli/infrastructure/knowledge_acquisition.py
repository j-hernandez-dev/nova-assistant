"""Explicit host-selected regular files; no tools, parsers or implicit refresh."""
import os
import stat
from pathlib import Path
from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode


class LocalHostFileAcquisition:
    def __init__(self, *, max_bytes=50*1024*1024, unit_bytes=256*1024):
        if not 0 < unit_bytes <= 1024*1024 or max_bytes < 0: raise ValueError('Invalid bounds')
        self.max_bytes, self.unit_bytes = max_bytes, unit_bytes

    def read(self, selected_path, *, cancelled, progress):
        # Fresh explicit host selection, not S3 workspace mediation. Fail closed
        # on redirects/reparse/hardlinks and object replacement. This is not OS
        # sandboxing or protection against an adversarial host process.
        try:
            if not isinstance(selected_path, str) or '\x00' in selected_path:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
            path = Path(selected_path)
            if not path.is_absolute(): raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
            def check_path():
                for part in (path, *path.parents):
                    info = part.lstat()
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                        raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
                return path.lstat()
            before = check_path()
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
            if before.st_size > self.max_bytes: raise KnowledgeError(KnowledgeErrorCode.SOURCE_TOO_LARGE)
            if cancelled(): raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            with os.fdopen(os.open(path, flags), 'rb') as stream:
                opened = os.fstat(stream.fileno())
                # On this Windows/Python host lstat exposes creation time as
                # ctime whereas fstat exposes a different timestamp. Compare
                # object ID/size/mtime across APIs, and ctime within the same
                # handle API below. Do not reject an unchanged regular file.
                signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
                if signature(before) != signature(opened) or not stat.S_ISREG(opened.st_mode):
                    raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
                size = 0
                while True:
                    if cancelled(): raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
                    block = stream.read(self.unit_bytes)
                    if not block: break
                    size += len(block)
                    if size > self.max_bytes: raise KnowledgeError(KnowledgeErrorCode.SOURCE_TOO_LARGE)
                    progress(size)
                    yield block
                if cancelled(): raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
                after = os.fstat(stream.fileno())
                if (signature(opened) != signature(after) or opened.st_ctime_ns != after.st_ctime_ns
                        or signature(opened) != signature(check_path()) or after.st_nlink != 1):
                    raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
        except KnowledgeError: raise
        except (OSError, ValueError):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED) from None
