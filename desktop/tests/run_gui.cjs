// Reproducible native smoke: real package version, private profile, scripted backend.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const {spawnSync} = require('node:child_process')
const root = path.resolve(__dirname, '../..'), desktop = path.join(root, 'desktop')
const value = flag => {const at = process.argv.indexOf(flag); return at < 0 ? null : process.argv[at + 1]}
const caseName = value('--case'), outputArg = value('--output'), python = value('--python')
assert.ok(['about-version','question-host','resume-recovery'].includes(caseName), 'Explicit supported --case required')
assert.ok(outputArg && path.isAbsolute(outputArg), 'Explicit absolute --output required')
assert.ok(python && path.isAbsolute(python) && fs.statSync(python).isFile(), 'Explicit --python executable required')
const output = path.resolve(outputArg)
const inside = (base, candidate) => {const rel = path.relative(base, candidate); return !rel || (!rel.startsWith('..' + path.sep) && rel !== '..' && !path.isAbsolute(rel))}
assert.ok(!inside(root, output), 'Use a fresh output outside the checkout')
assert.ok(!fs.existsSync(output), 'Use a fresh output directory')
fs.mkdirSync(output, {recursive:true})
assert.ok(!inside(fs.realpathSync(root), fs.realpathSync(output)), 'Output cannot resolve inside checkout')
const app = path.join(output, 'app'); fs.mkdirSync(app)
const version = JSON.parse(fs.readFileSync(path.join(desktop, 'package.json'), 'utf8')).version
fs.writeFileSync(path.join(app, 'package.json'), JSON.stringify({name:'nova-native-contract',version,main:'launch.cjs'}))
fs.writeFileSync(path.join(app, 'launch.cjs'), 'require(' + JSON.stringify(path.join(__dirname, 'gui_windows.electron.cjs')) + ')\n')
const env = {}
for (const name of ['SystemRoot','WINDIR','PATH','PATHEXT','COMSPEC','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMDATA']) {
  if (process.env[name]) env[name] = process.env[name]
}
for (const [name, suffix] of Object.entries({HOME:'user',USERPROFILE:'user',APPDATA:'user/AppData/Roaming',LOCALAPPDATA:'user/AppData/Local',TEMP:'user/AppData/Local/Temp',TMP:'user/AppData/Local/Temp'})) {
  env[name] = path.join(output, suffix); fs.mkdirSync(env[name], {recursive:true})
}
env.NOVA_GUI_TEST_OUTPUT = path.join(output, 'run')
env.NOVA_TEST_PYTHON = python
env.PYTHONIOENCODING = 'utf-8'
env.LOCAL_CLI_STATE_DIR = path.join(output, 'state')
const electron = require(path.join(desktop, 'node_modules/electron'))
const stdout = fs.openSync(path.join(output, 'stdout.log'), 'wx')
const stderr = fs.openSync(path.join(output, 'stderr.log'), 'wx')
let result
try { result = spawnSync(electron, [app, '--' + caseName], {cwd:root, env, windowsHide:true, stdio:['ignore',stdout,stderr],timeout:240000}) }
finally { fs.closeSync(stdout); fs.closeSync(stderr) }
if (result.error) throw result.error
process.exitCode = result.status === null ? 1 : result.status
