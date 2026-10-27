require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript')
require.extensions['.tsx']=(m,p)=>m._compile(ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,p)
const React=require('react'),actualReact={...React}
let cells=[],cursor=0,effects=[],queued=[]
function changed(a,b){return !a||!b||a.length!==b.length||a.some((value,i)=>value!==b[i])}
require.cache[require.resolve('react')].exports={...actualReact,
 useState(initial){const n=cursor++;if(!(n in cells))cells[n]=typeof initial==='function'?initial():initial;return[cells[n],v=>{cells[n]=typeof v==='function'?v(cells[n]):v}]},
 useRef(value){const n=cursor++;return cells[n]||(cells[n]={current:value})},
 useCallback(fn,deps){const n=cursor++;if(!cells[n]||changed(cells[n].deps,deps))cells[n]={fn,deps};return cells[n].fn},
 useEffect(fn,deps){const n=cursor++;if(!effects[n]||changed(effects[n].deps,deps))queued.push(()=>{effects[n]?.cleanup?.();effects[n]={deps,cleanup:fn()}})},
}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),loaded:true,exports:{useI18n:()=>({t:key=>key})}}
const {useSettingsAction}=require('../src/settings_actions.tsx')
function harness(){cells=[];effects=[];queued=[];return{render(scope='owned-session:workspace'){cursor=0;const value=useSettingsAction(scope);const apply=queued;queued=[];apply.forEach(fn=>fn());return value},dispose(){effects.forEach(e=>e?.cleanup?.())}}}
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return{promise,resolve}}

test('A settings request needs a receipt and duplicate clicks cannot submit twice',async()=>{
 const h=harness(),pending=deferred();let calls=0;const first=h.render()
 const running=first.run(()=>{calls++;return pending.promise})
 assert.equal(h.render().busy,true);assert.equal(await h.render().run(async()=>{calls++;return{accepted:true}}),null)
 pending.resolve({accepted:true,createdIds:{}});assert.equal((await running).accepted,true)
 assert.equal(calls,1);assert.equal(h.render().busy,false);assert.equal(h.render().result.accepted,true);h.dispose()
})
test('A scope change rejects a late result rather than attaching it to another project',async()=>{
 const h=harness(),pending=deferred();h.render();const running=h.render().run(()=>pending.promise)
 h.render('new-session:new-project');pending.resolve({completed:true,data:{private:'old project'}})
 assert.equal(await running,null);const current=h.render('new-session:new-project')
 assert.equal(current.result,null);assert.equal(current.busy,false);h.dispose()
})

test('Canceling a confirmation is neutral and allows the next explicit action',async()=>{
 const h=harness();h.render()
 assert.equal(await h.render().run(async()=>({completed:false,canceled:true})),null)
 assert.equal(h.render().busy,false);assert.equal(h.render().errorCode,null);assert.equal(h.render().unconfirmed,false)
 assert.equal((await h.render().run(async()=>({completed:true}))).completed,true);h.dispose()
})
test('Unknown effects remain unconfirmed and block another call, including Memory outcomeUnknown flags',async()=>{
 for(const error of [{code:'OUTCOME_UNKNOWN'},{code:'MEMORY_WRITE_FAILED',outcomeUnknown:true}]){
  const h=harness();h.render();assert.equal(await h.render().run(async()=>({completed:false,error})),null)
  const current=h.render();assert.equal(current.unconfirmed,true);assert.equal(current.busy,true);assert.equal(current.result,null)
  let calls=0;await current.run(async()=>{calls++;return{completed:true}});assert.equal(calls,0);h.dispose()
 }
})
test('Known denial keeps its code without copying exception or backend prose',async()=>{
 const h=harness();h.render();await h.render().run(async()=>({accepted:false,error:{code:'POLICY_DENIED',message:'private backend payload'}}))
 const current=h.render();assert.equal(current.busy,false);assert.equal(current.errorCode,'POLICY_DENIED')
 assert.ok(!JSON.stringify(current).includes('private backend'));h.dispose()
})
test('A rejected transport promise is bounded uncertainty, not an unhandled rejection or success',async()=>{
 const h=harness();h.render();assert.equal(await h.render().run(async()=>{throw Error('private connection details')}),null)
 const current=h.render();assert.equal(current.unconfirmed,true);assert.equal(current.result,null)
 assert.ok(!JSON.stringify(current).includes('private'));h.dispose()
})
