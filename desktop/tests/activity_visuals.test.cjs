const {test}=require('node:test')
const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript')
require('./register_typescript.cjs')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}
}).outputText,filename)
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')
const {activityToolVisual}=require('../src/activity_presentation.ts')
const {chainIcon,chainLabel}=require('../src/turn_activity.ts')
const {NovaIcon}=require('../src/components/NovaIcon.tsx')
const {ActionDetails}=require('../src/components/ToolActivity.tsx')
const {ActivityChain}=require('../src/components/TurnActivity.tsx')
const {translate}=require('../src/i18n.tsx')
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props))
const action=(name,args={})=>({key:name,name,args,output:'unchanged raw output',receipt:{operationId:'op',toolCallId:'tc',turnId:'turn',messageId:'m',name,arguments:args,cwd:'fixture',status:'completed',operationStatus:'completed',effectState:'none',output:'unchanged raw output',stdout:'',stderr:'',outputSequence:1,outputTruncated:false}})

test('each supported tool family has a real decorative SVG and labels in both languages',()=>{
 const names=['read','write','edit','glob','grep','bash','web_search','web_fetch','todo_write','ask_user','agent','memory_search','memory_remember','document_read','document_search','browser_navigate','browser_observe','browser_click','browser_type','browser_press_key','browser_back','browser_forward','browser_reload','browser_close','browser_request_takeover','browser_upload','browser_download','unrecognized_tool']
 for(const name of names){
  const visual=activityToolVisual(name),svg=render(NovaIcon,{name:visual.icon,size:15})
  assert.match(svg,/<svg/);assert.match(svg,/<(?:path|circle|rect)/)
  assert.match(svg,/aria-hidden="true"/);assert.match(svg,/focusable="false"/)
  for(const locale of ['es','en']) assert.ok(translate(locale,visual.heading),`${locale}: ${name}`)
 }
 assert.notEqual(activityToolVisual('read').icon,activityToolVisual('write').icon)
 assert.notEqual(activityToolVisual('write').icon,activityToolVisual('edit').icon)
 assert.notEqual(activityToolVisual('write').icon,activityToolVisual('bash').icon)
})
test('tool headings are translated while raw identifiers, arguments, receipts and output stay exact',()=>{
 for(const [name,es,en]of [['write','Escritura','Write'],['read','Lectura','Read'],['edit','Edición','Edit'],['bash','Terminal','Terminal']]){
  const item=action(name,{file_path:'C:/owned/example.txt',content:'Hola'})
  const html=render(ActionDetails,{action:item})
  const heading=html.slice(html.indexOf('nova-action-detail-heading'),html.indexOf('nova-action-invocation'))
  assert.match(heading,new RegExp(es));assert.ok(!heading.includes(`>${name}<`))
  assert.equal(translate('en',activityToolVisual(name).heading),en)
  const diagnostics=html.slice(html.indexOf('nova-action-diagnostics'))
  assert.ok(diagnostics.includes(`<dd>${name}</dd>`));assert.match(diagnostics,/completed \/ completed \/ none/)
  assert.match(html,/unchanged raw output/);assert.match(html,/C:\/owned\/example.txt/)
 }
})
test('command/file/mixed activities use distinct icons and command activity has its requested label',()=>{
 const commands=[action('bash',{command:'echo fixture'})],files=[action('read')]
 assert.equal(chainIcon(commands),'terminal');assert.equal(chainIcon(files),'files')
 assert.equal(chainIcon([...files,...commands]),'workflow')
 const web=[{name:'web_fetch'},{name:'browser_click'}]
 assert.equal(chainLabel(web),'activityWeb');assert.equal(chainIcon(web),'globe')
 assert.equal(chainLabel([{name:'memory_search'}]),'activityActions')
 const html=render(ActivityChain,{actions:commands})
 assert.match(html,/Actividad con comandos/);assert.match(html,/data-icon="terminal"/)
 assert.equal(translate('en','activityCommands'),'Command activity')
})
test('chevrons are SVGs next to labels and the raw simulated glyphs are gone',()=>{
 for(const html of [render(ActionDetails,{action:action('write')}),render(ActivityChain,{actions:[action('write')]})]){
  assert.match(html,/data-icon="chevron"/);assert.doesNotMatch(html,/◇|›_|⌄/)
  assert.doesNotMatch(html,/<details[^>]* open/)
 }
 const css=fs.readFileSync(require('node:path').join(__dirname,'../src/styles.css'),'utf8')
 assert.match(css,/nova-activity-expand[^}]*rotate\(-90deg\)/)
 assert.match(css,/nova-action-chain\[open\][^}]*rotate\(0\)/)
 assert.match(css,/nova-action-diagnostics\[open\][^}]*rotate\(0\)/)
})

test('thinking and running tool text share the folder pulse while finished, lost or permission states stay static',()=>{
 const running=action('bash',{command:'echo fixture'});running.receipt.status='running';running.receipt.operationStatus='running'
 assert.match(render(ActivityChain,{actions:[],active:true}),/nova-thinking-line nova-working-text/)
 assert.match(render(ActivityChain,{actions:[running],active:true}),/nova-chain-label nova-working-text/)
 assert.match(render(ActionDetails,{action:running}),/nova-activity-title nova-working-text/)
 assert.doesNotMatch(render(ActionDetails,{action:action('bash')}),/nova-working-text/)
 const waiting={...running,receipt:{...running.receipt,status:'pending',operationStatus:'requested'}}
 assert.doesNotMatch(render(ActivityChain,{actions:[waiting],active:true,approvalToolCallIds:['tc']}),/nova-working-text/)
 assert.doesNotMatch(render(ActionDetails,{action:waiting,awaitingPermission:true}),/nova-working-text/)
 const lost={...running,receipt:{...running.receipt,observationLost:true}}
 assert.doesNotMatch(render(ActivityChain,{actions:[lost],active:true}),/nova-working-text/)
 const css=fs.readFileSync(require('node:path').join(__dirname,'../src/styles.css'),'utf8')
 assert.match(css,/\.nova-working-text \{ animation: pulse 1s infinite;/)
 assert.match(css,/@media \(prefers-reduced-motion: reduce\) \{\s*\.nova-working-text, \.explorer-loading \{ animation: none;/)
})
