"""Pre-migration Desktop contracts: Application owns the only Turn/state."""

from threading import Event

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import new_command_id
from local_cli.harness import AgentEvent


def test_snapshot_exposes_active_turn_and_provider_change_is_non_destructive(tmp_path):
    entered, release = Event(), Event()

    def runner(provider, model, tools, messages, **kwargs):
        kwargs["emit"](AgentEvent("llm_start", {"iteration": 1}))
        kwargs["emit"](AgentEvent("content_delta", {"text": "hola"}))
        entered.set()
        assert release.wait(5)
        messages.append({"role": "assistant", "content": "hola"})
        return "hola"

    app = AgentSessionCoordinator(provider=object(), model="local",
        tool_factory=lambda _: [], run_agent_fn=runner)
    start = app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
        {"workspace": str(tmp_path)}))
    sid = start.session_id
    try:
        receipt = app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
            {"content": "saluda"}, session_id=sid))
        assert entered.wait(2)
        before = app.get_snapshot(sid).to_dict()
        assert before["transcript"][-1] == {"role": "user", "content": "saluda"}
        assert before["turns"][-1]["activeGenerationId"]
        rejected = app.handle(ApplicationCommand(new_command_id(), CommandKind.CHANGE_MODEL,
            {"modelId": "other"}, session_id=sid))
        assert not rejected.accepted
        assert rejected.error.code == "CONFLICT_ACTIVE_TURN"
        after = app.get_snapshot(sid).to_dict()
        assert after["turns"] == before["turns"]
        assert after["modelRuntime"] == before["modelRuntime"]
        release.set()
        assert app.wait_for_turn(receipt.created_ids["turnId"], 5)
        assert app.get_snapshot(sid).transcript[-1]["content"] == "hola"
    finally:
        release.set()


def test_desktop_file_preview_stays_read_only_and_tools_keep_public_names():
    from pathlib import Path
    from local_cli.tools import create_tools

    root = Path(__file__).resolve().parents[1]
    host = (root / "desktop/electron/main.ts").read_text(encoding="utf-8")
    assert "ipcMain.handle('list-directory'" in host
    assert "ipcMain.handle('read-file'" in host
    assert "fs.promises.readFile(filePath, 'utf-8')" in host
    tools = create_tools("server", confirm=lambda _: False)
    assert {t.name for t in tools} == {
        "bash", "read", "write", "edit", "glob", "grep", "web_fetch",
        "todo_write", "ask_user"}
