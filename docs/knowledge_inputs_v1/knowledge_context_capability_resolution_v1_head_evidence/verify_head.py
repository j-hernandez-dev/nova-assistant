"""Additive, private HEAD closure verification; no checkout edits."""
import fnmatch
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path('C:/Users/joseh/Downloads/nova-local-cli/nova-assistant')
OUT = Path(__file__).resolve().parent
PYTHON = Path('C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe')
SITE = Path('C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies')
REFERENCE = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v6-20261008/head-final')
PROOF = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-citation-proof-20261008-a/citation-identity-proof.json')
EXPECTED_HEAD = '717a24218dea7fb60d8b630896d653e39091bc7b'
PINNED_MANIFESTS = {
    'docs/knowledge_inputs_v1/k8_post_cert_conflict_manifest.json': 'd75ce3554d6c61837e7717c50d3f093cd986c58da5c5664b636284d9ddb81e4b',
    'docs/knowledge_inputs_v1/k8_post_cert_conflict_budget_audit_manifest.json': 'f0a9e96f43b8cced730552441e2bcf99361515ee788a72740a8a7460c6877ec0',
    'docs/knowledge_inputs_v1/k8_post_cert_supplemental_8k_manifest.json': '87aebd2beaf490c136adc500be5b1a28ad8ebf1857475fd08edd16f79d6c92c2',
    'docs/knowledge_inputs_v1/k8_repair6_manifest.json': 'facc970921ec1cc5f21ebd3c52f5a4487a4d7870089e31ac6e3443b160a2217a',
    'docs/knowledge_inputs_v1/k8_final_campaign_closure_manifest.json': 'fb2c736ebb509b3a97b909487b52b6d4d7792902b94b61b45d782eb6ac0c40bb',
}
STATES = {
    'remediation': 'K8 POST-CERT REMEDIATION PARTIAL',
    'historical4KQuality': '4K historical quality = 10/15',
    'originalCampaign': 'K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14',
    'packaging': 'ELECTRON_PACKAGING = ENVIRONMENT_BLOCKED_SYMLINK_PRIVILEGE',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8')


def inventory():
    paths = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0')
    return {p: sha(ROOT / p) for p in sorted(set(paths)) if p and (ROOT / p).is_file()}


def identity():
    return dict(head=git('rev-parse', 'HEAD').strip(), branch=git('branch', '--show-current').strip(),
                status=git('status', '--porcelain=v1', '--untracked-files=all'),
                staged=git('diff', '--cached', '--name-only'), tags=git('show-ref', '--tags'))


def test_id(node):
    return node.get('classname', '') + '::' + node.get('name', '')


def skip_rows(xml_path):
    return sorted(test_id(n) for n in ET.parse(xml_path).findall('.//testcase')
                  if n.find('skipped') is not None)


def integrity():
    assert sha(PROOF) == 'e7919d6f04ca67fc9d1833c68d2d306da199b7955723b6e661da4053ea0734dc'
    proof = read(PROOF)
    pins = proof['productPins']
    assert len(pins) == len({p['path'] for p in pins}) == 241
    for pin in pins:
        assert sha(ROOT / pin['path']) == pin['sha256'], pin['path']
    v6_path = ROOT / 'tests/knowledge_inputs_v1/fixtures/k8_repair6_freeze_v2.json'
    assert sha(v6_path) == 'cdbe771621f93c1c98b5268a7e2c1f232f399977c8eca45ba0f6eb15467b71b1'
    v6_pins = {p['path']: p['sha256'] for p in read(v6_path)['files']}
    delta = [p for p in pins if p['path'] in v6_pins and p['sha256'] != v6_pins[p['path']]]
    expected_delta = {
        'local_cli/infrastructure/knowledge_query.py': (
            '6590bab13e77718d9aa9c3de75779fc5683a502fec83c623f0709dffb302df2c',
            '15dd6f01ccdd8aedce0808543a9ffea68bc5866b6c857a4bce1f72c8a8886cea'),
        'local_cli/infrastructure/knowledge_retrieval_sqlite.py': (
            'f8b499ed545c6ed1e12d3f5ca9dc47b3b7b3b7103bd65c6b4d1c55a655b25412',
            'a3a59bf40823fa74950e7da9ddd58837850f2098d881b2491b3d14911021c7cf'),
    }
    assert {p['path'] for p in delta} == set(expected_delta)
    for p in delta:
        assert (v6_pins[p['path']], p['sha256']) == expected_delta[p['path']]
    references = []
    historical_current_references = []
    accepted_guard = 'tests/knowledge_inputs_v1/test_k8_repair6_quality.py'
    for path, digest in PINNED_MANIFESTS.items():
        assert sha(ROOT / path) == digest, path
        for pin in read(ROOT / path)['artifacts']:
            target = Path(pin['path'])
            target = target if target.is_absolute() else ROOT / target
            row = dict(manifest=path, path=pin['path'], expectedSha256=pin['sha256'])
            # Historical manifests also reference the then-current product and
            # guard. Their accepted applicability changes precede this run.
            # Keep those old references visible, without applying V6 to HEAD.
            if pin['path'] == accepted_guard or (
                path.endswith('k8_repair6_manifest.json') and pin['path'] in expected_delta
            ):
                row.update(currentSha256=sha(target),
                           classification='PREVIOUSLY_ACCEPTED_IDENTITY_OR_HARNESS_CHANGE')
                historical_current_references.append(row)
            else:
                row['actualSha256'] = sha(target)
                assert row['actualSha256'] == pin['sha256'], row
                references.append(row)
    freeze_path = ROOT / 'tests/knowledge_inputs_v1/fixtures/k8_post_cert_conflict_freeze_v1.json'
    assert sha(freeze_path) == '6f353006c17d092cf0602fa85226c3991647ff01c33fc062b8fb220fab2eb8fd'
    for pin in read(freeze_path)['files']:
        assert sha(ROOT / pin['path']) == pin['sha256'], pin['path']
    standalone = read(ROOT / 'tests/knowledge_inputs_v1/fixtures/k8_freeze_v1.json')
    for pin in standalone['files']:
        if pin['path'] == 'tests/knowledge_inputs_v1/run_k8.py':
            historical_current_references.append(dict(path=pin['path'], expectedSha256=pin['sha256'],
                currentSha256=sha(ROOT / pin['path']),
                classification='PREVIOUSLY_ACCEPTED_CURRENT_REGRESSION_RUNNER_CHANGE'))
        else:
            assert sha(ROOT / pin['path']) == pin['sha256'], pin['path']
    historical_4k = ROOT / Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-20261008-a/quality-final/pytest-private/test_frozen_prospective_qualit0/postcert-quality.json')
    admissions = read(historical_4k)['metrics']['multiSourceRequiredAdmissions']
    assert (admissions['passed'], admissions['total']) == (10, 15)
    assert read(historical_4k)['gates']['multiSourceRequiredAdmissions'] is False
    return dict(status='PASS', productPinsVerified=241, authorizedProductDeltas=delta,
        immutableHistoricalReferences=references, preservedOldReferences=historical_current_references,
        historical4KQuality=dict(passed=10, total=15, qualityGate=False, reexecuted=False))


def worker():
    network_events = []
    outcomes = []
    selection = read(OUT / 'selection.json')['currentHeadSelection']
    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
            address = args[1] if event == 'socket.connect' else (
                args[-1] if event == 'socket.sendto' else (args[0], args[1]))
            allowed = False
            if isinstance(address, tuple):
                host, port = address[:2]
                try:
                    loopback = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    loopback = host == 'localhost'
                allowed = loopback and port not in (11434, 11435)
            network_events.append(dict(event=event, address=str(address),
                allowed=allowed, purpose='LOCAL_SYNTHETIC_FIXTURE' if allowed else 'DENIED'))
            if not allowed:
                raise PermissionError('HEAD closure forbids external network/model services')
    sys.addaudithook(audit)
    import pytest
    class EvidencePlugin:
        def pytest_collection_finish(self, session):
            dump('collection.json', dict(nodeids=[item.nodeid for item in session.items],
                collectedCount=len(session.items)))
        def pytest_runtest_logreport(self, report):
            outcomes.append(dict(nodeid=report.nodeid, when=report.when,
                outcome=report.outcome, wasxfail=getattr(report, 'wasxfail', None)))
    try:
        return int(pytest.main(['-q', '-p', 'no:cacheprovider', '--maxfail=1',
            '--basetemp', str(OUT / 'pytest-private'), '--junitxml', str(OUT / 'tests.xml'),
            *selection], plugins=[EvidencePlugin()]))
    finally:
        dump('execution-audit.json', dict(networkEvents=network_events, reports=outcomes,
            xfailReports=[r for r in outcomes if r['wasxfail'] is not None],
            allowedExternalConnections=0, modelServiceConnections=0))


def main():
    assert Path(sys.executable).resolve() == PYTHON.resolve()
    assert platform.python_version() == '3.14.6' and sys.dont_write_bytecode
    assert OUT != ROOT and ROOT not in OUT.parents
    sys.path.insert(0, str(ROOT))
    if '--worker' in sys.argv:
        raise SystemExit(worker())
    from tests.knowledge_inputs_v1.k8_regression_manifest import (
        CURRENT_REGRESSION_TESTS, HISTORICAL_CERTIFICATION_ARTIFACTS)
    from tests.memory_v1.run_regression import HEAD_EXCLUSIONS
    before = inventory()
    baseline = identity()
    assert baseline['head'] == EXPECTED_HEAD and not baseline['staged']
    existing_exclusions = [s.split('=', 1)[1] for s in read(REFERENCE / 'run.json')['command']
                           if s.startswith('--ignore=')]
    assert set(existing_exclusions) == set(HEAD_EXCLUSIONS) and len(existing_exclusions) == 12
    assert len(CURRENT_REGRESSION_TESTS) == len(set(CURRENT_REGRESSION_TESTS))
    assert HISTORICAL_CERTIFICATION_ARTIFACTS == [
        'tests/knowledge_inputs_v1/test_k8_post_cert_conflict.py',
        'tests/knowledge_inputs_v1/test_k8_quality.py']
    found = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests').rglob('*.py')
             if fnmatch.fnmatch(p.name, 'test_*.py') or fnmatch.fnmatch(p.name, '*_test.py')}
    knowledge = {p for p in found if p.startswith('tests/knowledge_inputs_v1/')}
    assert knowledge == set(CURRENT_REGRESSION_TESTS) | set(HISTORICAL_CERTIFICATION_ARTIFACTS)
    assert not set(CURRENT_REGRESSION_TESTS) & set(HISTORICAL_CERTIFICATION_ARTIFACTS)
    selection = sorted((found - knowledge - set(existing_exclusions)) | set(CURRENT_REGRESSION_TESTS))
    assert set(selection) | set(existing_exclusions) | set(HISTORICAL_CERTIFICATION_ARTIFACTS) == found
    dump('selection.json', dict(classificationStatus='PASS',
        classificationManifest=dict(path='tests/knowledge_inputs_v1/k8_regression_manifest.py',
            sha256=before['tests/knowledge_inputs_v1/k8_regression_manifest.py']),
        CURRENT_REGRESSION_TESTS=CURRENT_REGRESSION_TESTS,
        HISTORICAL_CERTIFICATION_ARTIFACTS=HISTORICAL_CERTIFICATION_ARTIFACTS,
        currentHeadSelection=selection, inheritedNativeCIExclusions=existing_exclusions,
        newExclusions=[], historicalScorersExecuted=False))
    before_integrity = integrity()
    baseline_skips = skip_rows(REFERENCE / 'tests.xml')
    assert len(baseline_skips) == 11
    dump('preflight.json', dict(at=datetime.now(timezone.utc).isoformat(),
        runtime=sys.executable, python=platform.python_version(), baseline=baseline,
        repositoryPins=before, integrity=before_integrity, baselineSkipIds=baseline_skips,
        referenceXML=dict(path=str(REFERENCE / 'tests.xml'), sha256=sha(REFERENCE / 'tests.xml')),
        preservedStates=STATES, runnerSha256=sha(__file__)))
    env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'COMSPEC',
        'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
        'PROGRAMDATA', 'LANG', 'LC_ALL') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT) + os.pathsep + str(SITE))
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME',
                'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TEMP', 'TMP'):
        folder = OUT / 'private' / ('profile' if key in ('HOME', 'USERPROFILE') else key.lower())
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    command = [str(PYTHON), '-B', str(Path(__file__).resolve()), '--worker']
    print(json.dumps(dict(started=True, output=str(OUT), headTestFiles=len(selection),
        knowledgeCurrentFiles=len(CURRENT_REGRESSION_TESTS), historicalArtifacts=2,
        inheritedCIExclusions=12, newExclusions=0, repositoryPins=len(before))), flush=True)
    with (OUT / 'run.log').open('x', encoding='utf-8') as stream:
        code = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                              stderr=subprocess.STDOUT).returncode
    dump('run.json', dict(mode='HEAD_CURRENT_REGRESSION_CLOSURE', command=command,
        pytestArguments=['-q', '-p', 'no:cacheprovider', '--maxfail=1',
            '--basetemp', str(OUT / 'pytest-private'), '--junitxml', str(OUT / 'tests.xml'), *selection],
        python=sys.version, privateState=True, exitCode=code, noExternalInference=True,
        offlineDependencies=str(SITE)))
    after = inventory()
    unchanged = before == after and baseline == identity()
    dump('preservation.json', dict(repositoryUnchanged=unchanged,
        changed=[p for p in set(before) | set(after) if before.get(p) != after.get(p)],
        metadataBefore=baseline, metadataAfter=identity(), repositoryFiles=len(before)))
    after_integrity = integrity()
    tree = ET.parse(OUT / 'tests.xml')
    cases = tree.findall('.//testcase')
    failures = [n for n in cases if n.find('failure') is not None]
    errors = [n for n in cases if n.find('error') is not None]
    skips = skip_rows(OUT / 'tests.xml')
    audit = read(OUT / 'execution-audit.json')
    collection = read(OUT / 'collection.json')
    assert not any(p.split('::', 1)[0] in HISTORICAL_CERTIFICATION_ARTIFACTS
                   for p in collection['nodeids'])
    success = code == 0 and not failures and not errors and skips == baseline_skips and unchanged
    success = success and not audit['xfailReports']
    first = (failures + errors)[0] if failures or errors else None
    result = dict(at=datetime.now(timezone.utc).isoformat(),
        verdict='KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS' if success else 'HEAD_CLOSURE_NOT_PASS',
        headCurrentRegression='PASS' if success else 'FAIL_OR_REQUIREMENT_NOT_MET',
        exitCode=code, xmlTestcases=len(cases), collectedTests=collection['collectedCount'],
        passedXMLTestcases=len(cases)-len(failures)-len(errors)-len(skips),
        failures=len(failures), errors=len(errors), skips=len(skips), skipIds=skips,
        exactlySameHistoricalSkips=skips == baseline_skips, newXfails=len(audit['xfailReports']),
        newExclusions=0, classification='PASS', historicalArtifactIntegrity='PASS',
        integrityBefore=before_integrity, integrityAfter=after_integrity,
        preservation=read(OUT / 'preservation.json'), preservedStates=STATES,
        firstFailure=None if first is None else dict(id=test_id(first),
            detail=ET.tostring(first, encoding='unicode'), classification='PENDING_HUMAN_REVIEW'),
        historicalScorersExecuted=False, certificationV2=False, ready=False, commit=False, push=False, tag=False,
        logSummary=(OUT / 'run.log').read_text(encoding='utf-8').splitlines()[-1],
        artifacts=[dict(path=str(OUT / n), sha256=sha(OUT / n)) for n in
            ('verify_head.py', 'preflight.json', 'selection.json', 'collection.json',
             'execution-audit.json', 'run.json', 'run.log', 'tests.xml', 'preservation.json')])
    dump('head-closure-evidence.json', result)
    print(json.dumps({k: result[k] for k in ('verdict', 'logSummary', 'failures', 'errors',
        'skips', 'exactlySameHistoricalSkips', 'newXfails', 'newExclusions', 'historicalArtifactIntegrity')},
        ensure_ascii=False), flush=True)
    raise SystemExit(0 if success else 1)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        dump('verification-error.json', dict(error=traceback.format_exc()))
        raise
