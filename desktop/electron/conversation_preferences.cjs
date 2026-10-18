const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

const MAX_SESSIONS = 20
const MAX_IDS = 10_000
const MAX_BYTES = 8 * 1024 * 1024
const validId = (value, maxLength) => typeof value === 'string' && value.length > 0
  && value.length <= maxLength && !/[\u0000-\u0020\u007f]/.test(value)

function normalizeState(state) {
  if (!state || !Array.isArray(state.observedIds) || !Array.isArray(state.unreadIds)
      || state.observedIds.length > MAX_IDS || state.unreadIds.length > MAX_IDS) return null
  if (![...state.observedIds, ...state.unreadIds].every(value => validId(value, 512))) return null
  const observedIds = [...new Set(state.observedIds)]
  const observed = new Set(observedIds)
  const unreadIds = [...new Set(state.unreadIds)]
  if (unreadIds.some(id => !observed.has(id))) return null
  return { observedIds, unreadIds }
}

/** IDs only: presentation read-state never stores messages or execution authority. */
function createConversationPreferencesStore(directory) {
  const filename = path.join(directory, 'desktop-conversation-view.json')
  let sessions = []
  try {
    if (fs.statSync(filename).size <= MAX_BYTES) {
      const parsed = JSON.parse(fs.readFileSync(filename, 'utf8'))
      if (parsed && parsed.schemaVersion === 1 && Array.isArray(parsed.sessions)
          && parsed.sessions.length <= MAX_SESSIONS) {
        const seen = new Set()
        const normalized = parsed.sessions.map(entry => {
          if (!entry || !validId(entry.sessionId, 256) || seen.has(entry.sessionId)) return null
          seen.add(entry.sessionId)
          const state = normalizeState(entry)
          return state ? { sessionId: entry.sessionId, ...state } : null
        })
        if (normalized.every(Boolean)) sessions = normalized
      }
    }
  } catch { /* Missing, corrupt or inaccessible read-state does not block startup. */ }

  return {
    load(sessionId) {
      if (!validId(sessionId, 256)) return null
      const entry = sessions.find(item => item.sessionId === sessionId)
      return entry ? { observedIds: [...entry.observedIds], unreadIds: [...entry.unreadIds] } : null
    },
    save(sessionId, state) {
      if (!validId(sessionId, 256)) return false
      const normalized = normalizeState(state)
      if (!normalized) return false
      const next = [...sessions.filter(item => item.sessionId !== sessionId), { sessionId, ...normalized }].slice(-MAX_SESSIONS)
      const contents = JSON.stringify({ schemaVersion: 1, sessions: next }) + '\n'
      if (Buffer.byteLength(contents, 'utf8') > MAX_BYTES) return false
      const temporary = path.join(directory, `.desktop-conversation-view-${crypto.randomUUID()}.tmp`)
      try {
        fs.mkdirSync(directory, { recursive: true })
        fs.writeFileSync(temporary, contents, { encoding: 'utf8', mode: 0o600, flag: 'wx' })
        fs.renameSync(temporary, filename)
        sessions = next
        return true
      } catch {
        try { fs.unlinkSync(temporary) } catch { /* Only this owned temporary may be removed. */ }
        return false
      }
    },
  }
}

module.exports = { createConversationPreferencesStore }
