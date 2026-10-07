"""Local-only Ollama EmbeddingPort, independent of the conversation provider.

Only installed embedding-capable AND already resident models are used. No
pull/generate/chat/load/unload/keep_alive route, redirects, proxies or secrets.
Cold/missing/unknown capabilities degrade; another trusted host may warm the
model outside a Turn. Model digest+dimension define a new projection space.
"""
from concurrent.futures import Future, TimeoutError
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
from threading import Lock
from time import perf_counter as monotonic
from urllib.parse import urlsplit
import urllib.request

from local_cli.core.memory import EmbeddingSpace, MemoryError, MemoryErrorCode
from local_cli.infrastructure.memory_semantic import FORMAT


QWEN_MEMORY_QUERY_INSTRUCTION = (
    'Given a user request, retrieve the most relevant durable user or workspace '
    'memory needed to answer it.'
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)


@dataclass(frozen=True)
class _BackendMetadata:
    selection: tuple[str, str]
    space: EmbeddingSpace
    query_instruction: str | None
    embedding_capability: bool
    query_document_profile: str


class _AdmittedQuery:
    def __init__(self, adapter, metadata, deadline):
        self._adapter, self._metadata, self._deadline = adapter, metadata, deadline
        self._active, self._used = True, False

    @property
    def space(self): return self._metadata.space

    def embed_query(self, text):
        self._adapter._validate_query(text)
        if not self._active or self._used:
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        self._used = True
        return self._adapter._embed_verified([text], self._metadata, self._deadline, query=True)[0]


class LocalOllamaEmbeddings:
    def __init__(self, endpoint, model, *, timeout_ms=600, record_timeout_ms=30000, transport=None):
        try:
            parsed = urlsplit(endpoint)
            local = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
            if (not local or parsed.scheme not in ('http','https') or parsed.username or parsed.password or
                    parsed.path not in ('','/') or parsed.query or parsed.fragment or not model or
                    type(timeout_ms) is not int or not 1<=timeout_ms<=600 or
                    type(record_timeout_ms) is not int or not 1<=record_timeout_ms<=120000):
                raise ValueError()
            host = '127.0.0.1' if parsed.hostname == 'localhost' else parsed.hostname
            self.endpoint = f'{parsed.scheme}://'+('['+host+']' if ':' in host else host)+(
                ':'+str(parsed.port) if parsed.port else '')
        except (ValueError,TypeError):
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE) from None
        self.model, self.timeout_ms, self._space = model, timeout_ms, None
        self._query_instruction = None
        self._metadata = None
        self._metadata_lock, self._query_lock = Lock(), Lock()
        self._discovery = None
        self._cache_stats = dict(refreshes=0, reuses=0, coalesced=0, invalidations={})
        self.record_timeout_ms=record_timeout_ms  # Batch/idle only, NOT the Turn deadline.
        self._transport = transport
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _request(self, path, deadline, data=None):
        # A mutable host selection must never bypass constructor validation.
        self._selection()
        remaining = deadline-monotonic()
        if remaining<=0:
            raise MemoryError(MemoryErrorCode.RETRIEVAL_TIMEOUT)
        if self._transport is not None:
            result = self._transport(path, data, remaining)
        else:
            request=urllib.request.Request(self.endpoint+path,
                data=json.dumps(data).encode() if data is not None else None,
                headers={'Content-Type':'application/json'})
            try:
                with self._opener.open(request, timeout=remaining) as response:
                    raw=response.read(2*1024*1024+1)
                    if len(raw)>2*1024*1024:
                        raise ValueError()
                    result=json.loads(raw)
            except (OSError,ValueError):
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE) from None
        if monotonic()>deadline:
            raise MemoryError(MemoryErrorCode.RETRIEVAL_TIMEOUT)
        if not isinstance(result,dict):
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        return result

    def _selection(self):
        try:
            parsed=urlsplit(self.endpoint)
            local=parsed.hostname=='localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
            if (not local or parsed.scheme not in ('http','https') or parsed.username or parsed.password or
                    parsed.path not in ('','/') or parsed.query or parsed.fragment or
                    not isinstance(self.model,str) or not self.model.strip()):
                raise ValueError()
        except (ValueError,TypeError):
            self._invalidate('invalid_selection')
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE) from None
        return self.endpoint,self.model

    def _invalidate(self, reason):
        with self._metadata_lock:
            if self._metadata is not None:
                counts=self._cache_stats['invalidations']
                counts[reason]=counts.get(reason,0)+1
            self._metadata=self._space=self._query_instruction=None

    def metadata_cache_stats(self):
        """Bounded operational counters; no memory content or authority."""
        with self._metadata_lock:
            return dict(self._cache_stats,invalidations=dict(self._cache_stats['invalidations']))

    def _installed(self, deadline):
        rows=self._request('/api/tags',deadline).get('models',[])
        aliases={self.model,self.model+':latest'}
        found=[r for r in rows if isinstance(r,dict) and r.get('name') in aliases]
        if len(found)!=1 or not isinstance(found[0].get('digest'),str) or not found[0]['digest']:
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        return found[0]

    def _status(self, deadline):
        selection=self._selection()
        with self._metadata_lock:
            pending=self._discovery
            if pending is None:
                pending=Future(); self._discovery=pending; owner=True
            else:
                owner=False; self._cache_stats['coalesced']+=1
        if not owner:
            try:
                space=pending.result(timeout=max(0,deadline-monotonic()))
                with self._metadata_lock: metadata=self._metadata
                if metadata is None or metadata.selection!=selection or monotonic()>deadline:
                    raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
                return space
            except TimeoutError:
                raise MemoryError(MemoryErrorCode.RETRIEVAL_TIMEOUT) from None
        try:
            space=self._discover(deadline,selection)
            pending.set_result(space)
            return space
        except BaseException as exc:
            self._invalidate('discovery_failed')
            pending.set_exception(exc)
            raise
        finally:
            with self._metadata_lock:
                if self._discovery is pending: self._discovery=None

    def _discover(self, deadline, selection):
        tag=self._installed(deadline)
        ps=self._request('/api/ps',deadline).get('models',[])
        if not any(isinstance(r,dict) and r.get('digest')==tag['digest'] for r in ps):
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)  # No cold load on admission.
        with self._metadata_lock: metadata=self._metadata
        if metadata is not None and (metadata.selection!=selection or
                metadata.space.model_revision!=tag['digest'] or metadata.space.model_id!=tag['name']):
            self._invalidate('selection_or_revision_changed'); metadata=None
        if metadata is None:
            info=self._request('/api/show',deadline,{'model':tag['name']})
            if 'embedding' not in info.get('capabilities',[]):
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            dimensions={v for k,v in info.get('model_info',{}).items() if k.endswith('.embedding_length')
                and type(v) is int and 1<=v<=8192}
            if len(dimensions)!=1:
                raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
            dimension=dimensions.pop()
            # Verified Qwen3-Embedding uses asymmetric query/document inputs.
            # Do not infer this from a chat model name or apply it to other
            # embedding families. A preprocessing profile is part of space
            # identity, so pre-fix vectors/caches are never silently reused.
            basename = info.get('model_info',{}).get('general.basename')
            instruction = (QWEN_MEMORY_QUERY_INSTRUCTION if
                isinstance(basename,str) and basename.casefold()=='qwen3-embedding' else None)
            identity=['ollama',tag['name'],tag['digest'],dimension,'l2',FORMAT]
            if instruction is not None:
                identity.extend(['qwen-memory-query-document-v1',instruction])
            key=json.dumps(identity)
            space=EmbeddingSpace(embedding_space_id='ollama-'+hashlib.sha256(key.encode()).hexdigest(),
                provider_kind='ollama-local',model_id=tag['name'],model_revision=tag['digest'],dimension=dimension,
                normalization='l2',storage_format=FORMAT,created_at=datetime.now(timezone.utc))
            metadata=_BackendMetadata(selection,space,instruction,True,
                'qwen-memory-query-document-v1' if instruction is not None else 'plain-v1')
            with self._metadata_lock: self._cache_stats['refreshes']+=1
        else:
            with self._metadata_lock: self._cache_stats['reuses']+=1
        if self._selection()!=selection:
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
        with self._metadata_lock:
            self._metadata=metadata
            self._space,self._query_instruction=metadata.space,metadata.query_instruction
        return metadata.space

    def status(self):
        return self._status(monotonic()+self.timeout_ms/1000)

    @contextmanager
    def query_admission(self, expected_space_id):
        # Compatible metadata is content/revision-bound, NOT a residency TTL.
        # Cached path: fresh PS(expected digest), embed, fresh TAGS(alias proof).
        # Missing/changed selection still needs full discovery before admission.
        deadline=monotonic()+self.timeout_ms/1000
        if not self._query_lock.acquire(blocking=False):
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
        admitted=None
        try:
            selection=self._selection()
            with self._metadata_lock: metadata=self._metadata
            if metadata is not None and metadata.selection!=selection:
                self._invalidate('selection_or_revision_changed'); metadata=None
            if metadata is None:
                space=self._status(deadline)
                with self._metadata_lock: metadata=self._metadata
            else:
                space=metadata.space
                if space.embedding_space_id!=expected_space_id:
                    self._invalidate('expected_space_mismatch')
                    raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                ps=self._request('/api/ps',deadline).get('models',[])
                if not any(isinstance(r,dict) and r.get('digest')==space.model_revision for r in ps):
                    aliases={space.model_id,self.model,self.model+':latest'}
                    changed=any(isinstance(r,dict) and (r.get('name') in aliases or r.get('model') in aliases)
                        for r in ps)
                    raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH if changed else
                        MemoryErrorCode.EMBEDDING_UNAVAILABLE)
                if self._selection()!=selection:
                    raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                with self._metadata_lock:
                    if self._metadata is not metadata:
                        raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
                    self._cache_stats['reuses']+=1
            if space.embedding_space_id!=expected_space_id:
                self._invalidate('expected_space_mismatch')
                raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
            with self._metadata_lock: metadata=self._metadata
            if metadata is None or metadata.space!=space:
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            admitted=_AdmittedQuery(self,metadata,deadline)
            yield admitted
        except BaseException:
            self._invalidate('admission_validation_failed')
            raise
        finally:
            if admitted is not None: admitted._active=False
            self._query_lock.release()

    def _embed(self, texts, *, timeout_ms=None, query=False):
        deadline=monotonic()+(self.timeout_ms if timeout_ms is None else timeout_ms)/1000
        space=self._status(deadline)
        with self._metadata_lock: metadata=self._metadata
        if metadata is None or metadata.space!=space:
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
        return self._embed_verified(texts,metadata,deadline,query=query)

    def _embed_verified(self, texts, metadata, deadline, *, query=False):
        try:
            return self._embed_snapshot(texts,metadata,deadline,query=query)
        except BaseException:
            # Including detectable restart, missing model, transport failure,
            # revision/dimension mismatch: next admission must rediscover.
            self._invalidate('embedding_validation_failed')
            raise

    def _embed_snapshot(self, texts, metadata, deadline, *, query=False):
        if self._selection()!=metadata.selection:
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
        space=metadata.space
        if query and metadata.query_instruction is not None:
            texts=['Instruct: '+metadata.query_instruction+'\nQuery: '+text for text in texts]
        response=self._request('/api/embed',deadline,{'model':space.model_id,'input':texts,'truncate':False})
        # Detect ordinary alias/revision switches; never reinterpret the old space.
        if (self._installed(deadline)['digest']!=space.model_revision or
                self._selection()!=metadata.selection):
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
        rows=response.get('embeddings',[])
        if len(rows)!=len(texts):
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
        result=[]
        for row in rows:
            if (not isinstance(row,list) or len(row)!=space.dimension or
                    any(type(v) not in (int,float) or not math.isfinite(v) for v in row)):
                raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
            result.append(tuple(float(v) for v in row))
        return tuple(result)

    @staticmethod
    def _validate_query(text):
        if not isinstance(text,str) or not text.strip() or len(text)>4096:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)

    def embed_query(self, text):
        self._validate_query(text)
        return self._embed([text],query=True)[0]

    def embed_records(self, batch):
        if not isinstance(batch,tuple) or not 1<=len(batch)<=32:
            raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
        return self._embed([r.canonical_text for r in batch],timeout_ms=self.record_timeout_ms)
