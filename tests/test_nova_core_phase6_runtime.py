"""Phase-6 ToolRuntime contracts over the unchanged public tool surface."""

import subprocess
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from local_cli.application.tool_runtime import (
    LegacyToolAdapter, ToolPolicyAction, ToolRegistry, ToolRuntime,
)
from local_cli.application.events import EventBufferConfig
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import (
    EventKind, ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation,
    ToolStatus, new_operation_id, new_session_id, new_tool_call_id,
    new_turn_id, new_command_id,
)
from local_cli.shell_executor import ShellDescriptor
from local_cli.security import get_sanitized_env
from local_cli.sub_agent import SubAgent
from local_cli.tools import get_default_tools
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.agent_tool import AgentTool
from local_cli.tools.base import Tool
from local_cli.tools.todo_tool import TodoWriteTool
from tests.test_nova_core_phase4_session import ScriptedProvider
from tests.security_v12.process_fixtures import bind_mock_shell


class _NeverCancelled:
    def is_cancel_requested(self):
        return False


def _context(tmp_path, *, operation_id=None):
    return ExecutionContext(
        workspace=tmp_path, cwd=tmp_path, environment=get_sanitized_env(),
        session_id='fixture-session', turn_id='fixture-turn',
        operation_id=operation_id or new_operation_id(),
        cancellation_token=_NeverCancelled(), deadline=None,
        capabilities=RuntimeCapabilitySnapshot(
            captured_at=datetime.now(timezone.utc), source="test"),
    )


def _invoke(name, arguments, context):
    return ToolInvocation(name=name, arguments=arguments,
                          tool_call_id=new_tool_call_id(),
                          operation_id=context.operation_id, context=context)


def test_registry_preserves_nine_base_schemas_and_conditional_agent(tmp_path):
    originals = get_default_tools(cwd=tmp_path)
    registry = ToolRegistry(originals)
    assert registry.names == tuple(tool.name for tool in originals)
    assert all(registry.definition(tool.name).to_ollama_tool() ==
               tool.to_ollama_tool() for tool in originals)
    assert all(registry.definition(tool.name).to_claude_tool() ==
               tool.to_claude_tool() for tool in originals)
    assert "agent" not in registry.names
    agent = AgentTool(runner=object(), provider=object(), model="local",
                      sub_agent_tools=[], cwd=tmp_path)
    ten = ToolRegistry([*originals, agent])
    assert len(ten.names) == 10 and ten.names[-1] == "agent"
    assert ten.definition("agent").to_ollama_tool() == agent.to_ollama_tool()


def test_runtime_normalizes_call_revalidates_brokered_read_and_write(tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("old", encoding="utf-8")
    runtime = ToolRuntime(ToolRegistry(get_default_tools(cwd=tmp_path)))
    first = runtime.execute(_invoke("read_file", {"path": "note.txt"},
                                    _context(tmp_path)))
    second = runtime.execute(_invoke("read", {"file_path": "note.txt"},
                                     _context(tmp_path)))
    assert first.status is ToolStatus.COMPLETED
    assert second.metadata["cached"] is False
    assert first.legacy_text == second.legacy_text
    # A different operation must read the current object, never legacy cache.
    target.write_text("external change", encoding="utf-8")
    changed = runtime.execute(_invoke("read", {"file_path": "note.txt"}, _context(tmp_path)))
    assert "external change" in changed.legacy_text and changed.metadata["cached"] is False
    write = runtime.execute(_invoke("write", {"file_path": "note.txt",
                                            "content": "new"}, _context(tmp_path)))
    assert write.status is ToolStatus.COMPLETED
    refreshed = runtime.execute(_invoke("read", {"file_path": "note.txt"},
                                        _context(tmp_path)))
    assert refreshed.metadata["cached"] is False
    assert "new" in refreshed.legacy_text
    runtime.close()


def test_shell_policy_blocks_and_preserves_approval_then_exit_code(tmp_path):
    executor = Mock()
    descriptor = ShellDescriptor("Linux", "bash", "bash", "5")
    shell = BashTool(confirm=lambda _command: False, descriptor=descriptor,
                     executor=executor, cwd=tmp_path)
    bind_mock_shell(shell, executor)
    runtime = ToolRuntime(ToolRegistry([shell]))
    blocked = runtime.execute(_invoke("bash", {"command": "rm -rf /"},
                                      _context(tmp_path)))
    declined = runtime.execute(_invoke("bash", {"command": "git reset --hard"},
                                       _context(tmp_path)))
    assert blocked.status is ToolStatus.DENIED
    assert declined.status is ToolStatus.DENIED
    assert runtime.policy_for("bash", {"command": "git reset --hard"}).action is (
        ToolPolicyAction.REQUIRE_APPROVAL)
    assert executor.run.call_count == 0
    executor.run.return_value = subprocess.CompletedProcess([], 7, "out\n", "err\n")
    failed = runtime.execute(_invoke("bash", {"command": "echo hi"},
                                     _context(tmp_path)))
    assert (failed.status, failed.exit_code, failed.stdout, failed.stderr) == (
        ToolStatus.FAILED, 7, "out\n", "err\n")
    assert failed.legacy_text == "out\nerr\n[exit code: 7]"


def test_adapter_retains_public_wire_text_and_single_typed_terminal(tmp_path):
    original = TodoWriteTool()
    events = []
    runtime = ToolRuntime(ToolRegistry([original]), publish=events.append)
    adapter = LegacyToolAdapter(original, runtime,
                                context_factory=lambda: _context(tmp_path))
    assert adapter.to_ollama_tool() == original.to_ollama_tool()
    result = adapter.execute(todos=[{"content": "task", "status": "pending"}])
    assert result == original.execute(todos=[{"content": "task", "status": "pending"}])
    assert [kind for kind, _, _ in events] == [
        EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED,
        EventKind.TOOL_COMPLETED,
    ]
    assert len({invocation.operation_id for _, invocation, _ in events}) == 1


def test_separate_todo_registries_never_share_mutable_state(tmp_path):
    first = ToolRuntime(ToolRegistry([TodoWriteTool()]))
    second = ToolRuntime(ToolRegistry([TodoWriteTool()]))
    payload = {"todos": [{"content": "first", "status": "pending"}]}
    assert first.execute(_invoke("todo_write", payload, _context(tmp_path))).status \
        is ToolStatus.COMPLETED
    assert second.registry.tool("todo_write")._todos == []


def test_two_subagents_do_not_share_todo_template(tmp_path):
    template = TodoWriteTool()
    todo_call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "todo_write", "arguments": {"todos": [
            {"content": "one", "status": "pending"},
        ]}},
    }]}
    first = SubAgent(ScriptedProvider([todo_call, "done"]), "local", [template],
                     "first", cwd=tmp_path)
    second = SubAgent(ScriptedProvider(["done"]), "local", [template],
                      "second", cwd=tmp_path)
    assert first.run().status == "success"
    assert second.run().status == "success"
    assert template._todos == []
    assert first._tools[0]._tool is not second._tools[0]._tool


def test_main_agent_uses_tool_runtime_and_one_typed_tool_terminal(tmp_path):
    call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "todo_write", "arguments": {"todos": [
            {"content": "task", "status": "pending"},
        ]}},
    }]}
    tool = TodoWriteTool()
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([call, "done"]), model="local",
        tool_factory=lambda cwd: [tool],
        event_config=EventBufferConfig(32, 32, 8),
    )
    started = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(tmp_path)},
    ))
    receipt = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SUBMIT_USER_INPUT,
        session_id=started.session_id, payload={"content": "plan"},
    ))
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    events = coordinator.poll_events(coordinator.subscribe_events(
        started.session_id, after_sequence=0))
    tool_events = [event for event in events if event.kind in (
        EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED,
        EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED)]
    assert [event.kind for event in tool_events] == [
        EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED,
        EventKind.TOOL_COMPLETED,
    ]
    assert len({event.operation_id for event in tool_events}) == 1
    assert len({event.tool_call_id for event in tool_events}) == 1
    assert len(tool._todos) == 1


def test_operation_id_is_idempotent_and_conflicting_reuse_fails(tmp_path):
    tool = TodoWriteTool()
    events = []
    runtime = ToolRuntime(ToolRegistry([tool]), publish=events.append)
    context = _context(tmp_path)
    payload = {"todos": [{"content": "one", "status": "pending"}]}
    invocation = _invoke("todo_write", payload, context)
    first = runtime.execute(invocation)
    assert runtime.execute(invocation) is first
    assert len([event for event in events if event[0] is EventKind.TOOL_COMPLETED]) == 1
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        runtime.execute(_invoke("todo_write", {"todos": []}, context))
    assert tool._todos == payload["todos"]


def test_each_legacy_tool_invalid_call_returns_structured_result(tmp_path):
    originals = get_default_tools(cwd=tmp_path)
    agent = AgentTool(runner=object(), provider=object(), model="local",
                      sub_agent_tools=[], cwd=tmp_path)
    runtime = ToolRuntime(ToolRegistry([*originals, agent]))
    for tool in [*originals, agent]:
        result = runtime.execute(_invoke(tool.name, {}, _context(tmp_path)))
        assert isinstance(result.legacy_text, str)
        assert result.status is ToolStatus.FAILED, tool.name
        assert result.legacy_text.startswith("Error:"), tool.name
        assert runtime.registry.definition(tool.name).name == tool.name


def test_shell_runtime_denies_risky_command_without_explicit_approval(tmp_path):
    executor = Mock()
    shell = BashTool(confirm=None,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path)
    runtime = ToolRuntime(ToolRegistry([shell]))
    result = runtime.execute(_invoke("bash", {"command": "sudo echo hi"},
                                     _context(tmp_path)))
    assert result.status is ToolStatus.DENIED
    executor.run.assert_not_called()


def test_tool_policy_denial_emits_only_specialized_terminal(tmp_path):
    executor = Mock()
    shell = BashTool(confirm=lambda _command: True,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path)
    events = []
    runtime = ToolRuntime(ToolRegistry([shell]), publish=events.append)
    invocation = _invoke("bash", {"command": "rm -rf /"}, _context(tmp_path))
    result = runtime.execute(invocation)
    assert result.status is ToolStatus.DENIED
    assert [event[0] for event in events] == [EventKind.TOOL_REQUESTED,
                                             EventKind.TOOL_FAILED]
    assert events[-1][1].tool_call_id == invocation.tool_call_id
    assert events[-1][2].operation_outcome.value == "failed"
    executor.run.assert_not_called()


def test_explicit_auto_approval_cannot_replace_s2_human_confirmation(tmp_path):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    shell = BashTool(confirm=None,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path)
    runtime = ToolRuntime(ToolRegistry([shell]), auto_approve=True)
    result = runtime.execute(_invoke("bash", {"command": "git reset --hard"},
                                     _context(tmp_path)))
    assert result.status is ToolStatus.DENIED
    executor.run.assert_not_called()


def test_cwd_mismatch_is_denied_before_tool_execution(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     cwd=other)
    runtime = ToolRuntime(ToolRegistry([shell]))
    result = runtime.execute(_invoke("bash", {"command": "echo hi"},
                                     _context(tmp_path)))
    assert result.status is ToolStatus.DENIED


def test_shell_environment_mismatch_is_denied_before_execution(tmp_path):
    executor = Mock()
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path,
                     environment={"NOVA_PHASE6": "bound"})
    runtime = ToolRuntime(ToolRegistry([shell]))
    result = runtime.execute(_invoke("bash", {"command": "echo hi"},
                                     _context(tmp_path)))
    assert result.status is ToolStatus.DENIED
    executor.run.assert_not_called()


def test_interrupted_effect_is_unknown_and_same_operation_is_not_retried(tmp_path):
    class InterruptingTool(Tool):
        name = "interrupting"
        description = "Interrupt after starting."
        parameters = {"type": "object", "properties": {}, "required": []}

        def __init__(self):
            self.calls = 0

        def execute(self, **kwargs):
            self.calls += 1
            raise KeyboardInterrupt()

    tool = InterruptingTool()
    events = []
    runtime = ToolRuntime(ToolRegistry([tool]), publish=events.append)
    invocation = _invoke("interrupting", {}, _context(tmp_path))
    with pytest.raises(KeyboardInterrupt):
        runtime.execute(invocation)
    retry = runtime.execute(invocation)
    assert retry.status is ToolStatus.OUTCOME_UNKNOWN
    assert tool.calls == 1
    assert [event[0] for event in events] == [
        EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED, EventKind.TOOL_FAILED,
    ]
