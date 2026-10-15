// Real Electron main/preload/React, real Python server and Application.
// Test-only process substitution scripts inference/embeddings and isolates files.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const childProcess = require('node:child_process')
const https = require('node:https')
const { EventEmitter } = require('node:events')
const electron = require('electron')
const workspace = process.env.NOVA_TEST_WORKSPACE
const realOllama = process.env.NOVA_REAL_OLLAMA_E2E === '1'
assert.ok(workspace, 'isolated test workspace required')
const repo = path.resolve(__dirname, '../..')
let backend = null
let sentCommands = []
const spawn = childProcess.spawn
childProcess.spawn = (command, args, options) => {
  if (args.includes('--server')) {
    backend = spawn(process.env.NOVA_TEST_PYTHON || command,
      realOllama ? ['-m', 'local_cli', '--server'] : [path.join(repo, 'tests/desktop_backend_fixture.py')], {
        ...options, cwd: workspace, env: { ...options.env, PYTHONPATH: repo }, windowsHide: true,
      })
    const write = backend.stdin.write.bind(backend.stdin)
    backend.stdin.write = data => {
      try { sentCommands.push(JSON.parse(String(data))) } catch {}
      return write(data)
    }
    return backend
  }
  return spawn(command, args, options)
}
// Network update checks are not part of this smoke, and must not update anything.
const get = https.get
https.get = (url, options, callback) => {
  if (String(url).includes('api.github.com')) {
    const request = new EventEmitter()
    request.setTimeout = () => request
    process.nextTick(() => {
      const response = new EventEmitter()
      response.statusCode = 200
      response.headers = {}
      callback(response)
      response.emit('data', Buffer.from('{}'))
      response.emit('end')
    })
    return request
  }
  return get(url, options, callback)
}
// Force a hidden test window; production options and preload remain unchanged.
let createdWindow = null
class HiddenWindow extends electron.BrowserWindow {
  constructor(options) { super({ ...options, show: false }); this.setSkipTaskbar(true); createdWindow = this }
}
const load = Module._load
Module._load = function (name, ...rest) {
  if (name === 'electron') return { ...electron, BrowserWindow: HiddenWindow }
  return load.call(this, name, ...rest)
}
// Isolate appData itself: production chooses userData/sessionData underneath it.
const appData = path.join(workspace, 'electron-app-data')
const legacyProfile = path.join(appData, 'local-cli-desktop')
fs.mkdirSync(legacyProfile, { recursive: true })
fs.writeFileSync(path.join(legacyProfile, 'legacy-sentinel'), 'old profile')
electron.app.setPath('appData', appData)
const configHome = process.env.XDG_CONFIG_HOME
assert.ok(configHome && path.resolve(configHome).startsWith(path.resolve(workspace) + path.sep),
  'isolated credential directory required')
const legacyAuthPath = path.join(configHome, 'local-cli', 'claude-auth.json')
const testAuth = JSON.stringify({ method: 'api_key', key: 'nova-test-placeholder', encrypted: false })
fs.mkdirSync(path.dirname(legacyAuthPath), { recursive: true })
fs.writeFileSync(legacyAuthPath, testAuth)
require('../dist-electron/main.js')
const novaProfile = path.join(appData, 'nova-desktop')
assert.equal(electron.app.getPath('userData'), novaProfile)
assert.equal(electron.app.getPath('sessionData'), novaProfile)
assert.equal(fs.readFileSync(path.join(legacyProfile, 'legacy-sentinel'), 'utf8'), 'old profile')
assert.equal(fs.existsSync(path.join(novaProfile, 'legacy-sentinel')), false)

const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(fn, label, ms = 15000) {
  const deadline = Date.now() + ms
  while (Date.now() < deadline) { const result = await fn(); if (result) return result; await delay(25) }
  throw new Error(`Timeout: ${label}`)
}
let win
const js = source => win.webContents.executeJavaScript(source, true)
const view = () => js('window.__sessionView')
async function attach() {
  await until(() => js('!!window.api'), 'preload')
  await js(`window.__seenRagProgress = []; window.api.onSessionView(v => { window.__sessionView = v; if (v.ragProgress) window.__seenRagProgress.push(v.ragProgress) }); window.api.signalReady()`)
  return until(async () => (await view())?.status.ready, 'Application snapshot')
}
async function reload() {
  const loaded = new Promise(resolve => win.webContents.once('did-finish-load', resolve))
  win.webContents.reload()
  await loaded
  await attach()
}
async function command(kind, payload) {
  return js(`window.api.applicationCommand(${JSON.stringify(kind)}, ${JSON.stringify(payload)})`)
}
async function submit(text) {
  // Exercise React input and its SubmitUserInput handler.
  const count = sentCommands.filter(f => f.command?.kind === 'SubmitUserInput').length
  await js(`(() => {
    const el = document.querySelector('textarea.input-field');
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, ${JSON.stringify(text)});
    el.dispatchEvent(new Event('input', { bubbles: true }));
  })()`)
  await delay(50)
  await js(`document.querySelector('textarea.input-field').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }))`)
  await until(() => sentCommands.filter(f => f.command?.kind === 'SubmitUserInput').length === count + 1, 'one SubmitUserInput')
}
async function idle() { await until(async () => !(await view())?.activeTurnId, 'Turn terminal') }

electron.app.whenReady().then(async () => {
  try {
    win = await until(() => createdWindow, 'BrowserWindow')
    await until(() => !win.webContents.isLoading(), 'renderer load')
    await attach()
    assert.equal((await view()).status.provider, 'ollama')

    // Legacy credentials stay untouched; only the Nova file is read.
    assert.equal((await js('window.api.getClaudeAuth()')).authenticated, false)
    const novaAuthPath = path.join(configHome, 'nova', 'claude-auth.json')
    fs.mkdirSync(path.dirname(novaAuthPath), { recursive: true })
    fs.writeFileSync(novaAuthPath, testAuth)
    assert.equal((await js('window.api.getClaudeAuth()')).authenticated, true)
    fs.unlinkSync(novaAuthPath)
    assert.equal(fs.readFileSync(legacyAuthPath, 'utf8'), testAuth)

    if (realOllama) {
      await submit('Responde exactamente NOVA_DESKTOP_OLLAMA_OK. No uses herramientas.')
      await until(async () => (await view()).messages.some(m => m.role === 'assistant' && m.content.includes('NOVA_DESKTOP_OLLAMA_OK')), 'real Ollama response', 180000)
      await idle()
      await reload()
      assert.ok((await view()).messages.some(m => m.content.includes('NOVA_DESKTOP_OLLAMA_OK')))
      assert.equal((await view()).messages.some(m => m.toolCalls?.length), false)
      console.log('NOVA_PHASE13_REAL_OLLAMA_OK: Electron + JSONL + Application + Ollama + renderer reload')
      backend?.kill()
      electron.app.exit(0)
      return
    }

    await submit('hello')
    await until(async () => (await view()).messages.some(m => m.content.includes('\u00a1Hola \u{1f9e0}!')), 'Unicode final response')
    await idle()
    const sessionId = (await view()).sessionId
    await reload()
    assert.equal((await view()).sessionId, sessionId)
    assert.ok((await view()).messages.some(m => m.content === 'hello'))

    await submit('long')
    await until(async () => (await view()).activeTurnId, 'active Turn')
    const turnId = (await view()).activeTurnId
    win.minimize()
    assert.equal(win.isMinimized(), true)
    const before = (await view()).sequence
    await until(async () => (await view()).sequence > before, 'minimized streaming')
    const conflict = await command('ChangeModel', { modelId: 'local:8b' })
    assert.equal(conflict.error.code, 'CONFLICT_ACTIVE_TURN')
    assert.equal((await view()).activeTurnId, turnId)
    await reload()
    assert.equal((await view()).activeTurnId, turnId)
    assert.ok((await view()).messages.at(-1).content.includes('texto'))
    await js(`document.querySelector('button.stop-btn').click()`)
    await idle()

    await submit('approval')
    await until(async () => (await view()).approvals.length, 'approval')
    const approvalId = (await view()).approvals[0].approvalId
    await reload()
    assert.equal((await view()).approvals[0].approvalId, approvalId)
    await js(`document.querySelector('button.confirm-deny').click()`)
    await idle()
    assert.equal(fs.existsSync(path.join(workspace, 'missing.txt')), false)

    await submit('ask')
    await until(async () => (await view()).inputs.length, 'ask_user')
    const askTurn = (await view()).activeTurnId
    await reload()
    const inputRequestId = (await view()).inputs[0].inputRequestId
    await command('ResolveUserInput', { inputRequestId, response: 'sÃ­' })
    await idle()
    assert.ok(sentCommands.some(f => f.command?.kind === 'ResolveUserInput'))
    assert.notEqual(askTurn, turnId)

    await submit('read')
    await until(async () => (await view()).messages.some(m => m.toolResults?.some(r => r.output.includes('sample file'))), 'tool result')
    await idle()
    await js(`Array.from(document.querySelectorAll('button.status-btn')).find(b => b.textContent === 'files').click()`)
    await until(() => js(`Array.from(document.querySelectorAll('.explorer-name')).some(e => e.textContent === 'sample.txt')`), 'file explorer')
    await js(`Array.from(document.querySelectorAll('.explorer-name')).find(e => e.textContent === 'sample.txt').click()`)
    await until(() => js(`document.querySelector('.file-viewer-content')?.textContent.includes('sample file')`), 'file preview')

    assert.equal((await command('ChangeModel', { modelId: 'local:8b' })).accepted, true)
    await until(async () => (await view()).status.model === 'local:8b', 'model revision')
    assert.equal((await command('ChangeProvider', { providerId: 'claude', modelId: 'local:7b' })).accepted, true)
    await until(async () => (await view()).status.provider === 'claude', 'provider switch')
    assert.ok((await view()).messages.some(m => m.content === 'hello'))
    await command('ChangeProvider', { providerId: 'ollama', modelId: 'local:7b' })

    await js(`Array.from(document.querySelectorAll('button.status-btn')).find(b => b.textContent === 'settings').click()`)
    await js(`document.querySelector('input[aria-label="Enable project retrieval"]').click()`)
    await until(() => js('window.__seenRagProgress.length'), 'RAG progress')
    await until(async () => (await view()).rag.availability === 'AVAILABLE', 'RAG available')
    await command('QueryRAG', { query: 'sample' })
    await until(async () => (await view()).ragResult?.matches?.length, 'RAG query result')
    await command('QueryRAG', { query: 'fail' })
    await until(async () => (await view()).rag.error?.code === 'RAG_BACKEND_FAILED', 'RAG nonfatal failure')
    assert.equal((await view()).rag.availability, 'UNAVAILABLE')
    await js(`document.querySelector('.settings-close').click()`)
    await submit('hello after RAG failure')
    await until(async () => (await view()).messages.some(m => m.content.includes('\u00a1Hola \u{1f9e0}! hello after')), 'conversation after RAG failure')
    await idle()
    await command('SetRAGEnabled', { enabled: false })
    await until(async () => !(await view()).rag.enabled, 'RAG deactivated')

    backend.kill()
    await until(async () => !(await view()).status.connected, 'backend crash')
    assert.ok((await view()).messages.some(m => m.content === 'hello'))
    await js(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Restart backend').click()`)
    await until(async () => (await view()).status.ready && (await view()).messages.some(m => m.content === 'hello'), 'autosave restored after restart')
    assert.notEqual((await view()).sessionId, sessionId)
    await until(async () => (await view()).gap, 'explicit restart gap')
    assert.equal((await view()).approvals.length, 0)
    assert.equal((await view()).inputs.length, 0)
    assert.equal(sentCommands.filter(f => f.command?.kind === 'StartTurn').length, 0)
    console.log('NOVA_PHASE13_ELECTRON_OK: minimized/reload/stop/approval/ask_user/files/providers/RAG/crash/restore')
    backend?.kill()
    electron.app.exit(0)
  } catch (error) {
    console.error(error.stack || error)
    try { console.error('LAST_VIEW:', JSON.stringify(await view())) } catch {}
    backend?.kill()
    electron.app.exit(1)
  }
})
