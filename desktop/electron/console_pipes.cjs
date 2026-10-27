// A dev launcher may close its stdout/stderr pipes while Electron stays alive.
// Handle only that lost logging destination; unrelated errors remain errors.
const installations = new WeakMap()
const methods = {log:'stdout',info:'stdout',debug:'stdout',warn:'stderr',error:'stderr'}

function installConsolePipeGuard(options={}) {
  const target = options.console || console
  if (installations.has(target)) return installations.get(target)
  const channels = {stdout:options.stdout || process.stdout,stderr:options.stderr || process.stderr}
  const states = {}, originals = {}, wrappers = {}
  for (const [name,stream] of Object.entries(channels)) {
    const state = {closed:!!stream.destroyed || !!stream.writableEnded}
    state.error = error => {
      if (error?.code === 'EPIPE' || state.closed && ['ERR_STREAM_DESTROYED','ERR_STREAM_WRITE_AFTER_END'].includes(error?.code)) {
        state.closed = true
        return
      }
      throw error
    }
    stream.on('error',state.error)
    states[name] = state
  }
  for (const [method,channel] of Object.entries(methods)) {
    if (typeof target[method] !== 'function') continue
    originals[method] = target[method]
    wrappers[method] = function(...args) {
      if (states[channel].closed) return
      try { return Reflect.apply(originals[method],target,args) }
      catch (error) { states[channel].error(error) }
    }
    target[method] = wrappers[method]
  }
  const guard = {
    isClosed(channel) { return states[channel].closed },
    dispose() {
      for (const [name,stream] of Object.entries(channels)) stream.removeListener('error',states[name].error)
      for (const method of Object.keys(originals)) if (target[method] === wrappers[method]) target[method] = originals[method]
      installations.delete(target)
    },
  }
  installations.set(target,guard)
  return guard
}
module.exports = {installConsolePipeGuard}
