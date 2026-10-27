const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os')
const {createMemoryFileControls,MAX_BYTES}=require('../electron/memory_files.cjs')
function fixture(){
 const base=process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir();fs.mkdirSync(base,{recursive:true})
 const root=fs.mkdtempSync(path.join(base,'memory-files-'))
 const input=path.join(root,'input.json'),output=path.join(root,'output.json'),calls=[]
 fs.writeFileSync(input,JSON.stringify({format:'nova-memory-export',records:[]}))
 let confirmed=true,known=true,changePicker=false
 const folder=fs.realpathSync(root)
 const client={view:{sessionId:'owned',workspace:folder,stateRevision:1,status:{ready:true,connected:true}},workspaceBusy:()=>false,
   async memory(name,args){calls.push(['command',name,args]);return{schemaVersion:1,commandId:'owned',completed:true,stateRevision:2,data:name==='memory_export_all'?{format:'nova-memory-export',records:[{canonicalText:args.includeSensitive?'synthetic private':'synthetic normal'}]}:{imported:0}}}}
 const controls=createMemoryFileControls({client,projects:()=>({folders:known?[{name:'Owned',path:folder}]:[]}),getLocale:()=> 'es',
   confirm:async request=>{calls.push(['confirm',request.kind]);assert.equal(request.validate(),true);return{confirmed}},
   pickOpen:async options=>{calls.push(['open',options.title]);if(changePicker)client.view.stateRevision++;return{canceled:false,filePaths:[input]}},
   pickSave:async()=>{calls.push(['save']);return{canceled:false,filePath:output}}})
 return{root,input,output,calls,folder,client,controls,setConfirmed:v=>confirmed=v,setKnown:v=>known=v,changePicker:()=>changePicker=true}
}
test('Import confirms replacement before any file picker and cancellation never reads or writes',async()=>{
 const h=fixture();h.setConfirmed(false)
 const result=await h.controls.transfer('import');assert.equal(result.canceled,true)
 assert.deepEqual(h.calls,[['confirm','memory-import']])
 h.setConfirmed(true);h.calls.length=0;assert.equal((await h.controls.transfer('import')).completed,true)
 assert.deepEqual(h.calls.map(c=>c[0]),['confirm','open','command'])
 assert.equal(h.calls.at(-1)[1],'memory_import')
})
test('Normal export opens Save directly; sensitive export confirms before Save and never returns file data to renderer',async()=>{
 const h=fixture();let result=await h.controls.transfer('export',false)
 assert.equal(result.completed,true);assert.deepEqual(h.calls.map(c=>c[0]),['save','command'])
 assert.equal(result.data.records,undefined);assert.equal(result.data.exported,1)
 assert.equal(JSON.parse(fs.readFileSync(h.output)).records[0].canonicalText,'synthetic normal')
 h.calls.length=0;result=await h.controls.transfer('export',true)
 assert.deepEqual(h.calls.map(c=>c[0]),['confirm','save','command'])
 assert.equal(JSON.parse(fs.readFileSync(h.output)).records[0].canonicalText,'synthetic private')
 assert.deepEqual(fs.readdirSync(h.root).sort(),['input.json','output.json'])
})
test('Malformed/oversized import and state changes after the picker never dispatch a replacement',async()=>{
 const h=fixture();fs.writeFileSync(h.input,'{invalid')
 assert.equal((await h.controls.transfer('import')).error.code,'MEMORY_IMPORT_INVALID')
 assert.equal(h.calls.some(c=>c[0]==='command'),false)
 fs.truncateSync(h.input,MAX_BYTES+1)
 assert.equal((await h.controls.transfer('import')).error.code,'MEMORY_TRANSFER_TOO_LARGE')
 fs.writeFileSync(h.input,'{}');h.changePicker()
 assert.equal((await h.controls.transfer('import')).error.code,'REVISION_CONFLICT')
 assert.equal(h.calls.some(c=>c[0]==='command'),false)
})
test('Project permissions require a registered unchanged folder; enabling confirms and disabling does not',async()=>{
 const h=fixture();assert.equal((await h.controls.projectAccess(h.folder,true)).completed,true)
 assert.deepEqual(h.calls.map(c=>c[0]),['confirm','command'])
 assert.deepEqual(h.calls.at(-1),['command','memory_project_access',{projectPath:h.folder,enabled:true}])
 h.calls.length=0;assert.equal((await h.controls.projectAccess(h.folder,false)).completed,true)
 assert.deepEqual(h.calls.map(c=>c[0]),['command'])
 h.setKnown(false);assert.equal((await h.controls.projectAccess(h.folder,true)).error.code,'PROJECT_NOT_REGISTERED')
})
test('Concurrent requests cannot reuse a pending confirmation or file selection',async()=>{
 const h=fixture();let finish
 const pending=new Promise(resolve=>finish=resolve)
 const controls=createMemoryFileControls({client:h.client,projects:()=>({folders:[]}),getLocale:()=> 'en',
   confirm:()=>pending,pickOpen:()=>{throw Error('Must not open')},pickSave:()=>{throw Error('Must not save')}})
 const first=controls.transfer('import');assert.equal(controls.isBusy(),true)
 assert.equal((await controls.transfer('export')).error.code,'PROJECT_BUSY')
 finish({confirmed:false});assert.equal((await first).canceled,true);assert.equal(controls.isBusy(),false)
})
