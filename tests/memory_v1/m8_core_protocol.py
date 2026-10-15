"""OD-08 synthetic, outcome-independent taxonomy and frozen Core protocol.

Only fixture inputs are read. No historical report, model, retrieval, ranking or
score is used for classification/enrolment. Weak/unknown cases remain CORE.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from local_cli.application.memory_recall import MemoryQueryComposer

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    ('m8-fixed-synthetic-v1', 'tests/memory_v1/fixtures/m8_quality_v1.json'),
    ('m8-query-document-heldout-v1', 'tests/memory_v1/fixtures/m8_query_heldout_v1.json'),
    ('m8-bge-final-heldout-v1', 'tests/memory_v1/fixtures/m8_bge_final_heldout_v1.json'),
)
SOURCE_HASHES = (
    '9412e7d40a34d4ea0b26fa4a665860bc381ac28c8472cba36c3cda5157ba1d2f',
    '8ab1f9cb69c46eab68657938efa55a75cc405e7e442c3b75dacb99b4cc159718',
    '97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe',
)
SCENARIOS = 'tests/memory_v1/fixtures/m8_scenarios_v1.json'
EXTRA_STOPWORDS = frozenset(('preference workspace synthetic fictional ficticio ficticia ficticios ficticias '
    'profile perfil project proyecto projects proyectos when before after here there must have has had '
    'than with without rather then now whom whose where why let only more most some any every each who '
    'work works user usuario memory memoria').split())
SPANISH_RECORD_IDS = {
    'm8-fixed-synthetic-v1': frozenset(('dark', 'metric', 'offline', 'morning')),
    'm8-query-document-heldout-v1': frozenset(('spelling', 'terrain', 'currency', 'decisions', 'clock', 'zone')),
}
CLASSIFIER_VERSION = 'od08-discriminative-taxonomy-v1'
THRESHOLDS = dict(recall3=.85, precision1=.90, ordinaryAbstentionAccuracy=.95,
    e2eAccuracy={'4096':.85, '8192':.90, '16384':.90}, lexicalP95Ms=50,
    softMs=350, hardMs=600, guardMs=50, criticalAccuracy=1.)


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def file_hash(path):
    return digest_bytes(Path(path).read_bytes())


def tokens(text):
    normalized = ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
        if unicodedata.category(c) != 'Mn')
    return set(re.findall(r'[^\W_]+', normalized, flags=re.UNICODE))


def content_tokens(text):
    stop = {t for w in MemoryQueryComposer.STOP_WORDS | EXTRA_STOPWORDS for t in tokens(w)}
    return {t for t in tokens(text) if len(t) >= 3 and t not in stop}


def languages(data, query, record):
    if record is not None and query['question'] == record.get('key'):
        qlang = 'KEY'
    else:
        qlang = query.get('queryLanguage') or ('ES' if query['question'].startswith('¿') else 'EN')
    if record is None:
        rlang = 'NONE'
    elif query.get('recordLanguage'):
        rlang = query['recordLanguage']
    elif data['datasetVersion'] in SPANISH_RECORD_IDS:
        rlang = 'ES' if record['id'] in SPANISH_RECORD_IDS[data['datasetVersion']] else 'EN'
    else:
        rlang = 'UNKNOWN'
    return qlang, rlang


def classify(data):
    records = {r['id']:r for r in data['records']}
    if len(records) != len(data['records']):
        raise ValueError('Duplicate records')
    indexed = {rid:content_tokens(r['text']+' '+r['key']) for rid,r in records.items()}
    frequencies = Counter(t for terms in indexed.values() for t in terms)
    # Fixed before measurement: content anchor matches <=10% of source records,
    # bounded to <=8 (final-item cap). Small corpora permit a unique anchor.
    max_df = max(1, min(8, len(records)//10))
    rows = []
    for q in data['queries']:
        rec = records.get(q['gold']) if q['gold'] is not None else None
        if q['gold'] is not None and rec is None:
            raise ValueError('Unknown gold')
        qlang, rlang = languages(data, q, rec)
        shared = sorted(content_tokens(q['question']) & indexed[rec['id']]) if rec else []
        anchors = [t for t in shared if frequencies[t] <= max_df]
        if rec is None:
            profile, rule = 'CORE', 'C_NEGATIVE_NO_EVIDENCE'
        elif q['question'] in (rec['key'], rec['text']):
            profile, rule = 'CORE', 'C_EXACT_KEY_OR_TEXT'
        elif rec['key'] and rec['key'] in q['question']:
            profile, rule = 'CORE', 'C_EXPLICIT_KEY'
        elif qlang in ('EN','ES') and rlang in ('EN','ES') and qlang != rlang:
            profile, rule = 'SEMANTIC', 'S_VERIFIED_CROSS_LANGUAGE'
        elif anchors:
            profile, rule = 'CORE', 'C_DISCRIMINATIVE_LEXICAL'
        elif shared or rlang == 'UNKNOWN' or qlang not in ('EN','ES'):
            profile, rule = 'CORE', 'C_CONSERVATIVE_AMBIGUOUS'
        else:
            profile, rule = 'SEMANTIC', 'S_NO_CONTENT_LEXICAL_SUPPORT'
        rows.append(dict(caseId=q['id'], profile=profile, rule=rule, gold=q['gold'],
            originalSubset=q['type'], queryLanguage=qlang, recordLanguage=rlang,
            lexicalAnchor=q['question'] if rule.startswith('C_EXACT') else anchors,
            sharedContentTokens=shared,
            anchorDocumentFrequencies={t:frequencies[t] for t in anchors},
            maxAnchorDocumentFrequency=max_df, sourceRecords=len(records),
            originalCaseSha256=digest_bytes(canonical(q)),
            originalRecordSha256=digest_bytes(canonical(rec)) if rec else None))
    if len({r['caseId'] for r in rows}) != len(rows):
        raise ValueError('Duplicate queries')
    return sorted(rows, key=lambda r:r['caseId'])


def source_data():
    loaded = []
    for (version,path),sha in zip(SOURCES,SOURCE_HASHES):
        raw = (ROOT/path).read_bytes()
        if digest_bytes(raw) != sha:
            raise ValueError('Immutable source changed: '+path)
        data = json.loads(raw)
        if data.get('datasetVersion') != version or data.get('syntheticOnly') is not True:
            raise ValueError('Unexpected source')
        loaded.append((path,sha,data))
    return loaded


def build_annotation():
    result = dict(schemaVersion=1, annotationVersion=CLASSIFIER_VERSION,
        rules=dict(priority=['CORE_CONTRACT_NEGATIVE','CORE_EXACT','SEMANTIC_VERIFIED_CROSS_LANGUAGE',
            'CORE_DISCRIMINATIVE_ANCHOR','CORE_AMBIGUOUS','SEMANTIC_NO_CONTENT_SUPPORT'],
            normalization='NFD/casefold/Latin diacritics removed/Unicode words; no stemming or translation',
            composerStopwords=sorted(MemoryQueryComposer.STOP_WORDS), extraStopwords=sorted(EXTRA_STOPWORDS),
            discriminative='df <= max(1,min(8,floor(sourceRecords*0.10)))',
            ambiguous='CORE', minimumCorePositives=50, minimumOrdinaryNegatives=15),
        sources=[], historicalResultsUsed=False, rankingOrInferenceUsed=False)
    for path,sha,data in source_data():
        rows = classify(data)
        result['sources'].append(dict(corpusId=data['datasetVersion'], path=path, sha256=sha, cases=rows,
            counts=dict(Counter(r['profile'] for r in rows))))
    raw = (ROOT/SCENARIOS).read_bytes()
    scenarios = json.loads(raw)
    result['contractScenarios'] = dict(corpusId=scenarios['datasetVersion'], path=SCENARIOS,
        sha256=digest_bytes(raw), cases=[dict(caseId=c['id'], profile='CORE', rule='C_CONTRACT_CRITICAL_OR_TEMPORAL',
            originalSubset=c['subset'], queryLanguage='EN', recordLanguage='FIXTURE',
            lexicalAnchor=[], originalCaseSha256=digest_bytes(canonical(c))) for c in scenarios['cases']])
    return result


def outcome_independence_proof():
    checks=[]
    for path,sha,data in source_data():
        original = classify(data)
        modified = deepcopy(data)
        for i,q in enumerate(modified['queries']):
            q.update(passed=bool(i%2), score=999-i, historicalOutcome='FAIL' if i%2 else 'PASS',
                semanticRank=1, lexicalRank=1000, response='unsupported historical guess')
        # These diagnostic fields are not classifier inputs. Strip them from
        # the proof's originalCaseSha (provenance hash legitimately covers bytes).
        mutated = classify(modified)
        without_case_hash = lambda rows:[{k:v for k,v in r.items() if k!='originalCaseSha256'} for r in rows]
        independent = without_case_hash(original) == without_case_hash(mutated)
        reversed_data = deepcopy(data)
        reversed_data['queries'].reverse(); reversed_data['records'].reverse()
        stable = original == classify(reversed_data)
        if not independent or not stable:
            raise ValueError('Outcome/order dependence')
        checks.append(dict(source=path, sha256=sha, outcomesAndRanksChanged=True,
            classificationUnchanged=independent, inputOrderUnchangedClassification=stable))
    return dict(proof='metamorphic synthetic outcome/rank/order changes; classifier never reads reports', checks=checks,
        noInference=True, passed=all(c['classificationUnchanged'] for c in checks))


def build_protocol(annotation):
    enrolled=[]; semantic=[]; unique_questions=set(); unique_facts=set()
    datasets={d['datasetVersion']:d for _,_,d in source_data()}
    for src in annotation['sources']:
        data=datasets[src['corpusId']];lookup={q['id']:q for q in data['queries']}
        for row in src['cases']:
            item=dict(sourceCorpus=src['corpusId'], sourcePath=src['path'], sourceSha256=src['sha256'],
                caseId=row['caseId'], caseSha256=row['originalCaseSha256'], rule=row['rule'],
                positive=row['gold'] is not None)
            if row['profile']=='SEMANTIC':
                semantic.append(item);continue
            question=' '.join(unicodedata.normalize('NFKC',lookup[row['caseId']]['question']).casefold().split())
            if question in unique_questions:
                raise ValueError('Duplicate Core question: '+question)
            unique_questions.add(question)
            if row['gold'] is not None:unique_facts.add((src['corpusId'],row['gold']))
            enrolled.append(item)
    positives=sum(r['positive'] for r in enrolled);negatives=len(enrolled)-positives
    if positives<50 or negatives<15:raise ValueError('Core denominator insufficient')
    return dict(schemaVersion=1, protocolVersion='m8-core-certification-v1', phase='M8_CORE',
        annotationSha256=digest_bytes(canonical(annotation)), sourceCorpora=list(SOURCES),
        thresholds=THRESHOLDS, model='qwen3.5:9b', modelDownloads=False,
        semanticProfile='NOT_CERTIFIED', semanticCampaignExecuted=False,
        enrolled=enrolled, semanticCasesPreserved=semantic,
        denominators=dict(coreTotal=len(enrolled), positive=positives, ordinaryNegative=negatives,
            uniqueQuestions=len(unique_questions), uniqueSourceFacts=len(unique_facts),
            perWindow=len(enrolled), criticalPerWindow=len(annotation['contractScenarios']['cases'])),
        conditions=dict(backend='normal Application + real local Ollama; memory semantic unconfigured',
            seed='All original records per source, including distractors; no merged stores/rewritten records',
            history='Same original facts + 1000 synthetic noise messages; reset before each independent question',
            attribution='Gold ID selected and intact source statement in actual MEMORY capsule; no transcript-only evidence',
            retries=0, answerScorer='unchanged m8_evaluation.score',
            critical='Separate 100% campaign; cannot inflate normal ranking denominator',
            historical='57.14% and all other raw outcomes immutable; prospective certification, not a new held-out claim'))


def capsule_statements(prompt):
    from local_cli.core.context import MEMORY_HEADER, MEMORY_FOOTER
    result=[]
    for message in prompt or []:
        content=message.get('content','')
        if message.get('role')!='user' or not content.startswith(MEMORY_HEADER+'\n') or not content.endswith(MEMORY_FOOTER):
            continue
        for line in content.splitlines()[1:-1]:
            if line.startswith('- [') and '] ' in line:
                try:value=json.loads(line.split('] ',1)[1])
                except (ValueError,TypeError):continue
                if isinstance(value,str):result.append(value)
    return result


def supported_answer(case, row, records):
    if row.get('answer') is None or not row.get('actualPrompt'):
        return None, None
    if case['gold'] is None:
        return None, row['score']['abstentionCorrect']
    fact=next(r['text'] for r in records if r['id']==case['gold'])
    evidence=case['gold'] in row.get('ids',[]) and fact in capsule_statements(row['actualPrompt'])
    return evidence, bool(row['score']['answerCorrect'] and evidence)


def budget_valid(row):
    b=row.get('budget') or {}
    if not b:return False
    return (sum(b.get(k,0) for k in ('current_message_tokens','working_context_tokens','tool_result_tokens','retrieval_tokens'))
        <= b['available'] and b['memory_tokens']<=min(int(.08*b['selected_context_window']),1024))


def quality_gate(rows, target, expected, negatives):
    complete=len(rows)==expected and all(r.get('answer') is not None for r in rows)
    attributable=sum(r.get('supportedAnswerCorrect') is True for r in rows)/expected
    negative_rows=[r for r in rows if r['gold'] is None]
    abstention=sum(r.get('supportedAnswerCorrect') is True for r in negative_rows)/negatives
    lifecycle=all(r.get('turnStatus')=='completed' and r.get('terminalCount')==1 and not r.get('error') for r in rows)
    budget=all(budget_valid(r) for r in rows)
    return dict(passed=complete and attributable>=target and abstention>=.95 and lifecycle and budget,
        expected=expected, measured=len(rows), attributableAccuracy=attributable,
        positiveAccuracy=sum(r.get('supportedAnswerCorrect') is True for r in rows if r['gold'] is not None)/(expected-negatives),
        ordinaryAbstention=abstention, target=target, complete=complete,lifecycle=lifecycle,budget=budget)
