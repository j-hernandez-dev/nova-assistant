const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path')
const {createSourceImporter}=require('../electron/source_import.cjs')
function fixture(t){
 const parent=path.join(__dirname,'.source-import-artifacts');fs.mkdirSync(parent,{recursive:true})
 const root=fs.mkdtempSync(path.join(parent,'batch-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}))
 const files=['one.txt','two.txt'].map(name=>{const value=path.join(root,name);fs.writeFileSync(value,'Owned synthetic content');return value})
 const calls=[],lease=[]
 const client={view:{sessionId:'s',workspace:root,stateRevision:1,status:{ready:true},knowledgeOperations:[]},knowledge:async(name,args)=>{
  calls.push([name,args]);const id='op-'+calls.length
  client.view.knowledgeOperations.push({operationId:id,status:'completed',result:{sourceId:'source-'+calls.length}})
  client.view.stateRevision++;return {accepted:true,createdIds:{operationId:id}}
 }}
 return {client,files,calls,lease,host:createSourceImporter(client,{pick:async()=>({canceled:false,filePaths:files}),onBusy:busy=>lease.push(busy)})}
}
test('multi-file native selection imports serially, observes completion and releases the lease',async t=>{
 const f=fixture(t),result=await f.host.pick()
 assert.deepEqual(result,{completed:true,imported:2,sourceIds:['source-1','source-2']});assert.deepEqual(f.lease,[true,false]);assert.equal(f.calls.length,2)
 assert.ok(f.calls.every(([name,args])=>name==='source_import'&&args.scope==='WORKSPACE'))
})
test('a failed later import reports the completed count without retrying',async t=>{
 const f=fixture(t),first=f.client.knowledge
 f.client.knowledge=async(...args)=>f.calls.length?{accepted:false,error:{code:'SOURCE_TOO_LARGE'}}:first(...args)
 const result=await f.host.pick();assert.equal(result.imported,1);assert.deepEqual(result.sourceIds,['source-1']);assert.equal(result.error.code,'SOURCE_TOO_LARGE');assert.equal(f.calls.length,1)
})
test('project changes while the picker is open never import into a different project',async t=>{
 const f=fixture(t),host=createSourceImporter(f.client,{pick:async()=>{f.client.view.workspace='changed';return {canceled:false,filePaths:f.files}}})
 assert.equal((await host.pick()).error.code,'REVISION_CONFLICT');assert.equal(f.calls.length,0)
})
test('drop rejects invented paths, directories and duplicate selections before effects',async t=>{
 const f=fixture(t)
 for(const paths of [[f.client.view.workspace],[f.files[0],f.files[0]],['relative.txt'],[42]])assert.equal((await f.host.drop(paths)).completed,false)
 assert.equal(f.calls.length,0)
})
test('a pending picker owns a single lease and cancellation performs no import',async t=>{
 const f=fixture(t);let release
 const host=createSourceImporter(f.client,{pick:()=>new Promise(resolve=>{release=resolve})})
 const pending=host.pick();assert.equal(host.isBusy(),true);assert.equal((await host.drop(f.files)).error.code,'PROJECT_BUSY')
 release({canceled:true,filePaths:[]});assert.equal((await pending).canceled,true);assert.equal(host.isBusy(),false)
})
