/* Isolated interaction test: no provider, project writes or personal profile. */
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
const desktop=path.resolve(__dirname,'..'),output=path.resolve(process.argv[2]||path.join(desktop,'project-pane-qa'))
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const esbuild=require(path.join(desktop,'node_modules/esbuild')),errors=[]
const entry=`
import React,{useState,useRef} from 'react';import {createRoot} from 'react-dom/client'
import {I18nProvider,useI18n} from './src/i18n';import {ProjectPane} from './src/components/ProjectPane'
import {FileExplorer} from './src/components/FileExplorer';import {NovaIcon} from './src/components/NovaIcon';import {usePresence} from './src/use_presence'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css';import './src/themes.css';import './src/window_surfaces.css'
window.api={initialDesktopLocale:'es',getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es'}),setDesktopLocale:async locale=>({success:true,preferences:{schemaVersion:1,locale}}),
 listDir:async path=>({success:true,root:'/owned',path,entries:Array.from({length:35},(_,n)=>({name:'file-'+n+'.txt',isDirectory:false,isSymlink:false})),truncated:false,nextOffset:null})}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark');window.__theme('dark','nova')
const projects={schemaVersion:1,defaultPath:'/owned',activePath:'/owned',busy:false,folders:Array.from({length:12},(_,n)=>({path:n?'/owned-'+n:'/owned',name:n?'Proyecto '+n:'workspace',isDefault:!n}))}
function Harness(){const {t,setLocale}=useI18n(),[open,setOpen]=useState(false),[viewer,setViewer]=useState(false),[files,setFiles]=useState(true),toggle=useRef(null),present=usePresence(open)
 window.__locale=setLocale;window.__viewer=setViewer;window.__files=setFiles
 return <div className="app nova-app"><nav className="nova-rail"><button data-toggle ref={toggle} aria-label={t('projects')} aria-expanded={open} aria-controls="nova-project-pane" className={'nova-nav-button '+(open?'active':'')} onClick={()=>setOpen(v=>!v)}><NovaIcon name="folder" size={28}/></button></nav>
  <div className="nova-workspace"><div className="nova-main">
   {present&&<ProjectPane open={open} onCollapse={()=>setOpen(false)} toggleRef={toggle}><FileExplorer projects={projects} busy={false} showFiles={files} onFileSelect={()=>{}} onProjectAction={()=>{}}/></ProjectPane>}
   <main className="chat-pane"><header className="nova-header">Nova</header><div style={{padding:30}}>Área principal</div></main>
   {viewer&&<aside className="viewer-pane"><div>Vista previa</div></aside>}
  </div></div></div>
}
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><Harness/></I18nProvider></React.StrictMode>)`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'project-pane-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{height:100%;margin:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win;const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let n=0;n<180;n++){if(await js(code))return;await pause(25)}throw Error('Timeout '+code)}
const width=()=>js(`Math.round(document.querySelector('.nova-project-pane')?.getBoundingClientRect().width||0)`)
const maximum=()=>js(`Number(document.querySelector('[role=separator]').getAttribute('aria-valuemax'))`)
async function key(key,modifiers=[]){await js(`document.querySelector('[role=separator]').focus()`);const keyCode=({ArrowLeft:'Left',ArrowRight:'Right'})[key]||key;win.webContents.sendInputEvent({type:'keyDown',keyCode,modifiers});win.webContents.sendInputEvent({type:'keyUp',keyCode,modifiers});await pause(35)}
async function begin(){const box=await js(`(()=>{const b=document.querySelector('.nova-project-resize').getBoundingClientRect();return{x:Math.round(b.left+b.width/2),y:Math.round(b.top+b.height/2)}})()`)
 win.webContents.sendInputEvent({type:'mouseMove',...box});win.webContents.sendInputEvent({type:'mouseDown',button:'left',modifiers:['leftButtonDown'],clickCount:1,...box});await pause(40)
 assert.equal(await js(`document.documentElement.hasAttribute('data-nova-resizing-projects')`),true);return box}
async function move(point){win.webContents.sendInputEvent({type:'mouseMove',modifiers:['leftButtonDown'],...point});await pause(40)}
async function up(point){win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...point});await pause(40)}
async function open(){await js(`document.querySelector('[data-toggle]').click()`);await wait(`!!document.querySelector('[role=separator]')`);await pause(300)}
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1280,height:850,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`!!document.querySelector('[data-toggle]')`)
 await js(`window.__events=[];for(const type of ['pointerdown','pointermove','pointerup','pointercancel','lostpointercapture'])document.addEventListener(type,event=>window.__events.push({type,x:event.clientX,buttons:event.buttons,target:event.target.className,id:event.pointerId}),true)`)
 await js(`localStorage.removeItem('nova.projectPane.width.v1')`);await open();assert.equal(await width(),312)
 let point=await begin();await move({x:point.x+100,y:point.y});await up({x:point.x+100,y:point.y});assert.equal(await width(),412)
 assert.equal(await js(`localStorage.getItem('nova.projectPane.width.v1')`),'412')
 assert.equal(await js(`getComputedStyle(document.querySelector('.nova-project-pane')).animationName`),'none')
 await js(`document.querySelector('.project-options-button').click()`);await wait(`!!document.querySelector('.project-context-menu')`)
 point=await begin();assert.equal(await js(`!!document.querySelector('.project-context-menu')`),false);await up(point)
 point=await begin();await move({x:point.x+1000,y:point.y});await up({x:point.x+1000,y:point.y});assert.equal(await width(),await maximum())
 assert.ok(await width()<=600);assert.ok(await js(`document.querySelector('.chat-pane').getBoundingClientRect().width>=320`))
 await key('Home');assert.equal(await width(),240);await key('ArrowRight',['control']);assert.equal(await width(),240);await key('ArrowRight');assert.equal(await width(),256)
 point=await begin();await move({x:point.x+80,y:point.y});await key('Escape');await up({x:point.x+80,y:point.y});assert.equal(await width(),256)
 assert.equal(await js(`document.documentElement.hasAttribute('data-nova-resizing-projects')`),false)
 point=await begin();await move({x:point.x-100,y:point.y});await up({x:point.x-100,y:point.y});await wait(`!document.querySelector('.nova-project-pane')`)
 assert.equal(await js(`document.querySelector('[data-toggle]').getAttribute('aria-expanded')`),'false')
 assert.equal(await js(`document.activeElement===document.querySelector('[data-toggle]')`),true)
 await open();assert.equal(await width(),256)
 await key('ArrowRight');assert.equal(await width(),272)
 await js(`document.querySelector('[data-toggle]').click()`);await wait(`!document.querySelector('.nova-project-pane')`);await open();assert.equal(await width(),272)
 point=await begin();await move({x:point.x+60,y:point.y});await js(`window.dispatchEvent(new Event('blur'))`);await up({x:point.x+60,y:point.y});assert.equal(await width(),272)
 await key('End');const full=await width();await js(`window.__viewer(true)`);await pause(350)
 assert.ok(await js(`document.querySelector('.chat-pane').getBoundingClientRect().width>=319`));assert.ok(await width()<=full)
 await js(`window.__viewer(false)`);await pause(300);assert.equal(await width(),full)
 const themes=[]
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await pause(30)
  const proof=await js(`(()=>{const p=document.querySelector('.nova-project-pane'),s=p.querySelector('[role=separator]');return{label:s.getAttribute('aria-label'),line:getComputedStyle(s,'::after').backgroundColor,accent:getComputedStyle(document.documentElement).getPropertyValue('--accent'),overflow:p.scrollWidth>p.clientWidth,content:p.querySelector('.explorer').getBoundingClientRect().width,panel:p.getBoundingClientRect().width}})()`)
  assert.equal(proof.label,locale==='es'?'Ajustar ancho del panel de proyectos':'Resize project panel');assert.equal(proof.overflow,false);assert.ok(proof.content<proof.panel);themes.push(proof)
 }
 await js(`window.__locale('es');window.__theme('dark','nova')`);await pause(130)
 fs.writeFileSync(path.join(output,'expanded-es.png'),(await win.webContents.capturePage()).toPNG())
 win.setSize(600,700);await pause(350);assert.ok(await width()<=await maximum())
 win.setSize(1280,850);await pause(350);assert.equal(await width(),full)
 win.setSize(660,700);await pause(350);assert.ok(await width()<=await maximum())
 assert.equal(await js(`getComputedStyle(document.querySelector('.nova-project-pane')).position`),'absolute')
 assert.equal(await js(`document.documentElement.scrollWidth>innerWidth`),false)
 await key('Home');assert.equal(await width(),240);await key('ArrowLeft');await wait(`!document.querySelector('.nova-project-pane')`);await open()
 await js(`document.documentElement.dataset.novaTransitions='false'`);point=await begin();await move({x:point.x+40,y:point.y});await up({x:point.x+40,y:point.y})
 assert.equal(await js(`getComputedStyle(document.querySelector('.nova-project-pane')).animationName`),'none')
 assert.equal(await js(`(()=>{const p=document.querySelector('.project-folder-list'),s=document.querySelector('.nova-project-resize');return p.getBoundingClientRect().right<=s.getBoundingClientRect().left})()`),true)
 await js(`window.__files(false)`);await pause(50)
 assert.ok(await js(`document.querySelector('.project-folder-list').clientHeight>document.querySelector('.nova-project-pane').clientHeight*.65`))
 fs.writeFileSync(path.join(output,'compact-es.png'),(await win.webContents.capturePage()).toPNG())
 await key('Enter');await wait(`!document.querySelector('.nova-project-pane')`);await open()
 const saved=await width();await win.loadFile(path.join(output,'index.html'));await wait(`!!document.querySelector('[data-toggle]')`);await open();assert.equal(await width(),saved)
 const reset=await begin();await up(reset);win.webContents.sendInputEvent({type:'mouseDown',button:'left',modifiers:['leftButtonDown'],clickCount:2,...reset});win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:2,...reset});await pause(60)
 assert.equal(await width(),260);assert.equal(await js(`localStorage.getItem('nova.projectPane.width.v1')`),null)
 assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',themes,savedWidth:saved},null,2));app.exit(0)
}catch(error){const proof=win&&!win.isDestroyed()?await js(`({events:window.__events,style:document.querySelector('.nova-project-pane')?.getAttribute('style'),data:document.querySelector('.nova-project-pane')?.outerHTML.slice(0,600),saved:localStorage.getItem('nova.projectPane.width.v1')})`).catch(()=>null):null;fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:String(error.stack),errors,proof},null,2));app.exit(1)}})
