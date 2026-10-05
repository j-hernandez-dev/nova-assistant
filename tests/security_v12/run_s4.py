"""S4 evidence runner. All fixtures use private directories; no OS elevation."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import site
import subprocess
import sys
import tempfile

from run_s1 import REGRESSION


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tests', nargs='*')
    parser.add_argument('--host-real', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if not out.is_relative_to(root/'docs/security_v12/s4_evidence'):
        parser.error('output must be inside the repository S4 evidence directory')
    out.mkdir(parents=True, exist_ok=False)
    files = set(subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                '--exclude-standard'], cwd=root, text=True).splitlines())
    files.update(json.loads((root/'docs/security_v12/s3_manifest.json').read_text())['files'])
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest().upper()
              for name in sorted(files) if (root/name).is_file()
              and not name.startswith('docs/security_v12/s4_evidence/')}
    record = {'phase': 'S4', 'utc': datetime.now(timezone.utc).isoformat(),
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'sourceHashes': hashes, 'groups': [], 'hostRealSecurity': args.host_real}
    groups = [('selected', args.tests)] if args.tests else [
        ('s4', ['tests/security_v12/test_s4_contracts.py']),
        ('prior_regression', ['tests/security_v12/test_s1_contracts.py',
            'tests/security_v12/test_s1_issuer.py', 'tests/security_v12/test_s2_policy.py',
            'tests/security_v12/test_s2_runtime.py', 'tests/security_v12/test_s2_approvals.py',
            'tests/security_v12/test_s3_contracts.py', 'tests/security_v12/test_s3_runtime.py',
            *REGRESSION, 'tests/security_v12/test_s0_surfaces.py::test_public_base_tool_schemas_match_s0_snapshot']),
    ]
    if args.host_real:
        groups.append(('s4_host_real', ['tests/security_v12/test_s4_host.py']))
    failed = False
    with tempfile.TemporaryDirectory(prefix='s4_private_', dir=out) as private:
        env = os.environ.copy()
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONIOENCODING='utf-8', PYTHONPATH=os.pathsep.join(
                       [str(root), site.getusersitepackages(), *filter(None, sys.path)]))
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                    'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
            folder = Path(private)/key.lower(); folder.mkdir(); env[key] = str(folder)
        for key in ('NOVA_PHASE14_OLLAMA_SMOKE', 'NOVA_ELECTRON_E2E', 'NOVA_REAL_OLLAMA_E2E'):
            env.pop(key, None)
        env['NOVA_S4_HOST_REAL'] = '1' if args.host_real else '0'
        for name, tests in groups:
            cmd = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   '-o', 'junit_family=legacy', '--basetemp', str(Path(private)/name),
                   '--junitxml', str(out/(name+'.xml')), *tests]
            with (out/(name+'.log')).open('w', encoding='utf-8') as stream:
                try:
                    code = subprocess.run(cmd, cwd=root, env=env, stdout=stream,
                                          stderr=subprocess.STDOUT, timeout=300).returncode
                except subprocess.TimeoutExpired:
                    code = None
            record['groups'].append({'name': name, 'command': cmd, 'exitCode': code})
            failed |= code != 0
            (out/'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
            print((out/(name+'.log')).read_text(encoding='utf-8'), flush=True)
    record['status'] = 'FAIL_OR_UNKNOWN' if failed else 'PASS'
    (out/'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
