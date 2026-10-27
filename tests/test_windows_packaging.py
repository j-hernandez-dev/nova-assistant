"""Runtime layout remains independent of cwd and any development checkout."""
from pathlib import Path
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
