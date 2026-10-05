"""Characterize Core's existing host effects; passing is NOT enforcement.

Every real effect uses only pytest-owned temporary fixtures. No user data,
external network, provider inference, security backend or deprecated code.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from unittest.mock import Mock, patch

import pytest

from local_cli.tools import get_default_tools
from local_cli.tools.edit_tool import EditTool
from local_cli.tools.glob_tool import GlobTool
from local_cli.tools.grep_tool import GrepTool
from local_cli.tools.read_tool import ReadTool
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.web_fetch_tool import WebFetchTool
from local_cli.shell_executor import ShellDescriptor


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_public_base_tool_schemas_match_s0_snapshot(tmp_path):
    # A synthetic descriptor avoids running a shell merely to collect schemas.
    with patch('local_cli.tools.shell_tool.detect_shell', return_value=
               ShellDescriptor('fixture', 'bash', 'fixture', '0')), \
         patch('local_cli.tools.shell_tool.create_executor', return_value=Mock()):
        tools = get_default_tools(cwd=tmp_path)
    actual = {tool.name: tool.parameters for tool in tools}
    expected = json.loads(Path(__file__).with_name('s0_tool_schemas.json').read_text(encoding='utf-8'))
    assert actual == expected


@pytest.mark.parametrize('name', ['read', 'write', 'edit', 'glob', 'grep'])
def test_absolute_external_fixture_is_accessible_to_current_tools(tmp_path, name):
    workspace = tmp_path / 'workspace'
    outside = tmp_path / 'external_fixture'
    workspace.mkdir(); outside.mkdir()
    target = outside / 'note.txt'
    target.write_text('S0_DUMMY_ORIGINAL', encoding='utf-8')
    guard = outside / 'unrelated.txt'
    guard.write_text('S0_UNRELATED', encoding='utf-8')
    before = sha(guard)
    tools = {'read': ReadTool, 'write': WriteTool, 'edit': EditTool,
             'glob': GlobTool, 'grep': GrepTool}
    args = {
        'read': {'file_path': str(target)},
        'write': {'file_path': str(target), 'content': 'S0_DUMMY_NEW'},
        'edit': {'file_path': str(target), 'old_text': 'ORIGINAL', 'new_text': 'EDITED'},
        'glob': {'path': str(outside), 'pattern': 'note.txt'},
        'grep': {'path': str(outside), 'pattern': 'S0_DUMMY_ORIGINAL'},
    }
    result = tools[name](cwd=workspace).execute(**args[name])
    assert not result.startswith('Error:'), result
    if name == 'write':
        assert target.read_text(encoding='utf-8') == 'S0_DUMMY_NEW'
    elif name == 'edit':
        assert target.read_text(encoding='utf-8') == 'S0_DUMMY_EDITED'
    else:
        assert 'note.txt' in result if name == 'glob' else 'S0_DUMMY_ORIGINAL' in result
        assert target.read_text(encoding='utf-8') == 'S0_DUMMY_ORIGINAL'
    assert sha(guard) == before


@pytest.mark.parametrize('name', ['read', 'write', 'edit', 'glob', 'grep'])
def test_relative_traversal_is_rejected_without_fixture_mutation(tmp_path, name):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    target = tmp_path / 'external.txt'; target.write_text('S0_DUMMY', encoding='utf-8')
    before = sha(target)
    tool = {'read': ReadTool, 'write': WriteTool, 'edit': EditTool,
            'glob': GlobTool, 'grep': GrepTool}[name](cwd=workspace)
    args = ({'path': '..', 'pattern': '*'} if name == 'glob' else
            {'path': '..', 'pattern': 'S0_DUMMY'} if name == 'grep' else
            {'file_path': '../external.txt', 'content': 'NEW',
             'old_text': 'S0_DUMMY', 'new_text': 'NEW'})
    assert 'path rejected' in tool.execute(**args)
    assert sha(target) == before


def test_web_fetch_file_scheme_reads_only_an_artificial_fixture(tmp_path):
    target = tmp_path / 'web.txt'; target.write_text('S0_FILE_SCHEME', encoding='utf-8')
    before = sha(target)
    assert WebFetchTool().execute(url=target.as_uri()) == 'S0_FILE_SCHEME'
    assert sha(target) == before


def test_web_fetch_data_scheme_is_currently_accepted():
    assert WebFetchTool().execute(url='data:text/plain,S0_DATA_SCHEME') == 'S0_DATA_SCHEME'


def test_web_fetch_unsupported_scheme_returns_error_without_launch():
    assert WebFetchTool().execute(url='s0invalid:fixture').startswith('Error:')


@pytest.mark.parametrize('scheme', ['https', 'ftp'])
def test_web_fetch_delegates_scheme_to_urllib_with_no_nova_allowlist(scheme):
    response = Mock()
    response.read.return_value = b'S0_MOCK_TRANSPORT'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    # header object must support both get and get_content_charset.
    response.headers = Mock()
    response.headers.get.return_value = 'text/plain'
    response.headers.get_content_charset.return_value = 'utf-8'
    url = scheme + '://fixture.invalid/value'
    with patch('local_cli.tools.web_fetch_tool.urllib.request.urlopen', return_value=response) as opened:
        assert WebFetchTool().execute(url=url) == 'S0_MOCK_TRANSPORT'
    assert opened.call_args.args[0].full_url == url
    # This is delegation evidence, not an actual HTTPS/FTP connectivity claim.


def test_web_fetch_reads_entire_response_before_character_truncation():
    response = Mock()
    response.headers.get.return_value = 'text/plain'
    response.headers.get_content_charset.return_value = 'utf-8'
    response.read.return_value = b'X' * 4096
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch('local_cli.tools.web_fetch_tool.urllib.request.urlopen', return_value=response):
        result = WebFetchTool().execute(url='https://fixture.invalid/', max_length=4)
    response.read.assert_called_once_with()
    assert result.startswith('XXXX') and 'truncated' in result


def test_web_fetch_loopback_http_redirect_is_followed(tmp_path, monkeypatch):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path == '/start':
                self.send_response(302); self.send_header('Location', '/final'); self.end_headers()
            else:
                payload = b'S0_LOOPBACK_FIXTURE'
                self.send_response(200); self.send_header('Content-Type', 'text/plain')
                self.send_header('Content-Length', str(len(payload))); self.end_headers()
                self.wfile.write(payload)
        def log_message(self, *args):
            pass
    # Do not involve any external proxy or destination.
    for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('no_proxy', '*')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        assert WebFetchTool().execute(url=f'http://127.0.0.1:{server.server_port}/start') == 'S0_LOOPBACK_FIXTURE'
        assert requests == ['/start', '/final']
    finally:
        server.shutdown(); server.server_close(); worker.join(3)
    assert not worker.is_alive()
