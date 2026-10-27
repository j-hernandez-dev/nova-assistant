// Ordinary contracts only: no native windows, model inference or packaging.
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const { spawnSync } = require('node:child_process')
const assert = require('node:assert/strict')

const root = path.resolve(__dirname, '..')
const desktop = path.join(root, 'desktop')
const inventory = JSON.parse(fs.readFileSync(path.join(__dirname, 'pytest_contracts.json'), 'utf8'))
const files = fs.readdirSync(path.join(desktop, 'tests'))
  .filter(name => name.endsWith('.test.cjs')).map(name => 'tests/' + name).sort()
assert.ok(files.length > 0, 'Desktop contract selection must not be empty')
assert.deepEqual(inventory.desktop_ordinary.files, files, 'Desktop contract inventory drift')
const temporaryParent = fs.realpathSync(process.env.NOVA_DESKTOP_TEST_TMP || os.tmpdir())
const temporary = fs.mkdtempSync(path.join(temporaryParent, 'nova-desktop-contracts-'))
let result
try {
  result = spawnSync(process.execPath, ['--experimental-transform-types', '--test', '--test-concurrency=2', ...files], {
    cwd: desktop, stdio: 'inherit', windowsHide: true,
    env: { ...process.env, NOVA_DESKTOP_TEST_TMP: temporary },
  })
  if (result.error) throw result.error
} finally {
  assert.equal(path.dirname(path.resolve(temporary)), temporaryParent, 'Unexpected temporary directory')
  assert.ok(path.basename(temporary).startsWith('nova-desktop-contracts-'))
  assert.equal(fs.realpathSync(temporary), temporary, 'Temporary directory was replaced or redirected')
  fs.rmSync(temporary, { recursive: true, force: true })
}
process.exitCode = result.status === null ? 1 : result.status
