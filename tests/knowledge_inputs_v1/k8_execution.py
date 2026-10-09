"""Strict K8 exam/product reconciliation. CLI is preflight-only, never inference.

No historical verifier or scorer is replaced. A future explicitly authorized
caller can use run_verified_campaign(); it rechecks both identities and calls
the untouched original campaign with a complete, reconciled verification list.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HEAD = '717a24218dea7fb60d8b630896d653e39091bc7b'
ORIGINAL = 'docs/knowledge_inputs_v1/k8_evidence/e2e_freeze_v1.json'
V6 = 'docs/knowledge_inputs_v1/k8_repair6_manifest.json'
PRIOR_PREFLIGHT = 'docs/knowledge_inputs_v1/k8_final_manifest.json'
EXECUTION = 'docs/knowledge_inputs_v1/k8_evidence/e2e_execution_freeze_v2.json'
WRAPPER = 'tests/knowledge_inputs_v1/k8_execution.py'
CONTRACTS = 'tests/knowledge_inputs_v1/test_k8_execution.py'
ANCHORS = {
    ORIGINAL: '2c95d25b26d90e11e1333a5d5f1db6ae45fe09813b06a094b9d1649e9a6009e9',
    V6: 'facc970921ec1cc5f21ebd3c52f5a4487a4d7870089e31ac6e3443b160a2217a',
    PRIOR_PREFLIGHT: 'fe95db125391a3605d1a73005271331c893822717ca169678221686e2c3e5de3',
}
EXAM_ANCHORS = {
    'tests/knowledge_inputs_v1/fixtures/k8_core_v1.json': '832be39fa3efa475cd74b89c8f5d1632e445f5a6a67cecb72833d4f12814cd1a',
    'tests/knowledge_inputs_v1/fixtures/k8_protocol_v1.json': 'c0eb231bb2cbc812e49524cd295dc237c29265d4b4671cf7c2d97c285e11c092',
    'tests/knowledge_inputs_v1/run_k8_e2e.py': '27b745dc3a6a087c61156c10ed47ed03bd6f7df0c4cc5f787fdfda5645d46c4b',
    'docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md': '417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432',
}
AUTHORIZED_NEW_FILES = (
    EXECUTION, WRAPPER, CONTRACTS,
    'docs/knowledge_inputs_v1/k8_execution_preflight_resultados.md',
    'docs/knowledge_inputs_v1/k8_execution_preflight_manifest.json',
    'docs/knowledge_inputs_v1/k8_execution_evidence/preflight_v2.json',
)


class ExecutionIntegrityError(RuntimeError):
    """Fail closed before inference; not a new Core/Security contract."""


def _relative(path):
    p = PurePosixPath(path)
    if '\\' in path or ':' in path or p.is_absolute() or '..' in p.parts or str(p) != path:
        raise ExecutionIntegrityError('NON_CANONICAL_REPOSITORY_PATH: ' + path)
    return path


def _hash(path):
    if not path.is_file():
        raise ExecutionIntegrityError('MISSING_FILE: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_pins(rows):
    for row in rows:
        path = Path(row['path'])
        if not path.is_absolute():
            path = ROOT / _relative(row['path'])
        if _hash(path) != row['sha256']:
            raise ExecutionIntegrityError('HASH_MISMATCH: ' + row['path'])


def _load(path):
    return json.loads((ROOT / _relative(path)).read_text(encoding='utf-8'))


def _git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def _product(path):
    return path.startswith(('local_cli/', 'desktop/')) or path == 'pyproject.toml'


def _rows(pins):
    return [dict(path=path, sha256=sha) for path, sha in sorted(pins.items())]


def _merge(pins, rows, *, override=False):
    for row in rows:
        path = _relative(row['path'])
        if path in pins and pins[path] != row['sha256'] and not override:
            raise ExecutionIntegrityError('CONFLICTING_PIN: ' + path)
        pins[path] = row['sha256']


def _head_pins(overrides):
    """Prove canonical HEAD content, then bind exact Windows checkout bytes.

    Git blobs are LF-normalized, unlike some evaluated clean CRLF files. Never
    normalize an existing historical pin. Only previously unpinned clean files
    use Git's read-only canonical-content proof; execution then fixes raw SHA.
    """
    entries = []
    for entry in _git('ls-tree', '-rz', '--full-tree', HEAD).split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, oid = meta.split()
        if kind != b'blob':
            raise ExecutionIntegrityError('UNSUPPORTED_GIT_ENTRY: ' + name.decode())
        entries.append((_relative(name.decode('utf-8')), oid.decode('ascii')))
    clean = [(name, oid) for name, oid in entries if name not in overrides]
    attrs = subprocess.check_output(['git', 'check-attr', '-z', '--stdin', 'filter'], cwd=ROOT,
        input=b'\0'.join(name.encode('utf-8') for name, _ in clean) + b'\0').split(b'\0')
    # Do not start custom filter processes (including LFS) during preflight.
    if any(value not in (b'unspecified', b'unset') for value in attrs[2::3]):
        raise ExecutionIntegrityError('EXTERNAL_GIT_FILTER_NOT_ALLOWED')
    paths = ('\n'.join(json.dumps(name, ensure_ascii=False) for name, _ in clean) + '\n').encode('utf-8')
    actual = subprocess.check_output(['git', 'hash-object', '--stdin-paths'], cwd=ROOT, input=paths).decode().splitlines()
    if len(actual) != len(clean):
        raise ExecutionIntegrityError('INCOMPLETE_HEAD_CONTENT_PROOF')
    for (name, expected), oid in zip(clean, actual):
        if oid != expected:
            raise ExecutionIntegrityError('UNAUTHORIZED_HEAD_CONTENT_DRIFT: ' + name)
    pins = {name: _hash(ROOT / name) for name, _ in clean}
    pins.update({name: overrides[name] for name, _ in entries if name in overrides})
    return pins, dict(headEntries=len(entries), canonicalCleanFilesVerified=len(clean),
        cleanCanonicalContentChanges=0, externalFiltersInvoked=0,
        byteContract='Exact checkout SHA-256 after canonical HEAD proof; no historical pin normalized')


def _walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _historical_pins(v6):
    """Same absolute evidence references preserved by the V6 collector."""
    pins = {}
    for manifest in v6['history']['manifests']:
        value = json.loads(Path(manifest['path']).read_text(encoding='utf-8'))
        for row in _walk(value):
            path, sha = row.get('path'), row.get('sha256')
            if path and sha and Path(path).is_absolute():
                if path in pins and pins[path] != sha:
                    raise ExecutionIntegrityError('CONFLICTING_HISTORICAL_PIN: ' + path)
                pins[path] = sha
    if len(pins) != v6['history']['historicalArtifactsChecked']:
        raise ExecutionIntegrityError('INCOMPLETE_HISTORICAL_EVIDENCE_INVENTORY')
    return _rows(pins)


def _native_profile():
    if os.name != 'nt' or int(platform.version().split('.')[2]) < 22000:
        raise ExecutionIntegrityError('WINDOWS_11_CERTIFIED_PROFILE_REQUIRED')
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    root = ROOT.anchor
    kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel.GetDriveTypeW.restype = wintypes.UINT
    if kernel.GetDriveTypeW(root) != 3:
        raise ExecutionIntegrityError('LOCAL_FIXED_VOLUME_REQUIRED')
    fs = ctypes.create_unicode_buffer(32)
    kernel.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumeInformationW.restype = wintypes.BOOL
    if not kernel.GetVolumeInformationW(root, None, 0, None, None, None, fs, len(fs)) or fs.value != 'NTFS':
        raise ExecutionIntegrityError('NTFS_REQUIRED')
    return dict(platform=platform.platform(), filesystem=fs.value, driveType='LOCAL_FIXED',
                processModel='HOST_UNISOLATED')


def _expected_state():
    # 1. Original exam bytes, including gold/protocol/scorer/thresholds.
    _check_pins(_rows(EXAM_ANCHORS))
    # 2. Historical freeze itself: never revised or passed off as current product.
    _check_pins([dict(path=ORIGINAL, sha256=ANCHORS[ORIGINAL])])
    original = _load(ORIGINAL)
    exam = {row['path']: row['sha256'] for row in original['files'] if not _product(row['path'])}
    _merge(exam, _rows(EXAM_ANCHORS))
    _check_pins(_rows(exam))
    # 3. Complete V6 derivation, not a hand-selected 11-file reconciliation.
    _check_pins([dict(path=p, sha256=ANCHORS[p]) for p in (V6, PRIOR_PREFLIGHT)])
    v6 = _load(V6)
    if v6['verdict'] != 'K8 REPAIR V6 PASS' or v6['baseline']['head'] != HEAD:
        raise ExecutionIntegrityError('V6_PASS_BASELINE_REQUIRED')
    if _git('rev-parse', 'HEAD').decode().strip() != HEAD or _git('branch', '--show-current').decode().strip() != 'main':
        raise ExecutionIntegrityError('BASELINE_CHANGED')
    _check_pins(v6['artifacts'])
    _check_pins(v6['history']['manifests'])
    prior = _load(v6['baseline']['preflight'])
    integrity = _load('docs/knowledge_inputs_v1/k8_repair6_evidence/integrity_v1.json')
    if sorted(row['path'] for row in integrity['changes']) != sorted(v6['baseline']['authorizedDelta']):
        raise ExecutionIntegrityError('V6_DELTA_IDENTITY_CHANGED')
    overrides = {row['path']: row['sha256'] for row in prior['pins']}
    for delta in integrity['changes']:
        if overrides[delta['path']] != delta['before']:
            raise ExecutionIntegrityError('V6_BEFORE_PIN_MISMATCH')
        overrides[delta['path']] = delta['after']
    _check_pins(_rows(overrides))
    repo, checkout_proof = _head_pins(overrides)
    _merge(repo, _rows(overrides), override=True)
    relative_artifacts = [row for row in v6['artifacts'] if not Path(row['path']).is_absolute()]
    _merge(repo, relative_artifacts)  # Overlap must agree; cannot hide a stale V6 pin.
    _merge(repo, [dict(path=V6, sha256=ANCHORS[V6])])
    v6_repo = repo.copy()
    # Three already-authorized preflight evidence additions are not product.
    prior_report = _load(PRIOR_PREFLIGHT)
    _check_pins(prior_report['artifacts'])
    _merge(repo, prior_report['artifacts'])
    _merge(repo, [dict(path=PRIOR_PREFLIGHT, sha256=ANCHORS[PRIOR_PREFLIGHT])])
    artifacts = [dict(path=p, sha256=_hash(ROOT / p)) for p in (WRAPPER, CONTRACTS)]
    _merge(repo, artifacts)
    product = {p: sha for p, sha in v6_repo.items() if _product(p)}
    history = _historical_pins(v6)
    _check_pins(history)
    tags = _git('show-ref', '--tags').decode().splitlines()
    if tags != prior['tags'] or _git('diff', '--cached', '--name-only').strip():
        raise ExecutionIntegrityError('TAGS_OR_STAGING_CHANGED')
    return dict(schemaVersion=1, purpose='certification execution reconciliation',
        examIdentity='ORIGINAL_K8_E2E', productIdentity='POST_K8_REPAIR_V6',
        head=HEAD, branch='main', platform='Windows 11 + local NTFS + HOST_UNISOLATED',
        originalFreeze=dict(path=ORIGINAL, sha256=ANCHORS[ORIGINAL]),
        v6Manifest=dict(path=V6, sha256=ANCHORS[V6]),
        originalExamAnchors=_rows(EXAM_ANCHORS), examPins=_rows(exam), productPins=_rows(product),
        productDerivation=dict(baseHead=HEAD, completeV6PreflightPins=len(overrides),
            finalManifestArtifactReferences=len(v6['artifacts']),
            authorizedV6Delta=integrity['changes'], unchangedFiles=checkout_proof,
            selection='All repository product files: local_cli/**, desktop/**, pyproject.toml'),
        v6RepositoryPins=_rows(v6_repo), files=_rows(repo),
        historicalEvidencePins=history, reconciliationArtifacts=artifacts,
        authorizedNewFiles=list(AUTHORIZED_NEW_FILES), tags=tags,
        noExamArtifactRepinned=True, originalHarnessUnmodified=True,
        noGenericVerificationBypass=True, qualityRepeatConsumed=False)


def build_definition():
    """Read-only builder; agent saves this new artifact using file-edit tools."""
    value = _expected_state()
    value['createdAt'] = datetime.now(timezone.utc).isoformat()
    return value


def _check_definition(actual, expected):
    if set(actual) != set(expected) | {'createdAt'}:
        raise ExecutionIntegrityError('EXECUTION_FREEZE_SCHEMA_CHANGED')
    for key, value in expected.items():
        if actual[key] != value:
            raise ExecutionIntegrityError('EXECUTION_IDENTITY_CHANGED: ' + key)
    datetime.fromisoformat(actual['createdAt'])


def _check_inventory(rows, actual):
    expected = {row['path'] for row in rows}
    missing = sorted(expected - actual)
    additions = sorted(actual - expected - set(AUTHORIZED_NEW_FILES))
    if missing or additions:
        raise ExecutionIntegrityError('UNEXPECTED_REPOSITORY_DRIFT: ' + json.dumps(
            dict(missing=missing, additions=additions)))


def preflight():
    started = datetime.now(timezone.utc).isoformat()
    expected = _expected_state()
    execution = _load(EXECUTION)
    _check_definition(execution, expected)
    # 4. Detect additions/removals and changes across the complete evaluated tree.
    inventory = {_relative(p.decode('utf-8')) for p in
                 _git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0') if p}
    _check_inventory(expected['files'], inventory)
    _check_pins(expected['files'])
    native = _native_profile()
    corpus = _load('tests/knowledge_inputs_v1/fixtures/k8_core_v1.json')
    ids = [case['id'] for case in corpus['e2e']]
    if len(ids) != 14 or len(set(ids)) != 14:
        raise ExecutionIntegrityError('ORIGINAL_14_CASES_REQUIRED')
    return dict(schemaVersion=1, verdict='K8 E2E EXECUTION PREFLIGHT PASS',
        examIdentity=execution['examIdentity'], productIdentity=execution['productIdentity'],
        startUtc=started, endUtc=datetime.now(timezone.utc).isoformat(),
        runtime=dict(executable=sys.executable, python=platform.python_version()), nativeProfile=native,
        branch='main', head=HEAD, originalExamIdentity='PASS', originalFreezeUnchanged='PASS',
        v6ProductIdentity='PASS', unexpectedProductDrift=0, unexpectedRepositoryDrift=0,
        scorerProtocolGoldChanges=0, historicalEvidenceChanges=0,
        productPinCount=len(expected['productPins']), v6RepositoryPinCount=len(expected['v6RepositoryPins']),
        fullRepositoryPinCount=len(expected['files']), examPinCount=len(expected['examPins']),
        historicalEvidencePinCount=len(expected['historicalEvidencePins']),
        executionFreeze=dict(path=EXECUTION, sha256=_hash(ROOT / EXECUTION)),
        originalFreeze=execution['originalFreeze'], v6Manifest=execution['v6Manifest'],
        productPins=expected['productPins'], examPins=expected['examPins'],
        reconciliationArtifacts=expected['reconciliationArtifacts'], caseIds=ids, tags=expected['tags'],
        campaignExecuted=False, inferenceCalls=0, networkCalls=0, qualityRepeatConsumed=False,
        quality='NOT_EVALUATED', ready=False)


def run_verified_campaign(out):
    """Future explicit human authorization required; not invoked by this CLI.

    Original verify() still runs over every reconciled file. No function patch,
    filtered cases, changed scorer, retry, or altered historical artifact.
    """
    out = Path(out).resolve()
    if out.exists() or out == ROOT or ROOT in out.parents:
        raise ExecutionIntegrityError('FRESH_EXTERNAL_OUTPUT_REQUIRED')
    preflight()
    execution = _load(EXECUTION)
    from tests.knowledge_inputs_v1 import run_k8_e2e as original
    return original.run_campaign(out, execution)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Fresh preflight output outside Git')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or out == ROOT or ROOT in out.parents:
        parser.error('Fresh output outside Git required')
    try:
        result = preflight()
    except (ExecutionIntegrityError, OSError, ValueError) as exc:
        result = dict(verdict='K8 E2E EXECUTION PREFLIGHT BLOCKED', error=str(exc),
                      campaignExecuted=False, inferenceCalls=0, qualityRepeatConsumed=False)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'preflight.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['verdict'].endswith(' PASS') else 1)


if __name__ == '__main__':
    main()
