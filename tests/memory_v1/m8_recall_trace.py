"""Test-only forwarding instrumentation. No gold, scoring or product changes.

Each real worker keeps its originating recall ID even after admission returns.
The thread observer also distinguishes Future completion from thread cleanup.
All timings use the same monotonic clock as the unchanged production pipeline.
"""
from contextlib import contextmanager
from copy import deepcopy
from threading import local, current_thread
from time import perf_counter

from local_cli.application import memory_recall, memory_semantic


class RecallTrace:
    def __init__(self, service):
        self.service = service
        self.context = local()
        self.rows = []
        self.threads = []
        self.undo = []

    def state(self):
        semantic = self.service.semantic
        pending = semantic._pending
        running = sum(t.is_alive() for t in self.threads)
        return dict(state='IDLE' if (pending is None or pending.done()) and not running else 'BUSY',
            pending=pending is not None and not pending.done(), liveWorkerThreads=running)

    @contextmanager
    def span(self, stage, **extra):
        row = getattr(self.context, 'row', None)
        if row is None:
            yield None
            return
        start = perf_counter()
        entry = dict(stage=stage, startMs=(start-row['_start'])*1000,
            thread=current_thread().name, errorCode=None, **extra)
        row['spans'].append(entry)
        try:
            yield entry
        except BaseException as exc:
            entry['errorCode'] = str(getattr(exc, 'code', type(exc).__name__))
            raise
        finally:
            entry.update(endMs=(perf_counter()-row['_start'])*1000,
                elapsedMs=(perf_counter()-start)*1000)

    def patch(self, obj, name, fn):
        original = getattr(obj, name)
        self.undo.append((obj, name, original))
        setattr(obj, name, fn)

    def forward(self, obj, name, stage):
        original = getattr(obj, name)
        def observed(*args, **kwargs):
            with self.span(stage):
                return original(*args, **kwargs)
        self.patch(obj, name, observed)

    def __enter__(self):
        original_thread = memory_semantic.Thread
        def worker_thread(*args, **kwargs):
            row = getattr(self.context, 'row', None)
            target = kwargs['target']
            def observed_target():
                self.context.row = row
                try:
                    with self.span('worker_total'):
                        return target()
                finally:
                    self.context.row = None
            kwargs['target'] = observed_target
            thread = original_thread(*args, **kwargs)
            self.threads.append(thread)
            return thread
        self.patch(memory_semantic, 'Thread', worker_thread)
        self.forward(self.service.identity, 'resolve_workspace', 'scope_preparation')
        if self.service.maintenance:
            self.forward(self.service.maintenance, 'suppressed_memory_ids', 'suppression_preparation')
        self.forward(self.service.lexical, 'search', 'lexical_search')
        self.forward(self.service.store, 'get', 'hydration_get')
        self.forward(self.service.semantic.index, 'has_candidates', 'semantic_candidate_check')
        self.forward(self.service.semantic.index, 'search', 'semantic_search')
        self.forward(memory_recall, 'hybrid_fusion', 'fusion')
        original_render = memory_recall.MemoryCapsule.render
        def render(*args, **kwargs):
            with self.span('capsule_render'):
                return original_render(*args, **kwargs)
        self.patch(memory_recall.MemoryCapsule, 'render', staticmethod(render))
        original_query = self.service.semantic.query
        def query(*args, **kwargs):
            row = getattr(self.context, 'row', None)
            if row is not None:
                row['productionRecallStartDeltaMs'] = (kwargs['started']-row['_start'])*1000
                row['_production_start'] = kwargs['started']
                row['lexicalPreparationMs'] = (perf_counter()-kwargs['started'])*1000
            with self.span('semantic_admission'):
                return original_query(*args, **kwargs)
        self.patch(self.service.semantic, 'query', query)
        adapter = self.service.semantic.embeddings
        original_request = adapter._request
        def request(path, deadline, data=None):
            row = getattr(self.context, 'row', None)
            start = perf_counter()
            extra = dict(path=path, adapterBudgetRemainingMs=(deadline-start)*1000)
            if path == '/api/embed' and row is not None:
                production_start = row['_production_start']
                extra.update(input=list(data['input']),
                    recallHardBudgetRemainingMs=(production_start+.600-start)*1000,
                    admissionBudgetRemainingMs=(production_start+.550-start)*1000)
                row['embedEntered'] = True
            stage = {'/api/ps': 'http_ps', '/api/embed': 'http_embed',
                '/api/tags': 'http_post_tags' if row and row.get('embedEntered') else 'http_discovery_tags',
                '/api/show': 'http_show'}.get(path, 'http_other')
            with self.span(stage, **extra) as entry:
                result = original_request(path, deadline, data)
                if entry is not None and path == '/api/embed':
                    entry.update(ollamaTotalDurationNs=result.get('total_duration'),
                        ollamaLoadDurationNs=result.get('load_duration'),
                        promptEvalCount=result.get('prompt_eval_count'),
                        dimensions=[len(v) for v in result.get('embeddings', [])])
                return result
        self.patch(adapter, '_request', request)
        return self

    def __exit__(self, *args):
        for obj, name, original in reversed(self.undo):
            # Preserve the original staticmethod descriptor on the class.
            setattr(obj, name, staticmethod(original) if obj is memory_recall.MemoryCapsule else original)

    def recall(self, case, text, workspace, at):
        before = self.state()  # Observation is outside measured recall latency.
        row = dict(case=case, query=text, workerBefore=before, spans=[])
        row['_start'] = perf_counter()
        self.rows.append(row)
        self.context.row = row
        retriever = memory_recall.MemoryRetriever(self.service)
        self.forward(retriever.composer, 'compose', 'query_composer')
        try:
            snapshot = retriever.retrieve(text, workspace=workspace, at=at)
            row['totalReturnMs'] = (perf_counter()-row['_start'])*1000
            row['metadata'] = snapshot.metadata()
            row['workerAtReturn'] = self.state()
            row['_snapshot'] = snapshot
            row['_snapshot_proof'] = deepcopy((snapshot.metadata(), snapshot.capsule,
                tuple(r.memory_id for r in snapshot.records)))
            return snapshot, row
        finally:
            self.context.row = None

    def proof_after_quiescence(self, row):
        snapshot = row['_snapshot']
        unchanged = row['_snapshot_proof'] == (snapshot.metadata(), snapshot.capsule,
            tuple(r.memory_id for r in snapshot.records))
        row['snapshotUnchangedAfterQuiescence'] = unchanged
        row['lateResultUsed'] = False
        if not unchanged:
            raise RuntimeError('A returned snapshot changed after worker completion')

    def exported_rows(self):
        return [{k: v for k, v in r.items() if not k.startswith('_')} for r in self.rows]
