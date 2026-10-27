require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { DesktopApplicationClient, projectTranscript } = require('../electron/application_client.ts')

test('source input reports come from the user Turn projection and retain host availability', () => {
  const sourceContext = [{sourceId:'one',revisionId:'r1',displayName:'Guide.txt',status:'complete'},
    {sourceId:'two',revisionId:'r2',displayName:'Book.pdf',status:'partial',admittedChunks:1},
    {sourceId:'three',revisionId:'r3',displayName:'Revoked.txt',status:'unavailable',errorCode:'STALE_SOURCE'}]
  const rows = projectTranscript([{role:'user',content:'Explain my sources',sourceContext},
    {role:'assistant',content:'Answer',sourceContext}], 'test')
  assert.deepEqual(rows[0].sourceContext,sourceContext)
  assert.equal(rows[1].sourceContext,undefined)
  assert.deepEqual(projectTranscript([{role:'user',content:'x',sourceContext:[{status:'success'},null]}],'test')[0].sourceContext,[])
})

test('Auxiliary model errors stay in their owning panel only after exact outbound request registration', () => {
  for (const type of ['catalog', 'recommend', 'pull_model', 'delete_model', 'update_catalog']) {
    const client = new DesktopApplicationClient(() => {}, () => {})
    assert.equal(client.trackModelRequest({ id: 51, type }), true)
    client.receive({ id: 51, type: 'error', message: 'private auxiliary exception' })
    assert.equal(client.view.error, null)
    // Tracking is consumed, so an unrelated later error cannot inherit it.
    client.receive({ id: 51, type: 'error', code: 'UNRELATED_ERROR', message: 'general error' })
    assert.equal(client.view.error.code, 'UNRELATED_ERROR')
    client.disconnected()
  }
})
test('Unregistered, mismatched, general, and Application command errors remain visible', async () => {
  const c = setup()
  assert.equal(c.client.trackModelRequest({ id: 51, type: 'catalog' }), true)
  c.client.receive({ id: 52, type: 'error', code: 'GENERAL_ERROR', message: 'visible' })
  assert.equal(c.client.view.error.code, 'GENERAL_ERROR')
  const pending = c.client.command('CancelTurn', { turnId: 'turn' }, 'owned-command')
  const id = c.sent.at(-1).id
  assert.equal(c.client.trackModelRequest({ id, type: 'catalog' }), false)
  c.client.receive({ id, type: 'error', code: 'POLICY_DENIED', message: 'Application denial' })
  assert.equal((await pending).error.code, 'POLICY_DENIED')
  assert.equal(c.client.view.error.code, 'POLICY_DENIED')
  c.client.receive({ type: 'error', code: 'GENERAL_NO_ID', message: 'visible' })
  assert.equal(c.client.view.error.code, 'GENERAL_NO_ID')
  c.client.disconnected()
})
test('Exact terminal receipts clear auxiliary ownership while progress and wrong terminals do not', () => {
  const client = new DesktopApplicationClient(() => {}, () => {})
  client.trackModelRequest({ id: 9, type: 'pull_model' })
  client.receive({ id: 9, type: 'pull_progress', completed: 1, total: 2 })
  client.receive({ id: 9, type: 'catalog' })
  client.receive({ id: 9, type: 'error', message: 'owned download failed' })
  assert.equal(client.view.error, null)
  for (const [type, terminal] of [['catalog','catalog'], ['recommend','recommend'],
    ['pull_model','pull_done'], ['delete_model','delete_done'], ['update_catalog','catalog_updated']]) {
    client.trackModelRequest({ id: 10, type })
    client.receive({ id: 10, type: terminal })
    client.receive({ id: 10, type: 'error', code: 'LATE_UNRELATED_ERROR', message: 'visible' })
    assert.equal(client.view.error.code, 'LATE_UNRELATED_ERROR')
  }
  client.disconnected()
})
test('Backend disconnect and ready clear auxiliary bindings without hiding disconnect outcome', () => {
  const client = new DesktopApplicationClient(() => {}, () => {})
  client.trackModelRequest({ id: 18, type: 'recommend' })
  client.disconnected(); assert.equal(client.view.error.code, 'BACKEND_DISCONNECTED')
  client.receive({ id: 18, type: 'error', code: 'OLD_CONNECTION_ERROR' })
  assert.equal(client.view.error.code, 'OLD_CONNECTION_ERROR')
  client.trackModelRequest({ id: 19, type: 'catalog' })
  client.receive({ type: 'ready', sessionId: 'new-session', tools: [] })
  client.receive({ id: 19, type: 'error', code: 'OLD_READY_ERROR' })
  assert.equal(client.view.error.code, 'OLD_READY_ERROR')
  client.disconnected()
})
test('Only exact known model request types and unique numeric IDs may own auxiliary errors', () => {
  const client = new DesktopApplicationClient(() => {}, () => {})
  for (const frame of [{ id: 1, type: 'chat' }, { id: 'desktop-1', type: 'catalog' },
    { id: 0, type: 'catalog' }, { id: -1, type: 'catalog' }, { id: 1.5, type: 'catalog' },
    { id: 2, type: 'constructor' }, { id: 3, type: 'search_models' }]) assert.equal(client.trackModelRequest(frame), false)
  assert.equal(client.trackModelRequest({ id: 1, type: 'catalog' }), true)
  assert.equal(client.trackModelRequest({ id: 1, type: 'recommend' }), false)
  client.receive({ id: 1, type: 'error', code: 'COLLIDING_REQUEST' })
  assert.equal(client.view.error.code, 'COLLIDING_REQUEST')
  client.disconnected()
})

function state(sequence = 1, changes = {}) {
  return { sessionId: 'session', workspace: '/workspace', stateRevision: 1, lastSequence: sequence,
    transcript: [{ role: 'system', content: 'hidden' }, { role: 'user', content: 'hola' }],
    turns: [{ turnId: 'turn', status: 'running', activeGenerationId: 'generation',
      displayMessages: [{ role: 'assistant', content: '¡Sí! 🧠', thinking: false }] }],
    modelRuntime: { modelId: 'local:7b', providerId: 'ollama', providerRevision: 1 },
    services: { rag: { enabled: false, availability: 'DISABLED' }, interactions: { approvals: [], inputs: [] } }, ...changes }
}
function setup(snapshot = state()) {
  const sent = [], views = []
  const client = new DesktopApplicationClient(f => sent.push(f), v => views.push(v))
  client.receive({ type: 'ready', sessionId: 'session', tools: ['bash'] })
  client.receive({ type: 'snapshot', id: sent.at(-1).id, data: snapshot })
  const subscription = sent.find(f => f.type === 'subscribe_events').id
  return { client, sent, views, subscription }
}
function event(ctx, sequence, kind, payload = {}, extra = {}) {
  ctx.client.receive({ type: 'event', id: ctx.subscription, schemaVersion: 1,
    event: { schemaVersion: 1, eventId: `event-${sequence}`, sequence, sessionId: 'session',
      turnId: 'turn', generationId: 'generation', kind, payload, stateRevision: 1, ...extra } })
}

test('64K numeric backend metadata needs no preset enum or Desktop authority', () => {
  const snapshot = state(1, {
    modelRuntime: { modelId: 'synthetic:high-capacity', providerId: 'ollama', providerRevision: 1,
      modelContextWindow: 65536, providerContextWindow: 131072 },
    turns: [{ turnId: 'turn', status: 'completed', contextReports: [{ rule: 'context_budget',
      budget: { selected_context_window: 65536, output_reserve: 4096, safety_margin: 6554,
        selection_verified: true, selection_reason: 'manual_verified' } }] }],
  })
  const c = setup(snapshot)
  assert.equal(c.client.view.status.ready, true)
  assert.equal(c.client.view.status.model, 'synthetic:high-capacity')
  assert.equal(c.client.view.error, null)
  assert.equal(snapshot.turns[0].contextReports[0].budget.selected_context_window, 65536)
  assert.equal(c.sent.filter(f => f.type === 'application_command').length, 0)
})

test('Desktop preserves typed manual context rejection from Application', async () => {
  const c = setup()
  const pending = c.client.command('SubmitUserInput', { content: 'synthetic' }, 'cmd-64k')
  const id = c.sent.at(-1).id
  const error = { code: 'CONTEXT_LIMIT_EXCEEDED', message: 'Manual preset exceeds a known limit' }
  c.client.receive({ type: 'application_result', id,
    data: { schemaVersion: 1, commandId: 'cmd-64k', accepted: false, createdIds: {}, error } })
  assert.deepEqual((await pending).error, error)
  assert.deepEqual(c.client.view.error, error)
})

test('Memory projection exposes only local capabilities and drops obsolete remote fields', () => {
  const snapshot = state(1, { services: { rag: { enabled: false, availability: 'DISABLED' },
    memory: { lexicalRecall: true, semantic: false, autoCapture: false, allowRemoteMemoryInjection: true } } })
  const c = setup(snapshot)
  assert.deepEqual(c.client.view.memory, {lexicalRecall:true,semantic:false,autoCapture:false})
  assert.equal(Object.hasOwn(c.client.view,'memoryNotice'), false)
  assert.equal(c.client.view.messages.some(m => m.content.includes('MEMORY CONTEXT')), false)
  assert.equal(c.sent.filter(f => f.type === 'application_command').length, 0)
})

test('snapshot reconstructs the single live chat, tool view and Unicode', () => {
  const c = setup()
  assert.equal(c.client.view.messages.length, 2)
  assert.equal(c.client.view.messages[1].content, '¡Sí! 🧠')
  assert.equal(c.client.view.activeTurnId, 'turn')
  assert.equal(c.sent.at(-1).afterSequence, 1)
})
test('deltas survive disconnected renderer observers and duplicates are ignored', () => {
  const c = setup()
  event(c, 2, 'AssistantDelta', { text: ' continúa' })
  event(c, 2, 'AssistantDelta', { text: ' duplicate' })
  assert.equal(c.client.view.messages.at(-1).content, '¡Sí! 🧠 continúa')
  // A newly mounted observer gets this projection, not a new chat or Turn.
  c.client.refresh()
  assert.equal(c.client.view.activeTurnId, 'turn')
  assert.equal(c.sent.filter(f => f.type === 'application_command').length, 0)
})
test('stale session, subscription and generation do not append output', () => {
  const c = setup()
  event(c, 2, 'AssistantDelta', { text: 'old' }, { sessionId: 'old' })
  event(c, 3, 'AssistantDelta', { text: 'old' }, { generationId: 'old' })
  assert.equal(c.client.view.messages.at(-1).content, '¡Sí! 🧠')
})
test('stale snapshot cannot undo a newer delta', () => {
  const c = setup()
  c.client.refresh()
  const request = c.sent.at(-1)
  event(c, 2, 'AssistantDelta', { text: ' new' })
  c.client.receive({ type: 'snapshot', id: request.id, data: state(1) })
  assert.equal(c.client.view.messages.at(-1).content, '¡Sí! 🧠 new')
})
test('SubmitUserInput carries idempotency; no optimistic message or equivalent StartTurn', async () => {
  const c = setup(state(1, { turns: [], transcript: [] }))
  const pending = c.client.command('SubmitUserInput', { content: 'task' }, 'cmd-fixed')
  const frame = c.sent.at(-1)
  assert.equal(frame.command.commandId, 'cmd-fixed')
  assert.equal(frame.command.kind, 'SubmitUserInput')
  assert.deepEqual(c.client.view.messages, [])
  c.client.receive({ type: 'application_result', id: frame.id,
    data: { accepted: true, schemaVersion: 1, commandId: 'cmd-fixed', createdIds: { turnId: 'turn' } } })
  assert.equal((await pending).createdIds.turnId, 'turn')
  assert.equal((await c.client.command('StartTurn', {})).accepted, false)
})
test('provider conflict and cancellation receipt never invent a Turn terminal', async () => {
  const c = setup()
  const pending = c.client.command('ChangeModel', { modelId: 'other' })
  c.client.receive({ type: 'application_result', id: c.sent.at(-1).id, data: {
    accepted: false, error: { code: 'CONFLICT_ACTIVE_TURN', message: 'busy' }, createdIds: {} } })
  assert.equal((await pending).accepted, false)
  assert.equal(c.client.view.status.model, 'local:7b')
  assert.equal(c.client.view.activeTurnId, 'turn')
  const stop = c.client.command('CancelTurn', { turnId: 'turn' })
  c.client.receive({ type: 'application_result', id: c.sent.at(-1).id, data: { accepted: true, createdIds: {} } })
  await stop
  assert.equal(c.client.view.activeTurnId, 'turn')
})
test('all pending approvals and ask_user survive snapshots; commands bind backend fields', () => {
  const snapshot = state()
  snapshot.services.interactions = { approvals: [{ approvalId: 'a', toolCallId: 'tc',
    requestDigest: 'digest', cwd: '/workspace', policyRevision: 1, arguments: { command: 'rm file' } }],
    inputs: [{ inputRequestId: 'i', question: 'why?', turnId: 'turn' }] }
  const c = setup(snapshot)
  c.client.command('ResolveApproval', { ...c.client.view.approvals[0], approved: false })
  assert.equal(c.sent.at(-1).command.payload.requestDigest, 'digest')
  c.client.command('ResolveUserInput', { inputRequestId: 'i', response: 'answer' })
  assert.equal(c.sent.at(-1).command.kind, 'ResolveUserInput')
  assert.equal(c.client.view.activeTurnId, 'turn')
  assert.equal(c.client.view.approvals.length, 1) // cleared only by backend snapshot
})
test('out-of-sync recovers via snapshot then previous cursor, never blind continuity', () => {
  const c = setup()
  c.client.receive({ type: 'subscription_out_of_sync', id: c.subscription })
  const request = c.sent.at(-1)
  c.client.receive({ type: 'snapshot', id: request.id, data: state(90) })
  const subscription = c.sent.at(-1)
  assert.equal(subscription.type, 'subscribe_events')
  assert.equal(subscription.afterSequence, 1)
  assert.equal(c.client.view.gap, true)
})
test('backend crash retains display, invalidates human requests and never retries effects', async () => {
  const c = setup()
  const pending = c.client.command('SubmitUserInput', { content: 'effect' })
  c.client.disconnected()
  assert.equal((await pending).error.code, 'OUTCOME_UNKNOWN')
  assert.equal(c.client.view.status.ready, false)
  assert.equal(c.client.view.messages.length, 2)
  assert.deepEqual(c.client.view.approvals, [])
  assert.equal(c.sent.filter(f => f.type === 'application_command').length, 1)
  c.client.receive({ type: 'ready', sessionId: 'new' })
  const snapshot = state(1, { sessionId: 'new', turns: [] })
  c.client.receive({ type: 'snapshot', id: c.sent.at(-1).id, data: snapshot })
  assert.equal(c.sent.at(-1).sessionId, 'session') // ask server to expose restart gap
})
test('RAG progress/results/failure do not terminate conversation', () => {
  const c = setup()
  event(c, 2, 'OperationProgress', { service: 'rag', phase: 'indexing' })
  assert.equal(c.client.view.ragProgress, 'indexing')
  event(c, 3, 'OperationFailed', { service: 'rag', result: { error: { code: 'RAG_BACKEND_FAILED' } } })
  assert.equal(c.client.view.activeTurnId, 'turn')
  assert.equal(c.client.view.ragProgress, '')
})
test('EventGap and SessionSnapshot replace old view without duplicating deltas', () => {
  const c = setup()
  event(c, 8, 'EventGap', { reason: 'evicted' })
  event(c, 9, 'SessionSnapshot', state(9))
  event(c, 9, 'AssistantDelta', { text: 'duplicate' })
  assert.equal(c.client.view.gap, true)
  assert.equal(c.client.view.messages.at(-1).content, '¡Sí! 🧠')
})
test('persisted tool calls/results project to the original MessageBlock shape', () => {
  const messages = projectTranscript([{ role: 'assistant', content: '', tool_calls: [{
    function: { name: 'bash', arguments: { command: 'pwd' } } }] },
    { role: 'tool', tool_name: 'bash', content: 'workspace' }], 's')
  assert.deepEqual(messages[0].toolCalls, [{ name: 'bash', args: { command: 'pwd' } }])
  assert.deepEqual(messages[0].toolResults, [{ name: 'bash', output: 'workspace' }])
})

test('a broken pipe rejects the actual commandId without retry or hanging', async () => {
  const c = setup()
  c.client.send = () => false
  const receipt = await c.client.command('SubmitUserInput', { content: 'task' }, 'cmd-pipe')
  assert.equal(receipt.commandId, 'cmd-pipe')
  assert.equal(receipt.error.code, 'OUTCOME_UNKNOWN')
  assert.equal(c.client.view.status.connected, false)
})
test('snapshot recovers RAG result/progress and filesystem revision even when events were overtaken', () => {
  const snapshot = state(20)
  snapshot.services.filesystem = { revision: 7 }
  snapshot.services.operations = [
    { operationId: 'old', status: 'completed', service: 'rag', result: { matches: [{ content: 'recovered' }] } },
    { operationId: 'new', status: 'running', service: 'rag', phase: 'indexing' },
  ]
  const c = setup(snapshot)
  assert.equal(c.client.view.ragResult.matches[0].content, 'recovered')
  assert.equal(c.client.view.ragProgress, 'indexing')
  assert.equal(c.client.view.fileRevision, 7)
})
test('backend failure is visible without creating a successful terminal in React', () => {
  const c = setup(state(20, { turns: [{ turnId: 't', status: 'failed', errorCode: 'PROVIDER_FAILED' }] }))
  assert.equal(c.client.view.activeTurnId, null)
  assert.equal(c.client.view.error.code, 'PROVIDER_FAILED')
})
test('completed harness chips remain bound to their transcript range after reload', () => {
  const c = setup(state(20, { transcript: [{ role: 'user', content: 'task' }, { role: 'assistant', content: 'done' }],
    turns: [{ status: 'completed', transcriptStart: 0, transcriptEnd: 2,
      displayMessages: [{ harnessEvents: ['read_gate', 'retry'] }] }] }))
  assert.deepEqual(c.client.view.messages[1].harnessEvents, ['read_gate', 'retry'])
})
