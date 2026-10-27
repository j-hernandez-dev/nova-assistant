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
const deadline=setTimeout(()=>fail(Error('Knowledge settings integration timeout')),90000)
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

const http=require('node:http'),embeddings=[],chatRequests=[]
const chatModel='fixture-chat:latest',emModel='fixture-em:latest'
const models=[{name:chatModel,model:chatModel,size:100,digest:'chat-owned'},{name:emModel,model:emModel,size:100,digest:'em-owned'}]
const mock=http.createServer((req,res)=>{
 let raw='';req.on('data',data=>raw+=data);req.on('end',()=>{
  const input=raw?JSON.parse(raw):{},isEM=input.model===emModel
  res.setHeader('Content-Type','application/json')
  if(req.url==='/api/version')return res.end(JSON.stringify({version:'0.7.0'}))
  if(req.url==='/api/tags'||req.url==='/api/ps')return res.end(JSON.stringify({models}))
  if(req.url==='/api/show')return res.end(JSON.stringify({capabilities:isEM?['embedding']:['completion','tools'],
   digest:isEM?'em-owned':'chat-owned',details:{family:isEM?'bert':'llama',parameter_size:'1B',quantization_level:'Q4_K_M'},
   model_info:isEM?{'bert.embedding_length':3,'bert.context_length':32768}:{'llama.context_length':32768},template:'{{ .Messages }}',parameters:''}))
  if(req.url==='/api/embed'){embeddings.push(input);return res.end(JSON.stringify({embeddings:input.input.map(()=>[1,0,0]),prompt_eval_count:12}))}
  if(req.url==='/api/chat'){chatRequests.push(input);return res.end(JSON.stringify({model:chatModel,message:{role:'assistant',content:'The project uses the local database server. [K1]'},done:true,prompt_eval_count:200,eval_count:15})+'\n')}
  res.statusCode=404;res.end(JSON.stringify({error:'unsupported synthetic route'}))
 })
})
mock.listen(0,'127.0.0.1',()=>{
 const endpoint='http://127.0.0.1:'+mock.address().port,config=path.join(home,'.config','nova','config')
 fs.mkdirSync(path.dirname(config),{recursive:true})
 fs.writeFileSync(config,'model='+chatModel+'\nollama_host='+endpoint+'\nmemory_embedding_endpoint='+endpoint+'\n')
 const state=path.join(home,'.local','state','nova');fs.mkdirSync(state,{recursive:true})
 fs.writeFileSync(path.join(state,'memory-preferences.json'),JSON.stringify({schemaVersion:1,lexicalRecall:true,semanticRecall:false,autoCapture:false,captureMode:'low_risk',sensitiveProjects:[]}))
 require('../dist-electron/main.js')
})

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
 await until(()=>loaded&&view?.status?.ready&&view?.knowledgeSettings?.semanticAvailable,'backend and embedding inventory')
 const defaults={lexicalRecall:true,semanticRecall:false,autoIndex:true,autoRebuild:true}
 if(reopen){
  for(const [key,value] of Object.entries(defaults))assert.equal(view.knowledgeSettings[key],value)
  record('Reset defaults survive a complete application restart')
  finished=true;clearTimeout(deadline);save();backend?.kill();mock.close();electron.app.quit();return
 }
 for(const [key,value] of Object.entries(defaults))assert.equal(view.knowledgeSettings[key],value)
 picked.push([original]);assert.equal((await js('window.api.sourcesPick()')).completed,true)
 await until(()=>view?.knowledgeSettings?.indexedSources===1&&!view?.knowledgeSettings?.indexing,'automatic source indexing')
 assert.ok(embeddings.some(request=>request.model===emModel&&request.options?.num_ctx===8192&&request.truncate===false))
 record('A saved source is indexed through the selected EM and its automatic context setting')
 await js('document.querySelector(".nova-rail [data-icon=settings]").parentElement.click()')
 await until(()=>js('!!document.querySelector("[data-settings-section=knowledge]")'),'settings')
 await js('document.querySelector("[data-settings-section=knowledge]").click()')
 await until(()=>js('document.querySelectorAll("[data-knowledge-setting]").length===4'),'Knowledge switches')
 assert.equal(await js('!!document.querySelector("#nova-settings-rag-query,[data-testid=rag-panel]")'),false)
 assert.equal((await js('window.api.applicationCommand("SetEmbeddingSettings",{modelId:"",requestedTokens:0,enabledModels:[]})')).accepted,true)
 await until(()=>view?.knowledgeSettings?.semanticAvailable===false,'EM unavailable')
 await until(()=>js('Array.from(document.querySelectorAll("[data-knowledge-setting]")).filter(node=>node.disabled).length===3'),'EM controls disabled')
 assert.equal(await js('Array.from(document.querySelectorAll("[data-knowledge-setting]")).filter(node=>node.disabled).length'),3)
 assert.equal((await js('window.api.applicationCommand("ResetEmbeddingSettings",{})')).accepted,true)
 await until(()=>view?.knowledgeSettings?.semanticAvailable===true&&!view?.knowledgeSettings?.indexing,'EM restored')
 record('Unavailable EM disables the three dependent controls and restoring EM enables them')
 await js('document.querySelector(".nova-settings-close").click()')
 const configured=await js('window.api.applicationCommand("SetKnowledgeSettings",'+JSON.stringify({...defaults,lexicalRecall:false,semanticRecall:true})+')')
 assert.equal(configured.accepted,true,JSON.stringify(configured))
 await until(()=>view?.knowledgeSettings?.semanticRecall&&!view?.knowledgeSettings?.lexicalRecall&&!view?.knowledgeSettings?.indexing,'semantic configuration')
 const submitted=await js('window.api.applicationCommand("SubmitUserInput",{content:"Which service hosts the data?"})')
 assert.equal(submitted.accepted,true,JSON.stringify(submitted))
 await until(()=>chatRequests.length>0&&!view?.activeTurnId,'semantic documentary turn')
 assert.ok(chatRequests.some(request=>JSON.stringify(request.messages).includes('Database installation: use the local server.')))
 record('With lexical retrieval off, a real coordinator Turn admits semantically retrieved source text into the synthetic LLM request')
 assert.equal((await js('window.api.applicationCommand("SetKnowledgeSettings",'+JSON.stringify({...defaults,lexicalRecall:false,semanticRecall:true,autoIndex:false,autoRebuild:false})+')')).accepted,true)
 await until(()=>!view?.knowledgeSettings?.indexing&&!view?.knowledgeSettings?.autoRebuild,'automatic rebuild disabled')
 const before=embeddings.length
 assert.equal((await js('window.api.applicationCommand("SetEmbeddingSettings",'+JSON.stringify({modelId:emModel,requestedTokens:4096,enabledModels:[emModel]})+')')).accepted,true)
 await until(()=>view?.embedding?.selectedTokens===4096&&!view?.knowledgeSettings?.indexing,'new EM context without automatic rebuild')
 assert.equal(embeddings.length,before)
 assert.equal((await js('window.api.applicationCommand("ResetKnowledgeSettings",{})')).accepted,true)
 await until(()=>view?.knowledgeSettings?.indexedSources===1&&!view?.knowledgeSettings?.indexing,'reset and rebuild')
 assert.ok(embeddings.slice(before).some(request=>request.options?.num_ctx===4096))
 const saved=JSON.parse(fs.readFileSync(path.join(home,'.local','state','nova','knowledge-preferences.json'),'utf8'))
 assert.deepEqual(saved,{schemaVersion:1,...defaults})
 record('Rebuild permission is respected; Reset restores the four persistent defaults and rebuilds with the new context')
 assert.deepEqual(errors,[]);assert.equal(stderr.join(''),'')
 finished=true;clearTimeout(deadline);save();backend?.kill();mock.close();electron.app.quit()
 }catch(error){fail(error)}})
