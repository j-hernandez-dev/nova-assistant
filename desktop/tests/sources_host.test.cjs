const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path')
const {createStorageHost}=require('../electron/storage_host.cjs')
function fixture(t){
 const parent=path.join(__dirname,'.sources-host-artifacts');fs.mkdirSync(parent,{recursive:true})
 const root=fs.mkdtempSync(path.join(parent,'host-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}))
 const a=path.join(root,'A'),b=path.join(root,'B');fs.mkdirSync(a);fs.mkdirSync(b)
 const calls=[],prompts=[],files=[{id:'one',name:'one.txt',bytes:4,projectPath:a,kind:'file',downloadable:true},{id:'web',name:'web.html',bytes:4,projectPath:a,kind:'url',url:'https://example.com',downloadable:true},{id:'other',name:'private.txt',bytes:4,projectPath:b,kind:'file',downloadable:true}]
 const client={view:{sessionId:'s',workspace:a},storage:async(name,args)=>{calls.push([name,args]);return {success:true,data:name==='source_preview'?{preview:{sourceId:args.ids[0],name:'owned.txt',content:'Saved original',reason:null}}:{files:files.filter(file=>file.kind==='file'),sources:files}}}}
 let approve=true
 const options={homeDir:root,stateDir:path.join(root,'state'),profileDir:path.join(root,'profile'),client,getProjects:()=>[{path:a,name:'A'},{path:b,name:'B'}],confirm:async request=>{prompts.push(request);return {confirmed:approve}},openPath:async()=>'',restart:()=>{},pickSave:async()=>({canceled:false,filePath:path.join(root,'download.html')})}
 return {root,a,b,client,calls,prompts,options,setApprove:value=>{approve=value},host:createStorageHost(options)}
}
test('source list contains files and URLs only from the current registered project',async t=>{
 const f=fixture(t),result=await f.host.sources();assert.equal(result.success,true);assert.deepEqual(result.data.files.map(file=>file.id),['one','web']);assert.equal(result.data.projects.length,2)
})
test('source mutations reject records from other projects',async t=>{
 const f=fixture(t)
 assert.equal((await f.host.move(['other'],f.a,true)).success,false)
 assert.equal((await f.host.deleteFiles(['other'],true)).success,false)
 assert.equal((await f.host.download(['other'],true)).success,false)
 assert.equal((await f.host.sourcePreview('other')).success,false)
 assert.ok(f.calls.every(([name])=>name==='source_report'));assert.equal(f.prompts.length,0)
})
test('source previews use a source ID and bind the saved content to the current registered project',async t=>{
 const f=fixture(t),result=await f.host.sourcePreview('web')
 assert.equal(result.success,true);assert.equal(result.data.content,'Saved original');assert.equal(result.data.root,f.a)
 assert.deepEqual(f.calls.at(-1),['source_preview',{ids:['web'],projects:[{path:f.a,name:'A'},{path:f.b,name:'B'}]}])
 assert.equal((await f.host.sourcePreview('../foreign.txt')).success,false)
})
test('project changes during preview discard the saved content',async t=>{
 const f=fixture(t),original=f.client.storage
 f.client.storage=async(name,args)=>{const result=await original(name,args);if(name==='source_preview')f.client.view.workspace=f.b;return result}
 assert.equal((await f.host.sourcePreview('one')).success,false)
})
test('canceling the Nova source deletion modal preserves sources',async t=>{
 const f=fixture(t);f.setApprove(false)
 assert.equal((await f.host.deleteFiles(['web'],true)).canceled,true);assert.equal(f.prompts[0].kind,'sources-delete-files');assert.ok(!f.calls.some(([name])=>name==='source_delete'))
})
test('relink and download dispatch the source controls and a native Save As destination',async t=>{
 const f=fixture(t)
 assert.equal((await f.host.move(['web'],f.b,true)).success,true)
 assert.equal((await f.host.download(['web'],true)).success,true)
 assert.ok(f.calls.some(([name,args])=>name==='source_move'&&args.projectPath===f.b))
 assert.ok(f.calls.some(([name,args])=>name==='source_export'&&args.path===path.join(f.root,'download.html')))
})
test('a project switch invalidates a pending source confirmation',async t=>{
 const f=fixture(t)
 const host=createStorageHost({...f.options,confirm:async()=>{f.client.view.workspace=f.b;return {confirmed:true}}})
 assert.equal((await host.deleteFiles(['web'],true)).canceled,true);assert.ok(!f.calls.some(([name])=>name==='source_delete'))
})
test('overlapping source reads share the pending inventory before checking their own workspace busy state',async t=>{
 const f=fixture(t),original=f.client.storage;let release,pending=false,requests=0
 f.client.workspaceBusy=()=>pending
 f.client.storage=async(name,args)=>{requests++;pending=true;await new Promise(resolve=>{release=resolve});pending=false;return original(name,args)}
 const first=f.host.sources(),second=f.host.sources()
 assert.equal(requests,1)
 release();const results=await Promise.all([first,second]);assert.ok(results.every(result=>result.success));assert.deepEqual(results[0].data,results[1].data)
})
test('a failed inventory read releases the shared flight so an explicit refresh can recover',async t=>{
 const f=fixture(t),original=f.client.storage
 f.client.storage=async()=>({success:false,error:{code:'STORAGE_FAILED'}})
 const results=await Promise.all([f.host.sources(),f.host.sources()]);assert.ok(results.every(result=>!result.success))
 f.client.storage=original;assert.equal((await f.host.sources()).success,true)
})
