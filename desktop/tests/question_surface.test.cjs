const {test}=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events')
const {createQuestionSurface,questionBounds,captureQuestion,READY,DECIDE}=require('../electron/question_surface.cjs')
function fixture(){
  let clock=Date.parse('2030-01-01T00:00:00Z'),locale='es',allowed=true,receipt={accepted:true}
  const windows=[],handlers=new Map(),timers=new Map(),sent=[];let tid=0
  class Window extends EventEmitter{
    constructor(options={}){super();this.options=options;this.bounds={x:20,y:30,width:1000,height:650};this.destroyed=false;this.visible=!options.parent;this.messages=[]
      this.webContents=new EventEmitter();Object.assign(this.webContents,{mainFrame:{},send:(...args)=>this.messages.push(args),setWindowOpenHandler(){},
        session:{setPermissionRequestHandler(){},setPermissionCheckHandler(){}}});windows.push(this)}
    isDestroyed(){return this.destroyed}isVisible(){return this.visible}isMinimized(){return false}getContentBounds(){return this.bounds}setBounds(b){this.bounds=b}
    show(){this.visible=true}hide(){this.visible=false}setMenu(){}destroy(){this.destroyed=true;this.visible=false;this.emit('closed')}
    loadURL(){this.webContents.emit('did-start-navigation',{},'',false,true);return Promise.resolve()}
  }
  const parent=new Window(),client={view:{sessionId:'session',workspace:'C:/owned',status:{ready:true,connected:true},activeTurnId:'turn',
    inputs:[{inputRequestId:'input',turnId:'turn',question:'¿Continuar?',deadline:'2030-01-01T00:01:00Z'}]},
    command:(...args)=>{sent.push(args);return typeof receipt==='function'?receipt(...args):Promise.resolve(receipt)}}
  const controller=createQuestionSurface({BrowserWindow:Window,ipcMain:{handle:(n,f)=>handlers.set(n,f),removeHandler:n=>handlers.delete(n)},client,
    getParent:()=>parent,getLocale:()=>locale,canOpen:()=>allowed,preloadPath:'owned/question_preload.js',now:()=>clock,
    setTimeout:(fn,ms)=>{timers.set(++tid,{fn,ms});return tid},clearTimeout:id=>timers.delete(id)})
  const child=()=>windows.at(-1)
  const invoke=(channel,window=child(),payload,frame=window.webContents.mainFrame)=>handlers.get(channel)({sender:window.webContents,senderFrame:frame},payload)
  controller.sync()
  return {controller,client,parent,windows,timers,sent,child,invoke,ready:()=>invoke(READY),answer:(binding,response='Sí.\nSegunda línea.',window=child())=>invoke(DECIDE,window,{nonce:binding.nonce,action:'answer',response}),
    locale:value=>locale=value,allowed:value=>allowed=value,receipt:value=>receipt=value,advance:ms=>clock+=ms}
}
test('Question uses one real modal child across snapshots, with confirmation styling and bounded native geometry',()=>{
  const f=fixture();for(let i=0;i<10;i++)f.controller.sync()
  assert.equal(f.windows.length,2);assert.equal(f.child().options.parent,f.parent);assert.equal(f.child().options.modal,true)
  assert.equal(f.child().options.frame,false);assert.equal(f.child().options.backgroundColor,'#151413')
  const b=f.ready();assert.equal(b.accepted,true);assert.equal(b.question,'¿Continuar?');assert.equal(f.child().visible,true)
  f.parent.bounds={x:20,y:30,width:600,height:361};f.parent.emit('resize')
  const bounds=f.child().bounds;assert.ok(bounds.width<=568&&bounds.height<=329);assert.ok(bounds.x>=20&&bounds.y>=30)
  assert.deepEqual(bounds,questionBounds(f.parent))
})
test('Main renderer, a subframe, wrong nonce, blank response and extra fields cannot answer a native question',async()=>{
  const f=fixture(),b=f.ready(),valid={nonce:b.nonce,action:'answer',response:'yes'}
  for(const [window,payload,frame] of [[f.parent,valid],[f.child(),valid,{}],[f.child(),{...valid,nonce:'wrong'}],
    [f.child(),{...valid,response:'  '}],[f.child(),{...valid,inputRequestId:'other'}]]){
    assert.equal((await f.invoke(DECIDE,window,payload,frame)).accepted,false)
  }
  assert.equal(f.sent.length,0);assert.equal(f.child().destroyed,false)
})
test('A raw multiline answer is dispatched once to the host-captured request and cannot reopen before its snapshot arrives',async()=>{
  const f=fixture(),b=f.ready(),child=f.child();let resolve
  f.receipt(()=>new Promise(r=>resolve=r))
  const pending=f.answer(b);assert.equal((await f.answer(b)).accepted,false);assert.equal(f.sent.length,1)
  assert.equal(f.sent[0][0],'ResolveUserInput');assert.deepEqual(f.sent[0][1],{inputRequestId:'input',response:'Sí.\nSegunda línea.'})
  resolve({accepted:true});assert.equal((await pending).accepted,true);assert.equal(child.destroyed,true)
  for(let i=0;i<4;i++)f.controller.sync();assert.equal(f.windows.length,2)
})
test('A rejected receipt leaves the exact pending question open and permits a deliberate retry',async()=>{
  const f=fixture(),b=f.ready();f.receipt({accepted:false})
  assert.equal((await f.answer(b)).accepted,false);assert.equal(f.child().destroyed,false)
  f.receipt({accepted:true});assert.equal((await f.answer(b)).accepted,true);assert.equal(f.sent.length,2)
})
test('Stop remains available during a pending answer and targets only its captured turn',async()=>{
  const f=fixture(),b=f.ready();let resolve
  f.receipt(kind=>kind==='ResolveUserInput'?new Promise(r=>resolve=r):Promise.resolve({accepted:true}))
  const pending=f.answer(b)
  assert.equal((await f.invoke(DECIDE,f.child(),{nonce:b.nonce,action:'stop'})).accepted,true)
  assert.deepEqual(f.sent[1].slice(0,2),['CancelTurn',{turnId:'turn'}]);resolve({accepted:false});await pending
})
for(const [field,change] of [['session',f=>f.client.view.sessionId='other'],['project',f=>f.client.view.workspace='other'],
  ['turn',f=>f.client.view.activeTurnId='other'],['request',f=>f.client.view.inputs=[]],['disconnect',f=>f.client.view.status.connected=false],
  ['expiry',f=>f.advance(61000)]])test('A changed '+field+' invalidates the native question without sending a response',async()=>{
  const f=fixture(),b=f.ready(),old=f.child();change(f);f.controller.sync()
  assert.equal(old.destroyed,true);assert.equal((await f.answer(b,'stale',old)).accepted,false);assert.equal(f.sent.length,0)
})
test('A manually closed native question is suppressed until explicit reopen and gets a fresh nonce',async()=>{
  const f=fixture(),b=f.ready(),old=f.child();old.destroy();f.controller.sync();assert.equal(f.windows.length,2)
  const opened=f.controller.reopenPending();const next=f.ready();assert.equal((await opened).success,true)
  assert.notEqual(next.nonce,b.nonce);assert.equal((await f.answer(b,'stale',old)).accepted,false)
})
test('A question waits for other host dialogs; locale updates preserve the existing child and disposal removes handlers',()=>{
  const f=fixture(),child=f.child();f.ready();f.locale('en');f.controller.updateLocale()
  assert.deepEqual(child.messages.at(-1),['question-surface-locale','en'])
  f.allowed(false);f.controller.sync();assert.equal(child.destroyed,true)
  f.allowed(true);f.controller.sync();assert.equal(f.windows.length,3)
  f.ready();f.controller.dispose();assert.equal(f.child().destroyed,true);assert.equal(f.timers.size,0)
  assert.equal(captureQuestion({...f.client.view,status:{ready:false,connected:true}}),null)
})
