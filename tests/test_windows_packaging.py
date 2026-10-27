"""Runtime layout remains independent of cwd and any development checkout."""
from pathlib import Path
import json
import os
import subprocess
import sys
import pytest

from local_cli.tools.browser_tools import browser_package_root


def test_frozen_browser_component_follows_installed_backend_not_cwd(monkeypatch, tmp_path):
    resources = tmp_path / 'app' / 'resources'
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(resources / 'backend' / 'nova-backend.exe'))
    monkeypatch.chdir(tmp_path)
    assert browser_package_root() == resources / 'browser' / 'windows-x64'


def test_development_browser_component_keeps_its_existing_checkout_location(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    from local_cli.tools import browser_tools
    assert browser_package_root() == Path(browser_tools.__file__).resolve().parents[2] / 'dist/browser/windows-x64'


@pytest.mark.parametrize('operation', ['check_for_updates', 'perform_update'])
def test_frozen_updates_never_run_git_or_treat_the_backend_as_python(monkeypatch, operation):
    from local_cli import updater
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    def forbidden(*_args, **_kwargs):
        raise AssertionError('Packaged update must not discover Git or launch pip')
    monkeypatch.setattr(updater, 'detect_git_capability', forbidden)
    monkeypatch.setattr(updater.subprocess, 'run', forbidden)
    result, message = getattr(updater, operation)()
    assert result is False
    assert 'installer' in message


_BACKEND_ENTRY = Path(__file__).resolve().parents[1] / 'packaging/windows/backend_entry.py'
_UNICODE_TEXT = '¡Hola! ¿Cómo estás? áéíóú ñ — 中文 🚀'


def _run_backend_entry(script, mode):
    # Start actual text streams in the restrictive Windows encoding. The
    # entrypoint must override this itself, as the frozen runtime ignores the
    # PYTHONIOENCODING value passed by Electron during interpreter startup.
    environment = dict(os.environ, PYTHONIOENCODING='cp1252', PYTHONUTF8='0',
                       PYTHONDONTWRITEBYTECODE='1')
    root = str(_BACKEND_ENTRY.parents[2])
    environment['PYTHONPATH'] = root + os.pathsep + environment.get('PYTHONPATH', '')
    invocation = (
        'import json, runpy, sys, types\n'
        f'expected = {ascii(_UNICODE_TEXT)}\n'
        + script + '\n'
        + f'sys.argv = ["nova-backend.exe", {mode!r}]\n'
        + f'runpy.run_path({str(_BACKEND_ENTRY)!r}, run_name="__main__")\n'
    )
    return subprocess.run(
        [sys.executable, '-B', '-c', invocation],
        input=(json.dumps({'content': _UNICODE_TEXT}, ensure_ascii=False) + '\n').encode('utf-8'),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
        timeout=20, check=False,
    )


def test_backend_entrypoint_roundtrips_unicode_jsonl_and_cancellation_frames():
    result = _run_backend_entry('''
def main():
    from local_cli.server import _send
    request = json.loads(sys.stdin.readline())
    assert request['content'] == expected, 'UTF-8 input was decoded incorrectly'
    _send({'type': 'snapshot', 'data': {'transcript': [{'content': expected}]}})
    _send({'type': 'application_result', 'data': {'accepted': True, 'kind': 'CancelTurn'}})
    _send({'type': 'event', 'event': {'kind': 'TurnCancelled', 'content': expected}})
    sys.stderr.write(expected + '\\n')
module = types.ModuleType('local_cli.__main__')
module.main = main
sys.modules['local_cli.__main__'] = module
''', '--server')
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    frames = [json.loads(line) for line in result.stdout.decode('utf-8', errors='strict').splitlines()]
    assert frames == [
        {'type': 'snapshot', 'data': {'transcript': [{'content': _UNICODE_TEXT}]}},
        {'type': 'application_result', 'data': {'accepted': True, 'kind': 'CancelTurn'}},
        {'type': 'event', 'event': {'kind': 'TurnCancelled', 'content': _UNICODE_TEXT}},
    ]
    assert result.stderr.decode('utf-8', errors='strict').rstrip('\r\n') == _UNICODE_TEXT
    assert not result.stdout.startswith(b'\xef\xbb\xbf')


@pytest.mark.parametrize('mode', ['--runtime-info', '--check-browser'])
def test_backend_diagnostics_also_start_with_utf8_standard_streams(mode):
    result = _run_backend_entry('''
def diagnostic():
    assert [s.encoding.lower().replace('-', '') for s in (sys.stdin, sys.stdout, sys.stderr)] == ['utf8'] * 3
    assert sys.stdin.errors == sys.stdout.errors == 'strict'
    assert sys.stderr.errors == 'backslashreplace'
    assert json.loads(sys.stdin.readline())['content'] == expected
    sys.stderr.write(expected + '\\n')
    return {'status': 'PASS', 'unicode': expected}
module = types.ModuleType('runtime_checks')
module.runtime_info = diagnostic
module.check_browser = diagnostic
sys.modules['runtime_checks'] = module
''', mode)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    assert json.loads(result.stdout.decode('utf-8', errors='strict')) == {'status': 'PASS', 'unicode': _UNICODE_TEXT}
    assert result.stderr.decode('utf-8', errors='strict').rstrip('\r\n') == _UNICODE_TEXT
