"""Single AgentSession and transport-neutral session/event commands.

CLI and JSONL server keep their legacy paths while this coordinator is
characterized against run_agent. Phase-7 interactions are owned here.
"""

from __future__ import annotations

from local_cli.application.web_permissions import permitted_web_tools

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Any, Callable, Mapping
from uuid import uuid4

from local_cli.application.message_dates import saved_with_dates, restored_with_dates, display_dates
from local_cli.application.commands import (
    ApplicationCommand, ApplicationError, CommandKind, CommandReceipt,
    ErrorCategory,
)
from local_cli.application.legacy_runtime import LegacyAgentRuntime
from local_cli.application.providers import ProviderManager, ProviderTransitionError, BoundModelRuntime
from local_cli.application.context import bind_context, WorkingMessages as _WorkingMessages
from local_cli.application.memory_recall import (MemoryRetriever, TurnMemorySnapshot,
    admit_capsule, local_memory_destination)
from local_cli.core.memory import MemoryError,MemoryErrorCode
from local_cli.application.persistence import PersistenceService
from local_cli.application.environment import EnvironmentService
from local_cli.application.rag import RAGService
from local_cli.core.persistence import PersistenceError
from local_cli.core.security_audit import SecurityAuditError
from local_cli.core.context import ContextPolicy
from local_cli.infrastructure.capabilities import capture_capabilities
from local_cli.application.cancellation import CancellationController
from local_cli.application.interactions import (
    ApprovalGate, ApprovalRequest, InteractionError, UserInputGate,
    UserInputRequest,
)
from local_cli.application.events import EventBufferConfig, EventCursor, SessionEventStream
from local_cli.application.tool_runtime import (
    LegacyToolAdapter, ToolEvent, ToolRegistry, ToolRuntime,
)
from local_cli.application.process import TOOL_OUTPUT_BYTES
from local_cli.legacy_contracts import tool_result_to_legacy_text
from local_cli.core.contracts import (
    CausationId, CommandId, EventEnvelope, EventKind, GenerationId, OperationId,
    OperationStatus, OperationType, RuntimeCapabilitySnapshot, SessionId,
    TurnId, TurnStatus, ExecutionContext, Visibility,
    advance_operation_status, advance_turn_status, new_operation_id,
    new_generation_id, new_session_id, new_turn_id, operation_terminal_kind,
    AgentId, new_agent_id,
)
from local_cli.core.runtime import AgentRuntimePort, TurnOutcome
from local_cli.harness import AgentEvent, HarnessConfig
from local_cli.prompts import build_system_prompt
from local_cli.security import get_sanitized_env
from local_cli.tools.shell_tool import ShellTool
from local_cli.sub_agent import SubAgent, SubAgentResult, SubAgentRunner


TOOL_ARGUMENT_BYTES = 8 * 1024


@dataclass
class ToolOperation:
    token: CancellationController
    status: OperationStatus = OperationStatus.REQUESTED


@dataclass
class AgentOperation:
    operation_id: OperationId
    parent_turn_id: TurnId
    runner: SubAgentRunner
    status: OperationStatus = OperationStatus.RUNNING
    done: Event = field(default_factory=Event, repr=False)


@dataclass
class ServiceOperation:
    operation_id: OperationId
    command_id: CommandId
    token: CancellationController = field(default_factory=CancellationController)
    status: OperationStatus = OperationStatus.RUNNING
    turn_id: TurnId | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    done: Event = field(default_factory=Event)
    service: str = 'rag'
    deadline: datetime | None = None


@dataclass
class Turn:
    turn_id: TurnId
    operation_id: OperationId
    command_id: CommandId
    model_runtime: BoundModelRuntime | None = field(default=None, repr=False)
    generations: dict[str, dict[str, Any]] = field(default_factory=dict)
    context_reports: list[dict[str, Any]] = field(default_factory=list)
    memory_snapshot: TurnMemorySnapshot | None = field(default=None, repr=False)
    knowledge_admission: Any = field(default=None, repr=False)
    attachment_refs: tuple = field(default=(), repr=False)
    citation_reports: list[dict[str, Any]] = field(default_factory=list)
    effect_constraints: Any = field(default=None, repr=False)
    # Ephemeral owner-facing execution projection; never a second transcript,
    # prompt source, durable journal or renderer-owned lifecycle.
    display_messages: list[dict[str, Any]] = field(default_factory=list)
    tool_activities: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    user_message: dict[str, Any] | None = field(default=None, repr=False)
    transcript_start: int = 0
    transcript_end: int | None = None
    capabilities: RuntimeCapabilitySnapshot | None = field(default=None, repr=False)
    status: TurnStatus = TurnStatus.RUNNING
    operation_status: OperationStatus = OperationStatus.RUNNING
    final_content: str = ""
    error_code: str | None = None
    terminal_count: int = 0
    cancellation: CancellationController = field(default_factory=CancellationController,
                                                 repr=False)
    tool_operations: dict[OperationId, ToolOperation] = field(default_factory=dict,
                                                                repr=False)
    active_generation: GenerationId | None = None
    stop_generation_requested: bool = False
    has_unknown_effect: bool = False
    done: Event = field(default_factory=Event, repr=False)
    memory_capture: tuple | None = field(default=None,repr=False)


@dataclass
class AgentSession:
    session_id: SessionId
    workspace: Path
    model: str
    tools: list[Any]
    transcript: list[dict[str, Any]]
    base_transcript: list[dict[str, Any]] = field(default_factory=list)
    restored_display_dates: dict[int, dict[str, str]] = field(default_factory=dict, repr=False)
    installed_tools: list[Any] = field(default_factory=list, repr=False)
    environment: dict[str, str] = field(default_factory=dict)
    capabilities: RuntimeCapabilitySnapshot | None = field(default=None, repr=False)
    tool_runtime: ToolRuntime | None = field(default=None, repr=False)
    approval_gate: ApprovalGate | None = field(default=None, repr=False)
    user_input_gate: UserInputGate | None = field(default=None, repr=False)
    agent_operations: dict[str, AgentOperation] = field(default_factory=dict,
                                                             repr=False)
    state_revision: int = 1
    filesystem_revision: int = 0
    turns: list[Turn] = field(default_factory=list)
    status: str = "active"


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: SessionId
    workspace: str
    model: str
    status: str
    state_revision: int
    last_sequence: int
    transcript: tuple[dict[str, Any], ...]
    turns: tuple[dict[str, Any], ...]
    model_runtime: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id, "workspace": self.workspace,
            "model": self.model, "status": self.status,
            "stateRevision": self.state_revision,
            "lastSequence": self.last_sequence,
            "transcript": deepcopy(list(self.transcript)),
            "turns": deepcopy(list(self.turns)),
            "modelRuntime": deepcopy(self.model_runtime),
            "capabilities": deepcopy(self.capabilities),
            "services": deepcopy(self.services),
        }


class AgentSessionCoordinator:
    """Own exactly one main session and serialize its state transitions."""

    def __init__(
        self, *, provider: Any, model: str,
        tool_factory: Callable[[Path], list[Any]],
        prompt_factory: Callable[[list[Any], Path], str] | None = None,
        runtime: AgentRuntimePort | None = None,
        run_agent_fn: Callable[..., str] | None = None,
        harness: HarnessConfig | None = None,
        event_config: EventBufferConfig | None = None,
        auto_approve: bool = False,
        interaction_deadline_factory: Callable[[], datetime | None] | None = None,
        human_response_deadline_factory: Callable[[], datetime | None] | None = None,
        provider_manager: ProviderManager | None = None,
        provider_factory: Callable[[str], Any] | None = None,
        context_selection: str | int = "AUTO",
        context_policy: ContextPolicy = ContextPolicy(),
        capability_factory: Callable = capture_capabilities,
        persistence_factory: Callable[[Path], PersistenceService] | None = None,
        rag_factory: Callable[[Path], RAGService] | None = None,
        initial_messages_factory: Callable[[Path, list[Any]], list[dict[str, Any]]] | None = None,
        turn_messages_factory: Callable[[str], list[dict[str, Any]]] | None = None,
        inference_options_factory: Callable[[], dict[str, Any]] | None = None,
        sub_agent_runner: SubAgentRunner | None = None,
        sub_agent_tool_factory: Callable[[Path], list[Any]] | None = None,
        auxiliary_services: Any = None,
        refresh_base_factory: Callable[[Path, list[Any]], list[dict[str, Any]]] | None = None,
        workspace_rebinder: Any = None,
        process_service: Any = None,
        network_service: Any = None,
        environment_selector: Any = None, environment_source: Any = None,
        security_audit_port: Any = None,
        memory_factory: Any = None,
        knowledge_factory: Any = None,
        memory_capture_mode: str = 'off',
        memory_preferences: Any = None,
        memory_extractor_factory: Any = None,
        search_enabled: bool = True, browser_enabled: bool = True,
        web_engine: str = 'google', web_browser: str = 'webview2',
        web_settings_save: Callable[[dict], None] | None = None,
        fetch_enabled: bool = True,
        fetch_enabled_save: Callable[[bool], None] | None = None,
        context_selection_save: Callable[[int], None] | None = None,
        embedding_settings=None,
    ) -> None:
        if type(fetch_enabled) is not bool:
            raise ValueError('Fetch enabled must be true or false')
        if type(search_enabled) is not bool or type(browser_enabled) is not bool:
            raise ValueError('Web permissions must be boolean')
        self._search_enabled, self._browser_enabled = search_enabled, browser_enabled
        if web_engine not in ('google', 'bing', 'duckduckgo') or web_browser not in ('webview2', 'chrome', 'edge'):
            raise ValueError('Invalid web selection')
        self._web_engine, self._web_browser = web_engine, web_browser
        self._web_settings_save = web_settings_save
        self._fetch_enabled = fetch_enabled
        self._fetch_enabled_save = fetch_enabled_save
        if runtime is not None and run_agent_fn is not None:
            raise ValueError("pass either runtime or a legacy runner")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be non-empty")
        if provider_factory is None:
            from local_cli.providers import get_provider
            provider_factory = get_provider
        self.provider_manager = provider_manager or ProviderManager(
            provider, model, provider_factory=provider_factory)
        self.redactor = self.provider_manager.redactor
        from local_cli.application.security_audit import SecurityAuditService
        # Composition roots install the OD-05 durable port. Direct embedding
        # can inject a fixture; Application never chooses an on-disk format.
        self.security_audit = (SecurityAuditService(security_audit_port, redactor=self.redactor)
                               if security_audit_port is not None else None)
        from local_cli.infrastructure.process_environment import EnvironmentBuilder
        self._environment_service = EnvironmentService(EnvironmentBuilder(
            protected_value=self.redactor.protected_value), self.redactor, source=environment_source)
        self._environment_selector = environment_selector
        self._tool_factory = tool_factory
        self._process_service = process_service
        self._network_service = network_service
        self._context_selection, self._context_policy = context_selection, context_policy
        self._context_selection_save = context_selection_save
        self._embedding_settings = embedding_settings
        self._capability_factory = capability_factory
        self._persistence_factory, self._rag_factory = persistence_factory, rag_factory
        self._initial_messages_factory = initial_messages_factory
        self._turn_messages_factory = turn_messages_factory
        self._inference_options_factory = inference_options_factory
        self._sub_agent_runner = sub_agent_runner
        self._sub_agent_tool_factory = sub_agent_tool_factory
        self._auxiliary_services = auxiliary_services
        self._refresh_base_factory = refresh_base_factory
        self._workspace_rebinder = workspace_rebinder
        self._persistence: PersistenceService | None = None
        self._persistence_setup_error: str | None = None
        self._rag = RAGService(None)
        self._service_operations: dict[OperationId, ServiceOperation] = {}
        self._prompt_factory = prompt_factory or (
            lambda tools, cwd: build_system_prompt(tools, cwd=cwd)
        )
        self._runtime = runtime or (LegacyAgentRuntime(run_agent_fn, harness)
                                    if run_agent_fn is not None else LegacyAgentRuntime(harness=harness))
        self._lock = RLock()
        self._session: AgentSession | None = None
        self._event_config = event_config
        self._auto_approve = auto_approve
        self._interaction_deadline_factory = interaction_deadline_factory or (lambda: None)
        self._human_response_deadline_factory = human_response_deadline_factory
        self._events: SessionEventStream | None = None
        self._receipts: dict[CommandId, tuple[str, CommandReceipt]] = {}
        self._memory_factory, self._memory = memory_factory, None
        from local_cli.application.knowledge_host import KnowledgeHostControls
        self._knowledge = KnowledgeHostControls(self, knowledge_factory)
        self._knowledge_preferences = getattr(knowledge_factory, 'preferences', None)
        if self._knowledge_preferences is not None: knowledge_factory.on_change = self._knowledge_index_changed
        self._memory_actors = {}
        self._browser_actors = {}
        self._browser_control_result = {}
        self._memory_receipts = {}  # Digests + mutation summaries only, never recall/content cache.
        if memory_capture_mode not in ('off','propose_only','low_risk'):
            raise ValueError('Invalid memory capture mode')
        self._memory_capture_mode=memory_capture_mode
        self._memory_preferences=memory_preferences
        if memory_preferences is not None:
            value=memory_preferences.snapshot()
            self._memory_capture_mode=value['captureMode'] if value['autoCapture'] else 'off'
        self._memory_extractor_factory=memory_extractor_factory
        self._memory_worker=None

    def handle(self, command: ApplicationCommand) -> CommandReceipt | SessionSnapshot | EventCursor:
        """Handle the session API; future phases add other services."""
        if command.kind is CommandKind.GET_SNAPSHOT:
            try:
                return self.get_snapshot(command.session_id)
            except ValueError:
                return self._reject(command, "INVALID_SESSION",
                                    "No matching active AgentSession")
        if command.kind is CommandKind.SUBSCRIBE_EVENTS:
            try:
                return self.subscribe_events(
                    command.session_id,
                    after_sequence=command.payload.get("afterSequence", 0),
                )
            except ValueError:
                return self._reject(command, "INVALID_EVENT_CURSOR",
                                    "Session or event cursor is invalid")
        fingerprint = json.dumps(command.to_dict(), ensure_ascii=False,
                                 sort_keys=True, separators=(",", ":"))
        with self._lock:
            previous = self._receipts.get(command.command_id)
            if previous is not None:
                if previous[0] == fingerprint:
                    return previous[1]
                return self._reject(command, "IDEMPOTENCY_CONFLICT",
                                    "commandId was already used with different input")
            if command.kind is CommandKind.START_SESSION:
                receipt = self._start_session(command)
            elif command.kind is CommandKind.SUBMIT_USER_INPUT:
                receipt = self._start_turn(command)
            elif command.kind is CommandKind.RESOLVE_APPROVAL:
                receipt = self._resolve_approval(command)
            elif command.kind is CommandKind.RESOLVE_USER_INPUT:
                receipt = self._resolve_user_input(command)
            elif command.kind is CommandKind.CANCEL_TURN:
                receipt = self._cancel_turn(command)
            elif command.kind is CommandKind.STOP_GENERATION:
                receipt = self._stop_generation(command)
            elif command.kind is CommandKind.CANCEL_OPERATION:
                receipt = self._cancel_operation(command)
            elif command.kind is CommandKind.CANCEL_SUB_AGENT:
                receipt = self._cancel_sub_agent(command)
            elif command.kind is CommandKind.START_SUB_AGENT:
                receipt = self._start_sub_agent(command)
            elif command.kind in (CommandKind.CHANGE_MODEL, CommandKind.CHANGE_PROVIDER):
                receipt = self._change_model_runtime(command)
            elif command.kind in (CommandKind.SET_RAG_ENABLED, CommandKind.QUERY_RAG,
                                  CommandKind.GET_RAG_STATUS):
                receipt = self._rag_command(command)
            elif command.kind is CommandKind.EXECUTE_COMMAND:
                receipt = self._persistence_command(command)
            elif command.kind is CommandKind.SET_CONTEXT_WINDOW:
                receipt = self._set_context_window(command)
            elif command.kind in (CommandKind.SET_EMBEDDING_SETTINGS, CommandKind.RESET_EMBEDDING_SETTINGS):
                receipt = self._set_embedding_settings(command)
            elif command.kind in (CommandKind.SET_KNOWLEDGE_SETTINGS, CommandKind.RESET_KNOWLEDGE_SETTINGS):
                receipt = self._set_knowledge_settings(command)
            elif command.kind is CommandKind.SET_WEB_SETTINGS:
                receipt = self._set_web_settings(command)
            elif command.kind is CommandKind.SET_FETCH_ENABLED:
                receipt = self._set_fetch_enabled(command)
            elif command.kind is CommandKind.SET_SEARCH_ENGINE:
                receipt = self._set_search_engine(command)
            elif command.kind is CommandKind.SET_BROWSER:
                receipt = self._set_browser(command)
            elif command.kind is CommandKind.BROWSER_CONTROL:
                receipt = self._browser_control(command)
            else:
                receipt = self._reject(command, "UNSUPPORTED_COMMAND",
                                       "Command is not available in this Application API")
            self._receipts[command.command_id] = (fingerprint, receipt)
            return receipt

    def _reject(self, command: ApplicationCommand, code: str,
                message: str) -> CommandReceipt:
        revision = self._session.state_revision if self._session else None
        category = (ErrorCategory.POLICY if code.startswith('SECURITY_AUDIT_')
                    else ErrorCategory.FILESYSTEM if code == "INVALID_WORKSPACE"
                    else ErrorCategory.APPROVAL if command.kind is CommandKind.RESOLVE_APPROVAL
                    else ErrorCategory.CANCELLATION if command.kind in (
                        CommandKind.CANCEL_TURN, CommandKind.STOP_GENERATION,
                        CommandKind.CANCEL_OPERATION, CommandKind.CANCEL_SUB_AGENT)
                    else ErrorCategory.CAPABILITY if code == "UNSUPPORTED_COMMAND"
                    else ErrorCategory.RAG if command.kind in (CommandKind.SET_RAG_ENABLED,
                        CommandKind.QUERY_RAG, CommandKind.GET_RAG_STATUS)
                    else ErrorCategory.FILESYSTEM if code == "PERSISTENCE_UNAVAILABLE"
                    else ErrorCategory.CONTEXT)
        return CommandReceipt(
            command_id=command.command_id, accepted=False,
            session_id=command.session_id, state_revision=revision,
            error=ApplicationError(code=code, category=category,
                                   safe_message=message),
        )

    def _change_model_runtime(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        category = ErrorCategory.MODEL if command.kind is CommandKind.CHANGE_MODEL else ErrorCategory.PROVIDER
        def reject(code, message, error_category=category):
            return CommandReceipt(command.command_id, False, session.session_id,
                                  session.state_revision,
                                  error=ApplicationError(code, error_category, message))
        # Check before validation/factory/network; rejection has no effects.
        if any(not turn.done.is_set() for turn in session.turns):
            return reject("CONFLICT_ACTIVE_TURN", "Provider/model cannot change during an active Turn")
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return reject("REVISION_CONFLICT", "Session revision changed")
        if command.payload.get("endpointRef") is not None:
            return reject("UNSUPPORTED_ENDPOINT_REFERENCE", "Endpoint must come from trusted provider configuration")
        self._preempt_memory()
        try:
            if command.kind is CommandKind.CHANGE_MODEL:
                current = self.provider_manager.change_model(command.payload["modelId"])
                kind = EventKind.MODEL_CHANGED
            else:
                current = self.provider_manager.change_provider(
                    command.payload["providerId"], model=command.payload.get("modelId"))
                kind = EventKind.PROVIDER_CHANGED
        except ProviderTransitionError as exc:
            return reject(exc.code, str(exc), ErrorCategory(exc.category))
        session.model = current.snapshot.model_id
        session.capabilities = self._capability_factory(model=current.snapshot, cwd=session.workspace,
            shell=next((getattr(t, "descriptor", None) for t in session.tools if t.name == "bash"), None),
            resource_context_limit=self._context_policy.resource_limit)
        session.state_revision += 1
        if self._events is not None:
            self._events.publish(kind, current.snapshot.to_dict(),
                                 state_revision=session.state_revision,
                                 causation_id=CausationId(command.command_id))
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def register_browser_actor(self, kind, verify):
        if kind not in ('cli_tty', 'desktop_host') or not callable(verify): raise ValueError('Invalid Browser actor')
        actor = object()
        with self._lock: self._browser_actors[actor] = verify
        return actor

    def register_browser_sensitive(self, value, actor):
        try: verify = self._browser_actors.get(actor); verified = verify is not None and verify() is True
        except Exception: verified = False
        if not verified: raise ValueError('Authenticated human Browser control is required.')
        if not isinstance(value, str) or not 1 <= len(value) <= 8192: raise ValueError('Use a sensitive value of 1 to 8192 characters.')
        self.redactor.register(value, protected=True)

    def _browser_control(self, command):
        session = self._active_session(command)
        if session is None: return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        verify = self._browser_actors.get(command.approval_actor)
        try: verified = verify is not None and verify() is True
        except Exception: verified = False
        if not verified: return self._reject(command, 'BROWSER_HUMAN_REQUIRED', 'Authenticated human Browser control is required.')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if any(not t.done.is_set() for t in session.turns) or any(not a.done.is_set() for a in session.agent_operations.values()):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Wait for the active turn before controlling the Browser.')
        from local_cli.core.browser import BrowserActionError
        from local_cli.application.browser import BrowserUnavailable
        try:
            action = command.payload['action']
            result = session.tool_runtime.browser_control(action, session.workspace, session.session_id,
                                                         **{k: v for k, v in command.payload.items() if k != 'action'})
            self._browser_control_result = self.redactor.value(result)
            if action == 'file':
                session.transcript.append({'role': 'system', 'content': 'Host file selection (metadata only; upload still requires approval): ' +
                    json.dumps(self._browser_control_result, ensure_ascii=False)})
            session.state_revision += 1
            return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)
        except (BrowserActionError, BrowserUnavailable) as exc:
            return self._reject(command, exc.code, exc.message)
        except (OSError, ValueError):
            return self._reject(command, 'BROWSER_CONTROL_FAILED', 'The Browser control operation could not complete.')

    def _permitted_tools(self, tools):
        return permitted_web_tools(tools, fetch_enabled=self._fetch_enabled,
            search_enabled=self._search_enabled, browser_enabled=self._browser_enabled)

    def _set_web_settings(self, command, patch=None):
        session = self._active_session(command)
        if session is None:
            return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not turn.done.is_set() for turn in session.turns)
                or any(not agent.done.is_set() for agent in session.agent_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Web settings cannot change during active execution.')
        from local_cli.tools.browser_tools import BrowserTool
        from local_cli.tools.browser_search_tool import BrowserSearchTool
        from local_cli.application.browser import BrowserUnavailable
        from local_cli.core.browser_search import BrowserSearchSettings
        from local_cli.web_config import validate_web_settings
        search = next((tool for tool in session.installed_tools if isinstance(tool, BrowserSearchTool)), None)
        browser = next((tool for tool in session.installed_tools if isinstance(tool, BrowserTool)), None)
        current = dict(fetchEnabled=self._fetch_enabled, searchEnabled=self._search_enabled,
            browserEnabled=self._browser_enabled, engine=search.settings.engine if search else self._web_engine,
            browser=browser.selection.selected if browser else self._web_browser)
        candidate = validate_web_settings({**current, **patch} if patch is not None else dict(command.payload))
        if candidate == current:
            return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)
        tools = permitted_web_tools(session.installed_tools, fetch_enabled=candidate['fetchEnabled'],
            search_enabled=candidate['searchEnabled'], browser_enabled=candidate['browserEnabled'])
        try:
            # The default remains selectable even on hosts without WebView2;
            # capability discovery and execution still report its unavailability.
            if browser and candidate['browser'] != current['browser'] and candidate['browser'] != 'webview2':
                browser.selection.validate(candidate['browser'])
            prompt = self.redactor.text(self._prompt_factory(tools, session.workspace))
            if candidate['browser'] != current['browser'] or (current['browserEnabled'] and not candidate['browserEnabled']):
                session.tool_runtime.release_browser()
            if self._web_settings_save is not None:
                self._web_settings_save(candidate)
        except BrowserUnavailable as exc:
            return self._reject(command, exc.code, exc.message)
        except (OSError, ValueError):
            return self._reject(command, 'WEB_CONFIGURATION_FAILED', 'Could not save web settings. The previous settings are unchanged.')
        # Publish only after the single preference file commits. No tool runs here.
        if search: search.settings = BrowserSearchSettings(candidate['engine'], endpoint=search.settings.endpoint)
        if browser: browser.selection.selected = candidate['browser']
        self._web_engine, self._web_browser = candidate['engine'], candidate['browser']
        session.tool_runtime.set_web_permissions(fetch_enabled=candidate['fetchEnabled'],
            search_enabled=candidate['searchEnabled'], browser_enabled=candidate['browserEnabled'])
        self._fetch_enabled, self._search_enabled, self._browser_enabled = (
            candidate['fetchEnabled'], candidate['searchEnabled'], candidate['browserEnabled'])
        session.tools = tools
        for messages in (session.transcript, session.base_transcript):
            if messages and messages[0].get('role') == 'system':
                messages[0] = {**messages[0], 'content': prompt}
        session.state_revision += 1
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _set_browser(self, command: ApplicationCommand) -> CommandReceipt:
        if self._web_settings_save is not None:
            return self._set_web_settings(command, {'browser': command.payload['browser']})
        session = self._active_session(command)
        if session is None:
            return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not t.done.is_set() for t in session.turns)
                or any(not a.done.is_set() for a in session.agent_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Browser settings cannot change during active execution.')
        from local_cli.tools.browser_tools import BrowserTool
        from local_cli.application.browser import BrowserUnavailable
        tool = next((t for t in session.installed_tools if isinstance(t, BrowserTool)), None)
        if tool is None:
            return self._reject(command, 'BROWSER_UNAVAILABLE', 'The Browser tools are not installed.')
        selected = command.payload['browser']
        try:
            tool.selection.validate(selected)
            if tool.selection.selected != selected:
                session.tool_runtime.release_browser()
            tool.selection.select(selected)
        except BrowserUnavailable as exc:
            return self._reject(command, exc.code, exc.message)
        except (OSError, ValueError):
            return self._reject(command, 'BROWSER_CONFIGURATION_FAILED', 'Could not save browser settings. The previous selection is unchanged.')
        session.state_revision += 1
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _set_search_engine(self, command: ApplicationCommand) -> CommandReceipt:
        if self._web_settings_save is not None:
            return self._set_web_settings(command, {'engine': command.payload['engine']})
        session = self._active_session(command)
        if session is None:
            return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not t.done.is_set() for t in session.turns)
                or any(not a.done.is_set() for a in session.agent_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Search settings cannot change during active execution.')
        from local_cli.tools.browser_search_tool import BrowserSearchTool
        tool = next((t for t in session.installed_tools if isinstance(t, BrowserSearchTool)), None)
        if tool is None:
            return self._reject(command, 'BROWSER_SEARCH_UNAVAILABLE', 'The bundled browser search tool is not installed.')
        try:
            tool.set_engine(command.payload['engine'])
        except (ValueError, OSError):
            return self._reject(command, 'SEARCH_CONFIGURATION_FAILED', 'Could not save the search engine. The previous setting is unchanged.')
        session.state_revision += 1
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _set_embedding_settings(self, command):
        session = self._active_session(command)
        if session is None:
            return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not t.done.is_set() for t in session.turns)
                or any(not a.done.is_set() for a in session.agent_operations.values())
                or any(getattr(o, 'status', '') in ('running', 'pending') for o in self._service_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Wait for active execution to finish.')
        if self._embedding_settings is None:
            return self._reject(command, 'EMBEDDING_SETTINGS_UNAVAILABLE', 'Embedding settings are unavailable.')
        from local_cli.embedding_settings import EmbeddingSettingsError
        try:
            if command.kind is CommandKind.RESET_EMBEDDING_SETTINGS:
                self._embedding_settings.reset()
            else:
                self._embedding_settings.update(dict(command.payload))
        except EmbeddingSettingsError as exc:
            return self._reject(command, exc.code, 'Embedding setting was not applied. The previous settings remain active.')
        session.state_revision += 1
        self._refresh_knowledge_index()
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _knowledge_settings_snapshot(self):
        if self._knowledge_preferences is None: return None
        em = self._embedding_settings.snapshot() if self._embedding_settings else {}
        value = self._knowledge_preferences.snapshot()
        available = bool(em.get('connected') and em.get('selectedModel') and not em.get('errorCode'))
        index = getattr(self._knowledge.service, 'indexing', None)
        return dict(value, semanticAvailable=available,
            **(index.snapshot() if index else dict(indexing=False, indexedSources=0, totalSources=0, errorCode=None)))

    def _refresh_knowledge_index(self):
        if self._knowledge_preferences is None or self._knowledge.closing: return
        if self._knowledge.service is None:
            state = self._knowledge_settings_snapshot()
            if not state['semanticAvailable'] or self._session is None: return
            try:
                self._knowledge.service = self._knowledge.factory(self._session.workspace,
                    str(self._session.session_id), lambda kind, payload: None)
                return
            except Exception:
                return
        index = getattr(self._knowledge.service, 'indexing', None)
        if index: index.refresh()

    def _knowledge_index_changed(self, service):
        with self._lock:
            session = self._session
            if session is None or self._knowledge.closing or self._knowledge.service is not service: return
            if self._events is not None:
                # Index progress carries no source text, vectors or origin paths.
                self._events.publish(EventKind.OPERATION_PROGRESS,
                    dict(service='knowledge-index', **service.indexing.snapshot()),
                    state_revision=session.state_revision)

    def _set_knowledge_settings(self, command):
        session = self._active_session(command)
        if session is None: return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not turn.done.is_set() for turn in session.turns)
                or any(not task.done.is_set() for task in session.agent_operations.values())
                or any(not op.done.is_set() for op in self._service_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Wait for active execution to finish.')
        if self._knowledge_preferences is None:
            return self._reject(command, 'KNOWLEDGE_UNAVAILABLE', 'Knowledge settings are unavailable.')
        from local_cli.knowledge_preferences import DEFAULTS
        value = dict(DEFAULTS if command.kind is CommandKind.RESET_KNOWLEDGE_SETTINGS else command.payload)
        current = self._knowledge_settings_snapshot()
        if command.kind is not CommandKind.RESET_KNOWLEDGE_SETTINGS and not current['semanticAvailable'] and any(value[key] and not current[key] for key in ('semanticRecall','autoIndex','autoRebuild')):
            return self._reject(command, 'KNOWLEDGE_EMBEDDING_REQUIRED', 'An enabled embedding model is required.')
        try: self._knowledge_preferences.update(value)
        except (OSError, ValueError):
            return self._reject(command, 'KNOWLEDGE_SETTINGS_SAVE_FAILED', 'Previous Knowledge settings remain active.')
        session.state_revision += 1
        self._refresh_knowledge_index()
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _set_context_window(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not t.done.is_set() for t in session.turns)
                or any(not a.done.is_set() for a in session.agent_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION', 'Context settings cannot change during active execution.')
        from local_cli.application.context_settings import resolve_context
        from local_cli.core.context import ContextError
        requested = command.payload['requestedTokens']
        try:
            runtime = self.provider_manager.snapshot().snapshot
            # Before the first turn, the initial runtime may not yet have model
            # metadata. Read it without inference before validating a GUI save.
            if runtime.model_context_window is None and runtime.provider_id in self.provider_manager.SUPPORTED:
                runtime = self.provider_manager.refresh_status()
            resolve_context(requested, self._context_policy, runtime)
        except ContextError as exc:
            return self._reject(command, exc.code, str(exc))
        try:
            if self._context_selection_save is not None:
                self._context_selection_save(requested)
        except (OSError, ValueError):
            return self._reject(command, 'CONTEXT_PREFERENCES_SAVE_FAILED',
                                'Could not save context settings. The previous setting is unchanged.')
        self._context_selection = requested
        session.state_revision += 1
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _set_fetch_enabled(self, command: ApplicationCommand) -> CommandReceipt:
        if self._web_settings_save is not None:
            return self._set_web_settings(command, {'fetchEnabled': command.payload['enabled']})
        session = self._active_session(command)
        if session is None:
            return self._reject(command, 'INVALID_SESSION', 'No matching active AgentSession')
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, 'REVISION_CONFLICT', 'Session revision changed')
        if (any(not t.done.is_set() for t in session.turns)
                or any(not a.done.is_set() for a in session.agent_operations.values())):
            return self._reject(command, 'CONFLICT_ACTIVE_OPERATION',
                                'Fetch settings cannot change during active execution.')
        enabled = command.payload['enabled']
        tools = permitted_web_tools(session.installed_tools, fetch_enabled=enabled,
            search_enabled=self._search_enabled, browser_enabled=self._browser_enabled)
        try:
            prompt = self.redactor.text(self._prompt_factory(tools, session.workspace))
            if self._fetch_enabled_save is not None:
                self._fetch_enabled_save(enabled)
        except (OSError, ValueError):
            return self._reject(command, 'FETCH_CONFIGURATION_FAILED',
                                'Could not save fetch settings. The previous setting is unchanged.')
        session.tool_runtime.set_fetch_enabled(enabled)
        self._fetch_enabled = enabled
        session.tools = tools
        # Refresh only the tool catalog prompt, preserving project instructions
        # and the conversation. This setting never changes shell permissions.
        for messages in (session.transcript, session.base_transcript):
            if messages and messages[0].get('role') == 'system':
                messages[0] = {**messages[0], 'content': prompt}
        session.state_revision += 1
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)

    def _start_session(self, command: ApplicationCommand) -> CommandReceipt:
        if self._session is not None and self._session.status == "active":
            return self._reject(command, "CONFLICT_ACTIVE_SESSION",
                                "A main AgentSession is already active")
        candidate = Path(command.payload["workspace"]).expanduser()
        if not candidate.is_absolute():
            return self._reject(command, "INVALID_WORKSPACE",
                                "workspace must be an absolute directory")
        try:
            workspace = candidate.resolve()
        except OSError:
            return self._reject(command, "INVALID_WORKSPACE",
                                "workspace could not be resolved")
        if not workspace.is_dir():
            return self._reject(command, "INVALID_WORKSPACE",
                                "workspace must be an existing directory")
        try:
            installed_tools = self._source_tools(list(self._tool_factory(workspace)))
            tools = self._permitted_tools(installed_tools)
            prompt = self._prompt_factory(tools, workspace)
            registry = ToolRegistry(installed_tools)
            environment = dict(next(
                (tool.environment for tool in tools if isinstance(tool, ShellTool)),
                get_sanitized_env(),
            ))
            self.redactor.observe_environment(environment)
            environment = self._environment_service.build(environment, None)
            for tool in installed_tools:
                if hasattr(tool, 'environment'):
                    tool.environment = dict(environment)
        except Exception:
            return self._reject(command, "SESSION_SETUP_FAILED",
                                "Could not initialize the AgentSession")
        session_id = new_session_id()
        initial_messages = (deepcopy(self._initial_messages_factory(workspace, tools))
                            if self._initial_messages_factory is not None else
                            [{"role": "system", "content": prompt}])
        if (not isinstance(initial_messages, list) or not initial_messages or
                initial_messages[0].get("role") != "system"):
            return self._reject(command, "SESSION_SETUP_FAILED",
                                "Could not initialize the AgentSession")
        if not all((self._fetch_enabled, self._search_enabled, self._browser_enabled)):
            initial_messages[0] = {**initial_messages[0], 'content': prompt}
        initial_messages = self.redactor.messages(initial_messages)
        session = AgentSession(
            session_id=session_id, workspace=workspace, model=self.provider_manager.snapshot().snapshot.model_id,
            tools=tools, transcript=initial_messages,
            base_transcript=deepcopy(initial_messages),
            installed_tools=installed_tools,
            environment=environment,
        )
        session.approval_gate = ApprovalGate(
            deadline_factory=self._human_response_deadline_factory,
            on_required=lambda request: self._publish_approval_required(session, request),
            on_resolved=lambda request, approved, reason: self._publish_approval_resolved(
                session, request, approved, reason),
        )
        session.user_input_gate = UserInputGate(
            deadline_factory=self._human_response_deadline_factory,
            on_required=lambda request: self._publish_user_input_required(session, request),
            on_resolved=lambda request, reason: self._publish_user_input_resolved(
                session, request, reason),
        )
        session.tool_runtime = self._create_tool_runtime(session, registry, workspace)
        self._session = session
        if self._persistence_factory is not None:
            try:
                self._persistence = self._persistence_factory(workspace)
                self._bind_redaction(self._persistence)
                if self._persistence.workspace != workspace:
                    raise PersistenceError("PERSISTENCE_WORKSPACE_CONFLICT")
            except Exception:
                # Broken/unwritable state storage must not prevent conversation.
                self._persistence = None
                self._persistence_setup_error = "PERSISTENCE_SETUP_FAILED"
        if self._rag_factory is not None:
            try:
                self._rag = self._rag_factory(workspace)
            except Exception:
                self._rag = RAGService(None)
        session.capabilities = self._capability_factory(model=self.provider_manager.snapshot().snapshot,
            cwd=workspace, shell=next((getattr(t, "descriptor", None) for t in tools if t.name == "bash"), None),
            resource_context_limit=self._context_policy.resource_limit)
        for tool in tools:
            if hasattr(tool, "bind_model_runtime"):
                # Production adapters are managed; synthetic legacy adapters
                # without a fresh-instance contract retain their test bridge.
                if self.provider_manager.snapshot()._fresh_factory is not None:
                    tool.bind_model_runtime(lambda: bind_context(self.provider_manager.snapshot(),
                        workspace=session.workspace, tools=session.tools,
                        requested=self._context_selection, policy=self._context_policy,
                        capability_factory=self._capability_factory))
        if self._event_config is not None:
            self._events = SessionEventStream(session_id, self._event_config, redactor=self.redactor)
            self._events.publish(
                EventKind.SESSION_STARTED, {"status": "active"},
                state_revision=1, causation_id=CausationId(command.command_id),
            )
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session_id, state_revision=1,
                              created_ids={"sessionId": session_id})

    def _create_tool_runtime(self, session, registry, workspace, *, policy=None):
        """A workspace selection installs a fresh ceiling, broker and issuer.

        Conversation continuity never transfers the previous project's Grants,
        filesystem handles, cached tool results or Browser-derived bindings.
        """
        runtime = ToolRuntime(
            registry, auto_approve=self._auto_approve,
            approval_gate=session.approval_gate,
            user_input_gate=session.user_input_gate,
            publish=lambda event: self._publish_tool_event(session, event),
            publish_progress=lambda *args: self._publish_tool_progress(session, *args),
            on_agent_started=lambda *args: self._publish_agent_started(session, *args),
            on_agent_completed=lambda *args: self._publish_agent_completed(session, *args),
            process_service=self._process_service,
            network_service=self._network_service,
            redactor=self.redactor, environment_service=self._environment_service,
            environment_selector=self._environment_selector,
            security_audit=self.security_audit,
            fetch_enabled=self._fetch_enabled,
            search_enabled=self._search_enabled, browser_enabled=self._browser_enabled,
            policy=policy,
        )
        try:
            runtime.install_authority(workspace, session.session_id)
        except Exception:
            runtime.close()
            raise
        return runtime

    def _source_tools(self, tools):
        if not getattr(self._knowledge.factory, 'context_available', False):
            return tools
        from local_cli.tools.source_read_tool import SourceReadTool
        return [tool for tool in tools if tool.name != 'source_read'] + [SourceReadTool(self._read_turn_source)]

    def _read_turn_source(self, context, **arguments):
        from local_cli.application.selected_sources import SelectedSourceAdmission
        from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode
        with self._lock:
            session = self._session
            turn = next((t for t in session.turns if t.turn_id == context.turn_id), None) if session else None
            if (session is None or session.session_id != context.session_id or context.agent_id is not None
                    or turn is None or turn.done.is_set() or turn.cancellation.is_cancel_requested()
                    or not isinstance(turn.knowledge_admission, SelectedSourceAdmission)):
                raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
            admission = turn.knowledge_admission
        admission.service._check(context)
        return admission.read(**arguments)

    def _start_turn(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._session
        if session is None or command.session_id != session.session_id:
            return self._reject(command, "INVALID_SESSION",
                                "No matching active AgentSession")
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, "REVISION_CONFLICT",
                                "Session revision changed")
        if any(not turn.done.is_set() for turn in session.turns):
            return self._reject(command, "CONFLICT_ACTIVE_TURN",
                                "The main AgentSession already has an active Turn")
        browser = session.tool_runtime._browser_service
        if browser is not None and browser.human_phase in ('humanActive', 'resumePending', 'blocked'):
            return self._reject(command, 'BROWSER_HUMAN_ACTIVE', 'Browser control is paused for the human. Use /browser resume or /browser close before another task.')
        from local_cli.core.knowledge import KnowledgeError
        try:
            refs = self._knowledge.validate(command.payload.get('attachmentRefs', []))
        except KnowledgeError as exc:
            return CommandReceipt(command.command_id, False, session.session_id, session.state_revision,
                error=ApplicationError(exc.code, ErrorCategory.CAPABILITY, 'Attachment reference is unavailable or stale.'))
        self._preempt_memory(resume_after_turn=True)
        turn = Turn(new_turn_id(), new_operation_id(), command.command_id)
        from local_cli.application.turn_effects import resolve_turn_effects
        turn.effect_constraints = resolve_turn_effects(command.payload['content'])
        session.tool_runtime.bind_turn_effects(session.session_id,turn.turn_id,turn.effect_constraints)
        turn.attachment_refs = refs
        if self._memory_capture_mode!='off':
            turn.memory_capture=(session.workspace,self.redactor.text(command.payload['content']),datetime.now(timezone.utc))
        # Startup/model selection and background readiness own provider observations.
        # A foreground send pins those facts without another tags/show round trip.
        turn.model_runtime = self.provider_manager.begin_turn(
            turn.turn_id,
            inference_options=(self._inference_options_factory()
                               if self._inference_options_factory is not None else None))
        session.turns.append(turn)
        if self._turn_messages_factory is not None:
            session.transcript.extend(deepcopy(self._turn_messages_factory(command.payload["content"])))
        turn.transcript_start = len(session.transcript)
        session.transcript[:] = self.redactor.messages(session.transcript)
        session.transcript.append({"role": "user", "content": self.redactor.text(command.payload["content"]),
            **({'attachmentRefs': [r.to_dict() for r in refs]} if refs else {})})
        turn.user_message = {"id": "message_" + uuid4().hex,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "sourceIndex": len(session.transcript) - 1}
        if self._persistence is not None:
            self._persistence.save(self._saved_transcript(session))
        session.state_revision += 1
        if self._events is not None:
            self._events.publish(
                EventKind.TURN_STARTED, {"status": "running"},
                state_revision=session.state_revision, turn_id=turn.turn_id,
                operation_id=turn.operation_id,
                causation_id=CausationId(command.command_id),
            )
        receipt = CommandReceipt(
            command_id=command.command_id, accepted=True,
            session_id=session.session_id, state_revision=session.state_revision,
            created_ids={"turnId": turn.turn_id, "operationId": turn.operation_id},
        )
        try:
            Thread(target=self._run_turn, args=(session, turn), daemon=True).start()
        except Exception:
            turn.status = advance_turn_status(turn.status, TurnStatus.FAILED)
            turn.operation_status = advance_operation_status(
                turn.operation_status, OperationStatus.FAILED,
            )
            turn.error_code = "WORKER_START_FAILED"
            turn.terminal_count = 1
            session.state_revision += 1
            self._publish_turn_terminal(session, turn)
            self.provider_manager.end_turn(turn.turn_id)
            if turn.model_runtime._context is not None:
                turn.model_runtime._context.memory_source=None
                turn.model_runtime._context.knowledge_source=None
                turn.model_runtime._context.manager.invalidate_cache()
            turn.done.set()

        return receipt

    def _preempt_memory(self,*,resume_after_turn=False):
        if self._memory_worker and not self._memory_worker.done.is_set():
            if resume_after_turn:self._memory_worker.progress['resumeAfterTurn']=True
            self._memory_worker.token.request()

    def _queue_memory(self,session,turn,*,capture=True):
        """One idle worker/quota. All state/store writes serialized here."""
        from local_cli.core.memory import MemoryEvidence,MemorySourceClass
        from local_cli.core.memory_maintenance import MemoryExtractionInput
        import hashlib
        from types import SimpleNamespace
        from local_cli.core.security_audit import AuditKind
        with self._lock:
            if self._session is not session or self._memory_factory is None:return
            # Capture only successful user evidence, never tool/subagent output
            # or assistant hallucinations. Other trusted sources stay proposal-only.
            if turn.status is not TurnStatus.COMPLETED:return
            if not turn.memory_capture or turn.memory_capture[0]!=session.workspace:return
            if self._memory_worker and not self._memory_worker.done.is_set():
                # Capture for this terminal still needs to survive a busy worker;
                # retry scheduling only, not authoritative effects.
                self._memory_worker.token.request()
                self._memory_worker.progress['resumeAfterTurn']=True
            text=turn.memory_capture[1]
            capture_error=None
            # Every queue mutation, including capture/checkpoint, is audited
            # before its effect. The audit stores metadata only, not evidence.
            operation=ServiceOperation(new_operation_id(),turn.command_id,service='memory-maintenance',
                deadline=datetime.now(timezone.utc)+timedelta(seconds=30))
            self._service_operations[operation.operation_id]=operation
            invocation=SimpleNamespace(context=SimpleNamespace(session_id=session.session_id,
                operation_id=operation.operation_id,turn_id=None,agent_id=None,workspace=session.workspace,cwd=session.workspace),
                operation_id=operation.operation_id,tool_call_id=None,name='memory_maintenance',arguments={})
            try:
                if self.security_audit:
                    self.security_audit.request(invocation,origin='application')
                    self.security_audit.record(invocation,AuditKind.POLICY,{'decision':'AUTO_SAFE_OR_PROPOSAL',
                        'policyRevision':'mem6-conservative-span-v1'},origin='application')
                    self.security_audit.before_effect(invocation,origin='application')
                if self._memory is None:self._memory=self._memory_factory(session.workspace,self.redactor)
                maintenance=self._memory.maintenance
                if maintenance is None:raise MemoryError(MemoryErrorCode.UNAVAILABLE)
                scope=maintenance.scope(session.workspace,register=True)
                if capture and len(text)<=4096:
                    maintenance.capture(MemoryExtractionInput(subject_id=scope.subject_id,workspace_id=scope.workspace_id,
                        text=text,evidence=MemoryEvidence(source_id='mem6-turn-'+str(turn.turn_id),
                        source_class=MemorySourceClass.USER_ASSERTION,source_timestamp=turn.memory_capture[2],
                        session_id=str(session.session_id),turn_id=str(turn.turn_id),operation_id=str(turn.operation_id),
                        evidence_hash=hashlib.sha256(text.encode()).hexdigest())))
            except (MemoryError,SecurityAuditError) as exc:capture_error=exc
            except Exception:
                capture_error=MemoryError(MemoryErrorCode.WRITE_FAILED)
            if capture_error:
                if self.security_audit:self.security_audit.record(invocation,AuditKind.TERMINAL,
                    {'outcome':'FAILED','effectState':'unknown' if getattr(capture_error,'outcome_unknown',False) else 'none',
                     'errorCode':capture_error.code,'retryAllowed':False},origin='application')
                self._finish_service_operation(session,operation,OperationStatus.FAILED,
                    {'error':{'code':capture_error.code,'retryAllowed':False}})
                return
            if (self._memory_worker and not self._memory_worker.done.is_set()) or any(not t.done.is_set() for t in session.turns):
                if self.security_audit:self.security_audit.record(invocation,AuditKind.TERMINAL,
                    {'outcome':'COMPLETED','effectState':'applied','action':'queue_capture','retryAllowed':False},origin='application')
                self._finish_service_operation(session,operation,OperationStatus.COMPLETED,{'phase':'captured_deferred'})
                return
            self._memory_worker=operation
            operation.progress={'phase':'queued','quota':1,'deadline':operation.deadline.isoformat()}
            def worker():
                from local_cli.core.memory_maintenance import MemoryExtractionInput
                response={};status=OperationStatus.COMPLETED;job=None;effect=False;receipts=[]
                try:
                    for _ in range(4):  # Bounded idle batch within the existing deadline/quota.
                        with self._lock:
                            if operation.token.is_cancel_requested() or any(not t.done.is_set() for t in session.turns):
                                status=OperationStatus.CANCELLED;break
                            if datetime.now(timezone.utc)>=operation.deadline:
                                raise MemoryError(MemoryErrorCode.RETRIEVAL_TIMEOUT)
                            jobs=maintenance.jobs.list_jobs(scope,states=('PENDING','READY','DEFERRED'),limit=1)
                            if not jobs:break
                            job=jobs[0]
                            runtime=self.provider_manager.snapshot().snapshot
                            if not local_memory_destination(runtime):
                                raise MemoryError(MemoryErrorCode.EXTRACTION_UNAVAILABLE)
                        if job['state']!='READY':
                            if not self._memory_extractor_factory:
                                raise MemoryError(MemoryErrorCode.EXTRACTION_UNAVAILABLE)
                            n=turn.model_runtime._context.manager.selection.resolve(
                                model_limit=runtime.model_context_window,provider_limit=runtime.provider_context_window,
                                resource_limit=self._context_policy.resource_limit)[0]
                            extractor=self._memory_extractor_factory(runtime,n)
                            reply=extractor.extract(MemoryExtractionInput(subject_id=scope.subject_id,workspace_id=scope.workspace_id,
                                evidence=maintenance._evidence(job),text=job['text']),
                                cancellation=operation.token,deadline=operation.deadline)
                        with self._lock:
                            if (operation.token.is_cancel_requested() or any(not t.done.is_set() for t in session.turns)
                                or self.provider_manager.snapshot().snapshot!=runtime or self._session is not session
                                or maintenance.scope(session.workspace)!=scope
                                or datetime.now(timezone.utc)>=operation.deadline):
                                status=OperationStatus.CANCELLED;break  # No late/stale commit.
                            if self.security_audit:
                                self.security_audit.before_effect(invocation,origin='application')
                            if job['state']!='READY':job=maintenance.checkpoint(job,reply,scope)
                            def admissible():
                                if operation.token.is_cancel_requested() or datetime.now(timezone.utc)>=operation.deadline:
                                    raise MemoryError(MemoryErrorCode.RETRIEVAL_TIMEOUT)
                            receipt=maintenance.commit(job,scope,pre_commit=admissible)
                            receipts.append(receipt)
                            response={'accepted':sum(r.get('accepted',0) for r in receipts),
                                'proposed':sum(r.get('proposed',0) for r in receipts),'jobs':len(receipts)}
                            effect=True
                except (MemoryError,SecurityAuditError) as exc:
                    status=(OperationStatus.CANCELLED if operation.token.is_cancel_requested() else
                        OperationStatus.OUTCOME_UNKNOWN if getattr(exc,'outcome_unknown',False) else OperationStatus.FAILED)
                    response={'error':{'code':exc.code,'retryAllowed':False}}
                    if receipts:response['observedReceipts']=receipts
                    # Known computation/schema failure can be checkpointed. An
                    # unknown commit or audit failure NEVER triggers a retry.
                    if (job is not None and isinstance(exc,MemoryError) and not getattr(exc,'outcome_unknown',False)
                        and not operation.token.is_cancel_requested()):
                        try:
                            with self._lock:
                                if self.security_audit:self.security_audit.before_effect(invocation,origin='application')
                                fresh=maintenance.jobs.get_job(job['jobId'],scope)
                                if fresh and fresh['state'] in ('PENDING','READY','DEFERRED'):
                                    deferred=exc.code==MemoryErrorCode.EXTRACTION_UNAVAILABLE.value
                                    maintenance.jobs.save_job(fresh['jobId'],scope,expected_revision=fresh['revision'],payload={**fresh,
                                        'revision':fresh['revision']+1,'state':'DEFERRED' if deferred else 'FAILED',
                                        'text':fresh['text'] if deferred else '', 'drafts':[],
                                        'result':{'errorCode':exc.code,'retryAllowed':False}})
                        except Exception:pass  # No fabricated checkpoint acknowledgment.
                except Exception:
                    status=OperationStatus.OUTCOME_UNKNOWN;response={'error':{'code':'MEMORY_MAINTENANCE_FAILED','retryAllowed':False}}
                    if receipts:response['observedReceipts']=receipts
                if self.security_audit:
                    self.security_audit.record(invocation,AuditKind.TERMINAL,dict(action='memory_maintenance',
                        outcome=status.value,effectState='applied' if effect else 'unknown' if status is OperationStatus.OUTCOME_UNKNOWN else 'none',
                        errorCode=response.get('error',{}).get('code'),retryAllowed=False),origin='application')
                    if self.security_audit.health()['deliveryFailures']:
                        response['securityAudit']={'gap':True,'retryAllowed':False}
                self._finish_service_operation(session,operation,status,response)
                # A new Turn may have completed before cancellation returned.
                # Resume only known cancelled computation, never failed effects.
                with self._lock:
                    if self._session is session and self._memory is not None:
                        self._memory.refresh_settings(session.workspace)
                    if (status is OperationStatus.CANCELLED and operation.progress.get('resumeAfterTurn')
                            and self._session is session and not any(not t.done.is_set() for t in session.turns)):
                        self._queue_memory(session,session.turns[-1],capture=False)
            try:Thread(target=worker,name='nova-memory-maintenance',daemon=True).start()
            except Exception:self._finish_service_operation(session,operation,OperationStatus.FAILED,
                {'error':{'code':'WORKER_START_FAILED'}})

    def _active_session(self, command: ApplicationCommand) -> AgentSession | None:
        session = self._session
        return (session if session is not None and session.status == "active"
                and session.session_id == command.session_id else None)

    def can_rebind_workspace(self) -> bool:
        with self._lock:
            session = self._session
            return bool(session is not None and session.status == "active"
                and not any(not turn.done.is_set() for turn in session.turns)
                and not any(not agent.done.is_set() for agent in session.agent_operations.values())
                and not any(not operation.done.is_set() for operation in self._service_operations.values())
                and not session.approval_gate.pending()
                and not session.user_input_gate.pending()
                and not (session.tool_runtime._browser_service is not None and
                    session.tool_runtime._browser_service.human_phase in
                    ('humanActive', 'resumePending', 'blocked')))

    def change_workspace(self, session_id, path: str, *, project_chat: bool = False) -> dict[str, Any]:
        """Existing folder-selection capability with one Application writer."""
        from local_cli.application.auxiliary import AuxiliaryConflict
        with self._lock:
            self._snapshot_unlocked(session_id)
            if not self.can_rebind_workspace():
                exc = AuxiliaryConflict("Workspace cannot change during active execution")
                exc.code = "CONFLICT_ACTIVE_OPERATION"
                raise exc
            if not isinstance(path, str) or not path.strip():
                raise ValueError("No path specified")
            if self._workspace_rebinder is None:
                raise ValueError("Workspace selection is unavailable")
            try:
                if '\x00' in path:
                    raise ValueError("Invalid path")
                target = Path(path).expanduser()
                target = (target if target.is_absolute() else self._session.workspace / target).resolve()
                if not target.is_dir():
                    raise ValueError("Invalid directory")
            except (OSError, ValueError):
                raise ValueError("Workspace must be an accessible directory") from None
            prepared = self._workspace_rebinder(target)
            if project_chat:
                try:
                    persistence = prepared['persistence']
                    saved = []
                    if persistence is not None and persistence.info():
                        saved = persistence.restore(workspace=target)
                    saved, dates = restored_with_dates(saved)
                    current = self._session
                    if target != current.workspace and self._persistence is not None and any(
                            row.get('role') in ('user', 'assistant') for row in current.transcript):
                        self._persistence.save(self._saved_transcript(current))
                        if getattr(self._persistence, 'last_error', None) is not None:
                            raise self._persistence.last_error
                    self.rebind_legacy_workspace(target, base_messages=prepared['base_messages'],
                        persistence=persistence, rag=prepared['rag'], installed_tools=prepared.get('tools'),
                        commit=prepared.get('commit'), publish=False)
                except Exception:
                    if callable(prepared.get('abort')):
                        prepared['abort']()
                    raise
                current.transcript[:] = deepcopy(current.base_transcript) + saved
                current.turns.clear()
                current.agent_operations.clear()
                current.restored_display_dates = {len(current.base_transcript) + index: value for index, value in dates.items()}
                current.state_revision += 1
                self._publish_workspace_snapshot()
                return {**prepared['data'], 'resumable': None, 'projectChat': True}
            old_base = self._session.base_transcript
            retained_items = [(index, message) for index, message in enumerate(self._session.transcript)
                              if message not in old_base]
            retained = [message for _, message in retained_items]
            # Capture exact canonical index ownership before deepcopy changes
            # object identities. Public presentation remains outside messages.
            index_map = {index: len(prepared["base_messages"]) + offset
                         for offset, (index, _) in enumerate(retained_items)}
            try:
                self.rebind_legacy_workspace(target, base_messages=prepared["base_messages"],
                    persistence=prepared["persistence"], rag=prepared["rag"],
                    installed_tools=prepared.get("tools"), commit=prepared.get("commit"),
                    publish=False)
            except Exception:
                if callable(prepared.get("abort")):
                    prepared["abort"]()
                raise
            for turn in self._session.turns:
                if turn.user_message is not None:
                    source = turn.user_message.get("sourceIndex")
                    if source in index_map:
                        turn.user_message["sourceIndex"] = index_map[source]
                    else:
                        turn.user_message = None
                for row in turn.display_messages:
                    source = row.get("sourceIndex")
                    if source in index_map:
                        row["sourceIndex"] = index_map[source]
                    else:
                        row.pop("sourceIndex", None)
                turn.transcript_start = len(prepared["base_messages"]) + sum(
                    index < turn.transcript_start for index, _ in retained_items)
                if turn.transcript_end is not None:
                    turn.transcript_end = len(prepared["base_messages"]) + sum(
                        index < turn.transcript_end for index, _ in retained_items)
            self._session.restored_display_dates = {index_map[index]: dates
                for index, dates in self._session.restored_display_dates.items() if index in index_map}
            self._session.transcript[:] = deepcopy(self._session.base_transcript + retained)
            self._publish_workspace_snapshot()
            return prepared["data"]

    def project_chats(self, session_id, paths):
        with self._lock:
            self._snapshot_unlocked(session_id)
            if not isinstance(paths, list) or len(paths) > 32 or any(
                    not isinstance(value, str) or not value or not Path(value).is_absolute() for value in paths):
                raise ValueError('Invalid project chat selection')
            if self._persistence is None:
                raise PersistenceError('PROJECT_CHAT_UNAVAILABLE')
            result = []
            for path in paths:
                info = self._persistence.project_info(path)
                result.append({'path': path, 'hasHistory': bool(info), 'messageCount': info['count'] if info else 0,
                               'savedAt': info.get('saved_at') if info else None})
            return result

    def clear_project_chat(self, session_id, path):
        from local_cli.application.auxiliary import AuxiliaryConflict
        with self._lock:
            self._snapshot_unlocked(session_id)
            if not self.can_rebind_workspace():
                error = AuxiliaryConflict('Wait for active execution before deleting a chat')
                error.code = 'CONFLICT_ACTIVE_OPERATION'
                raise error
            if not isinstance(path, str) or not Path(path).is_absolute():
                raise ValueError('Invalid project chat selection')
            if self._persistence is None:
                raise PersistenceError('PROJECT_CHAT_UNAVAILABLE')
            if Path(path).resolve() == self._session.workspace:
                receipt = self._persistence_command(ApplicationCommand(
                    command_id=CommandId(str(uuid4())), kind=CommandKind.EXECUTE_COMMAND,
                    session_id=self._session.session_id, payload={'name': 'clear'}))
                if not receipt.accepted:
                    raise PersistenceError(receipt.error.code, receipt.error.safe_message)
                self._publish_workspace_snapshot()
            else:
                self._persistence.clear_project(path)
            return {'path': path}

    def rebind_legacy_workspace(self, workspace: Path, *,
                                base_messages: list[dict[str, Any]],
                                persistence: PersistenceService | None,
                                rag: RAGService | None,
                                installed_tools=None, commit=None, publish=True) -> None:
        """Keep the transitional JSONL folder selector on the one session.

        Project resources are assembled by the injected composition adapter;
        Application serializes replacement of the one active workspace.
        """
        with self._lock:
            session = self._session
            if not self.can_rebind_workspace():
                raise ValueError("workspace cannot change during active execution")
            if not workspace.is_absolute() or not workspace.is_dir():
                raise ValueError("workspace must be an absolute directory")
            workspace = workspace.resolve()
            installed_tools = self._source_tools(list(self._tool_factory(workspace) if installed_tools is None
                                   else installed_tools))
            tools = self._permitted_tools(installed_tools)
            previous_runtime = session.tool_runtime
            next_base = self.redactor.messages(base_messages)
            if not all((self._fetch_enabled, self._search_enabled, self._browser_enabled)):
                prompt = self.redactor.text(self._prompt_factory(tools, workspace))
                if next_base and next_base[0].get('role') == 'system':
                    next_base[0] = {**next_base[0], 'content': prompt}
            capabilities = self._capability_factory(
                model=self.provider_manager.snapshot().snapshot, cwd=workspace,
                shell=next((getattr(t, "descriptor", None) for t in tools
                            if t.name == "bash"), None),
                resource_context_limit=self._context_policy.resource_limit)
            # The existing runtime verifies cleanup before relinquishing a
            # Browser session. An uncertain cleanup cannot create a second one.
            runtime = self._create_tool_runtime(session, ToolRegistry(installed_tools),
                workspace, policy=previous_runtime.policy)
            try:
                previous_runtime.release_browser()
            except Exception:
                runtime.close()
                raise
            old_knowledge = self._knowledge
            old_knowledge.close()
            from local_cli.application.knowledge_host import KnowledgeHostControls
            self._knowledge = KnowledgeHostControls(self, old_knowledge.factory)
            self._knowledge.actors = old_knowledge.actors
            if commit is not None:
                commit()
            session.workspace = workspace
            session.installed_tools = installed_tools
            session.tools = tools
            session.tool_runtime = runtime
            previous_runtime._issuer.cancel_session(session.session_id)
            previous_runtime.close()
            session.base_transcript = next_base
            if not all((self._fetch_enabled, self._search_enabled, self._browser_enabled)):
                if session.transcript and session.transcript[0].get('role') == 'system':
                    session.transcript[0] = {**session.transcript[0], 'content': prompt}
            self._persistence = persistence
            self._bind_redaction(persistence)
            self._rag = rag if rag is not None else RAGService(None)
            session.capabilities = capabilities
            session.state_revision += 1
            if publish:
                self._publish_workspace_snapshot()

    def _publish_workspace_snapshot(self):
        if self._events is not None:
            session = self._session
            state = self._snapshot_unlocked(session.session_id).to_dict()
            state["lastSequence"] = self._events.last_sequence + 1
            self._events.publish(EventKind.SESSION_SNAPSHOT, state,
                                 state_revision=session.state_revision,
                                 visibility=Visibility.SENSITIVE)

    @staticmethod
    def _saved_transcript(session, messages=None):
        rows = session.transcript if messages is None else messages
        metadata = dict(session.restored_display_dates)
        for turn in session.turns:
            for item in [turn.user_message, *turn.display_messages]:
                if not isinstance(item, dict):
                    continue
                index = item.get('sourceIndex')
                if type(index) is int and 0 <= index < len(rows):
                    dates = display_dates(item)
                    if dates:
                        metadata[index] = dates
        return saved_with_dates(rows, metadata)

    def _persistence_command(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        name = command.payload["name"]
        if self._persistence is None and name != "clear":
            return self._reject(command, "PERSISTENCE_UNAVAILABLE", "Persistence is unavailable")
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, "REVISION_CONFLICT", "Session revision changed")
        if any(not t.done.is_set() for t in session.turns) or any(
                not a.done.is_set() for a in session.agent_operations.values()):
            return self._reject(command, "CONFLICT_ACTIVE_OPERATION", "Cannot restore/save during active execution")
        try:
            if name in ("clear", "clear_history"):
                fresh = deepcopy(session.base_transcript)
                if self._refresh_base_factory is not None:
                    fresh = self._refresh_base_factory(session.workspace, session.tools)
                    if not fresh or fresh[0].get("role") != "system":
                        return self._reject(command, "SESSION_SETUP_FAILED",
                                            "Could not rebuild project context")
                if self._persistence is not None:
                    if name == 'clear_history':
                        self._persistence.clear_history()
                    else:
                        self._persistence.clear()
                        if getattr(self._persistence, 'last_error', None) is not None:
                            raise self._persistence.last_error
                session.base_transcript = deepcopy(fresh)
                session.transcript[:] = deepcopy(session.base_transcript)
                session.turns.clear()
                session.restored_display_dates.clear()
                session.state_revision += 1
                return CommandReceipt(command.command_id, True, session.session_id,
                    session.state_revision)
            if name == "save":
                key = self._persistence.save_session(self._saved_transcript(session))
                return CommandReceipt(command.command_id, True, session.session_id,
                    session.state_revision, created_ids={"snapshotKey": key})
            if name != "resume":
                return self._reject(command, "UNSUPPORTED_COMMAND", "Persistence command is unavailable")
            saved = self._persistence.restore(workspace=session.workspace,
                                             snapshot_key=command.payload.get("snapshotKey"))
            if not saved:
                return self._reject(command, "NO_SAVED_CONVERSATION",
                                    "No saved conversation to resume")
            if self._refresh_base_factory is not None:
                fresh = self._refresh_base_factory(session.workspace, session.tools)
                if not fresh or fresh[0].get("role") != "system":
                    return self._reject(command, "SESSION_SETUP_FAILED",
                                        "Could not rebuild project context")
                session.base_transcript = deepcopy(fresh)
            saved, dates = restored_with_dates(saved)
            session.restored_display_dates = {len(session.base_transcript) + index: value for index, value in dates.items()}
            session.transcript[:] = deepcopy(session.base_transcript) + saved
            # Stored dates are display-only. Restored messages have no live generation IDs/receipts.
            # Keep prior domain outcomes, retire only their obsolete sidecars.
            for turn in session.turns:
                turn.user_message = None
                turn.display_messages.clear()
                turn.tool_activities.clear()
            session.state_revision += 1
            self._persistence.save(self._saved_transcript(session))
            return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)
        except PersistenceError as exc:
            return CommandReceipt(command.command_id, False, session.session_id, session.state_revision,
                error=ApplicationError(exc.code, ErrorCategory.FILESYSTEM, exc.safe_message))

    def _rag_command(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        if command.expected_revision is not None and command.expected_revision != session.state_revision:
            return self._reject(command, "REVISION_CONFLICT", "Session revision changed")
        if command.kind is CommandKind.QUERY_RAG and (
                not isinstance(command.payload["query"], str) or not command.payload["query"].strip()):
            return self._reject(command, "INVALID_RAG_QUERY", "RAG query must be non-empty text")
        operation = ServiceOperation(new_operation_id(), command.command_id)
        self._service_operations[operation.operation_id] = operation
        def worker():
            response = None
            try:
                if not operation.token.is_cancel_requested():
                    if command.kind is CommandKind.GET_RAG_STATUS:
                        response = self._rag.status()
                    else:
                        report = lambda p: self._rag_progress(session, p, causation_id=CausationId(command.command_id))
                        response = (self._rag.set_enabled(command.payload["enabled"],
                            operation_id=operation.operation_id, progress=report)
                            if command.kind is CommandKind.SET_RAG_ENABLED else
                            self._rag.query(command.payload["query"],
                                operation_id=operation.operation_id, progress=report)).to_dict()
                status = (OperationStatus.CANCELLED if response is None else
                          OperationStatus.FAILED if response.get("error") else OperationStatus.COMPLETED)
                # A completed index/deactivation has a known outcome, even if
                # cancellation arrived while the legacy embedding call ran.
                if command.kind is CommandKind.QUERY_RAG and operation.token.is_cancel_requested():
                    status, response = OperationStatus.CANCELLED, None
            except Exception:
                status, response = OperationStatus.FAILED, {"error": {"code": "RAG_BACKEND_FAILED"}}
            self._finish_service_operation(session, operation, status, response)
        try:
            Thread(target=worker, daemon=True).start()
        except Exception:
            self._finish_service_operation(session, operation, OperationStatus.FAILED,
                                           {"error": {"code": "WORKER_START_FAILED"}})
        return CommandReceipt(command.command_id, True, session.session_id, session.state_revision,
                              created_ids={"operationId": operation.operation_id})

    def _rag_progress(self, session, payload, *, turn_id=None, causation_id=None):
        with self._lock:
            operation = self._service_operations.get(payload["operationId"])
            if operation is not None:
                operation.progress = deepcopy(payload)
            if self._events is not None:
                self._events.publish(EventKind.OPERATION_PROGRESS, payload,
                    operation_id=payload["operationId"], turn_id=turn_id,
                    causation_id=causation_id, state_revision=session.state_revision)

    def _finish_service_operation(self, session, operation, status, response):
        with self._lock:
            operation.status = advance_operation_status(operation.status, status)
            operation.result = deepcopy(response)
            session.state_revision += 1
            if self._events is not None:
                self._events.publish(operation_terminal_kind(OperationType.OTHER, status),
                    {"status": status.value, "operationType": "OTHER", "service": operation.service,
                     "result": response}, operation_id=operation.operation_id,
                    causation_id=CausationId(operation.command_id),
                    visibility=Visibility.SENSITIVE if response and response.get("matches") else Visibility.PUBLIC,
                    state_revision=session.state_revision, turn_id=operation.turn_id)
            operation.done.set()

    def _resolve_approval(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None or session.approval_gate is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        payload = command.payload
        try:
            session.approval_gate.resolve(
                session.session_id, payload["approvalId"], payload["toolCallId"],
                payload["requestDigest"], cwd=payload["cwd"],
                policy_revision=payload["policyRevision"],
                approved=payload["approved"],
                actor=command.approval_actor,
            )
        except InteractionError as exc:
            return self._reject(command, exc.code, "Approval is stale or does not match")
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session.session_id,
                              state_revision=session.state_revision)

    def register_approval_actor(self, kind: str, verify: Callable[[], bool]) -> object:
        """Trusted adapter composition only; not an ApplicationCommand endpoint."""
        with self._lock:
            if self._session is None or self._session.approval_gate is None:
                raise ValueError('no active session')
            return self._session.approval_gate.register_actor(kind, verify)

    def _resolve_user_input(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None or session.user_input_gate is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        try:
            session.user_input_gate.resolve(
                session.session_id, command.payload["inputRequestId"],
                command.payload["response"],
            )
        except InteractionError as exc:
            return self._reject(command, exc.code, "User input request is stale or does not match")
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session.session_id,
                              state_revision=session.state_revision)

    def _cancel_turn(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        turn = next((item for item in session.turns
                     if item.turn_id == command.payload["turnId"]), None)
        if turn is None or turn.done.is_set():
            return self._reject(command, "STALE_TURN", "Turn is not active")
        if turn.cancellation.request():
            session.state_revision += 1
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session.session_id,
                              state_revision=session.state_revision)

    def _stop_generation(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        turn = next((item for item in session.turns
                     if item.active_generation == command.payload["generationId"]
                     and not item.done.is_set()), None)
        if turn is None:
            return self._reject(command, "STALE_GENERATION", "Generation is not active")
        if not turn.stop_generation_requested:
            turn.stop_generation_requested = True
            session.state_revision += 1
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session.session_id,
                              state_revision=session.state_revision)

    def _cancel_operation(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        operation_id = command.payload["operationId"]
        service_operation = self._service_operations.get(operation_id)
        if service_operation is not None and not service_operation.done.is_set():
            if service_operation.token.request():
                session.state_revision += 1
            return CommandReceipt(command.command_id, True, session.session_id, session.state_revision)
        pair = next(((turn, turn.tool_operations[operation_id])
                     for turn in session.turns if operation_id in turn.tool_operations), None)
        if pair is None or pair[1].status in (
                OperationStatus.COMPLETED, OperationStatus.FAILED,
                OperationStatus.CANCELLED, OperationStatus.OUTCOME_UNKNOWN):
            return self._reject(command, "STALE_OPERATION", "Operation is not active")
        if pair[1].token.request():
            session.state_revision += 1
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session.session_id,
                              state_revision=session.state_revision)

    def _cancel_sub_agent(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        agent_id = command.payload["agentId"]
        operation = session.agent_operations.get(agent_id)
        if operation is None or operation.status in (
                OperationStatus.COMPLETED, OperationStatus.FAILED,
                OperationStatus.CANCELLED, OperationStatus.OUTCOME_UNKNOWN):
            return self._reject(command, "STALE_AGENT", "Sub-agent is not active")
        if not operation.runner.cancel(agent_id):
            return self._reject(command, "STALE_AGENT", "Sub-agent is not active")
        session.state_revision += 1
        return CommandReceipt(command_id=command.command_id, accepted=True,
                              session_id=session.session_id,
                              state_revision=session.state_revision)

    def _start_sub_agent(self, command: ApplicationCommand) -> CommandReceipt:
        session = self._active_session(command)
        if session is None:
            return self._reject(command, "INVALID_SESSION", "No matching active AgentSession")
        parent = next((t for t in session.turns if t.turn_id == command.payload["parentTurnId"]
                       and not t.done.is_set()), None)
        if parent is None:
            return self._reject(command, "STALE_TURN", "Sub-agent requires an active parent Turn")
        if self._sub_agent_runner is None or self._sub_agent_tool_factory is None:
            return self._reject(command, "SUB_AGENT_UNAVAILABLE", "Sub-agent runner is unavailable")
        task = command.payload["task"]
        if not isinstance(task, str) or not task.strip():
            return self._reject(command, "INVALID_SUB_AGENT_TASK", "Sub-agent task must be text")
        mode = command.payload["mode"]
        if mode not in ("default", "worktree"):
            return self._reject(command, "INVALID_SUB_AGENT_MODE", "Unsupported sub-agent mode")
        selection=command.payload.get('knowledgeCitationIds')
        available={e.citation_id for e in parent.knowledge_admission.capsule.evidence} if parent.knowledge_admission else set()
        if selection is not None and (not isinstance(selection,(list,tuple)) or
                any(not isinstance(i,str) or i not in available for i in selection) or len(selection)!=len(set(selection))):
            return self._reject(command,'SOURCE_NOT_AUTHORIZED','Only parent-admitted evidence can be delegated')
        try:
            tools = self._permitted_tools(self._sub_agent_tool_factory(session.workspace))
            bound = bind_context(self.provider_manager.snapshot(), workspace=session.workspace,
                tools=tools, requested=self._context_selection,
                policy=self._context_policy, capability_factory=self._capability_factory)
            fresh_provider = bound.fresh()
            operation_id, agent_id = new_operation_id(), new_agent_id()
            context = ExecutionContext(
                workspace=session.workspace, cwd=session.workspace,
                environment=session.environment, session_id=session.session_id,
                turn_id=parent.turn_id, operation_id=operation_id,
                agent_id=agent_id, cancellation_token=parent.cancellation.child(),
                deadline=None, capabilities=parent.capabilities or session.capabilities,
                provider_revision=bound.snapshot.provider_revision,
                policy_revision=session.tool_runtime.policy.revision)
            parent_grant = session.tool_runtime.delegation_for(context)
            child = SubAgent(provider=fresh_provider, model=bound.snapshot.model_id,
                tools=tools, prompt=task.strip(),
                description=command.payload.get("description") or "sub-agent task",
                agent_id=agent_id, isolation="worktree" if mode == "worktree" else None,
                cwd=session.workspace, environment=session.environment,
                cancellation_token=context.cancellation_token,
                security_issuer=session.tool_runtime._issuer,
                security_policy=session.tool_runtime.policy, parent_grant=parent_grant,
                filesystem_authority=session.tool_runtime._filesystem,
                process_service=session.tool_runtime._process_service,
                network_service=session.tool_runtime._network_service,
                redactor=self.redactor, security_audit=self.security_audit,
                fetch_enabled=self._fetch_enabled,
                search_enabled=self._search_enabled, browser_enabled=self._browser_enabled)
            child._knowledge_selection=selection
        except SecurityAuditError:
            return self._reject(command, 'SECURITY_AUDIT_PRE_EFFECT_FAILED', 'Audit unavailable; sub-agent not started')
        except Exception:
            return self._reject(command, "SUB_AGENT_SETUP_FAILED", "Could not start sub-agent")
        try:
            self._publish_agent_started(session, child, operation_id, context, self._sub_agent_runner)
        except SecurityAuditError:
            return self._reject(command, 'SECURITY_AUDIT_PRE_EFFECT_FAILED', 'Audit unavailable; sub-agent not started')

        completed_once = Event()
        def completed(result: SubAgentResult) -> None:
            if completed_once.is_set():
                return
            completed_once.set()
            self._publish_agent_completed(session, result, operation_id, context)

        def run() -> None:
            try:
                self._sub_agent_runner.submit(child, on_complete=completed)
            except Exception:
                failure = SubAgentResult(agent_id=agent_id,
                    description=child.description, content="", status="error",
                    duration_seconds=0.0, messages_count=0,
                    tool_calls_count=0, error_message="Sub-agent failed")
                completed(failure)

        Thread(target=run, daemon=True).start()
        return CommandReceipt(command.command_id, True, session.session_id,
            session.state_revision,
            created_ids={"agentId": agent_id, "operationId": operation_id})

    def _run_turn(self, session: AgentSession, turn: Turn) -> None:
        working: _WorkingMessages | None = None
        active_generation: GenerationId | None = None
        tools_fallback_pending = False
        generation_output_observed = False
        # Raw append identity maps to presentation only. No IDs/timestamps are
        # inserted in the model's working messages or persisted transcript.
        display_bindings: dict[int, dict[str, Any]] = {}
        display_streams = {key: self.redactor.stream() for key in ('content_delta', 'thinking_delta')}

        def context_factory() -> ExecutionContext:
            operation_id = new_operation_id()
            token = turn.cancellation.child()
            with self._lock:
                turn.tool_operations[operation_id] = ToolOperation(token)
            return ExecutionContext(
                workspace=session.workspace, cwd=session.workspace,
                environment=session.environment, session_id=session.session_id,
                turn_id=turn.turn_id, operation_id=operation_id,
                cancellation_token=token,
                deadline=self._interaction_deadline_factory(),
                capabilities=turn.capabilities,
                provider_revision=turn.model_runtime.snapshot.provider_revision,
                policy_revision=session.tool_runtime.policy.revision,
            )

        runtime_tools = [LegacyToolAdapter(tool, session.tool_runtime,
                                           context_factory, guard_effects=lambda:turn.effect_constraints)
                         for tool in session.tools]

        def emit_legacy(event: AgentEvent) -> None:
            nonlocal active_generation, tools_fallback_pending, generation_output_observed
            with self._lock:
                previous_generation = active_generation
                # Unsupported native tools change the request format before any
                # model output. That adaptation continues the same response;
                # it is not a failed public reply followed by a new reply.
                reuse_generation = (event.kind == "llm_start"
                    and active_generation is not None and tools_fallback_pending
                    and not generation_output_observed)
                if event.kind == "llm_start":
                    tools_fallback_pending = False
                    if not reuse_generation:
                        if active_generation is not None:
                            self._finish_display(turn, "failed", active_generation)
                        active_generation = new_generation_id()
                        turn.active_generation = active_generation
                        turn.stop_generation_requested = False
                        generation_output_observed = False
                elif event.kind == "tools_fallback":
                    tools_fallback_pending = active_generation is not None
                elif event.kind in display_streams and event.data.get('text'):
                    # Observe before redaction buffering: partial output must
                    # never be erased or reclassified as a pre-output attempt.
                    generation_output_observed = True
                data = self.redactor.value(event.data)
                if event.kind in display_streams:
                    data['text'] = display_streams[event.kind].feed(event.data.get('text', ''))
                elif event.kind in ('assistant_message', 'interrupted', 'stopped'):
                    for key, scrub in display_streams.items():
                        tail = scrub.finish()
                        if tail:
                            # Tail is already safe; publish without feeding it
                            # back into the same stream's prefix buffer.
                            self._observe_display(turn, AgentEvent(key, {'text': tail}))
                            if self._events is not None and active_generation is not None:
                                self._events.publish(EventKind.ASSISTANT_DELTA if key == 'content_delta'
                                    else EventKind.THINKING_DELTA, {'text': tail},
                                    state_revision=session.state_revision, turn_id=turn.turn_id,
                                    generation_id=active_generation)
                event = AgentEvent(event.kind, data)
                if not reuse_generation:
                    self._observe_display(turn, event)
                stream = self._events
                def publish(*args: Any, **kwargs: Any) -> None:
                    if stream is not None:
                        stream.publish(*args, **kwargs)
                cause = CausationId(turn.command_id)
                common = dict(state_revision=session.state_revision,
                              turn_id=turn.turn_id, causation_id=cause)
                if event.kind == "llm_start" and not reuse_generation:
                    if previous_generation is not None:
                        publish(EventKind.GENERATION_FAILED,
                                       {"status": "failed", "reason": "incomplete"},
                                        generation_id=previous_generation, **common)
                    publish(EventKind.GENERATION_STARTED,
                                   {"status": "started", "modelRuntime": turn.model_runtime.snapshot.to_dict()},
                                   generation_id=active_generation, **common)
                    turn.generations[active_generation] = turn.model_runtime.snapshot.to_dict()
                elif event.kind in ("content_delta", "thinking_delta"):
                    text = event.data.get("text")
                    if active_generation is not None and isinstance(text, str):
                        kind = (EventKind.ASSISTANT_DELTA if event.kind == "content_delta"
                                else EventKind.THINKING_DELTA)
                        publish(kind, {"text": text},
                                       generation_id=active_generation, **common)
                elif event.kind in ("tool_start", "tool_result", "error", "debug"):
                    # A temporary internal observation preserves the exact
                    # legacy JSONL view while typed ToolRuntime owns outcomes.
                    publish(EventKind.LEGACY_AGENT_EVENT,
                            {"legacyKind": event.kind, "data": deepcopy(event.data)},
                            visibility=Visibility.INTERNAL, **common)
                elif event.kind == "assistant_message" and active_generation is not None:
                    self._record_citations(turn, event.data.get('message', {}).get('content', ''), active_generation)
                    cancelled = (turn.stop_generation_requested or
                                 turn.cancellation.is_cancel_requested())
                    publish(EventKind.GENERATION_CANCELLED if cancelled
                                   else EventKind.GENERATION_COMPLETED,
                                   {"status": "cancelled" if cancelled else "completed"},
                                   generation_id=active_generation, **common)
                    active_generation = None
                    turn.active_generation = None
                elif event.kind in ("interrupted", "stopped") and active_generation is not None:
                    publish(EventKind.GENERATION_CANCELLED,
                                   {"status": "cancelled"},
                                   generation_id=active_generation, **common)
                    active_generation = None
                    turn.active_generation = None
                elif event.kind in ("rescue", "loop_warning", "loop_break", "limit",
                                    "reminder", "verify_warning", "compaction",
                                    "retry", "nudge", "error_stop", "empty_response",
                                    "tools_fallback", "write_deferred",
                                    "deliverable_nudge", "read_gate"):
                    # Legacy payloads may contain commands, tool output or
                    # credentials. Publish only the intervention name.
                    publish(EventKind.HARNESS_INTERVENTION,
                                   {"rule": event.kind}, **common)
                elif event.kind in ("context_budget", "context_usage", "memory_recall", "knowledge_recall"):
                    session.state_revision += 1
                    turn.context_reports.append(deepcopy(event.data))
                    publish(EventKind.HARNESS_INTERVENTION, event.data,
                            state_revision=session.state_revision, turn_id=turn.turn_id,
                            generation_id=active_generation, causation_id=cause)

        try:
            citation_receipts = {}
            def captured_message(message):
                return deepcopy(citation_receipts.get(id(message),self._citation_message(turn,message)))
            def checkpoint(additions):
                with self._lock:
                    for message in additions:
                        if isinstance(message,dict) and id(message) not in citation_receipts:
                            citation_receipts[id(message)] = self._citation_message(turn,message)
                            if message.get("role") == "assistant":
                                row = next((row for row in reversed(turn.display_messages)
                                    if active_generation is not None
                                    and row.get("generationId") == active_generation
                                    and row.get("status") == "streaming"), None)
                                if row is None:
                                    # A host fallback or a compatible runtime may
                                    # append an assistant message without llm_start.
                                    row = self._new_display_message()
                                    turn.display_messages.append(row)
                                display_bindings[id(message)] = row
                if self._persistence is not None:
                    with self._lock:
                        self._persistence.save(self._saved_transcript(session, self.redactor.messages(session.transcript + [captured_message(m) for m in additions
                            if isinstance(m, dict) and m.get("role") in ("assistant", "tool")])))
            # Persisted provenance is not a user assertion/provider field. Old
            # Turn citation IDs must never authorize references in a new Turn.
            inference_history = [{k:v for k,v in m.items() if k not in ('attachmentRefs','knowledgeCitations','sourceContext')}
                                 for m in session.transcript]
            for item in inference_history:
                if item.get('role') == 'tool' and (item.get('tool_name') or item.get('name')) == 'source_read':
                    item['content'] = 'Previous-Turn source read omitted. Reselect the source to read its current prepared copy.'
            working = _WorkingMessages(inference_history, on_append=checkpoint)
            private_remote = (getattr(self._knowledge.factory,'context_available',False) and
                not local_memory_destination(turn.model_runtime.snapshot))
            if private_remote:
                from local_cli.core.context import message_kind
                for message in list(working):
                    # Legacy notes/RAG have no per-source forwarding consent or
                    # V1 citation provenance. Preserve history, deny forwarding.
                    if message_kind(message) in ('retrieval','knowledge'):
                        working.remove(message)
            if self._auxiliary_services is not None:
                plan_factory=getattr(self._auxiliary_services,'plan_context',None)
                plan=plan_factory() if callable(plan_factory) else None
                if (isinstance(plan,dict) and plan.get('role') in ('user','system')
                        and isinstance(plan.get('content'),str)):
                    working.insert(len(working)-1,self.redactor.value(plan))
            if self._rag.status()["enabled"] and not getattr(self._knowledge.factory, 'replaces_legacy_rag', False):
                rag_op = ServiceOperation(new_operation_id(), turn.command_id,
                    token=turn.cancellation.child(), turn_id=turn.turn_id)
                with self._lock:
                    self._service_operations[rag_op.operation_id] = rag_op
                if private_remote:
                    from local_cli.application.rag import RAGResponse,RAGState
                    from local_cli.core.rag import RAGError
                    response=RAGResponse(rag_op.operation_id,True,RAGState.UNAVAILABLE,
                        error=RAGError('REMOTE_FORWARDING_DENIED','Legacy document forwarding requires source consent.'))
                elif self._memory_worker and not self._memory_worker.done.is_set():
                    from local_cli.application.rag import RAGResponse,RAGState
                    from local_cli.core.rag import RAGError
                    response=RAGResponse(rag_op.operation_id,True,RAGState.UNAVAILABLE,
                        error=RAGError('RAG_BUSY','Optional document retrieval deferred for foreground priority.'))
                else:response = self._rag.query(session.transcript[-1]["content"], operation_id=rag_op.operation_id,
                    progress=lambda p: self._rag_progress(session, p, turn_id=turn.turn_id,
                                                          causation_id=CausationId(turn.command_id)))
                self._finish_service_operation(session, rag_op,
                    OperationStatus.CANCELLED if rag_op.token.is_cancel_requested() else
                    OperationStatus.FAILED if response.error else OperationStatus.COMPLETED,
                    {"availability": response.state.value, "error": response.error.to_dict() if response.error else None,
                     "matchCount": len(response.matches)})
                retrieval = response.context_message()
                if retrieval is not None and not rag_op.token.is_cancel_requested():
                    # Temporary context only; never persist/index chat as RAG.
                    working.insert(len(working) - 1, retrieval)
            turn.model_runtime = bind_context(turn.model_runtime,
                workspace=session.workspace, tools=session.tools,
                requested=self._context_selection, policy=self._context_policy,
                current_message=session.transcript[-1]["content"],
                report=lambda payload: emit_legacy(AgentEvent(payload["rule"], payload)),
                capability_factory=self._capability_factory)
            turn.capabilities = turn.model_runtime._context.capabilities
            self._stage_knowledge(session, turn, working)
            if (self._memory_factory is not None and local_memory_destination(turn.model_runtime.snapshot)
                    and not turn.cancellation.is_cancel_requested()):
                try:
                    with self._lock:
                        if self._memory is None:
                            self._memory = self._memory_factory(session.workspace, self.redactor)
                        self._memory.refresh_settings(session.workspace)
                    recalled = MemoryRetriever(self._memory).retrieve(session.transcript[-1]['content'],
                        workspace=session.workspace, at=datetime.now(timezone.utc),
                        semantic_allowed=not (self._memory_worker and not self._memory_worker.done.is_set()))
                except Exception as exc:
                    # Optional recall failure is observable, never a failed
                    # write turned into success, and never an implicit retry.
                    recalled = TurnMemorySnapshot(error_code=exc.code if isinstance(exc, MemoryError)
                        else 'MEMORY_UNAVAILABLE')
                if turn.cancellation.is_cancel_requested():
                    recalled = TurnMemorySnapshot(error_code='MEMORY_RETRIEVAL_CANCELLED')
                # RAG and MEMORY are distinct stores, but one payload budget.
                # Remove only literal duplicate data, not similar facts.
                if self._rag.status()['enabled'] and 'retrieval' in locals() and retrieval is not None:
                    from local_cli.application.retrieval_context import rag_message
                    if retrieval in working:working.remove(retrieval)
                    retrieval=rag_message(response,recalled,self.redactor)
                    if retrieval is not None:working.insert(len(working)-1,retrieval)
                turn.memory_snapshot = admit_capsule(working, turn.model_runtime._context.manager,
                    turn.model_runtime.format_tools(session.tools), recalled)
                emit_legacy(AgentEvent('memory_recall', {'rule':'memory_recall',
                    **turn.memory_snapshot.metadata()}))
            if turn.knowledge_admission is not None:
                turn.knowledge_admission.freeze(working,turn.model_runtime._context.manager,
                    turn.model_runtime.format_tools(session.tools))
                self._record_source_context(session, turn)
                emit_legacy(AgentEvent('knowledge_recall',turn.knowledge_admission.metadata()))
            with self._lock:
                session.capabilities = turn.capabilities
            turn.model_runtime._context.memory_source=lambda:self._revalidate_memory(session,turn,working)
            turn.model_runtime._context.knowledge_source=lambda:self._revalidate_knowledge(session,turn,working)
            turn.model_runtime._context.knowledge_output=turn.knowledge_admission is not None
            turn.model_runtime._context.turn_effect_constraints=turn.effect_constraints
            outcome = self._runtime.run_turn(
                provider=turn.model_runtime, model=turn.model_runtime.snapshot.model_id,
                tools=runtime_tools, messages=working, emit=emit_legacy,
                should_stop=lambda: (turn.cancellation.is_cancel_requested()
                                     or turn.stop_generation_requested),
            )
        except BaseException as exc:
            if turn.attachment_refs:
                self._record_source_context(session, turn, error=getattr(exc, 'code', 'SOURCE_INPUT_UNAVAILABLE'))
            outcome = TurnOutcome(TurnStatus.FAILED,
                                  error_code=getattr(exc, "code", type(exc).__name__))
        # Cancellation is a request, not evidence that background children
        # have stopped. Wait outside the session lock so their callbacks can
        # record their actual outcomes before the parent Turn becomes terminal.
        if turn.cancellation.is_cancel_requested():
            with self._lock:
                children = [operation for operation in session.agent_operations.values()
                            if operation.parent_turn_id == turn.turn_id]
            for child in children:
                child.done.wait()
        with self._lock:
            if active_generation is not None:
                kind = (EventKind.GENERATION_CANCELLED
                        if turn.cancellation.is_cancel_requested()
                        or turn.stop_generation_requested else
                        EventKind.GENERATION_COMPLETED
                        if isinstance(outcome, TurnOutcome)
                        and outcome.status is TurnStatus.COMPLETED
                        else EventKind.GENERATION_FAILED)
                status = ("completed" if kind is EventKind.GENERATION_COMPLETED
                          else "cancelled" if kind is EventKind.GENERATION_CANCELLED
                          else "failed")
                if self._events is not None:
                    self._events.publish(
                        kind, {"status": status},
                        state_revision=session.state_revision,
                        turn_id=turn.turn_id, generation_id=active_generation,
                        causation_id=CausationId(turn.command_id),
                    )
                turn.active_generation = None
            try:
                # The canonical transcript never loses prior turns when the
                # harness compacts its private working context.
                appended = [message for message in (working.appended if working is not None else ())
                            if isinstance(message, dict) and message.get("role") in ("assistant", "tool")]
                additions = self.redactor.messages([captured_message(message) for message in appended])
                first_index = len(session.transcript)
                session.transcript.extend(additions)
                for offset, message in enumerate(appended):
                    row = display_bindings.get(id(message))
                    if row is not None:
                        row["sourceIndex"] = first_index + offset
                        row["content"] = additions[offset].get("content") or ""
            except Exception:
                outcome = TurnOutcome(TurnStatus.FAILED,
                                      error_code="TRANSCRIPT_CAPTURE_FAILED")
            if not isinstance(outcome, TurnOutcome):
                outcome = TurnOutcome(TurnStatus.FAILED,
                                      error_code="INVALID_RUNTIME_OUTCOME")
            if turn.cancellation.is_cancel_requested():
                outcome = (TurnOutcome(TurnStatus.FAILED,
                                       error_code="OUTCOME_UNKNOWN")
                           if turn.has_unknown_effect else
                           TurnOutcome(TurnStatus.CANCELLED,
                                       final_content=outcome.final_content))
            turn.status = advance_turn_status(turn.status, outcome.status)
            turn.operation_status = advance_operation_status(
                turn.operation_status,
                OperationStatus.OUTCOME_UNKNOWN
                if outcome.error_code == "OUTCOME_UNKNOWN"
                else OperationStatus(outcome.status.value),
            )
            turn.final_content = self.redactor.text(outcome.final_content)
            self._finish_display(turn, turn.status.value)
            turn.transcript_end = len(session.transcript)
            turn.error_code = self.redactor.text(outcome.error_code)
            if outcome.status is TurnStatus.FAILED:
                self.provider_manager.invalidate_observation(turn.model_runtime, outcome.error_code)
            turn.terminal_count += 1
            session.state_revision += 1
            if self._persistence is not None:
                self._persistence.save(self._saved_transcript(session))
            self._publish_turn_terminal(session, turn)
            self.provider_manager.end_turn(turn.turn_id)
            if turn.model_runtime._context is not None:
                turn.model_runtime._context.memory_source=None
                turn.model_runtime._context.knowledge_source=None
                turn.model_runtime._context.manager.invalidate_cache()
            turn.done.set()

        # Already terminal: maintenance owns a different operation and never
        # appends to transcript, reopens Turn or changes its observed result.
        if self._memory_capture_mode!='off':
            self._queue_memory(session,turn)

    def _stage_knowledge(self, session, turn, working):
        """One scoped documentary query per Turn, never per Generation/child."""
        if not getattr(self._knowledge.factory,'context_available',False): return
        from local_cli.application.knowledge_context import KnowledgeAdmission
        from local_cli.core.knowledge import KnowledgeError
        operation = ServiceOperation(new_operation_id(),turn.command_id,
            token=turn.cancellation.child(),turn_id=turn.turn_id,service='knowledge-retrieval')
        with self._lock: self._service_operations[operation.operation_id] = operation
        context = ExecutionContext(workspace=session.workspace,cwd=session.workspace,
            environment=session.environment,session_id=session.session_id,turn_id=turn.turn_id,
            operation_id=operation.operation_id,cancellation_token=operation.token,
            deadline=self._interaction_deadline_factory(),capabilities=turn.capabilities)
        status = OperationStatus.COMPLETED
        response = {}
        try:
            if self._knowledge.service is None:
                # Existing managed corpus only: no path acquisition, legacy
                # rebuild, MemoryStore write, auto-index or embedding discovery.
                self._knowledge.service = self._knowledge.factory(session.workspace,str(session.session_id),lambda k,p:None)
            from local_cli.application.selected_sources import SelectedSourceAdmission
            admission_type = SelectedSourceAdmission if turn.attachment_refs else KnowledgeAdmission
            admission = admission_type(str(turn.turn_id),self._knowledge.service,self.redactor)
            turn.knowledge_admission = admission
            admission.retrieve(session.transcript[-1]['content'],context=context,refs=turn.attachment_refs,
                local_destination=local_memory_destination(turn.model_runtime.snapshot))
            if operation.token.is_cancel_requested():
                status = OperationStatus.CANCELLED
            else:
                admission.stage(working,turn.model_runtime._context.manager,turn.model_runtime.format_tools(session.tools))
            response = admission.metadata()
        except Exception as exc:
            status = OperationStatus.CANCELLED if operation.token.is_cancel_requested() else OperationStatus.FAILED
            response = {'error':{'code':exc.code if isinstance(exc,KnowledgeError) else 'KNOWLEDGE_RETRIEVAL_FAILED'}}
            if turn.knowledge_admission is not None:
                turn.knowledge_admission._remove(working)
                turn.knowledge_admission.pending=()
                turn.knowledge_admission.error_code=response['error']['code']
            if turn.attachment_refs:
                self._record_source_context(session, turn, error=response['error']['code'])
                self._finish_service_operation(session,operation,status,response)
                raise
        self._finish_service_operation(session,operation,status,response)

    def _record_source_context(self, session, turn, error=None):
        if not turn.attachment_refs: return
        from local_cli.application.selected_sources import SelectedSourceAdmission
        admission = turn.knowledge_admission
        rows = (admission.metadata()['selectedSources'] if isinstance(admission, SelectedSourceAdmission) else
            [dict(sourceId=r.source_id, revisionId=r.revision_id, displayName=r.display_name,
                status='unavailable', errorCode=error or 'SOURCE_CONTENT_UNAVAILABLE') for r in turn.attachment_refs])
        if error:
            rows = [dict(row, status='unavailable', errorCode=error) for row in rows]
        with self._lock:
            session.transcript[turn.transcript_start]['sourceContext'] = self.redactor.value(rows)

    def _revalidate_knowledge(self,session,turn,working):
        admission = turn.knowledge_admission
        if admission is None: return
        manager = turn.model_runtime._context.manager
        try:
            admission.revalidate(working,manager)
            self._record_source_context(session, turn)
            # Tool continuity/current input retain precedence in later rounds,
            # too. An optional static guard must not make them impossible.
            manager.prepare(working,turn.model_runtime.format_tools(session.tools))
        except Exception as exc:
            from local_cli.core.knowledge_context import KnowledgeCapsule
            admission._remove(working)
            admission.capsule = KnowledgeCapsule.empty(str(turn.turn_id))
            admission.error_code = 'STALE_SOURCE'
            manager.invalidate_cache()
            if turn.attachment_refs:
                # Required user-selected input cannot silently disappear while
                # inference continues as if the source had been delivered.
                self._record_source_context(session, turn, error=getattr(exc, 'code', 'SOURCE_CONTENT_UNAVAILABLE'))
                raise

    @staticmethod
    def _citation_message(turn, message):
        result = deepcopy(message)
        result.pop('knowledgeCitations',None)  # Never trust a provider-supplied receipt.
        if result.get('role') == 'assistant':
            from local_cli.core.knowledge_context import CitationRegistry
            registry = (getattr(turn.knowledge_admission, 'citation_registry', turn.knowledge_admission.capsule.citation_registry) if turn.knowledge_admission
                        else CitationRegistry(str(turn.turn_id)))
            report = registry.validate(result.get('content') or '',turn_id=str(turn.turn_id))
            if report['valid'] or report['invalid']: result['knowledgeCitations'] = report
        return result

    def _record_citations(self, turn, text, generation_id):
        report = self._citation_message(turn,{'role':'assistant','content':text}).get('knowledgeCitations')
        if not report: return
        turn.citation_reports.append(dict(generationId=generation_id,**report))
        if report['invalid'] and self._events is not None:
            self._events.publish(EventKind.HARNESS_INTERVENTION,{'rule':'knowledge.citation.invalid',
                'errorCode':'CITATION_INVALID','invalidCount':len(report['invalid'])},
                state_revision=self._session.state_revision,turn_id=turn.turn_id,generation_id=generation_id)

    def _revalidate_memory(self,session,turn,working):
        """Bounded ID/revision reads; no new retrieval/embedding each generation."""
        if self._memory is None or turn.memory_snapshot is None or not turn.memory_snapshot.records:return
        from local_cli.application.retrieval_context import current_snapshot
        from local_cli.application.memory_recall import MemoryCapsule,MEMORY_GUARD
        with self._lock:
            try:updated=current_snapshot(self._memory,turn.memory_snapshot,workspace=session.workspace,at=datetime.now(timezone.utc))
            except Exception:updated=replace(turn.memory_snapshot,records=(),capsule=None,error_code='MEMORY_UNAVAILABLE')
            if updated.records==turn.memory_snapshot.records:return
            for message in list(working):
                if message.get('_context_kind')=='memory' or message.get('content')==MEMORY_GUARD:working.remove(message)
            if updated.capsule:
                working.insert(0,dict(role='system',content=MEMORY_GUARD))
                working.insert(len(working)-1,MemoryCapsule.message(updated.capsule))
            turn.memory_snapshot=updated
            turn.model_runtime._context.manager.invalidate_cache()

    def _publish_turn_terminal(self, session: AgentSession, turn: Turn) -> None:
        stream = self._events
        if stream is None:
            return
        cause = CausationId(turn.command_id)
        op_kind = operation_terminal_kind(OperationType.OTHER, turn.operation_status)
        stream.publish(
            op_kind,
            {"status": turn.operation_status.value, "operationType": "OTHER"},
            state_revision=session.state_revision, turn_id=turn.turn_id,
            operation_id=turn.operation_id, causation_id=cause,
        )
        turn_kind = {
            TurnStatus.COMPLETED: EventKind.TURN_COMPLETED,
            TurnStatus.CANCELLED: EventKind.TURN_CANCELLED,
            TurnStatus.FAILED: EventKind.TURN_FAILED,
        }[turn.status]
        stream.publish(turn_kind, {"status": turn.status.value,
                                   "errorCode": turn.error_code},
                       state_revision=session.state_revision,
                       turn_id=turn.turn_id, causation_id=cause)

    @staticmethod
    def _new_display_message(generation_id=None) -> dict[str, Any]:
        return {"id": "message_" + uuid4().hex,
            "createdAt": datetime.now(timezone.utc).isoformat(), "status": "streaming",
            **({"generationId": generation_id} if generation_id is not None else {}),
            "role": "assistant", "content": "", "thinking": True,
            "toolCalls": [], "toolResults": [], "harnessEvents": []}

    @staticmethod
    def _finish_display(turn: Turn, status: str, generation_id=None) -> None:
        for row in turn.display_messages:
            if row.get("status") != "streaming" or (generation_id is not None
                    and row.get("generationId") != generation_id):
                continue
            row.update(status=status, completedAt=datetime.now(timezone.utc).isoformat(), thinking=False)

    @staticmethod
    def _observe_display(turn: Turn, event: AgentEvent) -> None:
        """Recover a live view after renderer reload or journal eviction.

        This projection belongs to Application and is returned only through
        session-owner snapshots. It does not affect harness/model messages.
        """
        if event.kind == "llm_start":
            turn.display_messages.append(AgentSessionCoordinator._new_display_message(turn.active_generation))
        if not turn.display_messages:
            return
        last = turn.display_messages[-1]
        if event.kind == "content_delta":
            last["content"] += event.data.get("text", "")
            last["thinking"] = False
        elif event.kind == "assistant_message":
            last["content"] = event.data.get("message", {}).get("content") or ""
            AgentSessionCoordinator._finish_display(turn,
                "cancelled" if turn.stop_generation_requested or turn.cancellation.is_cancel_requested()
                else "completed", last.get("generationId"))
        elif event.kind in ("interrupted", "stopped"):
            AgentSessionCoordinator._finish_display(turn, "cancelled", last.get("generationId"))
        elif event.kind == "tool_start":
            last["thinking"] = False
            last["toolCalls"].append({"name": event.data["tool_name"],
                                      "args": deepcopy(event.data["arguments"])})
        elif event.kind == "tool_result":
            last["toolResults"].append({"name": event.data["tool_name"],
                                        "output": event.data["result"]})
        elif event.kind in ("rescue", "loop_warning", "loop_break", "limit",
                            "reminder", "verify_warning", "compaction", "retry",
                            "nudge", "error_stop", "empty_response", "tools_fallback",
                            "write_deferred", "deliverable_nudge", "read_gate"):
            last["harnessEvents"].append(event.kind)

    def _publish_tool_event(self, session: AgentSession | None,
                            event: ToolEvent) -> None:
        if session is None:
            return
        kind, invocation, result = event
        with self._lock:
            stream = self._events
            turn = next((item for item in session.turns
                         if item.turn_id == invocation.context.turn_id), None)
            if turn is None:
                raise ValueError("tool invocation has no matching Turn")
            operation = turn.tool_operations.get(invocation.operation_id)
            if operation is None:
                operation = ToolOperation(invocation.context.cancellation_token)
                turn.tool_operations[invocation.operation_id] = operation
            if kind is EventKind.TOOL_STARTED:
                operation.status = advance_operation_status(
                    operation.status, OperationStatus.RUNNING)
            elif kind in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED):
                if result is None:
                    raise ValueError("terminal tool event requires a result")
                operation.status = advance_operation_status(
                    operation.status, result.operation_outcome)
                if result.operation_outcome is OperationStatus.OUTCOME_UNKNOWN:
                    turn.has_unknown_effect = True
                if invocation.name in ("write", "edit", "bash"):
                    session.filesystem_revision += 1
            activity = self._tool_activity(turn, invocation)
            activity['operationStatus'] = operation.status.value
            if kind is EventKind.TOOL_STARTED:
                activity.update(status='running', startedAt=datetime.now(timezone.utc).isoformat(),
                    outputSequence=activity['outputSequence'] + 1)
            if result is not None:
                output, output_cut = self._bounded_tool_text(tool_result_to_legacy_text(result))
                stdout, stdout_cut = self._bounded_tool_text(result.stdout)
                stderr, stderr_cut = self._bounded_tool_text(result.stderr)
                activity.update(status=result.status.value, effectState=result.effect_state.value,
                    output=output, stdout=stdout, stderr=stderr,
                    outputSequence=activity['outputSequence'] + 1,
                    outputTruncated=bool(output_cut or stdout_cut or stderr_cut or
                        result.metadata.get('truncated') or result.metadata.get('stdoutTruncated') or
                        result.metadata.get('stderrTruncated')),
                    completedAt=datetime.now(timezone.utc).isoformat())
                if result.exit_code is not None:
                    activity['exitCode'] = result.exit_code
                error = (result.metadata.get('securityErrorCode') or
                         result.metadata.get('turnConstraintCode') or result.error)
                if error:
                    activity['errorCode'] = self._bounded_tool_text(str(error), 256)[0]
            payload = {"name": invocation.name}
            if result is not None:
                payload.update({
                    "status": result.operation_outcome.value,
                    "toolStatus": result.status.value,
                    "effectState": result.effect_state.value,
                    "operationType": "TOOL",
                    "cached": result.metadata.get("cached", False),
                })
                if 'securityAudit' in result.metadata:
                    payload['securityAudit'] = result.metadata['securityAudit']
            if stream is not None:
                stream.publish(
                    kind, payload, state_revision=session.state_revision,
                    turn_id=turn.turn_id, operation_id=invocation.operation_id,
                    tool_call_id=invocation.tool_call_id,
                    causation_id=CausationId(turn.command_id),
                )
                stream.publish(EventKind.OPERATION_PROGRESS, {
                    'service': 'tool', 'operationType': 'TOOL',
                    'operationId': invocation.operation_id, 'toolCallId': invocation.tool_call_id,
                    'turnId': turn.turn_id, 'outputSequence': activity['outputSequence'],
                    'activity': deepcopy(activity),
                }, state_revision=session.state_revision, visibility=Visibility.SENSITIVE,
                    turn_id=turn.turn_id, operation_id=invocation.operation_id,
                    tool_call_id=invocation.tool_call_id, causation_id=CausationId(turn.command_id))

    def _bounded_tool_text(self, text: str, limit: int = TOOL_OUTPUT_BYTES) -> tuple[str, bool]:
        safe = self.redactor.text(text)
        encoded = safe.encode('utf-8')
        return encoded[:limit].decode('utf-8', errors='ignore'), len(encoded) > limit

    def _tool_activity(self, turn: Turn, invocation) -> dict[str, Any]:
        arguments = self.redactor.value(invocation.arguments)
        encoded = json.dumps(arguments, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(encoded) > TOOL_ARGUMENT_BYTES:
            # Preview is JSON text inside a JSON string: reserve its possible
            # second escaping of quotes/backslashes as well as the wrapper.
            arguments = {'preview': encoded[:(TOOL_ARGUMENT_BYTES - 64) // 2].decode('utf-8', errors='ignore'),
                         'truncated': True}
        return turn.tool_activities.setdefault(invocation.operation_id, {
            'operationId': invocation.operation_id, 'toolCallId': invocation.tool_call_id,
            'turnId': turn.turn_id,
            'messageId': turn.display_messages[-1]['id'] if turn.display_messages else None,
            'name': invocation.name, 'arguments': arguments,
            'cwd': self.redactor.text(str(invocation.context.cwd)), 'status': 'pending',
            'operationStatus': 'requested', 'effectState': 'none',
            'output': '', 'stdout': '', 'stderr': '', 'outputSequence': 0,
            'outputTruncated': False,
        })

    def _publish_tool_progress(self, session: AgentSession, invocation,
                               channel: str, text: str, truncated: bool) -> None:
        if channel not in ('stdout', 'stderr'):
            return
        with self._lock:
            turn = next((item for item in session.turns
                         if item.turn_id == invocation.context.turn_id), None)
            if turn is None:
                return
            activity = turn.tool_activities.get(invocation.operation_id)
            if activity is None or activity['status'] != 'running':
                return  # A terminal receipt is authoritative, including late output.
            retained = len(activity['output'].encode('utf-8'))
            safe, cut = self._bounded_tool_text(text, max(0, TOOL_OUTPUT_BYTES - retained))
            activity['outputTruncated'] |= truncated or cut
            if not safe and not (truncated or cut):
                return
            activity[channel] += safe
            activity['output'] += safe
            activity['outputSequence'] += 1
            if self._events is not None:
                self._events.publish(EventKind.OPERATION_PROGRESS, {
                    'service': 'tool', 'operationType': 'TOOL', 'channel': channel,
                    'text': safe, 'outputSequence': activity['outputSequence'],
                    'outputTruncated': activity['outputTruncated'],
                    'operationId': invocation.operation_id, 'toolCallId': invocation.tool_call_id,
                    'turnId': turn.turn_id, 'messageId': activity['messageId'],
                }, state_revision=session.state_revision, visibility=Visibility.SENSITIVE, turn_id=turn.turn_id,
                    operation_id=invocation.operation_id, tool_call_id=invocation.tool_call_id,
                    causation_id=CausationId(turn.command_id))

    def _publish_approval_required(self, session: AgentSession,
                                   request: ApprovalRequest) -> None:
        with self._lock:
            session.state_revision += 1
            if self._events is None:
                return
            turn = next(item for item in session.turns
                        if item.turn_id == request.turn_id)
            self._events.publish(
                EventKind.APPROVAL_REQUIRED,
                {"name": request.tool_name, "arguments": request.arguments,
                 "cwd": request.cwd, "policyRevision": request.policy_revision,
                 "requestDigest": request.request_digest,
                 "deadline": request.deadline.isoformat() if request.deadline else None},
                state_revision=session.state_revision,
                visibility=Visibility.SENSITIVE,
                turn_id=request.turn_id, operation_id=request.operation_id,
                tool_call_id=request.tool_call_id,
                approval_id=request.approval_id,
                causation_id=CausationId(turn.command_id),
            )

    def _publish_approval_resolved(self, session: AgentSession,
                                   request: ApprovalRequest,
                                   approved: bool, reason: str) -> None:
        with self._lock:
            session.state_revision += 1
            if self._events is None:
                return
            turn = next(item for item in session.turns
                        if item.turn_id == request.turn_id)
            self._events.publish(
                EventKind.APPROVAL_RESOLVED,
                {"approved": approved, "reason": reason},
                state_revision=session.state_revision,
                turn_id=request.turn_id, operation_id=request.operation_id,
                tool_call_id=request.tool_call_id,
                approval_id=request.approval_id,
                causation_id=CausationId(turn.command_id),
            )

    def _publish_user_input_required(self, session: AgentSession,
                                     request: UserInputRequest) -> None:
        with self._lock:
            session.state_revision += 1
            if self._events is None:
                return
            turn = next(item for item in session.turns
                        if item.turn_id == request.turn_id)
            self._events.publish(
                EventKind.USER_INPUT_REQUIRED,
                {"inputRequestId": request.input_request_id,
                 "question": request.question,
                 "deadline": request.deadline.isoformat() if request.deadline else None},
                state_revision=session.state_revision,
                visibility=Visibility.SENSITIVE,
                turn_id=request.turn_id, operation_id=request.operation_id,
                tool_call_id=request.tool_call_id,
                causation_id=CausationId(turn.command_id),
            )

    def _publish_user_input_resolved(self, session: AgentSession,
                                     request: UserInputRequest,
                                     reason: str) -> None:
        with self._lock:
            session.state_revision += 1
            if self._events is None:
                return
            turn = next(item for item in session.turns
                        if item.turn_id == request.turn_id)
            self._events.publish(
                EventKind.USER_INPUT_RESOLVED,
                {"inputRequestId": request.input_request_id, "reason": reason},
                state_revision=session.state_revision,
                turn_id=request.turn_id, operation_id=request.operation_id,
                tool_call_id=request.tool_call_id,
                causation_id=CausationId(turn.command_id),
            )

    def _publish_agent_started(self, session: AgentSession,
                               sub_agent: SubAgent,
                               operation_id: OperationId,
                               context: ExecutionContext,
                               runner: SubAgentRunner) -> None:
        with self._lock:
            turn = next(item for item in session.turns
                        if item.turn_id == context.turn_id)
            # Both model-requested and trusted-host child creation pass here.
            # A child prompt cannot lift its current parent Turn's reduction.
            if turn.effect_constraints is not None:
                sub_agent._turn_effect_constraints = turn.effect_constraints
            if sub_agent.agent_id in session.agent_operations:
                raise ValueError("duplicate agentId")
            if turn.knowledge_admission is not None and turn.knowledge_admission.capsule.evidence:
                from local_cli.application.knowledge_children import child_knowledge_source
                sub_agent.bind_knowledge_delegate(child_knowledge_source(turn.knowledge_admission,
                    local_destination=bool(sub_agent.model_snapshot and local_memory_destination(sub_agent.model_snapshot)),
                    selected_ids=getattr(sub_agent,'_knowledge_selection',None)))
            if (self._memory is not None and turn.memory_snapshot is not None
                    and sub_agent.model_snapshot and local_memory_destination(sub_agent.model_snapshot)):
                from local_cli.application.memory_children import child_memory_source
                sub_agent.bind_memory_delegate(child_memory_source(self._memory,turn.memory_snapshot,
                    session.workspace,sub_agent._prompt))
            if self.security_audit is not None:
                self.security_audit.agent(context, operation_id, sub_agent.agent_id, started=True)
                from types import SimpleNamespace
                self.security_audit.before_effect(SimpleNamespace(
                    context=replace(context, operation_id=operation_id, agent_id=sub_agent.agent_id),
                    operation_id=operation_id, name='agent', tool_call_id=None), origin='application')
            session.agent_operations[sub_agent.agent_id] = AgentOperation(
                operation_id=operation_id, parent_turn_id=turn.turn_id,
                runner=runner,
            )
            session.state_revision += 1
            if self._events is not None:
                self._events.publish(
                    EventKind.AGENT_STARTED,
                    {"status": "running", "operationType": "SUB_AGENT",
                     "modelRuntime": sub_agent.model_snapshot.to_dict() if sub_agent.model_snapshot else None},
                    state_revision=session.state_revision,
                    turn_id=turn.turn_id, operation_id=operation_id,
                    agent_id=AgentId(sub_agent.agent_id),
                    causation_id=CausationId(turn.command_id),
                )

    def _publish_agent_completed(self, session: AgentSession,
                                 result: SubAgentResult,
                                 operation_id: OperationId,
                                 context: ExecutionContext) -> None:
        with self._lock:
            operation = session.agent_operations.get(result.agent_id)
            if operation is None or operation.operation_id != operation_id:
                return
            if operation.done.is_set():return
            status = ({"success": OperationStatus.COMPLETED,
                       "cancelled": OperationStatus.CANCELLED,
                       "outcome_unknown": OperationStatus.OUTCOME_UNKNOWN,
                       "timeout": OperationStatus.OUTCOME_UNKNOWN}
                      .get(result.status, OperationStatus.FAILED))
            operation.status = advance_operation_status(operation.status, status)
            audit_lost = False
            if self.security_audit is not None:
                audit_lost = not self.security_audit.agent(context, operation_id, result.agent_id,
                                          started=False, outcome=status.value)
            if status is OperationStatus.OUTCOME_UNKNOWN:
                turn = next(item for item in session.turns
                            if item.turn_id == operation.parent_turn_id)
                turn.has_unknown_effect = True
            session.state_revision += 1
            if self._events is not None:
                turn = next(item for item in session.turns
                            if item.turn_id == operation.parent_turn_id)
                self._events.publish(
                    operation_terminal_kind(OperationType.SUB_AGENT, status),
                    {"status": status.value, "operationType": "SUB_AGENT",
                     "content": result.content, "duration": result.duration_seconds,
                     "toolCalls": result.tool_calls_count,
                     "error": result.error_message,
                     **({'securityAudit': {'gap': True, 'errorCode': 'SECURITY_AUDIT_DELIVERY_FAILED',
                                          'retryAllowed': False}} if audit_lost else {})},
                    state_revision=session.state_revision,
                    visibility=Visibility.SENSITIVE,
                    turn_id=turn.turn_id, operation_id=operation_id,
                    agent_id=AgentId(result.agent_id),
                    causation_id=CausationId(turn.command_id),
                )
            operation.done.set()
            if self._memory is not None and result.status=='success':
                from local_cli.application.memory_children import CHILD_HEADER
                if CHILD_HEADER in result.content:self._child_memory_proposal(session,result,context,operation_id)

    def _child_memory_proposal(self,session,result,context,child_operation_id):
        from types import SimpleNamespace
        from local_cli.core.security_audit import AuditKind
        from local_cli.application.memory_children import persist_child_proposal
        turn=next(t for t in session.turns if t.turn_id==context.turn_id)
        op=ServiceOperation(new_operation_id(),turn.command_id,service='memory-proposal',
            deadline=datetime.now(timezone.utc)+timedelta(seconds=30))
        self._service_operations[op.operation_id]=op
        op.progress={'phase':'proposal','quota':1,'deadline':op.deadline.isoformat()}
        invocation=SimpleNamespace(context=replace(context,operation_id=op.operation_id),
            operation_id=op.operation_id,name='memory_child_proposal',arguments={},tool_call_id=None)
        status=OperationStatus.FAILED;summary={}
        try:
            if turn.cancellation.is_cancel_requested():raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
            if self.security_audit:
                self.security_audit.request(invocation,origin='application')
                self.security_audit.record(invocation,AuditKind.POLICY,{'decision':'PROPOSE_ONLY'},origin='application')
                self.security_audit.before_effect(invocation,origin='application')
            summary=persist_child_proposal(self._memory,result,workspace=session.workspace,
                session_id=session.session_id,turn_id=turn.turn_id,operation_id=child_operation_id)
            status=OperationStatus.COMPLETED
        except (MemoryError,SecurityAuditError) as exc:
            status=OperationStatus.OUTCOME_UNKNOWN if getattr(exc,'outcome_unknown',False) else OperationStatus.FAILED
            summary={'error':{'code':exc.code,'retryAllowed':False}}
        except Exception:
            status=OperationStatus.OUTCOME_UNKNOWN;summary={'error':{'code':'MEMORY_WRITE_FAILED','retryAllowed':False}}
        if self.security_audit:
            self.security_audit.record(invocation,AuditKind.TERMINAL,{'action':'memory_child_proposal',
                'outcome':status.value,'effectState':'applied' if status is OperationStatus.COMPLETED else 'unknown'
                    if status is OperationStatus.OUTCOME_UNKNOWN else 'none','retryAllowed':False},origin='application')
            if self.security_audit.health()['deliveryFailures']:summary['securityAudit']={'gap':True,'retryAllowed':False}
        self._finish_service_operation(session,op,status,summary)

    def get_snapshot(self, session_id: SessionId | None) -> SessionSnapshot:
        with self._lock:
            return self._snapshot_unlocked(session_id)

    def get_context_usage(self, session_id) -> dict[str, Any]:
        """Common diagnostic, never the obsolete message-count heuristic."""
        state = self.get_snapshot(session_id)
        reports = state.turns[-1].get("contextReports", []) if state.turns else []
        budget = next((r.get("budget") for r in reversed(reports)
            if r.get("rule") == "context_budget"), None)
        keys = ("system_tokens", "tool_schema_tokens", "project_instruction_tokens",
            "skill_tokens", "current_message_tokens", "working_context_tokens",
            "tool_result_tokens", "retrieval_tokens")
        return {"messages": len(state.transcript),
            "estimated_tokens": sum(budget[k] for k in keys) if budget else None,
            "token_limit": budget["selected_context_window"] if budget else None,
            "compaction_triggered": budget["removed_messages"] > 0 if budget else False,
            "budget": budget}

    def list_models(self, session_id: SessionId | None) -> list[dict[str, Any]]:
        """Read-only provider query shared by transport adapters."""
        with self._lock:
            self._snapshot_unlocked(session_id)
        return self.provider_manager.list_models()

    def get_readiness(self, session_id: SessionId | None) -> dict[str, Any]:
        """Read-only host observation; unrelated optional tools do not gate chat."""
        with self._lock:
            session = self._session
            if session is None or session.session_id != session_id or session.status != "active":
                raise ValueError("No matching active AgentSession")
        # Do not hold the Application lock across provider I/O or mutate a turn.
        result = self.provider_manager.get_readiness()
        with self._lock:
            if self._session is not session or session.status != "active":
                raise ValueError("No matching active AgentSession")
            runtime = self.provider_manager.snapshot().snapshot
            if (result["providerId"], result["modelId"], result["providerRevision"]) != (
                    runtime.provider_id, runtime.model_id, runtime.provider_revision):
                result.update(ready=False, reason="READINESS_STALE", requiredAction=None, installedModels=[])
            if self._embedding_settings is not None:
                self._embedding_settings.observe(result['installedModels'], result.get('reason') not in
                    ('OLLAMA_UNAVAILABLE', 'READINESS_STALE', 'PROVIDER_UNVERIFIED'))
                self._refresh_knowledge_index()
            return self.redactor.value({**result, "sessionId": str(session.session_id)})

    def register_memory_actor(self, kind, verify):
        """Trusted in-process host seam, not a serialized token or a tool grant."""
        if kind not in ('cli_tty','desktop_host') or not callable(verify):
            raise ValueError('Invalid memory host actor')
        actor=object()
        with self._lock:
            self._memory_actors[actor]=(kind,verify)
        return actor

    def register_knowledge_actor(self, kind, verify):
        return self._knowledge.register(kind, verify)

    def execute_knowledge(self, command, *, actor=None):
        return self._knowledge.execute(command, actor)

    def execute_storage(self, command, *, actor=None):
        from local_cli.application.storage import execute_storage
        return execute_storage(self._knowledge, command, actor)

    def close_knowledge(self):
        self._knowledge.close()

    def close_browser(self):
        """Shared frontend shutdown; browser lifecycle belongs to Application."""
        if self._session is not None and self._session.tool_runtime is not None:
            service = self._session.tool_runtime._browser_service
            if service is not None:
                return service.close()

    def _memory_settings_snapshot(self):
        em=self._embedding_settings.snapshot() if self._embedding_settings else None
        available=bool(em and em['connected'] and em['selectedModel'] and em['selectedModel'] in em['enabledModels'])
        value=self._memory_preferences.snapshot() if self._memory_preferences else None
        return {'lexicalRecall':bool(self._memory_factory) and (value['lexicalRecall'] if value else True),
            'semantic':value['semanticRecall'] if value else bool(self._memory and self._memory.semantic and self._memory.semantic.available),
            'semanticAvailable':available,'autoCapture':value['autoCapture'] if value else self._memory_capture_mode!='off',
            'captureMode':value['captureMode'] if value else self._memory_capture_mode,
            'sensitiveProjects':value['sensitiveProjects'] if value else [],
            'maintenanceBusy':bool(self._memory_worker and not self._memory_worker.done.is_set())}

    def execute_memory(self, command, *, actor=None):
        """Explicit synchronous Application controls, with Core operation terminal.

        Replies contain requested inspection data; events/snapshots/idempotency
        entries retain summaries only. Never append memories to transcript or
        call the model. A receipt here reports a synchronous *observed* outcome.
        """
        import hashlib
        from types import SimpleNamespace
        from local_cli.application.memory import MemoryCommand, MEMORY_WRITES
        from local_cli.core.memory import MemoryError
        from local_cli.core.security_audit import AuditKind

        def rejected(code, unknown=False):
            raw_id=getattr(command,'command_id','')
            safe_id=self.redactor.text(raw_id) if isinstance(raw_id,str) else ''
            return dict(schemaVersion=1,commandId=safe_id,completed=False,
                stateRevision=self._session.state_revision if self._session else None,
                error=dict(code=code,category='MEMORY',message='Memory command could not complete.',
                           outcomeUnknown=unknown,retryable=False))

        with self._lock:
            if not isinstance(command,MemoryCommand):
                return rejected('MEMORY_UNTRUSTED_INPUT')
            try: registered=self._memory_actors.get(actor)
            except TypeError: registered=None
            try: verified=registered is not None and registered[1]() is True
            except Exception: verified=False
            if not verified:
                return rejected('MEMORY_UNTRUSTED_INPUT')
            session=self._session
            if session is None or session.session_id!=command.session_id or session.status!='active':
                return rejected('INVALID_SESSION')
            if any(self.redactor.text(v)!=v for v in (command.command_id,command.session_id)):
                return rejected('MEMORY_UNTRUSTED_INPUT')
            digest=hashlib.sha256(json.dumps(command.to_dict(),ensure_ascii=False,sort_keys=True,
                separators=(',',':')).encode('utf-8')).hexdigest()
            key=(command.session_id,command.command_id)
            cached=self._memory_receipts.get(key)
            if cached:
                return deepcopy(cached[1]) if cached[0]==digest else rejected('IDEMPOTENCY_CONFLICT')
            if command.expected_revision is not None and command.expected_revision!=session.state_revision:
                return rejected('REVISION_CONFLICT')
            if any(not t.done.is_set() for t in session.turns) or any(not a.done.is_set() for a in session.agent_operations.values()):
                return rejected('CONFLICT_ACTIVE_OPERATION')
            if self._memory_factory is None:
                return rejected('MEMORY_UNAVAILABLE')
            if command.name in MEMORY_WRITES and self._memory_worker and not self._memory_worker.done.is_set():
                return rejected('CONFLICT_ACTIVE_OPERATION')
            operation=ServiceOperation(new_operation_id(),command.command_id,service='memory')
            self._service_operations[operation.operation_id]=operation
            context=SimpleNamespace(session_id=session.session_id,operation_id=operation.operation_id,
                turn_id=None,agent_id=None,workspace=session.workspace,cwd=session.workspace)
            invocation=SimpleNamespace(context=context,operation_id=operation.operation_id,
                tool_call_id=None,name=command.name,arguments={})
            audit=self.security_audit
            response=None
            status=OperationStatus.FAILED
            try:
                if audit is not None:
                    audit.request(invocation,origin='application')
                    audit.record(invocation,AuditKind.POLICY,dict(decision='EXPLICIT_USER_CONTROL',
                        actor=registered[0]),origin='application')
                    audit.before_effect(invocation,origin='application')
                if command.name in ('memory_configure','memory_reset_settings','memory_project_access'):
                    if self._memory_preferences is None:raise MemoryError(MemoryErrorCode.UNAVAILABLE)
                    args=dict(command.arguments)
                    if command.name=='memory_configure':
                        if (args.get('semanticRecall') is True and not self._memory_preferences.snapshot()['semanticRecall']
                                and not self._memory_settings_snapshot()['semanticAvailable']):
                            raise MemoryError(MemoryErrorCode.EMBEDDING_REQUIRED)
                        data=self._memory_preferences.update(args)
                    elif command.name=='memory_project_access':
                        if set(args)!={'projectPath','enabled'}:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
                        data=self._memory_preferences.set_sensitive(args['projectPath'],args['enabled'])
                    else:
                        if args:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
                        data=self._memory_preferences.reset()
                    self._memory_capture_mode=data['captureMode'] if data['autoCapture'] else 'off'
                    if self._memory:self._memory.refresh_settings(session.workspace)
                else:
                    if self._memory is None:self._memory=self._memory_factory(session.workspace,self.redactor)
                    self._memory.refresh_settings(session.workspace)
                    if command.name=='memory_import':
                        from local_cli.application.memory_transfer import import_memories
                        if set(command.arguments)!={'backup'}:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
                        data=import_memories(self._memory,command.arguments['backup'],session.workspace)
                    elif command.name=='memory_export_all':
                        from local_cli.application.memory_transfer import export_memories
                        if set(command.arguments)!={'includeSensitive'}:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
                        data=export_memories(self._memory,command.arguments['includeSensitive'])
                    else:
                        data=self._memory.execute(command.name,command.arguments,workspace=str(session.workspace),
                            session_id=str(session.session_id),operation_id=str(operation.operation_id),explicit_user_action=True)
                if command.name in ('memory_forget','memory_correct','memory_edit','memory_delete'):
                    old_ids={row['memoryId'] for row in command.arguments['records']} if command.name in ('memory_edit','memory_delete') else {command.arguments.get('memoryId')}
                    from local_cli.application.memory_recall import MemoryCapsule
                    for previous_turn in session.turns:
                        snapshot=previous_turn.memory_snapshot
                        if snapshot and any(r.memory_id in old_ids for r in snapshot.records):
                            kept=tuple(r for r in snapshot.records if r.memory_id not in old_ids)
                            previous_turn.memory_snapshot=replace(snapshot,records=kept,
                                capsule=MemoryCapsule.render(kept,self.redactor),tokens=0 if not kept else snapshot.tokens)
                        if previous_turn.model_runtime and previous_turn.model_runtime._context:
                            previous_turn.model_runtime._context.manager.invalidate_cache()
                response=dict(schemaVersion=1,commandId=command.command_id,completed=True,
                    operationId=operation.operation_id,data=data)
                status=OperationStatus.COMPLETED
            except (MemoryError,SecurityAuditError) as exc:
                unknown=bool(getattr(exc,'outcome_unknown',False))
                status=OperationStatus.OUTCOME_UNKNOWN if unknown else OperationStatus.FAILED
                response=rejected(exc.code,unknown)
                response['operationId']=operation.operation_id
            except (ValueError,OSError):
                response=rejected('MEMORY_WRITE_FAILED' if command.name in MEMORY_WRITES else 'MEMORY_UNTRUSTED_INPUT')
                response['operationId']=operation.operation_id
            except Exception:
                # A foreign adapter may fail after an effect. No automatic retry
                # or raw traceback/content; do not invent a rollback.
                status=OperationStatus.OUTCOME_UNKNOWN
                response=rejected('MEMORY_WRITE_FAILED',True)
                response['operationId']=operation.operation_id
            summary=dict(command=command.name,completed=response['completed'],error=response.get('error'),
                memoryId=response.get('data',{}).get('memoryId'))
            if audit is not None:
                audit.record(invocation,AuditKind.TERMINAL,dict(action=command.name,outcome=status.value,
                    effectState=('unknown' if status is OperationStatus.OUTCOME_UNKNOWN else
                        'applied' if response['completed'] and command.name in MEMORY_WRITES else 'none'),
                    errorCode=response.get('error',{}).get('code'),retryAllowed=False),origin='application')
                health=audit.health()
                if health['deliveryFailures']:
                    response['securityAudit']=dict(gap=True,errorCode='SECURITY_AUDIT_DELIVERY_FAILED',retryAllowed=False)
                    summary['securityAudit']=response['securityAudit']
            self._finish_service_operation(session,operation,status,summary)
            response['stateRevision']=session.state_revision
            if command.name in MEMORY_WRITES:
                self._memory_receipts[key]=(digest,deepcopy(response))
            return response

    def execute_auxiliary(self, session_id: SessionId, name: str,
                          arguments: Mapping[str, Any] | None = None):
        """Transport-neutral access to secondary backend capabilities."""
        from local_cli.application.auxiliary import AuxiliaryConflict
        with self._lock:
            session = self._session
            if session is None or session.session_id != session_id or session.status != "active":
                raise ValueError("No matching active AgentSession")
            if self._auxiliary_services is None:
                raise ValueError("Application service is unavailable")
            if name != "update_check" and any(not turn.done.is_set() for turn in session.turns):
                raise AuxiliaryConflict("Command unavailable during active Turn")
            result = self._auxiliary_services.execute(
                name, arguments or {}, transcript=tuple(deepcopy(session.transcript)),
                model=session.model)
            if result.context_message is not None:
                session.transcript.append(deepcopy(dict(result.context_message)))
                session.state_revision += 1
                if self._persistence is not None:
                    self._persistence.save(self._saved_transcript(session))
                if self._events is not None:
                    state = self._snapshot_unlocked(session_id).to_dict()
                    state["lastSequence"] = self._events.last_sequence + 1
                    self._events.publish(EventKind.SESSION_SNAPSHOT, state,
                                         state_revision=session.state_revision,
                                         visibility=Visibility.SENSITIVE)
            return result

    def _bind_redaction(self, persistence):
        if persistence is None:
            return
        persistence.redactor = self.redactor
        audit = getattr(persistence, 'audit', None)
        logger = getattr(audit, '_logger', None)
        if logger is not None:
            logger.redactor = self.redactor

    def _context_settings(self):
        from local_cli.application.context_settings import context_settings
        return context_settings(self._context_selection, self._context_policy,
                                self.provider_manager.snapshot().snapshot)

    def _web_browser_state(self, session):
        state = next((t.selection.state() for t in session.installed_tools if hasattr(t, 'selection')), None)
        if state is None:
            state = dict(selected=self._web_browser, available=False, unavailableReason='BROWSER_NOT_INSTALLED',
                adapter=self._web_browser.upper(), runtimeCheckedOnUse=True, networkIsolation='NOT_PROVIDED',
                controlClass='HOST_UNISOLATED', choices=[dict(browser=name, adapter=name.upper(), available=False,
                    installed=False, reason='BROWSER_NOT_INSTALLED') for name in ('webview2','chrome','edge')])
        runtime_state = session.tool_runtime._browser_service.public_state() if session.tool_runtime._browser_service else {'controlState':'agentActive'}
        return {**state, **runtime_state, 'enabled':self._browser_enabled,
                'available':self._browser_enabled and state['available'], 'lastControlResult':self._browser_control_result}

    def _web_search_state(self, session):
        state = next((t.state() for t in session.installed_tools if t.name == 'web_search' and hasattr(t, 'state')), None)
        if state is None:
            state = dict(backend='browser', engine=self._web_engine, available=False, adapter=self._web_browser.upper(),
                runtimeCheckedOnUse=True, unavailableReason='BROWSER_SEARCH_NOT_INSTALLED', serverRequired=False, networkIsolation='NOT_PROVIDED')
        return {**state, 'enabled':self._search_enabled, 'available':self._search_enabled and state['available']}

    def _snapshot_unlocked(self, session_id: SessionId | None) -> SessionSnapshot:
        session = self._session
        if session is None or session.session_id != session_id:
            raise ValueError("No matching active AgentSession")
        snapshot = SessionSnapshot(
            session_id=session.session_id,
            workspace=str(session.workspace), model=session.model,
            status=session.status, state_revision=session.state_revision,
            last_sequence=self._events.last_sequence if self._events else 0,
            model_runtime=self.provider_manager.snapshot().snapshot.to_dict(),
            capabilities=session.capabilities.to_dict() if session.capabilities else {},
            services={"context": self._context_settings(), "rag": self._rag.status(),
                      **({'embedding': self._embedding_settings.snapshot()} if self._embedding_settings else {}),
                      "browser": self._web_browser_state(session),
                      "search": self._web_search_state(session),
                      "fetch": {"enabled": self._fetch_enabled,
                          "available": self._fetch_enabled and 'web_fetch' in session.tool_runtime.registry.names},
                      "knowledge": self._knowledge.snapshot(),
                      **({'knowledgeSettings': self._knowledge_settings_snapshot()} if self._knowledge_preferences is not None else {}),
                      "memory": self._memory_settings_snapshot(),
                      **({'securityAudit': self.security_audit.health()} if self.security_audit is not None else {}),
                      "filesystem": {"revision": session.filesystem_revision},
                      "conversationPresentation": [{"sourceIndex": index, **dates}
                          for index, dates in session.restored_display_dates.items()],
                      "interactions": {
                          "approvals": [{"approvalId": req.approval_id,
                              "turnId": req.turn_id, "operationId": req.operation_id,
                              "toolCallId": req.tool_call_id, "name": req.tool_name,
                              "arguments": self.redactor.value(req.arguments), "cwd": req.cwd,
                              "policyRevision": req.policy_revision,
                              "requestDigest": req.request_digest,
                              "deadline": req.deadline.isoformat() if req.deadline else None}
                              for req in session.approval_gate.pending()],
                          "inputs": [{"inputRequestId": req.input_request_id,
                              "turnId": req.turn_id, "question": req.question,
                              "deadline": req.deadline.isoformat() if req.deadline else None}
                              for req in session.user_input_gate.pending()]},
                      "persistence": {"available": self._persistence is not None,
                          "errorCode": self._persistence.last_error.code
                              if self._persistence and self._persistence.last_error else self._persistence_setup_error},
                      "operations": [{"operationId": op.operation_id, "status": op.status.value,
                          "service": op.service, "phase": op.progress.get("phase", "started"),
                          "result": deepcopy(op.result),
                          "turnId": op.turn_id, "cancelRequested": op.token.is_cancel_requested()}
                          for op in self._service_operations.values()]},
            transcript=tuple(self.redactor.messages(session.transcript)),
            turns=tuple({
                "turnId": turn.turn_id, "operationId": turn.operation_id,
                "commandId": turn.command_id, "status": turn.status.value,
                "operationStatus": turn.operation_status.value,
                "activeGenerationId": turn.active_generation,
                "cancelRequested": turn.cancellation.is_cancel_requested(),
                "stopGenerationRequested": turn.stop_generation_requested,
                "finalContent": turn.final_content,
                "errorCode": turn.error_code,
                "terminalCount": turn.terminal_count,
                "operationTerminalCount": turn.terminal_count,
                "modelRuntime": turn.model_runtime.snapshot.to_dict() if turn.model_runtime else None,
                "generations": deepcopy(turn.generations),
                "contextReports": deepcopy(turn.context_reports),
                "knowledgeCitations": self.redactor.value(turn.citation_reports),
                "displayMessages": self.redactor.value(turn.display_messages),
                "toolActivities": [self.redactor.tool_activity(activity)
                    for activity in turn.tool_activities.values()],
                "userMessage": self.redactor.value(turn.user_message),
                "transcriptStart": turn.transcript_start,
                "transcriptEnd": turn.transcript_end,
            } for turn in session.turns),
        )
        safe = self.redactor.snapshot(snapshot.to_dict())
        return replace(snapshot, workspace=safe['workspace'], model=safe['model'],
            transcript=tuple(safe['transcript']), turns=tuple(safe['turns']),
            model_runtime=safe['modelRuntime'], capabilities=safe['capabilities'], services=safe['services'])

    def subscribe_events(self, session_id: SessionId | None, *,
                         after_sequence: int = 0,
                         include_internal: bool = False) -> EventCursor:
        """Session-owner interface stream, including its human interactions.

        General/public journal consumers use SessionEventStream directly;
        approval/question payloads retain SENSITIVE visibility, not PUBLIC.
        """
        with self._lock:
            self._snapshot_unlocked(session_id)
            if self._events is None:
                raise ValueError("event stream is not configured")
            return self._events.subscribe(after_sequence=after_sequence,
                                          include_internal=include_internal,
                                          include_sensitive=True)

    def recover_unverified_events(self, *, requested_after: int,
                                  requested_session_id: str | None = None
                                  ) -> tuple[EventEnvelope, EventEnvelope]:
        """Expose an explicit gap/snapshot after an unprovable JSONL reconnect."""
        with self._lock:
            state = self._snapshot_unlocked(self._session.session_id)
            if self._events is None:
                raise ValueError("event stream is not configured")
            return self._events.recover_unverified(
                requested_after=requested_after, snapshot=state.to_dict(),
                state_revision=state.state_revision,
                requested_session_id=requested_session_id,
                snapshot_visibility=Visibility.SENSITIVE)

    def poll_events(self, cursor: EventCursor) -> tuple[EventEnvelope, ...]:
        with self._lock:
            if self._session is None or self._session.session_id != cursor.session_id:
                raise ValueError("No matching active AgentSession")
            if self._events is None:
                raise ValueError("event stream is not configured")
            # Most polls only deliver incremental events. Build and redact the
            # transcript once when recovery actually requires a snapshot.
            return self._events.poll(cursor,
                                     snapshot=lambda: self._snapshot_unlocked(cursor.session_id).to_dict(),
                                     state_revision=self._session.state_revision,
                                     snapshot_visibility=Visibility.SENSITIVE)

    def wait_for_turn(self, turn_id: TurnId | str, timeout: float | None = None) -> bool:
        """Technical wait for CLI/tests; it does not own session lifecycle."""
        with self._lock:
            session = self._session
            turn = next((item for item in session.turns if item.turn_id == turn_id), None) if session else None
        if turn is None:
            raise ValueError("Unknown turnId")
        return turn.done.wait(timeout)
