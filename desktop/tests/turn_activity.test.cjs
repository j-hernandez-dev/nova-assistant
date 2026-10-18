const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),ts=require('typescript')
require('./register_typescript.cjs')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}
}).outputText,filename)
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')
const {conversationGroups,collectActions,elapsedSeconds,groupElapsedSeconds,formatDuration,actionTitle}=require('../src/turn_activity.ts')
const {attachActivities}=require('../electron/activity_projection.ts')
const {ConversationTurn}=require('../src/components/ConversationTurn.tsx')
const {translate}=require('../src/i18n.tsx')
const render=props=>renderToStaticMarkup(React.createElement(ConversationTurn,props))
const receipt=(changes={})=>({operationId:'op1',toolCallId:'c1',turnId:'t1',messageId:'m1',name:'bash',arguments:{command:'echo hello'},cwd:'fixture',status:'completed',operationStatus:'completed',effectState:'none',output:'hello',stdout:'',stderr:'',outputSequence:1,outputTruncated:false,...changes})
const turn={turnId:'t1',status:'completed',transcriptStart:0,transcriptEnd:3,userMessage:{id:'u1',sourceIndex:0,createdAt:'2026-10-17T10:00:00Z'},displayMessages:[{id:'m1',sourceIndex:1,createdAt:'2026-10-17T10:00:01Z',completedAt:'2026-10-17T10:00:03Z'},{id:'m2',sourceIndex:2,completedAt:'2026-10-17T10:00:57Z'}]}
const rows=[{id:'u1',sourceIndex:0,role:'user',content:'hazlo'},{id:'m1',sourceIndex:1,role:'assistant',content:'Voy a comprobarlo.'},{id:'m2',sourceIndex:2,role:'assistant',content:'Respuesta final.'}]
function group(activity=receipt(),rawTurn=turn){return conversationGroups(attachActivities(rows,[activity],[rawTurn]),[activity])[0]}

test('host turn identity and observed times survive snapshot/reload without duplicate actions',()=>{
 const g=group();assert.equal(g.turn.id,'t1');assert.equal(elapsedSeconds(g.turn,false,0),57)
 assert.equal(collectActions(g.messages,g.activities).length,1)
 assert.deepEqual(group(),g)
 const other=receipt({operationId:'op2',turnId:'other'});assert.equal(conversationGroups(attachActivities(rows,[other],[turn]),[other])[0].activities.length,0)
})
test('elapsed time never fabricates old timestamps, negative duration or a terminal live clock',()=>{
 assert.equal(elapsedSeconds(undefined,false,1000),null)
 assert.equal(elapsedSeconds({id:'x',status:'completed',startedAt:'invalid'},false,1000),null)
 assert.equal(elapsedSeconds({id:'x',status:'completed',startedAt:'2026-10-17T10:00:00Z'},false,1000),null)
 assert.equal(elapsedSeconds({id:'x',status:'running',startedAt:'2026-10-17T10:00:00Z'},true,Date.parse('2026-10-17T10:00:17Z')),17)
 assert.equal(elapsedSeconds({id:'x',status:'running',startedAt:'2026-10-17T10:00:00Z'},true,0),0)
 assert.equal(formatDuration(75),'1 min 15 s');assert.equal(formatDuration(3700),'1 h 1 min')
})
test('completed turn keeps commentary then collapsed chain then final reply, with nested action details',()=>{
 const html=render({group:group()})
 assert.match(html,/Trabajó durante.*57 s/)
 assert.ok(html.indexOf('Voy a comprobarlo.')<html.indexOf('nova-action-chain'))
 assert.ok(html.indexOf('nova-action-chain')<html.indexOf('Respuesta final.'))
 assert.equal((html.match(/data-operation-id="op1"/g)||[]).length,1)
 assert.match(html,/nova-action-chain/);assert.match(html,/nova-action-row/)
 assert.doesNotMatch(html,/<details[^>]* open|Detalles de herramienta|No hay un resultado de ejecución verificable/)
})
test('thinking continues after public commentary and command replaces it only with a running host receipt',()=>{
 const activeTurn={...turn,status:'running',displayMessages:turn.displayMessages.slice(0,1)}
 let g=group(receipt({status:'running',operationStatus:'running'}),activeTurn)
 let html=render({group:g,activeTurnId:'t1'})
 assert.match(html,/Ejecutando echo hello/)
 assert.ok(html.indexOf('Voy a comprobarlo.')<html.indexOf('nova-action-chain'))
 g=group(receipt(),activeTurn);html=render({group:g,activeTurnId:'t1'})
 assert.match(html,/nova-chain-label[^>]*role="status"[^>]*>Pensando/)
 html=render({group:{id:'t1',messages:[],activities:[],turn:{id:'t1',status:'running'}},activeTurnId:'t1'})
 assert.match(html,/nova-thinking-line[^>]*role="status"[^>]*>Pensando/)
})
test('pending approval and UNKNOWN never become execution or confirmed success',()=>{
 const activeTurn={...turn,status:'running'}
 const html=render({group:group(receipt({status:'pending',operationStatus:'requested'}),activeTurn),activeTurnId:'t1',approvalToolCallIds:['c1']})
 assert.match(html,/Esperando permiso/);assert.doesNotMatch(html,/Ejecutando echo/)
 const unknown=render({group:group(receipt({status:'outcome_unknown',operationStatus:'outcome_unknown',effectState:'unknown'}))})
 assert.match(unknown,/No se pudo confirmar el resultado/);assert.match(unknown,/Revisar resultado/)
 assert.doesNotMatch(unknown,/Ejecución confirmada|Ejecutando echo/)
})
test('legacy tool output is inspectable but never treated as a typed receipt',()=>{
 const messages=[{id:'u',role:'user',content:'old task'},{id:'old',role:'assistant',content:'Prose',toolCalls:[{name:'bash',args:{command:'echo old'}}],toolResults:[{name:'bash',output:'SUCCESS'}]}]
 const g=conversationGroups(messages,[])[0],html=render({group:g})
 assert.match(html,/Terminal echo old/);assert.match(html,/Sin confirmación de ejecución/);assert.match(html,/SUCCESS/)
 assert.doesNotMatch(html,/Trabajó durante|Ejecución confirmada|Detalles de herramienta/)
})
test('model prose and malicious command/output remain exact escaped text, localized labels do not translate them',()=>{
 const g=group(receipt({arguments:{command:'<script>unsafe()</script>'},output:'<img src=x onerror=run()>'}))
 const html=render({group:g})
 assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<script>|<img/)
 const action=collectActions(g.messages,g.activities)[0]
 assert.match(actionTitle(action,key=>translate('en',key)),/^Terminal /)
 assert.equal(translate('en','activityThoughtFor'),'Thought for');assert.equal(translate('es','activityWorkedFor'),'Trabajó durante')
})

test('a typed orphan is displayed once without claiming a legacy proposal is another execution',()=>{
 const messages=[{id:'proposal',role:'assistant',content:'',toolCalls:[{name:'bash',args:{command:'echo hello'}}]}]
 const actions=collectActions(messages,[receipt({messageId:null})])
 assert.equal(actions.length,1);assert.equal(actions[0].receipt.operationId,'op1')
})

test('tool-only generations have no blank message bubble or standalone diagnostic noise',()=>{
 const g=group();g.messages[0].content='';
 const html=render({group:g})
 assert.equal((html.match(/<article/g)||[]).length,2) // one human, one public final reply
 assert.doesNotMatch(html,/nova-harness-diagnostics/)
})

test('plain replies show worked duration without tools, including after restoring only persisted message dates',()=>{
 const messages=[{id:'u',role:'user',content:'question',createdAt:'2026-10-17T10:00:00Z'},
  {id:'a1',role:'assistant',content:'commentary',createdAt:'2026-10-17T10:00:01Z',completedAt:'2026-10-17T10:00:03Z'},
  {id:'a2',role:'assistant',content:'answer',createdAt:'2026-10-17T10:00:04Z',completedAt:'2026-10-17T10:00:23Z'}]
 const g=conversationGroups(messages,[])[0]
 assert.equal(g.turn,undefined);assert.equal(groupElapsedSeconds(g,false,0),23)
 assert.match(render({group:g}),/Trabajó durante.*23 s/)
 assert.doesNotMatch(render({group:g}),/>Actividad<|Pensó durante/)
 const live={...g,turn:{id:'t1',status:'completed',startedAt:messages[0].createdAt,completedAt:messages[2].completedAt}}
 assert.match(render({group:live}),/Trabajó durante.*23 s/)
 assert.equal(groupElapsedSeconds(g,true,Date.parse('2026-10-17T10:00:17Z')),17)
})
test('missing archive timestamps and another user turn never create an invented duration',()=>{
 const old={id:'old',user:{id:'u',role:'user',content:'old',savedAt:'2026-10-17T10:00:00Z'},
  messages:[{id:'a',role:'assistant',content:'old answer',savedAt:'2026-10-17T10:01:00Z'}],activities:[]}
 assert.equal(groupElapsedSeconds(old,false,0),null)
 const groups=conversationGroups([{id:'u1',role:'user',content:'first',createdAt:'2026-10-17T10:00:00Z'},
  {id:'a1',role:'assistant',content:'first answer',completedAt:'2026-10-17T10:00:03Z'},
  {id:'u2',role:'user',content:'second',createdAt:'2026-10-17T10:01:00Z'},
  {id:'a2',role:'assistant',content:'second answer',completedAt:'2026-10-17T10:01:19Z'}],[])
 assert.deepEqual(groups.map(g=>groupElapsedSeconds(g,false,0)),[3,19])
})
