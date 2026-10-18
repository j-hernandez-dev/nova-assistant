require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { DesktopApplicationClient } = require('../electron/application_client.ts')

function services() {
  return {
    rag: { enabled: false, availability: 'DISABLED' },
    fetch: { enabled: true, available: true },
    search: { backend: 'browser', engine: 'bing', available: true, adapter: 'WEBVIEW2',
      runtimeCheckedOnUse: true, unavailableReason: null, serverRequired: false, networkIsolation: 'NOT_PROVIDED' },
    browser: { selected: 'webview2', available: true, adapter: 'WEBVIEW2', runtimeCheckedOnUse: true,
      unavailableReason: null, networkIsolation: 'NOT_PROVIDED', controlClass: 'HOST_UNISOLATED',
      controlState: 'agentActive', sessionState: 'notStarted', hasPage: false, lastErrorCode: null,
      choices: ['webview2', 'chrome', 'edge'].map(browser => ({browser, available: browser !== 'chrome',
        installed: browser !== 'chrome', adapter: browser.toUpperCase(), reason: browser === 'chrome' ? 'BROWSER_NOT_INSTALLED' : null})) },
    memory: { lexicalRecall: true, semantic: false, autoCapture: false, captureMode: 'off', allowRemoteMemoryInjection: false },
    interactions: { approvals: [], inputs: [] },
  }
}
function state(changes = {}) {
  return { sessionId: 'session', workspace: '/owned/workspace', stateRevision: 4, lastSequence: 4,
    transcript: [], turns: [], modelRuntime: { modelId: 'fixture:9b', providerId: 'ollama', providerRevision: 1 },
    services: services(), ...changes }
}
function setup(snapshot = state()) {
  const sent = [], views = []
  const client = new DesktopApplicationClient(frame => sent.push(frame), view => views.push(view), () => 'owned-proof')
  client.receive({ type: 'ready', sessionId: snapshot.sessionId, tools: [] })
  const c = { client, sent, views }
  replySnapshot(c, snapshot)
  return c
}
function replySnapshot(c, snapshot) {
  const request = c.sent.findLast(frame => frame.type === 'get_snapshot')
  c.client.receive({ type: 'snapshot', id: request.id, data: snapshot })
}
function receipt(c, request, accepted, error) {
  c.client.receive({type:'application_result',id:request.id,data:{schemaVersion:1,
    commandId:request.command.commandId,accepted,createdIds:{},error:error || null}})
}
const domains = ['fetch', 'search', 'browser', 'memory']

test('settings have no effective value before an authoritative snapshot', () => {
  const sent = []
  const client = new DesktopApplicationClient(frame => sent.push(frame), () => {})
  for (const name of domains) assert.equal(client.view[name], undefined)
  client.receive({type:'ready',sessionId:'session',tools:['web_search','web_fetch']})
  for (const name of domains) assert.equal(client.view[name], undefined)
  client.disconnected()
})

test('domain projections copy confirmed values without paths, credentials or Browser control results', () => {
  const original = services()
  original.browser.choices[0].executable = 'C:/private/browser.exe'
  original.browser.choices[0].message = 'private raw host detail'
  original.browser.lastControlResult = { path: 'C:/private/upload.bin', token: 'never-in-settings' }
  original.memory.records = [{canonicalText:'private memory'}]
  original.fetch.providerSecret = 'hidden'
  const c = setup(state({services:original}))
  assert.deepEqual(c.client.view.fetch, {enabled:true,available:true})
  assert.equal(c.client.view.search.engine, 'bing')
  assert.equal(c.client.view.browser.selected, 'webview2')
  assert.equal(c.client.view.memory.captureMode, 'off')
  assert.equal(c.client.view.browser.networkIsolation, 'NOT_PROVIDED')
  assert.equal(c.client.view.browser.controlClass, 'HOST_UNISOLATED')
  const json = JSON.stringify(domains.map(key => c.client.view[key]))
  assert.doesNotMatch(json, /private|hidden|never-in-settings|providerSecret|canonicalText/)
  original.browser.choices[0].available = false
  original.memory.autoCapture = true
  assert.equal(c.client.view.browser.choices[0].available, true)
  assert.equal(c.client.view.memory.autoCapture, false)
  c.client.disconnected()
})

test('malformed or absent service snapshots never become invented defaults', () => {
  const s = services()
  s.fetch.enabled = 'false'
  s.search.engine = 'unsupported'
  s.browser.networkIsolation = 'PUBLIC_ONLY'
  s.memory.allowRemoteMemoryInjection = 'true'
  const c = setup(state({services:s}))
  for (const key of domains) assert.equal(c.client.view[key], undefined)
  assert.equal(c.client.view.memoryNotice, null)
  c.client.refresh(); replySnapshot(c,state({stateRevision:5,lastSequence:5,services:{rag:s.rag}}))
  for (const key of domains) assert.equal(c.client.view[key], undefined)
  c.client.disconnected()
})

test('service setters validate exact schemas and cannot become arbitrary commands or Memory controls', async () => {
  const c = setup()
  const invalid = [
    ['SetFetchEnabled', {enabled:'true'}], ['SetFetchEnabled',{enabled:true,allowAll:true}],
    ['SetFetchEnabled',{}], ['SetFetchEnabled',null], ['SetSearchEngine',{engine:'searxng'}],
    ['SetSearchEngine',{engine:'bing',endpoint:'https://private.invalid'}], ['SetBrowser',{browser:'firefox'}],
    ['SetBrowser',{browser:'edge',path:'C:/program.exe'}], ['SetBrowser',['edge']],
  ]
  const start = c.sent.length
  for (const [kind,payload] of invalid) assert.equal((await c.client.command(kind,payload)).error.code,'INVALID_APPLICATION_COMMAND')
  assert.equal((await c.client.command('SetMemoryEnabled',{enabled:true})).accepted,false)
  assert.equal((await c.client.command('BrowserControl',{action:'resume'})).accepted,false)
  assert.equal(c.sent.length,start)
  c.client.disconnected()
})

test('an accepted setter is scoped and revision-bound; the receipt is not an optimistic state update', async () => {
  for (const [kind,payload,key] of [['SetFetchEnabled',{enabled:false},'fetch'],
    ['SetSearchEngine',{engine:'google'},'search'], ['SetBrowser',{browser:'edge'},'browser']]) {
    const c = setup(), before = structuredClone(c.client.view[key])
    const pending = c.client.command(kind,payload,'owned-change')
    const request = c.sent.at(-1)
    assert.equal(request.type,'application_command')
    assert.equal(request.command.sessionId,'session')
    assert.equal(request.command.expectedRevision,4)
    assert.deepEqual(request.command.payload,payload)
    assert.deepEqual(c.client.view[key],before)
    receipt(c,request,true)
    assert.equal((await pending).accepted,true)
    assert.deepEqual(c.client.view[key],before)
    const updated = services()
    if (key === 'fetch') updated.fetch = {enabled:false,available:false}
    if (key === 'search') updated.search.engine = 'google'
    if (key === 'browser') updated.browser.selected = 'edge'
    replySnapshot(c,state({stateRevision:5,lastSequence:5,services:updated}))
    assert.deepEqual(c.client.view[key],key === 'browser' ? {...before,selected:'edge'} : updated[key])
    assert.deepEqual(c.client.view.memory,services().memory)
    assert.equal(c.client.view.approvals.length,0)
    assert.equal(c.sent.some(frame => frame.command?.kind === 'ResolveApproval'),false)
    c.client.disconnected()
  }
})

test('a failed save preserves the old snapshot in every domain', async () => {
  const c = setup(), before = structuredClone(domains.map(key => c.client.view[key]))
  const pending = c.client.command('SetBrowser',{browser:'edge'},'failed-save')
  receipt(c,c.sent.at(-1),false,{code:'BROWSER_CONFIGURATION_FAILED',message:'Could not save.'})
  assert.equal((await pending).error.code,'BROWSER_CONFIGURATION_FAILED')
  assert.deepEqual(domains.map(key => c.client.view[key]),before)
  replySnapshot(c,state({stateRevision:5,lastSequence:5}))
  assert.deepEqual(domains.map(key => c.client.view[key]),before)
  c.client.disconnected()
})

test('stale or cross-session snapshots cannot replace confirmed settings', () => {
  const c = setup()
  c.client.refresh(); replySnapshot(c,state({sessionId:'other-session',services:{rag:services().rag,fetch:{enabled:false,available:false}}}))
  assert.equal(c.client.view.fetch.enabled,true)
  c.client.refresh(); replySnapshot(c,state({stateRevision:3,lastSequence:3,services:{rag:services().rag,fetch:{enabled:false,available:false}}}))
  assert.equal(c.client.view.fetch.enabled,true)
  c.client.disconnected()
})

test('disconnect clears observations and settles pending save as unknown without retry', async () => {
  const c = setup()
  const pending = c.client.command('SetFetchEnabled',{enabled:false})
  const before = c.sent.length
  c.client.disconnected()
  assert.equal((await pending).error.code,'OUTCOME_UNKNOWN')
  for (const key of domains) assert.equal(c.client.view[key],undefined)
  assert.equal(c.sent.length,before)
})

test('a fresh backend/session clears old observations and rejects old pending-setting confirmation', async () => {
  const c = setup()
  const pending = c.client.command('SetBrowser',{browser:'edge'})
  const old = c.sent.at(-1)
  c.client.receive({type:'ready',sessionId:'new-session',tools:[]})
  assert.equal((await pending).error.code,'OUTCOME_UNKNOWN')
  for (const key of domains) assert.equal(c.client.view[key],undefined)
  receipt(c,old,true)
  assert.equal(c.client.view.browser,undefined)
  const fresh = services(); fresh.browser.selected = 'chrome'; fresh.browser.available = false
  fresh.browser.unavailableReason = 'BROWSER_NOT_INSTALLED'
  replySnapshot(c,state({sessionId:'new-session',stateRevision:0,lastSequence:0,workspace:'/owned/other',services:fresh}))
  assert.equal(c.client.view.browser.selected,'chrome')
  assert.equal(c.client.view.browser.available,false)
  assert.equal(c.client.view.browser.unavailableReason,'BROWSER_NOT_INSTALLED')
  c.client.disconnected()
})

test('workspace changes and service settings cannot cross scopes while pending', async () => {
  const c = setup()
  const pending = c.client.command('SetSearchEngine',{engine:'google'})
  assert.equal(c.client.workspaceBusy(),true)
  assert.equal((await c.client.changeWorkspace('/owned/other')).error.code,'PROJECT_BUSY')
  receipt(c,c.sent.at(-1),true); await pending
  const workspace = c.client.changeWorkspace('/owned/other')
  const before = c.sent.length
  assert.equal((await c.client.command('SetFetchEnabled',{enabled:false})).error.code,'PROJECT_BUSY')
  assert.equal(c.sent.length,before)
  c.client.disconnected(); await workspace
})

test('Memory inspection still uses the existing authenticated, revision-bound control', async () => {
  const c = setup()
  const pending = c.client.memory('memory_status',{},'memory-status')
  const request = c.sent.at(-1)
  assert.equal(request.type,'memory_command')
  assert.equal(request.command.kind,'MemoryControl')
  assert.equal(request.command.expectedRevision,4)
  assert.equal(request.hostMemoryProof,'owned-proof')
  c.client.receive({type:'memory_result',id:request.id,data:{schemaVersion:1,commandId:'memory-status',completed:true,
    data:{available:true,captureMode:'off'}}})
  assert.equal((await pending).completed,true)
  assert.equal(c.client.view.memory.captureMode,'off')
  assert.equal(c.client.view.messages.length,0)
  c.client.disconnected()
})
