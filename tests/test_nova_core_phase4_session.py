"""Phase-4 contract: one active session, turns, snapshots and legacy loop parity."""

from threading import Event

import pytest

from local_cli.agent import run_agent
from local_cli.application.commands import ApplicationCommand, CommandKind, CommandReceipt
from local_cli.application.session import AgentSessionCoordinator, SessionSnapshot
from local_cli.core.contracts import new_command_id
from local_cli.core.runtime import TurnOutcome
from local_cli.harness import HarnessConfig, files_known_to_conversation
from local_cli.tools.base import Tool
from local_cli.tools.edit_tool import EditTool
from local_cli.tools.read_tool import ReadTool


class EchoTool(Tool):
    name = "echo"
    description = "Echo one text value."
    parameters = {"type": "object", "properties": {"text": {"type": "string"}},
                  "required": ["text"]}

    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["text"]


class ScriptedProvider:
    def __init__(self, turns):
        self.turns = list(turns)

    def chat_stream(self, model, messages, **kwargs):
        value = self.turns.pop(0) if self.turns else "done"
        message = value if isinstance(value, dict) else {"role": "assistant", "content": value}
        return iter([{"message": message, "done": True}])


def start(coordinator, workspace, command_id=None):
    return coordinator.handle(ApplicationCommand(
        command_id=command_id or new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(workspace)},
    ))


def submit(coordinator, session_id, content, command_id=None):
    return coordinator.handle(ApplicationCommand(
        command_id=command_id or new_command_id(), kind=CommandKind.SUBMIT_USER_INPUT,
        session_id=session_id, payload={"content": content},
    ))


def snapshot(coordinator, session_id):
    return coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.GET_SNAPSHOT,
        session_id=session_id,
    ))


def test_one_session_start_idempotency_and_conflict(tmp_path):
    coordinator = AgentSessionCoordinator(provider=ScriptedProvider([]), model="local",
                                          tool_factory=lambda cwd: [])
    command_id = new_command_id()
    first = start(coordinator, tmp_path, command_id)
    assert isinstance(first, CommandReceipt) and first.accepted
    assert start(coordinator, tmp_path, command_id) == first
    second = start(coordinator, tmp_path)
    assert not second.accepted and second.error.code == "CONFLICT_ACTIVE_SESSION"
    assert isinstance(snapshot(coordinator, first.session_id), SessionSnapshot)


def test_submit_creates_one_turn_and_duplicate_reuses_receipt(tmp_path):
    coordinator = AgentSessionCoordinator(provider=ScriptedProvider(["respuesta"]),
                                          model="local", tool_factory=lambda cwd: [])
    session_id = start(coordinator, tmp_path).session_id
    command_id = new_command_id()
    receipt = submit(coordinator, session_id, "hola", command_id)
    assert receipt.accepted and receipt.created_ids["turnId"]
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    assert submit(coordinator, session_id, "hola", command_id) == receipt
    conflict = submit(coordinator, session_id, "otro", command_id)
    assert not conflict.accepted and conflict.error.code == "IDEMPOTENCY_CONFLICT"
    state = snapshot(coordinator, session_id).to_dict()
    assert [m["role"] for m in state["transcript"]] == ["system", "user", "assistant"]
    assert len(state["turns"]) == 1
    assert state["turns"][0]["status"] == "completed"
    assert state["turns"][0]["terminalCount"] == 1


def test_active_turn_rejects_second_turn_without_creating_chat(tmp_path):
    entered, release = Event(), Event()

    def blocking_runner(provider, model, tools, messages, **kwargs):
        entered.set()
        assert release.wait(5)
        messages.append({"role": "assistant", "content": "done"})
        return "done"

    coordinator = AgentSessionCoordinator(provider=object(), model="local",
                                          tool_factory=lambda cwd: [],
                                          run_agent_fn=blocking_runner)
    session_id = start(coordinator, tmp_path).session_id
    first = submit(coordinator, session_id, "one")
    assert entered.wait(5)
    second = submit(coordinator, session_id, "two")
    assert not second.accepted and second.error.code == "CONFLICT_ACTIVE_TURN"
    release.set()
    assert coordinator.wait_for_turn(first.created_ids["turnId"], timeout=5)
    assert len(snapshot(coordinator, session_id).turns) == 1


def test_failure_has_one_terminal_and_can_start_next_turn(tmp_path):
    calls = 0

    def runner(provider, model, tools, messages, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("provider failed")
        messages.append({"role": "assistant", "content": "recovered"})
        return "recovered"

    coordinator = AgentSessionCoordinator(provider=object(), model="local",
                                          tool_factory=lambda cwd: [],
                                          run_agent_fn=runner)
    session_id = start(coordinator, tmp_path).session_id
    first = submit(coordinator, session_id, "first")
    assert coordinator.wait_for_turn(first.created_ids["turnId"], timeout=5)
    second = submit(coordinator, session_id, "second")
    assert coordinator.wait_for_turn(second.created_ids["turnId"], timeout=5)
    turns = snapshot(coordinator, session_id).to_dict()["turns"]
    assert [turn["status"] for turn in turns] == ["failed", "completed"]
    assert [turn["terminalCount"] for turn in turns] == [1, 1]


def test_compaction_of_working_messages_preserves_canonical_transcript(tmp_path):
    def compacting_runner(provider, model, tools, messages, **kwargs):
        messages.append({"role": "assistant", "content": "before compaction"})
        del messages[1:]
        messages.append({"role": "assistant", "content": "after compaction"})
        return "after compaction"

    coordinator = AgentSessionCoordinator(provider=object(), model="local",
                                          tool_factory=lambda cwd: [],
                                          run_agent_fn=compacting_runner)
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "keep me")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    contents = [m["content"] for m in snapshot(coordinator, session_id).transcript]
    assert "keep me" in contents and "before compaction" in contents
    assert "after compaction" in contents


def test_real_legacy_loop_tool_rescue_remains_available(tmp_path):
    text_call = '<tool_call>{"name":"echo","arguments":{"text":"ok"}}</tool_call>'
    direct_tool = EchoTool()
    direct_provider = ScriptedProvider([text_call, "finished"])
    direct_messages = [{"role": "system", "content": "sys"},
                       {"role": "user", "content": "echo"}]
    direct_answer = run_agent(direct_provider, "local", [direct_tool], direct_messages)

    tool = EchoTool()
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([text_call, "finished"]), model="local",
        tool_factory=lambda cwd: [tool],
        prompt_factory=lambda tools, cwd: "sys",
    )
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "echo")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    state = snapshot(coordinator, session_id).to_dict()
    assert state["turns"][0]["finalContent"] == direct_answer
    assert tool.calls == direct_tool.calls
    assert [m["role"] for m in state["transcript"]] == [m["role"] for m in direct_messages]


def test_read_before_edit_guard_uses_session_workspace(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("value = 1\n")
    request = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "edit", "arguments": {
            "file_path": "target.py", "old_text": "value = 1", "new_text": "value = 2",
        }},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([request, "done"]), model="local",
        tool_factory=lambda cwd: [ReadTool(cwd=cwd), EditTool(cwd=cwd)],
    )
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "update target.py")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    assert target.read_text() == "value = 1\n"
    assert any("read" in m.get("content", "").lower()
               for m in snapshot(coordinator, session_id).transcript
               if m["role"] == "tool")


def test_followup_turn_uses_prior_transcript_and_snapshot_isolated(tmp_path):
    seen = []

    def runner(provider, model, tools, messages, **kwargs):
        seen.append([m["content"] for m in messages if m["role"] == "user"])
        messages.append({"role": "assistant", "content": "reply"})
        return "reply"

    coordinator = AgentSessionCoordinator(provider=object(), model="local",
                                          tool_factory=lambda cwd: [],
                                          run_agent_fn=runner)
    session_id = start(coordinator, tmp_path).session_id
    for content in ("first", "second"):
        receipt = submit(coordinator, session_id, content)
        assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    assert seen == [["first"], ["first", "second"]]
    state = snapshot(coordinator, session_id).to_dict()
    state["transcript"][1]["content"] = "tampered"
    assert snapshot(coordinator, session_id).transcript[1]["content"] == "first"


def test_stale_revision_and_wrong_session_reject_without_turn(tmp_path):
    coordinator = AgentSessionCoordinator(provider=ScriptedProvider([]), model="local",
                                          tool_factory=lambda cwd: [])
    session_id = start(coordinator, tmp_path).session_id
    stale = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SUBMIT_USER_INPUT,
        session_id=session_id, expected_revision=0, payload={"content": "hello"},
    ))
    assert not stale.accepted and stale.error.code == "REVISION_CONFLICT"
    wrong = submit(coordinator, "ses_invalid", "hello")
    assert not wrong.accepted and wrong.error.code == "INVALID_SESSION"
    assert snapshot(coordinator, session_id).turns == ()


def test_invalid_runtime_outcome_fails_turn_once(tmp_path):
    class BrokenRuntime:
        def run_turn(self, **kwargs):
            return None

    coordinator = AgentSessionCoordinator(provider=object(), model="local",
                                          tool_factory=lambda cwd: [],
                                          runtime=BrokenRuntime())
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "hello")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    turn = snapshot(coordinator, session_id).to_dict()["turns"][0]
    assert (turn["status"], turn["operationStatus"], turn["terminalCount"],
            turn["operationTerminalCount"]) == ("failed", "failed", 1, 1)
    assert turn["errorCode"] == "INVALID_RUNTIME_OUTCOME"


def test_legacy_adapter_forwards_harness_configuration(tmp_path):
    selected = HarnessConfig(max_iterations=2)
    seen = []

    def runner(provider, model, tools, messages, **kwargs):
        seen.append(kwargs["harness"])
        messages.append({"role": "assistant", "content": "done"})
        return "done"

    coordinator = AgentSessionCoordinator(provider=object(), model="local",
                                          tool_factory=lambda cwd: [],
                                          run_agent_fn=runner, harness=selected)
    session_id = start(coordinator, tmp_path).session_id
    receipt = submit(coordinator, session_id, "hello")
    assert coordinator.wait_for_turn(receipt.created_ids["turnId"], timeout=5)
    assert seen == [selected]


def test_runtime_outcome_requires_typed_terminal_status():
    with pytest.raises(ValueError, match="terminal"):
        TurnOutcome("completed")


def test_read_history_relative_path_uses_session_workspace(tmp_path):
    history = [{"role": "assistant", "tool_calls": [{
        "function": {"name": "read", "arguments": {"file_path": "target.py"}},
    }]}]
    assert files_known_to_conversation(history, cwd=tmp_path) == {
        str((tmp_path / "target.py").resolve())
    }
