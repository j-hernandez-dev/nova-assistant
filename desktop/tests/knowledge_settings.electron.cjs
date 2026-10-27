// Isolated Knowledge settings: no personal profile, provider calls or documents.
const {app,BrowserWindow}=require('electron'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),esbuild=require('esbuild')
assert.ok(process.env.NOVA_KNOWLEDGE_UI_OUTPUT)
const output=path.resolve(process.env.NOVA_KNOWLEDGE_UI_OUTPUT),desktop=path.resolve(__dirname,'..'),errors=[]
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=`
import React,{useState} from 'react';import {createRoot} from 'react-dom/client'
import {I18nProvider,useI18n} from './src/i18n';import {SettingsPanel} from './src/components/SettingsPanel'
import {KnowledgeSettings} from './src/components/KnowledgeSettings';import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css';import './src/themes.css';import './src/window_surfaces.css'
const defaults={lexicalRecall:true,semanticRecall:false,autoIndex:true,autoRebuild:true}
let value={...defaults,semanticAvailable:false,indexing:false,indexedSources:0,totalSources:0,errorCode:null}
window.__calls=[]
window.api={initialDesktopLocale:'es',getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es'}),setDesktopLocale:async locale=>({success:true,preferences:{schemaVersion:1,locale}}),
 applicationCommand:async(kind,args)=>{window.__calls.push([kind,args]);await new Promise(resolve=>setTimeout(resolve,20));value={...value,...(kind==='ResetKnowledgeSettings'?defaults:args)};window.__publish({...value});return {accepted:true}}}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark');window.__theme('dark','nova')
function Harness(){const {setLocale}=useI18n(),[state,setState]=useState(value)
 window.__publish=setState;window.__locale=setLocale;window.__em=available=>{value={...value,semanticAvailable:available};setState(value)}
 const view={sessionId:'owned',workspace:'C:/Synthetic/Alpha',status:{ready:true,connected:true},approvals:[],inputs:[],knowledgeSettings:state}
 return <SettingsPanel initialSection="knowledge" onClose={()=>{}} knowledge={<KnowledgeSettings view={view}/>}/>
}
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><Harness/></I18nProvider></React.StrictMode>)`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'knowledge-settings-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),format:'iife',platform:'browser',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{height:100%;margin:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win;const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let n=0;n<180;n++){if(await js(code))return;await pause(25)}throw Error('Timeout '+code)}
const click=selector=>js(`document.querySelector(${JSON.stringify(selector)}).click()`)
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1180,height:850,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`document.querySelectorAll('[data-knowledge-setting]').length===4`)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('[data-knowledge-setting]'),node=>({checked:node.checked,disabled:node.disabled}))`),[
  {checked:true,disabled:false},{checked:false,disabled:true},{checked:true,disabled:true},{checked:true,disabled:true}])
 assert.equal(await js(`document.querySelectorAll('[data-settings-domain="knowledge"] .nova-settings-introduction').length`),1)
 assert.equal(await js(`!!document.querySelector('#nova-settings-rag-query,[data-testid="rag-panel"]')`),false)
 await click('[data-knowledge-setting="lexicalRecall"]');await wait(`document.querySelector('[data-knowledge-setting="lexicalRecall"]').checked===false`)
 await pause(50);await click('.nova-knowledge-settings .nova-settings-reset');await wait(`document.querySelector('[data-knowledge-setting="lexicalRecall"]').checked`)
 await js('window.__em(true)');await wait(`Array.from(document.querySelectorAll('[data-knowledge-setting]')).every(node=>!node.disabled)`)
 for(const field of ['semanticRecall','autoIndex','autoRebuild']){
  await click('[data-knowledge-setting="'+field+'"]');await pause(70)
 }
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('[data-knowledge-setting]'),node=>node.checked)`),[true,true,false,false])
 await click('.nova-knowledge-settings .nova-settings-reset');await wait(`document.querySelector('[data-knowledge-setting="autoIndex"]').checked`)
 assert.deepEqual(await js(`Array.from(document.querySelectorAll('[data-knowledge-setting]'),node=>node.checked)`),[true,false,true,true])
 const themes=[]
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await pause(25)
  const proof=await js(`(()=>{const panel=document.querySelector('.nova-knowledge-settings'),title=panel.querySelector('h2'),card=panel.querySelector('.nova-settings-card');return{locale:document.documentElement.lang,mode:document.documentElement.dataset.novaScheme,theme:document.documentElement.dataset.novaTheme,title:title.textContent,gap:getComputedStyle(title).marginBottom,card:getComputedStyle(card).backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth,descriptions:panel.querySelectorAll('.nova-preference-row p').length}})()`)
  assert.equal(proof.title,locale==='es'?'Conocimiento':'Knowledge');assert.equal(proof.gap,'7px');assert.equal(proof.overflow,false);assert.equal(proof.descriptions,4);themes.push(proof)
 }
 await js(`window.__locale('es');window.__theme('dark','nova')`);await pause(120)
 fs.writeFileSync(path.join(output,'knowledge-es.png'),(await win.webContents.capturePage()).toPNG())
 await js(`window.__locale('en');window.__theme('light','synthwave84');window.__em(false)`);win.setSize(690,850);await pause(120)
 assert.equal(await js(`document.documentElement.scrollWidth>innerWidth`),false)
 fs.writeFileSync(path.join(output,'knowledge-en-narrow.png'),(await win.webContents.capturePage()).toPNG())
 assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',themes,calls:await js('window.__calls'),defaults:[true,false,true,true],availabilityGate:true},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,errors},null,2));app.exit(1)}})
