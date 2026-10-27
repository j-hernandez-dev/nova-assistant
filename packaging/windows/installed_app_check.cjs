// Developer-only installed-payload check. Inspector is enabled only on our
// launched QA process to set known-folder paths before production code starts.
const fs=require('node:fs'),path=require('node:path'),net=require('node:net')
const {spawn,execFileSync}=require('node:child_process'),assert=require('node:assert/strict')
const appExe=path.resolve(process.argv[2]),output=path.resolve(process.argv[3])
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
const env={}
for(const name of ['SystemRoot','WINDIR','COMSPEC','PATHEXT','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','SystemDrive','ProgramData','ALLUSERSPROFILE','ProgramFiles','ProgramFiles(x86)','ProgramW6432','CommonProgramFiles','CommonProgramFiles(x86)','CommonProgramW6432','COMPUTERNAME','USERNAME','USERDOMAIN','OS','SESSIONNAME'])if(process.env[name])env[name]=process.env[name]
for(const[name,suffix]of Object.entries({HOME:'user',USERPROFILE:'user',APPDATA:'user/AppData/Roaming',LOCALAPPDATA:'user/AppData/Local',TEMP:'user/AppData/Local/Temp',TMP:'user/AppData/Local/Temp'})){env[name]=path.join(output,suffix);fs.mkdirSync(env[name],{recursive:true})}
// Keep the unique disposable TEMP root separate from the persisted QA profile.
env.TEMP=env.TMP=fs.mkdtempSync(path.join(process.env.TEMP,'nova-qa-'))
env.PATH=[path.join(env.SystemRoot,'System32'),env.SystemRoot,path.join(env.SystemRoot,'System32/WindowsPowerShell/v1.0')].join(';')
env.LOCAL_CLI_STATE_DIR=path.join(output,'state');env.LOCAL_CLI_OLLAMA_HOST='http://127.0.0.1:1'
const documents=path.join(output,'documents'),downloads=path.join(output,'downloads'),early=path.join(output,'early-user-data')
for(const directory of [documents,downloads,early])fs.mkdirSync(directory)
const result={status:'FAIL',checks:[],realModelInference:false,systemPythonRequired:false},check=(name,value)=>{assert.ok(value,name);result.checks.push(name)}
let child,inspector,renderer
;(async()=>{
 const backend=path.join(path.dirname(appExe),'resources/backend/nova-backend.exe')
 const runtime=JSON.parse(execFileSync(backend,['--runtime-info'],{env,cwd:output,encoding:'utf8',windowsHide:true,timeout:60000}))
 check('Installed frozen backend runs NumPy, PDF and SQLite without Python on PATH',runtime.status==='PASS'&&runtime.frozen&&runtime.browserPresent);result.runtime=runtime
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
 check('Version is 0.13.0 through actual preload and IPC',await renderer.eval('window.api.getAppVersion()')==='0.13.0')
 const projects=await renderer.eval('window.api.getProjects()')
 check('Default workspace lives in isolated writable documents, outside installation',projects.defaultPath===path.join(documents,'Nova/workspace'))
 const appData=await inspector.eval('globalThis.__novaInstallerQA.getPath("userData")')
 check('Profile is isolated below the owned QA directory',inside(output,appData))
 const general=await renderer.eval('window.api.setDesktopGeneral({language:"es",autoSwitchView:false,transitionsEnabled:false,showFiles:true,collapsibleSourceContext:false})')
 check('Preferences save through production IPC',general.success===true)
 fs.writeFileSync(path.join(appData,'qa-preserve.txt'),'owned profile marker')
 fs.writeFileSync(path.join(projects.defaultPath,'qa-preserve.txt'),'owned project marker')
 await renderer.eval('document.querySelector(".nova-rail [data-icon=settings]").closest("button").click();true')
 for(let n=0;n<100;n++){if(await renderer.eval('!!document.querySelector("[data-settings-section=about]")'))break;await pause(100)}
 await renderer.eval('document.querySelector("[data-settings-section=about]").click();true')
 for(let n=0;n<100;n++){if(await renderer.eval('document.querySelector(".nova-settings-dialog").textContent.includes("v0.13.0")'))break;await pause(100)}
 check('About visibly displays the installed version',await renderer.eval('document.querySelector(".nova-settings-dialog").textContent.includes("v0.13.0")'))
 const screenshot=await renderer.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'installed-about.png'),Buffer.from(screenshot.data,'base64'))
 result.profile=appData;result.workspace=projects.defaultPath
 const exited=new Promise(resolve=>child.once('exit',()=>resolve(true)))
 await inspector.eval('setTimeout(()=>globalThis.__novaInstallerQA.quit(),50);true')
 renderer.close();inspector.close()
 const closed=await Promise.race([exited,pause(30000).then(()=>false)])
 check('Application closes normally and releases its backend',closed)
 check('Saved preferences survive normal close',JSON.parse(fs.readFileSync(path.join(appData,'desktop-preferences.json'),'utf8')).language==='es')
 result.status='PASS'
})().catch(error=>{result.error=String(error.stack||error);process.exitCode=1}).finally(()=>{
 renderer?.close();inspector?.close();if(child&&child.exitCode===null)child.kill()
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result))
})
