require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const {DesktopApplicationClient}=require('../electron/application_client.ts')
function fixture(){
  const sent=[],client=new DesktopApplicationClient(frame=>sent.push(frame),()=>{})
  const snapshot=(workspace='/owned',operations=[])=>({sessionId:'session',workspace,stateRevision:1,lastSequence:1,transcript:[],turns:[],
    modelRuntime:{providerId:'ollama',modelId:'model',providerRevision:1},services:{rag:{enabled:false,availability:'UNKNOWN'},operations,interactions:{approvals:[],inputs:[]}}})
  client.receive({type:'ready',sessionId:'session',tools:[]})
  client.receive({type:'snapshot',id:sent.find(x=>x.type==='get_snapshot').id,data:snapshot()})
  return {client,sent,snapshot,refresh(state){const pending=sent.filter(x=>x.type==='get_snapshot').at(-1);client.receive({type:'snapshot',id:pending.id,data:state})}}
}
test('Workspace change waits for exact receipt plus Application snapshot; no optimistic workspace',async()=>{
  const f=fixture();let resolved=false
  const pending=f.client.changeWorkspace('/next').then(x=>{resolved=true;return x})
  const request=f.sent.find(x=>x.type==='set_cwd');assert.ok(request);assert.equal(request.projectChat,true)
  assert.equal(f.client.view.workspace,'/owned');assert.equal(f.client.workspaceBusy(),true)
  f.client.receive({type:'cwd_changed',id:request.id,resumable:null})
  await Promise.resolve();assert.equal(resolved,false)
  f.refresh(f.snapshot('/next'))
  assert.equal((await pending).success,true);assert.equal(f.client.workspaceBusy(),false)
  f.client.disconnected()
})
test('Wrong response ID does not acknowledge change, and mismatching snapshot cannot claim success',async()=>{
  const f=fixture();let resolved=false
  const pending=f.client.changeWorkspace('/next').then(x=>{resolved=true;return x})
  const request=f.sent.find(x=>x.type==='set_cwd')
  f.client.receive({type:'cwd_changed',id:'forged'})
  f.refresh(f.snapshot('/next'));await Promise.resolve();assert.equal(resolved,false)
  f.client.receive({type:'cwd_changed',id:request.id})
  f.refresh(f.snapshot('/other'));assert.equal((await pending).success,false)
  f.client.disconnected()
})
test('Backend error and disconnect resolve boundedly without saving intent as success',async()=>{
  for(const mode of ['error','disconnect']){
    const f=fixture(),pending=f.client.changeWorkspace('/next'),request=f.sent.find(x=>x.type==='set_cwd')
    if(mode==='error')f.client.receive({type:'error',id:request.id,code:'CONFLICT_ACTIVE_OPERATION'})
    else f.client.disconnected()
    const result=await pending;assert.equal(result.success,false)
    assert.equal(result.error.code,mode==='error'?'CONFLICT_ACTIVE_OPERATION':'PROJECT_CHANGE_UNKNOWN')
    f.client.disconnected()
  }
})
test('Active interactions and services block project changes before sending; active selection blocks chat',async()=>{
  const f=fixture()
  f.client.view.inputs=[{inputRequestId:'pending'}]
  assert.equal((await f.client.changeWorkspace('/next')).success,false)
  assert.equal(f.sent.filter(x=>x.type==='set_cwd').length,0)
  f.client.view.inputs=[];f.client.refresh();f.refresh(f.snapshot('/owned',[{operationId:'svc',status:'running',service:'rag'}]))
  assert.equal((await f.client.changeWorkspace('/next')).success,false)
  f.client.refresh();f.refresh(f.snapshot())
  const pending=f.client.changeWorkspace('/next')
  assert.equal((await f.client.command('SubmitUserInput',{text:'hello'})).error.code,'PROJECT_BUSY')
  f.client.disconnected();await pending
})


test('project-scoped message identity and notifications do not bleed across the same session',()=>{
 const f=fixture()
 const state=(workspace,text)=>({...f.snapshot(workspace),stateRevision:2,transcript:[{role:'user',content:text},{role:'assistant',content:'saved reply'}]})
 f.client.refresh();f.refresh(state('/Alpha','alpha request'))
 const first=f.client.view.messages.map(message=>message.id)
 f.client.refresh();f.refresh(state('/Beta','beta request'))
 assert.notDeepEqual(f.client.view.messages.map(message=>message.id),first)
 assert.equal(f.client.view.conversation.unreadCount,0)
 f.client.refresh();f.refresh(state('/Alpha','alpha request'))
 assert.deepEqual(f.client.view.messages.map(message=>message.id),first)
 f.client.refresh();f.refresh({...f.snapshot('/Empty'),stateRevision:2})
 assert.equal(f.client.view.conversation.hasConversation,false);assert.equal(f.client.view.messages.length,0)
 f.client.disconnected()
})
