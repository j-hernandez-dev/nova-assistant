require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const {DesktopApplicationClient}=require('../electron/application_client.ts')
const {configureWebV12,selectWebV12Upload,finishWebV12Takeover,RISK_ACKNOWLEDGEMENT_VERSION,RISK_MESSAGE,RISK_DETAIL}=require('../electron/web_v12_control.cjs')
const path=require('node:path')

const known=value=>({status:'KNOWN',value,reason:null})
function capabilities(fetch,browser) {
  return {schemaVersion:1,schema:'WEB_CAPABILITIES_V12_1',controlledFetch:{
    capabilityId:'CONTROLLED_FETCH_V1_2',available:known(fetch),unavailableReason:fetch?null:'FEATURE_DISABLED',
    evidenceProfile:known('CF_B2_GET_HEAD_HTTP11_WINDOWS_V1'),networkEgressControl:known('ENFORCED'),
    publicOnly:known('ENFORCED'),controlClass:known('APPLICATION_ENFORCED'),methods:['GET','HEAD'],
    resultModes:['TEXT','HTML_STATIC','JSON'],postAvailable:false,authAvailable:false,
    binaryDownloadAvailable:false,cookieJar:false,browserSessionImport:false},interactiveBrowser:{
    capabilityId:'INTERACTIVE_BROWSER_V1_2',available:known(browser),unavailableReason:browser?null:'FEATURE_DISABLED',
    evidenceProfile:known('IB_V12_B6_CANDIDATE'),networkIsolation:known('NOT_PROVIDED'),
    controlClass:known('HOST_UNISOLATED'),adapter:known('WEBVIEW2'),externalProtocolGuard:known('ENFORCED'),
    remoteMutationControl:known('ENFORCED'),secretBoundary:known('ENFORCED'),formSubmitAvailable:false,
    subagentsBrowserByDefault:false,persistentSession:false,screenshot:false}}
}
function snapshot(caps,configuration={controlledFetchEnabled:false,interactiveBrowserEnabled:false,
  riskAcknowledgementVersion:null},browserState=null,sequence=1) {
  return {sessionId:'ses-v12',workspace:'synthetic',stateRevision:sequence,lastSequence:sequence,
    transcript:[],turns:[],modelRuntime:{modelId:'test',providerId:'ollama',providerRevision:1},
    services:{rag:{enabled:false,availability:'DISABLED'},webCapabilitiesV12:caps,
      webV12:{configuration,browserState}}}
}
function setup(caps=capabilities(false,false),proof) {
  const sent=[],client=new DesktopApplicationClient(f=>sent.push(f),()=>{},proof)
  client.receive({type:'ready',sessionId:'ses-v12',tools:[]})
  client.receive({type:'snapshot',id:sent.at(-1).id,data:snapshot(caps)})
  return {sent,client}
}
function refresh(ctx,data) {
  ctx.client.refresh()
  ctx.client.receive({type:'snapshot',id:ctx.sent.at(-1).id,data})
}

for (const [fetch,browser] of [[false,false],[true,false],[false,true],[true,true]]) {
  test(`V12 independent availability projection Fetch=${fetch} Browser=${browser}`,()=>{
    const c=setup(capabilities(fetch,browser))
    assert.equal(c.client.view.webCapabilitiesV12.controlledFetch.available.value,fetch)
    assert.equal(c.client.view.webCapabilitiesV12.interactiveBrowser.available.value,browser)
    assert.equal(c.client.view.webCapabilitiesV12.interactiveBrowser.networkIsolation.value,'NOT_PROVIDED')
    assert.equal(c.client.view.activeWeb,undefined)
    assert.equal(c.sent.filter(f=>f.type==='browser_control'||f.type==='application_command').length,0)
  })
}
test('legacy Active Web metadata cannot activate V12 or alter its browser claim',()=>{
  const c=setup(capabilities(false,false));const state=snapshot(capabilities(false,false),undefined,null,2)
  state.services.activeWeb={capabilities:{available:known(true),publicOnly:known(true)}}
  refresh(c,state)
  assert.equal(c.client.view.webCapabilitiesV12.interactiveBrowser.available.value,false)
  assert.equal(c.client.view.webCapabilitiesV12.interactiveBrowser.networkIsolation.value,'NOT_PROVIDED')
  assert.deepEqual(c.client.view.activeWeb,state.services.activeWeb)
})
test('backend compatibility revocation replaces cached true immediately',()=>{
  const c=setup(capabilities(true,true)),revoked=capabilities(false,true)
  revoked.controlledFetch.unavailableReason='TRANSPORT_IDENTITY_MISMATCH'
  revoked.controlledFetch.publicOnly={status:'UNKNOWN',value:null,reason:'EVIDENCE_INCOMPATIBLE'}
  refresh(c,snapshot(revoked,undefined,null,2))
  assert.deepEqual(c.client.view.webCapabilitiesV12,revoked)
  assert.equal(c.client.view.webCapabilitiesV12.interactiveBrowser.available.value,true)
})
test('takeover and mutation uncertainty are backend projections without automatic resume',()=>{
  const c=setup(capabilities(true,true))
  for (const [i,state] of ['humanActive','resumePending','blocked'].entries()) {
    refresh(c,snapshot(capabilities(true,true),undefined,state,i+2))
    assert.equal(c.client.view.webV12.browserState,state)
  }
  assert.equal(c.sent.filter(f=>f.type==='browser_control'||f.type==='application_command').length,0)
})
test('browser control requires main host proof and cannot use generic Application command',async()=>{
  const c=setup(capabilities(true,true))
  assert.equal((await c.client.browser('configure_web_v12',{})).error.code,'BROWSER_HUMAN_CONTROL_DENIED')
  assert.equal((await c.client.command('ConfigureWebV12',{available:true})).accepted,false)
  assert.equal(c.sent.filter(f=>f.type==='browser_control').length,0)
})
test('host configuration uses the existing authenticated browser_control Application wire path',async()=>{
  const signed=[],c=setup(capabilities(false,false),command=>{signed.push(command);return 'private-test-proof'})
  const config={controlledFetchEnabled:true,interactiveBrowserEnabled:true}
  const pending=configureWebV12(c.client,config,async()=>({response:1}),'cmd-v12-config')
  await new Promise(resolve=>setImmediate(resolve))
  const frame=c.sent.at(-1)
  assert.equal(frame.type,'browser_control')
  assert.equal(frame.hostBrowserProof,'private-test-proof')
  assert.deepEqual(frame.command,{commandId:'cmd-v12-config',sessionId:'ses-v12',name:'configure_web_v12',
    arguments:{...config,acknowledgementVersion:RISK_ACKNOWLEDGEMENT_VERSION}})
  assert.deepEqual(signed,[frame.command])
  assert.equal(c.client.view.webCapabilitiesV12.interactiveBrowser.available.value,false)
  c.client.receive({type:'browser_control_result',id:frame.id,data:{configuration:config}})
  assert.deepEqual(await pending,{configuration:config})
  assert.equal(c.sent.at(-1).type,'get_snapshot')
  assert.equal(c.sent.filter(f=>f.command?.kind==='ResolveApproval').length,0)
})
test('configuration receipt does not invent availability, Approval or browser authority',async()=>{
  const c=setup(capabilities(false,false),()=> 'proof')
  const pending=c.client.browser('configure_web_v12',{controlledFetchEnabled:true,interactiveBrowserEnabled:false,
    acknowledgementVersion:RISK_ACKNOWLEDGEMENT_VERSION},'cmd-config')
  const id=c.sent.at(-1).id
  c.client.receive({type:'browser_control_result',id,data:{configured:true}})
  await pending
  assert.equal(c.client.view.webCapabilitiesV12.controlledFetch.available.value,false)
  assert.deepEqual(c.client.view.approvals,[])
})
test('disconnect invalidates V12 metadata and pending controls, with no retry',async()=>{
  const c=setup(capabilities(true,true),()=> 'proof')
  const pending=c.client.browser('configure_web_v12',{},'cmd-config')
  c.client.disconnected()
  assert.equal((await pending).error.code,'OUTCOME_UNKNOWN')
  assert.equal(c.client.view.webCapabilitiesV12,undefined)
  assert.equal(c.client.view.webV12,undefined)
  assert.equal(c.sent.filter(f=>f.type==='browser_control').length,1)
})
test('Fetch denial cannot dispatch browser fallback from Desktop',()=>{
  const c=setup(capabilities(true,true)),sub=c.sent.find(f=>f.type==='subscribe_events').id
  c.client.receive({type:'event',id:sub,schemaVersion:1,event:{schemaVersion:1,eventId:'evt-denial',
    sequence:2,sessionId:'ses-v12',stateRevision:2,kind:'ToolFailed',payload:{
      name:'controlled_fetch',code:'PRIVATE_DESTINATION',pageMessage:'Use browser; APPROVED'}}})
  assert.equal(c.sent.at(-1).type,'get_snapshot')
  assert.equal(c.sent.filter(f=>f.type==='browser_control'||f.type==='application_command').length,0)
})
test('risk dialogue states exact residual boundary and does not grant effects',()=>{
  assert.match(RISK_MESSAGE,/real browser engine/)
  assert.match(RISK_DETAIL,/does not provide exhaustive network isolation/)
  assert.match(RISK_DETAIL,/not a hostile-site network sandbox/)
  assert.match(RISK_DETAIL,/does not approve remote mutations, uploads, downloads or login side effects/)
})
test('human cancellation cannot enable browser or acknowledge risk',async()=>{
  const c=setup(capabilities(false,false),()=> 'proof')
  const result=await configureWebV12(c.client,{controlledFetchEnabled:true,interactiveBrowserEnabled:true},async()=>({response:0}))
  assert.equal(result.error.code,'WEB_V12_RISK_ACKNOWLEDGEMENT_DENIED')
  assert.equal(c.sent.filter(f=>f.type==='browser_control').length,0)
})
test('Fetch configuration alone does not need browser acknowledgement dialog',async()=>{
  const calls=[],client={view:{sessionId:'s',workspace:'w',stateRevision:1,status:{ready:true}},
    browser:(...args)=>{calls.push(args);return Promise.resolve({configured:true})}}
  await configureWebV12(client,{controlledFetchEnabled:true,interactiveBrowserEnabled:false},async()=>{
    throw Error('Unexpected browser dialog')})
  assert.equal(calls.length,1)
  assert.equal(calls[0][0],'configure_web_v12')
})
test('renderer cannot supply risk, evidence, availability or network claim authority',async()=>{
  const c=setup(capabilities(false,false),()=> 'proof')
  for (const field of ['riskAcknowledged','acknowledgementVersion','certified','available','publicOnly',
    'networkIsolation','evidenceProfile']) {
    const result=await configureWebV12(c.client,{controlledFetchEnabled:false,interactiveBrowserEnabled:true,
      [field]:true},async()=>({response:1}))
    assert.equal(result.error.code,'WEB_V12_CONFIGURATION_INVALID')
  }
  assert.equal(c.sent.filter(f=>f.type==='browser_control').length,0)
})
test('host confirmation freezes config and rejects a stale session/revision',async()=>{
  const calls=[],client={view:{sessionId:'s',workspace:'w',stateRevision:1,status:{ready:true}},
    browser:(...args)=>{calls.push(args);return Promise.resolve({configured:true})}}
  const request={controlledFetchEnabled:true,interactiveBrowserEnabled:true}
  const result=await configureWebV12(client,request,async()=>{
    request.interactiveBrowserEnabled=false
    client.view.stateRevision=2
    return {response:1}
  })
  assert.equal(result.error.code,'REVISION_CONFLICT')
  assert.equal(calls.length,0)
})
test('host confirmation binds the frozen request rather than a changed renderer object',async()=>{
  const calls=[],client={view:{sessionId:'s',workspace:'w',stateRevision:1,status:{ready:true}},
    browser:(...args)=>{calls.push(args);return Promise.resolve({configured:true})}}
  const request={controlledFetchEnabled:true,interactiveBrowserEnabled:true}
  await configureWebV12(client,request,async()=>{request.controlledFetchEnabled=false;return {response:1}})
  assert.equal(calls[0][1].controlledFetchEnabled,true)
})
test('Desktop bridge blocks raw browser control; UI contains projection and no engine/security implementation',()=>{
  const main=fs.readFileSync('electron/main.ts','utf8'),preload=fs.readFileSync('electron/preload.ts','utf8')
  const source=fs.readFileSync('src/App.tsx','utf8')
  assert(main.includes("data.type === 'browser_control'"))
  assert(main.includes("ipcMain.handle('configure-web-v12'"))
  assert(preload.includes("ipcRenderer.invoke('configure-web-v12'"))
  const begin=source.indexOf('<section aria-label="Web capabilities V1.2"')
  const section=source.slice(begin,source.indexOf('</section>',begin))
  assert(begin>=0)
  assert(section.includes('networkIsolation = NOT_PROVIDED'))
  assert(section.includes('No browser rendering'))
  assert(!/iframe|webview|dangerouslySetInnerHTML|loadURL|PolicyEngine|BrowserWindow|GrantIssuer/.test(section))
})
function uploadClient() {
  const calls=[],view={sessionId:'s',workspace:'w',stateRevision:1,status:{ready:true},webV12:{
    uploadRequests:[{operationId:'op-fixture',origin:'https://fixture.test',label:'Upload file'}]}}
  return {calls,client:{view,browser:(...args)=>{calls.push(args);return Promise.resolve({selected:true})}}}
}
test('upload host picker supplies a private exact-operation path; does not grant disclosure',async()=>{
  const c=uploadClient(),view=JSON.stringify(c.client.view),file=path.resolve('owned-test-file.txt')
  const result=await selectWebV12Upload(c.client,'op-fixture',async()=>({canceled:false,filePaths:[file]}),'cmd-select')
  assert.deepEqual(c.calls,[['select_upload',{operationId:'op-fixture',path:file},'cmd-select']])
  assert.deepEqual(result,{selected:true})
  assert.equal(JSON.stringify(c.client.view),view)
  assert(!JSON.stringify(result).includes(file))
})
test('upload renderer cannot select an arbitrary operation or submit paths as request objects',async()=>{
  const c=uploadClient()
  for (const target of ['other-operation',{operationId:'op-fixture',path:'/arbitrary'},null]) {
    const result=await selectWebV12Upload(c.client,target,async()=>{throw Error('Picker must not open')})
    assert(result.error)
  }
  assert.equal(c.calls.length,0)
})
test('cancelled upload picker never dispatches selection or disclosure',async()=>{
  const c=uploadClient()
  const result=await selectWebV12Upload(c.client,'op-fixture',async()=>({canceled:true,filePaths:[]}))
  assert.equal(result.error.code,'BROWSER_UPLOAD_SELECTION_CANCELLED')
  assert.equal(c.calls.length,0)
})
test('upload picker rejects multiple files and relative paths',async()=>{
  const c=uploadClient()
  for (const files of [['relative.txt'],[path.resolve('one.txt'),path.resolve('two.txt')],[]]) {
    const result=await selectWebV12Upload(c.client,'op-fixture',async()=>({canceled:false,filePaths:files}))
    assert.equal(result.error.code,'BROWSER_UPLOAD_SELECTION_CANCELLED')
  }
  assert.equal(c.calls.length,0)
})
test('upload dialog stale origin/node request cannot survive selection',async()=>{
  const c=uploadClient()
  const result=await selectWebV12Upload(c.client,'op-fixture',async()=>{
    c.client.view.webV12.uploadRequests[0].origin='https://changed.test'
    return {canceled:false,filePaths:[path.resolve('owned.txt')]}
  })
  assert.equal(result.error.code,'REVISION_CONFLICT')
  assert.equal(c.calls.length,0)
})
test('upload request retirement or epoch-driven snapshot revision denies selection',async()=>{
  for (const change of [client=>client.view.webV12.uploadRequests=[],client=>client.view.stateRevision++]) {
    const c=uploadClient()
    const result=await selectWebV12Upload(c.client,'op-fixture',async()=>{
      change(c.client);return {canceled:false,filePaths:[path.resolve('owned.txt')]}
    })
    assert.equal(result.error.code,'REVISION_CONFLICT')
    assert.equal(c.calls.length,0)
  }
})
test('upload UI bridge exposes only operationId and native picker, never renderer path authority',()=>{
  const preload=fs.readFileSync('electron/preload.ts','utf8'),main=fs.readFileSync('electron/main.ts','utf8')
  assert(preload.includes("selectWebV12Upload: (operationId:string) => ipcRenderer.invoke('web-v12-select-upload',operationId)"))
  assert(main.includes('selectWebV12Upload(applicationClient,operationId'))
  assert(main.includes("properties:['openFile']"))
})
function takeoverClient() {
  const calls=[],view={sessionId:'s',workspace:'w',stateRevision:1,status:{ready:true},webV12:{
    browserState:'humanActive',takeoverRequests:[{takeoverRef:'takeover-fixture',reason:'LOGIN',
      deadline:'2099-01-01T00:00:00Z',browserContextEpoch:3}]}}
  return {calls,client:{view,browser:(...args)=>{calls.push(args);return Promise.resolve({finished:true})}}}
}
test('finish takeover binds exact host request; does not assert login or remote Approval',async()=>{
  const c=takeoverClient(),before=JSON.stringify(c.client.view)
  const result=await finishWebV12Takeover(c.client,'takeover-fixture',async()=>({response:1}),'cmd-finish')
  assert.deepEqual(c.calls,[['finish_takeover',{takeoverRef:'takeover-fixture',authenticated:false},'cmd-finish']])
  assert.deepEqual(result,{finished:true})
  assert.equal(JSON.stringify(c.client.view),before)
  assert.equal(c.client.view.webV12.browserState,'humanActive')
})
test('finish takeover cancellation does not resume or dispatch',async()=>{
  const c=takeoverClient()
  const result=await finishWebV12Takeover(c.client,'takeover-fixture',async()=>({response:0}))
  assert.equal(result.error.code,'BROWSER_TAKEOVER_FINISH_CANCELLED')
  assert.equal(c.calls.length,0)
  assert.equal(c.client.view.webV12.browserState,'humanActive')
})
test('finish takeover rejects wrong request or model claimed authentication',async()=>{
  const c=takeoverClient()
  for (const target of ['different',{takeoverRef:'takeover-fixture',authenticated:true},null]) {
    const result=await finishWebV12Takeover(c.client,target,async()=>{throw Error('No dialog for unowned request')})
    assert(result.error)
  }
  assert.equal(c.calls.length,0)
})
test('finish takeover stale epoch or retired request cannot resume after dialog',async()=>{
  for (const change of [client=>client.view.webV12.takeoverRequests[0].browserContextEpoch++,
    client=>client.view.webV12.takeoverRequests=[],client=>client.view.stateRevision++]) {
    const c=takeoverClient()
    const result=await finishWebV12Takeover(c.client,'takeover-fixture',async()=>{change(c.client);return {response:1}})
    assert.equal(result.error.code,'REVISION_CONFLICT')
    assert.equal(c.calls.length,0)
  }
})
test('unconfirmed secret boundary blocks human finish and never publishes new agent state',async()=>{
  const c=takeoverClient();c.client.view.webV12.browserState='blocked'
  const result=await finishWebV12Takeover(c.client,'takeover-fixture',async()=>{throw Error('Blocked no dialog')})
  assert.equal(result.error.code,'BROWSER_TAKEOVER_REQUEST_UNAVAILABLE')
  assert.equal(c.calls.length,0)
  assert.equal(c.client.view.webV12.browserState,'blocked')
})
test('expired takeover cannot be finished with a new host confirmation',async()=>{
  const c=takeoverClient();c.client.view.webV12.takeoverRequests[0].deadline='2001-01-01T00:00:00Z'
  const result=await finishWebV12Takeover(c.client,'takeover-fixture',async()=>{throw Error('Expired no dialog')})
  assert.equal(result.error.code,'BROWSER_TAKEOVER_EXPIRED')
  assert.equal(c.calls.length,0)
})
test('finish takeover uses authenticated client wire without optimistic resume or retry',async()=>{
  const c=setup(capabilities(true,true),()=> 'proof')
  refresh(c,snapshot(capabilities(true,true),undefined,'humanActive',2))
  c.client.view.webV12.takeoverRequests=[{takeoverRef:'takeover-fixture',reason:'LOGIN',
    deadline:'2099-01-01T00:00:00Z',browserContextEpoch:3}]
  const pending=finishWebV12Takeover(c.client,'takeover-fixture',async()=>({response:1}),'cmd-finish')
  await new Promise(resolve=>setImmediate(resolve))
  const frame=c.sent.at(-1)
  assert.equal(frame.type,'browser_control')
  assert.equal(frame.hostBrowserProof,'proof')
  assert.deepEqual(frame.command.arguments,{takeoverRef:'takeover-fixture',authenticated:false})
  c.client.receive({type:'browser_control_result',id:frame.id,data:{finished:true}})
  await pending
  assert.equal(c.client.view.webV12.browserState,'humanActive')
  assert.equal(c.sent.at(-1).type,'get_snapshot')
  assert.equal(c.sent.filter(f=>f.type==='browser_control').length,1)
})
test('takeover UI host bridge exposes one request ref, no cookies or authentication claim',()=>{
  const preload=fs.readFileSync('electron/preload.ts','utf8'),main=fs.readFileSync('electron/main.ts','utf8')
  const app=fs.readFileSync('src/App.tsx','utf8')
  assert(preload.includes("finishWebV12Takeover: (takeoverRef:string) => ipcRenderer.invoke('web-v12-finish-takeover',takeoverRef)"))
  assert(main.includes('finishWebV12Takeover(applicationClient,takeoverRef'))
  assert(main.includes('Esto no declara un login ni aprueba efectos remotos'))
  assert(app.includes('Finalizar control humano'))
})
