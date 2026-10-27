// Isolated renderer: project navigation, disclosure and previews without a personal profile.
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),esbuild=require('esbuild')
assert.ok(process.env.NOVA_PROJECT_CONTENTS_OUTPUT)
const output=path.resolve(process.env.NOVA_PROJECT_CONTENTS_OUTPUT),desktop=path.resolve(__dirname,'..'),errors=[]
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const entry=`
import React,{useState} from 'react';import {createRoot} from 'react-dom/client'
import {I18nProvider,useI18n} from './src/i18n'
import {FileExplorer} from './src/components/FileExplorer';import {FileViewer} from './src/components/FileViewer'
import {MemoryItemViewer,SourceItemViewer} from './src/components/ProjectItemViewer'
import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import './src/styles.css';import './src/themes.css'
const A='C:/Synthetic/Alpha',B='C:/Synthetic/Beta',long='Un recuerdo muy largo que debe cortarse al final del panel pero verse completo en el visor. '.repeat(12)
const memory={memoryId:'normal',revision:1,canonicalText:long,kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE',status:'ACTIVE',sensitivityClass:'NORMAL'}
window.__calls=[];window.__allow=false;window.__late=false;window.__accept=()=>{}
window.api={initialDesktopLocale:'es',initialDesktopGeneral:{language:'es'},getDesktopPreferences:async()=>({schemaVersion:1,locale:'es',language:'es'}),setDesktopLocale:async locale=>({success:true,preferences:{schemaVersion:1,locale}}),
 listDir:async p=>({success:true,root:p,path:p,entries:[{name:'file.txt',isDirectory:false,isSymlink:false}],nextOffset:null}),
 readFile:async p=>({success:true,root:A,path:p,content:'Project file content'}),
 sourcesList:async()=>{window.__calls.push(['sources']);return {success:true,data:{files:[
  {id:'file',name:'Saved copy.txt',kind:'file',projectPath:A},{id:'url',name:'Saved web page.html',url:'https://example.com',kind:'url',projectPath:A},
  {id:'binary',name:'Image.png',kind:'file',projectPath:A},{id:'foreign',name:'Foreign project',kind:'file',projectPath:B}]}}},
 sourcePreview:async id=>{window.__calls.push(['preview',id]);return {success:true,data:{sourceId:id,root:A,content:id==='binary'?null:'<script>window.untrusted=true</script>\\nSaved original',reason:id==='binary'?'BINARY':null}}},
 memoryCommand:async(name,args)=>{window.__calls.push([name,args]);if(args.includeSensitive&&!window.__allow)return {canceled:true,completed:false};
 window.__maintenance(true);await new Promise(resolve=>setTimeout(resolve,10));window.__maintenance(false);
 const result={completed:true,data:{records:[memory,{...memory,memoryId:'sensitive',sensitivityClass:'SENSITIVE',canonicalText:args.includeSensitive?'Contenido secreto.':'[SENSITIVE — explicit inspection required]'}]}};
 if(window.__late)await new Promise(resolve=>{window.__accept=resolve});return result}}
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark');window.__theme('dark','nova')
function Harness(){
 const {setLocale,t}=useI18n(),[root,setRoot]=useState(A),[show,setShow]=useState(true),[item,setItem]=useState(null),[maintenanceBusy,setMaintenance]=useState(false)
 window.__maintenance=setMaintenance
 window.__locale=setLocale;window.__root=p=>{setItem(null);setRoot(p)};window.__show=value=>{setItem(null);setShow(value)}
 const view={sessionId:root,workspace:root,status:{ready:true,connected:true},approvals:[],inputs:[],memory:{lexicalRecall:true,maintenanceBusy},knowledge:{attachmentRefs:[]}}
 return <div className="harness"><aside className="nova-project-pane"><FileExplorer projects={{activePath:root,defaultPath:A,folders:[{path:A,name:'Alpha'},{path:B,name:'Beta'}]}} view={view} showFiles={show} busy={false} errorCode={null} onProjectAction={async()=>{}} onFileSelect={path=>setItem({kind:'file',path})} onSourceSelect={source=>setItem({kind:'source',source})} onMemorySelect={record=>setItem({kind:'memory',record})} onPreviewClear={()=>setItem(null)}/></aside><main><p id="general-label">{t('generalShowFiles')}</p><p id="general-hint">{t('generalShowFilesHint')}</p></main>{item&&<div className="viewer-pane">{item.kind==='source'?<SourceItemViewer key={item.source.id} source={item.source} rootDir={root} onClose={()=>setItem(null)}/>:item.kind==='memory'?<MemoryItemViewer record={item.record} onClose={()=>setItem(null)}/>:<FileViewer filePath={item.path} rootDir={root} onClose={()=>setItem(null)}/>}</div>}</div>
}
createRoot(document.getElementById('root')).render(<React.StrictMode><I18nProvider><Harness/></I18nProvider></React.StrictMode>)`
esbuild.buildSync({stdin:{contents:entry,resolveDir:desktop,sourcefile:'project-contents-fixture.tsx',loader:'tsx'},bundle:true,outfile:path.join(output,'renderer.js'),platform:'browser',format:'iife',jsx:'automatic',alias:{'@nova/keyboard-shortcuts':path.join(desktop,'shared/keyboard_shortcuts.cjs')}})
fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="renderer.css"><style>html,body,#root{height:100%;margin:0}.harness{display:flex;height:100%;--nova-project-width:300px}.harness main{flex:1}.nova-project-pane{width:var(--nova-project-width);height:100%;flex-shrink:0}.harness .viewer-pane{width:470px;flex-shrink:0}</style></head><body><div id="root"></div><script src="renderer.js"></script></body></html>')
let win;const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=source=>win.webContents.executeJavaScript(source,true)
async function wait(source){for(let i=0;i<180;i++){if(await js(source))return;await pause(25)}throw Error('Timeout '+source)}
const click=selector=>js(`document.querySelector(${JSON.stringify(selector)}).click()`)
const tab=name=>js(`Array.from(document.querySelectorAll('.project-content-tabs button')).find(node=>node.textContent===${JSON.stringify(name)}).click()`)
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1160,height:760,show:false,webPreferences:{offscreen:true,contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(message)})
 await win.loadFile(path.join(output,'index.html'));await wait(`!!document.querySelector('.explorer-node')`)
 assert.equal(await js(`document.querySelector('.project-content-tabs [aria-selected=true]').textContent`),'Archivos')
 await click('.explorer-node');await wait(`document.querySelector('.file-viewer-content').textContent.includes('Project file content')`)
 await tab('Fuentes');await wait(`document.querySelectorAll('.project-content-item').length===3`)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='sources').length`),1)
 assert.equal(await js(`document.querySelectorAll('.project-content-item [data-icon="globe"]').length`),1)
 await click('.project-source-row:nth-of-type(2) .project-content-item');await wait(`document.querySelector('.file-viewer-code')?.textContent.includes('<script>')`)
 assert.equal(await js(`!!window.untrusted`),false)
 await click('.project-source-row:nth-of-type(3) .project-content-item');await wait(`document.querySelector('.file-viewer-status')?.textContent.includes('formato')`)
 await tab('Recuerdos');await wait(`document.querySelectorAll('.project-content-item').length===2`)
 await pause(100)
 assert.equal(await js(`window.__calls.filter(call=>call[0]==='memory_list').length`),1)
 assert.equal(await js(`window.__calls.find(call=>call[0]==='memory_list')[1].scope`),'WORKSPACE')
 await click('.project-content-item');await wait(`!!document.querySelector('.project-memory-preview')`)
 const truncation=await js(`(()=>{const row=document.querySelector('.project-content-item>span');return {ellipsis:getComputedStyle(row).textOverflow,clipped:row.scrollWidth>row.clientWidth,full:document.querySelector('.project-memory-preview p').textContent.length}})()`)
 assert.equal(truncation.ellipsis,'ellipsis');assert.equal(truncation.clipped,true);assert.ok(truncation.full>500)
 await click('.project-content-sensitive input');await pause(70)
 assert.equal(await js(`document.querySelector('.project-content-sensitive input').checked`),false)
 assert.equal(await js(`document.querySelectorAll('.project-content-item')[1].textContent.includes('secreto')`),false)
 await js(`window.__allow=true`);await click('.project-content-sensitive input');await wait(`document.querySelector('.project-content-sensitive input').checked`)
 await click('.project-content-item:nth-of-type(2)');await wait(`document.querySelector('.project-memory-preview p')?.textContent==='Contenido secreto.'`)
 await click('.project-content-sensitive input');assert.equal(await js(`!!document.querySelector('.project-memory-preview')`),false)
 await wait(`!document.querySelector('.project-content-list').getAttribute('aria-busy')||document.querySelector('.project-content-list').getAttribute('aria-busy')==='false'`)
 const themes=[]
 for(const locale of ['es','en'])for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__locale('${locale}');window.__theme('${mode}','${theme}')`);await pause(15)
  const proof=await js(`(()=>{const row=document.querySelector('.project-content-item');return{locale:document.documentElement.lang,mode:document.documentElement.dataset.novaScheme,theme:document.documentElement.dataset.novaTheme,label:document.querySelector('#general-label').textContent,color:getComputedStyle(row).color,overflow:document.documentElement.scrollWidth>innerWidth}})()`)
  assert.equal(proof.overflow,false);assert.equal(proof.label,locale==='es'?'Mostrar contenido del proyecto':'Show project content');themes.push(proof)
 }
 await js(`window.__locale('es');window.__theme('dark','nova');document.querySelector('.nova-project-pane').style.setProperty('--nova-project-width','210px')`);await pause(100)
 const wrap=await js(`Array.from(document.querySelectorAll('.project-content-tabs button'),node=>node.getBoundingClientRect().top)`)
 assert.ok(new Set(wrap).size>1)
 fs.writeFileSync(path.join(output,'narrow-memories-es.png'),(await win.webContents.capturePage()).toPNG())
 await js(`document.querySelector('.nova-project-pane').style.setProperty('--nova-project-width','300px')`);await tab('Fuentes');await wait(`document.querySelectorAll('.project-content-item').length===3`)
 await click('.project-content-item');await wait(`!!document.querySelector('.file-viewer-code')`);await pause(100)
 fs.writeFileSync(path.join(output,'sources-es.png'),(await win.webContents.capturePage()).toPNG())
 await js(`window.__late=true`);await tab('Recuerdos');await pause(40);await js(`window.__root('C:/Synthetic/Beta');window.__accept()`)
 await wait(`document.querySelector('.project-content-tabs [aria-selected=true]').textContent==='Archivos'`)
 assert.equal(await js(`document.querySelectorAll('.project-content-item,.project-memory-preview').length`),0)
 await js(`window.__show(false)`);await wait(`!document.querySelector('.project-content-panel')`)
 assert.equal(await js(`getComputedStyle(document.querySelector('.project-folder-list')).maxHeight`),'none')
 await js(`window.__show(true)`);await wait(`!!document.querySelector('.project-content-panel')`)
 assert.equal(await js(`document.querySelector('.project-content-tabs [aria-selected=true]').textContent`),'Archivos')
 assert.deepEqual(errors,[])
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',strictMode:true,truncation,wrap,themes,sensitiveCancelAndRevoke:true,staleProjectResponseDiscarded:true,filesPreserved:true},null,2));app.exit(0)
 }catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,errors},null,2));app.exit(1)}})
