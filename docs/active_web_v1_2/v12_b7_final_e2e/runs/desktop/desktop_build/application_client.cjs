"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// electron/application_client.ts
var application_client_exports = {};
__export(application_client_exports, {
  DesktopApplicationClient: () => DesktopApplicationClient,
  projectTranscript: () => projectTranscript
});
module.exports = __toCommonJS(application_client_exports);
var import_node_crypto = require("node:crypto");
var PRODUCT_COMMANDS = /* @__PURE__ */ new Set([
  "SubmitUserInput",
  "CancelTurn",
  "CancelOperation",
  "StopGeneration",
  "ChangeModel",
  "ChangeProvider",
  "ResolveApproval",
  "ResolveUserInput",
  "ExecuteCommand",
  "SetRAGEnabled",
  "QueryRAG"
]);
var MEMORY_COMMANDS = /* @__PURE__ */ new Set([
  "memory_status",
  "memory_list",
  "memory_search",
  "memory_show",
  "memory_remember",
  "memory_correct",
  "memory_forget",
  "memory_export",
  "memory_proposals",
  "memory_confirm",
  "memory_reject"
]);
var KNOWLEDGE_COMMANDS = /* @__PURE__ */ new Set([
  "source_import",
  "source_promote",
  "source_delete",
  "source_list",
  "source_status",
  "source_cancel",
  "source_import_url",
  "source_refresh_url",
  "source_refresh",
  "source_detail",
  "source_remote",
  "source_export"
]);
function projectTranscript(transcript, prefix) {
  const messages = [];
  transcript.forEach((raw, index) => {
    if (raw.role === "user" || raw.role === "assistant") {
      const calls = (raw.tool_calls || []).map((call) => ({
        name: call.function?.name || "",
        args: call.function?.arguments || {}
      }));
      messages.push({
        id: `${prefix}:${index}`,
        sourceIndex: index,
        role: raw.role,
        content: raw.content || "",
        ...raw.role === "assistant" && raw.knowledgeCitations ? { knowledgeCitations: raw.knowledgeCitations } : {},
        ...raw.role === "user" && Array.isArray(raw.attachmentRefs) ? { attachmentRefs: raw.attachmentRefs } : {},
        ...calls.length ? { toolCalls: calls, toolResults: [] } : {}
      });
    } else if (raw.role === "tool") {
      const last = messages[messages.length - 1];
      if (last?.role === "assistant") {
        last.toolResults = [...last.toolResults || [], { name: raw.tool_name || raw.name || "", output: raw.content || "" }];
      }
    }
  });
  return messages;
}
var DesktopApplicationClient = class {
  constructor(send, publish, approvalProof) {
    this.send = send;
    this.publish = publish;
    this.approvalProof = approvalProof;
  }
  view = {
    sessionId: null,
    sequence: 0,
    stateRevision: 0,
    workspace: null,
    status: { model: "", provider: "", connected: false, ready: false, tools: [] },
    messages: [],
    activeTurnId: null,
    activeGenerationId: null,
    approvals: [],
    inputs: [],
    resumable: null,
    rag: { enabled: false, availability: "UNKNOWN" },
    ragProgress: "",
    ragResult: null,
    error: null,
    gap: false,
    fileRevision: 0
  };
  serial = 0;
  snapshotRequest = null;
  refreshAgain = false;
  subscription = null;
  reconnectCursor = null;
  pending = /* @__PURE__ */ new Map();
  memoryPending = /* @__PURE__ */ new Map();
  knowledgePending = /* @__PURE__ */ new Map();
  browserPending = /* @__PURE__ */ new Map();
  id() {
    return `desktop-${++this.serial}`;
  }
  changed() {
    this.publish(this.view);
  }
  transmit(frame) {
    if (this.send(frame) === false) this.disconnected();
  }
  refresh() {
    if (!this.view.status.connected || !this.view.sessionId) return;
    if (this.snapshotRequest) {
      this.refreshAgain = true;
      return;
    }
    this.snapshotRequest = this.id();
    this.transmit({ id: this.snapshotRequest, type: "get_snapshot", sessionId: this.view.sessionId });
  }
  subscribe() {
    this.subscription = this.id();
    const cursor = this.reconnectCursor || { sessionId: this.view.sessionId, sequence: this.view.sequence };
    this.reconnectCursor = null;
    this.transmit({
      id: this.subscription,
      type: "subscribe_events",
      sessionId: cursor.sessionId,
      afterSequence: cursor.sequence
    });
  }
  disconnected() {
    if (this.view.sessionId) this.reconnectCursor = { sessionId: this.view.sessionId, sequence: this.view.sequence };
    this.snapshotRequest = this.subscription = null;
    this.refreshAgain = false;
    this.view = {
      ...this.view,
      status: { ...this.view.status, ready: false, connected: false },
      approvals: [],
      inputs: [],
      activeWeb: void 0,
      webCapabilitiesV12: void 0,
      webV12: void 0,
      error: { code: "BACKEND_DISCONNECTED", message: "Backend disconnected. Restart to restore the saved transcript; active work is not resumed." }
    };
    for (const { commandId, resolve } of this.pending.values()) resolve({
      schemaVersion: 1,
      commandId,
      accepted: false,
      createdIds: {},
      error: { code: "OUTCOME_UNKNOWN", message: "Connection lost; command outcome is unknown. It will not be retried." }
    });
    this.pending.clear();
    for (const { commandId, resolve } of this.knowledgePending.values()) resolve({
      schemaVersion: 1,
      commandId,
      accepted: false,
      createdIds: {},
      error: { code: "OUTCOME_UNKNOWN", message: "Source outcome unknown. No retry." }
    });
    this.knowledgePending.clear();
    for (const { commandId, resolve } of this.memoryPending.values()) resolve({
      schemaVersion: 1,
      commandId,
      completed: false,
      error: {
        code: "OUTCOME_UNKNOWN",
        message: "Connection lost; memory outcome is unknown. No retry.",
        outcomeUnknown: true,
        retryable: false
      }
    });
    this.memoryPending.clear();
    for (const { commandId, resolve } of this.browserPending.values()) resolve({
      schemaVersion: 1,
      commandId,
      error: { code: "OUTCOME_UNKNOWN", message: "Browser control outcome unknown. No retry.", outcomeUnknown: true, retryable: false }
    });
    this.browserPending.clear();
    this.changed();
  }
  command(kind, payload, commandId = `cmd_${(0, import_node_crypto.randomUUID)()}`) {
    if (!PRODUCT_COMMANDS.has(kind) || !this.view.status.ready || !this.view.sessionId) {
      return Promise.resolve({
        schemaVersion: 1,
        commandId,
        accepted: false,
        createdIds: {},
        error: { code: "APPLICATION_UNAVAILABLE", message: "Application command is unavailable." }
      });
    }
    return new Promise((resolve) => {
      const id = this.id();
      this.pending.set(id, { commandId, resolve });
      const command = {
        schemaVersion: 1,
        commandId,
        sessionId: this.view.sessionId,
        kind,
        payload,
        expectedRevision: null
      };
      this.transmit({
        id,
        type: "application_command",
        command,
        ...kind === "ResolveApproval" && this.approvalProof ? { hostApprovalProof: this.approvalProof(command) } : {}
      });
    });
  }
  memory(name, args, commandId = `cmd_${(0, import_node_crypto.randomUUID)()}`) {
    if (!MEMORY_COMMANDS.has(name) || !this.view.status.ready || !this.view.sessionId || !this.approvalProof) {
      return Promise.resolve({
        schemaVersion: 1,
        commandId,
        completed: false,
        error: { code: "MEMORY_UNAVAILABLE", message: "Authenticated memory control is unavailable." }
      });
    }
    return new Promise((resolve) => {
      const id = this.id();
      this.memoryPending.set(id, { commandId, resolve });
      const command = {
        schemaVersion: 1,
        kind: "MemoryControl",
        commandId,
        sessionId: this.view.sessionId,
        name,
        arguments: args,
        expectedRevision: this.view.stateRevision
      };
      this.transmit({ id, type: "memory_command", command, hostMemoryProof: this.approvalProof(command) });
    });
  }
  knowledge(name, args, commandId = `cmd_${(0, import_node_crypto.randomUUID)()}`) {
    if (!KNOWLEDGE_COMMANDS.has(name) || !this.view.status.ready || !this.view.sessionId || !this.approvalProof) {
      return Promise.resolve({
        schemaVersion: 1,
        commandId,
        accepted: false,
        createdIds: {},
        error: { code: "KNOWLEDGE_UNAVAILABLE", message: "Authenticated source control is unavailable." }
      });
    }
    return new Promise((resolve) => {
      const id = this.id();
      this.knowledgePending.set(id, { commandId, resolve });
      const command = {
        schemaVersion: 1,
        kind: "KnowledgeControl",
        commandId,
        sessionId: this.view.sessionId,
        name,
        arguments: args,
        expectedRevision: this.view.stateRevision
      };
      this.transmit({ id, type: "knowledge_command", command, hostKnowledgeProof: this.approvalProof(command) });
    });
  }
  // Main-process authenticated human configuration, separate from tool Approval.
  browser(name, args, commandId = `cmd_${(0, import_node_crypto.randomUUID)()}`) {
    if (!["configure_web_v12", "finish_takeover", "select_upload"].includes(name) || !this.view.status.ready || !this.view.sessionId || !this.approvalProof) {
      return Promise.resolve({ schemaVersion: 1, commandId, error: {
        code: "BROWSER_HUMAN_CONTROL_DENIED",
        message: "Authenticated host browser control is unavailable.",
        retryable: false
      } });
    }
    return new Promise((resolve) => {
      const id = this.id();
      this.browserPending.set(id, { commandId, resolve });
      const command = { commandId, sessionId: this.view.sessionId, name, arguments: args };
      this.transmit({ id, type: "browser_control", command, hostBrowserProof: this.approvalProof(command) });
    });
  }
  receive(frame) {
    if (frame.type === "ready") {
      this.view = {
        ...this.view,
        sessionId: frame.sessionId,
        status: { ...this.view.status, connected: true, ready: false, tools: frame.tools || [] },
        resumable: frame.resumable || null,
        ragProgress: "",
        ragResult: null,
        error: null
      };
      this.refresh();
    } else if (frame.type === "snapshot" && frame.id === this.snapshotRequest) {
      this.snapshotRequest = null;
      this.snapshot(frame.data);
      if (!this.subscription) this.subscribe();
      if (this.refreshAgain) {
        this.refreshAgain = false;
        this.refresh();
      }
    } else if (frame.type === "event" && frame.id === this.subscription && frame.schemaVersion === 1) {
      this.event(frame.event);
    } else if (frame.type === "subscription_out_of_sync" && frame.id === this.subscription) {
      this.reconnectCursor = { sessionId: this.view.sessionId, sequence: this.view.sequence };
      this.subscription = null;
      this.view = { ...this.view, gap: true };
      this.refresh();
    } else if (frame.type === "application_result" && this.pending.has(frame.id)) {
      const receipt = frame.data;
      this.pending.get(frame.id).resolve(receipt);
      this.pending.delete(frame.id);
      this.view = { ...this.view, error: receipt.accepted ? null : receipt.error || null };
      this.refresh();
    } else if (frame.type === "knowledge_result" && this.knowledgePending.has(frame.id)) {
      this.knowledgePending.get(frame.id).resolve(frame.data);
      this.knowledgePending.delete(frame.id);
      this.refresh();
    } else if (frame.type === "memory_result" && this.memoryPending.has(frame.id)) {
      this.memoryPending.get(frame.id).resolve(frame.data);
      this.memoryPending.delete(frame.id);
      this.refresh();
    } else if (frame.type === "browser_control_result" && this.browserPending.has(frame.id)) {
      this.browserPending.get(frame.id).resolve(frame.data);
      this.browserPending.delete(frame.id);
      this.refresh();
    } else if (frame.type === "error") {
      const error = { code: frame.code || "TRANSPORT_ERROR", message: frame.message || "Request failed" };
      if (this.pending.has(frame.id)) {
        const pending = this.pending.get(frame.id);
        pending.resolve({ schemaVersion: 1, commandId: pending.commandId, accepted: false, createdIds: {}, error });
        this.pending.delete(frame.id);
      }
      if (this.memoryPending.has(frame.id)) {
        const pending = this.memoryPending.get(frame.id);
        pending.resolve({ schemaVersion: 1, commandId: pending.commandId, completed: false, error });
        this.memoryPending.delete(frame.id);
      }
      if (this.knowledgePending.has(frame.id)) {
        const p = this.knowledgePending.get(frame.id);
        p.resolve({ schemaVersion: 1, commandId: p.commandId, accepted: false, createdIds: {}, error });
        this.knowledgePending.delete(frame.id);
      }
      if (this.browserPending.has(frame.id)) {
        const pending = this.browserPending.get(frame.id);
        pending.resolve({ schemaVersion: 1, commandId: pending.commandId, error: { ...error, retryable: false } });
        this.browserPending.delete(frame.id);
      }
      if (frame.id === this.snapshotRequest) this.snapshotRequest = null;
      this.view = { ...this.view, error };
    } else if (frame.type === "cwd_changed") {
      this.view = { ...this.view, resumable: frame.resumable || null };
      this.refresh();
    }
    this.changed();
  }
  snapshot(state) {
    if (!state || state.sessionId !== this.view.sessionId || !Array.isArray(state.transcript)) return;
    if (this.view.status.ready && state.lastSequence < this.view.sequence) {
      this.refreshAgain = true;
      return;
    }
    const active = state.turns.find((t) => !["completed", "failed", "cancelled"].includes(t.status));
    const lastTurn = state.turns[state.turns.length - 1];
    const lastRetrieval = [...state.services.operations || []].reverse().find((op) => op.service === "rag" && op.result);
    const messages = projectTranscript(state.transcript, state.sessionId);
    for (const turn of state.turns) {
      const rules = (turn.displayMessages || []).flatMap((m) => m.harnessEvents || []);
      const rows = messages.filter((m) => m.role === "assistant" && m.sourceIndex !== void 0 && m.sourceIndex >= turn.transcriptStart && m.sourceIndex < turn.transcriptEnd);
      if (rules.length && rows.length) rows[rows.length - 1].harnessEvents = rules;
    }
    if (active) {
      const display = active.displayMessages?.length ? active.displayMessages : [{ role: "assistant", content: "", thinking: true }];
      display.forEach((m, i) => messages.push({
        ...m,
        id: `${active.turnId}:${i}`,
        streaming: true
      }));
    }
    this.view = {
      ...this.view,
      sequence: state.lastSequence,
      stateRevision: state.stateRevision,
      workspace: state.workspace,
      activeTurnId: active?.turnId || null,
      messages,
      activeGenerationId: active?.activeGenerationId || null,
      status: {
        ...this.view.status,
        ready: true,
        connected: true,
        model: state.modelRuntime.modelId,
        provider: state.modelRuntime.providerId
      },
      approvals: state.services.interactions?.approvals || [],
      inputs: state.services.interactions?.inputs || [],
      rag: state.services.rag,
      knowledge: state.services.knowledge,
      activeWeb: state.services.activeWeb,
      webCapabilitiesV12: state.services.webCapabilitiesV12,
      webV12: state.services.webV12,
      knowledgeOperations: (state.services.operations || []).filter((op) => op.service === "knowledge"),
      memoryNotice: state.services.memory?.allowRemoteMemoryInjection ? "Remote memory injection is enabled by host configuration. Selected memories may leave this host." : null,
      ragProgress: state.services.operations?.find((op) => op.service === "rag" && ["running", "requested"].includes(op.status))?.phase || "",
      ragResult: lastRetrieval?.result || this.view.ragResult,
      fileRevision: state.services.filesystem?.revision ?? this.view.fileRevision,
      error: lastTurn?.status === "failed" ? { code: lastTurn.errorCode || "TURN_FAILED", message: "Turn failed." } : this.view.error,
      ...messages.length ? { resumable: null } : {}
    };
    if ((state.services.securityAudit?.deliveryFailures || 0) > 0) {
      this.view = { ...this.view, error: {
        code: "SECURITY_AUDIT_DELIVERY_FAILED",
        message: "Audit gap. Observed result retained; no automatic retry or rollback."
      } };
    }
  }
  event(event) {
    if (!event || event.schemaVersion !== 1 || event.sessionId !== this.view.sessionId) return;
    if (event.kind === "EventGap") this.view = { ...this.view, gap: true };
    if (event.sequence <= this.view.sequence) return;
    this.view = { ...this.view, sequence: event.sequence, stateRevision: event.stateRevision };
    if (event.payload.securityAudit?.gap === true) {
      this.view = { ...this.view, error: {
        code: "SECURITY_AUDIT_DELIVERY_FAILED",
        message: "Audit gap. Observed result retained; no automatic retry or rollback."
      } };
    }
    if (event.kind === "SessionSnapshot") {
      this.snapshot(event.payload);
      return;
    }
    if (event.kind === "AssistantDelta" || event.kind === "ThinkingDelta") {
      if (event.turnId !== this.view.activeTurnId || event.generationId !== this.view.activeGenerationId) {
        this.refresh();
        return;
      }
      const messages = [...this.view.messages];
      const last = messages[messages.length - 1];
      if (last?.role === "assistant") messages[messages.length - 1] = {
        ...last,
        content: event.kind === "AssistantDelta" ? last.content + event.payload.text : last.content,
        thinking: event.kind === "ThinkingDelta" && !last.content,
        streaming: true
      };
      this.view = { ...this.view, messages };
      return;
    }
    if (event.kind === "OperationProgress" && event.payload.service === "rag") {
      this.view = { ...this.view, ragProgress: event.payload.phase || "" };
    }
    if (event.payload.service === "rag" && event.kind.startsWith("Operation") && event.kind !== "OperationProgress") {
      this.view = { ...this.view, ragProgress: "", ragResult: event.payload.result || null };
    }
    if (["ToolCompleted", "ToolFailed"].includes(event.kind) && ["write", "edit", "bash"].includes(event.payload.name)) {
      this.view = { ...this.view, fileRevision: this.view.fileRevision + 1 };
    }
    this.refresh();
  }
};
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  DesktopApplicationClient,
  projectTranscript
});
