const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const { validShortcuts, normalizeStoredShortcuts } = require('../shared/keyboard_shortcuts.cjs')
const { validZoomPercent } = require('./desktop_view.cjs')

const appearanceDefaults = () => ({ colorScheme: 'system', lightTheme: 'nova', darkTheme: 'nova', interfaceFont: 'system', codeFont: 'system', showStartupScreen: true, startupMotion: true, mascotMotion: true, mascotAppearance: '2d' })
const defaults = () => ({ schemaVersion: 1, locale: 'es', language: 'system', autoSwitchView: false, transitionsEnabled: true, showFiles: true, collapsibleSourceContext: false, zoomPercent:100, ...appearanceDefaults() })
const validLocale = locale => locale === 'es' || locale === 'en'
const validLanguage = language => language === 'system' || validLocale(language)
const validTheme = theme => ['nova', 'synthwave84', 'matrix', 'box'].includes(theme)
const validScheme = scheme => ['system', 'light', 'dark'].includes(scheme)
const validFont = font => typeof font === 'string' && font.length > 0 && font.length <= 128 && font.trim() === font && !/[\u0000-\u001f\u007f]/.test(font)
const appearanceKeys = Object.keys(appearanceDefaults())
function readStoredAppearance(value) {
  return { colorScheme: validScheme(value.colorScheme) ? value.colorScheme : 'system',
    lightTheme: validTheme(value.lightTheme) ? value.lightTheme : 'nova',
    darkTheme: validTheme(value.darkTheme) ? value.darkTheme : 'nova',
    interfaceFont: validFont(value.interfaceFont) ? value.interfaceFont : 'system',
    codeFont: validFont(value.codeFont) ? value.codeFont : 'system',
    showStartupScreen: typeof value.showStartupScreen === 'boolean' ? value.showStartupScreen : true,
    startupMotion: typeof value.startupMotion === 'boolean' ? value.startupMotion : value.reduceMotion !== true,
    mascotMotion: typeof value.mascotMotion === 'boolean' ? value.mascotMotion : value.reduceMotion !== true,
    mascotAppearance: value.mascotAppearance === '3d' ? '3d' : '2d' }
}

/** Desktop presentation only: never reads or writes CLI/runtime preferences. */
function createDesktopPreferencesStore(directory, systemLanguage = () => 'es') {
  const filename = path.join(directory, 'desktop-preferences.json')
  let current = defaults()
  try {
    if (fs.statSync(filename).size <= 4096) {
      const value = JSON.parse(fs.readFileSync(filename, 'utf8'))
      if (value && value.schemaVersion === 1 && validLocale(value.locale)) {
        const shortcuts = normalizeStoredShortcuts(value.shortcuts)
        current = { ...defaults(), locale: value.locale,
          language: validLanguage(value.language) ? value.language : value.locale,
          autoSwitchView: typeof value.autoSwitchView === 'boolean' ? value.autoSwitchView : false,
          transitionsEnabled: typeof value.transitionsEnabled === 'boolean' ? value.transitionsEnabled : true,
          showFiles: typeof value.showFiles === 'boolean' ? value.showFiles : true,
          collapsibleSourceContext: typeof value.collapsibleSourceContext === 'boolean' ? value.collapsibleSourceContext : false,
          zoomPercent: validZoomPercent(value.zoomPercent) ? value.zoomPercent : 100,
          ...readStoredAppearance(value),
          ...(shortcuts ? { shortcuts } : {}) }
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
      return { success: true, preferences: snapshot() }
    } catch {
      try { fs.unlinkSync(temporary) } catch { /* No other paths are cleaned. */ }
      return { success: false, error: { code: 'DESKTOP_PREFERENCES_SAVE_FAILED',
        message: 'The desktop preferences could not be saved. The previous settings are unchanged.' } }
    }
  }
  function snapshot() {
    let detected = 'es'
    try { detected = /^es(?:-|_|$)/i.test(String(systemLanguage())) ? 'es' : 'en' } catch { /* Retain the fallback. */ }
    return { ...current, locale: current.language === 'system' ? detected : current.language,
      ...(current.shortcuts ? { shortcuts: { ...current.shortcuts } } : {}) }
  }
  return {
    get: snapshot,
    setZoomPercent(value) {
      return validZoomPercent(value) ? save({...current,zoomPercent:value}) : {success:false,error:{code:'INVALID_DESKTOP_ZOOM',message:'Select a zoom level from 50% to 150%.'}}
    },
    setGeneral(value) {
      if (!value || typeof value !== 'object' || Array.isArray(value) ||
          !['language','autoSwitchView','transitionsEnabled'].every(key => Object.hasOwn(value,key)) ||
          Object.keys(value).some(key => !['language','autoSwitchView','transitionsEnabled','showFiles','collapsibleSourceContext'].includes(key)) ||
          !validLanguage(value.language) || typeof value.autoSwitchView !== 'boolean' || typeof value.transitionsEnabled !== 'boolean' ||
          (Object.hasOwn(value,'showFiles') && typeof value.showFiles !== 'boolean') ||
          (Object.hasOwn(value,'collapsibleSourceContext') && typeof value.collapsibleSourceContext !== 'boolean')) return { success: false,
        error: { code: 'INVALID_DESKTOP_GENERAL', message: 'Select valid general preferences.' } }
      return save({ ...current, language: value.language, autoSwitchView: value.autoSwitchView, transitionsEnabled: value.transitionsEnabled,
        showFiles: Object.hasOwn(value,'showFiles') ? value.showFiles : current.showFiles,
        collapsibleSourceContext: Object.hasOwn(value,'collapsibleSourceContext') ? value.collapsibleSourceContext : current.collapsibleSourceContext })
    },
    setShortcuts(value) {
      if (!validShortcuts(value)) return { success: false,
        error: { code: 'INVALID_DESKTOP_SHORTCUTS', message: 'Select valid, unique keyboard shortcuts.' } }
      return save({ ...current, shortcuts: { ...value } })
    },
    setLocale(locale) {
      if (!validLocale(locale)) return { success: false,
        error: { code: 'INVALID_DESKTOP_LOCALE', message: 'Select Spanish or English.' } }
      return save({ ...current, locale, language: locale })
    },
    setAppearance(value) {
      if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 2 &&
          Object.hasOwn(value, 'reduceMotion') && Object.hasOwn(value, 'showStartupScreen') &&
          typeof value.reduceMotion === 'boolean' && typeof value.showStartupScreen === 'boolean') {
        return save({ ...current, startupMotion: !value.reduceMotion, mascotMotion: !value.reduceMotion, showStartupScreen: value.showStartupScreen })
      }
      // Previous clients did not send a mascot design. Keep the user's choice
      // while still validating every field and rejecting unknown keys below.
      if (value && typeof value === 'object' && !Array.isArray(value) && !Object.hasOwn(value, 'mascotAppearance'))
        value = { ...value, mascotAppearance: current.mascotAppearance }
      if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== appearanceKeys.length ||
          !appearanceKeys.every(key => Object.hasOwn(value, key)) || !validScheme(value.colorScheme) ||
          !validTheme(value.lightTheme) || !validTheme(value.darkTheme) || !validFont(value.interfaceFont) || !validFont(value.codeFont) ||
          typeof value.showStartupScreen !== 'boolean' || typeof value.startupMotion !== 'boolean' || typeof value.mascotMotion !== 'boolean' ||
          !['2d','3d'].includes(value.mascotAppearance)) return { success: false,
        error: { code: 'INVALID_DESKTOP_APPEARANCE', message: 'Select valid appearance preferences.' } }
      return save({ ...current, ...Object.fromEntries(appearanceKeys.map(key => [key, value[key]])) })
    },
  }
}
module.exports = { createDesktopPreferencesStore }
