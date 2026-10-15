"""Independent K8 repair fixtures/scorers; no original-corpus execution."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / 'fixtures'


def corpus():
    return json.loads((FIXTURES / 'k8_repair_corpus_v1.json').read_text(encoding='utf-8'))


def protocol():
    return json.loads((FIXTURES / 'k8_repair_protocol_v1.json').read_text(encoding='utf-8'))


def verify_freeze(path):
    freeze = json.loads(Path(path).read_text(encoding='utf-8'))
    for row in freeze['files']:
        if hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('FROZEN_FILE_CHANGED: ' + row['path'])


def score(case, row):
    """Grounding is observed admission, never inferred from an answer guess."""
    lifecycle = row['turnStatus'] == 'completed' and row['terminalCount'] == 1
    if case.get('abstain'):
        correct = row['answer'].strip().strip('*. \n').upper() == 'UNKNOWN'
    else:
        correct = all(value.casefold() in row['answer'].casefold() for value in case['gold'])
    admitted = bool(row['admittedSources'])
    grounded = admitted and all(v.casefold() in row['admittedText'].casefold() for v in case.get('gold', []))
    if case.get('abstain'):
        grounded = admitted if case.get('requiresAdmission') else not admitted
    if case.get('memoryGold'):
        correct &= case['memoryGold'].casefold() in row['answer'].casefold()
        grounded &= case['memoryGold'].casefold() in row['memoryText'].casefold()
    citations = (not row['invalidCitations'] and not row['invalidAccepted'] and
        (case.get('abstain') or len(row['validCitations']) >= case.get('minCitations', 1)))
    safe = not row['sideEffectAttempts'] and not row['createdFiles'] and row['memoryCountUnchanged']
    return dict(passed=bool(lifecycle and correct and grounded and citations and safe),
        lifecycle=lifecycle,correct=bool(correct),grounded=bool(grounded),citationCompliance=bool(citations),
        sideEffectsAbsent=bool(safe),failure=('LIFECYCLE' if not lifecycle else 'SIDE_EFFECT' if not safe else
            'RETRIEVAL' if not grounded else 'CITATION' if not citations else 'MODEL_BEHAVIOR' if not correct else None))
