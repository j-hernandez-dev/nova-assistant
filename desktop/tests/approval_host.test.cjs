const { test } = require('node:test')
const assert = require('node:assert/strict')
const { signApproval, confirmApproval, validFrame } = require('../electron/approval_host.cjs')

const request = () => ({ approvalId: 'approval', toolCallId: 'tool', requestDigest: 'digest',
  cwd: 'C:/fixture', policyRevision: 1, deadline: new Date(Date.now() + 60000).toISOString(),
  arguments: { command: 'Remove-Item build -Recurse' } })
const response = r => ({ approvalId: r.approvalId, toolCallId: r.toolCallId,
  requestDigest: r.requestDigest, cwd: r.cwd, policyRevision: r.policyRevision, approved: true })

function client(r) {
  const sent = []
  return { view: { sessionId: 'session', approvals: [r] }, sent,
    command: (...args) => { sent.push(args); return { accepted: true } } }
}

test('a renderer yes still requires the native host dialog', async () => {
  const r = request(), c = client(r), dialogs = []
  await confirmApproval(c, response(r), 'command', async body => { dialogs.push(body); return { response: 0 } })
  assert.equal(dialogs.length, 1)
  assert.equal(dialogs[0].arguments.command, r.arguments.command)
  assert.equal(c.sent[0][1].approved, false)
})

test('host confirmation sends only the exact pending response', async () => {
  const r = request(), c = client(r)
  await confirmApproval(c, response(r), 'command', async () => ({ response: 1 }))
  assert.deepEqual(c.sent[0], ['ResolveApproval', response(r), 'command'])
})

test('mismatched renderer digest never opens or resolves a dialog', async () => {
  const r = request(), c = client(r)
  const result = await confirmApproval(c, { ...response(r), requestDigest: 'other' }, 'command',
    async () => { assert.fail('dialog opened') })
  assert.equal(result.error.code, 'APPROVAL_STALE')
  assert.equal(c.sent.length, 0)
})

for (const mutation of ['session', 'cwd', 'digest', 'removed']) {
  test('change during dialog is rejected: ' + mutation, async () => {
    const r = request(), c = client(r)
    const result = await confirmApproval(c, response(r), 'command', async () => {
      if (mutation === 'session') c.view.sessionId = 'other'
      if (mutation === 'cwd') c.view.approvals[0].cwd = 'C:/other'
      if (mutation === 'digest') c.view.approvals[0].requestDigest = 'other'
      if (mutation === 'removed') c.view.approvals = []
      return { response: 1 }
    })
    assert.equal(result.error.code, 'APPROVAL_STALE')
    assert.equal(c.sent.length, 0)
  })
}

test('private proof binds canonical command, action and session', () => {
  const key = 'ab'.repeat(32)
  const command = { schemaVersion: 1, commandId: 'cmd', sessionId: 'session', expectedRevision: null,
    kind: 'ResolveApproval', payload: { approved: true, cwd: 'C:/ñ' } }
  const proof = signApproval(key, command)
  assert.equal(proof.length, 64)
  assert.notEqual(proof, signApproval(key, { ...command, sessionId: 'other' }))
  assert.notEqual(proof, signApproval(key, { ...command, payload: { ...command.payload, approved: false } }))
  assert.notEqual(proof, signApproval('cd'.repeat(32), command))
})

test('invalid, circular and oversized renderer payloads fail closed', () => {
  const circular = {}; circular.self = circular
  for (const value of [null, [], 3, circular, { x: BigInt(1) }, { x: 'a'.repeat(131073) }]) {
    assert.equal(validFrame(value), false)
  }
  assert.equal(validFrame({ approvalId: 'a', approved: true }), true)
})

test('invalid deadline cannot produce host consent', async () => {
  const r = { ...request(), deadline: 'invalid' }, c = client(r)
  const result = await confirmApproval(c, response(r), 'command', async () => assert.fail('dialog opened'))
  assert.equal(result.error.code, 'APPROVAL_EXPIRED')
  assert.equal(c.sent.length, 0)
})
