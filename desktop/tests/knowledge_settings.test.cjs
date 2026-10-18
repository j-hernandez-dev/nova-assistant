require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require.extensions['.tsx'] = (module,filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
const actualReact = require('react')
let state=[],cursor=0
require.cache[require.resolve('react')].exports={...actualReact,
  useState(initial){const index=cursor++;if(!(index in state))state[index]=initial;return [state[index],next=>{state[index]=typeof next==='function'?next(state[index]):next}]},
  useRef(current){return {current}},useEffect(){}}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),loaded:true,exports:{useI18n:()=>({t:key=>key})}}
require.cache[require.resolve('../src/settings_actions.tsx')]={id:require.resolve('../src/settings_actions.tsx'),loaded:true,exports:{
  useSettingsAction:()=>({busy:false,run:async request=>{try{const result=await request();return result?.accepted&&!result?.error?result:null}catch{return null}}}),
  SettingsActionFeedback:()=>null,
}}
const {KnowledgeSettings}=require('../src/components/KnowledgeSettings.tsx')
const {knowledgeSettingsEnglish,knowledgeSettingsSpanish}=require('../src/knowledge_settings_locale.ts')
const tick=()=>new Promise(resolve=>setImmediate(resolve))
function nodes(root){if(!root||typeof root!=='object')return [];return [root,...[root.props?.children].flat(Infinity).flatMap(nodes)]}
function text(root){if(typeof root==='string'||typeof root==='number')return String(root);if(!root||typeof root!=='object')return '';return [root.props?.children].flat(Infinity).map(text).join('')}
function fixture(receipt={accepted:true}){
  state=[];cursor=0;const calls=[],selection=[]
  global.window={api:Object.fromEntries(['knowledgePick','knowledgeRefresh','knowledgeExport','knowledgeCommand','applicationCommand'].map(method=>[method,async(...args)=>{calls.push([method,...args]);return typeof receipt==='function'?await receipt(method,...args):receipt}]))}
  const view={sessionId:'owned-session',workspace:'owned-project',status:{ready:true},activeTurnId:null,recovering:false,gap:false,
    knowledge:{hostAcquisition:true,extraction:true,closing:false,attachmentRefs:[{attachmentId:'a1',sourceId:'s1',displayName:'Owned source',revisionId:'r1',state:'READY'}]},
    knowledgeOperations:[{operationId:'op-owned',status:'running',phase:'extract'}],rag:{enabled:false,availability:'DISABLED'},ragProgress:'',ragResult:null}
  const props={view,selectedSources:['s1'],onSelectedSources:next=>selection.push(next)}
  return {view,props,calls,selection,render(){cursor=0;return KnowledgeSettings(props)}}
}
function button(root,label){const found=nodes(root).find(node=>node.type==='button'&&text(node)===label);assert.ok(found,`button ${label}`);return found}

test('Every retained source action uses its existing host IPC and argument shape',async()=>{
  const harness=fixture();let tree=harness.render()
  nodes(tree).find(node=>node.type==='input'&&node.props.id==='nova-settings-source-url').props.onChange({target:{value:'https://owned.example/doc'}})
  tree=harness.render()
  for(const label of ['attach','listSources','capacityStatus','keepWorkspace','detail','refreshFile','refreshUrl','exportSource','settingsSourceRemote','settingsSourceLocal','cancelImport']){
    const control=button(tree,label);assert.equal(control.props.disabled,false,label);control.props.onClick();await tick()
  }
  nodes(tree).find(node=>node.type==='form'&&text(node).includes('importUrl')).props.onSubmit({preventDefault(){}})
  await tick()
  assert.deepEqual(harness.calls,[
    ['knowledgePick'],['knowledgeCommand','source_list',{}],['knowledgeCommand','source_status',{}],
    ['knowledgeCommand','source_promote',{sourceId:'s1'}],['knowledgeCommand','source_detail',{sourceId:'s1'}],
    ['knowledgeRefresh','s1'],['knowledgeCommand','source_refresh_url',{sourceId:'s1',url:'https://owned.example/doc'}],
    ['knowledgeExport','s1'],['knowledgeCommand','source_remote',{sourceId:'s1',allowed:true}],
    ['knowledgeCommand','source_remote',{sourceId:'s1',allowed:false}],['knowledgeCommand','source_cancel',{operationId:'op-owned'}],
    ['knowledgeCommand','source_import_url',{url:'https://owned.example/doc',scope:'WORKSPACE'}],
  ])
})

test('Delete does not alter attachment selection before a host receipt or after denial',async()=>{
  let resolveReceipt
  const receipt=new Promise(resolve=>{resolveReceipt=resolve})
  const harness=fixture(()=>receipt)
  button(harness.render(),'deleteSource').props.onClick()
  assert.deepEqual(harness.selection,[])
  resolveReceipt({accepted:false,error:{code:'POLICY_DENIED'}})
  await tick()
  assert.deepEqual(harness.selection,[])
  const accepted=fixture()
  button(accepted.render(),'deleteSource').props.onClick();await tick()
  assert.deepEqual(accepted.calls,[['knowledgeCommand','source_delete',{sourceId:'s1'}]])
  assert.deepEqual(accepted.selection,[[]])
})

test('Unavailable acquisition and active turns disable mutations without direct file access',()=>{
  const harness=fixture();harness.view.knowledge.hostAcquisition=false
  let tree=harness.render()
  assert.ok(!nodes(tree).some(node=>node.type==='button'&&text(node)==='attach'))
  assert.ok(text(tree).includes('settingsSourceUnavailable'))
  harness.view.knowledge.hostAcquisition=true;harness.view.activeTurnId='turn-owned';tree=harness.render()
  for(const label of ['attach','keepWorkspace','refreshFile','exportSource','settingsSourceRemote','deleteSource'])assert.equal(button(tree,label).props.disabled,true,label)
  assert.deepEqual(harness.calls,[])
})

test('RAG draft needs explicit Apply and uses session-only commands',async()=>{
  const harness=fixture();let tree=harness.render()
  assert.equal(button(tree,'settingsRagStart').props.disabled,true)
  const toggles=nodes(tree).filter(node=>node.type==='input'&&node.props.type==='checkbox')
  toggles.at(-1).props.onChange({target:{checked:true}})
  assert.deepEqual(harness.calls,[])
  tree=harness.render();assert.equal(button(tree,'settingsRagStart').props.disabled,false)
  button(tree,'settingsRagStart').props.onClick();await tick()
  assert.deepEqual(harness.calls,[['applicationCommand','SetRAGEnabled',{enabled:true}]])
  assert.equal(harness.view.rag.enabled,false,'receipt does not fabricate effective enabled state')
  harness.view.rag.enabled=true
  tree=harness.render()
  nodes(tree).find(node=>node.type==='input'&&node.props.id==='nova-settings-rag-query').props.onChange({target:{value:'owned query'}})
  tree=harness.render()
  nodes(tree).find(node=>node.type==='form'&&text(node).includes('queryProject')).props.onSubmit({preventDefault(){}});await tick()
  assert.deepEqual(harness.calls.at(-1),['applicationCommand','QueryRAG',{query:'owned query'}])
})

test('Attachment selection is unique and both language dictionaries cover the same UI labels',()=>{
  const harness=fixture();let tree=harness.render()
  const sourceCheckbox=nodes(tree).find(node=>node.type==='input'&&node.props.type==='checkbox')
  sourceCheckbox.props.onChange({target:{checked:true}})
  assert.deepEqual(harness.selection,[['s1']])
  sourceCheckbox.props.onChange({target:{checked:false}})
  assert.deepEqual(harness.selection.at(-1),[])
  assert.deepEqual(Object.keys(knowledgeSettingsEnglish).sort(),Object.keys(knowledgeSettingsSpanish).sort())
})
