const labels={
  es:{file:'Archivo',newProject:'Nuevo proyecto…',edit:'Editar',view:'Ver',zoomIn:'Acercar',zoomOut:'Alejar',actualSize:'Tamaño real',quit:'Cerrar Nova',undo:'Deshacer',redo:'Rehacer',cut:'Cortar',copy:'Copiar',paste:'Pegar',delete:'Eliminar',selectAll:'Seleccionar todo'},
  en:{file:'File',newProject:'New project…',edit:'Edit',view:'View',zoomIn:'Zoom in',zoomOut:'Zoom out',actualSize:'Actual size',quit:'Quit Nova',undo:'Undo',redo:'Redo',cut:'Cut',copy:'Copy',paste:'Paste',delete:'Delete',selectAll:'Select all'},
}
function desktopMenuTemplate(locale,actions,{platform=process.platform,zoomPercent=100,canAddProject=true}={}){
  const t=labels[locale==='en'?'en':'es']
  const item=(role,accelerator)=>({id:role,label:t[role],role,accelerator,registerAccelerator:false})
  return [
    {id:'file',label:t.file,submenu:[{id:'newProject',label:t.newProject,enabled:canAddProject,click:actions.newProject}]},
    {id:'edit',label:t.edit,submenu:[
      item('undo','CommandOrControl+Z'),item('redo',platform==='darwin'?'Command+Shift+Z':'Control+Y'),
      {type:'separator'},item('cut','CommandOrControl+X'),item('copy','CommandOrControl+C'),item('paste','CommandOrControl+V'),
      item('delete','Delete'),{type:'separator'},item('selectAll','CommandOrControl+A'),
    ]},
    {id:'view',label:t.view,submenu:[
      {id:'zoomIn',label:t.zoomIn,enabled:zoomPercent<150,click:actions.zoomIn},
      {id:'zoomOut',label:t.zoomOut,enabled:zoomPercent>50,click:actions.zoomOut},
      {id:'actualSize',label:t.actualSize,click:actions.actualSize},
    ]},{type:'separator'},{id:'quit',label:t.quit,click:actions.quit},
  ]
}

/** Native roles operate on Chromium's focused editor and preserve its undo stack. */
function createDesktopMenu({Menu,getWindow,getLocale,quit,newProject=()=>{},canAddProject=()=>true,view}){
  let ready=false,active=null,finish=null
  function close(){
    const menu=active
    active=null
    if(menu){try{const window=getWindow();menu.closePopup(window&&!window.isDestroyed()?window:undefined)}catch{/* The native window may already be closing. */}}
    if(finish){const done=finish;finish=null;done({opened:true})}
  }
  return{
    setReady(value){ready=value===true;if(!ready)close()},
    open(position){
      const window=getWindow()
      if(!ready||active||!window||window.isDestroyed()||window.webContents.isDestroyed()||window.webContents.isLoadingMainFrame()||
        !position||!Number.isSafeInteger(position.x)||!Number.isSafeInteger(position.y)||position.x<0||position.y<0||position.x>10000||position.y>500)
        return Promise.resolve({opened:false})
      return new Promise(resolve=>{
        try{
          // Recheck when clicked: state may have changed while a native menu was open.
          const run=callback=>()=>{
            if(!ready||getWindow()!==window||window.isDestroyed()||window.webContents.isDestroyed()||window.webContents.isLoadingMainFrame())return
            try{Promise.resolve(callback()).catch(()=>{})}catch{/* A closing host declines the action. */}
          }
          const percent=view?.getPercent()||100
          const menu=Menu.buildFromTemplate(desktopMenuTemplate(getLocale(),{
            quit:run(quit),newProject:run(()=>canAddProject()?newProject():undefined),
            zoomIn:run(()=>view?.change('in')),zoomOut:run(()=>view?.change('out')),actualSize:run(()=>view?.reset()),
          },{zoomPercent:percent,canAddProject:canAddProject()}))
          active=menu;finish=resolve
          // getBoundingClientRect uses CSS pixels; Electron popup coordinates are DIPs.
          menu.popup({window,x:Math.round(position.x*percent/100),y:Math.round(position.y*percent/100),callback(){if(active===menu){active=null;finish=null;resolve({opened:true})}}})
        }catch{active=null;finish=null;resolve({opened:false})}
      })
    },
    dispose(){ready=false;close()},
  }
}
module.exports={desktopMenuTemplate,createDesktopMenu}
