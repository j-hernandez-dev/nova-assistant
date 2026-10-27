const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const ts=require('typescript')
require('./register_typescript.cjs')
require.extensions['.tsx']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
}).outputText,filename)
const React=require('react')
const {renderToStaticMarkup}=require('react-dom/server')
const {parseInline,parseMarkdown}=require('../src/markdown.ts')
const {Markdown}=require('../src/components/Markdown.tsx')
const render=(text,streaming=false)=>renderToStaticMarkup(React.createElement(Markdown,{text,streaming}))

test('A filename inside bold is rendered as code, including the combined formatting from Nova replies',()=>{
 for(const text of ['**Archivo: `perrito.jpg`**','**Archivo:** **`perrito.jpg`**']){
  const html=render(text)
  assert.match(html,/<strong[^>]*>(?:(?!<\/strong>).)*<code class="md-inline-code">perrito\.jpg<\/code>(?:(?!<\/strong>).)*<\/strong>/)
  assert.doesNotMatch(html,/`|\*\*/)
 }
 const html=render('**Negrita con *cursiva* y `código`**; ***ambos***; ~~anterior~~; __otro__')
 assert.match(html,/<strong[^>]*>.*<em>.*cursiva/)
 assert.match(html,/<strong[^>]*><em>.*ambos/)
 assert.match(html,/<del>.*anterior/)
 assert.doesNotMatch(html,/\*\*|~~|__/)
})

test('Code spans preserve literal Markdown, Windows paths, escaped punctuation and embedded backticks',()=>{
 assert.deepEqual(parseInline('`` **literal** `tick` C:\\Users\\joseh ``'),[{kind:'code',text:'**literal** `tick` C:\\Users\\joseh'}])
 assert.match(render('\\*\\*literal\\*\\* y archivo_con_guiones.txt'),/\*\*literal\*\* y archivo_con_guiones\.txt/)
 assert.match(render('**Antes `**dentro**` después**'),/<strong[^>]*>.*<code[^>]*>\*\*dentro\*\*<\/code>.*<\/strong>/)
 assert.doesNotThrow(()=>render('**Incompleto `archivo'))
 assert.match(render('**Incompleto `archivo'),/Incompleto/)
})

test('Formatted link labels are nested safely and only HTTP(S) destinations become anchors',()=>{
 const html=render('[**`archivo`**](https://example.com/a_(b))')
 assert.match(html,/<a[^>]*href="https:\/\/example\.com\/a_\(b\)"[^>]*><strong[^>]*><code/)
 for(const href of ['javascript:alert(1)','data:text/html,test','file:///C:/secret.txt','https://example.com/\u0000x']){
  assert.doesNotMatch(render(`[abrir](${href})`),/<a\b/)
 }
 const unsafe=render('**<script>run()</script>** y `<img src=x onerror=run()>`')
 assert.doesNotMatch(unsafe,/<script|<img/)
 assert.match(unsafe,/&lt;script&gt;/);assert.match(unsafe,/&lt;img/)
})

test('Code fences and table cells keep their literal delimiters while nested formatting works in other blocks',()=>{
 const blocks=parseMarkdown('````js\r\nconst marker = "```";\r\n```\r\nstill code\r\n````\r\nfin')
 assert.equal(blocks[0].kind,'code');assert.equal(blocks[0].lang,'js')
 assert.equal(blocks[0].text,'const marker = "```";\n```\nstill code')
 assert.equal(blocks[1].kind,'p')
 const table=parseMarkdown('| Nombre | Valor |\n| --- | --- |\n| **`a`** | `a|b` y a\\|b |')[0]
 assert.equal(table.rows[0].length,2)
 assert.equal(table.rows[0][1][0].text,'a|b')
 const html=render('## **`Título`**\n\n- **`uno`**\n- *dos*\n\n~~~txt\n**literal**\n~~~')
 assert.match(html,/md-heading.*<strong[^>]*><code/)
 assert.match(html,/<li><strong[^>]*><code/)
 assert.match(html,/<pre[^>]*><code>\*\*literal\*\*<\/code><\/pre>/)
})

test('Streaming retains one cursor beside the final rendered text across nested formatting and code',()=>{
 for(const text of ['**Archivo: `perrito.jpg`**','- **`archivo`**','```js\nlet x = 1','texto\n\n']){
  const html=render(text,true)
  assert.equal((html.match(/class="cursor"/g)||[]).length,1)
  assert.doesNotMatch(render(text),/class="cursor"/)
 }
})
