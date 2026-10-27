// Hidden, synthetic renderer verification. Does not open a personal Nova profile.
const {app,BrowserWindow}=require('electron')
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),esbuild=require('esbuild')
assert.ok(process.env.NOVA_MEMORY_TABLE_OUTPUT)
const output=path.resolve(process.env.NOVA_MEMORY_TABLE_OUTPUT),desktop=path.resolve(__dirname,'..'),errors=[]
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=`
import React from 'react';import {createRoot} from 'react-dom/client'
import {I18nProvider,useI18n} from './src/i18n'
import {MemoryWindow} from './src/components/MemoryWindow'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css';import './src/themes.css';import './src/settings.css';import './src/window_surfaces.css'
let records=[{memoryId:'one',revision:1,canonicalText:'Prefiero ejemplos claros y respuestas breves.',kind:'PREFERENCE',scopeKind:'WORKSPACE',status:'ACTIVE',sensitivityClass:'NORMAL'},
 {memoryId:'two',revision:1,canonicalText:'Usa diagramas para explicar las relaciones.',kind:'PROCEDURE',scopeKind:'GLOBAL_PROFILE',status:'ACTIVE',sensitivityClass:'NORMAL'}]
window.__manyMemories=()=>{records=Array.from({length:60},(_,i)=>({...records[0],memoryId:'bulk-'+i,canonicalText:'Synthetic memory '+i}))};window.__cancelMemoryDelete=true;window.__calls=[];window.__allowChoice=false
window.api={initialDesktopLocale:'es',initialDesktopGeneral:{language:'es'},getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es'}),setDesktopLocale:async locale=>({success:true,preferences:{schemaVersion:1,locale}}),
 memoryEditSensitivity:async choice=>{window.__calls.push(['sensitivity',choice]);return window.__allowChoice?{completed:true,data:{token:'owned-receipt'}}:{completed:false,canceled:true}},
 memoryCommand:async(name,args)=>{window.__calls.push([name,args]);if(name==='memory_list')return {completed:true,data:{records}};if(name==='memory_delete'){if(window.__cancelMemoryDelete)return {completed:false,canceled:true};records=records.filter(record=>!args.records.some(row=>row.memoryId===record.memoryId))};if(name==='memory_edit')records=records.map(record=>{const row=args.records.find(row=>row.memoryId===record.memoryId);return row?{...record,revision:record.revision+1,canonicalText:row.text,kind:row.kind,scopeKind:row.scope,sensitivityClass:row.sensitive?'SENSITIVE':'NORMAL'}:record});return {completed:true,data:{}}}}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark');window.__theme('dark','nova')
const view={sessionId:'owned',workspace:'C:/Synthetic/Alpha',status:{ready:true,connected:true},approvals:[],inputs:[],memory:{lexicalRecall:true}}
function Harness(){const {setLocale}=useI18n();window.__locale=setLocale;return <MemoryWindow view={view} onClose={()=>{}}/>}
createRoot(document.getElementById('root')).render(<I18nProvider><Harness/></I18nProvider>)`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'memory-table-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{width:100%;height:100%;margin:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=source=>win.webContents.executeJavaScript(source,true)
async function wait(source){for(let i=0;i<200;i++){if(await js(source))return;await pause(25)}throw Error('Timeout: '+source)}
const clickText=text=>js(`Array.from(document.querySelectorAll('button')).find(button=>button.textContent===${JSON.stringify(text)}).click()`)
const setText=text=>js(`(()=>{const input=document.querySelector('.memories-table-input');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,${JSON.stringify(text)});input.dispatchEvent(new Event('input',{bubbles:true}))})()`)
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1180,height:850,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_event,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`document.querySelectorAll('.memories-table tbody tr').length===2`)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('.memories-table th:not(.memories-select-column)'),node=>node.textContent)`),['Recuerdo','Tipo','Ámbito','Contenido sensible'])
 assert.equal(await js(`document.querySelectorAll('.memories-record,[data-memory-detail],.memories-delete').length`),0)
 assert.equal(await js(`Array.from(document.querySelectorAll('.memories-table tbody input[aria-label="Contenido sensible"]')).every(input=>input.disabled)`),true)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('.memories-table-actions button'),node=>node.textContent)`),['Editar'])
 await pause(300)
 const initialDock=await js(`document.querySelector('.memories-table-actions').getBoundingClientRect().top`)
 const floating=await require('./floating_controls_assertions.cjs')(win,'.memories-table-actions','.memories-saved-scroll')
 const themes=[]
 for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__theme('${mode}','${theme}')`);await pause(30)
  themes.push(await js(`(()=>{const table=getComputedStyle(document.querySelector('.nova-data-table-wrap'));return {mode:document.documentElement.dataset.novaScheme,theme:document.documentElement.dataset.novaTheme,border:table.borderColor,background:table.backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth}})()`))
  assert.equal(themes.at(-1).overflow,false)
 }
 await js(`window.__theme('dark','nova')`);await pause(60)
 fs.writeFileSync(path.join(output,'memories-readonly-es.png'),(await win.webContents.capturePage()).toPNG())
 await clickText('Editar');await wait(`document.querySelectorAll('.memories-table-input').length===2`)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('.memories-table-actions button'),node=>node.textContent)`),['Descartar','Guardar'])
 const short=await js(`document.querySelector('.memories-table-input').clientHeight`)
 await setText(Array.from({length:12},(_,i)=>`Línea ${i+1}: ejemplo ampliado.`).join('\n'));await pause(60)
 assert.ok(await js(`document.querySelector('.memories-table-input').clientHeight>${short}`))
 await js(`document.querySelector('.memories-table tbody input[aria-label="Contenido sensible"]').click()`);await pause(30)
 assert.equal(await js(`document.querySelector('.memories-table tbody input[aria-label="Contenido sensible"]').checked`),false)
 await js(`window.__allowChoice=true;document.querySelector('.memories-table tbody input[aria-label="Contenido sensible"]').click()`);await pause(30)
 assert.equal(await js(`document.querySelector('.memories-table tbody input[aria-label="Contenido sensible"]').checked`),true)
 await clickText('Descartar');await wait(`!document.querySelector('.memories-table-input')`)
 assert.equal(await js(`window.__calls.some(call=>call[0]==='memory_edit')`),false)
 await clickText('Editar');await setText('Preferencia actualizada.');await pause(40)
 await clickText('Guardar');await wait(`document.querySelector('.memories-table-text')?.textContent==='Preferencia actualizada.'`)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='memory_edit').length`),1)
 await js(`window.__locale('en')`);await wait(`document.querySelector('.memories-table th:not(.memories-select-column)').textContent==='Memory'`)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('.memories-table th:not(.memories-select-column)'),node=>node.textContent)`),['Memory','Type','Scope','Sensitive content'])
 await clickText('Edit');await wait(`!!document.querySelector('.memories-table-input')`)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('.memories-table-actions button'),node=>node.textContent)`),['Discard','Save'])
 await js(`window.__theme('light','box')`);await pause(50)
 fs.writeFileSync(path.join(output,'memories-edit-en.png'),(await win.webContents.capturePage()).toPNG())
 win.setSize(620,850);await pause(90)
 assert.equal(await js(`document.documentElement.scrollWidth>innerWidth`),false)
 assert.equal(await js(`document.querySelector('.nova-data-table-wrap').scrollWidth>document.querySelector('.nova-data-table-wrap').clientWidth`),true)
 fs.writeFileSync(path.join(output,'memories-narrow-en.png'),(await win.webContents.capturePage()).toPNG())
 await clickText('Discard');win.setSize(1180,850);await js(`window.__locale('es');window.__theme('dark','nova');window.__manyMemories()`);await pause(60)
 await js(`document.querySelector('.memories-refresh').click()`);await wait(`document.querySelectorAll('.memories-table tbody tr').length===60`)
 await pause(60)
 const grownDock=await js(`document.querySelector('.memories-table-actions').getBoundingClientRect().top`)
 assert.ok(Math.abs(grownDock-initialDock)<2,'footer stays at the same viewport height as rows grow: '+JSON.stringify({initialDock,grownDock}))
 await js(`document.querySelector('.memories-select-column input[aria-label="Seleccionar recuerdo"]').click()`);await pause(40)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('.memories-table-actions button'),node=>node.textContent)`),['Eliminar'])
 await clickText('Eliminar');await pause(40)
 assert.equal(await js(`document.querySelector('.memories-select-column input[aria-label="Seleccionar recuerdo"]').checked`),true)
 await js(`document.querySelector('.memories-saved-scroll').scrollTop=99999`);await pause(50)
 const lastRow=await js(`(()=>{const row=document.querySelector('.memories-table tbody tr:last-child').getBoundingClientRect(),scroll=document.querySelector('.memories-saved-scroll').getBoundingClientRect(),dock=document.querySelector('.memories-table-actions').getBoundingClientRect(),button=document.querySelector('.memories-table-actions button').getBoundingClientRect(),table=document.querySelector('.nova-data-table-wrap').getBoundingClientRect();return {rowBottom:row.bottom,scrollBottom:scroll.bottom,dockTop:dock.top,buttonRight:button.right,tableRight:table.right}})()`)
 assert.ok(lastRow.rowBottom<=lastRow.dockTop-12,'the final row scrolls clear of the floating actions');assert.ok(lastRow.dockTop<lastRow.scrollBottom,'actions overlay the full viewport');assert.ok(Math.abs(lastRow.tableRight-lastRow.buttonRight)<2)
 assert.ok(Math.abs(lastRow.dockTop-initialDock)<2)
 fs.writeFileSync(path.join(output,'memories-fixed-delete-es.png'),(await win.webContents.capturePage()).toPNG())
 await js(`window.__cancelMemoryDelete=false`);await clickText('Eliminar');await wait(`document.querySelectorAll('.memories-table tbody tr').length===59`)
 await js(`window.__locale('en')`);await wait(`document.querySelector('.memories-table-actions button').textContent==='Edit'`)
 await js(`document.querySelector('.memories-table thead input').click()`);await wait(`document.querySelector('.memories-table-actions button').textContent==='Delete'`)
 assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',floating,themes,checks:'Read-only, edit, grow, confirm/cancel, discard, overwrite, ES/EN, eight themes, narrow containment'},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,errors},null,2));app.exit(1)}})
