const assert = require('node:assert/strict')
const { test } = require('node:test')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const Module = require('node:module')
const file = path.join(__dirname, '../electron/application_client.ts')
const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const loaded = new Module(file, module)
loaded.filename = file; loaded.paths = module.paths; loaded._compile(compiled, file)
const { DesktopApplicationClient } = loaded.exports

test('M6 proposal controls use the authenticated MemoryControl backend path, never tools or Turn', async () => {
  const sent = []
  const client = new DesktopApplicationClient(frame => { sent.push(frame); return true }, () => {}, () => 'synthetic-host-proof')
  client.view.sessionId = 'synthetic-session'; client.view.stateRevision = 4
  client.view.status.ready = true
  for (const name of ['memory_proposals', 'memory_confirm', 'memory_reject']) {
    const promise = client.memory(name, name === 'memory_proposals' ? {} : {
      jobId: 'synthetic-job', proposalId: 'synthetic-proposal', revision: 3,
    }, 'synthetic-' + name)
    const frame = sent.at(-1)
    assert.equal(frame.type, 'memory_command')
    assert.equal(frame.command.kind, 'MemoryControl')
    assert.equal(frame.command.name, name)
    assert.equal(frame.command.expectedRevision, 4)
    assert.equal(frame.hostMemoryProof, 'synthetic-host-proof')
    client.receive({ type: 'memory_result', id: frame.id, data: {
      schemaVersion: 1, commandId: frame.command.commandId, completed: true, stateRevision: 4, data: {},
    } })
    assert.equal((await promise).completed, true)
  }
  assert.equal(sent.some(f => f.type === 'application_command' || f.type === 'tool'), false)
})
