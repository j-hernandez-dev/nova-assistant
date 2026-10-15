// S8 runs the existing real Electron lifecycle harness against today's build.
// Only the test entry removes GPU probes/update checks. No policy, broker,
// launcher, grant, approval or audit adapter is replaced here.
const cp = require('node:child_process')
const path = require('node:path')
const spawn = cp.spawn
cp.spawn = (command, args, options) => {
  if (args.includes('--server') || args.some(a => a.endsWith('desktop_backend_fixture.py'))) {
    const mode = process.env.NOVA_REAL_OLLAMA_E2E === '1' ? '--server' : '--fixture'
    return spawn(command, [path.resolve(__dirname, '../../tests/security_v12/s8_backend_entry.py'), mode],
      { ...options, windowsHide: true })
  }
  return spawn(command, args, options)
}
require('./electron_phase13.cjs')
