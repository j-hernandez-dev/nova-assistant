/* Real App and memory window, with an owned profile and synthetic host projections. */
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
assert.ok(process.argv[2],'An owned output directory is required')
const output=path.resolve(process.argv[2]),desktop=path.resolve(__dirname,'..'),pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=String.raw`
import React from 'react';import {createRoot} from 'react-dom/client';import App from './src/App'
import {I18nProvider,useI18n} from './src/i18n';import {AppearanceProvider} from './src/appearance';import {ShortcutsProvider} from './src/keyboard_shortcuts'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance';import {defaultShortcuts} from './shared/keyboard_shortcuts.cjs';import {installStartupScreen} from './shared/startup_screen'
import './src/styles.css';import './src/themes.css';import './src/window_surfaces.css'
const A='C:/Synthetic/Alpha',B='C:/Synthetic/Beta';let observers=[],projectObservers=[]
let prefs={schemaVersion:1,locale:'es',language:'es',showFiles:true,transitionsEnabled:false,...defaultAppearance}
let proposals={[A]:['a','b'],[B]:['other']}
const folders=[{path:A,name:'Alpha',isDefault:true},{path:B,name:'Beta',isDefault:false}]
let view={sessionId:'owned',sequence:0,stateRevision:1,workspace:A,status:{ready:true,connected:true,provider:'ollama',model:'local:7b',tools:[]},
 readiness:{ready:true,observedAt:'2026-10-26T12:00:00Z',installedModels:[{name:'local:7b',kind:'llm'}]},modelPreferenceError:null,messages:[],activeTurnId:null,activeGenerationId:null,toolActivities:[],approvals:[],inputs:[],
 conversation:{hasConversation:true,historyVisible:false,unreadCount:0},rag:{enabled:false,availability:'DISABLED'},error:null,gap:false,recovering:false,fileRevision:0,
 memory:{lexicalRecall:true,semantic:false,autoCapture:true,maintenanceBusy:false},knowledge:{hostAcquisition:true,attachmentRefs:[]},knowledgeOperations:[]}
const projectState=()=>({schemaVersion:1,defaultPath:A,activePath:view.workspace,busy:false,folders})
function publish(){view={...view,stateRevision:view.stateRevision+1};observers.forEach(fn=>fn(structuredClone(view)));projectObservers.forEach(fn=>fn(projectState()))}
const proposal=id=>({jobId:'job-'+id,revision:1,proposal:{proposalId:id,text:'Propuesta '+id,kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE'}})
window.__calls=[]
const api={initialDesktopLocale:'es',initialDesktopAppearance:defaultAppearance,initialDesktopGeneral:prefs,initialDesktopShortcuts:defaultShortcuts(),
 getDesktopPreferences:async()=>prefs,setDesktopLocale:async locale=>({success:true,preferences:prefs={...prefs,locale,language:locale}}),
 getModelVisibility:async()=>({hiddenModels:[]}),getAppVersion:async()=>'fixture',getProjects:async()=>projectState(),
 onSessionView:fn=>{observers.push(fn);setTimeout(publish,0);return()=>{observers=observers.filter(item=>item!==fn)}},
 onProjectsChanged:fn=>{projectObservers.push(fn);return()=>{projectObservers=projectObservers.filter(item=>item!==fn)}},signalReady:publish,
 listDir:async root=>({success:true,root,path:root,entries:[],truncated:false,nextOffset:null}),setHistoryVisible:async()=>({success:true}),
 memoryCommand:async(name,args)=>{const root=view.workspace;window.__calls.push([name,args,root]);const rows=proposals[root].map(proposal)
  if(name==='memory_proposals'&&window.__hold){window.__hold=false;await new Promise(resolve=>window.__release=resolve)}
  if(name==='memory_reject')proposals[root]=proposals[root].filter(id=>id!==args.proposalId)
  publish();return{completed:true,stateRevision:view.stateRevision,data:name==='memory_proposals'?{proposals:rows}:name==='memory_list'?{records:[]}: {rejected:true}}},
 projectAction:async(action,root)=>{view={...view,workspace:root};publish();return{success:true,state:projectState()}},sendToPython:()=>{},refreshReadiness:async()=>{}
}
window.api=new Proxy(api,{get:(target,key)=>target[key]||(String(key).startsWith('on')?()=>()=>{}:async()=>({success:true}))})
window.__pending=(root,ids)=>{proposals[root]=ids;publish()};window.__root=root=>{view={...view,workspace:root};publish()}
window.__busy=busy=>{view={...view,memory:{...view.memory,maintenanceBusy:busy}};publish()}
window.__bump=publish
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark')
function Root(){const {setLocale}=useI18n();window.__locale=setLocale;return <App/>}
installStartupScreen(document,'es',defaultAppearance,()=>true,false,true)
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><ShortcutsProvider><AppearanceProvider><Root/></AppearanceProvider></ShortcutsProvider></I18nProvider></React.StrictMode>)
`
require('esbuild').buildSync({stdin:{contents:entry,sourcefile:'memory-notifications-fixture.tsx',resolveDir:desktop,loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
const html=fs.readFileSync(path.join(desktop,'index.html'),'utf8').replace('</head>','<link rel="stylesheet" href="renderer.css"></head>').replace(/<script\b[^>]*src="\/src\/main\.tsx"[^>]*><\/script>/,'<script src="renderer.js"></script>')
fs.copyFileSync(path.join(desktop,'public/icon.png'),path.join(output,'icon.png'));fs.writeFileSync(path.join(output,'index.html'),html)
let win;const errors=[],checks=[],themes=[],js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let i=0;i<250;i++){if(await js(code))return;await pause(20)}throw Error('Timeout: '+code)}
const click=selector=>js(`document.querySelector(${JSON.stringify(selector)}).click()`)
const badge=kind=>js(`document.querySelector('[data-memory-notification="${kind}"]')?.textContent||null`)
const open=async()=>{await click('[data-open-memories]');await wait(`!!document.querySelector('[data-memory-tab="proposals"]:not(:disabled)')`)}
const close=async()=>{await click('.nova-memories-dialog .memories-close');await wait(`!document.querySelector('.nova-memories-dialog')`);await pause(250)}
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1280,height:900,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`document.querySelector('[data-memory-notification="window"]')?.textContent==='2'`)
 const reads=await js(`window.__calls.filter(call=>call[0]==='memory_proposals').length`);await pause(700)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='memory_proposals').length`),reads,'Inspection receipts must not start a notification read loop')
 await open();await wait(`document.querySelector('[data-memory-notification="tab"]')?.textContent==='2'`)
 assert.equal(await badge('window'),null);assert.equal(await js(`document.querySelector('[data-memory-tab="saved"]').getAttribute('aria-selected')`),'true')
 checks.push('Existing pending proposals notify on the rail before the window is opened; the tab badge is visible from Saved')
 fs.writeFileSync(path.join(output,'pending-tab-es.png'),(await win.webContents.capturePage()).toPNG())
 await close();assert.equal(await badge('window'),null);await open();assert.equal(await badge('tab'),'2')
 await click('[data-memory-tab="proposals"]');await wait(`document.querySelectorAll('[data-memory-proposal]').length===2&&!document.querySelector('[data-memory-notification="tab"]')`)
 assert.equal(await js(`window.__calls.some(call=>['memory_confirm','memory_reject','memory_delete'].includes(call[0]))`),false)
 await click('[data-memory-tab="saved"]');assert.equal(await badge('tab'),null);await close();await open();assert.equal(await badge('tab'),null);await close()
 checks.push('Opening the window acknowledges only the rail; viewing the proposals tab acknowledges the tab without resolving proposals')
 await win.reload();await wait(`!!document.querySelector('[data-open-memories]')&&!document.getElementById('nova-startup')`);await pause(350)
 assert.equal(await badge('window'),null);await open();await pause(100);assert.equal(await badge('tab'),null);await close()
 checks.push('Acknowledgements persist across close, reopen and renderer reload')
 await js(`window.__pending('C:/Synthetic/Alpha',['a','b','c'])`);await wait(`document.querySelector('[data-memory-notification="window"]')?.textContent==='1'`)
 await open();assert.equal(await badge('tab'),'1');await click('[data-memory-tab="proposals"]');await wait(`document.querySelectorAll('[data-memory-proposal]').length===3&&!document.querySelector('[data-memory-notification="tab"]')`);await close()
 await js(`window.__root('C:/Synthetic/Beta')`);await wait(`document.querySelector('[data-memory-notification="window"]')?.textContent==='1'`)
 await open();assert.equal(await badge('tab'),'1');await close();await js(`window.__root('C:/Synthetic/Alpha')`);await pause(350);assert.equal(await badge('window'),null)
 checks.push('New proposal identities notify again; read state and counts stay isolated by project')
 await js(`window.__hold=true;window.__bump()`);await wait(`typeof window.__release==='function'`)
 await js(`window.__root('C:/Synthetic/Beta');window.__release()`);await pause(450);assert.equal(await badge('window'),null)
 await open();assert.equal(await badge('tab'),'1');await close()
 checks.push('A late inspection from a different project cannot overwrite the current project counters')
 await js(`window.__root('C:/Synthetic/Alpha');window.__busy(true);window.__pending('C:/Synthetic/Alpha',['a','b','c','d'])`)
 const before=await js('window.__calls.length');await pause(350);assert.equal(await js('window.__calls.length'),before)
 await js('window.__busy(false)');await wait(`document.querySelector('[data-memory-notification="window"]')?.textContent==='1'`)
 checks.push('Background inspection waits for memory maintenance and resumes after it finishes')
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await pause(30)
  // Preserve the window badge for this comparison by inspecting the rail only.
  const proof=await js(`(()=>{const n=document.querySelector('[data-memory-notification="window"]'),s=getComputedStyle(n);return{locale:document.documentElement.lang,mode:document.documentElement.dataset.novaScheme,theme:document.documentElement.dataset.novaTheme,label:n.parentElement.getAttribute('aria-label'),background:s.backgroundColor,color:s.color,borderRadius:s.borderRadius,overflow:document.documentElement.scrollWidth>innerWidth}})()`)
  assert.match(proof.label,locale==='es'?/propuestas sin revisar/:/unread proposals/);assert.equal(proof.overflow,false);themes.push(proof)
 }
 await js(`window.__locale('es');window.__theme('dark','nova')`);await pause(40)
 fs.writeFileSync(path.join(output,'memory-rail-badge-es.png'),(await win.webContents.capturePage()).toPNG())
 assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',checks,themes,errors,calls:await js('window.__calls')},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,checks,errors,calls:win?await js('window.__calls'):[]},null,2));app.exit(1)}})
