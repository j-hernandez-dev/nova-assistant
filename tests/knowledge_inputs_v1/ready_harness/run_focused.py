"""Run only R1/R2 tests with fresh evidence, offline, and preservation receipts."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT.parent / 'k8-certification-evidence'
CONTROL = EVIDENCE / 'executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029'
FREEZE = ROOT / 'docs/knowledge_inputs_v2/revision_04/freeze_final_v2_r4.json'
EXPECTED = '23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6'
# Existing pinned K3 dependency tree; read-only reuse, no install or new temp output.
DEPENDENCIES = Path('C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def verify_freeze():
    errors = []
    if sha(FREEZE) != EXPECTED:
        errors.append('FREEZE_SHA_MISMATCH')
    freeze = json.loads(FREEZE.read_text(encoding='utf-8'))
    for entry in freeze['pins'] + freeze.get('external_pins', []):
        path = Path(entry['path'])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file() or sha(path) != entry['sha256']:
            errors.append(str(path))
    return dict(checked=len(freeze['pins']) + len(freeze.get('external_pins', [])), errors=errors)


def main():
    preflight = verify_freeze()
    if preflight['errors']:
        raise SystemExit(json.dumps(preflight))
    now = datetime.now(timezone.utc)
    output = EVIDENCE / 'focused-harness' / (now.strftime('r1-r2-%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    paths = {ROOT / n for n in names if n and (ROOT / n).is_file()}
    paths.update(p for p in EVIDENCE.rglob('*') if p.is_file() and not p.is_relative_to(output))
    baseline = {str(p): sha(p) for p in sorted(paths)}
    write(output / 'preservation_before.json', baseline)
    write(output / 'preflight.json', dict(timestamp=now.isoformat(), freeze_sha256=EXPECTED,
        integrity=preflight, python=sys.executable, version=sys.version,
        scope='R1_R2_FOCUSED_HARNESS_ONLY', model_execution_authorized=False))
    command = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        str(ROOT / 'tests/knowledge_inputs_v1/ready_harness/test_focused.py'),
        '--basetemp=' + str(output / 'state'), '--junitxml=' + str(output / 'tests.xml')]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       PYTHONPATH=str(ROOT) + os.pathsep + str(DEPENDENCIES))
    with (output / 'tests.log').open('x', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    drift = [p for p, digest in baseline.items() if not Path(p).is_file() or sha(Path(p)) != digest]
    write(output / 'preservation_after.json', dict(checked=len(baseline), errors=drift, freeze=verify_freeze()))
    suites = ET.parse(output / 'tests.xml').getroot().findall('.//testsuite')
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ['tests', 'failures', 'errors', 'skipped']}
    events = [json.loads(line) for p in (output / 'state').rglob('runtime_events.jsonl')
              for line in p.read_text(encoding='utf-8').splitlines()]
    summary = dict(timestamp=datetime.now(timezone.utc).isoformat(), command=command,
        exit_code=result.returncode, tests=counts, protected_files=len(baseline), drift=drift,
        new_campaigns=0, new_inference=0, new_admission=0,
        focal_scope_retrieval=sum(e['kind'] == 'knowledge.retrieval.completed' for e in events),
        focal_fixture_imports=sum(e['kind'] == 'knowledge.import.completed' for e in events),
        counters_note='Focal real SQLite retrieval/import only, no exam or model. Original V2 ledger untouched.',
        historical_v2_counters=json.loads((CONTROL / 'execution_summary.json').read_text(encoding='utf-8')),
        output=str(output))
    write(output / 'run.json', summary)
    index = [{'path': str(p.relative_to(output)), 'sha256': sha(p)}
             for p in sorted(output.rglob('*')) if p.is_file()]
    write(output / 'evidence_index.json', dict(files=index))
    print(json.dumps(dict(output=str(output), exit_code=result.returncode, tests=counts,
                         integrity_errors=drift, freeze=verify_freeze())))
    return result.returncode or bool(drift)


if __name__ == '__main__':
    raise SystemExit(main())
