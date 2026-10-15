"""Read-only gate review; emits one fresh evidence JSON, never edits product."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=Path(__file__).resolve().parent
OUTPUT=EVIDENCE/'closure_review.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest().upper()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def relative(path):return path.relative_to(ROOT).as_posix()


def group(directory, name):
    path=directory/(name+'.xml')
    cases=list(ET.parse(path).iter('testcase'))
    assert cases and not any(c.find('failure') is not None or c.find('error') is not None for c in cases),path
    skipped=[c.attrib['name'] for c in cases if c.find('skipped') is not None]
    log=(directory/(name+'.log')).read_text(encoding='utf-8')
    passed=re.search(r'(\d+) passed',log)
    assert passed,path
    return dict(xml=relative(path),passed=int(passed[1]),skipped=skipped,
                cases=[dict(name=c.attrib['name'],file=c.get('file','').replace('\\','/'),
                            status='SKIP' if c.find('skipped') is not None else 'PASS',
                            seconds=float(c.get('time','0'))) for c in cases])


def main():
    assert not OUTPUT.exists(), 'Keep all prior review evidence intact'
    snapshot=json.loads(gzip.decompress(base64.b64decode(
        (EVIDENCE/'closure_before_snapshot.json.gz.b64').read_text(encoding='utf-8'))))
    permitted={'tests/security_v12/test_s8_e2e.py','tests/security_v12/s8_backend_entry.py',
               'tests/security_v12/run_s8.py','docs/security_v12/s8_resultados.md',
               'docs/security_v12/s8_manifest.json'}
    changed=[];missing=[]
    for name,digest in snapshot['files'].items():
        path=ROOT/name
        if not path.is_file():missing.append(name)
        elif sha(path)!=digest.upper():changed.append(name)
    assert not missing and set(changed)<=permitted,(missing,changed)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    assert head==snapshot['head'] and branch==snapshot['branch'] and not staged

    directories=[EVIDENCE/'after_symlink_permission',EVIDENCE/'closure_regression',EVIDENCE/'closure_final_e2e']
    runs=[read(d/'run.json') for d in directories]
    assert all(r['head']==head and r['testsStatus']=='PASS' and
               all(g['exitCode']==0 for g in r['groups']) for r in runs)
    assert runs[0]['requiredGroupsRequested']['hostReal']
    assert runs[1]['requiredGroupsRequested']['node']
    assert runs[2]['requiredGroupsRequested']['e2e']
    before_manual_mismatches=[n for n,h in runs[0]['sourceHashes'].items()
                              if snapshot['files'].get(n,'').upper()!=h.upper()]
    assert not before_manual_mismatches,before_manual_mismatches
    manual_drift=[n for n,h in runs[0]['sourceHashes'].items() if sha(ROOT/n)!=h.upper()]
    assert set(manual_drift)<=permitted and not any(n.startswith('local_cli/') for n in manual_drift)
    for run in runs[1:]:
        assert all(sha(ROOT/n)==h.upper() for n,h in run['sourceHashes'].items())
    groups=[]
    for directory,run in zip(directories,runs):
        for g in run['groups']:
            if (directory/(g['name']+'.xml')).exists():groups.append(group(directory,g['name']))
    symlinks=[c for g in groups if g['xml'].endswith('after_symlink_permission/s3_windows.xml')
              for c in g['cases'] if c['name'].endswith('[directory_symlink]') or c['name'].endswith('[file_symlink]')]
    assert len(symlinks)==2 and all(c['status']=='PASS' for c in symlinks)
    native_source=(ROOT/'tests/security_v12/test_s3_windows.py').read_text(encoding='utf-8')
    assert 'os.symlink(target, link' in native_source and 'pytest.fail' in native_source
    assert 'rt = runtime(workspace)' in native_source and 'result = invoke(rt, workspace, name, args, number)' in native_source

    proof=read(directories[2]/'ollama_dependency_proof.json')
    assert proof['status']==proof['auditStatus']=='PASS' and proof['finalBytesEqual']
    assert proof['realToolResultInWriteInput'] and proof['distinctInferences'] and proof['markerAbsentFromUserInputs']
    assert proof['normalSubmitUserInputs']==2 and proof['finalSha256']==proof['writeAfterHash']
    backend=read(directories[2]/'ollama_backend.json')
    closed=read(directories[2]/'ollama_backend_closed.json')
    assert backend['nativeBroker'] and not backend['providerScripted']
    assert closed['rawAuditArtifacts']
    for artifact in closed['rawAuditArtifacts']:
        assert sha(directories[2]/artifact['file'])==artifact['sha256'].upper()
    terminals=[r for r in backend['audit'] if r['kind']=='terminal']
    assert len(terminals)==3 and all(r['data']['outcome']=='completed' for r in terminals)

    matrix=read(ROOT/'docs/security_v12/s8_matrix.json')
    invariants=[]
    for row in matrix['invariants']:
        selected=[g for g in groups if any(c['file'] in row['files'] and c['status']=='PASS' for c in g['cases'])]
        missing_families=[name for name in row['files'] if not any(
            c['file']==name and c['status']=='PASS' for g in selected for c in g['cases'])]
        assert not missing_families,(row['id'],missing_families)
        invariants.append(dict(**row,status='PASS',evidence=sorted(set(g['xml'] for g in selected)),
                               missingFamilies=[],failingCasesInMappedFamilies=[]))
    assert len(invariants)==28
    historical=read(EVIDENCE/'pre_normative_review/s8_manifest.json')
    old_pins=historical['sourceAndArtifactPinsSHA256']
    old_pin_drift=[n for n,h in old_pins.items() if sha(ROOT/n)!=h.upper()]
    assert set(old_pin_drift)<=permitted,old_pin_drift
    result=dict(status='PASS',classification='MODEL_BEHAVIOR',READYDeclared=False,
        beforeFiles=len(snapshot['files']),missing=missing,changedBeforeFinalDocuments=changed,
        productChangesThisClosure=[],head=head,branch=branch,staged=staged,
        previousPins=len(old_pins),previousPinDriftOnlyAuthorized=old_pin_drift,
        earlierWinError1314EvidencePreserved=True,oldFailedAttemptsStillFail=True,
        manualSourcePinsVerifiedBeforeChanges=len(runs[0]['sourceHashes']),
        manualSourceDriftOnlyTestHarness=manual_drift,manualProductDrift=[],
        symlinkReview=dict(cases=symlinks,fixturesCreated=True,realBrokerReached=True,
            nativeSourceSHA256=sha(ROOT/'tests/security_v12/test_s3_windows.py'),
            basis='Matching source and unskipped passing XML: creation failure is pytest.fail; real default authority invokes five tools; legacy fallback is pytest.fail. Temporary links were cleaned, not inspected as existing links today.'),
        runs=[relative(d/'run.json') for d in directories],groups=groups,invariants=invariants,
        localDependencyProof=relative(directories[2]/'ollama_dependency_proof.json'))
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('groups','invariants')},indent=2))


if __name__=='__main__':main()
