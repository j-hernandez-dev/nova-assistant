const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript')
require('./register_typescript.cjs')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename)
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')
const {copyPublicMessage}=require('../electron/message_copy.ts')
const {historySections,localDay,numericDate,messageDate}=require('../src/message_presentation.ts')
const {MessageBlock}=require('../src/components/MessageBlock.tsx')
const {translate}=require('../src/i18n.tsx')
const render=message=>renderToStaticMarkup(React.createElement(MessageBlock,{message}))
const original='# Heading\n\n**bold** and [a link](https://example.test)\n\n```txt\nA  B\n```\n'

test('streaming cursor is inside the last rendered Markdown line instead of after its block',()=>{
 const cases=[
  ['First line\nLast **word**','</strong>', '</div>'],
  ['# Heading','</span>', '</div>'],
  ['- First\n- Last','</span>', '</li>'],
  ['1. First\n2. Last','</span>', '</li>'],
  ['```js\nconst answer = 42;','42;', '</pre>'],
  ['| One | Two |\n| --- | --- |\n| First | Last |','</span>', '</td>'],
  ['| One | Two |\n| --- | --- |','</span>', '</th>'],
  ['A [link](https://example.test)','</a>', '</div>'],
  ['Inline `code`','</code>', '</div>'],
 ]
 for(const[content,before,after]of cases){
  const html=render({id:'live',role:'assistant',content,streaming:true})
  const cursor='<span class="cursor" aria-hidden="true"></span>'
  assert.equal(html.split(cursor).length-1,1,content)
  assert.ok(html.includes(before+cursor+after),content)
 }
})

test('finished, interrupted, user and tool-call messages have no streaming cursor',()=>{
 for(const change of [{streaming:false},{deliveryStatus:'cancelled'},
  {deliveryStatus:'failed'},{role:'user'},{toolCalls:[{name:'read',args:{}}]}]){
  assert.doesNotMatch(render({id:'m',role:'assistant',content:'visible',streaming:true,...change}),/class="cursor"/)
 }
 const html=render({id:'live',role:'assistant',content:'<script>unsafe()</script>',streaming:true})
 assert.doesNotMatch(html,/<script>/)
 assert.match(html,/&lt;script&gt;/)
})

test('copy uses the exact original Markdown in the owner projection, never HTML, output or diagnostic text',()=>{
 const writes=[],message={id:'m',role:'assistant',content:original,toolResults:[{name:'read',output:'secret test diagnostic'}]}
 assert.deepEqual(copyPublicMessage([message],'m',text=>writes.push(text)),{success:true})
 assert.deepEqual(writes,[original])
 assert.deepEqual(copyPublicMessage([{id:'u',role:'user',content:'  user text\n'}],'u',text=>writes.push(text)),{success:true})
 assert.equal(writes[1],'  user text\n')
})
test('missing, streaming and non-public messages never write; clipboard errors are structured failures',()=>{
 let writes=0
 for(const row of [{id:'m',role:'tool',content:'output'},{id:'m',role:'system',content:'diagnostic'},
  {id:'m',role:'assistant',content:'partial',streaming:true},{id:'m',role:'user',content:''}]){
  assert.deepEqual(copyPublicMessage([row],'m',()=>writes++),{success:false})
 }
 assert.deepEqual(copyPublicMessage([],{},()=>writes++),{success:false});assert.equal(writes,0)
 assert.deepEqual(copyPublicMessage([{id:'m',role:'assistant',content:'hello'}],'m',()=>{throw Error('private exception')}),{success:false})
})
test('message footers put user time before copy and assistant copy before time; no time remains above prose',()=>{
 const at=new Date(2026,9,17,16,3).toISOString()
 for(const role of ['user','assistant']){
  const html=render({id:'m',role,content:'Hello',createdAt:at,completedAt:at})
  assert.ok(html.indexOf('nova-message-footer')>html.indexOf('Hello'))
  const footer=html.slice(html.indexOf('nova-message-footer'))
  assert.equal(footer.indexOf('nova-message-time')<footer.indexOf('nova-message-copy'),role==='user')
  assert.match(footer,/data-icon="copy"/);assert.match(footer,/Copiar mensaje/)
  assert.doesNotMatch(html,/nova-message-meta/)
 }
 assert.doesNotMatch(render({id:'m',role:'assistant',content:'Old message'}),/<time/)
})
test('day separators appear once per day, distinguish today and use exact dd/mm/yyyy for all earlier days',()=>{
 const today=new Date(2026,9,17,12),yesterday=new Date(2026,9,16,9),old=new Date(2025,1,3,20)
 const group=(id,at)=>({id,user:{id,role:'user',content:'hello',createdAt:at.toISOString()},messages:[],activities:[]})
 const sections=historySections([group('a',old),group('b',yesterday),group('c',new Date(2026,9,16,10)),group('d',today)],today)
 assert.deepEqual(sections.map(row=>!!row.separator),[true,true,false,true])
 assert.equal(numericDate(sections[0].separator.date),'03/02/2025')
 assert.equal(numericDate(sections[1].separator.date),'16/10/2026')
 assert.equal(sections.at(-1).separator.today,true)
 assert.equal(historySections([group('d',today)],new Date(2026,9,18,0,0))[0].separator.today,false)
 assert.equal(localDay(today),'2026-10-17')
})
test('missing historical dates stay absent; timestamps use completion for assistant and creation for user',()=>{
 assert.equal(historySections([{id:'legacy',messages:[{id:'old',role:'assistant',content:'old'}],activities:[]}],new Date())[0].separator,null)
 const created=new Date(2026,9,17,10).toISOString(),done=new Date(2026,9,17,11).toISOString()
 assert.equal(messageDate({role:'assistant',createdAt:created,completedAt:done}).toISOString(),done)
 assert.equal(messageDate({role:'user',createdAt:created,completedAt:done}).toISOString(),created)
})
test('copy feedback and prompt are localized while the original content remains unchanged',()=>{
 assert.equal(translate('es','messageCopied'),'Copiado');assert.equal(translate('en','messageCopied'),'Copied')
 assert.equal(translate('es','promptPlaceholder'),'Trabaja con Nova');assert.equal(translate('en','promptPlaceholder'),'Work with Nova')
 assert.equal(translate('es','historyToday'),'hoy');assert.equal(translate('en','historyToday'),'today')
})

// Legacy archives expose their true saved date without inventing a sent time.
test('archive dates create persistent day separators while message footers retain only exact message times',()=>{
 const savedAt=new Date(2026,9,15,12).toISOString()
 const legacy={id:'legacy',user:{id:'u',role:'user',content:'old',savedAt},messages:[{id:'a',role:'assistant',content:'old answer',savedAt}],activities:[]}
 const separator=historySections([legacy],new Date(2026,9,17,12))[0].separator
 assert.equal(separator.archived,true);assert.equal(numericDate(separator.date),'15/10/2026')
 assert.equal(messageDate(legacy.user),null);assert.doesNotMatch(render(legacy.messages[0]),/<time/)
 assert.equal(translate('es','historySavedDate'),'Guardado el');assert.equal(translate('en','historySavedDate'),'Saved on')
})
