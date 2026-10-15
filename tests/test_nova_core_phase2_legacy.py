"""Characterization of wire and call shapes before phase-2 contracts."""

import io
import json
import unittest
from dataclasses import asdict
from unittest.mock import patch

from local_cli.harness import AgentEvent
from local_cli.server import _send
from local_cli.tools.base import Tool
from tests.test_run_agent import _DummyTool, _ScriptedClient, _turn
from local_cli.agent import run_agent


class TestLegacyContractBoundary(unittest.TestCase):
    def test_harness_event_has_only_kind_and_data(self) -> None:
        event = AgentEvent("content_delta", {"text": "á"})
        self.assertEqual(asdict(event), {"kind": "content_delta", "data": {"text": "á"}})

    def test_jsonl_server_keeps_legacy_shape_and_unicode(self) -> None:
        out = io.StringIO()
        with patch("local_cli.server.sys.stdout", out):
            _send({"id": 7, "type": "stream", "content": "á"})
        self.assertEqual(out.getvalue(), '{"id": 7, "type": "stream", "content": "á"}\n')
        self.assertEqual(json.loads(out.getvalue())["content"], "á")

    def test_agent_returns_text_and_mutates_legacy_transcript(self) -> None:
        provider = _ScriptedClient([_turn("complete")])
        messages = [{"role": "user", "content": "go"}]
        result = run_agent(provider, "fixture-model", [], messages)
        self.assertIsInstance(result, str)
        self.assertEqual(result, "complete")
        self.assertEqual(messages[-1]["role"], "assistant")

    def test_tool_contract_still_returns_plain_text(self) -> None:
        tool: Tool = _DummyTool("echo", "legacy output")
        self.assertEqual(tool.execute(arg="x"), "legacy output")


if __name__ == "__main__":
    unittest.main()
