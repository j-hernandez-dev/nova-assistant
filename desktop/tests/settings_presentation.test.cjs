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
const Module = require('node:module')
const {settingsEnglish,settingsSpanish} = require('../src/settings_locale.ts')
const {shortcutsEnglish,shortcutsSpanish} = require('../src/shortcuts_locale.ts')
const {storageEnglish,storageSpanish} = require('../src/storage_locale.ts')
let locale='es'
const dictionary = {es:{...settingsSpanish,...shortcutsSpanish,...storageSpanish},en:{...settingsEnglish,...shortcutsEnglish,...storageEnglish}}
const baseLabels = {es:{settingsTitle:'Configuración',closeDialog:'Cerrar ventana',language:'Idioma de la interfaz',
  keyboardShortcuts:'Atajos de teclado',settings:'Configuración',toggleExplorer:'Mostrar archivos',stopHint:'Detener',newLine:'Nueva línea',
  localeSaveFailed:'No se pudo guardar el idioma.',checking:'Comprobando…'},
en:{settingsTitle:'Settings',closeDialog:'Close dialog',language:'Interface language',keyboardShortcuts:'Keyboard shortcuts',settings:'Settings',
  toggleExplorer:'Toggle files',stopHint:'Stop',newLine:'New line',localeSaveFailed:'Language could not be saved.',checking:'Checking…'}}
require.cache[require.resolve('../src/i18n.tsx')]={id:require.resolve('../src/i18n.tsx'),filename:require.resolve('../src/i18n.tsx'),loaded:true,
  exports:{useI18n:()=>({locale,general,generalReady:true,generalSaveState,saveGeneral:async()=>false,setLocale:async()=>false,t:key=>dictionary[locale][key]||baseLabels[locale][key]||key})}}
require.cache[require.resolve('../src/components/ModalHost.tsx')]={id:require.resolve('../src/components/ModalHost.tsx'),loaded:true,
  exports:{ModalHost:({children,...props})=>React.createElement('div',{'data-modal':true,className:props.className},children)}}
const originalLoad = Module._load
Module._load = function(request,parent,isMain) {
  if(request === '../appearance') return {useAppearance:()=>({appearance:{colorScheme:'system',lightTheme:'nova',darkTheme:'nova',interfaceFont:'system',codeFont:'system',showStartupScreen:true,startupMotion:true,mascotMotion:true,mascotAppearance:'2d'},ready:true,saveState:'idle',effectiveScheme:'dark',saveAppearance:async()=>false})}
  return originalLoad.apply(this,arguments)
}
const {SettingsPanel} = require('../src/components/SettingsPanel.tsx')
Module._load = originalLoad
const {GeneralSettings}=require('../src/components/GeneralSettings.tsx')
let general={language:'system',autoSwitchView:false,transitionsEnabled:true,showFiles:true,collapsibleSourceContext:false},generalSaveState='idle'
const render = (component,props) => renderToStaticMarkup(React.createElement(component,props))
const formProps = {locale:'es',draftLocale:'en',saveState:'idle',onChange(){},onSave(){},onCancel(){}}

test('Settings domains have isolated surfaces and hidden sections keep their drafts mounted',()=>{
  const domains=['chat','connection','embedding','projects','web','memory','storage','knowledge','about']
  const slots=Object.fromEntries(domains.map(name=>[name,React.createElement('div',{'data-domain':name},name)]))
  for(const domain of domains){
    const html=render(SettingsPanel,{onClose(){},initialSection:domain,...slots})
    assert.ok(html.includes(`data-domain="${domain}"`),domain)
    assert.equal((html.match(/data-settings-domain=/g)||[]).length,9,domain)
    if(domain!=='about')assert.ok(html.includes(`data-settings-domain="${domain}">`),domain)
    assert.equal((html.match(/aria-current="page"/g)||[]).length,1,domain)
    assert.ok(!html.includes('<form'),domain)
  }
  const chat=render(SettingsPanel,{onClose(){},initialSection:'chat',...slots})
  assert.ok(chat.indexOf('>General</span>')<chat.indexOf('>Chats</span>'))
  const general=render(SettingsPanel,{onClose(){},initialSection:'general',...slots})
  assert.equal((general.match(/<form/g)||[]).length,0)
  assert.equal((general.match(/hidden="" data-settings-domain=/g)||[]).length,9)
})

test('General exposes the five interface preferences and autosave without draft buttons',()=>{
  locale='es';generalSaveState='idle'
  const html=render(GeneralSettings,{titleId:'general-title'})
  for(const text of ['Configuración general de la aplicación.','Interfaz','Idioma de la interfaz de la aplicación','Mostrar contenido del proyecto','Cambio de vista','Activar transiciones','Sistema','Restablecer'])assert.ok(html.includes(text),text)
  assert.equal((html.match(/role="switch"/g)||[]).length,4)
  assert.match(html,/Plegable de contexto de fuentes/);assert.match(html,/data-general="collapsibleSourceContext"/)
  assert.ok(html.includes('data-settings-select="language"'));assert.ok(!html.includes('<select'))
  assert.ok(!html.includes('<form'));assert.ok(!html.includes('Cancelar cambios'));assert.ok(!html.includes('Los cambios se aplican sólo al guardar.'))
})
test('Pending and failed general saves never claim that settings were applied',()=>{
  generalSaveState='unconfirmed'
  const pending=render(GeneralSettings,{titleId:'general-title'})
  assert.equal((pending.match(/disabled=""/g)||[]).length,6)
  assert.ok(pending.includes('El guardado no se ha confirmado.'));assert.ok(!pending.includes('Preferencias guardadas.'))
  generalSaveState='failed'
  const failed=render(GeneralSettings,{titleId:'general-title'})
  assert.ok(failed.includes('role="alert"'));assert.ok(failed.includes('Los ajustes anteriores siguen activos.'))
  generalSaveState='idle'
})
test('Settings dictionaries cover both interfaces and General renders English without Spanish controls',()=>{
  assert.deepEqual(Object.keys(settingsEnglish).sort(),Object.keys(settingsSpanish).sort())
  locale='en';generalSaveState='saved'
  const html=render(GeneralSettings,{titleId:'general-title'})
  for(const text of ['General application settings.','Language','System','Show project content','View switching','Enable transitions','Reset','Preferences saved.'])assert.ok(html.includes(text),text)
  assert.ok(!html.includes('Cancelar cambios'));assert.ok(!html.includes('Preferencias guardadas.'))
  locale='es';generalSaveState='idle'
})

test('Shortcuts have their own section in Interface before Models and are removed from General',()=>{
  const html=render(SettingsPanel,{onClose(){}})
  assert.ok(!html.includes('nova-settings-shortcuts'))
  assert.ok(html.indexOf('data-settings-section="appearance"')<html.indexOf('data-settings-section="shortcuts"'))
  assert.ok(html.indexOf('data-settings-section="shortcuts"')<html.indexOf('data-settings-section="connection"'))
  assert.ok(html.indexOf('data-settings-section="shortcuts"')<html.indexOf('data-settings-section="about"'))
  const section=render(SettingsPanel,{onClose(){},initialSection:'shortcuts'})
  assert.ok(section.includes('Buscar atajos'));assert.ok(section.includes('Personaliza atajos para acciones comunes'))
  assert.ok(section.includes('Restablecer'));assert.ok(section.includes('data-icon="keyboard"'))
  assert.equal((section.match(/<form/g)||[]).length,1)
  assert.ok(section.includes('class="nova-shortcuts-search"'),'the only form submits the search field')
  assert.ok(!section.includes('Cancelar cambios'))
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
