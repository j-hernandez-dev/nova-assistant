const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')

// Development must use the environment installed for this checkout, even when
// the launching terminal still has another (possibly removed) venv activated.
function resolvePythonRuntime(projectRoot, options = {}) {
  const platform = options.platform || process.platform
  const paths = platform === 'win32' ? path.win32 : path.posix
  const exists = options.exists || fs.existsSync
  const probe = options.probe || (command => {
    try {
      execFileSync(command, ['--version'], { stdio: 'ignore', windowsHide: true })
      return true
    } catch { return false }
  })
  const inherited = options.env || process.env
  const env = Object.fromEntries(Object.entries(inherited).filter(([, value]) => value !== undefined))
  const venv = paths.join(projectRoot, '.venv')
  const executable = paths.join(venv, platform === 'win32' ? 'Scripts' : 'bin', platform === 'win32' ? 'python.exe' : 'python')

  if (exists(executable)) {
    const inheritedPath = Object.entries(env).find(([key]) => key.toUpperCase() === 'PATH')?.[1] || ''
    for (const key of Object.keys(env)) {
      if (['PATH', 'PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', '__PYVENV_LAUNCHER__', 'PYTHONNOUSERSITE'].includes(key.toUpperCase())) delete env[key]
    }
    env.PATH = paths.dirname(executable) + (inheritedPath ? paths.delimiter + inheritedPath : '')
    env.VIRTUAL_ENV = venv
    env.PYTHONNOUSERSITE = '1'
    return { executable, env }
  }

  // Preserve the existing system-Python fallback for installations without a
  // project venv, including packaged applications and minimal GUI PATHs.
  const candidates = platform === 'darwin'
    ? ['/opt/homebrew/bin/python3', '/usr/local/bin/python3', 'python3']
    : ['/usr/bin/python3', '/usr/local/bin/python3', 'python3']
  return { executable: platform === 'win32' ? 'python' : candidates.find(probe) || 'python3', env }
}

module.exports = { resolvePythonRuntime }
