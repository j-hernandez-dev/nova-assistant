const {test}=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events')
const fs=require('node:fs'),path=require('node:path'),os=require('node:os')
const {createDesktopView,validZoomPercent}=require('../electron/desktop_view.cjs')
const {createDesktopPreferencesStore}=require('../electron/desktop_preferences.cjs')
const {createDesktopMenu}=require('../electron/desktop_menu.cjs')
const {createProjectsHost}=require('../electron/projects_host.cjs')
const {surfaceBounds,surfaceScale}=require('../electron/surface_appearance.cjs')
function owned(t){const root=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-view-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root}
function windowFixture(){const contents=new EventEmitter();let factor=1,limits
  Object.assign(contents,{isDestroyed:()=>false,setZoomFactor:value=>factor=value,setVisualZoomLevelLimits:(...args)=>{limits=args;return Promise.resolve()}})
  const window=new EventEmitter();Object.assign(window,{webContents:contents,isDestroyed:()=>false})
  return{window,contents,factor:()=>factor,limits:()=>limits}}

test('Zoom has exactly eleven integer percentages, defaults to 100%, and never exceeds five steps each way',()=>{
  const f=windowFixture(),saved=[],view=createDesktopView({getWindow:()=>f.window,savePercent:value=>saved.push(value)})
  view.attach(f.window);assert.equal(f.factor(),1);assert.deepEqual(f.limits(),[1,1])
  for(const value of [110,120,130,140,150]){assert.equal(view.change('in'),true);assert.equal(view.getPercent(),value);assert.equal(f.factor(),value/100)}
  assert.equal(view.change('in'),false);assert.equal(view.reset(),true);assert.equal(f.factor(),1)
  for(const value of [90,80,70,60,50]){view.change('out');assert.equal(view.getPercent(),value);assert.equal(f.factor(),value/100)}
  assert.equal(view.change('out'),false);assert.equal(view.change('invalid'),false)
  f.contents.setZoomFactor(1.2);f.contents.emit('did-finish-load');assert.equal(f.factor(),.5)
  let prevented=false;f.contents.emit('zoom-changed',{preventDefault(){prevented=true}},'in');assert.equal(prevented,true);assert.equal(f.factor(),.6)
  f.window.emit('closed');assert.equal(f.contents.listenerCount('zoom-changed'),0);assert.equal(f.contents.listenerCount('did-finish-load'),0)
  assert.deepEqual(saved,[110,120,130,140,150,100,90,80,70,60,50,60])
  assert.deepEqual(Array.from({length:101},(_,index)=>index+50).filter(validZoomPercent),[50,60,70,80,90,100,110,120,130,140,150])
})

test('Zoom survives restart and unrelated preference saves; invalid/legacy values return to real size without rewriting',t=>{
  const root=owned(t),store=createDesktopPreferencesStore(root)
  assert.equal(store.get().zoomPercent,100);assert.equal(store.setZoomPercent(140).success,true)
  store.setLocale('en');store.setGeneral({language:'es',autoSwitchView:true,transitionsEnabled:false,showFiles:false})
  assert.equal(createDesktopPreferencesStore(root).get().zoomPercent,140)
  for(const value of [0,49,51,155,200,'110',NaN,Infinity,undefined])assert.equal(store.setZoomPercent(value).success,false)
  assert.equal(store.get().zoomPercent,140)
  for(const value of [undefined,1000,'150',125]){
    const bytes=JSON.stringify({schemaVersion:1,locale:'es',zoomPercent:value});fs.writeFileSync(path.join(root,'desktop-preferences.json'),bytes)
    assert.equal(createDesktopPreferencesStore(root).get().zoomPercent,100)
    assert.equal(fs.readFileSync(path.join(root,'desktop-preferences.json'),'utf8'),bytes)
  }
})

test('New project from File uses the existing picker and only persists the host-confirmed selected folder',async t=>{
  const root=owned(t),workspace=path.join(root,'workspace'),added=path.join(root,'selected')
  fs.mkdirSync(workspace);fs.mkdirSync(added)
  let canceled=true,picked=0,menu
  const client={view:{workspace,status:{ready:true}},workspaceBusy:()=>false,async changeWorkspace(value){this.view.workspace=value;return{success:true}}}
  const projects=createProjectsHost({directory:path.join(root,'profile'),defaultPath:workspace,client,openPath:async()=>'',chooseDirectory:async()=>{picked++;return{canceled,filePaths:canceled?[]:[added]}}})
  const f=windowFixture();f.contents.isLoadingMainFrame=()=>false
  const Menu={buildFromTemplate:template=>menu={template,popup(options){this.options=options},closePopup(){}}}
  let pending
  const host=createDesktopMenu({Menu,getWindow:()=>f.window,getLocale:()=> 'en',quit(){},newProject:()=>pending=projects.action('add')})
  host.setReady(true)
  let opened=host.open({x:9,y:44});menu.template[0].submenu[0].click();menu.options.callback();await opened;await pending
  assert.equal(picked,1);assert.equal(projects.state().folders.length,1);assert.equal(client.view.workspace,workspace)
  canceled=false;opened=host.open({x:9,y:44});menu.template[0].submenu[0].click();menu.options.callback();await opened;await pending
  assert.equal(projects.state().folders.length,2);assert.equal(projects.state().activePath,added)
  assert.equal(JSON.parse(fs.readFileSync(path.join(root,'profile','project-preferences.json'),'utf8')).activePath,added)
})

test('Host dialogs follow page zoom and stay centered inside the parent content area',()=>{
  for(const factor of [.5,1,1.5])for(const area of [{x:100,y:200,width:1600,height:900},{x:0,y:0,width:600,height:400}]){
    const parent={getContentBounds:()=>area,webContents:{getZoomFactor:()=>factor}}
    assert.equal(surfaceScale(parent),factor)
    const bounds=surfaceBounds(parent,640,320)
    assert.ok(bounds.width<=area.width&&bounds.height<=area.height)
    assert.ok(Math.abs(bounds.x+bounds.width/2-area.x-area.width/2)<1)
    assert.ok(Math.abs(bounds.y+bounds.height/2-area.y-area.height/2)<1)
  }
})
