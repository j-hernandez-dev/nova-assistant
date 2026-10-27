require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript')
require.extensions['.tsx']=(m,p)=>m._compile(ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,p)
const React=require('react');let state=[],cursor=0,result=null,calls=[],accept=true
require.cache[require.resolve('react')].exports={...React,useId:()=> 'web-test',useState(initial){const n=cursor++;if(!(n in state))state[n]=initial;return[state[n],v=>{state[n]=typeof v==='function'?v(state[n]):v}]}}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),loaded:true,exports:{useI18n:()=>({t:k=>k})}}
require.cache[require.resolve('../src/settings_actions.tsx')]={id:require.resolve('../src/settings_actions.tsx'),loaded:true,exports:{SettingsActionFeedback:()=>null,
 useSettingsAction:()=>({busy:false,result,run:async action=>{const receipt=await action();result=receipt.accepted?receipt:null;return result}})}}
const {WebSettings,observedWebPreferences,defaultWebPreferences}=require('../src/components/WebSettings.tsx')
const {SettingsSelect}=require('../src/components/SettingsSelect.tsx')
function nodes(v){return !v||typeof v!=='object'?[]:[v,...[v.props?.children].flat(Infinity).flatMap(nodes)]}
function fixture(patch={}){
 state=[];cursor=0;result=null;calls=[];accept=true
 global.window={api:{applicationCommand:async(kind,payload)=>{calls.push({kind,payload});return accept?{accepted:true}:{accepted:false,error:{code:'WEB_CONFIGURATION_FAILED'}}}}}
 const preferences={...defaultWebPreferences,...patch}
 const view={sessionId:'owned',workspace:'project',status:{ready:true,connected:true},approvals:[],inputs:[],
   fetch:{enabled:preferences.fetchEnabled},search:{enabled:preferences.searchEnabled,engine:preferences.engine},
   browser:{enabled:preferences.browserEnabled,selected:preferences.browser,choices:[]}}
 return{view,preferences,render(){cursor=0;return WebSettings({view})}}
}
const switches=tree=>nodes(tree).filter(n=>n.type==='input'&&n.props.role==='switch')
const selects=tree=>nodes(tree).filter(n=>n.type===SettingsSelect)
const settled=()=>new Promise(resolve=>setImmediate(resolve))

test('normalized permission rows contain the three switches, ordered selectors, Reset and the notice only',()=>{
 const f=fixture(),tree=f.render()
 assert.equal(switches(tree).length,3);assert.equal(nodes(tree).some(n=>n.type==='form'),false)
 assert.deepEqual(selects(tree).map(n=>n.props.options.map(o=>o.value)),[['google','bing','duckduckgo'],['webview2','chrome','edge']])
 assert.deepEqual(nodes(tree).filter(n=>n.type==='button').map(n=>n.props.children),['settingsReset'])
 assert.equal(nodes(tree).at(-1).props.children,'settingsNoIsolation')
})

test('toggles save the complete exact backend setting immediately and wait for the observed snapshot',async()=>{
 const f=fixture();switches(f.render())[1].props.onChange({target:{checked:false}});await settled()
 assert.deepEqual(calls,[{kind:'SetWebSettings',payload:{...defaultWebPreferences,searchEnabled:false}}])
 assert.equal(switches(f.render())[1].props.checked,true,'receipt alone never invents effective state')
 assert.equal(switches(f.render())[0].props.disabled,true)
 f.view.search.enabled=false
 assert.equal(switches(f.render())[0].props.disabled,false)
 assert.equal(selects(f.render())[0].props.disabled,true)
 assert.equal(selects(f.render())[1].props.disabled,false)
})

test('each selector follows its own permission; changing an enabled selector saves immediately',async()=>{
 const f=fixture({browserEnabled:false})
 assert.equal(selects(f.render())[0].props.disabled,false);assert.equal(selects(f.render())[1].props.disabled,true)
 selects(f.render())[0].props.onChange('duckduckgo');await settled()
 assert.deepEqual(calls,[{kind:'SetWebSettings',payload:{...f.preferences,engine:'duckduckgo'}}])
})

test('Reset submits one atomic defaults command, without changing local observed controls first',async()=>{
 const f=fixture({fetchEnabled:false,searchEnabled:false,browserEnabled:false,engine:'bing',browser:'edge'})
 nodes(f.render()).find(n=>n.type==='button').props.onClick();await settled()
 assert.deepEqual(calls,[{kind:'SetWebSettings',payload:defaultWebPreferences}]);assert.equal(switches(f.render())[0].props.checked,false)
})

test('rejected saves preserve confirmed values and permit a later explicit change',async()=>{
 const f=fixture();accept=false;switches(f.render())[0].props.onChange({target:{checked:false}});await settled()
 assert.equal(switches(f.render())[0].props.checked,true);assert.equal(switches(f.render())[0].props.disabled,false)
})

test('missing observations and active work disable all writes without inventing permission defaults',()=>{
 const f=fixture();delete f.view.search.enabled
 assert.equal(observedWebPreferences(f.view),null);assert.ok(switches(f.render()).every(n=>n.props.disabled))
 f.view.search.enabled=true;f.view.activeTurnId='running'
 assert.ok(switches(f.render()).every(n=>n.props.disabled));assert.equal(calls.length,0)
})
