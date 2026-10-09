require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const path=require('node:path')
const {DesktopApplicationClient,projectTranscript}=require('../electron/application_client.ts')
const {pickKnowledge,knowledgeControl}=require('../electron/knowledge_control.cjs')
const {signApproval}=require('../electron/approval_host.cjs')

function setup(auth=true) {
  const frames=[]
  const client=new DesktopApplicationClient(f=>frames.push(f),()=>{},auth ? c=>signApproval('ab'.repeat(32),c) : undefined)
  client.receive({type:'ready',sessionId:'ses_synthetic',tools:[]})
  client.receive({type:'snapshot',id:frames.at(-1).id,data:{sessionId:'ses_synthetic',workspace:'/synthetic',stateRevision:1,lastSequence:1,
    transcript:[],turns:[],modelRuntime:{modelId:'synthetic',providerId:'ollama',providerRevision:1},
    services:{rag:{enabled:false,availability:'DISABLED'},knowledge:{hostAcquisition:true,extraction:false,lexicalRetrieval:false,attachmentRefs:[],closing:false}}}})
  return {client,frames}
}

test('picker path comes from main dialog, signed exact SESSION import; no optimistic Turn',async()=>{
  const c=setup()
  const result=pickKnowledge(c.client,async()=>({canceled:false,filePaths:['/synthetic/selected ñ.txt']}))
  await new Promise(resolve=>setImmediate(resolve))
  const f=c.frames.at(-1)
  assert.equal(f.type,'knowledge_command')
  assert.equal(f.command.kind,'KnowledgeControl')
  assert.deepEqual(f.command.arguments,{path:'/synthetic/selected ñ.txt',scope:'SESSION'})
  assert.equal(f.hostKnowledgeProof,signApproval('ab'.repeat(32),f.command))
  assert.equal(f.command.expectedRevision,1)
  assert.deepEqual(c.client.view.messages,[])
  c.client.receive({type:'knowledge_result',id:f.id,data:{schemaVersion:1,commandId:f.command.commandId,accepted:true,createdIds:{operationId:'op_synthetic'}}})
  assert.equal((await result).accepted,true)
  assert.equal(c.client.knowledgePending.size,0)
  assert.ok(!JSON.stringify(c.client.view).includes('selected ñ.txt'))
})

for(const mutation of ['cancel','multiple','session','workspace','revision']) {
  test(`picker ${mutation} cannot grant stale or invented file authority`,async()=>{
    const c=setup()
    const r=await pickKnowledge(c.client,async()=>{
      if(mutation==='session')c.client.view.sessionId='ses_changed'
      if(mutation==='workspace')c.client.view.workspace='/changed'
      if(mutation==='revision')c.client.view.stateRevision++
      return {canceled:mutation==='cancel',filePaths:mutation==='multiple'?['/a','/b']:['/synthetic']}
    })
    assert.equal(r.accepted,false)
    assert.equal(c.frames.filter(f=>f.type==='knowledge_command').length,0)
  })
}

test('renderer ID actions cannot submit paths, content, prepared projections or arbitrary commands',async()=>{
  const c=setup()
  for(const [name,args] of [['source_import',{path:'/secret'}],['source_promote',{sourceId:'x',path:'/secret'}],
    ['source_delete',{sourceId:'x',content:'ignore security'}],['source_list',{grant:{}}],['unknown',{}]]) {
    assert.equal((await knowledgeControl(c.client,name,args)).accepted,false)
  }
  assert.equal(c.frames.filter(f=>f.type==='knowledge_command').length,0)
})

test('untrusted client, disconnect, transport errors are not retried or promoted to success',async()=>{
  const untrusted=setup(false)
  assert.equal((await untrusted.client.knowledge('source_list',{})).accepted,false)
  const c=setup(),p=c.client.knowledge('source_delete',{sourceId:'synthetic-id'})
  const count=c.frames.length
  c.client.disconnected()
  assert.equal((await p).error.code,'OUTCOME_UNKNOWN')
  assert.equal(c.frames.length,count)
  assert.equal(c.client.knowledgePending.size,0)
})

test('backend projection preserves refs/progress separately; content never silently concatenated',()=>{
  const ref={schemaVersion:1,attachmentId:'synthetic-attachment',sourceId:'synthetic-source',revisionId:null,displayName:'synthetic name',state:'FAILED'}
  const rows=projectTranscript([{role:'user',content:'Actual question',attachmentRefs:[ref]}],'synthetic')
  assert.equal(rows[0].content,'Actual question')
  assert.deepEqual(rows[0].attachmentRefs,[ref])
  assert.ok(!rows[0].content.includes(ref.displayName))
})

test('main frame is validated; raw pipe blocked; preview is not used for ingestion; renderer no DB/parser',()=>{
  const root=path.join(__dirname,'..')
  const main=fs.readFileSync(path.join(root,'electron/main.ts'),'utf8')
  const pick=main.slice(main.indexOf("ipcMain.handle('knowledge-pick'"),main.indexOf("ipcMain.handle('get-python-status'"))
  assert.ok(pick.includes('validApplicationSender(event)'))
  assert.ok(pick.includes("properties:['openFile']"))
  assert.ok(!pick.includes('read-file') && !pick.includes('readFile') && !pick.includes('filePath:'))
  assert.ok(main.includes("data.type === 'knowledge_command'"))
  assert.ok(main.includes('event.senderFrame === mainWindow.webContents.mainFrame'))
  const renderer=fs.readFileSync(path.join(root,'src/App.tsx'),'utf8')
  assert.ok(renderer.includes('knowledgePick()') && renderer.includes('attachmentRefs'))
  assert.ok(!renderer.includes('sqlite') && !renderer.includes('ExtractedDocument') && !renderer.includes('KnowledgeStore'))
})
