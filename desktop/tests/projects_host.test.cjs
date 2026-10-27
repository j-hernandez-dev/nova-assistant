const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const {createProjectsHost, MAX_ENTRIES, MAX_FILE_BYTES} = require('../electron/projects_host.cjs')

function fixture(t, saved) {
  const root = fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP || os.tmpdir(), 'nova-projects-'))
  const profile = path.join(root,'profile'), workspace = path.join(root,'workspace'), a = path.join(root,'a'), b = path.join(root,'b')
  for (const item of [profile,workspace,a,b]) fs.mkdirSync(item)
  if(saved)fs.writeFileSync(path.join(profile,'project-preferences.json'),JSON.stringify(saved({workspace,a,b})))
  const client = {view:{workspace,status:{ready:true},recovering:false},busy:false,
    workspaceBusy(){return this.busy},calls:[],async changeWorkspace(next){this.calls.push(next);this.view.workspace=next;return {success:true}}}
  let choice={canceled:false,filePaths:[a]}, opened=[]
  const events=[]
  const host=createProjectsHost({directory:profile,defaultPath:workspace,client,
    chooseDirectory:async()=>choice,openPath:async value=>{opened.push(value);return ''},publish:state=>events.push(state)})
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}))
  return {host,root,profile,workspace,a,b,client,opened,events,setChoice:value=>choice=value}
}
test('Legacy registries do not reinterpret a stray default field as a user-selected folder', t=>{
  const f=fixture(t,({a})=>({schemaVersion:1,defaultPath:a,activePath:a,folders:[a]}))
  assert.equal(f.host.state().defaultPath,f.workspace)
  assert.equal(f.host.preferredPath(),f.a)
  assert.equal(f.host.state().activePath,f.workspace)
  assert.equal(f.host.state().folders[0].isDefault,true)
})
test('Add uses native picker; Application confirmation precedes registry persistence',async t=>{
  const f=fixture(t)
  let resume
  f.client.changeWorkspace=next=>new Promise(resolve=>{resume=()=>{f.client.view.workspace=next;resolve({success:true})}})
  const pending=f.host.action('add','/untrusted/renderer/path')
  await new Promise(resolve=>setImmediate(resolve))
  assert.equal(fs.existsSync(path.join(f.profile,'project-preferences.json')),false)
  assert.equal(f.host.state().folders.length,1)
  resume();const result=await pending
  assert.equal(result.success,true);assert.equal(result.state.busy,false)
  assert.equal(result.state.activePath,f.a)
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.profile,'project-preferences.json'),'utf8')).activePath,f.a)
})
test('Cancel and failed Application confirmation leave folder selection unchanged',async t=>{
  const f=fixture(t);f.setChoice({canceled:true,filePaths:[]})
  assert.equal((await f.host.action('add')).canceled,true)
  assert.deepEqual(f.host.state().folders.map(x=>x.path),[f.workspace])
  f.setChoice({canceled:false,filePaths:[f.a]})
  f.client.changeWorkspace=async()=>({success:false,error:{code:'CONFLICT_ACTIVE_OPERATION'}})
  assert.equal((await f.host.action('add')).error.code,'CONFLICT_ACTIVE_OPERATION')
  assert.equal(f.host.state().activePath,f.workspace)
  assert.equal(fs.existsSync(path.join(f.profile,'project-preferences.json')),false)
})
test('Change replaces the selected registry entry only after confirmed destination; selecting does not use renderer paths',async t=>{
  const f=fixture(t);await f.host.action('add');f.setChoice({canceled:false,filePaths:[f.b]})
  assert.equal((await f.host.action('change',f.a)).success,true)
  assert.deepEqual(f.host.state().folders.map(x=>x.path),[f.workspace,f.b])
  assert.equal((await f.host.action('select',f.a)).error.code,'PROJECT_NOT_REGISTERED')
  assert.equal((await f.host.action('select',f.workspace)).success,true)
  assert.equal(f.host.state().activePath,f.workspace)
})
test('Remove never deletes data and confirms fallback to default before unregistering active folder',async t=>{
  const f=fixture(t);fs.writeFileSync(path.join(f.a,'keep.txt'),'owned')
  await f.host.action('add');let seen
  f.client.changeWorkspace=async next=>{seen=f.host.state().folders.map(x=>x.path);f.client.view.workspace=next;return {success:true}}
  assert.equal((await f.host.action('remove',f.a)).success,true)
  assert.ok(seen.includes(f.a));assert.equal(f.host.state().activePath,f.workspace)
  assert.equal(fs.readFileSync(path.join(f.a,'keep.txt'),'utf8'),'owned')
  assert.equal((await f.host.action('remove',f.workspace)).error.code,'PROJECT_DEFAULT_REQUIRED')
})
test('Open is limited to registered canonical roots',async t=>{
  const f=fixture(t)
  assert.equal((await f.host.action('open',f.b)).success,false)
  assert.equal(f.opened.length,0)
  assert.equal((await f.host.action('open',f.workspace)).success,true)
  assert.deepEqual(f.opened,[f.workspace])
})
test('Active work blocks picker and switching; a new turn during picker is rechecked',async t=>{
  const f=fixture(t);f.client.busy=true
  assert.equal((await f.host.action('add')).error.code,'PROJECT_BUSY')
  assert.equal(f.client.calls.length,0)
  f.client.busy=false;let finish
  const host=createProjectsHost({directory:f.profile,defaultPath:f.workspace,client:f.client,
    chooseDirectory:()=>new Promise(resolve=>finish=resolve),openPath:async()=>''})
  const pending=host.action('add');f.client.busy=true;finish({canceled:false,filePaths:[f.a]})
  assert.equal((await pending).error.code,'PROJECT_BUSY');assert.equal(f.client.calls.length,0)
})
test('Unavailable backend and malformed operations return structured errors',async t=>{
  const f=fixture(t);f.client.view.status.ready=false
  assert.equal((await f.host.action('add')).error.code,'PROJECT_UNAVAILABLE')
  assert.equal((await f.host.action('destroy')).error.code,'PROJECT_INVALID_ACTION')
  assert.equal((await f.host.readFile(99)).success,false)
  assert.equal(f.host.state().defaultPath,f.workspace)
})
test('Preview confines both directory and text file reads to active canonical root',async t=>{
  const f=fixture(t);fs.writeFileSync(path.join(f.workspace,'readme.txt'),'hello');fs.writeFileSync(path.join(f.b,'secret.txt'),'private')
  const listed=await f.host.listDirectory(f.workspace)
  assert.equal(listed.success,true);assert.deepEqual(listed.entries.map(x=>x.name),['readme.txt'])
  assert.equal((await f.host.readFile(path.join(f.workspace,'readme.txt'))).content,'hello')
  assert.equal((await f.host.readFile(path.join(f.b,'secret.txt'))).error.code,'PROJECT_OUTSIDE_ROOT')
  assert.equal((await f.host.listDirectory(path.join(f.workspace,'..'))).error.code,'PROJECT_OUTSIDE_ROOT')
  assert.equal((await f.host.readFile(f.workspace)).error.code,'PROJECT_NOT_FILE')
  assert.equal((await f.host.listDirectory(path.join(f.workspace,'readme.txt'))).error.code,'PROJECT_NOT_DIRECTORY')
  assert.equal((await f.host.readFile('relative.txt')).error.code,'PROJECT_INVALID_PATH')
})
test('Preview size, UTF8 and binary limits are bounded and errors never throw',async t=>{
  const f=fixture(t), large=path.join(f.workspace,'large'), binary=path.join(f.workspace,'binary'), bad=path.join(f.workspace,'bad')
  fs.writeFileSync(large,Buffer.alloc(MAX_FILE_BYTES+1,65));fs.writeFileSync(binary,Buffer.from([0,1]));fs.writeFileSync(bad,Buffer.from([0xff]))
  assert.equal((await f.host.readFile(large)).error.code,'PROJECT_FILE_TOO_LARGE')
  assert.equal((await f.host.readFile(binary)).error.code,'PROJECT_BINARY_FILE')
  assert.equal((await f.host.readFile(bad)).error.code,'PROJECT_READ_FAILED')
  assert.equal((await f.host.readFile(path.join(f.workspace,'missing'))).error.code,'PROJECT_READ_FAILED')
})
test('Outside symlink/junction is neither listed nor readable',async t=>{
  const f=fixture(t), link=path.join(f.workspace,'escape')
  fs.writeFileSync(path.join(f.b,'secret.txt'),'private')
  fs.symlinkSync(f.b,link,process.platform==='win32'?'junction':'dir')
  assert.equal((await f.host.listDirectory(f.workspace)).entries.length,0)
  assert.equal((await f.host.readFile(path.join(link,'secret.txt'))).error.code,'PROJECT_OUTSIDE_ROOT')
})
test('Directory enumeration stops at bounded ceiling with truncation metadata',async t=>{
  const f=fixture(t)
  for(let i=0;i<MAX_ENTRIES+2;i++)fs.writeFileSync(path.join(f.workspace,`file-${i}`),'')
  const result=await f.host.listDirectory(f.workspace)
  assert.equal(result.entries.length,MAX_ENTRIES);assert.equal(result.truncated,true)
  assert.equal(result.nextOffset,MAX_ENTRIES)
  const next=await f.host.listDirectory(f.workspace,result.nextOffset)
  assert.equal(next.entries.length,2);assert.equal(next.nextOffset,null)
  assert.equal((await f.host.listDirectory(f.workspace,-1)).error.code,'PROJECT_INVALID_OFFSET')
})
test('Deleted last project falls back to explicit default with a visible reason',t=>{
  const f=fixture(t,({a})=>({schemaVersion:1,activePath:path.join(a,'deleted'),folders:[]}))
  assert.equal(f.host.preferredPath(),f.workspace)
  assert.equal(f.host.state().error.code,'PROJECT_PREVIOUS_UNAVAILABLE')
})
test('Unavailable default remains explicit and a human-picked folder can bootstrap without source-root readiness',async t=>{
  const f=fixture(t), missing=path.join(f.root,'unavailable-default')
  f.client.view.workspace=null;f.client.view.status.ready=false
  let called=0
  const host=createProjectsHost({directory:f.profile,defaultPath:missing,client:f.client,
    chooseDirectory:async()=>({canceled:false,filePaths:[f.a]}),openPath:async()=>'',
    bootstrapWorkspace:async next=>{called++;assert.equal(f.client.view.status.ready,false);f.client.view.workspace=next;f.client.view.status.ready=true;return {success:true}}})
  assert.equal(host.state().error.code,'PROJECT_DEFAULT_UNAVAILABLE')
  assert.equal(host.state().activePath,null)
  assert.equal((await host.action('add')).success,true)
  assert.equal(called,1);assert.equal(host.state().activePath,f.a)
  assert.equal(host.state().defaultPath,missing)
  assert.equal(fs.existsSync(missing),false)
})
test('A registered root replaced by a junction cannot silently point at a different project',async t=>{
  const f=fixture(t);await f.host.action('add');await f.host.action('select',f.workspace)
  const original=path.join(f.root,'original-a')
  fs.renameSync(f.a,original)
  fs.symlinkSync(f.b,f.a,process.platform==='win32'?'junction':'dir')
  assert.equal((await f.host.action('select',f.a)).error.code,'PROJECT_PATH_CHANGED')
  assert.equal((await f.host.action('open',f.a)).error.code,'PROJECT_PATH_CHANGED')
  assert.equal(f.host.state().activePath,f.workspace)
})
test('Main IPC binds project and preview operations to main frame, and denies raw workspace override',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../electron/main.ts'),'utf8')
  assert.match(source,/ipcMain\.handle\('project-action',[\s\S]*?validApplicationSender\(event\)/)
  assert.match(source,/ipcMain\.handle\('list-directory',[\s\S]*?validApplicationSender\(event\)/)
  assert.match(source,/ipcMain\.handle\('read-file',[\s\S]*?validApplicationSender\(event\)/)
  assert.match(source,/data\.type === 'set_cwd'/)
  assert.match(source,/resolveDefaultWorkspace\(findProjectRoot\(\), app\.getPath\('documents'\), app\.isPackaged\)/)
  assert.match(source,/const initialWorkspace = defaultWorkspace\(\)/)
  assert.match(source,/Never expose chat readiness at the source root after failed bootstrap/)
  assert.match(source,/restartWorkspace = applicationClient\.view\.workspace \|\| projectsHost\?\.preferredPath\(\) \|\| defaultWorkspace\(\)/)
  assert.match(source,/restoreAfterRestart = restoreOnWorkspaceBootstrap && !!msg\.resumable/)
  assert.doesNotMatch(source,/restoreAfterRestart = !!msg\.resumable/)
  assert.match(source,/bootstrapProjectRequest\?\.acknowledged && view\.status\.ready/)
})


test('project removal deletes its chat only after a confirmed fallback; deletion failure keeps the registered project',async t=>{
 for(const deleted of [true,false]){
  const f=fixture(t);await f.host.action('add')
  const file=path.join(f.a,'keep.txt');fs.writeFileSync(file,'preserve')
  const removed=[]
  const host=createProjectsHost({directory:f.profile,defaultPath:f.workspace,client:f.client,
   chooseDirectory:async()=>({canceled:true}),openPath:async()=>'',clearChat:async target=>{
    assert.equal(f.client.view.workspace,f.workspace);removed.push(target);return {success:deleted}}})
  const result=await host.action('remove',f.a)
  assert.equal(result.success,deleted);assert.deepEqual(removed,[f.a])
  assert.equal(host.state().folders.some(folder=>folder.path===f.a),!deleted)
  assert.equal(fs.readFileSync(file,'utf8'),'preserve')
 }
})


test('Changing the default uses the native picker, preserves other projects and survives reopening',async t=>{
 const f=fixture(t);await f.host.action('add')
 fs.writeFileSync(path.join(f.workspace,'keep.txt'),'original files');fs.writeFileSync(path.join(f.b,'keep.txt'),'chosen files')
 f.setChoice({canceled:false,filePaths:[f.b]})
 const result=await f.host.action('change',f.workspace)
 assert.equal(result.success,true);assert.equal(f.host.defaultPath,f.b);assert.equal(result.state.activePath,f.b)
 assert.deepEqual(result.state.folders.map(x=>[x.path,x.isDefault]),[[f.b,true],[f.a,false]])
 assert.equal((await f.host.action('remove',f.b)).error.code,'PROJECT_DEFAULT_REQUIRED')
 const saved=JSON.parse(fs.readFileSync(path.join(f.profile,'project-preferences.json'),'utf8'))
 assert.equal(saved.schemaVersion,2);assert.equal(saved.defaultPath,f.b)
 const reopened=createProjectsHost({directory:f.profile,defaultPath:f.workspace,client:f.client,chooseDirectory:async()=>({canceled:true}),openPath:async()=>''})
 assert.equal(reopened.defaultPath,f.b);assert.equal(reopened.preferredPath(),f.b)
 assert.equal(fs.readFileSync(path.join(f.workspace,'keep.txt'),'utf8'),'original files');assert.equal(fs.readFileSync(path.join(f.b,'keep.txt'),'utf8'),'chosen files')
})

test('Cancel, busy work and rejected workspace changes do not replace the default',async t=>{
 const f=fixture(t);f.setChoice({canceled:true,filePaths:[]})
 assert.equal((await f.host.action('change',f.workspace)).canceled,true);assert.equal(f.host.defaultPath,f.workspace)
 f.client.busy=true;assert.equal((await f.host.action('reset-default')).error.code,'PROJECT_BUSY');f.client.busy=false
 f.setChoice({canceled:false,filePaths:[f.a]});f.client.changeWorkspace=async()=>({success:false,error:{code:'CONFLICT_ACTIVE_OPERATION'}})
 assert.equal((await f.host.action('change',f.workspace)).success,false);assert.equal(f.host.defaultPath,f.workspace)
 assert.equal(fs.existsSync(path.join(f.profile,'project-preferences.json')),false)
 assert.equal((await f.host.action('reset-default',f.b)).error.code,'PROJECT_INVALID_ACTION')
})

test('A failed preference write keeps the prior default and rolls the workspace back',async t=>{
 const f=fixture(t),rename=fs.renameSync
 fs.renameSync=(from,to)=>{if(to===path.join(f.profile,'project-preferences.json'))throw Error('owned failure');return rename(from,to)}
 try{
  const result=await f.host.action('change',f.workspace)
  assert.equal(result.success,false);assert.equal(result.error.code,'PROJECT_PREFERENCES_SAVE_FAILED')
  assert.equal(f.host.defaultPath,f.workspace);assert.equal(f.client.view.workspace,f.workspace)
  assert.deepEqual(f.host.state().folders.map(x=>x.path),[f.workspace])
 }finally{fs.renameSync=rename}
})

test('Reset restores the immutable original folder, recreates it if missing and preserves custom files',async t=>{
 const f=fixture(t);await f.host.action('change',f.workspace)
 fs.writeFileSync(path.join(f.a,'keep.txt'),'preserve')
 assert.equal(path.dirname(f.workspace),f.root);fs.rmdirSync(f.workspace)
 f.client.busy=true;assert.equal((await f.host.action('reset-default')).success,false);assert.equal(fs.existsSync(f.workspace),false);f.client.busy=false
 const result=await f.host.action('reset-default')
 assert.equal(result.success,true);assert.equal(f.host.defaultPath,f.workspace);assert.equal(result.state.activePath,f.workspace)
 assert.equal(fs.statSync(f.workspace).isDirectory(),true);assert.equal(fs.readFileSync(path.join(f.a,'keep.txt'),'utf8'),'preserve')
 assert.equal((await f.host.action('remove',f.workspace)).error.code,'PROJECT_DEFAULT_REQUIRED')
})

test('Reset refuses a replacement junction and can recover an unavailable backend through the host',async t=>{
 const f=fixture(t);await f.host.action('change',f.workspace)
 assert.equal(path.dirname(f.workspace),f.root);fs.rmdirSync(f.workspace);fs.symlinkSync(f.b,f.workspace,process.platform==='win32'?'junction':'dir')
 assert.equal((await f.host.action('reset-default')).error.code,'PROJECT_PATH_CHANGED');assert.equal(f.host.defaultPath,f.a)
 const missing=path.join(f.root,'new-original');f.client.view.status.ready=false;f.client.view.workspace=null
 const recovery=createProjectsHost({directory:path.join(f.root,'recovery-profile'),defaultPath:missing,client:f.client,
  chooseDirectory:async()=>({canceled:true}),openPath:async()=>'',bootstrapWorkspace:async root=>{f.client.view.workspace=root;f.client.view.status.ready=true;return{success:true}}})
 assert.equal((await recovery.action('reset-default')).success,true);assert.equal(recovery.defaultPath,missing)
})
