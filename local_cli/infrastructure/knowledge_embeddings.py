"""Optional local Ollama document adapter, independent of MEMORY spaces.

Discovery is explicit host idle work. The default adapter never loads a cold
model; enabled desktop Knowledge may explicitly allow local cold inference.
No path downloads a model. PS + post-revision proof bind vectors to the
expected space. No ambient proxy/cookies/auth/redirects or cloud endpoint.
"""
import hashlib
import ipaddress
import json
from time import perf_counter
from urllib.parse import urlsplit
import urllib.request
import urllib.error

from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode, _require
from local_cli.core.knowledge_chunking import CHUNK_PROFILE
from local_cli.core.knowledge_retrieval import DocumentEmbeddingSpace, vector


DOCUMENT_QUERY_INSTRUCTION = 'Given a user request, retrieve the most relevant document passage needed to answer it.'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args): raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)


class LocalDocumentEmbeddings:
    def __init__(self, endpoint, model, *, preprocessing_profile='document-raw-v1', transport=None, settings=None, allow_cold=False):
        try:
            parsed = urlsplit(endpoint)
            local = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
            if (not local or parsed.scheme not in ('http', 'https') or parsed.username or parsed.password
                    or parsed.path not in ('', '/') or parsed.query or parsed.fragment): raise ValueError()
            _require(isinstance(model, str) and bool(model.strip()))
            _require(preprocessing_profile in ('document-raw-v1', 'qwen-document-query-v1'))
        except (ValueError, TypeError):
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE) from None
        self._selection = endpoint.rstrip('/'), model, preprocessing_profile
        self._transport, self._space = transport, None
        self.settings, self.allow_cold = settings, allow_cold
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    @property
    def space(self):
        if self._space is None: raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
        return self._space

    def _request(self, path, data, deadline):
        remaining = deadline-perf_counter()
        if remaining <= 0: raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
        try:
            if self._transport is not None: result = self._transport(path, data, remaining)
            else:
                request = urllib.request.Request(self._selection[0]+path,
                    data=json.dumps(data).encode() if data is not None else None,
                    headers={'Content-Type': 'application/json'})
                with self._opener.open(request, timeout=remaining) as response:
                    raw = response.read(8*1024*1024+1)
                    if len(raw) > 8*1024*1024: raise ValueError()
                    result = json.loads(raw)
            if not isinstance(result, dict) or perf_counter() >= deadline: raise ValueError()
            return result
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode('utf-8', errors='replace').casefold()
            if any(term in detail for term in ('context length', 'input length', 'too long', 'context window')):
                raise KnowledgeError(KnowledgeErrorCode.EMBEDDING_CONTEXT_EXCEEDED) from None
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE) from None
        except (OSError, ValueError, TypeError):
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE) from None

    def _model(self, path, deadline):
        aliases = {self._selection[1], self._selection[1]+':latest'}
        rows = [r for r in self._request(path, None, deadline).get('models', [])
                if isinstance(r, dict) and r.get('name', r.get('model')) in aliases]
        if len(rows) != 1 or not rows[0].get('digest'):
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
        return rows[0]

    def discover(self):
        """No inference. Explicit local capability metadata; not certification."""
        deadline = perf_counter()+2
        try:
            installed = self._model('/api/tags', deadline)
            shown = self._request('/api/show', {'model': self._selection[1]}, deadline)
            info = shown.get('model_info', {})
            dimensions = {v for k,v in info.items() if k.endswith('.embedding_length') and type(v) is int}
            if 'embedding' not in shown.get('capabilities', ()) or len(dimensions) != 1:
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
            family = str(shown.get('details', {}).get('family', '')).casefold()
            qwen = 'qwen' in family or 'qwen' in self._selection[1].casefold()
            if self.settings is not None:
                self._selection = (*self._selection[:2], 'qwen-document-query-v1' if qwen else 'document-raw-v1')
            if qwen != (self._selection[2] == 'qwen-document-query-v1'):
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            if self._model('/api/tags', deadline)['digest'] != installed['digest']:
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            context = self.settings.snapshot().get('selectedTokens') if self.settings else None
            identity = self._selection[0] + ('|context:'+str(context) if self.settings else '')
            self._context = context
            self._space = DocumentEmbeddingSpace('ollama-local:'+hashlib.sha256(identity.encode()).hexdigest(),
                self._selection[1], installed['digest'], dimensions.pop(), self._selection[2], CHUNK_PROFILE)
            return self._space
        except Exception:
            self._space = None
            raise

    def _embed(self, texts, expected, *, query):
        if self.space != expected: raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
        _require(isinstance(texts, tuple) and 0 < len(texts) <= 16 and all(isinstance(t, str) and '\x00' not in t for t in texts))
        deadline = perf_counter()+(30 if query and self.allow_cold else .5 if query else 60 if self.allow_cold else 10)
        try:
            # Fresh residency/revision check: a cold model is never loaded here.
            if not self.allow_cold and self._model('/api/ps', deadline)['digest'] != expected.revision:
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            inputs = texts
            if query and expected.preprocessing_profile == 'qwen-document-query-v1':
                inputs = tuple('Instruct: '+DOCUMENT_QUERY_INSTRUCTION+'\nQuery: '+t for t in texts)
            options = {}
            if self.settings is not None:
                state = self.settings.snapshot()
                if state['selectedModel'] != expected.model or state['selectedTokens'] != self._context or state['errorCode']:
                    raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                options = {'options': self.settings.runtime_options(expected.model)}
            ledger = getattr(self.settings, 'usage', None)
            request_id = ledger.begin(expected.model) if ledger else None
            try:
                response = self._request('/api/embed', {'model': expected.model, 'input': list(inputs), 'truncate': False, **options}, deadline)
            except BaseException:
                if ledger: ledger.finish(request_id, {}, 'failed')
                raise
            else:
                if ledger: ledger.finish(request_id, {**response, 'eval_count':0}, 'completed')
            if self._model('/api/tags', deadline)['digest'] != expected.revision:
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            values = response.get('embeddings', ())
            if len(values) != len(texts): raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            return tuple(vector(v, expected) for v in values)
        except Exception:
            self._space = None  # Explicit rediscovery required; no stale reuse.
            raise

    def embed_query(self, text, expected_space): return self._embed((text,), expected_space, query=True)[0]
    def embed_documents(self, texts, expected_space): return self._embed(texts, expected_space, query=False)
