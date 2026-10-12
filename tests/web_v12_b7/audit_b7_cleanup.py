"""Point-in-time, read-only audit after B7 suites have completed.

Never deletes retained B6/B7 output, changes registry/ACL, stops a process or
works around cleanup policy. Output belongs only to a new explicit nb7-* root.
The audit correlates exact instance identities and command lines, not PID reuse.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import winreg

from audit_owned_resources import observe_os, reparse, ROOT, TEMP, B6


RUN_NAMES = ('nb7-attempt-01', 'nb7-final-02', 'nb7-final-03', 'nb7-regression-01')
RUN_NAMES += ('nb7-crosscap-final', 'nb7-candidate02-affected',
    'nb7-candidate02-final', 'nb7-candidate02-regression')
POLICY_BLOCKED_GUARD_JOURNAL_SHA256 = '7b7d1f9298719e8c7b5f7282c44d82a347553352ec23eeb8c5d9e87a04c1b968'


def read(path):
    # PowerShell-owned state files may have a UTF-8 BOM; it is encoding metadata.
    return json.loads(path.read_text(encoding='utf-8-sig'))


def records(output):
    """Read schema-specific resource metadata; never publish raw sensitive bodies."""
    found, errors = [], []
    for count, path in enumerate(output.rglob('*.json')):
        if count >= 10000:
            errors.append('JSON_SCAN_BOUND_REACHED')
            break
        if reparse(path):
            errors.append('REPARSE_NOT_FOLLOWED')
            continue
        try:
            if path.stat().st_size > 8 * 1024 * 1024:
                errors.append('JSON_SIZE_BOUND_REACHED')
                continue
            data = read(path)
            if type(data) is dict:
                found.append((path, data))
        except (OSError, ValueError):
            errors.append('JSON_METADATA_UNCONFIRMED:' + path.name)
    return found, errors


def check_udf(session, instance, recorded, process_by_pid, scopes):
    base = Path(os.environ['LOCALAPPDATA']) / 'Nova/Wv'
    expected = base / ('nova_wv2_' + session + '_' + instance)
    supplied = Path(recorded['udf']) if recorded.get('udf') else expected
    owned = (re.fullmatch(r'bws_[0-9a-f]{32}', session) is not None and
        re.fullmatch(r'bhi_[0-9a-f]{32}', instance) is not None and supplied == expected)
    pid = recorded.get('hostPid')
    current = process_by_pid.get(pid)
    command = (current.get('CommandLine') or '') if current else ''
    pid_owned = bool(current and (instance.casefold() in command.casefold() or str(expected).casefold() in command.casefold()))
    auxiliaries = [str(path) for path in base.glob('*' + instance + '*')] if owned else []
    scopes.extend((session.casefold(), instance.casefold(), str(expected).casefold()))
    return dict(session=session, instance=instance, udf=str(supplied), recordedPid=pid,
        ownedPathValidated=owned, udfAbsent=owned and not expected.exists(),
        ownedAuxiliariesPresent=auxiliaries, recordedCleanup=recorded.get('cleanup'),
        currentProcessMatchesOwnedIdentity=pid_owned, recordedPidCurrentlyExists=bool(current),
        pidReuseDoesNotEstablishOwnership=True, constructorOnly=pid is None,
        diagnosticOnlyNoProcessResource=pid is None and not auxiliaries and not expected.exists())


def registry_absence(key):
    if not re.fullmatch(r'Software\\Classes\\nova-v12-(?:guard|mail)-[0-9a-f]{32}', key):
        return 'OUTSIDE_OWNED_CANARY_SCOPE'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ):
            return 'PRESENT'
    except FileNotFoundError:
        return 'ABSENT'
    except OSError:
        return 'UNCONFIRMED'


def retained_auxiliary_observations(rows):
    observations = []
    forbidden = {'grant', 'approval', 'credentials', 'cookie', 'authorization',
        'password', 'secretref', 'networkproofref', 'hostfileselectionref'}
    for instance in rows:
        for raw in instance['ownedAuxiliariesPresent']:
            path = Path(raw)
            item = dict(path=raw, instance=instance['instance'], modificationAttempted=False,
                deletionAttempted=False, cleanup='CLEANUP_UNCONFIRMED')
            try:
                body = path.read_bytes()
                digest = hashlib.sha256(body).hexdigest()
                item.update(bytes=len(body), sha256=digest)
                if path.name.endswith('.guard-audit.jsonl') and digest == POLICY_BLOCKED_GUARD_JOURNAL_SHA256:
                    receipt_rows = [json.loads(line) for line in body.decode('utf-8').splitlines()]
                    expected_keys = {'agentId', 'auditSequence', 'auditStreamId', 'data', 'kind',
                        'operationId', 'origin', 'recordId', 'schemaVersion', 'sessionId', 'timestamp',
                        'tool', 'toolCallId', 'turnId'}
                    data_keys = {'action', 'decision', 'effectState', 'observationScope', 'outcome',
                        'reason', 'resource', 'retryAllowed'}
                    closed = all(type(row) is dict and set(row) == expected_keys and
                        type(row['data']) is dict and set(row['data']) == data_keys for row in receipt_rows)
                    authority_keys = any(key.casefold() in forbidden for row in receipt_rows for key in (
                        *row.keys(), *row.get('data', {}).keys()))
                    item.update(retainedReason='UNCONFIRMED_POLICY_BLOCK',
                        deletionAutoReview='REJECTED_BEFORE_EXECUTION',
                        deletionReattempted=False, alternativeDeletionMechanismUsed=False,
                        journalSchemaClosed=closed, receiptRows=len(receipt_rows),
                        reusableAuthorityOrCredentialFieldsPresent=authority_keys,
                        riskScope='EXACT_BENIGN_TEST_GUARD_RECEIPT_NO_REUSABLE_AUTHORITY')
                else:
                    item['retainedReason'] = 'OWNED_AUXILIARY_PRESENT_REQUIRES_REVIEW'
            except (OSError, ValueError, UnicodeError):
                item['retainedReason'] = 'OWNED_AUXILIARY_READ_UNCONFIRMED'
            observations.append(item)
    return observations


def current_candidate():
    path = ROOT / 'docs/active_web_v1_2/v12_b7_final_e2e/candidate_identity.json'
    data = read(path)
    pins = []
    for row in data['productPins']:
        source = Path(row['path'])
        if not source.is_absolute():
            source = ROOT / source
        try:
            observed = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() and not reparse(source) else None
        except OSError:
            observed = None
        pins.append(dict(path=row['path'], expectedSha256=row['sha256'], observedSha256=observed,
            compatible=observed == row['sha256'], referencesTemp=source.resolve().is_relative_to(TEMP.resolve())))
    return dict(candidateId=data['candidateId'], sourceTreeIdentity=data['sourceTreeIdentity'],
        identityPath=str(path), identitySha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        acceptedB6WasChangedProspectively=data.get('productChangesFromAcceptedB6'),
        allPinsCompatible=all(row['compatible'] and not row['referencesTemp'] for row in pins),
        pins=pins, historicalB6EvidenceReinterpreted=False)


def current_staging(roots):
    """Fresh exact-owned run staging observation, distinct from past teardown proof."""
    stages, errors = [], []
    for root in roots:
        visited = 0
        for directory, dirs, files in os.walk(root, followlinks=False):
            current = Path(directory)
            visited += 1
            if visited > 100000:
                errors.append('STAGING_ENUMERATION_BOUND_REACHED:' + root.name)
                break
            for leaf in tuple(dirs):
                candidate = current / leaf
                if reparse(candidate):
                    dirs.remove(leaf)
                    errors.append('STAGING_REPARSE_NOT_FOLLOWED:' + str(candidate))
                    continue
                if leaf.startswith('nova-browser-staging-'):
                    stages.append(dict(run=root.name, path=str(candidate), exists=True,
                        files=[str(p) for p in candidate.rglob('*') if p.is_file()]))
            for leaf in files:
                if leaf.casefold().endswith(('.crdownload', '.partial', '.part')):
                    stages.append(dict(run=root.name, path=str(current / leaf), exists=True,
                        kind='PARTIAL_TRANSFER_FILE'))
    return dict(observedOwnedStagingResources=stages, enumerationErrors=errors,
        currentlyAbsent=not stages and not errors,
        scope='EXACT_NEW_B7_RUN_DIRECTORIES_POINT_IN_TIME', deletionAttempted=False)


def audit(output_root):
    output_root = Path(output_root).resolve()
    if (not output_root.is_absolute() or output_root.parent != TEMP.resolve() or
            not output_root.name.startswith('nb7-') or output_root.name in RUN_NAMES or
            output_root.is_relative_to(ROOT) or reparse(output_root.parent) or
            output_root.exists() and reparse(output_root)):
        raise ValueError('OUTPUT_MUST_BE_SEPARATE_OWNED_NB7_TEMP_ROOT')
    os_snapshot = observe_os()
    processes = {row['ProcessId']: row for row in os_snapshot['processes']}
    scopes = [str(TEMP / name).casefold() for name in RUN_NAMES]
    manifests, instances, constructors, staging, fixture_cleanup, guard_canaries = [], [], [], [], [], []
    missing, read_errors, seen = [], [], set()
    raw_guard_hosts, calibrated_pids = [], []
    for name in RUN_NAMES:
        output = TEMP / name / 'output'
        manifest = output / 'owned_cleanup.json'
        if not manifest.is_file():
            missing.append(str(manifest))
            continue
        metadata = read(manifest)
        manifests.append(dict(run=name, path=str(manifest), sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            recordedScope=metadata.get('scope'), exitStatus=metadata.get('exitStatus'),
            instances=len(metadata.get('instances', []))))
        for row in metadata.get('instances', []):
            key = row['instance']
            if key in seen:
                continue
            seen.add(key)
            verified = check_udf(row['session'], key, row, processes, scopes)
            (constructors if verified['constructorOnly'] else instances).append(verified)
        blobs, errors = records(output)
        read_errors.extend(errors)
        for path, blob in blobs:
            relative = str(path.relative_to(output))
            if 'stagingRemoved' in blob:
                staging.append(dict(run=name, record=relative, instance=blob.get('instance'),
                    recordedStagingRemoved=blob['stagingRemoved'] is True,
                    recordedCleanup=blob.get('cleanup')))
            if all(key in blob for key in ('listenersClosed', 'socketObserverRestored', 'ownedTLSFilesRemoved')):
                fixture_cleanup.append(dict(run=name, record=relative,
                    listenersClosed=blob['listenersClosed'] is True,
                    socketObserverRestored=blob['socketObserverRestored'] is True,
                    ownedTLSFilesRemoved=blob['ownedTLSFilesRemoved'] is True,
                    globalCAStoreModified=blob.get('globalCAStoreModified')))
            if 'registryKey' in blob and 'positiveControlPids' in blob:
                key = blob['registryKey']
                observed = registry_absence(key)
                scheme = blob.get('scheme') or ''
                if scheme:
                    scopes.append(scheme.casefold())
                calibrated_pids.extend(blob['positiveControlPids'])
                guard_canaries.append(dict(run=name, record=relative, registryKey=key,
                    currentRegistration=observed, positiveControlPids=blob['positiveControlPids'],
                    recordedHandlerLaunchCount=blob.get('handlerLaunchCount'),
                    recordedCleanupConfirmed=blob.get('cleanupConfirmed') is True))
            if all(key in blob for key in ('session', 'instance', 'hostPid', 'nativePids', 'cleanupConfirmed')):
                session, instance = blob['session'], blob['instance']
                if instance in seen:
                    continue
                seen.add(instance)
                row = dict(hostPid=blob['hostPid'], cleanup='CONFIRMED' if blob['cleanupConfirmed'] else 'CLEANUP_UNCONFIRMED')
                verified = check_udf(session, instance, row, processes, scopes)
                verified.update(run=name, record=relative, calibratedGuardHost=True,
                    recordedNativePids=blob['nativePids'])
                raw_guard_hosts.append(verified)
    # Fresh command-line scan includes all exact B7 run roots, session/instance
    # identities and registered canary schemes. No raw unknown command is logged.
    current_owned = []
    for process in os_snapshot['processes']:
        command = process.get('CommandLine') or ''
        matches = [token for token in scopes if token in command.casefold()]
        if matches:
            current_owned.append(dict(pid=process['ProcessId'], parentPid=process['ParentProcessId'], name=process['Name'],
                commandLineInspected=True, commandLineSha256=hashlib.sha256(command.encode()).hexdigest(),
                matchingOwnedIdentity=matches))
    owned_pids = {row['pid'] for row in current_owned}
    current_calibrated = []
    for pid in sorted(set(calibrated_pids)):
        process = processes.get(pid)
        command = (process.get('CommandLine') or '') if process else ''
        owned = bool(process and any(token in command.casefold() for token in scopes))
        current_calibrated.append(dict(recordedPositiveControlPid=pid, currentPidExists=bool(process),
            currentProcessMatchesOwnedIdentity=owned, pidReuseDoesNotEstablishOwnership=True))
    listeners = [dict(protocol='TCP', **row) for row in os_snapshot['tcpListeners'] if row['OwningProcess'] in owned_pids]
    listeners += [dict(protocol='UDP', **row) for row in os_snapshot['udpEndpoints'] if row['OwningProcess'] in owned_pids]
    http_fixture_ports = [row for row in os_snapshot['tcpListeners'] if row['LocalPort'] in (80, 443)]
    all_instances = instances + raw_guard_hosts
    retained = retained_auxiliary_observations(all_instances)
    product_candidate = current_candidate()
    staging_now = current_staging([TEMP / name for name in RUN_NAMES])
    confirmed = (not missing and not read_errors and os_snapshot['processObservation'] == 'OBSERVED' and
        os_snapshot['tcpError'] is None and os_snapshot['udpError'] is None and not current_owned and not listeners and
        all(row['ownedPathValidated'] and row['udfAbsent'] and not row['ownedAuxiliariesPresent'] and
            not row['currentProcessMatchesOwnedIdentity'] for row in all_instances) and
        all(row['diagnosticOnlyNoProcessResource'] for row in constructors) and
        staging_now['currentlyAbsent'] and product_candidate['allPinsCompatible'] and
        bool(fixture_cleanup) and all(row['listenersClosed'] and row['socketObserverRestored'] and
            row['ownedTLSFilesRemoved'] and row['globalCAStoreModified'] is False for row in fixture_cleanup) and
        bool(guard_canaries) and all(row['currentRegistration'] == 'ABSENT' and
            row['recordedCleanupConfirmed'] for row in guard_canaries))
    legacy = read(B6 / 'cleanup_evidence.json')
    report = dict(schemaVersion=1, phase='V12_B7', observedAt=datetime.now(timezone.utc).isoformat(),
        result='CONFIRMED' if confirmed else 'CLEANUP_UNCONFIRMED',
        scope='EXACT_NEW_B7_INSTANCE_AND_FIXTURE_RESOURCES_POINT_IN_TIME',
        manifests=manifests, missingManifests=missing, metadataReadErrors=read_errors,
        nativeInstances=instances, constructorDiagnostics=constructors, guardNativeInstances=raw_guard_hosts,
        currentOwnedProcesses=current_owned, currentOwnedListeners=listeners,
        commandLineObservation=os_snapshot['processObservation'], tcpError=os_snapshot['tcpError'], udpError=os_snapshot['udpError'],
        currentlyListeningKnownHTTPFixturePorts=http_fixture_ports,
        calibratedGuardHandlerPids=current_calibrated, guardCanaryRegistrations=guard_canaries,
        stagingCleanupProofs=staging, actualHTTP_TLSFixtureCleanup=fixture_cleanup,
        freshOwnedStagingObservation=staging_now, currentFrozenCandidate=product_candidate,
        retainedOwnedAuxiliaries=retained,
        cleanupCause='UNCONFIRMED_POLICY_BLOCK' if retained and all(
            row.get('retainedReason') == 'UNCONFIRMED_POLICY_BLOCK' for row in retained) else
            'RESOURCE_STATE_REQUIRES_REVIEW' if not confirmed else None,
        componentObservations=dict(
            ownedProcesses='CONFIRMED_ABSENT' if os_snapshot['processObservation'] == 'OBSERVED' and not current_owned else 'UNCONFIRMED',
            ownedUDFs='CONFIRMED_ABSENT' if all(row['udfAbsent'] for row in all_instances) else 'UNCONFIRMED',
            ownedListeners='CONFIRMED_ABSENT' if not listeners and os_snapshot['tcpError'] is None and os_snapshot['udpError'] is None else 'UNCONFIRMED',
            staging='CONFIRMED_ABSENT_NOW' if staging_now['currentlyAbsent'] else 'UNCONFIRMED',
            TLSFixtureFiles='RECORDED_CONFIRMED' if fixture_cleanup and all(row['ownedTLSFilesRemoved'] for row in fixture_cleanup) else 'UNCONFIRMED',
            retainedAuxiliaries='CLEANUP_UNCONFIRMED' if retained else 'CONFIRMED_ABSENT'),
        B6HistoricalTempRetention=legacy['tempCleanup'], B6PolicyBlockPreserved=True,
        retainedTempDeletionAttempted=False, policyBypassAttempted=False, historicalResourcesTouched=False,
        claimLimits=['Cleanup observations are scoped to B7 owned resources, not all OS processes/sockets.',
            'Recorded PIDs are correlated with current command line; PID reuse is not ownership.',
            'Fixture TLS cleanup is backed by real harness reports; no global CA store modification.',
            'Retained temp test/build/output directories are intentionally not deleted.'])
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / 'b7_owned_cleanup_readonly.json').write_text(json.dumps(report, ensure_ascii=False, indent=2,
        default=str) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', required=True)
    arguments = parser.parse_args()
    result = audit(arguments.output_root)
    print(json.dumps(dict(result=result['result'], nativeInstances=len(result['nativeInstances']),
        constructorDiagnostics=len(result['constructorDiagnostics']), guardInstances=len(result['guardNativeInstances']),
        currentOwnedProcesses=len(result['currentOwnedProcesses']), currentOwnedListeners=len(result['currentOwnedListeners']),
        TLSCleanupReports=len(result['actualHTTP_TLSFixtureCleanup']), registryCanaries=len(result['guardCanaryRegistrations']))))
