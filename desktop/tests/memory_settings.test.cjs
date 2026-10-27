require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename)
const react=require('react');let slots=[],cursor=0,effects=[],pendingEffects=[]
require.cache[require.resolve('react')].exports={...react,useId:()=> 'memory',
 useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return[slots[i],next=>slots[i]=typeof next==='function'?next(slots[i]):next]},
 useRef(initial){const i=cursor++;if(!(i in slots))slots[i]={current:initial};return slots[i]},
 useEffect(fn,deps){const i=cursor++,previous=effects[i];if(!previous||deps.some((v,k)=>v!==previous.deps[k]))pendingEffects.push(()=>{previous?.cleanup?.();effects[i]={deps,cleanup:fn()}})}}
require.cache[require.resolve('../src/i18n.tsx')]={loaded:true,exports:{useI18n:()=>({t:key=>key})}}
let action
require.cache[require.resolve('../src/settings_actions.tsx')]={loaded:true,exports:{useSettingsAction:()=>action}}
const {MemorySettings,memoryDefaults}=require('../src/components/MemorySettings.tsx')
const {memorySettingsEnglish,memorySettingsSpanish}=require('../src/memory_settings_locale.ts')
const nodes=root=>!root||typeof root!=='object'?[]:[root,...[root.props?.children].flat(Infinity).flatMap(nodes)]
const text=root=>typeof root==='string'?root:!root||typeof root!=='object'?'':[root.props?.children].flat(Infinity).map(text).join('')
const find=(tree,prop,value)=>{const n=nodes(tree).find(n=>n.props?.[prop]===value);assert.ok(n,prop+': '+value);return n}
const tick=()=>new Promise(resolve=>setImmediate(resolve))
function fixture(){slots=[];effects=[];pendingEffects=[];cursor=0
 const calls=[],view={sessionId:'owned',workspace:'C:/project',stateRevision:1,status:{ready:true,connected:true},approvals:[],inputs:[],memory:{lexicalRecall:true,semantic:false,semanticAvailable:false,autoCapture:true,captureMode:'low_risk',sensitiveProjects:[]}}
 let deny=false,cancel=false
 action={busy:false,result:null,errorCode:null,run:async fn=>{const receipt=await fn();action.result=receipt.completed?receipt:null;action.errorCode=receipt.error?.code;return receipt.completed?receipt:null}}
 global.window={api:{memoryCommand:async(name,args)=>{calls.push([name,args]);if(deny)return{completed:false,error:{code:'MEMORY_WRITE_FAILED'}}
   if(name==='memory_reset_settings')Object.assign(view.memory,{lexicalRecall:true,semantic:false,autoCapture:true,captureMode:'low_risk',sensitiveProjects:[]})
   else Object.assign(view.memory,{lexicalRecall:args.lexicalRecall,semantic:args.semanticRecall,autoCapture:args.autoCapture,captureMode:args.captureMode})
   return{completed:true,stateRevision:++view.stateRevision}},
 memoryTransfer:async(kind,sensitive)=>{calls.push(['transfer',kind,sensitive]);return cancel?{completed:false,canceled:true}:{completed:true}},
 memoryProjectAccess:async(path,on)=>{calls.push(['access',path,on]);if(cancel)return{completed:false,canceled:true};view.memory.sensitiveProjects=on?[path]:[];return{completed:true,stateRevision:++view.stateRevision}}}}
 const projects={folders:[{name:'Owned project',path:'C:/project',isDefault:true}]}
 return{view,calls,projects,setDeny:v=>deny=v,setCancel:v=>cancel=v,render(extra={}){cursor=0;const tree=MemorySettings({view,projects,...extra});const jobs=pendingEffects;pendingEffects=[];jobs.forEach(fn=>fn());return tree}}
}
test('Memory settings have the three normalized groups and no record manager or export JSON viewer',()=>{
 const h=fixture(),tree=h.render()
 assert.deepEqual(nodes(tree).filter(n=>n.type==='h3').map(text),['memoryRecovery','memoryRecords','memorySensitiveAccess'])
 assert.equal(find(tree,'className','nova-settings-reset').props.disabled,false)
 assert.equal(nodes(tree).filter(n=>n.type==='form'||n.type==='textarea'||n.type==='pre').length,0)
 for(const old of ['memorySettingsInspect','memorySettingsProposals','memorySettingsNew','memorySettingsExportData'])assert.ok(!text(tree).includes(old))
 assert.deepEqual(h.calls,[])
})
test('Lexical saves immediately; semantic depends on authoritative installed and enabled EM availability',async()=>{
 const h=fixture();assert.equal(find(h.render(),'data-memory-setting','semanticRecall').props.disabled,true)
 find(h.render(),'data-memory-setting','lexicalRecall').props.onChange({target:{checked:false}});await tick()
 assert.deepEqual(h.calls.at(-1),['memory_configure',{...memoryDefaults,lexicalRecall:false}])
 h.view.memory.semanticAvailable=true
 assert.equal(find(h.render(),'data-memory-setting','semanticRecall').props.disabled,false)
 find(h.render(),'data-memory-setting','semanticRecall').props.onChange({target:{checked:true}});await tick()
 assert.equal(h.calls.at(-1)[1].semanticRecall,true)
})
test('Capture mode is disabled only when capture is off and retains the selected mode',async()=>{
 const h=fixture(),mode=()=>find(h.render(),'data-settings-select','memoryCaptureMode')
 assert.deepEqual(mode().props.options.map(x=>x.value),['low_risk','propose_only'])
 mode().props.onChange('propose_only');await tick();assert.equal(h.calls.at(-1)[1].captureMode,'propose_only')
 find(h.render(),'data-memory-setting','autoCapture').props.onChange({target:{checked:false}});await tick()
 assert.equal(mode().props.disabled,true);assert.equal(mode().props.value,'propose_only')
})
test('Reset uses a single host command; rejected saves do not invent a changed switch',async()=>{
 const h=fixture();h.setDeny(true)
 find(h.render(),'data-memory-setting','lexicalRecall').props.onChange({target:{checked:false}});await tick()
 assert.equal(find(h.render(),'data-memory-setting','lexicalRecall').props.checked,true)
 h.setDeny(false);find(h.render(),'className','nova-settings-reset').props.onClick();await tick()
 assert.deepEqual(h.calls.at(-1),['memory_reset_settings',{}])
})
test('Import/export and project access use dedicated host flows, with cancellation preserving access',async()=>{
 const h=fixture();find(h.render(),'data-memory-import',true).props.onClick();await tick();assert.deepEqual(h.calls.at(-1),['transfer','import',undefined])
 find(h.render(),'data-memory-export-sensitive',true).props.onChange({target:{checked:true}})
 find(h.render(),'data-memory-export',true).props.onClick();await tick();assert.deepEqual(h.calls.at(-1),['transfer','export',true])
 h.setCancel(true);find(h.render(),'data-memory-project','C:/project').props.onChange({target:{checked:true}});await tick()
 assert.equal(find(h.render(),'data-memory-project','C:/project').props.checked,false)
 assert.deepEqual(h.calls.at(-1),['access','C:/project',true])
})
test('Both languages describe the EM requirement and all new controls; locked backend disables writes',()=>{
 const h=fixture(),tree=h.render({locked:true})
 assert.ok(nodes(tree).filter(n=>n.type==='input'||n.type==='button').every(n=>n.props.disabled))
 assert.deepEqual(Object.keys(memorySettingsEnglish).sort(),Object.keys(memorySettingsSpanish).sort())
 assert.match(memorySettingsSpanish.memorySemanticHint,/\. Requiere.*instalado y habilitado\.$/)
 assert.match(memorySettingsEnglish.memorySemanticHint,/\. Requires.*installed and enabled.*\.$/)
})
