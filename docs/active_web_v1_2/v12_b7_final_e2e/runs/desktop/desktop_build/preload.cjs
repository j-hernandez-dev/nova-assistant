"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// electron/preload.ts
var preload_exports = {};
module.exports = __toCommonJS(preload_exports);
var import_electron = require("electron");
import_electron.contextBridge.exposeInMainWorld("api", {
  configureWebV12: (configuration) => import_electron.ipcRenderer.invoke("configure-web-v12", configuration),
  selectWebV12Upload: (operationId) => import_electron.ipcRenderer.invoke("web-v12-select-upload", operationId),
  finishWebV12Takeover: (takeoverRef) => import_electron.ipcRenderer.invoke("web-v12-finish-takeover", takeoverRef),
  memoryCommand: (name, args, commandId) => import_electron.ipcRenderer.invoke("memory-command", name, args, commandId),
  knowledgePick: () => import_electron.ipcRenderer.invoke("knowledge-pick"),
  knowledgeRefresh: (sourceId) => import_electron.ipcRenderer.invoke("knowledge-refresh", sourceId),
  knowledgeExport: (sourceId) => import_electron.ipcRenderer.invoke("knowledge-export", sourceId),
  knowledgeCommand: (name, args, commandId) => import_electron.ipcRenderer.invoke("knowledge-command", name, args, commandId),
  applicationCommand: (kind, payload, commandId) => import_electron.ipcRenderer.invoke("application-command", kind, payload, commandId),
  restartBackend: () => import_electron.ipcRenderer.invoke("restart-backend"),
  onSessionView: (callback) => {
    const handler = (_event, view) => callback(view);
    import_electron.ipcRenderer.on("session-view", handler);
    return () => import_electron.ipcRenderer.removeListener("session-view", handler);
  },
  sendToPython: (data) => {
    import_electron.ipcRenderer.send("send-to-python", data);
  },
  signalReady: () => {
    import_electron.ipcRenderer.send("renderer-ready");
  },
  onPythonMessage: (callback) => {
    const handler = (_event, msg) => callback(msg);
    import_electron.ipcRenderer.on("python-message", handler);
    return () => import_electron.ipcRenderer.removeListener("python-message", handler);
  },
  onPythonStderr: (callback) => {
    const handler = (_event, text) => callback(text);
    import_electron.ipcRenderer.on("python-stderr", handler);
    return () => import_electron.ipcRenderer.removeListener("python-stderr", handler);
  },
  onPythonExit: (callback) => {
    const handler = (_event, code) => callback(code);
    import_electron.ipcRenderer.on("python-exit", handler);
    return () => import_electron.ipcRenderer.removeListener("python-exit", handler);
  },
  getPythonStatus: () => import_electron.ipcRenderer.invoke("get-python-status"),
  listDir: (dirPath) => import_electron.ipcRenderer.invoke("list-directory", dirPath),
  readFile: (filePath) => import_electron.ipcRenderer.invoke("read-file", filePath),
  openDirectoryDialog: () => import_electron.ipcRenderer.invoke("open-directory-dialog"),
  getHomeDir: () => import_electron.ipcRenderer.invoke("get-home-dir"),
  hasClaudeAccess: () => import_electron.ipcRenderer.invoke("has-claude-access"),
  getAppVersion: () => import_electron.ipcRenderer.invoke("get-app-version"),
  checkAppUpdate: () => import_electron.ipcRenderer.invoke("check-app-update"),
  installAppUpdate: (zipUrl) => import_electron.ipcRenderer.invoke("install-app-update", zipUrl),
  onUpdateProgress: (callback) => {
    const handler = (_event, progress) => callback(progress);
    import_electron.ipcRenderer.on("update-progress", handler);
    return () => import_electron.ipcRenderer.removeListener("update-progress", handler);
  },
  onAutoUpdateStart: (callback) => {
    const handler = (_event, info) => callback(info);
    import_electron.ipcRenderer.on("auto-update-start", handler);
    return () => import_electron.ipcRenderer.removeListener("auto-update-start", handler);
  },
  openExternalUrl: (url) => import_electron.ipcRenderer.invoke("open-external-url", url),
  getClaudeAuth: () => import_electron.ipcRenderer.invoke("get-claude-auth"),
  saveClaudeKey: (key) => import_electron.ipcRenderer.invoke("save-claude-key", key),
  deleteClaudeAuth: () => import_electron.ipcRenderer.invoke("delete-claude-auth"),
  startClaudeOAuth: () => import_electron.ipcRenderer.invoke("start-claude-oauth")
});
