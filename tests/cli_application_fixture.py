"""Test-only composition for old CLI observations over the supported API.

No legacy slash handler is copied here. All actions exercise Application and
the production CLI parser/renderer. This fixture is not shipped in local_cli.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from local_cli.application.auxiliary import AuxiliaryServices
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.persistence import PersistenceService
from local_cli.application.rag import RAGService
from local_cli.application.events import EventBufferConfig
from local_cli.cli import _handle_application_slash_command
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.cli_application import CliApplicationClient
from tests.test_nova_core_phase4_session import ScriptedProvider


class _ReplContext(SimpleNamespace):
    def __init__(self, config, client, tools, messages, session_manager, system_prompt, **services):
        super().__init__(config=config, client=client, tools=tools, messages=messages,
            session_manager=session_manager, system_prompt=system_prompt,
            current_mode="agent", cwd=Path.cwd(), context_budget=None,
            token_tracker=None, tool_cache=None, provider_manager=None,
            rag_service=None, git_ops=None, orchestrator=None, **{
                k: v for k, v in services.items() if k not in {
                    "token_tracker", "tool_cache", "provider_manager", "rag_service",
                    "git_ops", "orchestrator"}})
        self.__dict__.update(services)


def _handle_slash_command(command, ctx):
    if not hasattr(ctx, "_console"):
        config = getattr(ctx, "config", SimpleNamespace(mascot="off", model="local"))
        ctx.config = config
        ctx.current_mode = "agent"
        model = config.model if isinstance(config.model, str) else "local"
        services = AuxiliaryServices(git=getattr(ctx, "git_ops", None),
            token_tracker=getattr(ctx, "token_tracker", None),
            orchestrator=getattr(ctx, "orchestrator", None))
        workspace = Path(getattr(ctx, "cwd", Path.cwd())).resolve()
        messages = getattr(ctx, "messages", [{"role": "system", "content": "safe"}])
        persistence = PersistenceService(workspace=workspace, conversation=Mock(last_error=None), snapshots=Mock())
        app = AgentSessionCoordinator(provider=ScriptedProvider([]), model=model, event_config=EventBufferConfig(),
            provider_manager=getattr(ctx, "provider_manager", None),
            tool_factory=lambda _: getattr(ctx, "tools", []),
            initial_messages_factory=lambda _w, _t: [m for m in messages if m.get("role") == "system"] or [{"role": "system", "content": getattr(ctx, "system_prompt", "safe")}],
            auxiliary_services=services, persistence_factory=lambda _: persistence,
            rag_factory=lambda _: getattr(ctx, "rag_service", None) or RAGService(None))
        receipt = app.handle(ApplicationCommand(command_id=new_command_id(),
            kind=CommandKind.START_SESSION, payload={"workspace": str(workspace)}))
        assert receipt.accepted
        app._session.transcript.extend(m for m in messages if m.get("role") != "system")
        ctx._console = CliApplicationClient(app, receipt.session_id)
    result = _handle_application_slash_command(command, ctx._console, ctx,
        context_budget=getattr(ctx, "context_budget", None))
    if hasattr(ctx, "messages"):
        ctx.messages[:] = ctx._console.snapshot().transcript
    return result
