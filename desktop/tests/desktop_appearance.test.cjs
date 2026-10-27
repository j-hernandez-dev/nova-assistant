require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict')
const {defaultAppearance,readAppearance,validAppearance,sameAppearance,appearancePresentation,applyAppearance}=require('../shared/desktop_appearance.ts')
const {themeIds,themePalettes,resolveTheme,SYSTEM_INTERFACE_FONT,SYSTEM_CODE_FONT}=require('../shared/desktop_theme.ts')

test('Appearance defaults follow the OS and expose two independent system font roles',()=>{
  assert.deepEqual(readAppearance(undefined),defaultAppearance)
  assert.equal(defaultAppearance.colorScheme,'system');assert.equal(defaultAppearance.interfaceFont,'system');assert.equal(defaultAppearance.codeFont,'system')
  assert.equal(defaultAppearance.startupMotion,true);assert.equal(defaultAppearance.mascotMotion,true)
  assert.equal(SYSTEM_INTERFACE_FONT,'system-ui, sans-serif');assert.equal(SYSTEM_CODE_FONT,'ui-monospace, monospace')
  assert.equal(validAppearance({...defaultAppearance,schemaVersion:1,locale:'en',transitionsEnabled:false}),true)
})
test('Legacy decorative motion migrates without overriding explicit per-element settings',()=>{
  assert.deepEqual(readAppearance({reduceMotion:true}),{...defaultAppearance,startupMotion:false,mascotMotion:false})
  assert.deepEqual(readAppearance({reduceMotion:true,startupMotion:true}),{...defaultAppearance,startupMotion:true,mascotMotion:false})
  assert.deepEqual(readAppearance({reduceMotion:false,mascotMotion:false}),{...defaultAppearance,mascotMotion:false})
})
test('Mascot design defaults to 2D, validates both choices, and is independent from motion',()=>{
  assert.equal(defaultAppearance.mascotAppearance,'2d')
  assert.equal(readAppearance({}).mascotAppearance,'2d')
  assert.equal(readAppearance({mascotAppearance:'unknown'}).mascotAppearance,'2d')
  assert.equal(validAppearance({...defaultAppearance,mascotAppearance:'unknown'}),false)
  assert.equal(validAppearance({...defaultAppearance,mascotAppearance:'3d',mascotMotion:false}),true)
  assert.equal(sameAppearance(defaultAppearance,{...defaultAppearance,mascotAppearance:'3d'}),false)
  assert.equal(appearancePresentation({...defaultAppearance,mascotAppearance:'3d'},false).attributes['data-nova-mascot-appearance'],'3d')
})
test('Shared font and theme parsing matches host accepted values and rejects invalid known settings',()=>{
  for(const invalid of ['', ' leading', 'trailing ', 'x'.repeat(129), 'Control\nFont', 'Delete\u007fFont']){
    assert.equal(readAppearance({...defaultAppearance,interfaceFont:invalid}).interfaceFont,'system')
    assert.equal(validAppearance({...defaultAppearance,codeFont:invalid}),false)
  }
  for(const invalid of [{colorScheme:'auto'},{lightTheme:'missing'},{darkTheme:'missing'},{startupMotion:'true'},{mascotMotion:1}])assert.equal(validAppearance({...defaultAppearance,...invalid}),false)
  assert.equal(validAppearance({...defaultAppearance,interfaceFont:'Noto Sans CJK JP',codeFont:'Iosevka "Term"'}),true)
  assert.equal(sameAppearance(defaultAppearance,{...defaultAppearance}),true)
  assert.equal(sameAppearance(defaultAppearance,{...defaultAppearance,mascotMotion:false}),false)
})
test('All four themes have complete light and dark palettes and System preserves each selected variant',()=>{
  assert.deepEqual(themeIds,['nova','synthwave84','matrix','box'])
  const keys=Object.keys(themePalettes.dark.nova.colors).sort()
  for(const mode of ['light','dark'])for(const id of themeIds){
    const theme=resolveTheme({...defaultAppearance,colorScheme:mode,lightTheme:id,darkTheme:id},mode!=='dark')
    assert.equal(theme.id,id);assert.equal(theme.mode,mode);assert.deepEqual(Object.keys(theme.colors).sort(),keys)
    assert.ok(theme.colors['--text']);assert.notEqual(theme.colors['--bg'],theme.colors['--text']);assert.equal(theme.colors['--nova-emblem-bright'],mode==='light'?'#15161b':'#ffffff')
  }
  const value={...defaultAppearance,lightTheme:'matrix',darkTheme:'synthwave84'}
  assert.equal(resolveTheme(value,false).id,'matrix');assert.equal(resolveTheme(value,true).id,'synthwave84')
})
test('Applying Appearance updates CSS roles and motion independently without touching interface transition settings',()=>{
  const attrs={'data-nova-reduce-motion':'true','data-nova-transitions':'false'},variables={}
  const doc={documentElement:{setAttribute:(key,value)=>{attrs[key]=value},removeAttribute:key=>delete attrs[key],style:{setProperty:(key,value)=>{variables[key]=value}}}}
  const chosen={...defaultAppearance,colorScheme:'light',lightTheme:'box',interfaceFont:'Noto "Sans"',codeFont:'Mono; color:red',startupMotion:false,mascotMotion:true}
  applyAppearance(doc,chosen,true)
  assert.equal(attrs['data-nova-theme'],'box');assert.equal(attrs['data-nova-scheme'],'light');assert.equal(attrs['data-nova-transitions'],'false')
  assert.equal(attrs['data-nova-startup-motion'],'false');assert.equal(attrs['data-nova-mascot-motion'],'true');assert.ok(!Object.hasOwn(attrs,'data-nova-reduce-motion'))
  assert.equal(variables['--font'],'"Noto \\"Sans\\"", system-ui, sans-serif');assert.equal(variables['--font-code'],'"Mono; color:red", ui-monospace, monospace')
  assert.equal(variables['color-scheme'],'light');assert.deepEqual(appearancePresentation(chosen,false).variables,variables)
})
