"""Optional local derived indexes, with one cancellable worker per project.

Network inference runs outside SQLite and the session lock. Source ownership,
revision identity and embedding spaces remain authoritative at publication.
"""
from threading import RLock, Thread
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode


class KnowledgeIndexing:
    def __init__(self, service, preferences, settings, endpoint, notify=lambda service: None, adapter_factory=None):
        self.service, self.preferences, self.settings = service, preferences, settings
        self.endpoint, self.notify, self.adapter_factory = endpoint, notify, adapter_factory
        self._lock = RLock()
        self._key = None
        self._epoch = 0
        self._closed = self._running = self._dirty = False
        self._error = None
        self._completed = self._total = 0

    def _selection(self):
        value = self.settings.snapshot() if self.settings else {}
        return value if value.get('connected') and value.get('selectedModel') and not value.get('errorCode') else {}

    def snapshot(self):
        with self._lock:
            return dict(indexing=self._running, indexedSources=self._completed, totalSources=self._total, errorCode=self._error)

    def _changed(self):
        try: self.notify(self.service)
        except Exception: pass

    def refresh(self, *, schedule=True):
        value, selected = self.preferences.snapshot(), self._selection()
        key = (tuple(value.items()), selected.get('selectedModel'), selected.get('selectedTokens'))
        with self._lock:
            if self._closed: return
            if key != self._key:
                self._key = key; self._epoch += 1; self._error = None
                old = self.service.retriever
                self.service.retriever = DocumentRetriever(self.service.store, lexical_enabled=value['lexicalRecall'], semantic_budget_limit=30)
                old.close()
            if not schedule or not selected or not any(value[k] for k in ('semanticRecall', 'autoIndex', 'autoRebuild')): return
            self._dirty = True
            if self._running: return
            self._running = True
            Thread(target=self._run, name='nova-knowledge-index', daemon=True).start()
        self._changed()

    def _current(self, epoch):
        return not self._closed and self._epoch == epoch

    def _run(self):
        while True:
            with self._lock:
                if self._closed:
                    self._running = False; return
                self._dirty = False
                epoch, key = self._epoch, self._key
            try:
                value, selected = self.preferences.snapshot(), self._selection()
                if selected:
                    self._prepare(epoch, key, value, selected)
            except Exception as exc:
                with self._lock:
                    if self._current(epoch):
                        self._error = exc.code if isinstance(exc, KnowledgeError) else 'KNOWLEDGE_INDEX_FAILED'
            with self._lock:
                again = self._dirty and not self._closed
                if not again: self._running = False
            self._changed()
            if not again: return

    def _prepare(self, epoch, key, value, selected):
        from local_cli.infrastructure.knowledge_embeddings import LocalDocumentEmbeddings
        store, access = self.service.store, self.service.access
        inventory = store.document_index_inventory(access)
        with self._lock:
            if not self._current(epoch): return
            self._total, self._completed, self._error = len(inventory), 0, None
        if not inventory: return
        model = selected['selectedModel']
        profile = 'qwen-document-query-v1' if 'qwen' in model.casefold() else 'document-raw-v1'
        factory = self.adapter_factory or LocalDocumentEmbeddings
        backend = factory(self.endpoint, model, preprocessing_profile=profile, settings=self.settings, allow_cold=True)
        space = backend.discover()
        inventory = store.document_index_inventory(access, space.space_id)
        with self._lock:
            if not self._current(epoch): return
            retriever = self.service.retriever
            retriever.backend, retriever.space = backend, space
            retriever.semantic_enabled = value['semanticRecall']
            self._completed = sum(row['indexed'] == row['chunks'] for row in inventory)
        for row in inventory:
            with self._lock:
                if not self._current(epoch): return
            if row['indexed'] == row['chunks']: continue
            # Existing projections require the independent rebuild consent.
            if not value['autoRebuild' if row['prior'] else 'autoIndex']: continue
            try:
                prepared = store.read_prepared(row['revision_id'], access)
                vectors = {}
                for offset in range(0, len(prepared.chunks), 16):
                    with self._lock:
                        if not self._current(epoch): return
                    batch = prepared.chunks[offset:offset+16]
                    values = backend.embed_documents(tuple(chunk.text for chunk in batch), space)
                    if len(values) != len(batch): raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                    vectors.update({chunk.chunk_id: vector for chunk, vector in zip(batch, values)})
                with self._lock:
                    if not self._current(epoch): return
                    store.put_document_vectors(row['revision_id'], space, vectors, access)
                    self._completed += 1
            except Exception as exc:
                with self._lock:
                    if self._current(epoch):
                        self._error = exc.code if isinstance(exc, KnowledgeError) else 'KNOWLEDGE_INDEX_FAILED'
                if isinstance(exc, KnowledgeError) and exc.code in ('SEMANTIC_SPACE_MISMATCH', 'SEMANTIC_UNAVAILABLE'):
                    break
            self._changed()

    def close(self):
        with self._lock:
            self._closed = True; self._dirty = False; self._epoch += 1
