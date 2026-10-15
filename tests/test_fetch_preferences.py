"""Optional fetch preference: host controls, temporary settings, mocked HTTP only."""

from dataclasses import replace
from threading import Event
from unittest.mock import Mock

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.network import NetworkFetchService
from local_cli.application.session import AgentOperation, AgentSessionCoordinator
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.contracts import ToolStatus, new_command_id
from local_cli.fetch_config import CONFIG_FILENAME, load_fetch_enabled, save_fetch_enabled
from local_cli.network_config import DEFAULT_FETCH_LIMITS
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.web_fetch_tool import WebFetchTool
from tests.security_v12.network_fixtures import ScriptedHTTPPort
from tests.security_v12.process_fixtures import bind_mock_shell
from tests.security_v12.test_s2_policy import invocation
from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit


def _toggle(coordinator, session_id, enabled):
    return coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.SET_FETCH_ENABLED,
        session_id=session_id, payload={"enabled": enabled},
    ))


def _tools(workspace, port):
    executor = Mock()
    shell = BashTool(
        descriptor=ShellDescriptor("Windows", "powershell", str(workspace / "fake-pwsh.exe"), "7"),
        executor=executor, cwd=workspace, environment={},
    )
    return [bind_mock_shell(shell, executor), WebFetchTool(http_broker=port)]


def _coordinator(workspace, **kwargs):
    port = ScriptedHTTPPort()
    return AgentSessionCoordinator(
        provider=ScriptedProvider([]), model="local",
        tool_factory=lambda cwd: _tools(cwd, port),
        prompt_factory=lambda tools, cwd: "tools: " + ", ".join(tool.name for tool in tools),
        network_service=NetworkFetchService(port, DEFAULT_FETCH_LIMITS),
        **kwargs,
    )


def test_missing_settings_default_on_without_creating_state_directory(tmp_path):
    state_dir = tmp_path / "new-state"
    assert load_fetch_enabled(state_dir) is True
    assert not state_dir.exists()


@pytest.mark.parametrize("enabled", [False, True])
def test_explicit_preference_round_trips(tmp_path, enabled):
    state_dir = tmp_path / "state"
    save_fetch_enabled(state_dir, enabled)
    assert load_fetch_enabled(state_dir) is enabled
    assert [path.name for path in state_dir.iterdir()] == [CONFIG_FILENAME]


@pytest.mark.parametrize("payload", [
    "not JSON",
    '{"schema":"NOVA_FETCH_PREFERENCE_V1","enabled":1}',
    '{"schema":"unknown","enabled":true}',
    '{"schema":"NOVA_FETCH_PREFERENCE_V1","enabled":true,"extra":true}',
])
def test_malformed_settings_fail_closed_without_rewriting(tmp_path, payload):
    path = tmp_path / CONFIG_FILENAME
    path.write_text(payload, encoding="utf-8")
    assert load_fetch_enabled(tmp_path) is False
    assert path.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize("payload", [
    {}, {"enabled": None}, {"enabled": 0}, {"enabled": "false"},
    {"enabled": False, "url": "https://example.test/"},
])
def test_toggle_command_requires_only_an_exact_boolean(payload):
    with pytest.raises(ValueError):
        ApplicationCommand(
            command_id=new_command_id(), kind=CommandKind.SET_FETCH_ENABLED,
            session_id="session", payload=payload,
        )


def test_default_session_exposes_fetch_and_toggle_updates_model_catalog(tmp_path):
    catalogs = []
    saved = []

    def runner(provider, model, tools, messages, **kwargs):
        catalogs.append(tuple(tool.name for tool in tools))
        messages.append({"role": "assistant", "content": "done"})
        return "done"

    coordinator = _coordinator(tmp_path, run_agent_fn=runner, fetch_enabled_save=saved.append)
    session_id = start(coordinator, tmp_path).session_id
    shell = next(tool for tool in coordinator._session.tools if tool.name == "bash")
    try:
        for enabled in (True, False, True):
            if enabled != coordinator.get_snapshot(session_id).services["fetch"]["enabled"]:
                assert _toggle(coordinator, session_id, enabled).accepted
            snapshot = coordinator.get_snapshot(session_id)
            assert snapshot.services["fetch"] == {"enabled": enabled, "available": enabled}
            assert ("web_fetch" in [tool.name for tool in coordinator._session.tools]) is enabled
            assert next(tool for tool in coordinator._session.tools if tool.name == "bash") is shell
            assert ("web_fetch" in snapshot.transcript[0]["content"]) is enabled
            turn = submit(coordinator, session_id, "check tools")
            assert turn.accepted and coordinator.wait_for_turn(turn.created_ids["turnId"], timeout=5)
        assert ["web_fetch" in names for names in catalogs] == [True, False, True]
        assert all("bash" in names for names in catalogs)
        assert saved == [False, True]
    finally:
        coordinator._session.tool_runtime.close()


def test_saved_off_starts_without_fetch_and_can_restore_it(tmp_path):
    state_dir = tmp_path / "state"
    save_fetch_enabled(state_dir, False)
    coordinator = _coordinator(
        tmp_path, fetch_enabled=load_fetch_enabled(state_dir),
        fetch_enabled_save=lambda enabled: save_fetch_enabled(state_dir, enabled),
    )
    session_id = start(coordinator, tmp_path).session_id
    try:
        assert coordinator.get_snapshot(session_id).services["fetch"] == {"enabled": False, "available": False}
        assert "web_fetch" not in [tool.name for tool in coordinator._session.tools]
        assert "bash" in [tool.name for tool in coordinator._session.tools]
        assert _toggle(coordinator, session_id, True).accepted
        assert load_fetch_enabled(state_dir) is True
        assert "web_fetch" in [tool.name for tool in coordinator._session.tools]
    finally:
        coordinator._session.tool_runtime.close()


def test_workspace_change_preserves_disabled_fetch_in_rebuilt_prompt(tmp_path):
    target = tmp_path / "other-workspace"
    target.mkdir()
    coordinator = _coordinator(tmp_path, workspace_rebinder=lambda workspace: {
        "base_messages": [{"role": "system", "content": "TOOLS:web_fetch,bash"}],
        "persistence": None, "rag": None, "data": {"workspace": str(workspace)},
    })
    session_id = start(coordinator, tmp_path).session_id
    try:
        assert _toggle(coordinator, session_id, False).accepted
        coordinator.change_workspace(session_id, str(target))
        snapshot = coordinator.get_snapshot(session_id)
        assert snapshot.workspace == str(target.resolve())
        assert snapshot.services["fetch"] == {"enabled": False, "available": False}
        assert "web_fetch" not in snapshot.transcript[0]["content"]
        assert "web_fetch" not in coordinator._session.base_transcript[0]["content"]
        assert "web_fetch" not in [tool.name for tool in coordinator._session.tools]
        assert coordinator._session.tool_runtime.fetch_enabled is False
    finally:
        coordinator._session.tool_runtime.close()


def test_fetch_off_denies_direct_runtime_before_dns_or_http_and_on_restores(tmp_path):
    port = ScriptedHTTPPort()
    runtime = ToolRuntime(ToolRegistry([WebFetchTool(http_broker=port)]), fetch_enabled=False)
    try:
        request = invocation(tmp_path, "web_fetch", {"url": "https://example.test/a"})
        denied = runtime.execute(request)
        assert denied.status is ToolStatus.DENIED
        assert denied.metadata["securityErrorCode"] == "FETCH_DISABLED"
        assert not port.resolutions and not port.gets
        revision = runtime.policy.revision
        runtime.set_fetch_enabled(True)
        assert runtime.policy.revision > revision
        fresh = replace(request, tool_call_id="enabled-call", operation_id="enabled-operation",
                        context=replace(request.context, operation_id="enabled-operation",
                                        policy_revision=runtime.policy.revision))
        assert runtime.execute(fresh).status is ToolStatus.COMPLETED
        assert len(port.gets) == 1
        revision = runtime.policy.revision
        runtime.set_fetch_enabled(False)
        assert runtime.policy.revision > revision
    finally:
        runtime.close()


def test_toggle_rejects_active_turn_without_saving_or_changing_state(tmp_path):
    entered, release = Event(), Event()
    saved = []

    def runner(provider, model, tools, messages, **kwargs):
        entered.set()
        assert release.wait(5)
        messages.append({"role": "assistant", "content": "done"})
        return "done"

    coordinator = _coordinator(tmp_path, run_agent_fn=runner, fetch_enabled_save=saved.append)
    session_id = start(coordinator, tmp_path).session_id
    turn = submit(coordinator, session_id, "hold")
    try:
        assert entered.wait(5)
        receipt = _toggle(coordinator, session_id, False)
        assert not receipt.accepted and receipt.error.code == "CONFLICT_ACTIVE_OPERATION"
        assert coordinator.get_snapshot(session_id).services["fetch"]["enabled"] is True
        assert not saved
    finally:
        release.set()
        assert coordinator.wait_for_turn(turn.created_ids["turnId"], timeout=5)
        coordinator._session.tool_runtime.close()


def test_toggle_rejects_active_subagent_without_saving_or_changing_state(tmp_path):
    saved = []
    coordinator = _coordinator(tmp_path, fetch_enabled_save=saved.append)
    session_id = start(coordinator, tmp_path).session_id
    operation = AgentOperation("child-operation", "parent-turn", Mock())
    coordinator._session.agent_operations["child"] = operation
    try:
        receipt = _toggle(coordinator, session_id, False)
        assert not receipt.accepted and receipt.error.code == "CONFLICT_ACTIVE_OPERATION"
        assert coordinator.get_snapshot(session_id).services["fetch"]["enabled"] is True
        assert not saved
    finally:
        operation.done.set()
        coordinator._session.tool_runtime.close()


def test_persistence_failure_keeps_runtime_catalog_and_revision(tmp_path):
    save = Mock(side_effect=OSError("fixture disk failure"))
    coordinator = _coordinator(tmp_path, fetch_enabled_save=save)
    session_id = start(coordinator, tmp_path).session_id
    before = coordinator.get_snapshot(session_id)
    runtime = coordinator._session.tool_runtime
    policy_revision = runtime.policy.revision
    try:
        receipt = _toggle(coordinator, session_id, False)
        assert not receipt.accepted and receipt.error.code == "FETCH_CONFIGURATION_FAILED"
        save.assert_called_once_with(False)
        after = coordinator.get_snapshot(session_id)
        assert after.services["fetch"] == before.services["fetch"]
        assert after.state_revision == before.state_revision
        assert after.transcript == before.transcript
        assert runtime.fetch_enabled is True and runtime.policy.revision == policy_revision
        assert "web_fetch" in [tool.name for tool in coordinator._session.tools]
    finally:
        runtime.close()
