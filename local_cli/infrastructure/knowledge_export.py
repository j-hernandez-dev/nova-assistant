"""Explicit host export, not a filesystem tool/S3 or OS isolation claim."""
from pathlib import Path
import os
import tempfile
from local_cli.core.knowledge import KnowledgeError,KnowledgeErrorCode


def export_copy(data, selected_path, managed_root):
    """Atomic Save As to the exact desktop-native picker destination."""
    path=Path(selected_path)
    root=Path(managed_root).resolve()
    if not path.is_absolute() or path.resolve().is_relative_to(root):
        raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
    temporary=None
    try:
        for part in (path,*path.parents):
            if not part.exists() and part==path:continue
            info=part.lstat()
            if part.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        if path.exists() and (not path.is_file() or path.stat().st_nlink!=1):
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.nova-download-',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        temporary=None
    except KnowledgeError:raise
    except (OSError,ValueError,TypeError):
        raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED) from None
    finally:
        if temporary is not None:
            try:temporary.unlink()
            except OSError:pass


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
