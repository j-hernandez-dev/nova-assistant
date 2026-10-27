// Frame-by-frame opening regression under the same StrictMode used by Vite.
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),esbuild=require('esbuild')
const output=path.resolve(process.env.NOVA_MEMORY_OPENING_OUTPUT),desktop=path.resolve(__dirname,'..')
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=`
import React,{useState} from 'react';import {createRoot} from 'react-dom/client'
import {MemoryWindow} from './src/components/MemoryWindow';import {I18nProvider,useI18n} from './src/i18n';import {usePresence} from './src/use_presence'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css';import './src/themes.css';import './src/settings.css';import './src/window_surfaces.css'
const records=Array.from({length:7},(_,i)=>({memoryId:'owned-'+i,revision:1,canonicalText:'Synthetic memory '+i,kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE',status:'ACTIVE',sensitivityClass:'NORMAL'}))
window.__calls=[];window.__pending=false;window.__conflicts=0;window.__errors=0
window.api={initialDesktopLocale:'es',initialDesktopGeneral:{language:'es'},getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es'}),setDesktopLocale:async locale=>({success:true,preferences:{schemaVersion:1,locale}}),memoryCommand:async(name,args)=>{
 window.__calls.push([name,args]);if(name!=='memory_list')return {completed:true,data:{}}
 if(window.__permanent)return {completed:false,error:{code:'PERMISSION_DENIED'}}
 if(window.__pending)return {completed:false,error:{code:'REVISION_CONFLICT'}}
 if(window.__conflicts>0){window.__conflicts--;return {completed:false,error:{code:'REVISION_CONFLICT'}}}
 window.__pending=true;window.__maintenance(true)
 await new Promise(resolve=>setTimeout(resolve,160))
 window.__maintenance(false);window.__pending=false
 return {completed:true,data:{records}}
}}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark');window.__theme('dark','nova');document.documentElement.dataset.novaTransitions='false'
function Harness(){const {setLocale}=useI18n();window.__locale=setLocale;const [open,setOpen]=useState(false),[maintenance,setMaintenance]=useState(false);window.__maintenance=setMaintenance;window.__open=()=>setOpen(true);window.__close=()=>setOpen(false);const present=usePresence(open)
 const view={sessionId:'owned',workspace:'C:/Synthetic/Project',status:{ready:true,connected:true},approvals:[],inputs:[],memory:{lexicalRecall:true,maintenanceBusy:maintenance}}
 return <>{present&&<MemoryWindow view={view} open={open} onClose={()=>setOpen(false)}/>}</>}
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><Harness/></I18nProvider></React.StrictMode>)`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'memory-opening-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{width:100%;height:100%;margin:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win;const errors=[],pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let i=0;i<200;i++){if(await js(code))return;await pause(20)}throw Error('Timeout '+code)}
async function observeOpening(){return js(`(async()=>{const frames=[],started=performance.now();window.__open();while(performance.now()-started<800){await new Promise(requestAnimationFrame);const search=document.querySelector('.memories-search'),dock=document.querySelector('.memories-table-actions');if(search&&dock)frames.push({time:performance.now()-started,searchTop:search.getBoundingClientRect().top,dockTop:dock.getBoundingClientRect().top,alert:!!document.querySelector('.memories-content [role="alert"]'),busyBanner:!!document.querySelector('.memories-content>.memories-notice'),rows:document.querySelectorAll('[data-memory-record]').length})}return frames})()`) }
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1180,height:850,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_event,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`typeof window.__open==='function'`)
 await pause(80);await js(`document.documentElement.dataset.novaTransitions='false'`)
 const first=await observeOpening(),metrics=frames=>({searchShift:Math.max(...frames.map(frame=>frame.searchTop))-Math.min(...frames.map(frame=>frame.searchTop)),dockShift:Math.max(...frames.map(frame=>frame.dockTop))-Math.min(...frames.map(frame=>frame.dockTop)),alerts:frames.filter(frame=>frame.alert).length,busyBanners:frames.filter(frame=>frame.busyBanner).length})
 const firstProof=metrics(first)
 fs.writeFileSync(path.join(output,'first-opening.json'),JSON.stringify({metrics:firstProof,frames:first,calls:await js('window.__calls')},null,2))
 assert.ok(firstProof.searchShift<1,JSON.stringify(firstProof));assert.ok(firstProof.dockShift<1);assert.equal(firstProof.alerts,0);assert.equal(firstProof.busyBanners,0)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='memory_list').length`),1)
 assert.equal(await js(`document.querySelectorAll('[data-memory-record]').length`),7)
 await js(`window.__close()`);await pause(280)
 const second=await observeOpening(),secondProof=metrics(second);assert.ok(secondProof.searchShift<1);assert.equal(secondProof.alerts,0)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='memory_list').length`),2)
 await js(`window.__close();window.__conflicts=1`);await pause(280)
 const conflict=await observeOpening(),conflictProof=metrics(conflict);assert.ok(conflictProof.searchShift<1);assert.equal(conflictProof.alerts,0)
 assert.equal(await js(`document.querySelectorAll('[data-memory-record]').length`),7)
 await js(`window.__close();window.__permanent=true`);await pause(280)
 const beforeDenied=await js(`window.__calls.length`);await observeOpening()
 assert.equal(await js(`window.__calls.length`),beforeDenied+1,'terminal read failures do not create an automatic retry loop')
 assert.equal(await js(`!!document.querySelector('.memories-content [role="alert"]')`),true)
 await js(`window.__close();window.__permanent=false`);await pause(280);await observeOpening()
 const themes=[]
 for(const language of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${language}');window.__theme('${mode}','${theme}')`);await pause(15)
  assert.equal(await js(`document.querySelector('.nova-memories-dialog h1').textContent`),language==='es'?'Recuerdos':'Memories');themes.push({language,mode,theme})
 }
 await js(`window.__locale('es');window.__theme('dark','nova')`)
 fs.writeFileSync(path.join(output,'memories-open-es.png'),(await win.webContents.capturePage()).toPNG())
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',first:firstProof,second:secondProof,revisionConflict:conflictProof,themes},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,errors},null,2));app.exit(1)}})
