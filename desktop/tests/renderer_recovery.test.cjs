require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const {createRendererRecovery, RENDERER_PROBE_MS, RENDERER_RELOAD_MS, RENDERER_STABLE_MS} = require('../electron/renderer_recovery.ts')

function setup() {
  let now=0, next=0
  const timers=new Map(), callbacks=[]
  const state={available:true,visible:true,throwPaint:false,throwRefresh:false,repaints:0,refreshes:0,probes:[],reloads:[],reports:[],prompts:[]}
  const controller=createRendererRecovery({
    available:()=>state.available, visible:()=>state.visible,
    repaint:()=>{if(state.throwPaint)throw Error('Unavailable compositor');state.repaints++},
    refresh:()=>{if(state.throwRefresh)throw Error('Unavailable snapshot');state.refreshes++},
    probe:nonce=>state.probes.push(nonce),reload:replace=>state.reloads.push(replace),
    offerRetry:()=>new Promise(resolve=>state.prompts.push(resolve)),report:event=>state.reports.push(event),
    schedule:(callback,delay)=>{timers.set(++next,{at:now+delay,callback});callbacks.push(callback);return next},
    cancel:id=>timers.delete(id),
  })
  function advance(ms) {
    const end=now+ms
    for(;;){const entry=[...timers].filter(([,timer])=>timer.at<=end).sort((a,b)=>a[1].at-b[1].at)[0]
      if(!entry)break;timers.delete(entry[0]);now=entry[1].at;entry[1].callback()}
    now=end
  }
  return {controller,state,advance,timers,callbacks}
}

test('healthy resume repaints and probes the existing UI without reloading or replaying work',()=>{
  const f=setup();f.controller.ready();f.controller.suspend();f.advance(10*RENDERER_STABLE_MS)
  assert.deepEqual(f.state.probes,[])
  f.controller.resume();assert.equal(f.state.refreshes,1);assert.equal(f.state.probes.length,1)
  f.controller.alive(f.state.probes[0]);f.advance(RENDERER_PROBE_MS)
  assert.deepEqual(f.state.reloads,[]);assert.ok(f.state.repaints>=3)
})

test('a missing or invalid probe reply replaces a stuck renderer exactly once',()=>{
  const f=setup();f.controller.ready();f.controller.resume()
  f.controller.alive('wrong-nonce');f.controller.alive(null);f.advance(RENDERER_PROBE_MS)
  assert.deepEqual(f.state.reloads,[true])
  f.controller.alive(f.state.probes[0]);f.controller.ready();f.advance(RENDERER_RELOAD_MS)
  assert.equal(f.state.prompts.length,0);assert.deepEqual(f.state.reloads,[true])
})

test('renderer death recovers even before its first ready and while no probe is pending',()=>{
  const f=setup();f.controller.gone();assert.deepEqual(f.state.reloads,[false])
  f.controller.loading();f.controller.ready();f.advance(RENDERER_RELOAD_MS)
  assert.equal(f.state.prompts.length,0)
})

test('time asleep never counts as a failed probe or reload',()=>{
  const f=setup();f.controller.ready();f.controller.resume();const old=f.state.probes[0]
  f.controller.suspend();f.advance(15*60_000);assert.deepEqual(f.state.reloads,[])
  f.controller.resume();f.controller.alive(old);f.advance(RENDERER_PROBE_MS)
  assert.deepEqual(f.state.reloads,[true])
  f.controller.suspend();f.advance(15*60_000);assert.equal(f.state.prompts.length,0)
  f.controller.resume();f.controller.ready();f.advance(RENDERER_RELOAD_MS)
  assert.equal(f.state.prompts.length,0)
})

test('minimized or hidden windows defer checks until restored, including renderer death',()=>{
  const f=setup();f.controller.ready();f.state.visible=false;f.controller.hidden();f.controller.resume()
  f.advance(15*60_000);assert.deepEqual(f.state.probes,[]);assert.deepEqual(f.state.reloads,[])
  f.controller.gone();f.advance(RENDERER_RELOAD_MS);assert.deepEqual(f.state.reloads,[])
  f.state.visible=true;f.controller.visible();assert.deepEqual(f.state.reloads,[false])
})

test('a window hidden during an outstanding check starts a fresh probe on restore',()=>{
  const f=setup();f.controller.ready();f.controller.resume();const old=f.state.probes[0]
  f.state.visible=false;f.controller.hidden();f.advance(RENDERER_PROBE_MS)
  assert.deepEqual(f.state.reloads,[])
  f.state.visible=true;f.controller.visible();assert.equal(f.state.probes.length,2)
  f.controller.alive(old);f.controller.alive(f.state.probes[1]);f.advance(RENDERER_PROBE_MS)
  assert.deepEqual(f.state.reloads,[])
})

test('repeated failure offers one explicit retry and cannot enter an automatic reload loop',async()=>{
  const f=setup();f.controller.gone();f.controller.ready();f.controller.gone()
  assert.deepEqual(f.state.reloads,[false]);assert.equal(f.state.prompts.length,1)
  f.controller.gone();f.controller.resume();f.advance(RENDERER_RELOAD_MS)
  assert.equal(f.state.prompts.length,1)
  f.state.prompts[0](false);await Promise.resolve()
  f.controller.gone();assert.deepEqual(f.state.reloads,[false]);assert.equal(f.state.prompts.length,1)
})

test('failed recovery times out into manual retry, and an accepted retry replaces only the renderer',async()=>{
  const f=setup();f.controller.gone();f.advance(RENDERER_RELOAD_MS)
  assert.equal(f.state.prompts.length,1);f.state.prompts[0](true);await Promise.resolve()
  assert.deepEqual(f.state.reloads,[false,true]);f.controller.ready();f.advance(RENDERER_RELOAD_MS)
  assert.equal(f.state.prompts.length,1)
})

test('only a stable recovered UI earns another automatic attempt',()=>{
  const f=setup();f.controller.gone();f.controller.ready();f.advance(RENDERER_STABLE_MS)
  f.controller.gone();assert.deepEqual(f.state.reloads,[false,false]);assert.equal(f.state.prompts.length,0)
})

test('initial navigation has no automatic reload watchdog',()=>{
  const f=setup();f.controller.loading();f.advance(15*60_000)
  assert.deepEqual(f.state.reloads,[]);assert.equal(f.state.prompts.length,0)
})

test('normal navigation after an earlier mount still uses startup recovery until the new UI mounts',()=>{
  const f=setup();f.controller.ready();f.controller.loading();f.controller.resume();f.advance(RENDERER_RELOAD_MS)
  assert.deepEqual(f.state.probes,[]);assert.deepEqual(f.state.reloads,[])
})

test('unavailable native paint and backend refresh cannot crash the main-process resume handler',()=>{
  const f=setup();f.controller.ready();f.state.throwRefresh=true
  assert.doesNotThrow(()=>f.controller.resume());assert.equal(f.state.probes.length,1)
  f.state.throwPaint=true
  assert.doesNotThrow(()=>f.controller.alive(f.state.probes[0]));assert.deepEqual(f.state.reloads,[true])
})

test('old reload deadlines and prompt decisions cannot reload a recovered or closed window',async()=>{
  const f=setup();f.controller.gone();const oldDeadline=f.callbacks[0]
  f.controller.ready();oldDeadline();assert.equal(f.state.prompts.length,0)
  f.controller.gone();assert.equal(f.state.prompts.length,1);f.controller.dispose()
  f.state.prompts[0](true);await Promise.resolve();f.advance(15*60_000)
  f.controller.resume();f.controller.gone();f.controller.ready()
  assert.deepEqual(f.state.reloads,[false]);assert.equal(f.timers.size,0)
})
