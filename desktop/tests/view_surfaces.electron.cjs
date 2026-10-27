/* Native surface geometry/legibility at every supported UI scale, owned profile only. */
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
const output=path.resolve(process.argv[2]);fs.mkdirSync(output,{recursive:true});app.setPath('userData',path.join(output,'profile'))
app.on('window-all-closed',()=>{})
const {surfaceDocument,surfaceBounds}=require('../electron/surface_appearance.cjs'),{approvalSurfaceBounds}=require('../electron/approval_surface.cjs')
const definitions=[['approval',require('../electron/approval_surface.cjs').APPROVAL_HTML,['deny','allow']],['confirmation',require('../electron/confirmation_surface.cjs').HTML,['cancel','confirm']],['question',require('../electron/question_surface.cjs').HTML,['stop','send']]]
app.whenReady().then(async()=>{const proof=[];try{
 for(const percent of [50,60,70,80,90,100,110,120,130,140,150])for(const size of [{width:600,height:400},{width:1280,height:850}])for(const [name,html,buttons]of definitions){
  const parent={getContentBounds:()=>({x:0,y:0,...size}),webContents:{getZoomFactor:()=>percent/100}}
  const bounds=name==='approval'?approvalSurfaceBounds(parent):surfaceBounds(parent,640,name==='question'?400:320)
  const child=new BrowserWindow({...bounds,show:false,frame:false,webPreferences:{offscreen:true,zoomFactor:percent/100,nodeIntegration:false,contextIsolation:true,sandbox:true}})
  await child.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(surfaceDocument(html)))
  child.webContents.setZoomFactor(percent/100);await new Promise(resolve=>setTimeout(resolve,30))
  assert.ok(Math.abs(child.webContents.getZoomFactor()-percent/100)<.001)
  await child.webContents.executeJavaScript(`document.querySelector('h1').textContent='Confirmar acción';for(const p of document.querySelectorAll('p'))p.textContent='Información de la acción solicitada.';for(const button of document.querySelectorAll('button')){button.textContent=button.id==='allow'||button.id==='confirm'||button.id==='send'?'Confirmar':'Cancelar';button.disabled=false}`)
  const report=await child.webContents.executeJavaScript(`(()=>({height:innerHeight,width:innerWidth,buttons:${JSON.stringify(buttons)}.map(id=>{const b=document.getElementById(id).getBoundingClientRect();return{id,top:b.top,bottom:b.bottom,left:b.left,right:b.right}})}))()`)
  for(const button of report.buttons)assert.ok(button.top>=0&&button.bottom<=report.height+1&&button.left>=0&&button.right<=report.width+1,JSON.stringify({percent,size,name,report}))
  proof.push({percent,size,name,bounds});child.destroy()
 }
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',cases:proof.length,proof},null,2));app.exit(0)
}catch(error){fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:String(error.stack),passed:proof.length},null,2));app.exit(1)}})
