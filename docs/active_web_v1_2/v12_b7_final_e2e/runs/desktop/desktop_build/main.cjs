"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __commonJS = (cb, mod) => function __require() {
  return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// electron/memory_control.cjs
var require_memory_control = __commonJS({
  "electron/memory_control.cjs"(exports2, module2) {
    "use strict";
    async function memoryControl2(client, name, args, commandId, showDialog) {
      const reject = (code) => ({
        schemaVersion: 1,
        commandId: commandId || "",
        completed: false,
        error: { code, message: "Memory action cancelled, unavailable or stale.", retryable: false }
      });
      const sessionId = client.view.sessionId, workspace = client.view.workspace, revision = client.view.stateRevision;
      if (!sessionId || !client.view.status.ready) return reject("MEMORY_UNAVAILABLE");
      const frozen = JSON.parse(JSON.stringify(args));
      if (frozen.consentSensitive === true || frozen.includeSensitive === true) {
        const answer = await showDialog({ name, workspace, write: frozen.consentSensitive === true });
        if (answer.response !== 1) return reject("MEMORY_SENSITIVE_DENIED");
      }
      if (client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== revision) {
        return reject("REVISION_CONFLICT");
      }
      return client.memory(name, frozen, commandId);
    }
    module2.exports = { memoryControl: memoryControl2 };
  }
});

// electron/knowledge_control.cjs
var require_knowledge_control = __commonJS({
  "electron/knowledge_control.cjs"(exports2, module2) {
    "use strict";
    var ID_ACTIONS = /* @__PURE__ */ new Set(["source_list", "source_status", "source_promote", "source_delete", "source_cancel", "source_detail"]);
    var reject = (code) => ({
      schemaVersion: 1,
      commandId: "",
      accepted: false,
      createdIds: {},
      error: { code, message: "Source selection unavailable, cancelled or stale.", retryable: false }
    });
    async function pickKnowledge2(client, showPicker) {
      const { sessionId, workspace, stateRevision } = client.view;
      if (!sessionId || !client.view.status.ready) return reject("KNOWLEDGE_UNAVAILABLE");
      const picked = await showPicker();
      if (picked.canceled || !Array.isArray(picked.filePaths) || picked.filePaths.length !== 1 || typeof picked.filePaths[0] !== "string") return reject("IMPORT_CANCELLED");
      if (client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== stateRevision) return reject("REVISION_CONFLICT");
      return client.knowledge("source_import", { path: picked.filePaths[0], scope: "SESSION" });
    }
    function knowledgeControl2(client, name, args, commandId) {
      const keys = { source_import_url: ["url", "scope"], source_refresh_url: ["sourceId", "url"], source_detail: ["sourceId", "revisionId"] };
      const allowed = (Object.hasOwn(keys, name) ? keys[name] : null) || (ID_ACTIONS.has(name) ? [name === "source_cancel" ? "operationId" : "sourceId"] : null);
      if (!allowed || !args || Array.isArray(args) || typeof args !== "object" || Object.keys(args).some((k) => !allowed.includes(k))) {
        return Promise.resolve(reject("SOURCE_NOT_AUTHORIZED"));
      }
      return client.knowledge(name, args, commandId);
    }
    async function hostSelection2(client, name, sourceId, select) {
      const { sessionId, workspace, stateRevision } = client.view;
      if (!sessionId || !client.view.status.ready) return reject("KNOWLEDGE_UNAVAILABLE");
      const picked = await select();
      const path2 = name === "source_export" ? picked.filePath : picked.filePaths?.length === 1 ? picked.filePaths[0] : null;
      if (picked.canceled || typeof path2 !== "string") return reject("IMPORT_CANCELLED");
      if (client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== stateRevision) return reject("REVISION_CONFLICT");
      return client.knowledge(name, { sourceId, path: path2 });
    }
    async function remoteKnowledge2(client, args, showConfirm, commandId) {
      if (!client.view.sessionId || !client.view.status.ready) return reject("KNOWLEDGE_UNAVAILABLE");
      if (!args || !Object.hasOwn(args, "sourceId") || !Object.hasOwn(args, "allowed") || Object.keys(args).some((k) => !["sourceId", "allowed"].includes(k)) || typeof args.sourceId !== "string" || typeof args.allowed !== "boolean") return reject("SOURCE_NOT_AUTHORIZED");
      const frozen = JSON.parse(JSON.stringify(args));
      const { sessionId, workspace, stateRevision } = client.view;
      if (frozen.allowed) {
        const answer = await showConfirm();
        if (answer.response !== 1) return reject("REMOTE_FORWARDING_DENIED");
        if (client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== stateRevision) return reject("REVISION_CONFLICT");
      }
      return client.knowledge("source_remote", frozen, commandId);
    }
    module2.exports = { pickKnowledge: pickKnowledge2, knowledgeControl: knowledgeControl2, hostSelection: hostSelection2, remoteKnowledge: remoteKnowledge2 };
  }
});

// electron/approval_host.cjs
var require_approval_host = __commonJS({
  "electron/approval_host.cjs"(exports2, module2) {
    "use strict";
    var crypto2 = require("node:crypto");
    function stableJson(value) {
      if (Array.isArray(value)) return "[" + value.map(stableJson).join(",") + "]";
      if (value !== null && typeof value === "object") {
        return "{" + Object.keys(value).sort().map((k) => JSON.stringify(k) + ":" + stableJson(value[k])).join(",") + "}";
      }
      return JSON.stringify(value);
    }
    function signApproval2(key, command) {
      return crypto2.createHmac("sha256", Buffer.from(key, "hex")).update(stableJson(command), "utf8").digest("hex");
    }
    function validFrame2(value) {
      try {
        return value !== null && typeof value === "object" && !Array.isArray(value) && JSON.stringify(value).length <= 131072;
      } catch {
        return false;
      }
    }
    async function confirmApproval2(client, payload, commandId, showDialog) {
      const reject = (code) => ({
        schemaVersion: 1,
        commandId: commandId || "",
        accepted: false,
        createdIds: {},
        error: { code, message: "Approval is unavailable or stale." }
      });
      const pending = client.view.approvals.find((p) => p.approvalId === payload.approvalId);
      const sessionId = client.view.sessionId;
      if (!pending || typeof payload.approved !== "boolean" || !sessionId) return reject("APPROVAL_STALE");
      for (const field of ["toolCallId", "requestDigest", "cwd", "policyRevision"]) {
        if (payload[field] !== pending[field]) return reject("APPROVAL_STALE");
      }
      const snapshot = JSON.parse(JSON.stringify(pending));
      const fingerprint = stableJson(snapshot);
      if (!snapshot.deadline || !Number.isFinite(Date.parse(snapshot.deadline)) || Date.now() >= Date.parse(snapshot.deadline)) return reject("APPROVAL_EXPIRED");
      const approved = payload.approved && (await showDialog(snapshot)).response === 1;
      const current = client.view.approvals.find((p) => p.approvalId === snapshot.approvalId);
      if (client.view.sessionId !== sessionId || !current || stableJson(current) !== fingerprint || Date.now() >= Date.parse(snapshot.deadline)) return reject("APPROVAL_STALE");
      return client.command("ResolveApproval", {
        approvalId: snapshot.approvalId,
        toolCallId: snapshot.toolCallId,
        requestDigest: snapshot.requestDigest,
        cwd: snapshot.cwd,
        policyRevision: snapshot.policyRevision,
        approved: Boolean(approved)
      }, commandId);
    }
    module2.exports = { stableJson, signApproval: signApproval2, confirmApproval: confirmApproval2, validFrame: validFrame2 };
  }
});

// electron/web_v12_control.cjs
var require_web_v12_control = __commonJS({
  "electron/web_v12_control.cjs"(exports2, module2) {
    "use strict";
    var path2 = require("node:path");
    var RISK_ACKNOWLEDGEMENT_VERSION = "IB_V12_RISK_1";
    var RISK_MESSAGE = "Interactive Browser uses a real browser engine.";
    var RISK_DETAIL = "Nova does not provide exhaustive network isolation for this capability. It is not a hostile-site network sandbox.\n\nEnabling this feature does not approve remote mutations, uploads, downloads or login side effects. Each action still follows Policy and any required Approval/Grant.";
    var reject = (code) => ({ schemaVersion: 1, error: {
      code,
      message: "Web host control was not completed.",
      retryable: false
    } });
    async function configureWebV122(client, request, showRiskDialog, commandId) {
      if (!request || typeof request !== "object" || Array.isArray(request) || Object.keys(request).length !== 2 || !Object.hasOwn(request, "controlledFetchEnabled") || !Object.hasOwn(request, "interactiveBrowserEnabled") || typeof request.controlledFetchEnabled !== "boolean" || typeof request.interactiveBrowserEnabled !== "boolean") {
        return reject("WEB_V12_CONFIGURATION_INVALID");
      }
      const { sessionId, workspace, stateRevision } = client.view;
      if (!sessionId || !client.view.status.ready) return reject("WEB_V12_APPLICATION_UNAVAILABLE");
      const frozen = {
        controlledFetchEnabled: request.controlledFetchEnabled,
        interactiveBrowserEnabled: request.interactiveBrowserEnabled
      };
      if (frozen.interactiveBrowserEnabled) {
        const answer = await showRiskDialog({ message: RISK_MESSAGE, detail: RISK_DETAIL });
        if (answer?.response !== 1) return reject("WEB_V12_RISK_ACKNOWLEDGEMENT_DENIED");
      }
      if (!client.view.status.ready || client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== stateRevision) return reject("REVISION_CONFLICT");
      return client.browser("configure_web_v12", { ...frozen, acknowledgementVersion: RISK_ACKNOWLEDGEMENT_VERSION }, commandId);
    }
    async function selectWebV12Upload2(client, operationId, showPicker, commandId) {
      if (typeof operationId !== "string" || !operationId || operationId.length > 128) return reject("BROWSER_UPLOAD_SELECTION_INVALID");
      const { sessionId, workspace, stateRevision } = client.view;
      const pending = client.view.webV12?.uploadRequests?.find((item) => item.operationId === operationId);
      if (!sessionId || !client.view.status.ready || !pending) return reject("BROWSER_UPLOAD_SELECTION_UNAVAILABLE");
      const fingerprint = JSON.stringify(pending);
      const selected = await showPicker({ origin: pending.origin, label: pending.label });
      if (selected?.canceled || !Array.isArray(selected?.filePaths) || selected.filePaths.length !== 1 || typeof selected.filePaths[0] !== "string" || !path2.isAbsolute(selected.filePaths[0])) {
        return reject("BROWSER_UPLOAD_SELECTION_CANCELLED");
      }
      const current = client.view.webV12?.uploadRequests?.find((item) => item.operationId === operationId);
      if (!client.view.status.ready || client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== stateRevision || !current || JSON.stringify(current) !== fingerprint) return reject("REVISION_CONFLICT");
      return client.browser("select_upload", { operationId, path: selected.filePaths[0] }, commandId);
    }
    async function finishWebV12Takeover2(client, takeoverRef, showConfirm, commandId) {
      if (typeof takeoverRef !== "string" || !takeoverRef || takeoverRef.length > 128) return reject("BROWSER_TAKEOVER_REQUEST_INVALID");
      const { sessionId, workspace, stateRevision } = client.view;
      const pending = client.view.webV12?.takeoverRequests?.find((item) => item.takeoverRef === takeoverRef);
      if (!sessionId || !client.view.status.ready || !pending || client.view.webV12?.browserState === "blocked") {
        return reject("BROWSER_TAKEOVER_REQUEST_UNAVAILABLE");
      }
      const fingerprint = JSON.stringify(pending), deadline = Date.parse(pending.deadline);
      if (!Number.isFinite(deadline) || Date.now() >= deadline) return reject("BROWSER_TAKEOVER_EXPIRED");
      const answer = await showConfirm({ reason: pending.reason });
      if (answer?.response !== 1) return reject("BROWSER_TAKEOVER_FINISH_CANCELLED");
      const current = client.view.webV12?.takeoverRequests?.find((item) => item.takeoverRef === takeoverRef);
      if (!client.view.status.ready || client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== stateRevision || client.view.webV12?.browserState === "blocked" || !current || JSON.stringify(current) !== fingerprint || Date.now() >= deadline) return reject("REVISION_CONFLICT");
      return client.browser("finish_takeover", { takeoverRef, authenticated: false }, commandId);
    }
    module2.exports = { configureWebV12: configureWebV122, selectWebV12Upload: selectWebV12Upload2, finishWebV12Takeover: finishWebV12Takeover2, RISK_ACKNOWLEDGEMENT_VERSION, RISK_MESSAGE, RISK_DETAIL };
  }
});

// electron/main.ts
var import_electron = require("electron");
var import_child_process = require("child_process");
var import_node_http = __toESM(require("node:http"));
var import_node_https = __toESM(require("node:https"));
var import_node_crypto2 = __toESM(require("node:crypto"));
var import_node_fs = __toESM(require("node:fs"));
var import_node_os = __toESM(require("node:os"));
var import_path = __toESM(require("path"));

// electron/application_client.ts
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

// electron/main.ts
var import_memory_control = __toESM(require_memory_control());
var import_knowledge_control = __toESM(require_knowledge_control());
var import_approval_host = __toESM(require_approval_host());
var import_web_v12_control = __toESM(require_web_v12_control());
var desktopDataPath = import_path.default.join(import_electron.app.getPath("appData"), "nova-desktop");
import_node_fs.default.mkdirSync(desktopDataPath, { recursive: true });
import_electron.app.setPath("userData", desktopDataPath);
import_electron.app.setPath("sessionData", desktopDataPath);
var APP_VERSION = import_electron.app.getVersion();
var GITHUB_REPO = "lutelute/local-cli";
var CLAUDE_AUTH_PATH = import_path.default.join(
  process.env.XDG_CONFIG_HOME || import_path.default.join(import_node_os.default.homedir(), ".config"),
  "nova",
  "claude-auth.json"
);
var mainWindow = null;
var pythonProcess = null;
var lineBuffer = "";
var rendererReady = false;
var lastReadyMessage = null;
var storedApiKey = null;
var restartWorkspace = null;
var restartReady = null;
var restoreAfterRestart = false;
var approvalHostKey = "";
var applicationClient = new DesktopApplicationClient(sendToPython, (view) => {
  if (rendererReady && mainWindow && !mainWindow.webContents.isDestroyed()) {
    mainWindow.webContents.send("session-view", view);
  }
}, (command) => (0, import_approval_host.signApproval)(approvalHostKey, command));
function loadClaudeAuth() {
  try {
    if (!import_node_fs.default.existsSync(CLAUDE_AUTH_PATH)) return null;
    const raw = import_node_fs.default.readFileSync(CLAUDE_AUTH_PATH, "utf-8");
    const data = JSON.parse(raw);
    if (data.encrypted && import_electron.safeStorage.isEncryptionAvailable()) {
      data.key = import_electron.safeStorage.decryptString(Buffer.from(data.key, "base64"));
    }
    return data;
  } catch {
    return null;
  }
}
function saveClaudeAuth(method, key) {
  const dir = import_path.default.dirname(CLAUDE_AUTH_PATH);
  import_node_fs.default.mkdirSync(dir, { recursive: true });
  let storedKey = key;
  let encrypted = false;
  if (import_electron.safeStorage.isEncryptionAvailable()) {
    storedKey = import_electron.safeStorage.encryptString(key).toString("base64");
    encrypted = true;
  }
  import_node_fs.default.writeFileSync(
    CLAUDE_AUTH_PATH,
    JSON.stringify({ method, key: storedKey, encrypted }),
    { mode: 384 }
  );
}
function deleteClaudeAuth() {
  try {
    import_node_fs.default.unlinkSync(CLAUDE_AUTH_PATH);
  } catch {
  }
  storedApiKey = null;
}
function initClaudeAuth() {
  const auth = loadClaudeAuth();
  if (auth?.key) {
    storedApiKey = auth.key;
    process.env.ANTHROPIC_API_KEY = auth.key;
  }
}
function validateApiKey(key) {
  return new Promise((resolve) => {
    const body = JSON.stringify({
      model: "claude-haiku-4-5",
      max_tokens: 1,
      messages: [{ role: "user", content: "hi" }]
    });
    const req = import_node_https.default.request(
      "https://api.anthropic.com/v1/messages",
      {
        method: "POST",
        headers: {
          "x-api-key": key,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json"
        },
        timeout: 15e3
      },
      (res) => {
        let data = "";
        res.on("data", (c) => {
          data += c;
        });
        res.on("end", () => {
          if (res.statusCode === 200) {
            resolve({ valid: true });
          } else if (res.statusCode === 401) {
            resolve({ valid: false, error: "Invalid API key." });
          } else {
            resolve({ valid: true });
          }
        });
      }
    );
    req.on("error", () => resolve({ valid: false, error: "Could not reach Anthropic API." }));
    req.on("timeout", () => {
      req.destroy();
      resolve({ valid: false, error: "Request timed out." });
    });
    req.write(body);
    req.end();
  });
}
function startOAuthFlow() {
  return new Promise((resolve) => {
    const state = import_node_crypto2.default.randomBytes(16).toString("hex");
    let resolved = false;
    const server = import_node_http.default.createServer((req, res) => {
      const url = new URL(req.url || "/", `http://localhost`);
      if (url.pathname !== "/callback") {
        res.writeHead(404);
        res.end();
        return;
      }
      const code = url.searchParams.get("code");
      const returnedState = url.searchParams.get("state");
      const error = url.searchParams.get("error");
      if (error) {
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end("<html><body><h2>Login failed</h2><p>You can close this window.</p></body></html>");
        if (!resolved) {
          resolved = true;
          server.close();
          resolve({ success: false, error: `OAuth error: ${error}` });
        }
        return;
      }
      if (!code || returnedState !== state) {
        res.writeHead(400, { "Content-Type": "text/html" });
        res.end("<html><body><h2>Invalid request</h2></body></html>");
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html" });
      res.end("<html><body><h2>Login successful!</h2><p>You can close this window and return to Local CLI.</p></body></html>");
      if (!resolved) {
        resolved = true;
        server.close();
        exchangeOAuthCode(code).then((result) => {
          if (result.apiKey) {
            saveClaudeAuth("subscription", result.apiKey);
            storedApiKey = result.apiKey;
            process.env.ANTHROPIC_API_KEY = result.apiKey;
            sendToPython({ type: "set_api_key", api_key: result.apiKey });
            resolve({ success: true });
          } else {
            resolve({ success: false, error: result.error || "Failed to exchange code." });
          }
        });
      }
    });
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      if (!addr || typeof addr === "string") {
        resolve({ success: false, error: "Failed to start callback server." });
        return;
      }
      const port = addr.port;
      const redirectUri = `http://127.0.0.1:${port}/callback`;
      const authUrl = `https://console.anthropic.com/oauth/authorize?response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}&client_id=local-cli`;
      import_electron.shell.openExternal(authUrl);
      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          server.close();
          resolve({ success: false, error: "Login timed out. Please try again." });
        }
      }, 3e5);
    });
    server.on("error", () => {
      if (!resolved) {
        resolved = true;
        resolve({ success: false, error: "Failed to start callback server." });
      }
    });
  });
}
function exchangeOAuthCode(code) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ code, grant_type: "authorization_code", client_id: "local-cli" });
    const req = import_node_https.default.request(
      "https://console.anthropic.com/oauth/token",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        timeout: 15e3
      },
      (res) => {
        let data = "";
        res.on("data", (c) => {
          data += c;
        });
        res.on("end", () => {
          try {
            const json = JSON.parse(data);
            if (json.access_token) {
              resolve({ apiKey: json.access_token });
            } else {
              resolve({ error: json.error || "No access token returned." });
            }
          } catch {
            resolve({ error: "Invalid response from auth server." });
          }
        });
      }
    );
    req.on("error", () => resolve({ error: "Could not reach auth server." }));
    req.on("timeout", () => {
      req.destroy();
      resolve({ error: "Auth request timed out." });
    });
    req.write(body);
    req.end();
  });
}
function findPython() {
  if (process.platform === "win32") return "python";
  const candidates = process.platform === "darwin" ? [
    "/opt/homebrew/bin/python3",
    // macOS ARM Homebrew
    "/usr/local/bin/python3",
    // macOS Intel Homebrew
    "python3"
  ] : [
    "/usr/bin/python3",
    // Linux system Python
    "/usr/local/bin/python3",
    // Linux manual install
    "python3"
  ];
  for (const candidate of candidates) {
    try {
      const { execFileSync } = require("child_process");
      execFileSync(candidate, ["--version"], { stdio: "ignore" });
      return candidate;
    } catch {
    }
  }
  return "python3";
}
function findProjectRoot() {
  if (import_electron.app.isPackaged && process.resourcesPath) {
    return import_path.default.resolve(process.resourcesPath);
  }
  return import_path.default.resolve(__dirname, "..", "..");
}
function startPythonServer() {
  const pythonCmd = findPython();
  const projectRoot = findProjectRoot();
  console.log(`Starting Python server: ${pythonCmd} -m local_cli --server`);
  console.log(`Working directory: ${projectRoot}`);
  const env = { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" };
  approvalHostKey = import_node_crypto2.default.randomBytes(32).toString("hex");
  env.NOVA_APPROVAL_HOST_KEY = approvalHostKey;
  if (storedApiKey) {
    env.ANTHROPIC_API_KEY = storedApiKey;
  }
  lineBuffer = "";
  lastReadyMessage = null;
  const child = (0, import_child_process.spawn)(pythonCmd, ["-m", "local_cli", "--server"], {
    cwd: projectRoot,
    stdio: ["pipe", "pipe", "pipe"],
    env,
    windowsHide: true
  });
  pythonProcess = child;
  child.stdout?.setEncoding("utf8");
  child.stderr?.setEncoding("utf8");
  child.stdout?.on("data", (data) => {
    if (pythonProcess !== child) return;
    lineBuffer += data;
    const lines = lineBuffer.split("\n");
    lineBuffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        if (msg.type === "ready") {
          lastReadyMessage = msg;
          if (restartWorkspace) {
            restartReady = msg;
            sendToPython({ id: "desktop-restart-cwd", type: "set_cwd", path: restartWorkspace });
            continue;
          }
        }
        if (msg.id === "desktop-restart-cwd") {
          restartWorkspace = null;
          if (msg.type === "cwd_changed" && restartReady) {
            applicationClient.receive(restartReady);
            restoreAfterRestart = !!msg.resumable;
          } else {
            applicationClient.receive(restartReady || {});
            applicationClient.receive(msg);
          }
          restartReady = null;
        }
        applicationClient.receive(msg);
        if (restoreAfterRestart && applicationClient.view.status.ready) {
          restoreAfterRestart = false;
          void applicationClient.command("ExecuteCommand", { name: "resume" });
        }
        if (rendererReady && mainWindow) {
          mainWindow.webContents.send("python-message", msg);
        }
      } catch {
        console.error("Invalid JSON from Python");
      }
    }
  });
  child.stderr?.on("data", (text) => {
    if (pythonProcess !== child) return;
    console.error("[python stderr]", text);
    mainWindow?.webContents.send("python-stderr", text);
  });
  child.on("error", () => {
    if (pythonProcess !== child) return;
    pythonProcess = null;
    applicationClient.disconnected();
  });
  child.stdin?.on("error", () => {
    if (pythonProcess === child) applicationClient.disconnected();
  });
  child.on("exit", (code) => {
    if (pythonProcess !== child) return;
    console.log(`Python process exited with code ${code}`);
    mainWindow?.webContents.send("python-exit", code);
    pythonProcess = null;
    applicationClient.disconnected();
  });
}
function sendToPython(data) {
  if (pythonProcess?.stdin?.writable) {
    try {
      pythonProcess.stdin.write(JSON.stringify(data) + "\n");
      return true;
    } catch {
      return false;
    }
  }
  return false;
}
function createWindow() {
  mainWindow = new import_electron.BrowserWindow({
    width: 1e3,
    height: 700,
    minWidth: 600,
    minHeight: 400,
    ...process.platform === "darwin" ? { titleBarStyle: "hiddenInset", trafficLightPosition: { x: 16, y: 16 } } : {},
    webPreferences: {
      preload: import_path.default.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(import_path.default.join(__dirname, "../dist/index.html"));
  }
  mainWindow.on("closed", () => {
    rendererReady = false;
    mainWindow = null;
  });
  mainWindow.webContents.on("did-start-loading", () => {
    rendererReady = false;
  });
}
function validApplicationSender(event) {
  return !!mainWindow && event.sender === mainWindow.webContents && event.senderFrame === mainWindow.webContents.mainFrame;
}
import_electron.ipcMain.on("send-to-python", (event, data) => {
  if (!validApplicationSender(event) || !(0, import_approval_host.validFrame)(data) || data.type === "memory_command" || data.type === "knowledge_command" || data.type === "browser_control" || data.type === "confirm_response" || data.type === "application_command" && data.command?.kind === "ResolveApproval") return;
  sendToPython(data);
});
import_electron.ipcMain.handle("configure-web-v12", async (event, configuration) => {
  if (!validApplicationSender(event) || !mainWindow || !(0, import_approval_host.validFrame)(configuration)) return {
    schemaVersion: 1,
    error: { code: "BROWSER_HUMAN_CONTROL_DENIED", message: "Main-frame host confirmation required.", retryable: false }
  };
  return (0, import_web_v12_control.configureWebV12)(applicationClient, configuration, (request) => import_electron.dialog.showMessageBox(mainWindow, {
    type: "warning",
    title: "Nova \u2014 Interactive Browser",
    message: request.message,
    detail: request.detail,
    buttons: ["Cancel", "Enable Interactive Browser"],
    defaultId: 0,
    cancelId: 0,
    noLink: true
  }));
});
import_electron.ipcMain.handle("web-v12-select-upload", async (event, operationId) => {
  if (!validApplicationSender(event) || !mainWindow || typeof operationId !== "string") return {
    schemaVersion: 1,
    error: { code: "BROWSER_HUMAN_CONTROL_DENIED", message: "Main-frame host file picker required.", retryable: false }
  };
  return (0, import_web_v12_control.selectWebV12Upload)(applicationClient, operationId, (request) => import_electron.dialog.showOpenDialog(mainWindow, {
    title: "Nova \u2014 select this upload file",
    message: request.origin + " \u2014 " + request.label,
    properties: ["openFile"]
  }));
});
import_electron.ipcMain.handle("web-v12-finish-takeover", async (event, takeoverRef) => {
  if (!validApplicationSender(event) || !mainWindow || typeof takeoverRef !== "string") return {
    schemaVersion: 1,
    error: { code: "BROWSER_HUMAN_CONTROL_DENIED", message: "Main-frame human control confirmation required.", retryable: false }
  };
  return (0, import_web_v12_control.finishWebV12Takeover)(applicationClient, takeoverRef, (request) => import_electron.dialog.showMessageBox(mainWindow, {
    type: "warning",
    title: "Nova \u2014 finalizar control humano",
    message: "\xBFFinalizar este control humano del navegador?",
    detail: "Motivo: " + request.reason + "\nPrimero completa la interacci\xF3n en la ventana del navegador y pulsa su control de finalizaci\xF3n. Nova comprobar\xE1 la continuidad sensible, invalidar\xE1 las referencias anteriores y observar\xE1 de nuevo antes de continuar. Si no puede confirmarlo, quedar\xE1 bloqueado. Esto no declara un login ni aprueba efectos remotos.",
    buttons: ["Cancelar", "Finalizar control humano"],
    defaultId: 0,
    cancelId: 0,
    noLink: true
  }));
});
import_electron.ipcMain.handle("memory-command", async (event, name, args, commandId) => {
  if (!validApplicationSender(event) || typeof name !== "string" || !(0, import_approval_host.validFrame)(args)) {
    return {
      schemaVersion: 1,
      commandId: commandId || "",
      completed: false,
      error: { code: "MEMORY_UNTRUSTED_INPUT", message: "Invalid memory action." }
    };
  }
  return (0, import_memory_control.memoryControl)(applicationClient, name, args, commandId, (request) => import_electron.dialog.showMessageBox(mainWindow, {
    type: "warning",
    title: "Nova \u2014 sensitive memory",
    message: request.write ? "Allow this exact sensitive memory write?" : "Reveal sensitive content for this memory inspection/export?",
    detail: request.name + "\nWorkspace: " + request.workspace + "\nLocal storage is not process isolation or encryption. Forget does not erase audit, logs, source conversations or backups.",
    buttons: ["Cancel", "Allow"],
    defaultId: 0,
    cancelId: 0,
    noLink: true
  }));
});
import_electron.ipcMain.handle("knowledge-pick", async (event) => {
  if (!validApplicationSender(event) || !mainWindow) return {
    schemaVersion: 1,
    commandId: "",
    accepted: false,
    createdIds: {},
    error: { code: "SOURCE_NOT_AUTHORIZED", message: "Main-frame host picker required." }
  };
  return (0, import_knowledge_control.pickKnowledge)(applicationClient, () => import_electron.dialog.showOpenDialog(mainWindow, { properties: ["openFile"] }));
});
import_electron.ipcMain.handle("knowledge-command", async (event, name, args, commandId) => {
  if (!validApplicationSender(event) || !(0, import_approval_host.validFrame)(args)) return {
    schemaVersion: 1,
    commandId: "",
    accepted: false,
    createdIds: {},
    error: { code: "SOURCE_NOT_AUTHORIZED", message: "Invalid source control." }
  };
  if (name === "source_remote") return (0, import_knowledge_control.remoteKnowledge)(applicationClient, args, () => import_electron.dialog.showMessageBox(mainWindow, {
    type: "warning",
    title: "Nova \u2014 document forwarding",
    message: "Allow this source in remote chat context?",
    detail: "Document data may leave this device. This does not enable remote MEMORY or grant tool/security authority. Future forwarding can be revoked; already transmitted data cannot be recalled.",
    buttons: ["Cancel", "Allow"],
    defaultId: 0,
    cancelId: 0,
    noLink: true
  }), commandId);
  return (0, import_knowledge_control.knowledgeControl)(applicationClient, name, args, commandId);
});
import_electron.ipcMain.handle("knowledge-refresh", async (event, sourceId) => {
  if (!validApplicationSender(event) || !mainWindow || typeof sourceId !== "string") return { accepted: false, error: { code: "SOURCE_NOT_AUTHORIZED" } };
  return (0, import_knowledge_control.hostSelection)(applicationClient, "source_refresh", sourceId, () => import_electron.dialog.showOpenDialog(mainWindow, { properties: ["openFile"] }));
});
import_electron.ipcMain.handle("knowledge-export", async (event, sourceId) => {
  if (!validApplicationSender(event) || !mainWindow || typeof sourceId !== "string") return { accepted: false, error: { code: "SOURCE_NOT_AUTHORIZED" } };
  return (0, import_knowledge_control.hostSelection)(applicationClient, "source_export", sourceId, () => import_electron.dialog.showSaveDialog(mainWindow, { defaultPath: "nova-source-export.bin" }));
});
import_electron.ipcMain.handle("get-python-status", () => {
  return { running: pythonProcess !== null && !pythonProcess.killed };
});
import_electron.ipcMain.handle("application-command", async (event, kind, payload, commandId) => {
  if (!validApplicationSender(event) || typeof kind !== "string" || !(0, import_approval_host.validFrame)(payload)) {
    return {
      schemaVersion: 1,
      commandId: commandId || "",
      accepted: false,
      createdIds: {},
      error: { code: "INVALID_APPLICATION_COMMAND", message: "Invalid application command." }
    };
  }
  if (kind === "ResolveApproval") {
    return (0, import_approval_host.confirmApproval)(applicationClient, payload, commandId, (request) => {
      const browserAction = ["browser_navigate", "browser_act", "browser_upload", "browser_download", "browser_takeover"].includes(request.name);
      return import_electron.dialog.showMessageBox(mainWindow, {
        type: "warning",
        title: browserAction ? "Nova \u2014 confirmar acci\xF3n web" : "Nova \u2014 confirmar ejecuci\xF3n local",
        message: browserAction ? "\xBFPermitir esta acci\xF3n web exacta?" : "Este comando se ejecutar\xE1 con los permisos normales de tu cuenta.",
        detail: (browserAction ? "Acci\xF3n: " + request.name + "\nLa p\xE1gina puede recibir datos o realizar un efecto remoto. La aceptaci\xF3n del riesgo del navegador no aprueba esta acci\xF3n.\n\n" : "Carpeta: " + request.cwd + "\n\n") + String(request.arguments.command || JSON.stringify(request.arguments)) + (request.arguments.environment ? "\n\nEnvironment: " + JSON.stringify(request.arguments.environment) : ""),
        buttons: ["Cancelar", "Ejecutar"],
        defaultId: 0,
        cancelId: 0,
        noLink: true
      });
    });
  }
  return applicationClient.command(kind, payload, commandId);
});
import_electron.ipcMain.handle("restart-backend", () => {
  if (pythonProcess) return { success: false, error: "Backend is already running." };
  restartWorkspace = applicationClient.view.workspace || findProjectRoot();
  startPythonServer();
  return { success: true };
});
import_electron.ipcMain.on("renderer-ready", () => {
  rendererReady = true;
  mainWindow?.webContents.send("session-view", applicationClient.view);
  applicationClient.refresh();
  if (lastReadyMessage) {
    mainWindow?.webContents.send("python-message", lastReadyMessage);
  }
});
import_electron.ipcMain.handle("open-directory-dialog", async () => {
  const result = await import_electron.dialog.showOpenDialog({ properties: ["openDirectory"] });
  return result;
});
import_electron.ipcMain.handle("list-directory", async (_event, dirPath) => {
  const entries = await import_node_fs.default.promises.readdir(dirPath, { withFileTypes: true });
  const results = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = import_path.default.join(dirPath, entry.name);
      let isSymlink = false;
      try {
        const stat = await import_node_fs.default.promises.lstat(fullPath);
        isSymlink = stat.isSymbolicLink();
      } catch {
      }
      return { name: entry.name, isDirectory: entry.isDirectory(), isSymlink };
    })
  );
  return results;
});
var MAX_FILE_SIZE = 1e6;
import_electron.ipcMain.handle("read-file", async (_event, filePath) => {
  const stat = await import_node_fs.default.promises.stat(filePath);
  if (stat.size > MAX_FILE_SIZE) {
    return { error: "too_large", size: stat.size };
  }
  const content = await import_node_fs.default.promises.readFile(filePath, "utf-8");
  return { content };
});
import_electron.ipcMain.handle("get-home-dir", () => {
  return import_node_os.default.homedir();
});
import_electron.ipcMain.handle("has-claude-access", () => {
  return !!process.env.ANTHROPIC_API_KEY || !!storedApiKey;
});
import_electron.ipcMain.handle("get-claude-auth", () => {
  const auth = loadClaudeAuth();
  if (!auth) return { method: null, keyHint: null, authenticated: false };
  const hint = auth.key ? auth.key.slice(0, 10) + "..." + auth.key.slice(-4) : null;
  return { method: auth.method, keyHint: hint, authenticated: true };
});
import_electron.ipcMain.handle("save-claude-key", async (_event, key) => {
  const validation = await validateApiKey(key);
  if (!validation.valid) {
    return { success: false, error: validation.error };
  }
  saveClaudeAuth("api_key", key);
  storedApiKey = key;
  process.env.ANTHROPIC_API_KEY = key;
  sendToPython({ type: "set_api_key", api_key: key });
  const hint = key.slice(0, 10) + "..." + key.slice(-4);
  return { success: true, keyHint: hint };
});
import_electron.ipcMain.handle("delete-claude-auth", () => {
  deleteClaudeAuth();
  delete process.env.ANTHROPIC_API_KEY;
  return { success: true };
});
import_electron.ipcMain.handle("start-claude-oauth", async () => {
  return await startOAuthFlow();
});
import_electron.ipcMain.handle("get-app-version", () => APP_VERSION);
import_electron.ipcMain.handle("check-app-update", async () => {
  try {
    const data = await fetchJson(`https://api.github.com/repos/${GITHUB_REPO}/releases/latest`);
    const latest = (data.tag_name || "").replace(/^v/, "");
    if (latest && latest !== APP_VERSION) {
      let downloadAsset;
      let zipAsset;
      if (process.platform === "darwin") {
        downloadAsset = data.assets?.find((a) => a.name.endsWith(".dmg"));
        zipAsset = data.assets?.find((a) => a.name.endsWith("-mac.zip") || a.name.endsWith(".zip"));
      } else if (process.platform === "linux") {
        downloadAsset = data.assets?.find((a) => a.name.endsWith(".AppImage"));
        zipAsset = data.assets?.find((a) => a.name.endsWith(".deb"));
      } else {
        downloadAsset = data.assets?.find((a) => a.name.endsWith(".exe"));
      }
      return {
        available: true,
        version: latest,
        notes: data.body || "",
        downloadUrl: downloadAsset?.browser_download_url || data.html_url,
        zipUrl: zipAsset?.browser_download_url || "",
        releaseUrl: data.html_url
      };
    }
    return { available: false, version: APP_VERSION };
  } catch {
    return { available: false, version: APP_VERSION, error: "Failed to check for updates" };
  }
});
function writeInstallScript(opts) {
  const installScript = import_path.default.join(import_node_os.default.tmpdir(), `local-cli-update-${Date.now()}.sh`);
  if (process.platform === "darwin") {
    import_node_fs.default.writeFileSync(installScript, `#!/bin/bash
while kill -0 ${process.pid} 2>/dev/null; do sleep 0.5; done
TRASH="${opts.currentAppPath}.old-${Date.now()}"
mv "${opts.currentAppPath}" "$TRASH" || exit 1
if mv "${opts.newAppPath}" "${opts.currentAppPath}"; then
  rm -rf "$TRASH"
else
  mv "$TRASH" "${opts.currentAppPath}"
fi
rm -f "${opts.tmpArchive}"
${opts.tmpDir ? `rm -rf "${opts.tmpDir}"` : ":"}
open "${opts.currentAppPath}"
rm -f "${installScript}"
`, { mode: 493 });
  } else {
    import_node_fs.default.writeFileSync(installScript, `#!/bin/bash
while kill -0 ${process.pid} 2>/dev/null; do sleep 0.5; done
cp "${opts.newAppPath}" "${opts.currentAppPath}"
chmod +x "${opts.currentAppPath}"
rm -f "${opts.tmpArchive}"
${opts.tmpDir ? `rm -rf "${opts.tmpDir}"` : ":"}
"${opts.currentAppPath}" &
rm -f "${installScript}"
`, { mode: 493 });
  }
  return installScript;
}
import_electron.ipcMain.handle("install-app-update", async (_event, zipUrl) => {
  const sendProgress = (stage, percent) => {
    mainWindow?.webContents.send("update-progress", { stage, percent });
  };
  try {
    sendProgress("downloading", 0);
    const tmpZip = import_path.default.join(import_node_os.default.tmpdir(), `local-cli-update-${Date.now()}.zip`);
    await downloadFile(zipUrl, tmpZip, (pct) => sendProgress("downloading", pct));
    sendProgress("extracting", 0);
    const tmpDir = import_path.default.join(import_node_os.default.tmpdir(), `local-cli-update-${Date.now()}`);
    import_node_fs.default.mkdirSync(tmpDir, { recursive: true });
    if (process.platform === "darwin") {
      await new Promise((resolve, reject) => {
        (0, import_child_process.execFile)("ditto", ["-xk", tmpZip, tmpDir], (err) => {
          if (err) reject(new Error(`Extract failed: ${err.message}`));
          else resolve();
        });
      });
    } else {
      await new Promise((resolve, reject) => {
        (0, import_child_process.execFile)("unzip", ["-o", tmpZip, "-d", tmpDir], (err) => {
          if (err) reject(new Error(`Extract failed: ${err.message}`));
          else resolve();
        });
      });
    }
    sendProgress("extracting", 100);
    let installScript;
    if (process.platform === "darwin") {
      const entries = import_node_fs.default.readdirSync(tmpDir);
      const appBundle = entries.find((e) => e.endsWith(".app"));
      if (!appBundle) throw new Error("No .app bundle found in ZIP");
      const newAppPath = import_path.default.join(tmpDir, appBundle);
      const currentAppPath = import_electron.app.isPackaged ? import_path.default.resolve(process.resourcesPath, "..", "..") : null;
      if (!currentAppPath || !currentAppPath.endsWith(".app")) {
        throw new Error("Cannot determine app path. Dev mode does not support auto-update.");
      }
      sendProgress("installing", 0);
      installScript = writeInstallScript({
        currentAppPath,
        newAppPath,
        tmpArchive: tmpZip,
        tmpDir
      });
    } else if (process.platform === "linux") {
      const entries = import_node_fs.default.readdirSync(tmpDir);
      const appImage = entries.find((e) => e.endsWith(".AppImage"));
      if (!appImage) throw new Error("No AppImage found in archive");
      const newAppPath = import_path.default.join(tmpDir, appImage);
      const currentAppPath = process.env.APPIMAGE || import_electron.app.getPath("exe");
      sendProgress("installing", 0);
      installScript = writeInstallScript({
        currentAppPath,
        newAppPath,
        tmpArchive: tmpZip,
        tmpDir
      });
    } else {
      throw new Error("Auto-update is not supported on this platform.");
    }
    sendProgress("installing", 50);
    (0, import_child_process.spawn)("bash", [installScript], {
      detached: true,
      stdio: "ignore"
    }).unref();
    sendProgress("installing", 100);
    setTimeout(() => {
      pythonProcess?.kill();
      import_electron.app.quit();
    }, 500);
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message || String(err) };
  }
});
function downloadFile(url, dest, onProgress) {
  return new Promise((resolve, reject) => {
    const doRequest = (reqUrl, redirects = 0) => {
      if (redirects > 5) return reject(new Error("Too many redirects"));
      const mod = reqUrl.startsWith("https") ? import_node_https.default : import_node_http.default;
      mod.get(reqUrl, { headers: { "User-Agent": `local-cli/${APP_VERSION}` } }, (res) => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          const loc = res.headers.location;
          if (loc) return doRequest(loc, redirects + 1);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`Download failed: HTTP ${res.statusCode}`));
        }
        const total = parseInt(res.headers["content-length"] || "0", 10);
        let received = 0;
        const file = import_node_fs.default.createWriteStream(dest);
        res.on("data", (chunk) => {
          received += chunk.length;
          file.write(chunk);
          if (total > 0) onProgress(Math.round(received / total * 100));
        });
        res.on("end", () => {
          file.end();
          resolve();
        });
        res.on("error", (e) => {
          file.close();
          reject(e);
        });
      }).on("error", reject);
    };
    doRequest(url);
  });
}
import_electron.ipcMain.handle("open-external-url", (_event, url) => {
  import_electron.shell.openExternal(url);
});
function fetchJson(url) {
  return new Promise((resolve, reject) => {
    const req = import_node_https.default.get(url, { headers: { "User-Agent": `local-cli/${APP_VERSION}` } }, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        const loc = res.headers.location;
        if (loc) return fetchJson(loc).then(resolve, reject);
      }
      let body = "";
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch {
          reject(new Error("Invalid JSON"));
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(15e3, () => {
      req.destroy();
      reject(new Error("Timeout"));
    });
  });
}
import_electron.app.whenReady().then(async () => {
  initClaudeAuth();
  startPythonServer();
  createWindow();
  try {
    const data = await fetchJson(`https://api.github.com/repos/${GITHUB_REPO}/releases/latest`);
    const latest = (data.tag_name || "").replace(/^v/, "");
    if (latest && latest !== APP_VERSION) {
      let updateAsset;
      if (process.platform === "darwin") {
        updateAsset = data.assets?.find((a) => a.name.endsWith("-mac.zip") || a.name.endsWith(".zip"));
      } else if (process.platform === "linux") {
        updateAsset = data.assets?.find((a) => a.name.endsWith(".AppImage"));
      }
      if (updateAsset?.browser_download_url && import_electron.app.isPackaged) {
        console.log(`Auto-update: ${APP_VERSION} \u2192 ${latest}`);
        const sendProgress = (stage, percent) => {
          mainWindow?.webContents.send("update-progress", { stage, percent, version: latest });
        };
        mainWindow?.webContents.send("auto-update-start", { version: latest });
        sendProgress("downloading", 0);
        const tmpFile = import_path.default.join(import_node_os.default.tmpdir(), `local-cli-update-${Date.now()}${process.platform === "darwin" ? ".zip" : ".AppImage"}`);
        await downloadFile(updateAsset.browser_download_url, tmpFile, (pct) => sendProgress("downloading", pct));
        if (process.platform === "darwin") {
          sendProgress("extracting", 0);
          const tmpDir = import_path.default.join(import_node_os.default.tmpdir(), `local-cli-update-${Date.now()}`);
          import_node_fs.default.mkdirSync(tmpDir, { recursive: true });
          await new Promise((resolve, reject) => {
            (0, import_child_process.execFile)("ditto", ["-xk", tmpFile, tmpDir], (err) => {
              err ? reject(err) : resolve();
            });
          });
          sendProgress("extracting", 100);
          const entries = import_node_fs.default.readdirSync(tmpDir);
          const appBundle = entries.find((e) => e.endsWith(".app"));
          if (appBundle) {
            const newAppPath = import_path.default.join(tmpDir, appBundle);
            const currentAppPath = import_path.default.resolve(process.resourcesPath, "..", "..");
            if (currentAppPath.endsWith(".app")) {
              sendProgress("installing", 50);
              const installScript = writeInstallScript({
                currentAppPath,
                newAppPath,
                tmpArchive: tmpFile,
                tmpDir
              });
              (0, import_child_process.spawn)("bash", [installScript], { detached: true, stdio: "ignore" }).unref();
              sendProgress("installing", 100);
              setTimeout(() => {
                pythonProcess?.kill();
                import_electron.app.quit();
              }, 500);
            }
          }
        } else if (process.platform === "linux") {
          const currentAppPath = process.env.APPIMAGE || import_electron.app.getPath("exe");
          sendProgress("installing", 50);
          const installScript = writeInstallScript({
            currentAppPath,
            newAppPath: tmpFile,
            tmpArchive: tmpFile
          });
          (0, import_child_process.spawn)("bash", [installScript], { detached: true, stdio: "ignore" }).unref();
          sendProgress("installing", 100);
          setTimeout(() => {
            pythonProcess?.kill();
            import_electron.app.quit();
          }, 500);
        }
      }
    }
  } catch (e) {
    console.log("Auto-update check failed (non-fatal):", e);
  }
});
import_electron.app.on("window-all-closed", () => {
  pythonProcess?.kill();
  import_electron.app.quit();
});
import_electron.app.on("before-quit", () => {
  pythonProcess?.kill();
});
