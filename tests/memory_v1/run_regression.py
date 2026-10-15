"""Reproducible M0/HEAD gate with private state; never overwrite old evidence.

python -B -m tests.memory_v1.run_regression --mode m0 --output <new-directory>
Modes: m0 (memory baseline), context64 (focused context regression),
head (current native CI contract selection), metrics, m1 (domain gate),
m2 (durable store gate), m3 (explicit shared user controls), m4 (lexical TAC).
Native host permissions are required for the same OS contracts as existing CI.
"""

import argparse
import json
import os
from pathlib import Path
import platform
import site
import subprocess
import sys


# Exact existing CI classifications, not new M0 skips or weakened assertions.
HEAD_EXCLUSIONS = (
    'tests/security_v12/test_s0_frontends.py', 'tests/security_v12/test_s0_process.py',
    'tests/security_v12/test_s0_surfaces.py', 'tests/security_v12/test_s3_windows.py',
    'tests/security_v12/test_s4_host.py', 'tests/security_v12/test_s5_network.py',
    'tests/security_v12/test_s6_host.py', 'tests/security_v12/test_s8_host.py',
    'tests/security_v12/test_s8_e2e.py', 'tests/test_nova_core_phase7_legacy_bridge.py',
    'tests/test_nova_core_phase7_server_legacy.py', 'tests/test_security_gates.py',
)
POSIX_EXCLUSIONS = (
    'tests/test_nova_core_phase12_client.py', 'tests/test_nova_core_phase3_cwd.py',
    'tests/test_nova_core_phase6_runtime.py', 'tests/test_nova_core_phase7_session.py',
)

CONTEXT64_TESTS = (
    'tests/test_context_64k.py', 'tests/test_context_sizing.py',
    'tests/test_context_command.py', 'tests/test_config.py',
    'tests/test_nova_core_phase9_context.py', 'tests/test_nova_core_phase9_integration.py',
    'tests/test_nova_core_phase9_capabilities.py', 'tests/test_nova_core_phase8_providers.py',
    'tests/test_nova_core_phase8_frontends.py', 'tests/test_nova_core_phase12_client.py',
    'tests/test_nova_core_phase13_snapshots.py', 'tests/test_nova_core_phase13_desktop.py',
    'tests/memory_v1',
)

M1_TESTS = (
    'tests/memory_v1/test_m1_identity_scope.py', 'tests/memory_v1/test_m1_domain.py',
    'tests/memory_v1/test_m1_admission_ports.py', 'tests/test_nova_core_phase14_architecture.py',
)

M2_TESTS = (
    'tests/memory_v1/test_m2_store.py', 'tests/memory_v1/test_m2_recovery.py',
    'tests/memory_v1/test_m2_performance.py', *M1_TESTS,
)

M3_TESTS = ('tests/memory_v1/test_m3_service.py', 'tests/memory_v1/test_m3_application.py',
    'tests/memory_v1/test_m3_composition.py',
    'tests/test_nova_core_phase12_client.py', 'tests/test_nova_core_phase13_desktop.py',
    'tests/test_nova_core_phase11_adapter.py', *M2_TESTS)

M4_TESTS = ('tests/memory_v1', 'tests/test_context_sizing.py', 'tests/test_context_command.py',
    'tests/test_nova_core_phase0_characterization.py',
    'tests/test_config.py', 'tests/test_context_64k.py', 'tests/test_nova_core_phase9_context.py',
    'tests/test_nova_core_phase9_integration.py', 'tests/test_nova_core_phase9_capabilities.py',
    'tests/test_nova_core_phase8_providers.py', 'tests/test_nova_core_phase8_frontends.py',
    'tests/test_nova_core_phase10_persistence.py', 'tests/test_nova_core_phase10_rag.py',
    'tests/test_nova_core_phase11_adapter.py', 'tests/test_nova_core_phase12_client.py',
    'tests/test_nova_core_phase13_desktop.py', 'tests/test_nova_core_phase14_architecture.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('m0', 'head', 'metrics', 'context64', 'm1', 'm2', 'm3', 'm4'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-test-site', type=Path,
        help='Existing pure-Python pytest site for an alternate offline runtime; never installs packages')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error('output already exists; choose a new directory to preserve evidence')
    out.mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
    # Copy only non-secret system/toolchain/locale fields. No .env/config loading.
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
    if args.mode == 'metrics':
        command = [sys.executable, '-B', '-m', 'tests.memory_v1.run_m0', '--output', str(out / 'report.json')]
    else:
        selection = (list(M4_TESTS) if args.mode == 'm4' else list(M3_TESTS) if args.mode == 'm3' else
                     list(M2_TESTS) if args.mode == 'm2' else
                     list(M1_TESTS) if args.mode == 'm1' else
                     list(CONTEXT64_TESTS) if args.mode == 'context64' else
                     ['tests/memory_v1'] if args.mode == 'm0' else ['tests'])
        excludes = HEAD_EXCLUSIONS + (POSIX_EXCLUSIONS if os.name != 'nt' else ()) if args.mode == 'head' else ()
        command = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '--basetemp', str(out / 'pytest-private'), '--junitxml', str(out / 'tests.xml'),
            *selection, *('--ignore=' + path for path in excludes)]
    with (out / 'run.log').open('x', encoding='utf-8') as stream:
        code = subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
    with (out / 'run.json').open('x', encoding='utf-8') as stream:
        json.dump({'mode': args.mode, 'python': sys.version, 'platform': platform.platform(),
            'command': command, 'exitCode': code, 'privateState': True,
            'externalInference': False}, stream, indent=2)
    sys.stdout.reconfigure(encoding='utf-8')
    print((out / 'run.log').read_text(encoding='utf-8'))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
