require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict')
const {createStartupScreen,startupLocale,STARTUP_WAIT_MS}=require('../shared/startup_screen.ts')
function setup(locale='es',reducedMotion=false,showStartupScreen=true){
  const calls={cancelled:[],reload:0,removed:0},listeners={},screenListeners={},timers=new Map()
  const attributes={inert:'', 'aria-hidden':'true'}
  const action={hidden:true,textContent:'',ownerDocument:{activeElement:null},
    addEventListener:(name,fn)=>{listeners[name]=fn},removeEventListener:name=>{delete listeners[name]}}
  const screen={setAttribute:(key,value)=>{calls[key]=value},remove:()=>{calls.removed++},
    addEventListener:(name,fn)=>{screenListeners[name]=fn},removeEventListener:name=>{delete screenListeners[name]}}
  const root={removeAttribute:key=>{delete attributes[key]},querySelector:()=>null}
  const message={textContent:''},hint={textContent:''}
  let timerId=0
  const controller=createStartupScreen({screen,root,message,hint,action},locale,{
    schedule:(fn,delay)=>{timers.set(++timerId,fn);calls.delay=delay;return timerId},
    cancel:id=>{calls.cancelled.push(id);timers.delete(id)},reload:()=>calls.reload++,reducedMotion:()=>reducedMotion,showStartupScreen})
  return {controller,calls,attributes,action,message,hint,
    expire:()=>{const next=timers.entries().next().value;if(next){timers.delete(next[0]);next[1]()}},
    transition:(propertyName='opacity',target=screen)=>screenListeners.transitionend?.({propertyName,target}),
    click:()=>listeners.click?.()}
}
test('startup reads only the explicit host locale and localizes both languages before React',()=>{
  assert.equal(startupLocale(['--nova-desktop-locale=en']),'en')
  assert.equal(startupLocale(['--nova-desktop-locale=fr']),'es')
  const es=setup(),en=setup('en')
  assert.equal(es.message.textContent,'Iniciando Nova…');assert.equal(en.message.textContent,'Starting Nova…')
  assert.equal(es.action.hidden,true);assert.equal(en.action.hidden,true)
  assert.equal(es.calls.delay,STARTUP_WAIT_MS)
})
test('ready reveals the UI below the fading overlay and removes startup exactly once',()=>{
  const f=setup();f.controller.update('mounted');f.controller.update('ready');f.controller.update('ready')
  assert.equal(f.calls.removed,0);assert.equal(f.calls['data-leaving'],'true')
  assert.equal(f.calls['aria-hidden'],'true');assert.equal(f.calls.inert,'')
  assert.deepEqual(f.attributes,{})
  f.transition('transform');f.transition('opacity',{});assert.equal(f.calls.removed,0)
  f.transition();f.transition();f.expire()
  assert.equal(f.calls.removed,1);assert.equal(f.calls.reload,0);assert.ok(f.calls.cancelled.includes(1))
})
test('a missing renderer bundle offers a manual reload after the bounded wait',()=>{
  const f=setup('en');f.expire()
  assert.equal(f.action.hidden,false);assert.equal(f.action.textContent,'Retry')
  assert.match(f.message.textContent,/longer than usual/);assert.equal(f.calls.reload,0)
  f.click();assert.equal(f.calls.reload,1);assert.equal(f.calls.removed,0)
  assert.equal(f.attributes.inert,'')
})
test('a mounted UI with a slow backend can be opened without restarting or submitting anything',()=>{
  const f=setup();f.controller.update('mounted');f.expire()
  assert.equal(f.action.textContent,'Abrir Nova');f.click()
  assert.equal(f.calls.removed,0);f.transition()
  assert.equal(f.calls.removed,1);assert.equal(f.calls.reload,0);assert.deepEqual(f.attributes,{})
})
test('a renderer that mounts after the timeout changes Retry to Open Nova',()=>{
  const f=setup('en');f.expire();assert.equal(f.action.textContent,'Retry')
  f.controller.update('mounted');assert.equal(f.action.textContent,'Open Nova')
  f.click();f.transition();assert.equal(f.calls.reload,0);assert.equal(f.calls.removed,1)
})
test('a failed entry exposes a localized retry immediately and can still recover',()=>{
  const f=setup();f.controller.update('failed')
  assert.equal(f.action.hidden,false);assert.equal(f.action.textContent,'Reintentar')
  assert.match(f.message.textContent,/No se pudo cargar/);assert.equal(f.calls['aria-busy'],'false')
  assert.equal(f.calls.removed,0);assert.equal(f.calls.reload,0)
  f.controller.update('mounted');f.controller.update('ready');f.transition();assert.equal(f.calls.removed,1)
})
test('unload cancels pending work and old callbacks cannot change the next page',()=>{
  const f=setup(),before=f.message.textContent;f.controller.dispose();f.expire();f.click();f.controller.update('ready')
  assert.equal(f.message.textContent,before);assert.equal(f.calls.reload,0);assert.equal(f.calls.removed,0)
})
test('transition cleanup remains bounded when no transitionend arrives',()=>{
  const f=setup();f.controller.update('ready');assert.equal(f.calls.removed,0)
  f.expire();f.transition();assert.equal(f.calls.removed,1)
})
test('reduced motion reveals the UI immediately without a fading overlay',()=>{
  const f=setup('en',true);f.controller.update('ready')
  assert.equal(f.calls.removed,1);assert.equal(f.calls['data-leaving'],undefined);assert.deepEqual(f.attributes,{})
})
test('unload during the fade cancels its cleanup and ignores stale transition events',()=>{
  const f=setup();f.controller.update('ready');f.controller.dispose();f.expire();f.transition()
  assert.equal(f.calls.removed,0);assert.equal(f.calls.reload,0)
})


test('Hidden loading opens the mounted UI immediately without waiting for backend readiness or a fade',()=>{
  const f=setup('es',false,false)
  f.controller.update('mounted')
  assert.equal(f.calls.removed,1); assert.deepEqual(f.attributes,{})
  assert.equal(f.calls['data-leaving'],undefined); assert.equal(f.calls.reload,0)
  f.controller.update('ready'); f.expire(); assert.equal(f.calls.removed,1)
})
test('Disabling the splash preserves localized manual recovery for a missing or failed renderer',()=>{
  const f=setup('en',false,false); f.expire()
  assert.equal(f.calls['data-startup-recovery'],'true'); assert.equal(f.action.hidden,false)
  assert.equal(f.action.textContent,'Retry'); f.click(); assert.equal(f.calls.reload,1)
  const failed=setup('es',false,false); failed.controller.update('failed')
  assert.equal(failed.calls['data-startup-recovery'],'true'); assert.equal(failed.action.textContent,'Reintentar')
})
