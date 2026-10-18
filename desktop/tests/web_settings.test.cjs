require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript')
require.extensions['.tsx']=(m,p)=>m._compile(ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,p)
const React=require('react');let state=[],cursor=0,result=null,calls=[]
require.cache[require.resolve('react')].exports={...React,useState(initial){const n=cursor++;if(!(n in state))state[n]=initial;return[state[n],v=>{state[n]=typeof v==='function'?v(state[n]):v}]},useRef:v=>({current:v}),useEffect(){}}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),loaded:true,exports:{useI18n:()=>({t:k=>k})}}
require.cache[require.resolve('../src/settings_actions.tsx')]={id:require.resolve('../src/settings_actions.tsx'),loaded:true,exports:{SettingsActionFeedback:()=>null,
 useSettingsAction:()=>({busy:false,result,run:async action=>{result=await action();return result}})}}
const {ServiceSetting}=require('../src/components/WebSettings.tsx')
const {settingStateKey,settingErrorKey}=require('../src/settings_services_locale.ts')
function nodes(v){return !v||typeof v!=='object'?[]:[v,...[v.props?.children].flat(Infinity).flatMap(nodes)]}
function fixture(effective='bing'){
 state=[];cursor=0;result=null;calls=[];global.window={api:{applicationCommand:async(kind,payload)=>{calls.push({kind,payload});return{accepted:true,createdIds:{}}}}}
 const props={title:'Search',effective,scope:'owned-session:project',kind:'SetSearchEngine',field:'engine',choices:[['bing','Bing'],['google','Google'],['duckduckgo','DuckDuckGo']],disabled:false}
 return{props,render(){cursor=0;return ServiceSetting(props)}}
}
test('A draft is not an operation; save uses the existing exact command payload',async()=>{
 const f=fixture();let tree=f.render();nodes(tree).find(n=>n.type==='select').props.onChange({target:{value:'google'}})
 assert.equal(calls.length,0);tree=f.render();tree.props.onSubmit({preventDefault(){}});await new Promise(r=>setImmediate(r))
 assert.deepEqual(calls,[{kind:'SetSearchEngine',payload:{engine:'google'}}])
 assert.equal(nodes(f.render()).find(n=>n.type==='select').props.disabled,true,'accepted is not the new observed state')
})
test('A confirmed previous save does not lock a later draft or prevent its cancellation',async()=>{
 const f=fixture();nodes(f.render()).find(n=>n.type==='select').props.onChange({target:{value:'google'}})
 f.render().props.onSubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));f.props.effective='google'
 let tree=f.render();assert.equal(nodes(tree).find(n=>n.type==='select').props.disabled,false)
 nodes(tree).find(n=>n.type==='select').props.onChange({target:{value:'duckduckgo'}})
 tree=f.render();assert.equal(nodes(tree).find(n=>n.type==='select').props.disabled,false)
 assert.equal(nodes(tree).find(n=>n.type==='button'&&n.props.type==='submit').props.disabled,false)
 nodes(tree).find(n=>n.type==='button'&&n.props.type==='button').props.onClick()
 assert.equal(nodes(f.render()).find(n=>n.type==='select').props.value,'google')
 assert.equal(calls.length,1)
})
test('Missing host observation cannot invent an effective default or offer saving',()=>{
 const f=fixture();f.props.effective=undefined;const tree=f.render()
 assert.equal(nodes(tree).find(n=>n.type==='select').props.disabled,true)
 assert.equal(nodes(tree).find(n=>n.type==='button'&&n.props.type==='submit').props.disabled,true)
 assert.equal(calls.length,0)
 assert.equal(settingStateKey('constructor'),'settingsStateUnknown')
 assert.equal(settingErrorKey('raw-secret-message'),'settingsOperationFailed')
})
