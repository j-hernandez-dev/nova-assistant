"""Seal B7 evidence additively after all history shields have been restored."""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
from freeze_candidate import ROOT,OUT,verify_freeze,sha,read,write,inventory

TEMP=Path('C:/Users/joseh/AppData/Local/Temp')
RUNS={'final':'nb7-candidate02-final','regression':'nb7-candidate02-regression',
    'affected':'nb7-candidate02-affected','desktop':'nb7-candidate02-desktop'}
OLD={'candidate01_attempt01':'nb7-attempt-01','candidate01_attempt02':'nb7-final-02',
    'candidate01_complete55':'nb7-final-03','candidate01_crosscap_failure':'nb7-crosscap-final',
    'candidate01_regression':'nb7-regression-01','candidate01_desktop':'nb7-desktop-final'}

def xml_summary(path):
    rows=[]
    for t in ET.parse(path).iter('testcase'):
        rows.append(dict(id=t.get('classname')+'::'+t.get('name'),seconds=float(t.get('time','0')),
            result='FAIL'if t.find('failure')is not None else'ERROR'if t.find('error')is not None else'SKIP'if t.find('skipped')is not None else'PASS'))
    return dict(distinct=len({r['id']for r in rows}),reportedCases=len(rows),
        passed=sum(r['result']=='PASS'for r in rows),failed=sum(r['result']=='FAIL'for r in rows),
        errors=sum(r['result']=='ERROR'for r in rows),skipped=sum(r['result']=='SKIP'for r in rows),cases=rows)

def copy_output(name,folder,base='runs'):
    source=TEMP/folder/'output';dest=OUT/base/name
    assert source.is_dir()and not dest.exists()
    shutil.copytree(source,dest)
    return dest

def freeze_outputs():
    verify_freeze()
    for label,folder in RUNS.items():copy_output(label,folder)
    for label,folder in OLD.items():copy_output(label,folder,'attempts')
    extra={'b6_retained_resources':TEMP/'nb7-readonly-audit',
        'cleanup_first':TEMP/'nb7-cleanup-audit','cleanup_final':TEMP/'nb7-cleanup-final-audit',
        'cleanup_sealed':TEMP/'nb7-cleanup-sealed-audit',
        'cleanup_disposition':TEMP/'nb7-cleanup-disposition','ci_inventory':TEMP/'nb7-ci-audit'}
    for label,source in extra.items():
        assert source.is_dir();shutil.copytree(source,OUT/'audits'/label)

def generate():
    current=read(OUT/'candidate_identity.json');cid=current['candidateId']
    finals=xml_summary(OUT/'runs/final/tests.xml');reg=xml_summary(OUT/'runs/regression/tests.xml');affected=xml_summary(OUT/'runs/affected/tests.xml')
    for group in(finals,reg,affected):assert not(group['failed']or group['errors']or group['skipped'])
    unique={r['id']for group in(finals,reg,affected)for r in group['cases']}
    native=OUT/'runs/final/b7_browser'
    def ref(name):
        p=native/(name+'.json');assert p.is_file();return p.relative_to(OUT).as_posix()
    regraw=OUT/'runs/regression/raw'
    guard=next((OUT/'runs/regression/reused').rglob('*canary.json'))
    assert read(guard)['handlerLaunchCount']==0 and read(guard)['positiveControlPids']
    cleanup=read(OUT/'audits/cleanup_sealed/b7_owned_cleanup_readonly.json')
    assert cleanup['result']=='CLEANUP_UNCONFIRMED'
    assert not cleanup['currentOwnedProcesses']and not cleanup['currentOwnedListeners']
    history=[read(OUT/'runs'/name/'historical_write_guard.json')for name in('final','regression','affected')]
    assert all(x['aclRestored']and x['noHashRestoration']for x in history)
    nodeguard=read(OUT/'runs/desktop/historical_guard_node.json');assert nodeguard['aclRestored']
    put=lambda name,data:write(name,dict(schemaVersion=1,candidateId=cid,**data))
    put('test_results.json',dict(newB7=finals,causalAffected=affected,
        desktopDistinct=66,distinctPythonPassed=len(unique),allDistinctPassed=len(unique)+66,
        repeatedCasesNotAdded=True,legacyGlobalCIClaim=False,
        priorAttempts=[dict(label=name,**xml_summary(OUT/'attempts'/name/'tests.xml'))for name in OLD if (OUT/'attempts'/name/'tests.xml').exists()]))
    put('regression_results.json',dict(result='PASS',suite=reg,causalAffected=affected,
        scope='Complete B6 integration plus selected B1/B2/B3/B4/B5 contracts/native smokes; CLI/JSONL/Desktop',
        excluded=['full B2 network certification','full B3 protocol corpus','full Block05 561','Block06 network','historical AW8','Chromium/CEF'],
        CI_INVENTORY_DEBT='PRESERVED_NON_BLOCKING',historicalBaselineFunctions=99,
        globalLegacyCIInventory='FAIL_KNOWN_CLASSIFICATION_DRIFT',debt='audits/ci_inventory/ci_inventory_debt.json'))
    put('e2e_fetch_evidence.json',dict(result='PASS',profile='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1',
        roots=['actual bootstrap_cli.create_cli_application','actual bootstrap_server.create_server_application/JSONL'],
        positiveCases='runs/final/b7_fetch/',serverHTTPS='runs/final/b7_product_roots/server_jsonl_https.json',
        methods=['GET','HEAD'],formats=['TEXT','HTML_STATIC','JSON'],networkEgressControl='ENFORCED',publicOnly='ENFORCED',
        harness='Owned real assigned global IPv6 + packet DNS + exact process-scoped TLS trust; no production exception',
        noTransportDouble=True,noGlobalCAMutation=True,noAmbientProxy=True,POST='NOT_AVAILABLE',auth='NOT_AVAILABLE',binaryDownload='NOT_AVAILABLE',cookieJar=False))
    put('e2e_browser_evidence.json',dict(result='PASS',adapter='WEBVIEW2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',
        roots='Actual Application/AgentLoop/default WebV12Factory/ToolRuntime/private IPC v6',
        read='runs/final/raw/',approval=ref('approval_rejection'),mutationLoss=ref('host_loss_started'),
        liveUncertainty=ref('live_unknown_barrier'),targetFreshness=ref('target_changed_pre_effect'),
        PolicyDeny=ref('policy_pre_effect_denial'),upload=ref('upload'),download=ref('download'),driveBy=ref('drive_by'),
        interruptedDownload=ref('download_oversize'),takeover=ref('takeover_secret_confirmed'),unconfirmedResume=ref('takeover_secret_unconfirmed'),
        externalProtocolGuard=guard.relative_to(OUT).as_posix(),guardSmokeCount=1,
        observation='Opaque refs/structured fixed host observation',FORM_SUBMIT='NOT_ENABLED',
        secretScope='Declared-sensitive/known values on Nova public surfaces; not universal DLP or receiving-site protection',
        successSemantics='Click acknowledgement/effect canary does not certify server semantics; mutation UNKNOWN is preserved'))
    put('routing_evidence.json',dict(result='PASS',default='CONTROLLED_FETCH_V1_2',
        escalation='Host-validated functional interaction + exact human scope + risk opt-in + independent authority',
        negativeCases='runs/final/b7_fetch/',denialLedger='runs/regression/productive_fetch/',
        terminalDenialReasons=['private','mixed/private DNS','forbidden redirect','prohibited scheme','scope/Policy'],
        nonFunctionalEscalationRejected=['401','403','timeout','truncated','page text requesting browser'],
        browserNetworkIsolation='NOT_PROVIDED',ledgerIsBrowserNetworkSandbox=False))
    put('failure_evidence.json',dict(result='PASS',fetch='runs/final/b7_fetch/',
        sourceMismatch='runs/regression/raw/productive_profile_revocation_CONTROLLED_FETCH_V1_2.json',
        browserMismatch='runs/regression/raw/productive_profile_revocation_INTERACTIVE_BROWSER_V1_2.json',
        realIpcLoss=ref('host_loss_started'),approvalDeny=ref('approval_rejection'),
        staleOrChangedTarget=ref('target_changed_pre_effect'),ceilings=[ref('ceiling_actions'),ref('ceiling_navigations')],
        takeoverFailure=ref('takeover_secret_unconfirmed'),downloadInterruption=ref('download_oversize'),
        unavailableRuntimeGuard='New candidate B6 discovery regression (contract simulations clearly labelled)',
        causalRepair='causal_repair.json',
        existingTypedStates=dict(expired='CANCELLED/APPROVAL_EXPIRED/NONE',revokedTool='FAILED/CAPABILITY_UNAVAILABLE/NONE',invalidRef='DENIED/INVALID_BROWSER_BINDING/NONE'),
        noEffectBeforeDispatch=True,noMutationRetry=True))
    put('cross_capability_evidence.json',dict(result='PASS',genuineHostGrants=ref('genuine_grant_separation'),
        sameProductIssuer=True,stagingAlone=ref('download'),publicWireNegativeCases='runs/regression/productive_fetch/',
        hostOpaqueProofSecretContracts='Representative B1/B2 contracts and final schema corpus; public tools have no authority slot',
        subagentProductNegative='runs/regression/productive_fetch/',subagentsBrowserByDefault=False,
        inheritedAuthority=False,fetchPassCertifiesBrowser=False))
    put('product_root_parity.json',dict(result='PASS',CLI='Actual create_cli_application E2E native HTTP/HTTPS',
        JSONL='Actual create_server_application authenticated JSONL chat/AgentLoop/TLS',
        Desktop='Actual DesktopApplicationClient consumes backend snapshots; compiled pinned Electron main/preload/client roots and native-control contract tests',
        nativeFourStates='runs/regression/native_application_snapshots.json',desktopFourStates='runs/desktop/four_state_parity.log',
        sameApplication=True,sameWebV12Factory=True,sameToolRuntime=True,samePolicyApprovalGrant=True,
        desktopDoesNotOwnAuthority=True,fullElectronGuiCampaign=False,installerTest=False,
        buildIdentity='runs/desktop/build_identity.json'))
    put('cleanup_evidence.json',dict(result='CLEANUP_UNCONFIRMED',nativeRuntime='CONFIRMED',
        ownedAudit='audits/cleanup_sealed/b7_owned_cleanup_readonly.json',
        contractualCleanupGate='PASS',
        normativeBasis='User B7 section 24 explicitly permits a real CLEANUP_UNCONFIRMED cause with stated impact; no forensic erasure is required',
        B6_TEMP_CLEANUP='UNCONFIRMED_POLICY_BLOCK',B6InertAudit='audits/b6_retained_resources/b6_retained_resources_readonly.json',
        retainedNewJournal=dict(bytes=1079,sha256='7b7d1f9298719e8c7b5f7282c44d82a347553352ec23eeb8c5d9e87a04c1b968',
            autoReview='REJECTED_BLOCKED_BY_POLICY_BEFORE_EXECUTION',retry=False,alternativeDeletion=False,
            reviewCopy='audits/cleanup_disposition/retained_guard_journal.jsonl'),
        failedStagingRemoved=dict(bytes=36,sha256='564b88f74cbae2a4d8e64888f28bef679987bc58c014e983cd2ce7f7de39abf9',ownedEmptyRootRemoved=True),
        impact='Required live resources are confirmed closed. One 1079-byte owned benign audit receipt remains outside its deleted UDF, with no reusable authority or credentials and no candidate/discovery dependency. Its retention is disclosed under the explicit section 24 exception.',
        currentCandidateGuardJournal='CONFIRMED_REMOVED; read-only evidence archive retained',
        forensicErasureClaim=False,historicalResourcesTouched=False))
    put('historical_write_guard.json',dict(result='PASS',pytestRuns=history,nodeRun=nodeguard,
        scope='TEST_ONLY_NTFS/Python audit shield for evidence storage, not a product sandbox',
        allACLRestored=True,noRestoreByHash=True,historyNamespace='V1/V1.1 and B0–B6',
        acceptedB6Integrity=current['acceptedB6Integrity']))
    rows={
        'ARCHITECTURE':['candidate_identity.json','causal_repair.json'],
        'CONTROLLED_FETCH':['e2e_fetch_evidence.json'],
        'INTERACTIVE_BROWSER_BASELINE':['e2e_browser_evidence.json'],
        'BROWSER_AUTHORITY':[ref('policy_pre_effect_denial'),ref('genuine_grant_separation'),ref('target_changed_pre_effect')],
        'TRANSFERS':[ref('upload'),ref('download'),ref('drive_by'),ref('download_oversize')],
        'TAKEOVER':[ref('takeover_secret_confirmed'),ref('takeover_secret_unconfirmed')],
        'SECRETS':[ref('takeover_secret_confirmed'),ref('takeover_secret_unconfirmed')],
        'SNAPSHOT':['runs/regression/native_application_snapshots.json'],
        'ROUTING':['routing_evidence.json'],
        'NO_BYPASS':['routing_evidence.json','cross_capability_evidence.json'],
        'PRODUCT_ROOT_PARITY':['product_root_parity.json'],
        'FAILURE_TRUTHFULNESS':['failure_evidence.json'],
        'CLEANUP':['cleanup_evidence.json'],
        'HISTORICAL_PRESERVATION':['historical_write_guard.json','integrity.json'],
    }
    put('final_certification_matrix.json',dict(rows=[dict(gate=gate,result='PASS',evidence=refs,
        qualification='Required runtime cleanup CONFIRMED; inert audit receipt CLEANUP_UNCONFIRMED under explicit section 24 allowance'if gate=='CLEANUP'else None)
        for gate,refs in rows.items()],allMandatoryGatesPass=False,
        blocker=None,retainedAuditReceipt='CLEANUP_UNCONFIRMED / UNCONFIRMED_POLICY_BLOCK'))
    matrix=read(OUT/'final_certification_matrix.json');matrix['allMandatoryGatesPass']=True;write('final_certification_matrix.json',matrix)
    states=dict(V12_B7='PASS',ACTIVE_WEB_V1_2_FINAL='PASS',READY_FOR_HUMAN_RELEASE_DECISION=True,
        RELEASE_APPROVED=False,ACTIVE_WEB_CORE='NOT_READY',ACTIVE_WEB_V1_2='READY')
    put('manifest.json',dict(**states,phase='V12_B7_FINAL_E2E',priorBlocks={f'V12_B{i}':'PASS'for i in range(7)},
        ACTIVE_WEB_V1_2_ARCHITECTURE='APPROVED',controlledFetch=dict(networkEgressControl='ENFORCED',publicOnly='ENFORCED',evidenceProfile='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1'),
        interactiveBrowser=dict(networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED'),
        historicalStates=dict(WEBVIEW2_REMEDIATION_BLOCK_05_FINAL='PASS',WEBVIEW2_BLOCK06_ARCHITECTURE='BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT',
            CEF_CHROMIUM_STANDARD_CANDIDATE='REJECTED',SOURCE_CONTROLLED_CHROMIUM='REQUIRES_SOURCE_PROTOTYPE',AW8='BLOCKED'),
        productSourceChanges=read(OUT/'causal_repair.json')['paths'],passedDistinct=len(unique)+66,newB7Distinct=finals['distinct'],
        candidateIdentitySha256=sha(OUT/'candidate_identity.json'),commitPushTagRelease=False))
    text=f'''# V12-B7 — Certificación E2E final Active Web V1.2

## Resultado

```ini
V12_B7 = PASS
ACTIVE_WEB_V1_2_FINAL = PASS
ACTIVE_WEB_V1_2 = READY
READY_FOR_HUMAN_RELEASE_DECISION = true
RELEASE_APPROVED = false
ACTIVE_WEB_CORE = NOT_READY
```

El candidato actual es `{cid}`. Pasaron **{finals['distinct']} casos B7**, **{reg['distinct']} casos de regresión**, **{affected['distinct']} comprobaciones causales** y **66 tests Desktop**: **{len(unique)+66} casos distintos**, sin sumar repeticiones. Los resultados del candidato anterior están en `attempts/`, incluidos los fallos y sus errores de teardown. No pertenecen al candidato actual.

## Reparación causal y freeze

La prueba de usar un `downloadRef` como `ElementRef` encontró una excepción Core que escapaba al resultado tipado. `browser_actions_v12.py` convierte ahora ese rechazo previo al efecto en `PolicyInputError(INVALID_BROWSER_BINDING)`. No concede autoridad ni cambia acciones. `bootstrap_web_v12.py` carga el nuevo artefacto host-owned B7; B6 y sus evidencias permanecen intactos. Tras el nuevo freeze se ejecutaron las comprobaciones afectadas y nuevamente el corpus E2E y la regresión focal. El host DLL sigue siendo `8a80a8987d081c750f39b598e1db5f00f58ef622e0310b7bd1c5670147f3a4a6`, SDK `1.0.4258.31`, Runtime `154.0.4258.62`, X64, .NET `10.0.7`, IPC v6.

## Fronteras demostradas

- CLI y JSONL reales atraviesan AgentLoop, ToolRuntime, Policy/Grant, DNS por paquetes, pin numérico y el transporte HTTP/TLS certificado. La confianza TLS adicional es exacta y sólo del proceso de test.
- WebView2 real demuestra observación/ref opaca, aprobación exacta, denegación antes del efecto, pérdida real después de STARTED, UNKNOWN, una única acción y barrera de incertidumbre.
- Upload host-owned, download autorizado/staging/digest, drive-by sin archivo, interrupción por límite y takeover con secreto sintético pasan por la composición productiva.
- El smoke calibrado de protocolo externo tiene un handler positivo fuera de la ventana protegida y cero launches dentro. No se ejecutó una campaña de red de WebView2.
- Los cuatro estados de disponibilidad son independientes. Desktop proyecta la misma Application/backend; se verificó el bridge y se compilaron sus raíces. No se afirma una campaña GUI Electron completa ni una certificación de instalador.
- Controlled Fetch conserva GET/HEAD, TEXT/HTML_STATIC/JSON y el perfil `CF_B2_GET_HEAD_HTTP11_WINDOWS_V1`. Browser conserva `NOT_PROVIDED`/`HOST_UNISOLATED`. POST/auth/binary/cookies y FORM_SUBMIT siguen indisponibles.

## Limpieza y disposición explícita del recibo retenido

La revisión automática rechazó `Remove-Item` sobre el journal owned del primer smoke del guard, antes de ejecutar la orden, con el motivo **`blocked by policy`**. El archivo de 1.079 bytes conserva SHA-256 `7b7d1f9298719e8c7b5f7282c44d82a347553352ec23eeb8c5d9e87a04c1b968`. No se reintentó su eliminación ni se usó otro mecanismo. Sólo se obtuvo una copia de lectura para revisión. La auditoría distingue procesos/listeners/UDF/TLS/staging cerrados de journals de auditoría retenidos. El staging de 36 bytes dejado por un test fallido y su raíz vacía sí se retiraron mediante operaciones literales sobre recursos nuevos owned.

La reauditoría confirma 172 UDF ausentes, cero procesos/listeners owned, staging vacío, seis fixtures TLS limpiados, dos canaries desregistrados y 341 pins compatibles sin referencias a Temp. El journal del candidato actual se archivó y retiró mediante una operación literal separada, sobre su identidad nueva; el journal cuyo retiro fue rechazado permanece intacto.

**No se declara eliminación de todos los archivos**. El runtime cleanup exigido queda CONFIRMED. El recibo de auditoría inerte de 1.079 bytes conserva CLEANUP_UNCONFIRMED / UNCONFIRMED_POLICY_BLOCK, con causa e impacto explícitos. La sección 24 de la solicitud permite esa disposición por causa real y no exige forensic erasure. Por ello la fila CLEANUP es PASS dentro de ese contrato; no afirma eliminación del recibo ni aislamiento adicional. La revisión interna de alcance confirmó esta interpretación, sin introducir un gate de ausencia universal de archivos. Se conservan también los temporales B6 `UNCONFIRMED_POLICY_BLOCK`, comprobados inertes; no se intentó borrarlos.

## Preservación y límites

La deuda CI histórica de **99 funciones B1/B2** permanece sin cambios y no causó los fallos del candidato. El inventario global legado sigue con drift; no se anuncia PASS de esa CI. Las fuentes B7 nuevas tienen ejecución local explícita, sin fingir clasificación CI ya aprobada.

`ACTIVE_WEB_CORE` es el agregado histórico V1/V1.1, no un switch V1.2. Permanece `NOT_READY`; `AW8=BLOCKED` y el Block06 histórico permanecen byte-intactos. El namespace B7 es aditivo. Los guards de evidencia estuvieron activos y sus ACL fueron restauradas, sin restore-by-hash.

No hubo commit, push, tag, release, ampliación de capabilities ni mantenimiento de perfiles históricos. La certificación final se detiene para revisión humana.
'''
    (OUT/'resultados.md').write_text(text,encoding='utf-8')
    verify_freeze()
    # Entire prior evidence is immutable; source deltas are only the recorded repair.
    baseline=read(OUT/'baseline.json');changes=[];errors=[];historical=0
    for pin in baseline['files']:
        p=ROOT/pin['path']
        if not p.is_file()or sha(p)!=pin['sha256']:
            if '/web_v12_b7/'in pin['path']or '/v12_b7/'in pin['path']:changes.append(pin['path'])
            else:errors.append(pin['path'])
        if pin['path'].startswith(('docs/active_web_v1/','docs/active_web_v1_2/')):historical+=1
    assert not errors,errors
    pins=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(OUT.rglob('*'))if p.is_file()and p.name!='integrity.json']
    write('integrity.json',dict(schemaVersion=1,result='PASS',candidateId=cid,productPinsVerified=len(current['productPins']),
        baselineFilesVerified=len(baseline['files']),historicalEvidenceFilesByteIntact=historical,
        testToolingChangesAfterBaseline=changes,historyRestoredByHash=False,artifactPins=pins,
        HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    print(json.dumps(dict(candidate=cid,V12_B7='PASS',newB7=finals['distinct'],distinctPassed=len(unique)+66,artifactPins=len(pins))))

if __name__=='__main__':freeze_outputs();generate()
