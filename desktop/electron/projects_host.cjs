const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

const MAX_FOLDERS = 32
const MAX_ENTRIES = 500
const MAX_DIRECTORY_OFFSET = 100000
const MAX_FILE_BYTES = 1_000_000
const key = value => process.platform === 'win32' ? value.toLowerCase() : value
const same = (a, b) => typeof a === 'string' && typeof b === 'string' && key(a) === key(b)
function canonicalDirectory(value) {
  if (typeof value !== 'string' || !value || value.length > 32768 || value.includes('\0') || !path.isAbsolute(value)) throw new Error('PROJECT_INVALID_PATH')
  const resolved = fs.realpathSync(value)
  if (!fs.statSync(resolved).isDirectory()) throw new Error('PROJECT_NOT_DIRECTORY')
  return resolved
}
function inside(root, candidate) {
  const relative = path.relative(root, candidate)
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative))
}
function createProjectsHost({directory, defaultPath, client, chooseDirectory, openPath, bootstrapWorkspace, clearChat, publish = () => {}}) {
  if (typeof defaultPath !== 'string' || !path.isAbsolute(defaultPath)) throw new Error('PROJECT_INVALID_PATH')
  let defaultRoot, defaultUnavailable = false
  try { defaultRoot = canonicalDirectory(defaultPath) }
  catch { defaultRoot = path.resolve(defaultPath); defaultUnavailable = true }
  const filename = path.join(directory, 'project-preferences.json')
  let folders = [defaultRoot], preferred = defaultRoot, busy = false,
    error = defaultUnavailable ? {code:'PROJECT_DEFAULT_UNAVAILABLE'} : null, previewEpoch = 0
  try {
    if (fs.statSync(filename).size <= 65536) {
      const saved = JSON.parse(fs.readFileSync(filename, 'utf8'))
      if (saved?.schemaVersion === 1 && Array.isArray(saved.folders)) {
        for (const value of saved.folders.slice(0, MAX_FOLDERS)) {
          try { const root = canonicalDirectory(value); if (!folders.some(item => same(item, root))) folders.push(root) } catch { /* Deleted folders are not restored. */ }
        }
        const selected = folders.find(item => same(item, saved.activePath))
        if (selected) preferred = selected
        else if (typeof saved.activePath === 'string' && saved.activePath) error = {code: 'PROJECT_PREVIOUS_UNAVAILABLE'}
      }
    }
  } catch { /* A missing/corrupt UI registry is not Application authority. */ }
  function active() {
    const root = client.view.workspace
    try {
      const canonical = root ? canonicalDirectory(root) : null
      return canonical && same(canonical, path.resolve(root)) ? canonical : null
    } catch { return null }
  }
  function state() {
    return {schemaVersion: 1, defaultPath: defaultRoot, activePath: active(),
      folders: folders.map(root => ({path: root, name: path.basename(root) || root, isDefault: same(root, defaultRoot)})),
      busy: busy || !!client.workspaceBusy?.(), error}
  }
  function notify() { publish(state()) }
  function fail(code) { error = {code}; notify(); return {success: false, state: state(), error: {code}} }
  function save() {
    const temporary = path.join(directory, `.project-preferences-${crypto.randomUUID()}.tmp`)
    try {
      fs.mkdirSync(directory, {recursive: true})
      fs.writeFileSync(temporary, JSON.stringify({schemaVersion: 1, folders, activePath: active()}) + '\n', {encoding: 'utf8', mode: 0o600, flag: 'wx'})
      fs.renameSync(temporary, filename)
      preferred = active() || defaultRoot
      return true
    } catch {
      try { fs.unlinkSync(temporary) } catch { /* Only own temporary file. */ }
      error = {code: 'PROJECT_PREFERENCES_SAVE_FAILED'}
      return false
    }
  }
  async function switchRoot(root) {
    try { if (!same(canonicalDirectory(root), root)) return {success:false,error:{code:'PROJECT_PATH_CHANGED'}} }
    catch { return {success:false,error:{code:'PROJECT_PATH_CHANGED'}} }
    if (same(active(), root) && client.view.status.ready && !client.view.recovering) return {success: true}
    const result = (!client.view.status.ready || client.view.recovering) && bootstrapWorkspace
      ? await bootstrapWorkspace(root) : await client.changeWorkspace(root)
    if (!result?.success || !same(active(), root)) return {success: false, error: {code: result?.error?.code || 'PROJECT_CHANGE_NOT_CONFIRMED'}}
    return {success: true}
  }
  async function performAction(action, suppliedPath) {
    if (!['add', 'change', 'select', 'remove', 'open'].includes(action) ||
        (suppliedPath !== undefined && typeof suppliedPath !== 'string')) return fail('PROJECT_INVALID_ACTION')
    if (busy || client.workspaceBusy?.()) return fail('PROJECT_BUSY')
    const bootstrap = !client.view.status.ready || client.view.recovering
    if (bootstrap && (action !== 'add' || !bootstrapWorkspace)) return fail('PROJECT_UNAVAILABLE')
    const selected = folders.find(item => same(item, suppliedPath || active()))
    if (action !== 'add' && !selected) return fail('PROJECT_NOT_REGISTERED')
    if (action === 'remove' && same(selected, defaultRoot)) return fail('PROJECT_DEFAULT_REQUIRED')
    busy = true; error = null; previewEpoch++; notify()
    try {
      if (action === 'open') {
        const root = canonicalDirectory(selected)
        if (!same(root, selected)) return fail('PROJECT_PATH_CHANGED')
        const reason = await openPath(root)
        return reason ? fail('PROJECT_OPEN_FAILED') : {success: true, state: state()}
      }
      let destination = selected
      if (action === 'add' || action === 'change') {
        if (action === 'add' && folders.length >= MAX_FOLDERS) return fail('PROJECT_LIMIT_REACHED')
        const choice = await chooseDirectory()
        if (choice?.canceled || !choice?.filePaths?.length) return {success: false, canceled: true, state: state()}
        destination = canonicalDirectory(choice.filePaths[0])
      }
      // Picker latency can overlap a new turn. The Application gate is still final.
      if (client.workspaceBusy?.() || (!bootstrap && (!client.view.status.ready || client.view.recovering))) return fail('PROJECT_BUSY')
      if (action === 'remove') destination = same(active(), selected) ? defaultRoot : active()
      if (!destination) return fail('PROJECT_UNAVAILABLE')
      const confirmed = await switchRoot(destination)
      if (!confirmed.success) return fail(confirmed.error.code)
      if (action === 'remove' && clearChat) {
        const deleted = await clearChat(selected)
        if (!deleted?.success) return fail('PROJECT_CHAT_CLEAR_FAILED')
      }
      if (action === 'remove' || action === 'change') folders = folders.filter(root => !same(root, selected) || same(root, defaultRoot))
      if (!folders.some(root => same(root, destination))) folders.push(destination)
      const persisted = save(); notify()
      return persisted ? {success: true, state: state()} : {success: false, state: state(), error}
    } catch (cause) {
      return fail(cause?.message?.startsWith('PROJECT_') ? cause.message : 'PROJECT_ACTION_FAILED')
    } finally { busy = false; notify() }
  }
  async function preview(value, kind, offset = 0) {
    const root = active()
    const epoch = previewEpoch
    const failure = (code, details = {}) => ({success: false, root, path: typeof value === 'string' ? value : null, ...details, error: {code}})
    if (!root || !client.view.status.ready || client.view.recovering || busy) return failure('PROJECT_UNAVAILABLE')
    if (!Number.isSafeInteger(offset) || offset < 0 || offset > MAX_DIRECTORY_OFFSET) return failure('PROJECT_INVALID_OFFSET')
    if (typeof value !== 'string' || !value || value.length > 32768 || value.includes('\0') || !path.isAbsolute(value)) return failure('PROJECT_INVALID_PATH')
    try {
      const candidate = await fs.promises.realpath(value)
      if (!inside(root, candidate)) return failure('PROJECT_OUTSIDE_ROOT')
      const stat = await fs.promises.stat(candidate)
      let result
      if (kind === 'directory') {
        if (!stat.isDirectory()) return failure('PROJECT_NOT_DIRECTORY')
        // opendir bounds enumeration instead of allocating the entire directory.
        const entries = [], handle = await fs.promises.opendir(candidate)
        let truncated = false, physical = 0, nextOffset = null
        try {
          for await (const entry of handle) {
            if (physical < offset) { physical++; continue }
            if (physical >= offset + MAX_ENTRIES) { truncated = true; nextOffset = physical <= MAX_DIRECTORY_OFFSET ? physical : null; break }
            physical++
            const full = path.join(candidate, entry.name)
            try {
              const resolved = await fs.promises.realpath(full)
              if (!inside(root, resolved)) continue
              const itemStat = await fs.promises.stat(resolved)
              entries.push({name: entry.name, isDirectory: itemStat.isDirectory(), isSymlink: entry.isSymbolicLink()})
            } catch { /* Unreadable or dangling entries are not accessible previews. */ }
          }
        } finally { try { await handle.close() } catch { /* Iteration auto-closes. */ } }
        entries.sort((a, b) => Number(b.isDirectory) - Number(a.isDirectory) || a.name.localeCompare(b.name))
        result = {success: true, root, path: candidate, entries, truncated, nextOffset,
          limitReached: truncated && nextOffset === null}
      } else {
        if (!stat.isFile()) return failure('PROJECT_NOT_FILE')
        if (stat.size > MAX_FILE_BYTES) return failure('PROJECT_FILE_TOO_LARGE', {size: stat.size})
        const handle = await fs.promises.open(candidate, 'r')
        try {
          const current = await handle.stat()
          if (!current.isFile()) return failure('PROJECT_NOT_FILE')
          if (current.dev !== stat.dev || current.ino !== stat.ino) return failure('PROJECT_PATH_CHANGED')
          if (current.size > MAX_FILE_BYTES) return failure('PROJECT_FILE_TOO_LARGE', {size: current.size})
          const bytes = Buffer.alloc(MAX_FILE_BYTES + 1)
          const {bytesRead} = await handle.read(bytes, 0, bytes.length, 0)
          if (bytesRead > MAX_FILE_BYTES) return failure('PROJECT_FILE_TOO_LARGE', {size: bytesRead})
          const contentBytes = bytes.subarray(0, bytesRead)
          if (contentBytes.includes(0)) return failure('PROJECT_BINARY_FILE')
          const content = new TextDecoder('utf-8', {fatal: true}).decode(contentBytes)
          result = {success: true, root, path: candidate, content}
        } finally { await handle.close() }
      }
      if (!same(root, active()) || busy || epoch !== previewEpoch) return failure('PROJECT_STALE_ROOT')
      // Recheck canonical containment after I/O; never publish a result whose root changed.
      if (!inside(root, await fs.promises.realpath(value))) return failure('PROJECT_OUTSIDE_ROOT')
      return result
    } catch { return failure('PROJECT_READ_FAILED') }
  }
  return {state, action: async (...args) => { const result = await performAction(...args); return {...result,state:state()} }, preferredPath: () => preferred, defaultPath: defaultRoot,
    listDirectory: (value, offset = 0) => preview(value, 'directory', offset), readFile: value => preview(value, 'file'),
    isChanging: () => busy, sync: notify, setError(code) { error = {code}; notify() }}
}
module.exports = {createProjectsHost, canonicalDirectory, inside, MAX_ENTRIES, MAX_FILE_BYTES}
