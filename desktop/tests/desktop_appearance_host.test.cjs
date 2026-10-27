const {test}=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'),os=require('node:os')
const {createDesktopPreferencesStore}=require('../electron/desktop_preferences.cjs')
const {defaultShortcuts}=require('../shared/keyboard_shortcuts.cjs')
const defaults={colorScheme:'system',lightTheme:'nova',darkTheme:'nova',interfaceFont:'system',codeFont:'system',showStartupScreen:true,startupMotion:true,mascotMotion:true}
function owned(t){const dir=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-appearance-host-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return dir}
function appearance(value){return Object.fromEntries(Object.keys(defaults).map(key=>[key,value[key]]))}
test('Appearance saves all themes and fonts independently while preserving General and shortcuts',t=>{
  const dir=owned(t),store=createDesktopPreferencesStore(dir)
  store.setGeneral({language:'en',autoSwitchView:true,transitionsEnabled:false});store.setShortcuts({...defaultShortcuts(),projects:'Mod+Alt+P'})
  const settings={...defaults,colorScheme:'light',lightTheme:'synthwave84',darkTheme:'matrix',interfaceFont:'Segoe UI',codeFont:'Cascadia Code',startupMotion:false}
  assert.equal(store.setAppearance(settings).success,true)
  assert.deepEqual(appearance(createDesktopPreferencesStore(dir).get()),settings)
  const snapshot=store.get();assert.equal(snapshot.locale,'en');assert.equal(snapshot.autoSwitchView,true);assert.equal(snapshot.transitionsEnabled,false);assert.equal(snapshot.shortcuts.projects,'Mod+Alt+P')
  assert.equal(store.setAppearance(defaults).success,true)
  assert.deepEqual(appearance(store.get()),defaults);assert.equal(store.get().shortcuts.projects,'Mod+Alt+P')
  assert.ok(!Object.hasOwn(store.get(),'reduceMotion'))
})
test('Legacy reduceMotion migrates both independent movements without rewriting startup preferences',t=>{
  const dir=owned(t),file=path.join(dir,'desktop-preferences.json')
  for(const input of [{reduceMotion:true},{reduceMotion:false},{reduceMotion:true,startupMotion:true,mascotMotion:false}]){
    const contents=JSON.stringify({schemaVersion:1,locale:'en',...input});fs.writeFileSync(file,contents)
    const value=createDesktopPreferencesStore(dir).get()
    assert.equal(value.startupMotion,input.startupMotion??!input.reduceMotion);assert.equal(value.mascotMotion,input.mascotMotion??!input.reduceMotion)
    assert.equal(value.colorScheme,'system');assert.equal(value.interfaceFont,'system');assert.equal(fs.readFileSync(file,'utf8'),contents)
  }
})
test('Strict Appearance validation rejects extra authority fields, invalid themes and unsafe font strings',t=>{
  const store=createDesktopPreferencesStore(owned(t));store.setAppearance({...defaults,darkTheme:'box'});const before=store.get()
  for(const input of [null,[],{}, {...defaults,colorScheme:'auto'},{...defaults,lightTheme:'missing'},{...defaults,interfaceFont:''},{...defaults,codeFont:' A '},{...defaults,interfaceFont:'bad\nfont'},{...defaults,codeFont:'a'.repeat(129)},{...defaults,mascotMotion:1},{...defaults,locale:'en'},{...defaults,autoApprove:true}]){
    assert.equal(store.setAppearance(input).success,false);assert.deepEqual(store.get(),before)
  }
  assert.equal(store.setAppearance({...defaults,interfaceFont:'Noto Sans CJK JP',codeFont:'Iosevka "Term"'}).success,true)
})
test('Legacy setter merges only old motion/startup fields and failed atomic saves keep effective Appearance',t=>{
  const dir=owned(t),store=createDesktopPreferencesStore(dir);store.setAppearance({...defaults,darkTheme:'matrix',interfaceFont:'Ubuntu'})
  assert.equal(store.setAppearance({reduceMotion:true,showStartupScreen:false}).success,true)
  assert.equal(store.get().darkTheme,'matrix');assert.equal(store.get().interfaceFont,'Ubuntu');assert.equal(store.get().mascotMotion,false)
  const blocked=path.join(dir,'blocked');fs.writeFileSync(blocked,'fixture');const failed=createDesktopPreferencesStore(blocked),before=failed.get()
  assert.equal(failed.setAppearance({...defaults,colorScheme:'dark'}).success,false);assert.deepEqual(failed.get(),before)
})
test('Font inventory IPC stays main-frame-only and native appearance updates broadcast presentation data only',()=>{
  const main=fs.readFileSync(path.join(__dirname,'../electron/main.ts'),'utf8'),preload=fs.readFileSync(path.join(__dirname,'../electron/preload.ts'),'utf8')
  const handler=main.slice(main.indexOf("ipcMain.handle('get-desktop-fonts'"),main.indexOf("ipcMain.handle('get-desktop-preferences'"))
  assert.match(handler,/if \(!validApplicationSender\(event\)\)/);assert.match(handler,/return desktopFonts\.get\(\)/)
  assert.doesNotMatch(handler,/applicationClient|sendToPython|signApproval/)
  assert.match(main,/nativeTheme\.on\('updated', syncDesktopAppearance\)/)
  assert.match(main,/if \(result\.success\) syncDesktopAppearance\(\)/)
  assert.match(preload,/ipcRenderer\.on\('desktop-appearance-changed', handler\)/);assert.match(preload,/return \(\) => ipcRenderer\.removeListener\('desktop-appearance-changed', handler\)/)
})
