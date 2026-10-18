require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { modelLibraryText } = require('../src/model_catalog_locale.ts')

test('Built-in descriptions project to Spanish and English without changing model identity', () => {
  const text = 'Qwen 3.5中型。Vision対応、バランスの取れた推論力。'
  assert.equal(modelLibraryText(text, 'es'), 'Qwen 3.5 de tamaño intermedio, con visión y razonamiento equilibrado.')
  assert.equal(modelLibraryText(text, 'en'), 'Mid-sized Qwen 3.5, with vision and balanced reasoning.')
  assert.equal(modelLibraryText('qwen3.5:9b', 'es'), 'qwen3.5:9b')
  assert.equal(modelLibraryText('Qwen 3.5 9B', 'en'), 'Qwen 3.5 9B')
})
test('Known built-in strength labels translate; technical acronyms remain exact', () => {
  assert.equal(modelLibraryText('コード生成', 'es'), 'Generación de código')
  assert.equal(modelLibraryText('コード生成', 'en'), 'Code generation')
  assert.equal(modelLibraryText('日本語', 'es'), 'Japonés')
  for (const value of ['MoE', 'NLP', 'CoT', '32K', '2024-11']) {
    assert.equal(modelLibraryText(value, 'es'), value)
    assert.equal(modelLibraryText(value, 'en'), value)
  }
})
test('RAM recommendation template translates only with an exact known built-in reason', () => {
  const value = 'Best for your 32GB system. Balanced reasoning + tools.'
  assert.equal(modelLibraryText(value, 'es'), 'Opción recomendada para tu equipo de 32 GB. Razonamiento equilibrado y herramientas.')
  assert.equal(modelLibraryText(value, 'en'), value)
  const unknown = 'Best for your 32GB system. Provider description not owned by Nova.'
  assert.equal(modelLibraryText(unknown, 'es'), unknown)
})
test('External text and new provider metadata are retained verbatim', () => {
  for (const value of ['Provider-supplied new description.', '外部提供者の説明', '<not markup>', 'unrecognized-label', '__proto__', 'constructor', 'toString']) {
    assert.equal(modelLibraryText(value, 'es'), value)
    assert.equal(modelLibraryText(value, 'en'), value)
  }
})
