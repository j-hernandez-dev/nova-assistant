"""Golden observations of the pre-refactor Nova Core phase-0 baseline.

The fixture is intentionally checked in separately.  Future migrations may
change internals, but should keep these legacy-facing observations until a
versioned adapter explicitly replaces them.
"""

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_cli.agent import run_agent
from local_cli.cli import build_parser
from local_cli.git_capability import detect_git_capability
from local_cli.providers.claude_provider import ClaudeProvider
from local_cli.providers.llama_server_provider import LlamaServerProvider
from local_cli.providers.message_converter import messages_to_claude
from local_cli.providers.ollama_provider import OllamaProvider
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools import create_tools
from local_cli.tools.bash_tool import BashTool
from tests.test_run_agent import _DummyTool, _ScriptedClient, _call, _turn
from tests.test_server import _EchoTool, _make_server


_FIXTURE = Path(__file__).with_name("nova_core_phase0_fixture.json")


def capture_cli_and_tools():
    args = build_parser().parse_args(
        ["--provider", "ollama", "--model", "qwen3:8b", "--yes"]
    )
    tools = create_tools("cli", confirm=lambda _command: False)
    return {
        "parsed": {
            "provider": args.provider,
            "model": args.model,
            "auto_approve": args.auto_approve,
            "server": args.server,
        },
        "tools": [
            {"name": tool.name, "parameters": tool.parameters}
            for tool in tools
        ],
    }


def capture_agent_and_harness():
    alpha = _DummyTool("alpha", "A")
    beta = _DummyTool("beta", "B")
    provider = _ScriptedClient([
        _turn("", [_call("alpha", {"arg": "one"}),
                   _call("beta", {"arg": "two"})]),
        _turn("complete"),
    ])
    messages = [{"role": "user", "content": "go"}]
    events = []
    result = run_agent(
        provider, "fixture-model", [alpha, beta], messages,
        emit=events.append,
    )

    rescued_tool = _DummyTool("bash", "rescued")
    rescue_provider = _ScriptedClient([
        _turn('<tool_call>{"name":"run","arguments":{"command":"echo hi"}}</tool_call>'),
        _turn("rescued final"),
    ])
    rescue_messages = [{"role": "user", "content": "run it"}]
    rescue_events = []
    rescue_result = run_agent(
        rescue_provider, "fixture-model", [rescued_tool],
        rescue_messages, emit=rescue_events.append,
    )
    return {
        "multi_tool": {
            "result": result,
            "messages": messages,
            "event_kinds": [event.kind for event in events],
            "tool_calls": [alpha.calls, beta.calls],
            "provider_message_counts": [
                request["message_count"] for request in provider.requests
            ],
        },
        "text_rescue": {
            "result": rescue_result,
            "messages": rescue_messages,
            "event_kinds": [event.kind for event in rescue_events],
            "tool_calls": rescued_tool.calls,
        },
    }


def capture_server_and_provider():
    provider = MagicMock()
    provider.name = "test"
    provider.chat_stream.side_effect = [
        iter([{
            "message": {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "echo", "arguments": {"text": "one"}},
                     "id": "c1"},
                    {"function": {"name": "echo", "arguments": {"text": "two"}},
                     "id": "c2"},
                ],
            },
            "done": True,
        }]),
        iter([{"message": {"content": "done"}, "done": True}]),
    ]
    server = _make_server(provider, [_EchoTool()])
    sent = []
    with patch("local_cli.server._send", side_effect=sent.append):
        server._handle_chat(7, "go")
    system, claude_messages = messages_to_claude(server._messages)
    tool_formats = {
        provider.name: provider.format_tools([_EchoTool()])
        for provider in (
            OllamaProvider(), ClaudeProvider(api_key="fixture"),
            LlamaServerProvider(),
        )
    }
    return {
        "jsonl_events": sent,
        "transcript": server._messages,
        "claude_conversion": {"system": system, "messages": claude_messages},
        "provider_tool_formats": tool_formats,
    }


def capture_approval_and_no_git():
    descriptor = ShellDescriptor("Windows", "powershell", "pwsh.exe", "7.6")
    command = "sudo echo ok"
    denied_executor = MagicMock()
    denied_tool = BashTool(
        confirm=lambda _command: False,
        descriptor=descriptor, executor=denied_executor,
    )
    denied = denied_tool.execute(command=command)
    approved_executor = MagicMock()
    approved_executor.run.return_value = subprocess.CompletedProcess(
        args=[command], returncode=0, stdout="approved\n", stderr="",
    )
    approved_tool = BashTool(
        confirm=lambda _command: True,
        descriptor=descriptor, executor=approved_executor,
    )
    approved = approved_tool.execute(command=command)
    with patch("local_cli.git_capability.subprocess.run",
               side_effect=FileNotFoundError):
        no_git = detect_git_capability(str(Path.cwd())).value
    return {
        "public_tool_name": approved_tool.name,
        "risky_command": command,
        "denied_output": denied,
        "denied_executor_calls": denied_executor.run.call_count,
        "approved_output": approved,
        "approved_executor_calls": approved_executor.run.call_count,
        "no_git_capability": no_git,
    }


def capture_baseline():
    return {
        "cli_and_tools": capture_cli_and_tools(),
        "agent_and_harness": capture_agent_and_harness(),
        "server_and_provider": capture_server_and_provider(),
        "approval_and_no_git": capture_approval_and_no_git(),
    }


class TestPhase0Characterization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    def test_cli_and_public_tool_schemas(self):
        self.assertEqual(capture_cli_and_tools(), self.expected["cli_and_tools"])

    def test_multi_tool_transcript_and_text_call_rescue(self):
        self.assertEqual(
            capture_agent_and_harness(), self.expected["agent_and_harness"]
        )

    def test_legacy_jsonl_and_provider_message_conversion(self):
        actual = capture_server_and_provider()
        # The Application route adds deterministic context-budget telemetry
        # (phase 9). Freeze all original frames and their order unchanged;
        # do not regenerate the phase-0 golden or hide other new frames.
        budget_events = [event for event in actual["jsonl_events"]
                         if event.get("type") == "harness"
                         and event.get("event") == "context_budget"]
        self.assertEqual(len(budget_events), 2)
        actual["jsonl_events"] = [event for event in actual["jsonl_events"]
            if not (event.get("type") == "harness"
                    and event.get("event") == "context_budget")]
        self.assertEqual(
            actual, self.expected["server_and_provider"]
        )

    def test_approval_denial_acceptance_and_missing_git(self):
        self.assertEqual(
            capture_approval_and_no_git(), self.expected["approval_and_no_git"]
        )
