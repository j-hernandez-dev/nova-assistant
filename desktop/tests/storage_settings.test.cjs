require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),Module=require('node:module'),path=require('node:path')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename)
require.extensions['.css']=()=>{}
const React=require('react')
let slots=[],cursor=0,effects=[],locale='es',calls=[]
const changed=(a,b)=>!a||a.length!==b.length||a.some((value,index)=>!Object.is(value,b[index]))
require.cache[require.resolve('react')].exports={...React,
 useId:()=> 'storage',
 useState(initial){const index=cursor++;if(!(index in slots))slots[index]=initial;return[slots[index],next=>{slots[index]=typeof next==='function'?next(slots[index]):next}]},
 useRef(initial){const index=cursor++;if(!(index in slots))slots[index]={current:initial};return slots[index]},
 useCallback(callback,deps){const index=cursor++;if(changed(slots[index]?.deps,deps))slots[index]={deps,value:callback};return slots[index].value},
 useEffect(effect,deps){const index=cursor++,prior=slots[index];if(changed(prior?.deps,deps))effects.push(()=>{prior?.cleanup?.();slots[index]={deps,cleanup:effect()}})},
}
const {storageEnglish,storageSpanish}=require('../src/storage_locale.ts')
const {settingsEnglish,settingsSpanish}=require('../src/settings_locale.ts')
const dict={es:{...settingsSpanish,...storageSpanish,diagnosticDetails:'Detalles de diagnóstico',memoriesRefresh:'Actualizar'},en:{...settingsEnglish,...storageEnglish,diagnosticDetails:'Diagnostic details',memoriesRefresh:'Refresh'}}
const load=Module._load
Module._load=function(request){if(request==='../i18n')return{useI18n:()=>({locale,t:key=>dict[locale][key]||key})};return load.apply(this,arguments)}
const {StorageSettings}=require('../src/components/StorageSettings.tsx')
const {SettingsSelect}=require('../src/components/SettingsSelect.tsx')
Module._load=load
const presentation=require('../src/storage_presentation.ts')
const nodes=value=>!value||typeof value!=='object'?[]:[value,...[value.props?.children].flat(Infinity).flatMap(nodes)]
const content=value=>value===null||value===false||value===undefined?'':typeof value!=='object'?String(value):[value.props?.children].flat(Infinity).map(content).join(' ')
const tick=()=>new Promise(resolve=>setImmediate(resolve))
const ok=data=>({success:true,data})
const file=(id,projectPath='A')=>({id,name:id+'.txt',modifiedAt:'2026-10-01T12:00:00Z',bytes:1024,projectPath})
let files,overview
function setup(){
 for(const slot of slots)slot?.cleanup?.()
 slots=[];cursor=0;effects=[];locale='es';calls=[]
 files=[file('one'),file('two')]
 overview={totalBytes:4096,categories:Object.keys(presentation.storageCategoryKeys).map(id=>({id,bytes:id==='attachments'?4096:0})),folders:Object.keys(presentation.storageCategoryKeys).map(id=>({id,category:id,path:'owned/'+id,bytes:id==='attachments'?4096:0,exists:true,restartRequired:true})),projects:[{path:'A',name:'Alpha',bytes:2048,fileCount:2},{path:null,name:'',bytes:0,fileCount:0},{path:'B',name:'Beta',bytes:0,fileCount:0}],restartRequired:false}
 global.window={api:{
  storageOverview:async()=>{calls.push(['overview']);return ok({...overview})},
  storageFiles:async project=>{calls.push(['files',project]);return ok({files:files.filter(file=>file.projectPath===project)})},
  storageMove:async(ids,project)=>{calls.push(['move',ids,project]);files=files.map(file=>ids.includes(file.id)?{...file,projectPath:project}:file);return ok({})},
  storageDownload:async ids=>{calls.push(['download',ids]);return ok({downloaded:ids.length})},
  storageDeleteFiles:async ids=>{calls.push(['delete',ids]);files=files.filter(file=>!ids.includes(file.id));return ok({})},
  storageDeleteFolder:async id=>{calls.push(['folder',id]);overview.restartRequired=true;return ok({restartRequired:true})},
  storageOpenFolder:async id=>{calls.push(['open',id]);return ok({})},storageRestart:async()=>{calls.push(['restart']);return ok({})},
 }}
}
function render(active=true,locked=false,projectRevision=''){cursor=0;const tree=StorageSettings({active,locked,projectRevision});const pending=effects;effects=[];for(const effect of pending)effect();return tree}
const find=(tree,predicate)=>nodes(tree).find(predicate)
const buttons=tree=>nodes(tree).filter(node=>node.type==='button')
const project=(tree,value)=>{const row=find(tree,node=>node.props?.['data-storage-project']===value);return row&&find(row,node=>node.props?.className==='nova-storage-project-open')}
const select=tree=>find(tree,node=>node.type===SettingsSelect)
async function ready(){render();await tick();return render()}
async function filePage(){const tree=await ready();project(tree,'A').props.onClick();await tick();return render()}

test('Storage reads only when active, keeps a stable request count and uses Refresh rather than Reset',async()=>{
 setup();render(false);assert.deepEqual(calls,[])
 let tree=await ready();assert.deepEqual(calls,[['overview']]);render();render();assert.equal(calls.length,1)
 assert.ok(content(tree).includes('Almacenamiento'));assert.ok(content(tree).includes('Actualizar'));assert.ok(!content(tree).includes('Restablecer'))
 assert.deepEqual(nodes(tree).filter(node=>node.type==='h3').map(content),['Este dispositivo','Carpetas','Administrar'])
 assert.equal(nodes(tree).filter(node=>node.type==='li').length,8)
 assert.deepEqual(nodes(tree).filter(node=>node.props?.['data-storage-project']!==undefined).map(content).map(text=>text.split(' ')[0]),['No','Alpha','Beta'])
 buttons(tree).find(node=>node.props['aria-label']==='Actualizar almacenamiento').props.onClick();await tick();tree=render();assert.equal(calls.filter(call=>call[0]==='overview').length,2)
 render(false);render(true);await tick();render();assert.equal(calls.filter(call=>call[0]==='overview').length,3)
})
test('File selection exposes the confirmed project and linking updates all selected files once then refreshes',async()=>{
 setup();let tree=await filePage();assert.ok(content(tree).includes('one.txt'));assert.equal(select(tree).props.disabled,true)
 find(tree,node=>node.props?.['aria-label']==='Seleccionar todos los archivos').props.onChange({target:{checked:true}});tree=render()
 assert.equal(select(tree).props.value,'A');assert.deepEqual(select(tree).props.options.map(option=>option.value),['','A','B'])
 assert.equal(find(tree,node=>node.props?.className?.includes('nova-storage-selection')).props.visible,true)
 select(tree).props.onChange('B');await tick();tree=render()
 assert.deepEqual(calls.filter(call=>call[0]==='move'),[['move',['one','two'],'B']])
 assert.equal(calls.filter(call=>call[0]==='files').length,2);assert.equal(calls.filter(call=>call[0]==='overview').length,2)
 assert.ok(!content(tree).includes('one.txt'));assert.equal(select(tree).props.disabled,true)
 assert.equal(find(tree,node=>node.props?.className?.includes('nova-storage-selection')).props.visible,false)
})
test('Canceled deletion retains selection and produces neither a failure nor a success message',async()=>{
 setup();window.api.storageDeleteFiles=async()=>({success:false,canceled:true})
 let tree=await filePage();find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: one.txt').props.onChange({target:{checked:true}});tree=render()
 buttons(tree).find(node=>content(node)==='Eliminar').props.onClick();await tick();tree=render()
 assert.equal(find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: one.txt').props.checked,true)
 assert.ok(!content(tree).includes('Archivos eliminados.'));assert.ok(!find(tree,node=>node.props?.role==='alert'))
 assert.equal(calls.filter(call=>call[0]==='overview').length,1)
})
test('A failed storage mutation keeps the files and selection visible and surfaces a localized error',async()=>{
 setup();window.api.storageMove=async()=>({success:false,error:{code:'STORAGE_BUSY'}})
 let tree=await filePage();find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: one.txt').props.onChange({target:{checked:true}});tree=render()
 select(tree).props.onChange('');await tick();tree=render()
 assert.ok(content(tree).includes('Espera a que termine'));assert.ok(content(tree).includes('one.txt'));assert.equal(select(tree).props.value,'A')
})
test('Refresh recomputes both overview and the active file list, discarding missing selected IDs',async()=>{
 setup();let tree=await filePage();find(tree,node=>node.props?.['aria-label']==='Seleccionar todos los archivos').props.onChange({target:{checked:true}});tree=render()
 files=[file('two')];buttons(tree).find(node=>node.props['aria-label']==='Actualizar almacenamiento').props.onClick();await tick();tree=render()
 assert.equal(calls.filter(call=>call[0]==='overview').length,2);assert.equal(calls.filter(call=>call[0]==='files').length,2)
 assert.equal(find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: two.txt').props.checked,true)
 assert.ok(!content(tree).includes('one.txt'))
})
test('Queued folder deletion displays Nova restart without claiming disk data was already removed',async()=>{
 setup();let tree=await ready();buttons(tree).find(node=>content(node)==='Eliminar').props.onClick();await tick();tree=render()
 assert.deepEqual(calls.filter(call=>call[0]==='folder'),[['folder','chats']]);assert.ok(content(tree).includes('La eliminación está programada.'))
 buttons(tree).find(node=>content(node)==='Reiniciar Nova').props.onClick();await tick();assert.equal(calls.filter(call=>call[0]==='restart').length,1)
})
test('A stale file result cannot replace the list after returning to overview',async()=>{
 setup();let resolve;window.api.storageFiles=()=>new Promise(done=>resolve=done)
 let tree=await ready();project(tree,'A').props.onClick();tree=render();buttons(tree).find(node=>content(node).includes('Volver a almacenamiento')).props.onClick()
 resolve(ok({files:[file('stale')]}));await tick();tree=render()
 assert.ok(!content(tree).includes('stale.txt'));assert.ok(content(tree).includes('Administrar'))
})
test('Unlinked and per-project inventory have no global-file fallback and supports empty collections',async()=>{
 setup();let tree=await ready();project(tree,'').props.onClick();await tick();tree=render()
 assert.deepEqual(calls.filter(call=>call[0]==='files'),[['files',null]]);assert.ok(content(tree).includes('No vinculado'));assert.ok(!content(tree).includes('one.txt'))
 assert.ok(content(tree).includes('No hay archivos adjuntos'))
})
test('Project registration changes refresh the active list once and leave a removed project safely',async()=>{
 setup();await filePage();overview.projects=overview.projects.filter(project=>project.path!=='A')
 render(true,false,'changed');await tick();const tree=render(true,false,'changed')
 assert.ok(content(tree).includes('Administrar'));assert.ok(!project(tree,'A'));assert.equal(calls.filter(call=>call[0]==='overview').length,2)
 render(true,false,'changed');assert.equal(calls.filter(call=>call[0]==='overview').length,2)
})
test('Storage labels are complete in English and Spanish, route follows Memory, and animations honor both preferences',async()=>{
 setup();locale='en';const tree=await ready();for(const text of ['Storage','Folders','Manage','Unlinked','Refresh'])assert.ok(content(tree).includes(text),text)
 assert.deepEqual(Object.keys(storageEnglish).sort(),Object.keys(storageSpanish).sort())
 const route=fs.readFileSync(path.join(__dirname,'../src/components/SettingsPanel.tsx'),'utf8')
 assert.match(route,/\['memory',[^\n]+\n\s*\['storage',/)
 const css=fs.readFileSync(path.join(__dirname,'../src/storage.css'),'utf8');assert.match(css,/data-nova-transitions="false"/);assert.match(css,/prefers-reduced-motion:reduce/)
 assert.equal(settingsSpanish.chatDelete,'Eliminar');assert.equal(settingsEnglish.chatDelete,'Delete')
})
test('Storage formatting and grouping never mutate snapshots or hide unlinked files',()=>{
 const values=[{path:'A',name:'Alpha',bytes:10,fileCount:1}];assert.deepEqual(presentation.storageGroups(values).map(value=>value.path),[null,'A']);assert.equal(values.length,1)
 assert.equal(presentation.storageBytes(1024,'en'),'1 KB');assert.equal(presentation.storageBytes(NaN,'es'),'0 B');assert.equal(presentation.storageBytes(-9,'en'),'0 B')
 assert.equal(presentation.storageCategoryKey('__proto__'),'settingsStorage')
 assert.deepEqual(presentation.storageSelectedFiles([file('one'),file('two')],['gone','one','one']),['one'])
 assert.equal(presentation.storageSelectionTarget([file('one'),file('two','B')],['one','two']),'__mixed__')
})

test('Download stays between reassignment and Delete, keeps selection and never mutates file access',async()=>{
 setup();let tree=await filePage()
 find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: one.txt').props.onChange({target:{checked:true}});tree=render()
 const footer=find(tree,node=>node.props?.className?.includes('nova-storage-selection'))
 assert.deepEqual(nodes(footer).filter(node=>node.type===SettingsSelect||node.type==='button').map(node=>node.type===SettingsSelect?'project':content(node)),['project','Descargar','Eliminar'])
 buttons(tree).find(node=>content(node)==='Descargar').props.onClick();await tick();tree=render()
 assert.deepEqual(calls.filter(c=>c[0]==='download'),[['download',['one']]])
 assert.equal(find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: one.txt').props.checked,true)
 assert.equal(calls.some(c=>c[0]==='move'||c[0]==='delete'),false)
})

test('File search filters only this project, clears hidden selections, and selects all matching rows',async()=>{
 setup();let tree=await filePage()
 const search=()=>find(render(),node=>node.type==='form'&&node.props?.role==='search')
 const input=()=>find(search(),node=>node.type==='input')
 find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: one.txt').props.onChange({target:{checked:true}})
 input().props.onChange({target:{value:'TWO'}});search().props.onSubmit({preventDefault(){}});tree=render()
 assert.ok(!content(tree).includes('one.txt'));assert.ok(content(tree).includes('two.txt'))
 assert.equal(find(tree,node=>node.props?.['aria-label']==='Seleccionar archivo: two.txt').props.checked,false)
 find(tree,node=>node.props?.['aria-label']==='Seleccionar todos los archivos').props.onChange({target:{checked:true}});tree=render()
 assert.equal(select(tree).props.value,'A')
 input().props.onChange({target:{value:'no such file'}});search().props.onSubmit({preventDefault(){}});tree=render()
 assert.ok(content(tree).includes('No se encontraron archivos'));assert.equal(calls.some(call=>call[0]==='move'||call[0]==='delete'),false)
})
