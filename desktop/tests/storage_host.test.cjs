const test=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const path=require('node:path')
const os=require('node:os')
const {createStorageHost,applyPendingStorageDeletions,measureStorage,storageLocations}=require('../electron/storage_host.cjs')
const {prepareChromiumCaches}=require('../electron/chromium_cache.cjs')

function fixture(t){
  const parent=path.join(__dirname,'.storage-test-artifacts');fs.mkdirSync(parent,{recursive:true})
  const root=fs.mkdtempSync(path.join(parent,'nova-storage-test-'))
  const options={profileDir:path.join(root,'profile'),stateDir:path.join(root,'state'),auditDir:path.join(root,'state','security_audit','v1'),catalogDir:path.join(root,'catalog'),tempDir:path.join(root,'temp'),controlDir:path.join(root,'control')}
  for(const value of Object.values(options))fs.mkdirSync(value,{recursive:true})
  options.homeDir=path.join(root,'home');fs.mkdirSync(options.homeDir);options.env={}
  t.after(()=>{assert.ok(path.basename(root).startsWith('nova-storage-test-'));fs.rmSync(root,{recursive:true,force:true})})
  const put=(relative,count)=>{const target=path.join(root,relative);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,Buffer.alloc(count));return target}
  return {root,options,put}
}

test('Electron 45 persistent graphics cache is measured and rotated without changing user preferences',async t=>{
  const {options,put}=fixture(t)
  const relative='GPUPersistentCache/DawnGraphiteCache/graphics/cache.db'
  put('profile/'+relative,11);put('profile/desktop-preferences.json',3)
  const before=await measureStorage(storageLocations(options))
  assert.equal(before.categories.find(item=>item.id==='caches').bytes,11)
  const rotation=prepareChromiumCaches(options.profileDir)
  assert.deepEqual(rotation.rotated,['GPUPersistentCache']);assert.deepEqual(rotation.failures,[])
  assert.equal(fs.existsSync(path.join(options.profileDir,relative)),false)
  assert.equal(fs.statSync(path.join(rotation.backupDirectory,relative)).size,11)
  assert.equal(fs.statSync(path.join(options.profileDir,'desktop-preferences.json')).size,3)
  const after=await measureStorage(storageLocations(options))
  assert.equal(after.totalBytes,before.totalBytes)
  assert.equal(after.categories.find(item=>item.id==='caches').bytes,11)
})

test('counts nested managed roots once and separates caches, document blobs and web snapshots',async t=>{
  const {options,put}=fixture(t)
  put('profile/desktop-preferences.json',3);put('profile/Cache/cache',5)
  put('profile/.chromium-cache-backup/GPUCache/a',7)
  put('state/projects/chat/last-conversation.jsonl',11);put('state/sessions/session.json',13)
  put('state/memory/v1/memory.db',17);put('state/browser-files/download.bin',19)
  put('temp/nova-browser-profiles/profile/Preferences',23);put('state/security_audit/v1/log',29)
  put('catalog/model_catalog.json',31);put('state/knowledge/v1/blobs/local.bin',37)
  put('state/knowledge/v1/blobs/web.bin',41);put('state/knowledge/v1/knowledge.db',43)
  put('state/knowledge/v1/cache/chunk.cache',47);put('state/desktop-context.json',53)
  const measured=await measureStorage(storageLocations(options),{webSnapshotBytes:41})
  assert.equal(measured.totalBytes,379)
  assert.deepEqual(Object.fromEntries(measured.categories.map(item=>[item.id,item.bytes])),{
    chats:24,attachments:37,memories:17,navigation:83,configuration:99,audit:29,catalog:31,caches:59})
  assert.deepEqual(measured.warnings,[])
  assert.equal(measured.folders.find(item=>item.id==='attachments').bytes,37)
  assert.equal(measured.folders.find(item=>item.id==='navigation').bytes,42)
  assert.equal(measured.folders.find(item=>item.id==='configuration').bytes,56)
})

test('scanner refuses junction traversal and reports incomplete totals',async t=>{
  const {root,options,put}=fixture(t)
  put('external/secret.txt',100);put('state/projects/chat/history',7)
  const link=path.join(options.stateDir,'projects','outside');fs.mkdirSync(link)
  const originalStat=fs.lstatSync
  t.mock.method(fs,'lstatSync',function(target,...args){const stat=originalStat.call(fs,target,...args);if(path.resolve(String(target))===link){const fake=Object.create(stat);fake.isSymbolicLink=()=>true;return fake}return stat})
  const measured=await measureStorage(storageLocations(options))
  assert.equal(measured.totalBytes,7)
  assert.ok(measured.warnings.some(item=>item.startsWith('STORAGE_UNSAFE_PATH')))
  assert.ok(measured.categories.every(item=>item.complete===false))
})

test('queue reset applies only at startup, preserves project registry, documents and originals',async t=>{
  const {root,options,put}=fixture(t)
  const preferences=put('profile/desktop-preferences.json',2),registry=put('profile/project-preferences.json',3)
  const config=put('state/desktop-context.json',5),usage=put('home/.local/state/nova/model-usage.sqlite3-wal',7)
  const unknown=put('state/unknown-user-file.txt',11),attachment=put('state/knowledge/v1/blobs/a.bin',13),original=put('originals/personal.txt',17)
  const host=createStorageHost({...options,client:{storage:async()=>({files:[]})},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  const queued=await host.deleteFolder('configuration')
  assert.equal(queued.success,true);assert.equal(queued.data.restartRequired,true)
  assert.ok(fs.existsSync(preferences));assert.ok(fs.existsSync(config))
  const applied=applyPendingStorageDeletions(options)
  assert.deepEqual(applied.completed,['configuration']);assert.deepEqual(applied.failed,[])
  for(const target of [preferences,config,usage])assert.equal(fs.existsSync(target),false)
  for(const target of [registry,unknown,attachment,original])assert.ok(fs.existsSync(target))
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(root,'control','pending-deletions.json'),'utf8')).categories,[])
})

test('pending manifest rejects paths or unknown categories and never deletes originals',t=>{
  const {options,put}=fixture(t),original=put('originals/keep.txt',19)
  fs.writeFileSync(path.join(options.controlDir,'pending-deletions.json'),JSON.stringify({schemaVersion:1,categories:[original]}))
  const applied=applyPendingStorageDeletions(options)
  assert.deepEqual(applied.completed,[]);assert.deepEqual(applied.warnings,['STORAGE_PENDING_INVALID']);assert.ok(fs.existsSync(original))
})

test('cleanup preflight blocks an entire folder category when it contains a junction',async t=>{
  const {root,options,put}=fixture(t),chat=put('state/projects/a/history',7),original=put('originals/keep.txt',19)
  const link=path.join(options.stateDir,'projects','outside');fs.mkdirSync(link)
  const originalStat=fs.lstatSync
  t.mock.method(fs,'lstatSync',function(target,...args){const stat=originalStat.call(fs,target,...args);if(path.resolve(String(target))===link){const fake=Object.create(stat);fake.isSymbolicLink=()=>true;return fake}return stat})
  fs.writeFileSync(path.join(options.controlDir,'pending-deletions.json'),JSON.stringify({schemaVersion:1,categories:['chats'],rootFingerprint:storageLocations(options).rootFingerprint}))
  const applied=applyPendingStorageDeletions(options)
  assert.deepEqual(applied.completed,[]);assert.equal(applied.failed[0].code,'STORAGE_UNSAFE_PATH')
  assert.ok(fs.existsSync(chat));assert.ok(fs.existsSync(original))
})

test('attachment folder deletion uses backend file authority and retains the Knowledge store',async t=>{
  const {options,put}=fixture(t),database=put('state/knowledge/v1/knowledge.db',17),web=put('state/knowledge/v1/blobs/web.bin',19),calls=[]
  const host=createStorageHost({...options,client:{storage:async(action,args)=>{calls.push({action,args});return {files:[]}}},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  const result=await host.deleteFolder('attachments')
  assert.equal(result.success,true);assert.equal(result.data.restartRequired,false)
  assert.equal(calls.at(-1).action,'delete_all');assert.ok(fs.existsSync(database));assert.ok(fs.existsSync(web))
  assert.equal(fs.existsSync(path.join(options.controlDir,'pending-deletions.json')),false)
})

test('unregistered projects appear unlinked, reassignment validates trusted current registry and selection',async t=>{
  const {root,options}=fixture(t),project=path.join(root,'workspace'),calls=[]
  const files=[{id:'a',name:'manual.pdf',bytes:100,modifiedAt:'2026-10-23T10:00:00Z',projectPath:path.join(root,'removed')}]
  const host=createStorageHost({...options,client:{storage:async(action,args)=>{calls.push({action,args});return {files}}},getProjects:()=>[{path:project,name:'Workspace'}],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  const unlinked=await host.files(null);assert.equal(unlinked.data.files.length,1);assert.equal(unlinked.data.files[0].projectPath,null)
  assert.equal((await host.move(['a'],path.join(root,'arbitrary'))).success,false)
  assert.equal((await host.move(['a','a'],project)).success,false)
  assert.equal((await host.move(['a'],project)).success,true)
  assert.equal(calls.at(-1).action,'move');assert.equal(calls.at(-1).args.projectPath,project)
})

test('canceling file deletion leaves backend untouched and restart warning survives reopening',async t=>{
  const {options}=fixture(t),calls=[]
  let accept=false
  const dependencies={...options,client:{storage:async(action)=>{calls.push(action);return {files:[]}}},getProjects:()=>[],confirm:async()=>({confirmed:accept}),openPath:async()=>'',restart:()=>{}}
  const host=createStorageHost(dependencies)
  assert.equal((await host.deleteFiles(['id'])).canceled,true);assert.deepEqual(calls,[])
  accept=true;assert.equal((await host.deleteFolder('caches')).success,true)
  const reopened=createStorageHost(dependencies)
  assert.equal((await reopened.overview()).data.restartRequired,true)
})

test('explicit refresh recomputes file sizes instead of returning the previous overview',async t=>{
  const {options,put}=fixture(t)
  const host=createStorageHost({...options,client:{storage:async()=>({files:[]})},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  assert.equal((await host.overview()).data.totalBytes,0)
  put('state/projects/chat/history',43)
  assert.equal((await host.overview()).data.totalBytes,0)
  assert.equal((await host.overview({refresh:true})).data.totalBytes,43)
})

test('trusted host config resolves custom state for measurement and pending startup cleanup',async t=>{
  const {root,options,put}=fixture(t)
  delete options.stateDir
  put('home/.config/nova/config',0)
  fs.writeFileSync(path.join(options.homeDir,'.config','nova','config'),'# host configuration\nstate_dir = ~/custom-state\n')
  const chat=put('home/custom-state/projects/chat/history',13),unmanaged=put('home/custom-state/personal.txt',97)
  assert.equal(storageLocations(options).stateDir,path.join(options.homeDir,'custom-state'))
  const host=createStorageHost({...options,client:{storage:async()=>({files:[]})},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  const measured=(await host.overview()).data
  assert.equal(measured.categories.find(item=>item.id==='chats').bytes,13)
  assert.equal(measured.totalBytes,13+fs.statSync(path.join(options.homeDir,'.config','nova','config')).size)
  assert.equal((await host.deleteFolder('chats')).success,true)
  assert.deepEqual(applyPendingStorageDeletions(options).completed,['chats'])
  assert.equal(fs.existsSync(chat),false);assert.ok(fs.existsSync(unmanaged))
})

test('root fingerprint prevents a changed host config from redirecting queued deletion',async t=>{
  const {options,put}=fixture(t);delete options.stateDir
  put('home/.config/nova/config',0)
  const config=path.join(options.homeDir,'.config','nova','config')
  fs.writeFileSync(config,'state_dir = ~/first\n')
  const first=put('home/first/projects/chat/history',7),second=put('home/second/projects/chat/history',11)
  const host=createStorageHost({...options,client:{storage:async()=>({files:[]})},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  assert.equal((await host.deleteFolder('chats')).success,true)
  fs.writeFileSync(config,'state_dir = ~/second\n')
  const result=applyPendingStorageDeletions(options)
  assert.deepEqual(result.completed,[]);assert.deepEqual(result.warnings,['STORAGE_ROOT_CHANGED'])
  assert.ok(fs.existsSync(first));assert.ok(fs.existsSync(second))
})

test('state config is bounded data and never evaluates shell text or relative paths',t=>{
  const {options,put}=fixture(t);delete options.stateDir
  put('home/.config/nova/config',0)
  const config=path.join(options.homeDir,'.config','nova','config')
  fs.writeFileSync(config,'state_dir = $(Write-Output unsafe)\n')
  const result=storageLocations(options)
  assert.equal(result.stateDir,path.join(options.homeDir,'.local','state','nova'))
  assert.deepEqual(result.warnings,['STORAGE_STATE_CONFIG_UNSUPPORTED'])
  fs.writeFileSync(config,'state_dir='+ 'a'.repeat(10240))
  assert.deepEqual(storageLocations(options).warnings,['STORAGE_STATE_CONFIG_UNAVAILABLE'])
})

test('backend composition root is trusted for report measurement; renderer file args cannot change roots',async t=>{
  const {root,options,put}=fixture(t)
  put('backend-state/projects/chat/history',41);put('state/projects/old/history',23)
  const host=createStorageHost({...options,client:{storage:async()=>({files:[],roots:{stateDir:path.join(root,'backend-state')}})},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  const measured=(await host.overview()).data
  assert.equal(measured.categories.find(item=>item.id==='chats').bytes,41)
  assert.equal((await host.files(path.join(root,'elsewhere'))).error.code,'STORAGE_PROJECT_UNAVAILABLE')
})

test('usage files honor XDG_STATE_HOME independently of a configured document state root',async t=>{
  const {root,options,put}=fixture(t)
  options.env={XDG_STATE_HOME:path.join(root,'metrics-state')}
  const usage=put('metrics-state/nova/model-usage.sqlite3',31),usageWal=put('metrics-state/nova/embedding-usage.sqlite3-wal',17)
  const ignored=put('metrics-state/nova/unrelated.txt',101),obsolete=put('state/model-usage.sqlite3',71)
  const host=createStorageHost({...options,client:{storage:async()=>({files:[]})},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{}})
  const measured=(await host.overview()).data
  assert.equal(measured.totalBytes,48);assert.equal(measured.folders.find(item=>item.id==='configuration').bytes,48)
  assert.equal((await host.deleteFolder('configuration')).success,true)
  assert.deepEqual(applyPendingStorageDeletions(options).completed,['configuration'])
  assert.equal(fs.existsSync(usage),false);assert.equal(fs.existsSync(usageWal),false)
  assert.ok(fs.existsSync(ignored));assert.ok(fs.existsSync(obsolete))
})

test('isBusy covers shared backend report work and file mutations, and resets after cancellation',async t=>{
  const {options}=fixture(t)
  let release,confirmRelease,reports=0
  const client={storage:async(action)=>{if(action==='report'){reports++;await new Promise(resolve=>{release=resolve})}return {files:[]}}}
  const host=createStorageHost({...options,client,getProjects:()=>[],confirm:async()=>new Promise(resolve=>{confirmRelease=resolve}),openPath:async()=>'',restart:()=>{}})
  const initial=host.overview(),files=host.files(null)
  assert.equal(host.isBusy(),true);assert.equal(reports,1)
  release();await Promise.all([initial,files]);assert.equal(host.isBusy(),false)
  const deleting=host.deleteFiles(['id']);assert.equal(host.isBusy(),true)
  confirmRelease({confirmed:false});assert.equal((await deleting).canceled,true);assert.equal(host.isBusy(),false)
})

test('Download passes only picker-selected destination, retains stored files and handles cancellation',async t=>{
 const {root,options}=fixture(t),calls=[],picks=[],destination=path.join(root,'Downloads','recovered.pdf')
 fs.mkdirSync(path.dirname(destination))
 const records=[{id:'file-one',name:'manual.pdf',bytes:100,modifiedAt:'2026-10-23T10:00:00Z',projectPath:null}]
 let chosen={canceled:false,filePath:destination}
 const host=createStorageHost({...options,client:{storage:async(action,args)=>{calls.push([action,args]);return {files:records}}},getProjects:()=>[],confirm:async()=>({confirmed:true}),openPath:async()=>'',restart:()=>{},pickSave:async options=>{picks.push(options);return chosen}})
 assert.deepEqual((await host.download(['file-one'])).data,{downloaded:1})
 assert.equal(picks[0].name,'manual.pdf');assert.equal(calls.at(-1)[0],'export');assert.equal(calls.at(-1)[1].path,destination)
 assert.equal((await host.files(null)).data.files[0].id,'file-one')
 chosen={canceled:true};const exports=calls.filter(c=>c[0]==='export').length
 assert.equal((await host.download(['file-one'])).canceled,true);assert.equal(calls.filter(c=>c[0]==='export').length,exports)
 chosen={canceled:false,filePath:path.join(options.stateDir,'knowledge','overwrite.bin')}
 assert.equal((await host.download(['file-one'])).success,false);assert.equal(calls.filter(c=>c[0]==='export').length,exports)
 assert.equal((await host.download(['missing'])).success,false)
})
