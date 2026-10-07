"""Synthetic-only forwarding observer: actual candidates, never a new ranker.

No gold is available during recall. NumPy is proxied on this private index,
not patched globally. The original einsum result and rankings pass through
unchanged. BM25 diagnostics and gold annotation occur AFTER recall/quiescence,
outside measured latency; no retry, additional embedding or late admission.
This module must never be wired into the production composition root.
"""
import hashlib
import re
import struct

from local_cli.application import memory_recall
from tests.memory_v1.m8_recall_trace import RecallTrace


class _ObservedNumpy:
    def __init__(self, original, trace, index):
        self.original, self.trace, self.index = original, trace, index

    def __getattr__(self, name):
        return getattr(self.original, name)

    def einsum(self, *args, **kwargs):
        result = self.original.einsum(*args, **kwargs)
        row = getattr(self.trace.context, 'row', None)
        if row is not None:
            # Actual pre-floor arithmetic inside the original search/lock.
            # Copy, since only synthetic fixtures are permitted and diagnostics
            # must survive later index mutation without retaining its matrix.
            positions = row['_eligible_positions']
            row['_cosines'] = tuple(zip(
                self.index._fields['memory_id'][positions].tolist(), result.tolist()))
        return result


class RankedRecallTrace(RecallTrace):
    def __enter__(self):
        super().__enter__()
        index = self.service.semantic.index
        self.patch(index, 'np', _ObservedNumpy(index.np, self, index))
        eligible = index._eligible_positions
        def positions(*args, **kwargs):
            result = eligible(*args, **kwargs)
            row = getattr(self.context, 'row', None)
            if row is not None:
                row['_eligible_positions'] = result.copy()
            return result
        self.patch(index, '_eligible_positions', positions)
        lexical = self.service.lexical.search
        def lexical_search(query):
            result = lexical(query)
            row = getattr(self.context, 'row', None)
            if row is not None:
                row['_lexical_query'], row['_lexical_rows'] = query, result
            return result
        self.patch(self.service.lexical, 'search', lexical_search)
        search = index.search
        def semantic_search(*args, **kwargs):
            result = search(*args, **kwargs)
            row = getattr(self.context, 'row', None)
            if row is not None:
                row['_semantic_rows'] = result
            return result
        self.patch(index, 'search', semantic_search)
        fusion = memory_recall.hybrid_fusion
        def fused(lexical, semantic):
            result = fusion(lexical, semantic)
            row = getattr(self.context, 'row', None)
            if row is not None:
                row['_fusion_inputs'], row['_fusion_rows'] = (lexical, semantic), result
            return result
        self.patch(memory_recall, 'hybrid_fusion', fused)
        adapter = self.service.semantic.embeddings
        request = adapter._request
        def observed_request(path, deadline, data=None):
            result = request(path, deadline, data)
            row = getattr(self.context, 'row', None)
            if row is not None and path == '/api/embed':
                vectors = result.get('embeddings', [])
                if len(vectors) == 1:
                    # Observed response is not necessarily admitted: post-check
                    # can still reject it. Never turn this hash into WARM.
                    row['_query_vector'] = tuple(vectors[0])
            return result
        self.patch(adapter, '_request', observed_request)
        return self

    def annotate(self, row, *, mapping=None, gold=None):
        """Diagnostics only, after measured recall and bounded worker teardown."""
        if self.state()['state'] != 'IDLE':
            raise RuntimeError('Ranking annotation requires completed teardown')
        inverse = {v: k for k, v in (mapping or {}).items()}
        def public_id(mid):
            return inverse.get(mid, mid)
        def ranked(values, scores, field):
            return [dict(id=public_id(r.memory_id), memoryId=r.memory_id, rank=r.rank,
                exact=r.exact, **{field: scores.get(r.memory_id)}) for r in values]
        lexical = row.get('_lexical_rows', ())
        bm25 = {}
        query = row.get('_lexical_query')
        if query is not None and lexical:
            # Same immutable synthetic corpus, same literal expression,
            # eligibility and BM25 formula. This READ is outside recall latency.
            words = re.findall(r'[^\W_]+', query.text, flags=re.UNICODE)
            expression = (' OR ' if query.match_any else ' AND ').join('"'+w+'"' for w in words)
            if expression:
                store = self.service.store
                clause, params = store._eligible(query)
                ids = [r.memory_id for r in lexical]
                with store._transaction():
                    values = store._connection.execute(
                        'SELECT m.memory_id,bm25(memory_fts) AS score FROM memory_fts '
                        'JOIN memories m ON m.rowid=memory_fts.rowid AND m.memory_id=memory_fts.memory_id '
                        'WHERE memory_fts MATCH ? AND '+clause+' AND m.memory_id IN ('+
                        ','.join('?' for _ in ids)+')', [expression, *params, *ids]).fetchall()
                bm25 = {r['memory_id']: r['score'] for r in values}
        cosines = dict(row.get('_cosines', ()))
        semantic = row.get('_semantic_rows', ())
        left, right = row.get('_fusion_inputs', ((), ()))
        totals = {}
        if right:
            for ranking in (left[:24], right[:24]):
                for item in ranking:
                    totals[item.memory_id] = totals.get(item.memory_id, 0) + 1/(60+item.rank)
        stages = dict(semantic=ranked(semantic, cosines, 'cosine'),
            lexical=ranked(lexical, bm25, 'bm25'),
            fusion=ranked(row.get('_fusion_rows', ()), totals, 'rrfTotal'))
        pre_floor = sorted(cosines.items(), key=lambda item: (-item[1], item[0]))
        stages['semanticEligiblePreFloor'] = [dict(id=public_id(mid), memoryId=mid,
            rank=i+1, cosine=value, meetsFloor=value >= self.service.semantic.index.minimum_similarity)
            for i, (mid, value) in enumerate(pre_floor)]
        vector = row.get('_query_vector')
        row['rankings'] = stages
        row['queryEmbedding'] = dict(dimension=len(vector) if vector is not None else None,
            hash=hashlib.sha256(struct.pack('<'+'d'*len(vector), *vector)).hexdigest()
                if vector is not None else None,
            encoding='IEEE754-f64-le-from-actual-response',
            responseObserved=vector is not None,
            admitted=row['metadata']['embeddingStatus'] == 'WARM')
        row['goldRanks'] = {stage: next((r['rank'] for r in values if r['id'] == gold), None)
            for stage, values in stages.items()} if gold is not None else None
        row['goldAnnotation'] = dict(gold=gold, outsideRecall=True, usedForRanking=False)
        row['bm25Observation'] = 'post-return read, same synthetic corpus; exact-only non-FTS score may be null'
        row['fusionObservation'] = 'actual original output order; totals derived from actual input ranks; no RRF in lexical-only fallback'
        row['workerFinal'] = self.state()
        self.proof_after_quiescence(row)
        return {k: v for k, v in row.items() if not k.startswith('_')}
