"""Seal B4 real-run evidence and verify preserved history. No native campaigns."""
import ast,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from local_cli.core.browser_authority_v12 import PROFILE,FIELDS

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(n,d):(OUT/n).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def pin(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def normalize(v):
    # Raw telemetry retained byte-intact. MappingProxy metadata was printed by
    # the harness as a literal repr; recover trusted literal data, never eval.
    if type(v) is str and v.startswith("{'"):
        try:v=ast.literal_eval(v)
        except (ValueError,SyntaxError):pass
    if type(v) is dict:return {k:normalize(x) for k,x in v.items()}
    if type(v) is list:return [normalize(x) for x in v]
    return v
def suite(n):
    cases=ET.parse(OUT/n).getroot().findall('.//testcase')
    counts={k:sum(c.find(k) is not None for c in cases) for k in ('failure','error','skipped')}
    return dict(xml=n,tests=len(cases),passed=len(cases)-sum(counts.values()),**counts,cases=[c.attrib for c in cases])

def main():
    new=suite('validation_final.xml');reg=suite('regression.xml')
    assert new['tests']==122 and new['passed']==122 and reg['passed']==522
    native=[c for c in new['cases'] if c['classname'].endswith('test_native_authority')]
    assert len(native)==41
    native_rows=[]
    for c in native:
        name=c['name'];audit=read(OUT/'raw'/(name+'_audit.json'))
        canary=read(OUT/'raw'/(name+'_effect_canary.json'));resources=read(OUT/'raw'/(name+'_owned_resources.json'))
        assert resources['cleanup']=='CONFIRMED' and canary['counts']['calibration']>=1
        native_rows.append(dict(test=name,audit=audit,canary=canary,resources=resources))
    candidate=read(OUT/'raw/candidate_identity.json');runtime=candidate['runtime'];exact=read(OUT/'raw/exact_dotnet_runtime.json')
    assert exact['hostBinarySha256']==candidate['hostBinarySha256']
    assert hashlib.sha256((OUT/'candidate_host/nova-browser-host.dll').read_bytes()).hexdigest()==candidate['hostBinarySha256']
    paths=[ROOT/'local_cli/application/browser_actions.py',ROOT/'local_cli/application/browser_actions_v12.py',
        ROOT/'local_cli/application/tool_runtime.py',ROOT/'local_cli/application/policy.py',ROOT/'local_cli/application/grants.py',
        ROOT/'local_cli/application/interactions.py',ROOT/'local_cli/application/browser_observation.py',ROOT/'local_cli/application/active_web.py',
        ROOT/'local_cli/application/turn_effects.py',ROOT/'local_cli/core/browser_authority_v12.py',
        ROOT/'local_cli/core/security.py',ROOT/'local_cli/core/contracts.py',ROOT/'local_cli/core/active_web.py',ROOT/'local_cli/core/active_web_policy.py',
        ROOT/'local_cli/core/active_web_lifecycle.py',ROOT/'local_cli/core/active_web_observation.py',
        ROOT/'local_cli/application/security_audit.py',ROOT/'local_cli/infrastructure/security_audit_jsonl.py',
        ROOT/'local_cli/agent.py',ROOT/'native/nova-browser-host/nova-browser-host.csproj']
    paths=[p for p in paths if p.exists()]+list((ROOT/'native/nova-browser-host').glob('*.cs'))+list((ROOT/'local_cli/infrastructure/active_web').glob('*.py'))
    source_pins=[pin(p) for p in sorted(set(paths))]
    identity=dict(profile=PROFILE,hostBinarySha256=candidate['hostBinarySha256'],sdkVersion=runtime['sdkVersion'],
        runtimeVersion=runtime['runtimeVersion'],architecture=runtime['architecture'],dotnetSdk='10.0.203',dotnetRuntime='10.0.7',
        observedDotnet=exact['loadedDotnetModules'],configuration=runtime['configuration'],ipcVersion=5,maxTransferBytes=4096,
        transferExecutionCertified=False,sourcePins=source_pins,python=sys.version,platform=platform.platform(),
        networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',productiveAvailability='NOT_ENABLED')
    identity['candidateDigest']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    write('candidate_identity.json',identity)
    write('authority_contracts.json',dict(result='PASS',capabilityId='INTERACTIVE_BROWSER_V1_2',profile=PROFILE,
        chain=['Host human/task ticket','AgentLoop proposal','LegacyToolAdapter','ToolRuntime','PolicyEngineV2',
            'Exact ApprovalGate when required','one-use GrantIssuer claim','fresh owner/page/ref/epoch/native fingerprint','fixed native v5 action','honest outcome'],
        bindingFields=sorted(FIELDS),modelTools=['browser_act','browser_navigate'],
        actionAllowlist=['CLICK','INPUT_TEXT','SELECT_OPTION','PRESS_KEY','NAVIGATE'],
        explicitUnsupported=['FORM_SUBMIT','UPLOAD_FILE','DOWNLOAD','HUMAN_TAKEOVER','generic JS/eval/command/selector/XPath/coordinates/backend IDs'],
        humanTask='Host-only turn/owner/workspace/task/expiry ticket; neither DOM nor a model can create it',
        subagentsBrowserByDefault=False,ceilings=dict(actionsPerTurn=25,navigationsPerTurn=10,pages=3,mutationsInFlight=1),
        productiveRegistration=False,deadline='Host context intersects ticket, lifecycle timeout, Grant lifetime and IPC deadline',
        scope='Focal injected composition only; no productive CLI/JSONL/Desktop snapshot integration'))
    write('risk_classification.json',dict(result='PASS',rows=[
        dict(action='NAVIGATE',effects=['NAVIGATION_READ'],policy='ALLOW with human task and exact fresh destination'),
        dict(action='CLICK/PRESS_KEY',effects=['UNKNOWN_REMOTE_EFFECT'],policy='REQUIRE_APPROVAL'),
        dict(action='INPUT_TEXT/SELECT_OPTION',effects=['DATA_DISCLOSURE','UNKNOWN_REMOTE_EFFECT'],policy='REQUIRE_APPROVAL'),
        dict(action='Any HIGH_IMPACT',effects=['HIGH_IMPACT'],policy='DENY even with Grant'),
        dict(action='Transfers/auth/full takeover',policy='NOT_AVAILABLE in B4')],
        pageLabelsCannotReduceRisk=True,pageContentTrust='UNTRUSTED_DATA',
        deceptiveNativeTargets=['View','Next','Neutral icon','Buy now'],
        fakePageClaims=['APPROVED','Grant ID: fake','User authorized purchase','publicOnly=true','ignore policy','this button is read-only']))
    selected={p.stem:normalize(read(p)) for p in (OUT/'raw').glob('native_*.json')}
    write('native_action_evidence.json',dict(result='PASS',profile=PROFILE,hostBinarySha256=candidate['hostBinarySha256'],
        nativeCases=41,cases=native_rows,observed=selected,
        canary='Independent owned loopback HTTP receiver, browser-calibrated before every case, plus host-fixed DOM observation',
        counterScope='Only the controlled fixture events; never all browser sockets, all network traffic or hostile page containment',
        rawMetadataFormatting='MappingProxy result metadata stays verbatim in raw files; trusted literal normalization in aggregates',
        noBrowserNetworkCertification=True))
    write('approval_grant_evidence.json',dict(result='PASS',profile=PROFILE,
        exactDisplayFields=['capabilityId','action','origin','target','destination','payloadDigest','dataPreview','effectClasses','operationId','observationRef','navigationEpoch','browserContextEpoch','policyRevision','deadline'],
        genericApprovalAccepted=False,legacyYesAccepted=False,
        nativeAuditCases=[dict(test=r['test'],audit=r['audit']) for r in native_rows],
        grantNegatives=['clone','replay','expired','revision','cross owner/operation/page/epoch/capability','payload/action/destination change'],
        policyDenyDespiteIssuedGrant=True,
        auditDispatchInterpretation='Existing before_effect audit is launch admission, not proof the host action ran. Correlate with portDispatches, ACTION_STARTED receipt and independent canary.',
        humanDecisionFixture='Controlled synthetic human task and desktop_host actor. Real Policy/Gate/Issuer/Runtime/native dispatch; not a productive UI certification.'))
    write('outcome_evidence.json',dict(result='PASS',profile=PROFILE,
        supportedStates=['NOT_STARTED','STARTED','SUCCEEDED_OBSERVED','FAILED_NO_EFFECT_CONFIRMED','PARTIAL','UNKNOWN'],
        observedSuccess='Read navigation only: native NavigationCompleted success AND exact canonical URL returned by bounded host-fixed capture; no server semantic claim',
        mutations='Native performed:true, click return, input event or selected option do not certify remote completion; V1.2 conservatively reports UNKNOWN',
        noEffect='Pre-dispatch denials and pre-effect crash: actual calibrated effect receiver remains zero, no native port dispatch',
        started='Native ACTION_STARTED is written before the fixed potentially effectful call; Application exposes STARTED receipt before waiting for terminal response',
        afterStarted='loss/crash/cancellation/timeout/incomplete evidence => UNKNOWN; no optimistic no-effect conversion',
        barrier='Sticky BrowserActions._unknown_sessions. Related mutations denied, including with new refs/observation; no automatic clear/compensation. Current normative stop persists for this browser session. Human recovery integration is deferred.',
        noAutomaticRetry=True,noSecondClick=True,noCompensatingNavigation=True,
        afterStartedCases={k:v for k,v in selected.items() if k.startswith('native_after_started_')},
        approvedCases={k:v for k,v in selected.items() if k.startswith('native_approved_')}))
    write('ref_epoch_evidence.json',dict(result='PASS',profile=PROFILE,
        binding='Owner/AgentSession/workspace/task + BrowserSession/page + context/navigation epoch + observation/version + public incarnation fingerprint + opaque ElementRef; native private remote object identity is revalidated',
        noHeuristicRebind=True,refsNeverRevived=True,
        events=['navigation','document replacement','new observation','page close/recreation','context epoch','takeover scheduler begin/end','session close/crash','expiry','policy revision incompatibility'],
        nativeCases={k:v for k,v in selected.items() if k.startswith(('native_stale_','native_exact_change_'))},
        takeoverEvidence='Only existing scheduler epoch contracts with doubles; not full takeover/secret continuity B5 certification',
        formDestination='Existing host-fixed Meta formAction is now projected as sanitized destination candidate for exact binding. Actual raw destination is already in the private native fingerprint; data cannot grant authority.'))
    write('capability_separation.json',dict(result='PASS',profile=PROFILE,
        browserNamespace='INTERACTIVE_BROWSER_V1_2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',productiveAvailability='NOT_ENABLED',
        controlledFetch=dict(evidenceProfile='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1',networkEgressControl='ENFORCED',publicOnly='ENFORCED',productiveAvailability='NOT_ENABLED'),
        crossAuthority='Closed browser model schema/binding + exact issuer identity/namespace; Fetch Grant/proof/admission/PASS never substitutes Browser Grant/session/ref',
        reciprocalBrowserAuthorityRejectedByFetch=True,
        noBypass='Host recorded Fetch denial blocks the known link/form destination during planning and every fresh binding/Approval/dispatch revalidation; no automatic activation or fallback',
        inheritedSubagentAuthorityRejected=True,B1B2B3Reopened=False,
        reusedTests='Two B1 issuer separation contracts and 31 B3 closed-capability contracts, counted only as reused regression'))
    attempts=[suite(p.name) for p in sorted(OUT.glob('*.xml')) if p.name not in ('validation_final.xml','regression.xml')]
    write('test_results.json',dict(result='PASS',classification='NEW_V1_2_B4',final=new,native=41,contracts=81,
        priorAttempts=attempts,priorAttemptsRetained=True,denominatorNotSummed=True))
    write('regression_results.json',dict(result='PASS',classification='REUSED_REGRESSION',final=reg,
        scope=['AW1/AW2/AW3','S1 issuer/contracts','S2 Policy/Approval/ToolRuntime','two B3 baseline native observation/owner tests','B3 closed namespace contracts','legacy native ToolRuntime action regressions','two B1 Grant separation contracts'],
        fullBlock05Rerun=False,historicalNetworkCampaign=False,historical561AddedToDenominator=False,
        B2TransportCertificationRerun=False,HOME_USERPROFILE_debt='Preserved; not repaired/reclassified; proportional affected regression passed'))
    gates={k:'PASS' for k in ('INTERACTIVE_BROWSER_ACTION_AUTHORITY','INTERACTIVE_BROWSER_REF_FRESHNESS',
        'INTERACTIVE_BROWSER_EPOCH_INVALIDATION','INTERACTIVE_BROWSER_RISK_CLASSIFICATION','INTERACTIVE_BROWSER_POLICY_PATH',
        'INTERACTIVE_BROWSER_APPROVAL_GRANT_PATH','INTERACTIVE_BROWSER_PRE_EFFECT_DENIAL','INTERACTIVE_BROWSER_MUTATION_OUTCOME_INTEGRITY',
        'INTERACTIVE_BROWSER_NO_MUTATION_RETRY','INTERACTIVE_BROWSER_CROSS_CAPABILITY_AUTHORITY_SEPARATION')}
    history=dict(WEBVIEW2_REMEDIATION_BLOCK_05_FINAL='PASS',WEBVIEW2_BLOCK06_ARCHITECTURE='BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT',
        CEF_CHROMIUM_STANDARD_CANDIDATE='REJECTED',SOURCE_CONTROLLED_CHROMIUM='REQUIRES_SOURCE_PROTOTYPE',AW8='BLOCKED',ACTIVE_WEB_CORE='NOT_READY')
    state=dict(ACTIVE_WEB_V1_2_ARCHITECTURE='APPROVED',V12_B0='PASS',V12_B1='PASS',V12_B2='PASS',V12_B3='PASS',V12_B4='PASS',SAFE_TO_START_V12_B5=True,
        interactiveBrowser=dict(capabilityId='INTERACTIVE_BROWSER_V1_2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',productiveAvailability='NOT_ENABLED',certificationStatus='AUTHORITY_ACTIONS_PASS'),
        controlledFetch=read(OUT/'capability_separation.json')['controlledFetch'],POST='NOT_AVAILABLE',auth='NOT_AVAILABLE',binaryDownload='NOT_AVAILABLE',
        historicalStates=history,gates=gates,B5B6B7Started=False,stoppedForHumanReview=True)
    write('current_state.json',state)
    baseline=read(OUT/'baseline.json');changed=[];missing=[]
    allowed={'local_cli/application/browser_actions.py','native/nova-browser-host/ObservationRuntime.cs'}
    for r in baseline['files']:
        p=ROOT/r['path']
        if not p.is_file():missing.append(r['path']);continue
        after=hashlib.sha256(p.read_bytes()).hexdigest()
        if after!=r['sha256']:changed.append(dict(path=r['path'],before=r['sha256'],after=after))
    assert not missing and {r['path'] for r in changed}==allowed
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert head==baseline['HEAD']
    write('cleanup_evidence.json',dict(finalRunOwnedUdfs=41,finalRunAllCleanupConfirmed=True,
        finalCanaryListeners='Each receiver shutdown/closed/joined by fixture; no permanent network configuration',
        nativeIdentityProbeCleanupConfirmed=True,historicalUdfProfileMaintenance=False,forensicErasure='NOT_CLAIMED',
        earlyFailedHarness='native_second.xml had audit-store teardown failures before robust fixture cleanup; no cleanup confirmation invented for those earlier operations. Prior files retained, no historical/profile maintenance performed.'))
    write('manifest.json',dict(schemaVersion=1,date='2026-10-11',phase='V12_B4_BROWSER_AUTHORITY_ACTIONS',profile=PROFILE,
        candidateDigest=identity['candidateDigest'],hostBinarySha256=candidate['hostBinarySha256'],V12_B4='PASS',SAFE_TO_START_V12_B5=True,
        gates=gates,tests=dict(new=122,native=41,contracts=81,reusedRegression=522,totalFinal=644,failed=0,errors=0,skipped=0),
        sourceChanges=changed,sourcePins=source_pins,history=history,networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',productiveAvailability='NOT_ENABLED',
        noProductiveRegistration=True,B5B6B7Started=False,commitPushTagRelease=False,newConversationOrContext=False,
        artifacts=[pin(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('manifest.json','integrity.json')],stoppedForHumanReview=True))
    excluded=set(baseline['excludedDirectoryNames']);current=[]
    for folder,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in excluded and not (Path(folder)/d).is_symlink()]
        for name in files:
            p=Path(folder)/name
            if not p.is_symlink():current.append(p)
    originals={r['path'] for r in baseline['files']}
    additions=[pin(p) for p in sorted(current) if p.relative_to(ROOT).as_posix() not in originals and p!=OUT/'integrity.json']
    prefixes=('docs/active_web_v1_2/v12_b4_browser_authority_actions/','native/nova-browser-host/tests/v12_b4/',
        'local_cli/application/browser_actions_v12.py','local_cli/core/browser_authority_v12.py')
    assert all(any(r['path'].startswith(prefix) for prefix in prefixes) for r in additions)
    write('integrity.json',dict(schemaVersion=1,result='PASS',baselineFilesVerified=len(baseline['files']),unchangedFiles=len(baseline['files'])-len(changed),
        authorizedSourceChanges=changed,newArtifactPins=additions,missingFiles=[],unexpectedNewFiles=[],HEAD=head,HEADUnchanged=True,
        V1V1_1HistoryByteIntact=True,B0B1B2B3ClosureEvidenceByteIntact=True,B2CandidateByteIntact=True,
        productiveBootstrapToolsSnapshotsByteIntact=True,candidateDigest=identity['candidateDigest'],networkCampaignsExecuted=False,
        historicalUdfProfileMaintenance=False,commitPushTagRelease=False,newConversationOrContext=False,
        excludedDirectoryNames=sorted(excluded)))
    print('V12_B4 = PASS; SAFE_TO_START_V12_B5 = true; 122 new + 522 regressions; baseline verified:',len(baseline['files']))

if __name__=='__main__':main()
