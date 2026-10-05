// Node executes the real TS display projection; no Electron/GPU/network.
const test = require('node:test')
const assert = require('node:assert/strict')
const { pathToFileURL } = require('node:url')
const path = require('node:path')

async function ready() {
  const { DesktopApplicationClient } = await import(pathToFileURL(path.resolve(__dirname,'../electron/application_client.ts')))
  const sent = [], published = []
  const client = new DesktopApplicationClient(f=>sent.push(f),v=>published.push(v))
  client.receive({type:'ready',sessionId:'session',tools:['bash']})
  const state = {sessionId:'session',workspace:'fixture',lastSequence:0,stateRevision:1,
    transcript:[],turns:[],modelRuntime:{modelId:'fixture',providerId:'fixture',providerRevision:1},
    services:{rag:{enabled:false,availability:'UNKNOWN'},interactions:{approvals:[],inputs:[]}}}
  client.receive({type:'snapshot',id:sent.find(f=>f.type==='get_snapshot').id,data:state})
  return {client,sent,state,published}
}

test('audit gap warns without changing transcript/lifecycle or retrying an effect',async()=>{
  const {client,sent} = await ready()
  const before = client.view.messages
  client.receive({type:'event',id:sent.find(f=>f.type==='subscribe_events').id,schemaVersion:1,
    event:{schemaVersion:1,sessionId:'session',eventId:'e',sequence:1,stateRevision:2,kind:'ToolCompleted',
      operationId:'operation',payload:{name:'bash',status:'completed',effectState:'unknown',securityAudit:{gap:true,retryAllowed:false}}}})
  assert.equal(client.view.error.code,'SECURITY_AUDIT_DELIVERY_FAILED')
  assert.equal(client.view.messages,before)
  assert.equal(client.view.activeTurnId,null)
  assert.equal(sent.filter(f=>f.type==='application_command').length,0)
})

test('reconnect snapshot discloses audit delivery loss without inventing a failed Turn',async()=>{
  const {client,sent,state} = await ready()
  client.refresh()
  const id = sent.filter(f=>f.type==='get_snapshot').at(-1).id
  client.receive({type:'snapshot',id,data:{...state,turns:[{turnId:'t',status:'completed'}],
    services:{...state.services,securityAudit:{deliveryFailures:1,lastError:null,storageGapCodes:[]}}}})
  assert.equal(client.view.error.code,'SECURITY_AUDIT_DELIVERY_FAILED')
  assert.match(client.view.error.message,/Observed result retained/)
  assert.equal(client.view.activeTurnId,null)
})
