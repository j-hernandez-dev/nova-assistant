const {test}=require('node:test'),assert=require('node:assert/strict')
const {EventEmitter}=require('node:events'),{spawn}=require('node:child_process')
const {installConsolePipeGuard}=require('../electron/console_pipes.cjs')
const modulePath=require.resolve('../electron/console_pipes.cjs')
function fixture(){
  const stdout=new EventEmitter(),stderr=new EventEmitter(),calls=[]
  const target={log:(...a)=>calls.push(['log',...a]),info:()=>{},debug:()=>{},warn:(...a)=>calls.push(['warn',...a]),error:(...a)=>calls.push(['error',...a])}
  return {stdout,stderr,target,calls,guard:installConsolePipeGuard({stdout,stderr,console:target})}
}
test('only the broken destination stops receiving console writes; installation is idempotent',()=>{
  const f=fixture(),original=f.target.log
  assert.equal(installConsolePipeGuard({stdout:f.stdout,stderr:f.stderr,console:f.target}),f.guard)
  assert.equal(f.stdout.listenerCount('error'),1)
  f.target.log('before');f.stdout.emit('error',Object.assign(Error('closed'),{code:'EPIPE'}))
  f.target.log('after');f.target.error('stderr still works')
  assert.equal(f.guard.isClosed('stdout'),true);assert.equal(f.guard.isClosed('stderr'),false)
  assert.deepEqual(f.calls,[['log','before'],['error','stderr still works']])
  f.stdout.emit('error',Object.assign(Error('follow-up'),{code:'ERR_STREAM_DESTROYED'}))
  f.guard.dispose();assert.equal(f.stdout.listenerCount('error'),0);assert.notEqual(f.target.log,original)
})
test('synchronous EPIPE is handled, while unrelated console and stream errors still propagate',()=>{
  const f=fixture()
  const unrelated=Object.assign(Error('real failure'),{code:'EIO'})
  assert.throws(()=>f.stderr.emit('error',unrelated),e=>e===unrelated)
  f.guard.dispose()
  const stdout=new EventEmitter(),stderr=new EventEmitter()
  const target={log:()=>{throw Object.assign(Error('closed'),{code:'EPIPE'})},error:()=>{throw unrelated}}
  const guard=installConsolePipeGuard({stdout,stderr,console:target})
  assert.doesNotThrow(()=>target.log());assert.equal(guard.isClosed('stdout'),true)
  assert.throws(()=>target.error(),e=>e===unrelated);guard.dispose()
})
for(const mode of ['stdout','stderr','both'])test('real child process survives closed '+mode+' pipes',async()=>{
  const script=`require(${JSON.stringify(modulePath)}).installConsolePipeGuard();process.send('ready');process.on('message',()=>{let n=0;const t=setInterval(()=>{console.log('window event');console.error('backend exit');if(++n===5){clearInterval(t);setTimeout(()=>{process.send('alive');process.exit(0)},25)}},10)});`
  const child=spawn(process.execPath,['-e',script],{stdio:['ignore','pipe','pipe','ipc'],windowsHide:true})
  await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{child.kill();reject(Error('Child did not complete'))},5000)
    let alive=false
    child.on('error',reject)
    child.on('message',message=>{
      if(message==='ready'){
        if(mode!=='stderr')child.stdout.destroy();else child.stdout.resume()
        if(mode!=='stdout')child.stderr.destroy();else child.stderr.resume()
        child.send('write')
      } else if(message==='alive')alive=true
    })
    child.on('exit',code=>{clearTimeout(timer);try{assert.equal(code,0);assert.equal(alive,true);resolve()}catch(e){reject(e)}})
  })
})
