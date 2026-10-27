// Real Electron IPC, Python coordinator and SQLite; owned profile, no LLM turn.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),Module=require('node:module')
const electron=require('electron'),repo=path.resolve(__dirname,'../..')
assert.ok(process.env.NOVA_GUI_TEST_OUTPUT&&process.env.NOVA_TEST_PYTHON)
const output=path.resolve(process.env.NOVA_GUI_TEST_OUTPUT),reopen=process.argv.includes('--reopen')
const home=path.join(output,'home'),profile=path.join(output,'app-data','nova-desktop'),alpha=path.join(output,'Alpha'),beta=path.join(output,'Beta')
const original=path.join(output,'manual.txt'),catalog=path.join(home,'.cache','nova','model_catalog.json')
if(!reopen){assert.ok(!fs.existsSync(output));for(const directory of [home,profile,alpha,beta,path.dirname(catalog)])fs.mkdirSync(directory,{recursive:true})
  fs.writeFileSync(original,'Database installation: use the local server.\n')
  fs.writeFileSync(catalog,JSON.stringify({owned:true}))
  fs.writeFileSync(path.join(profile,'project-preferences.json'),JSON.stringify({schemaVersion:2,defaultPath:alpha,folders:[alpha],activePath:alpha}))
  fs.writeFileSync(path.join(profile,'desktop-preferences.json'),JSON.stringify({schemaVersion:1,locale:'es',transitionsEnabled:false}))
}
electron.app.setPath('appData',path.dirname(profile))
Object.assign(process.env,{HOME:home,USERPROFILE:home,LOCALAPPDATA:path.join(home,'AppData','Local'),XDG_CONFIG_HOME:path.join(home,'.config'),
  XDG_STATE_HOME:path.join(home,'.local','state'),XDG_CACHE_HOME:path.join(home,'.cache'),PYTHONPATH:repo,PYTHONDONTWRITEBYTECODE:'1',LOCAL_CLI_AUTO_UPDATE:'false'})
delete process.env.VITE_DEV_SERVER_URL
let backend,win,view,loaded=false,finished=false,restartExpected=false,relaunchRequested=false
const checks=[],errors=[],stderr=[],opened=[],picked=[],handlers=new Map(),bindings=new Map(),children=[],saves=[],saveOptions=[]
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms))
async function until(fn,label,ms=30000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await delay(60)}throw Error('Timeout: '+label)}
function save(error){fs.writeFileSync(path.join(output,reopen?'reopen-result.json':'first-result.json'),JSON.stringify({status:error?'FAIL':'PASS',checks,errors,stderr:stderr.join(''),error:error?.stack,relaunchRequested,...(error?{view}: {})},null,2))}
function fail(error){if(finished)return;finished=true;clearTimeout(deadline);save(error);backend?.kill();electron.app.exit(1)}
process.on('uncaughtException',fail);process.on('unhandledRejection',fail)
const deadline=setTimeout(()=>fail(Error('Storage integration timeout')),90000)
const spawn=cp.spawn
cp.spawn=function(command,args,options){if(args?.includes('--server')){backend=spawn(process.env.NOVA_TEST_PYTHON,args,{...options,cwd:alpha,env:{...options.env,PYTHONPATH:repo},windowsHide:true});backend.stderr.on('data',data=>stderr.push(String(data)));return backend}return spawn(command,args,options)}
electron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[picked.shift()]})
electron.dialog.showSaveDialog=async(_parent,options)=>{saveOptions.push(options);return saves.shift()||{canceled:true}}

electron.shell.openPath=async target=>{opened.push(target);return ''}
electron.app.relaunch=()=>{relaunchRequested=true}
const handle=electron.ipcMain.handle.bind(electron.ipcMain)
electron.ipcMain.handle=(channel,handler)=>{handlers.set(channel,handler);return handle(channel,(event,...args)=>{
  const result=handler(event,...args)
  if(channel==='confirmation-surface-ready'&&result.accepted)bindings.set(event.sender.id,result)
  return result
})}
class HiddenWindow extends electron.BrowserWindow{
  show(){}
  isVisible(){return true}
  constructor(options){super({...options,show:false,webPreferences:{...options.webPreferences,backgroundThrottling:false}})
    if(options.parent)children.push(this);else{win=this;this.webContents.on('did-finish-load',()=>{loaded=true})}
    this.webContents.on('preload-error',(_e,_p,error)=>errors.push(error.message))
    this.webContents.on('render-process-gone',(_e,detail)=>errors.push(detail.reason))
    const send=this.webContents.send.bind(this.webContents)
    this.webContents.send=(channel,...args)=>{if(channel==='session-view')view=args[0];return send(channel,...args)}
  }
}
const load=Module._load
Module._load=function(name,...args){return name==='electron'?{...electron,BrowserWindow:HiddenWindow}:load.call(this,name,...args)}
require('../dist-electron/main.js')
const js=code=>win.webContents.executeJavaScript(code,true)
async function decision(confirmed,deleteAssociatedFiles=false){
  let child,binding
  await until(()=>{child=children.find(item=>!item.isDestroyed()&&bindings.has(item.webContents.id));binding=child&&bindings.get(child.webContents.id);return !!binding},'Nova confirmation')
  const payload={nonce:binding.nonce,confirmed,...(binding.kind==='remove-project'?{deleteAssociatedFiles}:{})}
  const receipt=handlers.get('confirmation-surface-decision')({sender:child.webContents,senderFrame:child.webContents.mainFrame},payload)
  assert.equal(receipt.accepted,true)
}
function record(label){checks.push(label);console.log('PASS',label)}
electron.app.on('before-quit',()=>{
  if(restartExpected&&relaunchRequested&&!finished){finished=true;clearTimeout(deadline);record('Restart button requests native relaunch after stopping the real backend');save()}
})
electron.app.whenReady().then(async()=>{
  try{
    await until(()=>loaded&&view?.status?.ready,'real backend and renderer')
    if(reopen){
      assert.equal(fs.existsSync(catalog),false)
      const manifest=path.join(output,'app-data','nova-storage-control','pending-deletions.json')
      if(fs.existsSync(manifest))assert.deepEqual(JSON.parse(fs.readFileSync(manifest,'utf8')).categories,[])
      assert.equal(fs.readFileSync(original,'utf8'),'Database installation: use the local server.\n')
      const report=await js('window.api.storageOverview()');assert.equal(report.success,true)
      const persisted=await js("window.api.memoryCommand('memory_list',{scope:'ALL'})")
      assert.equal(persisted.completed,true,JSON.stringify(persisted));assert.equal(persisted.data.records[0].canonicalText,'Synthetic preference for diagrams');assert.equal(persisted.data.records[0].revision,4)
      record('Table edits survive a real application restart')
      record('Startup applies only queued catalog deletion, retains originals and opens valid storage report')
      finished=true;clearTimeout(deadline);save();backend?.kill();electron.app.quit();return
    }
    picked.push(original);assert.equal((await js('window.api.knowledgePick()')).accepted,true)
    await until(()=>view?.knowledge?.attachmentRefs?.some(ref=>ref.displayName==='manual.txt'&&ref.revisionId)&&view?.knowledgeOperations?.every(operation=>operation.status!=='running'),'persistent import')
    const overview=await js('window.api.storageOverview()');assert.equal(overview.success,true)
    assert.equal(overview.data.categories.length,8);assert.equal(overview.data.projects[0].path,null)
    assert.equal(overview.data.projects.find(item=>item.path===alpha).fileCount,1)
    assert.equal(overview.data.totalBytes,overview.data.categories.reduce((sum,item)=>sum+item.bytes,0))
    let files=await js(`window.api.storageFiles(${JSON.stringify(alpha)})`);assert.equal(files.success,true)
    const id=files.data.files[0].id
    record('Eight measured categories, unlinked first, persistent Alpha attachment and exact summed total')
    picked.push(beta);assert.equal((await js("window.api.projectAction('add')")).success,true)
    assert.equal((await js(`window.api.storageFiles(${JSON.stringify(alpha)})`)).data.files.length,1)
    assert.equal((await js(`window.api.storageMove([${JSON.stringify(id)}],null)`)).success,true)
    assert.equal((await js('window.api.storageFiles(null)')).data.files.length,1)
    assert.equal((await js(`window.api.storageMove([${JSON.stringify(id)}],${JSON.stringify(beta)})`)).success,true)
    await until(()=>view?.knowledge?.attachmentRefs?.some(ref=>ref.sourceId===id),'new project attachment access')
    const recovered=path.join(output,'Recovered manual.txt')
    saves.push({canceled:false,filePath:recovered})
    const download=await js(`window.api.storageDownload([${JSON.stringify(id)}])`)
    assert.equal(download.success,true);assert.equal(download.data.downloaded,1)
    assert.deepEqual(fs.readFileSync(recovered),fs.readFileSync(original))
    assert.equal(path.basename(saveOptions.at(-1).defaultPath),'manual.txt');assert.equal(path.dirname(saveOptions.at(-1).defaultPath),electron.app.getPath('downloads'))
    assert.equal(saveOptions.at(-1).buttonLabel,'Guardar')
    record('Native Save As starts in Downloads with original filename and recovers exact stored bytes')
    record('Project switch retains attachment; unlink and relink change actual backend access')
    const removing=js(`window.api.projectAction('remove',${JSON.stringify(beta)})`)
    await decision(true,false);assert.equal((await removing).success,true)
    assert.equal((await js('window.api.storageFiles(null)')).data.files.length,1)
    assert.equal((await js(`window.api.storageMove([${JSON.stringify(id)}],${JSON.stringify(alpha)})`)).success,true)
    record('Removing a project without delete option puts its copy in Unlinked and permits reassignment')
    const remembered=await js(`window.api.memoryCommand('memory_remember',{kind:'PREFERENCE',text:'Synthetic preference for concise examples',scope:'WORKSPACE'})`)
    assert.equal(remembered.completed,true)
    const memoryId=remembered.data.memoryId
    const row={memoryId,revision:remembered.data.revision,text:'Synthetic preference for diagrams',kind:'PROCEDURE',scope:'GLOBAL_PROFILE',sensitive:false}
    const edited=await js(`window.api.memoryCommand('memory_edit',${JSON.stringify({records:[row]})})`)
    assert.equal(edited.completed,true)
    let shown=await js(`window.api.memoryCommand('memory_show',${JSON.stringify({memoryId})})`)
    assert.equal(shown.completed,true,JSON.stringify(shown));assert.equal(shown.data.record.canonicalText,row.text);assert.equal(shown.data.record.scopeKind,'GLOBAL_PROFILE');assert.equal(shown.data.record.revision,2)
    let confirmation=js(`window.api.memoryEditSensitivity(${JSON.stringify({memoryId,revision:2,sensitive:true})})`)
    await decision(false);assert.equal((await confirmation).canceled,true)
    confirmation=js(`window.api.memoryEditSensitivity(${JSON.stringify({memoryId,revision:2,sensitive:true})})`)
    await decision(true);const token=(await confirmation).data.token
    assert.equal((await js(`window.api.memoryCommand('memory_edit',${JSON.stringify({records:[{...row,revision:2,sensitive:true,consentToken:token}]})})`)).completed,true)
    shown=await js(`window.api.memoryCommand('memory_show',${JSON.stringify({memoryId})})`)
    assert.equal(shown.completed,true,JSON.stringify(shown));assert.equal(shown.data.record.sensitivityClass,'SENSITIVE');assert.ok(shown.data.record.canonicalText.startsWith('[SENSITIVE'))
    confirmation=js(`window.api.memoryEditSensitivity(${JSON.stringify({memoryId,revision:3,sensitive:false})})`)
    await decision(true);const normalToken=(await confirmation).data.token
    assert.equal((await js(`window.api.memoryCommand('memory_edit',${JSON.stringify({records:[{...row,revision:3,consentToken:normalToken}]})})`)).completed,true)
    shown=await js(`window.api.memoryCommand('memory_show',${JSON.stringify({memoryId})})`)
    assert.equal(shown.completed,true,JSON.stringify(shown));assert.equal(shown.data.record.canonicalText,row.text);assert.equal(shown.data.record.sensitivityClass,'NORMAL')
    const deletionRecords=[]
    for(const text of ['Synthetic deletable one','Synthetic deletable two']){
      const result=await js(`window.api.memoryCommand('memory_remember',${JSON.stringify({kind:'PREFERENCE',text,scope:'WORKSPACE'})})`)
      assert.equal(result.completed,true,JSON.stringify(result));deletionRecords.push({memoryId:result.data.memoryId,revision:result.data.revision})
    }
    let deletingMemories=js(`window.api.memoryCommand('memory_delete',${JSON.stringify({records:deletionRecords})})`)
    await decision(false);assert.equal((await deletingMemories).canceled,true)
    assert.equal((await js(`window.api.memoryCommand('memory_list',{scope:'ALL'})`)).data.records.length,3)
    deletingMemories=js(`window.api.memoryCommand('memory_delete',${JSON.stringify({records:deletionRecords})})`)
    await decision(true);const deletedMemories=await deletingMemories
    assert.equal(deletedMemories.completed,true,JSON.stringify(deletedMemories));assert.equal(deletedMemories.data.deleted,2)
    assert.equal((await js(`window.api.memoryCommand('memory_list',{scope:'ALL'})`)).data.records.length,1)
    record('Batch memory deletion requires Nova confirmation; cancel retains records and confirm removes exactly the selection')
    record('Authenticated table editing persists text/type/scope and honors Nova confirmation for both sensitivity changes')
    let deleting=js(`window.api.storageDeleteFiles([${JSON.stringify(id)}])`)
    await decision(false);assert.equal((await deleting).canceled,true)
    assert.equal((await js(`window.api.storageFiles(${JSON.stringify(alpha)})`)).data.files.length,1)
    deleting=js(`window.api.storageDeleteFiles([${JSON.stringify(id)}])`)
    await decision(true);assert.equal((await deleting).success,true)
    assert.equal((await js(`window.api.storageFiles(${JSON.stringify(alpha)})`)).data.files.length,0)
    assert.ok(fs.existsSync(original));record('Native Nova confirmation cancellation preserves file; confirmed deletion removes copy only')
    assert.equal((await js("window.api.storageOpenFolder('configuration')")).success,true)
    assert.equal(opened[0],profile)
    let clearing=js("window.api.storageDeleteFolder('catalog')")
    await decision(false);assert.equal((await clearing).canceled,true)
    clearing=js("window.api.storageDeleteFolder('catalog')")
    await decision(true);assert.equal((await clearing).data.restartRequired,true)
    assert.ok(fs.existsSync(catalog));assert.equal((await js('window.api.storageOverview()')).data.restartRequired,true)
    assert.deepEqual(errors,[]);assert.equal(stderr.join(''),'')
    record('Folder explorer uses owned path; confirmed cleanup is queued and never deletes a live store')
    restartExpected=true
    void js('window.api.storageRestart()').catch(()=>{})
    await decision(true)
  }catch(error){fail(error)}
})
