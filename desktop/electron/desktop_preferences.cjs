const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

const defaults = () => ({ schemaVersion: 1, locale: 'es', reduceMotion: false, showStartupScreen: true })
const validLocale = locale => locale === 'es' || locale === 'en'

/** Desktop presentation only: never reads or writes CLI/runtime preferences. */
function createDesktopPreferencesStore(directory) {
  const filename = path.join(directory, 'desktop-preferences.json')
  let current = defaults()
  try {
    if (fs.statSync(filename).size <= 4096) {
      const value = JSON.parse(fs.readFileSync(filename, 'utf8'))
      if (value && value.schemaVersion === 1 && validLocale(value.locale)) {
        current = { ...defaults(), locale: value.locale,
          reduceMotion: typeof value.reduceMotion === 'boolean' ? value.reduceMotion : false,
          showStartupScreen: typeof value.showStartupScreen === 'boolean' ? value.showStartupScreen : true }
      }
    }
  } catch { /* Missing/corrupt presentation preferences do not prevent startup. */ }

  function save(next) {
    const temporary = path.join(directory, '.desktop-preferences-' + crypto.randomUUID() + '.tmp')
    try {
      fs.mkdirSync(directory, { recursive: true })
      fs.writeFileSync(temporary, JSON.stringify(next) + '\n', { encoding: 'utf8', mode: 0o600, flag: 'wx' })
      fs.renameSync(temporary, filename)
      current = next
      return { success: true, preferences: { ...current } }
    } catch {
      try { fs.unlinkSync(temporary) } catch { /* No other paths are cleaned. */ }
      return { success: false, error: { code: 'DESKTOP_PREFERENCES_SAVE_FAILED',
        message: 'The desktop preferences could not be saved. The previous settings are unchanged.' } }
    }
  }
  return {
    get() { return { ...current } },
    setLocale(locale) {
      if (!validLocale(locale)) return { success: false,
        error: { code: 'INVALID_DESKTOP_LOCALE', message: 'Select Spanish or English.' } }
      return save({ ...current, locale })
    },
    setAppearance(value) {
      if (!value || typeof value !== 'object' || Array.isArray(value) ||
          Object.keys(value).length !== 2 || typeof value.reduceMotion !== 'boolean' ||
          typeof value.showStartupScreen !== 'boolean') return { success: false,
        error: { code: 'INVALID_DESKTOP_APPEARANCE', message: 'Select valid appearance preferences.' } }
      return save({ ...current, reduceMotion: value.reduceMotion, showStartupScreen: value.showStartupScreen })
    },
  }
}
module.exports = { createDesktopPreferencesStore }
