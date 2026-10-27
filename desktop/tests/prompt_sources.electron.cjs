/* Real App/React interaction with owned, deterministic host projections. No personal profile or model. */
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
const desktop=path.resolve(__dirname,'..'),output=path.resolve(process.argv[2]),esbuild=require(path.join(desktop,'node_modules/esbuild'))
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
if(process.argv.includes('--mascot')){app.commandLine.appendSwitch('use-angle','swiftshader');app.commandLine.appendSwitch('enable-unsafe-swiftshader')}
const entry=String.raw`
import React from 'react';import {createRoot} from 'react-dom/client';import App from './src/App'
import {I18nProvider,useI18n} from './src/i18n';import {AppearanceProvider,useAppearance} from './src/appearance';import {ShortcutsProvider} from './src/keyboard_shortcuts'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance';import {defaultShortcuts} from './shared/keyboard_shortcuts.cjs'
import {installStartupScreen} from './shared/startup_screen'
import './src/styles.css';import './src/themes.css';import './src/window_surfaces.css'
const A='C:/Synthetic/Alpha',B='C:/Synthetic/Beta';let observers=[],projectObservers=[],serial=0
const savedAppearance=JSON.parse(localStorage.getItem('__fixture_appearance')||'null')||defaultAppearance
let prefs={schemaVersion:1,locale:'es',language:'es',showFiles:true,transitionsEnabled:false,shortcuts:defaultShortcuts(),...savedAppearance}
let files=[{id:'file',name:'Manual de instalación con nombre muy largo para probar el truncado.txt',kind:'file',projectPath:A},{id:'url',name:'Página de referencia.html',kind:'url',url:'https://example.com/docs',projectPath:A},{id:'failed',name:'Sin contenido.pdf',kind:'file',projectPath:A}].map(file=>({...file,bytes:128,modifiedAt:'2026-10-25T12:00:00Z',state:file.id==='failed'?'FAILED':'READY',downloadable:true}))
const projectState=()=>({schemaVersion:1,defaultPath:A,activePath:view.workspace,busy:false,folders:[{path:A,name:'Alpha',isDefault:true},{path:B,name:'Beta',isDefault:false}]})
let view={sessionId:'session',sequence:0,stateRevision:1,status:{ready:true,connected:true,provider:'ollama',model:'local:7b',tools:[]},
 readiness:{ready:true,observedAt:'2026-10-25T12:00:00Z',installedModels:[{name:'local:7b',kind:'llm'}]},modelPreferenceError:null,messages:[],activeTurnId:null,activeGenerationId:null,toolActivities:[],approvals:[],inputs:[],workspace:A,conversation:{hasConversation:true,historyVisible:false,unreadCount:0},rag:{enabled:false,availability:'DISABLED'},ragProgress:'',error:null,gap:false,recovering:false,fileRevision:0,
 memory:{lexicalRecall:true,maintenanceBusy:false},knowledge:{hostAcquisition:true,attachmentRefs:[]},knowledgeOperations:[]}
window.__calls=[];window.__sends=[]
function publish(){view={...view,stateRevision:view.stateRevision+1,knowledge:{...view.knowledge,attachmentRefs:files.filter(file=>file.projectPath===view.workspace).map(file=>({schemaVersion:1,attachmentId:'a-'+file.id,sourceId:file.id,revisionId:file.state==='READY'?'r-'+file.id:null,displayName:file.name,state:file.state}))}};for(const observe of observers)observe(structuredClone(view));for(const observe of projectObservers)observe(projectState())}
function add(names,root=view.workspace){const rows=names.map(name=>({id:'import-'+(++serial),name,kind:'file',projectPath:root,bytes:128,modifiedAt:'2026-10-25T12:00:00Z',state:'READY',downloadable:true}));files.push(...rows);publish();return rows.map(row=>row.id)}
const api={initialDesktopLocale:'es',initialDesktopAppearance:savedAppearance,initialDesktopGeneral:prefs,initialDesktopShortcuts:defaultShortcuts(),
 getDesktopPreferences:async()=>prefs,setDesktopLocale:async locale=>({success:true,preferences:prefs={...prefs,locale,language:locale}}),
 setDesktopGeneral:async next=>window.__rejectGeneral?{success:false,error:{code:'DESKTOP_PREFERENCES_SAVE_FAILED'}}:{success:true,preferences:prefs={...prefs,...next}},
 setDesktopShortcuts:async next=>({success:true,preferences:prefs={...prefs,shortcuts:{...next}}}),
 setDesktopAppearance:async next=>{if(window.__rejectAppearance)return{success:false,error:{code:'DESKTOP_PREFERENCES_SAVE_FAILED'}};localStorage.setItem('__fixture_appearance',JSON.stringify(next));return{success:true,preferences:prefs={...prefs,...next}}},
 getDesktopFonts:async()=>({success:true,fonts:['Segoe UI','Consolas']}),
 getModelVisibility:async()=>({hiddenModels:[]}),getAppVersion:async()=> '0.12.6',getProjects:async()=>projectState(),
 onSessionView:callback=>{observers.push(callback);setTimeout(publish,0);return()=>{observers=observers.filter(item=>item!==callback)}},
 onProjectsChanged:callback=>{projectObservers.push(callback);return()=>{projectObservers=projectObservers.filter(item=>item!==callback)}},
 setHistoryVisible:async()=>({success:true}),signalReady:()=>publish(),
 listDir:async root=>({success:true,root:view.workspace,path:root,entries:[{name:'carpeta',isDirectory:true,isSymlink:false},{name:'archivo.txt',isDirectory:false,isSymlink:false}],truncated:false,nextOffset:null}),
 readFile:async path=>({success:true,root:view.workspace,path,content:'Texto del archivo del proyecto.'}),
 sourcesList:async()=>({success:true,data:{files:files.filter(file=>file.projectPath===view.workspace),projects:projectState().folders}}),
 sourcePreview:async id=>({success:true,data:{sourceId:id,root:view.workspace,name:'Source',content:'Texto de la copia guardada.',reason:null}}),
 sourcesPick:async()=>{window.__calls.push(['pick']);if(window.__holdPick)await new Promise(resolve=>window.__releasePick=resolve);if(window.__pickCancel)return{completed:false,canceled:true,imported:0};return{completed:true,imported:1,sourceIds:add(['Archivo elegido.txt'])}},
 sourcesDrop:async dropped=>{const root=view.workspace;window.__calls.push(['drop',dropped.map(file=>file.name)]);if(window.__holdImport)await new Promise(resolve=>window.__releaseImport=resolve);const ids=add(dropped.map(file=>file.name).slice(0,window.__partial?1:undefined),root);return{completed:!window.__partial,imported:ids.length,sourceIds:ids,...(window.__partial?{error:{code:'SOURCE_TOO_LARGE'}}:{})}},
 applicationCommand:async(kind,payload)=>{if(kind==='SubmitUserInput'){window.__sends.push(payload);return{accepted:!window.__rejectSend}}return{accepted:true}},
 memoryCommand:async()=>({completed:true,data:{records:[{memoryId:'memory',revision:1,kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE',status:'ACTIVE',canonicalText:'El proyecto utiliza una base de datos local.',sensitivityClass:'NORMAL'}]}}),
 projectAction:async(action,path)=>{view={...view,workspace:path};publish();return{success:true,state:projectState()}},
 sendToPython:()=>{},refreshReadiness:async()=>{},
}
window.api=new Proxy(api,{get:(target,key)=>target[key]||(String(key).startsWith('on')?()=>()=>{}:async()=>({success:true}))})
window.__root=root=>{view={...view,workspace:root};publish()};window.__withdraw=id=>{files=files.filter(file=>file.id!==id);publish()}
window.__sourceContext=()=>{view={...view,messages:[{id:'question',role:'user',content:'¿Cuál es el objetivo de las fuentes seleccionadas?',sourceContext:[
 {sourceId:'one',revisionId:'r1',displayName:'especificación-GUI.txt',status:'complete'},
 {sourceId:'two',revisionId:'r2',displayName:'Manual extenso.pdf',status:'partial',admittedChunks:2},
 {sourceId:'three',revisionId:'r3',displayName:'Fuente retirada.txt',status:'unavailable',errorCode:'STALE_SOURCE'}]},
 {id:'answer',role:'assistant',content:'El documento explica el propósito de la interfaz de Nova. [K1]',knowledgeCitations:{schemaVersion:1,turnId:'fixture',structuralOnly:true,valid:[
 {citationId:'K1',sourceId:'one',revisionId:'private-revision',displayLabel:'especificación-GUI.txt',originDisplay:'host-selected-local',locator:{kind:'TEXT_LINES',coordinates:{lineStart:1,lineEnd:1}}},
 {citationId:'K2',sourceId:'two',revisionId:'private-revision-two',displayLabel:'Manual extenso.pdf',originDisplay:'host-selected-local',locator:{kind:'PDF_PAGE',coordinates:{page:3}}}],invalid:[]}}]};publish()}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark')
function Root(){const {setLocale}=useI18n(),{appearance,saveAppearance}=useAppearance();window.__locale=setLocale;window.__appearance=()=>appearance;window.__saveAppearance=patch=>saveAppearance({...appearance,...patch});return <App/>}
installStartupScreen(document,'es',defaultAppearance,()=>true,false,true)
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><ShortcutsProvider><AppearanceProvider><Root/></AppearanceProvider></ShortcutsProvider></I18nProvider></React.StrictMode>)
`
const devServerMode=process.argv.includes('--vite')
if(!devServerMode)esbuild.buildSync({stdin:{contents:entry,sourcefile:'prompt-sources-fixture.tsx',resolveDir:desktop,loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
const productionHtml=fs.readFileSync(path.join(desktop,'index.html'),'utf8'),entryScript=/<script\b[^>]*src="\/src\/main\.tsx"[^>]*><\/script>/
assert.ok(entryScript.test(productionHtml),'Use the actual application document, including its critical startup CSS')
const fixtureHtml=devServerMode?productionHtml:productionHtml.replace('</head>','<link rel="stylesheet" href="renderer.css"></head>')
fs.copyFileSync(path.join(desktop,'public/icon.png'),path.join(output,'icon.png'))
fs.writeFileSync(path.join(output,'startup-only.html'),fixtureHtml.replace(entryScript,''))
const devEntry='/@fs/'+path.join(output,'renderer.tsx').replace(/\\/g,'/')
fs.writeFileSync(path.join(output,'index.html'),fixtureHtml.replace(entryScript,devServerMode?`<script type="module" src="${devEntry}"></script>`:'<script src="renderer.js"></script>'))
if(devServerMode)fs.writeFileSync(path.join(output,'renderer.tsx'),entry.replace(/(['"])\.\/(src|shared)\//g,'$1/$2/').replace("'/shared/keyboard_shortcuts.cjs'","'@nova/keyboard-shortcuts'"))
let devServer
let win;const errors=[],checks=[],pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let n=0;n<180;n++){if(await js(code))return;await pause(25)}throw Error('Timeout '+code)}
const click=selector=>js(`(()=>{const node=document.querySelector(${JSON.stringify(selector)});if(!node)throw Error('Missing control: '+${JSON.stringify(selector)});node.click()})()`)
async function nativeKey(keyCode,modifiers=[]){win.webContents.sendInputEvent({type:'keyDown',keyCode,modifiers});win.webContents.sendInputEvent({type:'keyUp',keyCode,modifiers});await pause(45)}
const tab=label=>js(`Array.from(document.querySelectorAll('.project-content-tabs button')).find(button=>button.textContent===${JSON.stringify(label)}).click()`)
const rail=icon=>js(`document.querySelector('.nova-rail [data-icon="${icon}"]').closest('button').click()`)
const count=()=>js(`document.querySelectorAll('.nova-prompt-source').length`)
async function drop(names){
 const directory=path.join(output,'native-drops');fs.mkdirSync(directory,{recursive:true})
 const files=names.map(name=>{const file=path.join(directory,path.basename(name));fs.writeFileSync(file,'Owned native drag fixture');return file})
 const point=await js(`(()=>{const b=document.querySelector('.chat-pane').getBoundingClientRect();return{x:b.left+b.width/2,y:b.top+120}})()`)
 const data={items:[],files,dragOperationsMask:1}
 await win.webContents.debugger.sendCommand('Input.dispatchDragEvent',{type:'dragEnter',...point,data});await wait(`!!document.querySelector('[data-source-drag]')`)
 if(!fs.existsSync(path.join(output,'drop-overlay-es.png'))){await pause(60);fs.writeFileSync(path.join(output,'drop-overlay-es.png'),(await win.webContents.capturePage()).toPNG())}
 await win.webContents.debugger.sendCommand('Input.dispatchDragEvent',{type:'dragOver',...point,data});await pause(40)
 assert.equal(await js(`window.__lastDragEffect`),'copy')
 await win.webContents.debugger.sendCommand('Input.dispatchDragEvent',{type:'drop',...point,data})
}
const mascotThemes=[]
async function checkMascot(){
  if(!await js(`!!document.querySelector('.nova-home-scene')`))await click('.nova-history-button')
  assert.equal(await js(`window.__appearance().mascotAppearance`),'2d')
  assert.equal(await js(`!!document.querySelector('.nova-home-scene .nova-orbit')`),true)
  const openAppearance=async()=>{await rail('settings');await wait(`!!document.querySelector('[data-settings-section="appearance"]')`);await click('[data-settings-section="appearance"]');await wait(`!!document.querySelector('[data-settings-select="mascotAppearance"]')`);await js(`document.querySelector('[data-settings-select="mascotAppearance"]').scrollIntoView({block:'center'})`);await pause(30)}
  const chooseMascot=async value=>{await wait(`!document.querySelector('[data-settings-select="mascotAppearance"]').disabled`);await click('[data-settings-select="mascotAppearance"]');await wait(`!!document.querySelector('[role="option"][data-value="${value}"]')`);await click('[role="option"][data-value="'+value+'"]');await pause(40)}
  const scrollPreview=()=>js(`(()=>{const content=document.querySelector('.nova-settings-content');content.style.scrollBehavior='auto';content.scrollTop=content.scrollHeight})()`)
  const preview='.nova-mascot-preview .nova-mascot-3d-host'
  await openAppearance()
  assert.equal(await js(`document.querySelector('[data-settings-select="mascotAppearance"]').textContent`),'Nova 2D')
  assert.equal(await js(`!!document.querySelector('.nova-mascot-preview .nova-orbit')`),true)
  await chooseMascot('3d');await scrollPreview()
  await wait(`document.querySelector('.nova-mascot-preview [data-mascot-renderer="ready"]')&&document.querySelector('${preview} canvas')`)
  assert.equal(await js(`window.__appearance().mascotAppearance`),'3d')
  await pause(150)
  assert.equal(await js(`document.querySelector('${preview}').dataset.animating`),'true')
  await js(`window.__rejectAppearance=true`);await chooseMascot('2d')
  assert.equal(await js(`document.querySelector('[data-settings-select="mascotAppearance"]').textContent`),'Nova 3D')
  assert.equal(await js(`!!document.querySelector('.nova-appearance-settings [role="alert"]')`),true)
  await js(`window.__rejectAppearance=false`)
  await js(`document.querySelector('[data-appearance="mascotMotion"]').scrollIntoView({block:'center'})`)
  await click('[data-appearance="mascotMotion"]');await scrollPreview();await pause(120)
  const frozen=await js(`document.querySelector('${preview}').dataset.renderFrames`);await pause(220)
  assert.equal(await js(`document.querySelector('${preview}').dataset.renderFrames`),frozen)
  assert.equal(await js(`document.querySelector('${preview}').dataset.animating`),'false')
  for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
   await js(`window.__locale('${locale}')`);assert.equal(await js(`window.__saveAppearance({colorScheme:'${mode}',lightTheme:'${theme}',darkTheme:'${theme}'})`),true)
   await wait(`!document.querySelector('[data-settings-select="mascotAppearance"]').disabled&&document.documentElement.dataset.novaScheme==='${mode}'&&document.documentElement.dataset.novaTheme==='${theme}'`)
   await scrollPreview();await pause(80)
   const proof=await js(`(()=>{const n=document.querySelector('${preview}'),c=n.querySelector('canvas');return{locale:document.documentElement.lang,mode:document.documentElement.dataset.novaScheme,theme:document.documentElement.dataset.novaTheme,title:document.querySelector('[data-appearance-row="mascotAppearance"] .nova-setting-label').textContent,selected:document.querySelector('[data-settings-select="mascotAppearance"]').textContent,color:getComputedStyle(n).color,width:c.width,height:c.height,overflow:document.documentElement.scrollWidth>innerWidth}})()`)
   assert.equal(proof.title,locale==='es'?'Apariencia de mascota':'Mascot appearance');assert.equal(proof.selected,'Nova 3D');assert.ok(proof.width>0&&proof.height>0);assert.equal(proof.overflow,false);mascotThemes.push(proof)
   if(locale==='es'&&theme==='nova')fs.writeFileSync(path.join(output,'mascot-preview-3d-'+mode+'.png'),(await win.webContents.capturePage()).toPNG())
  }
  await js(`window.__locale('es');window.__saveAppearance({colorScheme:'dark',darkTheme:'nova',mascotMotion:true})`);await wait(`!document.querySelector('[data-settings-select="mascotAppearance"]').disabled&&window.__appearance().mascotMotion`);await scrollPreview();await pause(100)
  await win.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]})
  await wait(`window.matchMedia('(prefers-reduced-motion: reduce)').matches&&document.querySelector('${preview}').dataset.animating==='false'`)
  assert.equal(await js(`document.querySelector('${preview}').dataset.animating`),'false')
  await win.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});await wait(`document.querySelector('${preview}').dataset.animating==='true'`)
  assert.equal(await js(`document.querySelector('${preview}').dataset.animating`),'true')
  await js(`document.querySelector('${preview} canvas').dispatchEvent(new Event('webglcontextlost',{cancelable:true}))`)
  await wait(`!!document.querySelector('.nova-mascot-preview [data-mascot-renderer="fallback"] .nova-orbit')`)
  assert.match(await js(`document.querySelector('.nova-mascot-fallback').textContent`),/No se pudo mostrar Nova 3D/)
  await chooseMascot('2d');await chooseMascot('3d');await scrollPreview();await wait(`!!document.querySelector('.nova-mascot-preview [data-mascot-renderer="ready"]')`)
  await click('.nova-settings-close');await wait(`!document.querySelector('.nova-settings-dialog')`)
  await wait(`!!document.querySelector('.nova-home-scene [data-mascot-renderer="ready"]')`)
  assert.equal(await js(`document.querySelectorAll('.nova-mascot-3d-host canvas').length`),1,'Closing Settings releases its preview canvas')
  await pause(100);assert.equal(await js(`document.querySelector('.nova-home-scene .nova-mascot-3d-host').dataset.animating`),'true')
  fs.writeFileSync(path.join(output,'mascot-home-3d.png'),(await win.webContents.capturePage()).toPNG())
  if(devServerMode)await win.reload();else await win.loadFile(path.join(output,'index.html'))
  await wait(`!document.getElementById('nova-startup')&&!!document.querySelector('.nova-home-scene [data-mascot-renderer="ready"]')`)
  assert.equal(await js(`window.__appearance().mascotAppearance`),'3d')
  await openAppearance();await scrollPreview();await wait(`!!document.querySelector('.nova-mascot-preview [data-mascot-renderer="ready"]')`)
  await click('.nova-appearance-settings .nova-settings-reset');await pause(90);await scrollPreview()
  assert.equal(await js(`window.__appearance().mascotAppearance`),'2d')
  assert.equal(await js(`!!document.querySelector('.nova-mascot-preview .nova-orbit')`),true)
  assert.equal(await js(`document.querySelectorAll('.nova-mascot-3d-host canvas').length`),0)
  fs.writeFileSync(path.join(output,'mascot-preview-2d.png'),(await win.webContents.capturePage()).toPNG())
  win.setSize(700,850);await pause(100);assert.equal(await js(`document.documentElement.scrollWidth>innerWidth`),false)
  checks.push('Nova 2D remains default; the confirmed 3D choice updates preview and home, survives reload, respects movement and system reduced motion, follows every palette, releases canvases and safely falls back after context loss; Reset restores 2D')
}
app.whenReady().then(async()=>{try{
 if(devServerMode){
  const {createServer}=await import(require('node:url').pathToFileURL(path.join(desktop,'node_modules/vite/dist/node/index.js')).href)
  const {shortcutDependencies}=require('../dev/shortcut_dependencies.cjs')
  devServer=await createServer({configFile:false,root:desktop,cacheDir:path.join(output,'vite-cache'),logLevel:'error',optimizeDeps:{include:['three']},plugins:[shortcutDependencies(path.join(desktop,'shared/keyboard_shortcuts.cjs'))],server:{host:'127.0.0.1',port:0,fs:{allow:[desktop,output]}}})
  await devServer.listen()
 }
 const loadFixture=filename=>devServerMode?win.loadURL('http://127.0.0.1:'+devServer.httpServer.address().port+'/@fs/'+path.join(output,filename).replace(/\\/g,'/')):win.loadFile(path.join(output,filename))
 win=new BrowserWindow({width:1280,height:850,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message)})
 win.webContents.debugger.attach('1.3')
 await loadFixture('startup-only.html')
 assert.equal(await js(`getComputedStyle(document.getElementById('root')).visibility`),'hidden')
 assert.equal(await js(`document.getElementById('root').inert&&document.getElementById('root').getAttribute('aria-hidden')==='true'`),true)
 assert.equal(await js(`document.getElementById('nova-window-menu').disabled`),true)
 checks.push('The actual application HTML keeps unrevealed startup content hidden and non-interactive')
 await loadFixture('index.html');await wait(`!!document.querySelector('.nova-attach-button:not(:disabled)')&&!document.getElementById('nova-startup')`)
 assert.equal(await js(`getComputedStyle(document.getElementById('root')).visibility`),'visible')
 if(process.argv.includes('--mascot-only')){await checkMascot();assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',developmentServer:devServerMode,checks,mascotThemes},null,2));await devServer?.close();app.exit(0);return}
 await js(`document.addEventListener('dragover',event=>{window.__lastDragEffect=event.dataTransfer.dropEffect})`)
 await rail('folder');await wait(`!!document.querySelector('.project-content-tabs')`);await tab('Fuentes');await wait(`document.querySelectorAll('.project-source-row').length===3`)
 assert.equal(await js(`document.querySelectorAll('.project-source-row input:disabled').length`),1)
 await click('.project-source-row input');await wait(`document.querySelectorAll('.nova-prompt-source').length===1`)
 await js(`document.querySelectorAll('.project-source-row input')[1].click()`);await wait(`document.querySelectorAll('.nova-prompt-source').length===2`)
 assert.equal(await js(`document.querySelector('.nova-prompt-source[data-source-id=url] [data-icon=globe]')!==null`),true)
 await rail('search');await wait(`!!document.querySelector('.nova-sources-dialog .sources-table tbody input')`)
 assert.equal(await js(`getComputedStyle(document.getElementById('root')).visibility`),'visible','Opening Sources must block background input while keeping the application painted')
 assert.equal(await js(`document.querySelectorAll('.sources-table tbody input:checked').length`),0)
 await click('.sources-table tbody input');assert.equal(await count(),2)
 await click('.nova-sources-dialog .memories-close');await wait(`!document.querySelector('[role=dialog]')`)
 await rail('search');await wait(`!!document.querySelector('.sources-table tbody input')`)
 assert.equal(await js(`document.querySelectorAll('.sources-table tbody input:checked').length`),0)
 await click('.nova-sources-dialog .memories-close');await wait(`!document.querySelector('[role=dialog]')`);assert.equal(await count(),2)
 await click('.nova-prompt-source[data-source-id=file] button');await wait(`document.querySelectorAll('.nova-prompt-source').length===1`)
 assert.equal(await js(`document.querySelector('.project-source-row input').checked`),false)
 checks.push('Management selection clears on close and never changes pending message selection; × unchecks the sidebar')
 await js(`(()=>{const input=document.querySelector('.nova-input');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'Según la fuente, explica los requisitos de instalación.');input.dispatchEvent(new Event('input',{bubbles:true}));window.__rejectSend=true})()`)
 await wait(`!document.querySelector('.nova-send-button').disabled`);await click('.nova-send-button');await wait(`window.__sends.length===1&&!document.querySelector('.nova-send-button').disabled`);assert.equal(await count(),1)
 await js(`window.__rejectSend=false`);await click('.nova-send-button');await wait(`window.__sends.length===2&&document.querySelectorAll('.nova-prompt-source').length===0`)
 assert.deepEqual(await js(`window.__sends[1].attachmentRefs.map(ref=>ref.sourceId)`),['url']);assert.equal(await js(`document.querySelectorAll('.project-source-row input:checked').length`),0)
 checks.push('Submit sends only current host refs, clears accepted selections and retains rejected selections')
 await rail('search');await wait(`!!document.querySelector('.sources-table')`)
 await js(`Array.from(document.querySelectorAll('.memories-tabs button')).find(button=>button.textContent==='Añadir fuente').click()`)
 await js(`window.__holdPick=true`);await click('.sources-dropzone');await wait(`!!window.__releasePick`)
 await click('.nova-sources-dialog .memories-close');await wait(`!document.querySelector('[role=dialog]')`)
 await js(`window.__holdPick=false;window.__releasePick()`);await wait(`document.querySelectorAll('.nova-prompt-source').length===1&&document.querySelectorAll('.project-source-row input:checked').length===1&&!document.querySelector('.nova-attach-button').disabled`)
 await click('.nova-prompt-source button');await wait(`document.querySelectorAll('.nova-prompt-source').length===0`)
 await rail('folder');await wait(`!document.querySelector('.project-content-panel')`)
 await click('.nova-attach-button');await wait(`document.querySelectorAll('.nova-prompt-source').length===1&&document.querySelectorAll('.project-source-row input:checked').length===1&&!document.querySelector('.nova-attach-button').disabled`)
 await js(`window.__pickCancel=true`);await click('.nova-attach-button');await pause(80);assert.equal(await count(),1);await js(`window.__pickCancel=false`)
 await drop(['Arrastrado uno.txt','Arrastrado dos.txt']);await wait(`document.querySelectorAll('.nova-prompt-source').length===3&&!document.querySelector('.nova-attach-button').disabled`)
 assert.equal(await js(`document.querySelectorAll('.project-source-row input:checked').length`),3)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='drop').length`),1)
 assert.equal(await js(`document.querySelector('[data-source-drag]')===null`),true)
 await click('.nova-history-button');await wait(`!!document.querySelector('.nova-conversation')`)
 await drop(['Desde chat.txt']);await wait(`document.querySelectorAll('.nova-prompt-source').length===4`)
 fs.writeFileSync(path.join(output,'selected-sources-es.png'),(await win.webContents.capturePage()).toPNG())
 checks.push('Picker and file drops in both simple/chat views import once, open Sources and automatically check confirmed copies')
 await js(`window.__partial=true`);await drop(['Importación parcial.txt','No importado.txt']);await wait(`document.querySelectorAll('.nova-prompt-source').length===5&&!!document.querySelector('.nova-source-import-feedback[data-error]')`)
 assert.equal(await js(`document.querySelector('.nova-prompt-sources').textContent.includes('No importado.txt')`),false);await js(`window.__partial=false`)
 const geometry={}
 for(const [label,selector]of [['Archivos','.explorer-node.file'],['Fuentes','.project-source-row .project-content-item'],['Recuerdos','.project-content-item']]){
  await tab(label);await wait(`!!document.querySelector(${JSON.stringify(selector)})`)
  geometry[label]=await js(`(()=>{const row=document.querySelector(${JSON.stringify(selector)}),style=getComputedStyle(row);return{height:row.getBoundingClientRect().height,radius:style.borderRadius,margin:style.marginBottom,font:style.fontSize}})()`)
 }
 assert.equal(geometry.Archivos.radius,geometry.Fuentes.radius);assert.equal(geometry.Archivos.radius,geometry.Recuerdos.radius)
 assert.equal(geometry.Archivos.height,geometry.Fuentes.height);assert.equal(geometry.Archivos.height,geometry.Recuerdos.height)
 await tab('Fuentes');await wait(`!!document.querySelector('.project-source-row')`)
 const themes=[]
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await pause(20)
  const report=await js(`(()=>{const row=document.querySelector('.nova-prompt-source'),style=getComputedStyle(row);return{locale:document.documentElement.lang,mode,theme,color:style.color,background:style.backgroundColor,remove:row.querySelector('button').getAttribute('aria-label'),overflow:document.documentElement.scrollWidth>innerWidth}})()`.replace('mode,theme,',`mode:'${mode}',theme:'${theme}',`))
  assert.equal(report.overflow,false);assert.ok(report.remove.startsWith(locale==='es'?'Quitar fuente':'Remove source'));themes.push(report)
 }
 checks.push('Files, sources and memories share row geometry; selections and controls render in all eight themes and both languages')
 await js(`window.__locale('es');window.__theme('dark','nova')`);await pause(60)
 await js(`window.__withdraw(document.querySelector('.nova-prompt-source').dataset.sourceId)`);await wait(`document.querySelectorAll('.nova-prompt-source').length===4`)
 await js(`window.__holdImport=true`);await drop(['Respuesta tardía.txt']);await wait(`!!window.__releaseImport`)
 assert.equal(await js(`document.querySelector('.nova-send-button').disabled`),true)
 await js(`window.__root('C:/Synthetic/Beta');window.__releaseImport()`);await pause(200);assert.equal(await count(),0)
 assert.equal(await js(`document.querySelector('[data-source-drag]')===null`),true)
 checks.push('Deleted sources and project changes revoke selection; a late import cannot attach files to the new project')
 await js(`window.__sourceContext()`);await wait(`!!document.querySelector('.nova-source-context')`)
 assert.equal(await js(`document.querySelector('.nova-source-context').tagName`),'DIV')
 assert.equal(await js(`!!document.querySelector('.nova-source-context>summary')`),false)
 await wait(`document.querySelectorAll('.nova-source-context li').length===3`)
 await click('.nova-source-references>summary')
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await pause(25)
  const report=await js(`(()=>{const note=document.querySelector('.nova-source-context'),box=note.getBoundingClientRect();return{text:note.textContent,overflow:document.documentElement.scrollWidth>innerWidth,width:box.width}})()`)
  assert.ok(report.text.includes(locale==='es'?'Texto preparado incluido completo':'Prepared text included in full'))
  assert.ok(report.text.includes(locale==='es'?'Fragmentos incluidos':'Excerpts included'))
  assert.equal(report.overflow,false);assert.ok(report.width>0)
  const refs=await js(`document.querySelector('.nova-source-references').textContent`)
  assert.ok(refs.includes(locale==='es'?'Línea 1':'Line 1'));assert.ok(refs.includes(locale==='es'?'Página 3':'Page 3'))
  assert.ok(!/private-revision|lineStart|schemaVersion/.test(refs))
 }
 await js(`window.__locale('es');window.__theme('dark','nova')`);await pause(80)
 fs.writeFileSync(path.join(output,'source-context-status-es.png'),(await win.webContents.capturePage()).toPNG())
 checks.push('Actual source context reports show complete, partial and unavailable input in both languages and all themes')
 const sourceContextToggle='[data-general=collapsibleSourceContext]'
 await rail('settings');await wait(`!!document.querySelector('${sourceContextToggle}:not(:disabled)')`)
 assert.equal(await js(`document.querySelector('${sourceContextToggle}').checked`),false)
 fs.writeFileSync(path.join(output,'general-source-context-es.png'),(await win.webContents.capturePage()).toPNG())
 await click(sourceContextToggle);await wait(`document.querySelector('${sourceContextToggle}').checked&&!document.querySelector('${sourceContextToggle}').disabled`)
 await click('.nova-settings-close');await wait(`!document.querySelector('.nova-settings-dialog')`)
 assert.equal(await js(`document.querySelector('.nova-source-context').tagName`),'DETAILS')
 assert.equal(await js(`document.querySelector('.nova-source-context').open`),false)
 const disclosureGeometry=[]
 for(const width of [1280,760,540]){
  win.setSize(width,850);await pause(100)
  const before=await js(`(()=>{const details=document.querySelector('.nova-source-context'),heading=details.querySelector(':scope>summary'),b=heading.getBoundingClientRect(),d=details.getBoundingClientRect();details.open=false;return{left:b.left,width:b.width,right:b.right,containerWidth:d.width}})()`)
  await click('.nova-source-context>summary');await wait(`document.querySelector('.nova-source-context').open`)
  const after=await js(`(()=>{const details=document.querySelector('.nova-source-context'),heading=details.querySelector(':scope>summary'),b=heading.getBoundingClientRect(),d=details.getBoundingClientRect();return{left:b.left,width:b.width,right:b.right,containerWidth:d.width,overflow:details.scrollWidth>details.clientWidth,oneLine:heading.querySelector('span').getBoundingClientRect().height<=parseFloat(getComputedStyle(heading).lineHeight)+1}})()`)
  for(const key of ['left','width','right','containerWidth'])assert.ok(Math.abs(before[key]-after[key])<1,'Disclosure moves on toggle at '+width+'px: '+JSON.stringify({before,after}))
  assert.equal(after.overflow,false);assert.equal(after.oneLine,true)
  disclosureGeometry.push({viewportWidth:width,before,after})
  await click('.nova-source-context>summary');await wait(`!document.querySelector('.nova-source-context').open`)
 }
 win.setSize(1280,850);await pause(100)
 await click('.nova-source-context>summary');await wait(`document.querySelector('.nova-source-context').open`)
 fs.writeFileSync(path.join(output,'source-context-collapsible-es.png'),(await win.webContents.capturePage()).toPNG())
 await rail('settings');await wait(`!!document.querySelector('${sourceContextToggle}:not(:disabled)')`)
 await js(`window.__rejectGeneral=true`);await click(sourceContextToggle);await wait(`!!document.querySelector('.nova-general-settings [role=alert]')`)
 assert.equal(await js(`document.querySelector('${sourceContextToggle}').checked`),true)
 await js(`window.__rejectGeneral=false`);await click(sourceContextToggle);await wait(`!document.querySelector('${sourceContextToggle}').checked&&!document.querySelector('${sourceContextToggle}').disabled`)
 await click(sourceContextToggle);await wait(`document.querySelector('${sourceContextToggle}').checked&&!document.querySelector('${sourceContextToggle}').disabled`)
 await click('.nova-general-settings .nova-settings-reset');await wait(`!document.querySelector('${sourceContextToggle}').checked&&!document.querySelector('${sourceContextToggle}').disabled`)
 await click('.nova-settings-close');await wait(`!document.querySelector('.nova-settings-dialog')`)
 assert.equal(await js(`document.querySelector('.nova-source-context').tagName`),'DIV')
 checks.push('General defaults to inline source cards; confirmed toggle enables a collapsible panel, failed saves retain the display and Reset restores inline cards')
 checks.push('Source disclosure heading keeps its position and width when opened at wide and compact viewport sizes')
 const surfaces=[]
 await js(`document.documentElement.dataset.novaTransitions='false'`)
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`)
  let reference=null
  for(const [name,icon]of [['settings','settings'],['models','brain'],['sources','search'],['memories','memories']]){
   await rail(icon);await wait(`!!document.querySelector('.nova-surface-dialog')`);await pause(35)
   const report=await js(`(()=>{const dialog=document.querySelector('.nova-surface-dialog'),backdrop=dialog.parentElement,s=getComputedStyle(dialog),b=getComputedStyle(backdrop),root=document.getElementById('root');return{background:b.backgroundColor,blur:b.backdropFilter,edge:s.border,shadow:s.boxShadow,radius:s.borderRadius,width:s.width,height:s.height,rootInert:root.inert,rootVisibility:getComputedStyle(root).visibility,appVisibility:getComputedStyle(document.querySelector('.nova-app')).visibility,focusInside:dialog.contains(document.activeElement)}})()`)
   assert.equal(report.background,'rgba(0, 0, 0, 0)');assert.equal(report.blur,'blur(5px)')
   assert.equal(report.rootInert,true);assert.equal(report.focusInside,true)
   assert.equal(report.rootVisibility,'visible');assert.equal(report.appVisibility,'visible')
   assert.notEqual(report.shadow,'none');assert.ok(report.shadow.includes('36px'))
   if(reference)assert.deepEqual(report,reference,name+' surface differs in '+mode+'/'+theme)
   else reference=report
   surfaces.push({locale,mode,theme,name,...report})
   if(locale==='es'&&theme==='nova'){
    fs.writeFileSync(path.join(output,'soft-backdrop-'+mode+'-'+name+'.png'),(await win.webContents.capturePage()).toPNG())
   }
   await click('.nova-surface-header>.nova-dismiss-button');await wait(`!document.querySelector('.nova-surface-dialog')`)
   assert.equal(await js(`document.getElementById('root').inert`),false)
  }
 }
 checks.push('Settings, Models, Sources and Memories share a transparent soft blur, moderate shadow and themed edge in both languages and all themes; focus and background input blocking remain intact')
 await js(`window.__locale('es');window.__theme('dark','nova')`);await pause(40)
 for(const [key,selector]of [['F','.nova-sources-dialog'],['N','.nova-memories-dialog'],['M','.nova-model-dialog']]){
  await nativeKey(key,['control','shift']);await wait(`!!document.querySelector('${selector}')`)
  await click(selector+' .nova-surface-header>.nova-dismiss-button');await wait(`!document.querySelector('${selector}')`)
 }
 assert.match(await js(`document.querySelector('[data-open-sources]').title`),/Ctrl\+Mayús\+F/)
 assert.match(await js(`document.querySelector('[data-open-memories]').title`),/Ctrl\+Mayús\+N/)
 assert.match(await js(`document.querySelector('.nova-rail [data-icon="brain"]').closest('button').title`),/Ctrl\+Mayús\+M/)
 await rail('settings');await click('[data-settings-section="shortcuts"]')
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('[data-shortcut]')).map(n=>n.dataset.shortcut).filter(id=>['sources','memories','models'].includes(id))`),['sources','memories','models'])
 assert.deepEqual(await js(`['sources','memories','models'].map(id=>document.querySelector('[data-shortcut="'+id+'"] .nova-setting-label').textContent)`),['Abrir fuentes','Abrir recuerdos','Abrir modelos'])
 const capture=async(id,key,modifiers)=>{await click('[data-shortcut="'+id+'"] .nova-shortcut-binding');await pause(30);await nativeKey(key,modifiers)}
 await capture('sources','M',['control','shift']);assert.equal(await js(`!!document.querySelector('.nova-model-dialog')`),false)
 assert.match(await js(`document.querySelector('.nova-shortcuts-feedback').textContent`),/ya está asignada/);await nativeKey('ESC')
 await capture('memories','N',['control','alt']);await wait(`document.querySelector('[data-shortcut="memories"] .nova-shortcut-binding').textContent==='Ctrl+Alt+N'`)
 assert.equal(await js(`document.querySelector('[data-open-memories]').title`),'Recuerdos (Ctrl+Alt+N)')
 await js(`window.__locale('en')`);await wait(`document.querySelector('[data-shortcut="sources"] .nova-setting-label').textContent==='Open sources'`)
 assert.deepEqual(await js(`['sources','memories','models'].map(id=>document.querySelector('[data-shortcut="'+id+'"] .nova-setting-label').textContent)`),['Open sources','Open memories','Open models'])
 await js(`window.__locale('es')`);await wait(`document.querySelector('[data-shortcut="sources"] .nova-setting-label').textContent==='Abrir fuentes'`)
 fs.writeFileSync(path.join(output,'shortcuts-windows-es.png'),(await win.webContents.capturePage()).toPNG())
 await click('.nova-settings-close');await wait(`!document.querySelector('.nova-settings-dialog')`)
 await nativeKey('N',['control','shift']);assert.equal(await js(`!!document.querySelector('.nova-memories-dialog')`),false)
 await nativeKey('N',['control','alt']);await wait(`!!document.querySelector('.nova-memories-dialog')`)
 await click('.nova-memories-dialog .memories-close');await wait(`!document.querySelector('.nova-memories-dialog')`)
 await rail('settings');await click('[data-settings-section="shortcuts"]');await click('[data-shortcut="sources"] .nova-shortcut-remove')
 await wait(`!!document.querySelector('[data-shortcut="sources"] .nova-shortcut-unassigned')`)
 assert.equal(await js(`document.querySelector('[data-open-sources]').title`),'Fuentes')
 await click('.nova-settings-close');await wait(`!document.querySelector('.nova-settings-dialog')`)
 await nativeKey('F',['control','shift']);assert.equal(await js(`!!document.querySelector('.nova-sources-dialog')`),false)
 await rail('settings');await click('[data-settings-section="shortcuts"]');await click('.nova-shortcuts-introduction .nova-settings-reset')
 await wait(`document.querySelector('[data-shortcut="sources"] .nova-shortcut-binding').textContent==='Ctrl+Mayús+F'&&document.querySelector('[data-shortcut="memories"] .nova-shortcut-binding').textContent==='Ctrl+Mayús+N'`)
 assert.equal(await js(`document.querySelector('[data-open-sources]').title`),'Fuentes (Ctrl+Mayús+F)')
 assert.equal(await js(`document.querySelector('[data-open-memories]').title`),'Recuerdos (Ctrl+Mayús+N)')
 await click('.nova-settings-close');await wait(`!document.querySelector('.nova-settings-dialog')`)
 await nativeKey('F',['control','shift']);await wait(`!!document.querySelector('.nova-sources-dialog')`)
 await click('.nova-sources-dialog .nova-surface-header>.nova-dismiss-button');await wait(`!document.querySelector('.nova-sources-dialog')`)
 checks.push('Native keyboard shortcuts open Sources, Memories and Models; bilingual Settings rows follow the rail order, preserve conflict detection, support reassignment/removal and Reset restores all defaults')
 if(process.argv.includes('--mascot'))await checkMascot()
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',developmentServer:devServerMode,checks,geometry,themes,disclosureGeometry,surfaces,mascotThemes},null,2));await devServer?.close();app.exit(0)
}catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:String(error.stack),errors,checks},null,2));await devServer?.close();app.exit(1)}})
