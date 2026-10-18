// Manual Electron startup smoke, isolated profile and scripted inference only.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),Module=require('node:module')
const electron=require('electron'),repo=path.resolve(__dirname,'../..')
assert.ok(process.env.NOVA_GUI_TEST_OUTPUT && process.env.NOVA_TEST_PYTHON,'explicit owned output and Python required')
const output=path.resolve(process.env.NOVA_GUI_TEST_OUTPUT),english=process.argv.includes('--english'),broken=process.argv.includes('--broken-entry'),savedAppearance=process.argv.includes('--saved-appearance')
assert.ok(!fs.existsSync(path.join(output,'started.json')),'use a fresh owned output')
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'started.json'),JSON.stringify({pid:process.pid,at:new Date().toISOString()}))
const profile=path.join(output,'app-data','nova-desktop'),home=path.join(output,'home'),workspace=path.join(output,'project')
for(const directory of [profile,home,workspace])fs.mkdirSync(directory,{recursive:true})
fs.writeFileSync(path.join(profile,'desktop-preferences.json'),JSON.stringify({schemaVersion:1,locale:english?'en':'es',reduceMotion:savedAppearance,showStartupScreen:!savedAppearance}))
fs.writeFileSync(path.join(profile,'project-preferences.json'),JSON.stringify({schemaVersion:1,folders:[workspace],activePath:workspace}))
electron.app.setPath('appData',path.dirname(profile));process.env.XDG_CONFIG_HOME=path.join(home,'.config')
let backend,win,held,block=true,breakOnce=broken,showRequests=0
const checks=[],crashes=[],spawn=cp.spawn
cp.spawn=function(command,args,options){
  if(args.includes('--server')){
    backend=spawn(process.env.NOVA_TEST_PYTHON,[path.join(repo,'tests/desktop_backend_fixture.py')],{...options,cwd:workspace,windowsHide:true,
      env:{...options.env,PYTHONPATH:process.env.NOVA_TEST_SOURCE||repo,USERPROFILE:home,HOME:home,LOCALAPPDATA:path.join(home,'AppData','Local'),
        LOCAL_CLI_MODEL:'local:7b',LOCAL_CLI_PROVIDER:'ollama',PYTHONDONTWRITEBYTECODE:'1',LOCAL_CLI_AUTO_UPDATE:'false'}})
    backend.stderr.on('data',()=>{});return backend
  }
  return spawn(command,args,options)
}
class StartupWindow extends electron.BrowserWindow{
  setTitle(){return super.setTitle('Nova — Startup validation')}
  show(){showRequests++;return super.show()}
  constructor(options){super(options);if(options.parent)return
    assert.equal(options.show,false,'host must wait for first paint')
    win=this;this.setTitle('Nova — Startup validation')
    this.webContents.on('render-process-gone',(_event,details)=>crashes.push(details.reason))
    this.webContents.on('preload-error',(_event,_preload,error)=>crashes.push(error.message))
    this.webContents.session.webRequest.onBeforeRequest({urls:['file:///*']},(request,callback)=>{
      if(request.url.includes('/assets/index-')&&request.url.endsWith('.js')){
        if(breakOnce){breakOnce=false;callback({cancel:true});return}
        if(block){held=callback;return}
      }
      callback({})
    })
  }
}
const load=Module._load
Module._load=function(name,...args){return name==='electron'?{...electron,BrowserWindow:StartupWindow}:load.call(this,name,...args)}
require('../dist-electron/main.js')
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms))
async function until(fn,label,ms=25000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await delay(60)}throw new Error('Timeout: '+label)}
async function evaluate(expression){const result=await win.webContents.debugger.sendCommand('Runtime.evaluate',{expression,returnByValue:true});if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value}
const record=name=>{checks.push(name);console.log('PASS',name)}
function save(status,error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status,english,broken,checks,crashes,error,runtime:process.versions},null,2))}
electron.app.whenReady().then(async()=>{
  try{
    await until(()=>win,'owned window');win.webContents.debugger.attach('1.3')
    await until(()=>showRequests>0,'host requests showing the first painted document')
    // STARTUPINFO from a hidden Windows helper may suppress the first ShowWindow.
    // Only repeat it after the production host has requested display.
    if(!win.isVisible())win.show()
    await until(()=>win.isVisible(),'owned review window visible')
    await until(()=>evaluate(`!!document.getElementById('nova-startup')?.hasAttribute('data-startup-managed')`),'preload screen before renderer')
    assert.equal(await evaluate(`document.documentElement.lang`),english?'en':'es')
    if(savedAppearance){
      assert.equal(await evaluate(`document.documentElement.dataset.novaReduceMotion`),'true')
      assert.equal(await evaluate(`document.documentElement.dataset.novaShowStartup`),'false')
      assert.equal(await evaluate(`getComputedStyle(document.getElementById('nova-startup')).display`),'none')
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.nova-startup-streak')).animationName`),'none')
      record('Saved appearance is applied in preload before the renderer: no splash or loading animation')
      block=false;assert.ok(held,'renderer request was held');held({});held=null
      await until(()=>evaluate(`!document.getElementById('nova-startup')&&!!document.querySelector('.nova-rail')`),'mounted UI opens without splash',40000)
      assert.equal(await evaluate(`document.getElementById('root').hasAttribute('inert')`),false)
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.nova-orbit-core')).animationName`),'none')
      record('Hidden splash opens an interactive mounted UI; saved reduced motion keeps the main mascot static')
      assert.deepEqual(crashes,[]);save('PASS');backend?.kill();electron.app.quit();return
    }
    assert.equal(await evaluate(`document.getElementById('root').hasAttribute('inert')`),true)
    assert.equal(await evaluate(`!!document.querySelector('.nova-rail')`),false)
    record('First visible frame has official startup screen before the React bundle; saved locale applied')
    assert.equal(await evaluate(`document.querySelector('.nova-startup-mark').querySelectorAll('image, foreignObject, rect').length`),0)
    assert.equal(await evaluate(`document.querySelector('.nova-startup-star').tagName.toLowerCase()`),'path')
    record('Loading emblem is a transparent vector with a separate star and no bitmap or tile')
    if(broken){
      await until(()=>evaluate(`!document.getElementById('nova-startup-action').hidden`),'script failure retry')
      assert.equal(await evaluate(`document.getElementById('nova-startup-action').textContent`),english?'Retry':'Reintentar')
      record('Broken entry displays a localized manual retry without a blank window')
      block=false
      await evaluate(`document.getElementById('nova-startup-action').click()`)
      record('Manual retry reloads the same UI without replaying a conversation')
    }else{
      const before=await evaluate(`getComputedStyle(document.querySelector('.nova-startup-streak')).strokeDashoffset`)
      await delay(250)
      assert.notEqual(await evaluate(`getComputedStyle(document.querySelector('.nova-startup-streak')).strokeDashoffset`),before)
      record('Orbit trail animates while the renderer bundle is held')
      await win.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]})
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.nova-startup-streak')).animationName`),'none')
      assert.equal(await evaluate(`getComputedStyle(document.querySelector('.nova-startup-star')).animationName`),'none')
      await win.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[]})
      record('Reduced motion disables both startup animations')
      if(process.argv.includes('--review'))await delay(22000)
      await until(()=>evaluate(`!document.getElementById('nova-startup-action').hidden`),'bounded startup wait',20000)
      assert.equal(await evaluate(`document.getElementById('nova-startup-action').textContent`),english?'Retry':'Reintentar')
      record('Missing renderer offers a bounded manual recovery; no automatic reload')
      await evaluate(`(() => {
        const screen=document.getElementById('nova-startup');
        window.__novaStartupFade={samples:[],rootVisible:false};
        const observer=new MutationObserver(() => {
          if(!screen.hasAttribute('data-leaving'))return;
          observer.disconnect();
          window.__novaStartupFade.rootVisible=!document.getElementById('root').hasAttribute('inert');
          const sample=()=>{
            if(!screen.isConnected)return;
            window.__novaStartupFade.samples.push(Number(getComputedStyle(screen).opacity));
            requestAnimationFrame(sample);
          };
          requestAnimationFrame(sample);
        });
        observer.observe(screen,{attributes:true,attributeFilter:['data-leaving']});
      })()`)
      block=false;assert.ok(held,'renderer request was held');held({});held=null
    }
    await until(()=>evaluate(`!document.getElementById('nova-startup')&&!!document.querySelector('.nova-rail')`),'initial snapshot reveals normal UI',40000)
    assert.equal(await evaluate(`document.getElementById('root').hasAttribute('inert')`),false)
    assert.equal(await evaluate(`document.documentElement.lang`),english?'en':'es')
    if(!broken){
      const fade=await evaluate(`window.__novaStartupFade`)
      assert.equal(fade.rootVisible,true,'UI is visible below the exiting splash')
      assert.ok(fade.samples.some(opacity=>opacity>0.05&&opacity<0.95),'native compositor must render intermediate opacity')
      record('Startup fades through intermediate frames over the revealed UI before removing its overlay')
    }
    assert.deepEqual(crashes,[])
    record('Normal UI replaces startup after initial Application state; locale and interactivity preserved')
    save('PASS');backend?.kill();electron.app.quit()
  }catch(error){console.error(error.stack||error);save('FAIL',String(error.stack||error));backend?.kill();electron.app.exit(1)}
})
electron.app.on('before-quit',()=>backend?.kill())
setTimeout(()=>{save('FAIL','test timeout');backend?.kill();electron.app.exit(2)},120000).unref()
