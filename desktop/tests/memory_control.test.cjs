require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { DesktopApplicationClient } = require('../electron/application_client.ts')
const { memoryControl } = require('../electron/memory_control.cjs')
const { signApproval } = require('../electron/approval_host.cjs')

function setup(authenticated = true) {
  const sent = [], views = [], proofs = []
  const client = new DesktopApplicationClient(f => sent.push(f), v => views.push(v),
    authenticated ? command => { proofs.push(command); return signApproval('ab'.repeat(32), command) } : undefined)
  client.receive({ type: 'ready', sessionId: 'synthetic-session', tools: [] })
  client.receive({ type: 'snapshot', id: sent.at(-1).id, data: {
    sessionId: 'synthetic-session', workspace: '/synthetic', stateRevision: 1, lastSequence: 1,
    transcript: [], turns: [], modelRuntime: { modelId: 'synthetic', providerId: 'ollama', providerRevision: 1 },
    services: { rag: { enabled: false, availability: 'DISABLED' }, interactions: { approvals: [], inputs: [] } },
  } })
  return { client, sent, views, proofs }
}

test('explicit host memory request is signed/correlated, not a user Turn or optimistic transcript', async () => {
  const c = setup()
  const pending = c.client.memory('memory_remember', { kind: 'PREFERENCE', text: 'Synthetic preference' }, 'memory-cmd')
  const frame = c.sent.at(-1)
  assert.equal(frame.type, 'memory_command')
  assert.equal(frame.command.kind, 'MemoryControl')
  assert.equal(frame.command.expectedRevision, 1)
  assert.equal(frame.command.sessionId, 'synthetic-session')
  assert.equal(frame.hostMemoryProof, signApproval('ab'.repeat(32), frame.command))
  assert.notEqual(frame.hostMemoryProof, signApproval('ab'.repeat(32), { ...frame.command, kind: 'ResolveApproval' }))
  assert.deepEqual(c.client.view.messages, [])
  assert.equal(c.sent.filter(f => f.type === 'application_command').length, 0)
  c.client.receive({ type: 'memory_result', id: frame.id, data: {
    schemaVersion: 1, commandId: 'memory-cmd', completed: true, operationId: 'op', data: { memoryId: 'mem', revision: 1 },
  } })
  assert.equal((await pending).data.memoryId, 'mem')
  assert.deepEqual(c.client.view.messages, [])
})

test('inspection payload is returned to its caller, never retained in the chat projection or pending map', async () => {
  const c = setup()
  const pending = c.client.memory('memory_show', { memoryId: 'fixture' })
  const frame = c.sent.at(-1)
  const data = { record: { canonicalText: 'Synthetic private memory content' } }
  c.client.receive({ type: 'memory_result', id: frame.id, data: { schemaVersion: 1, completed: true, data } })
  assert.deepEqual((await pending).data, data)
  assert.equal(c.client.memoryPending.size, 0)
  assert.ok(!JSON.stringify(c.client.view).includes('Synthetic private memory content'))
  assert.ok(!JSON.stringify(c.views).includes('Synthetic private memory content'))
})

test('unauthenticated host and unknown commands do not send a memory frame', async () => {
  const c = setup(false)
  assert.equal((await c.client.memory('memory_export', {})).error.code, 'MEMORY_UNAVAILABLE')
  assert.equal((await c.client.memory('auto_capture', {})).completed, false)
  assert.equal(c.sent.filter(f => f.type === 'memory_command').length, 0)
})

test('disconnect and broken pipe report unknown outcome without retry', async () => {
  for (const brokenPipe of [false, true]) {
    const c = setup()
    if (brokenPipe) c.client.send = () => false
    const pending = c.client.memory('memory_forget', { memoryId: 'fixture', revision: 1 }, 'delete-cmd')
    if (!brokenPipe) c.client.disconnected()
    const result = await pending
    assert.equal(result.commandId, 'delete-cmd')
    assert.equal(result.error.code, 'OUTCOME_UNKNOWN')
    assert.equal(result.error.retryable, false)
    assert.equal(c.client.memoryPending.size, 0)
    assert.equal(c.sent.filter(f => f.type === 'memory_command').length, brokenPipe ? 0 : 1)
  }
})

test('normal explicit write has no redundant dialog; sensitive consent requires exact host dialog', async () => {
  const calls = [], dialogs = []
  const client = { view: { sessionId: 's', workspace: '/w', stateRevision: 4, status: { ready: true } },
    memory: async (...args) => { calls.push(args); return { schemaVersion: 1, completed: true } } }
  const dialog = async request => { dialogs.push(request); return { response: 1 } }
  assert.equal((await memoryControl(client, 'memory_remember', { text: 'normal' }, 'normal', dialog)).completed, true)
  assert.equal(dialogs.length, 0)
  const args = { text: 'Synthetic health datum', consentSensitive: true }
  assert.equal((await memoryControl(client, 'memory_remember', args, 'sensitive', dialog)).completed, true)
  assert.equal(dialogs.length, 1)
  assert.deepEqual(dialogs[0], { name: 'memory_remember', workspace: '/w', write: true })
  assert.ok(!JSON.stringify(dialogs).includes(args.text))
  assert.equal(calls[1][2], 'sensitive')
})

test('sensitive reveal/export cancellation never dispatches; consent is not reused', async () => {
  let count = 0, sent = 0
  const client = { view: { sessionId: 's', workspace: '/w', stateRevision: 1, status: { ready: true } },
    memory: async () => { sent++; return { schemaVersion: 1, completed: true } } }
  const dialog = async () => ({ response: count++ === 0 ? 1 : 0 })
  const args = { includeSensitive: true }
  assert.equal((await memoryControl(client, 'memory_export', args, 'first', dialog)).completed, true)
  assert.equal((await memoryControl(client, 'memory_export', args, 'second', dialog)).error.code, 'MEMORY_SENSITIVE_DENIED')
  assert.equal(count, 2)
  assert.equal(sent, 1)
})

test('confirmation binds frozen arguments and session/workspace/revision; stale consent cannot dispatch', async () => {
  for (const field of ['sessionId', 'workspace', 'stateRevision']) {
    let sent = 0
    const client = { view: { sessionId: 's', workspace: '/w', stateRevision: 1, status: { ready: true } },
      memory: async () => { sent++; return { schemaVersion: 1, completed: true } } }
    const result = await memoryControl(client, 'memory_correct', { consentSensitive: true }, 'correct', async () => {
      client.view[field] = field === 'stateRevision' ? 2 : 'changed'
      return { response: 1 }
    })
    assert.equal(result.error.code, 'REVISION_CONFLICT')
    assert.equal(sent, 0)
  }
  const args = { text: 'Original synthetic datum', consentSensitive: true }
  let delivered
  const client = { view: { sessionId: 's', workspace: '/w', stateRevision: 1, status: { ready: true } },
    memory: async (_, frozen) => { delivered = frozen; return { schemaVersion: 1, completed: true } } }
  await memoryControl(client, 'memory_remember', args, 'freeze', async () => { args.text = 'Changed'; return { response: 1 } })
  assert.equal(delivered.text, 'Original synthetic datum')
})

test('renderer cannot inject a raw memory frame; preload exposes only a shared host control', () => {
  const main = fs.readFileSync(path.join(__dirname, '../electron/main.ts'), 'utf8')
  const preload = fs.readFileSync(path.join(__dirname, '../electron/preload.ts'), 'utf8')
  assert.match(main, /data.type === 'memory_command'/)
  assert.match(main, /ipcMain.handle\('memory-command'/)
  assert.match(main, /validApplicationSender\(event\)/)
  assert.match(preload, /memoryCommand:[\s\S]*ipcRenderer.invoke\('memory-command'/)
})
