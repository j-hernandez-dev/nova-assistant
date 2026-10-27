const crypto = require('node:crypto')
const { stableJson, validFrame } = require('./approval_host.cjs')
const { surfaceDocument, surfaceScale, surfaceBounds, applySurfaceZoom } = require('./surface_appearance.cjs')
const READY = 'question-surface-ready', DECIDE = 'question-surface-decision', LOCALE = 'question-surface-locale'
// Match the host confirmation: inline NOVA heading, fine border and filled gold action.
const HTML = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none';script-src 'none';style-src 'unsafe-inline';connect-src 'none';img-src 'none';object-src 'none';base-uri 'none';form-action 'none'"><title>Nova</title><style>
html{color-scheme:dark}*{box-sizing:border-box}html,body{margin:0;height:100%;background:#151413;color:#ede9e3;font:14px/1.55 system-ui,sans-serif}body{border:1px solid #9b7b50;border-radius:12px;overflow:hidden}main{display:flex;flex-direction:column;gap:16px;height:100%;padding:24px}header{display:flex;align-items:center;gap:12px}.mark{color:#d5ad71;font-weight:700;font-size:13px}h1{font-size:18px;margin:0}.content{flex:1;overflow:auto;min-height:0;padding:5px;margin:-5px;scrollbar-gutter:stable;overscroll-behavior:contain}#question{margin:0 0 16px;color:#c9c2b7;white-space:pre-wrap;overflow-wrap:anywhere;max-height:140px;overflow:auto}label{display:block;margin-bottom:7px;color:#c9c2b7;font-size:13px}textarea{display:block;width:100%;height:96px;min-height:70px;max-height:180px;resize:vertical;border:1px solid #494035;border-radius:7px;padding:10px 12px;background:#100f0e;color:#ede9e3;font:inherit}#hint,#status{font-size:11px;margin:7px 0 0;color:#a79b89}#status[role=alert]{color:#e3b583}footer{display:flex;justify-content:flex-end;gap:10px;flex-shrink:0}button{padding:9px 18px;border:1px solid #796548;border-radius:8px;background:#30291f;color:#f5f0e8;font:inherit;cursor:pointer}#send{background:#d5ad71;color:#1c170f;font-weight:600}button:focus-visible,textarea:focus-visible{outline:2px solid #d5ad71;outline-offset:3px}button:disabled,textarea:disabled{opacity:.5;cursor:default}
textarea{caret-color:#d5ad71}textarea:focus{border-color:#d5ad71}
@media(max-height:340px){main{padding:18px;gap:12px}#question{max-height:70px;margin-bottom:10px}textarea{height:72px}}
</style></head><body><main role="dialog" aria-modal="true" aria-labelledby="heading"><header><span class="mark">NOVA</span><h1 id="heading"></h1></header><div class="content"><p id="question"></p><label id="answer-label" for="answer"></label><textarea id="answer" disabled aria-describedby="question hint"></textarea><p id="hint"></p><p id="status" role="status" aria-live="polite"></p></div><footer><button id="stop" disabled></button><button id="send" disabled></button></footer></main></body></html>`
function captureQuestion(view, now = Date.now()) {
  const request = view?.inputs?.[0]
  if (!view?.status?.ready || !view.status.connected || view.recovering || view.gap ||
      typeof view.sessionId !== 'string' || !view.sessionId || !request ||
      typeof request.inputRequestId !== 'string' || !request.inputRequestId ||
      typeof request.turnId !== 'string' || request.turnId !== view.activeTurnId ||
      typeof request.question !== 'string' || !request.question) return null
  const deadline = request.deadline == null ? null : Date.parse(request.deadline)
  if (deadline !== null && (!Number.isFinite(deadline) || now >= deadline)) return null
  const copy = JSON.parse(JSON.stringify(request))
  return { request: copy, deadline, identity: stableJson([view.sessionId, request.inputRequestId]),
    fingerprint: stableJson([view.sessionId, view.workspace, view.activeTurnId, copy]) }
}
function questionBounds(parent) {
  return surfaceBounds(parent,640,400)
}
function createQuestionSurface({ BrowserWindow, ipcMain, client, getParent, getLocale, preloadPath,
  getPresentation,
  canOpen = () => true, now = Date.now, setTimeout: schedule = setTimeout, clearTimeout: cancel = clearTimeout }) {
  let active = null, disposed = false
  const suppressed = new Set(), consumed = new Set()
  const sender = (event, record) => !!record && !record.window.isDestroyed() && event.sender === record.window.webContents && event.senderFrame === record.window.webContents.mainFrame
  const current = record => captureQuestion(client.view, now())?.fingerprint === record.capture.fingerprint
  function close(record, suppress = true) {
    if (!record || active !== record) return
    active = null
    if (suppress) suppressed.add(record.capture.identity)
    cancel(record.bootTimer); cancel(record.timer); record.resolveReady(false)
    for (const [name, listener] of record.listeners) record.parent.removeListener(name, listener)
    if (!record.window.isDestroyed()) record.window.destroy()
  }
  function display(record) {
    if (active !== record || !current(record) || record.parent.isDestroyed()) return close(record)
    if (!canOpen()) return close(record, false)
    if (!record.ready) return
    if (!record.parent.isVisible() || record.parent.isMinimized()) { record.window.hide(); return }
    try { applySurfaceZoom(record.window,record.parent);record.window.setBounds(questionBounds(record.parent)); if (!record.window.isVisible()) record.window.show() }
    catch { close(record) }
  }
  function create(capture, parent) {
    const child = new BrowserWindow({ ...questionBounds(parent), parent, modal: true, frame: false, show: false,
      resizable: false, movable: false, minimizable: false, maximizable: false, fullscreenable: false,
      skipTaskbar: true, title: 'Nova', backgroundColor: getPresentation?.()?.variables?.['--panel'] || '#151413',
      webPreferences: { preload: preloadPath, sandbox: true, contextIsolation: true, nodeIntegration: false,zoomFactor:surfaceScale(parent),
        webviewTag: false, nodeIntegrationInSubFrames: false, nodeIntegrationInWorker: false, devTools: false,
        webSecurity: true, disableDialogs: true, partition: 'nova-question-surface' } })
    let resolveReady
    const readyPromise = new Promise(resolve => { resolveReady = resolve })
    const record = { window: child, parent, capture, nonce: crypto.randomBytes(32).toString('hex'),
      ready: false, readyPromise, resolveReady, listeners: [], bootTimer: null, timer: null, answerPending: false, stopPending: false }
    active = record
    child.setMenu(null); child.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    child.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false))
    child.webContents.session.setPermissionCheckHandler(() => false)
    const prevent = event => event.preventDefault()
    for (const name of ['will-navigate', 'will-frame-navigate', 'will-attach-webview']) child.webContents.on(name, prevent)
    let started = false
    child.webContents.on('did-start-navigation', (_event, _url, _inPlace, main) => { if (!main) return; if (started) close(record); else started = true })
    child.webContents.on('render-process-gone', () => close(record)); child.on('closed', () => close(record))
    for (const name of ['move', 'resize', 'maximize', 'unmaximize', 'show', 'restore']) {
      const listener = () => display(record); parent.on(name, listener); record.listeners.push([name, listener])
    }
    for (const name of ['hide', 'minimize']) {
      const listener = () => { if (!child.isDestroyed()) child.hide() }; parent.on(name, listener); record.listeners.push([name, listener])
    }
    const parentClosed = () => close(record); parent.on('closed', parentClosed); record.listeners.push(['closed', parentClosed])
    record.bootTimer = schedule(() => close(record), 5000); record.bootTimer?.unref?.()
    if (capture.deadline !== null) {
      const expire = () => {
        if (active !== record) return
        const remaining = capture.deadline - now()
        if (remaining <= 0) close(record)
        else { record.timer = schedule(expire, Math.min(remaining, 2147483647)); record.timer?.unref?.() }
      }
      expire()
    }
    Promise.resolve(child.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(surfaceDocument(HTML, getPresentation?.())))).catch(() => close(record))
  }
  function sync() {
    if (disposed) return
    const capture = captureQuestion(client.view, now())
    for (const identities of [suppressed, consumed]) for (const id of identities) if (id !== capture?.identity) identities.delete(id)
    if (active) {
      if (!current(active) || getParent() !== active.parent || active.parent.isDestroyed()) close(active)
      else if (!canOpen()) close(active, false)
      else { display(active); return }
    }
    const parent = getParent()
    if (!capture || consumed.has(capture.identity) || suppressed.has(capture.identity) || !canOpen() ||
        !parent || parent.isDestroyed() || !parent.isVisible() || parent.isMinimized()) return
    try { create(capture, parent) } catch { suppressed.add(capture.identity); if (active) close(active) }
  }
  ipcMain.handle(READY, event => {
    const record = active
    if (!sender(event, record) || record.ready || !current(record) || !canOpen()) return { accepted: false }
    record.ready = true; cancel(record.bootTimer); display(record)
    if (active !== record) return { accepted: false }
    record.resolveReady(true)
    return { accepted: true, nonce: record.nonce, question: record.capture.request.question, locale: getLocale(), presentation: getPresentation?.() }
  })
  ipcMain.handle(DECIDE, async (event, payload) => {
    const record = active
    if (!sender(event, record) || !record.ready || !validFrame(payload) || payload.nonce !== record.nonce || !current(record) || !canOpen()) return { accepted: false }
    const answering = payload.action === 'answer', stopping = payload.action === 'stop'
    if ((!answering && !stopping) || Object.keys(payload).sort().join(',') !== (answering ? 'action,nonce,response' : 'action,nonce') ||
        (answering && (record.answerPending || record.stopPending || typeof payload.response !== 'string' || !payload.response.trim())) ||
        (stopping && record.stopPending)) return { accepted: false }
    if (answering) record.answerPending = true; else record.stopPending = true
    try {
      const request = record.capture.request
      const result = await client.command(answering ? 'ResolveUserInput' : 'CancelTurn',
        answering ? { inputRequestId: request.inputRequestId, response: payload.response } : { turnId: request.turnId }, 'cmd_' + crypto.randomUUID())
      if (result?.accepted) { consumed.add(record.capture.identity); close(record, false); return { accepted: true } }
      return { accepted: false }
    } catch { return { accepted: false } }
    finally { if (answering) record.answerPending = false; else record.stopPending = false }
  })
  return { sync, invalidate: () => close(active),
    async reopenPending() {
      const capture = captureQuestion(client.view, now())
      if (capture && !consumed.has(capture.identity)) suppressed.delete(capture.identity)
      sync(); const record = active
      const ready = !!record && (record.ready || await record.readyPromise)
      return { success: ready && active === record && current(record) }
    },
    updateLocale() { if (active?.ready) active.window.webContents.send(LOCALE, getLocale()) },
    updateAppearance() { if (active && !active.window.isDestroyed()) {
      applySurfaceZoom(active.window,active.parent);active.window.setBounds(questionBounds(active.parent))
      const presentation = getPresentation?.()
      if (presentation?.variables?.['--panel']) active.window.setBackgroundColor?.(presentation.variables['--panel'])
      if (active.ready) active.window.webContents.send('question-surface-appearance', presentation)
    } },
    dispose() { disposed = true; close(active); ipcMain.removeHandler(READY); ipcMain.removeHandler(DECIDE) } }
}
module.exports = { createQuestionSurface, captureQuestion, questionBounds, HTML, READY, DECIDE, LOCALE }
