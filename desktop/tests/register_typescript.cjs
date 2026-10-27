// Test-only loader: use the project's existing TypeScript, no added runner.
const fs = require('node:fs')
const ts = require('typescript')
const Module = require('node:module'), path = require('node:path')
const resolveFilename = Module._resolveFilename
Module._resolveFilename = function(request, ...args) {
  return request === '@nova/keyboard-shortcuts'
    ? path.resolve(__dirname, '../shared/keyboard_shortcuts.cjs')
    : resolveFilename.call(this, request, ...args)
}
require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8')
  module._compile(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  } }).outputText, filename)
}
