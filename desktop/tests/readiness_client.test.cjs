require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { DesktopApplicationClient } = require('../electron/application_client.ts')

function snapshot(modelId = 'model:old', revision = 1) {
  return { sessionId: 'session', workspace: '/owned', stateRevision: revision, lastSequence: revision,
    transcript: [], turns: [], modelRuntime: { providerId: 'ollama', modelId, providerRevision: revision },
    services: { rag: { enabled: false, availability: 'UNAVAILABLE' }, interactions: { approvals: [], inputs: [] } } }
}
function setup(changes = {}) {
  const sent = [], views = [], confirmed = []
  const client = new DesktopApplicationClient(frame => sent.push(frame), view => views.push(view))
  client.setConfirmedModelObserver(runtime => confirmed.push(runtime))
  client.receive({ type: 'ready', sessionId: 'session', tools: ['read'] })
  client.receive({ type: 'snapshot', id: sent.find(frame => frame.type === 'get_snapshot').id, data: { ...snapshot(), ...changes } })
  return { client, sent, views, confirmed }
}
function observation(ctx, changes = {}) {
  const request = ctx.sent.filter(frame => frame.type === 'get_readiness').at(-1)
  ctx.client.receive({ type: 'readiness', id: request.id, data: { schemaVersion: 1,
    sessionId: 'session', providerId: 'ollama', modelId: 'model:old', providerRevision: 1,
    ready: true, reason: null, observedAt: new Date().toISOString(), requiredAction: null,
    installedModels: [{ name: 'model:old', size: 1 }, { name: 'model:new', size: 2 }], ...changes } })
}

test('A protocol snapshot does not imply chat readiness; a matching host observation does', () => {
  const ctx = setup()
  assert.equal(ctx.client.view.status.ready, true)
  assert.equal(ctx.client.view.readiness.ready, false)
  observation(ctx)
  assert.equal(ctx.client.view.readiness.ready, true)
  assert.equal(ctx.client.view.rag.availability, 'UNAVAILABLE')
  assert.equal(ctx.client.view.readiness.installedModels.length, 2)
  ctx.client.disconnected()
})

test('Ollama absence is actionable without inventing a configuration route', () => {
  const ctx = setup()
  observation(ctx, { ready: false, reason: 'OLLAMA_UNAVAILABLE', installedModels: [] })
  assert.equal(ctx.client.view.readiness.ready, false)
  assert.equal(ctx.client.view.readiness.requiredAction, null)
  assert.equal(ctx.client.view.status.ready, true)
  ctx.client.disconnected()
})

test('Cross-session, cross-model and cross-revision readiness cannot mark the selected runtime ready', () => {
  for (const changes of [{ sessionId: 'other' }, { modelId: 'other' }, { providerRevision: 2 },
    { ready: true, reason: 'OLLAMA_UNAVAILABLE' }, { observedAt: 'invalid' }]) {
    const ctx = setup()
    observation(ctx, changes)
    assert.equal(ctx.client.view.readiness.ready, false)
    assert.equal(ctx.client.view.readiness.reason, 'READINESS_CHECK_FAILED')
    ctx.client.disconnected()
  }
})

test('Disconnected or delayed observations never revive readiness', () => {
  const ctx = setup()
  const request = ctx.sent.find(frame => frame.type === 'get_readiness')
  ctx.client.disconnected()
  observation(ctx)
  assert.equal(ctx.client.view.readiness.reason, 'BACKEND_DISCONNECTED')
  assert.equal(ctx.client.view.status.connected, false)
  assert.ok(request)
})

test('Readiness probes are single-flight and cached without creating effect commands', () => {
  const ctx = setup()
  for (let i = 0; i < 10; i++) ctx.client.refreshReadiness(true)
  assert.equal(ctx.sent.filter(frame => frame.type === 'get_readiness').length, 1)
  observation(ctx)
  ctx.client.refreshReadiness()
  assert.equal(ctx.sent.filter(frame => frame.type === 'get_readiness').length, 1)
  ctx.client.refreshReadiness(true)
  assert.equal(ctx.sent.filter(frame => frame.type === 'get_readiness').length, 2)
  assert.equal(ctx.sent.filter(frame => frame.type === 'application_command').length, 0)
  ctx.client.disconnected()
})

test('A failed background observation is projected once as readiness, not as an extra chat error', () => {
  const ctx = setup()
  const request = ctx.sent.find(frame => frame.type === 'get_readiness')
  ctx.client.receive({ type: 'error', id: request.id, code: 'READINESS_BUSY', message: 'Internal probe busy' })
  assert.equal(ctx.client.view.readiness.ready, false)
  assert.equal(ctx.client.view.readiness.reason, 'READINESS_CHECK_FAILED')
  assert.equal(ctx.client.view.error, null)
  assert.deepEqual(ctx.client.view.messages, [])
  ctx.client.disconnected()
})

test('Persistence waits for both accepted selection and exact newer runtime snapshot', async () => {
  const ctx = setup()
  observation(ctx)
  const promise = ctx.client.command('ChangeModel', { modelId: 'model:new' })
  const request = ctx.sent.find(frame => frame.type === 'application_command')
  assert.deepEqual(ctx.confirmed, [])
  ctx.client.receive({ type: 'application_result', id: request.id,
    data: { schemaVersion: 1, commandId: request.command.commandId, accepted: true, createdIds: {} } })
  await promise
  assert.deepEqual(ctx.confirmed, [])
  const refresh = ctx.sent.filter(frame => frame.type === 'get_snapshot').at(-1)
  ctx.client.receive({ type: 'snapshot', id: refresh.id, data: snapshot('model:new', 2) })
  assert.deepEqual(ctx.confirmed, [{ providerId: 'ollama', modelId: 'model:new' }])
  assert.equal(ctx.client.view.readiness.ready, false)
  observation(ctx, { modelId: 'model:new', providerRevision: 2 })
  assert.equal(ctx.client.view.readiness.ready, true)
  ctx.client.disconnected()
})

test('Denied, mismatched or stale model selections are never persisted', async () => {
  for (const accepted of [true, false]) {
    const ctx = setup()
    const promise = ctx.client.command('ChangeModel', { modelId: 'model:new' })
    const request = ctx.sent.find(frame => frame.type === 'application_command')
    ctx.client.receive({ type: 'application_result', id: request.id,
      data: { schemaVersion: 1, commandId: request.command.commandId, accepted, createdIds: {} } })
    await promise
    const refresh = ctx.sent.filter(frame => frame.type === 'get_snapshot').at(-1)
    ctx.client.receive({ type: 'snapshot', id: refresh.id, data: snapshot('model:other', 2) })
    assert.deepEqual(ctx.confirmed, [])
    if (accepted) assert.equal(ctx.client.view.error.code, 'MODEL_SELECTION_NOT_CONFIRMED')
    ctx.client.disconnected()
  }
})

test('An accepted selection whose snapshot fails terminates confirmation without repeating ChangeModel', async () => {
  const ctx = setup()
  const promise = ctx.client.command('ChangeModel', { modelId: 'model:new' })
  const request = ctx.sent.find(frame => frame.type === 'application_command')
  ctx.client.receive({ type: 'application_result', id: request.id,
    data: { schemaVersion: 1, commandId: request.command.commandId, accepted: true, createdIds: {} } })
  await promise
  const refresh = ctx.sent.filter(frame => frame.type === 'get_snapshot').at(-1)
  ctx.client.receive({ type: 'error', id: refresh.id, code: 'SNAPSHOT_FAILED' })
  assert.equal(ctx.client.view.error.code, 'MODEL_SELECTION_NOT_CONFIRMED')
  assert.deepEqual(ctx.confirmed, [])
  assert.equal(ctx.sent.filter(frame => frame.type === 'application_command').length, 1)
  ctx.client.disconnected()
})

test('A missing snapshot has a bounded confirmation deadline and cannot persist a later result', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const ctx = setup()
  const promise = ctx.client.command('ChangeModel', { modelId: 'model:new' })
  const request = ctx.sent.find(frame => frame.type === 'application_command')
  ctx.client.receive({ type: 'application_result', id: request.id,
    data: { schemaVersion: 1, commandId: request.command.commandId, accepted: true, createdIds: {} } })
  await promise
  t.mock.timers.tick(10_001)
  assert.equal(ctx.client.view.error.code, 'MODEL_SELECTION_NOT_CONFIRMED')
  const refresh = ctx.sent.filter(frame => frame.type === 'get_snapshot').at(-1)
  ctx.client.receive({ type: 'snapshot', id: refresh.id, data: snapshot('model:new', 2) })
  assert.deepEqual(ctx.confirmed, [])
  assert.equal(ctx.sent.filter(frame => frame.type === 'application_command').length, 1)
  ctx.client.disconnected()
})

test('A persistence error is visible without lying about the current model or changing readiness', () => {
  const ctx = setup()
  observation(ctx)
  ctx.client.setModelPreferenceError('MODEL_PREFERENCE_SAVE_FAILED')
  assert.equal(ctx.client.view.modelPreferenceError, 'MODEL_PREFERENCE_SAVE_FAILED')
  assert.equal(ctx.client.view.status.model, 'model:old')
  assert.equal(ctx.client.view.readiness.ready, true)
  ctx.client.disconnected()
})

test('automatic readiness checks pause during generation and do not repeat user operations',t=>{
  t.mock.timers.enable({apis:['setTimeout','Date'],now:Date.now()})
  const ctx=setup({turns:[{turnId:'turn',status:'running',activeGenerationId:'generation'}]})
  observation(ctx)
  const count=ctx.sent.filter(f=>f.type==='get_readiness').length
  t.mock.timers.tick(16000)
  ctx.client.refreshReadiness()
  assert.equal(ctx.sent.filter(f=>f.type==='get_readiness').length,count)
  assert.equal(ctx.client.view.readiness.ready,true)
  assert.equal(ctx.client.view.activeTurnId,'turn')
  ctx.client.disconnected()
})
test('readiness deadline covers both provider calls and late errors stay with their retired request',t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  const ctx=setup();observation(ctx)
  ctx.client.refreshReadiness(true)
  const request=ctx.sent.filter(f=>f.type==='get_readiness').at(-1)
  t.mock.timers.tick(20001)
  assert.equal(ctx.client.view.readiness.reason,'CHECKING')
  t.mock.timers.tick(55000)
  assert.equal(ctx.client.view.readiness.reason,'READINESS_CHECK_FAILED')
  assert.equal(ctx.client.view.readiness.ready,false)
  assert.equal(ctx.client.view.readiness.installedModels.length,2)
  ctx.client.receive({id:request.id,type:'error',code:'READINESS_PROBE_FAILED'})
  assert.equal(ctx.client.view.error,null)
  ctx.client.refreshReadiness(true)
  const next=ctx.sent.filter(f=>f.type==='get_readiness').at(-1)
  ctx.client.receive({id:next.id,type:'error',code:'READINESS_BUSY'})
  assert.equal(ctx.client.view.readiness.installedModels.length,2)
  assert.equal(ctx.client.view.error,null)
  ctx.client.refreshReadiness(true);observation(ctx)
  assert.equal(ctx.client.view.readiness.ready,true)
  assert.equal(ctx.sent.filter(f=>f.type==='application_command').length,0)
  ctx.client.disconnected()
})

async function acceptModelSwitch(ctx,modelId){
 const promise=ctx.client.command('ChangeModel',{modelId})
 const request=ctx.sent.filter(f=>f.type==='application_command').at(-1)
 ctx.client.receive({type:'application_result',id:request.id,data:{schemaVersion:1,commandId:request.command.commandId,accepted:true,createdIds:{}}})
 await promise
 return request
}
test('model switch drains the previous probe before checking the confirmed runtime, including obsolete failures',async()=>{
 for(const terminal of ['readiness','error']){
  const ctx=setup(),old=ctx.sent.find(f=>f.type==='get_readiness')
  await acceptModelSwitch(ctx,'model:new')
  ctx.client.refreshReadiness(true)
  assert.equal(ctx.sent.filter(f=>f.type==='get_readiness').length,1,'no probe of old runtime after acceptance')
  ctx.client.receive({type:'snapshot',id:ctx.sent.filter(f=>f.type==='get_snapshot').at(-1).id,data:snapshot('model:new',2)})
  assert.equal(ctx.sent.filter(f=>f.type==='get_readiness').length,1,'old backend probe still owns its slot')
  if(terminal==='error')ctx.client.receive({id:old.id,type:'error',code:'READINESS_PROBE_FAILED'})
  else observation(ctx,{ready:false,reason:'OLLAMA_UNAVAILABLE',installedModels:[]})
  const current=ctx.sent.filter(f=>f.type==='get_readiness').at(-1)
  assert.notEqual(current.id,old.id)
  assert.equal(ctx.client.view.readiness.reason,'CHECKING')
  assert.equal(ctx.client.view.error,null)
  observation(ctx,{modelId:'model:new',providerRevision:2})
  assert.equal(ctx.client.view.readiness.ready,true)
  ctx.client.receive({id:old.id,type:'error',code:'LATE_PROBE_ERROR'})
  assert.equal(ctx.client.view.readiness.ready,true);assert.equal(ctx.client.view.error,null)
  assert.equal(ctx.sent.filter(f=>f.type==='application_command').length,1)
  ctx.client.disconnected()
 }
})
test('model switch checks only the new revision and still exposes a real current Ollama failure',async()=>{
 const ctx=setup();observation(ctx)
 const count=ctx.sent.filter(f=>f.type==='get_readiness').length
 await acceptModelSwitch(ctx,'model:new');ctx.client.refreshReadiness(true)
 assert.equal(ctx.sent.filter(f=>f.type==='get_readiness').length,count)
 ctx.client.receive({type:'snapshot',id:ctx.sent.filter(f=>f.type==='get_snapshot').at(-1).id,data:snapshot('model:new',2)})
 assert.equal(ctx.sent.filter(f=>f.type==='get_readiness').length,count+1)
 observation(ctx,{modelId:'model:new',providerRevision:2,ready:false,reason:'OLLAMA_UNAVAILABLE',installedModels:[]})
 assert.equal(ctx.client.view.readiness.ready,false)
 assert.equal(ctx.client.view.readiness.reason,'OLLAMA_UNAVAILABLE')
 ctx.client.disconnected()
})
