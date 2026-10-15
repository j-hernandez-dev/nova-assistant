"""Tests for local_cli.server — the JSON-line server's chat handler.

The fixture injects fake inference into the production Application composition
root. Only the test observation wrapper waits for an asynchronous Turn; the
production command reader does not. _send captures compatibility frames.
"""

import threading
import unittest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_cli.config import Config
from local_cli.conversation_store import ConversationStore
from local_cli.session_log import SessionLogger
from local_cli.server import JsonLineServer
from local_cli.token_tracker import TokenTracker
from local_cli.tool_cache import ToolCache
from local_cli.tools.base import Tool


class _EchoTool(Tool):
    """Minimal tool that echoes its ``text`` argument."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo the text argument."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    def execute(self, **kwargs: object) -> str:
        return f"echoed: {kwargs.get('text', '')}"


def _make_server(provider: MagicMock, tools: list) -> JsonLineServer:
    """Build an injectable fixture that composes the real Application lazily."""
    server = _ApplicationServerFixture.__new__(_ApplicationServerFixture)
    server._cwd = Path.cwd().resolve()
    server._environment = dict(os.environ)
    server._config = Config()
    server._provider = provider
    # Raw client stub: adaptive context sizing queries show_model; an
    # empty reply keeps the resolver at the deterministic 8192 floor.
    server._client = MagicMock()
    server._client.show_model.return_value = {}
    server._tools = tools
    server._messages = [{"role": "system", "content": "sys"}]
    server._tool_cache = ToolCache()
    server._token_tracker = TokenTracker()
    server._ideation_active = False
    server._skills_loader = None
    server._session_log = SessionLogger(".", enabled=False)
    server._instruction_source = None
    server._instruction_message = None
    server._map_message = None
    server._conversation_store = ConversationStore(".", enabled=False)
    return server


class _ApplicationServerFixture(JsonLineServer):
    """Inject tests into the same Application path as the production server.

    Only this test adapter waits for private-method observations. The actual
    JSONL command reader never joins a Turn or invokes a second agent loop.
    """
    def _compose_test_application(self):
        if hasattr(self, "_app_adapter"):
            return
        from local_cli.bootstrap_server import create_server_application
        from local_cli.application.persistence import PersistenceService
        from local_cli.application.rag import RAGService
        from local_cli.application.auxiliary import AuxiliaryServices
        from local_cli.model_manager import ModelManager
        from local_cli.updater import check_for_updates, perform_update
        from local_cli.prompts import build_system_prompt
        from local_cli.server import _send
        from tests.test_nova_core_phase4_session import ScriptedProvider
        if self._provider is None:
            self._provider = ScriptedProvider([])
        if not hasattr(self._provider, "name"):
            self._provider.name = "test"
        self._ensure_provider_manager()
        self._system_prompt = getattr(self, "_system_prompt", "sys")
        if self._instruction_message and self._instruction_message not in self._messages:
            self._messages.append(self._instruction_message)
        self._sub_agent_runner = getattr(self, "_sub_agent_runner", None)
        self._ensure_rag_service()
        if not isinstance(self._conversation_store, PersistenceService):
            self._conversation_store = PersistenceService(workspace=self._cwd,
                conversation=self._conversation_store, snapshots=MagicMock())
        self._auxiliary_services = AuxiliaryServices(git=getattr(self, "_git_ops", None),
            token_tracker=self._token_tracker, skills=self._skills_loader,
            model_manager=ModelManager(self._client),
            updater_check=check_for_updates, updater_perform=perform_update)
        create_server_application(self, send=lambda item: __import__(
            "local_cli.server", fromlist=["_send"])._send(item))

    def __getattribute__(self, name):
        method = super().__getattribute__(name)
        if not (name.startswith("_handle_") or name == "run"):
            return method
        def observe(*args, **kwargs):
            self._compose_test_application()
            result = method(*args, **kwargs)
            if name in ("_handle_chat", "_handle_rag"):
                import time
                limit = time.monotonic() + 5
                app = self._application
                while time.monotonic() < limit:
                    snapshot = app.get_snapshot(self._app_adapter.session_id)
                    active = any(t["status"] == "running" for t in snapshot.turns)
                    active |= any(o["status"] in ("requested", "running")
                        for o in snapshot.services["operations"])
                    if not active:break
                    time.sleep(.002)
                assert not active, "Application test operation did not finish"
                self._app_adapter._poll_legacy()
                reports = snapshot.turns[-1].get("contextReports", []) if snapshot.turns else []
                self._last_context_budget = next((r["budget"] for r in reversed(reports)
                    if r.get("rule") == "context_budget"), None)
            return result
        return observe


class TestHandleChat(unittest.TestCase):
    """Tests for JsonLineServer._handle_chat."""

    def _provider(self, turns: list) -> MagicMock:
        provider = MagicMock()
        provider.name = "test"  # not "ollama" — skips ollama-only kwargs
        provider.chat_stream.side_effect = [iter(t) for t in turns]
        return provider

    def test_chat_executes_tool_with_tool_name(self) -> None:
        """A tool call runs and its result message carries tool_name."""
        turn1 = [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "function": {"name": "echo", "arguments": {"text": "hi"}},
                    "id": "c1",
                }],
            },
            "done": True,
        }]
        turn2 = [{"message": {"content": "done"}, "done": True}]
        tool = _EchoTool()
        server = _make_server(self._provider([turn1, turn2]), [tool])

        sent: list = []
        with patch("local_cli.server._send", side_effect=sent.append):
            server._handle_chat(1, "say hi")

        tool_msgs = [m for m in server._messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(tool_msgs[0]["tool_name"], "echo")
        self.assertIn("echoed: hi", tool_msgs[0]["content"])

        types = [o.get("type") for o in sent]
        self.assertIn("tool_call", types)
        self.assertIn("tool_result", types)
        self.assertIn("done", types)

    def test_empty_message_returns_error(self) -> None:
        """An empty/whitespace message produces an error event, no call."""
        server = _make_server(self._provider([]), [])
        sent: list = []
        with patch("local_cli.server._send", side_effect=sent.append):
            server._handle_chat(1, "   ")
        self.assertTrue(any(o.get("type") == "error" for o in sent))

    def test_plain_answer_records_assistant(self) -> None:
        """A no-tool turn streams text, records it, and emits done."""
        turn1 = [{"message": {"content": "hi there"}, "done": True}]
        server = _make_server(self._provider([turn1]), [])
        sent: list = []
        with patch("local_cli.server._send", side_effect=sent.append):
            server._handle_chat(1, "hello")

        types = [o.get("type") for o in sent]
        self.assertIn("done", types)
        self.assertNotIn("tool_call", types)
        self.assertTrue(
            any(m.get("role") == "assistant" for m in server._messages)
        )

    def test_matching_skills_injected_before_user_message(self) -> None:
        """Server chat injects matching skills like the CLI does."""

        class _Skill:
            name = "deploy-guide"
            content = "Always run the smoke test first."

        class _Loader:
            def get_matching_skills(self, text):
                return [_Skill()] if "deploy" in text else []

        turn1 = [{"message": {"content": "done"}, "done": True}]
        server = _make_server(self._provider([turn1]), [])
        server._skills_loader = _Loader()

        with patch("local_cli.server._send"):
            server._handle_chat(1, "deploy the app")

        roles = [m.get("role") for m in server._messages]
        skill_idx = next(
            i for i, m in enumerate(server._messages)
            if "deploy-guide" in m.get("content", "")
        )
        user_idx = next(
            i for i, m in enumerate(server._messages)
            if m.get("role") == "user"
        )
        self.assertEqual(server._messages[skill_idx]["role"], "system")
        self.assertLess(skill_idx, user_idx)
        self.assertIn("smoke test", server._messages[skill_idx]["content"])

    def test_nudges_on_code_only_build_answer(self) -> None:
        """A code-only answer to a build request triggers one nudge."""
        turn1 = [{"message": {"content": "```python\nprint(1)\n```"}, "done": True}]
        turn2 = [{"message": {"content": "no file needed"}, "done": True}]
        server = _make_server(self._provider([turn1, turn2]), [])
        sent: list = []
        with patch("local_cli.server._send", side_effect=sent.append):
            server._handle_chat(1, "create a script")

        nudges = [
            m for m in server._messages
            if m.get("role") == "user" and "did not create" in m.get("content", "")
        ]
        self.assertEqual(len(nudges), 0)  # harness instructions are working context, not user transcript
        self.assertTrue(any(m.get("type") == "harness" for m in sent))
        self.assertEqual(server._provider.chat_stream.call_count, 2)


if __name__ == "__main__":
    unittest.main()
