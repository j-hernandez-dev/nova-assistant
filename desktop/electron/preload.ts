import { contextBridge, ipcRenderer } from 'electron'
import { installStartupScreen, startupLocale } from '../shared/startup_screen'
import { readAppearance } from '../shared/desktop_appearance'

const startupPreferences = process.isMainFrame ? ipcRenderer.sendSync('get-desktop-startup-preferences') : null
const initialDesktopLocale = startupPreferences?.locale === 'en' || startupPreferences?.locale === 'es'
  ? startupPreferences.locale : startupLocale(process.argv)
const initialDesktopAppearance = readAppearance(startupPreferences)
if (process.isMainFrame) {
  const disposeStartup = installStartupScreen(document, initialDesktopLocale, initialDesktopAppearance)
  window.addEventListener('unload', disposeStartup, { once: true })
}

export type PythonMessage = {
  id?: number
  type: string
  content?: string
  name?: string
  args?: Record<string, unknown>
  output?: string
  data?: unknown
  model?: string
  tools?: string[]
  message?: string
  input_request_id?: number
  question?: string
  provider?: string
}

contextBridge.exposeInMainWorld('api', {
  initialDesktopLocale,
  initialDesktopAppearance,
  copyMessage: (messageId: string) => ipcRenderer.invoke('copy-message', messageId),
  getProjects: () => ipcRenderer.invoke('get-projects'),
  getProjectChats: () => ipcRenderer.invoke('get-project-chats'),
  clearProjectChat: (path?:string) => ipcRenderer.invoke('clear-project-chat',path),
  projectAction: (action: 'add'|'change'|'select'|'remove'|'open', selectedPath?: string) => ipcRenderer.invoke('project-action', action, selectedPath),
  onProjectsChanged: (callback: (state: unknown) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, state: unknown) => callback(state)
    ipcRenderer.on('projects-state', handler)
    return () => ipcRenderer.removeListener('projects-state', handler)
  },
  reviewPendingApproval: () => ipcRenderer.invoke('review-pending-approval'),
  reviewPendingQuestion: () => ipcRenderer.invoke('review-pending-question'),
  refreshReadiness: () => ipcRenderer.invoke('refresh-readiness'),
  retryModelDownloadInventory: () => ipcRenderer.invoke('retry-model-download-inventory'),
  getDesktopPreferences: () => ipcRenderer.invoke('get-desktop-preferences'),
  setDesktopAppearance: (value: unknown) => ipcRenderer.invoke('set-desktop-appearance', value),
  setDesktopLocale: (locale: 'es' | 'en') => ipcRenderer.invoke('set-desktop-locale', locale),
  setHistoryVisible: (visible: boolean) => ipcRenderer.invoke('set-history-visible', visible),
  memoryCommand: (name: string, args: Record<string, unknown>, commandId?: string) =>
    ipcRenderer.invoke('memory-command', name, args, commandId),
  knowledgePick: () => ipcRenderer.invoke('knowledge-pick'),
  knowledgeRefresh:(sourceId:string)=>ipcRenderer.invoke('knowledge-refresh',sourceId),
  knowledgeExport:(sourceId:string)=>ipcRenderer.invoke('knowledge-export',sourceId),
  knowledgeCommand: (name:string,args:Record<string,unknown>,commandId?:string) =>
    ipcRenderer.invoke('knowledge-command',name,args,commandId),
  applicationCommand: (kind: string, payload: Record<string, unknown>, commandId?: string) =>
    ipcRenderer.invoke('application-command', kind, payload, commandId),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  onSessionView: (callback: (view: unknown) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, view: unknown) => callback(view)
    ipcRenderer.on('session-view', handler)
    return () => ipcRenderer.removeListener('session-view', handler)
  },
  sendToPython: (data: object) => {
    ipcRenderer.send('send-to-python', data)
  },
  signalReady: () => {
    ipcRenderer.send('renderer-ready')
  },
  onPythonMessage: (callback: (msg: PythonMessage) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, msg: PythonMessage) => callback(msg)
    ipcRenderer.on('python-message', handler)
    return () => ipcRenderer.removeListener('python-message', handler)
  },
  onPythonStderr: (callback: (text: string) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, text: string) => callback(text)
    ipcRenderer.on('python-stderr', handler)
    return () => ipcRenderer.removeListener('python-stderr', handler)
  },
  onPythonExit: (callback: (code: number | null) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, code: number | null) => callback(code)
    ipcRenderer.on('python-exit', handler)
    return () => ipcRenderer.removeListener('python-exit', handler)
  },
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),
  listDir: (dirPath: string, offset = 0) => ipcRenderer.invoke('list-directory', dirPath, offset),
  readFile: (filePath: string) => ipcRenderer.invoke('read-file', filePath),
  openDirectoryDialog: () => ipcRenderer.invoke('open-directory-dialog'),
  getHomeDir: () => ipcRenderer.invoke('get-home-dir'),
  hasClaudeAccess: () => ipcRenderer.invoke('has-claude-access'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  checkAppUpdate: () => ipcRenderer.invoke('check-app-update'),
  installAppUpdate: (zipUrl: string) => ipcRenderer.invoke('install-app-update', zipUrl),
  onUpdateProgress: (callback: (progress: { stage: string; percent: number; version?: string }) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, progress: { stage: string; percent: number; version?: string }) => callback(progress)
    ipcRenderer.on('update-progress', handler)
    return () => ipcRenderer.removeListener('update-progress', handler)
  },
  onAutoUpdateStart: (callback: (info: { version: string }) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, info: { version: string }) => callback(info)
    ipcRenderer.on('auto-update-start', handler)
    return () => ipcRenderer.removeListener('auto-update-start', handler)
  },
  openExternalUrl: (url: string) => ipcRenderer.invoke('open-external-url', url),
  getClaudeAuth: () => ipcRenderer.invoke('get-claude-auth'),
  saveClaudeKey: (key: string) => ipcRenderer.invoke('save-claude-key', key),
  deleteClaudeAuth: () => ipcRenderer.invoke('delete-claude-auth'),
  startClaudeOAuth: () => ipcRenderer.invoke('start-claude-oauth'),
})
