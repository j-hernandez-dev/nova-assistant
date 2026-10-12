"""Read-only B7 audit of explicitly retained B6 resources.

No deletion, ACL change, process stop, listener shutdown or policy workaround.
Only a new nb7-* output directory can receive files. This is scoped observation,
not forensic erasure, a browser network claim, or proof about all OS resources.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess


OWNED_B6_NAMES = (
    'nb6-close-tests', 'nb6-composition', 'nb6-contract', 'nb6-controls-final',
    'nb6-final', 'nb6-final-root-smoke', 'nb6-frozen', 'nb6-guard-regression',
    'nb6-initial', 'nb6-native-regression-final', 'nb6-native-root',
    'nb6-parity-closed', 'nb6-parity-real', 'nb6-regression', 'nb6-regression-final',
    'nb6-root-fixed', 'nb6-root-proof', 'nb6-sealed',
)
ROOT = Path(__file__).resolve().parents[2]
B6 = ROOT / 'docs/active_web_v1_2/v12_b6_snapshot_productive_integration'
TEMP = Path(os.environ['LOCALAPPDATA']) / 'Temp'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def reparse(path):
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)
    except OSError:
        return True


def inventory(path, maximum=100000):
    result = dict(path=str(path), exists=path.exists(), fileCount=0, totalBytes=0,
        enumerationComplete=True, reparseEntriesSkipped=0, errors=[], possibleStagingFiles=[])
    if not path.exists():
        return result
    if reparse(path):
        result['enumerationComplete'] = False
        result['errors'].append('OWNED_ROOT_REPARSE_NOT_FOLLOWED')
        return result
    visited = 0
    for directory, dirs, files in os.walk(path, followlinks=False):
        current = Path(directory)
        for leaf in tuple(dirs):
            if reparse(current / leaf):
                dirs.remove(leaf)
                result['reparseEntriesSkipped'] += 1
        for leaf in files:
            visited += 1
            if visited > maximum:
                result['enumerationComplete'] = False
                result['errors'].append('ENUMERATION_BOUND_REACHED')
                return result
            candidate = current / leaf
            if reparse(candidate):
                result['reparseEntriesSkipped'] += 1
                continue
            try:
                stat = candidate.stat()
                result['fileCount'] += 1
                result['totalBytes'] += stat.st_size
                if (any(part.casefold() in ('staging', 'downloads', 'upload-copies', 'owned_uploads')
                        for part in candidate.relative_to(path).parts[:-1]) or
                        candidate.suffix.casefold() in ('.crdownload', '.partial', '.part')):
                    if len(result['possibleStagingFiles']) < 256:
                        result['possibleStagingFiles'].append(candidate)
                    else:
                        result['enumerationComplete'] = False
                        result['errors'].append('STAGING_INSPECTION_BOUND_REACHED')
            except OSError:
                result['errors'].append('FILE_METADATA_UNCONFIRMED')
                result['enumerationComplete'] = False
    return result


def read_lock_observation(path):
    """Momentary read-only, OPEN_EXISTING observation; no file modification.

An exclusive read open detects a conflicting current handle at this instant.
Success does not prove absence of every possible handle or future activity.
"""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x00200000, None)
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        return dict(path=str(path), readOnlyExclusiveOpen='UNCONFIRMED', win32Error=ctypes.get_last_error())
    kernel.CloseHandle(handle)
    return dict(path=str(path), readOnlyExclusiveOpen='OBSERVED', modification=False)


def observe_os():
    # Command is fixed. No ExecutionPolicy override, global settings or mutation.
    script = r'''
$ErrorActionPreference='Stop'
$auditProcesses = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate)
$auditTcpError=$null; $auditUdpError=$null
try { $auditTcp = @(Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess) } catch { $auditTcp=@();$auditTcpError='TCP_OBSERVATION_UNCONFIRMED' }
try { $auditUdp = @(Get-NetUDPEndpoint | Select-Object LocalAddress,LocalPort,OwningProcess) } catch { $auditUdp=@();$auditUdpError='UDP_OBSERVATION_UNCONFIRMED' }
@{processes=$auditProcesses;tcpListeners=$auditTcp;udpEndpoints=$auditUdp;tcpError=$auditTcpError;udpError=$auditUdpError}|ConvertTo-Json -Depth 5 -Compress
'''
    process = subprocess.run(['powershell', '-NoLogo', '-NoProfile', '-Command', script],
        capture_output=True, text=True, encoding='utf-8', timeout=45,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode:
        return dict(processes=[], tcpListeners=[], udpEndpoints=[],
            processObservation='UNCONFIRMED', tcpError='UNCONFIRMED', udpError='UNCONFIRMED')
    result = json.loads(process.stdout)
    result['processObservation'] = 'OBSERVED'
    return result


def audit(output_root):
    output_root = Path(output_root).resolve()
    if (not output_root.is_absolute() or not output_root.name.startswith('nb7-') or
            output_root.parent != TEMP.resolve() or output_root.is_relative_to(ROOT) or reparse(output_root.parent)):
        raise ValueError('OUTPUT_MUST_BE_EXACT_NEW_OWNED_NB7_TEMP_ROOT')
    if output_root.exists() and reparse(output_root):
        raise ValueError('OUTPUT_REPARSE_DENIED')
    old_cleanup = load(B6 / 'cleanup_evidence.json')
    candidate = load(B6 / 'product_candidate.json')
    runtime = observe_os()
    owned_paths = [TEMP / name for name in OWNED_B6_NAMES]
    scope_tokens = [str(path).casefold() for path in owned_paths]
    scope_tokens += [instance['instance'].casefold() for instance in old_cleanup['instances']]
    current_owned = []
    for process in runtime['processes']:
        command = process.get('CommandLine') or ''
        matches = [token for token in scope_tokens if token in command.casefold()]
        if matches:
            current_owned.append(dict(pid=process['ProcessId'], parentPid=process['ParentProcessId'],
                name=process['Name'], created=process.get('CreationDate'),
                commandLineInspected=True, commandLineSha256=hashlib.sha256(command.encode()).hexdigest(),
                matchedOwnedResources=matches))
    owned_pids = {row['pid'] for row in current_owned}
    # PID reuse alone is not current ownership; command line/instance is checked.
    process_by_pid = {row['ProcessId']: row for row in runtime['processes']}
    instances = []
    for row in old_cleanup['instances']:
        udf = Path(row['udf'])
        expected = 'nova_wv2_bws_'
        path_in_scope = udf.parent == Path(os.environ['LOCALAPPDATA']) / 'Nova/Wv' and udf.name.startswith(expected) and row['instance'] in udf.name
        pid = row.get('recordedPid')
        current = process_by_pid.get(pid)
        process_matches = bool(current and row['instance'].casefold() in (current.get('CommandLine') or '').casefold())
        auxiliaries = []
        if path_in_scope:
            auxiliaries = [str(path) for path in udf.parent.glob('*' + row['instance'] + '*')]
        instances.append(dict(instance=row['instance'], udf=str(udf), recordedPid=pid,
            recordedPathOwned=path_in_scope, udfAbsent=path_in_scope and not udf.exists(),
            ownedAuxiliariesPresent=auxiliaries, currentProcessMatchesInstance=process_matches,
            recordedPidCurrentlyExists=bool(current), pidReuseDoesNotEstablishOwnership=True))
    pin_report = []
    for branch in ('fetch', 'browser'):
        for raw, expected in candidate[branch]['pins']:
            path = Path(raw)
            if not path.is_absolute():
                path = ROOT / path
            resolved = path.resolve()
            in_temp = resolved.is_relative_to(TEMP.resolve())
            try:
                actual = hash_file(path) if path.is_file() and not reparse(path) else None
            except OSError:
                actual = None
            pin_report.append(dict(capability=branch, path=raw, withinTemp=in_temp,
                bytesMatchFrozenPin=actual == expected, expectedSha256=expected, observedSha256=actual))
    folders = []
    for path in owned_paths:
        row = inventory(path)
        row['readOnlyStagingLockObservations'] = [read_lock_observation(p) for p in row.pop('possibleStagingFiles')]
        row['ownershipEvidence'] = 'EXACT_RETAINED_B6_ATTEMPT_NAMESPACE_AND_B6_CLEANUP_RECORD'
        row['deletionAttempted'] = False
        folders.append(row)
    owned_listeners = [dict(protocol='TCP', **row) for row in runtime['tcpListeners'] if row['OwningProcess'] in owned_pids]
    owned_listeners += [dict(protocol='UDP', **row) for row in runtime['udpEndpoints'] if row['OwningProcess'] in owned_pids]
    known_fixture_listeners = [row for row in runtime['tcpListeners'] if row['LocalPort'] in (80, 443)]
    inert = (runtime['processObservation'] == 'OBSERVED' and not current_owned and
        not owned_listeners and all(row['udfAbsent'] and not row['ownedAuxiliariesPresent'] and
            not row['currentProcessMatchesInstance'] for row in instances) and
        all(not row['withinTemp'] and row['bytesMatchFrozenPin'] for row in pin_report))
    report = dict(schemaVersion=1, phase='V12_B7', observedAt=datetime.now(timezone.utc).isoformat(),
        scope='READ_ONLY_EXACT_RETAINED_B6_RESOURCES_AND_FROZEN_CANDIDATE',
        tempRetentionHistoricalStatus=old_cleanup['tempCleanup'],
        policyBlockPreserved=True, deletionAttempted=False, policyBypassAttempted=False,
        result='INERT_RETAINED_TEMP_OBSERVED' if inert else 'RESOURCE_STATE_REQUIRES_REVIEW',
        currentOwnedProcesses=current_owned, commandLineInspection=runtime['processObservation'],
        currentOwnedListeners=owned_listeners, TCPObservationError=runtime['tcpError'],
        UDPObservationError=runtime['udpError'], currentKnownHttpFixturePorts=known_fixture_listeners,
        listenerClaimScope='MATCHED_OWNED_PROCESS_PIDS_ONLY_NOT_ALL_BROWSER_OR_OS_NETWORK',
        folders=folders, nativeInstances=instances, frozenProductCandidatePins=pin_report,
        productCandidateReferencesRetainedTemp=any(row['withinTemp'] for row in pin_report),
        limitations=['Point-in-time read-only observation; retained artifacts remain present.',
            'PID reuse is not ownership. No forensic erasure or universal handle/socket claim.',
            'Retained B6 cleanup policy block remains UNCONFIRMED_POLICY_BLOCK.'])
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / 'b6_retained_resources_readonly.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    result = audit(args.output_root)
    print(json.dumps(dict(result=result['result'], folders=len(result['folders']),
        nativeInstances=len(result['nativeInstances']), ownedProcesses=len(result['currentOwnedProcesses']),
        ownedListeners=len(result['currentOwnedListeners']), outputRoot=args.output_root)))
