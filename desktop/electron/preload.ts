import { contextBridge, ipcRenderer, webUtils } from 'electron'
import {nativeSourcePaths} from '../shared/source_drop'
import { installStartupScreen, startupLocale } from '../shared/startup_screen'
import { readAppearance } from '../shared/desktop_appearance'
import { readGeneral } from '../shared/desktop_general'
import {installWindowMenu} from '../shared/window_menu'

let startupWindowVisible = false
const startupWindowShown = () => { startupWindowVisible = true }
if (process.isMainFrame) ipcRenderer.on('desktop-window-shown', startupWindowShown)
const startupPreferences = process.isMainFrame ? ipcRenderer.sendSync('get-desktop-startup-preferences') : null
// Older running hosts have no visibility field; retain their existing startup behavior.
startupWindowVisible ||= startupPreferences?.windowVisible !== false
const initialDesktopLocale = startupPreferences?.locale === 'en' || startupPreferences?.locale === 'es'
  ? startupPreferences.locale : startupLocale(process.argv)
const initialDesktopAppearance = readAppearance(startupPreferences)
const initialDesktopSystemDark = startupPreferences?.systemDark !== false
const initialDesktopGeneral = readGeneral(startupPreferences)
if (process.isMainFrame) {
  // An acknowledgement after two animation frames verifies that the mounted UI
  // can run and paint after resume. Hidden-window probes are deferred by the host.
  const rendererProbe = (_event: Electron.IpcRendererEvent, nonce: unknown) => {
    if (typeof nonce !== 'string' || nonce.length > 128) return
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const phase = document.documentElement?.getAttribute('data-nova-startup')
      if (document.getElementById('root')?.childElementCount && (phase === 'mounted' || phase === 'ready')) {
        ipcRenderer.send('desktop-renderer-alive', nonce)
      }
    }))
  }
  ipcRenderer.on('desktop-renderer-probe', rendererProbe)
  // Presentation only: reserve the macOS traffic lights before the first paint.
  const applyWindowPlatform = () => document.documentElement?.setAttribute('data-nova-platform', process.platform)
  if (document.documentElement) applyWindowPlatform()
  else document.addEventListener('DOMContentLoaded', applyWindowPlatform, { once: true })
  const disposeStartup = installStartupScreen(document, initialDesktopLocale, initialDesktopAppearance, () => startupWindowVisible, initialDesktopGeneral.transitionsEnabled, initialDesktopSystemDark)
  const disposeMenu=installWindowMenu(document,position=>ipcRenderer.invoke('open-desktop-menu',position),ready=>ipcRenderer.send('desktop-menu-ready',ready))
  window.addEventListener('unload', () => {
    disposeStartup()
    disposeMenu()
    ipcRenderer.removeListener('desktop-window-shown', startupWindowShown)
    ipcRenderer.removeListener('desktop-renderer-probe', rendererProbe)
  }, { once: true })
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
  initialDesktopSystemDark,
  initialDesktopGeneral,
  initialDesktopShortcuts: startupPreferences?.shortcuts ?? null,
  copyMessage: (messageId: string) => ipcRenderer.invoke('copy-message', messageId),
  memoryTransfer:(kind:'import'|'export',includeSensitive=false)=>ipcRenderer.invoke('memory-transfer',kind,includeSensitive),
  memoryProjectAccess:(projectPath:string,enabled:boolean)=>ipcRenderer.invoke('memory-project-access',projectPath,enabled),
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
  getModelVisibility: () => ipcRenderer.invoke('get-model-visibility'),
  setModelVisibility: (value:unknown) => ipcRenderer.invoke('set-model-visibility',value),
  onModelVisibilityChanged: (callback:(value:unknown)=>void) => {
    const handler=(_event:Electron.IpcRendererEvent,value:unknown)=>callback(value)
    ipcRenderer.on('model-visibility-changed',handler)
    return ()=>ipcRenderer.removeListener('model-visibility-changed',handler)
  },
  getModelUsage: (range:string,kind:'llm'|'embedding'='llm') => ipcRenderer.invoke('get-model-usage',range,kind),
  getDesktopFonts: () => ipcRenderer.invoke('get-desktop-fonts'),
  onDesktopAppearanceChanged: (callback: (value: unknown) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, value: unknown) => callback(value)
    ipcRenderer.on('desktop-appearance-changed', handler)
    return () => ipcRenderer.removeListener('desktop-appearance-changed', handler)
  },
  setDesktopGeneral: (value: unknown) => ipcRenderer.invoke('set-desktop-general', value),
  setDesktopShortcuts: (value: unknown) => ipcRenderer.invoke('set-desktop-shortcuts', value),
  setShortcutCapture: (active: boolean) => ipcRenderer.invoke('set-shortcut-capture', active),
  setDesktopLocale: (locale: 'es' | 'en') => ipcRenderer.invoke('set-desktop-locale', locale),
  setHistoryVisible: (visible: boolean) => ipcRenderer.invoke('set-history-visible', visible),
  memoryEditSensitivity: (choice:{memoryId:string;revision:number;sensitive:boolean})=>ipcRenderer.invoke('memory-edit-sensitivity',choice),
  memoryCommand: (name: string, args: Record<string, unknown>, commandId?: string) =>
    ipcRenderer.invoke('memory-command', name, args, commandId),
  knowledgePick: () => ipcRenderer.invoke('knowledge-pick'),
  sourcesList:()=>ipcRenderer.invoke('sources-list'),
  sourcePreview:(id:string)=>ipcRenderer.invoke('source-preview',id),
  sourcesMove:(ids:string[],target:string|null)=>ipcRenderer.invoke('sources-move',ids,target),
  sourcesDelete:(ids:string[])=>ipcRenderer.invoke('sources-delete',ids),
  sourcesDownload:(ids:string[])=>ipcRenderer.invoke('sources-download',ids),
  sourcesPick:()=>ipcRenderer.invoke('sources-pick'),
  sourcesDrop:(files:File[])=>{
    try{
      return ipcRenderer.invoke('sources-drop',nativeSourcePaths(files,file=>webUtils.getPathForFile(file)))
    }catch{return Promise.resolve({completed:false,imported:0,error:{code:'SOURCE_NOT_AUTHORIZED'}})}
  },
  storageOverview: () => ipcRenderer.invoke('storage-overview'),
  storageFiles: (projectPath:string|null) => ipcRenderer.invoke('storage-files',projectPath),
  storageMove: (ids:string[],projectPath:string|null) => ipcRenderer.invoke('storage-move',ids,projectPath),
  storageDeleteFiles: (ids:string[]) => ipcRenderer.invoke('storage-delete-files',ids),
  storageDownload: (ids:string[]) => ipcRenderer.invoke('storage-download',ids),
  storageOpenFolder: (id:string) => ipcRenderer.invoke('storage-open-folder',id),
  storageDeleteFolder: (id:string) => ipcRenderer.invoke('storage-delete-folder',id),
  storageRestart: () => ipcRenderer.invoke('storage-restart'),
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
})
