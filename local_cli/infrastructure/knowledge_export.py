"""Explicit host export, not a filesystem tool/S3 or OS isolation claim."""
from pathlib import Path
import os
from local_cli.core.knowledge import KnowledgeError,KnowledgeErrorCode


def exporter(managed_root):
    root=Path(managed_root).resolve()
    def write(data,selected_path,cancelled):
        path=Path(selected_path)
        if not path.is_absolute() or path.resolve().is_relative_to(root) or path.exists() or path.is_symlink():
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        if cancelled():raise KnowledgeError(KnowledgeErrorCode.IMPORT_CANCELLED)
        started=False
        try:
            with path.open('xb') as stream:
                started=True
                for n in range(0,len(data),256*1024):
                    if cancelled():raise OSError('cancelled during export')
                    stream.write(data[n:n+256*1024])
                stream.flush();os.fsync(stream.fileno())
        except Exception:
            if started:
                from local_cli.core.knowledge_store import KnowledgeStorageError,StorageFailure
                raise KnowledgeStorageError(StorageFailure.FAILED,outcome_unknown=True) from None
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED) from None
    return write
