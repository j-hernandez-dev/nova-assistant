require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { DesktopApplicationClient } = require('../electron/application_client.ts')
const { ConversationNotifications } = require('../electron/conversation_notifications.ts')

const completed = (id, content = 'A public reply') => ({ id, role: 'assistant', content, deliveryStatus: 'completed' })
function state(sequence, turns = [], transcript = []) {
  return { sessionId: 'session', workspace: '/owned', stateRevision: sequence, lastSequence: sequence,
    transcript, turns, modelRuntime: { modelId: 'local', providerId: 'ollama', providerRevision: 1 },
    services: { rag: { enabled: false, availability: 'DISABLED' }, interactions: { approvals: [], inputs: [] } } }
}
function setup() {
  const sent = []
  const client = new DesktopApplicationClient(frame => sent.push(frame), () => {})
  client.receive({ type: 'ready', sessionId: 'session', tools: ['read'] })
  const apply = snapshot => {
    client.refresh()
    client.receive({ type: 'snapshot', id: sent.filter(f => f.type === 'get_snapshot').at(-1).id, data: snapshot })
  }
  apply(state(1))
  return { client, sent, apply }
}
const user = { role: 'user', content: 'Read the project' }
function turn(status, displayMessages) {
  return { turnId: 'turn', status, activeGenerationId: status === 'running' ? 'g2' : null,
    transcriptStart: 0, transcriptEnd: status === 'running' ? null : 3,
    userMessage: { id: 'u1', sourceIndex: 0, createdAt: '2026-10-15T12:00:00+00:00' }, displayMessages }
}
const display = (id, content, status = 'completed', extra = {}) => ({ id, role: 'assistant', content, status,
  createdAt: '2026-10-15T12:00:01+00:00', ...extra })

test('accepted canonical user reveals History; rejecting a submit cannot create a conversation', async t => {
  const c = setup(); t.after(() => c.client.disconnected())
  assert.equal(c.client.view.conversation.hasConversation, false)
  const receipt = c.client.command('SubmitUserInput', { content: 'read' })
  const frame = c.sent.at(-1)
  c.client.receive({ type: 'application_result', id: frame.id, data: {
    accepted: false, commandId: frame.command.commandId, createdIds: {}, error: { code: 'NOT_READY', message: 'No' } } })
  await receipt
  assert.equal(c.client.view.conversation.hasConversation, false)
  c.apply(state(2, [turn('running', [display('g1', '', 'streaming')])], [user]))
  assert.equal(c.client.view.conversation.hasConversation, true)
  assert.equal(c.client.view.conversation.unreadCount, 0)
})

test('one shared conversation counts preamble and final once, not deltas, tools, or terminal snapshots', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.apply(state(2, [turn('running', [display('g1', 'I will read it.', 'streaming')])], [user]))
  assert.equal(c.client.view.conversation.unreadCount, 0)
  const preamble = display('g1', 'I will read it.')
  c.apply(state(3, [turn('running', [preamble, display('g2', '', 'streaming', { thinking: true })])], [user]))
  assert.equal(c.client.view.conversation.unreadCount, 1)
  c.apply(state(4, [turn('running', [preamble, display('g2', 'A partial final', 'streaming')])], [user]))
  assert.equal(c.client.view.conversation.unreadCount, 1)
  const final = display('g2', 'A complete final')
  c.apply(state(5, [turn('running', [preamble, final])], [user]))
  assert.equal(c.client.view.conversation.unreadCount, 2)
  const canonical = [user, { role: 'assistant', content: preamble.content }, { role: 'assistant', content: final.content }]
  const terminal = state(6, [turn('completed', [{ ...preamble, sourceIndex: 1 }, { ...final, sourceIndex: 2 }])], canonical)
  c.apply(terminal); c.apply(terminal)
  assert.deepEqual(c.client.view.messages.map(m => m.id), ['u1', 'g1', 'g2'])
  assert.equal(c.client.view.conversation.unreadCount, 2)
  const before = c.sent.filter(frame => frame.type === 'application_command').length
  c.client.setHistoryVisible(true)
  assert.equal(c.client.view.conversation.unreadCount, 0)
  c.client.setHistoryVisible(false); c.apply(terminal)
  assert.equal(c.client.view.conversation.unreadCount, 0)
  assert.equal(c.sent.filter(frame => frame.type === 'application_command').length, before)
})

test('restored history has no fabricated timestamp or notification and accepted new generation does', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.apply(state(2, [], [user, { role: 'assistant', content: 'Historical answer' }]))
  assert.equal(c.client.view.conversation.hasConversation, true)
  assert.equal(c.client.view.conversation.unreadCount, 0)
  assert.equal(c.client.view.messages.at(-1).createdAt, undefined)
  c.apply(state(3, [turn('running', [display('new', 'New response')])], [user]))
  assert.equal(c.client.view.conversation.unreadCount, 1)
})

test('notifications exclude cancelled/failed/thinking/empty/tool-only and visible History marks each reply read', () => {
  const n = new ConversationNotifications(); n.observe('s', [])
  n.observe('s', [completed('empty', ' '), { ...completed('thinking', ''), thinking: true },
    { ...completed('tool', ''), toolCalls: [{ name: 'read', args: {} }] },
    { ...completed('cancelled'), deliveryStatus: 'cancelled' }, { ...completed('failed'), deliveryStatus: 'failed' }])
  assert.equal(n.projection.unreadCount, 0)
  n.setVisible(true); n.observe('s', [completed('one')])
  n.setVisible(false); n.observe('s', [completed('one'), completed('two')])
  assert.equal(n.projection.unreadCount, 1)
})

test('persistent per-session IDs survive a new client, replay, and clear without storing any content', () => {
  const disk = new Map()
  const prefs = { load: id => disk.get(id) || null, save: (id, value) => { disk.set(id, structuredClone(value)); return true } }
  const n = new ConversationNotifications(); n.setPreferences(prefs); n.observe('s', [])
  n.observe('s', [completed('reply')]); n.observe('s', [completed('reply')])
  assert.equal(n.projection.unreadCount, 1)
  const remount = new ConversationNotifications(); remount.setPreferences(prefs)
  remount.observe('s', [completed('reply')])
  assert.equal(remount.projection.unreadCount, 1)
  remount.setVisible(true); remount.setVisible(false); remount.observe('s', [completed('reply')])
  assert.equal(remount.projection.unreadCount, 0)
  assert.doesNotMatch(JSON.stringify([...disk]), /A public reply|content|tool/)
  remount.observe('new-session', [completed('reply')])
  assert.equal(remount.projection.unreadCount, 0)
  remount.observe('new-session', [completed('reply'), completed('new')])
  assert.equal(remount.projection.unreadCount, 1)
  remount.observe('new-session', [])
  assert.equal(remount.projection.unreadCount, 0)
})

test('late observer snapshots baseline old replies; disk failure preserves working in-memory counts', () => {
  const n = new ConversationNotifications()
  n.setPreferences({ load: () => { throw Error('disk') }, save: () => false })
  n.observe('s', [completed('historical')])
  assert.equal(n.projection.unreadCount, 0)
  n.observe('s', [completed('historical'), completed('new')])
  assert.equal(n.projection.unreadCount, 1)
  assert.equal(n.projection.preferenceError, 'CONVERSATION_PREFERENCES_SAVE_FAILED')
  n.setVisible(true)
  assert.equal(n.projection.unreadCount, 0)
})

test('reconnect and event gap replays do not duplicate completed message identity', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  const transcript = [user, { role: 'assistant', content: 'Response' }]
  const snapshot = state(7, [turn('completed', [display('g1', 'Response', 'completed', { sourceIndex: 1 })])], transcript)
  c.apply(snapshot)
  assert.equal(c.client.view.conversation.unreadCount, 1)
  c.client.disconnected()
  c.client.receive({ type: 'ready', sessionId: 'session', tools: ['read'] })
  c.apply(snapshot)
  const subscription = c.sent.filter(f => f.type === 'subscribe_events').at(-1).id
  c.client.receive({ type: 'event', id: subscription, event: { schemaVersion: 1, sequence: 8,
    sessionId: 'session', eventId: 'gap', kind: 'SessionSnapshot', stateRevision: 8, payload: { ...snapshot, lastSequence: 8 } } })
  c.apply({ ...snapshot, lastSequence: 8 })
  assert.equal(c.client.view.conversation.unreadCount, 1)
})

test('same-sequence older revision cannot resurrect a cleared conversation or badge', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  const previous = state(7, [turn('completed', [display('g1', 'Old', 'completed', { sourceIndex: 1 })])],
    [user, { role: 'assistant', content: 'Old' }])
  c.apply(previous)
  c.apply({ ...state(7), stateRevision: 8 })
  assert.equal(c.client.view.conversation.hasConversation, false)
  c.apply(previous)
  assert.equal(c.client.view.conversation.hasConversation, false)
  assert.equal(c.client.view.conversation.unreadCount, 0)
})

test('cancelled partial remains visible after terminal and before the next user without a notification', t => {
  const c = setup(); t.after(() => c.client.disconnected())
  c.apply(state(2, [turn('running', [display('partial', 'Visible partial', 'streaming')])], [user]))
  const terminal = { ...turn('cancelled', [display('partial', 'Visible partial', 'cancelled')]), transcriptEnd: 1 }
  c.apply(state(3, [terminal], [user, { role: 'user', content: 'Next task' }]))
  assert.deepEqual(c.client.view.messages.map(m => m.content), ['Read the project', 'Visible partial', 'Next task'])
  assert.equal(c.client.view.messages[1].id, 'partial')
  assert.equal(c.client.view.messages[1].deliveryStatus, 'cancelled')
  assert.equal(c.client.view.conversation.unreadCount, 0)
})
