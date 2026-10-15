"""M5 derived projection maintenance and bounded semantic admission.

No extraction/consolidation/write policy, chat-model reranker or new AgentLoop.
One daemon worker at most per service: an unresponsive port cannot force
unbounded worker growth or block a Turn. Timed-out results are never admitted.
"""
from concurrent.futures import Future, TimeoutError
from threading import Lock, Thread, Event
from time import perf_counter

from local_cli.core.memory import EmbeddingAdmissionPort, MemoryError, MemoryErrorCode, MemoryQuery


# Fixed BEFORE operational measurement: reserve the approved lexical p95
# budget for bounded hydration/render/fallback and caller scheduling. This
# is not an OS wall-clock guarantee or a configurable/public deadline change.
FALLBACK_RESERVE_MS = 50


class SemanticAdmission:
    def __init__(self, embeddings, index_factory, *, soft_ms=350, hard_ms=600):
        if not 0<soft_ms<=hard_ms<=600:
            raise ValueError('Invalid recall deadline')
        self.embeddings, self.index_factory = embeddings, index_factory
        self.soft_ms, self.hard_ms = soft_ms, hard_ms
        # Preserve a useful soft/hard interval for smaller contract-test budgets.
        self.fallback_reserve_ms=min(FALLBACK_RESERVE_MS,hard_ms*.1,(hard_ms-soft_ms)/2)
        self.index, self._pending, self._lock = None, None, Lock()

    @property
    def available(self):
        return bool(self.index and self.index.ready())

    def query(self, query, *, started):
        cutoff=started+(self.hard_ms-self.fallback_reserve_ms)/1000
        budget=cutoff-perf_counter()
        if budget<=0:
            return (), 'DEGRADED_TIMEOUT', MemoryErrorCode.RETRIEVAL_TIMEOUT.value
        if not self._lock.acquire(blocking=False):
            return (), 'DEGRADED_BUSY', MemoryErrorCode.EMBEDDING_UNAVAILABLE.value
        try:
            if self._pending is not None and not self._pending.done():
                return (), 'DEGRADED_BUSY', MemoryErrorCode.EMBEDDING_UNAVAILABLE.value
            future=Future(); self._pending=future
        finally:
            self._lock.release()
        readiness=Event();abandoned=Event()
        def complete(space,embed_query):
            if space is None or self.index is None:
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            if space.embedding_space_id!=self.index.capabilities().embedding_space_id:
                raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
            readiness.set()  # Verified warm; SOFT/HARD semantics are unchanged.
            if abandoned.is_set() or perf_counter()>=cutoff or not self.index.has_candidates(query):
                future.set_result(())
                return
            vector=embed_query(query.text)
            if abandoned.is_set() or perf_counter()>=cutoff:
                future.set_result(())
                return
            rows=self.index.search(vector,query,space.embedding_space_id)
            future.set_result(rows)
        def run():
            try:
                if isinstance(self.embeddings,EmbeddingAdmissionPort) and self.index is not None:
                    expected=self.index.capabilities().embedding_space_id
                    with self.embeddings.query_admission(expected) as admitted:
                        complete(admitted.space,admitted.embed_query)
                else:
                    complete(self.embeddings.status(),self.embeddings.embed_query)
            except BaseException as exc:
                future.set_exception(exc)
                readiness.set()
        Thread(target=run,name='nova-memory-semantic',daemon=True).start()
        try:
            if not readiness.wait(timeout=min(self.soft_ms/1000,budget)):
                raise TimeoutError()
            remaining=cutoff-perf_counter()
            if remaining<=0: raise TimeoutError()
            rows=future.result(timeout=remaining)
            if perf_counter()>=cutoff: raise TimeoutError()
            return rows, 'WARM', None
        except TimeoutError:
            abandoned.set()
            return (), 'DEGRADED_TIMEOUT', MemoryErrorCode.RETRIEVAL_TIMEOUT.value
        except MemoryError as exc:
            return (), 'DEGRADED', exc.code
        except Exception:
            return (), 'DEGRADED', MemoryErrorCode.EMBEDDING_UNAVAILABLE.value

    def prepare(self):
        """Restore persisted projections asynchronously; no record embeddings."""
        with self._lock:
            future=Future(); self._pending=future
        def run():
            try:
                space=self.embeddings.status()
                if space is None: raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
                self.index=self.index_factory(space)
                self.index.rebuild(space.embedding_space_id)
                future.set_result(None)
            except BaseException as exc:
                future.set_exception(exc)
        Thread(target=run,name='nova-memory-projection-restore',daemon=True).start()

    def project_record(self, record, *, redactor):
        """Derived work after an explicit durable write, not another write policy."""
        with self._lock:
            if self._pending is not None and not self._pending.done():
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            space=self.embeddings.status()
            if space is None: raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            if self.index is None or self.index.capabilities().embedding_space_id!=space.embedding_space_id:
                self.index=self.index_factory(space)
            if redactor.text(record.canonical_text)!=record.canonical_text:
                raise MemoryError(MemoryErrorCode.SECRET_DENIED)
            # Sensitive records are not sent to an embedding service by default.
            if record.sensitivity_class.value!='NORMAL' or record.status.value!='ACTIVE':
                return
            if not self.index.has_revision(record.memory_id,record.revision):
                vectors=self.embeddings.embed_records((record,))
                if len(vectors)!=1: raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                self.index.upsert(record.memory_id,vectors[0],space.embedding_space_id,
                    expected_revision=record.revision)
            self.index.rebuild(space.embedding_space_id)

    def invalidate(self, memory_id):
        if self.index is not None:
            self.index.remove(memory_id)
            self.index.rebuild(self.index.capabilities().embedding_space_id)

    def maintain(self, store, scope, *, at, redactor, batch_size=32):
        """Trusted idle/explicit-write maintenance. Never invoked by query().

        Reuses compatible revision vectors; missing ones embedded in bounded
        batches. CAS rejects records corrected/deleted while embedding. A new
        model space preserves old vectors, never mixes or migrates them in-place.
        """
        if type(batch_size) is not int or not 1<=batch_size<=32:
            raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
        with self._lock:
            if self._pending is not None and not self._pending.done():
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            # Holding this lock excludes a Turn query throughout maintenance.
            space=self.embeddings.status()
            if space is None:
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            if self.index is None or self.index.capabilities().embedding_space_id!=space.embedding_space_id:
                self.index=self.index_factory(space)
            # Respect the local adapter's bounded JSON response, including
            # high-dimensional models such as the selected 4096-D backend.
            effective_batch=min(batch_size,max(1,(2*1024*1024-4096)//(space.dimension*32)))
            cursor=None; calls=0
            while True:
                page=store.list(scope,limit=effective_batch,cursor=cursor)
                missing=[]
                for record in page.records:
                    if record.eligible(scope,at=at) and not self.index.has_revision(record.memory_id,record.revision):
                        if redactor.text(record.canonical_text)!=record.canonical_text:
                            raise MemoryError(MemoryErrorCode.SECRET_DENIED)
                        missing.append(record)
                if missing:
                    vectors=self.embeddings.embed_records(tuple(missing)); calls+=1
                    if len(vectors)!=len(missing):
                        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                    for record,vector in zip(missing,vectors):
                        self.index.upsert(record.memory_id,vector,space.embedding_space_id,
                            expected_revision=record.revision)
                cursor=page.next_cursor
                if cursor is None: break
            self.index.rebuild(space.embedding_space_id)
            return dict(embeddingBatches=calls,spaceId=space.embedding_space_id,status='WARM')
