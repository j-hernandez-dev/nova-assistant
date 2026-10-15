"""Read-only repository inventory with fresh generated evidence outside Git."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8')


def inventory():
    paths = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0')
    return [dict(path=p, sha256=sha(ROOT/p)) for p in sorted(set(paths)) if p and (ROOT/p).is_file()]


def preflight(output):
    assert sys.executable.replace('\\', '/').lower() == 'c:/users/joseh/appdata/local/python/pythoncore-3.14-64/python.exe'
    assert platform.python_version() == '3.14.6'
    assert not output.exists() and ROOT not in output.parents
    closure_path = ROOT/'docs/knowledge_inputs_v1/k8_final_campaign_closure_manifest.json'
    assert sha(closure_path) == 'fb2c736ebb509b3a97b909487b52b6d4d7792902b94b61b45d782eb6ac0c40bb'
    closure = json.loads(closure_path.read_text(encoding='utf-8'))
    refs = closure['artifacts']
    assert all(sha(Path(r['path']) if Path(r['path']).is_absolute() else ROOT/r['path']) == r['sha256'] for r in refs)
    freeze = json.loads((ROOT/'docs/knowledge_inputs_v1/k8_evidence/e2e_execution_freeze_v2.json').read_text(encoding='utf-8'))
    checks = {}
    for key in ('examPins', 'productPins', 'files', 'historicalEvidencePins'):
        pins = freeze[key]
        checks[key] = dict(total=len(pins), mismatches=[r['path'] for r in pins if sha(ROOT/r['path']) != r['sha256']])
        assert not checks[key]['mismatches'], checks[key]
    data = dict(purpose='K8 post-certification baseline; original campaign CLOSED 13/14',
        at=datetime.now(timezone.utc).isoformat(), runtime=sys.executable, python=platform.python_version(),
        branch=git('branch', '--show-current').strip(), head=git('rev-parse', 'HEAD').strip(),
        status=git('status', '--porcelain=v1', '--untracked-files=all'), tags=git('show-ref', '--tags'),
        staged=git('diff', '--cached', '--name-only'), pins=inventory(), closureReferences=refs,
        historicalChecks=checks,
        interruptedAttempt=dict(ownDeltaRemoved=True, originalQuerySha='6590bab13e77718d9aa9c3de75779fc5683a502fec83c623f0709dffb302df2c',
            result='39 passed / 2 failed', classification='HARNESS_BUG: historical freeze detects authorized product delta',
            raw='Conversation transcript only; prior invocation used default pytest temp and no XML. Not a qualifying baseline.'))
    output.mkdir(parents=True)
    (output/'preflight.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(dict(output=str(output), pins=len(data['pins']), history=checks, preflightSha=sha(output/'preflight.json'))))


def collect(output):
    pre = json.loads((output/'preflight.json').read_text(encoding='utf-8'))
    current = {r['path']:r['sha256'] for r in inventory()}
    changed = [dict(path=r['path'],before=r['sha256'],after=current.get(r['path'])) for r in pre['pins'] if current.get(r['path']) != r['sha256']]
    allowed = {'local_cli/infrastructure/knowledge_query.py','local_cli/infrastructure/knowledge_retrieval_sqlite.py',
        'tests/knowledge_inputs_v1/k8_post_cert_evidence.py'}
    assert {r['path'] for r in changed} == allowed, changed
    closure_refs = pre['closureReferences']
    assert all(sha(Path(r['path']) if Path(r['path']).is_absolute() else ROOT/r['path']) == r['sha256'] for r in closure_refs)
    execution_manifest = json.loads((ROOT/'docs/knowledge_inputs_v1/k8_final_execution_manifest.json').read_text(encoding='utf-8'))
    raw_ref = execution_manifest['artifacts']['rawInventory']
    raw_path = Path(raw_ref['path'])
    assert sha(raw_path) == raw_ref['sha256']
    raw_inventory = json.loads(raw_path.read_text(encoding='utf-8'))
    raw_mismatches = [r['path'] for r in raw_inventory['artifacts'] if sha(Path(r['path'])) != r['sha256']]
    assert not raw_mismatches
    freeze = json.loads((ROOT/'docs/knowledge_inputs_v1/k8_evidence/e2e_execution_freeze_v2.json').read_text(encoding='utf-8'))
    history = {}
    for group in ('examPins','productPins','files','historicalEvidencePins'):
        history[group] = dict(total=len(freeze[group]), mismatches=[r['path'] for r in freeze[group] if sha(ROOT/r['path']) != r['sha256']])
        assert set(history[group]['mismatches']) <= allowed
    runs = []
    for name in ('baseline','quality-first','quality-final','knowledge','memory','core','desktop','head'):
        folder = output/name
        run = json.loads((folder/'run.json').read_text(encoding='utf-8'))
        record = dict(name=name, run=run, artifacts=[])
        if (folder/'tests.xml').exists():
            xml = ET.parse(folder/'tests.xml')
            tests = xml.findall('.//testcase')
            failed = [t for t in tests if t.find('failure') is not None]
            errors = [t for t in tests if t.find('error') is not None]
            skips = [t for t in tests if t.find('skipped') is not None]
            record['counts'] = dict(testcases=len(tests),passed=len(tests)-len(failed)-len(errors)-len(skips),failed=len(failed),errors=len(errors),skips=len(skips))
            record['failures'] = []
            for t in failed+errors:
                node = t.find('failure') if t.find('failure') is not None else t.find('error')
                record['failures'].append(dict(id=t.get('classname')+'::'+t.get('name'),
                    classification='HARNESS_BUG' if 'test_k8_repair6_quality' in t.get('classname','') else 'PRODUCT_BUG' if 'test_k8_post_cert_conflict' in t.get('classname','') else 'UNKNOWN',
                    reason=node.get('message'),body=node.text))
            record['skipIds'] = [t.get('classname')+'::'+t.get('name') for t in skips]
            text = (folder/'run.log').read_text(encoding='utf-8')
            record['summary'] = text.splitlines()[-1]
            match = re.search(r'(\d+) subtests passed',text)
            record['passedSubtests'] = int(match.group(1)) if match else 0
        for path in sorted(folder.glob('*')):
            if path.is_file(): record['artifacts'].append(dict(path=str(path),sha256=sha(path)))
        for path in sorted(folder.rglob('postcert-quality.json')):
            record.setdefault('qualityArtifacts',[]).append(dict(path=str(path),sha256=sha(path)))
        for path in sorted(folder.rglob('historical-regression.json')):
            record.setdefault('historicalRegressionArtifacts',[]).append(dict(path=str(path),sha256=sha(path)))
        runs.append(record)
    old_head = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v6-20261008/head-final/tests.xml')
    old_xml = ET.parse(old_head)
    previous_skips = sorted(t.get('classname')+'::'+t.get('name') for t in old_xml.findall('.//testcase') if t.find('skipped') is not None)
    new_head = next(r for r in runs if r['name']=='head')
    assert sorted(new_head['skipIds']) == previous_skips and len(previous_skips) == 11
    first_path = next((output/'quality-first').rglob('postcert-quality.json'))
    final_path = next((output/'quality-final').rglob('postcert-quality.json'))
    data = dict(at=datetime.now(timezone.utc).isoformat(),runtime=sys.executable,python=platform.python_version(),
        branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),
        status=git('status','--porcelain=v1','--untracked-files=all'),staged=git('diff','--cached','--name-only'),
        tagsUnchanged=git('show-ref','--tags') == pre['tags'], changed=changed,
        originalFilesUnchanged=len(pre['pins'])-len(changed), historicalChecks=history,
        historicalRaws=dict(total=len(raw_inventory['artifacts']),mismatches=raw_mismatches,inventory=raw_ref),
        newFiles=[p for p in current if p not in {r['path'] for r in pre['pins']}], runs=runs,
        firstQuality=json.loads(first_path.read_text(encoding='utf-8')),
        finalQuality=json.loads(final_path.read_text(encoding='utf-8')),
        sameHistoricalSkips=True, historicalSkipReference=dict(path=str(old_head),sha256=sha(old_head)),
        diagnosis=json.loads((output/'diagnostic-final/diagnosis.json').read_text(encoding='utf-8')),
        preflight=dict(path=str(output/'preflight.json'),sha256=sha(output/'preflight.json')))
    assert not data['staged'] and data['tagsUnchanged'] and data['head'] == pre['head']
    with (output/'final-evidence.json').open('x',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2)
    print(json.dumps(dict(path=str(output/'final-evidence.json'),sha256=sha(output/'final-evidence.json'),
        delta=changed, runs=[{k:r.get(k) for k in ('name','counts','summary','passedSubtests')} for r in runs],
        gates=data['finalQuality']['metrics'],sameHistoricalSkips=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--preflight', type=Path)
    group.add_argument('--collect', type=Path)
    args = parser.parse_args()
    if args.preflight: preflight(args.preflight.resolve())
    else: collect(args.collect.resolve())
