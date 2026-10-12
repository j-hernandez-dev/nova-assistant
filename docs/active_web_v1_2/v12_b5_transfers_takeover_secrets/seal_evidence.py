"""Publish B5 only from frozen owned outputs, verify immutable prior evidence."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from local_cli.core.browser_transfers_v12 import PROFILE

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,d):(OUT/n).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def pin(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def suite(path):
    cases=ET.parse(path).getroot().findall('.//testcase')
    errors={k:sum(c.find(k) is not None for c in cases) for k in ('failure','error','skipped')}
    return dict(xml=path.relative_to(OUT).as_posix(),tests=len(cases),passed=len(cases)-sum(errors.values()),**errors,cases=[c.attrib for c in cases])
def raw(prefix):return {p.stem:read(p) for p in sorted((OUT/'final/raw').glob(prefix+'*.json'))}

def main():
    new=suite(OUT/'final/tests.xml');reg=suite(OUT/'regression/tests.xml')
    assert new['passed']==98 and reg['passed']==365 and all(x[k]==0 for x in (new,reg) for k in ('failure','error','skipped'))
    candidate=read(OUT/'final/raw/candidate_identity.json');exact=read(OUT/'exact_dotnet_runtime.json')
    assert exact['hostBinarySha256']==candidate['hostBinarySha256'] and exact['jobOwned']
    assert hashlib.sha256((OUT/'candidate_host/nova-browser-host.dll').read_bytes()).hexdigest()==candidate['hostBinarySha256']
    own=raw('test_');resources=[v for k,v in own.items() if k.endswith('_owned')]
    assert len(resources)==29 and all(v['cleanup']=='CONFIRMED' and v['stagingRemoved'] for v in resources)
    guards=[read(OUT/x/'historical_write_guard.json') for x in ('final','regression')]
    assert all(g['pythonAuditVeto'] and g['nativeNtfsDeny'] and g['aclRestored'] and g['noHashRestoration'] for g in guards)
    assert len(guards[1]['helperRedirects'])==2 and not guards[1]['blockedAttempts']
    paths=[ROOT/'local_cli/application/browser_actions.py',ROOT/'local_cli/application/browser_actions_v12.py',
        ROOT/'local_cli/application/browser_actions_v12_b5.py',ROOT/'local_cli/application/browser_takeover.py',
        ROOT/'local_cli/application/browser_transfers.py',ROOT/'local_cli/core/browser_authority_v12.py',
        ROOT/'local_cli/core/browser_transfers_v12.py',ROOT/'local_cli/core/active_web_transfers.py',
        ROOT/'local_cli/application/tool_runtime.py',ROOT/'local_cli/application/policy.py',ROOT/'local_cli/application/grants.py',
        ROOT/'local_cli/application/interactions.py',ROOT/'local_cli/application/browser_observation.py',ROOT/'local_cli/application/active_web.py',
        ROOT/'native/nova-browser-host/nova-browser-host.csproj']
    paths+=list((ROOT/'native/nova-browser-host').glob('*.cs'))+list((ROOT/'local_cli/infrastructure/active_web').glob('*.py'))
    source_pins=[pin(p) for p in sorted(set(paths))]
    identity=dict(profile=PROFILE,capabilityId='INTERACTIVE_BROWSER_V1_2',sdkVersion=candidate['runtime']['sdkVersion'],
        runtimeVersion=candidate['runtime']['runtimeVersion'],architecture=candidate['runtime']['architecture'],
        dotnetSdk='10.0.203',dotnetRuntime='10.0.7',dotnetModules=exact['modules'],hostBinarySha256=candidate['hostBinarySha256'],
        configuration=candidate['runtime']['configuration'],ipcVersion=5,maxTransferBytes=4096,sourcePins=source_pins,
        networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',productiveAvailability='NOT_ENABLED')
    identity['candidateDigest']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    write('candidate_identity.json',identity)
    write('transfer_authority.json',dict(result='PASS',profile=PROFILE,namespace='INTERACTIVE_BROWSER_V1_2',
        chain='Human/task ticket -> ToolRuntime -> PolicyEngineV2 -> exact Approval -> one-use Grant -> fresh ref -> locked file/one-use permit -> fixed v5 dispatch',
        upload=dict(source='HostFileSelectionRef',hostIssued=True,exactOwnerWorkspaceTaskOperation=True,identityRevisionSizeMimeDigest=True,
            selectedPathIdentityPrivate=True,expiry=True,pageDocumentEpochNodeOrigin=True,classification=['FILE_UPLOAD','DATA_DISCLOSURE','REMOTE_MUTATION'],
            originalFileReadLockHeldThroughDispatch=True,immutableOwnedCopy='UDF operation source token; only exact dispatch receives it; finite browser lifetime'),
        download=dict(permit='exact browser operation/epoch/node binding',classification=['FILE_DOWNLOAD'],maxBytes=4096,maxMimeChars=128,
            candidateWhereKnowable='Host-observed link destination + private native fingerprint/slot URI equality',oneUse=True,engineCompletedRequired=True),
        finalFence='After prepared locked read, revalidate claimed Grant, task expiry and current Policy before handing payload to engine; lock released on denial',
        modelPathsHandlesSelectorsKnowledge=False,FORM_SUBMIT='NOT_ENABLED',productiveRegistration=False,
        controlledFetchAuthorityAccepted=False,stagingCreatesFetchProof=False))
    write('upload_evidence.json',dict(result='PASS',profile=PROFILE,positive=read(OUT/'final/raw/upload_positive.json'),
        negative=raw('upload_deny_'),finalFences=raw('upload_final_fence_'),
        observedSuccess='Exact selected copy assigned to the verified native input; page observes expected file. Not server acceptance/submission.',
        disclosureBeforeSubmit=True,noGrantReplay=True,noDuplicateUpload=True))
    write('download_evidence.json',dict(result='PASS',profile=PROFILE,positive=read(OUT/'final/raw/download_positive.json'),
        driveBy=read(OUT/'final/raw/drive_by.json'),oversize=read(OUT/'final/raw/download_oversize.json'),losses=raw('transfer_loss_browser_download_'),
        success='Native DOWNLOAD_COMPLETED state Completed + owned read/counted bytes + matching digest + staging record',
        driveByNoAcceptedDownloadNoPartialNoCrdownload=True,filenameNeverFinalPath=True,noAutoOpenExecuteExportKnowledge=True))
    write('staging_evidence.json',dict(result='PASS',profile=PROFILE,ownedOutsideBrowserUdf=True,
        retainedAfterBrowserClose=True,digestChecked=True,explicitOwnerExpiryDiscardProvenance=True,
        positive=read(OUT/'final/raw/download_positive.json'),expiryAndCleanupContracts='Reused transfer/staging regression, exact finite ownership semantics',
        pendingInterruptedNotComplete=True,automaticKnowledgeImport=False))
    write('takeover_evidence.json',dict(result='PASS',profile=PROFILE,complete=read(OUT/'final/raw/takeover_complete.json'),
        guard=read(OUT/'final/raw/takeover_guard.json'),losses=raw('takeover_loss_'),
        hostOwnedPause=True,agentActionsDeniedWhileActive=True,oldRefsAndApprovalsInvalid=True,freshObservationRequired=True,
        loginIsMutationApproval=False,loginIsFetchAuthority=False,
        guardEvidenceScope='Full begin/end lifecycle only; unchanged B3 native guard source/SDK and prior registered-handler proof reused, not rerun as campaign'))
    write('secret_boundary_evidence.json',dict(result='PASS',profile=PROFILE,
        guarantee='Declared-sensitive / known values protected from Nova public surfaces',universalDlp=False,transformedSecretDetection=False,forensicErasure=False,receivingWebsiteProtection=False,
        protectedSurfaces=['Observation','ElementRef metadata','ToolResult','ToolRuntime result','audit','descriptor','capability metadata','IPC public projection','model context','public error/log','terminal public projection'],
        exactNativeV12=read(OUT/'final/raw/takeover_complete.json'),confirmedNavigation=read(OUT/'final/raw/confirmed_terminal_navigation.json'),
        unconfirmed=read(OUT/'final/raw/unconfirmed_navigation.json'),monotonicSensitiveKnowledge=True,
        rawDomCookiesDevtoolsOcrUsedForResume=False,
        regression='Eight page projection surfaces + public IPC/audit + post-epoch navigation + cross-origin retirement, with unchanged host-fixed schema-aware instrumentation',
        evidenceContainsRawHumanSecret=False))
    terminals={p.stem:read(p) for p in (OUT/'final/raw').glob('native-*.json')}
    write('terminal_authority_evidence.json',dict(result='PASS',profile=PROFILE,
        commitAbleSources=['SUBMIT_CONFIRMED','TAKEOVER_END_CHECKPOINT'],
        nonterminal=['INPUT','CHANGE','BLUR','PAGEHIDE','ENGINE_WORLD_RETIRE','navigation silence','page close','timeout','DOM disappearance'],
        retiredUnconfirmed='TerminalContinuityUnconfirmed; no resume/public observation',shortCommitted='Genuine terminal len 1..3 => SHORT_COMMITTED_VALUE / fail-closed',
        nativeSources=terminals,provenanceContracts='Exact snapshot/owner/page/generation/revision/world/reason; stale/forged/late terminal rejected',
        designReopened=False,modelFormSubmitEnabled=False))
    write('late_event_evidence.json',dict(result='PASS',profile=PROFILE,
        native=read(OUT/'final/raw/native-late-terminal.json'),
        scope='Real retired native document + controlled late checkpoint injection into fixed private terminal registry; no model JS API',
        lateEventCannotCommitClearUncertaintyResume=True,knownValueRetained=True,
        directContracts=['wrong owner/page/generation/world','invalid revision','late new/stale/duplicate','previous generation','retired snapshot','forged terminal source'],
        refsApprovalsNotRestored=True))
    write('historical_write_guard.json',dict(result='PASS',pythonAuditVeto=True,nativeNtfsWriteDeleteDeny=True,
        scope='Temporary test storage protection only, not browser/OS sandbox certification',executionPolicyChanged=False,
        originalAclRestored=True,roots=['docs/active_web_v1/**','docs/active_web_v1_2/** including B0-B4'],
        nativeAndPythonProbeDeniedBeforeFileEffect=True,runtimeOutputs='Owned temp only, copied into B5 after freeze/ACL restore',
        reusedHelperDestinationsRedirected=guards[1]['helperRedirects'],successfulHistoricalWrites=0,
        restoreByHashUsed=False,finalRun=guards[0],regressionRun=guards[1]))
    write('test_results.json',dict(result='PASS',classification='NEW_V12_B5',final=new,native=36,contracts=62,
        attempts=[suite(p) for p in sorted((OUT/'attempts').rglob('tests.xml'))],priorDenominatorsNotSummed=True,
        priorFailures='Harness event spelling/epoch lookup and asynchronous observation settling; retained without reclassification'))
    write('regression_results.json',dict(result='PASS',classification='REUSED_REGRESSION',final=reg,
        scope='Exact staging/transfer, strong terminal/provenance/retirement/leaf/transient policy; 8 secret surfaces and selected continuity; B3/B4 authority/epoch/outcome; AW3',
        historical561CampaignRerun=False,historicalResultsAddedToDenominator=False,networkCampaign=False,B2NativeCampaign=False,chromiumCefWork=False))
    write('cleanup_evidence.json',dict(result='PASS',nativeV12Instances=29,nativeTerminalCases=7,
        finalOwnedInstances=resources,nativeTerminalRootsAbsent=True,ownedAcrossAttempts=read(OUT/'owned_cleanup_receipts.json'),
        diagnostic=read(OUT/'regression_diagnostic_cleanup.json'),tempCleanup=read(OUT/'temp_cleanup.json'),
        identityProbeCleanupConfirmed=True,stagingRetainedUntilExplicitDiscardOrOwnedFixtureClose=True,
        historical36UdfsAnd3CefProfilesMaintained=False,historicalResourcesDeleted=False,forensicErasure='NOT_CLAIMED'))
    names=('INTERACTIVE_BROWSER_UPLOAD_AUTHORITY','INTERACTIVE_BROWSER_UPLOAD_IDENTITY_REVALIDATION','INTERACTIVE_BROWSER_DOWNLOAD_AUTHORITY',
        'INTERACTIVE_BROWSER_DOWNLOAD_DRIVE_BY_DENIAL','INTERACTIVE_BROWSER_DOWNLOAD_STAGING','INTERACTIVE_BROWSER_TRANSFER_OUTCOME_INTEGRITY',
        'INTERACTIVE_BROWSER_HUMAN_TAKEOVER','INTERACTIVE_BROWSER_TAKEOVER_EPOCH_INVALIDATION','INTERACTIVE_BROWSER_AGENT_PAUSE_DURING_TAKEOVER',
        'INTERACTIVE_BROWSER_SECRET_NON_EXPOSURE','INTERACTIVE_BROWSER_MONOTONIC_SENSITIVE_KNOWLEDGE','INTERACTIVE_BROWSER_SECRET_CONTINUITY',
        'INTERACTIVE_BROWSER_TERMINAL_AUTHORITY','INTERACTIVE_BROWSER_TERMINAL_PROVENANCE','INTERACTIVE_BROWSER_UNCONFIRMED_TERMINAL_DENIAL',
        'INTERACTIVE_BROWSER_LATE_EVENT_REJECTION','INTERACTIVE_BROWSER_OWNED_CLEANUP','HISTORICAL_EVIDENCE_WRITE_GUARD')
    gates={n:'PASS' for n in names}
    history=dict(WEBVIEW2_REMEDIATION_BLOCK_05_FINAL='PASS',WEBVIEW2_BLOCK06_ARCHITECTURE='BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT',
        CEF_CHROMIUM_STANDARD_CANDIDATE='REJECTED',SOURCE_CONTROLLED_CHROMIUM='REQUIRES_SOURCE_PROTOTYPE',AW8='BLOCKED',ACTIVE_WEB_CORE='NOT_READY')
    cf=dict(networkEgressControl='ENFORCED',publicOnly='ENFORCED',productiveAvailability='NOT_ENABLED',evidenceProfile='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1',POST='NOT_AVAILABLE',auth='NOT_AVAILABLE',binaryDownload='NOT_AVAILABLE')
    state=dict(ACTIVE_WEB_V1_2_ARCHITECTURE='APPROVED',V12_B0='PASS',V12_B1='PASS',V12_B2='PASS',V12_B3='PASS',V12_B4='PASS',V12_B5='PASS',SAFE_TO_START_V12_B6=True,
        interactiveBrowser=dict(capabilityId='INTERACTIVE_BROWSER_V1_2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',productiveAvailability='NOT_ENABLED'),controlledFetch=cf,
        gates=gates,historicalStates=history,B6B7Started=False,stoppedForHumanReview=True)
    write('current_state.json',state)
    baseline=read(OUT/'baseline.json');changed=[];missing=[]
    allowed={'local_cli/application/browser_actions.py','local_cli/application/browser_actions_v12.py','local_cli/core/browser_authority_v12.py'}
    for r in baseline['files']:
        p=ROOT/r['path']
        if not p.is_file():missing.append(r['path']);continue
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        if sha!=r['sha256']:changed.append(dict(path=r['path'],before=r['sha256'],after=sha))
    assert not missing and {r['path'] for r in changed}==allowed
    assert not any(r['path'].startswith('docs/') for r in changed)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert head==baseline['HEAD']
    write('manifest.json',dict(schemaVersion=1,date='2026-10-11',phase='V12_B5_TRANSFERS_TAKEOVER_SECRETS',profile=PROFILE,
        candidateDigest=identity['candidateDigest'],hostBinarySha256=candidate['hostBinarySha256'],V12_B5='PASS',SAFE_TO_START_V12_B6=True,
        gates=gates,tests=dict(new=98,native=36,contracts=62,reusedRegression=365,totalFinal=463,failed=0,errors=0,skipped=0),
        sourceChanges=changed,sourcePins=source_pins,historicalStates=history,controlledFetch=cf,
        productiveAvailability='NOT_ENABLED',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',
        B6B7Started=False,commitPushTagRelease=False,newConversationOrContext=False,
        artifacts=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('manifest.json','integrity.json')]))
    old={r['path'] for r in baseline['files']};excluded=set(baseline['excludedDirectoryNames']);additions=[]
    for folder,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in excluded and not (Path(folder)/d).is_symlink()]
        for n in files:
            p=Path(folder)/n;rel=p.relative_to(ROOT).as_posix()
            if not p.is_symlink() and rel not in old and p!=OUT/'integrity.json':additions.append(pin(p))
    prefixes=('docs/active_web_v1_2/v12_b5_transfers_takeover_secrets/','native/nova-browser-host/tests/v12_b5/',
        'local_cli/application/browser_actions_v12_b5.py','local_cli/core/browser_transfers_v12.py','local_cli/infrastructure/active_web/webview2_transfers_v12.py')
    assert all(any(r['path'].startswith(x) for x in prefixes) for r in additions)
    write('integrity.json',dict(schemaVersion=1,result='PASS',baselineFilesVerified=len(baseline['files']),unchangedFiles=len(baseline['files'])-len(changed),
        authorizedSourceChanges=changed,newArtifactPins=sorted(additions,key=lambda r:r['path']),missingFiles=[],unexpectedNewFiles=[],HEAD=head,HEADUnchanged=True,
        V1V1_1EvidenceByteIntact=True,B0B1B2B3B4EvidenceByteIntact=True,historicalEvidenceWrites=0,hashRestorationUsed=False,
        nativeHostSourceByteIntact=True,B2TransportByteIntact=True,productiveBootstrapSnapshotToolsByteIntact=True,
        candidateDigest=identity['candidateDigest'],historicalUdfProfileMaintenance=False,commitPushTagRelease=False,newConversationOrContext=False))
    print('V12_B5 = PASS; SAFE_TO_START_V12_B6 = true; 98 new + 365 reused regressions; baseline verified:',len(baseline['files']))

if __name__=='__main__':main()
