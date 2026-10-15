"""K0 contracts / CI harness verification with synthetic private state.

Outputs MUST be fresh and outside the checkout. No model calls or installs.
For broad HEAD/MEMORY use the existing tests.memory_v1.run_regression runner.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import site
import subprocess
import sys


SELECTIONS = {
    'contracts': ['tests/knowledge_inputs_v1'],
    'ci-harness': ['tests/memory_v1/test_m8_qwen4_chat7b.py',
                   'tests/memory_v1/test_m8_metadata_admission.py',
                   'tests/memory_v1/test_m8_ps_operational.py'],
    'boundaries': ['tests/test_nova_core_phase14_architecture.py',
                   'tests/test_nova_core_phase9_context.py',
                   'tests/test_nova_core_phase9_integration.py',
                   'tests/test_context_64k.py',
                   'tests/test_nova_core_phase10_rag.py'],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=SELECTIONS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-test-site', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out == root or root in out.parents:
        parser.error('Output must be outside the Git checkout')
    if out.exists():
        parser.error('Output exists; never overwrite prior evidence')
    out.mkdir(parents=True)
    env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'COMSPEC',
        'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
        'PROGRAMDATA', 'LANG', 'LC_ALL') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
        PYTHONIOENCODING='utf-8', PYTHONPATH=str(root) + os.pathsep + site.getusersitepackages())
    if args.extra_test_site:
        env['PYTHONPATH'] += os.pathsep + str(args.extra_test_site.resolve())
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
        folder = out / 'private' / ('profile' if key in ('HOME', 'USERPROFILE') else key.lower())
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    command = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--basetemp', str(out / 'pytest-private'), '--junitxml', str(out / 'tests.xml'),
        *SELECTIONS[args.mode]]
    with (out / 'run.log').open('x', encoding='utf-8') as stream:
        code = subprocess.run(command, cwd=root, env=env, stdout=stream,
                              stderr=subprocess.STDOUT).returncode
    with (out / 'run.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(mode=args.mode, python=sys.version, platform=platform.platform(),
            command=command, exitCode=code, privateState=True, externalInference=False),
            stream, indent=2)
    sys.stdout.reconfigure(encoding='utf-8')
    print((out / 'run.log').read_text(encoding='utf-8'))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
