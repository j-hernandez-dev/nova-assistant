"""Keep RAGEngine algorithms; each call owns its SQLite connection/thread."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from local_cli.core.rag import RAGError
from local_cli.rag import RAGEngine


class LegacyProjectRetrieval:
    def __init__(self, *, client: Any, workspace: Path, path: str = ".",
                 embedding_model: str = "all-minilm", db_path: str | None = None,
                 engine_factory: Callable = RAGEngine, excluded_paths=()):
        if not Path(workspace).is_absolute():
            raise ValueError("retrieval requires an explicit absolute workspace")
        self.workspace = Path(workspace).resolve()
        self.path, self.embedding_model, self.db_path = path, embedding_model, db_path
        self._client, self._engine_factory = client, engine_factory
        self._excluded_paths = tuple(excluded_paths)
        self._lock = RLock()

    @contextmanager
    def _engine(self):
        failures = []
        def failed(_exc):
            failures.append(True)
        # Creation/use/close occur in this caller's thread, including workers.
        with self._lock:
            engine = self._engine_factory(client=self._client, cwd=self.workspace,
                db_path=self.db_path, embedding_model=self.embedding_model,
                on_embedding_error=failed, excluded_paths=self._excluded_paths)
            try:
                yield engine
                if failures:
                    raise RAGError("RAG_EMBEDDING_UNAVAILABLE",
                                   "Project embeddings are unavailable")
            finally:
                engine.close()

    def index(self) -> dict[str, int]:
        if not (self.workspace / self.path).resolve().is_dir():
            raise RAGError("RAG_INVALID_PATH", "RAG path must be an existing directory")
        with self._engine() as engine:
            # An empty directory must not claim an unavailable model works.
            vectors = self._client.embed(self.embedding_model, "RAG availability")
            if not vectors or not vectors[0]:
                raise RAGError("RAG_EMBEDDING_UNAVAILABLE", "Project embeddings are unavailable")
            return engine.index_directory(self.path)

    def query(self, text: str, top_k: int) -> list[dict[str, Any]]:
        with self._engine() as engine:
            return engine.query(text, top_k=top_k)


class ExistingEngineRetrieval:
    """Temporary run_repl(rag_engine=...) bridge; new production uses the port."""

    def __init__(self, engine: Any, *, excluded_paths=()):
        self._engine = engine
        self._owned_connections = (LegacyProjectRetrieval(client=engine.client,
            workspace=engine.cwd, embedding_model=engine.embedding_model,
            db_path=engine.db_path, excluded_paths=tuple(engine.excluded_paths) + tuple(excluded_paths))
            if isinstance(engine, RAGEngine) else None)

    def index(self) -> dict[str, int]:
        # The legacy caller already indexed; do not reindex or transfer SQLite.
        return {}

    def query(self, text: str, top_k: int) -> list[dict[str, Any]]:
        # A raw legacy engine's existing connection stays owned by its caller.
        # Reopen its index locally instead of passing that connection to workers.
        return (self._owned_connections.query(text, top_k) if self._owned_connections is not None
                else self._engine.query(text, top_k=top_k))
