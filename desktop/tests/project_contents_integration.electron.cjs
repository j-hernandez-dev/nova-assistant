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
  fs.writeFileSync(path.join(profile,'project-preferences.json'),JSON.stringify({schemaVersion:2,defaultPath:alpha,folders:[alpha,beta],activePath:alpha}))
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
const deadline=setTimeout(()=>fail(Error('Project contents integration timeout')),90000)
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
 fs.writeFileSync(path.join(alpha,'project-note.txt'),'A project file, separate from saved sources.')
 const second=path.join(output,'second.txt');fs.writeFileSync(second,'Another owned source.\n')
 picked.push([original,second])
 const imported=await js('window.api.sourcesPick()');assert.equal(imported.completed,true);assert.equal(imported.imported,2);assert.equal(imported.sourceIds.length,2)
 const inventory=await js('window.api.sourcesList()')
 assert.equal(inventory.success,true)
 const first=inventory.data.files.find(file=>file.name==='manual.txt')
 fs.renameSync(original,path.join(output,'moved-original.txt'))
 const preview=await js('window.api.sourcePreview('+JSON.stringify(first.id)+')')
 assert.equal(preview.success,true);assert.equal(preview.data.content,'Database installation: use the local server.\n')
 record('Real authenticated source preview reads the owned SQLite blob after the original was moved')
 const normal=await js('window.api.memoryCommand("memory_remember",{kind:"WORKSPACE_FACT",text:"Este proyecto utiliza una base de datos local.",scope:"WORKSPACE"})')
 assert.equal(normal.completed,true,JSON.stringify(normal))
 const sensitive=js('window.api.memoryCommand("memory_remember",{kind:"PREFERENCE",text:"Recuerdo sensible sintético.",scope:"WORKSPACE",sensitive:true,consentSensitive:true})')
 await decision(true);assert.equal((await sensitive).completed,true)
 await js('document.querySelector(".nova-rail button").click()')
 await until(()=>js('!!document.querySelector(".project-content-tabs")'),'project content')
 assert.equal(await js('document.querySelector(".project-content-tabs [aria-selected=true]").textContent'),'Archivos')
 await until(()=>js('!!document.querySelector(".explorer-node")'),'project file')
 await js('document.querySelector(".explorer-node").click()')
 await until(()=>js('document.querySelector(".file-viewer-content")?.textContent.includes("A project file")'),'existing file viewer')
 await js('Array.from(document.querySelectorAll(".project-content-tabs button")).find(node=>node.textContent==="Fuentes").click()')
 await until(()=>js('document.querySelectorAll(".project-content-item").length===2&&!document.querySelector(".project-content-item").disabled'),'saved source rows')
 await js('Array.from(document.querySelectorAll(".project-content-item")).find(node=>node.textContent==="manual.txt").click()')
 await until(()=>js('document.querySelector(".file-viewer-content")?.textContent.includes("Database installation")'),'saved source viewer')
 record('Full App keeps Files as the initial tab and previews project files and saved source copies')
 await js('Array.from(document.querySelectorAll(".project-content-tabs button")).find(node=>node.textContent==="Recuerdos").click()')
 await until(()=>js('document.querySelectorAll(".project-content-item").length===2&&!document.querySelector(".project-content-sensitive input").disabled'),'memory rows')
 assert.equal(await js('document.querySelector(".project-content-list").textContent.includes("Recuerdo sensible sintético.")'),false)
 await js('Array.from(document.querySelectorAll(".project-content-item")).find(node=>node.textContent.includes("base de datos")).click()')
 await until(()=>js('!!document.querySelector(".project-memory-preview")'),'memory viewer')
 assert.deepEqual(await js('Array.from(document.querySelectorAll(".project-memory-preview dt")).map(node=>node.textContent)'),['Tipo','Ámbito','Contenido sensible'])
 assert.equal(await js('document.querySelector(".project-memory-preview p").textContent'),'Este proyecto utiliza una base de datos local.')
 await delay(150)
 fs.writeFileSync(path.join(output,'project-memories-es.png'),(await win.webContents.capturePage()).toPNG())
 await js('document.querySelector(".project-content-sensitive input").click()');await decision(false)
 await until(()=>js('!document.querySelector(".project-content-sensitive input").disabled'),'canceled inspection')
 assert.equal(await js('document.querySelector(".project-content-sensitive input").checked'),false)
 await js('document.querySelector(".project-content-sensitive input").click()');await decision(true)
 await until(()=>js('document.querySelector(".project-content-sensitive input").checked&&!document.querySelector(".project-content-sensitive input").disabled'),'approved inspection')
 await js('Array.from(document.querySelectorAll(".project-content-item")).find(node=>node.textContent==="Recuerdo sensible sintético.").click()')
 await until(()=>js('document.querySelector(".project-memory-preview p")?.textContent==="Recuerdo sensible sintético."'),'sensitive viewer')
 await js('document.querySelector(".project-content-sensitive input").click()')
 await until(()=>js('!document.querySelector(".project-memory-preview")&&!document.querySelector(".project-content-sensitive input").disabled'),'sensitive revocation')
 assert.equal(await js('document.querySelector(".project-content-list").textContent.includes("Recuerdo sensible sintético.")'),false)
 record('Nova confirmations gate real sensitive inspection; cancel preserves masking and uncheck clears the right viewer')
 const switched=await js('window.api.projectAction("select",'+JSON.stringify(beta)+')')
 assert.equal(switched.success,true,JSON.stringify(switched))
 await until(()=>js('document.querySelector(".project-content-tabs [aria-selected=true]")?.textContent==="Archivos"'),'new project default tab')
 await js('Array.from(document.querySelectorAll(".project-content-tabs button")).find(node=>node.textContent==="Fuentes").click()')
 await until(()=>js('document.querySelector(".project-content-list").textContent.includes("no tiene fuentes")'),'new project empty list')
 assert.equal((await js('window.api.sourcePreview('+JSON.stringify(first.id)+')')).success,false)
 record('Changing project resets the tab, clears prior details and rejects foreign source IDs')
 assert.deepEqual(errors,[]);assert.equal(stderr.join(''),'')
 finished=true;clearTimeout(deadline);save();backend?.kill();electron.app.quit()
 }catch(error){fail(error)}})
