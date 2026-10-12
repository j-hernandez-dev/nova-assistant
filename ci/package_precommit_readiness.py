"""Freeze public pre-commit readiness evidence; never stage, commit or release.

Only current counters, hashes and reviewed metadata are published. Raw pytest
stdout/XML failure bodies, credentials and fixture directories remain in temp.
The output is one new additive namespace; B0-B7 are read, never rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from contract_inventory import MANIFEST as CONTRACT_MANIFEST, ROOT, select, validate
from sanitize_reports import SAFE_RUN_FIELDS


OUTPUT = ROOT / 'docs/active_web_v1_2/pre_commit_readiness'
B7 = ROOT / 'docs/active_web_v1_2/v12_b7_final_e2e'
REQUIRED_JOBS = ('core', 'security', 'memory', 'knowledge', 'active-web',
    'web-v12', 'web-v12-windows', 'web-v12-windows-native')
ARTIFACT_NAMES = ('resultados.md', 'gitignore_audit.json', 'gitignore_audit.md',
    'tracked_untracked_inventory.json', 'ci_audit.json', 'ci_audit.md',
    'ci_inventory_results.json', 'workflow_validation.json', 'local_preflight_results.json',
    'final_git_status.txt', 'manifest.json')
STATE = dict(ACTIVE_WEB_V1_2_ARCHITECTURE='APPROVED',
    V12_B0='PASS', V12_B1='PASS', V12_B2='PASS', V12_B3='PASS', V12_B4='PASS', V12_B5='PASS', V12_B6='PASS',
    V12_B7='PASS', ACTIVE_WEB_V1_2_FINAL='PASS', ACTIVE_WEB_V1_2='READY',
    READY_FOR_HUMAN_RELEASE_DECISION=True, RELEASE_APPROVED=False,
    ACTIVE_WEB_CORE='NOT_READY', AW8='BLOCKED',
    WEBVIEW2_REMEDIATION_BLOCK_05_FINAL='PASS',
    WEBVIEW2_BLOCK06_ARCHITECTURE='BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT',
    CEF_CHROMIUM_STANDARD_CANDIDATE='REJECTED', SOURCE_CONTROLLED_CHROMIUM='REQUIRES_SOURCE_PROTOTYPE',
    CONTROLLED_FETCH_NETWORK_EGRESS_CONTROL='ENFORCED', CONTROLLED_FETCH_PUBLIC_ONLY='ENFORCED',
    CONTROLLED_FETCH_EVIDENCE_PROFILE='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1',
    INTERACTIVE_BROWSER_NETWORK_ISOLATION='NOT_PROVIDED', INTERACTIVE_BROWSER_CONTROL_CLASS='HOST_UNISOLATED')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def git(*arguments, stdin=None):
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run(['git', '-c', 'core.longpaths=true', '-c',
        'safe.directory=' + str(ROOT), *arguments], cwd=ROOT, input=stdin,
        capture_output=True, timeout=90, env=environment,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.returncode, result.stdout, result.stderr


def require_temp(path):
    path = Path(path).resolve()
    if not path.is_absolute() or not path.is_dir() or path.is_relative_to(ROOT):
        raise ValueError('INPUT_MUST_BE_EXISTING_OWNED_TEMP_OUTSIDE_REPOSITORY')
    return path


def write(name, value):
    (OUTPUT/name).write_text(value if isinstance(value, str) else
        json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def in_current_output(path):
    prefix = OUTPUT.relative_to(ROOT).as_posix() + '/'
    return path.replace('\\', '/').startswith(prefix)


def resume_incomplete_output(audit):
    """Resume only this phase's exact nine-file unfinished assembly.

    Existing frozen results/manifests, reparse points and foreign files fail
    closed. Capture immutable hash-only failure metadata in owned audit temp
    before any output file can be overwritten; publish it in the final manifest.
    """
    if not OUTPUT.is_dir():
        raise ValueError('RESUME_REQUIRES_EXACT_EXISTING_INCOMPLETE_NAMESPACE')
    for path in (OUTPUT, *OUTPUT.parents):
        if path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('RESUME_NAMESPACE_REPARSE_DENIED')
        if path == ROOT:
            break
    partial_names = set(ARTIFACT_NAMES) - {'resultados.md', 'manifest.json'}
    children = list(OUTPUT.iterdir())
    if {path.name for path in children} != partial_names:
        raise ValueError('RESUME_REQUIRES_EXACT_NINE_PARTIAL_ARTIFACTS_WITHOUT_FROZEN_RESULT')
    if any(not path.is_file() or path.is_symlink() or
            bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400) for path in children):
        raise ValueError('RESUME_NAMESPACE_FOREIGN_RESOURCE_OR_REPARSE_DENIED')
    owner = load(OUTPUT/'tracked_untracked_inventory.json').get('precommitEvidenceGroup', {})
    expected_paths = [(OUTPUT/name).relative_to(ROOT).as_posix() for name in ARTIFACT_NAMES]
    if (owner.get('group') != 'PRECOMMIT_EVIDENCE_GENERATED_AFTER_SOURCE_AUDIT' or
            owner.get('paths') != expected_paths or
            owner.get('sourceGenerator', {}).get('path') != 'ci/package_precommit_readiness.py' or
            owner.get('hashesRecordedIn') != 'manifest.json'):
        raise ValueError('RESUME_NAMESPACE_PHASE_OWNERSHIP_UNCONFIRMED')
    attempt = dict(schemaVersion=1, phase='PRE_COMMIT_REPOSITORY_AND_CI_READINESS',
        outcome='INCOMPLETE_ASSEMBLY', cause='REPORT_ASSEMBLY_ERROR',
        capturedBeforeOverwrite=True, namespace=OUTPUT.relative_to(ROOT).as_posix(),
        previousGenerator=owner['sourceGenerator'], rawFailureBodyPublished=False,
        capturedAt=datetime.now(timezone.utc).isoformat(),
        artifacts=[dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
            for path in sorted(children)])
    ordinal = 1
    while (audit/f'failed_assembly_attempt_{ordinal:02d}.json').exists():
        ordinal += 1
    receipt = audit/f'failed_assembly_attempt_{ordinal:02d}.json'
    with receipt.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(attempt, ensure_ascii=False, indent=2)+'\n')
    return dict(metadata=attempt, receiptSha256=sha(receipt), receiptTempName=receipt.name)


def counters(path):
    counts = Counter()
    for case in ET.parse(path).iter('testcase'):
        state = next((kind for kind in ('failure', 'error', 'skipped') if case.find(kind) is not None), 'passed')
        counts[state] += 1
    return dict(counts)


def safe_receipt(run):
    public = {key: run[key] for key in SAFE_RUN_FIELDS if key in run}
    # These are closed counters/booleans, never test bodies or parameter values.
    for key in ('public_report_counts', 'parameter_values_published', 'raw_failure_bodies_published'):
        if key in run:
            public[key] = run[key]
    cleanup = run.get('native_ci_profile_cleanup')
    if isinstance(cleanup, dict):
        public['native_ci_profile_cleanup'] = {key: cleanup[key] for key in
            ('status', 'owned_profile_absent') if key in cleanup}
    return public


def attempt_receipt(folder):
    raw = load(folder/'run.json')
    public_path = folder/'public/run.json'
    public = load(public_path) if public_path.is_file() else safe_receipt(raw)
    # Reproject even a public file rather than copying an unchecked object.
    receipt = safe_receipt(public)
    selection = load(folder/'selection.json') if (folder/'selection.json').is_file() else []
    collected = load(folder/'collected_nodeids.json') if (folder/'collected_nodeids.json').is_file() else []
    observed = counters(folder/'tests.xml') if (folder/'tests.xml').is_file() else public.get('public_report_counts', {})
    references = {name: sha(folder/name) for name in ('run.json', 'selection.json', 'collected_nodeids.json', 'tests.xml', 'pytest.log')
        if (folder/name).is_file()}
    return dict(attempt=folder.name, receipt=receipt, countedResults=observed,
        sourceSha256=references, sourceMtime=(folder/'run.json').stat().st_mtime), selection, collected, raw


def preflight_evidence(preflight, data, blockers):
    attempts = []
    private = {}
    for folder in sorted(preflight.iterdir()):
        if not folder.is_dir() or not (folder/'run.json').is_file():
            continue
        row, selection, collected, raw = attempt_receipt(folder)
        if row['receipt'].get('job') not in REQUIRED_JOBS:
            continue
        attempts.append(row)
        private[folder.name] = (selection, collected, raw)
    latest = []
    selected_union = set()
    collected_union = set()
    logical_cases = set()
    case_cardinality_by_function = {}
    overlap_cardinality_mismatches = []
    for job in REQUIRED_JOBS:
        matching = [row for row in attempts if row['receipt'].get('job') == job]
        if not matching:
            blockers.append('LOCAL_PREFLIGHT_MISSING:' + job)
            latest.append(dict(job=job, status='MISSING'))
            continue
        chosen = max(matching, key=lambda row: (row['sourceMtime'], row['attempt']))
        selection, collected, raw = private[chosen['attempt']]
        receipt = chosen['receipt']
        host = receipt.get('host')
        try:
            current = select(data, job, host, special=False)
        except Exception:
            current = []
        exact = (type(selection) is list and bool(current) and selection == current and
            len(selection) == len(set(selection)))
        count = chosen['countedResults']
        clean = (receipt.get('exit_code') == 0 and receipt.get('scope') == 'CURRENT_REGRESSION_CONTRACT' and
            receipt.get('collection_guard') == 'PASS' and receipt.get('tests_executed', 0) > 0 and
            receipt.get('tests_executed') == receipt.get('collected_parameter_instances') == len(collected) and
            sum(count.values()) == len(collected) and count.get('passed') == len(collected) and
            not count.get('failure', 0) and not count.get('error', 0) and not count.get('skipped', 0) and
            receipt.get('zero_collected') is False and receipt.get('execution_complete') is True and
            receipt.get('new_skips_xfails_or_deselection') is False and
            not raw.get('skip_xfail_reports') and raw.get('bootstrap_error_class') is None and
            raw.get('quality_attempts') == 0 and raw.get('model_campaigns') == 0 and exact)
        if job == 'web-v12-windows-native':
            cleanup = raw.get('native_ci_profile_cleanup', {})
            clean = clean and host == 'Windows' and cleanup.get('status') == 'CONFIRMED' and cleanup.get('owned_profile_absent') is True
        if not clean:
            blockers.append('LOCAL_PREFLIGHT_NOT_CURRENT_COMPLETE_PASS:' + job)
        selected_union.update(selection)
        collected_union.update(collected)
        # Generated opaque parameter values can change across repeated jobs.
        # Deduplicate the fixed corpus by base function and collected case
        # ordinal; first verify every overlapping function has the same size.
        ordinal_by_function = Counter()
        for nodeid in collected:
            base = nodeid.split('[', 1)[0]
            logical_cases.add((base, ordinal_by_function[base]))
            ordinal_by_function[base] += 1
        for base, cardinality in ordinal_by_function.items():
            previous = case_cardinality_by_function.get(base)
            if previous is not None and previous != cardinality:
                overlap_cardinality_mismatches.append(dict(baseFunction=base,
                    previousCaseCount=previous, currentCaseCount=cardinality, job=job))
            case_cardinality_by_function[base] = cardinality
        latest.append(dict(job=job, attempt=chosen['attempt'], status='PASS' if clean else 'FAIL',
            receipt=receipt, countedResults=count, selectorsMatchCurrent=exact,
            currentSelectorSha256=hashlib.sha256(json.dumps(current, ensure_ascii=False).encode()).hexdigest(),
            selectionManifestMatchesCurrentHash=receipt.get('selection_manifest_sha256') == sha(CONTRACT_MANIFEST),
            sourceSha256=chosen['sourceSha256']))
    failures = [dict(attempt=row['attempt'], job=row['receipt'].get('job'), exitCode=row['receipt'].get('exit_code'),
        countedResults=row['countedResults'], sourceSha256=row['sourceSha256']) for row in attempts
        if row['receipt'].get('exit_code') != 0 or row['countedResults'].get('failure') or row['countedResults'].get('error') or row['countedResults'].get('skipped')]
    if overlap_cardinality_mismatches:
        blockers.append('LOCAL_PREFLIGHT_OVERLAP_PARAMETER_CARDINALITY_MISMATCH')
    return dict(schemaVersion=1, scope='LATEST_COMPLETE_OFFICIAL_LOCAL_CI_SELECTION_PER_JOB',
        latest=latest, priorFailedAttempts=failures, attemptsObserved=len(attempts),
        passedRepetitionsSummed=False, distinctLatestBaseContracts=len(selected_union),
        rawDistinctLatestParameterNodeIds=len(collected_union), distinctLatestParameterCases=len(logical_cases),
        denominatorMethod='CANONICAL_BASE_FUNCTION_PLUS_COLLECTED_CASE_ORDINAL_IN_FIXED_CORPUS',
        overlapCountMismatch=len(overlap_cardinality_mismatches),
        overlapCardinalityMismatches=overlap_cardinality_mismatches, rawBodiesOrStdoutPublished=False,
        GitHubActionsRunExecuted=False, certificationReplay=False)


def adapter_evidence(preflight, local, blockers):
    selected = next((row for row in local['latest'] if row['job'] == 'web-v12-windows-native'), {})
    path = preflight/selected.get('attempt', '')/'windows_adapter_smoke.json'
    if not path.is_file():
        blockers.append('LOCAL_NATIVE_ADAPTER_RECEIPT_MISSING')
        return dict(status='MISSING', scope='CURRENT_WINDOWS_ADAPTER_REGRESSION')
    data = load(path)
    runtime = data.get('observedRuntime', {})
    okay = (data.get('scope') == 'CURRENT_WINDOWS_ADAPTER_REGRESSION' and
        data.get('guardInstalled') is True and data.get('fixedObservationReturned') is True and
        data.get('cleanup') == 'CONFIRMED' and data.get('listenerClosed') is True and
        data.get('ownedUdfAbsent') is True and data.get('nativeCertification') is False and
        data.get('B7Recertification') is False and data.get('networkIsolation') == 'NOT_PROVIDED' and
        data.get('controlClass') == 'HOST_UNISOLATED' and data.get('engineDownloadedByTest') is False)
    if not okay:
        blockers.append('LOCAL_NATIVE_ADAPTER_RECEIPT_NOT_PASS')
    return dict(status='PASS' if okay else 'FAIL', scope=data.get('scope'), sdk=data.get('sdk'),
        observedRuntime={key: runtime.get(key) for key in ('engine', 'sdkVersion', 'runtimeVersion', 'architecture', 'platform')},
        guardInstalled=data.get('guardInstalled'), fixedObservationReturned=data.get('fixedObservationReturned'),
        cleanup=data.get('cleanup'), listenerClosed=data.get('listenerClosed'), ownedUdfAbsent=data.get('ownedUdfAbsent'),
        nativeCertification=False, B7Recertification=False, networkIsolation='NOT_PROVIDED',
        controlClass='HOST_UNISOLATED', sourceSha256=sha(path), instanceRefsOrRawBodiesPublished=False)


def workflow_evidence(folder, blockers):
    current = folder/'current_review'
    review_path = current/'workflow_review.json'
    action_path = current/'actionlint_result.json'
    if not review_path.is_file() or not action_path.is_file():
        blockers.append('CURRENT_WORKFLOW_VALIDATION_RECEIPT_MISSING')
        return dict(schemaVersion=1, result='MISSING', rows=[], desktop=dict(status='MISSING'),
            GitHubActionsRunExecuted=False, workflowExecutionClaim=False)
    review, action = load(review_path), load(action_path)
    rows = []
    compatible = review.get('result') == 'PASS' and action.get('exitCode') == 0
    for row in review.get('rows', []):
        path = row['path'].replace('\\', '/')
        match = (ROOT/path).is_file() and sha(ROOT/path) == row['sha256']
        compatible &= match
        rows.append(dict(path=path, sha256=row['sha256'], currentBytesMatch=match,
            jobs=[dict(job=j['workflowJob'], officialSelectionJobs=[s['job'] for s in j.get('officialSelections', [])])
                for j in row.get('jobs', [])]))
    if not compatible:
        blockers.append('WORKFLOW_VALIDATION_NOT_CURRENT_PASS')
    observed = review.get('desktopObserved', {})
    temp_parent = folder.parent
    def receipt_path(key):
        raw = observed.get(key)
        if not isinstance(raw, str):
            raise ValueError('DESKTOP_RECEIPT_MISSING')
        path = (temp_parent/raw).resolve()
        if not path.is_relative_to(temp_parent) or not path.is_file():
            raise ValueError('DESKTOP_RECEIPT_OUTSIDE_OWNED_TEMP_OR_MISSING')
        return path
    desktop = dict(status='MISSING')
    try:
        log = receipt_path('desktopTestReceiptTempRelativePath')
        tsc_path = receipt_path('typecheckReceiptTempRelativePath')
        vite_path = receipt_path('viteBuildReceiptTempRelativePath')
        tsc, vite = load(tsc_path), load(vite_path)
        passed = (observed.get('tests') == observed.get('passed') == 105 and observed.get('skipped') == 0 and
            sha(log) == observed.get('logSha256') and tsc.get('exitCode') == 0 and vite.get('exitCode') == 0 and
            vite.get('scope') == 'ACTUAL_DESKTOP_VITE_SOURCE_BUILD_CHECK' and vite.get('installer') is False and
            vite.get('release') is False and vite.get('publish') is False)
        desktop = dict(status='PASS' if passed else 'FAIL', tests=observed.get('tests'), passed=observed.get('passed'),
            skipped=observed.get('skipped'), testsLogSha256=sha(log),
            typecheck=dict(exitCode=tsc.get('exitCode'), receiptSha256=sha(tsc_path)),
            ViteBuild=dict(exitCode=vite.get('exitCode'), receiptSha256=sha(vite_path),
                installer=False, release=False, publish=False), rawLogsPublished=False,
            fullElectronGuiE2EClaim=False)
        if not passed:
            blockers.append('DESKTOP_LOCAL_PREFLIGHT_NOT_PASS')
    except (OSError, ValueError, KeyError):
        blockers.append('DESKTOP_REQUIRED_RECEIPT_MISSING_OR_INVALID')
    return dict(schemaVersion=1, result='PASS' if compatible else 'FAIL',
        scope='CURRENT_WORKFLOW_STATIC_VALIDATION_NOT_ACTIONS_EXECUTION',
        sourceSha256=dict(workflowReview=sha(review_path), actionlint=sha(action_path)),
        actionlint=dict(exitCode=action.get('exitCode'), version=action.get('version')),
        rows=rows, desktop=desktop, GitHubActionsRunExecuted=False,
        workflowExecutionClaim=False, productCertificationClaim=False)


def frozen_evidence(blockers):
    integrity = load(B7/'integrity.json')
    identity = load(B7/'candidate_identity.json')
    mismatch = []
    for group in (integrity['artifactPins'], identity['productPins']):
        for row in group:
            path = Path(row['path'])
            path = path if path.is_absolute() else ROOT/path
            if not path.is_file() or sha(path) != row['sha256']:
                mismatch.append(dict(path=row['path'], expectedSha256=row['sha256']))
    if mismatch or integrity.get('result') != 'PASS':
        blockers.append('FROZEN_B7_OR_CANDIDATE_PIN_MISMATCH')
    # Byte filtering for the source/config identity used by host discovery.
    filter_rows = []
    skipped_filters = []
    for raw in sorted({row['path'] for row in identity['productPins']}):
        path = Path(raw)
        if path.is_absolute():
            try:
                raw = path.relative_to(ROOT).as_posix()
            except ValueError:
                skipped_filters.append(dict(path=raw, reason='ABSOLUTE_HOST_EXECUTABLE_OR_RUNTIME_OUTSIDE_GIT',
                    fileBytesStillVerifiedByCandidatePin=True))
                continue
        code1, unfiltered, _ = git('hash-object', '--no-filters', raw)
        code2, filtered, _ = git('hash-object', '--path='+raw, raw)
        match = code1 == code2 == 0 and unfiltered.strip() == filtered.strip()
        filter_rows.append(dict(path=raw, GitAddCheckoutFilterPreservesBytes=match))
    if any(not row['GitAddCheckoutFilterPreservesBytes'] for row in filter_rows):
        blockers.append('PINNED_SOURCE_GIT_FILTER_BYTE_DRIFT')
    return dict(result='PASS' if not mismatch and all(row['GitAddCheckoutFilterPreservesBytes'] for row in filter_rows) else 'FAIL',
        candidateId=identity['candidateId'], evidencePinsVerified=len(integrity['artifactPins']),
        candidatePinsVerified=len(identity['productPins']), mismatches=mismatch,
        sourceFilterChecks=filter_rows, sourceFilterChecksNotApplicable=skipped_filters, historicalStates=STATE,
        integritySha256=sha(B7/'integrity.json'), historicalBytesModified=False)


def package(audit, preflight, workflows, *, resume_incomplete=False):
    audit, preflight, workflows = map(require_temp, (audit, preflight, workflows))
    failed_assembly = resume_incomplete_output(audit) if resume_incomplete else None
    failed_assemblies = []
    for receipt in sorted(audit.glob('failed_assembly_attempt_*.json')):
        metadata = load(receipt)
        if (metadata.get('phase') != 'PRE_COMMIT_REPOSITORY_AND_CI_READINESS' or
                metadata.get('namespace') != OUTPUT.relative_to(ROOT).as_posix() or
                metadata.get('outcome') != 'INCOMPLETE_ASSEMBLY' or
                metadata.get('rawFailureBodyPublished') is not False):
            raise ValueError('FAILED_ASSEMBLY_RECEIPT_OWNERSHIP_UNCONFIRMED')
        failed_assemblies.append(dict(metadata=metadata, receiptSha256=sha(receipt),
            receiptTempName=receipt.name))
    if OUTPUT.exists() and not resume_incomplete:
        raise ValueError('ADDITIVE_PRECOMMIT_NAMESPACE_ALREADY_EXISTS')
    blockers = []
    index = ROOT/'.git/index'
    index_before = sha(index) if index.is_file() else None
    source_inventory = [row for row in load(audit/'candidate_inventory.json')
        if not in_current_output(row['path'])]
    audit_summary = load(audit/'repository_audit_summary.json')
    triage = load(audit/'secret_triage.json')
    historical_comparison = load(audit/'historical_file_comparison.json')
    if historical_comparison.get('status') != 'PASS':
        blockers.append('FROZEN_HISTORICAL_PHASE_BYTE_COMPARISON_FAILED')
    # Require fresh bytes for every already audited candidate; this catches CI
    # edits after a preflight audit without importing product or running tests.
    stale_audit = []
    for row in source_inventory:
        path = ROOT/row['path']
        if not path.is_file() or sha(path) != row['sha256']:
            stale_audit.append(row['path'])
    if stale_audit:
        blockers.append('REPOSITORY_AUDIT_CANDIDATE_BYTES_STALE')
    _, tracked_paths, _ = git('ls-files', '--cached', '-z')
    _, visible_paths, _ = git('ls-files', '--others', '--exclude-standard', '-z')
    current_paths = {value.decode('utf-8', errors='surrogateescape').replace('\\', '/')
        for value in (tracked_paths+visible_paths).split(b'\0') if value}
    current_paths = {path for path in current_paths if not in_current_output(path)}
    audited_paths = {row['path'] for row in source_inventory}
    if current_paths != audited_paths:
        blockers.append('REPOSITORY_AUDIT_VERSIONABLE_SET_STALE')
    if audit_summary.get('requiredIgnoredEvidence') != 0 or audit_summary.get('readErrors') or audit_summary.get('gitWarnings'):
        blockers.append('REPOSITORY_ENUMERATION_OR_REQUIRED_EVIDENCE_NOT_READY')
    if triage.get('unresolvedCandidateFindings') or triage.get('liveCredentialsDetected'):
        blockers.append('SECRET_TRIAGE_NOT_RESOLVED')
    triage_stale = [row['fileSha256'] for row in triage.get('findings', []) if row.get('path') and
        (not (ROOT/row['path']).is_file() or sha(ROOT/row['path']) != row['fileSha256'])]
    if triage_stale:
        blockers.append('SECRET_TRIAGE_SOURCE_BYTES_STALE')
    full_inventory = load(audit/'repository_inventory.json')
    tracked_ignored = [row['path'] for row in full_inventory if row['versioning'] == 'TRACKED' and
        (row.get('ignoredReason') or {}).get('pattern') and not row['ignoredReason']['pattern'].startswith('!')]
    generated_candidates = [row['path'] for row in source_inventory if
        row['classification'] == 'GENERATED_DEPENDENCY_BUILD_OR_CACHE' and not row['path'].startswith('docs/')]
    large_candidates = [row['path'] for row in load(audit/'large_files.json') if row['versioning'] in ('TRACKED', 'UNTRACKED_VISIBLE')]
    if tracked_ignored:
        blockers.append('TRACKED_FILES_MATCH_IGNORED_RULES')
    if generated_candidates:
        blockers.append('VERSIONABLE_GENERATED_NON_DOCUMENTATION_ARTIFACTS')
    if large_candidates:
        blockers.append('VERSIONABLE_LARGE_ARTIFACT_REQUIRES_DISPOSITION')
    inventory_result = dict(status='FAIL')
    try:
        data = validate()
        inventory_result = dict(status='PASS', staticContracts=len(data['contracts']),
            classifications=dict(Counter(row['classification'] for row in data['contracts'])),
            manifestSha256=sha(CONTRACT_MANIFEST), unclassified=[], stale=[], duplicates=[],
            testExecutionByPackaging=0)
    except Exception:
        blockers.append('CURRENT_STATIC_CONTRACT_INVENTORY_INVALID')
        data = None
    local = preflight_evidence(preflight, data, blockers) if data else dict(latest=[], priorFailedAttempts=[])
    local['nativeAdapter'] = adapter_evidence(preflight, local, blockers)
    workflow = workflow_evidence(workflows, blockers)
    frozen = frozen_evidence(blockers)
    diff_code, _, diff_error = git('diff', '--check')
    if diff_code:
        blockers.append('GIT_DIFF_CHECK_FAILED')
    code, head, _ = git('rev-parse', 'HEAD')
    if code:
        blockers.append('GIT_HEAD_READ_FAILED')
    status_code, normal_status, _ = git('status', '--short', '--untracked-files=all')
    ignored_code, ignored_status, _ = git('status', '--short', '--ignored', '--untracked-files=normal')
    if status_code or ignored_code:
        blockers.append('GIT_STATUS_READ_FAILED')
    if (sha(index) if index.is_file() else None) != index_before:
        blockers.append('GIT_INDEX_BYTES_CHANGED_DURING_READONLY_CHECK')
    ready = not blockers
    def gate(prefixes):
        return 'BLOCKED' if any(code.startswith(prefixes) for code in blockers) else 'PASS'
    gates = dict(GITIGNORE_AUDIT=gate(('REPOSITORY_ENUMERATION', 'SECRET_TRIAGE', 'TRACKED_FILES_MATCH')),
        VERSION_CONTROL_INVENTORY=gate(('REPOSITORY_AUDIT', 'VERSIONABLE_', 'PINNED_SOURCE_', 'FROZEN_', 'GIT_')),
        CI_INVENTORY=inventory_result['status'], GITHUB_ACTIONS_CONFIGURATION=workflow['result'],
        LOCAL_CI_PREFLIGHT=gate(('LOCAL_PREFLIGHT_', 'LOCAL_NATIVE_', 'DESKTOP_')),
        READY_TO_COMMIT=ready, GITHUB_ACTIONS_READY=(workflow['result'] == 'PASS' and inventory_result['status'] == 'PASS' and
            not any(code.startswith(('LOCAL_PREFLIGHT_', 'LOCAL_NATIVE_', 'DESKTOP_')) for code in blockers)))
    if not resume_incomplete:
        OUTPUT.mkdir(parents=True, exist_ok=False)
    own = dict(group='PRECOMMIT_EVIDENCE_GENERATED_AFTER_SOURCE_AUDIT',
        paths=[(OUTPUT/name).relative_to(ROOT).as_posix() for name in ARTIFACT_NAMES],
        sourceGenerator=dict(path='ci/package_precommit_readiness.py', sha256=sha(Path(__file__))),
        hashesRecordedIn='manifest.json', contentDoesNotGrantAuthority=True)
    write('tracked_untracked_inventory.json', dict(schemaVersion=1, sourceAuditSha256=sha(audit/'candidate_inventory.json'),
        candidates=source_inventory, precommitEvidenceGroup=own,
        currentPhaseGeneratedOutputsExcludedFromSourceSnapshot=True,
        FILES_TO_COMMIT=[row for row in source_inventory if row.get('gitStatus')] + [own],
        FILES_IGNORED=load(audit/'ignored_runtime_summary.json'),
        generatedIgnoredSummary=load(audit/'ignored_runtime_summary.json'),
        detailedPhysicalInventoryRetainedInOwnedTemp=True, rawFixtureOrSecretContentsIncluded=False))
    ignore_report = dict(schemaVersion=1, requiredIgnoredEvidence=audit_summary['requiredIgnoredEvidence'],
        inventoryCounts=audit_summary['counts'], sourceAuditSha256=sha(audit/'repository_audit_summary.json'),
        ignoredRuntimeGroups=load(audit/'ignored_runtime_summary.json'),
        versionableLargeFiles=[row for row in load(audit/'large_files.json') if row['versioning'] in ('TRACKED', 'UNTRACKED_VISIBLE')],
        stagedNothing=True, GitConfigModified=False, historicalArtifactBytesModified=False,
        statuses=gates, trackedIgnoredPaths=tracked_ignored,
        versionableGeneratedNonDocsPaths=generated_candidates, versionableLargePaths=large_candidates,
        staleCandidatePaths=stale_audit, frozenEvidence=frozen,
        historicalPhaseByteComparison=historical_comparison,
        historicalPhaseByteComparisonSha256=sha(audit/'historical_file_comparison.json'),
        candidateSetDrift=dict(newUnauditedPaths=sorted(current_paths-audited_paths),
            auditedPathsNoLongerCandidates=sorted(audited_paths-current_paths)),
        secrets=dict(triageSha256=sha(audit/'secret_triage.json'), classificationCounts=triage['classificationCounts'],
            unresolvedCandidateFindings=triage['unresolvedCandidateFindings'],
            liveCredentialsDetected=triage['liveCredentialsDetected'], valuesDisclosed=False,
            staleReviewedFileHashes=triage_stale),
        retainedResources=load(audit/'current_owned_resources.json'))
    write('gitignore_audit.json', ignore_report)
    write('gitignore_audit.md', '# Auditoría Git e integridad\n\n'
        f"Evidencias requeridas ignoradas: **{ignore_report['requiredIgnoredEvidence']}**. "
        f"Archivos candidatos: **{len(source_inventory)}**. "
        'Los caches, dependencias, locks y estados privados siguen separados de la evidencia frozen.\n\n'
        f"Integridad B7: **{frozen['result']}**. Comparación de todos los archivos históricos previos a esta fase: **{historical_comparison['status']}**. Los filtros Git se verificaron sobre las fuentes/configuraciones pinned. "
        'No se cambió el index ni la configuración Git.\n\n'
        'Los hallazgos sintéticos se resolvieron por hash/procedencia; no se copiaron valores de secretos. '
        'La retención de temporales y del recibo benigno por policy conserva su causa histórica.\n')
    write('ci_inventory_results.json', inventory_result)
    write('workflow_validation.json', workflow)
    write('local_preflight_results.json', local)
    ci = dict(schemaVersion=1, result='PASS' if ready else 'BLOCKED', blockers=blockers,
        statuses=gates,
        staticInventory=inventory_result, latestJobResults=[dict(job=row['job'], status=row['status'],
            attempt=row.get('attempt')) for row in local['latest']], desktop=workflow['desktop'],
        failedAttemptCountersPreserved=len(local['priorFailedAttempts']), repeatedAttemptsSummed=False,
        nativeAdapter=local['nativeAdapter'],
        GitHubActionsExecutionClaim=False, B7RecertificationClaim=False,
        commitPushTagReleasePerformed=False, historicalStates=STATE)
    write('ci_audit.json', ci)
    table = '\n'.join('| '+row['job']+' | '+row['status']+' | '+str(row.get('countedResults', {}).get('passed', 0))+' |'
        for row in local['latest'])
    write('ci_audit.md', '# Auditoría CI prospectiva\n\n'
        '| Selección oficial | Estado local actual | Casos pasados |\n|---|---|---:|\n'+table+'\n\n'
        'Cada fila corresponde al último intento de esa selección y exige coincidencia con los selectors actuales, '
        'ejecución completa, colección no vacía y cero skips. No se suman reintentos ni se infiere un run remoto de Actions.\n\n'
        f"Desktop: **{workflow['desktop']['status']}**; tests, TypeScript y Vite tienen receipts independientes. "
        'El build termina antes del instalador/publicación.\n\n'
        '## Ajustes causales de CI\n\n'
        '- Core conserva el golden histórico; compara por separado el prompt host-owned del catálogo V1.2.\n'
        '- La prueba JSONL espera la pareja asíncrona EventGap → SessionSnapshot en orden.\n'
        '- K6 comprueba el catálogo V1.2 y conecta ScriptedHTTPPort al constructor privado de adquisición host-owned tras retirar la ruta legacy; no cambia Approval.\n'
        '- El perfil privado de CI tiene rutas cortas, ownership y lifetime bounded; no usa el perfil humano ambiental.\n'
        '- El selector C# se trasladó a la selección Windows con sus prerrequisitos; no se eliminó cobertura.\n'
        '- Las 99 funciones B1/B2 antes omitidas quedaron clasificadas positivamente.\n\n'
        'Estos cambios preparan regresión prospectiva. No cambian ni rescoring de evidencias certificadas históricas.\n')
    # Git status is repository metadata, not raw test diagnostics.
    write('final_git_status.txt', 'HEAD: '+head.decode().strip()+'\n\n'
        'STATUS NORMAL (READ ONLY)\n'+normal_status.decode('utf-8', errors='replace')+'\n'
        'STATUS INCLUDING IGNORED TOP LEVEL GROUPS (READ ONLY)\n'+ignored_status.decode('utf-8', errors='replace')+'\n'
        f'DIFF_CHECK_EXIT_CODE={diff_code}\nDIFF_CHECK_DIAGNOSTIC_SHA256={hashlib.sha256(diff_error).hexdigest()}\n'
        'PRECOMMIT_GENERATED_NAMESPACE='+OUTPUT.relative_to(ROOT).as_posix()+'\n')
    states = '\n'.join(key+' = '+('true' if value is True else 'false' if value is False else value) for key,value in STATE.items())
    write('resultados.md', '# Pre-commit — Repositorio y CI\n\n'
        f"Estado: **{'READY_FOR_HUMAN_COMMIT_REVIEW' if ready else 'BLOCKED'}**. "
        'Esta fase prepara una revisión humana; no autoriza ni realiza commit, push, tag o release.\n\n'
        f"Inventario estático: **{inventory_result['status']}**. Workflow validation: **{workflow['result']}**. "
        f"Integridad B7: **{frozen['result']}**. Desktop: **{workflow['desktop']['status']}**.\n\n"
        'Los intentos fallidos mantienen contadores y SHA separados; sus cuerpos/logs privados permanecen en temp. '
        'No se suman repeticiones ni se altera la historia B0–B7.\n\n'+
        ('## Bloqueos\n\n'+'\n'.join('- '+code for code in blockers)+'\n\n' if blockers else '')+
        '## Estados preservados\n\n```ini\n'+states+'\n```\n\n'
        '## Gates de esta fase\n\n```ini\n'+ '\n'.join(key+' = '+('true' if value is True else 'false' if value is False else value)
            for key,value in gates.items())+'\n```\n\n'
        f"READY_FOR_COMMIT_REVIEW = {'true' if ready else 'false'}\n")
    pins = [dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(OUTPUT.iterdir()) if path.is_file()]
    write('manifest.json', dict(schemaVersion=1, phase='PRE_COMMIT_REPOSITORY_AND_CI_READINESS',
        generatedAt=datetime.now(timezone.utc).isoformat(), READY_FOR_COMMIT_REVIEW=ready,
        statuses=gates, READY_TO_COMMIT=ready, GITHUB_ACTIONS_READY=gates['GITHUB_ACTIONS_READY'],
        blockers=blockers, HEAD=head.decode().strip(), artifacts=pins,
        failedAssemblyAttempt=failed_assembly, failedAssemblyAttempts=failed_assemblies,
        sourceInputs=dict(audit=str(audit), preflight=str(preflight), workflowValidation=str(workflows)),
        historicalStates=STATE, rawDiagnosticsPublished=False, commitPushTagReleasePerformed=False))
    # Capture the true final namespace, including its manifest, then seal the
    # updated status hash. The manifest deliberately never hashes itself.
    status_code, normal_status, _ = git('status', '--short', '--untracked-files=all')
    ignored_code, ignored_status, _ = git('status', '--short', '--ignored', '--untracked-files=normal')
    if status_code or ignored_code or (sha(index) if index.is_file() else None) != index_before:
        raise ValueError('FINAL_READONLY_GIT_OBSERVATION_UNCONFIRMED')
    write('final_git_status.txt', 'HEAD: '+head.decode().strip()+'\n\n'
        'FINAL STATUS NORMAL (READ ONLY)\n'+normal_status.decode('utf-8', errors='replace')+'\n'
        'FINAL STATUS INCLUDING IGNORED TOP LEVEL GROUPS (READ ONLY)\n'+ignored_status.decode('utf-8', errors='replace')+'\n'
        f'DIFF_CHECK_EXIT_CODE={diff_code}\nDIFF_CHECK_DIAGNOSTIC_SHA256={hashlib.sha256(diff_error).hexdigest()}\n')
    final_manifest = load(OUTPUT/'manifest.json')
    final_manifest['artifacts'] = [dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(OUTPUT.iterdir()) if path.is_file() and path.name != 'manifest.json']
    write('manifest.json', final_manifest)
    return dict(READY_FOR_COMMIT_REVIEW=ready, blockers=blockers,
        output=str(OUTPUT), manifestSha256=sha(OUTPUT/'manifest.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--preflight', required=True, type=Path)
    parser.add_argument('--workflow-validation', required=True, type=Path)
    parser.add_argument('--resume-incomplete', action='store_true',
        help='Resume only the exact nine-artifact unfinished current phase; complete/frozen namespaces are rejected.')
    args = parser.parse_args()
    print(json.dumps(package(args.audit, args.preflight, args.workflow_validation,
        resume_incomplete=args.resume_incomplete)))
