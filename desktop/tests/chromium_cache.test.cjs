const { test } = require('node:test'), assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), os = require('node:os')
const { prepareChromiumCaches, CACHE_NAMES } = require('../electron/chromium_cache.cjs')

function fixture(t) {
  const parent = path.resolve(process.env.NOVA_CACHE_TEST_ROOT || os.tmpdir())
  fs.mkdirSync(parent, { recursive: true })
  const root = fs.mkdtempSync(path.join(parent, 'nova-cache-test-'))
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), parent)
    assert.ok(path.basename(root).startsWith('nova-cache-test-'))
    fs.rmSync(root, { recursive: true, force: true })
  })
  return root
}
const put = (root, name, value) => {
  const filename = path.join(root, name)
  fs.mkdirSync(path.dirname(filename), { recursive: true })
  fs.writeFileSync(filename, value)
}

test('damaged caches rotate before startup; settings, cookies and browser storage remain byte-for-byte intact', t => {
  const root = fixture(t)
  const preserved = ['desktop-preferences.json', 'project-preferences.json', 'Preferences', 'Local State', 'Local Storage/data', 'Session Storage/data', 'Network/Cookies', 'knowledge/v1/knowledge.db']
  for (const name of preserved) put(root, name, 'preserve:' + name)
  for (const name of CACHE_NAMES) put(root, name + '/data_0', 'interrupted blockfile')
  const first = prepareChromiumCaches(root)
  assert.deepEqual(first.rotated, CACHE_NAMES)
  assert.deepEqual(first.failures, [])
  for (const name of CACHE_NAMES) {
    assert.equal(fs.existsSync(path.join(root, name)), false)
    assert.equal(fs.readFileSync(path.join(first.backupDirectory, name, 'data_0'), 'utf8'), 'interrupted blockfile')
    put(root, name + '/index', 'new cache')
  }
  const second = prepareChromiumCaches(root)
  assert.deepEqual(second.failures, [])
  for (const name of CACHE_NAMES) {
    assert.equal(fs.existsSync(path.join(second.backupDirectory, name, 'data_0')), false)
    assert.equal(fs.readFileSync(path.join(second.backupDirectory, name, 'index'), 'utf8'), 'new cache')
  }
  for (const name of preserved) assert.equal(fs.readFileSync(path.join(root, name), 'utf8'), 'preserve:' + name)
})

test('a failed cache rename is reported without stopping recovery of other caches or deleting the original', t => {
  const root = fixture(t)
  put(root, 'GPUCache/data_0', 'locked cache')
  put(root, 'Code Cache/index', 'other cache')
  const io = { ...fs, renameSync(source, target) {
    if (path.basename(source) === 'GPUCache') throw Object.assign(new Error('locked'), { code: 'EPERM' })
    fs.renameSync(source, target)
  } }
  const result = prepareChromiumCaches(root, io)
  assert.deepEqual(result.failures, [{ name: 'GPUCache', code: 'EPERM' }])
  assert.deepEqual(result.rotated, ['Code Cache'])
  assert.equal(fs.readFileSync(path.join(root, 'GPUCache/data_0'), 'utf8'), 'locked cache')
})

test('unexpected file at the backup path is left intact; no cache path escapes its profile', t => {
  const root = fixture(t)
  put(root, 'GPUCache/data_0', 'original')
  put(root, '.chromium-cache-backup', 'not a cache directory')
  const result = prepareChromiumCaches(root)
  assert.deepEqual(result.failures, [{ name: 'GPUCache', code: 'CACHE_DIRECTORY_UNSAFE' }])
  assert.equal(fs.readFileSync(path.join(root, '.chromium-cache-backup'), 'utf8'), 'not a cache directory')
  assert.equal(fs.readFileSync(path.join(root, 'GPUCache/data_0'), 'utf8'), 'original')
  assert.throws(() => prepareChromiumCaches('../other-profile'), /MUST_BE_ABSOLUTE/)
})
