const {test}=require('node:test'),assert=require('node:assert/strict')
const {desktopMenuTemplate,createDesktopMenu}=require('../electron/desktop_menu.cjs')
test('File, View, Edit and Quit expose the requested ES/EN actions with native editing roles',()=>{
  let closed=0
  for(const locale of ['es','en']){
    const template=desktopMenuTemplate(locale,{quit:()=>closed++,newProject(){},zoomIn(){},zoomOut(){},actualSize(){}},{platform:'win32'}),items=template.filter(item=>item.type!=='separator')
    assert.deepEqual(items.map(item=>item.label),locale==='es'?['Archivo','Editar','Ver','Cerrar Nova']:['File','Edit','View','Quit Nova'])
    assert.equal(items[0].submenu[0].label,locale==='es'?'Nuevo proyecto…':'New project…')
    assert.deepEqual(items[2].submenu.map(item=>item.label),locale==='es'?['Acercar','Alejar','Tamaño real']:['Zoom in','Zoom out','Actual size'])
    const actions=items[1].submenu.filter(item=>item.type!=='separator')
    assert.deepEqual(actions.map(item=>item.role),['undo','redo','cut','copy','paste','delete','selectAll'])
    assert.deepEqual(actions.map(item=>item.label),locale==='es'?['Deshacer','Rehacer','Cortar','Copiar','Pegar','Eliminar','Seleccionar todo']:['Undo','Redo','Cut','Copy','Paste','Delete','Select all'])
    assert.ok(actions.every(item=>item.registerAccelerator===false));items[3].click()
  }
  assert.equal(closed,2)
})

test('View disables only the exhausted direction and scales native popup coordinates from CSS pixels',async()=>{
  let percent=100,menu,adds=0,canAdd=true
  const window={isDestroyed:()=>false,webContents:{isDestroyed:()=>false,isLoadingMainFrame:()=>false}}
  const Menu={buildFromTemplate:template=>menu={template,popup(options){this.options=options},closePopup(){}}}
  const host=createDesktopMenu({Menu,getWindow:()=>window,getLocale:()=> 'es',quit(){},newProject(){adds++},canAddProject:()=>canAdd,
    view:{getPercent:()=>percent,change:direction=>percent+=direction==='in'?10:-10,reset:()=>percent=100}})
  host.setReady(true)
  for(const value of [50,100,150]){
    percent=value;const opened=host.open({x:9,y:44})
    assert.equal(menu.options.x,Math.round(9*value/100));assert.equal(menu.options.y,Math.round(44*value/100))
    const view=menu.template.find(item=>item.id==='view').submenu
    assert.equal(view[0].enabled,value<150);assert.equal(view[1].enabled,value>50)
    view[2].click();assert.equal(percent,100)
    menu.options.callback();await opened
  }
  const opened=host.open({x:9,y:44}),add=menu.template[0].submenu[0]
  canAdd=false;add.click();assert.equal(adds,0)
  canAdd=true;add.click();assert.equal(adds,1)
  host.setReady(false);add.click();assert.equal(adds,1)
  await opened
})
test('Host rejects startup, reload and invalid requests independently of the disabled titlebar button',async()=>{
  let popup=0,loading=false
  const window={isDestroyed:()=>false,webContents:{isDestroyed:()=>false,isLoadingMainFrame:()=>loading}}
  const Menu={buildFromTemplate:()=>({popup(){popup++},closePopup(){}})}
  const host=createDesktopMenu({Menu,getWindow:()=>window,getLocale:()=> 'es',quit(){}})
  assert.deepEqual(await host.open({x:9,y:44}),{opened:false});assert.equal(popup,0)
  host.setReady(true)
  for(const position of [null,{x:-1,y:44},{x:9,y:NaN},{x:9,y:10000},{x:'9',y:44}])assert.deepEqual(await host.open(position),{opened:false})
  loading=true;assert.deepEqual(await host.open({x:9,y:44}),{opened:false});assert.equal(popup,0)
})
test('A popup keeps one lifecycle and closes on loading or shutdown without an uncaught native-window exception',async()=>{
  let menu,closed=0
  const window={isDestroyed:()=>false,webContents:{isDestroyed:()=>false,isLoadingMainFrame:()=>false}}
  const Menu={buildFromTemplate:()=>menu={popup(options){this.options=options},closePopup(){closed++;throw Error('window closing')}}}
  const host=createDesktopMenu({Menu,getWindow:()=>window,getLocale:()=> 'en',quit(){}})
  host.setReady(true);const result=host.open({x:9,y:44})
  assert.deepEqual(await host.open({x:9,y:44}),{opened:false})
  assert.equal(menu.options.window,window);host.setReady(false)
  assert.deepEqual(await result,{opened:true});assert.equal(closed,1)
  host.dispose();assert.equal(closed,1)
})
