require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require.extensions['.tsx'] = (module,filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
const react = require('react')
let slots = [], cursor = 0, effects = [], pendingEffects = []
require.cache[require.resolve('react')].exports = {...react,
  useId(){return 'owned-memory'},
  useState(initial){const index=cursor++;if(!(index in slots))slots[index]=typeof initial==='function'?initial():initial
    return [slots[index],next=>{slots[index]=typeof next==='function'?next(slots[index]):next}]},
  useRef(value){const index=cursor++;if(!(index in slots))slots[index]={current:value};return slots[index]},
  useEffect(callback,deps){const index=cursor++,previous=effects[index];if(!previous||deps.some((value,i)=>value!==previous.deps[i]))
    pendingEffects.push(()=>{previous?.cleanup?.();effects[index]={deps,cleanup:callback()}})},
}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),loaded:true,exports:{useI18n:()=>({t:key=>key})}}
require.cache[require.resolve('../src/settings_actions.tsx')]={id:require.resolve('../src/settings_actions.tsx'),loaded:true,exports:{
  useSettingsAction:()=>({busy:false,errorCode:null,run:async action=>{const result=await action();return result?.completed&&!result.error?result:null}}),
  SettingsActionFeedback:()=>null,
}}
const {MemorySettings,memoryInspection,memoryProposals,memoryRecordMutation,memoryProposalMutation}=require('../src/components/MemorySettings.tsx')
const {memorySettingsEnglish,memorySettingsSpanish}=require('../src/memory_settings_locale.ts')
const tick=()=>new Promise(resolve=>setImmediate(resolve))
const owned={memoryId:'memory-owned',revision:3,canonicalText:'Este proyecto usa C# <script>data</script>',kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE',status:'ACTIVE',sensitivityClass:'NORMAL'}
const proposal={jobId:'job-owned',revision:7,proposal:{proposalId:'proposal-owned',text:'Texto literal del usuario',kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE'}}
function nodes(root){return !root||typeof root!=='object'?[]:[root,...[root.props?.children].flat(Infinity).flatMap(nodes)]}
function text(root){if(typeof root==='string'||typeof root==='number')return String(root);return !root||typeof root!=='object'?'':[root.props?.children].flat(Infinity).map(text).join('')}
function button(tree,label){const result=nodes(tree).find(node=>node.type==='button'&&text(node)===label);assert.ok(result,`button ${label}`);return result}
function control(tree,suffix){const result=nodes(tree).find(node=>node.props?.id===`owned-memory-${suffix}`);assert.ok(result,`control ${suffix}`);return result}
function fixture(reply){
  slots=[];effects=[];pendingEffects=[];cursor=0
  const calls=[]
  global.window={api:{memoryCommand:async(name,args)=>{calls.push([name,args]);if(reply)return await reply(name,args)
    const data=name==='memory_list'?{records:[owned],nextCursor:'exact-cursor'}:name==='memory_search'?{records:[owned],nextCursor:null}:
      name==='memory_show'?{record:owned}:name==='memory_status'?{available:true,captureMode:'off'}:
      name==='memory_proposals'?{proposals:[proposal]}:name==='memory_export'?{format:'nova-memory-export',records:[owned]}:{memoryId:owned.memoryId}
    return {schemaVersion:1,completed:true,data}
  }}}
  const view={sessionId:'owned-session',workspace:'owned-project',status:{ready:true,connected:true},recovering:false,gap:false,
    activeTurnId:null,activeGenerationId:null,memory:{lexicalRecall:true,semantic:false,autoCapture:false,allowRemoteMemoryInjection:false}}
  const render=()=>{cursor=0;const tree=MemorySettings({view});const jobs=pendingEffects;pendingEffects=[];for(const job of jobs)job();return tree}
  return {view,calls,render}
}

test('Memory inspection validates identities and never imports source authority or scopes into write arguments',()=>{
  const record=memoryInspection({...owned,subjectId:'forged-user',scopeId:'forged-workspace',sources:[{secret:'not-needed'}]})
  assert.equal(record.canonicalText,owned.canonicalText)
  assert.deepEqual(memoryRecordMutation(record,'A correction',true),{memoryId:'memory-owned',revision:3,text:'A correction',consentSensitive:true})
  assert.deepEqual(memoryRecordMutation(record),{memoryId:'memory-owned',revision:3})
  for(const bad of [{...owned,revision:-1},{...owned,memoryId:''},{...owned,scopeKind:'FORGED'},{...owned,status:'constructor'},{...owned,kind:'other'}])assert.equal(memoryInspection(bad),null)
  assert.equal(memoryInspection({...owned,sensitivityClass:'SENSITIVE',canonicalText:'[SENSITIVE — explicit inspection required]'}).hidden,true)
  assert.equal(memoryInspection(owned).hidden,false)
})

test('Proposal decisions preserve exact job, proposal and revision and drop supplied authority',()=>{
  const parsed=memoryProposals([{...proposal,token:'forged',subjectId:'forged'}])
  assert.equal(parsed.length,1)
  assert.deepEqual(memoryProposalMutation(parsed[0],'supersede'),{jobId:'job-owned',proposalId:'proposal-owned',revision:7,resolution:'supersede'})
  assert.deepEqual(memoryProposalMutation(parsed[0]),{jobId:'job-owned',proposalId:'proposal-owned',revision:7})
  assert.deepEqual(memoryProposals([{...proposal,revision:'7'},{...proposal,proposal:{...proposal.proposal,proposalId:''}}]),[])
})

test('Mount and readonly capability state never auto-query, auto-reveal or change host configuration',()=>{
  const h=fixture(),tree=h.render()
  assert.deepEqual(h.calls,[])
  assert.ok(text(tree).includes('memorySettingsNotLoaded'))
  for(const name of ['memorySettingsLexical','memorySettingsSemantic','memorySettingsCapture','memorySettingsRemote'])assert.ok(text(tree).includes(name))
  assert.ok(!nodes(tree).some(node=>node.type==='input'&&node.props.type==='checkbox'&&/autoCapture|semantic|Remote/.test(node.props.name||'')))
  h.view.memory=undefined;const unavailable=h.render()
  assert.ok(text(unavailable).includes('memorySettingsUnavailable'))
  for(const label of ['memorySettingsList','memorySettingsRemember','memorySettingsLoadProposals','memorySettingsExport'])assert.equal(button(unavailable,label).props.disabled,true)
})

test('Explicit list, pagination, search, status and export use the existing exact Memory API',async()=>{
  const h=fixture();button(h.render(),'memorySettingsList').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_list',{scope:'WORKSPACE',limit:20,includeSensitive:false}])
  button(h.render(),'memorySettingsNext').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_list',{scope:'WORKSPACE',limit:20,includeSensitive:false,cursor:'exact-cursor'}])
  control(h.render(),'query').props.onChange({target:{value:' C# '}})
  const search=nodes(h.render()).find(node=>node.type==='form'&&text(node).includes('memorySettingsSearch'))
  search.props.onSubmit({preventDefault(){}});await tick()
  assert.deepEqual(h.calls.at(-1),['memory_search',{scope:'WORKSPACE',limit:20,includeSensitive:false,query:'C#'}])
  button(h.render(),'memorySettingsStatusDetail').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_status',{}])
  button(h.render(),'memorySettingsExport').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_export',{includeSensitive:false}])
  assert.ok(text(h.render()).includes('nova-memory-export'))
})

test('Sensitive disclosure and saving require explicit checkbox intent and still go to the native host',async()=>{
  const h=fixture();let tree=h.render()
  const reveal=nodes(tree).find(node=>node.type==='input'&&node.props.type==='checkbox')
  assert.equal(reveal.props.checked,false)
  reveal.props.onChange({target:{checked:true}})
  assert.deepEqual(h.calls,[])
  button(h.render(),'memorySettingsList').props.onClick();await tick()
  assert.equal(h.calls.at(-1)[1].includeSensitive,true)
  control(h.render(),'text').props.onChange({target:{value:'Explicit sensitive preference'}})
  tree=h.render()
  nodes(tree).filter(node=>node.type==='input'&&node.props.type==='checkbox').at(-1).props.onChange({target:{checked:true}})
  tree=h.render()
  nodes(tree).find(node=>node.type==='form'&&text(node).includes('memorySettingsNew')).props.onSubmit({preventDefault(){}});await tick()
  assert.deepEqual(h.calls.at(-1),['memory_remember',{kind:'WORKSPACE_FACT',text:'Explicit sensitive preference',scope:'WORKSPACE',sensitive:true,consentSensitive:true}])
  assert.equal(control(h.render(),'text').props.value,'')
})

test('Inspect, correct and two-step forget use selected record revision; known denial preserves the draft',async()=>{
  const h=fixture();button(h.render(),'memorySettingsList').props.onClick();await tick()
  let tree=h.render(),row=nodes(tree).find(node=>node.type?.name==='MemoryRecordRow')
  row.props.onInspect();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_show',{memoryId:'memory-owned',includeSensitive:false}])
  control(h.render(),'correction').props.onChange({target:{value:'Corrected fact'}})
  button(h.render(),'memorySettingsCorrect').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_correct',{memoryId:'memory-owned',revision:3,text:'Corrected fact'}])
  button(h.render(),'memorySettingsList').props.onClick();await tick()
  nodes(h.render()).find(node=>node.type?.name==='MemoryRecordRow').props.onInspect();await tick()
  const before=h.calls.length
  button(h.render(),'memorySettingsForget').props.onClick();await tick()
  assert.equal(h.calls.length,before)
  button(h.render(),'memorySettingsForgetConfirm').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_forget',{memoryId:'memory-owned',revision:3}])
  const denied=fixture(async()=>({completed:false,error:{code:'POLICY_DENIED'}}))
  control(denied.render(),'text').props.onChange({target:{value:'Keep this draft'}})
  nodes(denied.render()).find(node=>node.type==='form'&&text(node).includes('memorySettingsNew')).props.onSubmit({preventDefault(){}});await tick()
  assert.equal(control(denied.render(),'text').props.value,'Keep this draft')
})

test('Proposal confirmation/rejection does not reuse sibling job revisions',async()=>{
  for(const confirm of [true,false]){
    const h=fixture();button(h.render(),'memorySettingsLoadProposals').props.onClick();await tick()
    button(h.render(),confirm?'memorySettingsConfirm':'memorySettingsReject').props.onClick();await tick()
    assert.deepEqual(h.calls.at(-1),[confirm?'memory_confirm':'memory_reject',{jobId:'job-owned',proposalId:'proposal-owned',revision:7,...(confirm?{resolution:'create'}:{})}])
    assert.ok(!nodes(h.render()).some(node=>node.type==='button'&&text(node)==='memorySettingsConfirm'))
  }
})

test('Old inspection replies are discarded after a workspace change and unknown effects never retry',async()=>{
  let resolve
  const h=fixture(()=>new Promise(next=>{resolve=next}))
  button(h.render(),'memorySettingsList').props.onClick()
  h.view.workspace='owned-other';h.render()
  resolve({completed:true,data:{records:[owned],nextCursor:null}});await tick()
  assert.ok(!nodes(h.render()).some(node=>node.type?.name==='MemoryRecordRow'))
  const unknown=fixture(async()=>({completed:false,error:{code:'MEMORY_WRITE_FAILED',outcomeUnknown:true}}))
  control(unknown.render(),'text').props.onChange({target:{value:'Unknown effect'}})
  nodes(unknown.render()).find(node=>node.type==='form'&&text(node).includes('memorySettingsNew')).props.onSubmit({preventDefault(){}});await tick()
  assert.equal(unknown.calls.length,1)
  assert.equal(button(unknown.render(),'memorySettingsRemember').props.disabled,true)
  assert.ok(text(unknown.render()).includes('memorySettingsUnconfirmed'))
})

test('Both languages cover the same Memory UI while source content stays untouched',()=>{
  assert.deepEqual(Object.keys(memorySettingsEnglish).sort(),Object.keys(memorySettingsSpanish).sort())
  for(const key of Object.keys(memorySettingsEnglish))assert.ok(memorySettingsEnglish[key]&&memorySettingsSpanish[key],key)
  assert.equal(memoryInspection(owned).canonicalText,owned.canonicalText)
  const source=fs.readFileSync(require.resolve('../src/components/MemorySettings.tsx'),'utf8')
  assert.ok(!source.includes('dangerouslySetInnerHTML'))
  assert.ok(!source.includes('localStorage'))
  assert.ok(!source.includes('sendToPython'))
  assert.ok(!source.includes('applicationCommand'))
})
