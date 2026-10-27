"""Build the Windows x64 NSIS installer, frozen backend and local browser.

Only an explicit build downloads dependencies. Normal application startup does
not install Python, .NET, WebView2, Ollama or any model. Publishing is disabled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def run(args, *, environment=None):
    print('Build step: ' + str(args[0]) + ' ' + str(args[1]), flush=True)
    subprocess.run([str(arg) for arg in args], cwd=ROOT, env=environment,
                   check=True, shell=False)


def checked_output(path, parent):
    target, allowed = path.resolve(), parent.resolve()
    if not target.is_relative_to(allowed) or target == allowed:
        raise ValueError('Build output must remain below ' + str(allowed))
    for item in [path, *path.parents]:
        if item == ROOT.parent:
            break
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('Build output cannot traverse a link')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt' or platform.machine().upper() not in ('AMD64', 'X86_64'):
        raise ValueError('Windows x64 is required')
    if sys.version_info[:2] != (3, 14):
        raise ValueError('Build with Python 3.14 x64; installed Nova needs no Python')
    node = args.node.resolve()
    if not node.is_file():
        raise ValueError('Node executable missing')
    build = checked_output(ROOT / 'build/windows', ROOT / 'build')
    build.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1',
                       PYTHONNOUSERSITE='1', DOTNET_CLI_TELEMETRY_OPTOUT='1',
                       DOTNET_NOLOGO='1')
    for key in list(environment):
        if key.upper() in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', '__PYVENV_LAUNCHER__'):
            del environment[key]
    system = Path(os.environ['SystemRoot'])
    environment['PATH'] = os.pathsep.join(dict.fromkeys([
        str(node.parent), str(system / 'System32'), str(system),
        str(system / 'System32/WindowsPowerShell/v1.0'),
        *[str(Path(found).parent) for name in ['dotnet', 'git'] if (found := shutil.which(name))],
    ]))
    requirements = ROOT / 'packaging/windows/requirements-build.txt'
    build_python = build / 'python/Scripts/python.exe'
    requirement_receipt = build / 'requirements.sha256'
    if not build_python.is_file():
        venv.EnvBuilder(with_pip=True).create(build / 'python')
    run([build_python, '-m', 'pip', 'install', '-r', requirements], environment=environment)
    requirement_receipt.write_text(digest(requirements))
    run([build_python, '-m', 'pip', 'install', '--no-deps', '-e', ROOT], environment=environment)
    run([build_python, '-m', 'pip', 'check'], environment=environment)
    backend = checked_output(ROOT / 'dist/windows-backend', ROOT / 'dist')
    checked_output(backend / 'nova-backend', backend)
    run([build_python, '-m', 'PyInstaller', '--noconfirm', '--distpath', backend,
         '--workpath', build / 'pyinstaller', ROOT / 'packaging/windows/backend.spec'], environment=environment)
    run([backend / 'nova-backend/nova-backend.exe', '--version'], environment=environment)

    browser = checked_output(ROOT / 'dist/windows-browser/windows-x64', ROOT / 'dist/windows-browser')
    browser_stamp = build / 'browser-sources.json'
    inputs = [ROOT / 'scripts/package_browser_windows.py', ROOT / 'native/browser-dependencies.json',
              *sorted((ROOT / 'native/nova-webview-host').glob('*.cs')),
              *sorted((ROOT / 'native/nova-webview-host').glob('*.csproj'))]
    fingerprints = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    if browser.exists() and (not browser_stamp.is_file() or json.loads(browser_stamp.read_text()) != fingerprints):
        if not (browser / '.nova-build-owned').is_file():
            raise ValueError('Refusing to replace an unowned browser build directory')
        # The absolute fixed destination was checked above; never follow links.
        for directory, dirs, _ in os.walk(browser, followlinks=False):
            for name in dirs:
                item = Path(directory) / name
                if item.is_symlink() or item.is_junction():
                    raise ValueError('Refusing to remove a linked browser build')
        shutil.rmtree(browser)
    if not browser.exists():
        run([build_python, ROOT / 'scripts/package_browser_windows.py', '--download', '--output', browser], environment=environment)
        (browser / '.nova-build-owned').write_text('Nova Windows build output\n')
        browser_stamp.write_text(json.dumps(fingerprints, sort_keys=True))
    receipt = json.loads((browser / 'package.json').read_text(encoding='utf-8'))
    if (digest(browser / 'host/nova-webview-host.exe') != receipt['hostSha256'] or
            digest(browser / 'host/nova-webview-host.dll') != receipt['hostAssemblySha256'] or
            not (browser / 'runtime/msedgewebview2.exe').is_file()):
        raise ValueError('Browser build verification failed')
    desktop = ROOT / 'desktop'
    subprocess.run([str(node), str(desktop / 'node_modules/typescript/bin/tsc'), '--noEmit'], cwd=desktop, check=True)
    # Vite resolves paths relative to cwd, unlike PyInstaller/native packaging.
    subprocess.run([str(node), str(desktop / 'node_modules/vite/bin/vite.js'), 'build'], cwd=desktop, env=environment, check=True)
    subprocess.run([str(node), str(desktop / 'node_modules/electron-builder/out/cli/cli.js'),
                    '--win', '--x64', '--publish', 'never'], cwd=desktop, env=environment, check=True)
    version = json.loads((desktop / 'package.json').read_text(encoding='utf-8'))['version']
    artifacts = [desktop / 'release' / ('Nova-' + version + '-windows-x64-setup.exe')]
    artifacts = [item for item in artifacts if item.is_file()]
    if len(artifacts) != 1:
        raise ValueError('Expected one versioned Windows installer')
    result = dict(schema='NOVA_WINDOWS_BUILD_V1', version=json.loads((desktop / 'package.json').read_text())['version'],
                  installer=artifacts[0].name, sha256=digest(artifacts[0]), bytes=artifacts[0].stat().st_size,
                  backend=digest(backend / 'nova-backend/nova-backend.exe'),
                  browser=receipt['webview2Runtime']['version'], published=False,
                  pythonRequiredAtRuntime=False, dotnetRequiredAtRuntime=False,
                  externalRequirements=['Ollama', 'a compatible installed LLM'])
    (desktop / 'release/windows-build.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
