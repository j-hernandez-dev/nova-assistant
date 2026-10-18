import { app, BrowserWindow, dialog, ipcMain, shell, safeStorage, Menu, clipboard } from 'electron'
import { spawn, execFile, ChildProcess } from 'child_process'
import http from 'node:http'
import https from 'node:https'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'path'
import { copyPublicMessage } from './message_copy'
import { DesktopApplicationClient } from './application_client'
import { memoryControl } from './memory_control.cjs'
import { pickKnowledge, knowledgeControl,hostSelection,remoteKnowledge } from './knowledge_control.cjs'
import { signApproval, validFrame } from './approval_host.cjs'
import { createApprovalSurfaceController } from './approval_surface.cjs'
import { createDesktopPreferencesStore } from './desktop_preferences.cjs'
import { createDesktopModelPreferencesStore } from './desktop_model_preferences.cjs'
import { createConversationPreferencesStore } from './conversation_preferences.cjs'
import { createConfirmationSurface } from './confirmation_surface.cjs'
import { createQuestionSurface } from './question_surface.cjs'
import { createProjectChatClient } from './project_chats.cjs'
import { createProjectsHost } from './projects_host.cjs'
import { DESKTOP_UPDATES_ENABLED, disabledDesktopUpdate, editingActionForInput } from './desktop_host_policy.cjs'
import { memoryDialogOptions, forwardingDialogOptions, pickerDialogOptions, oauthPage } from './desktop_host_locale.cjs'

// Keep the user profile independent of the legacy package name. Set both paths
// before ready so Chromium caches/cookies also use the Nova profile.
const desktopDataPath = path.join(app.getPath('appData'), 'nova-desktop')
fs.mkdirSync(desktopDataPath, { recursive: true })
app.setPath('userData', desktopDataPath)
app.setPath('sessionData', desktopDataPath)
const desktopPreferences = createDesktopPreferencesStore(desktopDataPath)
const desktopModelPreferences = createDesktopModelPreferencesStore(desktopDataPath)
const conversationPreferences = createConversationPreferencesStore(desktopDataPath)

// Read the real version from package.json (via Electron) instead of
// hardcoding — a stale hardcode was shown in the UI for several releases.
const APP_VERSION = app.getVersion()
const GITHUB_REPO = 'lutelute/local-cli'

// Claude auth credential storage path.
const CLAUDE_AUTH_PATH = path.join(
  process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'),
  'nova',
  'claude-auth.json',
)

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null
let lineBuffer = ''
let rendererReady = false
let requestedHistoryVisible = false
let lastReadyMessage: object | null = null
let storedApiKey: string | null = null
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
  preloadPath: path.join(__dirname, 'approval_preload.js') })
const projectChatClient = createProjectChatClient({send:sendToPython,getView:()=>applicationClient.view})
confirmationSurface = createConfirmationSurface({BrowserWindow,ipcMain,getParent:()=>mainWindow,
  getLocale:()=>desktopPreferences.get().locale,preloadPath:path.join(__dirname,'confirmation_preload.js')})
questionSurface = createQuestionSurface({BrowserWindow, ipcMain, client: applicationClient, getParent: () => mainWindow,
  getLocale: () => desktopPreferences.get().locale, preloadPath: path.join(__dirname, 'question_preload.js'),
  canOpen: () => !confirmationSurface?.isPending() && !chatMutation && !applicationClient.view.approvals.length })
applicationClient.setConversationPreferences(conversationPreferences)
applicationClient.setConfirmedModelObserver(runtime => {
  const result = desktopModelPreferences.saveConfirmed(runtime)
  applicationClient.setModelPreferenceError(result.success ? null : 'MODEL_PREFERENCE_SAVE_FAILED')
})
// Recheck only host readiness. This monitor never retries a user operation.
const readinessMonitor = setInterval(() => applicationClient.refreshReadiness(), 15_000)
readinessMonitor.unref()

function syncHistoryVisibility() {
  applicationClient.setHistoryVisible(requestedHistoryVisible && rendererReady && !!mainWindow
    && !mainWindow.isDestroyed() && mainWindow.isVisible() && !mainWindow.isMinimized())
}

function clearHistoryVisibility() {
  requestedHistoryVisible = false
  applicationClient.setHistoryVisible(false)
}

// ---------------------------------------------------------------------------
// Claude credential storage (encrypted with safeStorage when available)
// ---------------------------------------------------------------------------

type ClaudeAuth = {
  method: 'api_key' | 'subscription'
  key: string // encrypted (base64) or plain
  encrypted: boolean
}

function loadClaudeAuth(): ClaudeAuth | null {
  try {
    if (!fs.existsSync(CLAUDE_AUTH_PATH)) return null
    const raw = fs.readFileSync(CLAUDE_AUTH_PATH, 'utf-8')
    const data = JSON.parse(raw) as ClaudeAuth
    if (data.encrypted && safeStorage.isEncryptionAvailable()) {
      data.key = safeStorage.decryptString(Buffer.from(data.key, 'base64'))
    }
    return data
  } catch {
    return null
  }
}

function saveClaudeAuth(method: 'api_key' | 'subscription', key: string): void {
  const dir = path.dirname(CLAUDE_AUTH_PATH)
  fs.mkdirSync(dir, { recursive: true })

  let storedKey = key
  let encrypted = false
  if (safeStorage.isEncryptionAvailable()) {
    storedKey = safeStorage.encryptString(key).toString('base64')
    encrypted = true
  }
  fs.writeFileSync(
    CLAUDE_AUTH_PATH,
    JSON.stringify({ method, key: storedKey, encrypted } as ClaudeAuth),
    { mode: 0o600 },
  )
}

function deleteClaudeAuth(): void {
  try { fs.unlinkSync(CLAUDE_AUTH_PATH) } catch { /* ignore */ }
  storedApiKey = null
}

function initClaudeAuth(): void {
  // Load stored credentials and set env var for Python.
  const auth = loadClaudeAuth()
  if (auth?.key) {
    storedApiKey = auth.key
    process.env.ANTHROPIC_API_KEY = auth.key
  }
}

/** Validate an API key by making a lightweight request to the Anthropic API. */
function validateApiKey(key: string): Promise<{ valid: boolean; error?: string }> {
  return new Promise((resolve) => {
    const body = JSON.stringify({
      model: 'claude-haiku-4-5',
      max_tokens: 1,
      messages: [{ role: 'user', content: 'hi' }],
    })
    const req = https.request(
      'https://api.anthropic.com/v1/messages',
      {
        method: 'POST',
        headers: {
          'x-api-key': key,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json',
        },
        timeout: 15000,
      },
      (res) => {
        let data = ''
        res.on('data', (c) => { data += c })
        res.on('end', () => {
          if (res.statusCode === 200) {
            resolve({ valid: true })
          } else if (res.statusCode === 401) {
            resolve({ valid: false, error: 'AUTH_INVALID_KEY' })
          } else {
            // 429 (rate limit) or other errors — key format is valid.
            resolve({ valid: true })
          }
        })
      },
    )
    req.on('error', () => resolve({ valid: false, error: 'AUTH_NETWORK_FAILED' }))
    req.on('timeout', () => { req.destroy(); resolve({ valid: false, error: 'AUTH_TIMEOUT' }) })
    req.write(body)
    req.end()
  })
}

// ---------------------------------------------------------------------------
// OAuth flow for Claude subscription
// ---------------------------------------------------------------------------

function startOAuthFlow(): Promise<{ success: boolean; error?: string }> {
  return new Promise((resolve) => {
    // Start a local HTTP server to receive the OAuth callback.
    const state = crypto.randomBytes(16).toString('hex')
    let resolved = false

    const server = http.createServer((req, res) => {
      const url = new URL(req.url || '/', `http://localhost`)
      if (url.pathname !== '/callback') {
        res.writeHead(404)
        res.end()
        return
      }

      const code = url.searchParams.get('code')
      const returnedState = url.searchParams.get('state')
      const error = url.searchParams.get('error')

      if (error) {
        res.writeHead(200, { 'Content-Type': 'text/html' })
        res.end(oauthPage(desktopPreferences.get().locale, 'failed'))
        if (!resolved) {
          resolved = true
          server.close()
          resolve({ success: false, error: 'AUTH_OAUTH_FAILED' })
        }
        return
      }

      if (!code || returnedState !== state) {
        res.writeHead(400, { 'Content-Type': 'text/html' })
        res.end(oauthPage(desktopPreferences.get().locale, 'invalid'))
        return
      }

      res.writeHead(200, { 'Content-Type': 'text/html' })
      res.end(oauthPage(desktopPreferences.get().locale, 'success'))

      if (!resolved) {
        resolved = true
        server.close()

        // Exchange the auth code for a session key.
        exchangeOAuthCode(code).then((result) => {
          if (result.apiKey) {
            try { saveClaudeAuth('subscription', result.apiKey) }
            catch { resolve({ success: false, error: 'AUTH_SAVE_FAILED' }); return }
            storedApiKey = result.apiKey
            process.env.ANTHROPIC_API_KEY = result.apiKey
            // Notify Python backend.
            sendToPython({ type: 'set_api_key', api_key: result.apiKey })
            resolve({ success: true })
          } else {
            resolve({ success: false, error: result.error || 'AUTH_OAUTH_FAILED' })
          }
        })
      }
    })

    // Listen on a random available port.
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address()
      if (!addr || typeof addr === 'string') {
        resolve({ success: false, error: 'AUTH_CALLBACK_FAILED' })
        return
      }
      const port = addr.port
      const redirectUri = `http://127.0.0.1:${port}/callback`
      const authUrl = `https://console.anthropic.com/oauth/authorize?response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}&client_id=local-cli`

      shell.openExternal(authUrl)

      // Timeout after 5 minutes.
      setTimeout(() => {
        if (!resolved) {
          resolved = true
          server.close()
          resolve({ success: false, error: 'AUTH_TIMEOUT' })
        }
      }, 300_000)
    })

    server.on('error', () => {
      if (!resolved) {
        resolved = true
        resolve({ success: false, error: 'AUTH_CALLBACK_FAILED' })
      }
    })
  })
}

function exchangeOAuthCode(code: string): Promise<{ apiKey?: string; error?: string }> {
  return new Promise((resolve) => {
    const body = JSON.stringify({ code, grant_type: 'authorization_code', client_id: 'local-cli' })
    const req = https.request(
      'https://console.anthropic.com/oauth/token',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        timeout: 15000,
      },
      (res) => {
        let data = ''
        res.on('data', (c) => { data += c })
        res.on('end', () => {
          try {
            const json = JSON.parse(data)
            if (json.access_token) {
              resolve({ apiKey: json.access_token })
            } else {
              resolve({ error: 'AUTH_OAUTH_FAILED' })
            }
          } catch {
            resolve({ error: 'AUTH_INVALID_RESPONSE' })
          }
        })
      },
    )
    req.on('error', () => resolve({ error: 'AUTH_NETWORK_FAILED' }))
    req.on('timeout', () => { req.destroy(); resolve({ error: 'AUTH_TIMEOUT' }) })
    req.write(body)
    req.end()
  })
}

// ---------------------------------------------------------------------------

function findPython(): string {
  if (process.platform === 'win32') return 'python'

  // GUI apps may get a minimal PATH. Check common paths for Python 3.10+.
  const candidates: string[] = process.platform === 'darwin'
    ? [
        '/opt/homebrew/bin/python3',   // macOS ARM Homebrew
        '/usr/local/bin/python3',      // macOS Intel Homebrew
        'python3',
      ]
    : [
        '/usr/bin/python3',            // Linux system Python
        '/usr/local/bin/python3',      // Linux manual install
        'python3',
      ]
  for (const candidate of candidates) {
    try {
      const { execFileSync } = require('child_process')
      execFileSync(candidate, ['--version'], { stdio: 'ignore' })
      return candidate
    } catch {
      // Not found, try next.
    }
  }
  return 'python3'
}

function findProjectRoot(): string {
  // In dev mode: __dirname is desktop/dist-electron, so ../../ is project root.
  // In packaged app: local_cli/ and pyproject.toml are in Resources/ via extraResources.
  if (app.isPackaged && process.resourcesPath) {
    return path.resolve(process.resourcesPath)
  }
  return path.resolve(__dirname, '..', '..')
}

function startPythonServer() {
  const pythonCmd = findPython()
  const projectRoot = findProjectRoot()
  if (!restartWorkspace) restartWorkspace = projectsHost?.preferredPath() || path.join(projectRoot, 'workspace')

  console.log(`Starting Python server: ${pythonCmd} -m local_cli --server`)
  console.log(`Working directory: ${projectRoot}`)

  const env: Record<string, string> = desktopModelPreferences.childEnvironment({
    ...process.env as Record<string, string>, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8',
  })
  approvalHostKey = crypto.randomBytes(32).toString('hex')
  env.NOVA_APPROVAL_HOST_KEY = approvalHostKey
  if (storedApiKey) {
    env.ANTHROPIC_API_KEY = storedApiKey
  }

  lineBuffer = ''
  lastReadyMessage = null
  bootstrapReadyMessage = null
  const child = spawn(pythonCmd, ['-m', 'local_cli', '--server'], {
    cwd: projectRoot,
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
    projectChatClient.disconnected()
    applicationClient.disconnected()
  })
  child.stdin?.on('error', () => {
    if (pythonProcess === child) applicationClient.disconnected()
  })
  child.on('exit', (code) => {
    if (pythonProcess !== child) return
    console.log(`Python process exited with code ${code}`)
    mainWindow?.webContents.send('python-exit', code)
    pythonProcess = null
    projectChatClient.disconnected()
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

function createWindow() {
  mainWindow = new BrowserWindow({
    title: 'Nova',
    icon: path.join(__dirname, process.env.VITE_DEV_SERVER_URL ? '../public' : '../dist',
      process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    backgroundColor: '#090c12',
    show: false,
    width: 1000,
    height: 700,
    minWidth: 600,
    minHeight: 400,
    ...(process.platform === 'darwin'
      ? { titleBarStyle: 'hiddenInset' as const, trafficLightPosition: { x: 16, y: 16 } }
      : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      additionalArguments: [`--nova-desktop-locale=${desktopPreferences.get().locale}`],
    },
  })
  const window = mainWindow
  window.once('ready-to-show', () => { if (!window.isDestroyed()) window.show() })
  mainWindow.setMenu(null)
  mainWindow.webContents.on('page-title-updated', event => {
    event.preventDefault()
    mainWindow?.setTitle('Nova')
  })
  mainWindow.webContents.on('before-input-event', (event, input) => {
    const action = editingActionForInput(input, process.platform)
    if (!action || !mainWindow) return
    event.preventDefault()
    mainWindow.webContents[action]()
  })

  // In dev mode, load from Vite dev server.
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    approvalSurface?.invalidate()
    questionSurface?.invalidate()
    rendererReady = false
    clearHistoryVisibility()
    mainWindow = null
  })
  mainWindow.on('hide', () => applicationClient.setHistoryVisible(false))
  mainWindow.on('minimize', () => applicationClient.setHistoryVisible(false))
  mainWindow.on('show', () => { syncHistoryVisibility(); questionSurface?.sync() })
  mainWindow.on('restore', () => { syncHistoryVisibility(); questionSurface?.sync() })
  mainWindow.on('focus', () => { applicationClient.refreshReadiness(); questionSurface?.sync() })
  mainWindow.webContents.on('did-start-loading', () => { rendererReady = false; clearHistoryVisibility() })
  mainWindow.webContents.on('destroyed', clearHistoryVisibility)
  mainWindow.webContents.on('render-process-gone', () => { rendererReady = false; clearHistoryVisibility() })
  approvalSurface?.sync()
  questionSurface?.sync()
}

// IPC handlers.
function validApplicationSender(event: Electron.IpcMainEvent | Electron.IpcMainInvokeEvent) {
  return !!mainWindow && event.sender === mainWindow.webContents &&
    event.senderFrame === mainWindow.webContents.mainFrame
}

// A memory-only snapshot lets preload apply presentation before the first paint, including reloads.
ipcMain.on('get-desktop-startup-preferences', event => {
  event.returnValue = validApplicationSender(event) ? desktopPreferences.get() : null
})
ipcMain.handle('set-desktop-appearance', (event, value: unknown) => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  return desktopPreferences.setAppearance(value)
})
ipcMain.handle('get-desktop-preferences', event => {
  if (!validApplicationSender(event)) return { success: false,
    error: { code: 'DESKTOP_UNTRUSTED_SENDER', message: 'Desktop preferences are unavailable.' } }
  return desktopPreferences.get()
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
  if (!validApplicationSender(event) || !validFrame(data) || data.type === 'set_cwd' || ['project_chats','clear_project_chat','command','chat'].includes(data.type) || data.type === 'memory_command' || data.type === 'knowledge_command' || data.type === 'confirm_response' ||
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
ipcMain.handle('memory-command', async (event, name: string, args: Record<string, unknown>, commandId?: string) => {
  if (!validApplicationSender(event) || typeof name !== 'string' || !validFrame(args)) {
    return { schemaVersion: 1, commandId: commandId || '', completed: false,
      error: { code: 'MEMORY_UNTRUSTED_INPUT', message: 'Invalid memory action.' } }
  }
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:commandId || '',completed:false,error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  return memoryControl(applicationClient, name, args, commandId, (request: { name: string; workspace: string | null; write: boolean }) =>
    dialog.showMessageBox(mainWindow!, memoryDialogOptions(desktopPreferences.get().locale, request)))
})

ipcMain.handle('knowledge-pick', async event => {
  if (!validApplicationSender(event) || !mainWindow) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},
    error:{code:'SOURCE_NOT_AUTHORIZED',message:'Main-frame host picker required.'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  return pickKnowledge(applicationClient, () => dialog.showOpenDialog(mainWindow!,pickerDialogOptions(desktopPreferences.get().locale,'document')))
})
ipcMain.handle('knowledge-command', async (event,name:string,args:Record<string,unknown>,commandId?:string) => {
  if (!validApplicationSender(event) || !validFrame(args)) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},
    error:{code:'SOURCE_NOT_AUTHORIZED',message:'Invalid source control.'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  if(name==='source_remote')return remoteKnowledge(applicationClient,args,()=>dialog.showMessageBox(mainWindow!,
    forwardingDialogOptions(desktopPreferences.get().locale)),commandId)
  return knowledgeControl(applicationClient,name,args,commandId)
})
ipcMain.handle('knowledge-refresh',async(event,sourceId:string)=>{
  if(!validApplicationSender(event)||!mainWindow||typeof sourceId!=='string')return {accepted:false,error:{code:'SOURCE_NOT_AUTHORIZED'}}
  if (applicationClient.modelDownloadBusy()) return {schemaVersion:1,commandId:'',accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}}
  return hostSelection(applicationClient,'source_refresh',sourceId,()=>dialog.showOpenDialog(mainWindow!,pickerDialogOptions(desktopPreferences.get().locale,'refresh')))
})
ipcMain.handle('knowledge-export',async(event,sourceId:string)=>{
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
  if ((confirmationSurface?.isPending() || chatMutation) && !['CancelTurn','CancelOperation','StopGeneration'].includes(kind)) {
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
  if (projectsHost?.isChanging() && ['SubmitUserInput','ExecuteCommand','ChangeProvider','ChangeModel','SetFetchEnabled','SetSearchEngine','SetBrowser','SetContextWindow'].includes(kind)) {
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
  restartWorkspace = applicationClient.view.workspace || projectsHost?.preferredPath() || path.join(findProjectRoot(),'workspace')
  restoreOnWorkspaceBootstrap = true
  startPythonServer()
  return { success: true }
})

ipcMain.on('renderer-ready', event => {
  if (!validApplicationSender(event)) return
  rendererReady = true
  syncHistoryVisibility()
  mainWindow?.webContents.send('session-view', applicationClient.view)
  applicationClient.refresh()
  if (lastReadyMessage) {
    mainWindow?.webContents.send('python-message', lastReadyMessage)
  }
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
  if(!validApplicationSender(event)||!projectsHost || confirmationSurface?.isPending() || chatMutation ||
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
ipcMain.handle('project-action', async (event, action: unknown, selectedPath?:unknown) => {
  if (!validApplicationSender(event) || !projectsHost) return {success:false,error:{code:'PROJECT_UNAVAILABLE'}}
  if (applicationClient.modelDownloadBusy()) return {success:false,state:projectsHost.state(),error:{code:'MODEL_DOWNLOAD_BUSY'}}
  if (confirmationSurface?.isPending() || chatMutation) return {success:false,state:projectsHost.state(),error:{code:'PROJECT_BUSY'}}
  if (action === 'remove') {
    const folder = projectsHost.state().folders.find(folder=>folder.path===selectedPath)
    if (!folder) return {success:false,state:projectsHost.state(),error:{code:'PROJECT_NOT_REGISTERED'}}
    if (folder.isDefault) return {success:false,state:projectsHost.state(),error:{code:'PROJECT_DEFAULT_REQUIRED'}}
    const decision=await confirmChatAction('remove-project',folder.path)
    if (!decision.confirmed) return {success:false,canceled:true,state:projectsHost.state()}
  }
  return projectsHost.action(action, selectedPath)
})
ipcMain.handle('list-directory', (event, dirPath: unknown, offset:unknown = 0) => validApplicationSender(event) && projectsHost
  ? projectsHost.listDirectory(dirPath, offset) : {success:false,error:{code:'PROJECT_UNAVAILABLE'}})
ipcMain.handle('read-file', (event, filePath: unknown) => validApplicationSender(event) && projectsHost
  ? projectsHost.readFile(filePath) : {success:false,error:{code:'PROJECT_UNAVAILABLE'}})
// Legacy picker no longer changes authority; project-action owns selection and confirmation.
ipcMain.handle('open-directory-dialog', () => ({canceled:true,filePaths:[]}))

ipcMain.handle('get-home-dir', () => {
  return os.homedir()
})

ipcMain.handle('has-claude-access', () => {
  return !!process.env.ANTHROPIC_API_KEY || !!storedApiKey
})

ipcMain.handle('get-claude-auth', () => {
  const auth = loadClaudeAuth()
  if (!auth) return { method: null, keyHint: null, authenticated: false }
  const hint = auth.key ? auth.key.slice(0, 10) + '...' + auth.key.slice(-4) : null
  return { method: auth.method, keyHint: hint, authenticated: true }
})

ipcMain.handle('save-claude-key', async (_event, key: string) => {
  const validation = await validateApiKey(key)
  if (!validation.valid) {
    return { success: false, error: validation.error }
  }
  try { saveClaudeAuth('api_key', key) }
  catch { return { success: false, error: 'AUTH_SAVE_FAILED' } }
  storedApiKey = key
  process.env.ANTHROPIC_API_KEY = key
  // Notify Python backend about the new key.
  sendToPython({ type: 'set_api_key', api_key: key })
  const hint = key.slice(0, 10) + '...' + key.slice(-4)
  return { success: true, keyHint: hint }
})

ipcMain.handle('delete-claude-auth', () => {
  deleteClaudeAuth()
  delete process.env.ANTHROPIC_API_KEY
  return { success: true }
})

ipcMain.handle('start-claude-oauth', async () => {
  return await startOAuthFlow()
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
  initClaudeAuth()
  const defaultWorkspace = path.join(findProjectRoot(), 'workspace')
  let defaultAccessible = true
  try { fs.mkdirSync(defaultWorkspace, {recursive:true}); fs.accessSync(defaultWorkspace,fs.constants.R_OK|fs.constants.W_OK) }
  catch { defaultAccessible = false; console.error('PROJECT_DEFAULT_UNAVAILABLE') }
  try {
    projectsHost = createProjectsHost({directory:desktopDataPath,defaultPath:defaultWorkspace,client:applicationClient,
      chooseDirectory:()=>mainWindow ? dialog.showOpenDialog(mainWindow,pickerDialogOptions(desktopPreferences.get().locale,'project')) : Promise.resolve({canceled:true,filePaths:[]}),
      openPath:selectedPath=>shell.openPath(selectedPath),
      bootstrapWorkspace:bootstrapProject,
      clearChat:selectedPath=>projectChatClient.clear(selectedPath),
      publish:state=>{ if (rendererReady && mainWindow && !mainWindow.webContents.isDestroyed()) mainWindow.webContents.send('projects-state',state) }})
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
  confirmationSurface?.dispose()
  questionSurface?.dispose()
  projectChatClient.disconnected()
  approvalSurface?.dispose()
  clearInterval(readinessMonitor)
  pythonProcess?.kill()
})
