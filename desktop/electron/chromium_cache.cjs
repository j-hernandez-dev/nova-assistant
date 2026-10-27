const fs = require('node:fs')
const path = require('node:path')

// Only disposable Chromium caches belong here. Cookies, browser storage,
// Preferences and Nova's own JSON/SQLite stores must remain at their paths.
const CACHE_NAMES = Object.freeze(['Cache', 'Code Cache', 'GPUCache', 'DawnGraphiteCache', 'DawnWebGPUCache', 'GPUPersistentCache'])

function prepareChromiumCaches(directory, io = fs) {
  if (!path.isAbsolute(directory)) throw new Error('CACHE_PROFILE_MUST_BE_ABSOLUTE')
  const root = path.resolve(directory)
  const backupDirectory = path.join(root, '.chromium-cache-backup')
  const rotated = [], failures = []
  const ordinaryDirectory = target => {
    const info = io.lstatSync(target)
    if (info.isSymbolicLink() || !info.isDirectory()) throw Object.assign(new Error('CACHE_DIRECTORY_UNSAFE'), { code: 'CACHE_DIRECTORY_UNSAFE' })
  }
  const missing = target => {
    try { io.lstatSync(target); return false }
    catch (error) { if (error.code === 'ENOENT') return true; throw error }
  }

  // Called before Chromium opens the profile, with the single-instance lock
  // held. Fresh caches on every launch also recover old, unmarked crashes.
  ordinaryDirectory(root)
  for (const name of CACHE_NAMES) {
    try {
      const source = path.resolve(root, name), backup = path.resolve(backupDirectory, name)
      if (path.dirname(source) !== root || path.dirname(backup) !== backupDirectory) throw new Error('CACHE_PATH_OUTSIDE_PROFILE')
      if (missing(source)) continue
      ordinaryDirectory(source)
      if (missing(backupDirectory)) io.mkdirSync(backupDirectory)
      ordinaryDirectory(backupDirectory)
      if (!missing(backup)) {
        ordinaryDirectory(backup)
        // Both absolute targets have been checked against the fixed cache
        // allowlist. rm does not follow links inside the previous backup.
        io.rmSync(backup, { recursive: true, force: true })
      }
      io.renameSync(source, backup)
      rotated.push(name)
    } catch (error) {
      failures.push({ name, code: error.code || 'CACHE_RECOVERY_FAILED' })
    }
  }
  return { rotated, failures, backupDirectory }
}

module.exports = { prepareChromiumCaches, CACHE_NAMES }
