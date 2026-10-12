"""B7 evidence tooling: read-only verification and additive candidate freeze."""
import hashlib
import json
import os
from pathlib import Path
import platform
import ssl
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/active_web_v1_2/v12_b7_final_e2e'
B6 = ROOT / 'docs/active_web_v1_2/v12_b6_snapshot_productive_integration'
EXCLUDED = {'.git','node_modules','__pycache__','.pytest_cache','.cache','bin','obj','dist','out'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def verify_b6():
    baseline = read(B6/'baseline.json')
    seal = read(B6/'integrity.json')
    changes = {r['path']:r['after'] for r in seal['authorizedSourceChanges']}
    causal=read(OUT/'causal_repair.json') if (OUT/'causal_repair.json').exists() else {'paths':[]}
    overrides={r['path']:r['after'] for r in causal['paths']}
    failures=[]
    for pin in baseline['files']:
        p=ROOT/pin['path']
        if not p.is_file() or sha(p)!=overrides.get(pin['path'],changes.get(pin['path'],pin['sha256'])): failures.append(pin['path'])
    for pin in seal['newAndChangedArtifactPins']:
        p=ROOT/pin['path']
        if not p.is_file() or sha(p)!=overrides.get(pin['path'],pin['sha256']): failures.append(pin['path'])
    candidate=read(B6/'product_candidate.json')
    for cap in ('fetch','browser'):
        for path,digest in candidate[cap]['pins']:
            p=Path(path); p=p if p.is_absolute() else ROOT/p
            if not p.is_file() or sha(p)!=overrides.get(path,digest): failures.append(path)
    assert not failures, 'B6 integrity mismatch: '+str(failures)
    return dict(result='PASS',baselineFiles=len(baseline['files']),artifactPins=len(seal['newAndChangedArtifactPins']),
        historicalFiles=seal['historicalEvidenceFilesByteIntact'],historicalEvidenceByteIntact=True,
        acceptedB6SourceDelta=causal['paths'],restoredByHash=False)

def inventory():
    pins=[]
    for parent,dirs,files in os.walk(ROOT):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDED and not (Path(parent)/d).is_symlink())
        for name in sorted(files):
            p=Path(parent)/name
            if p.is_symlink() or p.is_relative_to(OUT): continue
            pins.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    return pins

def product_pin(pin):
    path=pin['path']
    return (path.startswith('local_cli/') or path.startswith(('desktop/electron/','desktop/src/','desktop/shared/'))
        or (path.startswith('native/nova-browser-host/') and '/tests/' not in path)
        or path in ('pyproject.toml','desktop/package.json','desktop/package-lock.json','desktop/tsconfig.json')
        or '/candidate_host/' in path or path.endswith('/product_candidate.json'))

def freeze():
    assert not (OUT/'candidate_identity.json').exists(), 'Preserve existing freeze; create a separate attempt if repair needed'
    verification=verify_b6()
    pins=inventory(); product=[p for p in pins if product_pin(p)]
    identity=hashlib.sha256(json.dumps(product,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert head=='b0bf60f91956e4a5c17af02be5a6e241ec0363a7'
    artifact=OUT/'product_candidate.json' if (OUT/'product_candidate.json').exists() else B6/'product_candidate.json'
    candidate=read(artifact)
    framework=read((ROOT/candidate['hostAssembly']).with_suffix('.runtimeconfig.json'))
    write('baseline.json',dict(schemaVersion=1,HEAD=head,excludedDirectoryNames=sorted(EXCLUDED),files=pins))
    write('candidate_identity.json',dict(schemaVersion=1,candidateId='AW_V12_B7_'+identity[:20],
        frozenAt=datetime.now(timezone.utc).isoformat(),sourceTreeIdentity=identity,HEAD=head,dirtyWorkingTreeExpected=True,
        productChangesFromAcceptedB6=artifact.parent==OUT,productPins=product,acceptedB6Integrity=verification,
        compositionArtifact=artifact.relative_to(ROOT).as_posix(),
        compositionArtifactSha256=sha(artifact),composition=candidate,
        browserHostBinarySha256=sha(ROOT/candidate['hostAssembly']),browserFramework=framework,
        runtime=dict(python=platform.python_version(),architecture=platform.machine(),os=platform.system(),openssl=ssl.OPENSSL_VERSION),
        schemaVersions=dict(WebCapabilitiesV12='WEB_CAPABILITIES_V12_1',Candidate=candidate['schema'],
            ControlledFetch='CONTROLLED_FETCH_V1_2',Browser='INTERACTIVE_BROWSER_V1_2',privateIPC=6),
        policyFamily='PolicyEngineV2/1',evidenceProfile='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1',
        compatibilityChain=dict(B3='V12_B3_PASS',B4='V12_B4_PASS',B5='V12_B5_PASS',B6='V12_B6_PASS',
            exactB6ChainArtifact='docs/active_web_v1_2/v12_b6_snapshot_productive_integration/evidence_compatibility.json',
            exactB6ChainSha256=sha(B6/'evidence_compatibility.json')),
        buildIdentities=dict(CLI='Pinned Python source composition',JSONL='Pinned Python source composition',
            Desktop='Pinned Electron/React/bridge source; build artifacts recorded in B7',releasedPackage=False),
        historicalActiveWebCore=dict(semantic='V1/V1.1 historical certification aggregate; not V1.2 switch',value='NOT_READY'),
        productiveDefault='FEATURES_OFF',releaseApproved=False))
    print(json.dumps(dict(candidateId='AW_V12_B7_'+identity[:20],productPins=len(product),baselineFiles=len(pins),verification=verification)))

def verify_freeze():
    data=read(OUT/'candidate_identity.json')
    failures=[p['path'] for p in data['productPins'] if not (ROOT/p['path']).is_file() or sha(ROOT/p['path'])!=p['sha256']]
    assert not failures, 'Frozen product changed: '+str(failures)
    verify_b6()
    print(json.dumps(dict(candidateId=data['candidateId'],productUnchanged=True,B6Integrity='PASS')))

if __name__=='__main__':
    import sys
    freeze() if len(sys.argv)==1 else verify_freeze()
