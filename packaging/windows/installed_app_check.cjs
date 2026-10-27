// Developer-only installed-payload check. Inspector is enabled only on our
// launched QA process to set known-folder paths before production code starts.
const fs=require('node:fs'),path=require('node:path'),net=require('node:net')
const {spawn,execFileSync}=require('node:child_process'),assert=require('node:assert/strict')
const http=require('node:http')
const appExe=path.resolve(process.argv[2]),output=path.resolve(process.argv[3])
const expectedVersion=process.argv[4]||JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../desktop/package.json'),'utf8')).version
assert.match(expectedVersion,/^\d+\.\d+\.\d+$/)
assert.ok(path.isAbsolute(process.argv[2])&&path.isAbsolute(process.argv[3]))
assert.ok(fs.statSync(appExe).isFile());assert.ok(!fs.existsSync(output),'Fresh QA output required')
fs.mkdirSync(output,{recursive:true})
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))
const inside=(root,target)=>{const relative=path.relative(root,target);return !relative||(!relative.startsWith('..'+path.sep)&&relative!=='..'&&!path.isAbsolute(relative))}
async function freePort(){return new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>resolve(port))})})}
class Cdp{
 constructor(url){this.ws=new WebSocket(url);this.serial=0;this.pending=new Map();this.events=new Map();this.ready=new Promise((resolve,reject)=>{this.ws.onopen=resolve;this.ws.onerror=reject});this.ws.onmessage=event=>{const frame=JSON.parse(event.data);if(frame.id){const task=this.pending.get(frame.id);if(task){this.pending.delete(frame.id);frame.error?task.reject(Error(JSON.stringify(frame.error))):task.resolve(frame.result)}}else{const task=this.events.get(frame.method);if(task){this.events.delete(frame.method);task(frame.params)}}}}
 event(name){return new Promise(resolve=>this.events.set(name,resolve))}
 async send(method,params={}){await this.ready;const id=++this.serial;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout: '+method))},30000);this.pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value)},reject:error=>{clearTimeout(timer);reject(error)}});this.ws.send(JSON.stringify({id,method,params}))})}
 async eval(expression){const r=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
 close(){this.ws.close()}
}
async function target(port){for(let n=0;n<150;n++){try{const rows=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();const row=rows.find(r=>r.webSocketDebuggerUrl);if(row)return row}catch{}await pause(200)}throw Error('Debugger target unavailable')}
const unicodeText='¡Hola! ¿Cómo estás? áéíóú ñ — 中文 🚀'
async function startOllamaFixture(){
 const model='nova-utf8-fixture:tiny',sockets=new Set(),timers=new Set()
 const stats={requests:[],userMessages:[],cancelledStreams:0,unexpected:[],realModelInference:false}
 const details={format:'gguf',family:'qwen3',families:['qwen3'],parameter_size:'0.5B',quantization_level:'Q4_K_M'}
 const server=http.createServer((req,res)=>{
  let body=''
  req.on('data',chunk=>{body+=chunk;if(body.length>1_000_000)req.destroy()})
  req.on('end',()=>{
   const url=new URL(req.url,'http://127.0.0.1').pathname
   stats.requests.push(url)
   const json=value=>{res.writeHead(200,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value))}
   if(url==='/api/version')return json({version:'0.0.0-owned-test'})
   if(url==='/api/tags')return json({models:[{name:model,model,size:65536,digest:'a'.repeat(64),modified_at:'2026-10-27T00:00:00Z',details}]})
   if(url==='/api/ps')return json({models:[]})
   if(url==='/api/show')return json({capabilities:['completion','tools'],details,model_info:{'general.architecture':'qwen3','general.parameter_count':500000000,'qwen3.context_length':8192},parameters:'num_ctx 8192'})
   if(url==='/api/chat'){
    const input=JSON.parse(body),last=[...input.messages].reverse().find(m=>m.role==='user')?.content||''
    stats.userMessages.push(last)
    const long=last.startsWith('cancel-check:'),chunk=content=>({model,message:{role:'assistant',content},done:false})
    if(input.stream===false)return json({model,message:{role:'assistant',content:unicodeText},done:true,prompt_eval_count:12,eval_count:12})
    res.writeHead(200,{'Content-Type':'application/x-ndjson; charset=utf-8','Cache-Control':'no-store'})
    res.write(JSON.stringify(chunk(unicodeText))+'\n')
    if(!long){res.end(JSON.stringify({model,message:{role:'assistant',content:''},done:true,prompt_eval_count:12,eval_count:12})+'\n');return}
    let n=0
    const timer=setInterval(()=>{
     if(res.destroyed){clearInterval(timer);timers.delete(timer);return}
     res.write(JSON.stringify(chunk(' · '+(++n)+' ñ 🚀'))+'\n')
     if(n===300){clearInterval(timer);timers.delete(timer);res.end(JSON.stringify({model,done:true})+'\n')}
    },150)
    timers.add(timer)
    res.once('close',()=>{clearInterval(timer);timers.delete(timer);stats.cancelledStreams++})
    return
   }
   stats.unexpected.push(url);res.writeHead(404);res.end('{}')
  })
 })
 server.on('connection',socket=>{sockets.add(socket);socket.once('close',()=>sockets.delete(socket))})
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
 return {url:'http://127.0.0.1:'+server.address().port,model,stats,
  close(){for(const timer of timers)clearInterval(timer);for(const socket of sockets)socket.destroy();server.close()}}
}
async function waitFor(probe,label,ms=30000){
 const deadline=Date.now()+ms
 while(Date.now()<deadline){if(await probe())return;await pause(100)}
 throw Error('Timed out: '+label)
}
const env={}
for(const name of ['SystemRoot','WINDIR','COMSPEC','PATHEXT','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','SystemDrive','ProgramData','ALLUSERSPROFILE','ProgramFiles','ProgramFiles(x86)','ProgramW6432','CommonProgramFiles','CommonProgramFiles(x86)','CommonProgramW6432','COMPUTERNAME','USERNAME','USERDOMAIN','OS','SESSIONNAME'])if(process.env[name])env[name]=process.env[name]
for(const[name,suffix]of Object.entries({HOME:'user',USERPROFILE:'user',APPDATA:'user/AppData/Roaming',LOCALAPPDATA:'user/AppData/Local',TEMP:'user/AppData/Local/Temp',TMP:'user/AppData/Local/Temp'})){env[name]=path.join(output,suffix);fs.mkdirSync(env[name],{recursive:true})}
// Keep the unique disposable TEMP root separate from the persisted QA profile.
env.TEMP=env.TMP=fs.mkdtempSync(path.join(process.env.TEMP,'nova-qa-'))
env.PATH=[path.join(env.SystemRoot,'System32'),env.SystemRoot,path.join(env.SystemRoot,'System32/WindowsPowerShell/v1.0')].join(';')
env.LOCAL_CLI_STATE_DIR=path.join(env.USERPROFILE,'.local/state/nova');env.OLLAMA_HOST='http://127.0.0.1:1'
const documents=path.join(output,'documents-ñ-🚀'),downloads=path.join(output,'downloads'),early=path.join(output,'early-user-data')
for(const directory of [documents,downloads,early])fs.mkdirSync(directory)
const result={status:'FAIL',checks:[],realModelInference:false,systemPythonRequired:false},check=(name,value)=>{assert.ok(value,name);result.checks.push(name)}
let child,inspector,renderer,fixture
;(async()=>{
 fixture=await startOllamaFixture()
 env.OLLAMA_HOST=fixture.url;env.LOCAL_CLI_MODEL=fixture.model
 env.PYTHONIOENCODING='cp1252'
 fs.mkdirSync(env.LOCAL_CLI_STATE_DIR,{recursive:true})
 fs.writeFileSync(path.join(env.LOCAL_CLI_STATE_DIR,'memory-preferences.json'),JSON.stringify({schemaVersion:1,lexicalRecall:true,semanticRecall:false,autoCapture:false,captureMode:'low_risk',sensitiveProjects:[]}))
 const backend=path.join(path.dirname(appExe),'resources/backend/nova-backend.exe')
 const runtime=JSON.parse(execFileSync(backend,['--runtime-info'],{env,cwd:output,encoding:'utf8',windowsHide:true,timeout:60000}))
 check('Installed frozen backend runs NumPy, PDF and SQLite without Python on PATH',runtime.status==='PASS'&&runtime.frozen&&runtime.browserPresent);result.runtime=runtime
 check('Frozen backend version matches release',runtime.version===expectedVersion)
 const browser=JSON.parse(execFileSync(backend,['--check-browser'],{env,cwd:output,encoding:'utf8',windowsHide:true,timeout:120000}))
 check('Installed native WebView2 opens and edits the owned local fixture and closes its job/profile',browser.status==='PASS'&&browser.profileRemoved&&browser.jobEmpty&&browser.hostExited);result.browser=browser
 const mainPort=await freePort(),rendererPort=await freePort()
 const stdout=fs.openSync(path.join(output,'app.stdout.log'),'wx'),stderr=fs.openSync(path.join(output,'app.stderr.log'),'wx')
 child=spawn(appExe,[`--inspect-brk=127.0.0.1:${mainPort}`,`--remote-debugging-port=${rendererPort}`,'--remote-debugging-address=127.0.0.1','--user-data-dir='+early],{env,cwd:output,windowsHide:true,stdio:['ignore',stdout,stderr]})
 child.once('error',error=>{result.launchError=error.message})
 inspector=new Cdp((await target(mainPort)).webSocketDebuggerUrl)
 await inspector.send('Runtime.enable');await inspector.send('Debugger.enable')
 const paused=inspector.event('Debugger.paused');await inspector.send('Runtime.runIfWaitingForDebugger');const frame=await paused
 const expression=`(()=>{const {app}=require('electron');app.setPath('appData',${JSON.stringify(env.APPDATA)});app.setPath('documents',${JSON.stringify(documents)});app.setPath('downloads',${JSON.stringify(downloads)});globalThis.__novaInstallerQA=app;return app.isPackaged})()`
 const patch=await inspector.send('Debugger.evaluateOnCallFrame',{callFrameId:frame.callFrames[0].callFrameId,expression,returnByValue:true})
 if(patch.exceptionDetails)throw Error(JSON.stringify(patch.exceptionDetails))
 check('Production packaged mode retained; known folders redirected before entry point runs',patch.result.value===true)
 await inspector.send('Debugger.resume')
 renderer=new Cdp((await target(rendererPort)).webSocketDebuggerUrl)
 for(let n=0;n<180;n++){if(await renderer.eval('!!window.api && !document.getElementById("nova-startup")'))break;await pause(250)}
 await renderer.eval('window.api.onSessionView(v=>window.__installerView=v);window.api.signalReady();true')
 let view
 for(let n=0;n<180;n++){view=await renderer.eval('window.__installerView?{session:window.__installerView.sessionId,connected:window.__installerView.status.connected}:null');if(view?.session&&view.connected)break;await pause(250)}
 check('Real packaged backend exchanges JSONL and remains connected',view?.session&&view.connected)
 check('Version is '+expectedVersion+' through actual preload and IPC',await renderer.eval('window.api.getAppVersion()')===expectedVersion)
 const projects=await renderer.eval('window.api.getProjects()')
 check('Default workspace lives in isolated writable documents, outside installation',projects.defaultPath===path.join(documents,'Nova/workspace'))
 const appData=await inspector.eval('globalThis.__novaInstallerQA.getPath("userData")')
 check('Profile is isolated below the owned QA directory',inside(output,appData))
 const general=await renderer.eval('window.api.setDesktopGeneral({language:"es",autoSwitchView:true,transitionsEnabled:false,showFiles:true,collapsibleSourceContext:false})')
 check('Preferences save through production IPC',general.success===true)
 fs.writeFileSync(path.join(appData,'qa-preserve.txt'),'owned profile marker')
 fs.writeFileSync(path.join(projects.defaultPath,'qa-preserve.txt'),'owned project marker')
 await renderer.eval('document.querySelector(".nova-rail [data-icon=settings]").closest("button").click();true')
 for(let n=0;n<100;n++){if(await renderer.eval('!!document.querySelector("[data-settings-section=about]")'))break;await pause(100)}
 await renderer.eval('document.querySelector("[data-settings-section=about]").click();true')
 for(let n=0;n<100;n++){if(await renderer.eval('document.querySelector(".nova-settings-dialog").textContent.includes('+JSON.stringify('v'+expectedVersion)+')'))break;await pause(100)}
 check('About visibly displays the installed version',await renderer.eval('document.querySelector(".nova-settings-dialog").textContent.includes('+JSON.stringify('v'+expectedVersion)+')'))
 const screenshot=await renderer.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'installed-about.png'),Buffer.from(screenshot.data,'base64'))
 await renderer.eval('document.querySelector(".nova-settings-close").click();true')
 await waitFor(()=>renderer.eval('!document.querySelector(".nova-settings-dialog")'),'settings closes')
 async function sendPrompt(text){
  await renderer.eval('(()=>{const e=document.querySelector("textarea.nova-input");e.focus();e.select();return true})()')
  await renderer.send('Input.insertText',{text})
  await waitFor(()=>renderer.eval('!!document.querySelector(".nova-send-button") && !document.querySelector(".nova-send-button").disabled'),'send enabled',45000)
  await renderer.eval('document.querySelector(".nova-send-button").click();true')
 }
 const firstPrompt='unicode-check: '+unicodeText
 await sendPrompt(firstPrompt)
 await waitFor(()=>renderer.eval('!window.__installerView.activeTurnId && window.__installerView.messages.some(m=>m.role==="assistant" && m.content?.includes('+JSON.stringify(unicodeText)+'))'),'Unicode reply completes')
 await renderer.eval('if(document.querySelector(".nova-home-scene"))document.querySelector(".nova-history-button").click();true')
 await waitFor(()=>renderer.eval('!document.querySelector(".nova-home-scene")'),'conversation history is visible')
 check('UTF-8 input reaches the owned Ollama fixture unchanged',fixture.stats.userMessages.includes(firstPrompt))
 check('Installed chat history renders accents, Chinese and emoji without replacement characters',await renderer.eval('[...document.querySelectorAll(".nova-message-assistant .msg-body.agent")].some(e=>e.innerText.includes('+JSON.stringify(unicodeText)+')) && !JSON.stringify(window.__installerView).includes("\\ufffd")'))
 const chatShot=await renderer.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'installed-unicode-chat.png'),Buffer.from(chatShot.data,'base64'))
 await sendPrompt('cancel-check: '+unicodeText)
 await waitFor(()=>renderer.eval('!!window.__installerView.activeTurnId && window.__installerView.messages.some(m=>m.streaming && m.content?.includes("🚀"))'),'Unicode stream is active')
 const cancelStarted=Date.now()
 await renderer.eval('document.querySelector(".nova-send-button").click();true')
 await waitFor(()=>renderer.eval('!window.__installerView.activeTurnId && !window.__installerView.activeGenerationId'),'cancel reaches terminal',20000)
 await waitFor(()=>renderer.eval('["Enviar","Send"].includes(document.querySelector(".nova-send-button")?.getAttribute("aria-label"))'),'composer returns to Send')
 await waitFor(()=>fixture.stats.cancelledStreams>0,'provider stream closes',10000)
 result.cancellationMilliseconds=Date.now()-cancelStarted
 check('Actual Stop button cancels an active Unicode response and releases the provider stream',fixture.stats.cancelledStreams>0)
 check('Cancellation refresh stays valid without APPLICATION_ADAPTER_FAILED or mojibake',await renderer.eval('!JSON.stringify(window.__installerView).includes("APPLICATION_ADAPTER_FAILED") && !JSON.stringify(window.__installerView).includes("\\ufffd")'))
 await sendPrompt('post-cancel-check: '+unicodeText)
 await waitFor(()=>renderer.eval('!window.__installerView.activeTurnId && window.__installerView.messages.filter(m=>m.role==="assistant" && m.content?.includes('+JSON.stringify(unicodeText)+') && m.deliveryStatus==="completed").length>=2'),'a new Unicode turn completes after cancellation')
 check('New messages still complete after cancellation',fixture.stats.userMessages.some(s=>s.startsWith('post-cancel-check:')))
 const cancelShot=await renderer.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'installed-unicode-cancel.png'),Buffer.from(cancelShot.data,'base64'))
 result.unicodeFixture=fixture.stats
 result.profile=appData;result.workspace=projects.defaultPath
 const exited=new Promise(resolve=>child.once('exit',()=>resolve(true)))
 await inspector.eval('setTimeout(()=>globalThis.__novaInstallerQA.quit(),50);true')
 renderer.close();inspector.close()
 const closed=await Promise.race([exited,pause(30000).then(()=>false)])
 check('Application closes normally and releases its backend',closed)
 check('Saved preferences survive normal close',JSON.parse(fs.readFileSync(path.join(appData,'desktop-preferences.json'),'utf8')).language==='es')
 result.status='PASS'
})().catch(async error=>{
 result.error=String(error.stack||error);process.exitCode=1
 if(renderer){
  try{result.failureView=await renderer.eval('({view:window.__installerView,input:document.querySelector("textarea.nova-input")?.value,buttonDisabled:document.querySelector(".nova-send-button")?.disabled})')
   const shot=await renderer.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'failure.png'),Buffer.from(shot.data,'base64'))
  }catch{}
 }
}).finally(()=>{
 if(fixture)result.unicodeFixture=fixture.stats
 renderer?.close();inspector?.close();if(child&&child.exitCode===null)child.kill()
 fixture?.close()
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result))
})
