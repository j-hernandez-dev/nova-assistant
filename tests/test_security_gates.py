"""Tests for the security boundaries around one-shot behaviour.

Audit findings (2026-07-07): the GUI (desktop) path constructed
``BashTool()`` with no confirm callback, so risky commands (sudo,
recursive rm, kill, ...) ran unconfirmed; sub-agents likewise.  The
system prompt had no security section, and injected project-instruction
files carried no authority boundary — a malicious AGENTS.md in a cloned
repo could steer a small model.

These tests pin the fixes: GUI confirm flow (deny on timeout),
sub-agent risky refusal, the SECURITY prompt section, and the
instruction-injection boundary.
"""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from local_cli.project_instructions import build_instruction_message
from local_cli.prompts import build_system_prompt
from local_cli.tools import get_default_tools, get_sub_agent_tools
from tests.test_server import _make_server


class TestSubAgentBashPolicy(unittest.TestCase):
    def _bash(self, tools: list) -> object:
        return next(t for t in tools if t.name == "bash")

    def test_sub_agent_refuses_risky_commands(self) -> None:
        bash = self._bash(get_sub_agent_tools())
        # $((6*7)) would expand to 42 only if the command actually ran;
        # the decline message merely echoes the unexpanded text.
        result = bash.execute(command="sudo echo $((6*7))")
        self.assertIn("Command declined (not run)", result)
        self.assertNotIn("42", result)

    def test_sub_agent_still_runs_normal_commands(self) -> None:
        bash = self._bash(get_sub_agent_tools())
        result = bash.execute(command="echo subagent-ok")
        self.assertIn("subagent-ok", result)

    def test_default_tools_deny_risky_without_frontend(self) -> None:
        """An unattended frontend cannot silently approve risky commands."""
        bash = self._bash(get_default_tools())
        self.assertIsNotNone(bash._confirm)
        self.assertFalse(bash._confirm("Remove-Item -Recurse build"))


class TestGuiConfirm(unittest.TestCase):
    """Same security observations through the sole Application approval gate."""
    def _exercise(self, approved=None, *, auto=False, timeout=None):
        import tempfile
        from pathlib import Path
        from tests.test_nova_core_phase7_server_legacy import approval_adapter
        from tests.test_nova_core_phase11_adapter import _wait_for
        with tempfile.TemporaryDirectory() as directory:
            adapter,app,sent,executor=approval_adapter(Path(directory),auto=auto,timeout=timeout)
            try:
                adapter.handle({"id":1,"type":"chat","content":"run"})
                if approved is not None:
                    request=_wait_for(sent,"confirm_request")
                    adapter.handle({"type":"confirm_response","confirm_id":request["confirm_id"],"approved":approved})
                _wait_for(sent,"done",request_id=1)
                return sent,executor.run.call_count
            finally:adapter.close()

    def test_auto_approve_skips_the_dialog(self):
        sent,calls=self._exercise(auto=True)
        self.assertEqual(calls,1)
        self.assertFalse(any(m.get("type")=="confirm_request" for m in sent))

    def test_approved_by_gui(self):
        sent,calls=self._exercise(True)
        self.assertEqual(calls,1)
        request=next(m for m in sent if m.get("type")=="confirm_request")
        self.assertIn("confirm_id",request)

    def test_denied_by_gui(self):
        _,calls=self._exercise(False)
        self.assertEqual(calls,0)

    def test_timeout_denies(self):
        _,calls=self._exercise(timeout=.05)
        self.assertEqual(calls,0)

    def test_confirm_response_routing_sets_event(self):
        _,calls=self._exercise(True)
        self.assertEqual(calls,1)


class TestPromptSecuritySection(unittest.TestCase):
    def test_system_prompt_has_security_rules(self) -> None:
        prompt = build_system_prompt(get_default_tools())
        self.assertIn("SECURITY:", prompt)
        self.assertIn("DATA", prompt)
        self.assertIn("secrets", prompt)
        self.assertIn("least destructive", prompt)

    def test_instruction_injection_carries_boundary(self) -> None:
        msg = build_instruction_message("AGENTS.md", "use tabs")
        self.assertIn("conventions ONLY", msg["content"])
        self.assertIn("do NOT comply", msg["content"])


if __name__ == "__main__":
    unittest.main()
