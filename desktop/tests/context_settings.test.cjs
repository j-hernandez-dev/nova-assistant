require('./register_typescript.cjs')
const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),ts=require('typescript')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')
const {DesktopApplicationClient}=require('../electron/application_client.ts')
const {settingsEnglish,settingsSpanish}=require('../src/settings_locale.ts')
let locale='es'
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),loaded:true,
  exports:{useI18n:()=>({t:key=>(locale==='es'?settingsSpanish:settingsEnglish)[key]||key})}}
const {ContextSettings}=require('../src/components/ContextSettings.tsx')
const context={requestedTokens:8192,selectedTokens:8192,errorCode:null}
const snapshot=(value=context)=>({sessionId:'owned',workspace:'/owned',lastSequence:1,stateRevision:3,
  modelRuntime:{modelId:'fixture',providerId:'ollama',providerRevision:1},transcript:[],turns:[],services:{rag:{},context:value}})
function setup(){const sent=[],client=new DesktopApplicationClient(frame=>sent.push(frame),()=>{})
  client.receive({type:'ready',sessionId:'owned',tools:[]})
  client.receive({type:'snapshot',id:sent.findLast(f=>f.type==='get_snapshot').id,data:snapshot()})
  return {client,sent}}

for (const tokens of [65536,131072,262144]) test('context setter validates and confirms '+tokens+' tokens',async()=>{
  const {client,sent}=setup(),before=sent.length
  for(const requestedTokens of [true,'65536',524288,262145,-1,undefined,null])
    assert.equal((await client.command('SetContextWindow',{requestedTokens})).accepted,false)
  assert.equal((await client.command('SetContextWindow',{requestedTokens:8192,permission:'all'})).accepted,false)
  assert.equal(sent.length,before)
  const pending=client.command('SetContextWindow',{requestedTokens:tokens},'owned-preset'),request=sent.at(-1)
  assert.equal(request.command.expectedRevision,3)
  assert.equal(client.view.context.requestedTokens,8192)
  client.receive({type:'application_result',id:request.id,data:{accepted:true,schemaVersion:1,commandId:'owned-preset',createdIds:{}}})
  assert.equal((await pending).accepted,true)
  assert.equal(client.view.context.requestedTokens,8192)
  client.receive({type:'snapshot',id:sent.findLast(f=>f.type==='get_snapshot').id,data:snapshot({requestedTokens:tokens,selectedTokens:tokens,errorCode:null})})
  assert.equal(client.view.context.requestedTokens,tokens)
  client.disconnected()
})

test('context projection drops absent or malformed settings on recovery',()=>{
  for(const invalid of [undefined,{...context,requestedTokens:524288},{...context,selectedTokens:0},
    {...context,errorCode:'invalid with spaces'},{...context,selectedTokens:null}]){
    const {client,sent}=setup();client.refresh()
    const state=snapshot(invalid);state.services.context=invalid
    client.receive({type:'snapshot',id:sent.findLast(f=>f.type==='get_snapshot').id,data:state})
    assert.equal(client.view.context,undefined)
    client.disconnected()
  }
})

test('a rejected context save preserves the conversation error and the confirmed preset',async()=>{
  const {client,sent}=setup(),previous={code:'OWNED_TURN_ERROR',message:'owned fixture'}
  client.view.error=previous
  const pending=client.command('SetContextWindow',{requestedTokens:65536}),request=sent.at(-1)
  client.receive({type:'application_result',id:request.id,data:{schemaVersion:1,commandId:request.command.commandId,
    accepted:false,createdIds:{},error:{code:'CONTEXT_LIMIT_EXCEEDED',message:'synthetic limit'}}})
  assert.equal((await pending).error.code,'CONTEXT_LIMIT_EXCEEDED')
  assert.deepEqual(client.view.error,previous)
  assert.equal(client.view.context.requestedTokens,8192)
  client.disconnected()
})

test('context UI has seven native keyboard steps capped at 256K and translated labels',()=>{
  const {client}=setup()
  for(locale of ['es','en']){
    const html=renderToStaticMarkup(React.createElement(ContextSettings,{view:client.view}))
    assert.match(html,/type="range" min="0" max="6" step="1"/)
    assert.match(html,/aria-valuetext="8K"/)
    assert.match(html,/>64K<\/button>/)
    assert.match(html,/>128K<\/button>/)
    assert.match(html,/>256K<\/button>/)
    assert.ok(html.includes((locale==='es'?settingsSpanish:settingsEnglish).contextTokensHint))
    assert.ok(html.includes(`aria-label="${locale==='es'?'Tokens de contexto':'Context tokens'}"`))
    assert.ok(html.includes(`aria-label="${locale==='es'?'Automático':'Automatic'}"`))
    assert.ok(html.includes(locale==='es'?'Tokens de contexto':'Context tokens'))
    assert.ok(html.includes(locale==='es'?'Automático':'Automatic'))
  }
  client.disconnected()
})

for (const tokens of [131072,262144]) test('context slider displays confirmed '+tokens+' tokens and proportional fill',()=>{
  const {client}=setup()
  client.view.context={requestedTokens:tokens,selectedTokens:tokens,errorCode:null}
  const html=renderToStaticMarkup(React.createElement(ContextSettings,{view:client.view}))
  assert.ok(html.includes('aria-valuetext="'+tokens/1024+'K"'))
  assert.match(html,tokens===262144 ? /--context-fill:100%/ : /--context-fill:83\.333/)
  client.disconnected()
})
