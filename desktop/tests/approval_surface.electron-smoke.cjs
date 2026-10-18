// Owned fixture: real Electron sandbox/preload/IPC, fake command sink. No backend,
// account data, tools, external network, synthetic consent, or execution effects.
const { app, BrowserWindow, ipcMain } = require('electron')
const fs = require('node:fs')
const path = require('node:path')
const { createApprovalSurfaceController, READY_CHANNEL } = require('../electron/approval_surface.cjs')
const caseName = process.argv.find(value => value.startsWith('--case='))?.slice(7) || 'allow'
const readyOnly = process.argv.includes('--ready-only')
if (!/^[a-z0-9-]{1,24}$/.test(caseName)) throw new Error('Invalid fixture case')
const output = path.resolve(__dirname, '../../.runtime/gui-b4-native')
fs.mkdirSync(output, { recursive: true })
const logPath = path.join(output, `approval-native-${caseName}.jsonl`)
const completionPath = path.join(output, `approval-native-${caseName}.done.json`)
app.setPath('userData', path.join(output, `profile-${caseName}`))
const log = value => fs.appendFileSync(logPath, JSON.stringify({ at: new Date().toISOString(), ...value }) + '\n')
fs.writeFileSync(logPath, '')
let controller
app.whenReady().then(async () => {
  const parent = new BrowserWindow({ title: 'Nova — GUI-B4 owned approval fixture', width: 1000, height: 700,
    minWidth: 600, minHeight: 400, backgroundColor: '#10100f',
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } })
  parent.setMenu(null)
  await parent.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'"><title>Nova — GUI-B4 owned approval fixture</title><style>body{background:#10100f;color:#ded7cb;font:15px system-ui;margin:30px}h1{font-size:20px;color:#d5ad71}.composer{position:fixed;bottom:25px;left:45px;right:45px;border:1px solid #554733;border-radius:12px;padding:18px;display:flex;justify-content:space-between;align-items:center;background:#1a1815}button{background:#30291f;color:#f4e9d8;border:1px solid #796548;padding:10px 20px;border-radius:8px}</style><h1>Nova · GUI-B4</h1><p>Prueba local de la superficie de aprobación.</p><p>El comando de ejemplo no se ejecuta. La decisión se guarda únicamente como evidencia de la prueba.</p><div class="composer"><span>Escribe un mensaje…</span><button type="button">Detener</button></div>`))
  const request = { approvalId: 'fixture-approval', toolCallId: 'fixture-tool', turnId: 'fixture-turn',
    operationId: 'fixture-operation', name: 'bash', cwd: output, policyRevision: 1,
    requestDigest: 'fixture-digest', deadline: new Date(Date.now() + 8 * 60000).toISOString(),
    arguments: { command: 'Write-Output NOVA_GUI_B4_OWNED_FIXTURE', environment: { MODE: 'owned-fixture' } } }
  const client = { view: { sessionId: 'fixture-session', status: { ready: true, connected: true }, approvals: [request] },
    command: (kind, payload, commandId) => {
      const receipt = { event: 'decision', kind, payload, commandId, dispatchCount: ++dispatchCount, executed: false }
      log(receipt); fs.writeFileSync(completionPath, JSON.stringify(receipt, null, 2) + '\n')
      setTimeout(() => app.quit(), 1200)
      return Promise.resolve({ schemaVersion: 1, commandId, accepted: true, createdIds: {} })
    } }
  let dispatchCount = 0
  const observedIpc = { handle(channel, handler) {
    ipcMain.handle(channel, (event, payload) => {
      const result = handler(event, payload)
      const promise = typeof result?.then === 'function'
      log({ event: 'fixture-ipc', channel, accepted: promise ? null : result?.accepted === true,
        phase: promise ? 'pending' : 'completed', errorCode: result?.error?.code || null })
      if (promise) result.then(receipt => log({ event: 'fixture-ipc-complete', channel,
        accepted: receipt?.accepted === true, errorCode: receipt?.error?.code || null }))
      if (channel === READY_CHANNEL && result?.accepted) {
        const child = BrowserWindow.fromWebContents(event.sender)
        const preferences = event.sender.getLastWebPreferences()
        log({ event: 'surface-ready', childId: child.id, childPid: event.sender.getOSProcessId(),
          parentId: parent.id, exactParent: child.getParentWindow() === parent,
          localDataDocument: event.sender.getURL().startsWith('data:text/html;charset=utf-8,'),
          mainFrameOnly: event.senderFrame === event.sender.mainFrame,
          sandbox: preferences.sandbox, contextIsolation: preferences.contextIsolation,
          nodeIntegration: preferences.nodeIntegration, preload: preferences.preload,
          parentBounds: parent.getContentBounds(), childBounds: child.getBounds(),
          decisionButtons: ['No permitir', 'Permitir'], hostProofExposed: 'hostApprovalProof' in result })
        if (readyOnly) setTimeout(async () => {
          const review = await controller.reopenPending()
          const receipt = { event: 'ready-verification', ready: review.success, dispatchCount, executed: false }
          log(receipt); fs.writeFileSync(completionPath, JSON.stringify(receipt, null, 2) + '\n')
          app.quit()
        }, 0)
      }
      return result
    })
  }, removeHandler: channel => ipcMain.removeHandler(channel) }
  function ObservedWindow(options) {
    const child = new BrowserWindow(options)
    child.webContents.on('preload-error', (_event, preloadPath, error) => log({ event: 'preload-error', preloadPath, message: error.message }))
    child.webContents.on('console-message', (_event, level, message) => log({ event: 'child-console', level, message }))
    child.webContents.on('did-finish-load', () => log({ event: 'child-loaded', localDataDocument: child.webContents.getURL().startsWith('data:text/html;charset=utf-8,') }))
    child.webContents.on('did-fail-load', (_event, code, description) => log({ event: 'child-load-failed', code, description }))
    child.on('closed', () => log({ event: 'child-closed' }))
    return child
  }
  controller = createApprovalSurfaceController({ BrowserWindow: ObservedWindow, ipcMain: observedIpc, client,
    getParent: () => parent, getLocale: () => 'es', preloadPath: path.resolve(__dirname, '../dist-electron/approval_preload.js') })
  parent.show()
  controller.sync()
  log({ event: 'started', pid: process.pid, parentId: parent.id, caseName, logPath, completionPath,
    executionEffects: false, safetyTimerMinutes: 8, parentVisible: parent.isVisible(),
    parentMinimized: parent.isMinimized(), windows: BrowserWindow.getAllWindows().map(window => window.id) })
  parent.on('closed', () => app.quit())
  setTimeout(() => { log({ event: 'fixture-timeout', dispatchCount }); app.quit() }, 8 * 60000).unref()
})
app.on('before-quit', () => controller?.dispose())
app.on('window-all-closed', () => app.quit())
