require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict')
const {PublicModelLibrary,defaultLibraryFilters:filters}=require('../src/public_model_library.ts')
function fixture(){const sent=[],timers=new Map();let id=0;const client=new PublicModelLibrary(frame=>sent.push(frame),()=>++id,(fn)=>{timers.set(id,fn);return id},id=>timers.delete(id));return{client,sent,last:()=>sent.at(-1),timers}}
const model=name=>({name,display:name,category:'General',params:'',size_gb:0,description:'Owned fixture',tags:['tools'],installed:false,kind:'llm',cloud_only:false})
test('Host correlates public-library errors without adding an unrelated chat error',()=>{
 const {DesktopApplicationClient}=require('../electron/application_client.ts')
 const host=new DesktopApplicationClient(()=>{},()=>{})
 for(const [index,type]of ['library_search','library_variants'].entries()){
  assert.equal(host.trackModelRequest({id:900+index,type}),true)
  host.receive({id:900+index,type:'error',code:'MODEL_LIBRARY_UNAVAILABLE'})
  assert.equal(host.view.error,null)
 }
 host.disconnected()
})
function reply(request,models,nextPage=null){return{id:request.id,type:'library_search',data:{...filters,...request,models,nextPage,syncedAt:1000,offline:false,stale:false,source:request.source==='snapshot'?'snapshot':'web'}}}
test('Late query replies are ignored; pagination preserves existing rows and deduplicates families',()=>{
 const f=fixture();f.client.search();const old=f.last();f.client.search({...filters,query:'owned'});const current=f.last()
 assert.equal(f.client.receive(reply(old,[model('old')])),false)
 f.client.receive(reply(current,[model('owned-one')],2));f.client.more();const page=f.last();assert.equal(page.page,2)
 f.client.receive(reply(page,[model('owned-one'),model('owned-two')]))
 assert.deepEqual(f.client.state.models.map(m=>m.name),['owned-one','owned-two']);assert.equal(f.client.state.nextPage,null)
 f.client.dispose()
})
test('Errors retain visible models and retry the failed page without an install or selection',()=>{
 const f=fixture();f.client.search();f.client.receive(reply(f.last(),[model('owned')],2));f.client.more()
 f.client.receive({id:f.last().id,type:'error',message:'private'})
 assert.equal(f.client.state.error,true);assert.equal(f.client.state.models.length,1)
 f.client.more();assert.equal(f.sent.length,2);f.client.retry();assert.equal(f.last().page,2)
 assert.ok(f.sent.every(frame=>frame.type==='library_search'));f.client.dispose()
})
test('Mismatching filters, unsafe rows and invalid pagination do not replace a catalog',()=>{
 for(const bad of [{query:'wrong'},{models:[{...model('owned'),kind:'unknown'}]},{nextPage:50},{syncedAt:1e20},{source:'unsafe'},{models:[{...model('owned'),name:'../escape'}]}]){
  const f=fixture();f.client.search();const frame=reply(f.last(),[model('owned')]);Object.assign(frame.data,bad);f.client.receive(frame)
  assert.equal(f.client.state.error,true);assert.equal(f.client.state.models.length,0);f.client.dispose()
 }
})
test('Snapshot pagination keeps its source after a full sync instead of mixing website pages',()=>{
 const f=fixture();f.client.search();const frame=reply(f.last(),[model('owned')],2);frame.data.source='snapshot';f.client.receive(frame)
 f.client.more();assert.equal(f.last().source,'snapshot');f.client.dispose()
})
test('Variants retain exact identity and reject another family; read timeouts do not trigger retries',()=>{
 const f=fixture();f.client.variants('owned');const request=f.last()
 const variant={name:'other:3b',size_gb:1.8,size_label:'1.8GB',context_length:8192,cloud_only:false}
 f.client.receive({id:request.id,type:'library_variants',data:{family:'owned',variants:[variant],syncedAt:1000,offline:false,stale:false}})
 assert.equal(f.client.state.variants.get('owned').error,true)
 f.client.variants('owned',true);const next=f.last();f.client.receive({id:next.id,type:'library_variants',data:{family:'owned',variants:[{...variant,name:'owned:3b-q4_K_M'}],syncedAt:1,offline:true,stale:true}})
 assert.equal(f.client.state.variants.get('owned').variants[0].name,'owned:3b-q4_K_M')
 assert.equal(f.client.state.variants.get('owned').offline,true)
 f.client.search();f.timers.get(f.last().id)();assert.equal(f.client.state.loading,false);assert.equal(f.client.state.error,true)
 assert.equal(f.sent.length,3);f.client.dispose()
})
