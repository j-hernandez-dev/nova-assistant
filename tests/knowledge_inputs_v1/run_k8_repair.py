"""Explicit independent repair campaign. Quality and original K8 remain separate."""
import argparse
import json
from pathlib import Path
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main as regression_main
from tests.knowledge_inputs_v1.k8_repair_helpers import FIXTURES, verify_freeze

SELECTIONS['repair']=['tests/knowledge_inputs_v1/test_k8_repair.py']


def main():
    import sys
    if '--baseline' not in sys.argv:
        regression_main(); return
    parser=argparse.ArgumentParser(); parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]; out=args.output.resolve()
    if out.exists() or out==root or root in out.parents: parser.error('Fresh external output required')
    verify_freeze(FIXTURES/'k8_repair_freeze_v1.json')
    out.mkdir(parents=True)
    from tests.knowledge_inputs_v1.test_k8_repair import measure
    result=measure(out)
    (out/'retrieval.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__': main()
