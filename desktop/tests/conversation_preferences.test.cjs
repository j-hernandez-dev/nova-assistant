const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { createConversationPreferencesStore } = require('../electron/conversation_preferences.cjs')

function ownedDirectory(t) {
  const directory = fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP || os.tmpdir(), 'nova-conversation-view-test-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  return directory
}

test('Read-state reloads exact IDs only and never stores transcript, content or authority', t => {
  const directory = ownedDirectory(t)
  const store = createConversationPreferencesStore(directory)
  const state = { observedIds: ['response:1', 'response:2'], unreadIds: ['response:2'],
    transcript: [{ content: 'PRIVATE_MARKER_NOT_TO_SAVE' }], grant: { secret: 'NOT_AUTHORITY' } }
  assert.equal(store.load('session:owned'), null)
  assert.equal(store.save('session:owned', state), true)
  const persisted = fs.readFileSync(path.join(directory, 'desktop-conversation-view.json'), 'utf8')
  assert.doesNotMatch(persisted, /PRIVATE_MARKER_NOT_TO_SAVE|NOT_AUTHORITY|transcript|grant/)
  assert.deepEqual(JSON.parse(persisted), { schemaVersion: 1, sessions: [
    { sessionId: 'session:owned', observedIds: ['response:1', 'response:2'], unreadIds: ['response:2'] }] })
  state.observedIds.push('caller-mutation')
  const restored = createConversationPreferencesStore(directory)
  const loaded = restored.load('session:owned')
  loaded.unreadIds.length = 0
  assert.deepEqual(restored.load('session:owned'), { observedIds: ['response:1', 'response:2'], unreadIds: ['response:2'] })
  assert.equal(restored.load('session:another'), null)
  assert.deepEqual(fs.readdirSync(directory), ['desktop-conversation-view.json'])
})

test('Saving a read conversation clears its unread IDs across reload without duplicating IDs', t => {
  const directory = ownedDirectory(t)
  const store = createConversationPreferencesStore(directory)
  assert.equal(store.save('session', { observedIds: ['r1', 'r1', 'r2'], unreadIds: ['r2', 'r2'] }), true)
  assert.deepEqual(store.load('session'), { observedIds: ['r1', 'r2'], unreadIds: ['r2'] })
  assert.equal(store.save('session', { observedIds: ['r1', 'r2'], unreadIds: [] }), true)
  assert.deepEqual(createConversationPreferencesStore(directory).load('session'), { observedIds: ['r1', 'r2'], unreadIds: [] })
})

test('Session and ID bounds reject malformed state and keep only 20 most recently saved sessions', t => {
  const store = createConversationPreferencesStore(ownedDirectory(t))
  for (const sessionId of ['', 'bad session', 'a'.repeat(257), null, {}, ['session']]) {
    assert.equal(store.save(sessionId, { observedIds: [], unreadIds: [] }), false)
    assert.equal(store.load(sessionId), null)
  }
  for (const state of [null, {}, { observedIds: [], unreadIds: ['unobserved'] },
    { observedIds: ['bad\nref'], unreadIds: [] }, { observedIds: ['a'.repeat(513)], unreadIds: [] },
    { observedIds: Array(10_001).fill('r'), unreadIds: [] }, { observedIds: 'r', unreadIds: [] }]) {
    assert.equal(store.save('session', state), false)
  }
  for (let index = 0; index < 21; index++) assert.equal(store.save(`session:${index}`, {
    observedIds: [`response:${index}`], unreadIds: [] }), true)
  assert.equal(store.load('session:0'), null)
  assert.deepEqual(store.load('session:20'), { observedIds: ['response:20'], unreadIds: [] })
})

test('Corrupt, wrong-version and oversized files are ignored without rewriting them', t => {
  const directory = ownedDirectory(t)
  const filename = path.join(directory, 'desktop-conversation-view.json')
  for (const text of ['{bad', JSON.stringify({ schemaVersion: 2, sessions: [] }),
    JSON.stringify({ schemaVersion: 1, sessions: [{ sessionId: 'session', observedIds: [], unreadIds: ['not-observed'] }] }),
    'x'.repeat(8 * 1024 * 1024 + 1)]) {
    fs.writeFileSync(filename, text)
    assert.equal(createConversationPreferencesStore(directory).load('session'), null)
    assert.equal(fs.readFileSync(filename, 'utf8'), text)
  }
})

test('Disk failure is nonfatal and retains previous read-state without stray owned temporaries', t => {
  const directory = ownedDirectory(t)
  const store = createConversationPreferencesStore(directory)
  assert.equal(store.save('session', { observedIds: ['r1'], unreadIds: ['r1'] }), true)
  const filename = path.join(directory, 'desktop-conversation-view.json')
  fs.rmSync(filename)
  fs.mkdirSync(filename)
  assert.equal(store.save('session', { observedIds: ['r1'], unreadIds: [] }), false)
  assert.deepEqual(store.load('session'), { observedIds: ['r1'], unreadIds: ['r1'] })
  assert.equal(fs.readdirSync(directory).some(name => name.endsWith('.tmp')), false)
})
