"""JSONL projection of the one-session Application API.

The adapter owns wire request IDs and compatibility shapes, never a second
agent loop, approval decision or transcript.
"""

from __future__ import annotations

from threading import Event, RLock, Thread
from dataclasses import replace
from typing import Any, Callable

from local_cli.application.commands import ApplicationCommand, CommandKind, CommandReceipt
from local_cli.application.events import SubscriptionOutOfSync
from local_cli.application.auxiliary import AuxiliaryConflict, AuxiliaryUnavailable
from local_cli.application.legacy_event_bridge import envelope_to_jsonl
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.interfaces.approval_proof import verify_approval_proof


class JsonlApplicationAdapter:
    def __init__(self, application: Any, session_id: str,
                 send: Callable[[dict[str, Any]], None], *,
                 on_provider_changed: Callable[[], None] | None = None,
                 host_approval_key: str | None = None) -> None:
        self.application, self.session_id, self._send = application, session_id, send
        self._on_provider_changed = on_provider_changed or (lambda: None)
        self._lock = RLock()
        self._wake = Event()
        self._closed = False
        self._legacy_turns: dict[str, Any] = {}
        self._active_turn_id: str | None = None
        self._stop_ids: list[Any] = []
        self._error_sent: set[str] = set()
        self._confirm_seq = 0
        self._input_seq = 0
        self._pending_confirms: dict[int, dict[str, Any]] = {}
        self._pending_inputs: dict[int, str] = {}
        self._subscriptions: dict[Any, Any] = {}
        self._agent_requests: dict[str, tuple[Any, bool]] = {}
        self._host_approval_key = host_approval_key
        if host_approval_key and getattr(application, 'redactor', None) is not None:
            application.redactor.register(host_approval_key, protected=True)
        self._approval_actor = (application.register_approval_actor('desktop_host', lambda: True)
                                if host_approval_key else None)
        self._memory_actor = (application.register_memory_actor('desktop_host', lambda: not self._closed)
                              if host_approval_key else None)
        snapshot = self.application.get_snapshot(session_id)
        self._legacy_cursor = self.application.subscribe_events(
            session_id, after_sequence=snapshot.last_sequence,
            include_internal=True)
        self._pump: Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._pump is None:
                self._pump = Thread(target=self._pump_events, daemon=True,
                                    name="nova-jsonl-events")
                self._pump.start()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._wake.set()
            cursors = [self._legacy_cursor, *self._subscriptions.values()]
            self._subscriptions.clear()
        for cursor in cursors:
            cursor._stream.close(cursor)

    def _command(self, kind: CommandKind, payload: dict[str, Any],
                 *, expected_revision: int | None = None) -> CommandReceipt:
        return self.application.handle(ApplicationCommand(
            command_id=new_command_id(), kind=kind, payload=payload,
            session_id=self.session_id, expected_revision=expected_revision))

    def _receipt_error(self, req_id: Any, receipt: CommandReceipt) -> None:
        error = receipt.error
        self._send({"id": req_id, "type": "error", "code": error.code,
                    "category": error.category.value, "message": error.safe_message})

    def handle(self, request: dict[str, Any]) -> bool:
        kind, req_id = request.get("type"), request.get("id", 0)
        if kind == 'memory_command':
            from local_cli.application.memory import MemoryCommand
            from local_cli.core.memory import MemoryError, MemoryErrorCode
            try:
                command=MemoryCommand.from_dict(request.get('command'))
                if not verify_approval_proof(self._host_approval_key,command.to_dict(),request.get('hostMemoryProof')):
                    raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
                result=self.application.execute_memory(command,actor=self._memory_actor)
                self._send(dict(id=req_id,type='memory_result',schemaVersion=1,data=result))
            except (MemoryError,TypeError,ValueError):
                self._send(dict(id=req_id,type='error',category='MEMORY',code='MEMORY_UNTRUSTED_INPUT',
                                message='Authenticated host memory control is required.'))
            return True
        if kind == "command":
            command = request.get("command")
            if not isinstance(command, str):
                self._send({"id": req_id, "type": "error", "category": "TRANSPORT",
                            "code": "INVALID_COMMAND", "message": "Invalid command"})
                return True
            parts = command.strip().split(maxsplit=1)
            name = parts[0].lower() if parts else ""
            argument = parts[1].strip() if len(parts) > 1 else ""
            if name == "/status":
                return self.handle({"id": req_id, "type": "status"})
            if name == "/models":
                return self.handle({"id": req_id, "type": "models"})
            if name == "/model":
                if not argument:
                    self._send({"id": req_id, "type": "status",
                                "data": {"model": self.application.get_snapshot(self.session_id).model}})
                    return True
                return self.handle({"id": req_id, "type": "switch_model", "model": argument})
            if name == "/provider" and argument:
                return self.handle({"id": req_id, "type": "switch_provider",
                                    "provider": argument})
            if name == "/clear":
                return self.handle({"id": req_id, "type": "clear"})
            if name == "/resume":
                return self.handle({"id": req_id, "type": "resume"})
            return False
        if kind == "chat":
            content = request.get("content", "")
            if not isinstance(content, str) or not content.strip():
                self._send({"id": req_id, "type": "error", "message": "Empty message"})
                return True
            with self._lock:
                receipt = self._command(CommandKind.SUBMIT_USER_INPUT,
                                        {"content": content})
                if receipt.accepted:
                    turn_id = receipt.created_ids["turnId"]
                    self._legacy_turns[turn_id] = req_id
                    self._active_turn_id = turn_id
                    self._wake.set()
                else:
                    self._receipt_error(req_id, receipt)
            return True
        if kind == "stop":
            with self._lock:
                turn_id = self._active_turn_id
                if turn_id is None:
                    self._send({"id": req_id, "type": "stopped"})
                else:
                    receipt = self._command(CommandKind.CANCEL_TURN,
                                            {"turnId": turn_id})
                    if receipt.accepted:
                        self._stop_ids.append(req_id)
                        self._send({"id": req_id, "type": "stop_requested"})
                    else:
                        self._receipt_error(req_id, receipt)
            return True
        if kind == "confirm_response":
            self._send({'id': req_id, 'type': 'error', 'category': 'APPROVAL',
                        'code': 'APPROVAL_ACTOR_INVALID',
                        'message': 'Host confirmation is required.'})
            return True
        if kind == "input_response":
            input_id = request.get("input_request_id")
            if type(input_id) is int and isinstance(request.get("response"), str):
                with self._lock:
                    app_id = self._pending_inputs.pop(input_id, None)
                if app_id is not None:
                    self._command(CommandKind.RESOLVE_USER_INPUT,
                                  {"inputRequestId": app_id,
                                   "response": request["response"]})
            return True
        if kind == "status":
            self._status(req_id)
            return True
        if kind == "models":
            self._models(req_id)
            return True
        if kind == "auxiliary_command":
            name, arguments = request.get("name"), request.get("arguments", {})
            if not isinstance(name, str) or not name or not isinstance(arguments, dict):
                self._send({"id": req_id, "type": "error", "category": "TRANSPORT",
                            "code": "INVALID_COMMAND", "message": "Invalid auxiliary command"})
                return True
            try:
                result = self.application.execute_auxiliary(
                    self.session_id, name, arguments)
            except AuxiliaryConflict as exc:
                self._send({"id": req_id, "type": "error", "category": "CONTEXT",
                            "code": exc.code, "message": str(exc)})
            except AuxiliaryUnavailable as exc:
                self._send({"id": req_id, "type": "error", "category": "CAPABILITY",
                            "code": "AUXILIARY_UNAVAILABLE", "message": str(exc)})
            except Exception:
                self._send({"id": req_id, "type": "error", "category": "APPLICATION",
                            "code": "AUXILIARY_FAILED", "message": "Command failed"})
            else:
                self._send({"id": req_id, "type": "auxiliary_result",
                            "name": result.kind, "data": dict(result.data)})
            return True
        if kind in ("switch_model", "switch_provider"):
            self._change_provider(req_id, request)
            return True
        if kind in ("set_rag_enabled", "query_rag", "rag_status"):
            self._rag(req_id, request)
            return True
        if kind == "spawn_agent":
            self._spawn_agent(req_id, request)
            return True
        if kind in ("clear", "resume"):
            self._persistence(req_id, kind)
            return True
        if kind == "get_snapshot":
            self._snapshot(req_id, request)
            return True
        if kind == "subscribe_events":
            self._subscribe(req_id, request)
            return True
        if kind == "unsubscribe_events":
            subscription_id = request.get("subscriptionId")
            with self._lock:
                cursor = self._subscriptions.pop(subscription_id, None)
            if cursor is not None:
                cursor._stream.close(cursor)
            self._send({"id": req_id, "type": "unsubscribed"})
            return True
        if kind == "application_command":
            self._versioned_command(req_id, request)
            return True
        return False

    def _status(self, req_id: Any) -> None:
        state = self.application.get_snapshot(self.session_id)
        runtime = state.model_runtime
        self._send({"id": req_id, "type": "status", "data": {
            "model": state.model, "provider": runtime.get("providerId", "ollama"),
            "messages": sum(m.get("role") == "user" for m in state.transcript),
            "connected": runtime.get("health") == "AVAILABLE",
            "ollama_version": "", "modelRuntime": runtime,
        }})

    def _models(self, req_id: Any) -> None:
        try:
            models = self.application.list_models(self.session_id)
        except Exception:
            self._send({"id": req_id, "type": "error", "category": "PROVIDER",
                        "code": "PROVIDER_UNAVAILABLE", "message": "Could not list models"})
            return
        self._send({"id": req_id, "type": "models", "data": [
            {"name": item.get("name", ""), "size": item.get("size", 0)}
            for item in models if isinstance(item, dict)]})

    def _persistence(self, req_id: Any, name: str) -> None:
        receipt = self._command(CommandKind.EXECUTE_COMMAND, {"name": name})
        if not receipt.accepted:
            self._receipt_error(req_id, receipt)
            return
        snapshot = self.application.get_snapshot(self.session_id)
        if name == "clear":
            self._send({"id": req_id, "type": "cleared"})
        else:
            display = [{"role": m["role"], "content": str(m.get("content", ""))}
                       for m in snapshot.transcript
                       if m.get("role") in ("user", "assistant") and
                       str(m.get("content", "")).strip()]
            self._send({"id": req_id, "type": "restored",
                        "messages": display, "count": len(snapshot.transcript) -
                        len([m for m in snapshot.transcript if m.get("role") == "system"])})

    def _change_provider(self, req_id: Any, request: dict[str, Any]) -> None:
        model = request.get("model", "")
        kind = (CommandKind.CHANGE_MODEL if request["type"] == "switch_model"
                else CommandKind.CHANGE_PROVIDER)
        if kind is CommandKind.CHANGE_MODEL:
            if not isinstance(model, str) or not model.strip():
                self._send({"id": req_id, "type": "error", "code": "INVALID_MODEL",
                            "category": "MODEL", "message": "No valid model specified"})
                return
            payload = {"modelId": model}
        else:
            provider = request.get("provider", "")
            if not isinstance(provider, str) or not provider.strip():
                self._send({"id": req_id, "type": "error", "code": "INVALID_PROVIDER",
                            "category": "PROVIDER", "message": "No valid provider specified"})
                return
            payload = {"providerId": provider}
            if isinstance(model, str) and model.strip():
                payload["modelId"] = model
        receipt = self._command(kind, payload)
        if not receipt.accepted:
            self._receipt_error(req_id, receipt)
            return
        self._on_provider_changed()
        runtime = self.application.get_snapshot(self.session_id).model_runtime
        if kind is CommandKind.CHANGE_MODEL:
            self._send({"id": req_id, "type": "model_changed", "model": runtime["modelId"],
                        "providerRevision": runtime["providerRevision"]})
        else:
            self._send({"id": req_id, "type": "provider_changed",
                        "provider": runtime["providerId"], "model": runtime["modelId"],
                        "providerRevision": runtime["providerRevision"]})

    def _rag(self, req_id: Any, request: dict[str, Any]) -> None:
        kind = request["type"]
        if kind == "rag_status":
            self._send({"id": req_id, "type": "rag_result", "data":
                        self.application.get_snapshot(self.session_id).services["rag"]})
            return
        if kind == "set_rag_enabled":
            if not isinstance(request.get("enabled"), bool):
                self._send({"id": req_id, "type": "error", "category": "RAG",
                            "code": "INVALID_RAG_REQUEST",
                            "message": "Invalid project retrieval request"})
                return
            command_kind, payload = CommandKind.SET_RAG_ENABLED, {"enabled": request["enabled"]}
        else:
            query = request.get("query")
            if not isinstance(query, str) or not query.strip():
                self._send({"id": req_id, "type": "error", "category": "RAG",
                            "code": "INVALID_RAG_REQUEST",
                            "message": "Invalid project retrieval request"})
                return
            command_kind, payload = CommandKind.QUERY_RAG, {"query": query}
        with self._lock:
            receipt = self._command(command_kind, payload)
            if receipt.accepted:
                self._legacy_turns[receipt.created_ids["operationId"]] = req_id
                self._wake.set()
            else:
                self._receipt_error(req_id, receipt)

    def _spawn_agent(self, req_id: Any, request: dict[str, Any]) -> None:
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            self._send({"id": req_id, "type": "error", "message": "Prompt is required."})
            return
        with self._lock:
            parent_turn = request.get("parentTurnId") or self._active_turn_id
            if parent_turn is None:
                self._send({"id": req_id, "type": "error", "code": "STALE_TURN",
                            "category": "CONTEXT",
                            "message": "Sub-agent requires an active parent Turn"})
                return
            background = request.get("run_in_background", False) is True
            receipt = self._command(CommandKind.START_SUB_AGENT, {
                "parentTurnId": parent_turn, "task": prompt,
                "description": request.get("description") or "sub-agent task",
                "mode": request.get("mode") or "default"})
            if not receipt.accepted:
                self._receipt_error(req_id, receipt)
                return
            agent_id = receipt.created_ids["agentId"]
            self._agent_requests[agent_id] = (req_id, background)
            if background:
                self._send({"id": req_id, "type": "agent_started",
                            "agent_id": agent_id,
                            "description": request.get("description", "")})
            else:
                self._send({"id": req_id, "type": "agent_running",
                            "description": request.get("description", "")})
            self._wake.set()

    def _snapshot(self, req_id: Any, request: dict[str, Any]) -> None:
        if request.get("sessionId", self.session_id) != self.session_id:
            self._send({"id": req_id, "type": "error", "category": "TRANSPORT",
                        "code": "INVALID_SESSION", "message": "No matching active AgentSession"})
            return
        self._send({"id": req_id, "type": "snapshot", "schemaVersion": 1,
                    "data": self.application.get_snapshot(self.session_id).to_dict()})

    def _subscribe(self, req_id: Any, request: dict[str, Any]) -> None:
        requested_session = request.get("sessionId", self.session_id)
        after = request.get("afterSequence", 0)
        if type(after) is not int or after < 0 or not isinstance(requested_session, str):
            self._send({"id": req_id, "type": "error", "category": "TRANSPORT",
                        "code": "INVALID_EVENT_CURSOR", "message": "Invalid event cursor"})
            return
        snapshot = self.application.get_snapshot(self.session_id)
        recovery = None
        if requested_session != self.session_id or after > snapshot.last_sequence:
            recovery = self.application.recover_unverified_events(
                requested_after=after, requested_session_id=requested_session)
            after = recovery[-1].sequence
        try:
            cursor = self.application.subscribe_events(
                self.session_id, after_sequence=after)
        except ValueError:
            self._send({"id": req_id, "type": "error", "category": "TRANSPORT",
                        "code": "INVALID_EVENT_CURSOR", "message": "Invalid event cursor"})
            return
        with self._lock:
            old = self._subscriptions.pop(req_id, None)
            if old is not None:
                old._stream.close(old)
            self._subscriptions[req_id] = cursor
            self._send({"id": req_id, "type": "subscribed", "schemaVersion": 1,
                        "sessionId": self.session_id, "afterSequence": cursor.position})
            if recovery is not None:
                for event in recovery:
                    self._send({"id": req_id, "type": "event", "schemaVersion": 1,
                                "event": event.to_dict()})
            self._wake.set()

    def _versioned_command(self, req_id: Any, request: dict[str, Any]) -> None:
        try:
            command = ApplicationCommand.from_dict(request["command"])
            if command.kind is CommandKind.RESOLVE_APPROVAL:
                if not verify_approval_proof(self._host_approval_key, command.to_dict(),
                                              request.get('hostApprovalProof')):
                    self._send({'id': req_id, 'type': 'error', 'category': 'APPROVAL',
                                'code': 'APPROVAL_ACTOR_INVALID',
                                'message': 'Host confirmation is required.'})
                    return
                command = replace(command, approval_actor=self._approval_actor)
            result = self.application.handle(command)
            if (command.kind in (CommandKind.CHANGE_MODEL, CommandKind.CHANGE_PROVIDER)
                    and isinstance(result, CommandReceipt) and result.accepted):
                self._on_provider_changed()
            if hasattr(result, "to_dict"):
                self._send({"id": req_id, "type": "application_result",
                            "schemaVersion": 1, "data": result.to_dict()})
            else:
                raise ValueError("unsupported application response")
        except (KeyError, TypeError, ValueError):
            self._send({"id": req_id, "type": "error", "category": "TRANSPORT",
                        "code": "INVALID_APPLICATION_COMMAND",
                        "message": "Invalid application command"})

    def _pump_events(self) -> None:
        while True:
            with self._lock:
                if self._closed:
                    return
                self._poll_legacy()
                for subscription_id, cursor in tuple(self._subscriptions.items()):
                    try:
                        events = self.application.poll_events(cursor)
                    except SubscriptionOutOfSync:
                        self._subscriptions.pop(subscription_id, None)
                        self._send({"id": subscription_id, "type": "subscription_out_of_sync",
                                    "code": "CONSUMER_OUT_OF_SYNC"})
                        continue
                    for event in events:
                        self._send({"id": subscription_id, "type": "event",
                                    "schemaVersion": 1, "event": event.to_dict()})
            self._wake.wait(0.02)
            self._wake.clear()

    def _poll_legacy(self) -> None:
        try:
            events = self.application.poll_events(self._legacy_cursor)
        except SubscriptionOutOfSync:
            snapshot = self.application.get_snapshot(self.session_id)
            self._legacy_cursor = self.application.subscribe_events(
                self.session_id, after_sequence=snapshot.last_sequence,
                include_internal=True)
            self._send({"type": "event_gap", "schemaVersion": 1,
                        "snapshot": snapshot.to_dict()})
            return
        for event in events:
            if event.kind in (EventKind.AGENT_COMPLETED, EventKind.AGENT_FAILED,
                              EventKind.AGENT_CANCELLED) and event.agent_id in self._agent_requests:
                agent_req_id, background = self._agent_requests.pop(event.agent_id)
                if not background:
                    self._send({"id": agent_req_id, "type": "agent_done",
                                "agent_id": event.agent_id,
                                "status": event.payload.get("status"),
                                "content": event.payload.get("content", ""),
                                "duration": event.payload.get("duration", 0),
                                "tool_calls": event.payload.get("toolCalls", 0),
                                "error": event.payload.get("error", "")})
                continue
            if event.kind is EventKind.APPROVAL_REQUIRED:
                self._confirm_seq += 1
                confirm_id = self._confirm_seq
                self._pending_confirms[confirm_id] = {
                    "approvalId": event.approval_id,
                    "toolCallId": event.tool_call_id,
                    "requestDigest": event.payload["requestDigest"],
                    "cwd": event.payload["cwd"],
                    "policyRevision": event.payload["policyRevision"],
                }
                self._send({"type": "confirm_request", "confirm_id": confirm_id,
                            "command": event.payload["arguments"].get("command", "")})
                continue
            if event.kind is EventKind.USER_INPUT_REQUIRED:
                self._input_seq += 1
                input_id = self._input_seq
                self._pending_inputs[input_id] = event.payload["inputRequestId"]
                self._send({"type": "input_request", "input_request_id": input_id,
                            "question": event.payload["question"]})
                continue
            if event.kind is EventKind.APPROVAL_RESOLVED:
                for key, pending in tuple(self._pending_confirms.items()):
                    if pending["approvalId"] == event.approval_id:
                        self._pending_confirms.pop(key, None)
                continue
            if event.kind is EventKind.USER_INPUT_RESOLVED:
                for key, value in tuple(self._pending_inputs.items()):
                    if value == event.payload["inputRequestId"]:
                        self._pending_inputs.pop(key, None)
                continue
            req_id = self._legacy_turns.get(event.turn_id)
            if req_id is not None:
                if event.kind in (EventKind.TURN_COMPLETED, EventKind.TURN_CANCELLED,
                                  EventKind.TURN_FAILED):
                    stopped = bool(self._stop_ids)
                    if event.kind is EventKind.TURN_COMPLETED and not stopped:
                        self._send({"id": req_id, "type": "done"})
                    elif event.kind is EventKind.TURN_FAILED and event.turn_id not in self._error_sent:
                        self._send({"id": req_id, "type": "error",
                                    "message": event.payload.get("errorCode") or "Turn failed"})
                    for stop_id in self._stop_ids:
                        self._send({"id": stop_id, "type": "stopped",
                                    "status": ("outcome_unknown" if event.payload.get("errorCode") == "OUTCOME_UNKNOWN"
                                               else "cancelled")})
                    self._stop_ids.clear()
                    self._active_turn_id = None
                    self._legacy_turns.pop(event.turn_id, None)
                    self._error_sent.discard(event.turn_id)
                    continue
                for frame in envelope_to_jsonl(event, req_id):
                    if frame["type"] == "error":
                        self._error_sent.add(event.turn_id)
                    if frame["type"] != "done":
                        self._send(frame)
            elif event.operation_id in self._legacy_turns:
                rag_req_id = self._legacy_turns[event.operation_id]
                if event.kind is EventKind.OPERATION_PROGRESS:
                    self._send({"id": rag_req_id, "type": "rag_progress",
                                "data": dict(event.payload)})
                elif event.kind in (EventKind.OPERATION_COMPLETED, EventKind.OPERATION_FAILED,
                                    EventKind.OPERATION_CANCELLED, EventKind.OPERATION_OUTCOME_UNKNOWN):
                    self._send({"id": rag_req_id, "type": "rag_result",
                                "data": event.payload.get("result")})
                    self._legacy_turns.pop(event.operation_id, None)
