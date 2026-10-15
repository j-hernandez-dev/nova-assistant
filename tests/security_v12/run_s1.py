"""S1 unit/contracts and pertinent Core regression, without native host launches.

Usage: python -B tests/security_v12/run_s1.py --output <NEW directory>
Requires the project's existing pytest development dependency. No installation.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import platform
import site
import subprocess
import sys
import tempfile


REGRESSION = [
    'tests/test_nova_core_phase2_contracts.py', 'tests/test_nova_core_phase2_legacy.py',
    'tests/test_nova_core_phase4_session.py', 'tests/test_nova_core_phase5_events.py',
    'tests/test_nova_core_phase6_runtime.py', 'tests/test_nova_core_phase7_interactions.py',
    'tests/test_nova_core_phase7_session.py', 'tests/test_nova_core_phase7_subagent.py',
    'tests/test_nova_core_phase8_frontends.py', 'tests/test_nova_core_phase8_providers.py',
    'tests/test_nova_core_phase9_capabilities.py', 'tests/test_nova_core_phase9_context.py',
    'tests/test_nova_core_phase9_integration.py', 'tests/test_nova_core_phase10_services.py',
    'tests/test_nova_core_phase11_adapter.py', 'tests/test_nova_core_phase11_events.py',
    'tests/test_nova_core_phase12_client.py', 'tests/test_nova_core_phase13_snapshots.py',
    'tests/test_nova_core_phase14_architecture.py', 'tests/test_nova_core_phase14_characterization.py',
    'tests/test_nova_core_phase14_smoke.py', 'tests/security_v12/test_s0_frontends.py',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    hashes = {str(p.relative_to(root)).replace('\\', '/'):
              hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in [
        root/'local_cli/core/security.py', root/'local_cli/application/grants.py',
        root/'tests/security_v12/test_s1_contracts.py', root/'tests/security_v12/test_s1_issuer.py',
        root/'tests/security_v12/run_s1.py',
        root/'docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md',
        root/'docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md',
    ]}
    result = {'phase': 'S1', 'utc': datetime.now(timezone.utc).isoformat(),
              'model': 'HOST_UNISOLATED', 'python': platform.python_version(),
              'platform': platform.platform(), 'sourceHashes': hashes,
              'hostRealExperiments': False, 'groups': []}
    failed = False
    # An explicit writable task directory avoids platform temp redirection.
    with tempfile.TemporaryDirectory(prefix='s1_private_', dir=out) as private:
        env = os.environ.copy()
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONIOENCODING='utf-8',
                   PYTHONPATH=os.pathsep.join([str(root), site.getusersitepackages(),
                       *[p for p in sys.path if p and Path(p).is_dir()]]))
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                    'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
            folder = Path(private)/key.lower(); folder.mkdir(); env[key] = str(folder)
        for key in ('NOVA_PHASE14_OLLAMA_SMOKE', 'NOVA_ELECTRON_E2E', 'NOVA_REAL_OLLAMA_E2E'):
            env.pop(key, None)
        for name, selected in [('s1', ['tests/security_v12/test_s1_contracts.py',
                                      'tests/security_v12/test_s1_issuer.py']),
                               ('core_regression', REGRESSION)]:
            cmd = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   '-o', 'junit_family=legacy', '--basetemp', str(Path(private)/name),
                   '--junitxml', str(out/(name+'.xml')),
                   '-k', 'not native_shell and not windows_cancellation', *selected]
            with (out/(name+'.log')).open('w', encoding='utf-8') as stream:
                try:
                    code = subprocess.run(cmd, cwd=root, env=env, stdout=stream,
                                          stderr=subprocess.STDOUT, timeout=180).returncode
                    status = 'PASS' if code == 0 else 'FAIL'
                except subprocess.TimeoutExpired:
                    code, status = None, 'UNKNOWN_TIMEOUT'
            result['groups'].append({'name': name, 'selected': selected, 'status': status,
                                     'exitCode': code, 'command': cmd})
            failed |= status != 'PASS'
            (out/'run.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print((out/(name+'.log')).read_text(encoding='utf-8'), flush=True)
    result['status'] = 'FAIL_OR_UNKNOWN' if failed else 'PASS'
    (out/'run.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
