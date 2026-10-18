const { test } = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const fs = require('node:fs')
const path = require('node:path')
const { createApprovalSurfaceController, approvalSurfaceBounds, APPROVAL_HTML,
  READY_CHANNEL, DECISION_CHANNEL, UPDATE_CHANNEL } = require('../electron/approval_surface.cjs')
const { signApproval } = require('../electron/approval_host.cjs')

const request = () => ({ approvalId: 'approval', toolCallId: 'tool', turnId: 'turn', operationId: 'operation',
  name: 'bash', requestDigest: 'digest', cwd: 'C:/fixture', policyRevision: 1,
  deadline: '2030-01-01T00:01:00.000Z', arguments: { command: 'Write-Output fixture', environment: { MODE: 'fixture' } } })

function fixture(pending = request(), config = {}) {
  let clock = Date.parse('2030-01-01T00:00:00.000Z')
  let locale = 'es'
  const windows = [], handlers = new Map(), timers = new Map(), sent = []
  let timerId = 0
  class Window extends EventEmitter {
    constructor(options = {}) {
      super()
      if (options.parent && config.rejectConstructor) { config.constructorFailures = (config.constructorFailures || 0) + 1; throw new Error('fixture constructor failed') }
      this.options = options; this.destroyed = false; this.visible = false; this.bounds = options
      this.webContents = new EventEmitter()
      Object.assign(this.webContents, { mainFrame: {}, isDestroyed: () => this.destroyed,
        send: (...args) => { this.messages.push(args) }, setWindowOpenHandler: handler => { this.openHandler = handler },
        session: { setPermissionRequestHandler: handler => { this.permissionRequest = handler },
          setPermissionCheckHandler: handler => { this.permissionCheck = handler } } })
      this.messages = []; windows.push(this)
    }
    setMenu(value) { this.menu = value }
    getContentBounds() { return this.bounds }
    setBounds(value) { this.bounds = value }
    isDestroyed() { return this.destroyed }
    isVisible() { return this.visible }
    isMinimized() { return !!this.minimized }
    show() { if (this.options.parent && config.rejectShow) throw new Error('fixture show failed'); this.visible = true }
    hide() { this.visible = false }
    destroy() { this.destroyed = true; this.visible = false; this.emit('closed') }
    loadURL(url) { this.url = url; this.webContents.emit('did-start-navigation', {}, url, false, true)
      return config.rejectLoad ? Promise.reject(new Error('fixture load failed')) : Promise.resolve() }
  }
  const parent = new Window()
  parent.bounds = { x: 50, y: 50, width: 1000, height: 650 }; parent.visible = true
  const client = { view: { sessionId: 'session', status: { connected: true, ready: true }, approvals: pending ? [pending] : [] },
    command: (...args) => { sent.push(args); return Promise.resolve({ accepted: true }) } }
  const ipcMain = { handle: (channel, handler) => { assert.ok(!handlers.has(channel)); handlers.set(channel, handler) },
    removeHandler: channel => handlers.delete(channel) }
  const controller = createApprovalSurfaceController({ BrowserWindow: Window, ipcMain, client,
    getParent: () => parent, preloadPath: '/trusted/approval_preload.js', getLocale: () => locale,
    now: () => clock, setTimeout: (fn, delay) => { const id = ++timerId; timers.set(id, { fn, delay }); return id },
    clearTimeout: id => timers.delete(id) })
  const invoke = (channel, sender, payload, frame = sender.webContents.mainFrame) =>
    handlers.get(channel)({ sender: sender.webContents, senderFrame: frame }, payload)
  controller.sync()
  return { controller, client, parent, windows, handlers, timers, sent, invoke,
    child: () => windows[windows.length - 1], ready() { return invoke(READY_CHANNEL, this.child()) },
    decision(binding, decision = 'allow', child = this.child()) {
      return invoke(DECISION_CHANNEL, child, { nonce: binding.nonce, decision })
    }, setLocale: value => { locale = value }, advance: value => { clock += value } }
}

test('one host surface is created for the real pending request across repeated publishes', () => {
  const f = fixture()
  for (let i = 0; i < 10; i++) f.controller.sync()
  assert.equal(f.windows.length, 2)
  assert.equal(f.child().options.parent, f.parent)
  assert.equal(f.child().options.modal, false)
  const binding = f.ready()
  assert.equal(binding.accepted, true)
  assert.deepEqual(binding.request, request())
  assert.equal(binding.locale, 'es')
  assert.equal(f.child().isVisible(), true)
  assert.equal('hostApprovalProof' in binding, false)
  assert.equal('sessionId' in binding, false)
  assert.match(binding.nonce, /^[a-f0-9]{64}$/)
})

test('one human allow dispatches once using the host-captured exact response and a fresh command', async () => {
  const f = fixture(), binding = f.ready(), child = f.child(), signed = []
  f.client.command = (kind, payload, commandId) => {
    f.sent.push([kind, payload, commandId])
    signed.push(signApproval('ab'.repeat(32), { kind, payload, commandId, sessionId: f.client.view.sessionId }))
    return new Promise(() => {})
  }
  f.decision(binding)
  f.decision(binding, 'allow', child)
  f.controller.reopenPending()
  f.controller.sync()
  assert.equal(f.sent.length, 1)
  assert.deepEqual(f.sent[0].slice(0, 2), ['ResolveApproval', { approvalId: 'approval', toolCallId: 'tool',
    requestDigest: 'digest', cwd: 'C:/fixture', policyRevision: 1, approved: true }])
  assert.match(f.sent[0][2], /^cmd_[a-f0-9-]{36}$/)
  assert.equal(signed[0].length, 64)
  assert.equal(child.isDestroyed(), true)
  assert.equal(f.windows.length, 2)
})

test('an explicit deny is exactly one false resolution and has no second native prompt', async () => {
  const f = fixture(), binding = f.ready()
  await f.decision(binding, 'deny')
  assert.equal(f.sent.length, 1)
  assert.equal(f.sent[0][1].approved, false)
  assert.equal(f.child().isDestroyed(), true)
})

for (const [field, value] of [['approvalId', 'other'], ['toolCallId', 'other'], ['turnId', 'other'],
  ['operationId', 'other'], ['requestDigest', 'other'], ['cwd', 'C:/other'], ['policyRevision', 2],
  ['deadline', '2030-01-01T00:02:00.000Z'], ['name', 'other'], ['arguments', { command: 'different' }]]) {
  test('a changed pending ' + field + ' closes without dispatch', () => {
    const f = fixture(), binding = f.ready(), child = f.child()
    f.client.view.approvals[0][field] = value
    const result = f.decision(binding)
    assert.equal(result.accepted, false)
    assert.equal(f.sent.length, 0)
    assert.equal(child.isDestroyed(), true)
  })
}

test('publish invalidates changed arguments; explicit review captures them into a new child and nonce', async () => {
  const f = fixture(), first = f.ready(), old = f.child()
  f.client.view.approvals[0].arguments.command = 'changed'
  f.controller.sync(); f.controller.sync()
  assert.equal(old.isDestroyed(), true)
  assert.equal(f.windows.length, 2)
  const review = f.controller.reopenPending()
  const next = f.ready()
  assert.equal((await review).success, true)
  assert.notEqual(first.nonce, next.nonce)
  assert.equal(next.request.arguments.command, 'changed')
  assert.equal(f.decision(first, 'allow', old).accepted, false)
  assert.equal(f.sent.length, 0)
})

for (const mutation of ['session', 'removed', 'disconnect', 'not-ready', 'deadline']) {
  test('live ' + mutation + ' invalidates consent before dispatch', () => {
    const f = fixture(), binding = f.ready(), child = f.child()
    if (mutation === 'session') f.client.view.sessionId = 'other'
    if (mutation === 'removed') f.client.view.approvals = []
    if (mutation === 'disconnect') f.client.view.status.connected = false
    if (mutation === 'not-ready') f.client.view.status.ready = false
    if (mutation === 'deadline') f.advance(60000)
    assert.equal(f.decision(binding).accepted, false)
    assert.equal(f.sent.length, 0)
    assert.equal(child.isDestroyed(), true)
  })
}

test('deadline timer closes the surface without needing another host publish', () => {
  const f = fixture(), child = f.child()
  f.ready(); f.advance(60000)
  for (const timer of f.timers.values()) timer.fn()
  assert.equal(child.isDestroyed(), true)
  assert.equal(f.sent.length, 0)
})

test('principal renderer, other windows and cross-frame callers cannot bind or resolve', () => {
  const f = fixture(), child = f.child()
  assert.equal(f.invoke(READY_CHANNEL, f.parent).accepted, false)
  assert.equal(f.invoke(READY_CHANNEL, child, undefined, {}).accepted, false)
  const binding = f.ready()
  assert.equal(f.invoke(DECISION_CHANNEL, f.parent, { nonce: binding.nonce, decision: 'allow' }).accepted, false)
  assert.equal(f.invoke(DECISION_CHANNEL, child, { nonce: binding.nonce, decision: 'allow' }, {}).accepted, false)
  assert.equal(f.sent.length, 0)
  assert.equal(child.isDestroyed(), false)
})

test('malformed, oversized, wrong-nonce and boolean decisions do not resolve', () => {
  const f = fixture(), binding = f.ready(), child = f.child()
  const circular = {}; circular.self = circular
  for (const payload of [null, [], true, circular, { nonce: binding.nonce, approved: true },
    { nonce: binding.nonce, decision: true }, { nonce: 'wrong', decision: 'allow' },
    { nonce: binding.nonce, decision: 'allow', approvalId: 'approval' },
    { nonce: binding.nonce, decision: 'x'.repeat(131073) }]) {
    assert.equal(f.invoke(DECISION_CHANNEL, child, payload).accepted, false)
  }
  assert.equal(f.sent.length, 0)
  assert.equal(child.isDestroyed(), false)
})

test('a child close preserves pending, suppresses repeats and explicit review uses a fresh binding', () => {
  const f = fixture(), first = f.ready(), old = f.child()
  old.destroy(); f.controller.sync(); f.controller.sync()
  assert.equal(f.client.view.approvals.length, 1)
  assert.equal(f.windows.length, 2)
  assert.equal(f.sent.length, 0)
  f.controller.reopenPending()
  const next = f.ready()
  assert.notEqual(next.nonce, first.nonce)
  assert.equal(f.decision(first, 'allow', old).accepted, false)
})

test('child reload revokes its binding while principal renderer reload leaves independent surface intact', () => {
  const f = fixture(), binding = f.ready(), child = f.child()
  f.parent.webContents.emit('did-start-loading')
  f.controller.sync()
  assert.equal(child.isDestroyed(), false)
  child.webContents.emit('did-start-navigation', {}, child.url, false, true)
  assert.equal(child.isDestroyed(), true)
  assert.equal(f.decision(binding, 'allow', child).accepted, false)
  assert.equal(f.sent.length, 0)
})

test('surface sandbox, fixed CSP and navigation restrictions block remote content', () => {
  const f = fixture(), child = f.child(), prefs = child.options.webPreferences
  assert.equal(prefs.sandbox, true); assert.equal(prefs.contextIsolation, true)
  assert.equal(prefs.nodeIntegration, false); assert.equal(prefs.nodeIntegrationInSubFrames, false)
  assert.equal(prefs.nodeIntegrationInWorker, false); assert.equal(prefs.devTools, false)
  assert.equal(prefs.webviewTag, false); assert.equal(prefs.webSecurity, true)
  assert.equal(prefs.preload, '/trusted/approval_preload.js')
  assert.match(child.url, /^data:text\/html/)
  assert.match(APPROVAL_HTML, /default-src 'none'/)
  assert.match(APPROVAL_HTML, /script-src 'none'/)
  assert.match(APPROVAL_HTML, /connect-src 'none'/)
  assert.doesNotMatch(APPROVAL_HTML, /<script|<iframe|onload=|onclick=/i)
  assert.deepEqual(child.openHandler({ url: 'https://example.com' }), { action: 'deny' })
  for (const name of ['will-navigate', 'will-frame-navigate', 'will-attach-webview']) {
    let blocked = false
    child.webContents.emit(name, { preventDefault: () => { blocked = true } }, 'https://example.com')
    assert.equal(blocked, true)
  }
  let permission = true
  child.permissionRequest(null, 'media', granted => { permission = granted })
  assert.equal(permission, false); assert.equal(child.permissionCheck(), false)
})

test('host bounds track parent above composer; hide/minimize never leave floating approval', () => {
  const f = fixture(), child = f.child()
  f.ready()
  for (const height of [400, 650, 1000]) {
    f.parent.bounds = { x: 100, y: 80, width: 600, height }
    f.parent.emit('resize')
    const b = child.bounds
    assert.ok(b.y >= 80 && b.x >= 100)
    assert.ok(b.y + b.height <= 80 + height - 146)
    assert.deepEqual(b, approvalSurfaceBounds(f.parent))
  }
  f.parent.visible = false; f.parent.emit('hide'); assert.equal(child.isVisible(), false)
  f.parent.visible = true; f.parent.emit('show'); assert.equal(child.isVisible(), true)
  f.parent.minimized = true; f.parent.emit('minimize'); assert.equal(child.isVisible(), false)
})

test('host locale changes update the isolated surface without another window', () => {
  const f = fixture(); f.ready(); f.setLocale('en'); f.controller.updateLocale()
  assert.deepEqual(f.child().messages, [[UPDATE_CHANNEL, 'en']])
  assert.equal(f.windows.length, 2)
})

test('malformed or absent pending requests cannot create a surface', () => {
  const bad = [null, {}, { ...request(), deadline: null }, { ...request(), deadline: 'invalid' },
    { ...request(), deadline: '2029-01-01T00:00:00.000Z' }, { ...request(), turnId: '' },
    { ...request(), operationId: '' }, { ...request(), arguments: [] }]
  for (const pending of bad) { const f = fixture(pending); assert.equal(f.windows.length, 1); f.controller.dispose() }
})

test('isolated preload inserts request data only as text and exposes no renderer bridge', () => {
  const source = fs.readFileSync(path.join(__dirname, '../electron/approval_preload.ts'), 'utf8')
  assert.match(source, /event\.isTrusted/)
  assert.match(source, /\.textContent = JSON\.stringify\(binding\.request\.arguments/)
  assert.doesNotMatch(source, /innerHTML|insertAdjacentHTML|eval\(|executeJavaScript|exposeInMainWorld/)
})

test('dispose revokes bindings, closes child and removes only its own IPC handlers', () => {
  const f = fixture(), child = f.child()
  f.controller.dispose()
  assert.equal(child.isDestroyed(), true)
  assert.equal(f.handlers.size, 0)
  assert.equal(f.sent.length, 0)
})

test('review succeeds only after the real child READY and reuses an already ready surface', async () => {
  const f = fixture()
  let settled = false
  const review = f.controller.reopenPending().then(result => { settled = true; return result })
  await Promise.resolve()
  assert.equal(settled, false)
  f.ready()
  assert.deepEqual(await review, { success: true })
  assert.deepEqual(await f.controller.reopenPending(), { success: true })
  assert.equal(f.windows.length, 2)
})

test('failed document load resolves explicit review false without consent or retries', async () => {
  const f = fixture(request(), { rejectLoad: true }), child = f.child()
  const review = f.controller.reopenPending()
  assert.deepEqual(await review, { success: false })
  assert.equal(child.isDestroyed(), true)
  f.controller.sync()
  assert.equal(f.windows.length, 2)
  assert.equal(f.sent.length, 0)
})

test('missing preload READY times out, closes and resolves explicit review false', async () => {
  const f = fixture(), child = f.child()
  const review = f.controller.reopenPending()
  const boot = [...f.timers.values()].find(timer => timer.delay === 5000)
  assert.ok(boot)
  boot.fn()
  assert.deepEqual(await review, { success: false })
  assert.equal(child.isDestroyed(), true)
  assert.equal(f.sent.length, 0)
  f.controller.sync()
  assert.equal(f.windows.length, 2)
})

test('closing before READY resolves explicit review false', async () => {
  const f = fixture()
  const review = f.controller.reopenPending()
  f.child().destroy()
  assert.deepEqual(await review, { success: false })
  assert.equal(f.sent.length, 0)
})

test('recovering projection blocks READY, consent and review until a fresh explicit review', async () => {
  const first = fixture(), firstChild = first.child()
  first.client.view.recovering = true
  assert.equal(first.ready().accepted, false)
  assert.equal(firstChild.isDestroyed(), true)
  assert.deepEqual(await first.controller.reopenPending(), { success: false })
  assert.equal(first.sent.length, 0)

  const f = fixture(), binding = f.ready(), old = f.child()
  f.client.view.recovering = true
  assert.equal(f.decision(binding).accepted, false)
  assert.equal(old.isDestroyed(), true)
  f.client.view.recovering = false
  f.controller.sync()
  assert.equal(f.windows.length, 2)
  const review = f.controller.reopenPending(), next = f.ready()
  assert.deepEqual(await review, { success: true })
  assert.notEqual(next.nonce, binding.nonce)
  assert.equal(f.sent.length, 0)
})

test('native constructor failure is contained without dispatch or automatic retries', async () => {
  const config = { rejectConstructor: true }, f = fixture(request(), config)
  assert.equal(f.windows.length, 1)
  assert.equal(config.constructorFailures, 1)
  for (let i = 0; i < 10; i++) f.controller.sync()
  assert.equal(config.constructorFailures, 1)
  assert.deepEqual(await f.controller.reopenPending(), { success: false })
  assert.equal(config.constructorFailures, 2)
  assert.equal(f.sent.length, 0)
})

test('native show failure revokes READY binding and resolves review false', async () => {
  const f = fixture(request(), { rejectShow: true }), child = f.child()
  const review = f.controller.reopenPending()
  const binding = f.ready()
  assert.equal(binding.accepted, false)
  assert.equal(binding.error.code, 'APPROVAL_SURFACE_UNAVAILABLE')
  assert.deepEqual(await review, { success: false })
  assert.equal(child.isDestroyed(), true)
  f.controller.sync()
  assert.equal(f.windows.length, 2)
  assert.equal(f.sent.length, 0)
})
