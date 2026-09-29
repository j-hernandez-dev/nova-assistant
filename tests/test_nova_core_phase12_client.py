"""CLI consumes the same one-session Application commands and events."""

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.cli_application import CliApplicationClient
from tests.test_nova_core_phase4_session import ScriptedProvider
import pytest


def _client(tmp_path, provider, *, tools=(), answers=()):
    app = AgentSessionCoordinator(provider=provider, model="local",
        tool_factory=lambda _: list(tools), event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.START_SESSION, {"workspace": str(tmp_path)}))
    output = []
    responses = iter(answers)
    client = CliApplicationClient(app, started.session_id,
        write=output.append, read=lambda _: next(responses))
    return client, app, output


def test_cli_turn_uses_application_and_prints_stream(tmp_path):
    client, app, output = _client(tmp_path, ScriptedProvider(["hola"]))
    receipt = client.submit_user_input("saluda")
    assert receipt.accepted
    assert "hola" in "".join(output)
    state = app.get_snapshot(client.session_id)
    assert len(state.turns) == 1
    assert state.turns[0]["status"] == "completed"
    assert [m["role"] for m in state.transcript][-2:] == ["user", "assistant"]


def test_cli_resolves_ask_user_inside_same_turn(tmp_path):
    from local_cli.tools.ask_user_tool import AskUserTool
    ask = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "ask_user", "arguments": {"question": "¿Continuar?"}},
    }]}
    client, app, output = _client(tmp_path, ScriptedProvider([ask, "listo"]),
                                  tools=[AskUserTool()], answers=["sí"])
    receipt = client.submit_user_input("pregunta")
    assert receipt.accepted
    state = app.get_snapshot(client.session_id)
    assert len(state.turns) == 1
    assert any(m.get("role") == "tool" and "sí" in m.get("content", "")
               for m in state.transcript)


def test_cli_model_command_uses_application_conflict_policy(tmp_path):
    from tests.test_nova_core_phase8_providers import Provider
    client, app, _ = _client(tmp_path, Provider())
    receipt = client.command(CommandKind.CHANGE_MODEL, {"modelId": "new"})
    assert receipt.accepted
    assert app.get_snapshot(client.session_id).model == "new"


def test_repl_turn_does_not_call_legacy_console_agent_loop(tmp_path, monkeypatch, capsys):
    from local_cli.cli import run_repl
    from local_cli.config import Config
    from local_cli.application.providers import ProviderManager
    from local_cli.application.rag import RAGService
    from local_cli.tools.read_tool import ReadTool
    from tests.test_nova_core_phase8_providers import Provider
    provider = Provider(steps=["hola"])
    config = Config()
    config.state_dir = str(tmp_path / "state")
    config.model = "old"
    config.mascot = "off"
    answers = iter(["saluda", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr("local_cli.agent.agent_loop",
                        lambda **_: (_ for _ in ()).throw(AssertionError("legacy path")))
    run_repl(config, object(), [ReadTool(cwd=tmp_path)],
             provider_manager=ProviderManager(provider, "old"),
             rag_service=RAGService(None))
    assert "hola" in capsys.readouterr().out


def test_cli_and_jsonl_use_same_auxiliary_application_service(tmp_path):
    from local_cli.application.auxiliary import AuxiliaryResult
    from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter

    class Service:
        def __init__(self):
            self.calls = []

        def execute(self, name, arguments, *, transcript, model):
            self.calls.append((name, dict(arguments), model))
            return AuxiliaryResult(name, {"value": len(self.calls)})

    service = Service()
    app = AgentSessionCoordinator(provider=ScriptedProvider([]), model="local",
        tool_factory=lambda _: [], auxiliary_services=service,
        event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.START_SESSION, {"workspace": str(tmp_path)}))
    cli = CliApplicationClient(app, started.session_id, write=lambda _: None)
    assert cli.execute_auxiliary("plan_list").data == {"value": 1}

    frames = []
    adapter = JsonlApplicationAdapter(app, started.session_id, frames.append)
    assert adapter.handle({"id": 9, "type": "auxiliary_command",
                           "name": "plan_list", "arguments": {}})
    assert frames[-1] == {"id": 9, "type": "auxiliary_result",
                          "name": "plan_list", "data": {"value": 2}}
    assert [call[0] for call in service.calls] == ["plan_list", "plan_list"]
    adapter.close()
    cli.close()


def test_cli_approval_uses_application_gate_and_does_not_create_extra_turn(tmp_path):
    import subprocess
    from unittest.mock import Mock
    from local_cli.tools.bash_tool import BashTool
    from local_cli.shell_executor import ShellDescriptor

    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    risky = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "sudo echo ok"}},
    }]}
    client, app, _ = _client(tmp_path, ScriptedProvider([risky, "done"]),
                             tools=[shell], answers=["no"])
    try:
        receipt = client.submit_user_input("run")
        assert receipt.accepted
        assert len(app.get_snapshot(client.session_id).turns) == 1
        executor.run.assert_not_called()
    finally:
        client.close()


def test_cli_ctrl_c_requests_cancel_and_waits_for_terminal(tmp_path):
    from tests.test_nova_core_phase7_session import _BlockingProvider

    provider = _BlockingProvider()
    app = AgentSessionCoordinator(provider=provider, model="local",
        tool_factory=lambda _: [], event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.START_SESSION, {"workspace": str(tmp_path)}))
    interrupted = False
    def write(text):
        nonlocal interrupted
        if "partial" in text and not interrupted:
            interrupted = True
            raise KeyboardInterrupt
    def command(kind, _payload, _receipt):
        if kind is CommandKind.CANCEL_TURN:
            provider.release.set()
    client = CliApplicationClient(app, started.session_id,
                                  write=write, on_command=command)
    try:
        receipt = client.submit_user_input("go")
        assert receipt.accepted and interrupted
        assert app.get_snapshot(client.session_id).turns[0]["status"] == "cancelled"
    finally:
        provider.release.set()
        client.close()


def test_server_legacy_plan_and_knowledge_commands_use_shared_application(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from local_cli.config import Config
    from local_cli.server import JsonLineServer

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("local_cli.bootstrap_server.Config", lambda: Config(
        cli_args=SimpleNamespace(state_dir=str(tmp_path / "state"),
                                 plan_dir=str(tmp_path / "plans"),
                                 knowledge_dir=str(tmp_path / "knowledge"))))
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    server = JsonLineServer()
    calls = []
    original = server._application.execute_auxiliary
    def observed(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)
    monkeypatch.setattr(server._application, "execute_auxiliary", observed)
    try:
        server._handle_plan(1, "create First plan")
        server._handle_plan(2, "list")
        server._handle_knowledge(3, "save item")
        server._handle_knowledge(4, "list")
        assert calls == ["plan_create", "plan_list", "knowledge_save", "knowledge_list"]
        assert [frame["type"] for frame in frames] == ["command_result"] * 4
        assert "First plan" in frames[1]["output"]
        assert "item" in frames[3]["output"]
    finally:
        server._app_adapter.close()
        server._session_log.close()


def test_cli_slash_model_rag_clear_use_application_without_turn(tmp_path, capsys):
    from types import SimpleNamespace
    from local_cli.cli import _handle_application_slash_command
    from local_cli.config import Config
    from tests.test_nova_core_phase8_providers import Provider

    client, app, _ = _client(tmp_path, Provider())
    ctx = SimpleNamespace(config=Config(), current_mode="agent")
    try:
        for command in ("/model new", "/rag status", "/clear", "/status"):
            assert _handle_application_slash_command(command, client, ctx)
        state = app.get_snapshot(client.session_id)
        assert state.model == "new"
        assert state.turns == ()
        output = capsys.readouterr().out
        assert "Switched to model: new" in output
        assert "Conversation history cleared." in output
    finally:
        client.close()


def test_git_capability_unavailable_is_a_result_not_a_cli_failure():
    from local_cli.application.auxiliary import AuxiliaryServices

    result = AuxiliaryServices(git=None).execute("git_capability", {})
    assert result.data == {"capability": "UNAVAILABLE"}


def test_plan_review_uses_current_provider_without_adding_chat_turn(tmp_path):
    from local_cli.application.auxiliary import AuxiliaryServices
    from local_cli.application.providers import ProviderManager
    from local_cli.bootstrap_cli import create_plan_reviewer
    from local_cli.config import Config
    from local_cli.plan_manager import PlanManager
    from tests.test_nova_core_phase8_providers import Provider

    provider = Provider(steps=["Review complete"])
    manager = ProviderManager(provider, "local")
    config = Config()
    plans = PlanManager(plans_dir=str(tmp_path / "plans"))
    plan = plans.create_plan("Example")
    service = AuxiliaryServices(plans=plans, reviewer=create_plan_reviewer(
        provider_manager=manager, config=config, workspace=tmp_path))
    app = AgentSessionCoordinator(provider=provider, model="local",
        provider_manager=manager, tool_factory=lambda _: [],
        auxiliary_services=service, event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.START_SESSION, {"workspace": str(tmp_path)}))
    before = app.get_snapshot(started.session_id)
    result = app.execute_auxiliary(started.session_id, "plan_review",
                                   {"planId": plan.plan_id})
    after = app.get_snapshot(started.session_id)
    assert result.data["response"] == "Review complete"
    assert after.turns == () and after.transcript == before.transcript


def test_auxiliary_command_rejects_active_turn_without_running_service(tmp_path):
    import pytest
    from tests.test_nova_core_phase7_session import _BlockingProvider
    from local_cli.application.auxiliary import AuxiliaryConflict

    class Service:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("service ran during Turn")

    provider = _BlockingProvider()
    app = AgentSessionCoordinator(provider=provider, model="local",
        tool_factory=lambda _: [], auxiliary_services=Service(),
        event_config=EventBufferConfig())
    started = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.START_SESSION, {"workspace": str(tmp_path)}))
    turn = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.SUBMIT_USER_INPUT, {"content": "work"},
        session_id=started.session_id))
    assert provider.started.wait(2)
    try:
        with pytest.raises(AuxiliaryConflict, match="active Turn"):
            app.execute_auxiliary(started.session_id, "plan_list")
    finally:
        provider.release.set()
        assert app.wait_for_turn(turn.created_ids["turnId"], 5)


def test_server_legacy_git_frames_delegate_to_application(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from local_cli.application.auxiliary import AuxiliaryResult
    from local_cli.server import JsonLineServer

    server = JsonLineServer.__new__(JsonLineServer)
    server._app_adapter = SimpleNamespace(session_id="session")
    calls = []
    def execute(session_id, name, arguments):
        calls.append((session_id, name, arguments))
        return AuxiliaryResult(name, {"message": "undone"} if name == "undo"
                               else {"diff": "changes"})
    server._application = Mock(execute_auxiliary=execute)
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    server._handle_undo(1)
    server._handle_diff(2)
    assert calls == [("session", "undo", {"confirmed": True}),
                     ("session", "diff", {"color": False})]
    assert frames == [{"id": 1, "type": "undo", "data": {"message": "undone"}},
                      {"id": 2, "type": "diff", "data": {"diff": "changes"}}]


def test_cli_recovers_terminal_from_snapshot_when_journal_evicted_it(tmp_path):
    from local_cli.core.contracts import EventKind

    app = AgentSessionCoordinator(provider=ScriptedProvider(["finished"]), model="local",
        tool_factory=lambda _: [], event_config=EventBufferConfig(
            journal_capacity=2, consumer_queue_capacity=2))
    started = app.handle(ApplicationCommand(new_command_id(),
        CommandKind.START_SESSION, {"workspace": str(tmp_path)}))
    output = []
    client = CliApplicationClient(app, started.session_id, write=output.append)
    receipt = client.command(CommandKind.SUBMIT_USER_INPUT, {"content": "task"})
    assert app.wait_for_turn(receipt.created_ids["turnId"], 5)
    for index in range(4):
        app._events.publish(EventKind.HARNESS_INTERVENTION, {"rule": str(index)},
                            state_revision=app.get_snapshot(started.session_id).state_revision)
    try:
        outcome = client._wait_for_terminal(receipt.created_ids["turnId"], turn=True)
        assert outcome.status == "completed" and outcome.recovered_from_snapshot
        assert "Event history expired" in "".join(output)
        assert "finished" in "".join(output)
    finally:
        client.close()


def test_ideation_service_uses_current_provider_and_explicit_output_sink(tmp_path, capsys):
    from unittest.mock import Mock
    from local_cli.application.auxiliary import AuxiliaryServices
    from local_cli.application.providers import ProviderManager
    from local_cli.bootstrap_cli import create_cli_ideation_adapter
    from local_cli.config import Config
    from local_cli.ideation import IdeationEngine
    from tests.test_nova_core_phase8_providers import Provider

    provider = Provider(steps=["idea", "one shot"])
    manager = ProviderManager(provider, "old")
    stale_client = Mock()
    stale_client.chat_stream.side_effect = AssertionError("stale provider")
    history = IdeationEngine(stale_client)
    deltas = []
    adapter = create_cli_ideation_adapter(history=history, provider_manager=manager,
        config=Config(), workspace=tmp_path, output=lambda *args: deltas.append(args))
    service = AuxiliaryServices(ideation=adapter)
    manager.change_model("new")
    result = service.execute("ideate_chat", {"prompt": "brainstorm"}, model="old")
    assert result.data["response"] == "idea"
    before = list(history.get_history())
    once = service.execute("ideate_once", {"prompt": "another idea"}, model="old")
    assert once.data["response"] == "one shot"
    assert history.get_history() == before
    assert all(request[0] == "new" for request in provider.requests)
    assert all(not request[1].get("tools") for request in provider.requests)
    assert deltas == [("content", "idea"), ("content", "one shot")]
    assert capsys.readouterr().out == ""
    stale_client.chat_stream.assert_not_called()


@pytest.mark.parametrize("command,service,arguments,data", [
    ("/knowledge list", "knowledge_list", {"name": ""}, {"items": []}),
    ("/knowledge save notes", "knowledge_save", {"name": "notes"}, {}),
    ("/knowledge load notes", "knowledge_load", {"name": "notes"}, {}),
    ("/knowledge delete notes", "knowledge_delete", {"name": "notes"}, {}),
    ("/skills show python", "skills_show", {"name": "python"}, {"content": "skill text"}),
    ("/skills list", "skills_list", {}, {"skills": []}),
    ("/checkpoint point", "checkpoint", {"message": "point"}, {"tag": "tag"}),
    ("/rollback tag", "rollback", {"tag": "tag"}, {"tag": "tag"}),
    ("/diff", "diff", {}, {"diff": "diff"}),
    ("/undo", "undo", {}, {"message": "undone"}),
    ("/install local", "model_install", {"model": "local"}, {}),
    ("/uninstall local", "model_delete", {"model": "local"}, {}),
    ("/info local", "model_info", {"model": "local"}, {"info": {}}),
    ("/running", "model_running", {"model": ""}, {"models": []}),
    ("/brain local", "brain_set", {"model": "local"}, {"model": "local"}),
    ("/registry", "registry_get", {"model": ""}, {"configured": False}),
    ("/agents", "agents_list", {"model": ""}, {"agents": []}),
    ("/usage", "usage_get", {"model": ""}, {"table": "usage"}),
    ("/plan list", "plan_list", {"planId": ""}, {"plans": [], "activePlanId": None}),
])
def test_secondary_slash_parser_only_calls_application(command, service, arguments, data):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from local_cli.application.auxiliary import AuxiliaryResult
    from local_cli.cli import _handle_application_auxiliary
    from local_cli.config import Config

    console = Mock()
    console.execute_auxiliary.return_value = AuxiliaryResult(service, data)
    ctx = SimpleNamespace(config=Config(), current_mode="agent")
    assert _handle_application_auxiliary(command, console, ctx)
    console.execute_auxiliary.assert_called_once_with(service, arguments)


def test_cli_tool_preview_and_session_log_survive_application_migration(tmp_path, monkeypatch, capsys):
    import json
    from local_cli.application.providers import ProviderManager
    from local_cli.application.rag import RAGService
    from local_cli.cli import run_repl
    from local_cli.config import Config
    from local_cli.session_log import SessionLogger
    from local_cli.tools.read_tool import ReadTool
    from tests.test_nova_core_phase8_providers import Provider

    (tmp_path / "data.txt").write_text("file content", encoding="utf-8")
    read = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "read", "arguments": {"file_path": "data.txt"}},
    }]}
    provider = Provider(steps=[read, "final reply"])
    config = Config()
    config.state_dir, config.model, config.mascot = str(tmp_path / "state"), "old", "off"
    logger = SessionLogger(config.state_dir, cwd=str(tmp_path))
    monkeypatch.setattr("local_cli.cli.SessionLogger", lambda *_args, **_kwargs: logger)
    answers = iter(["read file", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    run_repl(config, object(), [ReadTool(cwd=tmp_path)],
             provider_manager=ProviderManager(provider, "old"), rag_service=RAGService(None))
    captured = capsys.readouterr()
    assert "Result:" in captured.err and "file content" in captured.err
    assert "final reply" in captured.out
    entries = [json.loads(line) for line in logger.path.read_text(encoding="utf-8").splitlines()]
    final = next(entry for entry in entries if entry["type"] == "turn_end")
    assert final["tool_calls"] == 1 and final["visible_chars"] == len("final reply")
    assert logger._fh is None
