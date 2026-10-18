"""Test process: real JSONL server/Application/harness/tools/persistence.

Only inference and project embeddings are scripted; no remote model/download.
Launched exclusively by the Electron E2E harness in an isolated workspace.
"""

import sys
import time
import os
from pathlib import Path

from local_cli.application.rag import RAGService
from local_cli.core.rag import RAGError
from local_cli.providers.ollama_provider import OllamaProvider
from local_cli.server import JsonLineServer
import local_cli.bootstrap_server as server_module


class ScriptedClient:
    downloaded = set()
    refresh_delay = False
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def list_models(self):
        return [{"name": "local:7b", "size": 4_000_000_000}, {"name": "local:8b", "size": 5_000_000_000}] + [
            {"name": name, "size": 1_000_000_000} for name in self.downloaded]

    def pull_model(self, model):
        assert os.environ.get("NOVA_TEST_MODEL_DOWNLOAD") == "1", "Downloads require the isolated fixture flag"
        for percent, pause in [(15, 5), (55, 4), (100, 2)]:
            yield {"status": "pulling fixture-layer", "completed": percent, "total": 100}
            time.sleep(pause)
        self.downloaded.add(model)
        self.__class__.refresh_delay = True
        yield {"status": "success"}

    def show_model(self, model):
        return {"name": model, "capabilities": ["completion", "tools"],
                "model_info": {"test.context_length": 32768}}

    def get_version(self):
        return {"version": "test"}

    def chat_stream(self, model, messages, **kwargs):
        task = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "hello")
        latest_tool = messages[-1].get("role") == "tool"
        if task in ("ask", "approval", "read") and not latest_tool:
            name, arguments = {
                "ask": ("ask_user", {"question": "¿Continuar?"}),
                "approval": ("bash", {"command": "Remove-Item ./missing.txt" if sys.platform == "win32" else "rm ./missing.txt"}),
                "read": ("read", {"file_path": "sample.txt"}),
            }[task]
            yield {"message": {"role": "assistant", "content": "", "tool_calls": [{
                "function": {"name": name, "arguments": arguments}}]}, "done": True}
            return
        if task.startswith("stream-markdown:"):
            yield {"message": {"role": "assistant", "content": task.split(":", 1)[1]}, "done": False}
            for _ in range(300):
                time.sleep(0.025)
                yield {"message": {"role": "assistant", "content": ""}, "done": False}
            yield {"message": {"role": "assistant", "content": ""}, "done": True}
            return
        if task == "long":
            for _ in range(300):
                yield {"message": {"role": "assistant", "content": "texto "}, "done": False}
                time.sleep(0.025)
        yield {"message": {"role": "assistant", "content": "¡Hola 🧠! " + task}, "done": True}


class NamedProvider(OllamaProvider):
    def __init__(self, name):
        super().__init__(ScriptedClient())
        self._name = name

    @property
    def name(self):
        return self._name


class Retrieval:
    def index(self):
        time.sleep(0.5)
        return {"files": 1, "chunks": 1}

    def query(self, text, top_k):
        if text == "fail":
            raise RAGError("RAG_BACKEND_FAILED", "Test retrieval failure")
        return [{"file_path": "sample.txt", "chunk_index": 0, "score": 1.0, "content": "sample file"}]


class DesktopServer(JsonLineServer):
    def _handle_catalog(self, req_id):
        if ScriptedClient.refresh_delay:
            ScriptedClient.refresh_delay = False
            time.sleep(2)
        super()._handle_catalog(req_id)

    def _bg_update_check(self):
        pass  # No updater/network side effects in an isolated E2E.

    def _ensure_rag_service(self):
        if not hasattr(self, "_rag_service"):
            self._rag_service = RAGService(Retrieval())
        return self._rag_service


# Workspace changes recreate retrieval through this factory too.
server_module.create_rag_service = lambda **kwargs: RAGService(Retrieval())
server_module.OllamaClient = ScriptedClient
# Exercise the supported Git-absent path; no Git worktree/update is needed.
import local_cli.infrastructure.capabilities as capabilities
from local_cli.git_capability import GitCapability
capabilities.detect_git_capability = lambda *args, **kwargs: GitCapability.UNAVAILABLE
if os.environ.get("NOVA_TEST_MODEL_DOWNLOAD") == "1":
    import local_cli.server as jsonl_server
    jsonl_server.get_merged_catalog = lambda: ([{
        "name": "downloaded:1b", "display": "Downloaded fixture", "category": "Test",
        "params": "1B", "size_gb": 1, "description": "Owned download fixture", "tags": [],
    }], ["Test"])
server = DesktopServer()
server._provider_manager._factory = NamedProvider
if os.environ.get("NOVA_TEST_DELAY_READINESS") == "1":
    _readiness = server._application.get_readiness
    def delayed_readiness(session_id):
        time.sleep(0.4)
        return _readiness(session_id)
    server._application.get_readiness = delayed_readiness
server.run()
