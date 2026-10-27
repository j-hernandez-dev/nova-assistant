const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require('./register_typescript.cjs')
require.extensions['.css']=()=>{}
require.extensions['.tsx'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText, filename)
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { projectPathKey, sameProjectPath, fileBasename, validProjectState, projectErrorKey, mergeProjectEntries, projectPreviewMatches } = require('../src/project_presentation.ts')
const { FileExplorer } = require('../src/components/FileExplorer.tsx')
const { translate } = require('../src/i18n.tsx')
const { FileViewer } = require('../src/components/FileViewer.tsx')
const state = { schemaVersion: 1, defaultPath: 'C:\\Nova\\workspace', activePath: 'C:\\owned project', busy: false,
  folders: [{ path: 'C:\\Nova\\workspace', name: 'workspace', isDefault: true },
    { path: 'C:\\owned project', name: 'owned project', isDefault: false }] }
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props))

test('Project display correlation supports Windows separators and preserves POSIX case', () => {
  assert.equal(fileBasename('C:\\Owned Folder\\README.md'), 'README.md')
  assert.equal(fileBasename('/owned/README.md'), 'README.md')
  assert.equal(projectPathKey('C:\\Owned\\'), 'c:/owned')
  assert.equal(sameProjectPath('C:\\Owned', 'c:/owned/'), true)
  assert.equal(sameProjectPath('/Owned', '/owned'), false)
  assert.equal(sameProjectPath(null, undefined), false)
})
test('A late or mismatched preview is not admitted to the current project display', () => {
  assert.equal(projectPreviewMatches({ root: 'c:/owned project', path: 'C:\\owned project\\README.md' }, 'C:\\owned project', 'c:/owned project/README.md'), true)
  for (const result of [{ root: 'c:/old', path: 'c:/owned/file' }, { root: 'c:/owned', path: 'c:/old/file' }, {}]) {
    assert.equal(projectPreviewMatches(result, 'c:/owned', 'c:/owned/file'), false)
  }
})
test('Host state validation rejects malformed project state rather than fabricating a root', () => {
  assert.equal(validProjectState(state), true)
  for (const invalid of [null, {}, { ...state, schemaVersion: 2 }, { ...state, activePath: 17 },
    { ...state, busy: 'false' }, { ...state, folders: [{ path: 'x', isDefault: false }] }]) assert.equal(validProjectState(invalid), false)
})
test('Host project and preview error codes map to localized product messages', () => {
  for (const code of ['PROJECT_BUSY', 'PROJECT_OUTSIDE_ROOT', 'PROJECT_STALE_ROOT', 'PROJECT_FILE_TOO_LARGE',
    'PROJECT_BINARY_FILE', 'PROJECT_NOT_DIRECTORY', 'PROJECT_UNAVAILABLE', 'PROJECT_PREFERENCES_SAVE_FAILED',
    'PROJECT_OPEN_FAILED', 'PROJECT_DEFAULT_REQUIRED', 'PROJECT_PREVIOUS_UNAVAILABLE', 'PROJECT_DEFAULT_UNAVAILABLE',
    'PROJECT_BOOTSTRAP_FAILED', 'PROJECT_CHANGE_NOT_CONFIRMED', 'CONFLICT_ACTIVE_OPERATION', 'PROJECT_CHANGE_UNKNOWN']) assert.notEqual(projectErrorKey(code), 'projectActionFailed', code)
  assert.equal(projectErrorKey('UNTRUSTED_EXTERNAL_ERROR'), 'projectActionFailed')
})
test('Bounded folder pages merge without losing expanded child state or duplicating paths', () => {
  const folder = { path: 'C:/OWNED/src', name: 'src', isDirectory: true, expanded: true, children: [{ name: 'kept' }] }
  const result = mergeProjectEntries([folder], [{ ...folder, path: 'c:\\owned\\SRC', expanded: false },
    { path: 'C:/OWNED/readme', name: 'README.md', isDirectory: false }])
  assert.equal(result.length, 2)
  assert.equal(result[0], folder)
  assert.equal(result[0].children[0].name, 'kept')
})
test('Project drawer is localized, escaped, uses registered folder actions and exposes no raw cwd setter', () => {
  const html = render(FileExplorer, { projects: { ...state, folders: [...state.folders,
    { path: 'C:/<script>bad</script>', name: '<script>bad</script>', isDefault: false }] }, busy: false, errorCode: null,
    onFileSelect() {}, async onProjectAction() {} })
  assert.ok(html.includes('Proyectos'))
  assert.ok(html.includes('Añadir proyecto'))
  assert.ok(html.includes('<span>owned project</span>'))
  assert.ok(!html.includes('Carpeta con acceso'))
  assert.deepEqual(['projectChange','projectRemove','projectOpen'].map(key=>translate('es',key)), ['Cambiar proyecto','Quitar proyecto','Abrir en el Explorador'])
  assert.equal(translate('en','projectRemove'),'Remove project')
  assert.ok(html.includes('Proyecto predeterminado'))
  assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'))
  assert.ok(!html.includes('<script>bad</script>'))
  assert.ok(html.includes('aria-pressed="true"'))
  const app = fs.readFileSync(require.resolve('../src/App.tsx'), 'utf8')
  assert.ok(!app.includes("type: 'set_cwd'"))
  assert.ok(!app.includes('openDirectoryDialog()'))
  assert.ok(app.includes('window.api.projectAction(action, path)'))
})
test('Preview remains read-only and escaped, with a localized dismiss control', () => {
  const html = render(FileViewer, { filePath: 'C:\\Owned\\<unsafe>.txt', rootDir: 'C:\\Owned', onClose() {} })
  assert.ok(html.includes('&lt;unsafe&gt;.txt'))
  assert.ok(html.includes('Cerrar vista previa'))
  assert.ok(html.includes('Cargando vista previa'))
  assert.ok(!html.includes('contenteditable'))
  assert.ok(!html.includes('<textarea'))
})

test('Hiding files preserves project selection and actions while omitting the file tree',()=>{
  const props={projects:state,busy:false,errorCode:null,onFileSelect(){},async onProjectAction(){}}
  const visible=render(FileExplorer,props),hidden=render(FileExplorer,{...props,showFiles:false})
  assert.ok(visible.includes('class="explorer-tree"'))
  for(const text of ['Archivos','Fuentes','Recuerdos'])assert.ok(visible.includes(text),text)
  assert.ok(!hidden.includes('project-content-panel'))
  assert.ok(!hidden.includes('class="explorer-tree"'))
  for(const text of ['owned project','Añadir proyecto',translate('es','projectOptions')])assert.ok(hidden.includes(text),text)
  assert.equal((hidden.match(/class="project-select-button"/g)||[]).length,state.folders.length)
})


test('Project settings present the default first, path descriptions and one menu per registered folder in both languages',()=>{
 const i18n=require('../src/i18n.tsx'),original=i18n.useI18n,{ProjectsSettings}=require('../src/components/ProjectsSettings.tsx')
 try{for(const locale of ['es','en']){
  i18n.useI18n=()=>({t:key=>translate(locale,key)})
  const html=render(ProjectsSettings,{projects:state,busy:false,errorCode:null,async onAction(){}})
  const headings=[...html.matchAll(/<h3[^>]*>([^<]+)<\/h3>/g)].map(m=>m[1])
  assert.deepEqual(headings,locale==='es'?['Carpeta predeterminada','Carpetas por proyecto']:['Default folder','Folders by project'])
  assert.equal((html.match(/data-project-menu=/g)||[]).length,2)
  assert.ok(html.includes(locale==='es'?'Restablecer':'Reset'))
  assert.ok(html.includes('owned project'))
  assert.doesNotMatch(html,/Proyecto actual|Proyecto predeterminado|Abrir panel de proyectos|Current project|Open project panel/)
 }}finally{i18n.useI18n=original}
})
