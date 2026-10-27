// Bounded native smoke: actual vite-plugin-electron, actual Electron children,
// isolated generated fixture, and the same launcher used by vite.config.ts.
const fs=require('node:fs')
const path=require('node:path')
const {spawn}=require('node:child_process')
const assert=require('node:assert/strict')

async function run(){
  const output=process.env.NOVA_DEV_RESTART_TEST_OUTPUT
  if(!output||!path.isAbsolute(output))throw Error('NOVA_DEV_RESTART_TEST_OUTPUT must be an absolute fresh test directory')
  if(fs.existsSync(output)&&fs.readdirSync(output).length)throw Error('Test output must be empty')
  fs.mkdirSync(output,{recursive:true})
  const desktop=path.resolve(__dirname,'..'),plugin=require.resolve('vite-plugin-electron'),viteCli=path.join(desktop,'node_modules','vite','bin','vite.js')
  const launcher=path.join(desktop,'dev','electron_exit.cjs')
  fs.writeFileSync(path.join(output,'package.json'),JSON.stringify({name:'nova-dev-restart-smoke',version:'1.0.0',private:true,main:'dist-electron/main.js'}))
  fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html><title>Nova isolated restart check</title><body>restart-smoke</body></html>')
  fs.writeFileSync(path.join(output,'health.txt'),'nova-dev-server-live')
  const slowPreload=process.env.NOVA_DEV_RESTART_SLOW_PRELOAD==='1'
  fs.writeFileSync(path.join(output,'preload.ts'),'export const ready=true\n')
  fs.writeFileSync(path.join(output,'vite.config.mjs'),`
import {createRequire} from 'node:module'
const require=createRequire(import.meta.url)
const {default:electron,startup}=require(${JSON.stringify(plugin)})
const {launchElectronDev,reloadOrLaunchElectronDev}=require(${JSON.stringify(launcher)})
export default {
  cacheDir:${JSON.stringify(path.join(output,'vite-cache'))},
  server:{host:'127.0.0.1',port:0,watch:{ignored:['**/electron-profile/**']}},
  plugins:[electron([{entry:${JSON.stringify(path.join(output,'main.ts'))},onstart:()=>launchElectronDev(startup),
    vite:{build:{outDir:${JSON.stringify(path.join(output,'dist-electron'))},minify:false}}},
    ...(${slowPreload}?[{entry:${JSON.stringify(path.join(output,'preload.ts'))},onstart:({reload})=>reloadOrLaunchElectronDev(startup,reload),
      vite:{build:{outDir:${JSON.stringify(path.join(output,'dist-electron'))},minify:false},plugins:[{name:'deliberately-slow-preload',async generateBundle(){await new Promise(resolve=>setTimeout(resolve,1000))}}]}}]:[])])],
}
`)
  fs.writeFileSync(path.join(output,'main.ts'),`
import {app,BrowserWindow} from 'electron'
import fs from 'node:fs'
import path from 'node:path'
const root=${JSON.stringify(output)},events=path.join(root,'events.jsonl')
app.setPath('userData',path.join(root,'electron-profile'))
app.setPath('sessionData',path.join(root,'electron-profile'))
app.disableHardwareAcceleration()
const record=value=>fs.appendFileSync(events,JSON.stringify({...value,pid:process.pid,time:Date.now()})+'\\n')
const prior=fs.existsSync(events)?fs.readFileSync(events,'utf8').trim().split('\\n').filter(Boolean).map(line=>JSON.parse(line)):[]
const launch=prior.filter(item=>item.kind==='launch').length+1
if(launch>2){record({kind:'failure',message:'Unexpected third launch'});app.exit(1)}
app.whenReady().then(async()=>{
  const url=process.env.VITE_DEV_SERVER_URL
  const healthURL=new URL('health.txt',url);healthURL.hostname='127.0.0.1'
  const response=await fetch(healthURL),health=await response.text()
  if(health!=='nova-dev-server-live')throw Error('Vite server unavailable')
  const window=new BrowserWindow({show:false,webPreferences:{sandbox:true}})
  const rendererURL=new URL(url);rendererURL.hostname='127.0.0.1'
  await window.loadURL(rendererURL.toString())
  record({kind:'launch',launch,url,health})
  await new Promise(resolve=>setTimeout(resolve,250))
  const code=launch===1?75:0
  record({kind:'exit-request',launch,code})
  app.exit(code)
}).catch(error=>{record({kind:'failure',message:String(error.stack||error),cause:String(error.cause?.stack||error.cause||'')});app.exit(1)})
`)
  const env={...process.env};delete env.ELECTRON_RUN_AS_NODE
  const child=spawn(process.execPath,[viteCli,'--config',path.join(output,'vite.config.mjs'),'--host','127.0.0.1'],{cwd:output,env,stdio:['ignore','pipe','pipe'],windowsHide:true})
  let stdout='',stderr='',timedOut=false
  child.stdout.on('data',chunk=>{stdout+=chunk.toString()})
  child.stderr.on('data',chunk=>{stderr+=chunk.toString()})
  const deadline=45000
  const timer=setTimeout(()=>{timedOut=true;child.kill()},deadline)
  let exit
  try{exit=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',(code,signal)=>resolve({code,signal}))})}
  finally{clearTimeout(timer);fs.writeFileSync(path.join(output,'stdout.log'),stdout);fs.writeFileSync(path.join(output,'stderr.log'),stderr)}
  assert.equal(timedOut,false,'Restart smoke exceeded '+deadline+' milliseconds')
  assert.equal(exit.code,0,stderr)
  const events=fs.readFileSync(path.join(output,'events.jsonl'),'utf8').trim().split('\n').map(line=>JSON.parse(line))
  const launches=events.filter(item=>item.kind==='launch'),requests=events.filter(item=>item.kind==='exit-request')
  assert.deepEqual(events.filter(item=>item.kind==='failure'),[])
  assert.equal(launches.length,2);assert.notEqual(launches[0].pid,launches[1].pid)
  assert.equal(launches[0].url,launches[1].url)
  assert.deepEqual(requests.map(item=>item.code),[75,0])
  assert.equal(/taskkill|no se encontr|not found|broken pipe|EPIPE/i.test(stdout+'\n'+stderr),false)
  const result={success:true,launches:launches.map(({pid,url,launch})=>({pid,url,launch})),exitCodes:requests.map(item=>item.code),viteExit:exit,taskkillError:false}
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2)+'\n')
  process.stdout.write(JSON.stringify({success:true,output,result})+'\n')
}
run().catch(error=>{process.stderr.write(String(error.stack||error)+'\n');process.exitCode=1})
