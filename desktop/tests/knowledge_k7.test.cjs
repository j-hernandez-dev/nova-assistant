require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript')
const {DesktopApplicationClient,projectTranscript}=require('../electron/application_client.ts')
const {hostSelection,remoteKnowledge,knowledgeControl}=require('../electron/knowledge_control.cjs')
const {signApproval}=require('../electron/approval_host.cjs')

function setup() {
 const frames=[];const client=new DesktopApplicationClient(f=>frames.push(f),()=>{},c=>signApproval('ab'.repeat(32),c))
 client.receive({type:'ready',sessionId:'ses_synthetic',tools:[]})
 client.receive({type:'snapshot',id:frames.at(-1).id,data:{sessionId:'ses_synthetic',workspace:'/synthetic',stateRevision:1,lastSequence:1,
  transcript:[],turns:[],modelRuntime:{modelId:'synthetic',providerId:'ollama',providerRevision:1},services:{rag:{enabled:false,availability:'DISABLED'}}}})
 return {client,frames}
}
function acknowledge(c) {
 const f=c.frames.at(-1);c.client.receive({type:'knowledge_result',id:f.id,data:{schemaVersion:1,commandId:f.command.commandId,accepted:true,createdIds:{operationId:'op_synthetic'}}})
 return f
}

for(const name of ['source_refresh','source_export']) {
 test(`${name} target comes from native selection, not renderer paths`,async()=>{
  const c=setup(),select=async()=>name==='source_export'?{canceled:false,filePath:'/synthetic/host target'}:{canceled:false,filePaths:['/synthetic/host target']}
  const p=hostSelection(c.client,name,'source-synthetic',select);await new Promise(r=>setImmediate(r))
  const f=acknowledge(c);assert.equal((await p).accepted,true)
  assert.deepEqual(f.command.arguments,{sourceId:'source-synthetic',path:'/synthetic/host target'})
  assert.equal(f.hostKnowledgeProof,signApproval('ab'.repeat(32),f.command))
 })
 for(const mutate of ['session','workspace','revision','cancel']) test(`${name} ${mutate} cannot reuse a selection`,async()=>{
  const c=setup();const result=await hostSelection(c.client,name,'synthetic',async()=>{
   if(mutate==='session')c.client.view.sessionId='other'
   if(mutate==='workspace')c.client.view.workspace='other'
   if(mutate==='revision')c.client.view.stateRevision++
   return {canceled:mutate==='cancel',filePaths:['/target'],filePath:'/target'}
  })
  assert.equal(result.accepted,false);assert.equal(c.frames.filter(f=>f.type==='knowledge_command').length,0)
 })
}

test('remote forwarding requires exact native consent, default denial does not send',async()=>{
 const c=setup();const args={sourceId:'synthetic',allowed:true}
 assert.equal((await remoteKnowledge(c.client,args,async()=>({response:0}))).error.code,'REMOTE_FORWARDING_DENIED')
 assert.equal(c.frames.filter(f=>f.type==='knowledge_command').length,0)
 const p=remoteKnowledge(c.client,args,async()=>({response:1}));await new Promise(r=>setImmediate(r))
 const f=acknowledge(c);assert.equal((await p).accepted,true);assert.deepEqual(f.command.arguments,args)
 assert.equal(f.command.name,'source_remote')
})
for(const mutate of ['session','workspace','revision','arguments']) test(`remote consent ${mutate} never broadens frozen request`,async()=>{
 const c=setup(),args={sourceId:'original',allowed:true}
 const p=remoteKnowledge(c.client,args,async()=>{
  if(mutate==='arguments')args.sourceId='forged'
  else if(mutate==='session')c.client.view.sessionId='other'
  else if(mutate==='workspace')c.client.view.workspace='other'
  else c.client.view.stateRevision++
  return {response:1}
 });await new Promise(r=>setImmediate(r))
 if(mutate==='arguments') {const f=acknowledge(c);assert.equal((await p).accepted,true);assert.equal(f.command.arguments.sourceId,'original')}
 else {assert.equal((await p).accepted,false);assert.equal(c.frames.filter(f=>f.type==='knowledge_command').length,0)}
})

test('renderer cannot pass paths/credentials/grants to generic Knowledge controls',async()=>{
 const c=setup()
 for(const [name,args] of [['source_refresh',{sourceId:'x',path:'/secret'}],['source_export',{sourceId:'x',path:'/secret'}],
  ['source_remote',{sourceId:'x',allowed:true}],['source_detail',{sourceId:'x',path:'/secret'}],['source_import_url',{url:'https://a/',grant:{}}],
  ['__proto__',{}],['constructor',{}],['toString',{}]]) assert.equal((await knowledgeControl(c.client,name,args)).accepted,false)
 assert.equal(c.frames.filter(f=>f.type==='knowledge_command').length,0)
})

test('citation projection preserves historical IDs/locator; React renders labels as data',()=>{
 const citations={schemaVersion:1,turnId:'turn',structuralOnly:true,valid:[{citationId:'K1',sourceId:'src',revisionId:'old',
  displayLabel:'<script>forged authority</script>',originDisplay:'data',locator:{kind:'PDF_PAGE',coordinates:{page:2}}}],invalid:['K999']}
 const rows=projectTranscript([{role:'assistant',content:'Synthetic answer [K1]',knowledgeCitations:citations}],'synthetic')
 assert.deepEqual(rows[0].knowledgeCitations,citations)
 require.extensions['.tsx']=(mod,file)=>mod._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,file)
 const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')
 const {MessageBlock}=require('../src/components/MessageBlock.tsx')
 const html=renderToStaticMarkup(React.createElement(MessageBlock,{message:rows[0]}))
 assert.ok(html.includes('old') && html.includes('K999') && html.includes('&lt;script&gt;'))
 assert.ok(!html.includes('<script>forged') && html.includes('not guaranteed entailment'))
})

test('minimal Desktop remains a projection: no DB/parser/authority or direct file ingestion',()=>{
 const root=path.join(__dirname,'..'),main=fs.readFileSync(path.join(root,'electron/main.ts'),'utf8')
 for(const channel of ['knowledge-refresh','knowledge-export']) {
  const text=main.slice(main.indexOf(`ipcMain.handle('${channel}'`),main.indexOf(`ipcMain.handle('${channel}'`)+550)
  assert.ok(text.includes('validApplicationSender(event)') && text.includes('hostSelection'))
 }
 const app=fs.readFileSync(path.join(root,'src/App.tsx'),'utf8')
 assert.ok(app.includes('knowledgeRefresh(ref.sourceId)') && app.includes('knowledgeExport(ref.sourceId)'))
 assert.ok(!app.includes('KnowledgeStore') && !app.includes('sqlite') && !app.includes('SourceRevision.from'))
 assert.ok(main.includes('remoteKnowledge') && main.includes('buttons:[\'Cancel\',\'Allow\']'))
})
