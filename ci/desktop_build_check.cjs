// Actual Vite build entry from package.json, stopping before electron-builder.
// Build outputs are disposable; frozen product source/config is never edited.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto')
const {spawnSync}=require('node:child_process')
const repo=path.resolve(__dirname,'..'),desktop=path.join(repo,'desktop')
const raw=process.argv[2]
if (!raw || !path.isAbsolute(raw)) throw Error('ABSOLUTE_OWNED_CI_OUTPUT_REQUIRED')
const out=path.resolve(raw),relation=path.relative(repo,out)
if (!relation.startsWith('..') || fs.existsSync(out)) throw Error('FRESH_OUTPUT_OUTSIDE_CHECKOUT_REQUIRED')
fs.mkdirSync(out,{recursive:true})
const generated=path.join(desktop,'dist-electron')
const originals=['main.js','preload.js'].map(name=>{
  const file=path.join(generated,name),backup=path.join(out,'original_generated',name),existed=fs.existsSync(file)
  if (existed) {fs.mkdirSync(path.dirname(backup),{recursive:true});fs.copyFileSync(file,backup)}
  return {file,backup,existed}
})
let result
try {
  result=spawnSync(process.execPath,[path.join(desktop,'node_modules/vite/bin/vite.js'),'build',
    '--outDir',path.join(out,'renderer'),'--emptyOutDir','false'],{
    cwd:desktop,encoding:'utf8',timeout:120000,windowsHide:true})
  fs.writeFileSync(path.join(out,'build.log'),(result.stdout||'')+(result.stderr||''))
  const pins=originals.filter(row=>fs.existsSync(row.file)).map(row=>{
    const data=fs.readFileSync(row.file)
    return {name:path.basename(row.file),bytes:data.length,sha256:crypto.createHash('sha256').update(data).digest('hex')}
  })
  fs.writeFileSync(path.join(out,'build_identity.json'),JSON.stringify({schemaVersion:1,
    scope:'ACTUAL_DESKTOP_VITE_SOURCE_BUILD_CHECK',node:process.version,
    command:'vite build using unchanged desktop/vite.config.ts',exitCode:result.status,
    installer:false,publish:false,release:false,guiEndToEnd:false,nativeCertification:false,
    errorCode:result.error?.code||null,generatedEntryPins:result.status===0?pins:[]},null,2)+'\n')
  process.stdout.write(result.stdout||'');process.stderr.write(result.stderr||'')
  process.exitCode=result.status===0?0:1
} finally {
  // Preserve pre-existing generated entries; no historical evidence is involved.
  for (const row of originals) {
    if (row.existed) fs.copyFileSync(row.backup,row.file)
    else if (fs.existsSync(row.file)) fs.unlinkSync(row.file)
  }
}
