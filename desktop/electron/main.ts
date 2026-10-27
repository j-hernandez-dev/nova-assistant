import { installConsolePipeGuard } from './console_pipes.cjs'
import { resolvePythonRuntime, resolveDefaultWorkspace } from './python_runtime.cjs'
import { prepareChromiumCaches } from './chromium_cache.cjs'
import { applyPendingStorageDeletions, createStorageHost } from './storage_host.cjs'
import { app, BrowserWindow, dialog, ipcMain, shell, Menu, clipboard, nativeTheme, powerMonitor } from 'electron'
import { spawn, execFile, ChildProcess } from 'child_process'
import http from 'node:http'
import https from 'node:https'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'path'
import { copyPublicMessage } from './message_copy'
import { DesktopApplicationClient } from './application_client'
import { createRendererRecovery } from './renderer_recovery'
import { memoryControl, createMemoryEditControls } from './memory_control.cjs'
import { createMemoryFileControls } from './memory_files.cjs'
import { createSourceImporter } from './source_import.cjs'
import { pickKnowledge, knowledgeControl,hostSelection,remoteKnowledge } from './knowledge_control.cjs'
import { signApproval, validFrame } from './approval_host.cjs'
import { createApprovalSurfaceController } from './approval_surface.cjs'
import { createDesktopPreferencesStore } from './desktop_preferences.cjs'
import { createModelVisibilityStore } from './desktop_model_visibility.cjs'
import { createModelUsageClient } from './model_usage.cjs'
import { usageQuery, usageRanges, type UsageRange } from '../shared/model_usage'
import { createDesktopFontService } from './desktop_fonts.cjs'
import { resolveTheme } from '../shared/desktop_theme'
import { appearancePresentation } from '../shared/desktop_appearance'
import { createDesktopModelPreferencesStore } from './desktop_model_preferences.cjs'
import { createConversationPreferencesStore } from './conversation_preferences.cjs'
import { createConfirmationSurface } from './confirmation_surface.cjs'
import { createQuestionSurface } from './question_surface.cjs'
import { createProjectChatClient } from './project_chats.cjs'
import { createProjectsHost } from './projects_host.cjs'
import { DESKTOP_UPDATES_ENABLED, disabledDesktopUpdate, editingActionForInput } from './desktop_host_policy.cjs'
import {createDesktopMenu} from './desktop_menu.cjs'
import {createDesktopView} from './desktop_view.cjs'
import { forwardingDialogOptions, pickerDialogOptions } from './desktop_host_locale.cjs'

installConsolePipeGuard()

// Keep the profile stable, including cookies/localStorage. Only disposable
// caches are regenerated, before Chromium can open them.
const desktopDataPath = path.join(app.getPath('appData'), 'nova-desktop')
fs.mkdirSync(desktopDataPath, { recursive: true })
app.setPath('userData', desktopDataPath)
app.setPath('sessionData', desktopDataPath)
if (!app.requestSingleInstanceLock()) app.exit(0)
const storageLocations = {profileDir:desktopDataPath}
const storageCleanup = applyPendingStorageDeletions(storageLocations)
for (const failure of storageCleanup.failed) console.warn(`[storage] ${failure.id}: ${failure.code}`)
const chromiumCaches = prepareChromiumCaches(desktopDataPath)
if (chromiumCaches.rotated.length) console.info(`[cache] Regenerated ${chromiumCaches.rotated.length} disposable Chromium caches.`)
if (chromiumCaches.failures.length) {
  // A locked/unwritable cache must not prevent opening the UI. Keep GPU
  // acceleration; bypass persistent HTTP/shader caches for this launch only.
  app.commandLine.appendSwitch('disable-http-cache')
  app.commandLine.appendSwitch('disable-gpu-shader-disk-cache')
  for (const failure of chromiumCaches.failures) console.warn(`[cache] ${failure.name}: ${failure.code}; using memory caches.`)
}
const desktopPreferences = createDesktopPreferencesStore(desktopDataPath, () =>
  app.isReady() ? (app.getPreferredSystemLanguages()[0] || app.getLocale()) : Intl.DateTimeFormat().resolvedOptions().locale)
const desktopFonts = createDesktopFontService()
const modelVisibility = createModelVisibilityStore(desktopDataPath)
const desktopModelPreferences = createDesktopModelPreferencesStore(desktopDataPath)
const conversationPreferences = createConversationPreferencesStore(desktopDataPath)

// Read the real version from package.json (via Electron) instead of
// hardcoding — a stale hardcode was shown in the UI for several releases.
const APP_VERSION = app.getVersion()
const GITHUB_REPO = 'j-hernandez-dev/nova-assistant'

let mainWindow: BrowserWindow | null = null
const desktopView=createDesktopView({getWindow:()=>mainWindow,getPercent:()=>desktopPreferences.get().zoomPercent,
  savePercent:percent=>desktopPreferences.setZoomPercent(percent),onChange:()=>syncDesktopAppearance()})
app.on('second-instance', () => {
  if (!mainWindow || mainWindow.isDestroyed()) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
})
let rendererRecovery: ReturnType<typeof createRendererRecovery> | null = null
let quitting = false
let systemSuspended = false
let shortcutCapture = false
let pythonProcess: ChildProcess | null = null
let lineBuffer = ''
let rendererReady = false
let requestedHistoryVisible = false
let lastReadyMessage: object | null = null
let restartWorkspace: string | null = null
let restartReady: Record<string, any> | null = null
let restoreAfterRestart = false
let restoreOnWorkspaceBootstrap = true
let approvalHostKey = ''
let approvalSurface: ReturnType<typeof createApprovalSurfaceController> | null = null
let confirmationSurface: ReturnType<typeof createConfirmationSurface> | null = null
let questionSurface: ReturnType<typeof createQuestionSurface> | null = null
let chatMutation = false
let projectsHost: ReturnType<typeof createProjectsHost> | null = null
let bootstrapReadyMessage: Record<string,any> | null = null
let bootstrapProjectRequest: {path:string;acknowledged:boolean;resolve:(value:{success:boolean;error?:{code:string}})=>void;timer:ReturnType<typeof setTimeout>} | null = null
function sameWorkspacePath(left:string,right:string) {
  const normalize = (value:string) => process.platform === 'win32' ? path.resolve(value).toLowerCase() : path.resolve(value)
  return normalize(left) === normalize(right)
}
const applicationClient = new DesktopApplicationClient(sendToPython, view => {
  confirmationSurface?.sync()
  questionSurface?.sync()
  approvalSurface?.sync()
  projectsHost?.sync()
  if (bootstrapProjectRequest?.acknowledged && view.status.ready && view.workspace &&
      sameWorkspacePath(view.workspace,bootstrapProjectRequest.path)) {
    const pending = bootstrapProjectRequest; bootstrapProjectRequest = null
    clearTimeout(pending.timer); pending.resolve({success:true})
  }
  if (rendererReady && mainWindow && !mainWindow.webContents.isDestroyed()) {
    mainWindow.webContents.send('session-view', view)
  }
}, command => signApproval(approvalHostKey, command))
approvalSurface = createApprovalSurfaceController({ BrowserWindow, ipcMain, client: applicationClient,
  getParent: () => mainWindow, getLocale: () => desktopPreferences.get().locale,
  getAppearance: () => desktopPreferences.get(), getSystemDark: () => nativeTheme.shouldUseDarkColors,
  getPresentation: () => appearancePresentation(desktopPreferences.get(), nativeTheme.shouldUseDarkColors),
  preloadPath: path.join(__dirname, 'approval_preload.js') })
const modelUsageClient = createModelUsageClient({send:sendToPython})
const projectChatClient = createProjectChatClient({send:sendToPython,getView:()=>applicationClient.view})
confirmationSurface = createConfirmationSurface({BrowserWindow,ipcMain,getParent:()=>mainWindow,
  getLocale:()=>desktopPreferences.get().locale,getAppearance:()=>desktopPreferences.get(),getSystemDark:()=>nativeTheme.shouldUseDarkColors,
  getPresentation:()=>appearancePresentation(desktopPreferences.get(),nativeTheme.shouldUseDarkColors),
  preloadPath:path.join(__dirname,'confirmation_preload.js')})
questionSurface = createQuestionSurface({BrowserWindow, ipcMain, client: applicationClient, getParent: () => mainWindow,
  getLocale: () => desktopPreferences.get().locale, preloadPath: path.join(__dirname, 'question_preload.js'),
  getAppearance: () => desktopPreferences.get(), getSystemDark: () => nativeTheme.shouldUseDarkColors,
  getPresentation: () => appearancePresentation(desktopPreferences.get(), nativeTheme.shouldUseDarkColors),
  canOpen: () => !confirmationSurface?.isPending() && !chatMutation && !applicationClient.view.approvals.length })
applicationClient.setConversationPreferences(conversationPreferences)
applicationClient.setConfirmedModelObserver(runtime => {
  const result = desktopModelPreferences.saveConfirmed(runtime)
  applicationClient.setModelPreferenceError(result.success ? null : 'MODEL_PREFERENCE_SAVE_FAILED')
})
// Recheck only host readiness. This monitor never retries a user operation.
const readinessMonitor = setInterval(() => { if (!systemSuspended) applicationClient.refreshReadiness() }, 15_000)
readinessMonitor.unref()

function syncHistoryVisibility() {
  applicationClient.setHistoryVisible(requestedHistoryVisible && rendererReady && !!mainWindow
    && !mainWindow.isDestroyed() && mainWindow.isVisible() && !mainWindow.isMinimized())
}

function clearHistoryVisibility() {
  requestedHistoryVisible = false
  applicationClient.setHistoryVisible(false)
}

function findProjectRoot(): string {
  // In dev mode: __dirname is desktop/dist-electron, so ../../ is project root.
  // In packaged app: local_cli/ and pyproject.toml are in Resources/ via extraResources.
  if (app.isPackaged && process.resourcesPath) {
    return path.resolve(process.resourcesPath)
  }
  return path.resolve(__dirname, '..', '..')
}

function defaultWorkspace() {
  return resolveDefaultWorkspace(findProjectRoot(), app.getPath('documents'), app.isPackaged)
}

function startPythonServer() {
  const projectRoot = findProjectRoot()
  let runtime: ReturnType<typeof resolvePythonRuntime>
  try { runtime = resolvePythonRuntime(projectRoot, {packaged: app.isPackaged && process.platform === 'win32'}) }
  catch { console.error('BUNDLED_BACKEND_NOT_FOUND'); applicationClient.disconnected(); return }
  const pythonCmd = runtime.executable
  const backendArgs = runtime.args || ['-m', 'local_cli', '--server']
  if (!restartWorkspace) restartWorkspace = projectsHost?.preferredPath() || defaultWorkspace()

  console.log(`Starting backend: ${pythonCmd} ${backendArgs.join(' ')}`)
  const backendCwd = app.isPackaged && process.platform === 'win32' ? restartWorkspace : projectRoot
  console.log(`Working directory: ${backendCwd}`)

  const env: Record<string, string> = desktopModelPreferences.childEnvironment({
    ...runtime.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8',
  })
  approvalHostKey = crypto.randomBytes(32).toString('hex')
  env.NOVA_APPROVAL_HOST_KEY = approvalHostKey

  lineBuffer = ''
  lastReadyMessage = null
  bootstrapReadyMessage = null
  const child = spawn(pythonCmd, backendArgs, {
    cwd: backendCwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    env,
    windowsHide: true,
  })
  pythonProcess = child
  child.stdout?.setEncoding('utf8')
  child.stderr?.setEncoding('utf8')

  child.stdout?.on('data', (data: string) => {
    if (pythonProcess !== child) return
    lineBuffer += data
    const lines = lineBuffer.split('\n')
    // Keep the last incomplete line in the buffer.
    lineBuffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const msg = JSON.parse(line)
        // Remember the ready message so we can re-send it on HMR re-mounts.
        if (msg.type === 'ready') {
          bootstrapReadyMessage = msg
          if (restartWorkspace) {
            restartReady = msg
            sendToPython({ id: 'desktop-restart-cwd', type: 'set_cwd', path: restartWorkspace, projectChat: true })
            continue
          }
          lastReadyMessage = msg
        }
        if (msg.id === 'desktop-restart-cwd') {
          restartWorkspace = null
          if (msg.type === 'cwd_changed' && restartReady) {
            if (bootstrapProjectRequest) bootstrapProjectRequest.acknowledged = true
            restartReady = {...restartReady,resumable:msg.resumable || null}
            lastReadyMessage = restartReady
            applicationClient.receive(restartReady)
            restoreAfterRestart = restoreOnWorkspaceBootstrap && !!msg.resumable
            restoreOnWorkspaceBootstrap = false
          } else {
            // Never expose chat readiness at the source root after failed bootstrap.
            projectsHost?.setError('PROJECT_BOOTSTRAP_FAILED')
            if (bootstrapProjectRequest) {
              const pending = bootstrapProjectRequest; bootstrapProjectRequest = null
              clearTimeout(pending.timer); pending.resolve({success:false,error:{code:msg.code || 'PROJECT_BOOTSTRAP_FAILED'}})
            }
            applicationClient.receive(msg)
            restartReady = null
            continue
          }
          restartReady = null
        }
        if (modelUsageClient.receive(msg)) continue
        if (projectChatClient.receive(msg)) {
          if (msg.type === 'clear_project_chat' && msg.success) applicationClient.refresh()
          continue
        }
        applicationClient.receive(msg)
        if (restoreAfterRestart && applicationClient.view.status.ready) {
          restoreAfterRestart = false
          // Restore the saved transcript, never effects or pending requests.
          void applicationClient.command('ExecuteCommand', { name: 'resume' })
        }
        if (rendererReady && mainWindow) {
          mainWindow.webContents.send('python-message', msg)
        }
      } catch {
        console.error('Invalid JSON from Python')
      }
    }
  })

  child.stderr?.on('data', (text: string) => {
    if (pythonProcess !== child) return
    console.error('[python stderr]', text)
    mainWindow?.webContents.send('python-stderr', text)
  })

  child.on('error', () => {
    if (pythonProcess !== child) return
    pythonProcess = null
    projectChatClient.disconnected(); modelUsageClient.disconnected()
    applicationClient.disconnected()
  })
  child.stdin?.on('error', () => {
    if (pythonProcess === child) applicationClient.disconnected()
  })
  child.on('exit', (code, signal) => {
    if (pythonProcess !== child) return
    if (!quitting) console.log(`Python process exited ${signal ? `after ${signal}` : `with code ${code}`}`)
    mainWindow?.webContents.send('python-exit', code)
    pythonProcess = null
    projectChatClient.disconnected(); modelUsageClient.disconnected()
    applicationClient.disconnected()
  })
}

function sendToPython(data: object) {
  if (pythonProcess?.stdin?.writable) {
    try {
      pythonProcess.stdin.write(JSON.stringify(data) + '\n')
      return true
    } catch { return false }
  }
  return false
}

/** Explicit human folder selection can recover an inaccessible initial workspace. */
function bootstrapProject(selectedPath:string):Promise<{success:boolean;error?:{code:string}}> {
  if (bootstrapProjectRequest || applicationClient.workspaceBusy()) return Promise.resolve({success:false,error:{code:'PROJECT_BUSY'}})
  return new Promise(resolve => {
    const timer = setTimeout(() => {
      if (!bootstrapProjectRequest) return
      bootstrapProjectRequest = null
      projectsHost?.setError('PROJECT_CHANGE_UNKNOWN')
      resolve({success:false,error:{code:'PROJECT_CHANGE_UNKNOWN'}})
    }, 20_000)
    timer.unref()
    bootstrapProjectRequest = {path:selectedPath,acknowledged:false,resolve,timer}
    restoreOnWorkspaceBootstrap = true
    restartWorkspace = selectedPath
    if (!pythonProcess) startPythonServer()
    else if (bootstrapReadyMessage) {
      restartReady = bootstrapReadyMessage
      sendToPython({id:'desktop-restart-cwd',type:'set_cwd',path:selectedPath,projectChat:true})
    }
    // If startup is still pending, its ready frame uses restartWorkspace above.
  })
}

// Bounded diagnostics contain lifecycle events only, never conversation content.
function reportRendererRecovery(event: string) {
  console.warn('[Nova window]', event)
  try {
    const file = path.join(desktopDataPath, 'desktop-recovery.log')
    if (fs.existsSync(file) && fs.statSync(file).size > 65_536) {
      fs.writeFileSync(file, fs.readFileSync(file).subarray(-32_768))
    }
    fs.appendFileSync(file, `${new Date().toISOString()} ${event}\n`)
  } catch { /* Diagnostics must not prevent recovery. */ }
}

function createWindow() {
  desktopMenu.setReady(false)
  const theme = resolveTheme(desktopPreferences.get(), nativeTheme.shouldUseDarkColors)
  mainWindow = new BrowserWindow({
    title: 'Nova',
    icon: path.join(__dirname, process.env.VITE_DEV_SERVER_URL ? '../public' : '../dist',
      process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    backgroundColor: theme.colors['--bg'],
    show: false,
    width: 1000,
    height: 700,
    minWidth: 600,
    minHeight: 400,
    ...(process.platform === 'darwin'
      ? { titleBarStyle: 'hiddenInset' as const, trafficLightPosition: { x: 16, y: 16 } }
      : { titleBarStyle: 'hidden' as const,
          titleBarOverlay: { color: theme.colors['--nova-titlebar-bg'], symbolColor: theme.colors['--nova-titlebar-text'], height: Math.round(44*desktopView.getPercent()/100) } }),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      zoomFactor:desktopView.getPercent()/100,
      additionalArguments: [`--nova-desktop-locale=${desktopPreferences.get().locale}`],
    },
  })
  const window = mainWindow
  desktopView.attach(window)
  window.on('show', () => {
    if (!window.webContents.isDestroyed() && !window.webContents.isCrashed()) window.webContents.send('desktop-window-shown')
  })
  window.once('ready-to-show', () => { if (!window.isDestroyed()) window.show() })
  mainWindow.setMenu(null)
  mainWindow.webContents.on('page-title-updated', event => {
    event.preventDefault()
    mainWindow?.setTitle('Nova')
  })
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (shortcutCapture) return
    const action = editingActionForInput(input, process.platform)
    if (!action || !mainWindow) return
    event.preventDefault()
    mainWindow.webContents[action]()
  })

  let replacingRenderer = false, closing = false
  const loadRenderer = () => {
    if (quitting || closing || window.isDestroyed() || window.webContents.isDestroyed()) return
    const loading = process.env.VITE_DEV_SERVER_URL
      ? window.loadURL(process.env.VITE_DEV_SERVER_URL)
      : window.loadFile(path.join(__dirname, '../dist/index.html'))
    void loading.catch(() => reportRendererRecovery('renderer-load-failed'))
  }
  const recovery = createRendererRecovery({
    available: () => !quitting && !closing && !window.isDestroyed() && !window.webContents.isDestroyed(),
    visible: () => window.isVisible() && !window.isMinimized(),
    repaint: () => window.webContents.invalidate(),
    probe: nonce => window.webContents.send('desktop-renderer-probe', nonce),
    reload: replaceProcess => {
      // Wait for the old process to exit before navigating. A reload issued while
      // its renderer is still blocked can be lost on Windows/Electron 33.
      if (replaceProcess && !window.webContents.isCrashed()) {
        replacingRenderer = true
        window.webContents.forcefullyCrashRenderer()
        return
      }
      loadRenderer()
    },
    refresh: () => {
      applicationClient.refresh()
      applicationClient.refreshReadiness()
      syncDesktopAppearance()
    },
    offerRetry: async () => {
      const en = desktopPreferences.get().locale === 'en'
      const result = await dialog.showMessageBox(window, {
        type: 'warning', title: 'Nova',
        message: en ? 'The Nova interface could not be restored.' : 'No se pudo recuperar la interfaz de Nova.',
        detail: en ? 'Reload the window to try again. The conversation process will keep running.'
          : 'Recarga la ventana para volver a intentarlo. El proceso de la conversación seguirá funcionando.',
        buttons: en ? ['Reload window', 'Cancel'] : ['Recargar ventana', 'Cancelar'],
        defaultId: 0, cancelId: 1, noLink: true,
      })
      return result.response === 0
    },
    report: reportRendererRecovery,
  })
  rendererRecovery = recovery
  const onSuspend = () => { systemSuspended = true; recovery.suspend() }
  const onResume = () => { systemSuspended = false; recovery.resume() }
  const onChildGone = (_event: Electron.Event, details: Electron.Details) => {
    if (details.type !== 'GPU' || details.reason === 'clean-exit') return
    reportRendererRecovery(`gpu-process-gone:${details.reason}`)
    recovery.suspect()
  }
  powerMonitor.on('suspend', onSuspend)
  powerMonitor.on('resume', onResume)
  app.on('child-process-gone', onChildGone)

  window.on('close', () => { closing = true; recovery.dispose() })
  mainWindow.on('closed', () => {
    recovery.dispose()
    powerMonitor.removeListener('suspend', onSuspend)
    powerMonitor.removeListener('resume', onResume)
    app.removeListener('child-process-gone', onChildGone)
    if (rendererRecovery === recovery) rendererRecovery = null
    shortcutCapture = false
    approvalSurface?.invalidate()
    questionSurface?.invalidate()
    rendererReady = false
    clearHistoryVisibility()
    mainWindow = null
  })
  mainWindow.on('blur', () => { shortcutCapture = false })
  mainWindow.on('hide', () => { shortcutCapture = false; applicationClient.setHistoryVisible(false); recovery.hidden() })
  mainWindow.on('minimize', () => { applicationClient.setHistoryVisible(false); recovery.hidden() })
  mainWindow.on('show', () => { syncHistoryVisibility(); questionSurface?.sync(); recovery.visible() })
  mainWindow.on('restore', () => { syncHistoryVisibility(); questionSurface?.sync(); recovery.visible() })
  mainWindow.on('focus', () => { if (!systemSuspended) applicationClient.refreshReadiness(); questionSurface?.sync(); recovery.visible() })
  mainWindow.on('unresponsive', () => { reportRendererRecovery('renderer-unresponsive'); recovery.suspect() })
  mainWindow.webContents.on('did-start-loading', () => { desktopMenu.setReady(false); shortcutCapture = false; rendererReady = false; clearHistoryVisibility(); recovery.loading() })
  mainWindow.webContents.on('destroyed', clearHistoryVisibility)
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    rendererReady = false; clearHistoryVisibility()
    reportRendererRecovery(`render-process-gone:${details.reason}`)
    if (replacingRenderer) {
      replacingRenderer = false
      setImmediate(loadRenderer)
      return
    }
    recovery.gone()
  })
  // Attach lifecycle handlers before the first navigation, including in dev mode.
  loadRenderer()
  approvalSurface?.sync()
  questionSurface?.sync()
}

function syncDesktopAppearance() {
  const preferences = desktopPreferences.get(), systemDark = nativeTheme.shouldUseDarkColors
  if (mainWindow && !mainWindow.isDestroyed()) {
    const theme = resolveTheme(preferences, systemDark)
    mainWindow.setBackgroundColor(theme.colors['--bg'])
    if (process.platform !== 'darwin') mainWindow.setTitleBarOverlay({
      color: theme.colors['--nova-titlebar-bg'], symbolColor: theme.colors['--nova-titlebar-text'], height: Math.round(44*desktopView.getPercent()/100),
    })
    if (rendererReady && !mainWindow.webContents.isDestroyed() && !mainWindow.webContents.isCrashed()) {
      mainWindow.webContents.send('desktop-appearance-changed', { preferences, systemDark })
    }
  }
  approvalSurface?.updateAppearance(preferences, systemDark)
  confirmationSurface?.updateAppearance(preferences, systemDark)
  questionSurface?.updateAppearance(preferences, systemDark)
}
nativeTheme.on('updated', syncDesktopAppearance)

// IPC handlers.
function validApplicationSender(event: Electron.IpcMainEvent | Electron.IpcMainInvokeEvent) {
  return !!mainWindow && event.sender === mainWindow.webContents &&
    event.senderFrame === mainWindow.webContents.mainFrame
}

function canAddProjectFromMenu(){
  return !quitting&&!systemSuspended&&!!projectsHost&&!projectsHost.isChanging()&&!applicationClient.workspaceBusy()&&
    !applicationClient.modelDownloadBusy()&&!confirmationSurface?.isPending()&&!chatMutation&&!memoryFiles.isBusy()&&!memoryEditor.isBusy()&&!storageHost.isBusy()&&!sourceImportBusy
}
const desktopMenu=createDesktopMenu({Menu,getWindow:()=>mainWindow,getLocale:()=>desktopPreferences.get().locale,quit:()=>app.quit(),view:desktopView,
  canAddProject:canAddProjectFromMenu,newProject:async()=>{
    try{const result=await performProjectAction('add');if(!result.success&&result.error)projectsHost?.setError(result.error.code)}
    catch{projectsHost?.setError('PROJECT_ACTION_FAILED')}
  }})
ipcMain.on('desktop-menu-ready',(event,ready:unknown)=>{if(validApplicationSender(event))desktopMenu.setReady(ready===true)})
ipcMain.handle('open-desktop-menu',(event,position:unknown)=>validApplicationSender(event)?desktopMenu.open(position):{opened:false})

// A memory-only snapshot lets preload apply presentation before the first paint, including reloads.
ipcMain.on('get-desktop-startup-preferences', event => {
  event.returnValue = validApplicationSender(event)
    ? { ...desktopPreferences.get(), systemDark: nativeTheme.shouldUseDarkColors, windowVisible: mainWindow?.isVisible() === true } : null
})
ipcMain.handle('set-desktop-appearance', (event, value: unknown) => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  const result = desktopPreferences.setAppearance(value)
  if (result.success) syncDesktopAppearance()
  return result
})
ipcMain.handle('get-model-visibility', event => validApplicationSender(event)
  ? modelVisibility.get() : {hiddenModels:[]})
ipcMain.handle('set-model-visibility', (event, value:unknown) => {
  if (!validApplicationSender(event)) return {success:false,error:{code:'INVALID_DESKTOP_SENDER'}}
  const result=modelVisibility.set(value)
  if(result.success) mainWindow?.webContents.send('model-visibility-changed',result.preferences)
  return result
})
ipcMain.handle('get-model-usage', (event, range:unknown, kind:unknown='llm') => {
  if(!validApplicationSender(event)||!usageRanges.includes(range as UsageRange)||!['llm','embedding'].includes(kind as string)) return {success:false,error:{code:'INVALID_USAGE_RANGE'}}
  if(!applicationClient.view.status.ready) return {success:false,error:{code:'USAGE_UNAVAILABLE'}}
  return modelUsageClient.request(usageQuery(range as UsageRange),kind as "llm"|"embedding")
})

ipcMain.handle('get-desktop-fonts', event => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop fonts are unavailable.' } }
  return desktopFonts.get()
})
ipcMain.handle('get-desktop-preferences', event => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  return desktopPreferences.get()
})
ipcMain.handle('set-desktop-shortcuts', (event, value: unknown) => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  return desktopPreferences.setShortcuts(value)
})
ipcMain.handle('set-desktop-general', (event, value: unknown) => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  const result = desktopPreferences.setGeneral(value)
  if (result.success) { approvalSurface?.updateLocale(); confirmationSurface?.updateLocale(); questionSurface?.updateLocale() }
  return result
})
ipcMain.handle('set-shortcut-capture', (event, active: unknown) => {
  if (!validApplicationSender(event) || typeof active !== 'boolean') return { success: false }
  shortcutCapture = active
  return { success: true }
})
ipcMain.handle('set-desktop-locale', (event, locale: unknown) => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  const result = desktopPreferences.setLocale(locale)
  if (result.success) { approvalSurface?.updateLocale(); confirmationSurface?.updateLocale(); questionSurface?.updateLocale() }
  return result
})
ipcMain.handle('set-history-visible', (event, visible: unknown) => {
  if (!validApplicationSender(event) || typeof visible !== 'boolean') return { success: false }
  requestedHistoryVisible = visible
  syncHistoryVisibility()
  return { success: true }
})

ipcMain.on('send-to-python', (event, data) => {
  if(((memoryFiles.isBusy()||memoryEditor.isBusy())||storageHost.isBusy())&&['application_command','command','chat','set_cwd','pull_model','delete_model'].includes(data?.type))return
  if (!validApplicationSender(event) || !validFrame(data) || data.type === 'set_cwd' || ['project_chats','clear_project_chat','command','chat','storage_command'].includes(data.type) || data.type === 'memory_command' || data.type === 'knowledge_command' || data.type === 'confirm_response' ||
      (projectsHost?.isChanging() && ['chat','command','application_command'].includes(data.type)) ||
      (data.type === 'application_command' && ['ResolveApproval','ResolveUserInput','ExecuteCommand'].includes(data.command?.kind)) ||
      ((confirmationSurface?.isPending() || chatMutation) && data.type === 'application_command')) return
  if (applicationClient.modelDownloadBusy() || data.type === 'pull_model' &&
      (projectsHost?.isChanging() || confirmationSurface?.isPending() || chatMutation || !applicationClient.beginModelDownload(data))) {
    mainWindow?.webContents.send('python-message', { id: data.id, type: 'error', code: 'MODEL_DOWNLOAD_BUSY', message: 'Wait for the model download and inventory refresh.' })
    return
  }
  applicationClient.trackModelRequest(data)
  sendToPython(data)
})
const memoryFiles=createMemoryFileControls({
  client:applicationClient,projects:()=>projectsHost?.state(),getLocale:()=>desktopPreferences.get().locale,
  isBlocked:()=>!!projectsHost?.isChanging()||chatMutation||memoryEditor.isBusy(),
  confirm:(request:any)=>confirmationSurface?.request(request)||Promise.resolve({confirmed:false,canceled:true}),
  pickOpen:(options:any)=>dialog.showOpenDialog(mainWindow!,options),
  pickSave:(options:any)=>dialog.showSaveDialog(mainWindow!,options),
  isProtected:(filename:string)=>{
    const normalized=(p:string)=>process.platform==='win32'?path.resolve(p).toLowerCase():path.resolve(p)
    const candidate=normalized(path.join(fs.realpathSync(path.dirname(filename)),path.basename(filename)))
    return [app.getPath('userData'),process.env.LOCAL_CLI_STATE_DIR||path.join(os.homedir(),'.local','state','nova')]
      .some(root=>candidate===normalized(root)||candidate.startsWith(normalized(root)+path.sep))
  },
})
async function restartForStorage() {
  if (quitting) return
  const child=pythonProcess
  if(child && child.exitCode===null && child.signalCode===null) {
    await new Promise<void>(resolve=>{
      const timer=setTimeout(resolve,5_000)
      child.once('exit',()=>{clearTimeout(timer);resolve()})
      child.kill()
    })
  }
  if(process.env.VITE_DEV_SERVER_URL) {
    app.once('will-quit',()=>app.exit(75))
  } else app.relaunch()
  app.quit()
}
let sourceImportBusy=false
const storageHost=createStorageHost({...storageLocations,client:applicationClient,
  externalBusy:()=>sourceImportBusy,
  getProjects:()=>projectsHost?.state()||{folders:[]},
  confirm:request=>confirmationSurface?.request(request)||Promise.resolve({confirmed:false,canceled:true}),
  openPath:target=>shell.openPath(target),restart:restartForStorage,
  pickSave:({name})=>dialog.showSaveDialog(mainWindow!,{title:desktopPreferences.get().locale==='es'?'Descargar archivo':'Download file',defaultPath:path.join(app.getPath('downloads'),name),buttonLabel:desktopPreferences.get().locale==='es'?'Guardar':'Save',properties:['showOverwriteConfirmation','createDirectory']}),
  isBlocked:()=>quitting||systemSuspended||(memoryFiles.isBusy()||memoryEditor.isBusy())||chatMutation||!!projectsHost?.isChanging(),
})
const storageSender=(event:Electron.IpcMainInvokeEvent)=>validApplicationSender(event)&&!confirmationSurface?.isPending()&&!chatMutation&&!(memoryFiles.isBusy()||memoryEditor.isBusy())
const invalidStorage=()=>({success:false,error:{code:'STORAGE_UNTRUSTED_INPUT'}})
ipcMain.handle('storage-overview',event=>storageSender(event)?storageHost.overview({refresh:true}):invalidStorage())
ipcMain.handle('storage-files',(event,projectPath:unknown)=>storageSender(event)&&(projectPath===null||typeof projectPath==='string')?storageHost.files(projectPath):invalidStorage())
ipcMain.handle('storage-move',(event,ids:unknown,projectPath:unknown)=>storageSender(event)&&Array.isArray(ids)&&ids.every(id=>typeof id==='string')&&(projectPath===null||typeof projectPath==='string')?storageHost.move(ids,projectPath):invalidStorage())
ipcMain.handle('storage-delete-files',(event,ids:unknown)=>storageSender(event)&&Array.isArray(ids)&&ids.every(id=>typeof id==='string')?storageHost.deleteFiles(ids):invalidStorage())
ipcMain.handle('storage-download',(event,ids:unknown)=>storageSender(event)&&Array.isArray(ids)&&ids.every(id=>typeof id==='string')?storageHost.download(ids):invalidStorage())
ipcMain.handle('storage-open-folder',(event,id:unknown)=>storageSender(event)&&typeof id==='string'?storageHost.openFolder(id):invalidStorage())
ipcMain.handle('storage-delete-folder',(event,id:unknown)=>storageSender(event)&&typeof id==='string'?storageHost.deleteFolder(id):invalidStorage())
ipcMain.handle('storage-restart',event=>storageSender(event)?storageHost.restart():invalidStorage())
ipcMain.handle('sources-list',event=>storageSender(event)?storageHost.sources():invalidStorage())
ipcMain.handle('source-preview',(event,id:unknown)=>storageSender(event)&&typeof id==='string'?storageHost.sourcePreview(id):invalidStorage())
ipcMain.handle('sources-move',(event,ids:unknown,target:unknown)=>storageSender(event)&&Array.isArray(ids)&&ids.every(id=>typeof id==='string')&&(target===null||typeof target==='string')?storageHost.move(ids,target,true):invalidStorage())
ipcMain.handle('sources-delete',(event,ids:unknown)=>storageSender(event)&&Array.isArray(ids)&&ids.every(id=>typeof id==='string')?storageHost.deleteFiles(ids,true):invalidStorage())
ipcMain.handle('sources-download',(event,ids:unknown)=>storageSender(event)&&Array.isArray(ids)&&ids.every(id=>typeof id==='string')?storageHost.download(ids,true):invalidStorage())

ipcMain.handle('memory-transfer',(event,kind:unknown,includeSensitive:unknown)=>{
  if(!validApplicationSender(event)||!mainWindow||confirmationSurface?.isPending()||storageHost.isBusy()||memoryEditor.isBusy())return {schemaVersion:1,commandId:'',completed:false,error:{code:'MEMORY_UNTRUSTED_INPUT',message:'Memory action is unavailable.'}}
  return memoryFiles.transfer(kind,includeSensitive)
})
ipcMain.handle('memory-project-access',(event,projectPath:unknown,enabled:unknown)=>{
  if(!validApplicationSender(event)||!mainWindow||confirmationSurface?.isPending()||storageHost.isBusy()||memoryEditor.isBusy())return {schemaVersion:1,commandId:'',completed:false,error:{code:'MEMORY_UNTRUSTED_INPUT',message:'Memory action is unavailable.'}}
  return memoryFiles.projectAccess(projectPath,enabled)
})
const memoryEditor=createMemoryEditControls(applicationClient,async request=>{
  const result=await confirmationSurface?.request({kind:request.kind,fileCount:request.fileCount,path:request.workspace||'',validate:request.validate})
  return {confirmed:result?.confirmed===true}
})
ipcMain.handle('memory-edit-sensitivity',(event,choice:unknown)=>{
  if(!validApplicationSender(event)||(memoryFiles.isBusy()||memoryEditor.isBusy())||storageHost.isBusy()||confirmationSurface?.isPending()||projectsHost?.isChanging()||chatMutation||applicationClient.modelDownloadBusy())
    return {schemaVersion:1,commandId:'',completed:false,error:{code:'MEMORY_HOST_ACTION_REQUIRED'}}
  return memoryEditor.confirm(choice)
})
ipcMain.handle('memory-command', async (event, name: string, args: Record<string, unknown>, commandId?: string) => {
  if((memoryFiles.isBusy()||memoryEditor.isBusy())||storageHost.isBusy()||confirmationSurface?.isPending()||projectsHost?.isChanging()||chatMutation||['memory_import','memory_export_all','memory_project_access'].includes(name))
    return {schemaVersion:1,commandId:commandId||'',completed:false,error:{code:'MEMORY_HOST_ACTION_REQUIRED',message:'Use the host Memory controls.'}}
  if (!validApplicationSender(event) || typeof name !== 'string' || !validFrame(args)) {
    return { schemaVersion: 1, commandId: commandId || '', completed: false,
      error: { code: 'MEMORY_UNTRUSTED_INPUT', message: 'Invalid memory action.' } }
  }
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:commandId || '',completed:false,error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  if(name==='memory_delete')return memoryEditor.remove(args,commandId)
  if(name==='memory_edit')return memoryEditor.edit(args,commandId)
  return memoryControl(applicationClient, name, args, commandId, async request => {
    const decision=await confirmationSurface?.request({kind:request.write?'memory-write-sensitive':'memory-reveal-sensitive',
      path:request.workspace||'',validate:request.validate})
    return {response:decision?.confirmed?1:0}
  })
})

const sourceImporter=createSourceImporter(applicationClient,{
  pick:()=>dialog.showOpenDialog(mainWindow!,{...pickerDialogOptions(desktopPreferences.get().locale,'document'),properties:['openFile','multiSelections']}),
  isBlocked:()=>!mainWindow||quitting||systemSuspended||storageHost.isBusy()||!!confirmationSurface?.isPending()||memoryFiles.isBusy()||memoryEditor.isBusy()||!!projectsHost?.isChanging()||chatMutation,
  onBusy:value=>{sourceImportBusy=value},
})
ipcMain.handle('sources-pick',event=>validApplicationSender(event)?sourceImporter.pick():Promise.resolve({completed:false,imported:0,error:{code:'SOURCE_NOT_AUTHORIZED'}}))
ipcMain.handle('sources-drop',(event,paths:unknown)=>validApplicationSender(event)?sourceImporter.drop(paths):Promise.resolve({completed:false,imported:0,error:{code:'SOURCE_NOT_AUTHORIZED'}}))

ipcMain.handle('knowledge-pick', async event => {
  if(storageHost.isBusy()||confirmationSurface?.isPending())return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'PROJECT_BUSY'}}
  if (!validApplicationSender(event) || !mainWindow) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},
    error:{code:'SOURCE_NOT_AUTHORIZED',message:'Main-frame host picker required.'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  return pickKnowledge(applicationClient, () => dialog.showOpenDialog(mainWindow!,pickerDialogOptions(desktopPreferences.get().locale,'document')))
})
ipcMain.handle('knowledge-command', async (event,name:string,args:Record<string,unknown>,commandId?:string) => {
  if(storageHost.isBusy()||confirmationSurface?.isPending())return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'PROJECT_BUSY'}}
  if (!validApplicationSender(event) || !validFrame(args)) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},
    error:{code:'SOURCE_NOT_AUTHORIZED',message:'Invalid source control.'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  if(name==='source_remote')return remoteKnowledge(applicationClient,args,()=>dialog.showMessageBox(mainWindow!,
    forwardingDialogOptions(desktopPreferences.get().locale)),commandId)
  return knowledgeControl(applicationClient,name,args,commandId)
})
ipcMain.handle('knowledge-refresh',async(event,sourceId:string)=>{
  if(storageHost.isBusy()||confirmationSurface?.isPending())return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'PROJECT_BUSY'}}
  if(!validApplicationSender(event)||!mainWindow||typeof sourceId!=='string')return {accepted:false,error:{code:'SOURCE_NOT_AUTHORIZED'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  return hostSelection(applicationClient,'source_refresh',sourceId,()=>dialog.showOpenDialog(mainWindow!,pickerDialogOptions(desktopPreferences.get().locale,'refresh')))
})
ipcMain.handle('knowledge-export',async(event,sourceId:string)=>{
  if(storageHost.isBusy()||confirmationSurface?.isPending())return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'PROJECT_BUSY'}}
  if(!validApplicationSender(event)||!mainWindow||typeof sourceId!=='string')return {accepted:false,error:{code:'SOURCE_NOT_AUTHORIZED'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  return hostSelection(applicationClient,'source_export',sourceId,()=>dialog.showSaveDialog(mainWindow!,pickerDialogOptions(desktopPreferences.get().locale,'export')))
})

ipcMain.handle('get-python-status', () => {
  return { running: pythonProcess !== null && !pythonProcess.killed }
})

ipcMain.handle('application-command', async (event, kind: string, payload: Record<string, unknown>, commandId?: string) => {
  if (!validApplicationSender(event) || typeof kind !== 'string' || !validFrame(payload)) {
    return { schemaVersion: 1, commandId: commandId || '', accepted: false, createdIds: {},
      error: { code: 'INVALID_APPLICATION_COMMAND', message: 'Invalid application command.' } }
  }
  if (kind === 'ExecuteCommand' && ['clear','clear_history'].includes(payload.name as string)) {
    return {schemaVersion:1,commandId:commandId || '',accepted:false,createdIds:{},error:{code:'CHAT_CONFIRMATION_REQUIRED',message:'Use the host chat confirmation.'}}
  }
  if ((confirmationSurface?.isPending() || sourceImportBusy || chatMutation || (memoryFiles.isBusy()||memoryEditor.isBusy()) || storageHost.isBusy()) && !['CancelTurn','CancelOperation','StopGeneration'].includes(kind)) {
    return {schemaVersion:1,commandId:commandId || '',accepted:false,createdIds:{},error:{code:'PROJECT_BUSY',message:'Finish the current confirmation first.'}}
  }
  if (kind === 'ResolveUserInput') {
    return { schemaVersion: 1, commandId: commandId || '', accepted: false, createdIds: {},
      error: { code: 'QUESTION_HOST_ONLY', message: 'Use the host question dialog to answer.' } }
  }
  if (kind === 'ResolveApproval') {
    return { schemaVersion: 1, commandId: commandId || '', accepted: false, createdIds: {},
      error: { code: 'APPROVAL_HOST_ONLY', message: 'Use the trusted approval surface to decide.' } }
  }
  if (projectsHost?.isChanging() && ['SubmitUserInput','ExecuteCommand','ChangeProvider','ChangeModel','ResetEmbeddingSettings', 'SetEmbeddingSettings', 'SetWebSettings','SetFetchEnabled','SetSearchEngine','SetBrowser','SetContextWindow'].includes(kind)) {
    return {schemaVersion:1,commandId:commandId || '',accepted:false,createdIds:{},
      error:{code:'PROJECT_BUSY',message:'Wait for the selected project to be confirmed.'}}
  }
  return applicationClient.command(kind, payload, commandId)
})
ipcMain.handle('copy-message', (event, id: unknown) => validApplicationSender(event)
  ? copyPublicMessage(applicationClient.view.messages, id, text => clipboard.writeText(text)) : { success: false })
ipcMain.handle('review-pending-question', event => {
  if (!validApplicationSender(event)) return { success: false }
  return questionSurface?.reopenPending() || { success: false }
})
ipcMain.handle('review-pending-approval', event => {
  if (!validApplicationSender(event)) return { success: false }
  return approvalSurface?.reopenPending() || { success: false }
})
ipcMain.handle('refresh-readiness', event => {
  if (!validApplicationSender(event)) return { success: false }
  applicationClient.refreshReadiness(true)
  return { success: true }
})
ipcMain.handle('retry-model-download-inventory', event => {
  if (!validApplicationSender(event)) return {success:false}
  return {success:applicationClient.retryDownloadInventory()}
})
ipcMain.handle('restart-backend', event => {
  if (!validApplicationSender(event)) return {success:false,error:'DESKTOP_UNTRUSTED_SENDER'}
  if (applicationClient.modelDownloadBusy()) return {success:false,error:'MODEL_DOWNLOAD_BUSY'}
  if (pythonProcess) return { success: false, error: 'Backend is already running.' }
  restartWorkspace = applicationClient.view.workspace || projectsHost?.preferredPath() || defaultWorkspace()
  restoreOnWorkspaceBootstrap = true
  startPythonServer()
  return { success: true }
})

ipcMain.on('renderer-ready', event => {
  if (!validApplicationSender(event)) return
  rendererReady = true
  rendererRecovery?.ready()
  syncHistoryVisibility()
  mainWindow?.webContents.send('session-view', applicationClient.view)
  applicationClient.refresh()
  if (lastReadyMessage) {
    mainWindow?.webContents.send('python-message', lastReadyMessage)
  }
})

ipcMain.on('desktop-renderer-alive', (event, nonce: unknown) => {
  if (validApplicationSender(event)) rendererRecovery?.alive(nonce)
})

ipcMain.handle('get-projects', event => validApplicationSender(event) && projectsHost
  ? projectsHost.state() : {schemaVersion:1,defaultPath:'',activePath:null,folders:[],busy:false,error:{code:'PROJECT_UNAVAILABLE'}})
async function confirmChatAction(kind:'remove-project'|'clear-chat'|'clear-all', selectedPath?:string) {
  const current=applicationClient.view
  const identity={sessionId:current.sessionId,workspace:current.workspace,revision:current.stateRevision}
  const folder=selectedPath ? projectsHost?.state().folders.find(folder=>folder.path===selectedPath) : null
  const valid=()=>{
    const view=applicationClient.view
    if(!view.status.ready || view.recovering || view.sessionId!==identity.sessionId || view.workspace!==identity.workspace ||
      view.stateRevision!==identity.revision || applicationClient.workspaceBusy() || projectsHost?.isChanging() || chatMutation)return false
    if(folder){try{return fs.realpathSync(folder.path)===folder.path && !!projectsHost?.state().folders.some(item=>item.path===folder.path)}catch{return false}}
    return !selectedPath
  }
  if(!confirmationSurface || !valid())return {confirmed:false,canceled:true}
  return confirmationSurface.request({kind,projectName:folder?.name,path:folder?.path,validate:valid})
}
ipcMain.handle('get-project-chats',event=>applicationClient.modelDownloadBusy()
  ? {success:false,error:{code:'MODEL_DOWNLOAD_BUSY'}} : validApplicationSender(event)&&projectsHost
  ? projectChatClient.list(projectsHost.state().folders.map(folder=>folder.path))
  : {success:false,error:{code:'PROJECT_CHAT_UNAVAILABLE'}})
ipcMain.handle('clear-project-chat',async(event,selectedPath?:unknown)=>{
  if (applicationClient.modelDownloadBusy()) return {success:false,error:{code:'MODEL_DOWNLOAD_BUSY'}}
  if(!validApplicationSender(event)||!projectsHost || confirmationSurface?.isPending() || chatMutation || (memoryFiles.isBusy()||memoryEditor.isBusy()) || storageHost.isBusy() ||
    (selectedPath!==undefined && typeof selectedPath!=='string'))return {success:false,error:{code:'PROJECT_BUSY'}}
  if(typeof selectedPath==='string' && !projectsHost.state().folders.some(folder=>folder.path===selectedPath))
    return {success:false,error:{code:'PROJECT_NOT_REGISTERED'}}
  const decision=await confirmChatAction(selectedPath===undefined?'clear-all':'clear-chat',selectedPath as string|undefined)
  if(!decision.confirmed)return {success:false,canceled:true}
  chatMutation=true
  try{
    if(typeof selectedPath==='string')return await projectChatClient.clear(selectedPath)
    const receipt=await applicationClient.command('ExecuteCommand',{name:'clear_history',scope:'all'})
    return {success:receipt.accepted,error:receipt.error}
  }finally{chatMutation=false}
})
async function performProjectAction(action:unknown,selectedPath?:unknown){
  if (!projectsHost) return {success:false,error:{code:'PROJECT_UNAVAILABLE'}}
  if (applicationClient.modelDownloadBusy()) return {success:false,state:projectsHost.state(),error:{code:'MODEL_DOWNLOAD_BUSY'}}
  if (confirmationSurface?.isPending() || sourceImportBusy || chatMutation || (memoryFiles.isBusy()||memoryEditor.isBusy()) || storageHost.isBusy()) return {success:false,state:projectsHost.state(),error:{code:'PROJECT_BUSY'}}
  let removeAttachments=false
  if (action === 'remove') {
    const folder = projectsHost.state().folders.find(folder=>folder.path===selectedPath)
    if (!folder) return {success:false,state:projectsHost.state(),error:{code:'PROJECT_NOT_REGISTERED'}}
    if (folder.isDefault) return {success:false,state:projectsHost.state(),error:{code:'PROJECT_DEFAULT_REQUIRED'}}
    const decision=await confirmChatAction('remove-project',folder.path)
    if (!decision.confirmed) return {success:false,canceled:true,state:projectsHost.state()}
    removeAttachments=decision.deleteAssociatedFiles===true
  }
  const result=await projectsHost.action(action, selectedPath)
  if(result.success && action==='remove' && typeof selectedPath==='string') {
    const detached=await storageHost.detachProject(selectedPath,removeAttachments)
    if(!detached.success)return {...result,success:false,error:detached.error||{code:'STORAGE_FAILED'}}
    storageHost.invalidate()
  }
  return result
}
ipcMain.handle('project-action', (event,action:unknown,selectedPath?:unknown)=>validApplicationSender(event)
  ? performProjectAction(action,selectedPath) : {success:false,error:{code:'PROJECT_UNAVAILABLE'}})
ipcMain.handle('list-directory', (event, dirPath: unknown, offset:unknown = 0) => validApplicationSender(event) && projectsHost
  ? projectsHost.listDirectory(dirPath, offset) : {success:false,error:{code:'PROJECT_UNAVAILABLE'}})
ipcMain.handle('read-file', (event, filePath: unknown) => validApplicationSender(event) && projectsHost
  ? projectsHost.readFile(filePath) : {success:false,error:{code:'PROJECT_UNAVAILABLE'}})
// Legacy picker no longer changes authority; project-action owns selection and confirmation.
ipcMain.handle('open-directory-dialog', () => ({canceled:true,filePaths:[]}))

ipcMain.handle('get-home-dir', () => {
  return os.homedir()
})

ipcMain.handle('get-app-version', () => APP_VERSION)

ipcMain.handle('check-app-update', async () => {
  if (!DESKTOP_UPDATES_ENABLED) return disabledDesktopUpdate(APP_VERSION)
  try {
    const data = await fetchJson(`https://api.github.com/repos/${GITHUB_REPO}/releases/latest`)
    const latest = (data.tag_name || '').replace(/^v/, '')
    if (latest && latest !== APP_VERSION) {
      let downloadAsset: any
      let zipAsset: any
      if (process.platform === 'darwin') {
        downloadAsset = data.assets?.find((a: any) => a.name.endsWith('.dmg'))
        zipAsset = data.assets?.find((a: any) => a.name.endsWith('-mac.zip') || a.name.endsWith('.zip'))
      } else if (process.platform === 'linux') {
        downloadAsset = data.assets?.find((a: any) => a.name.endsWith('.AppImage'))
        zipAsset = data.assets?.find((a: any) => a.name.endsWith('.deb'))
      } else {
        downloadAsset = data.assets?.find((a: any) => a.name.endsWith('.exe'))
      }
      return {
        available: true,
        version: latest,
        notes: data.body || '',
        downloadUrl: downloadAsset?.browser_download_url || data.html_url,
        zipUrl: zipAsset?.browser_download_url || '',
        releaseUrl: data.html_url,
      }
    }
    return { available: false, version: APP_VERSION }
  } catch {
    return { available: false, version: APP_VERSION, error: 'Failed to check for updates' }
  }
})

// Write a self-deleting install script for the pending update.
//
// Hardened after a real 0.11.0 → 0.12.0 field failure:
// - Waits on the exact main-process PID (`kill -0`), NOT `pgrep -f <name>`
//   — name matching also hits unrelated processes whose command line merely
//   contains the app name (a terminal, a watcher script), blocking the
//   install forever while the app re-downloads in a loop.
// - Unique script path per update — the old fixed path let a second update
//   overwrite the script file while an earlier bash was still executing it.
// - macOS swap is restorable: the old bundle is moved aside and put back if
//   the swap fails, instead of being `rm -rf`ed before the `mv`.
function writeInstallScript(opts: {
  currentAppPath: string
  newAppPath: string
  tmpArchive: string
  tmpDir?: string
}): string {
  const installScript = path.join(os.tmpdir(), `local-cli-update-${Date.now()}.sh`)
  if (process.platform === 'darwin') {
    fs.writeFileSync(installScript, `#!/bin/bash
while kill -0 ${process.pid} 2>/dev/null; do sleep 0.5; done
TRASH="${opts.currentAppPath}.old-${Date.now()}"
mv "${opts.currentAppPath}" "$TRASH" || exit 1
if mv "${opts.newAppPath}" "${opts.currentAppPath}"; then
  rm -rf "$TRASH"
else
  mv "$TRASH" "${opts.currentAppPath}"
fi
rm -f "${opts.tmpArchive}"
${opts.tmpDir ? `rm -rf "${opts.tmpDir}"` : ':'}
open "${opts.currentAppPath}"
rm -f "${installScript}"
`, { mode: 0o755 })
  } else {
    fs.writeFileSync(installScript, `#!/bin/bash
while kill -0 ${process.pid} 2>/dev/null; do sleep 0.5; done
cp "${opts.newAppPath}" "${opts.currentAppPath}"
chmod +x "${opts.currentAppPath}"
rm -f "${opts.tmpArchive}"
${opts.tmpDir ? `rm -rf "${opts.tmpDir}"` : ':'}
"${opts.currentAppPath}" &
rm -f "${installScript}"
`, { mode: 0o755 })
  }
  return installScript
}

ipcMain.handle('install-app-update', async (_event, zipUrl: string) => {
  if (!DESKTOP_UPDATES_ENABLED) return { success: false, ...disabledDesktopUpdate(APP_VERSION),
    error: 'Desktop updates are not configured for Nova.' }
  // Download ZIP, extract, replace current app, restart.
  // Progress events sent via mainWindow.webContents.send('update-progress', ...)
  const sendProgress = (stage: string, percent: number) => {
    mainWindow?.webContents.send('update-progress', { stage, percent })
  }

  try {
    // 1. Download ZIP to temp file with progress.
    sendProgress('downloading', 0)
    const tmpZip = path.join(os.tmpdir(), `local-cli-update-${Date.now()}.zip`)
    await downloadFile(zipUrl, tmpZip, (pct) => sendProgress('downloading', pct))

    // 2. Extract ZIP / AppImage.
    sendProgress('extracting', 0)
    const tmpDir = path.join(os.tmpdir(), `local-cli-update-${Date.now()}`)
    fs.mkdirSync(tmpDir, { recursive: true })

    if (process.platform === 'darwin') {
      await new Promise<void>((resolve, reject) => {
        execFile('ditto', ['-xk', tmpZip, tmpDir], (err) => {
          if (err) reject(new Error(`Extract failed: ${err.message}`))
          else resolve()
        })
      })
    } else {
      await new Promise<void>((resolve, reject) => {
        execFile('unzip', ['-o', tmpZip, '-d', tmpDir], (err) => {
          if (err) reject(new Error(`Extract failed: ${err.message}`))
          else resolve()
        })
      })
    }
    sendProgress('extracting', 100)

    let installScript: string

    if (process.platform === 'darwin') {
      // macOS: Find the .app bundle in extracted contents.
      const entries = fs.readdirSync(tmpDir)
      const appBundle = entries.find(e => e.endsWith('.app'))
      if (!appBundle) throw new Error('No .app bundle found in ZIP')
      const newAppPath = path.join(tmpDir, appBundle)

      const currentAppPath = app.isPackaged
        ? path.resolve(process.resourcesPath!, '..', '..')
        : null

      if (!currentAppPath || !currentAppPath.endsWith('.app')) {
        throw new Error('Cannot determine app path. Dev mode does not support auto-update.')
      }

      sendProgress('installing', 0)
      installScript = writeInstallScript({
        currentAppPath, newAppPath, tmpArchive: tmpZip, tmpDir,
      })
    } else if (process.platform === 'linux') {
      // Linux: Replace AppImage in place.
      const entries = fs.readdirSync(tmpDir)
      const appImage = entries.find(e => e.endsWith('.AppImage'))
      if (!appImage) throw new Error('No AppImage found in archive')
      const newAppPath = path.join(tmpDir, appImage)

      const currentAppPath = process.env.APPIMAGE || app.getPath('exe')

      sendProgress('installing', 0)
      installScript = writeInstallScript({
        currentAppPath, newAppPath, tmpArchive: tmpZip, tmpDir,
      })
    } else {
      throw new Error('Auto-update is not supported on this platform.')
    }

    sendProgress('installing', 50)

    spawn('bash', [installScript], {
      detached: true,
      stdio: 'ignore',
    }).unref()

    sendProgress('installing', 100)

    setTimeout(() => {
      pythonProcess?.kill()
      app.quit()
    }, 500)

    return { success: true }
  } catch (err: any) {
    return { success: false, error: err.message || String(err) }
  }
})

function downloadFile(url: string, dest: string, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const doRequest = (reqUrl: string, redirects = 0) => {
      if (redirects > 5) return reject(new Error('Too many redirects'))
      const mod = reqUrl.startsWith('https') ? https : http
      mod.get(reqUrl, { headers: { 'User-Agent': `local-cli/${APP_VERSION}` } }, (res) => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          const loc = res.headers.location
          if (loc) return doRequest(loc, redirects + 1)
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`Download failed: HTTP ${res.statusCode}`))
        }
        const total = parseInt(res.headers['content-length'] || '0', 10)
        let received = 0
        const file = fs.createWriteStream(dest)
        res.on('data', (chunk: Buffer) => {
          received += chunk.length
          file.write(chunk)
          if (total > 0) onProgress(Math.round((received / total) * 100))
        })
        res.on('end', () => { file.end(); resolve() })
        res.on('error', (e) => { file.close(); reject(e) })
      }).on('error', reject)
    }
    doRequest(url)
  })
}

ipcMain.handle('open-external-url', (_event, url: string) => {
  return shell.openExternal(url)
})

function fetchJson(url: string): Promise<any> {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { 'User-Agent': `local-cli/${APP_VERSION}` } }, (res) => {
      // Follow redirects.
      if (res.statusCode === 301 || res.statusCode === 302) {
        const loc = res.headers.location
        if (loc) return fetchJson(loc).then(resolve, reject)
      }
      let body = ''
      res.on('data', (chunk) => { body += chunk })
      res.on('end', () => {
        try { resolve(JSON.parse(body)) }
        catch { reject(new Error('Invalid JSON')) }
      })
    })
    req.on('error', reject)
    req.setTimeout(15000, () => { req.destroy(); reject(new Error('Timeout')) })
  })
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  const initialWorkspace = defaultWorkspace()
  let defaultAccessible = true
  try { fs.mkdirSync(initialWorkspace, {recursive:true}); fs.accessSync(initialWorkspace,fs.constants.R_OK|fs.constants.W_OK) }
  catch { defaultAccessible = false; console.error('PROJECT_DEFAULT_UNAVAILABLE') }
  try {
    projectsHost = createProjectsHost({directory:desktopDataPath,defaultPath:initialWorkspace,client:applicationClient,
      chooseDirectory:()=>mainWindow ? dialog.showOpenDialog(mainWindow,pickerDialogOptions(desktopPreferences.get().locale,'project')) : Promise.resolve({canceled:true,filePaths:[]}),
      openPath:selectedPath=>shell.openPath(selectedPath),
      bootstrapWorkspace:bootstrapProject,
      clearChat:selectedPath=>projectChatClient.clear(selectedPath),
      publish:state=>{ if (rendererReady && mainWindow && !mainWindow.webContents.isDestroyed()) mainWindow.webContents.send('projects-state',state) }})
    try { fs.accessSync(projectsHost.defaultPath,fs.constants.R_OK|fs.constants.W_OK); defaultAccessible = fs.statSync(projectsHost.defaultPath).isDirectory() }
    catch { defaultAccessible = false }
    if (!defaultAccessible) projectsHost.setError('PROJECT_DEFAULT_UNAVAILABLE')
  } catch { console.error('PROJECT_DEFAULT_UNAVAILABLE') }
  if (!projectsHost) { createWindow(); return }
  if (defaultAccessible || projectsHost.preferredPath() !== projectsHost.defaultPath) startPythonServer()
  createWindow()

  if (!DESKTOP_UPDATES_ENABLED) return

  // Auto-update: check on startup, download+install automatically if available.
  try {
    const data = await fetchJson(`https://api.github.com/repos/${GITHUB_REPO}/releases/latest`)
    const latest = (data.tag_name || '').replace(/^v/, '')
    if (latest && latest !== APP_VERSION) {
      // Find platform-appropriate update asset.
      let updateAsset: any
      if (process.platform === 'darwin') {
        updateAsset = data.assets?.find((a: any) => a.name.endsWith('-mac.zip') || a.name.endsWith('.zip'))
      } else if (process.platform === 'linux') {
        updateAsset = data.assets?.find((a: any) => a.name.endsWith('.AppImage'))
      }
      if (updateAsset?.browser_download_url && app.isPackaged) {
        console.log(`Auto-update: ${APP_VERSION} → ${latest}`)
        const sendProgress = (stage: string, percent: number) => {
          mainWindow?.webContents.send('update-progress', { stage, percent, version: latest })
        }
        mainWindow?.webContents.send('auto-update-start', { version: latest })

        sendProgress('downloading', 0)
        const tmpFile = path.join(os.tmpdir(), `local-cli-update-${Date.now()}${process.platform === 'darwin' ? '.zip' : '.AppImage'}`)
        await downloadFile(updateAsset.browser_download_url, tmpFile, (pct) => sendProgress('downloading', pct))

        if (process.platform === 'darwin') {
          // macOS: Extract ZIP and replace .app bundle.
          sendProgress('extracting', 0)
          const tmpDir = path.join(os.tmpdir(), `local-cli-update-${Date.now()}`)
          fs.mkdirSync(tmpDir, { recursive: true })
          await new Promise<void>((resolve, reject) => {
            execFile('ditto', ['-xk', tmpFile, tmpDir], (err) => {
              err ? reject(err) : resolve()
            })
          })
          sendProgress('extracting', 100)

          const entries = fs.readdirSync(tmpDir)
          const appBundle = entries.find(e => e.endsWith('.app'))
          if (appBundle) {
            const newAppPath = path.join(tmpDir, appBundle)
            const currentAppPath = path.resolve(process.resourcesPath!, '..', '..')

            if (currentAppPath.endsWith('.app')) {
              sendProgress('installing', 50)
              const installScript = writeInstallScript({
                currentAppPath, newAppPath, tmpArchive: tmpFile, tmpDir,
              })

              spawn('bash', [installScript], { detached: true, stdio: 'ignore' }).unref()
              sendProgress('installing', 100)
              setTimeout(() => { pythonProcess?.kill(); app.quit() }, 500)
            }
          }
        } else if (process.platform === 'linux') {
          // Linux: Replace AppImage in place.
          const currentAppPath = process.env.APPIMAGE || app.getPath('exe')
          sendProgress('installing', 50)
          const installScript = writeInstallScript({
            currentAppPath, newAppPath: tmpFile, tmpArchive: tmpFile,
          })

          spawn('bash', [installScript], { detached: true, stdio: 'ignore' }).unref()
          sendProgress('installing', 100)
          setTimeout(() => { pythonProcess?.kill(); app.quit() }, 500)
        }
      }
    }
  } catch (e) {
    console.log('Auto-update check failed (non-fatal):', e)
  }
})

app.on('window-all-closed', () => {
  pythonProcess?.kill()
  app.quit()
})

app.on('before-quit', () => {
  quitting = true
  desktopMenu.dispose()
  rendererRecovery?.dispose()
  confirmationSurface?.dispose()
  questionSurface?.dispose()
  projectChatClient.disconnected(); modelUsageClient.disconnected()
  approvalSurface?.dispose()
  clearInterval(readinessMonitor)
  pythonProcess?.kill()
})
