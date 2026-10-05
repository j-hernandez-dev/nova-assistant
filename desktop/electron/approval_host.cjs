// Main-process approval correlation and private-pipe authentication.
const crypto = require('node:crypto')

function stableJson(value) {
  if (Array.isArray(value)) return '[' + value.map(stableJson).join(',') + ']'
  if (value !== null && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + stableJson(value[k])).join(',') + '}'
  }
  return JSON.stringify(value)
}

function signApproval(key, command) {
  return crypto.createHmac('sha256', Buffer.from(key, 'hex')).update(stableJson(command), 'utf8').digest('hex')
}

function validFrame(value) {
  try {
    return value !== null && typeof value === 'object' && !Array.isArray(value) &&
      JSON.stringify(value).length <= 131072
  } catch { return false }
}

async function confirmApproval(client, payload, commandId, showDialog) {
  const reject = code => ({ schemaVersion: 1, commandId: commandId || '', accepted: false,
    createdIds: {}, error: { code, message: 'Approval is unavailable or stale.' } })
  const pending = client.view.approvals.find(p => p.approvalId === payload.approvalId)
  const sessionId = client.view.sessionId
  if (!pending || typeof payload.approved !== 'boolean' || !sessionId) return reject('APPROVAL_STALE')
  for (const field of ['toolCallId', 'requestDigest', 'cwd', 'policyRevision']) {
    if (payload[field] !== pending[field]) return reject('APPROVAL_STALE')
  }
  const snapshot = JSON.parse(JSON.stringify(pending))
  const fingerprint = stableJson(snapshot)
  if (!snapshot.deadline || !Number.isFinite(Date.parse(snapshot.deadline)) ||
      Date.now() >= Date.parse(snapshot.deadline)) return reject('APPROVAL_EXPIRED')
  const approved = payload.approved && (await showDialog(snapshot)).response === 1
  const current = client.view.approvals.find(p => p.approvalId === snapshot.approvalId)
  if (client.view.sessionId !== sessionId || !current || stableJson(current) !== fingerprint ||
      Date.now() >= Date.parse(snapshot.deadline)) return reject('APPROVAL_STALE')
  return client.command('ResolveApproval', {
    approvalId: snapshot.approvalId, toolCallId: snapshot.toolCallId,
    requestDigest: snapshot.requestDigest, cwd: snapshot.cwd,
    policyRevision: snapshot.policyRevision, approved: Boolean(approved),
  }, commandId)
}

module.exports = { stableJson, signApproval, confirmApproval, validFrame }
