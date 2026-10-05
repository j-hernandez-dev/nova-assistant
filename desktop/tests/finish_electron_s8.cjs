// S8 development-install finalizer only; no product/runtime dependency.
// Use after the official cached ZIP was checksum-verified and extracted.
// Generate precisely the package metadata its postinstall normally generates.
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const assert = require('node:assert/strict')
const directory = path.resolve(__dirname, '../node_modules/electron')
const zip = process.argv[2]
const executableHashFromArchive = process.argv[3]
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const pkg = require(path.join(directory, 'package.json'))
const checksums = require(path.join(directory, 'checksums.json'))
assert.equal(path.basename(zip), `electron-v${pkg.version}-win32-x64.zip`)
assert.equal(hash(zip), checksums[path.basename(zip)].toLowerCase())
assert.equal(fs.readFileSync(path.join(directory, 'dist/version'), 'utf8').trim(), pkg.version)
const executable = path.join(directory, 'dist/electron.exe')
assert.match(executableHashFromArchive, /^[a-fA-F0-9]{64}$/)
assert.equal(hash(executable), executableHashFromArchive.toLowerCase())
// Generated install artifact, not an edit to a dependency's source/lockfile.
fs.writeFileSync(path.join(directory, 'path.txt'), 'electron.exe')
assert.equal(require(directory), executable)
console.log(JSON.stringify({version:pkg.version, archiveSHA256:hash(zip),
  executableSHA256:hash(executable), moduleResolved:true, download:false}))
