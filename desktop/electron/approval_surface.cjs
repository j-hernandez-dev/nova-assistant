// One host-created approval surface. The application renderer never supplies consent.
const crypto = require('node:crypto')
const { stableJson, validFrame } = require('./approval_host.cjs')

const READY_CHANNEL = 'approval-surface-ready'
const DECISION_CHANNEL = 'approval-surface-decision'
const UPDATE_CHANNEL = 'approval-surface-locale'
const APPROVAL_HTML = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; font-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Nova</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#151413;color:#ede9e3;font:13px/1.45 system-ui,sans-serif}body{border:1px solid #9b7b50;border-radius:12px;overflow:hidden}.surface{height:100%;display:flex;flex-direction:column;padding:16px 18px;gap:9px}header{display:flex;align-items:center;gap:10px}h1{font-size:15px;margin:0}.mark{color:#d5ad71;font-weight:700}p{margin:0;color:#c3bcb0}.details{min-height:0;overflow:auto;flex:1;border:1px solid #494035;border-radius:7px;background:#100f0e;padding:9px 11px}dl{display:grid;grid-template-columns:100px minmax(0,1fr);gap:4px 10px;margin:0 0 8px}dt{color:#a79b89}dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}pre{font:12px/1.45 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0;color:#e7e0d5}.actions{display:flex;justify-content:flex-end;gap:8px}button{font:inherit;font-weight:600;border:1px solid #796548;border-radius:6px;padding:7px 15px;background:#30291f;color:#f5f0e8;cursor:pointer}button.allow{background:#d5ad71;color:#1c170f;border-color:#d5ad71}button:focus-visible{outline:2px solid #fff;outline-offset:2px}button:disabled{opacity:.5;cursor:default}.foot{font-size:11px;color:#a79b89}
</style></head><body><main class="surface" aria-labelledby="heading"><header><span class="mark" aria-hidden="true">NOVA</span><h1 id="heading"></h1></header><p id="explanation"></p><section class="details" aria-label="Request"><dl><dt id="tool-label"></dt><dd id="tool"></dd><dt id="cwd-label"></dt><dd id="cwd"></dd><dt id="deadline-label"></dt><dd id="deadline"></dd></dl><pre id="arguments"></pre></section><p class="foot" id="scope"></p><div class="actions"><button id="deny" type="button" disabled></button><button id="allow" type="button" class="allow" disabled></button></div></main></body></html>`
const APPROVAL_URL = 'data:text/html;charset=utf-8,' + encodeURIComponent(APPROVAL_HTML)

function captureApproval(view, pending, now = Date.now()) {
  if (!view || typeof view.sessionId !== 'string' || !view.sessionId ||
      !view.status?.ready || !view.status?.connected || view.recovering === true || !validFrame(pending)) return null
  for (const field of ['approvalId', 'toolCallId', 'turnId', 'operationId', 'requestDigest', 'cwd', 'name']) {
    if (typeof pending[field] !== 'string' || !pending[field]) return null
  }
  if (!Number.isSafeInteger(pending.policyRevision) || pending.policyRevision < 0 ||
      !validFrame(pending.arguments) || typeof pending.deadline !== 'string') return null
  const deadline = Date.parse(pending.deadline)
  if (!Number.isFinite(deadline) || now >= deadline) return null
  // Snapshot every projected request field, including arguments and correlations.
  const request = JSON.parse(JSON.stringify(pending))
  return { sessionId: view.sessionId, request, deadline,
    identity: stableJson([view.sessionId, request.approvalId]),
    fingerprint: stableJson([view.sessionId, request]) }
}

function approvalSurfaceBounds(parent) {
  const area = parent.getContentBounds()
  const inset = 12
  // Reserve the bottom composer and its Stop control, including at minimum size.
  const reserve = Math.min(210, Math.max(146, Math.round(area.height * .27)))
  const width = Math.max(1, Math.min(720, area.width - inset * 2))
  const height = Math.max(1, Math.min(360, area.height - reserve - inset * 2))
  return { x: Math.round(area.x + (area.width - width) / 2),
    y: Math.round(area.y + area.height - reserve - height - inset), width, height }
}

function createApprovalSurfaceController(options) {
  const { BrowserWindow, ipcMain, client, getParent, preloadPath } = options
  const now = options.now || Date.now
  const schedule = options.setTimeout || setTimeout
  const unschedule = options.clearTimeout || clearTimeout
  const getLocale = () => options.getLocale?.() === 'en' ? 'en' : 'es'
  const suppressed = new Set()
  const consumed = new Set()
  let active = null
  let disposed = false
  const pendingRequests = () => Array.isArray(client.view?.approvals) ? client.view.approvals : []

  const reject = code => ({ accepted: false, error: { code } })
  const exactSender = (event, record) => !!record && !record.window.isDestroyed() &&
    event.sender === record.window.webContents && event.senderFrame === record.window.webContents.mainFrame
  function currentCapture(record) {
    const view = client.view
    const pending = pendingRequests().find(p => p?.approvalId === record.capture.request.approvalId)
    const capture = captureApproval(view, pending, now())
    return capture?.fingerprint === record.capture.fingerprint ? capture : null
  }
  function close(record, suppress = true) {
    if (!record || active !== record) return
    active = null // Invalidate the nonce before any window event or command dispatch.
    if (suppress) suppressed.add(record.capture.identity)
    if (record.timer) unschedule(record.timer)
    if (record.bootTimer) unschedule(record.bootTimer)
    record.resolveReady(false)
    for (const [name, handler] of record.parentEvents) record.parent.removeListener(name, handler)
    record.parentEvents = []
    try { if (!record.window.isDestroyed()) record.window.destroy() } catch { /* Binding is already revoked. */ }
  }
  function position(record) {
    if (active !== record || record.parent.isDestroyed()) return false
    try { record.window.setBounds(approvalSurfaceBounds(record.parent)); return true }
    catch { close(record); return false }
  }
  function display(record) {
    if (active !== record || !record.ready || record.parent.isDestroyed()) return false
    try {
      if (!record.parent.isVisible() || record.parent.isMinimized()) { record.window.hide(); return true }
      if (!position(record)) return false
      record.window.show()
      return true
    } catch { close(record); return false }
  }
  function create(capture, parent) {
    const child = new BrowserWindow({ ...approvalSurfaceBounds(parent), parent, modal: false,
      title: 'Nova', frame: false, show: false, resizable: false, movable: false,
      minimizable: false, maximizable: false, fullscreenable: false, skipTaskbar: true,
      backgroundColor: '#151413', autoHideMenuBar: true,
      webPreferences: { preload: preloadPath, sandbox: true, contextIsolation: true,
        nodeIntegration: false, nodeIntegrationInSubFrames: false, webviewTag: false,
        nodeIntegrationInWorker: false, devTools: false,
        webSecurity: true, navigateOnDragDrop: false, disableDialogs: true,
        partition: 'nova-approval-surface' } })
    let resolveReady
    const readyPromise = new Promise(resolve => { resolveReady = resolve })
    const record = { window: child, parent, capture, nonce: crypto.randomBytes(32).toString('hex'),
      ready: false, readyPromise, resolveReady, parentEvents: [], timer: null, bootTimer: null, started: false }
    active = record
    child.setMenu(null)
    child.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    child.webContents.session?.setPermissionRequestHandler?.((_wc, _permission, callback) => callback(false))
    child.webContents.session?.setPermissionCheckHandler?.(() => false)
    const prevent = event => event.preventDefault()
    child.webContents.on('will-navigate', prevent)
    child.webContents.on('will-frame-navigate', prevent)
    child.webContents.on('will-attach-webview', prevent)
    child.webContents.on('did-start-navigation', (_event, _url, _inPlace, isMainFrame) => {
      if (!isMainFrame || active !== record) return
      if (record.started) close(record)
      else record.started = true
    })
    child.webContents.on('render-process-gone', () => close(record))
    child.webContents.on('destroyed', () => close(record))
    child.on('closed', () => close(record)) // Closing preserves the pending backend request.
    for (const name of ['move', 'resize', 'maximize', 'unmaximize']) {
      const handler = () => position(record)
      parent.on(name, handler); record.parentEvents.push([name, handler])
    }
    for (const name of ['show', 'restore']) {
      const handler = () => display(record)
      parent.on(name, handler); record.parentEvents.push([name, handler])
    }
    for (const name of ['hide', 'minimize']) {
      const handler = () => { if (!child.isDestroyed()) child.hide() }
      parent.on(name, handler); record.parentEvents.push([name, handler])
    }
    const parentClosed = () => close(record)
    parent.on('closed', parentClosed); record.parentEvents.push(['closed', parentClosed])
    const expire = () => {
      if (active !== record) return
      const remaining = capture.deadline - now()
      if (remaining <= 0 || !currentCapture(record)) close(record)
      else { record.timer = schedule(expire, Math.min(remaining, 2147483647)); record.timer?.unref?.() }
    }
    record.timer = schedule(expire, Math.min(capture.deadline - now(), 2147483647))
    record.timer?.unref?.()
    record.bootTimer = schedule(() => close(record), Math.min(5000, capture.deadline - now()))
    record.bootTimer?.unref?.()
    Promise.resolve(child.loadURL(APPROVAL_URL)).catch(() => close(record))
  }
  function sync() {
    if (disposed) return
    const view = client.view
    const present = new Set(pendingRequests().map(p => stableJson([view?.sessionId, p?.approvalId])))
    for (const identity of suppressed) if (!present.has(identity)) suppressed.delete(identity)
    for (const identity of consumed) if (!present.has(identity)) consumed.delete(identity)
    if (active) {
      if (!currentCapture(active) || getParent() !== active.parent || active.parent.isDestroyed()) close(active)
      else { position(active); return }
    }
    const parent = getParent()
    if (!parent || parent.isDestroyed() || !parent.isVisible() || parent.isMinimized()) return
    for (const pending of pendingRequests()) {
      const capture = captureApproval(view, pending, now())
      if (capture && !suppressed.has(capture.identity)) {
        try { create(capture, parent) }
        catch {
          if (active?.capture.identity === capture.identity) close(active)
          suppressed.add(capture.identity)
        }
        return
      }
    }
  }
  ipcMain.handle(READY_CHANNEL, event => {
    const record = active
    if (!exactSender(event, record)) return reject('APPROVAL_UNTRUSTED_SENDER')
    if (record.ready) { close(record); return reject('APPROVAL_STALE') }
    if (!currentCapture(record)) { close(record); return reject('APPROVAL_STALE') }
    record.ready = true
    if (record.bootTimer) unschedule(record.bootTimer)
    record.bootTimer = null
    if (!display(record)) return reject('APPROVAL_SURFACE_UNAVAILABLE')
    record.resolveReady(true)
    return { accepted: true, nonce: record.nonce, locale: getLocale(), request: record.capture.request }
  })
  ipcMain.handle(DECISION_CHANNEL, (event, payload) => {
    const record = active
    if (!exactSender(event, record)) return reject('APPROVAL_UNTRUSTED_SENDER')
    if (!record.ready || !validFrame(payload) || Object.keys(payload).sort().join(',') !== 'decision,nonce' ||
        typeof payload.nonce !== 'string' || payload.nonce !== record.nonce ||
        !['allow', 'deny'].includes(payload.decision)) return reject('APPROVAL_INVALID_DECISION')
    if (!currentCapture(record)) { close(record); return reject('APPROVAL_STALE') }
    const request = record.capture.request
    const approved = payload.decision === 'allow'
    consumed.add(record.capture.identity)
    close(record)
    // The application client creates the command and fresh private host HMAC here.
    return client.command('ResolveApproval', { approvalId: request.approvalId,
      toolCallId: request.toolCallId, requestDigest: request.requestDigest,
      cwd: request.cwd, policyRevision: request.policyRevision, approved }, `cmd_${crypto.randomUUID()}`)
  })
  return { sync, invalidate: () => close(active),
    async reopenPending() {
      for (const pending of pendingRequests()) {
        const capture = captureApproval(client.view, pending, now())
        if (capture && !consumed.has(capture.identity)) suppressed.delete(capture.identity)
      }
      sync()
      const record = active
      const ready = !!record && (record.ready || await record.readyPromise)
      return { success: ready && active === record && !!currentCapture(record) }
    },
    updateLocale() { if (active?.ready) active.window.webContents.send(UPDATE_CHANNEL, getLocale()) },
    dispose() { disposed = true; close(active); ipcMain.removeHandler(READY_CHANNEL); ipcMain.removeHandler(DECISION_CHANNEL) } }
}

module.exports = { createApprovalSurfaceController, captureApproval, approvalSurfaceBounds,
  APPROVAL_HTML, READY_CHANNEL, DECISION_CHANNEL, UPDATE_CHANNEL }
