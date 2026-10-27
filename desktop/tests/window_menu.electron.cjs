/* Isolated chrome/editor QA. Never opens Nova's personal profile or clipboard. */
const {app,BrowserWindow,Menu,ipcMain}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
const {createDesktopMenu}=require('../electron/desktop_menu.cjs')
const {createDesktopView}=require('../electron/desktop_view.cjs')
const desktop=path.resolve(__dirname,'..'),output=path.resolve(process.argv[2]||path.join(desktop,'window-menu-qa'))
fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
const esbuild=require(path.join(desktop,'node_modules/esbuild')),errors=[],checks=[]
esbuild.buildSync({stdin:{contents:`
import {ipcRenderer} from 'electron';import {installStartupScreen} from './shared/startup_screen';import {installWindowMenu} from './shared/window_menu'
const startup=installStartupScreen(document,'es',undefined,()=>true)
const menu=installWindowMenu(document,position=>ipcRenderer.invoke('open-desktop-menu',position),ready=>ipcRenderer.send('desktop-menu-ready',ready))
window.addEventListener('unload',()=>{startup();menu()},{once:true})`,resolveDir:desktop,sourcefile:'chrome-preload.ts',loader:'ts'},bundle:true,external:['electron'],platform:'node',format:'cjs',outfile:path.join(output,'preload.cjs')})
esbuild.buildSync({stdin:{contents:`
import React,{useState} from 'react';import {createRoot} from 'react-dom/client';import {applyAppearance,defaultAppearance} from './shared/desktop_appearance'
import {ModalHost} from './src/components/ModalHost'
import './src/styles.css';import './src/themes.css'
window.__theme=(mode,theme)=>applyAppearance(document,{...defaultAppearance,colorScheme:mode,darkTheme:theme,lightTheme:theme},mode==='dark')
function Fixture(){const [input,setInput]=useState('Texto inicial'),[text,setText]=useState('Otra nota'),[modal,setModal]=useState(false),[note,setNote]=useState('Recuerdo de prueba');window.__modal=setModal;return <div style={{padding:50}}>
 <input id="field" value={input} onChange={e=>setInput(e.target.value)}/><span id="field-mirror">{input}</span>
 <textarea id="note" value={text} onChange={e=>setText(e.target.value)}/><span id="note-mirror">{text}</span>
 <input id="readonly" readOnly value="Sólo lectura"/><div id="rich" contentEditable suppressContentEditableWarning>Texto editable</div>
 {modal&&<ModalHost open onClose={()=>setModal(false)} label="Fixture" className="nova-memories-dialog nova-surface-dialog"><textarea id="modal-note" value={note} onChange={e=>setNote(e.target.value)}/><button onClick={()=>setModal(false)}>Cerrar</button></ModalHost>}
 </div>}
window.__mount=()=>{createRoot(document.getElementById('root')).render(<Fixture/>);document.documentElement.dataset.novaStartup='ready'}
`,resolveDir:desktop,sourcefile:'chrome-renderer.tsx',loader:'tsx'},bundle:true,platform:'browser',format:'iife',jsx:'automatic',outfile:path.join(output,'renderer.js')})
let html=fs.readFileSync(path.join(desktop,'index.html'),'utf8').replace('<script type="module" async src="/src/main.tsx"></script>','<script src="./renderer.js"></script>')
html=html.replace('</head>','<link rel="stylesheet" href="renderer.css"></head>');fs.writeFileSync(path.join(output,'index.html'),html)
let win,currentMenu,popupOptions,locale='es',quits=0,opens=0,projects=0
const view=createDesktopView({getWindow:()=>win||null,onChange:percent=>{if(process.platform!=='darwin')win.setTitleBarOverlay({height:Math.round(44*percent/100)})}})
const proxy={buildFromTemplate(template){const menu=Menu.buildFromTemplate(template);menu.popup=options=>{currentMenu=menu;popupOptions=options;opens++};menu.closePopup=()=>popupOptions?.callback();return menu}}
const host=createDesktopMenu({Menu:proxy,getWindow:()=>win||null,getLocale:()=>locale,quit:()=>{quits++},newProject:()=>{projects++},view})
ipcMain.on('desktop-menu-ready',(event,ready)=>{if(event.sender===win?.webContents&&event.senderFrame===win.webContents.mainFrame)host.setReady(ready)})
ipcMain.handle('open-desktop-menu',(event,position)=>event.sender===win?.webContents&&event.senderFrame===win.webContents.mainFrame?host.open(position):{opened:false})
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=code=>win.webContents.executeJavaScript(code,true)
async function wait(code){for(let n=0;n<160;n++){if(await js(code))return;await pause(30)}throw Error('Timeout '+code)}
async function openMenu(){const before=opens,b=await js(`(()=>{const b=document.getElementById('nova-window-menu').getBoundingClientRect();return {x:Math.round(b.left+b.width/2),y:Math.round(b.top+b.height/2)}})()`)
 b.x=Math.round(b.x*view.getPercent()/100);b.y=Math.round(b.y*view.getPercent()/100)
 win.webContents.sendInputEvent({type:'mouseMove',...b});win.webContents.sendInputEvent({type:'mouseDown',button:'left',modifiers:['leftButtonDown'],clickCount:1,...b});win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...b})
 for(let n=0;n<80&&opens===before;n++)await pause(25);assert.equal(opens,before+1);await wait(`document.getElementById('nova-window-menu').getAttribute('aria-expanded')==='true'`)}
function closeMenu(){popupOptions.callback()}
async function edit(role){await openMenu();const item=currentMenu.getMenuItemById(role);assert.equal(item.role.toLowerCase(),role.toLowerCase())
 // Invoke the exact native editor command represented by the selected role.
 // Copy/cut/paste bindings are checked without changing the user's clipboard.
 win.webContents[role]();closeMenu();await pause(60)}
app.whenReady().then(async()=>{try{
 win=new BrowserWindow({width:1100,height:760,show:false,...(process.platform==='darwin'?{}:{titleBarStyle:'hidden',titleBarOverlay:{height:44,color:'#0a0a0a',symbolColor:'#ffffff'}}),webPreferences:{offscreen:true,preload:path.join(output,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}})
 view.attach(win)
 win.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message)})
 win.webContents.on('preload-error',(_e,_path,error)=>errors.push(String(error)))
 await win.loadFile(path.join(output,'index.html'));await wait(`!!window.__mount&&document.getElementById('nova-startup').hasAttribute('data-startup-managed')`)
 assert.equal(await js(`document.getElementById('nova-window-menu').disabled`),true)
 await js(`document.getElementById('nova-window-menu').click()`);assert.equal(opens,0)
 assert.deepEqual(await host.open({x:9,y:44}),{opened:false});checks.push('Menu is disabled in the document and host throughout startup')
 assert.equal(await js(`document.querySelectorAll('.nova-startup h1').length`),0)
 assert.equal(await js(`getComputedStyle(document.getElementById('nova-startup-message')).clipPath`),'inset(50%)')
 assert.equal(await js(`getComputedStyle(document.getElementById('nova-startup-action')).fontSize`),'0px')
 const themes=[]
 for(const mode of ['dark','light'])for(const theme of ['nova','synthwave84','matrix','box']){
  await js(`window.__theme('${mode}','${theme}')`);await pause(25)
  const proof=await js(`(()=>{const a=document.getElementById('nova-startup').getBoundingClientRect(),b=document.querySelector('.nova-startup-mark').getBoundingClientRect();return {x:Math.abs(a.left+a.width/2-b.left-b.width/2),y:Math.abs(a.top+a.height/2-b.top-b.height/2),background:getComputedStyle(document.getElementById('nova-startup')).backgroundColor}})()`)
  assert.ok(proof.x<1&&proof.y<1);themes.push({mode,theme,...proof})
 }
 await js(`window.__theme('dark','nova')`);await pause(130);fs.writeFileSync(path.join(output,'startup-emblem.png'),(await win.webContents.capturePage()).toPNG())
 await js(`document.documentElement.dataset.novaStartup='failed'`);await wait(`!document.getElementById('nova-startup-action').hidden`)
 assert.equal(await js(`document.getElementById('nova-window-menu').disabled`),true)
 checks.push('Loading and recovery show only the centered emblem; text remains available to assistive technology')
 await js(`window.__mount()`);await wait(`!document.getElementById('nova-startup')&&!document.getElementById('nova-window-menu').disabled`)
 for(const id of ['field','note']){
  const original=await js(`document.getElementById('${id}').value`)
  await js(`(()=>{const f=document.getElementById('${id}');f.focus();f.setSelectionRange(0,f.value.length)})()`)
  await win.webContents.insertText('Nova editada');await pause(70)
  assert.equal(await js(`document.getElementById('${id}-mirror').textContent`),'Nova editada')
  await edit('undo');assert.equal(await js(`document.getElementById('${id}').value`),original)
  await edit('redo');assert.equal(await js(`document.getElementById('${id}').value`),'Nova editada')
  await edit('selectAll');assert.deepEqual(await js(`(()=>{const f=document.getElementById('${id}');return [document.activeElement.id,f.selectionStart,f.selectionEnd]})()`),[id,0,12])
  await edit('delete');assert.equal(await js(`document.getElementById('${id}-mirror').textContent`),'')
 }
 checks.push('Menu opening preserves focus and selection; native undo, redo, delete and select-all update controlled inputs and textareas')
 await js(`document.getElementById('readonly').focus()`);await edit('selectAll');await edit('delete');assert.equal(await js(`document.getElementById('readonly').value`),'Sólo lectura')
 await js(`document.getElementById('rich').focus()`);await edit('selectAll');await edit('delete');assert.equal(await js(`document.getElementById('rich').textContent`),'')
 checks.push('Read-only controls stay read-only, and contenteditable fields use the same native editor actions')
 await js(`document.getElementById('field').focus()`);await win.webContents.insertText('Teclado prueba');await wait(`document.getElementById('field-mirror').textContent==='Teclado prueba'`)
 await js(`(()=>{const f=document.getElementById('field');f.setSelectionRange(2,8);document.getElementById('nova-window-menu').focus()})()`)
 await js(`document.getElementById('nova-window-menu').click()`);await wait(`document.getElementById('nova-window-menu').getAttribute('aria-expanded')==='true'`)
 assert.deepEqual(await js(`(()=>{const f=document.getElementById('field');return [document.activeElement.id,f.selectionStart,f.selectionEnd]})()`),['field',2,8]);closeMenu();await pause(40)
 await js(`window.__modal(true)`);await wait(`document.getElementById('root').inert&&!!document.getElementById('modal-note')`)
 assert.equal(await js(`document.querySelector('.nova-window-titlebar').inert||document.getElementById('nova-window-menu').disabled`),false)
 await js(`document.getElementById('modal-note').focus()`);await edit('selectAll');await edit('delete');assert.equal(await js(`document.getElementById('modal-note').value`),'')
 win.webContents.sendInputEvent({type:'keyDown',keyCode:'Tab',modifiers:['shift']});win.webContents.sendInputEvent({type:'keyUp',keyCode:'Tab',modifiers:['shift']});await pause(50)
 assert.equal(await js(`document.activeElement.id`),'nova-window-menu')
 await js(`document.getElementById('nova-window-menu').click()`);await wait(`document.getElementById('nova-window-menu').getAttribute('aria-expanded')==='true'`)
 assert.equal(await js(`document.activeElement.id`),'modal-note')
 await js(`document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`)
 assert.equal(await js(`!!document.getElementById('modal-note')`),true);closeMenu();await pause(30)
 await js(`window.__modal(false)`);await wait(`!document.querySelector('[role=dialog]')&&!document.getElementById('root').inert`)
 checks.push('Edit remains accessible inside Nova modal windows while background application controls stay inert')
 for(const language of ['es','en']){
  locale=language;await js(`document.documentElement.lang='${language}'`);await pause(30);await openMenu()
  assert.deepEqual(currentMenu.items.filter(item=>item.type!=='separator').map(item=>item.label),language==='es'?['Archivo','Editar','Ver','Cerrar Nova']:['File','Edit','View','Quit Nova'])
  for(const role of ['undo','redo','cut','copy','paste','delete','selectAll'])assert.equal(currentMenu.getMenuItemById(role).role.toLowerCase(),role.toLowerCase())
  assert.equal(currentMenu.getMenuItemById('newProject').label,language==='es'?'Nuevo proyecto…':'New project…')
  assert.deepEqual(currentMenu.getMenuItemById('view').submenu.items.map(item=>item.label),language==='es'?['Acercar','Alejar','Tamaño real']:['Zoom in','Zoom out','Actual size'])
  closeMenu();await pause(30)
 }
 await openMenu();currentMenu.getMenuItemById('newProject').click();assert.equal(projects,1);closeMenu();await pause(30)
 const scales=[]
 for(const [direction,values] of [['zoomIn',[110,120,130,140,150]],['zoomOut',[90,80,70,60,50]]]){
  await openMenu();currentMenu.getMenuItemById('actualSize').click();closeMenu();await pause(80)
  for(const percent of values){
   await openMenu();currentMenu.getMenuItemById(direction).click();closeMenu();await pause(100)
   assert.equal(view.getPercent(),percent);assert.ok(Math.abs(win.webContents.getZoomFactor()-percent/100)<.001)
   const position=await js(`(()=>{const b=document.getElementById('nova-window-menu').getBoundingClientRect();return {x:Math.round(b.left),y:Math.round(b.bottom),innerWidth,header:document.querySelector('.nova-window-titlebar').getBoundingClientRect().height}})()`)
   assert.ok(Math.abs(position.innerWidth*percent/100-1100)<3)
   scales.push({percent,position})
  }
  await openMenu();assert.equal(currentMenu.getMenuItemById(direction).enabled,false);closeMenu();await pause(40)
  fs.writeFileSync(path.join(output,'scale-'+view.getPercent()+'.png'),(await win.webContents.capturePage()).toPNG())
 }
 await openMenu();currentMenu.getMenuItemById('actualSize').click();closeMenu();await pause(80);assert.equal(view.getPercent(),100)
 checks.push('File invokes New project; View applies exact 50–150% page zoom in ten-point steps, disables limits and resets to 100%')
 await openMenu();currentMenu.getMenuItemById('quit').click();assert.equal(quits,1);closeMenu()
 checks.push('ES/EN menu structure and all seven edit roles are correct; Quit invokes normal app shutdown')
 assert.deepEqual(errors,[]);host.dispose()
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',checks,themes,scales},null,2));app.exit(0)
}catch(error){host.dispose();fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:String(error.stack),errors,checks},null,2));app.exit(1)}})
