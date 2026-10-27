const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),os=require('node:os')
const {shortcutDefinitions,defaultShortcuts,readShortcuts,validShortcuts,bindingIssue,bindingFromEvent,formatShortcut}=require('../shared/keyboard_shortcuts.cjs')
const {createDesktopPreferencesStore}=require('../electron/desktop_preferences.cjs')
const event=(key,more={})=>({key,ctrlKey:false,metaKey:false,altKey:false,shiftKey:false,...more})
function owned(t){const dir=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-keys-'));t.after(()=>{assert.ok(path.basename(dir).startsWith('nova-keys-'));fs.rmSync(dir,{recursive:true,force:true})});return dir}
test('Defaults retain the existing shortcuts, allow unassigned actions and have no collisions',()=>{
  const values=defaultShortcuts();assert.equal(validShortcuts(values),true)
  assert.equal(values.settings,'Mod+,');assert.equal(values.projects,'Mod+B');assert.equal(values.stopGeneration,'Escape');assert.equal(values.sendMessage,'Enter');assert.equal(values.newLine,'Shift+Enter');assert.equal(values.showHome,null)
  assert.equal(new Set(shortcutDefinitions.map(d=>d.id)).size,shortcutDefinitions.length)
  values.projects=null;assert.equal(validShortcuts(values),true);assert.equal(defaultShortcuts().projects,'Mod+B')
})
test('Sources, Memories and Models have distinct defaults in the sidebar order',()=>{
  const values=defaultShortcuts()
  assert.equal(values.sources,'Mod+Shift+F');assert.equal(values.memories,'Mod+Shift+N');assert.equal(values.models,'Mod+Shift+M')
  assert.deepEqual(shortcutDefinitions.filter(d=>['sources','memories','models'].includes(d.id)).map(d=>d.id),['sources','memories','models'])
  for(const id of ['sources','memories','models'])assert.equal(bindingIssue(id,values[id],values),null)
  assert.equal(formatShortcut(values.sources,'es'),'Ctrl+Mayús+F');assert.equal(formatShortcut(values.memories,'en',true),'Cmd+Shift+N')
})
test('Existing complete shortcut maps gain the new actions without overwriting custom or unassigned shortcuts',t=>{
  const legacy={...defaultShortcuts(),settings:'Mod+Alt+K',models:null};delete legacy.sources;delete legacy.memories
  const expected={...legacy,sources:'Mod+Shift+F',memories:'Mod+Shift+N'}
  assert.equal(validShortcuts(legacy),false);assert.deepEqual(readShortcuts(legacy),expected)
  const dir=owned(t),file=path.join(dir,'desktop-preferences.json')
  const raw=JSON.stringify({schemaVersion:1,locale:'en',language:'en',showFiles:false,shortcuts:legacy})
  fs.writeFileSync(file,raw)
  const store=createDesktopPreferencesStore(dir)
  assert.deepEqual(store.get().shortcuts,expected);assert.equal(fs.readFileSync(file,'utf8'),raw)
  assert.equal(store.get().showFiles,false);assert.equal(store.setShortcuts(legacy).success,false)
  assert.equal(store.setLocale('es').success,true);assert.deepEqual(createDesktopPreferencesStore(dir).get().shortcuts,expected)
})
test('Legacy custom assignments take precedence over new defaults; corrupt maps still fall back safely',()=>{
  const legacy={...defaultShortcuts(),focusPrompt:'Mod+Shift+F',models:'Mod+Shift+N'};delete legacy.sources;delete legacy.memories
  assert.deepEqual(readShortcuts(legacy),{...legacy,sources:null,memories:null})
  for(const bad of [{...legacy,extra:null},{...legacy,settings:undefined},{...legacy,models:'Mod+B'}])assert.deepEqual(readShortcuts(bad),defaultShortcuts())
})
test('Shortcut validation rejects conflicts, reserved editing combinations and malformed records',()=>{
  const defaults=defaultShortcuts()
  assert.deepEqual(bindingIssue('models','Mod+B',defaults),{kind:'conflict',action:'projects'})
  for(const value of ['Mod+C','Mod+V','Mod+W','Alt+F4','F5'])assert.equal(bindingIssue('models',value,defaults).kind,'reserved',value)
  for(const value of ['A','Shift+A','Mod+Mod+A','Alt+Mod+J','Mod+Tab','Mod+Unknown',{},'',undefined])assert.ok(bindingIssue('models',value,defaults),String(value))
  for(const record of [null,[],{}, {...defaults, extra:'Mod+K'},{...defaults, models:'Mod+B'},{...defaults,settings:undefined}])assert.equal(validShortcuts(record),false)
  assert.equal(bindingIssue('models','Mod+Alt+K',defaults),null)
})
test('Event matching respects modifier identity, composition, AltGraph and platform conventions',()=>{
  assert.equal(bindingFromEvent(event('b',{ctrlKey:true})),'Mod+B')
  assert.equal(bindingFromEvent(event('b',{metaKey:true}),true),'Mod+B')
  assert.equal(bindingFromEvent(event('b',{metaKey:true})),null)
  assert.equal(bindingFromEvent(event('Enter',{ctrlKey:true,shiftKey:true})),'Mod+Shift+Enter')
  for(const more of [{isComposing:true},{keyCode:229},{getModifierState:name=>name==='AltGraph'}])assert.equal(bindingFromEvent(event('b',{ctrlKey:true,...more})),null)
  for(const key of ['Shift','Control','Meta','Alt','Dead','Process','Tab'])assert.equal(bindingFromEvent(event(key)),null)
  assert.equal(bindingFromEvent(event(' ')),'Space');assert.equal(bindingFromEvent(event('+',{ctrlKey:true})),'Mod+Plus')
  assert.equal(formatShortcut('Mod+Shift+Enter','es'),'Ctrl+Mayús+Intro');assert.equal(formatShortcut('Mod+,','en',true),'Cmd+,')
})
test('Legacy profiles gain defaults without a startup rewrite, and unrelated preferences survive shortcut saves',t=>{
  const dir=owned(t),file=path.join(dir,'desktop-preferences.json'),legacy=JSON.stringify({schemaVersion:1,locale:'en',reduceMotion:true,showStartupScreen:false})
  fs.writeFileSync(file,legacy)
  const store=createDesktopPreferencesStore(dir);assert.deepEqual(readShortcuts(store.get().shortcuts),defaultShortcuts());assert.equal(fs.readFileSync(file,'utf8'),legacy)
  const next={...defaultShortcuts(),settings:'Mod+Alt+S',models:null}
  assert.equal(store.setShortcuts(next).success,true)
  next.settings=null
  const copy=store.get();copy.shortcuts.settings=null
  const saved=createDesktopPreferencesStore(dir).get();assert.equal(saved.shortcuts.settings,'Mod+Alt+S');assert.equal(saved.locale,'en');assert.equal(saved.startupMotion,false);assert.equal(saved.mascotMotion,false);assert.equal(saved.showStartupScreen,false)
  store.setLocale('es');store.setAppearance({reduceMotion:false,showStartupScreen:true})
  assert.equal(createDesktopPreferencesStore(dir).get().shortcuts.settings,'Mod+Alt+S')
  const before=fs.readFileSync(file,'utf8');assert.equal(store.setShortcuts({...defaultShortcuts(),models:'Mod+B'}).success,false);assert.equal(fs.readFileSync(file,'utf8'),before)
})
test('Corrupt bindings fall back safely, and failed writes preserve all effective shortcuts',t=>{
  const dir=owned(t),file=path.join(dir,'desktop-preferences.json')
  fs.writeFileSync(file,JSON.stringify({schemaVersion:1,locale:'en',shortcuts:{...defaultShortcuts(),models:'Mod+B'}}))
  const store=createDesktopPreferencesStore(dir);assert.deepEqual(readShortcuts(store.get().shortcuts),defaultShortcuts());assert.equal(store.get().locale,'en')
  const blocked=path.join(dir,'blocked');fs.writeFileSync(blocked,'fixture');const failed=createDesktopPreferencesStore(blocked)
  const before=failed.get();assert.equal(failed.setShortcuts(defaultShortcuts()).success,false);assert.deepEqual(failed.get(),before)
})
