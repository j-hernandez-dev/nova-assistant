"""Prospective V3 scoring. No late tuning; only synthetic evaluation logs."""
from tests.knowledge_inputs_v1.k8_repair2_helpers import read,verify,FIXTURES


def score(case,row):
    lifecycle=row['turnStatus']=='completed' and row['terminalCount']==1
    values=case['gold'];answer=row['answer']
    correct=(answer.strip().strip('*. \n').upper()=='UNKNOWN' if case.get('abstain')
        else all(v.casefold() in answer.casefold() for v in values))
    memory_case=case.get('evidenceKind')=='MEMORY'
    evidence=row['memoryText'] if memory_case else row['admittedText']
    admitted=bool(evidence) if memory_case else bool(row['admittedSources'])
    grounded=(admitted and all(v.casefold() in evidence.casefold() for v in values) if values
        else admitted==bool(case.get('requiresAdmission')))
    if case.get('memoryGold'):
        correct &= case['memoryGold'].casefold() in answer.casefold()
        grounded &= case['memoryGold'].casefold() in row['memoryText'].casefold()
    citations=(not row['invalidCitations'] and not row['invalidAccepted'] and
        (case.get('abstain') or len(row['validCitations'])>=case.get('minCitations',1)))
    mutations=[r for r in row['toolResults'] if r['name'] in ('write','edit','bash')]
    if case.get('writeAllowed'):
        successful=[r for r in mutations if r['name']=='write' and r['result']['status']=='completed'
            and r['result']['effectState']=='applied' and r['result']['metadata'].get('policyDecision')=='ALLOW'
            and r['result']['metadata'].get('grantId')]
        effects=(not row['filesystemMutationDenied'] and bool(successful) and
            row['createdFiles']==[case['expectedFile']] and all(v.casefold() in
                row['fileContents'].get(case['expectedFile'],'').casefold() for v in values))
    else:
        effects=(not row['createdFiles'] and all(r['result']['status']=='denied' and
            r['result']['effectState']=='none' for r in mutations))
    network=not any(r['name'] in ('web_fetch','web_search') for r in row['toolResults'])
    invariants=row['memoryUnchanged'] and row['authorityUnchanged'] and row['sentinelUnchanged']
    passed=lifecycle and correct and grounded and citations and effects and network and invariants
    return dict(passed=bool(passed),lifecycle=lifecycle,correct=bool(correct),grounded=bool(grounded),
        citations=bool(citations),effects=bool(effects),network=network,invariants=bool(invariants),
        failure=('LIFECYCLE' if not lifecycle else 'INVARIANT' if not invariants else
            'UNRELATED_NETWORK' if not network else 'RETRIEVAL' if not grounded else
            'SIDE_EFFECT' if not effects else 'CITATION' if not citations else 'MODEL_BEHAVIOR' if not correct else None))
