"""Preflight-only V2-R2 runner. No campaign/inference path is enabled by default."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
FREEZE=ROOT/'docs/knowledge_inputs_v2/revision_02/freeze_final_v2_r2.json'
PROFILE=ROOT/'docs/knowledge_inputs_v2/revision_02/execution_profile_v2_r2.json'
def preflight():
    f=json.loads(FREEZE.read_text(encoding='utf-8')); p=json.loads(PROFILE.read_text(encoding='utf-8')); errors=[]
    for path, expected in f['pins'].items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest() if (ROOT/path).is_file() else 'MISSING'
        if actual.lower()!=expected.lower(): errors.append('DRIFT:'+path)
    if p['llm']['model']!='qwen3.5:9b' or p['llm']['digest']!='c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a': errors.append('MODEL_IDENTITY')
    if p['llm']['seed']!='NOT_SUPPORTED': errors.append('SEED_POLICY')
    if p['joint_authorization']!={'4K':True,'8K':True}: errors.append('CAMPAIGN_AUTHORIZATION')
    if f['campaigns_consumed']!=0 or f['inference']!=0 or f['retrieval']!=0 or f['admission']!=0: errors.append('NONZERO_EXECUTION_COUNTER')
    return errors
if __name__=='__main__':
    e=preflight(); print(json.dumps({'executable':not e,'campaigns_started':0,'campaigns_consumed':0,'inference':0,'retrieval':0,'admission':0,'errors':e})); raise SystemExit(0 if not e else 2)
