const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { createDesktopModelPreferencesStore } = require('../electron/desktop_model_preferences.cjs')

function ownedDirectory(t) {
  const directory = fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP || os.tmpdir(), 'nova-desktop-model-test-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  return directory
}

test('Only a confirmed exact Ollama selection is persisted independently and restored', t => {
  const directory = ownedDirectory(t)
  const store = createDesktopModelPreferencesStore(directory)
  assert.equal(store.get(), null)
  assert.deepEqual(store.childEnvironment({ PATH: 'owned' }), { PATH: 'owned' })
  const selection = { providerId: 'ollama', modelId: 'qwen3.5:9b', token: 'ignored', temperature: 99 }
  assert.deepEqual(store.saveConfirmed(selection), { success: true,
    preferences: { schemaVersion: 1, providerId: 'ollama', modelId: 'qwen3.5:9b' } })
  assert.deepEqual(fs.readdirSync(directory), ['desktop-runtime-preferences.json'])
  const persisted = JSON.parse(fs.readFileSync(path.join(directory, 'desktop-runtime-preferences.json'), 'utf8'))
  assert.deepEqual(persisted, { schemaVersion: 1, providerId: 'ollama', modelId: 'qwen3.5:9b' })
  const copy = store.get()
  copy.modelId = 'forged'
  assert.equal(store.get().modelId, 'qwen3.5:9b')
  const restarted = createDesktopModelPreferencesStore(directory)
  assert.equal(restarted.get().modelId, 'qwen3.5:9b')
  // An unavailable saved model is kept exact; it is not replaced by an alternative.
  assert.deepEqual(restarted.childEnvironment({ PATH: 'owned' }), {
    PATH: 'owned', LOCAL_CLI_MODEL: 'qwen3.5:9b', LOCAL_CLI_PROVIDER: 'ollama' })
})

test('Repeated confirmed writes stay bounded and later accepted tags replace earlier preferences', t => {
  const directory = ownedDirectory(t)
  const store = createDesktopModelPreferencesStore(directory)
  for (const modelId of ['qwen3.5:9b', 'qwen3.5:9b', 'qwen3.5:4b', 'qwen3.5:9b']) {
    assert.equal(store.saveConfirmed({ providerId: 'ollama', modelId }).success, true)
  }
  assert.equal(createDesktopModelPreferencesStore(directory).get().modelId, 'qwen3.5:9b')
  assert.deepEqual(fs.readdirSync(directory), ['desktop-runtime-preferences.json'])
})

test('Explicit provider or model environment settings take precedence over the entire saved pair', t => {
  const store = createDesktopModelPreferencesStore(ownedDirectory(t))
  store.saveConfirmed({ providerId: 'ollama', modelId: 'qwen3.5:9b' })
  for (const environment of [
    { LOCAL_CLI_MODEL: 'explicit:tag' }, { LOCAL_CLI_PROVIDER: 'anthropic' },
    { LOCAL_CLI_MODEL: '', LOCAL_CLI_PROVIDER: 'ollama' },
    { local_cli_model: 'windows-case-insensitive' },
  ]) assert.deepEqual(store.childEnvironment(environment), environment)
  const inherited = { PATH: 'owned' }
  store.childEnvironment(inherited)
  assert.deepEqual(inherited, { PATH: 'owned' })
})

test('Corrupt and invalid saved data never selects a model or rewrites the source', t => {
  const directory = ownedDirectory(t)
  const filename = path.join(directory, 'desktop-runtime-preferences.json')
  for (const text of ['{bad', 'x'.repeat(4097), JSON.stringify({ schemaVersion: 2, providerId: 'ollama', modelId: 'x' }),
    JSON.stringify({ schemaVersion: 1, providerId: 'other', modelId: 'x' }),
    JSON.stringify({ schemaVersion: 1, providerId: 'ollama', modelId: '' })]) {
    fs.writeFileSync(filename, text)
    const store = createDesktopModelPreferencesStore(directory)
    assert.equal(store.get(), null)
    assert.deepEqual(store.childEnvironment({}), {})
    assert.equal(fs.readFileSync(filename, 'utf8'), text)
  }
  const store = createDesktopModelPreferencesStore(directory)
  for (const value of [null, {}, { providerId: 'claude', modelId: 'a' },
    { providerId: 'ollama', modelId: ' a' }, { providerId: 'ollama', modelId: 'bad\nname' }]) {
    assert.equal(store.saveConfirmed(value).error.code, 'INVALID_DESKTOP_MODEL_SELECTION')
  }
})

test('Disk failure does not replace the saved selection and returns a nonfatal persistence notice', t => {
  const directory = ownedDirectory(t)
  const store = createDesktopModelPreferencesStore(directory)
  store.saveConfirmed({ providerId: 'ollama', modelId: 'before:exact' })
  const filename = path.join(directory, 'desktop-runtime-preferences.json')
  fs.rmSync(filename)
  fs.mkdirSync(filename)
  const result = store.saveConfirmed({ providerId: 'ollama', modelId: 'active:but-unsaved' })
  assert.equal(result.success, false)
  assert.equal(result.error.code, 'DESKTOP_MODEL_PREFERENCES_SAVE_FAILED')
  assert.equal(store.get().modelId, 'before:exact')
  assert.equal(fs.readdirSync(directory).filter(name => name.endsWith('.tmp')).length, 0)
})
