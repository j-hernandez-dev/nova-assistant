"""Single AgentSession and transport-neutral session/event commands.

CLI and JSONL server keep their legacy paths while this coordinator is
characterized against run_agent. Phase-7 interactions are owned here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Any, Callable, Mapping

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
    # Ephemeral owner-facing execution projection; never a second transcript,
    # prompt source, durable journal or renderer-owned lifecycle.
    display_messages: list[dict[str, Any]] = field(default_factory=list)
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
        allow_remote_memory_injection: bool = False,
        memory_capture_mode: str = 'off',
        memory_extractor_factory: Any = None,
    ) -> None:
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
        if type(allow_remote_memory_injection) is not bool:
            raise ValueError('remote memory injection requires an explicit boolean')
        self._allow_remote_memory_injection = allow_remote_memory_injection
        self._memory_actors = {}
        self._memory_receipts = {}  # Digests + mutation summaries only, never recall/content cache.
        if memory_capture_mode not in ('off','propose_only','low_risk'):
            raise ValueError('Invalid memory capture mode')
        self._memory_capture_mode=memory_capture_mode
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
            tools = self._tool_factory(workspace)
            prompt = self._prompt_factory(tools, workspace)
            registry = ToolRegistry(tools)
            environment = dict(next(
                (tool.environment for tool in tools if isinstance(tool, ShellTool)),
                get_sanitized_env(),
            ))
            self.redactor.observe_environment(environment)
            environment = self._environment_service.build(environment, None)
            for tool in tools:
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
        initial_messages = self.redactor.messages(initial_messages)
        session = AgentSession(
            session_id=session_id, workspace=workspace, model=self.provider_manager.snapshot().snapshot.model_id,
            tools=tools, transcript=initial_messages,
            base_transcript=deepcopy(initial_messages),
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
        session.tool_runtime = ToolRuntime(
            registry, auto_approve=self._auto_approve,
            approval_gate=session.approval_gate,
            user_input_gate=session.user_input_gate,
            publish=lambda event: self._publish_tool_event(session, event),
            on_agent_started=lambda *args: self._publish_agent_started(session, *args),
            on_agent_completed=lambda *args: self._publish_agent_completed(session, *args),
            process_service=self._process_service,
            network_service=self._network_service,
            redactor=self.redactor, environment_service=self._environment_service,
            environment_selector=self._environment_selector,
            security_audit=self.security_audit,
        )
        session.tool_runtime.install_authority(workspace, session_id)
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
        self._preempt_memory(resume_after_turn=True)
        turn = Turn(new_turn_id(), new_operation_id(), command.command_id)
        if self._memory_capture_mode!='off':
            turn.memory_capture=(session.workspace,self.redactor.text(command.payload['content']),datetime.now(timezone.utc))
        if self.provider_manager.snapshot().name in ProviderManager.SUPPORTED:
            self.provider_manager.refresh_status()
        turn.model_runtime = self.provider_manager.begin_turn(
            turn.turn_id,
            inference_options=(self._inference_options_factory()
                               if self._inference_options_factory is not None else None))
        session.turns.append(turn)
        if self._turn_messages_factory is not None:
            session.transcript.extend(deepcopy(self._turn_messages_factory(command.payload["content"])))
        turn.transcript_start = len(session.transcript)
        session.transcript[:] = self.redactor.messages(session.transcript)
        session.transcript.append({"role": "user", "content": self.redactor.text(command.payload["content"])})
        if self._persistence is not None:
            self._persistence.save(session.transcript)
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
                                raise MemoryError(MemoryErrorCode.REMOTE_INJECTION_DENIED)
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
                and not any(not operation.done.is_set() for operation in self._service_operations.values()))

    def change_workspace(self, session_id, path: str) -> dict[str, Any]:
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
            target = Path(path).expanduser()
            target = (target if target.is_absolute() else self._session.workspace / target).resolve()
            if not target.is_dir():
                raise ValueError("Workspace must be a directory")
            prepared = self._workspace_rebinder(target)
            old_base = self._session.base_transcript
            retained = [m for m in self._session.transcript if m not in old_base]
            self._session.transcript[:] = deepcopy(prepared["base_messages"] + retained)
            self.rebind_legacy_workspace(target, base_messages=prepared["base_messages"],
                persistence=prepared["persistence"], rag=prepared["rag"])
            return prepared["data"]

    def rebind_legacy_workspace(self, workspace: Path, *,
                                base_messages: list[dict[str, Any]],
                                persistence: PersistenceService | None,
                                rag: RAGService | None) -> None:
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
            session.workspace = workspace.resolve()
            session.base_transcript = self.redactor.messages(base_messages)
            self._persistence = persistence
            self._bind_redaction(persistence)
            self._rag = rag if rag is not None else RAGService(None)
            session.capabilities = self._capability_factory(
                model=self.provider_manager.snapshot().snapshot,
                cwd=session.workspace,
                shell=next((getattr(t, "descriptor", None) for t in session.tools
                            if t.name == "bash"), None),
                resource_context_limit=self._context_policy.resource_limit)
            session.state_revision += 1
            if self._events is not None:
                state = self._snapshot_unlocked(session.session_id).to_dict()
                state["lastSequence"] = self._events.last_sequence + 1
                self._events.publish(EventKind.SESSION_SNAPSHOT, state,
                                     state_revision=session.state_revision,
                                     visibility=Visibility.SENSITIVE)

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
            if name == "clear":
                if self._refresh_base_factory is not None:
                    fresh = self._refresh_base_factory(session.workspace, session.tools)
                    if not fresh or fresh[0].get("role") != "system":
                        return self._reject(command, "SESSION_SETUP_FAILED",
                                            "Could not rebuild project context")
                    session.base_transcript = deepcopy(fresh)
                session.transcript[:] = deepcopy(session.base_transcript)
                session.turns.clear()
                session.state_revision += 1
                if self._persistence is not None:
                    self._persistence.clear()
                return CommandReceipt(command.command_id, True, session.session_id,
                    session.state_revision)
            if name == "save":
                key = self._persistence.save_session(session.transcript)
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
            session.transcript[:] = deepcopy(session.base_transcript) + saved
            session.state_revision += 1
            self._persistence.save(session.transcript)
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
        try:
            tools = self._sub_agent_tool_factory(session.workspace)
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
                redactor=self.redactor, security_audit=self.security_audit)
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
                                           context_factory)
                         for tool in session.tools]

        def emit_legacy(event: AgentEvent) -> None:
            nonlocal active_generation
            with self._lock:
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
                self._observe_display(turn, event)
                stream = self._events
                def publish(*args: Any, **kwargs: Any) -> None:
                    if stream is not None:
                        stream.publish(*args, **kwargs)
                cause = CausationId(turn.command_id)
                common = dict(state_revision=session.state_revision,
                              turn_id=turn.turn_id, causation_id=cause)
                if event.kind == "llm_start":
                    if active_generation is not None:
                        publish(EventKind.GENERATION_FAILED,
                                       {"status": "failed", "reason": "incomplete"},
                                       generation_id=active_generation, **common)
                    active_generation = new_generation_id()
                    turn.active_generation = active_generation
                    turn.stop_generation_requested = False
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
                elif event.kind in ("context_budget", "context_usage", "memory_recall"):
                    session.state_revision += 1
                    turn.context_reports.append(deepcopy(event.data))
                    publish(EventKind.HARNESS_INTERVENTION, event.data,
                            state_revision=session.state_revision, turn_id=turn.turn_id,
                            generation_id=active_generation, causation_id=cause)

        try:
            def checkpoint(additions):
                if self._persistence is not None:
                    with self._lock:
                        self._persistence.save(self.redactor.messages(session.transcript + [deepcopy(m) for m in additions
                            if isinstance(m, dict) and m.get("role") in ("assistant", "tool")]))
            working = _WorkingMessages(session.transcript, on_append=checkpoint)
            if self._auxiliary_services is not None:
                plan_factory=getattr(self._auxiliary_services,'plan_context',None)
                plan=plan_factory() if callable(plan_factory) else None
                if (isinstance(plan,dict) and plan.get('role') in ('user','system')
                        and isinstance(plan.get('content'),str)):
                    working.insert(len(working)-1,self.redactor.value(plan))
            if self._rag.status()["enabled"]:
                rag_op = ServiceOperation(new_operation_id(), turn.command_id,
                    token=turn.cancellation.child(), turn_id=turn.turn_id)
                with self._lock:
                    self._service_operations[rag_op.operation_id] = rag_op
                if self._memory_worker and not self._memory_worker.done.is_set():
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
            if self._memory_factory is not None and not turn.cancellation.is_cancel_requested():
                remote = not local_memory_destination(turn.model_runtime.snapshot)
                if remote and not self._allow_remote_memory_injection:
                    recalled = TurnMemorySnapshot(error_code='MEMORY_REMOTE_INJECTION_DENIED', remote=True)
                else:
                    try:
                        with self._lock:
                            if self._memory is None:
                                self._memory = self._memory_factory(session.workspace, self.redactor)
                        recalled = MemoryRetriever(self._memory).retrieve(session.transcript[-1]['content'],
                            workspace=session.workspace, at=datetime.now(timezone.utc),
                            semantic_allowed=not (self._memory_worker and not self._memory_worker.done.is_set()))
                        recalled = replace(recalled, remote=remote)
                    except Exception as exc:
                        # Optional recall failure is observable, never a failed
                        # write turned into success, and never an implicit retry.
                        recalled = TurnMemorySnapshot(error_code=exc.code if isinstance(exc, MemoryError)
                            else 'MEMORY_UNAVAILABLE', remote=remote)
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
            with self._lock:
                session.capabilities = turn.capabilities
            turn.model_runtime._context.memory_source=lambda:self._revalidate_memory(session,turn,working)
            outcome = self._runtime.run_turn(
                provider=turn.model_runtime, model=turn.model_runtime.snapshot.model_id,
                tools=runtime_tools, messages=working, emit=emit_legacy,
                should_stop=lambda: (turn.cancellation.is_cancel_requested()
                                     or turn.stop_generation_requested),
            )
        except BaseException as exc:
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
                additions = [deepcopy(message) for message in
                             (working.appended if working is not None else ())
                             if isinstance(message, dict)
                             and message.get("role") in ("assistant", "tool")]
                session.transcript.extend(self.redactor.messages(additions))
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
            turn.transcript_end = len(session.transcript)
            turn.error_code = self.redactor.text(outcome.error_code)
            turn.terminal_count += 1
            session.state_revision += 1
            if self._persistence is not None:
                self._persistence.save(session.transcript)
            self._publish_turn_terminal(session, turn)
            self.provider_manager.end_turn(turn.turn_id)
            if turn.model_runtime._context is not None:
                turn.model_runtime._context.memory_source=None
                turn.model_runtime._context.manager.invalidate_cache()
            turn.done.set()

        # Already terminal: maintenance owns a different operation and never
        # appends to transcript, reopens Turn or changes its observed result.
        if self._memory_capture_mode!='off':
            self._queue_memory(session,turn)

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
    def _observe_display(turn: Turn, event: AgentEvent) -> None:
        """Recover a live view after renderer reload or journal eviction.

        This projection belongs to Application and is returned only through
        session-owner snapshots. It does not affect harness/model messages.
        """
        if event.kind == "llm_start":
            turn.display_messages.append({"role": "assistant", "content": "",
                "thinking": True, "toolCalls": [], "toolResults": [], "harnessEvents": []})
        if not turn.display_messages:
            return
        last = turn.display_messages[-1]
        if event.kind == "content_delta":
            last["content"] += event.data.get("text", "")
            last["thinking"] = False
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
            if sub_agent.agent_id in session.agent_operations:
                raise ValueError("duplicate agentId")
            if self._memory is not None and turn.memory_snapshot is not None:
                from local_cli.application.memory_children import child_memory_source
                remote=not local_memory_destination(sub_agent.model_snapshot) if sub_agent.model_snapshot else True
                if not remote or self._allow_remote_memory_injection:
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

    def register_memory_actor(self, kind, verify):
        """Trusted in-process host seam, not a serialized token or a tool grant."""
        if kind not in ('cli_tty','desktop_host') or not callable(verify):
            raise ValueError('Invalid memory host actor')
        actor=object()
        with self._lock:
            self._memory_actors[actor]=(kind,verify)
        return actor

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
                if self._memory is None:
                    self._memory=self._memory_factory(session.workspace,self.redactor)
                data=self._memory.execute(command.name,command.arguments,workspace=str(session.workspace),
                    session_id=str(session.session_id),operation_id=str(operation.operation_id),explicit_user_action=True)
                if command.name in ('memory_forget','memory_correct'):
                    old_id=command.arguments.get('memoryId')
                    from local_cli.application.memory_recall import MemoryCapsule
                    for previous_turn in session.turns:
                        snapshot=previous_turn.memory_snapshot
                        if snapshot and any(r.memory_id==old_id for r in snapshot.records):
                            kept=tuple(r for r in snapshot.records if r.memory_id!=old_id)
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
                    self._persistence.save(session.transcript)
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
            services={"rag": self._rag.status(),
                      "memory": {"lexicalRecall": self._memory_factory is not None,
                          "semantic": bool(self._memory and self._memory.semantic and self._memory.semantic.available),
                          "autoCapture": self._memory_capture_mode!='off', "captureMode":self._memory_capture_mode,
                          "allowRemoteMemoryInjection": self._allow_remote_memory_injection},
                      **({'securityAudit': self.security_audit.health()} if self.security_audit is not None else {}),
                      "filesystem": {"revision": session.filesystem_revision},
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
                "displayMessages": self.redactor.value(turn.display_messages),
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
            state = self._snapshot_unlocked(cursor.session_id)
            if self._events is None:
                raise ValueError("event stream is not configured")
            return self._events.poll(cursor, snapshot=state.to_dict(),
                                     state_revision=state.state_revision,
                                     snapshot_visibility=Visibility.SENSITIVE)

    def wait_for_turn(self, turn_id: TurnId | str, timeout: float | None = None) -> bool:
        """Technical wait for CLI/tests; it does not own session lifecycle."""
        with self._lock:
            session = self._session
            turn = next((item for item in session.turns if item.turn_id == turn_id), None) if session else None
        if turn is None:
            raise ValueError("Unknown turnId")
        return turn.done.wait(timeout)
