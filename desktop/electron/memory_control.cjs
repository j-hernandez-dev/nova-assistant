// Host-confirmed sensitive control, not backend WritePolicy or memory storage.
async function memoryControl(client, name, args, commandId, showDialog) {
  const reject = code => ({ schemaVersion: 1, commandId: commandId || '', completed: false,
    error: { code, message: 'Memory action cancelled, unavailable or stale.', retryable: false } })
  const sessionId = client.view.sessionId, workspace = client.view.workspace, revision = client.view.stateRevision
  if (!sessionId || !client.view.status.ready) return reject('MEMORY_UNAVAILABLE')
  const frozen = JSON.parse(JSON.stringify(args))
  if (frozen.consentSensitive === true || frozen.includeSensitive === true) {
    const answer = await showDialog({ name, workspace, write: frozen.consentSensitive === true })
    if (answer.response !== 1) return reject('MEMORY_SENSITIVE_DENIED')
  }
  if (client.view.sessionId !== sessionId || client.view.workspace !== workspace || client.view.stateRevision !== revision) {
    return reject('REVISION_CONFLICT')
  }
  return client.memory(name, frozen, commandId)
}
module.exports = { memoryControl }
