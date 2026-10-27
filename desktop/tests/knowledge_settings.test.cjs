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
  useId(){return 'knowledge-settings'},useRef(current){return {current}},useEffect(){}}
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
  const view={sessionId:'owned-session',workspace:'owned-project',status:{ready:true,connected:true},approvals:[],inputs:[],activeTurnId:null,recovering:false,gap:false,
    knowledge:{hostAcquisition:true,extraction:true,closing:false,attachmentRefs:[{attachmentId:'a1',sourceId:'s1',displayName:'Owned source',revisionId:'r1',state:'READY'}]},
    knowledgeSettings:{lexicalRecall:true,semanticRecall:false,autoIndex:true,autoRebuild:true,semanticAvailable:false,indexing:false,indexedSources:0,totalSources:0,errorCode:null},knowledgeOperations:[],rag:{enabled:false,availability:'DISABLED'},ragProgress:'',ragResult:null}
  const props={view,selectedSources:['s1'],onSelectedSources:next=>selection.push(next)}
  return {view,props,calls,selection,render(){cursor=0;return KnowledgeSettings(props)}}
}
function button(root,label){const found=nodes(root).find(node=>node.type==='button'&&text(node)===label);assert.ok(found,`button ${label}`);return found}

test('Knowledge contains project retrieval settings without source management or capacity controls',()=>{
  const harness=fixture(),tree=harness.render()
  for(const label of ['attach','listSources','capacityStatus','detail','refreshFile','refreshUrl','exportSource','deleteSource','importUrl'])assert.ok(!nodes(tree).some(node=>node.type==='button'&&text(node)===label),label)
  assert.equal(nodes(tree).filter(node=>node.type==='input'&&node.props.role==='switch').length,4)
  assert.ok(text(tree).includes('knowledgeRecovery'));assert.ok(!text(tree).includes('settingsSessionOnly'));assert.equal(nodes(tree).filter(node=>node.type==='form').length,0);assert.deepEqual(harness.calls,[])
  harness.view.activeTurnId='active-turn'
  assert.equal(button(harness.render(),'settingsReset').props.disabled,true)
})

test('EM controls are disabled without availability and defaults remain visible',()=>{
  const harness=fixture()
  let tree=harness.render(),toggles=nodes(tree).filter(node=>node.props?.['data-knowledge-setting'])
  assert.deepEqual(toggles.map(node=>node.props.checked),[true,false,true,true])
  assert.deepEqual(toggles.map(node=>!!node.props.disabled),[false,true,true,true])
  harness.view.knowledgeSettings.semanticAvailable=true
  tree=harness.render();toggles=nodes(tree).filter(node=>node.props?.['data-knowledge-setting'])
  assert.ok(toggles.every(node=>!node.props.disabled))
})

test('Changes save immediately through persistent commands; reset carries no session-only RAG action',async()=>{
  const harness=fixture()
  let tree=harness.render()
  nodes(tree).find(node=>node.props?.['data-knowledge-setting']==='lexicalRecall').props.onChange({target:{checked:false}})
  await tick()
  assert.deepEqual(harness.calls,[['applicationCommand','SetKnowledgeSettings',{lexicalRecall:false,semanticRecall:false,autoIndex:true,autoRebuild:true}]])
  assert.equal(harness.view.knowledgeSettings.lexicalRecall,true,'receipt does not invent effective preferences')
  button(harness.render(),'settingsReset').props.onClick();await tick()
  assert.deepEqual(harness.calls.at(-1),['applicationCommand','ResetKnowledgeSettings',{}])
  assert.ok(!harness.calls.some(call=>['SetRAGEnabled','QueryRAG'].includes(call[1])))
})

test('Knowledge and Sources dictionaries cover the same UI labels in English and Spanish',()=>{
  const {sourcesEnglish,sourcesSpanish}=require('../src/sources_locale.ts')
  assert.deepEqual(Object.keys(knowledgeSettingsEnglish).sort(),Object.keys(knowledgeSettingsSpanish).sort())
  assert.deepEqual(Object.keys(sourcesEnglish).sort(),Object.keys(sourcesSpanish).sort())
})
