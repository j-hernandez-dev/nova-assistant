require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require.extensions['.tsx'] = (module,filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
const React = require('react')
const {renderToStaticMarkup} = require('react-dom/server')
const presentation = require('../src/model_catalog_presentation.ts')
const {ModelRow,ModelActions} = require('../src/components/ModelPicker.tsx')
const render = (component,props) => renderToStaticMarkup(React.createElement(component,props))

test('Installed selection uses exact tag and never substitutes another tagged variant',()=>{
  const {installedModelName:resolve,installedVariants:variants}=presentation
  assert.equal(resolve('qwen3.5:9b',['qwen3.5:4b']),null)
  assert.equal(resolve('qwen3.5',['qwen3.5:9b']),'qwen3.5:9b')
  assert.equal(resolve('qwen3.5',['qwen3.5:9b','qwen3.5:4b']),null)
  assert.equal(resolve('qwen3.5:9b',['qwen3.5:9b','qwen3.5:4b']),'qwen3.5:9b')
  assert.equal(resolve('qwen3.5:9b',undefined),null)
  assert.deepEqual(variants('qwen3.5',['qwen3.5:9b','qwen3.5:4b','qwen3:8b']),['qwen3.5:9b','qwen3.5:4b'])
})
test('Catalog filters all existing metadata without mutating or dropping unknown categories',()=>{
  const models=[{name:'owned:1b',display:'Owned One',description:'Small fixture',tags:['tools'],category:'General'},
    {name:'other:2b',display:'Other',description:'Coder',tags:['code'],category:'Future category'}]
  const before=JSON.stringify(models)
  assert.deepEqual(presentation.filterCatalog(models,' TOOLS ',null),[models[0]])
  assert.deepEqual(presentation.filterCatalog(models,'coder','Future category'),[models[1]])
  assert.deepEqual(presentation.catalogSections.map(section=>section.id),['all','installed','recommend'])
  assert.equal(presentation.modelCategoryKey('Japanese'),null)
  assert.equal(presentation.modelCategoryKey('日本語'),null)
  assert.equal(presentation.modelCategoryKey('Future category'),null)
  assert.equal(presentation.modelCategoryKey('constructor'),null)
  assert.equal(presentation.modelErrorKey('toString'),'actionFailed')
  assert.equal(JSON.stringify(models),before)
})
test('Unknown metrics stay unknown; progress percent only comes from real progress text',()=>{
  for(const bad of [undefined,0,NaN,Infinity,-1])assert.equal(presentation.modelContext(bad),'')
  assert.equal(presentation.modelContext(32768),'32K')
  for(const bad of [undefined,0,NaN,4.5,6])assert.equal(presentation.easeRating(bad),null)
  assert.equal(presentation.easeRating(4),4)
  assert.equal(presentation.pullPercent('pulling manifest'),null)
  assert.equal(presentation.pullPercent('pulling layer 48%'),48)
  assert.equal(presentation.pullPercent('complete 100%'),100)
})
test('Model rows escape source content and omit unavailable size',()=>{
  const html=render(ModelRow,{name:'owned:1b',display:'<script>bad</script>',description:'<img src=x>',size:NaN,
    selected:false,actions:'action'})
  assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'))
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('GB'))
  assert.ok(!html.includes('role="button"'))
})
const actionProps={name:'owned',current:'other:1b',exact:null,ambiguous:false,cloudOnly:false,disabled:false,
  mutationLocked:false,pulling:false,deleting:false,canDelete:true,onSelect(){},onPull(){},onDelete(){},onViewInstalled(){}}
test('Installed family exposes exact selection; ambiguous family routes to installed variants',()=>{
  const exact=render(ModelActions,{...actionProps,exact:'owned:1b'})
  assert.ok(exact.includes('owned:1b'));assert.ok(exact.includes('Usar'));assert.ok(!exact.includes('Descargar'))
  const ambiguous=render(ModelActions,{...actionProps,ambiguous:true})
  assert.ok(ambiguous.includes('Ver variantes instaladas'));assert.ok(!ambiguous.includes('Descargar'))
  const selected=render(ModelActions,{...actionProps,exact:'owned:1b',current:'owned:1b'})
  assert.ok(selected.includes('Activo'));assert.ok(!selected.includes('Eliminar'))
})
test('Cloud-only results do not download; pending mutations disable other model actions',()=>{
  const cloud=render(ModelActions,{...actionProps,cloudOnly:true})
  assert.ok(!cloud.includes('<button'));assert.ok(!cloud.includes('Descargar'))
  const pending=render(ModelActions,{...actionProps,mutationLocked:true})
  assert.ok(pending.includes('disabled=""'))
})
test('Model actions and host error messages have distinct ES and EN product text',()=>{
  for(const code of ['MODEL_CATALOG_FAILED','MODEL_RECOMMEND_FAILED','MODEL_DOWNLOAD_FAILED',
    'MODEL_DELETE_FAILED','MODEL_SYNC_FAILED','MODEL_OPERATION_UNCONFIRMED']){
    const key=presentation.modelErrorKey(code)
    assert.notEqual(key,'actionFailed')
    const source=fs.readFileSync(require.resolve('../src/i18n.tsx'),'utf8')
    const values=[...source.matchAll(new RegExp(`${key}: '([^']*)'`,'g'))].map(match=>match[1])
    assert.equal(values.length,2,key);assert.notEqual(values[0],values[1])
  }
  assert.equal(presentation.modelErrorKey('RAW_PRIVATE_TEXT'),'actionFailed')
})
