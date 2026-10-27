require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { themeIds, themePalettes, resolveTheme, SYSTEM_INTERFACE_FONT, SYSTEM_CODE_FONT } = require('../shared/desktop_theme.ts')

function luminance(hex) {
  const rgb = hex.slice(1).match(/../g).map(value => {
    const channel = parseInt(value, 16) / 255
    return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4
  })
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
}
function contrast(a, b) { const x = luminance(a), y = luminance(b); return (Math.max(x,y) + .05) / (Math.min(x,y) + .05) }

test('Every theme supplies a complete immutable light and dark presentation palette', () => {
  assert.deepEqual(themeIds, ['nova','synthwave84','matrix','box'])
  const expected = Object.keys(themePalettes.dark.nova.colors).sort()
  for (const mode of ['dark','light']) for (const id of themeIds) {
    const palette = themePalettes[mode][id]
    assert.equal(palette.mode, mode); assert.equal(palette.id, id)
    assert.ok(Object.isFrozen(palette)); assert.ok(Object.isFrozen(palette.colors))
    assert.deepEqual(Object.keys(palette.colors).sort(), expected)
    for (const [token,color] of Object.entries(palette.colors)) {
      assert.ok(token.startsWith('--')); assert.match(color, /^#[a-f0-9]{6}$/i)
    }
  }
})
test('System follows the OS scheme and each manual scheme retains its own selected theme', () => {
  const preferences = {colorScheme:'system',darkTheme:'matrix',lightTheme:'synthwave84'}
  assert.equal(resolveTheme(preferences,true),themePalettes.dark.matrix)
  assert.equal(resolveTheme(preferences,false),themePalettes.light.synthwave84)
  assert.equal(resolveTheme({...preferences,colorScheme:'light'},true),themePalettes.light.synthwave84)
  assert.equal(resolveTheme({...preferences,colorScheme:'dark'},false),themePalettes.dark.matrix)
})
test('All palettes keep body, secondary text and accent readable on their primary surfaces', () => {
  for (const mode of ['dark','light']) for (const id of themeIds) {
    const c = themePalettes[mode][id].colors
    for (const surface of ['--bg','--panel','--bg-input','--bubble-assistant','--bubble-user','--code-bg']) {
      assert.ok(contrast(c['--text'],c[surface]) >= 7, `${mode}/${id} text on ${surface}`)
      assert.ok(contrast(c['--text-dim'],c[surface]) >= 4.5, `${mode}/${id} secondary on ${surface}`)
      assert.ok(contrast(c['--accent'],c[surface]) >= 4.5, `${mode}/${id} accent on ${surface}`)
    }
  }
})
test('Light startup emblems use dark ink and platform fonts need no bundled font files', () => {
  assert.equal(SYSTEM_INTERFACE_FONT,'system-ui, sans-serif')
  assert.equal(SYSTEM_CODE_FONT,'ui-monospace, monospace')
  for (const id of themeIds) {
    const c=themePalettes.light[id].colors
    assert.ok(contrast(c['--nova-emblem-bright'],c['--bg']) > 12)
    assert.ok(luminance(c['--nova-titlebar-bg']) > .65)
  }
})
test('The theme bridge covers legacy colors across all desktop surfaces', () => {
  const fs = require('node:fs'), path = require('node:path'), postcss = require('postcss')
  const stylesheet = postcss.parse(fs.readFileSync(path.join(__dirname,'../src/themes.css'),'utf8'))
  const scope = stylesheet.nodes.find(node => node.type === 'atrule' && node.name === 'scope')
  assert.ok(scope, 'The bridge is scoped away from the existing Nova dark colors')
  const actual = new Set()
  scope.walkRules(rule => rule.walkDecls(decl => actual.add(rule.selector + '|' + decl.prop)))
  for (const file of ['styles.css','settings.css']) {
    postcss.parse(fs.readFileSync(path.join(__dirname,'../src',file),'utf8')).walkRules(rule => {
      if (rule.selector.includes(':root')) return
      for (let node = rule.parent; node; node = node.parent) if (node.type === 'atrule' && /keyframes/.test(node.name)) return
      rule.walkDecls(decl => {
        if (!/^(color|background(?:-color|-image)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?|box-shadow|text-shadow|filter|scrollbar-color|accent-color|fill|stroke|caret-color)$/.test(decl.prop)) return
        if (!/(#[\da-f]{3,8}\b|rgba?\(|\b(?:white|black)\b)/i.test(decl.value)) return
        assert.ok(actual.has(rule.selector+'|'+decl.prop), `${file}: ${rule.selector} ${decl.prop} is missing its theme treatment`)
      })
    })
  }
})
