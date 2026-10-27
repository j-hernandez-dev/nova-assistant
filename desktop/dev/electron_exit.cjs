const guarded = new WeakSet()
const launches = new WeakMap()
const restarts = new WeakMap()

// vite-plugin-electron 0.28 retains the child after its natural exit and then
// taskkills that dead PID from process.exit. Retain the plugin's live-process
// cleanup/restart behavior while avoiding that duplicate termination.
function guardElectronDevExit(startup, host = process) {
  if (guarded.has(startup)) return
  const exit = startup.exit
  startup.exit = async function (...args) {
    const child = host.electronApp
    if (child && (child.exitCode !== null || child.signalCode !== null)) {
      host.electronApp = undefined
      return
    }
    return exit.apply(this, args)
  }
  guarded.add(startup)
}

// A storage cleanup restart must retain Vite's local server. The main process
// requests exit 75 only after closing its services; ordinary exits still end
// the dev command. Never retry an application crash or a failed model turn.
async function launchElectronDev(startup, host = process) {
  if (launches.has(host)) return launches.get(host)
  const scheduled = restarts.get(host)
  if (scheduled) { clearTimeout(scheduled); restarts.delete(host) }
  const launched = (async () => {
    guardElectronDevExit(startup, host)
    await startup()
    const child = host.electronApp
    if (!child) throw Error('Electron did not start')
    child.removeListener('exit', host.exit)
    child.once('exit', (code, signal) => {
      if (host.electronApp === child) host.electronApp = undefined
      if (code === 75) {
        const timer = setTimeout(() => {
          restarts.delete(host)
          launchElectronDev(startup, host).catch(error => { console.error(error); host.exit(1) })
        }, 200)
        restarts.set(host, timer)
      } else host.exit(code === null ? signal ? 1 : 0 : code)
    })
  })()
  launches.set(host, launched)
  try { await launched }
  finally { if (launches.get(host) === launched) launches.delete(host) }
}

// On the initial build the plugin invokes whichever entry finished last.
// Every preload must therefore be able to start Electron as well as reload it.
// Singleflight also prevents parallel watchers/restart timers spawning peers.
function reloadOrLaunchElectronDev(startup, reload, host = process) {
  const child = host.electronApp
  if (child && child.exitCode === null && child.signalCode === null && !launches.has(host)) return reload()
  return launchElectronDev(startup, host)
}

module.exports = { guardElectronDevExit, launchElectronDev, reloadOrLaunchElectronDev }
