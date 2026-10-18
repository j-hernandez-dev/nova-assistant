require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const {ModelDownload}=require('../electron/model_download.ts')
const {DesktopApplicationClient}=require('../electron/application_client.ts')
function setup(){
  const sent=[],states=[],installed=[];let probes=0,finished=0
  const download=new ModelDownload(frame=>sent.push(frame),state=>states.push(state),models=>installed.push(models),()=>probes++,()=>finished++)
  return {download,sent,states,installed,get probes(){return probes},get finished(){return finished}}
}
test('Only correlated progress and terminal frames update the host download; bytes at 100 percent retain the lock',()=>{
  const c=setup(),d=c.download
  assert.equal(d.start(12,'target:8b'),true);assert.equal(d.start(13,'other:1b'),false)
  for(const frame of [{id:13,type:'pull_done',model:'target:8b'},{id:12,type:'pull_progress',model:'other:1b',completed:99,total:100}])d.receive(frame)
  assert.equal(d.state.percent,null);assert.equal(d.state.phase,'downloading')
  d.receive({id:12,type:'pull_progress',model:'target:8b',completed:100,total:100,status:'verifying\nlayer'})
  assert.equal(d.state.percent,100);assert.equal(d.state.detail,'verifying layer');assert.equal(d.busy(),true);assert.equal(c.sent.length,0)
  d.receive({id:12,type:'pull_done',model:'target:8b'})
  assert.equal(d.state.phase,'refreshing');assert.equal(c.sent.at(-1).type,'catalog')
  assert.equal(d.busy(),true);d.disconnected()
})
test('Exact installed tag plus a fresh readiness observation are needed before unlock',()=>{
  const c=setup(),d=c.download;d.start(1,'target:8b');d.receive({id:1,type:'pull_done',model:'target:8b'})
  const request=c.sent.at(-1)
  assert.equal(d.receive({id:request.id,type:'catalog',data:{installedModels:[{name:'target:8b',size:5}]}}),true)
  assert.equal(c.probes,1);assert.equal(d.busy(),true);assert.deepEqual(c.installed,[[{name:'target:8b',size:5}]])
  d.confirmReadiness(true);assert.equal(d.busy(),false);assert.equal(d.state.phase,'complete');assert.equal(c.finished,1)
})
test('Missing, malformed or wrong-tag inventories stay locked and can retry inventory without downloading again',()=>{
  for(const inventory of [null,[],[{name:'target:4b',size:5}],[{name:'target:8b',size:-1}],[{name:'target:8b',size:'5'}]]){
    const c=setup(),d=c.download;d.start(1,'target:8b');d.receive({id:1,type:'pull_done',model:'target:8b'})
    const old=c.sent.at(-1).id
    d.receive({id:old,type:'catalog',data:{installedModels:inventory}})
    assert.equal(d.state.phase,'refresh-failed');assert.equal(d.busy(),true);assert.equal(c.probes,0)
    assert.equal(d.refreshInventory(),true);const current=c.sent.at(-1).id;assert.notEqual(current,old)
    d.receive({id:old,type:'error',message:'late'});assert.equal(d.state.phase,'refreshing')
    d.receive({id:current,type:'catalog',data:{installedModels:[{name:'target:8b',size:5}]}})
    d.confirmReadiness(false);assert.equal(d.state.phase,'refresh-failed');assert.equal(d.busy(),true)
    assert.ok(c.sent.every(frame=>frame.type==='catalog'));d.disconnected()
  }
})
test('Bare tag resolves to latest; pull errors and actual disconnect terminate the download state',()=>{
  const c=setup(),d=c.download;d.start(1,'target');d.receive({id:1,type:'pull_done',model:'target'})
  d.receive({id:c.sent.at(-1).id,type:'catalog',data:{installedModels:[{name:'target:latest',size:5}]}})
  assert.equal(c.probes,1);d.confirmReadiness(true)
  d.start(2,'second');d.receive({id:2,type:'error'});assert.equal(d.state.phase,'failed');assert.equal(d.busy(),false)
  d.start(3,'third');d.disconnected();assert.equal(d.state.phase,'failed');assert.equal(d.busy(),false)
})
function clientSetup(){
  const sent=[];const client=new DesktopApplicationClient(frame=>sent.push(frame),()=>{})
  client.receive({type:'ready',sessionId:'s',tools:[]})
  client.receive({id:sent.at(-1).id,type:'snapshot',data:{sessionId:'s',workspace:'/workspace',stateRevision:1,lastSequence:1,
    transcript:[],turns:[],modelRuntime:{providerId:'ollama',modelId:'local:7b',providerRevision:1},
    services:{rag:{enabled:false,availability:'DISABLED'},interactions:{approvals:[],inputs:[]}}}})
  return {client,sent}
}
function readiness(c,request){c.client.receive({id:request.id,type:'readiness',data:{schemaVersion:1,sessionId:'s',providerId:'ollama',modelId:'local:7b',providerRevision:1,
  ready:true,reason:null,requiredAction:null,installedModels:[{name:'local:7b',size:5},{name:'target:8b',size:5}],observedAt:new Date().toISOString()}})}
test('Host rejects workspace, chat, provider, settings and source changes locally and defers probes/snapshots during download',async()=>{
  const c=clientSetup(),d=c.client;const old=c.sent.find(f=>f.type==='get_readiness')
  assert.equal(d.beginModelDownload({id:80,model:'target:8b'}),true);d.trackModelRequest({id:80,type:'pull_model'})
  const before=c.sent.length
  for(const kind of ['SubmitUserInput','ChangeModel','ChangeProvider','SetContextWindow','SetFetchEnabled'])assert.equal((await d.command(kind,{})).error.code,'MODEL_DOWNLOAD_BUSY')
  assert.equal((await d.memory('status',{})).error.code,'MODEL_DOWNLOAD_BUSY')
  assert.equal((await d.knowledge('source_list',{})).error.code,'MODEL_DOWNLOAD_BUSY')
  assert.equal((await d.changeWorkspace('/other')).success,false)
  d.refresh();d.refreshReadiness(true);assert.equal(c.sent.length,before)
  d.receive({id:old.id,type:'error',message:'stale probe'});assert.equal(d.view.error,null);assert.equal(d.view.modelDownload.phase,'downloading')
  assert.equal(c.sent.length,before,'old probe failure does not start a new probe while downloading')
  d.receive({id:80,type:'pull_done',model:'target:8b'});const inventory=c.sent.at(-1)
  d.receive({id:inventory.id,type:'catalog',data:{installedModels:[{name:'local:7b',size:5},{name:'target:8b',size:5}]}})
  const probe=c.sent.at(-1);assert.equal(probe.type,'get_readiness');assert.equal(d.modelDownloadBusy(),true)
  readiness(c,probe);assert.equal(d.modelDownloadBusy(),false);assert.equal(d.view.modelDownload.phase,'complete')
  assert.equal(d.view.readiness.ready,true);assert.equal(d.view.error,null)
  assert.ok(d.view.readiness.installedModels.some(model=>model.name==='target:8b'));d.disconnected()
})

test('No progress becomes waiting, inventory timeout stays locked, and late inventory frames cannot settle a retry',t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  const c=setup(),d=c.download;d.start(91,'target:8b')
  t.mock.timers.tick(120001);assert.equal(d.state.phase,'waiting');assert.equal(d.busy(),true)
  d.receive({id:91,type:'pull_progress',model:'target:8b',completed:55,total:100});assert.equal(d.state.phase,'downloading')
  d.receive({id:91,type:'pull_done',model:'target:8b'});const expired=c.sent.at(-1).id
  t.mock.timers.tick(45001);assert.equal(d.state.phase,'refresh-failed');assert.equal(d.busy(),true)
  d.refreshInventory();const fresh=c.sent.at(-1).id
  d.receive({id:expired,type:'catalog',data:{installedModels:[{name:'target:8b',size:5}]}})
  assert.equal(c.probes,0);assert.equal(d.state.phase,'refreshing')
  d.receive({id:fresh,type:'catalog',data:{installedModels:[{name:'target:8b',size:5}]}})
  d.confirmReadiness(true);assert.equal(d.state.phase,'complete');d.disconnected()
})
test('A readiness result that loses the downloaded tag cannot unlock the host',()=>{
  const c=clientSetup(),d=c.client;const old=c.sent.find(f=>f.type==='get_readiness');readiness(c,old)
  d.beginModelDownload({id:81,model:'target:8b'});d.trackModelRequest({id:81,type:'pull_model'})
  d.receive({id:81,type:'pull_done',model:'target:8b'});const inventory=c.sent.at(-1)
  d.receive({id:inventory.id,type:'catalog',data:{installedModels:[{name:'target:8b',size:5}]}})
  d.receive({id:c.sent.at(-1).id,type:'readiness',data:{schemaVersion:1,sessionId:'s',providerId:'ollama',modelId:'local:7b',providerRevision:1,
    ready:true,reason:null,observedAt:new Date().toISOString(),installedModels:[{name:'local:7b',size:5}]}})
  assert.equal(d.modelDownloadBusy(),true);assert.equal(d.view.modelDownload.phase,'refresh-failed')
  assert.equal(d.view.error,null);assert.equal(d.retryDownloadInventory(),true);assert.equal(c.sent.at(-1).type,'catalog');d.disconnected()
})
