const {test} = require('node:test')
const assert = require('node:assert/strict')
require('./register_typescript.cjs')
const {recheckBackend} = require('../src/backend_recovery.ts')

test('A disconnected backend restarts before readiness refresh, without submitting any turn', async () => {
  const events=[]
  await recheckBackend(false, {restartBackend:async()=>{events.push('restart');return {success:true}},
    refreshReadiness:async()=>events.push('readiness')})
  assert.deepEqual(events,['restart','readiness'])
})
test('An Ollama outage on a connected backend only rechecks readiness', async () => {
  await recheckBackend(true, {restartBackend:async()=>assert.fail('must not restart a live backend'),
    refreshReadiness:async()=>true})
})
test('Rejected or disconnected restart remains a visible failure without repeated restart', async () => {
  let calls=0
  await assert.rejects(recheckBackend(false,{restartBackend:async()=>{calls++;return {success:false}},
    refreshReadiness:async()=>assert.fail('no successful restart')}), /BACKEND_RESTART_FAILED/)
  assert.equal(calls,1)
  await assert.rejects(recheckBackend(false,{restartBackend:async()=>{throw new Error('IPC disconnected')},
    refreshReadiness:async()=>assert.fail('no successful restart')}), /IPC disconnected/)
})
