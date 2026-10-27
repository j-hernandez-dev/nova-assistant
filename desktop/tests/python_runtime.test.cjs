const { test } = require('node:test')
const assert = require('node:assert/strict')
const { resolvePythonRuntime, resolveDefaultWorkspace } = require('../electron/python_runtime.cjs')

test('Windows uses the checkout venv despite a stale activated environment', () => {
  const inherited = {
    Path: 'C:\\Temp\\removed-venv\\Scripts;C:\\Windows\\System32',
    pythonhome: 'C:\\Temp\\removed-venv', PYTHONPATH: 'C:\\Temp\\old-source',
    virtual_env: 'C:\\Temp\\removed-venv', __PYVENV_LAUNCHER__: 'old-python',
    PythonNoUserSite: '0', LOCAL_CLI_MODEL: 'saved-model', NOVA_APPROVAL_HOST_KEY: 'host-key',
  }
  const before = { ...inherited }
  const runtime = resolvePythonRuntime('C:\\Nova', {
    platform: 'win32', env: inherited,
    exists: filename => filename === 'C:\\Nova\\.venv\\Scripts\\python.exe',
    probe: () => { throw Error('must not probe the old environment') },
  })
  assert.equal(runtime.executable, 'C:\\Nova\\.venv\\Scripts\\python.exe')
  assert.equal(runtime.env.PATH, 'C:\\Nova\\.venv\\Scripts;' + inherited.Path)
  assert.equal(runtime.env.VIRTUAL_ENV, 'C:\\Nova\\.venv')
  assert.equal(runtime.env.PYTHONNOUSERSITE, '1')
  assert.deepEqual(Object.keys(runtime.env).filter(k => ['PYTHONHOME', 'PYTHONPATH', '__PYVENV_LAUNCHER__'].includes(k.toUpperCase())), [])
  assert.equal(Object.keys(runtime.env).filter(k => k.toUpperCase() === 'PATH').length, 1)
  assert.equal(runtime.env.LOCAL_CLI_MODEL, 'saved-model')
  assert.equal(runtime.env.NOVA_APPROVAL_HOST_KEY, 'host-key')
  assert.deepEqual(inherited, before)
})

for (const platform of ['linux', 'darwin']) test(platform + ' uses its checkout venv and preserves ordinary tool paths', () => {
  const runtime = resolvePythonRuntime('/apps/nova', {
    platform, env: { PATH: '/usr/bin:/bin', PYTHONHOME: '/old-python' },
    exists: filename => filename === '/apps/nova/.venv/bin/python',
  })
  assert.equal(runtime.executable, '/apps/nova/.venv/bin/python')
  assert.equal(runtime.env.PATH, '/apps/nova/.venv/bin:/usr/bin:/bin')
  assert.equal(runtime.env.PYTHONHOME, undefined)
})

test('without a checkout venv, existing system-Python fallbacks and environment are retained', () => {
  const env = { PATH: '/custom/bin', PYTHONPATH: '/packaged/source' }
  const base = { env, exists: () => false }
  assert.deepEqual(resolvePythonRuntime('C:\\resources', { ...base, platform: 'win32' }), { executable: 'python', env })
  assert.equal(resolvePythonRuntime('/resources', { ...base, platform: 'darwin', probe: c => c === '/usr/local/bin/python3' }).executable, '/usr/local/bin/python3')
  assert.equal(resolvePythonRuntime('/resources', { ...base, platform: 'linux', probe: () => false }).executable, 'python3')
})

test('packaged Windows starts its exact bundled executable without probing a system Python', () => {
  const inherited={Path:'C:\\Tools',PYTHONHOME:'C:\\foreign',PythonPath:'C:\\old',VIRTUAL_ENV:'old',_PYI_APPLICATION_HOME_DIR:'foreign',NOVA_APPROVAL_HOST_KEY:'bound-secret'}
  const runtime=resolvePythonRuntime('C:\\Program Files\\Nova\\resources',{
    platform:'win32',packaged:true,env:inherited,
    exists:filename=>filename==='C:\\Program Files\\Nova\\resources\\backend\\nova-backend.exe',
    probe:()=>{throw Error('Packaged apps must not discover another interpreter')},
  })
  assert.equal(runtime.executable,'C:\\Program Files\\Nova\\resources\\backend\\nova-backend.exe')
  assert.deepEqual(runtime.args,['--server'])
  assert.equal(runtime.env.NOVA_APPROVAL_HOST_KEY,'bound-secret')
  assert.equal(runtime.env.Path,'C:\\Tools')
  for(const key of ['PYTHONHOME','PythonPath','VIRTUAL_ENV','_PYI_APPLICATION_HOME_DIR'])assert.equal(runtime.env[key],undefined)
  assert.equal(inherited.PYTHONHOME,'C:\\foreign')
})

test('a missing packaged backend fails closed instead of falling back to system Python or a venv', () => {
  assert.throws(()=>resolvePythonRuntime('C:\\Nova\\resources',{
    platform:'win32',packaged:true,exists:filename=>filename.includes('.venv'),
    probe:()=>{throw Error('Unexpected interpreter lookup')},
  }),/BUNDLED_BACKEND_NOT_FOUND/)
})

test('fresh packaged workspaces are writable user documents, independent of the installation directory', () => {
  const documents='C:\\Users\\Example\\Documents'
  for(const installation of ['C:\\Program Files\\Nova\\resources','D:\\Apps\\Nova\\resources']){
    assert.equal(resolveDefaultWorkspace(installation,documents,true,'win32'),documents+'\\Nova\\workspace')
  }
  assert.equal(resolveDefaultWorkspace('C:\\checkout',documents,false,'win32'),'C:\\checkout\\workspace')
})
