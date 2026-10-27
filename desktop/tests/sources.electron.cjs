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
const deadline=setTimeout(()=>fail(Error('Sources integration timeout')),90000)
const spawn=cp.spawn
cp.spawn=function(command,args,options){if(args?.includes('--server')){backend=spawn(process.env.NOVA_TEST_PYTHON,args,{...options,cwd:alpha,env:{...options.env,PYTHONPATH:repo},windowsHide:true});backend.stderr.on('data',data=>stderr.push(String(data)));return backend}return spawn(command,args,options)}
electron.dialog.showOpenDialog=async()=>({canceled:!picked.length,filePaths:picked.shift()||[]})
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
electron.app.whenReady().then(async()=>{try{
 await until(()=>loaded&&view?.status?.ready,'backend and renderer')
 const second=path.join(output,'second.txt');fs.writeFileSync(second,'Another owned source.\n')
 picked.push([original,second])
 const imported=await js('window.api.sourcesPick()')
 assert.deepEqual(imported,{completed:true,imported:2})
 record('Native multi-file picker serially imports both real files into the current project')
 let inventory=await js('window.api.sourcesList()');assert.equal(inventory.success,true);assert.equal(inventory.data.files.length,2)
 const first=inventory.data.files.find(file=>file.name==='manual.txt')
 const destination=path.join(output,'Recovered original.txt');saves.push({canceled:false,filePath:destination})
 assert.equal((await js(`window.api.sourcesDownload([${JSON.stringify(first.id)}])`)).success,true)
 assert.deepEqual(fs.readFileSync(destination),fs.readFileSync(original))
 record('Source download writes the exact original bytes only to the native Save As destination')
 await js(`document.querySelector('[data-open-sources]').click()`)
 await until(()=>js("document.querySelectorAll('.sources-table tbody tr').length===2"),'real source table')
 const nav=await js("Array.from(document.querySelectorAll('.nova-rail button')).slice(0,3).map(button=>button.getAttribute('aria-label'))")
 assert.deepEqual(nav,['Proyectos','Fuentes','Recuerdos'])
 record('Sources opens after Projects and lists the real current-project copies')
 let deleting=js(`window.api.sourcesDelete([${JSON.stringify(first.id)}])`)
 await until(()=>children.some(child=>!child.isDestroyed()&&bindings.has(child.webContents.id)),'Spanish source confirmation')
 let child=children.find(item=>!item.isDestroyed()&&bindings.has(item.webContents.id))
 await until(async()=>(await child.webContents.executeJavaScript('document.body.textContent')).includes('Eliminar fuentes'),'Spanish confirmation text')
 await decision(false);assert.equal((await deleting).canceled,true)
 assert.equal((await js('window.api.sourcesList()')).data.files.length,2)
 await js("window.api.setDesktopLocale('en')")
 deleting=js(`window.api.sourcesDelete([${JSON.stringify(first.id)}])`)
 await until(()=>children.some(child=>!child.isDestroyed()&&bindings.has(child.webContents.id)),'English source confirmation')
 child=children.find(item=>!item.isDestroyed()&&bindings.has(item.webContents.id))
 await until(async()=>(await child.webContents.executeJavaScript('document.body.textContent')).includes('Delete sources'),'English confirmation text')
 await decision(true);assert.equal((await deleting).success,true)
 assert.equal((await js('window.api.sourcesList()')).data.files.length,1)
 assert.ok(fs.existsSync(original)&&fs.existsSync(second));record('Nova source confirmation works in ES/EN: cancel retains data; confirm removes only the saved copy')
 const remaining=(await js('window.api.sourcesList()')).data.files[0]
 assert.equal((await js(`window.api.sourcesMove([${JSON.stringify(remaining.id)}],null)`)).success,true)
 assert.equal((await js('window.api.sourcesList()')).data.files.length,0)
 assert.equal((await js('window.api.storageFiles(null)')).data.files.length,1)
 record('Unlinking removes the source from the project while retaining its file under Unlinked storage')
 assert.deepEqual(errors,[]);assert.equal(stderr.join(''),'')
 finished=true;clearTimeout(deadline);save();backend?.kill();electron.app.quit()
 }catch(error){fail(error)}})
