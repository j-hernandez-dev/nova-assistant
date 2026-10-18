const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

const valid = value => value && value.providerId === 'ollama' && typeof value.modelId === 'string'
  && value.modelId.length > 0 && value.modelId.length <= 256 && value.modelId.trim() === value.modelId
  && !/[\s\u0000-\u001f\u007f]/.test(value.modelId)

/** Desktop's last accepted runtime selection. Never touches CLI configuration. */
function createDesktopModelPreferencesStore(directory) {
  const filename = path.join(directory, 'desktop-runtime-preferences.json')
  let current = null
  try {
    if (fs.statSync(filename).size <= 4096) {
      const value = JSON.parse(fs.readFileSync(filename, 'utf8'))
      if (value.schemaVersion === 1 && valid(value)) {
        current = { schemaVersion: 1, providerId: 'ollama', modelId: value.modelId }
      }
    }
  } catch { /* A missing or invalid preference is not a model selection. */ }

  return {
    get() { return current ? { ...current } : null },
    saveConfirmed(selection) {
      if (!valid(selection)) return { success: false, error: {
        code: 'INVALID_DESKTOP_MODEL_SELECTION', message: 'Select an installed Ollama model.' } }
      const next = { schemaVersion: 1, providerId: 'ollama', modelId: selection.modelId }
      if (current && current.providerId === next.providerId && current.modelId === next.modelId) {
        return { success: true, preferences: { ...current } }
      }
      const temporary = path.join(directory, `.desktop-runtime-preferences-${crypto.randomUUID()}.tmp`)
      try {
        fs.mkdirSync(directory, { recursive: true })
        fs.writeFileSync(temporary, JSON.stringify(next) + '\n', { encoding: 'utf8', mode: 0o600, flag: 'wx' })
        fs.renameSync(temporary, filename)
        current = next
        return { success: true, preferences: { ...current } }
      } catch {
        try { fs.unlinkSync(temporary) } catch { /* Only this operation's owned temp is eligible. */ }
        return { success: false, error: { code: 'DESKTOP_MODEL_PREFERENCES_SAVE_FAILED',
          message: 'The model selection is active but could not be saved for the next launch.' } }
      }
    },
    childEnvironment(environment) {
      const next = { ...environment }
      // Either explicit setting owns the pair; do not combine unrelated providers/models.
      const explicit = Object.keys(environment).some(key => {
        const upper = key.toUpperCase()
        return (upper === 'LOCAL_CLI_MODEL' || upper === 'LOCAL_CLI_PROVIDER') && environment[key] !== undefined
      })
      if (!explicit && current) {
        next.LOCAL_CLI_MODEL = current.modelId
        next.LOCAL_CLI_PROVIDER = current.providerId
      }
      return next
    },
  }
}

module.exports = { createDesktopModelPreferencesStore }
