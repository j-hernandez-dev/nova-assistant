require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const {DesktopApplicationClient}=require('../electron/application_client.ts')

function setup(){
  const sent=[],client=new DesktopApplicationClient(frame=>sent.push(frame),()=>{})
  client.receive({type:'ready',sessionId:'ses-display',tools:[]})
  const status={schemaVersion:1,domain:'ACTIVE_WEB',processModel:'HOST_UNISOLATED',passiveWebIndependent:true,
    capabilities:{available:{status:'UNKNOWN',value:null,reason:'not certified'}},
    browserSession:{browserSessionRef:'opaque',state:'HUMAN_TAKEOVER',browserContextEpoch:0},
    pages:[{pageRef:'opaque-page',title:'<script>untrusted()</script>',origin:'https://source.test'}],
    takeoverRequests:[{takeoverRef:'opaque-human',reason:'LOGIN',deadline:'2026-10-10T00:00:00Z'}],
    receipts:[{operationId:'operation',outcome:'UNKNOWN',effectState:'unknown',retryAllowed:false}],cleanup:null}
  const snapshot={sessionId:'ses-display',workspace:'synthetic',stateRevision:2,lastSequence:1,
    transcript:[],turns:[],modelRuntime:{modelId:'test',providerId:'ollama',providerRevision:1},
    services:{rag:{enabled:false,availability:'DISABLED'},activeWeb:status}}
  client.receive({type:'snapshot',id:sent.at(-1).id,data:snapshot})
  return {sent,client,status}
}

test('Active Web projected from Application, not authority or second browser',async()=>{
  const {sent,client,status}=setup()
  assert.deepEqual(client.view.activeWeb,status)
  assert.equal(client.view.activeWeb.capabilities.available.value,null)
  const denied=await client.command('BrowserNavigate',{url:'file:///private'})
  assert.equal(denied.accepted,false)
  assert.equal(sent.filter(f=>f.type==='application_command').length,0)
  assert.equal(client.view.activeWeb.receipts[0].outcome,'UNKNOWN')
})

test('Browser event refreshes authority snapshot; no optimistic success or retry',()=>{
  const {sent,client,status}=setup();const sub=sent.find(f=>f.type==='subscribe_events').id
  client.receive({id:sub,type:'event',schemaVersion:1,event:{schemaVersion:1,eventId:'event',sequence:2,
    sessionId:'ses-display',stateRevision:2,kind:'BrowserOutcomeUnknown',payload:{outcome:'UNKNOWN'}}})
  assert.equal(sent.at(-1).type,'get_snapshot')
  assert.deepEqual(client.view.activeWeb,status)
  client.disconnected();assert.equal(client.view.activeWeb,undefined)
  assert.equal(sent.filter(f=>f.type==='application_command').length,0)
})

test('Browser UI is text only, never iframe/webview/page scripts/Policy',()=>{
  const src=fs.readFileSync('src/App.tsx','utf8')
  const section=src.slice(src.indexOf('<section aria-label="Active Web status"'),src.indexOf('</section>',src.indexOf('<section aria-label="Active Web status"')))
  assert(section.includes('HOST_UNISOLATED'))
  assert(!/iframe|webview|dangerouslySetInnerHTML|loadURL|PolicyEngine|BrowserWindow/.test(section))
  assert(section.includes('page.title')&&section.includes('takeoverRequests')&&section.includes('receipt.outcome'))
})
