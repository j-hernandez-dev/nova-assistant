"""Documentary signal from a private factual/control plan, never authority.

No global content-word blacklist. Floors, FTS/BM25, fusion and caps stay V1.
Existing host source/revision filters remain in the store, not inferred here.
"""
from local_cli.core.knowledge_retrieval import lexical_text
from local_cli.infrastructure.knowledge_query import plan_query, presentation

LEXICAL_QUERY_PROFILE = 'ki-document-rank-v1/lexical-signals-v4'


def documentary_terms(query):
    plan=plan_query(query)
    # Keys already live in factual spans; explicit inclusion deduplicates them.
    signal=' '.join(query[s.start:s.end] for s in (*plan.factual_spans,*plan.identifiers))
    return tuple(dict.fromkeys(lexical_text(signal).split()))[:32]


def factual_query(query):
    plan=plan_query(query)
    return ' '.join(query[s.start:s.end] for s in plan.factual_spans)


def presentation_clause(normalized):
    return presentation(normalized)


def identifier_terms(signal):
    return tuple(t for t in signal if any(c.isalpha() for c in t) and any(c.isdigit() for c in t))
