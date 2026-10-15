"""Build an offline freeze inventory for human review; never changes old artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DOCS=ROOT/'docs/knowledge_inputs_v2/revision_03'
HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def payload():
    baseline=json.loads((DOCS/'preserved_inventory.json').read_text(encoding='utf-8'))
    pins={r['path']:r['sha256'] for r in baseline['files']}
    pins['pyproject.toml']=sha(ROOT/'pyproject.toml')
    pins['docs/memory_v1/memory_v1_ready_resultados.md']=sha(ROOT/'docs/memory_v1/memory_v1_ready_resultados.md')
    for directory in (DOCS,HERE):
        for path in sorted(directory.rglob('*')):
            if not path.is_file() or path.name in ('freeze_final_v2_r3.json','human_authorization.pending.json','evidence_index.json'):continue
            if '__pycache__' in path.parts or path.suffix=='.pyc':continue
            pins[path.relative_to(ROOT).as_posix()]=sha(path)
    runtime=json.loads((DOCS/'runtime.json').read_text(encoding='utf-8'))
    return dict(schema='k8-v2-freeze-3',revision='V2-R3',status='FROZEN_PENDING_HUMAN_REVIEW',
        head=baseline['baseline_head'],knowledge_specific_minimum_context_window='NOT_DEFINED',
        profiles_file='docs/knowledge_inputs_v2/revision_03/profiles.json',retry_rules_file='docs/knowledge_inputs_v2/revision_03/retry_rules.json',
        authorization='additive external authorization bound to SHA of this exact freeze; never mutate this freeze to activate',
        campaigns_consumed=0,inference=0,retrieval=0,admission=0,quality_measured=False,ready=False,
        pins=[dict(path=path,sha256=value) for path,value in sorted(pins.items())],external_pins=runtime['external_pins'])
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    out=args.output.resolve()
    if out.is_relative_to(ROOT) or out.exists():raise ValueError('fresh external inventory required')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload(),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(freeze_sha256=sha(out),pins=len(payload()['pins']))))
