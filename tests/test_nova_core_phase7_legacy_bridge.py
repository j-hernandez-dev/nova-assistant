"""Legacy interfaces resolve the common gates until full API migration."""

import subprocess
from threading import Event, Thread
from unittest.mock import Mock

from local_cli.application.legacy_interactions import LegacyInteractionBridge
from local_cli.shell_executor import ShellDescriptor, ShellExecutionCancelled
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.agent_tool import AgentTool
from local_cli.sub_agent import SubAgentResult, SubAgentRunner
from tests.test_nova_core_phase4_session import ScriptedProvider


def test_cli_responder_uses_common_input_gate_and_keeps_tool_schema(tmp_path):
    asked = []
    tool = AskUserTool(responder=lambda question: asked.append(question) or "answer")
    bridge = LegacyInteractionBridge([tool], cwd=tmp_path)
    adapted = bridge.tools[0]
    assert adapted.parameters == tool.parameters
    assert adapted.execute(question="Question?") == "answer"
    assert asked == ["Question?"]
    assert not bridge.user_input_gate.pending()


def test_legacy_approval_resolver_is_one_shot_and_executes_once(tmp_path):
    confirmed = []
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    tool = BashTool(confirm=lambda command: confirmed.append(command) or True,
                    descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                    executor=executor, cwd=tmp_path, environment={})
    bridge = LegacyInteractionBridge([tool], cwd=tmp_path, environment={})
    assert bridge.tools[0].execute(command="sudo echo ok") == "ok\n"
    assert confirmed == ["sudo echo ok"]
    assert not bridge.approval_gate.pending()
    executor.run.assert_called_once()


def test_legacy_stop_reaches_running_shell(tmp_path):
    started, cancelled = Event(), Event()
    executor = Mock()

    def run(*_args, cancellation_token, **_kwargs):
        started.set()
        assert cancelled.wait(2)
        assert cancellation_token.is_cancel_requested()
        raise ShellExecutionCancelled()

    executor.run.side_effect = run
    tool = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                    executor=executor, cwd=tmp_path, environment={})
    bridge = LegacyInteractionBridge([tool], cwd=tmp_path, environment={},
                                   should_stop=cancelled.is_set)
    output = []
    worker = Thread(target=lambda: output.append(
        bridge.tools[0].execute(command="echo begun")))
    worker.start()
    assert started.wait(1)
    cancelled.set()
    worker.join(2)
    assert not worker.is_alive()
    assert "outcome unknown" in output[0]
    executor.run.assert_called_once()


def test_legacy_cancel_waits_for_background_child_outcome(tmp_path, monkeypatch):
    runner = SubAgentRunner(max_workers=1)
    agent_tool = AgentTool(runner, ScriptedProvider([]), "local", [], cwd=tmp_path)
    monkeypatch.setattr(agent_tool, "_create_fresh_provider", lambda: ScriptedProvider([]))
    submitted = []

    def submit(child, *, on_complete):
        submitted.append((child, on_complete))
        return child.agent_id

    monkeypatch.setattr(runner, "submit_background", submit)
    bridge = LegacyInteractionBridge([agent_tool], cwd=tmp_path)
    try:
        assert "background" in bridge.tools[0].execute(
            description="child", prompt="work", run_in_background=True)
        bridge.cancel()
        waiting = Event()

        def wait():
            bridge.wait_for_children()
            waiting.set()

        worker = Thread(target=wait)
        worker.start()
        assert not waiting.wait(0.05)
        child, completed = submitted[0]
        assert child._cancellation.is_cancel_requested()
        completed(SubAgentResult(child.agent_id, "child", "", "cancelled", 0, 0, 0))
        worker.join(2)
        assert waiting.is_set()
    finally:
        runner.shutdown()
