"""K4 exact/lexical coordinator and optional deterministic document hybrid.

One bounded optional worker; timeout results are immutable and no late vector
may enter the returned snapshot. No inference is scheduled by default, no
context admission, citations, MEMORY or second AgentLoop.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import replace
from threading import Lock
from time import perf_counter

from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode, _require
from local_cli.core.knowledge_retrieval import (DocumentEmbeddingPort, DocumentEmbeddingSpace,
    DocumentRetrievalFilter, DocumentRetrievalPort, DocumentRetrievalResult,
    FINAL_CAP, MERGED_CAP, RRF_K, vector)


def fuse(lexical, semantic):
    scores, records = {}, {}
    for ranking in (lexical, semantic):
        seen = set()
        for rank, candidate in enumerate(ranking, 1):
            key = candidate.key
            if key in seen: continue
            seen.add(key)
            scores[key] = scores.get(key, 0) + 1/(RRF_K+rank)
            old = records.get(key)
            if old is None or candidate.exact: records[key] = candidate
    keys = sorted(records, key=lambda k: (not records[k].exact, -scores[k],
        records[k].revision_id, records[k].chunk.ordinal, records[k].chunk.chunk_id))[:MERGED_CAP]
    return tuple(replace(records[key], score=scores[key]) for key in keys)


class DocumentRetriever:
    def __init__(self, store: DocumentRetrievalPort, *, backend=None, space=None, semantic_enabled=False):
        _require(isinstance(store, DocumentRetrievalPort) and type(semantic_enabled) is bool)
        if backend is not None:
            _require(isinstance(backend, DocumentEmbeddingPort) and isinstance(space, DocumentEmbeddingSpace))
        self.store, self.backend, self.space = store, backend, space
        self.semantic_enabled = semantic_enabled
        self._busy = Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='nova-document-semantic')

    def close(self): self._worker.shutdown(wait=False, cancel_futures=True)

    @property
    def busy(self): return self._busy.locked()

    def retrieve(self, query, access, filters=DocumentRetrievalFilter(), *, semantic_budget=.5):
        _require(type(semantic_budget) in (int,float) and 0 <= semantic_budget <= .5)
        lexical = self.store.lexical_candidates(query, access, filters)
        state, error, semantic, space_id = 'DISABLED', None, (), None
        if self.semantic_enabled:
            state = 'UNAVAILABLE' if self.backend is None else 'NOT_CERTIFIED'
            if self.backend is None: error = KnowledgeErrorCode.SEMANTIC_UNAVAILABLE.value
            elif not self._busy.acquire(blocking=False):
                state, error = 'DEGRADED', 'DOCUMENT_SEMANTIC_BUSY'
            else:
                expected = self.space
                deadline = perf_counter()+semantic_budget
                def work():
                    if self.backend.space != expected:
                        raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                    value = vector(self.backend.embed_query(query, expected), expected)
                    if self.backend.space != expected:
                        raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                    if perf_counter() >= deadline: raise TimeoutError()
                    return self.store.semantic_candidates(value, expected, access, filters)
                try:
                    pending = self._worker.submit(work)
                    pending.add_done_callback(lambda unused: self._busy.release())
                    semantic = pending.result(timeout=max(0, deadline-perf_counter()))
                    if perf_counter() >= deadline: raise TimeoutError()
                    space_id = expected.space_id
                except TimeoutError:
                    state, error = 'DEGRADED', 'DOCUMENT_SEMANTIC_TIMEOUT'
                    semantic = ()
                except Exception as exc:
                    state = 'DEGRADED'
                    error = exc.code if isinstance(exc, KnowledgeError) else KnowledgeErrorCode.SEMANTIC_UNAVAILABLE.value
                    semantic = ()
                    if 'pending' not in locals(): self._busy.release()
        candidates = fuse(lexical, semantic) if semantic else fuse(lexical, ())
        candidates = self.store.validate_candidates(candidates, access, filters)[:FINAL_CAP]
        mode = 'hybrid' if semantic else 'lexical'
        return DocumentRetrievalResult(candidates, mode if candidates else 'NONE', state, error, space_id,
            rank_profile='ki-document-rank-v1/lexical-signals-v4')

    def project_revision(self, revision_id, access):
        """Explicit host idle rebuild. No automatic projection during retrieval."""
        if not self.semantic_enabled or self.backend is None:
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
        if not self._busy.acquire(blocking=False):
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
        try:
            prepared = self.store.read_prepared(revision_id, access)
            expected = self.space
            if self.backend.space != expected or any(c.chunking_profile != expected.chunking_profile for c in prepared.chunks):
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            values = {}
            for offset in range(0, len(prepared.chunks), 16):
                batch = prepared.chunks[offset:offset+16]
                embedded = self.backend.embed_documents(tuple(c.text for c in batch), expected)
                if len(embedded) != len(batch) or self.backend.space != expected:
                    raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                values.update({c.chunk_id: vector(v, expected) for c,v in zip(batch, embedded)})
            self.store.put_document_vectors(revision_id, expected, values, access)
        finally: self._busy.release()
