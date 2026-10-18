require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require.extensions['.tsx'] = (module,filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
require.extensions['.css'] = () => {}
const React = require('react')
const {renderToStaticMarkup} = require('react-dom/server')
const {settingsEnglish,settingsSpanish} = require('../src/settings_locale.ts')
let locale='es'
const dictionary = {es:settingsSpanish,en:settingsEnglish}
const baseLabels = {es:{settingsTitle:'Configuración',closeDialog:'Cerrar ventana',language:'Idioma de la interfaz',
  keyboardShortcuts:'Atajos de teclado',settings:'Configuración',toggleExplorer:'Mostrar archivos',stopHint:'Detener',newLine:'Nueva línea',
  localeSaveFailed:'No se pudo guardar el idioma.',checking:'Comprobando…'},
en:{settingsTitle:'Settings',closeDialog:'Close dialog',language:'Interface language',keyboardShortcuts:'Keyboard shortcuts',settings:'Settings',
  toggleExplorer:'Toggle files',stopHint:'Stop',newLine:'New line',localeSaveFailed:'Language could not be saved.',checking:'Checking…'}}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),filename:require.resolve('../src/i18n.tsx'),loaded:true,
  exports:{useI18n:()=>({locale,setLocale:async()=>false,t:key=>dictionary[locale][key]||baseLabels[locale][key]||key})}}
require.cache[require.resolve('../src/components/ModalHost.tsx')]={id:require.resolve('../src/components/ModalHost.tsx'),loaded:true,
  exports:{ModalHost:({children,...props})=>React.createElement('div',{'data-modal':true,className:props.className},children)}}
const {SettingsPanel,GeneralSettingsForm,persistLocaleDraft} = require('../src/components/SettingsPanel.tsx')
const render = (component,props) => renderToStaticMarkup(React.createElement(component,props))
const formProps = {locale:'es',draftLocale:'en',saveState:'idle',onChange(){},onSave(){},onCancel(){}}

test('Settings domains have isolated surfaces and hidden sections keep their drafts mounted',()=>{
  const domains=['chat','connection','projects','web','memory','knowledge','about']
  const slots=Object.fromEntries(domains.map(name=>[name,React.createElement('div',{'data-domain':name},name)]))
  for(const domain of domains){
    const html=render(SettingsPanel,{onClose(){},initialSection:domain,...slots})
    assert.ok(html.includes(`data-domain="${domain}"`),domain)
    assert.equal((html.match(/data-settings-domain=/g)||[]).length,7,domain)
    if(domain!=='about')assert.ok(html.includes(`data-settings-domain="${domain}">`),domain)
    assert.equal((html.match(/aria-current="page"/g)||[]).length,1,domain)
    assert.ok(!html.includes('<form'),domain)
  }
  const chat=render(SettingsPanel,{onClose(){},initialSection:'chat',...slots})
  assert.ok(chat.indexOf('>General</span>')<chat.indexOf('>Chats</span>'))
  const general=render(SettingsPanel,{onClose(){},initialSection:'general',...slots})
  assert.equal((general.match(/<form/g)||[]).length,1)
  assert.equal((general.match(/hidden="" data-settings-domain=/g)||[]).length,7)
})

test('General shows a language draft without claiming it is saved',()=>{
  locale='es'
  const html=render(GeneralSettingsForm,formProps)
  assert.ok(html.includes('<option value="en" selected="">English</option>'))
  assert.ok(html.includes('Los cambios se aplican sólo al guardar.'))
  assert.ok(html.includes('No cambia la CLI ni el idioma de las respuestas del modelo.'))
  assert.ok(!html.includes('Preferencias guardadas.'))
  assert.ok(!html.includes('disabled=""'))
  const unchanged=render(GeneralSettingsForm,{...formProps,draftLocale:'es'})
  assert.equal((unchanged.match(/disabled=""/g)||[]).length,2)
})

test('Unconfirmed persistence locks controls and never reports success',()=>{
  const html=render(GeneralSettingsForm,{...formProps,saveState:'unconfirmed'})
  assert.equal((html.match(/disabled=""/g)||[]).length,3)
  assert.ok(html.includes('El guardado no se ha confirmado.'))
  assert.ok(!html.includes('Preferencias guardadas.'))
  const failed=render(GeneralSettingsForm,{...formProps,saveState:'failed'})
  assert.ok(failed.includes('role="alert"'))
  assert.ok(!failed.includes('Preferencias guardadas.'))
})

test('A slow receipt reports uncertainty, remains pending and can later confirm',async()=>{
  let resolveReceipt,notices=0,calls=0,settled=false
  const receipt=new Promise(resolve=>{resolveReceipt=resolve})
  const saving=persistLocaleDraft(async next=>{calls++;assert.equal(next,'en');return await receipt},'en',()=>{notices++},5)
  saving.then(()=>{settled=true})
  await new Promise(resolve=>setTimeout(resolve,15))
  assert.equal(notices,1);assert.equal(calls,1);assert.equal(settled,false)
  resolveReceipt(true)
  assert.equal(await saving,true)
})

test('Persistence errors are returned as failure without uncaught exceptions or delayed notices',async()=>{
  let notices=0
  assert.equal(await persistLocaleDraft(async()=>{throw new Error('owned failure')},'es',()=>{notices++},5),false)
  assert.equal(await persistLocaleDraft(async()=>false,'en',()=>{notices++},5),false)
  await new Promise(resolve=>setTimeout(resolve,10))
  assert.equal(notices,0)
})

test('Both Desktop dictionaries contain every settings label and render translated controls',()=>{
  assert.deepEqual(Object.keys(settingsEnglish).sort(),Object.keys(settingsSpanish).sort())
  assert.ok(Object.values(settingsEnglish).every(value=>typeof value==='string'&&value.length))
  assert.ok(Object.values(settingsSpanish).every(value=>typeof value==='string'&&value.length))
  locale='en'
  const html=render(GeneralSettingsForm,{...formProps,saveState:'saved'})
  assert.ok(html.includes('Preferences saved.'));assert.ok(html.includes('Cancel changes'))
  assert.ok(!html.includes('Preferencias guardadas.'))
  locale='es'
})

test('Settings preserve existing shortcuts and expose no updater or speculative capabilities',()=>{
  const html=render(SettingsPanel,{onClose(){}})
  for(const shortcut of ['Ctrl/Cmd+,','Ctrl/Cmd+B','Shift+Enter'])assert.ok(html.includes(shortcut))
  assert.equal((html.match(/aria-current="page"/g)||[]).length,1)
  const source=fs.readFileSync(require.resolve('../src/components/SettingsPanel.tsx'),'utf8')
  for(const operation of ['checkAppUpdate','installAppUpdate','do_update','openExternalUrl'])assert.ok(!source.includes(operation))
})

test('Two-column settings layout keeps independent navigation and content scrolling at compact sizes',()=>{
  const css=fs.readFileSync(require.resolve('../src/settings.css'),'utf8')
  assert.ok(css.includes('grid-template-columns: 220px minmax(0, 1fr)'))
  assert.ok(css.includes('grid-template-columns: 174px minmax(0, 1fr)'))
  assert.ok(css.includes('@media (max-height: 520px)'))
  assert.ok(css.includes('overflow-y: auto'))
  assert.ok(css.includes('min-height: 0'))
})
