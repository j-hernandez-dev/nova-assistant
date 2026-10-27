const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os')
const ts=require('typescript'),Module=require('node:module')
const filename=path.join(__dirname,'../shared/model_usage.ts'),compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
const mod=new Module(filename);mod._compile(compiled,filename)
const {usageQuery,usageRanges}=mod.exports
const {createModelVisibilityStore}=require('../electron/desktop_model_visibility.cjs')
const {createModelUsageClient}=require('../electron/model_usage.cjs')
test('Seven local calendar periods form contiguous bounded buckets',()=>{
  const date=new Date(2026,9,19,13,20)
  assert.equal(usageRanges.length,7)
  for(const range of usageRanges){const q=usageQuery(range,date);assert.ok(q.buckets.length>=1&&q.buckets.length<=31);assert.equal(q.buckets[0].start,q.start);assert.equal(q.buckets.at(-1).end,q.end);q.buckets.forEach((b,i)=>{assert.ok(b.end>b.start);if(i)assert.equal(q.buckets[i-1].end,b.start)})}
  assert.equal(usageQuery('last7',date).buckets.length,7);assert.equal(usageQuery('last30',date).buckets.length,30)
  assert.equal(usageQuery('thisMonth',date).buckets.length,31);assert.equal(usageQuery('lastMonth',date).buckets.length,30)
})
test('Last six months stays last and groups six calendar months across years and leap days',()=>{
 assert.equal(usageRanges.at(-1),'last6Months')
 for(const now of [new Date(2026,0,31,13),new Date(2024,3,30,13),new Date(2026,9,19,13)]){
  const q=usageQuery('last6Months',now),first=new Date(now.getFullYear(),now.getMonth()-5,1),tomorrow=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1)
  assert.equal(q.start,first.toISOString());assert.equal(q.end,tomorrow.toISOString());assert.equal(q.buckets.length,6)
  for(let i=0;i<6;i++)assert.equal(q.buckets[i].start,new Date(first.getFullYear(),first.getMonth()+i,1).toISOString())
 }
})

test('Hourly charts follow 23- and 25-hour daylight-saving days',()=>{
  const previous=process.env.TZ
  try{process.env.TZ='America/New_York';assert.equal(usageQuery('today',new Date(2026,2,8,12)).buckets.length,23);assert.equal(usageQuery('today',new Date(2026,10,1,12)).buckets.length,25)}
  finally{if(previous===undefined)delete process.env.TZ;else process.env.TZ=previous}
})
test('Retired authentication APIs and the external provider widgets have no active entry point',()=>{
  for(const file of ['../electron/main.ts','../electron/preload.ts','../src/App.tsx','../src/types.ts'])assert.doesNotMatch(fs.readFileSync(path.join(__dirname,file),'utf8'),/hasClaude|ClaudeLogin|ProviderSelector|anthropic\.com|claude-auth|claude-oauth/)
  assert.equal(fs.existsSync(path.join(__dirname,'../src/components/ClaudeLogin.tsx')),false)
})
test('Visibility records exclusions only, so new installed tags default to visible and choices persist',t=>{
  const directory=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-visibility-'));t.after(()=>fs.rmSync(directory,{recursive:true,force:true}))
  const store=createModelVisibilityStore(directory);assert.deepEqual(store.get().hiddenModels,[])
  assert.equal(store.set({hiddenModels:['local:7b']}).success,true)
  const saved=createModelVisibilityStore(directory).get();assert.deepEqual(['local:7b','new:9b'].filter(name=>!saved.hiddenModels.includes(name)),['new:9b'])
  assert.equal(store.set({hiddenModels:[],autoApprove:true}).success,false);assert.deepEqual(store.get(),saved)
  assert.equal(store.set({hiddenModels:[]}).success,true)
})
test('A failed visibility save preserves the confirmed choices',t=>{
  const directory=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-visibility-fail-'));t.after(()=>fs.rmSync(directory,{recursive:true,force:true}))
  const blocked=path.join(directory,'blocked');fs.writeFileSync(blocked,'owned fixture')
  const store=createModelVisibilityStore(blocked);assert.equal(store.set({hiddenModels:['local:7b']}).success,false);assert.deepEqual(store.get().hiddenModels,[])
})
test('Usage replies correlate with their query; disconnects and late replies never enter chat',async()=>{
  const sent=[],client=createModelUsageClient({send:frame=>sent.push(frame)}),q=usageQuery('last7')
  const request=client.request(q),b={requests:1,inputTokens:4,outputTokens:2,unreported:0}
  assert.equal(client.receive({id:'other',type:'model_usage'}),false)
  assert.equal(client.receive({id:sent[0].id,type:'model_usage',success:true,data:{schemaVersion:1,...b,gap:false,buckets:q.buckets.map(()=>b)}}),true)
  assert.equal((await request).success,true)
  const interrupted=client.request(q),last=sent.at(-1);client.disconnected();assert.equal((await interrupted).success,false);assert.equal(client.receive({id:last.id,type:'error'}),true)
})
