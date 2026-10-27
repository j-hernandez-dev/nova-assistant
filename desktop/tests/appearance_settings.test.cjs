require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),Module=require('node:module')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename)
require.extensions['.css']=()=>{}
const React=require('react')
let slots=[],cursor=0,pendingEffects=[],appearance,ready,saveState,effectiveScheme,locale,calls,fontCalls
require.cache[require.resolve('react')].exports={...React,
 useId(){return'appearance'},
 useState(initial){const index=cursor++;if(!(index in slots))slots[index]=initial;return[slots[index],value=>{slots[index]=typeof value==='function'?value(slots[index]):value}]},
 useRef(initial){const index=cursor++;if(!(index in slots))slots[index]={current:initial};return slots[index]},
 useEffect(effect,deps){const index=cursor++,previous=slots[index];if(!previous||deps.some((value,i)=>value!==previous.deps[i]))pendingEffects.push(()=>{previous?.cleanup?.();slots[index]={deps,cleanup:effect()}})},
}
const {settingsEnglish,settingsSpanish}=require('../src/settings_locale.ts')
const dictionary={es:settingsSpanish,en:settingsEnglish}
const defaults={colorScheme:'system',lightTheme:'nova',darkTheme:'nova',interfaceFont:'system',codeFont:'system',showStartupScreen:true,startupMotion:true,mascotMotion:true,mascotAppearance:'2d'}
const originalLoad=Module._load
Module._load=function(request,parent,isMain){
 if(request==='../appearance')return{useAppearance:()=>({appearance,ready,saveState,effectiveScheme,saveAppearance:async(next,reset)=>{calls.push({next,reset});return true}})}
 if(request==='../i18n')return{useI18n:()=>({t:key=>dictionary[locale][key]||key})}
 if(request==='../../shared/desktop_appearance')return{defaultAppearance:defaults}
 return originalLoad.apply(this,arguments)
}
const {AppearanceSettings,appearanceFontOptions}=require('../src/components/AppearanceSettings.tsx')
const {SettingsSelect}=require('../src/components/SettingsSelect.tsx')
Module._load=originalLoad
function nodes(value){return!value||typeof value!=='object'?[]:[value,...[value.props?.children].flat(Infinity).flatMap(nodes)]}
function content(value){if(value===null||value===false||value===undefined)return'';if(typeof value!=='object')return String(value);return[value.props?.children].flat(Infinity).map(content).join(' ')}
function render(active=false){cursor=0;const tree=AppearanceSettings({titleId:'appearance-title',active});const effects=pendingEffects;pendingEffects=[];for(const effect of effects)effect();return tree}
function setup(){
 for(const slot of slots)slot?.cleanup?.()
 slots=[];cursor=0;pendingEffects=[];appearance={...defaults};ready=true;saveState='idle';effectiveScheme='dark';locale='es';calls=[];fontCalls=0
 global.window={api:{getDesktopFonts:async()=>{fontCalls++;return{success:true,fonts:['Segoe UI','Consolas','Aptos']}}}}
}
const select=(tree,name)=>nodes(tree).find(node=>node.type===SettingsSelect&&node.props['data-settings-select']===name)
const tick=()=>new Promise(resolve=>setImmediate(resolve))
test('Appearance uses the four requested groups, custom selectors and autosave without draft buttons',()=>{
 setup();const tree=render()
 const text=content(tree)
 for(const label of ['Personaliza la experiencia visual de Nova.','Estilo','Esquema de color','Tema','Tipografía','Fuente de la interfaz','Fuente de código','Pantalla de carga','Mostrar pantalla de carga','Movimiento de pantalla de carga','Mascota','Movimiento de mascota','Restablecer'])assert.ok(text.includes(label),label)
 const headings=nodes(tree).filter(node=>node.type==='h3').map(content)
 assert.deepEqual(headings,['Estilo','Tipografía','Pantalla de carga','Mascota'])
 assert.equal(nodes(tree).filter(node=>node.type===SettingsSelect).length,5)
 assert.equal(nodes(tree).filter(node=>node.props?.role==='switch').length,3)
 assert.ok(!nodes(tree).some(node=>node.type==='form'||node.type==='select'||node.props?.type==='submit'))
 assert.ok(!text.includes('Cancelar cambios'));assert.ok(!text.includes('Los cambios se aplican'))
 assert.deepEqual(select(tree,'colorScheme').props.options.map(value=>value.value),['system','light','dark'])
 assert.deepEqual(select(tree,'theme').props.options.map(value=>value.label),['Nova',"SynthWave '84",'Matrix','Box'])
 assert.deepEqual(select(tree,'mascotAppearance').props.options,[{value:'2d',label:'Nova 2D'},{value:'3d',label:'Nova 3D'}])
 assert.equal(select(tree,'mascotAppearance').props.value,'2d')
 assert.ok(nodes(tree).some(node=>node.type==='figure'&&node.props.className==='nova-mascot-preview'))
})
test('Each appearance control saves one complete preference record and keeps light and dark choices separate',()=>{
 setup()
 select(render(),'colorScheme').props.onChange('light')
 assert.deepEqual(calls.pop(),{next:{...defaults,colorScheme:'light'},reset:undefined})
 effectiveScheme='light';select(render(),'theme').props.onChange('matrix')
 assert.deepEqual(calls.pop().next,{...defaults,lightTheme:'matrix'})
 effectiveScheme='dark';select(render(),'theme').props.onChange('box')
 assert.deepEqual(calls.pop().next,{...defaults,darkTheme:'box'})
 for(const field of ['interfaceFont','codeFont']){select(render(),field).props.onChange('Any installed family');assert.deepEqual(calls.pop().next,{...defaults,[field]:'Any installed family'})}
 for(const field of ['showStartupScreen','startupMotion','mascotMotion']){
  const control=nodes(render()).find(node=>node.props?.['data-appearance']===field);control.props.onChange({target:{checked:false}})
  assert.deepEqual(calls.pop().next,{...defaults,[field]:false})
 }
 select(render(),'mascotAppearance').props.onChange('3d')
 assert.deepEqual(calls.pop().next,{...defaults,mascotAppearance:'3d'})
 assert.deepEqual(appearance,defaults,'controls do not optimistically replace confirmed preferences')
})
test('Appearance Reset passes only Appearance defaults and pending saves lock all eight controls',()=>{
 setup();appearance={...defaults,interfaceFont:'Consolas',mascotMotion:false}
 nodes(render()).find(node=>node.type==='button').props.onClick()
 assert.deepEqual(calls,[{next:defaults,reset:true}])
 for(const state of ['saving','unconfirmed']){
  saveState=state;const controls=nodes(render()).filter(node=>node.type===SettingsSelect||node.props?.role==='switch'||node.type==='button')
  assert.equal(controls.length,9);assert.ok(controls.every(node=>node.props.disabled))
 }
 saveState='idle';ready=false;assert.ok(nodes(render()).filter(node=>node.type===SettingsSelect||node.props?.role==='switch'||node.type==='button').every(node=>node.props.disabled))
})
test('Font discovery runs on active Appearance only and supplies all families to both selectors',async()=>{
 setup();render(false);assert.equal(fontCalls,0)
 render(true);assert.equal(fontCalls,1);await tick()
 const tree=render(true)
 for(const field of ['interfaceFont','codeFont'])assert.deepEqual(select(tree,field).props.options.map(value=>value.value),['system','Aptos','Consolas','Segoe UI'])
 render(false);render(true);assert.equal(fontCalls,1);assert.equal(calls.length,0)
})
test('Font discovery failure keeps System and saved choices usable and retries on section reopening',async()=>{
 setup();appearance={...defaults,interfaceFont:'Saved Family'};window.api.getDesktopFonts=async()=>{fontCalls++;throw Error('owned fixture failure')}
 render(true);await tick();let tree=render(true)
 assert.ok(content(tree).includes('No se pudieron cargar las fuentes instaladas.'))
 assert.deepEqual(select(tree,'interfaceFont').props.options.map(value=>value.value),['system','Saved Family'])
 assert.equal(select(tree,'interfaceFont').props.disabled,false)
 window.api.getDesktopFonts=async()=>{fontCalls++;return{success:true,fonts:['Arial']}}
 render(false);render(true);await tick();tree=render(true);assert.equal(fontCalls,2)
 assert.ok(select(tree,'interfaceFont').props.options.find(value=>value.value==='Saved Family').description.includes('No está instalada'))
})
test('Font options include every family, deduplicate names and retain an unavailable saved choice',()=>{
 const options=appearanceFontOptions(['Consolas','Segoe UI','Arial','Consolas',''], 'Missing Family','System','Not installed',true)
 assert.deepEqual(options.map(value=>value.value),['system','Arial','Consolas','Segoe UI','Missing Family'])
 assert.equal(options.at(-1).description,'Not installed')
 assert.deepEqual(appearanceFontOptions([],'Saved','System','Unavailable',false),[{value:'system',label:'System'},{value:'Saved',label:'Saved'}])
})
test('English labels cover the same controls and failed saves retain the confirmed values',()=>{
 setup();locale='en';saveState='failed';appearance={...defaults,startupMotion:false}
 const tree=render(),text=content(tree)
 for(const label of ['Customize Nova’s visual experience.','Style','Color scheme','Theme','Typography','Interface font','Code font','Startup screen','Startup screen motion','Mascot motion','Reset'])assert.ok(text.includes(label),label)
 assert.ok(text.includes('previous settings are unchanged'));assert.ok(!text.includes('Preferencias guardadas.'))
 assert.equal(nodes(tree).find(node=>node.props?.['data-appearance']==='startupMotion').props.checked,false)
 assert.deepEqual(Object.keys(settingsEnglish).sort(),Object.keys(settingsSpanish).sort())
})
