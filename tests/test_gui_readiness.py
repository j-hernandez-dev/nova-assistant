"""Desktop readiness observes host facts without inference or authority changes."""

from datetime import datetime
from threading import Event, Thread
from unittest.mock import Mock

import pytest

from local_cli.application.events import EventBufferConfig
from local_cli.application.providers import ProviderManager
from local_cli.application.session import AgentSessionCoordinator
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.providers.base import ProviderConnectionError
from tests.test_nova_core_phase4_session import start


class ReadinessProvider:
    name = "ollama"

    def __init__(self, *, models=None, capabilities=None, failure=None):
        self.models = models if models is not None else [{"name": "local:chat", "size": 1024}]
        self.capabilities = capabilities if capabilities is not None else ["completion", "tools"]
        self.failure = failure
        self.list_calls = 0
        self.info_calls = []
        self.before_info = lambda: None

    def list_models(self):
        self.list_calls += 1
        if self.failure:
            raise self.failure
        return self.models

    def get_model_info(self, model):
        self.info_calls.append(model)
        self.before_info()
        return {"capabilities": self.capabilities, "model_info": {"test.context_length": 8192}}

    def chat_stream(self, *args, **kwargs):
        pytest.fail("Readiness must not invoke inference")


def application(tmp_path, provider=None, model="local:chat"):
    provider = provider or ReadinessProvider()
    manager = ProviderManager(provider, model, clone_factory=lambda _provider: None)
    app = AgentSessionCoordinator(provider=provider, model=model, provider_manager=manager,
        tool_factory=lambda _workspace: [], event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    return app, session_id, provider, manager


def test_readiness_compatible_local_model_and_optional_services_do_not_gate_chat(tmp_path):
    app, session_id, provider, manager = application(tmp_path)
    original = manager.snapshot()
    before = app.get_snapshot(session_id)
    result = app.get_readiness(session_id)
    assert result == {"schemaVersion": 1, "sessionId": session_id, "providerId": "ollama",
        "modelId": "local:chat", "providerRevision": 1, "ready": True, "reason": None,
        "observedAt": result["observedAt"], "installedModels": [{"name": "local:chat", "size": 1024}],
        "requiredAction": None}
    assert datetime.fromisoformat(result["observedAt"]).utcoffset() is not None
    after = app.get_snapshot(session_id)
    assert manager.snapshot() is original
    assert after.state_revision == before.state_revision
    assert after.transcript == before.transcript and after.turns == ()
    assert not after.services["rag"]["enabled"]
    assert provider.list_calls == 1 and provider.info_calls == ["local:chat"]


@pytest.mark.parametrize("provider,reason,action", [
    (ReadinessProvider(failure=ProviderConnectionError("private endpoint detail")), "OLLAMA_UNAVAILABLE", None),
    (ReadinessProvider(models=[]), "NO_MODELS_INSTALLED", "SELECT_MODEL"),
    (ReadinessProvider(models=[{"name": "other:chat"}]), "MODEL_NOT_INSTALLED", "SELECT_MODEL"),
    (ReadinessProvider(capabilities=["embedding"]), "MODEL_NOT_CHAT_CAPABLE", "SELECT_MODEL"),
    (ReadinessProvider(capabilities="tools"), "MODEL_VALIDATION_FAILED", "SELECT_MODEL"),
    (ReadinessProvider(models=[{"name": "local:chat", "size": -1}]), "MODEL_VALIDATION_FAILED", "SELECT_MODEL"),
    (ReadinessProvider(models=[{"name": None}]), "MODEL_VALIDATION_FAILED", "SELECT_MODEL"),
    (ReadinessProvider(failure=RuntimeError("raw private payload")), "MODEL_VALIDATION_FAILED", "SELECT_MODEL"),
])
def test_readiness_reports_exact_block_without_private_provider_text(tmp_path, provider, reason, action):
    app, session_id, _, manager = application(tmp_path, provider)
    original = manager.snapshot()
    result = app.get_readiness(session_id)
    assert result["ready"] is False and result["reason"] == reason and result["requiredAction"] == action
    assert "private" not in repr(result)
    assert manager.snapshot() is original


def test_readiness_other_provider_is_truthfully_unverified_and_does_not_probe(tmp_path):
    provider = ReadinessProvider()
    provider.name = "claude"
    app, session_id, _, _ = application(tmp_path, provider)
    result = app.get_readiness(session_id)
    assert result["reason"] == "PROVIDER_UNVERIFIED" and not result["ready"]
    assert result["requiredAction"] == "CONFIGURE_PROVIDER"
    assert provider.list_calls == 0 and provider.info_calls == []


def test_completion_only_model_is_ready_without_inference_or_tool_authority(tmp_path):
    provider = ReadinessProvider(capabilities=["completion"])
    app, session_id, _, manager = application(tmp_path, provider)
    original = manager.snapshot()
    before = app.get_snapshot(session_id)
    assert app.get_readiness(session_id)["ready"] is True
    after = app.get_snapshot(session_id)
    assert manager.snapshot() is original and original.snapshot.tool_support == "UNKNOWN"
    assert before.turns == after.turns == ()
    assert before.state_revision == after.state_revision
    assert after.services["interactions"]["approvals"] == []


def test_wrong_session_rejected_without_provider_io(tmp_path):
    app, _, provider, _ = application(tmp_path)
    with pytest.raises(ValueError, match="No matching active AgentSession"):
        app.get_readiness("another-session")
    assert provider.list_calls == 0


def test_readiness_during_inflight_preserves_pinned_runtime_and_never_touches_authority(tmp_path):
    app, session_id, provider, manager = application(tmp_path)
    pinned = manager.begin_turn("owned-inflight-turn")
    runtime = app._session.tool_runtime
    original_policy, original_approval, original_issuer = runtime.policy, runtime._approval_gate, runtime._issuer
    runtime.policy = Mock(side_effect=AssertionError("No Policy operation expected"))
    runtime._approval_gate = Mock(side_effect=AssertionError("No Approval operation expected"))
    runtime._issuer = Mock(side_effect=AssertionError("No Grant operation expected"))
    result = app.get_readiness(session_id)
    assert not runtime.policy.mock_calls and not runtime._approval_gate.mock_calls and not runtime._issuer.mock_calls
    runtime.policy, runtime._approval_gate, runtime._issuer = original_policy, original_approval, original_issuer
    assert result["ready"]
    assert manager.snapshot() is pinned
    assert pinned.snapshot.provider_revision == 1
    assert pinned.snapshot.health == "UNKNOWN"
    manager.end_turn("owned-inflight-turn")


def test_provider_switch_during_probe_is_stale_without_mutating_new_identity(tmp_path):
    provider = ReadinessProvider(models=[{"name": "local:chat"}, {"name": "other:chat"}])
    app, session_id, _, manager = application(tmp_path, provider)
    entered, release = Event(), Event()

    def wait_once():
        if not entered.is_set():
            entered.set()
            assert release.wait(5)

    provider.before_info = wait_once
    results = []
    thread = Thread(target=lambda: results.append(app.get_readiness(session_id)))
    thread.start()
    try:
        assert entered.wait(5)
        manager.change_model("other:chat")
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert results[0]["reason"] == "READINESS_STALE" and not results[0]["ready"]
    assert results[0]["installedModels"] == []
    assert manager.snapshot().snapshot.model_id == "other:chat"
    assert manager.snapshot().snapshot.provider_revision == 2


def test_jsonl_get_readiness_uses_application_and_rejects_user_claimed_authority(tmp_path):
    app, session_id, provider, _ = application(tmp_path)
    sent = []
    delivered = Event()
    def receive(frame):
        sent.append(frame)
        delivered.set()
    adapter = JsonlApplicationAdapter(app, session_id, receive)
    assert adapter.handle({"id": "probe", "type": "get_readiness", "sessionId": session_id,
                           "ready": True, "available": True, "providerId": "forged"})
    assert delivered.wait(5)
    assert sent[-1]["type"] == "readiness" and sent[-1]["id"] == "probe"
    assert sent[-1]["data"]["providerId"] == "ollama"
    assert provider.list_calls == 1
    assert adapter.handle({"id": "wrong", "type": "get_readiness", "sessionId": "wrong"})
    assert sent[-1]["code"] == "INVALID_SESSION" and provider.list_calls == 1


def test_jsonl_probe_is_singleflight_and_does_not_block_other_requests(tmp_path):
    app, session_id, provider, _ = application(tmp_path)
    entered, release, delivered = Event(), Event(), Event()
    def wait_info():
        entered.set()
        assert release.wait(5)
    provider.before_info = wait_info
    sent = []
    def receive(frame):
        sent.append(frame)
        if frame["type"] == "readiness":
            delivered.set()
    adapter = JsonlApplicationAdapter(app, session_id, receive)
    try:
        assert adapter.handle({"id": "first", "type": "get_readiness"})
        assert entered.wait(5)
        assert adapter.handle({"id": "second", "type": "get_readiness"})
        assert sent[-1]["code"] == "READINESS_BUSY"
        assert adapter.handle({"id": "status", "type": "status"})
        assert sent[-1]["type"] == "status"
        assert provider.list_calls == 1
    finally:
        release.set()
    assert delivered.wait(5)


def test_readiness_observation_does_not_select_model_or_start_turn(tmp_path):
    app, session_id, _, _ = application(tmp_path, model="not-installed")
    before = app.get_snapshot(session_id)
    result = app.get_readiness(session_id)
    after = app.get_snapshot(session_id)
    assert result["reason"] == "MODEL_NOT_INSTALLED"
    assert after.model == before.model == "not-installed"
    assert after.state_revision == before.state_revision
    assert after.turns == () and after.services["interactions"]["approvals"] == []
