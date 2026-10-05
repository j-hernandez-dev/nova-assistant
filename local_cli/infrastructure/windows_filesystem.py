"""Windows NTFS handle-relative mediation. Never used by shell processes.

No path-based read/write fallback. Reparse, streams, devices, UNC, short aliases,
case-sensitive directories and non-NTFS volumes are unsupported. Active ancestry
handles deny write/delete sharing; an idle root lease permits rename but prevents
file-ID reuse, and every request reopens/checks the configured root identity.
"""
from contextlib import ExitStack
from pathlib import Path, PureWindowsPath
import ctypes as c
import os
import re
import uuid

from local_cli.core.filesystem import FilesystemError, FilesystemRoot


U32, U16, I64, HANDLE = c.c_uint32, c.c_uint16, c.c_int64, c.c_void_p


class UnicodeString(c.Structure):
    _fields_ = [('Length', U16), ('MaximumLength', U16), ('Buffer', HANDLE)]


class ObjectAttributes(c.Structure):
    _fields_ = [('Length', U32), ('RootDirectory', HANDLE),
                ('ObjectName', c.POINTER(UnicodeString)), ('Attributes', U32),
                ('SecurityDescriptor', HANDLE), ('SecurityQualityOfService', HANDLE)]


class IoStatus(c.Structure):
    _fields_ = [('Status', HANDLE), ('Information', c.c_size_t)]


class FileInfo(c.Structure):
    _fields_ = [('attributes', U32), ('creationLow', U32), ('creationHigh', U32),
                ('accessLow', U32), ('accessHigh', U32), ('writeLow', U32),
                ('writeHigh', U32), ('volume', U32), ('sizeHigh', U32),
                ('sizeLow', U32), ('links', U32), ('indexHigh', U32), ('indexLow', U32)]


class DirectoryInfo(c.Structure):
    _fields_ = [('next', U32), ('index', U32), ('creation', I64), ('access', I64),
                ('write', I64), ('change', I64), ('size', I64), ('allocation', I64),
                ('attributes', U32), ('nameLength', U32), ('ea', U32),
                ('shortLength', c.c_int8), ('shortName', U16 * 12),
                ('id', I64), ('name', U16 * 1)]


class RenameInfo(c.Structure):
    _fields_ = [('replace', U32), ('root', HANDLE), ('length', U32), ('name', U16 * 1)]


def component(name):
    if (not isinstance(name, str) or not name or name in ('.', '..')
            or name.endswith(('.', ' ')) or any(ord(ch) < 32 for ch in name)
            or any(ch in name for ch in '\\/:*?<>|"~')
            or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)', name)):
        raise FilesystemError('FILESYSTEM_PATH_UNSUPPORTED')
    return name


def absolute_path(raw, cwd=None):
    if not isinstance(raw, str) or not raw.strip():
        raise FilesystemError('INVALID_TOOL_ARGUMENTS')
    text = raw.replace('/', '\\')
    if text.startswith('\\') or (':' in text and not re.match(r'^[A-Za-z]:\\', text)):
        raise FilesystemError('FILESYSTEM_PATH_UNSUPPORTED')
    if not re.match(r'^[A-Za-z]:\\', text):
        if cwd is None:
            raise FilesystemError('FILESYSTEM_PATH_UNSUPPORTED')
        text = str(cwd).rstrip('\\/') + '\\' + text
    parts = text[3:].split('\\')
    # Explicit './' is the conventional relative cwd, never accept '..'.
    parts = [p for p in parts if p not in ('', '.')]
    for part in parts:
        component(part)
    return str(PureWindowsPath(text[:3], *parts))


class Handle:
    def __init__(self, api, value):
        self.api, self.value = api, value
    def close(self):
        if self.value is not None:
            value, self.value = self.value, None
            self.api.kernel.CloseHandle(value)
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.close()
    def __del__(self):
        self.close()


class WindowsApi:
    def __init__(self):
        if os.name != 'nt':
            raise FilesystemError('FILESYSTEM_PLATFORM_UNSUPPORTED')
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.nt = c.WinDLL('ntdll')
        specs = [
            ('CreateFileW', [c.c_wchar_p, U32, U32, HANDLE, U32, U32, HANDLE], HANDLE),
            ('CloseHandle', [HANDLE], c.c_int),
            ('GetFileInformationByHandle', [HANDLE, c.POINTER(FileInfo)], c.c_int),
            ('GetFileInformationByHandleEx', [HANDLE, c.c_int, HANDLE, U32], c.c_int),
            ('GetFinalPathNameByHandleW', [HANDLE, c.c_wchar_p, U32, U32], U32),
            ('GetVolumeInformationByHandleW', [HANDLE, c.c_wchar_p, U32, HANDLE,
                 HANDLE, HANDLE, c.c_wchar_p, U32], c.c_int),
            ('ReadFile', [HANDLE, HANDLE, U32, c.POINTER(U32), HANDLE], c.c_int),
            ('WriteFile', [HANDLE, HANDLE, U32, c.POINTER(U32), HANDLE], c.c_int),
            ('FlushFileBuffers', [HANDLE], c.c_int),
            ('SetFileInformationByHandle', [HANDLE, c.c_int, HANDLE, U32], c.c_int),
        ]
        for name, args, result in specs:
            fn = getattr(self.kernel, name); fn.argtypes = args; fn.restype = result
        self.nt.NtCreateFile.argtypes = [c.POINTER(HANDLE), U32, c.POINTER(ObjectAttributes),
                    c.POINTER(IoStatus), HANDLE, U32, U32, U32, U32, HANDLE, U32]
        self.nt.NtCreateFile.restype = c.c_int32
        self.nt.NtSetInformationFile.argtypes = [HANDLE, c.POINTER(IoStatus), HANDLE, U32, c.c_int]
        self.nt.NtSetInformationFile.restype = c.c_int32
        self.nt.RtlNtStatusToDosError.argtypes = [c.c_int32]
        self.nt.RtlNtStatusToDosError.restype = U32

    @staticmethod
    def fail(error=None):
        number = c.get_last_error() if error is None else error
        if number in (2, 3):
            raise FileNotFoundError(number, 'filesystem object unavailable')
        if number in (5, 32, 33):
            raise FilesystemError('FILESYSTEM_ACCESS_CONFLICT')
        raise FilesystemError('FILESYSTEM_OPERATION_FAILED') from OSError(number, 'Windows operation failed')

    def drive(self, drive, *, share=1):
        h = self.kernel.CreateFileW(drive, 0x100081, share, None, 3,
                                     0x02200000, None)
        if h in (None, c.c_void_p(-1).value):
            self.fail()
        result = Handle(self, h)
        try:
            fs = c.create_unicode_buffer(32)
            if not self.kernel.GetVolumeInformationByHandleW(h, None, 0, None,
                    None, None, fs, len(fs)) or fs.value != 'NTFS':
                raise FilesystemError('FILESYSTEM_VOLUME_UNSUPPORTED')
            self.checked(result, directory=True)
            return result
        except BaseException:
            result.close(); raise

    def open(self, parent, name, *, directory=None, create=False, share=1,
             read=False, write=False, delete=False):
        component(name)
        buf = c.create_unicode_buffer(name)
        us = UnicodeString(len(name.encode('utf-16-le')), len(name.encode('utf-16-le'))+2,
                           c.cast(buf, HANDLE))
        oa = ObjectAttributes(c.sizeof(ObjectAttributes), parent.value, c.pointer(us),
                              0x40, None, None)
        handle, status = HANDLE(), IoStatus()
        access = 0x100080 | (1 if read or directory else 0) | (2 if write else 0) | (0x10000 if delete else 0)
        options = 0x200020 | (1 if directory is True else 0x40 if directory is False else 0)
        disposition = (3 if directory else 2) if create else 1
        code = self.nt.NtCreateFile(c.byref(handle), access, c.byref(oa), c.byref(status),
                    None, 0x80, share, disposition, options, None, 0)
        if code < 0:
            self.fail(self.nt.RtlNtStatusToDosError(code))
        result = Handle(self, handle.value)
        try:
            self.checked(result, directory=directory)
            # The normalized name must be the requested long entry name, not 8.3.
            if PureWindowsPath(self.final_path(result)).name.casefold() != name.casefold():
                raise FilesystemError('FILESYSTEM_ALIAS_UNSUPPORTED')
            return result
        except BaseException:
            result.close(); raise

    def info(self, handle):
        info = FileInfo()
        if not self.kernel.GetFileInformationByHandle(handle.value, c.byref(info)):
            self.fail()
        return info

    def checked(self, handle, *, directory=None):
        info = self.info(handle)
        if info.attributes & 0x400:
            raise FilesystemError('FILESYSTEM_REPARSE_DENIED')
        is_dir = bool(info.attributes & 0x10)
        if directory is not None and is_dir != directory:
            raise FilesystemError('FILESYSTEM_TYPE_MISMATCH')
        if not is_dir and info.links != 1:
            raise FilesystemError('FILESYSTEM_HARDLINK_DENIED')
        if is_dir:
            flags = U32()
            if not self.kernel.GetFileInformationByHandleEx(handle.value, 23, c.byref(flags), 4):
                raise FilesystemError('FILESYSTEM_CASE_MODE_UNSUPPORTED')
            if flags.value & 1:
                raise FilesystemError('FILESYSTEM_CASE_MODE_UNSUPPORTED')
        return info

    def identity(self, handle):
        i = self.info(handle)
        return f'{i.volume:08x}:{i.indexHigh:08x}{i.indexLow:08x}'

    def snapshot(self, handle):
        i = self.checked(handle)
        return {'identity': self.identity(handle), 'size': (i.sizeHigh << 32) | i.sizeLow,
                'write': (i.writeHigh << 32) | i.writeLow, 'attributes': i.attributes}

    def final_path(self, handle):
        buf = c.create_unicode_buffer(32768)
        length = self.kernel.GetFinalPathNameByHandleW(handle.value, buf, len(buf), 0)
        if not length or length >= len(buf) or not buf.value.startswith('\\\\?\\'):
            raise FilesystemError('FILESYSTEM_ALIAS_UNSUPPORTED')
        return buf.value[4:]

    def chain(self, path, stack):
        parts = PureWindowsPath(absolute_path(path)).parts
        h = stack.enter_context(self.drive(parts[0]))
        for name in parts[1:]:
            h = stack.enter_context(self.open(h, name, directory=True))
        if self.final_path(h).rstrip('\\').casefold() != str(path).rstrip('\\').casefold():
            raise FilesystemError('FILESYSTEM_ALIAS_UNSUPPORTED')
        return h

    def read(self, handle, guard=lambda: None):
        chunks, buffer = [], c.create_string_buffer(65536)
        while True:
            guard()
            count = U32()
            if not self.kernel.ReadFile(handle.value, buffer, len(buffer), c.byref(count), None):
                self.fail()
            if not count.value:
                return b''.join(chunks)
            chunks.append(buffer.raw[:count.value])

    def entries(self, handle):
        buffer = c.create_string_buffer(65536)
        restart = True
        while True:
            if not self.kernel.GetFileInformationByHandleEx(handle.value, 11 if restart else 10,
                    buffer, len(buffer)):
                if c.get_last_error() == 18:
                    return
                self.fail()
            restart = False
            offset = 0
            while True:
                record = DirectoryInfo.from_buffer_copy(buffer.raw[offset:offset+c.sizeof(DirectoryInfo)])
                begin = offset + DirectoryInfo.name.offset
                name = buffer.raw[begin:begin+record.nameLength].decode('utf-16-le')
                if name not in ('.', '..'):
                    yield name, record.attributes, record.write
                if not record.next:
                    break
                offset += record.next

    def atomic_write(self, parent, name, content, guard=lambda: None):
        guard()
        temp_name = '.nova-s3-' + uuid.uuid4().hex + '.tmp'
        temp = self.open(parent, temp_name, directory=False, create=True, write=True, delete=True)
        committed = False
        try:
            data = content.encode('utf-8')
            for start in range(0, len(data), 65536):
                guard()
                chunk = data[start:start+65536]; count = U32()
                if not self.kernel.WriteFile(temp.value, chunk, len(chunk), c.byref(count), None) or count.value != len(chunk):
                    self.fail()
            if not self.kernel.FlushFileBuffers(temp.value):
                self.fail()
            encoded = name.encode('utf-16-le')
            buffer = c.create_string_buffer(c.sizeof(RenameInfo) + len(encoded))
            rename = RenameInfo.from_buffer(buffer)
            # A simple name with NULL RootDirectory means rename in the SOURCE
            # handle's own directory (not process cwd). This avoids reopening
            # the pinned directory for write through IopOpenLinkOrRenameTarget.
            rename.replace, rename.root, rename.length = 1, None, len(encoded)
            c.memmove(c.addressof(buffer)+RenameInfo.name.offset, encoded, len(encoded))
            status = IoStatus()
            identity = self.identity(temp)
            guard()
            code = self.nt.NtSetInformationFile(temp.value, c.byref(status), buffer, len(buffer), 10)
            if code < 0:
                self.fail(self.nt.RtlNtStatusToDosError(code))
            committed = True
            return identity
        finally:
            if not committed:
                delete = c.c_ubyte(1)
                if not self.kernel.SetFileInformationByHandle(temp.value, 4, c.byref(delete), 1):
                    temp.close()
                    raise FilesystemError('FILESYSTEM_TEMP_CLEANUP_UNKNOWN', effect='unknown')
            temp.close()


class WindowsFilesystemBroker:
    def __init__(self):
        self.api = WindowsApi()
        self._leases = {}

    def bind_root(self, path):
        logical = absolute_path(str(path))
        with ExitStack() as stack:
            root = self.api.chain(logical, stack)
            parts = PureWindowsPath(logical).parts
            # Lease the same object without denying delete sharing while idle.
            if len(parts) == 1:
                lease = self.api.drive(parts[0], share=7)
            else:
                parent = self.api.chain(str(PureWindowsPath(*parts[:-1])), stack)
                lease = self.api.open(parent, parts[-1], directory=True, share=7)
            identity = self.api.identity(root)
            if identity != self.api.identity(lease):
                lease.close(); raise FilesystemError('FILESYSTEM_RESOURCE_CHANGED')
        prior = self._leases.setdefault((logical.casefold(), identity), lease)
        if prior is not lease:
            lease.close()
        return FilesystemRoot(logical, identity)

    def prepare(self, root, invocation):
        from local_cli.infrastructure.filesystem_plan import WindowsFilesystemPlan
        if (root.path.casefold(), root.identity) not in self._leases:
            raise FilesystemError('FILESYSTEM_ROOT_UNKNOWN')
        return WindowsFilesystemPlan(self.api, root, invocation)

    def close(self):
        for lease in self._leases.values():
            lease.close()
        self._leases.clear()

    def __del__(self):
        if hasattr(self, '_leases'):
            self.close()
