require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os')
const {createDesktopPreferencesStore}=require('../electron/desktop_preferences.cjs')
const {defaultGeneral,readGeneral,applyGeneral}=require('../shared/desktop_general.ts')
const {defaultShortcuts}=require('../shared/keyboard_shortcuts.cjs')
function owned(t){const dir=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-general-'));t.after(()=>{assert.ok(path.basename(dir).startsWith('nova-general-'));fs.rmSync(dir,{recursive:true,force:true})});return dir}
test('Fresh settings follow the system language, use supported-language fallback and remain dynamic only in System mode',t=>{
  const dir=owned(t);let system='es-MX'
  const store=createDesktopPreferencesStore(dir,()=>system)
  assert.deepEqual(readGeneral(store.get()),defaultGeneral);assert.equal(store.get().locale,'es')
  system='en-US';assert.equal(store.get().locale,'en');system='fr-FR';assert.equal(store.get().locale,'en')
  assert.equal(store.setGeneral({...defaultGeneral,language:'es'}).success,true);assert.equal(store.get().locale,'es')
  system='en-GB';assert.equal(store.get().locale,'es')
  assert.equal(store.setGeneral(defaultGeneral).success,true);assert.equal(store.get().locale,'en')
})
test('Legacy manual language and appearance survive migration without rewriting the profile at startup',t=>{
  const dir=owned(t),file=path.join(dir,'desktop-preferences.json'),legacy=JSON.stringify({schemaVersion:1,locale:'en',reduceMotion:true,showStartupScreen:false})
  fs.writeFileSync(file,legacy)
  const store=createDesktopPreferencesStore(dir,()=> 'es-MX')
  assert.equal(store.get().language,'en');assert.equal(store.get().locale,'en');assert.equal(store.get().startupMotion,false);assert.equal(store.get().mascotMotion,false)
  assert.equal(store.get().transitionsEnabled,true);assert.equal(store.get().showFiles,true);assert.equal(fs.readFileSync(file,'utf8'),legacy)
})
test('General resets only its own fields and persists independently of shortcuts and decorative motion',t=>{
  const dir=owned(t),store=createDesktopPreferencesStore(dir,()=> 'en-US')
  store.setAppearance({reduceMotion:true,showStartupScreen:false});store.setShortcuts({...defaultShortcuts(),projects:'Mod+Alt+P'})
  const changed={language:'es',autoSwitchView:true,transitionsEnabled:false,showFiles:false,collapsibleSourceContext:true}
  assert.equal(store.setGeneral(changed).success,true)
  assert.deepEqual(readGeneral(createDesktopPreferencesStore(dir,()=> 'en-US').get()),changed)
  store.setGeneral(defaultGeneral)
  const value=createDesktopPreferencesStore(dir,()=> 'en-US').get()
  assert.deepEqual(readGeneral(value),defaultGeneral);assert.equal(value.locale,'en')
  assert.equal(value.startupMotion,false);assert.equal(value.mascotMotion,false);assert.equal(value.showStartupScreen,false);assert.equal(value.shortcuts.projects,'Mod+Alt+P')
})
test('Invalid input and storage failures preserve the last confirmed General values',t=>{
  const dir=owned(t),store=createDesktopPreferencesStore(dir)
  store.setGeneral({...defaultGeneral,autoSwitchView:true});const before=store.get()
  for(const invalid of [null,[],{}, {...defaultGeneral,language:'fr'},{...defaultGeneral,transitionsEnabled:'false'},{...defaultGeneral,showFiles:'false'},{...defaultGeneral,collapsibleSourceContext:'true'},{...defaultGeneral,autoApprove:true}]){
    assert.equal(store.setGeneral(invalid).success,false);assert.deepEqual(store.get(),before)
  }
  const blocked=path.join(dir,'file');fs.writeFileSync(blocked,'fixture');const failed=createDesktopPreferencesStore(blocked)
  const previous=failed.get();assert.equal(failed.setGeneral(defaultGeneral).success,false);assert.deepEqual(failed.get(),previous)
})

test('Source context is inline by default, migrates without rewriting, and survives legacy General writes',t=>{
  const dir=owned(t),file=path.join(dir,'desktop-preferences.json'),old=JSON.stringify({schemaVersion:1,locale:'es',showFiles:false})
  fs.writeFileSync(file,old)
  const store=createDesktopPreferencesStore(dir)
  assert.equal(store.get().collapsibleSourceContext,false);assert.equal(fs.readFileSync(file,'utf8'),old)
  assert.equal(store.setGeneral({...defaultGeneral,collapsibleSourceContext:true}).success,true)
  assert.equal(createDesktopPreferencesStore(dir).get().collapsibleSourceContext,true)
  store.setGeneral({language:'en',autoSwitchView:false,transitionsEnabled:true})
  assert.equal(store.get().collapsibleSourceContext,true)
  store.setLocale('es');store.setShortcuts(defaultShortcuts());store.setZoomPercent(120)
  assert.equal(createDesktopPreferencesStore(dir).get().collapsibleSourceContext,true)
  store.setGeneral(defaultGeneral);assert.equal(store.get().collapsibleSourceContext,false)
  for(const value of [undefined,null,'true',1])assert.equal(readGeneral({collapsibleSourceContext:value}).collapsibleSourceContext,false)
})
test('Applying General changes only transition presentation, leaving decorative motion separate',()=>{
  const attrs={'data-nova-startup-motion':'false','data-nova-mascot-motion':'true'},doc={documentElement:{setAttribute:(name,value)=>{attrs[name]=value}}}
  applyGeneral(doc,{...defaultGeneral,transitionsEnabled:false})
  assert.equal(attrs['data-nova-transitions'],'false');assert.equal(attrs['data-nova-startup-motion'],'false');assert.equal(attrs['data-nova-mascot-motion'],'true')
})

test('Legacy General writes preserve a saved files preference; missing or invalid stored flags default to visible',t=>{
  const dir=owned(t),store=createDesktopPreferencesStore(dir)
  assert.equal(store.get().showFiles,true)
  assert.equal(store.setGeneral({...defaultGeneral,showFiles:false}).success,true)
  assert.equal(store.setGeneral({language:'en',autoSwitchView:true,transitionsEnabled:false}).success,true)
  assert.equal(createDesktopPreferencesStore(dir).get().showFiles,false)
  for(const value of [undefined,null,'false',0])assert.equal(readGeneral({showFiles:value}).showFiles,true)
})
