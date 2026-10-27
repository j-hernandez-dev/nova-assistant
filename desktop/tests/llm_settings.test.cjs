require('./register_typescript.cjs')
const fs=require('node:fs'),ts=require('typescript')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename)
require.extensions['.css']=()=>{}
const {test}=require('node:test'),assert=require('node:assert/strict'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),Module=require('node:module')
const {llmEnglish,llmSpanish}=require('../src/llm_locale.ts'),{settingsEnglish,settingsSpanish}=require('../src/settings_locale.ts')
const {settingsServicesEnglish,settingsServicesSpanish}=require('../src/settings_services_locale.ts')
let language='es'
const original=Module._load
Module._load=function(request){if(request==='../i18n')return{useI18n:()=>({locale:language,t:key=>({...language==='es'?settingsSpanish:settingsEnglish,...language==='es'?llmSpanish:llmEnglish,...language==='es'?settingsServicesSpanish:settingsServicesEnglish})[key]||key})};return original.apply(this,arguments)}
const {LLMSettings}=require('../src/components/LLMSettings.tsx')
Module._load=original
const view={status:{ready:true,model:'one:7b',provider:'ollama'},readiness:{ready:true,observedAt:'2026-10-19T00:00:00Z',reason:null},context:{requestedTokens:0,selectedTokens:8192},approvals:[],inputs:[]}
const visibility={hiddenModels:[],ready:true,busy:false,error:false,save:async()=>true}
test('LLM settings use the shared grouped layout, two charts and autosaving context in both languages',()=>{
 for(language of ['es','en']){
  const html=renderToStaticMarkup(React.createElement(LLMSettings,{view,models:['one:7b','new:9b'],visibility,active:false,locked:false}))
  assert.ok(html.includes(language==='es'?'Modelo LLM':'LLM model'))
  assert.ok(html.includes(language==='es'?'Motor de inferencia':'Inference engine'))
  assert.ok(html.includes(language==='es'?'Restablecer':'Reset'))
  assert.ok(html.includes(language==='es'?'<dt>Proveedor</dt>':'<dt>Provider</dt>'))
  assert.ok(html.includes(language==='es'?'<dt>Conexión</dt>':'<dt>Connection</dt>'))
  assert.doesNotMatch(html,/Abrir gestor de modelos|Open model manager/)
  assert.equal((html.match(/data-usage-chart=/g)||[]).length,2)
  assert.equal((html.match(/data-model-visibility=/g)||[]).length,2)
  assert.equal((html.match(/role="switch"/g)||[]).length,2)
  assert.doesNotMatch(html,/<form|type="submit"|provider-select|API Key|Clear filters|Export/)
 }
})
test('Known empty inventories and hidden model choices have distinct, accessible states',()=>{
 language='es'
 const empty=renderToStaticMarkup(React.createElement(LLMSettings,{view,models:[],visibility,active:false,locked:false}))
 assert.ok(empty.includes(llmSpanish.llmModelsEmpty))
 const hidden=renderToStaticMarkup(React.createElement(LLMSettings,{view,models:['one:7b'],visibility:{...visibility,hiddenModels:['one:7b']},active:false,locked:false}))
 assert.ok(hidden.includes(llmSpanish.llmNoVisibleModels));assert.doesNotMatch(hidden,/data-model-visibility="one:7b"[^>]*checked/)
})
