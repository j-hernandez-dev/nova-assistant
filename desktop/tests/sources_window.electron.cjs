// Hidden source-window verification with an isolated profile and synthetic project data.
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),esbuild=require('esbuild')
const output=path.resolve(process.env.NOVA_SOURCES_UI_OUTPUT),desktop=path.resolve(__dirname,'..')
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=`
import React,{useState} from 'react';import {createRoot} from 'react-dom/client'
import {SourcesWindow} from './src/components/SourcesWindow';import {KnowledgeSettings} from './src/components/KnowledgeSettings'
import {I18nProvider,useI18n} from './src/i18n';import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css';import './src/themes.css';import './src/settings.css';import './src/window_surfaces.css'
let files=Array.from({length:60},(_,i)=>({id:'file-'+i,name:'Reference '+i+'.txt',bytes:1024,modifiedAt:'2026-10-24T12:00:00Z',projectPath:'Alpha',kind:'file',url:null,state:'READY',downloadable:true}))
files.push({id:'url',name:'Public documentation',bytes:2048,modifiedAt:'2026-10-24T13:00:00Z',projectPath:'Alpha',kind:'url',url:'https://example.com/documentation',state:'READY',downloadable:true})
window.__calls=[];window.__cancel=true
window.api={initialDesktopLocale:'es',initialDesktopGeneral:{language:'es'},getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es'}),setDesktopLocale:async locale=>({success:true,preferences:{schemaVersion:1,locale}}),
 sourcesList:async()=>{window.__listRequests=(window.__listRequests||0)+1;if(window.__listing)return {success:false,error:{code:'STORAGE_BUSY'}};window.__listing=true;try{await new Promise(resolve=>setTimeout(resolve,60));if(window.__busyReads>0){window.__busyReads--;return {success:false,error:{code:'STORAGE_BUSY'}}};if(window.__listFailure)return {success:false,error:{code:window.__listFailure}};return {success:true,data:{files:files.filter(file=>file.projectPath==='Alpha'),projects:[{path:'Alpha',name:'Alpha'},{path:'Beta',name:'Beta'}]}}}finally{window.__listing=false}},
 sourcesMove:async(ids,target)=>{window.__calls.push(['move',ids,target]);files=files.map(file=>ids.includes(file.id)?{...file,projectPath:target}:file);return {success:true,data:{}}},
 sourcesDownload:async ids=>{window.__calls.push(['download',ids]);return {success:true,data:{downloaded:ids.length}}},
 sourcesDelete:async ids=>{window.__calls.push(['delete',ids]);if(window.__cancel)return {success:false,canceled:true};files=files.filter(file=>!ids.includes(file.id));return {success:true,data:{}}},
 sourcesPick:async()=>{window.__calls.push(['pick']);files.push({...files[0],id:'picked',name:'New selected file.txt'});return {completed:true,imported:1}},
 sourcesDrop:async dropped=>{window.__calls.push(['drop',dropped.map(file=>file.name)]);return {completed:false,imported:0,error:{code:'SOURCE_NOT_AUTHORIZED'}}},
 knowledgeCommand:async(name,args)=>{window.__calls.push([name,args]);window.__updateOps([{operationId:'url-import',status:'running'}]);setTimeout(()=>{files.push({...files[0],id:'new-url',kind:'url',url:args.url,name:'New URL'});window.__updateOps([{operationId:'url-import',status:'completed',result:{}}])},150);return {accepted:true,createdIds:{operationId:'url-import'}}}
}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark');window.__theme('dark','nova')
function Harness(){const {setLocale}=useI18n();window.__locale=setLocale;const [ops,setOps]=useState([]);window.__updateOps=setOps;const [revision,setRevision]=useState(0);window.__remount=()=>setRevision(value=>value+1)
 const view={sessionId:'synthetic',workspace:'Alpha',status:{ready:true},rag:{enabled:false,availability:'DISABLED'},knowledge:{hostAcquisition:true},knowledgeOperations:ops}
 return <><SourcesWindow key={revision} view={view} onClose={()=>{}}/><div hidden id="knowledge-reference"><KnowledgeSettings view={view}/></div></>}
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><Harness/></I18nProvider></React.StrictMode>)`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'sources-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{width:100%;height:100%;margin:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win;const errors=[],pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=async code=>{try{return await win.webContents.executeJavaScript(code,true)}catch(error){throw Error(code.slice(0,280)+' :: '+error.message)}}
async function wait(code){for(let i=0;i<160;i++){if(await js(code))return;await pause(25)}throw Error('Timeout '+code)}
const setInput=(selector,value)=>js(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}))})()`)
const click=selector=>js(`document.querySelector(${JSON.stringify(selector)}).click()`)
const textClick=text=>js(`Array.from(document.querySelectorAll('button')).find(e=>e.textContent===${JSON.stringify(text)}).click()`)
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1220,height:920,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_event,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`document.querySelectorAll('.sources-table tbody tr').length===61`);await pause(300)
 assert.equal(await js('window.__listRequests'),1,'StrictMode mount shares one inventory request')
 await js(`window.__listFailure='STORAGE_FAILED';window.__remount()`)
 await wait(`document.querySelector('.sources-content [role="alert"]')?.textContent.includes('No se pudieron cargar las fuentes')`)
 assert.equal(await js(`document.querySelector('.sources-content').textContent.includes('No hay fuentes guardadas')`),false)
 assert.equal(await js(`document.querySelector('.sources-summary').textContent.includes('Cantidad de fuentes no disponible')`),true)
 assert.equal(await js(`document.querySelector('.nova-search-refresh').disabled`),false)
 await js(`window.__listFailure=null`);await click('.nova-search-refresh');await wait(`document.querySelectorAll('.sources-table tbody tr').length===61`)
 assert.equal(await js(`document.querySelector('.sources-content [role="alert"]')===null`),true)
 await js(`window.__busyReads=2;window.__remount()`);await wait(`document.querySelectorAll('.sources-table tbody tr').length===61`)
 assert.equal(await js(`document.querySelector('.sources-content [role="alert"]')===null`),true)
 assert.equal(await js(`document.querySelector('.sources-content .nova-data-search [role="combobox"]')===null`),true)
 assert.equal(await js(`document.querySelector('#knowledge-reference').textContent.includes('Capacidad y estado')`),false)
 assert.equal(await js(`document.querySelectorAll('#knowledge-reference [data-knowledge-setting]').length`),4)
 await click('.sources-table tbody input');await wait(`document.querySelector('.sources-actions').dataset.visible==='true'`)
 const dock=await js(`(()=>{const e=document.querySelector('.sources-actions'),d=e.getBoundingClientRect(),t=document.querySelector('.sources-scroll .nova-data-table-wrap').getBoundingClientRect(),b=e.querySelector('.nova-settings-danger').getBoundingClientRect();return{top:d.top,right:Math.abs(t.right-b.right),bottom:d.bottom,dialogBottom:document.querySelector('.nova-sources-dialog').getBoundingClientRect().bottom}})()`)
 assert.ok(dock.right<2,JSON.stringify(dock));assert.ok(dock.bottom<dock.dialogBottom)
 const floating=await require('./floating_controls_assertions.cjs')(win,'.sources-actions','.sources-scroll')
 await textClick('Descargar');await wait(`window.__calls.some(call=>call[0]==='download')`)
 await wait(`!document.querySelector('.sources-actions .nova-settings-danger').disabled`)
 await js(`document.querySelector('.sources-scroll').scrollTop=100000`);await pause(25)
 assert.ok(Math.abs((await js(`document.querySelector('.sources-actions').getBoundingClientRect().top`))-dock.top)<2)
 await textClick('Eliminar');await wait(`!document.querySelector('.sources-actions .nova-settings-danger').disabled`)
 assert.equal(await js(`document.querySelectorAll('.sources-table tbody tr').length`),61)
 await js(`window.__cancel=false`);await textClick('Eliminar');await wait(`document.querySelectorAll('.sources-table tbody tr').length===60`)
 await click('.sources-table tbody input');await click('.sources-actions [role="combobox"]');await wait(`document.querySelector('[role="listbox"]')!==null`)
 await js(`Array.from(document.querySelectorAll('[role="option"]')).find(e=>e.textContent==='Beta').click()`);await wait(`document.querySelectorAll('.sources-table tbody tr').length===59`)
 await setInput('.sources-content input[type=search]','example.com');await click('.sources-content .nova-search-submit');await wait(`document.querySelectorAll('.sources-table tbody tr').length===1`)
 assert.ok((await js(`document.querySelector('.sources-name').textContent`)).includes('https://example.com'))
 await textClick('Añadir fuente');assert.equal(await js(`document.querySelector('.sources-dropzone [data-icon="folder"]')!==null`),true)
 await pause(100)
 fs.writeFileSync(path.join(output,'sources-add-es.png'),(await win.webContents.capturePage()).toPNG())
 await click('.sources-dropzone');await wait(`document.querySelector('.sources-table')!==null&&document.querySelector('.memories-feedback').textContent.includes('Fuentes añadidas')`)
 await wait(`!document.querySelector('.memories-tabs button').disabled`)
 await textClick('Añadir fuente');await wait(`document.querySelector('.sources-url input')!==null`);await setInput('.sources-url input','https://example.com/new');await textClick('Importar URL')
 await wait(`document.querySelector('.sources-table')!==null&&window.__calls.some(call=>call[0]==='source_import_url')`)
 const themes=[]
 for(const language of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${language}');window.__theme('${mode}','${theme}')`);await pause(20)
  const proof=await js(`(()=>{const d=document.querySelector('.nova-sources-dialog'),t=getComputedStyle(document.querySelector('.sources-table')),s=document.querySelector('.sources-scroll');return{language:document.documentElement.lang,theme:document.documentElement.dataset.novaTheme,mode:document.documentElement.dataset.novaScheme,radius:getComputedStyle(d).borderRadius,header:t.fontSize,thumb:getComputedStyle(s,'::-webkit-scrollbar-thumb').borderRadius,overflow:document.documentElement.scrollWidth>innerWidth,title:d.querySelector('h1').textContent}})()`)
  assert.equal(proof.overflow,false);assert.equal(proof.radius,'22px');assert.equal(proof.header,'12px');assert.equal(proof.thumb,'3px');assert.equal(proof.title,language==='es'?'Fuentes':'Sources');themes.push(proof)
 }
 await js(`window.__locale('es');window.__theme('dark','nova');document.querySelector('.sources-table tbody input').click()`);await pause(60)
 fs.writeFileSync(path.join(output,'sources-saved-es.png'),(await win.webContents.capturePage()).toPNG())
 win.setSize(620,760);await pause(80)
 const narrow=await js(`(()=>{const d=document.querySelector('.nova-sources-dialog').getBoundingClientRect(),a=document.querySelector('.sources-actions').getBoundingClientRect();return{dockInside:a.left>=d.left&&a.right<=d.right&&a.bottom<d.bottom,overflow:document.documentElement.scrollWidth>innerWidth}})()`)
 assert.equal(narrow.dockInside,true);assert.equal(narrow.overflow,false);assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',strictMode:true,loadFailureRecovery:true,transientBusyRecovery:true,floating,dock,themes,narrow,calls:await js('window.__calls')},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,errors},null,2));app.exit(1)}})
