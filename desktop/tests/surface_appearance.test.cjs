const {test}=require('node:test')
const assert=require('node:assert/strict')
const {surfaceDocument,presentationCss}=require('../electron/surface_appearance.cjs')

test('Native theme styles are embedded before first paint without relaxing the fixed document policy',()=>{
  for(const file of ['approval','confirmation','question']){
    const surface=require('../electron/'+file+'_surface.cjs')
    const html=surface.APPROVAL_HTML || surface.HTML
    const themed=surfaceDocument(html,{variables:{'--panel':'#fafafa','--text':'#171717','--accent':'#135b38','color-scheme':'light'}})
    assert.ok(themed.indexOf('--panel:#fafafa')<themed.indexOf('</head>'))
    assert.ok(themed.includes('--nova-color-scheme:light'))
    assert.equal((themed.match(/Content-Security-Policy/g)||[]).length,1)
    assert.match(themed,/script-src 'none'/)
    assert.doesNotMatch(themed,/<script/i)
    assert.match(themed,/font-family:var\(--font-code/)
  }
})
test('A font family cannot terminate the host-owned native stylesheet or add markup',()=>{
  const family='Example </style><img src=x onerror=alert(1)> "Family"'
  const css=presentationCss({variables:{'--font':JSON.stringify(family)+', system-ui, sans-serif','color-scheme':'dark','not-a-css-variable':'ignored'}})
  assert.doesNotMatch(css,/<|>|not-a-css-variable/)
  assert.match(css,/\\3c /)
  assert.match(css,/--nova-color-scheme:dark/)
})
