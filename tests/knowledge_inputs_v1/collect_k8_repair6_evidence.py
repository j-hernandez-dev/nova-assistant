"""Read-only synthetic V6 evidence collector. No inference or product writes.

Prints JSON for the agent to save with file-edit tools. Never rewrites history.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v6-20261008')


def pin(path):
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def walk(value):
    if isinstance(value,dict):
        yield value
        for item in value.values():yield from walk(item)
    elif isinstance(value,list):
        for item in value:yield from walk(item)


def collect():
    preflight=json.loads((ROOT/'docs/knowledge_inputs_v1/k8_repair6_evidence/preflight_v1.json').read_text())
    changed=[]
    for row in preflight['pins']:
        if pin(ROOT/row['path'])['sha256']!=row['sha256']:changed.append(row['path'])
    manifests=list((ROOT/'docs/knowledge_inputs_v1').glob('*manifest.json'))
    historical={}
    for manifest in manifests:
        if 'repair6' in manifest.name:continue
        for row in walk(json.loads(manifest.read_text(encoding='utf-8'))):
            if row.get('path') and row.get('sha256') and Path(row['path']).is_absolute():
                historical[row['path']]=row['sha256']
    historical_errors=[path for path,sha in historical.items()
        if not Path(path).is_file() or pin(Path(path))['sha256']!=sha]
    gates=[]
    for directory in sorted(OUT.iterdir()):
        run=directory/'run.json'
        if not run.is_file():continue
        row=dict(name=directory.name,output=str(directory),run=json.loads(run.read_text()),artifacts=[pin(run)])
        xml=directory/'tests.xml'
        if xml.is_file():
            root=ET.parse(xml).getroot();cases=root.findall('.//testcase')
            failures=[c.attrib for c in cases if c.find('failure') is not None]
            errors=[c.attrib for c in cases if c.find('error') is not None]
            skips=[dict(id=c.get('classname','')+'::'+c.get('name',''),reason=c.find('skipped').get('message',''))
                for c in cases if c.find('skipped') is not None]
            row['junit']=dict(total=len(cases),successful=len(cases)-len(failures)-len(errors)-len(skips),
                failures=failures,errors=errors,skips=skips)
            row['junit']['suiteAttributes']=[s.attrib for s in root.findall('.//testsuite')]
            row['junit']['passedSubtests']=sum(int(n) for n in re.findall(r'(\d+) subtests passed',
                (directory/'run.log').read_text(encoding='utf-8')))
            row['artifacts'].extend([pin(xml),pin(directory/'run.log')])
        else:
            row['artifacts'].extend(pin(p) for p in directory.glob('*.log'))
        gates.append(row)
    metrics=list((OUT/'quality-final-frozen').rglob('retrieval-v6.json'))
    assert len(metrics)==1
    metric=json.loads(metrics[0].read_text())
    historical_head=ET.parse('C:/Users/joseh/AppData/Local/Temp/nova-k8-repair-v5-20261008/head-final/tests.xml')
    old_skips=sorted(c.get('classname','')+'::'+c.get('name','') for c in historical_head.findall('.//testcase') if c.find('skipped') is not None)
    old_reasons={c.get('classname','')+'::'+c.get('name',''):c.find('skipped').get('message','')
        for c in historical_head.findall('.//testcase') if c.find('skipped') is not None}
    def normalize_reason(text):
        return re.sub(r'nova-k8-repair-v[56]-20261008','<external-v6-or-v5-output>',text)
    head=next((r for r in gates if r['name']=='head-final'),None)
    tags=subprocess.check_output(['git','show-ref','--tags'],cwd=ROOT,text=True).splitlines()
    return dict(schemaVersion=1,phase='K8_REPAIR_V6',baseline=preflight['head'],
        initialPins=len(preflight['pins']),authorizedChangedFiles=changed,
        onlyAuthorizedDelta=sorted(changed)==['local_cli/infrastructure/knowledge_lexical.py','local_cli/infrastructure/knowledge_query.py'],
        tagsUnchanged=tags==preflight['tags'],historicalArtifactsChecked=len(historical),historicalMismatches=historical_errors,
        historicalManifestPins=[pin(p) for p in manifests if 'repair6' not in p.name],
        originalK8Executed=False,newInference=False,tests=gates,metricsArtifact=pin(metrics[0]),
        metrics={k:v for k,v in metric.items() if k!='rows'},historicalSkips=old_skips,
        headSkipsUnchanged=(sorted(r['id'] for r in head['junit']['skips'])==old_skips) if head else None,
        headSkipReasonsUnchanged=all(normalize_reason(r['reason'])==normalize_reason(old_reasons.get(r['id'],''))
            for r in head['junit']['skips']) if head else None)


if __name__=='__main__':print(json.dumps(collect(),indent=2))
