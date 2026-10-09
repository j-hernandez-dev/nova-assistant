"""Frozen V4 scoring: no guessing, no output substitution in the scorer."""
from tests.knowledge_inputs_v1.k8_repair2_helpers import read,verify,FIXTURES
from tests.knowledge_inputs_v1.k8_repair3_helpers import score as prior_contract_score
from local_cli.application.knowledge_output import canonical_terminal


def score(case,row):
    base=prior_contract_score(case,row)
    exact=(row['answer']=='UNKNOWN') if case.get('abstain') else True
    output=(row['publicContent']==row['answer']==row['transcriptAnswer'] and
        row['answer']==canonical_terminal(row['rawAnswer']))
    health=row['auditHealth']
    audits=(health['deliveryFailures']==0 and health['lastError'] is None and not health['storageGapCodes'] and
        all(a['valid'] and a['complete'] and not a['gap'] for a in row['auditOperations']))
    return {**base,'passed':bool(base['passed'] and exact and output and audits),
        'exactAbstention':bool(exact),'publicOutputContract':bool(output),
        'auditDelivery':bool(audits),'failure':base['failure'] or (
            'ABSTENTION_OUTPUT_CONTRACT' if not exact or not output else
            'AUDIT_DELIVERY' if not audits else None)}
