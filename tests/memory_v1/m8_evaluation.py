"""M8 locked test-only quality contracts. No product threshold decision."""
import hashlib
import json
from pathlib import Path

DATASET_PATH=Path(__file__).parent/'fixtures/m8_quality_v1.json'


def load_dataset():
    raw=DATASET_PATH.read_bytes();data=json.loads(raw)
    if data['schemaVersion']!=1 or data['syntheticOnly'] is not True:raise ValueError('Invalid M8 dataset')
    ids={r['id'] for r in data['records']}
    if len(ids)!=len(data['records']) or len({q['id'] for q in data['queries']})!=len(data['queries']):raise ValueError('Duplicate IDs')
    if any(q['gold'] is not None and q['gold'] not in ids for q in data['queries']):raise ValueError('Unknown gold')
    return data,hashlib.sha256(raw).hexdigest()


def score(case,*,ranked_ids,answer):
    # Scorer never invents a response for failed/no inference. None means UNKNOWN
    # measurement, distinct from the model explicitly answering UNKNOWN.
    if len(set(ranked_ids))!=len(ranked_ids):raise ValueError('Duplicate retrieval IDs')
    gold=case['gold'];normalized=answer.casefold().strip() if isinstance(answer,str) else None
    if gold is None:
        return dict(recall3=None,precision1=None,answerCorrect=normalized=='unknown' if normalized is not None else None,
            abstentionCorrect=normalized=='unknown' if normalized is not None else None,returned=len(ranked_ids))
    return dict(recall3=float(gold in ranked_ids[:3]),precision1=float(bool(ranked_ids) and ranked_ids[0]==gold),
        answerCorrect=any(t.casefold() in normalized for t in case['accepted']) if normalized is not None else None,
        abstentionCorrect=None,returned=len(ranked_ids))


def aggregate(rows):
    def mean(name):
        values=[r['score'][name] for r in rows if r.get('score') and r['score'][name] is not None]
        return sum(values)/len(values) if values else None
    supported=[r['supportedAnswerCorrect'] for r in rows if r.get('supportedAnswerCorrect') is not None]
    return dict(cases=len(rows),measured=sum(r.get('answer') is not None for r in rows),
        recall3=mean('recall3'),precision1=mean('precision1'),answerAccuracy=mean('answerCorrect'),
        attributableAnswerAccuracy=sum(supported)/len(supported) if supported else None,
        attributableMeasured=len(supported),
        abstentionAccuracy=mean('abstentionCorrect'),failures=sum(bool(r.get('error')) for r in rows))


def evidence_score(case,row,records):
    """Independent QA: a gold guess is not evidence of persistent recall.

    Original raw-answer metric remains available, never retroactively rewritten.
    Prompt source facts are literal, so no extra model judge or gold injection is
    needed. Missing observation/inference is UNKNOWN, not an invented success.
    """
    if row.get('answer') is None or not row.get('actualPrompt'):
        return dict(goldEvidenceInActualPrompt=None,supportedAnswerCorrect=None)
    if case['gold'] is None:
        return dict(goldEvidenceInActualPrompt=None,
            supportedAnswerCorrect=row['score']['abstentionCorrect'])
    fact=next(r['text'] for r in records if r['id']==case['gold'])
    supported=any(fact in m.get('content','') for m in row['actualPrompt'])
    return dict(goldEvidenceInActualPrompt=supported,
        supportedAnswerCorrect=bool(row['score']['answerCorrect'] and supported))
