// Owns Electron's logging pipes and closes them after the real app is ready.
// The Electron fixture uses an isolated profile and never shows a window.
const {spawn}=require('node:child_process')
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict')
const output=process.env.NOVA_GUI_TEST_OUTPUT
assert.ok(output,'owned output directory required')
fs.mkdirSync(output,{recursive:true})
const env={...process.env};delete env.ELECTRON_RUN_AS_NODE
const child=spawn(require('electron'),[path.join(__dirname,'gui_windows.electron.cjs'),'--closed-console'],{
  cwd:path.resolve(__dirname,'..'),env,stdio:['ignore','pipe','pipe','ipc'],windowsHide:true,
})
let closed=false,logs=''
child.stdout.on('data',chunk=>{logs+=String(chunk)})
child.stderr.on('data',chunk=>{logs+=String(chunk)})
child.on('message',message=>{
  if(message?.type==='close-console'){
    closed=true;child.stdout.destroy();child.stderr.destroy()
  }
})
child.on('error',error=>{throw error})
child.on('exit',code=>{
  fs.writeFileSync(path.join(output,'launcher.log'),logs)
  try{
    assert.equal(closed,true,'the test must actually close the pipes')
    assert.equal(code,0)
    assert.equal(JSON.parse(fs.readFileSync(path.join(output,'result.json'),'utf8')).status,'PASS')
    console.log('PASS: real Electron survives closed stdout/stderr and backend exit without visible windows')
  }catch(error){console.error(error);process.exitCode=1}
})
