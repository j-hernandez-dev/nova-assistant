const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { createDesktopPreferencesStore } = require('../electron/desktop_preferences.cjs')
const { DESKTOP_UPDATES_ENABLED, disabledDesktopUpdate, editingActionForInput } = require('../electron/desktop_host_policy.cjs')

function ownedDirectory(t) {
  const directory = fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP || os.tmpdir(), 'nova-desktop-preferences-test-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  return directory
}

test('Desktop defaults to Spanish, persists presentation preferences and isolates returned objects', t => {
  const directory = ownedDirectory(t)
  const store = createDesktopPreferencesStore(directory)
  assert.deepEqual(store.get(), { schemaVersion: 1, locale: 'es', reduceMotion: false, showStartupScreen: true })
  const copy = store.get()
  copy.locale = 'en'
  assert.equal(store.get().locale, 'es')
  assert.deepEqual(store.setLocale('en'), { success: true, preferences: { schemaVersion: 1, locale: 'en', reduceMotion: false, showStartupScreen: true } })
  assert.equal(createDesktopPreferencesStore(directory).get().locale, 'en')
  assert.deepEqual(fs.readdirSync(directory), ['desktop-preferences.json'])
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(directory, 'desktop-preferences.json'), 'utf8')),
    { schemaVersion: 1, locale: 'en', reduceMotion: false, showStartupScreen: true })
  assert.equal(store.setLocale('es').success, true)
  assert.equal(createDesktopPreferencesStore(directory).get().locale, 'es')
})

test('Invalid input and corrupt/oversized preference data do not grant settings or break startup', t => {
  const directory = ownedDirectory(t)
  const filename = path.join(directory, 'desktop-preferences.json')
  for (const contents of ['{broken', JSON.stringify({ schemaVersion: 2, locale: 'en' }), 'x'.repeat(4097)]) {
    fs.writeFileSync(filename, contents)
    const store = createDesktopPreferencesStore(directory)
    assert.equal(store.get().locale, 'es')
    for (const value of [null, '', 'ES', 'fr', {}, { locale: 'en', autoApprove: true }]) {
      assert.equal(store.setLocale(value).error.code, 'INVALID_DESKTOP_LOCALE')
      assert.equal(store.get().locale, 'es')
    }
    assert.equal(fs.readFileSync(filename, 'utf8'), contents)
  }
})

test('Storage failure keeps the effective locale and returns a bounded user error', t => {
  const directory = ownedDirectory(t)
  const blocked = path.join(directory, 'not-a-directory')
  fs.writeFileSync(blocked, 'owned fixture')
  const store = createDesktopPreferencesStore(blocked)
  assert.equal(store.get().locale, 'es')
  assert.equal(store.setLocale('en').error.code, 'DESKTOP_PREFERENCES_SAVE_FAILED')
  assert.equal(store.get().locale, 'es')
  assert.equal(fs.readFileSync(blocked, 'utf8'), 'owned fixture')
})

test('Editing shortcuts survive an absent menubar without consuming plain input or Alt shortcuts', () => {
  const input = { type: 'keyDown', key: 'c', control: true, meta: false, alt: false, shift: false }
  for (const [key, action] of [['c', 'copy'], ['x', 'cut'], ['v', 'paste'], ['a', 'selectAll'], ['z', 'undo'], ['y', 'redo']]) {
    assert.equal(editingActionForInput({ ...input, key }, 'win32'), action)
  }
  assert.equal(editingActionForInput({ ...input, key: 'z', shift: true }, 'win32'), 'redo')
  assert.equal(editingActionForInput({ ...input, control: false, meta: true }, 'darwin'), 'copy')
  for (const changes of [{ type: 'keyUp' }, { control: false }, { alt: true }, { key: 'F4', alt: true }]) {
    assert.equal(editingActionForInput({ ...input, ...changes }, 'win32'), null)
  }
})

test('Nova has no updater destination and all three updater entry points are disabled before network access', () => {
  assert.equal(DESKTOP_UPDATES_ENABLED, false)
  assert.equal(disabledDesktopUpdate('0.12.6').code, 'NOVA_DESKTOP_UPDATES_DISABLED')
  const source = fs.readFileSync(path.join(__dirname, '../electron/main.ts'), 'utf8')
  assert.match(source, /ipcMain\.handle\('check-app-update', async \(\) => \{\s*if \(!DESKTOP_UPDATES_ENABLED\) return/)
  assert.match(source, /ipcMain\.handle\('install-app-update', async \(_event, zipUrl: string\) => \{\s*if \(!DESKTOP_UPDATES_ENABLED\) return/)
  const initialization = source.slice(source.indexOf('app.whenReady().then'))
  assert.ok(initialization.indexOf('if (!DESKTOP_UPDATES_ENABLED) return') < initialization.indexOf('await fetchJson'))
  assert.match(initialization, /Menu\.setApplicationMenu\(null\)/)
  assert.match(source, /mainWindow\.setMenu\(null\)/)
})

test('Presentation IPC validates the main-frame sender and never reaches Application commands', () => {
  const source = fs.readFileSync(path.join(__dirname, '../electron/main.ts'), 'utf8')
  const handlers = source.slice(source.indexOf("ipcMain.handle('get-desktop-preferences'"),
    source.indexOf("ipcMain.on('send-to-python'"))
  assert.equal((handlers.match(/if \(!validApplicationSender\(event\)\)/g) || []).length, 2)
  assert.match(handlers, /desktopPreferences\.get\(\)/)
  assert.match(handlers, /desktopPreferences\.setLocale\(locale\)/)
  assert.doesNotMatch(handlers, /sendToPython|applicationClient\.command|signApproval/)
})


test('Old locale-only profiles retain their language and gain safe appearance defaults without rewriting at startup', t => {
  const directory = ownedDirectory(t), filename = path.join(directory, 'desktop-preferences.json')
  const before = JSON.stringify({ schemaVersion: 1, locale: 'en' })
  fs.writeFileSync(filename, before)
  const store = createDesktopPreferencesStore(directory)
  assert.deepEqual(store.get(), { schemaVersion: 1, locale: 'en', reduceMotion: false, showStartupScreen: true })
  assert.equal(fs.readFileSync(filename, 'utf8'), before)
})
test('Appearance survives restart and locale saves; saving appearance also preserves language', t => {
  const directory = ownedDirectory(t), store = createDesktopPreferencesStore(directory)
  assert.equal(store.setAppearance({ reduceMotion: true, showStartupScreen: false }).success, true)
  assert.equal(store.setLocale('en').success, true)
  const reloaded = createDesktopPreferencesStore(directory)
  assert.deepEqual(reloaded.get(), { schemaVersion: 1, locale: 'en', reduceMotion: true, showStartupScreen: false })
  assert.equal(reloaded.setAppearance({ reduceMotion: false, showStartupScreen: true }).success, true)
  assert.equal(createDesktopPreferencesStore(directory).get().locale, 'en')
})
test('Invalid appearance requests cannot overwrite saved settings or inject runtime/permission settings', t => {
  const directory = ownedDirectory(t), store = createDesktopPreferencesStore(directory)
  const valid = { reduceMotion: true, showStartupScreen: false }
  store.setAppearance(valid)
  for (const value of [null, [], true, {}, { reduceMotion: 'false', showStartupScreen: true },
    { ...valid, locale: 'en' }, { reduceMotion: true }, { ...valid, autoApprove: true }]) {
    assert.equal(store.setAppearance(value).error.code, 'INVALID_DESKTOP_APPEARANCE')
    assert.deepEqual(createDesktopPreferencesStore(directory).get(), store.get())
    assert.equal(store.get().reduceMotion, true); assert.equal(store.get().showStartupScreen, false)
  }
})
test('Failed appearance persistence retains the effective settings and leaves unrelated files untouched', t => {
  const directory = ownedDirectory(t), blocked = path.join(directory, 'blocked')
  fs.writeFileSync(blocked, 'owned fixture')
  const store = createDesktopPreferencesStore(blocked), before = store.get()
  assert.equal(store.setAppearance({ reduceMotion: true, showStartupScreen: false }).error.code, 'DESKTOP_PREFERENCES_SAVE_FAILED')
  assert.deepEqual(store.get(), before); assert.equal(fs.readFileSync(blocked, 'utf8'), 'owned fixture')
})
test('Appearance and initial presentation IPC accept only the main frame and do not touch the backend', () => {
  const source = fs.readFileSync(path.join(__dirname, '../electron/main.ts'), 'utf8')
  const handlers = source.slice(source.indexOf("ipcMain.on('get-desktop-startup-preferences'"), source.indexOf("ipcMain.handle('get-desktop-preferences'"))
  assert.match(handlers, /event.returnValue = validApplicationSender\(event\) \? desktopPreferences.get\(\) : null/)
  assert.match(handlers, /if \(!validApplicationSender\(event\)\)/)
  assert.match(handlers, /desktopPreferences.setAppearance\(value\)/)
  assert.doesNotMatch(handlers, /sendToPython|applicationClient|signApproval/)
})
