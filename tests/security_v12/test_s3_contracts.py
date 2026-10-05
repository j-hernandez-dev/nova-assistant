"""S3 portable unit/contract checks; do not call the Windows filesystem."""
import pytest

from local_cli.core.filesystem import FilesystemError
from local_cli.infrastructure.windows_filesystem import absolute_path, component


@pytest.mark.parametrize('name', ['..', 'CON', 'nul.txt', 'COM¹', 'a:b', 'a.', 'a ',
                                  'a/b', 'x\\y', 'SHORT~1', '\x00bad', '?', ''])
def test_unsupported_component_has_typed_error(name):
    with pytest.raises(FilesystemError, match='FILESYSTEM_PATH_UNSUPPORTED'):
        component(name)


@pytest.mark.parametrize('path', ['\\\\server\\share\\x', '\\\\?\\C:\\x', '\\\\.\\C:',
                                  'C:relative', '\\rooted', '../outside', 'x:stream'])
def test_unsupported_paths_have_no_implicit_namespace(path):
    with pytest.raises(FilesystemError):
        absolute_path(path, 'C:\\workspace')


def test_case_and_dot_cwd_spelling_are_lexical_not_object_evidence():
    assert absolute_path('./src/file.txt', 'C:\\Workspace') == 'C:\\Workspace\\src\\file.txt'
    assert absolute_path('.', 'C:\\Workspace') == 'C:\\Workspace'
