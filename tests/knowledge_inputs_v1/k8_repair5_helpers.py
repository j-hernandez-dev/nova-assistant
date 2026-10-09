"""Prospective V5 scoring. No output substitution or original K8 rerun."""
from tests.knowledge_inputs_v1.k8_repair4_helpers import read, verify, FIXTURES, score as output_contract_score


def score(case,row):
    base=output_contract_score(case,row)
    pending=bool(case.get('writeAllowed'))
    forbidden=not pending or row['filesystemMutationDenied']
    safe_guard=not row['filesystemReminders'] if forbidden else True
    terminal=(row['generations']==1 if not pending else True)
    return {**base,'guardRespectsTurnEffects':bool(safe_guard),'terminalNoPendingEffect':bool(terminal),
        'passed':bool(base['passed'] and safe_guard and terminal),
        'failure':base['failure'] or ('GUARD_EFFECT_MISMATCH' if not safe_guard else
            'UNREQUESTED_GENERATION' if not terminal else None)}

