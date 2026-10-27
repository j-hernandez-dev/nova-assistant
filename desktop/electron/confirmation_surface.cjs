const crypto = require('node:crypto')
const { surfaceDocument, surfaceScale, surfaceBounds, applySurfaceZoom } = require('./surface_appearance.cjs')
const READY = 'confirmation-surface-ready', DECIDE = 'confirmation-surface-decision'
const HTML = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none';script-src 'none';style-src 'unsafe-inline';connect-src 'none';img-src 'none';object-src 'none';base-uri 'none';form-action 'none'"><title>Nova</title><style>
html{color-scheme:dark}*{box-sizing:border-box}html,body{margin:0;height:100%;background:#151413;color:#ede9e3;font:14px/1.55 system-ui,sans-serif}body{border:1px solid #9b7b50;border-radius:12px;overflow:hidden}main{display:flex;flex-direction:column;gap:16px;height:100%;padding:24px}header{display:flex;align-items:center;gap:12px}.mark{color:#d5ad71;font-weight:700;font-size:13px}h1{font-size:18px;margin:0}p{margin:0;color:#c9c2b7;white-space:pre-wrap;overflow-wrap:anywhere}.content{flex:1;overflow:auto;min-height:0;scrollbar-gutter:stable;overscroll-behavior:contain}#path{font-size:12px;margin-top:14px;color:#a79b89}footer{display:flex;justify-content:flex-end;gap:10px}button{padding:9px 18px;border:1px solid #796548;border-radius:8px;background:#30291f;color:#f5f0e8;font:inherit;cursor:pointer}#confirm{background:#d5ad71;color:#1c170f;font-weight:600}button:focus-visible{outline:2px solid #d5ad71;outline-offset:3px}button:disabled{opacity:.5;cursor:default}
</style></head><body><main aria-labelledby="heading"><header><span class="mark">NOVA</span><h1 id="heading"></h1></header><div class="content"><p id="message"></p><p id="path"></p><label id="delete-files-option" hidden style="margin-top:14px;align-items:center;gap:8px"><input id="delete-files" type="checkbox" style="accent-color:var(--accent,#d5ad71)"><span id="delete-files-label"></span></label></div><footer><button id="cancel" disabled></button><button id="confirm" disabled></button></footer></main></body></html>`

function createConfirmationSurface({BrowserWindow,ipcMain,getParent,getLocale,preloadPath,getPresentation}) {
  let active = null, disposed = false
  const sender = (event,record) => !!record && !record.window.isDestroyed() && event.sender === record.window.webContents && event.senderFrame === record.window.webContents.mainFrame
  const valid = record => { try { return record.validate() === true && !record.parent.isDestroyed() } catch { return false } }
  function close(record, confirmed=false, deleteAssociatedFiles=false) {
    if (!record || active !== record) return
    active = null
    clearTimeout(record.timer)
    for(const [name,handler] of record.listeners)record.parent.removeListener(name,handler)
    if(!record.window.isDestroyed())record.window.destroy()
    record.resolve({confirmed,canceled:!confirmed,...(record.kind==='remove-project'?{deleteAssociatedFiles:confirmed&&deleteAssociatedFiles}:{})})
  }
  function position(record) {
    if(!valid(record))return close(record)
    applySurfaceZoom(record.window,record.parent)
    record.window.setBounds(surfaceBounds(record.parent,640,320))
  }
  function request({kind,projectName='',path='',folderId='',fileCount=0,restartRequired=false,validate}) {
    if(disposed || active || !['remove-project','clear-chat','clear-all','memory-import','memory-export-sensitive','memory-sensitive-access','memory-reveal-sensitive','memory-write-sensitive','memory-classify-sensitive','memory-classify-normal','memory-delete-records','storage-delete-folder','storage-delete-files','sources-delete-files','storage-restart'].includes(kind))return Promise.resolve({confirmed:false,canceled:true})
    const parent=getParent()
    if(!parent || parent.isDestroyed() || !parent.isVisible() || parent.isMinimized())return Promise.resolve({confirmed:false,canceled:true})
    return new Promise(resolve=>{
      let child,record
      try {
        child=new BrowserWindow({parent,modal:true,frame:false,show:false,...surfaceBounds(parent,640,320),resizable:false,movable:false,
          minimizable:false,maximizable:false,fullscreenable:false,skipTaskbar:true,title:'Nova',backgroundColor:getPresentation?.()?.variables?.['--panel'] || '#151413',
          webPreferences:{preload:preloadPath,sandbox:true,contextIsolation:true,nodeIntegration:false,webviewTag:false,zoomFactor:surfaceScale(parent),
            nodeIntegrationInSubFrames:false,nodeIntegrationInWorker:false,devTools:false,webSecurity:true,disableDialogs:true,partition:'nova-confirmation-surface'}})
        record={window:child,parent,resolve,validate,kind,projectName,path,folderId,fileCount,restartRequired,nonce:crypto.randomBytes(32).toString('hex'),ready:false,listeners:[],timer:null}
        active=record
        child.setMenu(null);child.webContents.setWindowOpenHandler(()=>({action:'deny'}))
        child.webContents.session.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false))
        child.webContents.session.setPermissionCheckHandler(()=>false)
        const prevent=event=>event.preventDefault()
        child.webContents.on('will-navigate',prevent);child.webContents.on('will-frame-navigate',prevent);child.webContents.on('will-attach-webview',prevent)
        let started=false
        child.webContents.on('did-start-navigation',(_e,_url,_inPlace,main)=>{if(!main)return;if(started)close(record);else started=true})
        child.webContents.on('render-process-gone',()=>close(record));child.on('closed',()=>close(record))
        for(const name of ['move','resize','maximize','unmaximize']){const handler=()=>position(record);parent.on(name,handler);record.listeners.push([name,handler])}
        const parentClosed=()=>close(record);parent.on('closed',parentClosed);record.listeners.push(['closed',parentClosed])
        position(record)
        record.timer=setTimeout(()=>close(record),120000);record.timer.unref?.()
        Promise.resolve(child.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(surfaceDocument(HTML,getPresentation?.())))).catch(()=>close(record))
      }catch{if(record&&active===record)close(record);else{child?.destroy();resolve({confirmed:false,canceled:true})}}
    })
  }
  ipcMain.handle(READY,event=>{
    const record=active
    if(!sender(event,record)||record.ready||!valid(record))return {accepted:false}
    record.ready=true;position(record);record.window.show()
    return {accepted:true,nonce:record.nonce,kind:record.kind,projectName:record.projectName,path:record.path,folderId:record.folderId,fileCount:record.fileCount,restartRequired:record.restartRequired,locale:getLocale(),presentation:getPresentation?.()}
  })
  ipcMain.handle(DECIDE,(event,payload)=>{
    const record=active
    if(!sender(event,record)||!record.ready||!payload||Object.keys(payload).some(key=>!['confirmed','nonce',...(record.kind==='remove-project'?['deleteAssociatedFiles']:[])].includes(key))||
       (payload.deleteAssociatedFiles!==undefined&&typeof payload.deleteAssociatedFiles!=='boolean')||
       typeof payload.confirmed!=='boolean'||payload.nonce!==record.nonce)return {accepted:false}
    if(!valid(record)){close(record);return {accepted:false}}
    close(record,payload.confirmed,payload.deleteAssociatedFiles===true);return {accepted:true}
  })
  return {request,isPending:()=>!!active,sync(){if(active&&!valid(active))close(active)},
    updateLocale(){if(active?.ready)active.window.webContents.send('confirmation-surface-locale',getLocale())},
    updateAppearance(){if(active&&!active.window.isDestroyed()){
      position(active)
      if(!active)return
      const presentation=getPresentation?.()
      if(presentation?.variables?.['--panel'])active.window.setBackgroundColor?.(presentation.variables['--panel'])
      if(active.ready)active.window.webContents.send('confirmation-surface-appearance',presentation)
    }},
    dispose(){disposed=true;close(active);ipcMain.removeHandler(READY);ipcMain.removeHandler(DECIDE)}}
}
module.exports={createConfirmationSurface,HTML,READY,DECIDE}
