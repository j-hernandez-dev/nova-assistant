require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require.extensions['.tsx'] = (module,filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
require.extensions['.css']=()=>{}
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
const {MemoryRecords,memoryInspection,memoryProposals,memoryRecordMutation,memoryProposalMutation}=require('../src/components/MemoryRecords.tsx')
const {memorySettingsEnglish,memorySettingsSpanish}=require('../src/memory_settings_locale.ts')
// Opening reads start after the mount-effect cleanup pass, like React's
// StrictMode lifecycle; allow that timer and its receipt to settle.
const tick=()=>new Promise(resolve=>setTimeout(resolve,5))
const owned={memoryId:'memory-owned',revision:3,canonicalText:'Este proyecto usa C# <script>data</script>',kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE',status:'ACTIVE',sensitivityClass:'NORMAL'}
const proposal={jobId:'job-owned',revision:7,proposal:{proposalId:'proposal-owned',text:'Texto literal del usuario',kind:'WORKSPACE_FACT',scopeKind:'WORKSPACE'}}
function nodes(root){return !root||typeof root!=='object'?[]:[root,...[root.props?.children].flat(Infinity).flatMap(nodes)]}
function text(root){if(typeof root==='string'||typeof root==='number')return String(root);return !root||typeof root!=='object'?'':[root.props?.children].flat(Infinity).map(text).join('')}
function button(tree,label){const result=nodes(tree).find(node=>node.type==='button'&&text(node)===label);assert.ok(result,`button ${label}`);return result}
function control(tree,suffix){const result=nodes(tree).find(node=>node.props?.id===`owned-memory-${suffix}`);assert.ok(result,`control ${suffix}`);return result}
function fixture(reply){
  for(const effect of effects)effect?.cleanup?.()
  slots=[];effects=[];pendingEffects=[];cursor=0
  const calls=[]
  global.window={api:{memoryCommand:async(name,args)=>{calls.push([name,args]);if(reply)return await reply(name,args)
    const data=name==='memory_list'?{records:[owned],nextCursor:'exact-cursor'}:name==='memory_search'?{records:[owned],nextCursor:null}:
      name==='memory_show'?{record:owned}:name==='memory_status'?{available:true,captureMode:'off'}:
      name==='memory_proposals'?{proposals:[proposal]}:name==='memory_export'?{format:'nova-memory-export',records:[owned]}:{memoryId:owned.memoryId}
    return {schemaVersion:1,completed:true,data}
  }}}
  const view={sessionId:'owned-session',workspace:'owned-project',status:{ready:true,connected:true},recovering:false,gap:false,
    activeTurnId:null,activeGenerationId:null,approvals:[],inputs:[],memory:{lexicalRecall:false,semantic:false,autoCapture:false}}
  const render=(extra={})=>{cursor=0;const tree=MemoryRecords({view,...extra});const jobs=pendingEffects;pendingEffects=[];for(const job of jobs)job();return tree}
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


function byData(tree,key,value){const n=nodes(tree).find(n=>n.props?.[key]===value);assert.ok(n,key+':'+value);return n}
async function openTab(h,tab){byData(h.render(),'data-memory-tab',tab).props.onClick();h.render();await tick()}
const editor=tree=>nodes(tree).find(n=>n.type==='form'&&n.props.className==='memories-editor')
const row=tree=>nodes(tree).find(n=>n.type==='tr'&&n.props?.['data-memory-record'])

test('Opening loads normal memories once even with lexical recall off; unavailable or inactive windows do not query',async()=>{
  const h=fixture();h.render();await tick()
  assert.deepEqual(h.calls,[['memory_list',{scope:'ALL',limit:20,includeSensitive:false}]])
  h.view.stateRevision=12;h.render();await tick();assert.equal(h.calls.length,1)
  assert.ok(row(h.render()))
  const inactive=fixture();inactive.render({active:false});await tick();assert.equal(inactive.calls.length,0)
  const unavailable=fixture();unavailable.view.memory=undefined;unavailable.render();await tick();assert.equal(unavailable.calls.length,0)
  unavailable.view.memory={lexicalRecall:false};unavailable.render();await tick();assert.equal(unavailable.calls.length,1)
})

test('List search and pagination remain scoped; sensitive listing is an explicit host-confirmed command',async()=>{
  const h=fixture();h.render();await tick()
  button(h.render(),'memoriesLoadMore').props.onClick();await tick()
  assert.deepEqual(h.calls.at(-1),['memory_list',{scope:'ALL',limit:20,includeSensitive:false,cursor:'exact-cursor'}])
  assert.equal(nodes(h.render()).filter(n=>n.type==='tr'&&n.props?.['data-memory-record']).length,1,'pagination deduplicates identities')
  control(h.render(),'query').props.onChange({target:{value:' C# '}})
  nodes(h.render()).find(n=>n.props?.className?.split(' ').includes('memories-search')).props.onSubmit({preventDefault(){}});await tick()
  assert.deepEqual(h.calls.at(-1),['memory_search',{scope:'ALL',limit:20,includeSensitive:false,query:'C#'}])
  control(h.render(),'scope').props.onChange('GLOBAL_PROFILE');await tick()
  assert.equal(h.calls.at(-1)[1].scope,'GLOBAL_PROFILE')
  control(h.render(),'reveal').props.onChange({target:{checked:true}});await tick()
  assert.equal(h.calls.at(-1)[1].includeSensitive,true)
})

test('Manual memories keep chosen scope and explicit sensitive intent; successful writes reload without sensitive data',async()=>{
  const h=fixture();h.render();await tick();await openTab(h,'add')
  control(h.render(),'text').props.onChange({target:{value:'Explicit synthetic sensitive preference'}})
  control(h.render(),'write-scope').props.onChange('GLOBAL_PROFILE')
  control(h.render(),'sensitive').props.onChange({target:{checked:true}})
  editor(h.render()).props.onSubmit({preventDefault(){}});await tick()
  assert.equal(control(h.render(),'kind').props.options.some(o=>o.value==='WORKSPACE_FACT'),false,'Project facts stay scoped to a project')
  assert.deepEqual(h.calls.find(c=>c[0]==='memory_remember'),['memory_remember',{kind:'PREFERENCE',text:'Explicit synthetic sensitive preference',scope:'GLOBAL_PROFILE',sensitive:true,consentSensitive:true}])
  assert.equal(control(h.render(),'text').props.value,'')
  assert.equal(h.calls.at(-1)[0],'memory_list');assert.equal(h.calls.at(-1)[1].includeSensitive,false)
})

test('Sensitive checkbox changes only after confirmation; cancellation preserves the list and unchecked state',async()=>{
  let finish
  const h=fixture(async(_name,args)=>args.includeSensitive?new Promise(resolve=>{finish=resolve}):
    {completed:true,data:{records:[owned],nextCursor:null}})
  h.render();await tick()
  control(h.render(),'reveal').props.onChange({target:{checked:true}})
  assert.equal(control(h.render(),'reveal').props.checked,false)
  assert.ok(row(h.render()),'existing normal records remain while confirmation is open')
  finish({completed:false,canceled:true});await tick()
  assert.equal(control(h.render(),'reveal').props.checked,false);assert.ok(row(h.render()))
  control(h.render(),'reveal').props.onChange({target:{checked:true}})
  finish({completed:true,data:{records:[owned],nextCursor:null}});await tick()
  assert.equal(control(h.render(),'reveal').props.checked,true)
  control(h.render(),'reveal').props.onChange({target:{checked:false}});await tick()
  assert.equal(control(h.render(),'reveal').props.checked,false)
})

test('The table has one edit flow; discard never writes and save uses exact identities and revisions',async()=>{
  const h=fixture();h.render();await tick()
  assert.equal(nodes(h.render()).some(n=>n.props?.['data-memory-detail']),false)
  assert.equal(nodes(h.render()).some(n=>n.props?.className==='memories-record'),false)
  assert.equal(nodes(row(h.render())).find(n=>n.type==='input'&&n.props?.['aria-label']==='memoriesSensitiveContent').props.disabled,true)
  button(h.render(),'memoriesEdit').props.onClick()
  let input=nodes(h.render()).find(n=>n.type?.name==='GrowingMemoryText')
  input.props.onChange('Discard this draft')
  button(h.render(),'memoriesDiscard').props.onClick()
  assert.equal(h.calls.some(c=>c[0]==='memory_edit'),false)
  assert.ok(text(h.render()).includes(owned.canonicalText))
  button(h.render(),'memoriesEdit').props.onClick()
  input=nodes(h.render()).find(n=>n.type?.name==='GrowingMemoryText');input.props.onChange('Corrected fact')
  button(h.render(),'memoriesSave').props.onClick();await tick()
  assert.deepEqual(h.calls.find(c=>c[0]==='memory_edit'),['memory_edit',{records:[{memoryId:'memory-owned',revision:3,text:'Corrected fact',kind:'WORKSPACE_FACT',scope:'WORKSPACE',sensitive:false}]}])
  assert.equal(h.calls.at(-1)[0],'memory_list')
})

test('Classification changes only after host confirmation and save carries the opaque receipt',async()=>{
  let finish
  const h=fixture();h.render();await tick();button(h.render(),'memoriesEdit').props.onClick()
  window.api.memoryEditSensitivity=()=>new Promise(resolve=>{finish=resolve})
  const checkbox=()=>nodes(row(h.render())).find(n=>n.type==='input'&&n.props?.['aria-label']==='memoriesSensitiveContent')
  checkbox().props.onChange({target:{checked:true}})
  assert.equal(checkbox().props.checked,false)
  finish({completed:false,canceled:true});await tick();assert.equal(checkbox().props.checked,false)
  checkbox().props.onChange({target:{checked:true}})
  finish({completed:true,data:{token:'host-confirmed-choice'}});await tick();assert.equal(checkbox().props.checked,true)
  button(h.render(),'memoriesSave').props.onClick();await tick()
  assert.equal(h.calls.find(c=>c[0]==='memory_edit')[1].records[0].consentToken,'host-confirmed-choice')
})

test('Denied edits preserve draft and hidden sensitive rows cannot enter the editor',async()=>{
  const h=fixture(async name=>name==='memory_list'?{completed:true,data:{records:[owned]}}:{completed:false,error:{code:'MEMORY_CONFLICT'}})
  h.render();await tick();button(h.render(),'memoriesEdit').props.onClick()
  nodes(h.render()).find(n=>n.type?.name==='GrowingMemoryText').props.onChange('Keep this edit')
  button(h.render(),'memoriesSave').props.onClick();await tick()
  assert.equal(nodes(h.render()).find(n=>n.type?.name==='GrowingMemoryText').props.value,'Keep this edit')
  const hidden=fixture(async()=>({completed:true,data:{records:[{...owned,sensitivityClass:'SENSITIVE',canonicalText:'[SENSITIVE — explicit inspection required]'}]}}))
  hidden.render();await tick();assert.equal(button(hidden.render(),'memoriesEdit').props.disabled,true)
})

test('Proposal decisions reload the whole job and never reuse sibling revisions',async()=>{
  for(const approve of [true,false]){
    let revision=7
    const h=fixture(async(name)=>({completed:true,data:name==='memory_proposals'?{proposals:[{...proposal,revision}]}:name==='memory_list'?{records:[]}:((revision++),{})}))
    h.render();await tick();await openTab(h,'proposals')
    button(h.render(),approve?'memoriesApprove':'memoriesReject').props.onClick();await tick()
    assert.deepEqual(h.calls.find(c=>c[0]===(approve?'memory_confirm':'memory_reject')),[approve?'memory_confirm':'memory_reject',{jobId:'job-owned',proposalId:'proposal-owned',revision:7,...(approve?{resolution:'create'}:{})}])
    assert.equal(h.calls.at(-1)[0],'memory_proposals')
    button(h.render(),approve?'memoriesApprove':'memoriesReject').props.onClick();await tick()
    assert.equal(h.calls.filter(c=>c[0]===(approve?'memory_confirm':'memory_reject')).at(-1)[1].revision,8)
  }
})

test('Old replies are discarded after a workspace change or closing; unknown writes never retry',async()=>{
  let resolve
  const h=fixture(()=>new Promise(next=>{resolve=next}));h.render();await tick()
  h.view.workspace='owned-other';h.render({active:false})
  resolve({completed:true,data:{records:[owned],nextCursor:null}});await tick()
  assert.equal(row(h.render({active:false})),undefined)
  const unknown=fixture(async(name)=>name==='memory_list'?{completed:true,data:{records:[]}}:{completed:false,error:{code:'MEMORY_WRITE_FAILED',outcomeUnknown:true}})
  unknown.render();await tick();await openTab(unknown,'add')
  control(unknown.render(),'text').props.onChange({target:{value:'Unknown effect'}})
  editor(unknown.render()).props.onSubmit({preventDefault(){}});await tick()
  assert.equal(unknown.calls.filter(c=>c[0]==='memory_remember').length,1)
  assert.equal(button(unknown.render(),'memorySettingsRemember').props.disabled,true)
  assert.ok(text(unknown.render()).includes('memorySettingsUnconfirmed'))
})

test('ES and EN cover every control; stored content remains literal and never enters chat commands or browser storage',()=>{
  assert.deepEqual(Object.keys(memorySettingsEnglish).sort(),Object.keys(memorySettingsSpanish).sort())
  for(const key of Object.keys(memorySettingsEnglish))assert.ok(memorySettingsEnglish[key]&&memorySettingsSpanish[key],key)
  assert.equal(memoryInspection(owned).canonicalText,owned.canonicalText)
  const source=fs.readFileSync(require.resolve('../src/components/MemoryRecords.tsx'),'utf8')
  for(const unwanted of ['dangerouslySetInnerHTML','localStorage','sendToPython','applicationCommand'])assert.ok(!source.includes(unwanted))
})

test('Selecting memories replaces Edit with Delete; cancellation keeps rows and selection, success reloads',async()=>{
 let accept=false
 const h=fixture(async name=>name==='memory_list'?{completed:true,data:{records:[owned]}}:name==='memory_delete'?(accept?{completed:true,data:{deleted:1}}:{completed:false,canceled:true}):{completed:true,data:{}})
 h.render();await tick()
 const select=()=>nodes(row(h.render())).find(n=>n.type==='input'&&n.props?.['aria-label']==='memoriesSelectRecord')
 select().props.onChange({target:{checked:true}})
 assert.equal(nodes(h.render()).some(n=>n.type==='button'&&text(n)==='memoriesEdit'),false)
 button(h.render(),'memoriesDelete').props.onClick();await tick()
 assert.equal(select().props.checked,true)
 assert.deepEqual(h.calls.find(c=>c[0]==='memory_delete'),['memory_delete',{records:[{memoryId:'memory-owned',revision:3}]}])
 accept=true;button(h.render(),'memoriesDelete').props.onClick();await tick()
 assert.ok(h.calls.slice(h.calls.findLastIndex(call=>call[0]==='memory_delete')+1).some(call=>call[0]==='memory_list'))
 assert.equal(select().props.checked,false)
 button(h.render(),'memoriesEdit').props.onClick();assert.equal(select().props.disabled,true)
})
