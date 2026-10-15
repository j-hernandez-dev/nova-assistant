"""Reproduce S0 in isolated user-state directories, with no product changes.

Run from the clean Core checkout: python -B tests/security_v12/run_s0.py
--output <NEW directory>. Requires the project's test dependency pytest.
Output is a test artifact, never a production audit or security certificate.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import site
import subprocess
import sys
import tempfile
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.repository.resolve()
    if not (root / 'local_cli/core/contracts.py').is_file():
        parser.error('repository must be the Nova Core checkout')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)  # Never overwrite an earlier run.
    groups = {
        's0_characterization': ['tests/security_v12'],
        'core_regression': sorted(str(p.relative_to(root)) for p in (root / 'tests').glob('test_nova_core_phase*.py')) + [
            'tests/test_shell_platform.py', 'tests/test_security.py', 'tests/test_security_gates.py',
            'tests/test_web_monitor_containment.py',
            *['tests/test_tools/test_' + name + '_tool.py' for name in ('read', 'write', 'edit', 'glob', 'grep')],
        ],
    }
    # Hash relevant sources so a replay can distinguish a changed baseline.
    paths = list((root / 'local_cli').rglob('*.py')) + [
        root / 'docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md',
        root / 'docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md',
    ]
    manifest = {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths)}
    run = {'utc': datetime.now(timezone.utc).isoformat(), 'phase': 'S0',
           'python': platform.python_version(), 'platform': platform.platform(),
           'model': 'HOST_UNISOLATED', 'productionCodeChanged': False,
           'externalProviderSmokeEnabled': False, 'sourceHashes': manifest, 'groups': []}
    (out / 'run.json').write_text(json.dumps(run, indent=2), encoding='utf-8')
    failed = False
    with tempfile.TemporaryDirectory(prefix='s0_private_') as private:
        base = Path(private)
        # Resolve test dependencies before relocating application user state.
        dependencies = [str(p) for p in sys.path if p and Path(p).is_dir()]
        env = os.environ.copy()
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                    'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
            folder = base / key.lower(); folder.mkdir(); env[key] = str(folder)
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONIOENCODING='utf-8',
                   PYTHONPATH=os.pathsep.join([str(root), site.getusersitepackages(), *dependencies]))
        for opt_in in ('NOVA_PHASE14_OLLAMA_SMOKE', 'NOVA_ELECTRON_E2E',
                       'NOVA_REAL_OLLAMA_E2E'):
            env.pop(opt_in, None)
        for name, selected in groups.items():
            start = time.monotonic()
            command = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                       '-o', 'junit_family=legacy',
                       '--basetemp', str(base / name), '--junitxml', str(out / (name + '.xml')), *selected]
            with (out / (name + '.log')).open('w', encoding='utf-8') as log:
                try:
                    completed = subprocess.run(command, cwd=root, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, timeout=300)
                    exit_code = completed.returncode
                    status = 'PASS' if exit_code == 0 else 'FAIL'
                except subprocess.TimeoutExpired:
                    exit_code = None; status = 'UNKNOWN_TIMEOUT'
            text = (out / (name + '.log')).read_text(encoding='utf-8')
            summary = [line for line in text.splitlines() if re.search(r'\d+ (passed|failed|error|skipped)', line)]
            entry = {'name': name, 'selected': selected, 'status': status, 'exitCode': exit_code,
                     'seconds': round(time.monotonic() - start, 3), 'summary': summary[-1:],
                     'logSha256': sha(out / (name + '.log'))}
            run['groups'].append(entry)
            # Preserve each completed group, even if a later group fails.
            (out / 'run.json').write_text(json.dumps(run, indent=2), encoding='utf-8')
            print(json.dumps(entry), flush=True)
            failed = failed or status != 'PASS'
    run['status'] = 'FAIL_OR_UNKNOWN' if failed else 'PASS'
    run['fixtureUserStateRemoved'] = True
    (out / 'run.json').write_text(json.dumps(run, indent=2), encoding='utf-8')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
