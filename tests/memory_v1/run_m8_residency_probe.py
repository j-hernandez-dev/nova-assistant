"""M8 local installed-model residency probe, not product config or quality.

Only loads existing local models for this explicit synthetic experiment. No
pull, GPU change, global options, or unload. Co-residency must be observed, not
inferred from installed capabilities. Original 9B results remain authoritative
for that configuration; this probes the already-installed smaller 7B candidate.
"""
import argparse
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request,urlopen


def request(path,payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request('http://127.0.0.1:11434/api/'+path,data=data,
        headers={'Content-Type':'application/json'}),timeout=180) as response:
        return json.load(response)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve()
    if out.exists():p.error('New output required')
    out.mkdir(parents=True)
    report={'syntheticOnly':True,'modelsDownloaded':False,'globalConfigChanged':False,
        'gpuChanged':False,'qualityClaim':False,'chatModel':'qwen2.5:7b','embeddingModel':'qwen3-embedding:8b'}
    chat={'model':report['chatModel'],'stream':False,'messages':[{'role':'user','content':'Reply only OK.'}],
        'options':{'num_ctx':4096,'num_predict':8,'temperature':0}}
    try:
        names={m['name'] for m in request('tags')['models']}
        if not {report['chatModel'],report['embeddingModel']}<=names:raise RuntimeError('Candidate not installed')
        report['initialPs']=request('ps');report['chatBefore']=request('chat',chat)
        began=perf_counter()
        embedded=request('embed',{'model':report['embeddingModel'],'input':['Synthetic M8 residency fixture']})
        report['explicitEmbeddingLoadMs']=(perf_counter()-began)*1000
        report['dimensions']=len(embedded['embeddings'][0])
        report['afterEmbeddingPs']=request('ps');report['chatAfter']=request('chat',chat)
        report['afterChatPs']=request('ps')
        wanted={report['chatModel'],report['embeddingModel']}
        report['coResidentObserved']=wanted<={m['name'] for m in report['afterChatPs']['models']}
    except Exception as exc:report['errorCode']=type(exc).__name__
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'coResidentObserved':report.get('coResidentObserved'),'errorCode':report.get('errorCode')}))


if __name__=='__main__':main()
