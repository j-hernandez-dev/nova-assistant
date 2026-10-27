const { test } = require('node:test'), assert = require('node:assert/strict')
const { guardElectronDevExit } = require('../dev/electron_exit.cjs')
const { launchElectronDev } = require('../dev/electron_exit.cjs')
const { reloadOrLaunchElectronDev } = require('../dev/electron_exit.cjs')
const { EventEmitter } = require('node:events')

test('normal and signaled Electron exits do not taskkill a dead PID', async () => {
  for (const child of [{ exitCode: 0, signalCode: null }, { exitCode: null, signalCode: 'SIGTERM' }]) {
    const host = { electronApp: child }
    const startup = { exit: async () => { throw Error('must not kill an exited process') } }
    guardElectronDevExit(startup, host)
    const wrapped = startup.exit
    guardElectronDevExit(startup, host)
    assert.equal(startup.exit, wrapped)
    await startup.exit()
    assert.equal(host.electronApp, undefined)
  }
})

test('live Electron restart cleanup still runs and genuine failures remain visible', async () => {
  const host = { electronApp: { exitCode: null, signalCode: null } }
  const failure = Error('real cleanup failure')
  const startup = { exit: async () => { throw failure } }
  guardElectronDevExit(startup, host)
  await assert.rejects(startup.exit(), error => error === failure)
  assert.ok(host.electronApp)
})

test('only requested storage restart reopens Electron while retaining the dev server', async () => {
  const exits=[],children=[]
  const host={exit:code=>exits.push(code),electronApp:undefined}
  const startup=Object.assign(async()=>{
    const child=Object.assign(new EventEmitter(),{exitCode:null,signalCode:null})
    children.push(child);host.electronApp=child;child.once('exit',host.exit)
  },{exit:async()=>{}})
  await launchElectronDev(startup,host)
  children[0].exitCode=75;children[0].emit('exit',75,null)
  await new Promise(resolve=>setTimeout(resolve,250))
  assert.equal(children.length,2);assert.deepEqual(exits,[])
  children[1].exitCode=0;children[1].emit('exit',0,null)
  assert.deepEqual(exits,[0]);assert.equal(host.electronApp,undefined)
})

test('parallel preload/main startup is coalesced and live preloads reload the existing process', async () => {
  let release,starts=0,reloads=0
  const host={exit:()=>{},electronApp:undefined}
  const startup=Object.assign(async()=>{
    starts++;await new Promise(resolve=>{release=resolve})
    host.electronApp=Object.assign(new EventEmitter(),{exitCode:null,signalCode:null})
    host.electronApp.once('exit',host.exit)
  },{exit:async()=>{}})
  const main=launchElectronDev(startup,host)
  const preload=reloadOrLaunchElectronDev(startup,()=>{reloads++},host)
  assert.equal(starts,1);release();await Promise.all([main,preload])
  assert.equal(reloads,0)
  await reloadOrLaunchElectronDev(startup,()=>{reloads++},host)
  assert.equal(starts,1);assert.equal(reloads,1)
})

test('a preload finishing during requested restart starts once and cancels the older timer', async () => {
  const children=[],exits=[],host={exit:code=>exits.push(code),electronApp:undefined}
  const startup=Object.assign(async()=>{
    host.electronApp=Object.assign(new EventEmitter(),{exitCode:null,signalCode:null})
    children.push(host.electronApp);host.electronApp.once('exit',host.exit)
  },{exit:async()=>{}})
  await launchElectronDev(startup,host)
  children[0].exitCode=75;children[0].emit('exit',75,null)
  await reloadOrLaunchElectronDev(startup,()=>{throw Error('must start, not reload')},host)
  await new Promise(resolve=>setTimeout(resolve,250))
  assert.equal(children.length,2);assert.deepEqual(exits,[])
  children[1].exitCode=0;children[1].emit('exit',0,null)
  assert.deepEqual(exits,[0])
})
