const {test}=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events')
const {createConfirmationSurface,READY,DECIDE}=require('../electron/confirmation_surface.cjs')
const {createProjectChatClient}=require('../electron/project_chats.cjs')
function fixture(t){
  const handlers=new Map(),windows=[];let current=true
  class Window extends EventEmitter{
    constructor(options={}){super();this.options=options;this.destroyed=false;windows.push(this)
      this.webContents=new EventEmitter();Object.assign(this.webContents,{mainFrame:{},setWindowOpenHandler(){},
        send(){},session:{setPermissionRequestHandler(){},setPermissionCheckHandler(){}}})}
    setMenu(){} getContentBounds(){return{x:10,y:10,width:1000,height:700}} setBounds(bounds){this.bounds=bounds}
    isDestroyed(){return this.destroyed}isVisible(){return true}isMinimized(){return false}show(){this.shown=true}
    destroy(){this.destroyed=true;this.emit('closed')}loadURL(url){this.url=url;this.webContents.emit('did-start-navigation',{},url,false,true);return Promise.resolve()}
  }
  const parent=new Window(),controller=createConfirmationSurface({BrowserWindow:Window,
    ipcMain:{handle:(name,fn)=>handlers.set(name,fn),removeHandler:name=>handlers.delete(name)},
    getParent:()=>parent,getLocale:()=>'es',preloadPath:'/trusted/confirmation_preload.js'})
  t.after(()=>controller.dispose())
  const invoke=(name,window,payload,frame=window.webContents.mainFrame)=>handlers.get(name)({sender:window.webContents,senderFrame:frame},payload)
  return {parent,controller,windows,invoke,request:()=>controller.request({kind:'remove-project',projectName:'<project>',path:'/owned',validate:()=>current}),
    child:()=>windows.at(-1),invalidate(){current=false;controller.sync()}}
}
test('confirmation has one modal host binding and the main renderer or a subframe cannot accept it',async t=>{
  const f=fixture(t),decision=f.request()
  assert.equal((await f.request()).confirmed,false);assert.equal(f.windows.length,2)
  assert.equal(f.child().options.modal,true);assert.equal(f.child().options.webPreferences.sandbox,true)
  assert.equal(f.invoke(READY,f.parent).accepted,false);assert.equal(f.invoke(READY,f.child(),undefined,{}).accepted,false)
  const binding=f.invoke(READY,f.child());assert.equal(binding.projectName,'<project>')
  assert.equal(f.invoke(DECIDE,f.parent,{nonce:binding.nonce,confirmed:true}).accepted,false)
  assert.equal(f.invoke(DECIDE,f.child(),{nonce:'wrong',confirmed:true}).accepted,false)
  assert.equal(f.invoke(DECIDE,f.child(),{nonce:binding.nonce,confirmed:true,path:'/other'}).accepted,false)
  assert.equal(f.invoke(DECIDE,f.child(),{nonce:binding.nonce,confirmed:true}).accepted,true)
  assert.equal((await decision).confirmed,true)
  assert.equal(f.invoke(DECIDE,f.child(),{nonce:binding.nonce,confirmed:true}).accepted,false)
})
test('cancel, close and a changed project invalidate confirmation without destructive work',async t=>{
  for(const action of ['cancel','close','changed']){
    const f=fixture(t),decision=f.request(),binding=f.invoke(READY,f.child())
    if(action==='cancel')f.invoke(DECIDE,f.child(),{nonce:binding.nonce,confirmed:false})
    if(action==='close')f.child().destroy()
    if(action==='changed')f.invalidate()
    assert.deepEqual(await decision,{confirmed:false,canceled:true});assert.equal(f.controller.isPending(),false)
  }
})
test('project chat transport correlates exact responses and disconnect resolves requests without replay',async()=>{
  const frames=[],client=createProjectChatClient({send:frame=>frames.push(frame),getView:()=>({status:{ready:true}})})
  const list=client.list(['/a','/b']),frame=frames.at(-1)
  assert.equal(client.receive({id:frame.id,type:'clear_project_chat',success:true}),false)
  assert.equal(client.receive({id:'other',type:'project_chats',success:true}),false)
  client.receive({id:frame.id,type:'project_chats',success:true,chats:[]});assert.equal((await list).success,true)
  const clear=client.clear('/a');assert.equal(client.busy(),true);client.disconnected()
  assert.equal((await clear).success,false);assert.equal(client.busy(),false);assert.equal(frames.length,2)
})

test('project chat error frames settle the exact owner and late replies never leak into chat',async t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  const sent=[],client=createProjectChatClient({send:f=>sent.push(f),getView:()=>({status:{ready:true}})})
  const result=client.list(['/owned']),id=sent.at(-1).id
  assert.equal(client.receive({id:'unrelated',type:'error',code:'OTHER'}),false)
  assert.equal(client.receive({id,type:'error',code:'CONFLICT_ACTIVE_TURN'}),true)
  assert.equal((await result).error.code,'CONFLICT_ACTIVE_TURN')
  assert.equal(client.receive({id,type:'error',code:'LATE'}),true)
  const timed=client.clear('/owned'),second=sent.at(-1).id
  t.mock.timers.tick(15001)
  assert.equal((await timed).error.code,'PROJECT_CHAT_UNKNOWN')
  assert.equal(client.receive({id:second,type:'error',code:'LATE'}),true)
  client.disconnected()
})
