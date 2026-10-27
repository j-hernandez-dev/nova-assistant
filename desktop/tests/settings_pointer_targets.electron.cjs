/* Native pointer regression for every Settings section. Synthetic state and owned profile only. */
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
const desktop=path.resolve(__dirname,'..'),output=path.resolve(process.argv[2]),baseline=process.argv.includes('--baseline')
assert.ok(process.argv[2],'An owned output directory is required')
if(baseline)assert.ok(process.env.NOVA_SETTINGS_BASELINE_ROOT,'The original desktop checkout must be supplied explicitly')
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=String.raw`
import React,{useState} from 'react';import {createRoot} from 'react-dom/client'
import {I18nProvider,useI18n} from './src/i18n';import {AppearanceProvider} from './src/appearance';import {ShortcutsProvider} from './src/keyboard_shortcuts'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance';import {defaultShortcuts} from './shared/keyboard_shortcuts.cjs';import {installStartupScreen} from './shared/startup_screen'
import {SettingsPanel} from './src/components/SettingsPanel';import {LLMSettings} from './src/components/LLMSettings';import {EmbeddingSettings} from './src/components/EmbeddingSettings'
import {MemorySettings} from './src/components/MemorySettings';import {KnowledgeSettings} from './src/components/KnowledgeSettings';import {WebSettings} from './src/components/WebSettings'
import {ProjectsSettings} from './src/components/ProjectsSettings';import {ChatSettings} from './src/components/ChatSettings';import {StorageSettings} from './src/components/StorageSettings';import {AboutRuntime} from './src/components/AboutSettings'
import './src/styles.css';import './src/themes.css';import './src/window_surfaces.css'
const A='C:/Synthetic/Alpha',B='C:/Synthetic/Beta'
const folders=[{path:A,name:'Alpha',isDefault:true},{path:B,name:'Beta',isDefault:false}],projects={folders,defaultPath:A,activePath:A,busy:false}
let prefs={schemaVersion:1,locale:'es',language:'es',showFiles:true,autoSwitchView:false,transitionsEnabled:false,collapsibleSourceContext:false,...defaultAppearance},hidden=[]
let view={sessionId:'owned',workspace:A,stateRevision:1,status:{ready:true,connected:true,provider:'ollama',model:'local:7b',tools:['read_file','source_read']},
 readiness:{ready:true,observedAt:'2026-10-26T12:00:00Z'},approvals:[],inputs:[],context:{requestedTokens:8192,selectedTokens:8192},
 embedding:{modelId:'embed:1b',selectedModel:'embed:1b',connected:true,enabledModels:['embed:1b'],requestedTokens:1024,selectedTokens:1024},
 memory:{lexicalRecall:true,semantic:false,semanticAvailable:true,autoCapture:true,captureMode:'low_risk',sensitiveProjects:[]},
 knowledge:{closing:false},knowledgeOperations:[],knowledgeSettings:{lexicalRecall:true,semanticRecall:false,autoIndex:true,autoRebuild:true,semanticAvailable:true},
 fetch:{enabled:true},search:{enabled:true,engine:'google'},browser:{enabled:true,selected:'webview2',choices:['webview2','chrome','edge'].map(browser=>({browser,available:true}))}}
const file={id:'report',name:'Report.txt',bytes:128,projectPath:A,modifiedAt:'2026-10-26T12:00:00Z'}
window.__calls=[];window.__activations=[];window.__uiErrors=[]
window.addEventListener('error',event=>window.__uiErrors.push(event.error?.stack||event.message))
function publish(){view={...view,stateRevision:view.stateRevision+1};window.__publish?.({...view})}
const api={initialDesktopLocale:'es',initialDesktopAppearance:defaultAppearance,initialDesktopGeneral:prefs,initialDesktopShortcuts:defaultShortcuts(),
 getAppVersion:async()=>'fixture',getDesktopPreferences:async()=>prefs,getDesktopFonts:async()=>({success:true,fonts:['Arial']}),
 setDesktopLocale:async locale=>({success:true,preferences:prefs={...prefs,locale,language:locale}}),
 setDesktopGeneral:async next=>{window.__calls.push(['general',next]);return{success:true,preferences:prefs={...prefs,...next}}},
 setDesktopAppearance:async next=>{window.__calls.push(['appearance',next]);return{success:true,preferences:prefs={...prefs,...next}}},
 setShortcutCapture:async capture=>{window.__calls.push(['capture',capture]);return{success:true}},
 applicationCommand:async(kind,args)=>{window.__calls.push([kind,args]);if(kind==='SetContextWindow')view.context={...view.context,...args};
  if(kind==='SetEmbeddingSettings')view.embedding={...view.embedding,...args,selectedModel:args.modelId};if(kind==='SetKnowledgeSettings')view.knowledgeSettings={...view.knowledgeSettings,...args};
  if(kind==='SetWebSettings'){view.fetch.enabled=args.fetchEnabled;view.search={enabled:args.searchEnabled,engine:args.engine};view.browser={...view.browser,enabled:args.browserEnabled,selected:args.browser}}
  publish();return{accepted:true}},
 memoryCommand:async(kind,args)=>{window.__calls.push([kind,args]);view.memory={...view.memory,...args,semantic:args.semanticRecall};publish();return{completed:true}},
 memoryProjectAccess:async(...args)=>{window.__calls.push(['access',...args]);return{completed:false,canceled:true}},
 memoryTransfer:async(...args)=>{window.__calls.push(['transfer',...args]);return{completed:false,canceled:true}},
 storageOverview:async()=>({success:true,data:{totalBytes:128,categories:[{id:'attachments',bytes:128}],folders:[{id:'attachments',category:'attachments',path:'C:/Synthetic/Nova/attachments',bytes:128,exists:true}],projects:[{path:null,name:'',bytes:0,fileCount:0},{path:A,name:'Alpha',bytes:128,fileCount:1},{path:B,name:'Beta',bytes:0,fileCount:0}],restartRequired:false}}),
 storageFiles:async()=>({success:true,data:{files:[file]}}),storageMove:async(...args)=>{window.__calls.push(['move',...args]);return{success:true}},
 storageDownload:async(...args)=>{window.__calls.push(['download',...args]);return{success:true}},storageDeleteFiles:async(...args)=>{window.__calls.push(['delete',...args]);return{success:false,canceled:true}},
 storageOpenFolder:async(...args)=>{window.__calls.push(['open-folder',...args]);return{success:true}},storageDeleteFolder:async(...args)=>{window.__calls.push(['delete-folder',...args]);return{success:false,canceled:true}}
}
window.api=new Proxy(api,{get:(target,key)=>target[key]||(String(key).startsWith('on')?()=>()=>{}:async()=>({success:true}))})
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark')
document.addEventListener('click',event=>{const control=event.target.closest('button,input,select,textarea,summary,[role="option"]');if(control)window.__activations.push(control.id||control.className||control.tagName)},true)
function Harness(){const {setLocale}=useI18n(),[state,setState]=useState(view),[section,setSection]=useState('general'),[hiddenModels,setHidden]=useState(hidden)
 window.__publish=setState;window.__locale=setLocale
 const visibility={hiddenModels,ready:true,busy:false,error:false,save:async next=>{window.__calls.push(['visibility',next]);setHidden(next);return true}}
 return <SettingsPanel onClose={()=>{}} onSectionChange={setSection}
 connection={<LLMSettings view={state} models={['local:7b']} visibility={visibility} active={false} locked={false}/>}
 embedding={<EmbeddingSettings view={state} models={[{name:'embed:1b',kind:'embedding'}]} active={false} locked={false}/>}
 memory={<MemorySettings view={state} projects={projects}/>} knowledge={<KnowledgeSettings view={state}/>} web={<WebSettings view={state}/>}
 projects={<ProjectsSettings projects={projects} busy={false} errorCode={null} onAction={async(...args)=>{window.__calls.push(['project',...args])}}/>}
 chat={<ChatSettings disabled={false} chats={[{path:A,name:'Alpha',active:true,hasHistory:true,messageCount:3}]} loading={false} error={false} onClear={async(...args)=>{window.__calls.push(['clear',...args]);return{success:false,canceled:true}}} onOpen={(...args)=>window.__calls.push(['chat-open',...args])}/>}
 storage={<StorageSettings active={section==='storage'}/>} about={<AboutRuntime status={state.status}/>}/>
}
installStartupScreen(document,'es',defaultAppearance,()=>true,false,true)
document.documentElement.setAttribute('data-nova-startup','ready')
createRoot(document.getElementById('root')).render(<I18nProvider><ShortcutsProvider><AppearanceProvider><Harness/></AppearanceProvider></ShortcutsProvider></I18nProvider>)
`
const plugins=baseline?[{name:'original-settings',setup(build){build.onLoad({filter:/desktop[\\/]src[\\/].*\.(tsx|css)$/},args=>{
 const original=path.join(process.env.NOVA_SETTINGS_BASELINE_ROOT,path.relative(desktop,args.path))
 return{contents:fs.readFileSync(original,'utf8'),loader:args.path.endsWith('.css')?'css':'tsx',resolveDir:path.dirname(args.path)}
})}}]:[]
const bundle=require('esbuild').build({stdin:{contents:entry,sourcefile:'settings-pointer-fixture.tsx',resolveDir:desktop,loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')},plugins})
const html=fs.readFileSync(path.join(desktop,'index.html'),'utf8').replace('</head>','<link rel="stylesheet" href="renderer.css"></head>').replace(/<script\b[^>]*src="\/src\/main\.tsx"[^>]*><\/script>/,'<script src="renderer.js"></script>')
fs.copyFileSync(path.join(desktop,'public/icon.png'),path.join(output,'icon.png'));fs.writeFileSync(path.join(output,'index.html'),html)
let win;const errors=[],checked=[],themes=[],pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let n=0;n<200;n++){if(await js(code))return;await pause(20)}throw Error('Timeout: '+code)}
const rect=(selector)=>js(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center'});const b=n.getBoundingClientRect();return{x:b.x,y:b.y,width:b.width,height:b.height}})()`)
async function pointer(x,y,click=false){win.webContents.sendInputEvent({type:'mouseMove',x:Math.round(x),y:Math.round(y)});await pause(12);if(click){win.webContents.sendInputEvent({type:'mouseDown',x:Math.round(x),y:Math.round(y),button:'left',clickCount:1});win.webContents.sendInputEvent({type:'mouseUp',x:Math.round(x),y:Math.round(y),button:'left',clickCount:1});await pause(20)}}
async function nativeClick(selector){const b=await rect(selector);await pointer(b.x+b.width/2,b.y+b.height/2,true)}
async function section(name){await js(`document.querySelector('[data-settings-section="${name}"]').click()`);await pause(35)}
async function inertText(selector,label){
 await rect(selector);await pause(20)
 const b=await js(`(()=>{const n=document.querySelector(${JSON.stringify(selector)}),text=n.querySelector('input')&&Array.from(n.childNodes).find(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());const r=document.createRange();if(text)r.selectNodeContents(text);const b=text?r.getBoundingClientRect():n.getBoundingClientRect();return{x:b.x,y:b.y,width:b.width,height:b.height}})()`)
 const x=b.x+Math.min(12,b.width/2),y=b.y+b.height/2
 await js('window.__activations=[]');const before=await js('window.__calls.length')
 await pointer(x,y)
 const hovered=await js(`Array.from(document.querySelectorAll('.nova-settings-content :is(button,input,select,textarea):hover')).map(n=>n.outerHTML)`)
 if(hovered.length)fs.writeFileSync(path.join(output,'incorrect-label-hover.png'),(await win.webContents.capturePage()).toPNG())
 assert.deepEqual(hovered,[],label+': text must not hover a remote control')
 await pointer(x,y,true)
 assert.deepEqual(await js('window.__activations'),[],label+': text must not forward clicks')
 assert.equal(await js('window.__calls.length'),before,label+': text must not change settings')
 assert.equal(await js(`!!document.querySelector('.nova-settings-content :is(button,input,select,textarea):focus')`),false,label+': text must not focus a remote control')
 checked.push(label)
}
async function keyboard(key){win.webContents.sendInputEvent({type:'keyDown',keyCode:key});win.webContents.sendInputEvent({type:'keyUp',keyCode:key});await pause(25)}
app.whenReady().then(async()=>{try{
 await bundle
 win=new BrowserWindow({width:1280,height:900,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(message)})
 win.webContents.debugger.attach('1.3')
 await win.loadFile(path.join(output,'index.html'));await wait(`!!document.querySelector('[data-settings-select="language"]:not(:disabled)')&&!document.getElementById('nova-startup')`)
 await inertText('.nova-general-settings .nova-preference-row :is(.nova-setting-label,label)','General language caption')
 const sections=['general','appearance','shortcuts','connection','embedding','memory','knowledge','web','projects','chat','storage','about']
 for(const name of sections){
  await section(name)
  await js(`window.__texts=Array.from(document.querySelectorAll('.nova-settings-content :is(.nova-setting-label,.nova-preference-row p,.nova-context-settings>.settings-hint,.nova-shortcut-copy p,.nova-preference-row h4,.nova-storage-project strong,.settings-toggle-row)')).filter(n=>n.getClientRects().length);window.__texts.forEach((n,i)=>n.dataset.pointerText=String(i))`)
  const count=await js('window.__texts.length')
  for(let i=0;i<count;i++){
   // Target text after an inline checkbox without changing React-owned nodes.
   await inertText('[data-pointer-text="'+i+'"]',name+' text '+i)
  }
  if(name==='chat'){
   const area=await rect('.nova-project-chat'),control=await rect('.nova-chat-open'),del=await rect('.nova-project-chat .nova-settings-danger')
   assert.ok(control.x+control.width<del.x-8,'The chat open button must stop before empty row space')
   await js('window.__activations=[]');await pointer((control.x+control.width+del.x)/2,area.y+area.height/2,true)
   assert.deepEqual(await js('window.__activations'),[],'Empty chat row space must not open the chat')
  }
  const ax=await win.webContents.debugger.sendCommand('Accessibility.getFullAXTree')
  for(const node of ax.nodes.filter(node=>!node.ignored&&['button','checkbox','switch','combobox','slider','searchbox'].includes(node.role?.value)))assert.ok(node.name?.value,'Accessible name: '+JSON.stringify(node.role))
  await js(`document.querySelectorAll('[data-pointer-text]').forEach(n=>n.removeAttribute('data-pointer-text'))`)
 }
 // Real control hits, keyboard focus, combo options, sliders and disabled gating still work.
 await section('general');const select='[data-settings-select="language"]',b=await rect(select)
 await pointer(b.x+b.width/2,b.y+b.height/2);assert.equal(await js(`document.querySelector('${select}').matches(':hover')`),true)
 await nativeClick(select);await wait(`!!document.querySelector('[role="listbox"]')`);await keyboard('ESC')
 await js(`document.querySelector('${select}').focus()`);await keyboard('DOWN');await wait(`!!document.querySelector('[role="listbox"]')`);await keyboard('ESC')
 const toggle='[data-general="showFiles"]',old=await js(`document.querySelector('${toggle}').checked`)
 await nativeClick(toggle);await wait(`document.querySelector('${toggle}').checked===${!old}`)
 await js(`document.querySelector('${toggle}').focus()`);await keyboard('SPACE');await wait(`document.querySelector('${toggle}').checked===${old}`)
 await section('embedding');const slider='[data-embedding-context]',before=await js(`document.querySelector('${slider}').value`)
 await js(`document.querySelector('${slider}').focus()`);await keyboard('RIGHT');await wait(`document.querySelector('${slider}').value!==${JSON.stringify(before)}`)
 await nativeClick('[data-embedding-context-auto]');await wait(`document.querySelector('${slider}').disabled`)
 const callCount=await js('window.__calls.length');await nativeClick(slider);assert.equal(await js('window.__calls.length'),callCount,'Disabled slider cannot save')
 await section('shortcuts');await inertText('.nova-shortcut-copy .nova-setting-label','Shortcut caption cannot start recording')
 await nativeClick('.nova-shortcut-binding');await wait(`!!document.querySelector('[data-recording="true"]')`);await keyboard('ESC')
 await section('projects');await nativeClick('[data-project-menu]');await wait(`!!document.querySelector('[role="menu"]')`);await keyboard('ESC')
 await section('storage');await nativeClick('[data-storage-project="C:/Synthetic/Alpha"] button');await wait(`!!document.querySelector('.nova-storage-filename')`)
 await inertText('.nova-storage-filename','Storage filename cannot select checkbox')
 await nativeClick('.nova-storage-table tbody input');await wait(`!!document.querySelector('.nova-storage-selection[data-visible="true"]')`)
 await nativeClick('[data-settings-select="storageProject"]');await wait(`!!document.querySelector('[role="listbox"]')`);await keyboard('ESC')
 await section('about');await nativeClick('.nova-about-tools summary');await wait(`document.querySelector('.nova-about-tools').open`)
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await section('general')
  await inertText('.nova-general-settings .nova-setting-label',locale+' '+mode+' '+theme+' label')
  const proof=await js(`(()=>{const text=document.querySelector('.nova-general-settings .nova-setting-label'),control=document.querySelector('[data-settings-select="language"]');return{locale:document.documentElement.lang,theme:document.documentElement.dataset.novaTheme,mode:document.documentElement.dataset.novaScheme,title:text.textContent,font:getComputedStyle(text).fontSize,weight:getComputedStyle(text).fontWeight,color:getComputedStyle(text).color,name:control.getAttribute('aria-label'),overflow:document.documentElement.scrollWidth>innerWidth}})()`)
  assert.equal(proof.title,locale==='es'?'Idioma':'Language');assert.ok(proof.name);assert.equal(proof.weight,'600');assert.equal(proof.overflow,false);themes.push(proof)
 }
 await js(`window.__locale('es');window.__theme('dark','nova')`);await section('general');await nativeClick(select);await keyboard('ESC');await pointer(600,260)
 fs.writeFileSync(path.join(output,'general-pointer-es.png'),(await win.webContents.capturePage()).toPNG())
 win.setSize(700,850);await pause(100);await inertText('.nova-general-settings .nova-setting-label','Compact General caption');await nativeClick(select);await wait(`!!document.querySelector('[role="listbox"]')`);await keyboard('ESC')
 assert.equal(await js('document.documentElement.scrollWidth>innerWidth'),false)
 assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',sections,checked,themes,nativePointer:true,accessibleNames:true,keyboard:true,disabled:true,errors},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,checked,errors,rendererErrors:win?await js('window.__uiErrors'):[]},null,2));app.exit(1)}})
