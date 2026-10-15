"""Frozen legacy formats/behaviour before extracting phase-10 services."""

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import pytest

from local_cli.conversation_store import ConversationStore
from local_cli.session import SessionManager
from local_cli.rag import RAGEngine


def test_autosave_preserves_fields_unicode_and_legacy_tail(tmp_path):
    store = ConversationStore(str(tmp_path), cwd=str(tmp_path))
    messages = [{"role": "user", "content": str(i)} for i in range(405)]
    messages += [{"role": "system", "content": "rebuilt"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call-1",
            "function": {"name": "read", "arguments": {"file_path": "á.txt"}}}]},
        {"role": "tool", "tool_call_id": "call-1", "content": "ñ🙂"}]
    store.save(messages)
    loaded = store.load()
    assert len(loaded) == 400 and loaded[0]["content"] == "7"
    assert loaded[-2:] == messages[-2:]
    meta = json.loads(store.path.read_text(encoding="utf-8").splitlines()[0])
    assert meta["_meta"] and meta["cwd"] == str(tmp_path.resolve())


def test_failed_atomic_autosave_keeps_previous_copy(tmp_path):
    store = ConversationStore(str(tmp_path), cwd=str(tmp_path))
    old = [{"role": "user", "content": "last good"}]
    store.save(old)
    with patch("local_cli.conversation_store.os.replace", side_effect=OSError("crash")):
        store.save([{"role": "user", "content": "new"}])
    assert store.load() == old


def test_old_snapshot_jsonl_with_usage_and_partial_line_loads(tmp_path):
    manager = SessionManager(str(tmp_path))
    messages = [{"role": "system", "content": "old prompt"},
        {"role": "assistant", "content": "ñ", "token_usage": {"input_tokens": 19},
         "tool_calls": [{"id": "x", "function": {"name": "read"}}]}]
    path = tmp_path / "sessions" / "20260101-010101-abcd.jsonl"
    path.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in messages)
                    + '\n{"role":', encoding="utf-8")
    assert manager.load_session(path.stem) == messages


def test_manual_snapshot_includes_system_and_has_no_autosave_tail_limit(tmp_path):
    manager = SessionManager(str(tmp_path))
    messages = [{"role": "system", "content": "system"}] + [
        {"role": "user", "content": str(i)} for i in range(450)]
    key = manager.save_session(messages)
    assert manager.load_session(key) == messages


def test_sqlite_legacy_engine_cannot_cross_thread(tmp_path):
    engine = RAGEngine(Mock(embed=Mock(return_value=[[1.0]])), cwd=tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(Exception, match="SQLite objects created in a thread"):
                pool.submit(engine.query, "question").result()
    finally:
        engine.close()


def test_legacy_rag_swallows_query_embedding_failure(tmp_path):
    engine = RAGEngine(Mock(embed=Mock(side_effect=RuntimeError("offline"))), cwd=tmp_path)
    try:
        assert engine.query("question") == []
        assert engine.augment_prompt("question") == "question"
    finally:
        engine.close()


def test_legacy_rag_index_stats_and_prompt_format(tmp_path):
    (tmp_path / "source.txt").write_text("useful project fact", encoding="utf-8")
    client = Mock(embed=Mock(side_effect=lambda _m, text: [[1., 0.]] *
                            (len(text) if isinstance(text, list) else 1)))
    engine = RAGEngine(client, cwd=tmp_path)
    try:
        stats = engine.index_directory(".")
        assert stats["files_indexed"] == 1 and stats["chunks_indexed"] == 1
        assert engine.index_directory(".")["files_unchanged"] == 1
        prompt = engine.augment_prompt("question", top_k=1)
        assert prompt.startswith("Here is relevant context from the codebase:\n\n")
        assert prompt.endswith("\n\n---\n\nUser question: question")
    finally:
        engine.close()
