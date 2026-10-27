// Manual hidden smoke with a real backend, owned profile and no model turns.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path')
const cp = require('node:child_process'), Module = require('node:module'), electron = require('electron')
assert.ok(process.env.NOVA_GUI_TEST_OUTPUT && process.env.NOVA_TEST_PYTHON, 'owned output and installed Python required')
const output = path.resolve(process.env.NOVA_GUI_TEST_OUTPUT), mode = process.env.NOVA_CACHE_CASE || 'first'
const secondary = process.argv.includes('--secondary'), profile = path.join(output, 'app-data', 'nova-desktop')
const home = path.join(output, 'home'), workspace = path.join(output, 'project')
const cacheNames = ['Cache', 'Code Cache', 'GPUCache', 'DawnGraphiteCache', 'DawnWebGPUCache']
const put = (relative, value) => { const name = path.join(profile, relative); fs.mkdirSync(path.dirname(name), { recursive: true }); fs.writeFileSync(name, value) }
const preferences = JSON.stringify({ schemaVersion: 1, locale: 'es', transitionsEnabled: false })
if (!secondary) {
  if (mode === 'first' || mode === 'fallback') {
    assert.ok(!fs.existsSync(output), 'fresh owned output required')
    for (const directory of [profile, home, workspace]) fs.mkdirSync(directory, { recursive: true })
    put('desktop-preferences.json', preferences)
    put('project-preferences.json', JSON.stringify({ schemaVersion: 1, folders: [workspace], activePath: workspace }))
    put('Local Storage/retention-canary.txt', 'retained browser storage')
    for (const name of cacheNames) put(name + '/data_0', 'interrupted cache')
    if (mode === 'fallback') put('.chromium-cache-backup', 'do not overwrite an unexpected file')
  } else assert.ok(fs.existsSync(path.join(output, 'first-result.json')))
}
electron.app.setPath('appData', path.dirname(profile))
Object.assign(process.env, { HOME: home, USERPROFILE: home, LOCALAPPDATA: path.join(home, 'AppData', 'Local'),
  XDG_CONFIG_HOME: path.join(home, '.config'), LOCAL_CLI_STATE_DIR: path.join(home, 'state'),
  PYTHONDONTWRITEBYTECODE: '1', LOCAL_CLI_AUTO_UPDATE: 'false' })
delete process.env.VITE_DEV_SERVER_URL
let backend, win, view, ready = false, finished = false
const errors = [], stderr = [], checks = []
function finish(error) {
  if (finished || secondary) return
  finished = true; clearTimeout(deadline)
  fs.writeFileSync(path.join(output, mode + '-result.json'), JSON.stringify({ status: error ? 'FAIL' : 'PASS',
    error: error?.stack, checks, errors, stderr: stderr.join(''), backendReady: !!view?.status?.ready }, null, 2))
  backend?.kill()
  if (error || mode === 'first') electron.app.exit(error ? 1 : 0)
  else electron.app.quit()
}
process.on('uncaughtException', finish); process.on('unhandledRejection', finish)
const deadline = setTimeout(() => finish(Error('Startup timeout')), 45000)
const spawn = cp.spawn
cp.spawn = function (command, args, options) {
  if (args?.includes('--server')) {
    assert.equal(secondary, false, 'second instance must exit before backend startup')
    backend = spawn(process.env.NOVA_TEST_PYTHON, args, { ...options, windowsHide: true })
    backend.stderr.on('data', data => stderr.push(String(data)))
    return backend
  }
  return spawn(command, args, options)
}
class HiddenWindow extends electron.BrowserWindow {
  show() {}
  showInactive() {}
  constructor(options) {
    if (!options.parent) {
      assert.equal(fs.readFileSync(path.join(profile, 'desktop-preferences.json'), 'utf8'), preferences)
      assert.equal(fs.readFileSync(path.join(profile, 'Local Storage/retention-canary.txt'), 'utf8'), 'retained browser storage')
      assert.equal(electron.app.getPath('sessionData'), profile)
      if (mode === 'first') for (const name of cacheNames) {
        assert.equal(fs.existsSync(path.join(profile, name)), false)
        assert.equal(fs.readFileSync(path.join(profile, '.chromium-cache-backup', name, 'data_0'), 'utf8'), 'interrupted cache')
      }
      if (mode === 'reopen') assert.equal(fs.readFileSync(path.join(profile, '.chromium-cache-backup', 'Code Cache', 'interrupted-canary'), 'utf8'), 'left by abrupt termination')
      if (mode === 'fallback') {
        assert.ok(electron.app.commandLine.hasSwitch('disable-http-cache'))
        assert.ok(electron.app.commandLine.hasSwitch('disable-gpu-shader-disk-cache'))
      }
      checks.push('cache recovery runs before BrowserWindow; preferences and browser storage preserved')
    }
    super({ ...options, show: false, webPreferences: { ...options.webPreferences, backgroundThrottling: false } })
    if (!options.parent) win = this
    this.webContents.on('did-finish-load', () => { ready = true })
    this.webContents.on('preload-error', (_e, _p, error) => errors.push(error.message))
    this.webContents.on('render-process-gone', (_e, detail) => errors.push(detail.reason))
    const send = this.webContents.send.bind(this.webContents)
    this.webContents.send = (channel, ...args) => { if (channel === 'session-view') view = args[0]; return send(channel, ...args) }
  }
}
const load = Module._load
Module._load = function (name, ...args) { return name === 'electron' ? { ...electron, BrowserWindow: HiddenWindow } : load.call(this, name, ...args) }
require('../dist-electron/main.js')
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(predicate) { const end = Date.now() + 35000; while (Date.now() < end) { if (predicate()) return; await delay(80) } throw Error('Backend did not become ready') }
if (!secondary) electron.app.whenReady().then(async () => {
  try {
    await until(() => ready && view?.status?.ready)
    assert.equal(path.resolve(view.workspace), workspace)
    assert.deepEqual(errors, [])
    assert.equal(stderr.join(''), '')
    checks.push('real renderer and Python backend ready, no stderr')
    if (mode === 'first') {
      put('GPUCache/second-instance-canary', 'active primary cache')
      const duplicate = spawn(process.execPath, [__filename, '--secondary'], { env: process.env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
      let secondError = ''
      duplicate.stderr.on('data', data => { secondError += data })
      const code = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { duplicate.kill(); reject(Error('Second instance did not exit')) }, 10000)
        duplicate.on('error', reject); duplicate.on('exit', value => { clearTimeout(timer); resolve(value) })
      })
      assert.equal(code, 0, secondError)
      assert.equal(fs.readFileSync(path.join(profile, 'GPUCache/second-instance-canary'), 'utf8'), 'active primary cache')
      checks.push('second instance exits without moving primary caches or starting a backend')
      put('Code Cache/interrupted-canary', 'left by abrupt termination')
      checks.push('immediate app.exit without normal shutdown; reopen must recover the cache')
    }
    if (mode === 'reopen') checks.push('successful restart after forced termination and fresh cache rotation')
    if (mode === 'fallback') checks.push('unavailable cache backup uses memory caches while startup remains functional')
    finish()
  } catch (error) { finish(error) }
})
