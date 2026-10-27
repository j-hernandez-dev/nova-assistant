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
  const {validate,...shown}=dialogs[0]
  assert.deepEqual(shown, { name: 'memory_remember', workspace: '/w', write: true })
  assert.equal(validate(),true)
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
  const canceled=await memoryControl(client, 'memory_export', args, 'second', dialog)
  assert.equal(canceled.canceled,true);assert.equal(canceled.error,undefined)
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

const {createMemoryEditControls}=require('../electron/memory_control.cjs')
function editFixture(){
 const calls=[],dialogs=[],client={view:{sessionId:'session',workspace:'alpha',stateRevision:1,status:{ready:true}},memory:async(name,args)=>{calls.push([name,args]);return {completed:true}}}
 let accept=true
 const editor=createMemoryEditControls(client,async request=>{dialogs.push(request.kind);assert.equal(request.validate(),true);return {confirmed:accept}})
 return {client,calls,dialogs,editor,deny(){accept=false}}
}
const editRow=(patch={})=>({memoryId:'one',revision:3,text:'Synthetic preference',kind:'PREFERENCE',scope:'WORKSPACE',sensitive:false,...patch})
test('Classification confirmation is bound to record revision, target value and workspace and consumed once',async()=>{
 const h=editFixture(),choice={memoryId:'one',revision:3,sensitive:true}
 const result=await h.editor.confirm(choice);assert.equal(result.completed,true);assert.deepEqual(h.dialogs,['memory-classify-sensitive']);assert.equal(h.calls.length,0)
 const token=result.data.token
 assert.equal((await h.editor.edit({records:[editRow({revision:4,sensitive:true,consentToken:token})]})).completed,false)
 assert.equal((await h.editor.edit({records:[editRow({sensitive:true,consentToken:token})]})).completed,true)
 assert.equal(h.calls[0][1].records[0].consentSensitive,true);assert.equal(h.calls[0][1].records[0].consentToken,undefined)
 assert.equal((await h.editor.edit({records:[editRow({sensitive:true,consentToken:token})]})).completed,false)
 assert.deepEqual(h.dialogs,['memory-classify-sensitive'],'save does not repeat confirmed classification')
 const next=await h.editor.confirm(choice);h.client.view.workspace='beta'
 assert.equal((await h.editor.edit({records:[editRow({sensitive:true,consentToken:next.data.token})]})).completed,false)
})
test('Unmarking needs its own modal; unrelated sensitive consent cannot authorize an unmarked row',async()=>{
 const h=editFixture()
 const choice=await h.editor.confirm({memoryId:'one',revision:3,sensitive:false})
 assert.equal(h.dialogs[0],'memory-classify-normal')
 await h.editor.edit({records:[editRow({consentToken:choice.data.token})]})
 assert.equal(h.calls[0][1].records[0].consentSensitive,true)
 await h.editor.edit({records:[editRow(),editRow({memoryId:'two',sensitive:true})]})
 assert.equal(h.dialogs.at(-1),'memory-write-sensitive')
 assert.equal(h.calls[1][1].records[0].consentSensitive,false)
 assert.equal(h.calls[1][1].records[1].consentSensitive,true)
 h.deny();const count=h.calls.length
 assert.equal((await h.editor.confirm({memoryId:'one',revision:3,sensitive:true})).canceled,true)
 assert.equal((await h.editor.edit({records:[editRow({sensitive:true})]})).canceled,true)
 assert.equal(h.calls.length,count)
})

test('Completed write revision is available to the immediate follow-up read without retaining memory content',async()=>{
 const c=setup(),pending=c.client.memory('memory_edit',{records:[]}),frame=c.sent.at(-1)
 c.client.receive({type:'memory_result',id:frame.id,data:{schemaVersion:1,completed:true,stateRevision:12,data:{records:[{canonicalText:'Private fixture'}]}}})
 await pending
 const reading=c.client.memory('memory_list',{})
 const readFrame=c.sent.filter(frame=>frame.type==='memory_command').at(-1)
 assert.equal(readFrame.command.expectedRevision,12);assert.ok(!JSON.stringify(c.client.view).includes('Private fixture'))
 c.client.receive({type:'memory_result',id:readFrame.id,data:{schemaVersion:1,completed:true,stateRevision:13,data:{records:[]}}});await reading
})

test('Batch deletion requires its own Nova confirmation; canceled, forged and stale requests never dispatch',async()=>{
 const h=editFixture(),args={records:[{memoryId:'one',revision:3},{memoryId:'two',revision:2}]}
 h.deny();assert.equal((await h.editor.remove(args)).canceled,true);assert.equal(h.calls.length,0);assert.equal(h.dialogs.at(-1),'memory-delete-records')
 const allow=editFixture();assert.equal((await allow.editor.remove(args)).completed,true)
 assert.deepEqual(allow.calls,[['memory_delete',args]])
 assert.equal((await allow.editor.remove({records:[{memoryId:'one',revision:3,subjectId:'forged'}]})).completed,false)
 assert.equal((await allow.editor.remove({records:[args.records[0],args.records[0]]})).completed,false)
 const client={view:{sessionId:'owned',workspace:'alpha',stateRevision:1,status:{ready:true}},memory:async()=>{throw Error('must not dispatch')}}
 const stale=createMemoryEditControls(client,async()=>{client.view.workspace='beta';return {confirmed:true}})
 assert.equal((await stale.remove(args)).error.code,'REVISION_CONFLICT')
})
