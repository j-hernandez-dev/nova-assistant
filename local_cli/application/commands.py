"""Transport-neutral command and receipt DTOs, without command handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from local_cli.core.contracts import CommandId, SessionId, json_safe_copy


class CommandKind(str, Enum):
    START_SESSION = "StartSession"
    GET_SNAPSHOT = "GetSnapshot"
    SUBMIT_USER_INPUT = "SubmitUserInput"
    CANCEL_TURN = "CancelTurn"
    STOP_GENERATION = "StopGeneration"
    CANCEL_OPERATION = "CancelOperation"
    CHANGE_MODEL = "ChangeModel"
    CHANGE_PROVIDER = "ChangeProvider"
    RESOLVE_APPROVAL = "ResolveApproval"
    RESOLVE_USER_INPUT = "ResolveUserInput"
    EXECUTE_COMMAND = "ExecuteCommand"
    START_SUB_AGENT = "StartSubAgent"
    CANCEL_SUB_AGENT = "CancelSubAgent"
    SET_RAG_ENABLED = "SetRAGEnabled"
    QUERY_RAG = "QueryRAG"
    GET_RAG_STATUS = "GetRAGStatus"
    SET_CONTEXT_WINDOW = "SetContextWindow"
    SET_EMBEDDING_SETTINGS = "SetEmbeddingSettings"
    RESET_EMBEDDING_SETTINGS = "ResetEmbeddingSettings"
    SET_KNOWLEDGE_SETTINGS = "SetKnowledgeSettings"
    RESET_KNOWLEDGE_SETTINGS = "ResetKnowledgeSettings"
    SET_WEB_SETTINGS = "SetWebSettings"
    SET_FETCH_ENABLED = "SetFetchEnabled"
    SET_SEARCH_ENGINE = "SetSearchEngine"
    SET_BROWSER = "SetBrowser"
    BROWSER_CONTROL = "BrowserControl"
    SUBSCRIBE_EVENTS = "SubscribeEvents"
    CLOSE_SESSION = "CloseSession"


_REQUIRED_FIELDS: dict[CommandKind, tuple[str, ...]] = {
    CommandKind.START_SESSION: ("workspace",),
    CommandKind.SUBMIT_USER_INPUT: ("content",),
    CommandKind.CANCEL_TURN: ("turnId",),
    CommandKind.STOP_GENERATION: ("generationId",),
    CommandKind.CANCEL_OPERATION: ("operationId",),
    CommandKind.CHANGE_MODEL: ("modelId",),
    CommandKind.CHANGE_PROVIDER: ("providerId",),
    CommandKind.RESOLVE_APPROVAL: ("approvalId", "toolCallId",
                                   "requestDigest", "cwd", "policyRevision",
                                   "approved"),
    CommandKind.RESOLVE_USER_INPUT: ("inputRequestId", "response"),
    CommandKind.EXECUTE_COMMAND: ("name",),
    CommandKind.START_SUB_AGENT: ("parentTurnId", "task", "mode"),
    CommandKind.CANCEL_SUB_AGENT: ("agentId",),
    CommandKind.SET_RAG_ENABLED: ("enabled",),
    CommandKind.SET_CONTEXT_WINDOW: ("requestedTokens",),
    CommandKind.SET_FETCH_ENABLED: ("enabled",),
    CommandKind.SET_SEARCH_ENGINE: ("engine",),
    CommandKind.SET_BROWSER: ("browser",),
    CommandKind.BROWSER_CONTROL: ("action",),
    CommandKind.QUERY_RAG: ("query",),
    CommandKind.CLOSE_SESSION: ("policy",),
}


@dataclass(frozen=True)
class ApplicationCommand:
    """A versioned command request; acceptance belongs to Application."""

    command_id: CommandId
    kind: CommandKind
    payload: Mapping[str, Any] = field(default_factory=dict)
    session_id: SessionId | None = None
    expected_revision: int | None = None
    schema_version: int = 1
    approval_actor: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1 or not self.command_id:
            raise ValueError("unsupported command version or missing commandId")
        if not isinstance(self.kind, CommandKind):
            raise TypeError("command kind must use CommandKind")
        if self.kind is CommandKind.START_SESSION:
            if self.session_id is not None:
                raise ValueError("StartSession does not target an existing session")
        elif not self.session_id:
            raise ValueError("command requires sessionId")
        if self.expected_revision is not None and (
                type(self.expected_revision) is not int or self.expected_revision < 0):
            raise ValueError("expectedRevision must be non-negative")
        for name in _REQUIRED_FIELDS.get(self.kind, ()):
            if name not in self.payload or self.payload[name] is None:
                raise ValueError(f"{self.kind.value} requires {name}")
        if self.kind is CommandKind.SUBMIT_USER_INPUT and (
                not isinstance(self.payload["content"], str) or
                not self.payload["content"].strip()):
            raise ValueError("SubmitUserInput requires non-empty content")
        if self.kind is CommandKind.SUBMIT_USER_INPUT and 'attachmentRefs' in self.payload:
            from local_cli.core.attachments import attachment_refs
            attachment_refs(self.payload['attachmentRefs'])
        if self.kind is CommandKind.START_SESSION and (
                not isinstance(self.payload["workspace"], str) or
                not self.payload["workspace"].strip()):
            raise ValueError("StartSession requires non-empty workspace")
        if self.kind is CommandKind.RESOLVE_APPROVAL and not isinstance(
                self.payload["approved"], bool):
            raise ValueError("ResolveApproval requires boolean approved")
        if self.kind is CommandKind.RESOLVE_APPROVAL and (
                not isinstance(self.payload["cwd"], str) or
                type(self.payload["policyRevision"]) is not int):
            raise ValueError("ResolveApproval requires cwd and policyRevision")
        if self.kind is CommandKind.RESOLVE_USER_INPUT and not isinstance(
                self.payload["response"], str):
            raise ValueError("ResolveUserInput requires a text response")
        if self.kind is CommandKind.SET_RAG_ENABLED and not isinstance(
                self.payload["enabled"], bool):
            raise ValueError("SetRAGEnabled requires boolean enabled")
        if self.kind is CommandKind.SET_CONTEXT_WINDOW:
            from local_cli.core.context import PRESETS
            if (set(self.payload) != {'requestedTokens'} or type(self.payload['requestedTokens']) is not int
                    or self.payload['requestedTokens'] not in (0, *PRESETS)):
                raise ValueError('SetContextWindow requires only requestedTokens: 0, 4096, 8192, 16384, 32768, 65536, 131072, or 262144')
        if self.kind is CommandKind.EXECUTE_COMMAND and self.payload.get('name') == 'clear_history':
            if set(self.payload) != {'name', 'scope'} or self.payload['scope'] != 'all':
                raise ValueError('clear_history requires scope: all')
        if self.kind is CommandKind.RESET_EMBEDDING_SETTINGS and self.payload:
            raise ValueError('ResetEmbeddingSettings requires an empty payload')
        if self.kind is CommandKind.SET_EMBEDDING_SETTINGS:
            from local_cli.embedding_settings import validate_settings
            validate_settings(dict(self.payload))
        if self.kind is CommandKind.RESET_KNOWLEDGE_SETTINGS and self.payload:
            raise ValueError('ResetKnowledgeSettings requires an empty payload')
        if self.kind is CommandKind.SET_KNOWLEDGE_SETTINGS:
            from local_cli.knowledge_preferences import validate_settings
            validate_settings(dict(self.payload))
        if self.kind is CommandKind.SET_WEB_SETTINGS:
            from local_cli.web_config import validate_web_settings
            validate_web_settings(dict(self.payload))
        if self.kind is CommandKind.SET_FETCH_ENABLED and (
                set(self.payload) != {'enabled'} or type(self.payload['enabled']) is not bool):
            raise ValueError('SetFetchEnabled requires only a boolean enabled')
        if self.kind is CommandKind.SET_SEARCH_ENGINE and (
                set(self.payload) != {'engine'} or self.payload['engine'] not in ('bing', 'google', 'duckduckgo')):
            raise ValueError('SetSearchEngine requires only engine: bing, google, or duckduckgo')
        if self.kind is CommandKind.SET_BROWSER and (
                set(self.payload) != {'browser'} or self.payload['browser'] not in ('webview2', 'chrome', 'edge')):
            raise ValueError('SetBrowser requires only browser: webview2, chrome, or edge')
        if self.kind is CommandKind.BROWSER_CONTROL:
            action = self.payload['action']
            fields = {'action', 'path'} if action == 'file' else {'action', 'downloadId'} if action == 'discard' else {'action'}
            if (action not in ('takeover', 'resume', 'close', 'file', 'downloads', 'discard') or set(self.payload) != fields
                    or any(not isinstance(v, str) or not v.strip() for v in self.payload.values())):
                raise ValueError('Invalid BrowserControl arguments')
        if self.kind is CommandKind.CLOSE_SESSION and (
                not isinstance(self.payload["policy"], str) or
                not self.payload["policy"].strip()):
            raise ValueError("CloseSession requires an explicit policy")
        object.__setattr__(self, "payload",
                           MappingProxyType(json_safe_copy(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {"schemaVersion": self.schema_version,
                "commandId": self.command_id, "kind": self.kind.value,
                "sessionId": self.session_id,
                "expectedRevision": self.expected_revision,
                "payload": json_safe_copy(self.payload)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ApplicationCommand:
        return cls(command_id=CommandId(data["commandId"]),
                   kind=CommandKind(data["kind"]), payload=data["payload"],
                   session_id=(SessionId(data["sessionId"])
                               if data.get("sessionId") is not None else None),
                   expected_revision=data.get("expectedRevision"),
                   schema_version=data["schemaVersion"])


class ErrorCategory(str, Enum):
    PROVIDER = "PROVIDER"
    MODEL = "MODEL"
    TOOL = "TOOL"
    POLICY = "POLICY"
    APPROVAL = "APPROVAL"
    CANCELLATION = "CANCELLATION"
    FILESYSTEM = "FILESYSTEM"
    GIT = "GIT"
    RAG = "RAG"
    CONTEXT = "CONTEXT"
    CAPABILITY = "CAPABILITY"
    TRANSPORT = "TRANSPORT"


@dataclass(frozen=True)
class ApplicationError:
    code: str
    category: ErrorCategory
    safe_message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if (not self.code or not self.safe_message or
                not isinstance(self.category, ErrorCategory) or
                not isinstance(self.retryable, bool)):
            raise ValueError("invalid typed application error")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "category": self.category.value,
                "message": self.safe_message, "retryable": self.retryable}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ApplicationError:
        return cls(code=data["code"], category=ErrorCategory(data["category"]),
                   safe_message=data["message"],
                   retryable=data.get("retryable", False))


@dataclass(frozen=True)
class CommandReceipt:
    """Accepted means queued/started, never that async work is complete."""

    command_id: CommandId
    accepted: bool
    session_id: SessionId | None = None
    state_revision: int | None = None
    created_ids: Mapping[str, str] = field(default_factory=dict)
    error: ApplicationError | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1 or not self.command_id:
            raise ValueError("unsupported receipt version or missing commandId")
        if not isinstance(self.accepted, bool):
            raise TypeError("receipt accepted must be a boolean")
        if self.accepted == (self.error is not None):
            raise ValueError("accepted receipt has no error; rejected receipt needs one")
        if self.state_revision is not None and (
                type(self.state_revision) is not int or self.state_revision < 0):
            raise ValueError("stateRevision must be non-negative")
        if any(not isinstance(key, str) or not isinstance(value, str)
               for key, value in self.created_ids.items()):
            raise ValueError("createdIds must map string names to IDs")
        object.__setattr__(self, "created_ids",
                           MappingProxyType(dict(self.created_ids)))

    def to_dict(self) -> dict[str, Any]:
        return {"schemaVersion": self.schema_version,
                "commandId": self.command_id, "accepted": self.accepted,
                "sessionId": self.session_id,
                "stateRevision": self.state_revision,
                "createdIds": dict(self.created_ids),
                "error": self.error.to_dict() if self.error else None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CommandReceipt:
        error = data.get("error")
        return cls(command_id=CommandId(data["commandId"]),
                   accepted=data["accepted"],
                   session_id=(SessionId(data["sessionId"])
                               if data.get("sessionId") is not None else None),
                   state_revision=data.get("stateRevision"),
                   created_ids=data.get("createdIds", {}),
                   error=ApplicationError.from_dict(error) if error else None,
                   schema_version=data["schemaVersion"])
