"""Reproducible S2 tests using private state and fresh evidence directories."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import site
import shutil
import subprocess
import sys
import tempfile

from run_s1 import REGRESSION


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--tests', nargs='*')
    parser.add_argument('--node', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                     '--exclude-standard'], cwd=root, text=True).splitlines()
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest().upper()
              for name in files if (root/name).is_file() and not name.startswith('docs/security_v12/s2_evidence/')}
    record = {'phase': 'S2', 'utc': datetime.now(timezone.utc).isoformat(),
              'sourceHashes': hashes, 'groups': [], 'hostRealSecurity': False}
    if args.snapshot:
        record['gitStatus'] = subprocess.check_output(
            ['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=root, text=True).splitlines()
        (out/'snapshot.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(f'Snapshot: {len(hashes)} files')
        return 0
    groups = [('selected', args.tests)] if args.tests else [
        ('s2', ['tests/security_v12/test_s2_policy.py', 'tests/security_v12/test_s2_runtime.py',
                'tests/security_v12/test_s2_approvals.py']),
        ('s1_core', ['tests/security_v12/test_s1_contracts.py',
                     'tests/security_v12/test_s1_issuer.py', *REGRESSION,
                     'tests/security_v12/test_s0_surfaces.py::test_public_base_tool_schemas_match_s0_snapshot']),
    ]
    failed = False
    with tempfile.TemporaryDirectory(prefix='s2_private_', dir=out) as private:
        env = os.environ.copy()
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONIOENCODING='utf-8', PYTHONPATH=os.pathsep.join(
                       [str(root), site.getusersitepackages(), *filter(None, sys.path)]))
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                    'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
            folder = Path(private)/key.lower(); folder.mkdir(); env[key] = str(folder)
        for key in ('NOVA_PHASE14_OLLAMA_SMOKE', 'NOVA_ELECTRON_E2E', 'NOVA_REAL_OLLAMA_E2E'):
            env.pop(key, None)
        for name, selected in groups:
            cmd = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   '-o', 'junit_family=legacy', '--basetemp', str(Path(private)/name),
                   '--junitxml', str(out/(name+'.xml')),
                   '-k', 'not native_shell and not windows_cancellation', *selected]
            with (out/(name+'.log')).open('w', encoding='utf-8') as stream:
                try:
                    code = subprocess.run(cmd, cwd=root, env=env, stdout=stream,
                                          stderr=subprocess.STDOUT, timeout=240).returncode
                except subprocess.TimeoutExpired:
                    code = None
            record['groups'].append({'name': name, 'command': cmd, 'exitCode': code})
            failed |= code != 0
            (out/'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
            print((out/(name+'.log')).read_text(encoding='utf-8'), flush=True)
    record['status'] = 'FAIL_OR_UNKNOWN' if failed else 'PASS'
    if args.node:
        node = shutil.which('node')
        if node:
            commands = [('desktop_host', [node, '--test', 'desktop/tests/approval_host.test.cjs']),
                        ('desktop_main_syntax', [node, '--experimental-transform-types', '--check',
                                                'desktop/electron/main.ts']),
                        ('desktop_client_syntax', [node, '--experimental-transform-types', '--check',
                                                  'desktop/electron/application_client.ts'])]
            for name, cmd in commands:
                with (out/(name+'.log')).open('w', encoding='utf-8') as stream:
                    code = subprocess.run(cmd, cwd=root, stdout=stream,
                                          stderr=subprocess.STDOUT, timeout=30).returncode
                record['groups'].append({'name': name, 'command': cmd, 'exitCode': code})
                failed |= code != 0
                (out/'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
                print((out/(name+'.log')).read_text(encoding='utf-8'), flush=True)
        else:
            record['node'] = 'UNAVAILABLE'
            failed = True
    record['status'] = 'FAIL_OR_UNKNOWN' if failed else 'PASS'
    (out/'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
