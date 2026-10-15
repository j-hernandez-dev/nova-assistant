"""Test-only dataset/metrics contract. No store, model calls or recall algorithm.

Gold labels are expected future outcomes, not claims about today's product.
Unknown/product-not-implemented measurements remain None, never fabricated zero.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from uuid import UUID


DATASET_PATH = Path(__file__).parent / 'fixtures' / 'corpus_v1.json'
KINDS = {'PREFERENCE', 'SEMANTIC_FACT', 'WORKSPACE_FACT', 'EPISODE', 'PROCEDURE'}
SOURCES = {'USER_ASSERTION', 'USER_EXPLICIT_MEMORY', 'TOOL_OBSERVATION',
           'ASSISTANT_INFERENCE', 'SUBAGENT_PROPOSAL', 'IMPORT', 'SYSTEM_MIGRATION'}
STATUSES = {'ACTIVE', 'SUPERSEDED', 'CONFLICTED', 'RETRACTED', 'EXPIRED', 'DELETED'}


def load_dataset():
    data = json.loads(DATASET_PATH.read_text(encoding='utf-8'))
    validate_dataset(data)
    return data


def validate_dataset(data):
    """Fail loudly on an invalid fixture, including forged scope/provenance."""
    if data.get('schemaVersion') != 1 or data.get('syntheticOnly') is not True:
        raise ValueError('unsupported or non-synthetic dataset')
    subjects = {r['id'] for r in data['identities']['subjects']}
    workspaces = {r['id'] for r in data['identities']['workspaces']}
    sessions = set(data['identities']['sessions'])
    for value in subjects:
        if str(UUID(value)) != value or value in sessions:
            raise ValueError('subject fixture must be UUID, not session identity')
    for value in workspaces:
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('workspace fixture must be 64 hex characters')
    rows = {r['id']: r for r in data['evidence']}
    if len(rows) != len(data['evidence']):
        raise ValueError('duplicate evidence identity')
    for row in rows.values():
        if row['subjectId'] not in subjects or row['scope'] not in {'GLOBAL_PROFILE', 'WORKSPACE'}:
            raise ValueError('invalid evidence scope')
        if (row['scope'] == 'WORKSPACE' and row['workspaceId'] not in workspaces or
                row['scope'] == 'GLOBAL_PROFILE' and row['workspaceId'] is not None):
            raise ValueError('invalid workspace binding')
        source = row['source']
        if source['sourceClass'] not in SOURCES or source['sessionId'] not in sessions:
            raise ValueError('invalid source identity')
        if not all(source.get(k) for k in ('turnId', 'messageId', 'locator', 'observedAt')):
            raise ValueError('missing provenance')
        if row['status'] not in STATUSES or row['targetKind'] not in KINDS | {None}:
            raise ValueError('invalid taxonomy')
        if not set(row['supersedes'] + source['derivedFrom']) <= rows.keys():
            raise ValueError('broken lineage')
        if row['targetKind'] == 'PROCEDURE' and source['sourceClass'] != 'USER_EXPLICIT_MEMORY':
            raise ValueError('procedure fixture must be explicit')
    case_ids = set()
    for case in data['cases']:
        if case['id'] in case_ids:
            raise ValueError('duplicate case')
        case_ids.add(case['id'])
        if case['subjectId'] not in subjects or case['workspaceId'] not in workspaces:
            raise ValueError('invalid query scope')
        if type(case['k']) is not int or case['k'] <= 0 or not case['expectedResolution']:
            raise ValueError('invalid query expectation')
        gold, forbidden = set(case['relevantIds']), set(case['forbiddenIds'])
        if not gold | forbidden <= rows.keys() or gold & forbidden:
            raise ValueError('invalid gold labels')
        for key in gold:
            row = rows[key]
            if row['subjectId'] != case['subjectId'] or (
                    row['scope'] == 'WORKSPACE' and row['workspaceId'] != case['workspaceId']):
                raise ValueError('gold cannot cross scope')
            if row['status'] not in {'ACTIVE', 'CONFLICTED'} or row['targetKind'] is None:
                raise ValueError('gold is not an eligible candidate')
    for timeline in data['timelines']:
        for event in timeline['events']:
            if 'evidenceId' in event and event['evidenceId'] not in rows:
                raise ValueError('timeline refers to missing evidence')


def score_observation(dataset, case, *, ranked_ids, resolution):
    """precision@k=hits/k; recall@k=hits/|gold| (None if no gold).

    Also report hits/returned, scope leak, forbidden hit and exact resolution.
    A raw ranking never establishes factual confidence or write eligibility.
    """
    rows = {r['id']: r for r in dataset['evidence']}
    if len(set(ranked_ids)) != len(ranked_ids) or not set(ranked_ids) <= rows.keys():
        raise ValueError('observation has duplicate/unknown evidence IDs')
    selected = ranked_ids[:case['k']]
    hits = len(set(selected) & set(case['relevantIds']))
    leaks = sum(rows[i]['subjectId'] != case['subjectId'] or (
        rows[i]['scope'] == 'WORKSPACE' and rows[i]['workspaceId'] != case['workspaceId']) for i in selected)
    return {'precision_at_k': hits / case['k'],
            'precision_returned': hits / len(selected) if selected else None,
            'recall_at_k': hits / len(case['relevantIds']) if case['relevantIds'] else None,
            'scope_leaks': leaks,
            'forbidden_hits': len(set(selected) & set(case['forbiddenIds'])),
            'resolution_correct': resolution == case['expectedResolution'],
            'abstention_correct': (not selected) if not case['relevantIds'] else None,
            'returned_count': len(selected), 'k': case['k']}


def tac_reference_ceiling(window, output_reserve, safety_margin, mandatory_tokens):
    """MEMORY §19 arithmetic oracle ONLY, not a wired Core/MEMORY category.

    Includes all mandatory material/current user/minimum continuity in M.
    Ceilings are not reservations. No 60/40 split implementation in M0.
    """
    if any(type(v) is not int or v < 0 for v in
           (window, output_reserve, safety_margin, mandatory_tokens)):
        raise ValueError('invalid reference budget')
    available = max(0, window - output_reserve - safety_margin)
    optional = max(0, available - mandatory_tokens)
    shared = min(math.floor(.15 * available), optional)
    return {'available': available, 'optional': optional,
            'shared_retrieval_cap': shared,
            'memory_hard_cap': min(shared, math.floor(.08 * window), 1024),
            'implementation': 'REFERENCE_ORACLE_ONLY'}


def unknown_quality():
    return {'state': 'NOT_IMPLEMENTED', 'precision_at_k': None, 'recall_at_k': None,
            'conflict_accuracy': None, 'correction_accuracy': None,
            'delete_no_resurrection': None, 'semantic_model_latency_ms': None,
            'reason': 'M0 has no production MEMORY retrieval/write/delete/embedding adapter'}
