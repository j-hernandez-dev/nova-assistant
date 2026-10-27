// Hidden renderer regression with synthetic profile files. No personal Nova profile or backend is opened.
const {app,BrowserWindow}=require('electron')
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),esbuild=require('esbuild')
const output=path.resolve(process.env.NOVA_STORAGE_UI_OUTPUT||'')
assert.ok(process.env.NOVA_STORAGE_UI_OUTPUT,'an explicit owned output folder is required')
fs.mkdirSync(output,{recursive:true})
app.setPath('userData',path.join(output,'profile'))
const desktop=path.resolve(__dirname,'..'),errors=[]
const entry=`
import React,{useState} from 'react'
import {createRoot} from 'react-dom/client'
import {I18nProvider,useI18n} from './src/i18n'
import {SettingsPanel} from './src/components/SettingsPanel'
import {StorageSettings} from './src/components/StorageSettings'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css'
import './src/themes.css'
import './src/window_surfaces.css'
const file=(id,name,projectPath,bytes)=>({id,name,projectPath,bytes,modifiedAt:'2026-10-22T12:00:00Z'})
let files=[file('orphan','orphan.pdf',null,4096),file('report','report.md','A',1024),file('notes','notes.txt','A',2048)],restartRequired=false
const categories=['chats','attachments','memories','navigation','configuration','audit','catalog','caches']
window.__manyFiles=()=>{files=Array.from({length:80},(_,i)=>file('bulk-'+i,'bulk-'+String(i).padStart(2,'0')+'.txt','A',100))};window.__storageCalls=[];window.__cancelDelete=false
function overview(){
 const bytes=files.reduce((sum,file)=>sum+file.bytes,0)
 return {totalBytes:bytes+16384,categories:categories.map(id=>({id,bytes:id==='attachments'?bytes:id==='caches'?16384:0})),
 folders:categories.map(id=>({id,category:id,path:'C:/Nova-owned-test/'+id,bytes:id==='attachments'?bytes:0,exists:true,restartRequired:true})),
 projects:[{path:null,name:'',bytes:files.filter(file=>file.projectPath===null).reduce((sum,file)=>sum+file.bytes,0),fileCount:files.filter(file=>file.projectPath===null).length},...['A','B'].map((path,index)=>({path,name:index?'Beta':'Alpha',bytes:files.filter(file=>file.projectPath===path).reduce((sum,file)=>sum+file.bytes,0),fileCount:files.filter(file=>file.projectPath===path).length}))],restartRequired}
}
window.api={initialDesktopLocale:'es',initialDesktopGeneral:{language:'es',autoSwitchView:false,transitionsEnabled:true},getAppVersion:async()=>'fixture',
 getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es',autoSwitchView:false,transitionsEnabled:true}),
 setDesktopLocale:async(locale)=>({success:true,preferences:{schemaVersion:1,locale}}),
 storageOverview:async()=>{window.__storageCalls.push(['overview']);return {success:true,data:overview()}},
 storageFiles:async(projectPath)=>{window.__storageCalls.push(['files',projectPath]);return {success:true,data:{projectPath,files:files.filter(file=>file.projectPath===projectPath)}}},
 storageMove:async(ids,projectPath)=>{window.__storageCalls.push(['move',ids,projectPath]);files=files.map(file=>ids.includes(file.id)?{...file,projectPath}:file);return {success:true,data:{}}},
 storageDownload:async(ids)=>{window.__storageCalls.push(['download',ids]);return {success:true,data:{downloaded:ids.length}}},
 storageDeleteFiles:async(ids)=>{window.__storageCalls.push(['delete',ids]);if(window.__cancelDelete){window.__cancelDelete=false;return {success:false,canceled:true}}files=files.filter(file=>!ids.includes(file.id));return {success:true,data:{}}},
 storageOpenFolder:async(id)=>({success:true,data:{}}),
 storageDeleteFolder:async(id)=>{restartRequired=true;return {success:true,data:{restartRequired:true}}},storageRestart:async()=>({success:true,data:{}}),
}
window.__setStorageTheme=(colorScheme,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme,darkTheme:theme,lightTheme:theme},colorScheme==='dark')
window.__setStorageTheme('dark','nova')
function Harness(){const {setLocale}=useI18n(),[section,setSection]=useState('storage');window.__setStorageLocale=setLocale;return <SettingsPanel initialSection="storage" onClose={()=>{}} onSectionChange={setSection} storage={<StorageSettings active={section==='storage'}/>}/>}
createRoot(document.getElementById('root')).render(<I18nProvider><Harness/></I18nProvider>)
`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'storage-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{width:100%;height:100%;margin:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))
const js=source=>win.webContents.executeJavaScript(source,true)
async function wait(source,label){for(let index=0;index<200;index++){if(await js(source))return;await pause(25)}throw Error('Timed out: '+label)}
const click=selector=>js(`(()=>{const element=document.querySelector(${JSON.stringify(selector)});element.focus();element.click()})()`)
async function key(value){win.webContents.sendInputEvent({type:'keyDown',keyCode:value});win.webContents.sendInputEvent({type:'keyUp',keyCode:value});await pause(35)}
async function choose(keyName){await click('[data-settings-select="storageProject"]');await key(keyName);await key('ENTER')}
app.whenReady().then(async()=>{
 try{
  win=new BrowserWindow({width:1180,height:850,show:false,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false,offscreen:true}})
  win.webContents.on('console-message',(_event,level,message)=>{if(level>=3)errors.push(message)})
  await win.loadFile(path.join(output,'index.html'))
  await wait(`document.querySelectorAll('.nova-storage-project').length===3`,'storage inventory')
  assert.deepEqual(await js(`Array.from(document.querySelectorAll('.nova-storage-project strong'),node=>node.textContent)`),['No vinculado','Alpha','Beta'])
  await js(`(()=>{const reference=document.createElement('div');reference.id='common-settings-reference';reference.style.display='none';reference.innerHTML='<div class="nova-settings-introduction"><h2>Reference</h2><p>Description</p></div><div class="nova-settings-card"></div>';document.querySelector('.nova-settings-dialog').append(reference)})()`)
  const themeProof=[]
  for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
   await js(`window.__setStorageTheme(${JSON.stringify(mode)},${JSON.stringify(theme)})`);await pause(30)
   const colors=await js(`(()=>{const root=getComputedStyle(document.documentElement),bar=getComputedStyle(document.querySelector('.nova-storage-bar [data-storage-category="chats"]'));return {mode:document.documentElement.dataset.novaScheme,theme:document.documentElement.dataset.novaTheme,text:root.getPropertyValue('--text'),accent:root.getPropertyValue('--accent'),bar:bar.backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth}})()`)
   assert.equal(colors.mode,mode);assert.equal(colors.theme,theme);assert.equal(colors.overflow,false);assert.notEqual(colors.bar,'rgba(0, 0, 0, 0)');themeProof.push(colors)
   const shared=await js(`(()=>{const card=getComputedStyle(document.querySelector('.nova-storage-settings .nova-settings-card')),reference=getComputedStyle(document.querySelector('#common-settings-reference .nova-settings-card'));return {storageCard:card.backgroundColor,commonCard:reference.backgroundColor,storageBorder:card.borderColor,commonBorder:reference.borderColor,headingGap:getComputedStyle(document.querySelector('.nova-storage-settings h2')).marginBottom,commonGap:getComputedStyle(document.querySelector('#common-settings-reference h2')).marginBottom}})()`)
   assert.equal(shared.storageCard,shared.commonCard);assert.equal(shared.storageBorder,shared.commonBorder);assert.equal(shared.headingGap,shared.commonGap);assert.equal(shared.headingGap,'7px');Object.assign(themeProof.at(-1),shared)
  }
  await js(`window.__setStorageTheme('dark','nova')`);await pause(180)
  fs.writeFileSync(path.join(output,'overview-dark.png'),(await win.webContents.capturePage()).toPNG())
  await js(`document.querySelector('.nova-storage-project').scrollIntoView({block:'center'})`);await pause(50)
  const bounds=await js(`(()=>{const row=document.querySelector('.nova-storage-project').getBoundingClientRect(),button=document.querySelector('.nova-storage-project-open').getBoundingClientRect();return {rowX:Math.round(row.x+10),y:Math.round(button.y+button.height/2),buttonX:Math.round(button.x+button.width/2)}})()`)
  win.webContents.sendInputEvent({type:'mouseMove',x:bounds.rowX,y:bounds.y});await pause(180)
  const rowHover=await js(`getComputedStyle(document.querySelector('.nova-storage-project-open')).backgroundColor`)
  assert.equal(rowHover,'rgba(0, 0, 0, 0)')
  win.webContents.sendInputEvent({type:'mouseMove',x:bounds.buttonX,y:bounds.y});await pause(180)
  const buttonHover=await js(`getComputedStyle(document.querySelector('.nova-storage-project-open')).backgroundColor`)
  assert.notEqual(buttonHover,rowHover)
  fs.writeFileSync(path.join(output,'manage-button-hover.png'),(await win.webContents.capturePage()).toPNG())
  await click('.nova-storage-project[data-storage-project=""] .nova-storage-project-open');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===1`,'unlinked file')
  await click('input[aria-label="Seleccionar todos los archivos"]');await pause(60)
  assert.equal(await js(`document.querySelector('[data-settings-select="storageProject"]').textContent.trim()`),'Sin vincular')
  await choose('DOWN');await wait(`window.__storageCalls.some(call=>call[0]==='move'&&call[2]==='A')`,'keyboard link')
  await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===0`,'moved out of unlinked')
  await click('.nova-storage-back');await click('.nova-storage-project[data-storage-project="A"] .nova-storage-project-open');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===3`,'project inventory after move')
  await click('input[aria-label="Seleccionar todos los archivos"]');await pause(40)
  assert.equal(await js(`document.querySelector('[data-settings-select="storageProject"]').textContent.trim()`),'Alpha')
  await js(`document.documentElement.dataset.novaTransitions='false'`)
  const motion=await js(`(()=>{const selection=getComputedStyle(document.querySelector('.nova-storage-selection')),page=getComputedStyle(document.querySelector('.nova-storage-page'));return {transition:selection.transitionDuration,animation:page.animationName}})()`)
  assert.equal(motion.transition,'0s');assert.equal(motion.animation,'none')
  await pause(100)
  fs.writeFileSync(path.join(output,'files-selected.png'),(await win.webContents.capturePage()).toPNG())
  const layout=await js(`(()=>{const table=document.querySelector('.nova-storage-table-wrap').getBoundingClientRect(),footer=document.querySelector('.nova-storage-selection').getBoundingClientRect(),box=document.querySelector('[data-settings-select="storageProject"]').getBoundingClientRect();return {gap:footer.top-table.bottom,left:box.left,right:footer.right,footerPosition:getComputedStyle(document.querySelector('.nova-storage-selection')).position,rounding:getComputedStyle(document.querySelector('.nova-storage-table tbody td')).borderTopLeftRadius}})()`)
  assert.equal(layout.footerPosition,'absolute');assert.equal(layout.rounding,'8px')
  await require('./floating_controls_assertions.cjs')(win,'.nova-storage-selection','.nova-storage-file-scroll')
  await js(`Array.from(document.querySelectorAll('.nova-storage-selection button')).find(button=>button.textContent==='Descargar').click()`)
  await wait(`window.__storageCalls.some(call=>call[0]==='download'&&call[1].length===3)`,'download selected files')
  assert.equal(await js(`document.querySelector('.nova-storage-table tbody input').checked`),true)
  await choose('HOME');await wait(`window.__storageCalls.some(call=>call[0]==='move'&&call[1].length===3&&call[2]===null)`,'unlink three files')
  await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===0`,'unlinked out of project')
  await click('.nova-storage-back');await click('.nova-storage-project[data-storage-project=""] .nova-storage-project-open');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===3`,'unlinked inventory after reassignment')
  await click('.nova-storage-table tbody input');await pause(30);await js(`window.__cancelDelete=true`);await click('.nova-storage-selection .nova-settings-danger');await pause(80)
  assert.equal(await js(`document.querySelectorAll('.nova-storage-table tbody tr').length`),3)
  assert.equal(await js(`document.querySelector('.nova-storage-table tbody input').checked`),true)
  assert.equal(await js(`!!document.querySelector('.nova-storage-feedback [role="alert"]')`),false)
  await click('.nova-storage-selection .nova-settings-danger');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===2`,'confirmed deletion')
  await click('.nova-storage-back');await js(`window.__setStorageLocale('en')`);await pause(100)
  assert.equal(await js(`document.querySelector('.nova-storage-settings h2').textContent`),'Storage')
  assert.deepEqual(await js(`Array.from(document.querySelectorAll('.nova-storage-project strong'),node=>node.textContent)`),['Unlinked','Alpha','Beta'])
  await js(`window.__setStorageTheme('light','box')`);await pause(50)
  fs.writeFileSync(path.join(output,'overview-light-english.png'),(await win.webContents.capturePage()).toPNG())
  const reads=await js(`window.__storageCalls.filter(call=>call[0]==='overview').length`)
  await click('[aria-label="Refresh storage"]');await wait(`window.__storageCalls.filter(call=>call[0]==='overview').length===${reads+1}`,'fresh update')
  await js(`window.__manyFiles();window.__setStorageTheme('dark','nova')`);await click('[aria-label="Refresh storage"]');await pause(60)
  await click('.nova-storage-project[data-storage-project="A"] .nova-storage-project-open');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===80`)
  await click('.nova-storage-table tbody input');await pause(60)
  const dockBefore=await js(`document.querySelector('.nova-storage-selection').getBoundingClientRect().top`)
  assert.equal(await js(`document.querySelector('.nova-storage-search').compareDocumentPosition(document.querySelector('.nova-storage-file-heading')) & Node.DOCUMENT_POSITION_FOLLOWING`),4)
  await js(`(()=>{const input=document.querySelector('.nova-storage-search input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'BULK-09');input.dispatchEvent(new Event('input',{bubbles:true}))})()`);await click('.nova-storage-search [type="submit"]');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===1`)
  assert.equal(await js(`document.querySelector('.nova-storage-table tbody input').checked`),false)
  await click('.nova-storage-table tbody input');await pause(40)
  const dockAfter=await js(`document.querySelector('.nova-storage-selection').getBoundingClientRect().top`)
  assert.ok(Math.abs(dockAfter-dockBefore)<2,'searching a short table does not move the actions')
  await js(`(()=>{const input=document.querySelector('.nova-storage-search input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'');input.dispatchEvent(new Event('input',{bubbles:true}))})()`);await click('.nova-storage-search [type="submit"]');await wait(`document.querySelectorAll('.nova-storage-table tbody tr').length===80`)
  await click('.nova-storage-table thead input');await js(`document.querySelector('.nova-storage-file-scroll').scrollTop=99999`);await pause(60)
  const last=await js(`(()=>{const row=document.querySelector('.nova-storage-table tbody tr:last-child').getBoundingClientRect(),scroll=document.querySelector('.nova-storage-file-scroll').getBoundingClientRect(),dock=document.querySelector('.nova-storage-selection').getBoundingClientRect(),button=document.querySelector('.nova-storage-selection .nova-settings-danger').getBoundingClientRect(),table=document.querySelector('.nova-storage-table-wrap').getBoundingClientRect();return {rowBottom:row.bottom,scrollBottom:scroll.bottom,dockTop:dock.top,buttonRight:button.right,tableRight:table.right}})()`)
  assert.ok(last.rowBottom<=last.dockTop-12,'the final row scrolls clear of the floating actions');assert.ok(last.dockTop<last.scrollBottom,'actions overlay the full viewport');assert.ok(Math.abs(last.tableRight-last.buttonRight)<2)
  assert.ok(Math.abs(last.dockTop-dockBefore)<2)
  fs.writeFileSync(path.join(output,'storage-fixed-actions-long-en.png'),(await win.webContents.capturePage()).toPNG())
  win.setSize(690,850);await pause(90)
  assert.equal(await js(`document.documentElement.scrollWidth>innerWidth`),false)
  fs.writeFileSync(path.join(output,'storage-fixed-actions-narrow-en.png'),(await win.webContents.capturePage()).toPNG())
  assert.deepEqual(errors,[])
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',checks:25,themeProof,hover:{rowHover,buttonHover},motion,calls:await js('window.__storageCalls')},null,2))
  app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:String(error.stack||error),consoleErrors:errors},null,2));app.exit(1)}
})
