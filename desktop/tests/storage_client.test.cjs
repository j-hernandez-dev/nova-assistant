require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict')
const {DesktopApplicationClient}=require('../electron/application_client.ts')
function fixture(){
  const sent=[],signed=[]
  const client=new DesktopApplicationClient(frame=>{sent.push(frame);return true},()=>{},command=>{signed.push(command);return 'owned-test-proof'})
  client.view={...client.view,sessionId:'storage-session',stateRevision:4,status:{...client.view.status,ready:true,connected:true}}
  return {client,sent,signed}
}
test('private storage commands are signed and serialized; success updates revision and file access before resolving',async()=>{
  const {client,sent,signed}=fixture(),pending=client.storage('move',{ids:['owned'],projectPath:null,projects:[]})
  const frame=sent.at(-1)
  assert.equal(frame.type,'storage_command');assert.equal(frame.hostStorageProof,'owned-test-proof')
  assert.deepEqual(signed,[frame.command]);assert.equal(client.workspaceBusy(),true)
  assert.equal((await client.storage('report',{projects:[]})).success,false)
  const knowledge={attachmentRefs:[],sources:[]}
  client.receive({type:'storage_result',id:frame.id,success:true,stateRevision:5,data:{knowledge}})
  assert.equal((await pending).success,true);assert.equal(client.view.stateRevision,5)
  assert.deepEqual(client.view.knowledge,knowledge);assert.equal(client.workspaceBusy(),false)
  client.disconnected()
})
test('a failed storage receipt advances revision and refreshes actual state without replaying the mutation',async()=>{
  const {client,sent}=fixture(),pending=client.storage('delete',{ids:['owned'],projects:[]}),frame=sent.at(-1)
  client.receive({type:'storage_result',id:frame.id,success:false,stateRevision:6,error:{code:'STORAGE_FAILED',outcomeUnknown:true}})
  assert.equal((await pending).error.code,'STORAGE_FAILED');assert.equal(client.view.stateRevision,6)
  assert.equal(sent.filter(frame=>frame.type==='storage_command').length,1)
  assert.equal(sent.at(-1).type,'get_snapshot')
  const next=client.storage('report',{projects:[]}),request=sent.at(-1)
  assert.equal(request.command.expectedRevision,6)
  client.receive({type:'storage_result',id:request.id,success:true,stateRevision:7,data:{files:[]}})
  assert.equal((await next).success,true);client.disconnected()
})
test('backend disconnection resolves pending storage as unknown and never resends it',async()=>{
  const {client,sent}=fixture(),pending=client.storage('delete',{ids:['owned'],projects:[]})
  client.disconnected()
  assert.equal((await pending).error.code,'STORAGE_OUTCOME_UNKNOWN')
  assert.equal(sent.filter(frame=>frame.type==='storage_command').length,1)
})
