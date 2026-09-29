"""Same RAGService contract, real SQLite and optional embeddings/client failures."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from local_cli.application.rag import RAGService, create_rag_service
from local_cli.core.rag import RAGError
from local_cli.infrastructure.rag import LegacyProjectRetrieval
from local_cli.rag import RAGEngine


def embeddings():
    return Mock(embed=Mock(side_effect=lambda _model, texts:
        [[1., 0.]] * (len(texts) if isinstance(texts, list) else 1)))


def test_available_query_progress_disable_and_same_index_schema(tmp_path):
    (tmp_path / "source.txt").write_text("a project fact", encoding="utf-8")
    progress = []
    client = embeddings()
    service = create_rag_service(client=client, workspace=tmp_path, top_k=1)
    assert service.status()["availability"] == "DISABLED"
    assert not (tmp_path / "rag_index.db").exists()
    result = service.set_enabled(True, progress=progress.append)
    assert result.stats["chunks_indexed"] == 1
    assert [p["phase"] for p in progress] == ["started", "completed"]
    assert {p["operationId"] for p in progress} == {result.operation_id}
    response = service.query("question")
    assert response.state.value == "AVAILABLE" and len(response.matches) == 1
    assert response.context_message()["_context_kind"] == "retrieval"
    assert "User question:" not in response.context_message()["content"]
    legacy = RAGEngine(client, cwd=tmp_path)
    try:
        assert legacy.query("question", 1) == list(response.matches)
    finally:
        legacy.close()
    service.set_enabled(False)
    client.embed.reset_mock()
    assert service.query("question").context_message() is None
    client.embed.assert_not_called()


def test_missing_backend_reports_typed_nonfatal_error_and_disable_recovers():
    service = RAGService(None)
    progress = []
    result = service.set_enabled(True, progress=progress.append)
    assert result.error.code == "RAG_UNAVAILABLE" and result.enabled
    assert progress[-1]["phase"] == "failed"
    assert service.query("question").context_message() is None
    service.set_enabled(False)
    assert service.status()["error"] is None


def test_empty_index_does_not_claim_missing_embedding_model_is_available(tmp_path):
    client = Mock(embed=Mock(side_effect=RuntimeError("token secret-123")))
    service = create_rag_service(client=client, workspace=tmp_path)
    response = service.set_enabled(True)
    assert response.state.value == "UNAVAILABLE" and response.error
    assert "secret-123" not in str(response.to_dict())


def test_swallowed_legacy_embedding_errors_surface_at_common_boundary(tmp_path, capsys):
    (tmp_path / "source.txt").write_text("project", encoding="utf-8")
    client = embeddings()
    service = create_rag_service(client=client, workspace=tmp_path)
    assert not service.set_enabled(True).error
    client.embed.side_effect = RuntimeError("secret-123")
    response = service.query("question")
    assert response.error.code == "RAG_EMBEDDING_UNAVAILABLE"
    assert "secret-123" not in capsys.readouterr().err
    response = service.set_enabled(True)
    assert response.error
    assert "secret-123" not in capsys.readouterr().err


def test_partial_index_failure_observable_without_algorithm_redesign(tmp_path, capsys):
    (tmp_path / "source.txt").write_text("project", encoding="utf-8")
    client = Mock(embed=Mock(side_effect=lambda _m, t:
        [[1.]] if isinstance(t, str) else (_ for _ in ()).throw(RuntimeError("secret"))))
    response = create_rag_service(client=client, workspace=tmp_path).set_enabled(True)
    assert response.error.code == "RAG_EMBEDDING_UNAVAILABLE"
    assert "secret" not in capsys.readouterr().err


@pytest.mark.parametrize("bad", [[], [[1.], [2.]]])
def test_invalid_embedding_results_do_not_hide_failure(tmp_path, bad):
    (tmp_path / "source.txt").write_text("project", encoding="utf-8")
    client = Mock(embed=Mock(side_effect=lambda _m, t: [[1.]] if isinstance(t, str) else bad))
    result = create_rag_service(client=client, workspace=tmp_path).set_enabled(True)
    assert result.error.code == "RAG_EMBEDDING_UNAVAILABLE"


def test_service_crosses_worker_threads_with_owned_sqlite_connections(tmp_path):
    (tmp_path / "source.txt").write_text("fact", encoding="utf-8")
    service = create_rag_service(client=embeddings(), workspace=tmp_path)
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert not pool.submit(service.set_enabled, True).result().error
        results = list(pool.map(service.query, ["q1", "q2", "q3", "q4"]))
    assert all(not r.error and len(r.matches) == 1 for r in results)


def test_connection_closed_on_query_and_index_exceptions(tmp_path):
    engine = Mock()
    engine.query.side_effect = RuntimeError("failed")
    factory = Mock(return_value=engine)
    backend = LegacyProjectRetrieval(client=embeddings(), workspace=tmp_path, engine_factory=factory)
    with pytest.raises(RuntimeError):
        backend.query("q", 5)
    engine.close.assert_called_once()
    engine.close.reset_mock()
    engine.index_directory.side_effect = RuntimeError("failed")
    with pytest.raises(RuntimeError):
        backend.index()
    engine.close.assert_called_once()


def test_disconnected_progress_consumer_does_not_change_outcome(tmp_path):
    service = create_rag_service(client=embeddings(), workspace=tmp_path)
    def disconnected(_event):
        raise ConnectionError("renderer reloaded")
    assert not service.set_enabled(True, progress=disconnected).error


def test_unavailable_query_can_recover_without_rebuilding_frontend(tmp_path):
    backend = Mock(index=Mock(return_value={}), query=Mock(side_effect=RAGError("OFFLINE", "offline")))
    service = RAGService(backend)
    service.set_enabled(True)
    assert service.query("q").error.code == "OFFLINE"
    backend.query.side_effect = None
    backend.query.return_value = []
    assert not service.query("q").error
    assert service.status()["availability"] == "AVAILABLE"


def test_invalid_backend_results_degrade_instead_of_breaking_context_injection():
    backend = Mock(index=Mock(return_value={}), query=Mock(return_value=[{"content": "malformed"}]))
    service = RAGService(backend)
    service.set_enabled(True)
    response = service.query("q")
    assert response.error.code == "RAG_INVALID_RESPONSE"
    assert response.context_message() is None


def test_invalid_optional_config_never_claims_availability(tmp_path):
    service = create_rag_service(client=embeddings(), workspace=tmp_path, top_k=0)
    assert service.status()["error"]["code"] == "RAG_INVALID_CONFIGURATION"
    assert service.set_enabled(True).state.value == "UNAVAILABLE"
    assert service.query("q").context_message() is None
    assert not (tmp_path / "rag_index.db").exists()


def test_real_legacy_engine_bridge_never_transfers_sqlite_connection(tmp_path):
    from local_cli.infrastructure.rag import ExistingEngineRetrieval
    (tmp_path / "source.txt").write_text("fact", encoding="utf-8")
    engine = RAGEngine(embeddings(), cwd=tmp_path)
    try:
        engine.index_directory(".")
        service = RAGService(ExistingEngineRetrieval(engine))
        service.set_enabled(True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(service.query, "question").result()
        assert not response.error and response.matches[0]["content"] == "fact"
        assert engine.query("question")  # Caller still owns its original connection.
    finally:
        engine.close()


def test_project_retrieval_excludes_owned_transcript_snapshots_and_audit_logs(tmp_path):
    from local_cli.conversation_store import ConversationStore
    from local_cli.session import SessionManager
    from local_cli.session_log import SessionLogger
    state = tmp_path / "state"
    ConversationStore(str(state), cwd=str(tmp_path)).save([{"role": "user", "content": "private conversation"}])
    SessionManager(str(state)).save_session([{"role": "assistant", "content": "private snapshot"}])
    logger = SessionLogger(str(state), cwd=str(tmp_path))
    logger.log("event", content="private audit")
    logger.close()
    (tmp_path / "source.jsonl").write_text('{"project": "valid dataset"}', encoding="utf-8")
    service = create_rag_service(client=embeddings(), workspace=tmp_path, state_dir=state)
    result = service.set_enabled(True)
    assert result.stats["files_indexed"] == 1
    matches = service.query("private").matches
    assert len(matches) == 1 and matches[0]["file_path"].endswith("source.jsonl")
    assert "private conversation" not in str(matches)


def test_existing_index_state_chunks_filtered_without_changing_legacy_format(tmp_path):
    from local_cli.application.rag import adapt_legacy_rag_service
    state = tmp_path / "state"
    (state / "projects").mkdir(parents=True)
    (state / "projects" / "last-conversation.jsonl").write_text("old private history", encoding="utf-8")
    (tmp_path / "source.txt").write_text("project fact", encoding="utf-8")
    client = embeddings()
    old = RAGEngine(client, cwd=tmp_path)
    try:
        old.index_directory(".")
        assert len(old.query("q")) == 2
        for service in (create_rag_service(client=client, workspace=tmp_path, state_dir=state),
                        adapt_legacy_rag_service(old, workspace=tmp_path, state_dir=state)):
            service.set_enabled(True)
            matches = service.query("q").matches
            assert len(matches) == 1 and matches[0]["content"] == "project fact"
        assert len(old.query("q")) == 2  # No destructive migration/retention decision.
    finally:
        old.close()
