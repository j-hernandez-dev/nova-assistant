"""Sub-agent cancellation propagates without changing process cwd."""

from threading import Event, Thread
import time
from unittest.mock import Mock

from local_cli.application.cancellation import CancellationController
from local_cli.sub_agent import SubAgent, SubAgentRunner
from local_cli.shell_executor import ShellDescriptor, ShellExecutionCancelled
from local_cli.tools.bash_tool import BashTool
from tests.test_nova_core_phase4_session import ScriptedProvider


class _BlockingProvider:
    name = "fake"

    def __init__(self):
        self.started = Event()
        self.release = Event()

    def chat_stream(self, *_args, **_kwargs):
        self.started.set()
        yield {"message": {"content": "partial"}}
        self.release.wait(5)
        yield {"message": {"content": "late"}}


def test_subagent_cancellation_token_stops_child_loop(tmp_path):
    provider = _BlockingProvider()
    token = CancellationController()
    agent = SubAgent(provider, "local", [], "task", cwd=tmp_path,
                     cancellation_token=token)
    output = []
    worker = Thread(target=lambda: output.append(agent.run()))
    worker.start()
    assert provider.started.wait(2)
    token.request()
    provider.release.set()
    worker.join(5)
    assert not worker.is_alive()
    assert output[0].status == "cancelled"


def test_background_runner_cancel_requests_then_observes_terminal(tmp_path):
    provider = _BlockingProvider()
    agent = SubAgent(provider, "local", [], "task", cwd=tmp_path)
    runner = SubAgentRunner(max_workers=1)
    try:
        agent_id = runner.submit_background(agent)
        assert provider.started.wait(2)
        assert runner.cancel(agent_id)
        provider.release.set()
        result = None
        for _ in range(200):
            result = runner.get_background_result(agent_id)
            if result is not None:
                break
            time.sleep(0.005)
        assert result is not None and result.status == "cancelled"
        assert not runner.cancel(agent_id)
    finally:
        provider.release.set()
        runner.shutdown()


def test_cancelled_subagent_with_started_shell_preserves_unknown_effect(tmp_path):
    executor = Mock()
    token = CancellationController()

    def interrupted(*_args, **_kwargs):
        token.request()
        raise ShellExecutionCancelled()

    executor.run.side_effect = interrupted
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "echo begun"}},
    }]}
    agent = SubAgent(ScriptedProvider([call]), "local", [shell], "task",
                     cwd=tmp_path, environment={}, cancellation_token=token)
    result = agent.run()
    assert result.status == "outcome_unknown"
    executor.run.assert_called_once()
