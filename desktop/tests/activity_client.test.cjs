require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { DesktopApplicationClient } = require('../electron/application_client.ts')

function row(changes = {}) {
  return { operationId: 'op', toolCallId: 'tc', turnId: 'turn', messageId: 'message', name: 'bash',
    arguments: { command: 'owned fixture' }, cwd: '/owned', status: 'running', operationStatus: 'running',
    effectState: 'none', output: '', stdout: '', stderr: '', outputSequence: 1, outputTruncated: false,
    startedAt: '2026-10-16T12:00:00Z', ...changes }
}
function state(sequence = 1, activities = [row()], changes = {}) {
  return { sessionId: 'session', workspace: '/owned', stateRevision: 1, lastSequence: sequence,
    transcript: [{ role: 'user', content: 'A fixture command' }],
    turns: [{ turnId: 'turn', status: 'running', transcriptStart: 0, transcriptEnd: null,
      activeGenerationId: null, displayMessages: [{ id: 'message', role: 'assistant', content: 'Running the fixture.', status: 'completed' }],
      toolActivities: activities }], modelRuntime: { providerId: 'ollama', modelId: 'owned', providerRevision: 1 },
    services: { rag: { enabled: false, availability: 'DISABLED' }, interactions: { approvals: [], inputs: [] } }, ...changes }
}
function setup(initial = state()) {
  const sent = []
  const client = new DesktopApplicationClient(frame => sent.push(frame), () => {})
  client.receive({ type: 'ready', sessionId: 'session', tools: ['bash', 'read'] })
  const snapshot = data => {
    client.refresh()
    client.receive({ type: 'snapshot', id: sent.filter(frame => frame.type === 'get_snapshot').at(-1).id, data })
  }
  snapshot(initial)
  const event = (sequence, payload, extra = {}) => client.receive({ type: 'event', schemaVersion: 1,
    id: sent.filter(frame => frame.type === 'subscribe_events').at(-1).id,
    event: { schemaVersion: 1, sessionId: 'session', eventId: `event-${sequence}`, sequence, stateRevision: 1,
      kind: 'OperationProgress', turnId: 'turn', operationId: 'op', toolCallId: 'tc', payload: { service: 'tool', ...payload }, ...extra } })
  return { client, sent, snapshot, event }
}

test('typed operations attach by host message identity, not positional tool name or output text', t => {
  const c = setup(state(1, [row(), row({ operationId: 'other', toolCallId: 'other-tc', messageId: null })]))
  t.after(() => c.client.disconnected())
  assert.deepEqual(c.client.view.messages.find(m => m.id === 'message').toolActivities.map(a => a.operationId), ['op'])
  assert.equal(c.client.view.messages.some(m => m.id === 'activity:turn'), false)
  assert.equal(c.client.view.toolActivities.length, 2)
  assert.equal(c.client.view.conversation.unreadCount, 0)
})

test('real progress is ordered and deduplicated; a sequence gap requests a snapshot rather than fabricating output', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.event(2, { outputSequence: 2, channel: 'stdout', text: 'first\n' })
  c.event(2, { outputSequence: 2, channel: 'stdout', text: 'duplicate\n' })
  c.event(3, { outputSequence: 2, channel: 'stdout', text: 'duplicate at newer envelope\n' })
  assert.equal(c.client.view.toolActivities[0].stdout, 'first\n')
  c.event(4, { outputSequence: 4, channel: 'stderr', text: 'missing predecessor' })
  assert.equal(c.client.view.toolActivities[0].stderr, '')
  assert.equal(c.sent.at(-1).type, 'get_snapshot')
  c.snapshot(state(5, [row({ outputSequence: 4, stdout: 'first\nsecond\n', stderr: 'recovered' })]))
  assert.equal(c.client.view.toolActivities[0].stderr, 'recovered')
  assert.equal(c.client.view.toolActivities[0].stdout, 'first\nsecond\n')
})

test('terminal receipt replaces progress authoritatively and late output cannot reopen an UNKNOWN effect', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.event(2, { outputSequence: 2, channel: 'stdout', text: 'preview' })
  c.event(3, { activity: row({ status: 'outcome_unknown', operationStatus: 'outcome_unknown', effectState: 'unknown',
    outputSequence: 3, stdout: 'final captured output', output: 'final receipt', completedAt: '2026-10-16T12:00:01Z' }) })
  c.event(4, { outputSequence: 4, channel: 'stdout', text: 'late' })
  c.event(5, { activity: row({ outputSequence: 4, stdout: 'late full running state' }) })
  assert.equal(c.client.view.toolActivities[0].status, 'outcome_unknown')
  assert.equal(c.client.view.toolActivities[0].stdout, 'final captured output')
  assert.equal(c.sent.filter(frame => frame.type === 'application_command').length, 0)
})

test('wrong operation, toolCall, turn and session cannot append progress to another card', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  let seq = 2
  for (const extra of [{ operationId: 'other' }, { toolCallId: 'other' }, { turnId: 'other' }, { sessionId: 'other' }]) {
    c.event(seq++, { outputSequence: 2, channel: 'stdout', text: 'must not appear' }, extra)
  }
  c.event(seq++, { activity: row({ operationId: 'other', stdout: 'wrong full state' }) })
  assert.equal(c.client.view.toolActivities[0].stdout, '')
  assert.equal(c.client.view.toolActivities.length, 1)
})

test('denied pre-effect has no invented start, and legacy text cannot create a successful receipt', t => {
  const denied = row({ status: 'denied', operationStatus: 'failed', effectState: 'none',
    startedAt: undefined, errorCode: 'POLICY_DENIED', output: 'success! created!' })
  const c = setup(state(1, [denied])); t.after(() => c.client.disconnected())
  assert.equal(c.client.view.toolActivities[0].startedAt, undefined)
  assert.equal(c.client.view.toolActivities[0].status, 'denied')
  c.snapshot(state(2, [], { transcript: [{ role: 'assistant', content: '', tool_calls: [{ function: { name: 'write', arguments: {} } }] },
    { role: 'tool', name: 'write', content: 'Done' }], turns: [] }))
  assert.deepEqual(c.client.view.toolActivities, [])
  assert.equal(c.client.view.messages[0].toolResults[0].output, 'Done')
  assert.deepEqual(c.client.view.messages[0].toolActivities, [])
})

test('disconnect or event gap loses observation, not host outcome; only a fresh snapshot restores progress', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.event(2, {}, { kind: 'EventGap' })
  assert.equal(c.client.view.recovering, true)
  assert.equal(c.client.view.toolActivities[0].observationLost, true)
  c.snapshot(state(3))
  assert.equal(c.client.view.recovering, false)
  assert.equal(c.client.view.toolActivities[0].observationLost, undefined)
  c.client.disconnected()
  assert.equal(c.client.view.toolActivities[0].observationLost, true)
  assert.equal(c.client.view.toolActivities[0].status, 'running')
  assert.equal(c.client.view.messages.find(m => m.id === 'message').toolActivities[0].observationLost, true)
  assert.equal(c.sent.filter(frame => frame.type === 'application_command').length, 0)
})

test('oversized progress stays bounded in the projection and does not affect execution authority', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.event(2, { outputSequence: 2, channel: 'stdout', text: 'x'.repeat(100000) })
  assert.equal(c.client.view.toolActivities[0].stdout.length, 32768)
  assert.equal(c.client.view.toolActivities[0].outputTruncated, true)
  assert.equal(c.sent.filter(frame => frame.type === 'application_command').length, 0)
})

test('orphan tool activity cannot receive a public assistant delta and stale gap replay cannot freeze approval', t => {
  const snapshot = state(1, [row({ messageId: null })])
  snapshot.turns[0].activeGenerationId = 'generation'
  snapshot.turns[0].displayMessages = [{ id: 'message', generationId: 'generation', role: 'assistant', content: 'Public', status: 'streaming' }]
  const c = setup(snapshot); t.after(() => c.client.disconnected())
  c.event(2, { text: ' response' }, { kind: 'AssistantDelta', generationId: 'generation' })
  assert.equal(c.client.view.messages.find(m => m.id === 'message').content, 'Public response')
  assert.equal(c.client.view.messages.some(m => m.id.startsWith('activity:')), false)
  c.event(3, {}, { kind: 'EventGap' })
  c.snapshot({ ...snapshot, lastSequence: 4 })
  assert.equal(c.client.view.recovering, false)
  c.event(3, {}, { kind: 'EventGap' })
  assert.equal(c.client.view.recovering, false)
})
